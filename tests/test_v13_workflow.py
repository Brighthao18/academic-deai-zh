"""Simulated engineering fixtures, not model evidence or writing-effect scores."""
import copy
import unittest

from test_deai_core import c, simulated_review
from test_v12_scope import quote, unit, evidence, binding


def fixture(scope="本项目的", keep_scope=True):
    topic = scope + "随访安排"
    doc = c.document_from_text("下面介绍" + topic + "。参与者完成登记后进入随访，失访原因由研究护士记录。招募尚未开始。")
    kept = topic if keep_scope else "随访安排"
    after = kept + "：参与者完成登记后进入随访，失访原因由研究护士记录。招募尚未开始。"
    b = c.build_bundle(doc, {"original_hash": doc.hash,
        "review_policy": {"require_information_units": True, "require_benefit": True},
        "edits": [{"paragraph_id": "p00001", "new": after, "reason": "SIMULATED: expose the full topic, removing only navigation"}]})
    request = c.build_review_request(doc, b)
    preview = unit("preview", "discourse_preview", doc.text.split("。")[0], "", doc.text, after)
    preview["topic_units"] = ["topic"]
    topic_unit = unit("topic", "topic", kept, kept, doc.text, after)
    review = simulated_review(doc, b)
    row = review["transactions"][0]
    row["information_review"] = evidence(doc, after, [preview, topic_unit], [])
    for marker in c.MODAL_RE.finditer(kept):
        row["information_review"]["qualifier_bindings"].append(
            binding("topic", [quote(doc.text, marker.group())], [quote(after, marker.group())]))
    row["information_review"]["verbatim_units"] = [
        {"id": v["id"], "status": "pass", "note": "SIMULATED: clause and its contextual governance were reviewed"}
        for v in request["information_requirements"][0]["verbatim_candidates"]]
    row["benefit_review"] = {"status": "pass", "problem_type": "buried_topic",
        "problem_before": [quote(doc.text, doc.text.split("。")[0])],
        "resolution_after": [quote(after, kept)],
        "observed_gain": "SIMULATED: direct topic labels the unchanged operations without a navigation sentence",
        "note": "SIMULATED: source topic, phase and responsibilities remain"}
    return doc, after, b, review, request


class VerbatimCoverage(unittest.TestCase):
    def test_unchanged_facts_and_negations_need_no_redundant_anchor_forms(self):
        doc, after, b, review, request = fixture()
        final, report = c.apply_bundle(doc, b, review)
        self.assertEqual(final, after)
        self.assertEqual(report["status"], "checked_edit")
        self.assertEqual(len(request["information_requirements"][0]["verbatim_candidates"]), 3)
        self.assertEqual(review["transactions"][0]["information_review"]["qualifier_bindings"], [])

    def test_request_does_not_generate_any_pass_verdict(self):
        request = fixture()[-1]
        row = request["review_template"]["transactions"][0]
        self.assertEqual(row["information_review"]["status"], "unknown")
        self.assertEqual(row["information_review"]["verbatim_units"], [])
        self.assertTrue(all("status" not in v for v in request["information_requirements"][0]["verbatim_candidates"]))

    def test_copy_missing_unknown_failed_forged_duplicate_and_extra_fields_reject(self):
        for mode in ("missing", "unknown", "fail", "forged", "duplicate", "extra", "no_note"):
            with self.subTest(mode=mode):
                doc, _, b, review, _ = fixture()
                rows = review["transactions"][0]["information_review"]["verbatim_units"]
                if mode == "missing": rows.pop()
                elif mode in ("unknown", "fail"): rows[0]["status"] = mode
                elif mode == "forged": rows[0]["id"] = "not-a-source-copy"
                elif mode == "duplicate": rows.append(copy.deepcopy(rows[0]))
                elif mode == "extra": rows[0]["before"] = []
                else: rows[0]["note"] = ""
                self.assertEqual(c.apply_bundle(doc, b, review)[0], doc.text)

    def test_copies_do_not_bypass_global_or_dimension_or_benefit_reviews(self):
        for mode in ("global", "dimension", "benefit"):
            with self.subTest(mode=mode):
                doc, _, b, review, _ = fixture()
                if mode == "global": review["global_coherence"]["status"] = "unknown"
                elif mode == "dimension": review["transactions"][0]["dimensions"]["condition"]["status"] = "fail"
                else: review["transactions"][0]["benefit_review"]["status"] = "fail"
                self.assertEqual(c.apply_bundle(doc, b, review)[0], doc.text)

    def test_changed_or_newly_governed_clause_cannot_claim_literal_copy(self):
        for after in ("流程：项目已整理材料。", "流程：项目拟认真整理材料。", "流程：可能项目拟整理材料。"):
            doc = c.document_from_text("下面介绍流程。项目拟整理材料。")
            b = c.build_bundle(doc, {"original_hash": doc.hash, "review_policy": {"require_information_units": True},
                "edits": [{"paragraph_id": "p00001", "new": after, "reason": "SIMULATED changed clause"}]})
            candidates = c.build_review_request(doc, b)["information_requirements"][0]["verbatim_candidates"]
            self.assertFalse(any(v["before"]["text"] == "项目拟整理材料" for v in candidates))

    def test_source_positions_remain_exact_with_unicode_newlines_and_prior_edits(self):
        doc = c.document_from_text("下面介绍💡流程。甲仍在核对。\r\n\r\n下面介绍乙的安排。乙尚未登记。")
        paras = c.parse_document(doc)["paragraphs"]
        b = c.build_bundle(doc, {"original_hash": doc.hash, "review_policy": {"require_information_units": True},
            "edits": [{"paragraph_id": p["id"], "new": p["text"].replace("下面介绍", "").replace("。", "：", 1),
                       "reason": "SIMULATED navigation only"} for p in paras]})
        request = c.build_review_request(doc, b)
        count = 0
        for requirement in request["information_requirements"]:
            for pair in requirement["verbatim_candidates"]:
                count += 1
                for side in ("before", "after"):
                    span = pair[side]
                    self.assertEqual(request[side][span["start"]:span["end"]], span["text"])
                self.assertEqual(pair["before"]["text"], pair["after"]["text"])
        self.assertEqual(count, 2)

    def test_duplicate_manual_binding_cannot_reuse_copied_marker(self):
        doc, after, b, review, request = fixture()
        pair = request["information_requirements"][0]["verbatim_candidates"][-1]
        review["transactions"][0]["information_review"]["qualifier_bindings"] = [
            binding(pair["id"], [quote(doc.text, "尚未")], [quote(after, "尚未")])]
        self.assertEqual(c.apply_bundle(doc, b, review)[0], doc.text)

    def test_stale_candidate_review_never_releases_copy(self):
        doc, _, b, review, _ = fixture()
        b["patches"][0]["new"] += "其他"
        self.assertEqual(c.apply_bundle(doc, b, review)[0], doc.text)


class ScopeLoss(unittest.TestCase):
    def test_exposed_d11_style_scope_loss_is_rejected_even_with_model_pass(self):
        doc, _, b, review, _ = fixture(keep_scope=False)
        final, report = c.apply_bundle(doc, b, review)
        self.assertEqual(final, doc.text)
        self.assertIn("preview_scope_not_preserved", report["transactions"][0]["reasons"])

    def test_scope_variants_must_be_retained(self):
        for scope in ("本研究的", "该队列的", "本阶段的", "本院的", "截至目前的", "仅在成人中的"):
            with self.subTest(scope=scope):
                doc, _, b, review, _ = fixture(scope, False)
                self.assertEqual(c.apply_bundle(doc, b, review)[0], doc.text)
                doc, after, b, review, _ = fixture(scope, True)
                self.assertEqual(c.apply_bundle(doc, b, review)[0], after)

    def test_splitting_preview_spans_does_not_hide_scope(self):
        doc, _, b, review, _ = fixture(keep_scope=False)
        preview = review["transactions"][0]["information_review"]["units"][0]
        preview["before"] = [quote(doc.text, "下面介绍本项"), quote(doc.text, "目的随访安排")]
        self.assertEqual(c.apply_bundle(doc, b, review)[0], doc.text)


class QuoteBinding(unittest.TestCase):
    def quoted_review(self):
        doc, after, b, review, request = fixture()
        raw = copy.deepcopy(review)
        def replace(value):
            if isinstance(value, dict):
                if set(value) == {"start", "end", "text"}:
                    return {"text": value["text"]}
                return {k: replace(v) for k, v in value.items()}
            if isinstance(value, list): return [replace(v) for v in value]
            return value
        return doc, after, b, review, replace(raw)

    def test_bind_and_apply_real_shape_without_manual_offsets(self):
        doc, after, b, review, raw = self.quoted_review()
        self.assertEqual(c.bind_review(doc, b, raw), review)
        self.assertEqual(c.apply_bundle(doc, b, c.bind_review(doc, b, raw))[0], after)

    def test_binding_keeps_explicit_failure_and_input_unchanged(self):
        doc, _, b, _, raw = self.quoted_review()
        raw["transactions"][0]["status"] = "fail"
        original = copy.deepcopy(raw)
        bound = c.bind_review(doc, b, raw)
        self.assertEqual(raw, original)
        self.assertEqual(bound["transactions"][0]["status"], "fail")
        self.assertEqual(c.apply_bundle(doc, b, bound)[0], doc.text)

    def test_fabricated_invalid_and_out_of_range_quote_references_reject(self):
        for ref in ({"text": "并不存在"}, {"text": "下面介绍", "occurrence": True},
                    {"text": "下面介绍", "occurrence": -1}, {"text": "下面介绍", "occurrence": 2},
                    {"text": "下面介绍", "extra": 0}, {"text": ""}):
            doc, _, b, _, raw = self.quoted_review()
            raw["transactions"][0]["benefit_review"]["problem_before"] = [ref]
            with self.assertRaises(c.InputError): c.bind_review(doc, b, raw)

    def test_ambiguous_quotation_requires_explicit_occurrence(self):
        doc = c.document_from_text("甲拟登记。甲拟核对。")
        b = c.build_bundle(doc, {"original_hash": doc.hash, "edits": []})
        raw = {"before_hash": doc.hash, "after_hash": doc.hash, "transactions": [
            {"benefit_review": {"problem_before": [{"text": "甲"}]}}]}
        with self.assertRaises(c.InputError): c.bind_review(doc, b, raw)
        raw["transactions"][0]["benefit_review"]["problem_before"][0]["occurrence"] = 1
        bound = c.bind_review(doc, b, raw)
        self.assertEqual(bound["transactions"][0]["benefit_review"]["problem_before"], [quote(doc.text, "甲", 1)])

    def test_stale_hashes_reject_before_any_binding(self):
        for key in ("before_hash", "after_hash"):
            doc, _, b, _, raw = self.quoted_review()
            raw[key] = "stale"
            with self.assertRaises(c.InputError): c.bind_review(doc, b, raw)

    def test_malformed_nested_evidence_is_controlled_error(self):
        for value in (None, [None], "bad"):
            doc, _, b, _, raw = self.quoted_review()
            raw["transactions"][0]["information_review"]["units"] = value
            with self.assertRaises(c.InputError): c.bind_review(doc, b, raw)


def compact_review(raw):
    out = copy.deepcopy(raw)
    out["review_format"] = "compact-1"
    for row in out["transactions"]:
        for value in [*row["dimensions"].values(), *row["claims"]]:
            value.pop("before"); value.pop("after")
        info = row["information_review"]
        info.pop("before_hash"); info.pop("after_hash")
        for unit in info["units"]:
            unit.pop("pure_discourse"); unit.pop("no_research_commitment")
            if unit["kind"] == "discourse_preview": unit.pop("after")
            else: unit.pop("topic_units")
            for key in ("subject", "action", "conditions"): unit.pop(key)
    return out


class CompactBinding(unittest.TestCase):
    def test_compact_and_full_reviews_reach_same_candidate(self):
        doc, after, b, full, raw = QuoteBinding().quoted_review()
        compact = compact_review(raw)
        bound = c.bind_review(doc, b, compact)
        self.assertEqual(c.apply_bundle(doc, b, bound)[0], after)
        self.assertEqual(bound["transactions"][0]["dimensions"]["subject"]["before"], doc.text)
        self.assertFalse(bound["binding_metadata"]["verdicts_generated"])
        self.assertEqual(c.bind_review(doc, b, bound), bound)

    def test_compact_missing_or_negative_judgment_still_rolls_back(self):
        for mode in ("missing", "fail", "unknown"):
            doc, _, b, _, raw = QuoteBinding().quoted_review()
            compact = compact_review(raw)
            dimensions = compact["transactions"][0]["dimensions"]
            if mode == "missing": dimensions.pop("condition")
            else: dimensions["condition"]["status"] = mode
            bound = c.bind_review(doc, b, compact)
            self.assertEqual(c.apply_bundle(doc, b, bound)[0], doc.text)

    def test_compact_does_not_fill_unit_or_benefit_status(self):
        doc, _, b, _, raw = QuoteBinding().quoted_review()
        compact = compact_review(raw)
        compact["transactions"][0]["information_review"]["units"][0].pop("status")
        bound = c.bind_review(doc, b, compact)
        self.assertNotIn("status", bound["transactions"][0]["information_review"]["units"][0])
        self.assertEqual(c.apply_bundle(doc, b, bound)[0], doc.text)

    def test_compact_conflicting_flags_hash_and_preview_fields_reject(self):
        for mode in ("flag", "hash", "preview_after", "dimension_text"):
            doc, _, b, _, raw = QuoteBinding().quoted_review()
            compact = compact_review(raw)
            row = compact["transactions"][0]
            if mode == "flag": row["information_review"]["units"][0]["pure_discourse"] = False
            elif mode == "hash": row["information_review"]["after_hash"] = "stale"
            elif mode == "preview_after": row["information_review"]["units"][0]["after"] = []
            else: row["dimensions"]["subject"]["before"] = "override"
            with self.assertRaises(c.InputError): c.bind_review(doc, b, compact)


if __name__ == "__main__":
    unittest.main()

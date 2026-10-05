"""v1.2 evidence-gate engineering fixtures; no models or style-effect evidence.

V11-03/07 are explicitly exposed development regressions, never holdout cases.
"""
import copy
import unittest

from test_deai_core import c, patch, bundle, simulated_review


def quote(text, value, occurrence=0):
    start = -1
    for _ in range(occurrence + 1):
        start = text.find(value, start + 1)
    assert start >= 0, value
    return {"start": start, "end": start + len(value), "text": value}


def unit(uid, kind, before, after, before_text, after_text, subject="", action="", conditions=()):
    item = {"id": uid, "kind": kind, "status": "pass", "before": [quote(before_text, before)],
            "after": [quote(after_text, after)] if after else [], "pure_discourse": kind == "discourse_preview",
            "no_research_commitment": kind == "discourse_preview", "topic_units": [],
            "note": "SIMULATED: exact proposition and source coverage"}
    for key, values in (("subject", [subject] if subject else []), ("action", [action] if action else []),
                        ("conditions", conditions)):
        item[key] = {"before": [quote(before_text, v) for v in values],
                     "after": [quote(after_text, v) for v in values]}
    return item


def evidence(doc, after, units, bindings):
    return {"status": "pass", "before_hash": doc.hash, "after_hash": c.text_hash(after),
            "covered_paragraph_ids": ["p00001"], "units": units, "qualifier_bindings": bindings,
            "topic_preserved": {"status": "pass", "note": "SIMULATED: the exact research topic survives"}}


def binding(uid, before, after):
    return {"unit_id": uid, "status": "pass", "before": before, "after": after,
            "note": "SIMULATED: this marker still governs the same anchored proposition"}


def planned_fixture():
    doc = c.document_from_text("项目拟检查甲材料、项目拟检查乙材料。")
    after = "项目拟检查甲材料、检查乙材料。"
    b = bundle(doc, [patch(doc, "项目拟检查乙材料", "检查乙材料")])
    b["review_policy"] = {"require_information_units": True}
    review = simulated_review(doc, b)
    units = [unit("甲", "research_fact", "项目拟检查甲材料", "项目拟检查甲材料", doc.text, after,
                  "项目", "检查甲材料"),
             unit("乙", "research_fact", "项目拟检查乙材料", "项目拟检查甲材料、检查乙材料", doc.text, after,
                  "项目", "检查乙材料")]
    # Resolve the second explicit subject rather than fabricate its occurrence.
    units[1]["subject"] = {"before": [quote(doc.text, "项目", 1)], "after": [quote(after, "项目")]}
    binds = [binding("甲", [quote(doc.text, "拟", 0)], [quote(after, "拟")]),
             binding("乙", [quote(doc.text, "拟", 1)], [quote(after, "拟")])]
    review["transactions"][0]["information_review"] = evidence(doc, after, units, binds)
    return doc, after, b, review


class ScopeEvidence(unittest.TestCase):
    def assert_rollback(self, fixture, mutate):
        doc, _, b, review = fixture
        mutate(b, review)
        final, report = c.apply_bundle(doc, b, review)
        self.assertEqual(final, doc.text)
        self.assertEqual(report["status"], "all_rollback")
        return report

    def test_positive_marker_decrease_has_raw_fail_and_model_adjudicated_pass(self):
        doc, after, b, review = planned_fixture()
        final, report = c.apply_bundle(doc, b, review)
        self.assertEqual(final, after)
        self.assertEqual(report["status"], "checked_edit")
        self.assertEqual(report["final_mechanical"]["status"], "fail")
        self.assertEqual(report["final_validation"]["status"], "pass")
        self.assertTrue(report["final_validation"]["count_adjudicated_by_model"])
        self.assertFalse(report["equivalence_proven"])

    def test_default_unknown_template_cannot_release_scope_edit(self):
        doc, _, b, _ = planned_fixture()
        request = c.build_review_request(doc, b)
        self.assertTrue(request["information_requirements"][0]["before_scope_spans"])
        self.assertEqual(request["review_template"]["transactions"][0]["information_review"]["status"], "unknown")
        self.assertEqual(c.apply_bundle(doc, b, request["review_template"])[0], doc.text)

    def test_missing_evidence_rejects_even_semantic_pass(self):
        self.assert_rollback(planned_fixture(), lambda b, r: r["transactions"][0].pop("information_review"))

    def test_information_fail_or_unknown_rejects(self):
        for status in ("fail", "unknown"):
            with self.subTest(status=status):
                self.assert_rollback(planned_fixture(), lambda b, r: r["transactions"][0]["information_review"].update(status=status))

    def test_semantic_fail_or_unknown_cannot_be_overridden(self):
        for status in ("fail", "unknown"):
            with self.subTest(status=status):
                self.assert_rollback(planned_fixture(), lambda b, r: r["transactions"][0].update(status=status))

    def test_stale_evidence_hash_rejects(self):
        self.assert_rollback(planned_fixture(), lambda b, r: r["transactions"][0]["information_review"].update(after_hash="stale"))

    def test_fabricated_offset_rejects(self):
        self.assert_rollback(planned_fixture(), lambda b, r: r["transactions"][0]["information_review"]["units"][0]["before"][0].update(start=1))

    def test_placeholder_fact_rejects(self):
        self.assert_rollback(planned_fixture(), lambda b, r: r["transactions"][0]["information_review"]["units"][0]["action"]["before"][0].update(text="待填"))

    def test_omitted_second_proposition_rejects(self):
        self.assert_rollback(planned_fixture(), lambda b, r: r["transactions"][0]["information_review"]["units"].pop())

    def test_one_whole_sentence_unit_cannot_hide_second_action(self):
        def mutate(b, r):
            info = r["transactions"][0]["information_review"]
            info["units"][0]["before"] = [quote(planned_fixture()[0].text, planned_fixture()[0].text)]
            info["units"][0]["after"] = [quote(planned_fixture()[1], planned_fixture()[1])]
            info["units"].pop()
            info["qualifier_bindings"] = [binding("甲", [quote(planned_fixture()[0].text, "拟", 0), quote(planned_fixture()[0].text, "拟", 1)], [quote(planned_fixture()[1], "拟")])]
        report = self.assert_rollback(planned_fixture(), mutate)
        self.assertIn("information_scope_without_proposition_witness_before", report["transactions"][0]["reasons"])

    def test_duplicate_atom_id_rejects(self):
        self.assert_rollback(planned_fixture(), lambda b, r: r["transactions"][0]["information_review"]["units"][1].update(id="甲"))

    def test_original_marker_occurrence_cannot_explain_two_propositions(self):
        def mutate(b, r):
            info = r["transactions"][0]["information_review"]
            info["qualifier_bindings"][1]["before"] = info["qualifier_bindings"][0]["before"]
        self.assert_rollback(planned_fixture(), mutate)

    def test_duplicate_after_marker_within_one_binding_rejects(self):
        self.assert_rollback(planned_fixture(), lambda b, r: r["transactions"][0]["information_review"]["qualifier_bindings"][1]["after"].append(copy.deepcopy(r["transactions"][0]["information_review"]["qualifier_bindings"][1]["after"][0])))

    def test_changed_subject_action_or_condition_rejects(self):
        for field in ("subject", "action", "conditions"):
            with self.subTest(field=field):
                def mutate(b, r):
                    r["transactions"][0]["information_review"]["units"][1][field]["after"] = [quote(planned_fixture()[1], "检查甲材料")]
                self.assert_rollback(planned_fixture(), mutate)

    def test_negative_marker_loss_cannot_be_adjudicated(self):
        doc = c.document_from_text("项目未检查甲材料、项目未检查乙材料。")
        after = "项目未检查甲材料、项目检查乙材料。"
        b = bundle(doc, [patch(doc, "项目未检查乙材料", "项目检查乙材料")])
        review = simulated_review(doc, b)
        units = [unit("甲", "research_fact", "项目未检查甲材料", "项目未检查甲材料", doc.text, after, "项目", "检查甲材料"),
                 unit("乙", "research_fact", "项目未检查乙材料", "项目检查乙材料", doc.text, after, "项目", "检查乙材料")]
        units[1]["subject"] = {"before": [quote(doc.text, "项目", 1)], "after": [quote(after, "项目", 1)]}
        review["transactions"][0]["information_review"] = evidence(doc, after, units, [binding("甲", [quote(doc.text, "未")], [quote(after, "未")]), binding("乙", [quote(doc.text, "未", 1)], [quote(after, "未")])])
        final, report = c.apply_bundle(doc, b, review)
        self.assertEqual(final, doc.text)
        self.assertEqual(report["transactions"][0]["model_adjudications"], [])

    def test_marker_substitution_and_increase_remain_hard(self):
        for before, after in (("项目拟检查材料。", "项目已检查材料。"), ("项目检查材料。", "项目拟检查材料。")):
            doc = c.document_from_text(before)
            b = bundle(doc, [patch(doc, before, after)])
            self.assertEqual(c.apply_bundle(doc, b, simulated_review(doc, b))[0], before)

    def test_recognized_modality_scope_mismatch_stays_hard(self):
        check = c.mechanical_check("甲组拟检查材料，乙组已检查材料。", "甲组已检查材料，乙组拟检查材料。")
        self.assertIn("modality_scope_changed", [e["code"] for e in check["errors"]])

    def test_shared_after_marker_cannot_cross_repeated_subject(self):
        doc, _, b, review = planned_fixture()
        after = "项目拟检查甲材料、项目检查乙材料。"
        b["patches"][0]["new"] = "项目检查乙材料"
        review = simulated_review(doc, b)
        units = [unit("甲", "research_fact", "项目拟检查甲材料", "项目拟检查甲材料", doc.text, after, "项目", "检查甲材料"),
                 unit("乙", "research_fact", "项目拟检查乙材料", "项目检查乙材料", doc.text, after, "项目", "检查乙材料")]
        units[1]["subject"] = {"before": [quote(doc.text, "项目", 1)], "after": [quote(after, "项目", 1)]}
        review["transactions"][0]["information_review"] = evidence(doc, after, units,
            [binding("甲", [quote(doc.text, "拟")], [quote(after, "拟")]), binding("乙", [quote(doc.text, "拟", 1)], [quote(after, "拟")])])
        final, report = c.apply_bundle(doc, b, review)
        self.assertEqual(final, doc.text)
        self.assertIn("shared_qualifier_governance_ambiguous", report["transactions"][0]["reasons"])

    def test_hard_number_and_citation_changes_keep_original(self):
        for before, after in (("项目拟检查12例、项目拟检查材料。", "项目拟检查13例、检查材料。"),
                              ("项目拟检查材料[1]、项目拟检查记录。", "项目拟检查材料[2]、检查记录。")):
            doc = c.document_from_text(before)
            b = bundle(doc, [patch(doc, before, after)])
            self.assertEqual(c.apply_bundle(doc, b)[0], before)

    def test_actual_quote_substring_cannot_be_scope_evidence(self):
        doc = c.document_from_text("“项目拟检查甲材料、项目拟检查乙材料。”")
        after = "“项目拟检查甲材料、检查乙材料。”"
        b = bundle(doc, [patch(doc, "项目拟检查乙材料", "检查乙材料")])
        review = {"transactions": [{}]}
        units = [unit("甲", "research_fact", "项目拟检查甲材料", "项目拟检查甲材料", doc.text, after, "项目", "检查甲材料"),
                 unit("乙", "research_fact", "项目拟检查乙材料", "项目拟检查甲材料、检查乙材料", doc.text, after, "项目", "检查乙材料")]
        units[1]["subject"]["before"] = [quote(doc.text, "项目", 1)]
        review["transactions"][0]["information_review"] = evidence(doc, after, units,
            [binding("甲", [quote(doc.text, "拟")], [quote(after, "拟")]), binding("乙", [quote(doc.text, "拟", 1)], [quote(after, "拟")])])
        reasons = c._information_check(doc, after, c.parse_document(doc), b["patches"], b["patches"], review["transactions"][0])
        final, report = c.apply_bundle(doc, b, review)
        self.assertEqual(final, doc.text)
        self.assertIn("information_quoted_content_not_adjudicable", reasons)

    def test_partial_rollback_cannot_reuse_count_evidence_for_different_final_hash(self):
        doc, _, b, review = planned_fixture()
        combined = c.document_from_text(doc.text + "\n\n综上所述，记录一致。")
        b = bundle(combined, [patch(combined, "项目拟检查乙材料", "检查乙材料", "a"),
                              patch(combined, "综上所述，", "", "b")])
        review = simulated_review(combined, b)
        after = c._apply(combined.text, b["patches"])
        info = planned_fixture()[3]["transactions"][0]["information_review"]
        info.update(before_hash=combined.hash, after_hash=c.text_hash(after))
        review["transactions"][0]["information_review"] = info
        review["transactions"][1]["status"] = "unknown"
        partial = c._apply(combined.text, [b["patches"][0]])
        coherence = copy.deepcopy(review["global_coherence"])
        coherence["after_hash"] = c.text_hash(partial)
        final, report = c.apply_bundle(combined, b, review, coherence_review=coherence)
        self.assertEqual(final, combined.text)
        self.assertEqual(report["attempts"][0]["transactions"][0]["status"], "accepted")
        self.assertIn("merged_mechanical_check_failed", report["transactions"][0]["reasons"])

    def test_duplicate_or_conflicting_legacy_claims_reject(self):
        for extra in ("duplicate", "fail", "extra"):
            doc = c.document_from_text("综上所述，记录一致。")
            b = bundle(doc, [patch(doc, "综上所述，", "")])
            review = simulated_review(doc, b)
            claim = copy.deepcopy(review["transactions"][0]["claims"][0])
            if extra == "fail":
                claim["status"] = "fail"
            if extra == "extra":
                claim["id"] = "unexpected"
            review["transactions"][0]["claims"].append(claim)
            self.assertEqual(c.apply_bundle(doc, b, review)[0], doc.text)

    def test_duplicate_covered_patch_ids_reject(self):
        doc, _, b, review = planned_fixture()
        review["transactions"][0]["covered_patch_ids"].append(b["patches"][0]["id"])
        self.assertEqual(c.apply_bundle(doc, b, review)[0], doc.text)

    def test_policy_cannot_be_disabled_in_repair(self):
        doc, _, b, review = planned_fixture()
        review["transactions"][0]["status"] = "unknown"
        repair = copy.deepcopy(b)
        repair.pop("review_policy")
        final, report = c.apply_bundle(doc, b, review, repair, simulated_review(doc, repair))
        self.assertEqual(final, doc.text)
        self.assertEqual(report["status"], "execution_failed")


class PreviewAndBenefit(unittest.TestCase):
    def qualifier_split_fixture(self, merged=False):
        doc = c.document_from_text("下面介绍流程。材料尚未核对，不进入编码。")
        after = "流程：材料尚未核对，不进入编码。"
        b = c.build_bundle(doc, {"original_hash": doc.hash, "review_policy": {"require_information_units": True},
            "edits": [{"paragraph_id": "p00001", "new": after, "reason": "SIMULATED: retain flow topic and unchanged conditions"}]})
        review = simulated_review(doc, b)
        preview = unit("预告", "discourse_preview", "下面介绍", "", doc.text, after)
        preview["topic_units"] = ["主题"]
        units = [preview, unit("主题", "topic", "流程", "流程", doc.text, after),
                 unit("条件", "condition", "材料尚未核对，不进入编码", "材料尚未核对，不进入编码", doc.text, after)]
        if merged:
            bindings = [binding("条件", [quote(doc.text, "尚未"), quote(doc.text, "不")],
                                [quote(after, "尚未"), quote(after, "不")])]
        else:
            bindings = [binding("条件", [quote(doc.text, marker)], [quote(after, marker)]) for marker in ("尚未", "不")]
        review["transactions"][0]["information_review"] = evidence(doc, after, units, bindings)
        return doc, after, b, review

    def test_same_unit_merged_and_split_qualifier_records_are_equivalent(self):
        for merged in (True, False):
            with self.subTest(merged=merged):
                doc, after, b, review = self.qualifier_split_fixture(merged)
                final, report = c.apply_bundle(doc, b, review)
                self.assertEqual(final, after)
                self.assertEqual(report["status"], "checked_edit")

    def test_split_qualifier_records_cannot_reuse_original_occurrence(self):
        doc, _, b, review = self.qualifier_split_fixture()
        rows = review["transactions"][0]["information_review"]["qualifier_bindings"]
        rows.append(copy.deepcopy(rows[0]))
        final, report = c.apply_bundle(doc, b, review)
        self.assertEqual(final, doc.text)
        self.assertIn("qualifier_original_occurrence_reused", report["transactions"][0]["reasons"])

    def test_split_qualifier_records_cannot_swap_marker_correspondence(self):
        doc, after, b, review = self.qualifier_split_fixture()
        rows = review["transactions"][0]["information_review"]["qualifier_bindings"]
        rows[0]["after"] = [quote(after, "不")]
        rows[1]["after"] = [quote(after, "尚未")]
        final, report = c.apply_bundle(doc, b, review)
        self.assertEqual(final, doc.text)
        self.assertIn("qualifier_proposition_status_changed", report["transactions"][0]["reasons"])

    def test_split_qualifier_records_still_require_all_pass_and_complete_coverage(self):
        for status in ("fail", "unknown", "missing"):
            with self.subTest(status=status):
                doc, _, b, review = self.qualifier_split_fixture()
                rows = review["transactions"][0]["information_review"]["qualifier_bindings"]
                if status == "missing":
                    rows.pop()
                else:
                    rows[1]["status"] = status
                final, report = c.apply_bundle(doc, b, review)
                self.assertEqual(final, doc.text)
                self.assertEqual(report["status"], "all_rollback")

    def preview_fixture(self):
        doc = c.document_from_text("下面介绍随访安排。项目拟联系受试者。")
        after = "随访安排：项目拟联系受试者。"
        b = c.build_bundle(doc, {"original_hash": doc.hash,
            "review_policy": {"require_information_units": True, "require_benefit": True},
            "edits": [{"paragraph_id": "p00001", "new": after, "reason": "SIMULATED: retain topic while removing navigation"}]})
        review = simulated_review(doc, b)
        preview = unit("预告", "discourse_preview", "下面介绍随访安排。", "", doc.text, after)
        preview["topic_units"] = ["主题"]
        topic = unit("主题", "topic", "随访安排", "随访安排", doc.text, after)
        fact = unit("事实", "research_fact", "项目拟联系受试者", "项目拟联系受试者", doc.text, after, "项目", "联系受试者")
        row = review["transactions"][0]
        row["information_review"] = evidence(doc, after, [preview, topic, fact], [binding("事实", [quote(doc.text, "拟")], [quote(after, "拟")])])
        row["benefit_review"] = {"status": "pass", "problem_type": "buried_topic",
            "problem_before": [quote(doc.text, "下面介绍随访安排")], "resolution_after": [quote(after, "随访安排：项目拟联系受试者")],
            "observed_gain": "SIMULATED: the surviving topic immediately labels the concrete arrangement", "note": "SIMULATED: observable navigation removal with unchanged topic"}
        return doc, after, b, review

    def test_preview_removal_preserves_exact_topic_and_has_observable_gain(self):
        doc, after, b, review = self.preview_fixture()
        final, report = c.apply_bundle(doc, b, review)
        self.assertEqual(final, after)
        self.assertEqual(report["status"], "checked_edit")
        self.assertEqual(report["review_policy"], b["review_policy"])

    def test_split_navigation_and_literal_topic_union_cover_one_scope(self):
        doc, after, b, review = self.preview_fixture()
        preview = review["transactions"][0]["information_review"]["units"][0]
        preview["before"] = [quote(doc.text, "下面介绍")]
        final, report = c.apply_bundle(doc, b, review)
        self.assertEqual(final, after)
        self.assertEqual(report["status"], "checked_edit")

    def test_split_preview_topic_cannot_be_borrowed_from_another_sentence(self):
        doc, _, b, review = self.preview_fixture()
        info = review["transactions"][0]["information_review"]
        info["units"][0]["before"] = [quote(doc.text, "下面介绍")]
        original_topic = copy.deepcopy(info["units"][1])
        original_topic["id"] = "原主题"
        info["units"].append(original_topic)
        info["units"][1] = unit("主题", "topic", "受试者", "受试者", doc.text, c._apply(doc.text, b["patches"]))
        final, report = c.apply_bundle(doc, b, review)
        self.assertEqual(final, doc.text)
        # All source text is covered, but the preview's topic reference points
        # to a later sentence; coverage alone must not establish correspondence.
        self.assertIn("preview_unique_topic_not_preserved", report["transactions"][0]["reasons"])

    def implicit_operations_fixture(self):
        doc = c.document_from_text("下面介绍样本处理。离心后收集上清液，置于冰上。")
        after = "样本处理：离心后收集上清液，置于冰上。"
        b = c.build_bundle(doc, {"original_hash": doc.hash,
            "review_policy": {"require_information_units": True, "require_benefit": True},
            "edits": [{"paragraph_id": "p00001", "new": after, "reason": "SIMULATED: only remove navigation, operations untouched"}]})
        review = simulated_review(doc, b)
        preview = unit("预告", "discourse_preview", "下面介绍", "", doc.text, after)
        preview["topic_units"] = ["主题"]
        units = [preview, unit("主题", "topic", "样本处理", "样本处理", doc.text, after),
                 unit("收集", "research_fact", "离心后收集上清液", "离心后收集上清液", doc.text, after,
                      action="收集上清液", conditions=["离心后"]),
                 unit("保存", "research_fact", "置于冰上", "置于冰上", doc.text, after, action="置于冰上")]
        row = review["transactions"][0]
        row["information_review"] = evidence(doc, after, units, [])
        row["benefit_review"] = {"status": "pass", "problem_type": "redundant_discourse",
            "problem_before": [quote(doc.text, "下面介绍样本处理")], "resolution_after": [quote(after, "样本处理：离心后收集上清液")],
            "observed_gain": "SIMULATED: topic immediately labels unchanged operations without navigation", "note": "SIMULATED: readout operations and condition remain literal"}
        return doc, after, b, review

    def test_unchanged_implicit_subject_fact_units_keep_explicit_actions(self):
        doc, after, b, review = self.implicit_operations_fixture()
        final, report = c.apply_bundle(doc, b, review)
        self.assertEqual(final, after)
        self.assertEqual(report["status"], "checked_edit")
        for fact in review["transactions"][0]["information_review"]["units"][2:]:
            self.assertEqual(fact["subject"], {"before": [], "after": []})
            self.assertTrue(fact["action"]["before"])

    def test_changed_fact_text_cannot_use_empty_subject_exception(self):
        doc, _, b, _ = self.implicit_operations_fixture()
        after = "样本处理：离心后收集上清液，轻轻置于冰上。"
        b = c.build_bundle(doc, {"original_hash": doc.hash, "review_policy": {"require_information_units": True},
            "edits": [{"paragraph_id": "p00001", "new": after, "reason": "SIMULATED: changed factual wording cannot claim unchanged subject exception"}]})
        review = simulated_review(doc, b)
        info = self.implicit_operations_fixture()[3]["transactions"][0]["information_review"]
        info["after_hash"] = c.text_hash(after)
        info["units"][3]["after"] = [quote(after, "轻轻置于冰上")]
        info["units"][3]["action"]["after"] = [quote(after, "置于冰上")]
        review["transactions"][0]["information_review"] = info
        final, report = c.apply_bundle(doc, b, review)
        self.assertEqual(final, doc.text)
        self.assertEqual(report["status"], "all_rollback")

    def test_literal_union_cannot_hide_a_factual_scope_without_action(self):
        doc, after, b, review = self.implicit_operations_fixture()
        info = review["transactions"][0]["information_review"]
        info["units"][2]["before"] = [quote(doc.text, "离心后收集上清液，置于冰上")]
        info["units"][2]["after"] = [quote(after, "离心后收集上清液，置于冰上")]
        info["units"][3] = unit("保存", "topic", "置于冰上", "置于冰上", doc.text, after)
        final, report = c.apply_bundle(doc, b, review)
        self.assertEqual(final, doc.text)
        self.assertIn("information_scope_without_proposition_witness_before", report["transactions"][0]["reasons"])

    def test_unchanged_implicit_subject_fact_still_requires_action(self):
        doc, _, b, review = self.implicit_operations_fixture()
        review["transactions"][0]["information_review"]["units"][3]["action"] = {"before": [], "after": []}
        self.assertEqual(c.apply_bundle(doc, b, review)[0], doc.text)

    def test_missing_unique_topic_rejects(self):
        doc, _, b, review = self.preview_fixture()
        review["transactions"][0]["information_review"]["units"][0]["topic_units"] = []
        self.assertEqual(c.apply_bundle(doc, b, review)[0], doc.text)

    def test_benefit_missing_fail_unknown_and_only_shorter_reject(self):
        for value in (None, "fail", "unknown", "shorter"):
            with self.subTest(value=value):
                doc, _, b, review = self.preview_fixture()
                row = review["transactions"][0]
                if value is None:
                    row.pop("benefit_review")
                elif value == "shorter":
                    row["benefit_review"]["observed_gain"] = "更短"
                else:
                    row["benefit_review"]["status"] = value
                self.assertEqual(c.apply_bundle(doc, b, review)[0], doc.text)

    def test_true_research_commitment_cannot_be_called_preview(self):
        doc = c.document_from_text("下面介绍本项目拟检验的研究假设。项目拟联系受试者。")
        after = "研究假设：项目拟联系受试者。"
        b = bundle(doc, [patch(doc, doc.text, after)])
        review = simulated_review(doc, b)
        u = unit("预告", "discourse_preview", "下面介绍本项目拟检验的研究假设。", "", doc.text, after)
        u["topic_units"] = ["主题"]
        topic = unit("主题", "topic", "研究假设", "研究假设", doc.text, after)
        fact = unit("事实", "research_fact", "项目拟联系受试者", "项目拟联系受试者", doc.text, after, "项目", "联系受试者")
        fact["subject"]["before"] = [quote(doc.text, "项目", 1)]
        review["transactions"][0]["information_review"] = evidence(doc, after, [u, topic, fact], [])
        self.assertEqual(c.apply_bundle(doc, b, review)[0], doc.text)

    def test_quoted_content_cannot_supply_scope_exception(self):
        doc, _, b, review = self.preview_fixture()
        unit0 = review["transactions"][0]["information_review"]["units"][0]
        unit0["before"][0]["text"] = "“下面介绍随访安排。”"
        self.assertEqual(c.apply_bundle(doc, b, review)[0], doc.text)

    def test_new_proposal_noop_skips_benefit(self):
        doc = c.document_from_text("项目拟联系受试者。")
        b = c.build_bundle(doc, {"original_hash": doc.hash, "review_policy": {"require_benefit": True, "require_information_units": True},
            "edits": [{"paragraph_id": "p00001", "new": doc.text, "reason": "SIMULATED: no change needed"}]})
        self.assertEqual(c.apply_bundle(doc, b)[1]["status"], "no_op")

    def test_v11_03_exposed_topic_loss_regression_stays_rejected(self):
        doc = c.document_from_text("为使方案的表述更加明确，下面介绍随访安排。项目拟按既定时间联系受试者，联系记录由指定人员核查。招募尚未开始。")
        after = "项目拟按既定时间联系受试者，联系记录由指定人员核查。招募尚未开始。"
        b = bundle(doc, [patch(doc, "为使方案的表述更加明确，下面介绍随访安排。", "")])
        b["review_policy"] = {"require_information_units": True}
        review = simulated_review(doc, b)
        self.assertEqual(c.apply_bundle(doc, b, review)[0], doc.text)
        self.assertNotIn("随访安排", after)  # exposed source topic must be mapped, not called filler

    def test_v11_07_exposed_preview_status_regression_can_be_adjudicated(self):
        preview_text = "以下将对本阶段已经完成的工作作一个说明。"
        remainder = "本阶段已完成访谈材料的去标识化，录音转写仍在核对。未完成核对的材料不进入编码。"
        doc = c.document_from_text(preview_text + remainder)
        b = bundle(doc, [patch(doc, preview_text, "")])
        b["review_policy"] = {"require_information_units": True}
        review = simulated_review(doc, b)
        preview = unit("预告", "discourse_preview", preview_text, "", doc.text, remainder)
        preview["topic_units"] = ["阶段"]
        topic = unit("阶段", "topic", "本阶段", "本阶段", doc.text, remainder)
        fact = unit("完成", "research_fact", "本阶段已完成访谈材料的去标识化", "本阶段已完成访谈材料的去标识化", doc.text, remainder,
                    "本阶段", "完成访谈材料的去标识化")
        fact["subject"]["before"] = [quote(doc.text, "本阶段", 1)]
        ongoing = unit("核对", "stance", "录音转写仍在核对", "录音转写仍在核对", doc.text, remainder)
        condition = unit("条件", "condition", "未完成核对的材料不进入编码", "未完成核对的材料不进入编码", doc.text, remainder)
        bindings = [binding("阶段", [quote(doc.text, "已经")], [quote(remainder, "已")]),
                    binding("完成", [quote(doc.text, "已", 1)], [quote(remainder, "已")]),
                    binding("条件", [quote(doc.text, "未"), quote(doc.text, "不")], [quote(remainder, "未"), quote(remainder, "不")])]
        review["transactions"][0]["information_review"] = evidence(doc, remainder, [preview, topic, fact, ongoing, condition], bindings)
        final, report = c.apply_bundle(doc, b, review)
        self.assertEqual(final, remainder)
        self.assertTrue(report["final_validation"]["count_adjudicated_by_model"])


if __name__ == "__main__":
    unittest.main()

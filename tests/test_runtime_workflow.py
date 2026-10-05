"""Runtime-only regressions extracted from the development v1.1 suite.

All review fixtures are SIMULATED; no account, corpus, or model call is used.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_deai_core import c, patch, bundle, simulated_review, SCRIPTS

class NarrowGateRegression(unittest.TestCase):
    def codes(self, before, after):
        return {e['code'] for e in c.mechanical_check(before, after)['errors']}

    def test_adjacent_duplicate_retains_modality_and_requires_review(self):
        doc = c.document_from_text('偏倚可能影响估计。偏倚可能影响估计。仍需谨慎解释。')
        b = bundle(doc, [patch(doc, '偏倚可能影响估计。', '', occurrence=1)])
        check = c.mechanical_check(doc.text, c._apply(doc.text, b['patches']))
        self.assertEqual(check['errors'], [])
        self.assertEqual(check['duplicate_deletion_evidence'][0]['removed_copies'], 1)
        self.assertEqual(c.apply_bundle(doc, b)[1]['status'], 'all_rollback')
        final, report = c.apply_bundle(doc, b, simulated_review(doc, b))
        self.assertEqual(report['status'], 'checked_edit')
        self.assertEqual(final, '偏倚可能影响估计。仍需谨慎解释。')

    def test_duplicate_and_independent_shell_edit_can_merge(self):
        doc = c.document_from_text('目前尚未完成核查。目前尚未完成核查。\n\n接下来介绍进展。材料已归档。')
        b = bundle(doc, [patch(doc, '目前尚未完成核查。', '', 'a', occurrence=1),
                         patch(doc, '接下来介绍进展。', '', 'b')])
        final, report = c.apply_bundle(doc, b, simulated_review(doc, b))
        self.assertEqual(report['status'], 'checked_edit')
        self.assertEqual(final, '目前尚未完成核查。\n\n材料已归档。')

    def test_multiple_copies_reduce_to_one(self):
        check = c.mechanical_check('拟核对记录。' * 4, '拟核对记录。')
        self.assertEqual(check['errors'], [])
        self.assertEqual(check['duplicate_deletion_evidence'][0]['removed_copies'], 3)

    def test_near_duplicate_does_not_get_count_exception(self):
        self.assertIn('modality_negation_status_changed', self.codes('可能影响估计。影响估计。', '影响估计。'))

    def test_nonadjacent_duplicate_does_not_get_exception(self):
        self.assertIn('modality_negation_status_changed', self.codes('拟核查。条件满足后开展。拟核查。', '拟核查。条件满足后开展。'))

    def test_cross_paragraph_duplicate_does_not_get_exception(self):
        self.assertIn('modality_negation_status_changed', self.codes('拟核查。\n\n拟核查。', '拟核查。\n\n'))

    def test_quoted_duplicate_is_not_a_witness(self):
        check = c.mechanical_check('“可能”。“可能”。', '“可能”。')
        self.assertEqual(check['duplicate_deletion_evidence'], [])

    def test_numeric_duplicate_still_protected(self):
        self.assertIn('number_or_unit_changed', self.codes('拟纳入12例。拟纳入12例。', '拟纳入12例。'))

    def test_citation_duplicate_still_protected(self):
        self.assertIn('citation_identifier_changed', self.codes('可能相关[1]。可能相关[1]。', '可能相关[1]。'))

    def test_duplicate_exception_does_not_cover_extra_modality_loss(self):
        self.assertIn('modality_negation_status_changed', self.codes('拟核查。拟核查。乙可能有效。', '拟核查。乙有效。'))

    def test_respectively_maps_each_group(self):
        before = '丙组和丁组的反应率分别为82%和79%。'
        after = '丙组的反应率为82%，丁组的反应率为79%。'
        self.assertEqual(self.codes(before, after), set())
        self.assertEqual(c._clause_bindings(before, c.NUMBER_RE), {'丙组': ('82%',), '丁组': ('79%',)})

    def test_respectively_order_swap_still_rejected(self):
        check = self.codes('丙组和丁组的反应率分别为82%和79%。', '丁组和丙组的反应率分别为82%和79%。')
        self.assertIn('number_assignment_changed', check)

    def test_ambiguous_multi_metric_binding_is_disclosed(self):
        source = '丙组和丁组的反应率分别为82%和79%，共40例。'
        # The literal two-value mapping is covered; pooled totals are not mapped.
        self.assertEqual(c._clause_bindings(source, c.NUMBER_RE), {'丙组': ('82%',), '丁组': ('79%',)})
        check = c.mechanical_check('丙组和丁组共有40例。', '丙组与丁组共有40例。')
        self.assertTrue(check['unresolved_group_bindings']['number_before'])
        self.assertFalse(check['equivalence_proven'])

    def test_unrelated_ambiguous_clause_does_not_hide_number_swap(self):
        before = '甲组10例，乙组20例。丙组和丁组共有40例。'
        after = '甲组20例，乙组10例。丙组与丁组共有40例。'
        self.assertIn('number_assignment_changed', self.codes(before, after))

    def test_unchanged_ambiguity_does_not_hide_same_group_swap(self):
        before = '甲组10例，乙组20例。甲组和乙组共有30例。'
        after = '甲组20例，乙组10例。甲组和乙组共有30例。'
        self.assertIn('number_assignment_changed', self.codes(before, after))

    def test_unrelated_ambiguous_clause_does_not_hide_modality_swap(self):
        before = '甲可能有效，乙无效。丙组和丁组拟随访。'
        after = '甲有效，乙可能无效。丙组与丁组拟随访。'
        self.assertIn('modality_scope_changed', self.codes(before, after))

class ProposalWorkflow(unittest.TestCase):
    def propose(self, doc, new, **overrides):
        p = c.parse_document(doc)['paragraphs'][0]
        value = {'original_hash': doc.hash, 'edits': [{'paragraph_id': p['id'], 'new': new,
                 'reason': 'SIMULATED: remove uninformative preview'}]}
        value.update(overrides)
        return c.build_bundle(doc, value)

    def test_unicode_minimal_range_and_exact_candidate(self):
        doc = c.document_from_text('😀共有16例。接下来介绍进展。资料已归档。')
        new = '😀共有16例。资料已归档。'
        b = self.propose(doc, new)
        self.assertEqual(c._apply(doc.text, b['patches']), new)
        self.assertEqual(b['patches'][0]['old'], '接下来介绍进展。')
        self.assertEqual(b['patches'][0]['protect_ids'], [])
        self.assertEqual(c.build_review_request(doc, b)['review_template']['transactions'][0]['status'], 'unknown')

    def test_changed_number_is_not_hidden_by_prefix_trimming(self):
        with self.assertRaises(c.InputError):
            self.propose(c.document_from_text('共有16例。'), '共有17例。')

    def test_unchanged_scientific_anchor_remains_within_small_patch(self):
        doc = c.document_from_text('对IL-6进行检测。')
        b = self.propose(doc, '检测IL-6。')
        self.assertEqual(c._apply(doc.text, b['patches']), '检测IL-6。')
        self.assertTrue(b['patches'][0]['protect_ids'])

    def test_stale_proposal_rejected(self):
        with self.assertRaises(c.InputError):
            self.propose(c.document_from_text('接下来介绍进展。'), '进展。', original_hash='stale')

    def test_duplicate_paragraph_proposals_rejected(self):
        doc = c.document_from_text('接下来介绍进展。资料已归档。')
        edit = {'paragraph_id': 'p00001', 'new': '资料已归档。', 'reason': 'SIMULATED'}
        with self.assertRaises(c.InputError):
            c.build_bundle(doc, {'original_hash': doc.hash, 'edits': [edit, edit]})

    def test_diagnose_mode_cannot_compile_changed_text(self):
        with self.assertRaises(c.InputError):
            self.propose(c.document_from_text('接下来介绍进展。资料已归档。'), '资料已归档。', mode='diagnose')

    def test_identical_proposal_is_noop(self):
        doc = c.document_from_text('资料已归档。')
        self.assertEqual(self.propose(doc, doc.text)['patches'], [])

    def test_cli_build_and_review_request_in_unicode_path(self):
        with tempfile.TemporaryDirectory(prefix='deai_中文 ') as temp:
            root = Path(temp)
            src = root / '输入.md'
            src.write_bytes(b'\xef\xbb\xbf' + '接下来介绍进展。资料已归档。\r\n'.encode('utf-8'))
            doc = c.document_from_path(src)
            raw = src.read_bytes()
            edits = {'original_hash': doc.hash, 'edits': [{'paragraph_id': 'p00001',
                     'new': '资料已归档。', 'reason': 'SIMULATED'}]}
            (root / 'edits.json').write_text(json.dumps(edits, ensure_ascii=False), encoding='utf-8')
            commands = [
                ['build-bundle', '--input', str(src), '--edits', str(root / 'edits.json'), '--output', str(root / 'patches.json')],
                ['review-request', '--input', str(src), '--patches', str(root / 'patches.json'), '--output', str(root / 'request.json')]]
            for args in commands:
                result = subprocess.run([sys.executable, '-X', 'utf8', str(SCRIPTS / 'deai.py'), *args], capture_output=True, text=True, encoding='utf-8')
                self.assertEqual(result.returncode, 0, result.stderr)
            request = json.loads((root / 'request.json').read_text(encoding='utf-8'))
            self.assertEqual(request['after'], '资料已归档。\r\n')
            self.assertEqual(src.read_bytes(), raw)

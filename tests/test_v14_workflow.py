"""Simulated engineering evidence only; never writing-effect scores."""
import copy
import json
import unittest

import test_v13_workflow as fixtures
c = fixtures.c


class CompactWorkflow(unittest.TestCase):
    def test_compact_request_keeps_full_text_and_all_judgments(self):
        doc, _, bundle, _, full = fixtures.fixture()
        small = c.build_review_request(doc, bundle, 'compact')
        self.assertEqual(small['before'], full['before'])
        self.assertEqual(small['after'], full['after'])
        self.assertEqual(small['compact_review_template'], full['compact_review_template'])
        for a, b in zip(small['information_requirements'], full['information_requirements']):
            for key in ('verbatim_candidates', 'before_qualifier_spans', 'after_qualifier_spans'):
                self.assertEqual(a[key], b[key])
        self.assertNotIn('review_template', small)
        self.assertLess(len(json.dumps(small)), len(json.dumps(full)))

    def test_direct_compact_and_old_expanded_application_match(self):
        doc, expected, bundle, _, raw = fixtures.QuoteBinding().quoted_review()
        compact = fixtures.compact_review(raw)
        before = copy.deepcopy(compact)
        actual, report = c.apply_bundle(doc, bundle, compact)
        expanded, old_report = c.apply_bundle(doc, bundle, c.bind_review(doc, bundle, compact))
        self.assertEqual(actual, expected)
        self.assertEqual((actual, report), (expanded, old_report))
        self.assertEqual(compact, before)

    def test_direct_compact_cannot_bypass_failed_unknown_or_stale_evidence(self):
        for issue in ('dimension', 'unit', 'benefit', 'coherence', 'stale'):
            for status in ('fail', 'unknown'):
                with self.subTest(issue=issue, status=status):
                    doc, _, bundle, _, raw = fixtures.QuoteBinding().quoted_review()
                    compact = fixtures.compact_review(raw)
                    row = compact['transactions'][0]
                    if issue == 'dimension': row['dimensions']['subject']['status'] = status
                    elif issue == 'unit': row['information_review']['units'][0]['status'] = status
                    elif issue == 'benefit': row['benefit_review']['status'] = status
                    elif issue == 'coherence': compact['global_coherence']['status'] = status
                    else: compact['after_hash'] = 'stale'
                    self.assertEqual(c.apply_bundle(doc, bundle, compact)[0], doc.text)

    def test_malformed_compact_is_controlled_failure(self):
        for field, value in (('review_format', 'future'), ('transactions', None)):
            doc, _, bundle, _, raw = fixtures.QuoteBinding().quoted_review()
            compact = fixtures.compact_review(raw)
            compact[field] = value
            result, report = c.apply_bundle(doc, bundle, compact)
            self.assertEqual(result, doc.text)
            self.assertEqual(report['status'], 'execution_failed')


class ContextQuotes(unittest.TestCase):
    def quote_result(self, source, ref):
        doc = c.document_from_text(source)
        bundle = c.build_bundle(doc, {'original_hash': doc.hash, 'edits': []})
        review = {'before_hash': doc.hash, 'after_hash': doc.hash,
                  'transactions': [{'benefit_review': {'problem_before': [ref]}}]}
        return c.bind_review(doc, bundle, review)['transactions'][0]['benefit_review']['problem_before'][0]

    def test_unique_context_locates_repeated_word_without_global_counting(self):
        source = '研究A使用自报量。💡\r\n研究B使用记录量。'
        span = self.quote_result(source, {'text': '使用', 'context': '研究B使用记录量'})
        self.assertEqual(span['start'], source.index('使用', source.index('研究B')))
        self.assertEqual(source[span['start']:span['end']], '使用')

    def test_local_occurrence_is_not_global_occurrence(self):
        source = '复核。甲先复核记录，再复核异常值。'
        span = self.quote_result(source, {'text': '复核', 'context': '甲先复核记录，再复核异常值', 'occurrence': 1})
        self.assertEqual(span['start'], source.rindex('复核'))

    def test_overlapping_context_is_ambiguous(self):
        with self.assertRaises(c.InputError):
            self.quote_result('aaaa', {'text': 'a', 'context': 'aaa'})

    def test_missing_ambiguous_wrong_context_or_invalid_occurrence_reject(self):
        source = '甲拟登记。乙拟核对。'
        refs = [{'text': '拟', 'context': ''}, {'text': '拟', 'context': '拟'},
                {'text': '拟', 'context': '缺失'}, {'text': '核对', 'context': '甲拟登记'},
                {'text': '拟', 'context': '乙拟核对', 'occurrence': True},
                {'text': '拟', 'context': '乙拟核对', 'occurrence': -1},
                {'text': '拟', 'context': '乙拟核对', 'occurrence': 1}]
        for ref in refs:
            with self.subTest(ref=ref), self.assertRaises(c.InputError): self.quote_result(source, ref)


class ReviewDiagnostics(unittest.TestCase):
    def test_ready_diagnostics_are_read_only_and_match_application(self):
        doc, _, bundle, _, raw = fixtures.QuoteBinding().quoted_review()
        compact = fixtures.compact_review(raw)
        before = copy.deepcopy(compact)
        check = c.check_review(doc, bundle, compact)
        self.assertEqual(check['status'], 'review_ready')
        self.assertEqual(check['would_apply_status'], c.apply_bundle(doc, bundle, compact)[1]['status'])
        self.assertFalse(check['judgments_generated'])
        self.assertEqual(compact, before)

    def test_semantic_failure_and_bad_quote_stay_blocked(self):
        for issue in ('fail', 'unknown', 'quote'):
            doc, _, bundle, _, raw = fixtures.QuoteBinding().quoted_review()
            compact = fixtures.compact_review(raw)
            if issue == 'quote': compact['transactions'][0]['benefit_review']['problem_before'] = [{'text': '不存在'}]
            else: compact['transactions'][0]['dimensions']['subject']['status'] = issue
            self.assertEqual(c.check_review(doc, bundle, compact)['status'], 'review_blocked')

    def test_empty_mismatch_and_outside_anchors_report_paths_not_auto_repairs(self):
        doc, after, bundle, review, _ = fixtures.fixture()
        # Deliberately invalid factual mapping, rather than a simulated pass.
        unit = review['transactions'][0]['information_review']['units'][1]
        unit['kind'] = 'research_fact'
        unit['before'] = [fixtures.quote(doc.text, '下面介绍本项目的随访安排')]
        unit['action'] = {'before': [fixtures.quote(doc.text, '随访安排')],
                          'after': [fixtures.quote(after, '参与者')]}
        check = c.check_review(doc, bundle, review)
        codes = {d['code'] for d in check['diagnostics']}
        self.assertTrue({'required_anchor_empty', 'anchor_literal_mismatch', 'anchor_outside_unit'} <= codes)
        self.assertEqual(check['status'], 'review_blocked')
        self.assertTrue(all(d['path'] and d['requires_model_decision'] for d in check['diagnostics']))


if __name__ == '__main__': unittest.main()

from dataclasses import replace
import importlib
import json
import unittest

from project_management.app.domain.summary_contracts import AcceptedSummary, AnalysisError
from project_management.app.domain.summary_input import build_initial_input
from project_management.app.domain.summary_validation import validate_candidate
from project_management.tests.summary_fixtures import SummaryScenario


class TestSummaryDelta(SummaryScenario, unittest.TestCase):
    def sources(self):
        first, a = self.summary_source()
        b = replace(a, facts=dict(a.facts, status='In Analysis'), comments_by_id={
            **a.comments_by_id,
            '202': {'id': '202', 'body': 'An intermediate regression was reproduced.'},
            '204': {'id': '204', 'body': 'A temporary investigation note.'},
        })
        c = replace(a, comments_by_id={key: value for key, value in a.comments_by_id.items() if key != '201'})
        second = replace(first, capture_id='71000000-0000-4000-8000-000000000002',
                         sequence=2, previous_capture_id=first.capture_id, source_hash='b' * 64)
        third = replace(second, capture_id='71000000-0000-4000-8000-000000000003',
                        sequence=3, previous_capture_id=second.capture_id, source_hash='c' * 64)
        key = self.source_key(self.intent())
        initial = build_initial_input(self.project.id, self.stage, key, first, a,
                                      'project-reporting.summary@review-1')
        baseline = AcceptedSummary('74000000-0000-4000-8000-000000000001', 1, first.capture_id,
                                   first.source_hash, self.contract.definition_hash, initial.input_hash,
                                   validate_candidate(initial, self.output(initial)), {})
        return key, (first, second, third), (a, b, c), baseline

    def build(self, key, chain, snapshots, baseline):
        module = importlib.import_module('project_management.app.domain.summary_delta')
        return module.build_analysis_input(self.project.id, self.stage, key, chain, snapshots,
                                           'project-reporting.summary@review-1', baseline)

    def test_shouldBuildCumulativeInputFromAcceptedBaseline(self):
        key, chain, sources, baseline = self.sources()
        prepared = self.build(key, chain, sources, baseline)
        value = json.loads(prepared.input_content)

        self.contract.validate_input(value)
        self.assertEqual((1, baseline.summary_id), (prepared.expected_revision, prepared.base_summary_id))
        self.assertEqual(baseline.candidate, json.loads(value['baseline']['text']))
        self.assertEqual({
            'from_capture_id': chain[0].capture_id, 'to_capture_id': chain[2].capture_id,
            'added_ids': ['comment:204'], 'updated_ids': ['comment:202', 'fields'],
            'deleted_ids': ['comment:201', 'comment:204'],
        }, value['delta'])
        fields = [row for row in value['evidence'] if row['kind'] == 'field']
        self.assertEqual(['Fixed', 'In Analysis', 'Fixed'], [row['value']['status'] for row in fields])
        historical = next(row for row in value['evidence'] if row['source_id'] == '204')
        self.assertEqual(chain[1].capture_id, historical['capture_id'])
        self.assertEqual('A temporary investigation note.', historical['value']['body'])
        self.assertEqual(f'archived:{chain[1].capture_id}:comment:204', historical['ref_id'])
        current_ids = [row['ref_id'] for row in value['evidence'] if row['capture_id'] == chain[-1].capture_id]
        self.assertEqual(['fields', 'comment:202', 'comment:203'], current_ids)

    def test_shouldPreserveInitialInputBytesAndIds(self):
        key, chain, sources, _ = self.sources()
        legacy = build_initial_input(self.project.id, self.stage, key, chain[0], sources[0],
                                     'project-reporting.summary@review-1')
        self.assertEqual(legacy, self.build(key, chain[:1], sources[:1], None))

    def test_shouldIncludePreAcceptanceHistoryWithoutABaseline(self):
        key, chain, sources, _ = self.sources()
        value = json.loads(self.build(key, chain, sources, None).input_content)
        self.assertEqual({'summary_id': None, 'accepted_revision': 0, 'capture_id': None, 'text': None},
                         value['baseline'])
        self.assertIsNone(value['delta']['from_capture_id'])
        self.assertEqual(['comment:201', 'comment:202', 'comment:203', 'comment:204'],
                         value['delta']['added_ids'])
        self.assertEqual(12, len(value['evidence']))

    def test_shouldRejectBrokenBaselineIncompleteSegmentAndOversizedHistory(self):
        key, chain, sources, baseline = self.sources()
        cases = [
            ((chain[0], chain[2]), (sources[0], sources[2]), baseline, 'ANALYSIS_SOURCE_CHANGED'),
            (chain, sources, replace(baseline, source_hash='f' * 64), 'ANALYSIS_SOURCE_CHANGED'),
            (chain, sources, replace(baseline, revision=True), 'ANALYSIS_SOURCE_CHANGED'),
            (chain, (sources[0], replace(sources[1], consistent=False), sources[2]), baseline,
             'ANALYSIS_SOURCE_INCOMPLETE'),
            (chain, (sources[0], replace(sources[1], facts={'summary': 'x' * 70000}), sources[2]), baseline,
             'ANALYSIS_INPUT_LIMIT'),
            (chain, (sources[0], replace(sources[1], comments_by_id={
                str(index): {'body': 'Retain this evidence.'} for index in range(64)
            }), sources[2]), baseline, 'ANALYSIS_INPUT_LIMIT'),
        ]
        for refs, snapshots, accepted, code in cases:
            with self.subTest(code=code), self.assertRaises(AnalysisError) as caught:
                self.build(key, refs, snapshots, accepted)
            self.assertEqual(code, caught.exception.code)

    def test_shouldValidateHistoricalCitationsWithoutRelabelingThemCurrent(self):
        key, chain, sources, baseline = self.sources()
        prepared = self.build(key, chain, sources, baseline)
        historical_id = f'archived:{chain[1].capture_id}:comment:204'
        output = {
            **self.output(prepared), 'base_summary_id': baseline.summary_id,
            'what': 'Review "A temporary investigation note." in the captured history.',
            'evidence': ['fields', historical_id], 'next_actions': [],
        }
        self.contract.validate_input(json.loads(prepared.input_content))
        accepted = validate_candidate(prepared, output)
        self.assertEqual(prepared.input_hash, accepted['input_hash'])
        forged = json.loads(prepared.input_content)
        next(row for row in forged['evidence'] if row['ref_id'] == historical_id)['capture_id'] = chain[0].capture_id
        from project_management.app.domain.capture_values import canonical_bytes, sha256_bytes
        content = canonical_bytes(forged)
        invalid = replace(prepared, input_content=content.decode(), input_hash=sha256_bytes(content))
        with self.assertRaises(AnalysisError) as caught:
            validate_candidate(invalid, output)
        self.assertEqual('ANALYSIS_EVIDENCE_INVALID', caught.exception.code)

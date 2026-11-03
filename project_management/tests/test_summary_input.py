from dataclasses import replace
import hashlib
import json
import unittest
import uuid

from project_management.app.api.capture_archive import PartCoverage, StoredSnapshotRef
from project_management.app.domain.summary_contracts import AnalysisError
from project_management.app.domain.summary_input import build_initial_input, unchanged_since
from project_management.tests.capture_archive_fixtures import CaptureArchiveScenario


class TestSummaryInput(CaptureArchiveScenario, unittest.TestCase):
    def source(self):
        snapshot = replace(
            self.snapshot(('raw-1',)),
            facts={'summary': 'Intermittent validation failure', 'status': 'Fixed',
                   'reporter': {'key': 'qa-b', 'displayName': 'Bob'}},
            comments_by_id={
                '201': {'id': '201', 'body': 'Failure observed.', 'author': {'key': 'dev-a'}},
                '202': {'id': '202', 'body': 'Logs attached; \u539f\u6587 preserved. ' + 'x' * 13000},
                '203': {'id': '203', 'body': 'Bob (qa-b), please rerun validation on build r8.'},
            },
            coverage=replace(self.snapshot(('raw-1',)).coverage,
                             comments=PartCoverage('complete', 'comments-v1', 3, 3, None),
                             history=PartCoverage('complete', 'history-v1', 0, 0, None)),
        )
        reference = StoredSnapshotRef(snapshot.identity, str(uuid.uuid4()), 1, None, 'a' * 64, 'snapshot.json')
        return reference, snapshot

    def build(self, reference, snapshot):
        return build_initial_input(self.project.id, self.stage, self.source_key(self.intent()),
                                   reference, snapshot, 'project-reporting.summary@review-1')

    def test_shouldPreserveActualScopeAllCommentsAndLongOriginalText(self):
        reference, snapshot = self.source()
        prepared = self.build(reference, snapshot)
        value = json.loads(prepared.input_content)
        self.assertEqual((self.project.id, self.stage.id, self.stage.definition_hash, reference.capture_id),
                         (value['binding']['project_id'], value['binding']['stage_id'],
                          value['binding']['rule_hash'], value['target_capture_id']))
        self.assertEqual(['201', '202', '203'], value['delta']['added_ids'])
        comments = [row for row in value['evidence'] if row['kind'] == 'comment']
        self.assertEqual([snapshot.comments_by_id[key] for key in ['201', '202', '203']],
                         [row['value'] for row in comments])
        for row in value['evidence']:
            expected = hashlib.sha256(json.dumps(row['value'], sort_keys=True, separators=(',', ':'),
                                                 ensure_ascii=False).encode()).hexdigest()
            self.assertEqual(expected, row['source_hash'])
        self.assertEqual(hashlib.sha256(prepared.input_content.encode()).hexdigest(), prepared.input_hash)

    def test_shouldRefuseIncompleteUnstableOrOversizedInputWithoutTruncating(self):
        reference, snapshot = self.source()
        cases = [
            (replace(snapshot, consistent=False), 'ANALYSIS_SOURCE_INCOMPLETE'),
            (replace(snapshot, coverage=replace(snapshot.coverage,
                                               history=PartCoverage('partial', None, 0, None, 'partial'))),
             'ANALYSIS_SOURCE_INCOMPLETE'),
            (replace(snapshot, comments_by_id={str(i): {'id': str(i), 'body': 'Retain every record.'}
                                               for i in range(64)}), 'ANALYSIS_INPUT_LIMIT'),
            (replace(snapshot, facts={'summary': 'x' * 70000}), 'ANALYSIS_INPUT_LIMIT'),
            (replace(snapshot, dependencies_by_id={'d1': {'id': 'd1'}}), 'ANALYSIS_PART_UNSUPPORTED'),
        ]
        for source, code in cases:
            with self.subTest(code=code), self.assertRaises(AnalysisError) as caught:
                self.build(reference, source)
            self.assertEqual(code, caught.exception.code)

    def test_shouldReuseOnlyEveryUnchangedRetainedVersionAfterAcceptedBaseline(self):
        first, _ = self.source()
        second = replace(first, capture_id=str(uuid.uuid4()), sequence=2, previous_capture_id=first.capture_id)
        third = replace(second, capture_id=str(uuid.uuid4()), sequence=3, previous_capture_id=second.capture_id)
        self.assertTrue(unchanged_since(first.capture_id, first.source_hash, (first, second, third)))
        self.assertFalse(unchanged_since(first.capture_id, first.source_hash,
                                         (first, replace(second, source_hash='b' * 64), third)))
        self.assertFalse(unchanged_since(first.capture_id, first.source_hash, (second, third)))
        self.assertFalse(unchanged_since(first.capture_id, first.source_hash, (first, third)))

    def test_shouldRefuseNonInitialSourceUntilCumulativeDeltaIsAvailable(self):
        reference, snapshot = self.source()
        with self.assertRaises(AnalysisError) as caught:
            self.build(replace(reference, sequence=2, previous_capture_id=str(uuid.uuid4())), snapshot)
        self.assertEqual('ANALYSIS_DELTA_REQUIRED', caught.exception.code)

    def test_shouldRefuseUnusableOutOfProfileCoverageEvenWithEmptyBodyCollections(self):
        reference, snapshot = self.source()
        for name in ('attachments', 'dependencies'):
            for state in ('partial', 'access_lost', 'unsupported'):
                source = replace(snapshot, coverage=replace(
                    snapshot.coverage, **{name: PartCoverage(state, None, 0, None, 'unavailable')},
                ))
                with self.subTest(part=name, state=state), self.assertRaises(AnalysisError):
                    self.build(reference, source)

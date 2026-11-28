from dataclasses import replace
import hashlib
import json
import unittest
import uuid

from project_management.app.api.capture_archive import PartCoverage, StoredSnapshotRef
from project_management.app.domain.summary_contracts import AnalysisError
from project_management.app.domain.summary_input import build_initial_input, unchanged_since
from project_management.tests.capture_archive_fixtures import CaptureArchiveScenario


def body_not_requested_metadata(snapshot, *, attachments=1, dependencies=1, reason='BODY_NOT_REQUESTED'):
    attachments_by_id = {
        f'att-{index}': {'id': f'att-{index}', 'filename': f'log-{index}.txt', 'size': index}
        for index in range(1, attachments + 1)
    }
    dependencies_by_id = {
        f'dep-{index}': {'id': f'dep-{index}', 'type': 'relates', 'key': f'ALPHA-{index + 1}'}
        for index in range(1, dependencies + 1)
    }
    return replace(
        snapshot,
        attachments_by_id=attachments_by_id,
        dependencies_by_id=dependencies_by_id,
        coverage=replace(
            snapshot.coverage,
            attachments=PartCoverage('partial', 'attachments-v1', attachments, attachments, reason),
            dependencies=PartCoverage('partial', 'dependencies-v1', dependencies, dependencies, reason),
        ),
    )


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
                                   reference, snapshot, 'metrics.project_summary@3')

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

    def test_shouldAdmitRetainedBodyNotRequestedMetadataWithoutSupplyingBodies(self):
        reference, snapshot = self.source()
        source = body_not_requested_metadata(snapshot)

        prepared = self.build(reference, source)
        value = json.loads(prepared.input_content)

        self.assertEqual('metrics.project_summary@3', value['profile_revision'])
        self.assertEqual({'facts': 'complete', 'comments': 'complete', 'history': 'complete'}, value['coverage'])
        self.assertNotIn('attachments_by_id', value)
        self.assertNotIn('dependencies_by_id', value)
        self.assertEqual(['field', 'comment', 'comment', 'comment'], [row['kind'] for row in value['evidence']])
        self.assertEqual(hashlib.sha256(prepared.input_content.encode()).hexdigest(), prepared.input_hash)

    def test_shouldRejectInvalidRetainedBodyMetadataSiblings(self):
        reference, snapshot = self.source()
        valid = body_not_requested_metadata(snapshot)
        invalid_cases = {
            'unknown_reason': replace(
                valid,
                coverage=replace(
                    valid.coverage,
                    attachments=PartCoverage('partial', 'attachments-v1', 1, 1, 'FETCH_FAILED'),
                ),
            ),
            'observed_count_mismatch': replace(
                valid,
                coverage=replace(
                    valid.coverage,
                    attachments=PartCoverage('partial', 'attachments-v1', 0, 1, 'BODY_NOT_REQUESTED'),
                ),
            ),
            'total_count_mismatch': replace(
                valid,
                coverage=replace(
                    valid.coverage,
                    dependencies=PartCoverage('partial', 'dependencies-v1', 1, 2, 'BODY_NOT_REQUESTED'),
                ),
            ),
            'positive_complete_claim': replace(
                valid,
                coverage=replace(
                    valid.coverage,
                    dependencies=PartCoverage('complete', 'dependencies-v1', 1, 1, None),
                ),
            ),
            'access_lost': replace(
                valid,
                coverage=replace(
                    valid.coverage,
                    attachments=PartCoverage('access_lost', 'attachments-v1', 1, 1, 'BODY_NOT_REQUESTED'),
                ),
            ),
            'empty_partial_not_broadened': replace(
                snapshot,
                coverage=replace(
                    snapshot.coverage,
                    attachments=PartCoverage('partial', 'attachments-v1', 0, 0, 'BODY_NOT_REQUESTED'),
                ),
            ),
        }
        for name, source in invalid_cases.items():
            with self.subTest(name=name), self.assertRaises(AnalysisError) as caught:
                self.build(reference, source)
            self.assertEqual('ANALYSIS_PART_UNSUPPORTED', caught.exception.code)

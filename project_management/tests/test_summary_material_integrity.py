from contextlib import nullcontext
import unittest
from unittest.mock import patch

from project_management.app.domain.capture_values import canonical_bytes, content_hash, decode_json
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.summary_contracts import AnalysisError


class TestSummaryMaterialIntegrity(unittest.TestCase):
    def test_shouldRejectBooleanExpectedRevisionEvenWithMatchingDispatchHash(self):
        from project_management.tests.test_report_source_reader import TestReportSourceReader

        fixture = TestReportSourceReader()
        fixture.setUp()
        archive, repository, capture_id = fixture.memory_reader_with_capture()
        intent_path = next(path for path in repository.files if path.startswith('analysis_attempts/')
                           and path.endswith('/intent.json'))
        intent = decode_json(repository.files[intent_path])
        intent['payload']['prepared']['expected_revision'] = False
        repository.files[intent_path] = canonical_bytes(intent)
        dispatch_path = intent_path.replace('/intent.json', '/dispatch.json')
        dispatch = decode_json(repository.files[dispatch_path])
        dispatch['payload']['intent_hash'] = content_hash(intent)
        repository.files[dispatch_path] = canonical_bytes(dispatch)

        with self.assertRaises(ReportError) as caught:
            fixture.read_memory_report(archive, repository, capture_id)
        self.assertEqual('REPORT_SOURCE_CHANGED', caught.exception.code)

    def test_shouldNotReplayACorruptedAcceptedIdentity(self):
        from project_management.tests.test_report_source_reader import TestReportSourceReader

        fixture = TestReportSourceReader()
        fixture.setUp()
        archive, repository, _, paths = fixture.memory_reader_with_capture(return_paths=True)
        envelope = decode_json(repository.files[paths['accepted']])
        snapshot = envelope['payload']['snapshot']
        result = envelope['payload']['summary']['run_result']
        envelope['payload']['summary']['summary_id'] = '74000000-0000-4000-8000-000000000999'
        repository.files[paths['accepted']] = canonical_bytes(envelope)
        with patch.object(archive, '_analysis_repository', return_value=nullcontext(repository)):
            with self.assertRaises(AnalysisError):
                archive.accept_analysis(fixture.actor, fixture.project.id, fixture.stage.id,
                                        envelope['attempt_id'], snapshot, result, fixture.contract)

    def test_shouldReadEachPinnedSourceSnapshotOnlyOnce(self):
        from project_management.tests.test_report_source_reader import TestReportSourceReader

        fixture = TestReportSourceReader()
        fixture.setUp()
        archive, repository, capture_id = fixture.memory_reader_with_capture()
        repository.reads.clear()
        report = fixture.read_memory_report(archive, repository, capture_id)

        self.assertEqual(1, report.rows[0].summary_ref.revision)
        source_paths = [path for path in repository.reads if '/snapshots/' in path]
        self.assertTrue(source_paths, repository.reads)
        self.assertEqual(len(set(source_paths)), len(source_paths), source_paths)

    def test_shouldReplayTheVerifiedOriginalAcceptance(self):
        from project_management.tests.test_report_source_reader import TestReportSourceReader

        fixture = TestReportSourceReader()
        fixture.setUp()
        archive, repository, _, paths = fixture.memory_reader_with_capture(return_paths=True)
        envelope = decode_json(repository.files[paths['accepted']])
        before = dict(repository.files)
        with patch.object(archive, '_analysis_repository', return_value=nullcontext(repository)):
            accepted = archive.accept_analysis(
                fixture.actor, fixture.project.id, fixture.stage.id, envelope['attempt_id'],
                envelope['payload']['snapshot'], envelope['payload']['summary']['run_result'], fixture.contract,
            )
        self.assertEqual(envelope['payload']['summary']['summary_id'], accepted.summary_id)
        self.assertEqual(before, repository.files)

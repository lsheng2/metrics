from dataclasses import replace
from datetime import UTC, datetime, timedelta
import json
import unittest

from project_management.app.domain.summary_contracts import AnalysisError
from project_management.app.domain.captures import PartCoverage
from project_management.tests.report_source_fixtures import ReportSourceScenario


class TestSummaryDeltaJournal(ReportSourceScenario, unittest.TestCase):
    def prepare(self, archive, key):
        return archive.prepare_analysis(self.actor, self.project.id, self.stage.id, key,
                                        self.contract, self.backend(), datetime.now(UTC) + timedelta(minutes=5))

    def accept(self, archive, attempt):
        archive.claim_analysis_dispatch(self.actor, self.project.id, self.stage.id, attempt.attempt_id)
        output = {**self.output(attempt.prepared), 'base_summary_id': attempt.prepared.base_summary_id}
        snapshot, result = self.responses(attempt, output)
        archive.record_analysis_observation(self.actor, self.project.id, self.stage.id, attempt.attempt_id,
                                            {'snapshot': snapshot})
        accepted = archive.accept_analysis(self.actor, self.project.id, self.stage.id, attempt.attempt_id,
                                           snapshot, result, self.contract)
        return accepted, snapshot, result

    def test_shouldAdvanceAcceptedRevisionAndReadItInReport(self):
        with self.archive_service() as (root, archive):
            first = self.capture_summary_source(archive)
            initial = self.prepare(archive, first.source_key).attempt
            accepted1, snapshot1, result1 = self.accept(archive, initial)
            second = self.capture_summary_source(archive, snapshot=replace(
                first.snapshot, facts=dict(first.snapshot.facts, status='In Analysis'),
            ))
            attempt2 = self.prepare(archive, first.source_key).attempt
            self.assertEqual((1, accepted1.summary_id),
                             (attempt2.prepared.expected_revision, attempt2.prepared.base_summary_id))
            accepted2, _, _ = self.accept(archive, attempt2)
            report = self.read_report_source(archive, second.capture_id)
            self.assertEqual((2, accepted2.summary_id, 'In Analysis'),
                             (report.rows[0].summary_ref.revision, report.rows[0].summary_ref.summary_id,
                              report.rows[0].status))
            unchanged = self.capture_summary_source(archive, snapshot=second.snapshot)
            before = self.archive_files(root)
            reused = self.prepare(archive, first.source_key)
            self.assertEqual(('no_work', accepted2.summary_id), (reused.kind, reused.accepted.summary_id))
            self.assertEqual(before, self.archive_files(root))
            self.assertEqual(2, self.read_report_source(archive, unchanged.capture_id).rows[0].summary_ref.revision)
            third = self.capture_summary_source(archive, snapshot=replace(
                second.snapshot, facts=dict(second.snapshot.facts, status='Fixed'),
            ))
            attempt3 = self.prepare(archive, first.source_key).attempt
            accepted3, _, _ = self.accept(archive, attempt3)
            self.assertEqual(3, accepted3.revision)
            replay = archive.accept_analysis(self.actor, self.project.id, self.stage.id,
                                              initial.attempt_id, snapshot1, result1, self.contract)
            self.assertEqual(accepted1, replay)
            self.assertEqual(3, self.read_report_source(archive, third.capture_id).rows[0].summary_ref.revision)

    def test_shouldPreserveChangesAcrossFailedAnalysis(self):
        with self.archive_service() as (root, archive):
            first = self.capture_summary_source(archive)
            initial = self.prepare(archive, first.source_key).attempt
            accepted1, _, _ = self.accept(archive, initial)
            second = self.capture_summary_source(archive, snapshot=replace(
                first.snapshot, comments_by_id={
                    **first.snapshot.comments_by_id, '204': {'id': '204', 'body': 'Intermediate failure investigation.'},
                },
                coverage=replace(first.snapshot.coverage, comments=PartCoverage('complete', 'comments-v2', 4, 4, None)),
            ))
            failed_attempt = self.prepare(archive, first.source_key).attempt
            archive.claim_analysis_dispatch(self.actor, self.project.id, self.stage.id, failed_attempt.attempt_id)
            failed, _ = self.responses(failed_attempt)
            failed.update(state='failed', error={'code': 'backend_failed', 'message': 'Synthetic', 'recovery': 'stop'},
                          result={'availability': 'not_produced', 'sha256': None, 'mediaType': None, 'expiresAt': None})
            archive.record_analysis_observation(self.actor, self.project.id, self.stage.id,
                                                failed_attempt.attempt_id, {'snapshot': failed})
            self.capture_summary_source(archive, snapshot=first.snapshot)
            current = self.prepare(archive, first.source_key).attempt
            value = json.loads(current.prepared.input_content)
            self.assertEqual(accepted1.summary_id, value['baseline']['summary_id'])
            self.assertIn('comment:204', value['delta']['added_ids'])
            self.assertIn('comment:204', value['delta']['deleted_ids'])
            row = next(item for item in value['evidence'] if item['source_id'] == '204')
            self.assertEqual(second.capture_id, row['capture_id'])
            self.assertEqual('Intermediate failure investigation.', row['value']['body'])
            accepted2, _, _ = self.accept(archive, current)
            self.assertEqual(2, accepted2.revision)
            self.assertNotEqual(failed_attempt.attempt_id, current.attempt_id)

    def test_shouldKeepUnknownPriorSubmissionBlockingNewDispatch(self):
        with self.archive_service() as (root, archive):
            first = self.capture_summary_source(archive)
            self.accept(archive, self.prepare(archive, first.source_key).attempt)
            second = self.capture_summary_source(archive, snapshot=replace(
                first.snapshot, facts=dict(first.snapshot.facts, status='In Analysis'),
            ))
            pending = self.prepare(archive, first.source_key).attempt
            archive.claim_analysis_dispatch(self.actor, self.project.id, self.stage.id, pending.attempt_id)
            archive.record_analysis_observation(self.actor, self.project.id, self.stage.id, pending.attempt_id, {
                'state': 'unknown', 'code': 'transport_outcome_unknown',
                'recovery': 'query_by_client_key', 'status': None, 'operation': 'submit',
            })
            self.capture_summary_source(archive, snapshot=first.snapshot)
            before = self.archive_files(root)
            with self.assertRaises(AnalysisError) as caught:
                self.prepare(archive, first.source_key)
            self.assertEqual('ANALYSIS_ATTEMPT_PENDING', caught.exception.code)
            self.assertEqual(before, self.archive_files(root))
            original = archive.read_analysis_attempt(self.actor, self.project.id, self.stage.id, pending.attempt_id)
            self.assertEqual(pending.request, original.request)
            output = {**self.output(pending.prepared), 'base_summary_id': pending.prepared.base_summary_id}
            snapshot, result = self.responses(pending, output)
            archive.record_analysis_observation(self.actor, self.project.id, self.stage.id, pending.attempt_id,
                                                {'snapshot': snapshot})
            with self.assertRaises(AnalysisError) as stale:
                archive.accept_analysis(self.actor, self.project.id, self.stage.id, pending.attempt_id,
                                        snapshot, result, self.contract)
            self.assertEqual('ANALYSIS_ACCEPTANCE_CONFLICT', stale.exception.code)
            latest = self.prepare(archive, first.source_key).attempt
            self.assertEqual(1, latest.prepared.expected_revision)
            self.assertNotEqual(second.capture_id, latest.prepared.target_capture_id)

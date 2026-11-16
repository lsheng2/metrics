from dataclasses import replace
from datetime import UTC, datetime, timedelta
import unittest
import uuid

from project_management.app.api import ProjectActor, ProjectError
from project_management.app.api.capture_archive import MembershipInput, PartCoverage
from project_management.app.domain.summary_contracts import AnalysisError
from project_management.tests.summary_fixtures import SummaryScenario


class TestSummaryJournal(SummaryScenario, unittest.TestCase):
    def prepare(self, archive, source_key, **kwargs):
        return archive.prepare_analysis(self.actor, self.project.id, self.stage.id, source_key,
                                        self.contract, kwargs.get('principal', self.principal()),
                                        kwargs.get('deadline_at', datetime.now(UTC) + timedelta(minutes=5)))

    def test_shouldPersistDistinctEventsRecoverAndAcceptOnlyOneSummaryUsingRealGit(self):
        with self.archive_service() as (root, archive):
            source_key = self.capture_source(archive)
            prepared = self.prepare(archive, source_key)
            attempt = prepared.attempt
            self.assertEqual(timedelta(0), attempt.request.deadline_at.utcoffset())
            renewed = self.prepare(archive, source_key, deadline_at=datetime.now(UTC) + timedelta(minutes=9))
            self.assertEqual(attempt.request, renewed.attempt.request)
            with self.assertRaises(AnalysisError):
                self.prepare(archive, source_key, principal=replace(self.principal(), subject='other-owner'))
            with self.assertRaises(ProjectError):
                archive.read_analysis_attempt(ProjectActor('other-owner'), self.project.id, self.stage.id, attempt.attempt_id)
            self.assertTrue(archive.claim_analysis_dispatch(self.actor, self.project.id, self.stage.id, attempt.attempt_id))
            reloaded = type(archive)(archive.project_api, archive.repository_factory, archive.config)
            self.assertFalse(reloaded.claim_analysis_dispatch(self.actor, self.project.id, self.stage.id, attempt.attempt_id))
            snapshot, result = self.responses(attempt)
            reloaded.record_analysis_observation(self.actor, self.project.id, self.stage.id, attempt.attempt_id,
                                                  {'snapshot': snapshot})
            accepted = reloaded.accept_analysis(self.actor, self.project.id, self.stage.id, attempt.attempt_id,
                                                  snapshot, result, self.contract)
            replay = reloaded.accept_analysis(self.actor, self.project.id, self.stage.id, attempt.attempt_id,
                                                snapshot, result, self.contract)
            self.assertEqual(accepted.summary_id, replay.summary_id)
            accepted.candidate['what'] = 'Caller mutation must not alter the archive.'
            no_work = self.prepare(reloaded, source_key)
            self.assertEqual(('no_work', 1, 'Intermittent failure during validation.'),
                             (no_work.kind, no_work.accepted.revision, no_work.accepted.candidate['what']))
            files = self.git_text(self.archive_path(root), 'ls-tree', '-r', '--name-only', 'main').splitlines()
            self.assertEqual(1, len([name for name in files if name.startswith('accepted_summaries/')]))
            self.assertEqual(3, len([name for name in files if name.startswith('analysis_attempts/')]))
            _, original_source = self.summary_source()
            partial = replace(original_source, coverage=replace(
                original_source.coverage, attachments=PartCoverage('partial', None, 0, None, 'not_captured'),
            ))
            self.capture_source(reloaded, partial)
            with self.assertRaises(AnalysisError) as caught:
                self.prepare(reloaded, source_key)
            self.assertEqual('ANALYSIS_SOURCE_INCOMPLETE', caught.exception.code)

    def test_shouldRejectChangedTargetAndIncompleteLatestCaptureWithoutAdvancingAcceptance(self):
        with self.archive_service() as (root, archive):
            source_key = self.capture_source(archive)
            attempt = self.prepare(archive, source_key).attempt
            archive.claim_analysis_dispatch(self.actor, self.project.id, self.stage.id, attempt.attempt_id)
            _, source = self.summary_source()
            changed = replace(source, facts=dict(source.facts, status='Reopened'))
            self.capture_source(archive, changed)
            snapshot, result = self.responses(attempt)
            with self.assertRaises(AnalysisError) as caught:
                archive.accept_analysis(self.actor, self.project.id, self.stage.id, attempt.attempt_id,
                                          snapshot, result, self.contract)
            self.assertEqual('ANALYSIS_ACCEPTANCE_CONFLICT', caught.exception.code)
            incomplete = replace(changed, coverage=replace(changed.coverage,
                                                           history=PartCoverage('partial', None, 0, None, 'partial')))
            self.capture_source(archive, incomplete)
            with self.assertRaises(AnalysisError):
                self.prepare(archive, source_key)
            files = self.git_text(self.archive_path(root), 'ls-tree', '-r', '--name-only', 'main').splitlines()
            self.assertFalse(any(name.startswith('accepted_summaries/') for name in files))

from dataclasses import replace
import importlib
import unittest

from project_management.app.domain.summary_contracts import AnalysisError
from project_management.tests.summary_fixtures import SummaryScenario


class TestSummaryAttemptAdmission(SummaryScenario, unittest.TestCase):
    def blocked(self, attempt, observations=(), accepted=()):
        classifier = importlib.import_module('project_management.app.domain.summary_attempts')
        return classifier.attempt_blocks_new_input(
            attempt, observations, self.contract, accepted_attempt_ids=set(accepted),
            target_capture_id='71000000-0000-4000-8000-000000000003',
        )

    def test_shouldIgnorePreviouslyAcceptedAttemptsAndUndispatchedStaleTargets(self):
        attempt = self.attempt()
        self.assertFalse(self.blocked(attempt))
        attempt = replace(attempt, dispatched=True)
        self.assertTrue(self.blocked(attempt))
        self.assertFalse(self.blocked(attempt, accepted=(attempt.attempt_id,)))

    def test_shouldKeepUnknownOrUnresolvedExposureBlocking(self):
        attempt = replace(self.attempt(), dispatched=True)
        succeeded, _ = self.responses(attempt)
        uncertain = {**succeeded, 'unresolvedExposure': True}
        pending = {**succeeded, 'state': 'indeterminate', 'terminalAt': None}
        for observations in (
            (), ({'state': 'unknown', 'code': 'transport_outcome_unknown'},),
            ({'snapshot': uncertain},), ({'snapshot': pending},),
            ({'state': 'cancel_requested', 'remote_stop': 'unknown'},),
        ):
            with self.subTest(observations=observations):
                self.assertTrue(self.blocked(attempt, observations))

    def test_shouldReleaseVerifiedTerminalResultWithoutAcceptingIt(self):
        attempt = replace(self.attempt(), dispatched=True)
        snapshot, _ = self.responses(attempt)
        self.assertFalse(self.blocked(attempt, ({'snapshot': snapshot},)))
        failed = {
            **snapshot, 'state': 'failed',
            'result': {'availability': 'not_produced', 'sha256': None, 'mediaType': None, 'expiresAt': None},
            'error': {'code': 'backend_failed', 'message': 'Synthetic failure', 'recovery': 'stop'},
        }
        self.assertFalse(self.blocked(attempt, ({'snapshot': failed},)))
        may_dispatch = {**failed, 'dispatch': {**failed['dispatch'], 'knowledge': 'may_have_dispatched'}}
        self.assertTrue(self.blocked(attempt, ({'snapshot': may_dispatch},)))
        confirmed = {**may_dispatch, 'dispatch': {**may_dispatch['dispatch'], 'remoteStop': 'confirmed'}}
        self.assertFalse(self.blocked(attempt, ({'snapshot': confirmed},)))

    def test_shouldNotTreatAResultReadRejectionAsSubmissionRejection(self):
        attempt = replace(self.attempt(), dispatched=True)
        observation = {'state': 'rejected', 'code': 'invalid_request', 'recovery': 'correct_request', 'status': 422}
        self.assertTrue(self.blocked(attempt, (observation,)))
        self.assertTrue(self.blocked(attempt, ({**observation, 'operation': 'result'},)))
        self.assertTrue(self.blocked(attempt, ({**observation, 'operation': 'observe'},)))
        self.assertFalse(self.blocked(attempt, ({**observation, 'operation': 'submit'},)))

    def test_shouldRejectWrongIdentityOrMissingTerminalProof(self):
        attempt = replace(self.attempt(), dispatched=True)
        snapshot, _ = self.responses(attempt)
        with self.assertRaises(AnalysisError):
            self.blocked(attempt, ({'snapshot': {**snapshot, 'runStoreId': 'foreign-store'}},))
        for value in (None, 'not-a-date', '2026-11-02T00:00:30'):
            with self.subTest(terminal=value):
                self.assertTrue(self.blocked(attempt, ({'snapshot': {**snapshot, 'terminalAt': value}},)))

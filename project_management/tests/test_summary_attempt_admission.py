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
        uncertain_dispatch = replace(succeeded.dispatch, uncertainty='unknown')
        empty_result = replace(succeeded.result, output_sha256=None, output_schema_sha256=None)
        uncertain = self.task_record(replace(succeeded, dispatch=uncertain_dispatch))
        pending = self.task_record(replace(
            succeeded,
            status='indeterminate',
            dispatch=uncertain_dispatch,
            result=empty_result,
            error_code='runtime_outcome_unknown',
            retry='observe',
        ))
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
        self.assertFalse(self.blocked(attempt, ({'snapshot': self.task_record(snapshot)},)))
        failed_snapshot = replace(
            snapshot,
            status='failed',
            result=replace(snapshot.result, output_sha256=None, output_schema_sha256=None),
            error_code='backend_failed',
            retry='no',
        )
        failed = self.task_record(failed_snapshot)
        self.assertFalse(self.blocked(attempt, ({'snapshot': failed},)))
        may_dispatch = self.task_record(replace(
            failed_snapshot,
            dispatch=replace(failed_snapshot.dispatch, uncertainty='unknown'),
        ))
        self.assertTrue(self.blocked(attempt, ({'snapshot': may_dispatch},)))
        confirmed = self.task_record(failed_snapshot)
        self.assertFalse(self.blocked(attempt, ({'snapshot': confirmed},)))

    def test_shouldNotTreatAResultReadRejectionAsSubmissionRejection(self):
        attempt = replace(self.attempt(), dispatched=True)
        observation = {'state': 'rejected', 'code': 'invalid_request', 'retry': 'correct', 'status': 422}
        self.assertTrue(self.blocked(attempt, (observation,)))
        self.assertTrue(self.blocked(attempt, ({**observation, 'operation': 'result'},)))
        self.assertTrue(self.blocked(attempt, ({**observation, 'operation': 'observe'},)))
        self.assertFalse(self.blocked(attempt, ({**observation, 'operation': 'submit'},)))

    def test_shouldRejectWrongIdentityOrMissingTerminalProof(self):
        attempt = replace(self.attempt(), dispatched=True)
        snapshot, _ = self.responses(attempt)
        with self.assertRaises(AnalysisError):
            self.blocked(attempt, ({'snapshot': self.task_record(replace(snapshot, source_input_sha256='f' * 64))},))
        empty_result = replace(snapshot.result, output_sha256=None, output_schema_sha256=None)
        for value in (
            replace(snapshot, status='running', result=empty_result),
            replace(snapshot, status='indeterminate', result=empty_result),
            replace(snapshot, dispatch=replace(snapshot.dispatch, uncertainty='unknown')),
        ):
            with self.subTest(status=value.status, uncertainty=value.dispatch.uncertainty):
                self.assertTrue(self.blocked(attempt, ({'snapshot': self.task_record(value)},)))

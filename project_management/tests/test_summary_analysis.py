from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import unittest
from unittest.mock import patch

from project_management.app.api.summary_analysis import SummaryAnalysisService
from project_management.app.domain.capture_values import canonical_bytes, decode_json
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.summary_contracts import AcceptedSummary, AnalysisError, AnalysisPreparation
from project_management.app.domain.task_runs import TaskRunCancellation, TaskRunError
from project_management.tests.summary_fixtures import SummaryScenario


class MemoryJournal:
    def __init__(self, attempt):
        self.attempt = attempt
        self.observations = []
        self.accepted = None
        self.claim_failure = False

    def prepare_analysis(self, *args, **kwargs):
        return AnalysisPreparation('ready', self.attempt)

    def read_analysis_attempt(self, *args):
        return self.attempt

    def read_analysis_observations(self, *args):
        return deepcopy(self.observations)

    def request_analysis_cancel(self, *args):
        self.attempt = replace(self.attempt, cancel_requested=True)
        return self.attempt

    def claim_analysis_dispatch(self, *args, cancel_requested=None):
        if self.claim_failure:
            raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE')
        if self.attempt.cancel_requested or cancel_requested is not None and cancel_requested():
            raise AnalysisError('ANALYSIS_CANCELED')
        if self.attempt.dispatched:
            return False
        self.attempt = replace(self.attempt, dispatched=True)
        return True

    def record_analysis_observation(self, *args, **kwargs):
        self.observations.append(decode_json(canonical_bytes(args[-1])))

    def accept_analysis(self, actor, project_id, stage_id, attempt_id, snapshot, result, contract, *, cancel_requested=None):
        if self.attempt.cancel_requested or cancel_requested is not None and cancel_requested():
            raise AnalysisError('ANALYSIS_CANCELED')
        candidate = contract.validate_result(self.attempt.prepared, self.attempt.request, snapshot, result)
        self.accepted = AcceptedSummary(
            'summary-fixture', 1, self.attempt.prepared.target_capture_id, self.attempt.prepared.source_hash,
            contract.definition_hash, self.attempt.prepared.input_hash, candidate,
            decode_json(canonical_bytes(result)),
        )
        return self.accepted


class RecordingPort:
    def __init__(self, handler):
        self.handler = handler
        self.calls = []
        self.timeouts = []

    def _call(self, method, *args):
        self.calls.append((method, args))
        return self.handler(method, *args)

    def start(self, principal, request):
        return self._call('start', principal, request)

    def lookup(self, principal, request, *, timeout=None):
        self.timeouts.append(timeout)
        return self._call('lookup', principal, request)

    def get(self, principal, request, run_id, *, timeout=None):
        self.timeouts.append(timeout)
        return self._call('get', principal, request, run_id)

    def result(self, principal, request, run_id):
        return self._call('result', principal, request, run_id)

    def cancel(self, principal, run_id, *, timeout=None):
        self.timeouts.append(timeout)
        return self._call('cancel', principal, run_id)


class TestSummaryAnalysis(SummaryScenario, unittest.TestCase):
    def service(self, handler):
        self.value = self.attempt()
        self.journal = MemoryJournal(self.value)
        self.port = RecordingPort(handler)
        return SummaryAnalysisService(self.journal, self.contract, self.port)

    def advance(self, service, **kwargs):
        return service.advance(
            self.actor, self.project.id, self.stage.id, self.value.attempt_id,
            principal=kwargs.get('principal', self.value.principal),
            cancel_requested=kwargs.get('cancel_requested'),
        )

    def test_shouldRecoverLostSubmitUsingTheSameImmutableKeyAndDeadline(self):
        attempts = []

        def handler(method, principal, request, *args):
            snapshot, result = self.responses(self.value)
            if method == 'start':
                attempts.append(request)
                if len(attempts) == 1:
                    raise TaskRunError('RUN_UNAVAILABLE', runtime_code='runtime_call_timeout', retry='observe')
            return result if method == 'result' else snapshot

        service = self.service(handler)
        self.assertEqual('unknown', self.advance(service).state)
        recovered = self.advance(SummaryAnalysisService(self.journal, self.contract, self.port))
        self.assertEqual('accepted', recovered.state)
        self.assertEqual([self.value.request], attempts)
        self.assertEqual(['start', 'lookup', 'result'], [call[0] for call in self.port.calls])
        self.assertEqual(self.port.calls[0][1], self.port.calls[1][1])

    def test_missing_lookup_keeps_original_dispatch_unknown_without_admission(self):
        service = self.service(lambda method, *args: None if method == 'lookup' else self.fail('Unexpected admission'))
        self.journal.attempt = replace(self.value, dispatched=True)
        original = self.journal.attempt.request
        self.assertEqual('unknown', self.advance(service).state)
        self.assertEqual(original, self.journal.attempt.request)
        self.assertIsNone(self.journal.accepted)
        self.assertEqual(['lookup'], [call[0] for call in self.port.calls])

    def test_lost_dispatch_claim_observes_instead_of_admitting(self):
        service = self.service(lambda method, *args: None if method == 'lookup' else self.fail('Unexpected admission'))
        self.journal.claim_analysis_dispatch = lambda *args, **kwargs: False
        self.assertEqual('unknown', self.advance(service).state)
        self.assertEqual(['lookup'], [call[0] for call in self.port.calls])

    def test_shouldNotSubmitBeforeTheDurableClaimSucceeds(self):
        service = self.service(lambda *args: self.fail('No port call may occur'))
        self.journal.claim_failure = True
        with self.assertRaises(ArchiveError):
            self.advance(service)
        self.assertEqual([], self.port.calls)

    def test_shouldRefuseChangedPrincipalAndExpiredUndispatchedInput(self):
        service = self.service(lambda *args: self.fail('No port call may occur'))
        with self.assertRaises(AnalysisError):
            self.advance(service, principal=replace(self.value.principal, subject='other'))
        self.journal.attempt = replace(
            self.value, request=replace(self.value.request, deadline_at=datetime.now(UTC) - timedelta(seconds=1)),
        )
        with self.assertRaises(AnalysisError):
            self.advance(service)
        self.assertEqual([], self.port.calls)

    def test_shouldObserveKnownRunWithoutAnotherAdmission(self):
        service = self.service(lambda method, *args: self.responses(self.value)[0])
        self.journal.attempt = replace(self.value, dispatched=True)
        running = replace(self.responses(self.value)[0], status='running')
        self.journal.observations.append({'snapshot': decode_json(canonical_bytes(running))})
        self.port.handler = lambda *args: running
        self.assertEqual('running', self.advance(service).state)
        self.assertEqual(['get'], [call[0] for call in self.port.calls])

    def test_shouldKeepUnknownDispatchUnacceptedEvenWhenStatusSaysSucceeded(self):
        service = self.service(lambda *args: None)
        snapshot = self.responses(self.value)[0]
        uncertain = replace(snapshot, dispatch=replace(snapshot.dispatch, uncertainty='unknown'))
        self.port.handler = lambda *args: uncertain
        self.assertEqual('unknown', self.advance(service).state)
        self.assertIsNone(self.journal.accepted)
        self.assertEqual(['start'], [call[0] for call in self.port.calls])

    def test_shouldRespectCancellationAtDispatchAndAcceptanceFences(self):
        service = self.service(lambda *args: self.fail('No port call may occur'))
        self.assertEqual('canceled', self.advance(service, cancel_requested=lambda: True).state)
        service = self.service(lambda method, *args: self.responses(self.value)[1 if method == 'result' else 0])
        calls = {'count': 0}

        def canceled():
            calls['count'] += 1
            return calls['count'] > 1

        self.assertEqual('canceled', self.advance(service, cancel_requested=canceled).state)
        self.assertIsNone(self.journal.accepted)

    def test_shouldDistinguishAdmissionRejectionFromResultReadFailure(self):
        def rejected(*args):
            raise TaskRunError('input_schema_invalid', runtime_code='input_schema_invalid', retry='correct')

        service = self.service(rejected)
        self.assertEqual('rejected', self.advance(service).state)
        self.assertEqual('correct', self.journal.observations[-1]['retry'])
        service = self.service(lambda method, *args: rejected() if method == 'result' else self.responses(self.value)[0])
        self.assertEqual('unknown', self.advance(service).state)
        self.assertEqual('result', self.journal.observations[-1]['operation'])

    def test_cancel_with_unknown_run_id_must_not_admit_new_work(self):
        service = self.service(lambda method, *args: None if method == 'lookup' else self.fail('Unexpected admission'))
        self.journal.attempt = replace(self.value, dispatched=True)
        result = service.cancel(
            self.actor, self.project.id, self.stage.id, self.value.attempt_id, principal=self.value.principal,
        )
        self.assertEqual('cancel_requested', result.state)
        self.assertIsNone(result.acknowledged)
        self.assertEqual(['lookup'], [call[0] for call in self.port.calls])

    def test_cancel_recovers_original_run_with_lookup_then_observes_cancel(self):
        service = self.service(lambda *args: None)
        self.journal.attempt = replace(self.value, dispatched=True)
        snapshot = self.responses(self.value)[0]
        self.port.handler = lambda method, *args: (
            TaskRunCancellation(run_id=snapshot.run_id, canceled=True) if method == 'cancel'
            else replace(snapshot, status='canceled' if method == 'get' else 'running')
        )
        result = service.cancel(
            self.actor, self.project.id, self.stage.id, self.value.attempt_id, principal=self.value.principal,
        )
        self.assertEqual('canceled', result.state)
        self.assertTrue(result.acknowledged)
        self.assertEqual(['lookup', 'cancel', 'get'], [call[0] for call in self.port.calls])

    def test_cancel_lookup_failure_preserves_uncertainty(self):
        def unavailable(*args):
            raise TaskRunError('RUN_UNAVAILABLE', runtime_code='runtime_call_timeout', retry='observe')

        service = self.service(unavailable)
        self.journal.attempt = replace(self.value, dispatched=True)
        result = service.cancel(
            self.actor, self.project.id, self.stage.id, self.value.attempt_id, principal=self.value.principal,
        )
        self.assertEqual('cancel_requested', result.state)
        self.assertIsNone(result.run_id)
        self.assertIsNone(result.acknowledged)
        self.assertEqual('runtime_call_timeout', result.error_code)
        self.assertEqual(['lookup'], [call[0] for call in self.port.calls])

    def test_cancel_acknowledgement_requires_a_separate_observed_snapshot(self):
        service = self.service(lambda *args: None)
        running = replace(self.responses(self.value)[0], status='running')
        self.journal.attempt = replace(self.value, dispatched=True)
        self.journal.observations.append({'snapshot': decode_json(canonical_bytes(running))})
        self.port.handler = lambda method, *args: (
            TaskRunCancellation(run_id='run-fixture', canceled=True) if method == 'cancel' else running
        )
        result = service.cancel(
            self.actor, self.project.id, self.stage.id, self.value.attempt_id, principal=self.value.principal,
        )
        self.assertEqual('cancel_requested', result.state)
        self.assertTrue(result.acknowledged)
        self.assertEqual(['cancel', 'get'], [call[0] for call in self.port.calls])

    def test_cancel_shares_one_deadline_and_preserves_ack_when_observation_budget_expires(self):
        service = self.service(lambda *args: None)
        running = replace(self.responses(self.value)[0], status='running')
        self.journal.attempt = replace(self.value, dispatched=True)
        self.port.handler = lambda method, *args: (
            TaskRunCancellation(run_id=running.run_id, canceled=True) if method == 'cancel' else running
        )
        with patch('project_management.services.summary_analysis.time.monotonic',
                   side_effect=[100.0, 101.0, 104.0, 110.1]):
            result = service.cancel(
                self.actor, self.project.id, self.stage.id, self.value.attempt_id,
                principal=self.value.principal, timeout_seconds=10,
            )
        self.assertEqual('cancel_requested', result.state)
        self.assertTrue(result.acknowledged)
        self.assertEqual('runtime_call_timeout', result.error_code)
        self.assertEqual(['lookup', 'cancel'], [call[0] for call in self.port.calls])
        self.assertEqual([9.0, 6.0], self.port.timeouts)
        self.assertTrue(self.journal.observations[-1]['cancel']['canceled'])
        self.assertIsNone(self.journal.accepted)

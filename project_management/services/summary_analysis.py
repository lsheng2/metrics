from datetime import UTC, datetime
import math
import time

from project_management.app.domain.summary_contracts import AnalysisCancellation, AnalysisError, AnalysisStep
from project_management.app.domain.task_run_codec import cancellation_from_record, snapshot_from_record
from project_management.app.domain.task_run_observations import execution_is_settled
from project_management.app.domain.task_runs import TaskPrincipal, TaskRunError
from project_management.services.summary_journal_reads import validate_principal


class SummaryAnalysisService:
    def __init__(self, archive, contract, task_run_port, clock=None):
        self.archive = archive
        self.contract = contract
        self.task_run_port = task_run_port
        self.clock = clock or (lambda: datetime.now(UTC))

    def prepare(self, actor, project_id, stage_id, source_key, *, principal, deadline_at, cancel_requested=None):
        validate_principal(principal, actor.subject)
        return self.archive.prepare_analysis(
            actor, project_id, stage_id, source_key, self.contract, principal, deadline_at,
            cancel_requested=cancel_requested,
        )

    def _attempt(self, arguments, principal):
        validate_principal(principal, arguments[0].subject)
        attempt = self.archive.read_analysis_attempt(*arguments)
        if not isinstance(principal, TaskPrincipal) or attempt.principal != principal:
            raise AnalysisError('ANALYSIS_PRINCIPAL_MISMATCH')
        self.contract.validate_request(attempt.request)
        return attempt

    def _observations(self, arguments, attempt):
        observations = self.archive.read_analysis_observations(*arguments)
        latest = None
        acknowledgement = None
        for observation in observations:
            if not isinstance(observation, dict):
                raise AnalysisError('ANALYSIS_INVALID')
            try:
                if 'snapshot' in observation:
                    snapshot = snapshot_from_record(observation['snapshot'])
                    self.contract.validate_snapshot(attempt.request, snapshot)
                    if latest is not None and latest.run_id != snapshot.run_id:
                        raise AnalysisError('ANALYSIS_RESULT_INVALID')
                    latest = snapshot
                if 'cancel' in observation:
                    acknowledgement = cancellation_from_record(observation['cancel'])
                    if observation.get('run_id') != acknowledgement.run_id:
                        raise AnalysisError('ANALYSIS_RESULT_INVALID')
            except (TypeError, ValueError):
                raise AnalysisError('ANALYSIS_RESULT_INVALID') from None
        if acknowledgement is not None and latest is not None and acknowledgement.run_id != latest.run_id:
            raise AnalysisError('ANALYSIS_RESULT_INVALID')
        return latest, acknowledgement

    def advance(self, actor, project_id, stage_id, attempt_id, *, principal, cancel_requested=None):
        arguments = (actor, project_id, stage_id, attempt_id)
        attempt = self._attempt(arguments, principal)
        if attempt.cancel_requested:
            canceled = self.cancel(*arguments, principal=principal)
            return AnalysisStep(canceled.state, attempt_id, error_code=canceled.error_code)
        if not attempt.dispatched and attempt.request.deadline_at <= self.clock():
            raise AnalysisError('ANALYSIS_DEADLINE_EXPIRED')
        snapshot, _ = self._observations(arguments, attempt)
        operation = 'observe'
        try:
            if not attempt.dispatched:
                claimed = self.archive.claim_analysis_dispatch(*arguments, cancel_requested=cancel_requested)
                operation = 'submit' if claimed else 'observe'
            if snapshot is None:
                if operation == 'submit':
                    snapshot = self.task_run_port.start(principal, attempt.request)
                else:
                    snapshot = self.task_run_port.lookup(principal, attempt.request)
                    if snapshot is None:
                        self.archive.record_analysis_observation(
                            *arguments, {'state': 'unknown', 'operation': 'lookup'},
                        )
                        return AnalysisStep('unknown', attempt_id)
            else:
                snapshot = self.task_run_port.get(principal, attempt.request, snapshot.run_id)
            self.contract.validate_snapshot(attempt.request, snapshot)
            self.archive.record_analysis_observation(*arguments, {'snapshot': snapshot})
            if snapshot.dispatch.uncertainty == 'unknown':
                return AnalysisStep('unknown', attempt_id, error_code=snapshot.error_code)
            if snapshot.status != 'succeeded':
                return AnalysisStep(snapshot.status, attempt_id, error_code=snapshot.error_code)
            operation = 'result'
            result = self.task_run_port.result(principal, attempt.request, snapshot.run_id)
            self.contract.validate_result(attempt.prepared, attempt.request, snapshot, result)
            accepted = self.archive.accept_analysis(
                *arguments, snapshot, result, self.contract, cancel_requested=cancel_requested,
            )
            return AnalysisStep('accepted', attempt_id, accepted)
        except AnalysisError as error:
            if error.code == 'ANALYSIS_CANCELED':
                return AnalysisStep('canceled', attempt_id, error_code=error.code)
            raise
        except TaskRunError as error:
            state = 'rejected' if operation == 'submit' and error.retry == 'correct' else 'unknown'
            code = error.runtime_code or error.code
            self.archive.record_analysis_observation(*arguments, {
                'state': state, 'code': code, 'retry': error.retry, 'operation': operation,
            })
            return AnalysisStep(state, attempt_id, error_code=code)

    def cancel(self, actor, project_id, stage_id, attempt_id, *, principal, timeout_seconds=10):
        if (type(timeout_seconds) not in (int, float)
                or not math.isfinite(timeout_seconds) or timeout_seconds <= 0):
            raise AnalysisError('ANALYSIS_INVALID')
        deadline = time.monotonic() + timeout_seconds

        def call(method, *args):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TaskRunError('RUN_UNAVAILABLE', runtime_code='runtime_call_timeout', retry='observe')
            return method(*args, timeout=remaining)

        arguments = (actor, project_id, stage_id, attempt_id)
        attempt = self._attempt(arguments, principal)
        attempt = self.archive.request_analysis_cancel(*arguments)
        if not attempt.dispatched:
            return AnalysisCancellation('canceled', attempt_id, None, None)
        snapshot, acknowledgement = self._observations(arguments, attempt)
        new_acknowledgement = False
        try:
            if snapshot is None:
                snapshot = call(self.task_run_port.lookup, principal, attempt.request)
                if snapshot is None:
                    self.archive.record_analysis_observation(
                        *arguments, {'state': 'cancel_requested', 'operation': 'lookup'},
                    )
                    return AnalysisCancellation('cancel_requested', attempt_id, None, None)
                self.contract.validate_snapshot(attempt.request, snapshot)
            if acknowledgement is not None and execution_is_settled(snapshot):
                return AnalysisCancellation(snapshot.status, attempt_id, snapshot.run_id, acknowledgement.canceled)
            if acknowledgement is None:
                acknowledgement = call(self.task_run_port.cancel, principal, snapshot.run_id)
                new_acknowledgement = True
                if acknowledgement.run_id != snapshot.run_id:
                    raise AnalysisError('ANALYSIS_RESULT_INVALID')
            current = call(self.task_run_port.get, principal, attempt.request, snapshot.run_id)
            self.contract.validate_snapshot(attempt.request, current)
            if current.run_id != snapshot.run_id:
                raise AnalysisError('ANALYSIS_RESULT_INVALID')
            observation = {'snapshot': current}
            if new_acknowledgement:
                observation.update(run_id=current.run_id, cancel=acknowledgement)
            self.archive.record_analysis_observation(
                *arguments, observation, cancellation=new_acknowledgement,
            )
            state = current.status if execution_is_settled(current) else 'cancel_requested'
            return AnalysisCancellation(state, attempt_id, current.run_id, acknowledgement.canceled)
        except TaskRunError as error:
            run_id = None if snapshot is None else snapshot.run_id
            observation = {
                'state': 'cancel_requested', 'run_id': run_id,
                'code': error.runtime_code or error.code, 'retry': error.retry,
            }
            if snapshot is not None:
                observation['snapshot'] = snapshot
            if new_acknowledgement:
                observation['cancel'] = acknowledgement
            self.archive.record_analysis_observation(
                *arguments, observation, cancellation=new_acknowledgement,
            )
            return AnalysisCancellation(
                'cancel_requested', attempt_id, run_id,
                None if acknowledgement is None else acknowledgement.canceled,
                error.runtime_code or error.code,
            )

import asyncio
from datetime import UTC, datetime
import re

from ai_base_application_sdk import TaskRunClientError

from project_management.app.domain.summary_contracts import AnalysisCancellation, AnalysisError, AnalysisStep


class SummaryAnalysisService:
    def __init__(self, archive, contract, client_factory, clock=None):
        self.archive = archive
        self.contract = contract
        self.client_factory = client_factory
        self.clock = clock or (lambda: datetime.now(UTC))
        self.control_timeout_seconds = 10

    def prepare(self, actor, project_id, stage_id, source_key, *, backend, deadline_at, cancel_requested=None):
        return self.archive.prepare_analysis(actor, project_id, stage_id, source_key,
                                             self.contract, backend, deadline_at,
                                             cancel_requested=cancel_requested)

    async def advance(self, actor, project_id, stage_id, attempt_id, *, backend, cancel_requested=None):
        arguments = (actor, project_id, stage_id, attempt_id)
        attempt = await asyncio.to_thread(self.archive.read_analysis_attempt, *arguments)
        if attempt.backend != backend:
            raise AnalysisError('ANALYSIS_BACKEND_MISMATCH')
        if attempt.cancel_requested:
            return AnalysisStep('canceled', attempt_id, error_code='ANALYSIS_CANCELED')
        remaining = (datetime.fromisoformat(attempt.request['deadlineAt']) - self.clock()).total_seconds()
        if remaining <= 0:
            raise AnalysisError('ANALYSIS_DEADLINE_EXPIRED')
        if not attempt.dispatched:
            self.contract.validate_request(attempt.request)
        try:
            dispatch = await asyncio.to_thread(self.archive.claim_analysis_dispatch, *arguments,
                                               cancel_requested=cancel_requested)
            operation = 'submit' if dispatch else 'observe'
            async with self.client_factory(backend) as client:
                snapshot = await self._network(
                    attempt, lambda: client.submit(attempt.request) if dispatch else client.get_by_client_key(
                        backend.scope_key, attempt.attempt_id,
                    ),
                )
                self.contract.validate_snapshot(attempt, snapshot)
                await asyncio.to_thread(self.archive.record_analysis_observation, *arguments, {'snapshot': snapshot})
                if snapshot['state'] != 'succeeded':
                    return AnalysisStep(snapshot['state'], attempt_id)
                operation = 'result'
                result = await self._network(attempt, lambda: client.get_result(backend.scope_key, snapshot['runId']))
                self.contract.validate_result(attempt, snapshot, result)
                accepted = await asyncio.to_thread(self.archive.accept_analysis, *arguments,
                                                   snapshot, result, self.contract,
                                                   cancel_requested=cancel_requested)
                return AnalysisStep('accepted', attempt_id, accepted)
        except AnalysisError as error:
            if error.code == 'ANALYSIS_CANCELED':
                return AnalysisStep('canceled', attempt_id, error_code=error.code)
            raise
        except (TaskRunClientError, TimeoutError) as error:
            code = error.code if isinstance(error, TaskRunClientError) else 'transport_outcome_unknown'
            if not isinstance(code, str) or re.fullmatch('[a-z][a-z0-9_]{0,79}', code) is None:
                code = 'invalid_response'
            recovery = error.recovery if isinstance(error, TaskRunClientError) else 'query_by_client_key'
            if recovery not in {'correct_request', 'query_by_client_key', 'stop', 'poll', 'query_run'}:
                recovery = 'query_by_client_key'
            status = error.status if isinstance(error, TaskRunClientError) else None
            state = 'rejected' if operation == 'submit' and recovery == 'correct_request' and status in {400, 413, 422} else 'unknown'
            observation = {'state': state, 'code': code, 'recovery': recovery, 'status': status, 'operation': operation}
            await asyncio.to_thread(self.archive.record_analysis_observation, *arguments, observation)
            return AnalysisStep(state, attempt_id, error_code=code)

    async def cancel(self, actor, project_id, stage_id, attempt_id, *, backend, timeout_seconds=None):
        arguments = (actor, project_id, stage_id, attempt_id)
        attempt = await asyncio.to_thread(self.archive.read_analysis_attempt, *arguments)
        if attempt.backend != backend:
            raise AnalysisError('ANALYSIS_BACKEND_MISMATCH')
        attempt = await asyncio.to_thread(self.archive.request_analysis_cancel, *arguments)
        if attempt.backend != backend:
            raise AnalysisError('ANALYSIS_BACKEND_MISMATCH')
        if not attempt.dispatched:
            return AnalysisCancellation('canceled', attempt_id, None, 'not_requested')
        observations = await asyncio.to_thread(self.archive.read_analysis_observations, *arguments)
        retained = self._retained_cancellation(attempt, observations)
        if retained is not None:
            return retained
        run_id = self._observed_run_id(attempt, observations)
        control_deadline = self._control_deadline(timeout_seconds)
        async with self.client_factory(backend) as client:
            if run_id is None:
                try:
                    snapshot = await self._control_network(control_deadline, lambda: client.get_by_client_key(
                        backend.scope_key, attempt.attempt_id,
                    ))
                    self.contract.validate_snapshot(attempt, snapshot)
                    run_id = snapshot['runId']
                except (TaskRunClientError, TimeoutError) as error:
                    if self._refuses_trusted_identity(error):
                        raise AnalysisError('ANALYSIS_RESULT_INVALID') from None
                    code, status = self._safe_transport_error(error)
                    observation = {'state': 'cancel_requested', 'remote_stop': 'unknown',
                                   'code': code, 'status': status}
                    await asyncio.to_thread(self.archive.record_analysis_observation, *arguments,
                                            observation, cancellation=True)
                    return AnalysisCancellation('cancel_requested', attempt_id, None, 'unknown', code)
            try:
                response = await self._control_network(control_deadline, lambda: client.cancel(backend.scope_key, run_id))
                snapshot = self.contract.validate_cancel(attempt, response, expected_run_id=run_id)
                await asyncio.to_thread(self.archive.record_analysis_observation, *arguments,
                                        {'run_id': run_id, 'cancel': response}, cancellation=True)
                return AnalysisCancellation('canceled', attempt_id, run_id,
                                            snapshot['dispatch']['remoteStop'])
            except (TaskRunClientError, TimeoutError) as error:
                if self._refuses_trusted_identity(error):
                    raise AnalysisError('ANALYSIS_RESULT_INVALID') from None
                code, status = self._safe_transport_error(error)
                observation = {'state': 'cancel_requested', 'run_id': run_id, 'remote_stop': 'unknown',
                               'code': code, 'status': status}
                await asyncio.to_thread(self.archive.record_analysis_observation, *arguments,
                                        observation, cancellation=True)
                return AnalysisCancellation('cancel_requested', attempt_id, run_id, 'unknown', code)

    async def _network(self, attempt, action):
        remaining = (datetime.fromisoformat(attempt.request['deadlineAt']) - self.clock()).total_seconds()
        if remaining <= 0:
            raise TimeoutError
        async with asyncio.timeout(remaining):
            return await action()

    def _control_deadline(self, timeout_seconds=None):
        seconds = self.control_timeout_seconds if timeout_seconds is None else timeout_seconds
        if type(seconds) not in {int, float} or not 0 < seconds <= 10:
            raise AnalysisError('ANALYSIS_INVALID')
        return asyncio.get_running_loop().time() + seconds

    async def _control_network(self, deadline, action):
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise TimeoutError
        async with asyncio.timeout(remaining):
            return await action()

    def _retained_cancellation(self, attempt, observations):
        for observation in reversed(observations):
            if 'cancel' in observation:
                response = observation['cancel']
                try:
                    run_id = observation['run_id']
                    snapshot = self.contract.validate_cancel(attempt, response, expected_run_id=run_id)
                    return AnalysisCancellation('canceled', attempt.attempt_id, run_id,
                                                snapshot['dispatch']['remoteStop'])
                except (KeyError, TypeError):
                    raise AnalysisError('ANALYSIS_RESULT_INVALID') from None
            if observation.get('state') == 'cancel_requested' and observation.get('remote_stop') == 'unknown':
                if len(observations) >= 17:
                    return AnalysisCancellation('cancel_requested', attempt.attempt_id, observation.get('run_id'),
                                                'unknown', observation.get('code'))
        return None

    def _observed_run_id(self, attempt, observations):
        run_id = None
        for observation in observations:
            if 'snapshot' in observation:
                snapshot = observation['snapshot']
                self.contract.validate_snapshot(attempt, snapshot)
                run_id = snapshot['runId']
        return run_id

    def _safe_transport_error(self, error):
        code = error.code if isinstance(error, TaskRunClientError) else 'transport_outcome_unknown'
        if not isinstance(code, str) or re.fullmatch('[a-z][a-z0-9_]{0,79}', code) is None:
            code = 'invalid_response'
        status = error.status if isinstance(error, TaskRunClientError) else None
        return code, status

    def _refuses_trusted_identity(self, error):
        return isinstance(error, TaskRunClientError) and error.code in {
            'invalid_response', 'contract_unsupported', 'run_store_mismatch',
        }

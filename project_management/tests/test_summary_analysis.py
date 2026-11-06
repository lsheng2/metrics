from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import unittest

from ai_base_application_sdk import TaskRunClient
import httpx

from project_management.app.api.summary_analysis import SummaryAnalysisService
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.summary_contracts import AcceptedSummary, AnalysisError, AnalysisPreparation
from project_management.tests.summary_fixtures import SummaryScenario


class MemoryJournal:
    def __init__(self, attempt):
        self.attempt = attempt
        self.observations = []
        self.accepted = None
        self.claim_failure = False

    def prepare_analysis(self, *args, **kwargs):
        return AnalysisPreparation('no_work', accepted=self.accepted) if self.accepted else AnalysisPreparation('ready', self.attempt)

    def read_analysis_attempt(self, *args):
        return deepcopy(self.attempt)

    def claim_analysis_dispatch(self, *args, cancel_requested=None):
        if self.claim_failure:
            raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE')
        if cancel_requested is not None and cancel_requested():
            raise AnalysisError('ANALYSIS_CANCELED')
        if self.attempt.dispatched:
            return False
        self.attempt = replace(self.attempt, dispatched=True)
        return True

    def record_analysis_observation(self, *args):
        self.observations.append(deepcopy(args[-1]))

    def accept_analysis(self, actor, project_id, stage_id, attempt_id, snapshot, result, contract, *, cancel_requested=None):
        if cancel_requested is not None and cancel_requested():
            raise AnalysisError('ANALYSIS_CANCELED')
        candidate = contract.validate_result(self.attempt, snapshot, result)
        self.accepted = AcceptedSummary('summary-fixture', 1, self.attempt.prepared.target_capture_id,
                                        self.attempt.prepared.source_hash, contract.definition_hash,
                                        self.attempt.prepared.input_hash, candidate, deepcopy(result))
        return self.accepted


class TestSummaryAnalysis(SummaryScenario, unittest.IsolatedAsyncioTestCase):
    def service(self, handler):
        self.value = self.attempt()
        self.journal = MemoryJournal(self.value)
        self.requests = []

        def transport(request):
            self.requests.append((request.method, request.url.path, request.url.params.get('clientRunKey')))
            return handler(request)

        def client(target):
            return TaskRunClient(
                base_url=target.base_url, source_app_id=target.source_app_id, run_store_id=target.run_store_id,
                credential_ref='synthetic-test', token='synthetic-only', transport=httpx.MockTransport(transport),
            )

        return SummaryAnalysisService(self.journal, self.contract, client)

    async def advance(self, service, **kwargs):
        return await service.advance(self.actor, self.project.id, self.stage.id, self.value.attempt_id,
                                     backend=kwargs.get('backend', self.value.backend))

    async def test_shouldRecoverLostSubmitByOriginalKeyWithoutAnotherPost(self):
        def handler(request):
            if request.method == 'POST':
                raise httpx.ReadTimeout('Synthetic lost response.', request=request)
            snapshot, result = self.responses(self.value)
            return httpx.Response(200, json=result if request.url.path.endswith('/result') else snapshot)

        service = self.service(handler)
        first = await self.advance(service)
        self.assertEqual('unknown', first.state)
        recovered = await self.advance(SummaryAnalysisService(self.journal, self.contract, service.client_factory))
        self.assertEqual('accepted', recovered.state)
        self.assertEqual([('POST', '/api/runs', None),
                          ('GET', '/api/runs/by-client-key', self.value.attempt_id),
                          ('GET', '/api/runs/run-fixture/result', None)], self.requests)
        self.assertEqual(self.value.prepared.input_hash, recovered.accepted.input_hash)

    async def test_shouldNotConstructASubmitAfterDurableClaimFailure(self):
        service = self.service(lambda request: self.fail('No HTTP request may occur.'))
        self.journal.claim_failure = True
        with self.assertRaises(ArchiveError):
            await self.advance(service)
        self.assertEqual([], self.requests)

    async def test_shouldRefuseWrongStoreOrExpiredOriginalDeadlineBeforeNetwork(self):
        service = self.service(lambda request: self.fail('No HTTP request may occur.'))
        with self.assertRaises(AnalysisError):
            await self.advance(service, backend=replace(self.value.backend, run_store_id='another-store'))
        self.journal.attempt.request['deadlineAt'] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
        with self.assertRaises(AnalysisError):
            await self.advance(service)
        self.assertEqual([], self.requests)

    async def test_shouldNotFetchResultForCanceledRun(self):
        def handler(request):
            snapshot, _ = self.responses(self.value)
            snapshot['state'] = 'canceled'
            snapshot['result'] = {'availability': 'not_produced', 'sha256': None, 'mediaType': None, 'expiresAt': None}
            return httpx.Response(200, json=snapshot)

        service = self.service(handler)
        result = await self.advance(service)
        self.assertEqual(('canceled', 1, None), (result.state, len(self.requests), self.journal.accepted))

    async def test_shouldEvaluateTrustedCancelCallbackInsideDispatchAndAcceptanceFence(self):
        service = self.service(lambda request: self.fail('Canceled dispatch must not use HTTP.'))
        step = await service.advance(
            self.actor,
            self.project.id,
            self.stage.id,
            self.value.attempt_id,
            backend=self.value.backend,
            cancel_requested=lambda: True,
        )
        self.assertEqual(('canceled', 'ANALYSIS_CANCELED', []), (step.state, step.error_code, self.requests))

        def handler(request):
            snapshot, result = self.responses(self.value)
            return httpx.Response(200, json=result if request.url.path.endswith('/result') else snapshot)

        service = self.service(handler)
        first = {'value': True}

        def cancel_after_dispatch():
            if first['value']:
                first['value'] = False
                return False
            return True

        step = await service.advance(
            self.actor,
            self.project.id,
            self.stage.id,
            self.value.attempt_id,
            backend=self.value.backend,
            cancel_requested=cancel_after_dispatch,
        )
        self.assertEqual(('canceled', 'ANALYSIS_CANCELED', None), (step.state, step.error_code, self.journal.accepted))

    async def test_shouldPreserveDefiniteRequestRejectionWithoutInventingUnknownExecution(self):
        service = self.service(lambda request: httpx.Response(422, json={
            'contractVersion': 'task-run/1',
            'error': {'code': 'invalid_request', 'recovery': 'correct_request'},
        }))
        result = await self.advance(service)
        self.assertEqual(('rejected', 'correct_request', 422, 1),
                         (result.state, self.journal.observations[-1]['recovery'],
                          self.journal.observations[-1]['status'], len(self.requests)))
        self.assertEqual('submit', self.journal.observations[-1]['operation'])

    async def test_shouldDistinguishResultReadFailureFromSubmitRejection(self):
        def handler(request):
            if request.url.path.endswith('/result'):
                return httpx.Response(422, json={
                    'contractVersion': 'task-run/1',
                    'error': {'code': 'invalid_request', 'recovery': 'correct_request'},
                })
            snapshot, _ = self.responses(self.value)
            return httpx.Response(200, json=snapshot)

        service = self.service(handler)
        await self.advance(service)
        self.assertEqual('result', self.journal.observations[-1]['operation'])
        self.assertIsNone(self.journal.accepted)

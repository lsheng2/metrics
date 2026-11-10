from copy import deepcopy
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import uuid

from ai_base_application_sdk import TaskRunClient
import httpx

from project_management.app.api import ProjectActor, ProjectError
from project_management.app.api.capture_archive import MembershipInput, PartCoverage
from project_management.app.domain.capture_values import canonical_bytes, content_hash, decode_json, sha256_bytes
from project_management.app.domain.captures import ArchiveError, ArchiveStorageConfig
from project_management.app.domain.summary_contracts import AcceptedSummary, AnalysisError
from project_management.app.api.summary_analysis import SummaryAnalysisService
from project_management.app.spi.archive import CommitReceipt
from project_management.storage.paths import safe_relative_path
from project_management.tests.capture_archive_fixtures import ProjectApiStub
from project_management.tests.report_source_memory import (
    MemoryCaptureArchiveService, MemoryRepository, MemoryRepositoryFactory,
)
from project_management.tests.summary_fixtures import SummaryScenario


class CancellationMemoryJournal:
    def __init__(self, attempt):
        self.attempt = attempt
        self.observations = []
        self.cancel_requests = 0
        self.dispatch_claims = 0
        self.cancel_on_claim = False
        self.cancel_on_accept = False

    def read_analysis_attempt(self, *args):
        return deepcopy(self.attempt)

    def request_analysis_cancel(self, *args):
        self.cancel_requests += 1
        self.attempt = replace(self.attempt, cancel_requested=True)
        return deepcopy(self.attempt)

    def read_analysis_observations(self, *args):
        return tuple(deepcopy(row) for row in self.observations)

    def record_analysis_observation(self, *args, cancellation=False):
        self.observations.append(deepcopy(args[-1]))

    def claim_analysis_dispatch(self, *args, cancel_requested=None):
        self.dispatch_claims += 1
        if self.cancel_on_claim or (cancel_requested is not None and cancel_requested()):
            self.attempt = replace(self.attempt, cancel_requested=True)
        if self.attempt.cancel_requested:
            raise AnalysisError('ANALYSIS_CANCELED')
        if self.attempt.dispatched:
            return False
        self.attempt = replace(self.attempt, dispatched=True)
        return True

    def accept_analysis(self, actor, project_id, stage_id, attempt_id, snapshot, result, contract, *, cancel_requested=None):
        if self.cancel_on_accept or (cancel_requested is not None and cancel_requested()):
            self.attempt = replace(self.attempt, cancel_requested=True)
        if self.attempt.cancel_requested:
            raise AnalysisError('ANALYSIS_CANCELED')
        candidate = contract.validate_result(self.attempt, snapshot, result)
        return AcceptedSummary('summary-fixture', 1, self.attempt.prepared.target_capture_id,
                               self.attempt.prepared.source_hash, contract.definition_hash,
                               self.attempt.prepared.input_hash, candidate, deepcopy(result))


class SlowCancelClient:
    def __init__(self, snapshot, response, *, delay):
        self.snapshot = snapshot
        self.response = response
        self.delay = delay
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get_by_client_key(self, scope_key, client_run_key):
        self.calls.append('lookup')
        await asyncio.sleep(self.delay)
        return deepcopy(self.snapshot)

    async def cancel(self, scope_key, run_id):
        self.calls.append('cancel')
        return deepcopy(self.response)


class WritableMemoryRepository(MemoryRepository):
    def __init__(self, project, stage, files, root):
        super().__init__(project, stage, files)
        self.history = [self.commit]
        self.stage_root = root / 'projects' / project.id / 'stages' / stage.id
        self.archive = self.stage_root / 'archive'
        self.runtime = self.stage_root / 'runtime'
        self.objects = self.stage_root / 'objects'
        self.archive.mkdir(parents=True)
        self.runtime.mkdir(parents=True)
        self.objects.mkdir(parents=True)

    def initialize(self):
        return self.commit

    def _check_commit(self, git_path, commit):
        # Appends build a linear history, so like git a path stays readable at every later commit.
        requested = self.commit if commit == 'main' else commit
        written = self.history.index(self.commits[git_path])
        if requested not in self.history or written > self.history.index(requested):
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')

    def append_record(self, record_id, namespace, files, *, expected_head, record_fingerprint):
        if self.commit != expected_head:
            raise ArchiveError('ARCHIVE_CHAIN_CONFLICT')
        if namespace not in {'captures', 'source_resolution', 'analysis_attempts', 'accepted_summaries'}:
            raise ArchiveError('UNSAFE_PATH')
        for path, data in files.items():
            parts = safe_relative_path(path)
            if parts[0] != namespace or type(data) is not bytes:
                raise ArchiveError('UNSAFE_PATH')
        parent = self.commit
        commit = f'{len(self.history) + 1:040x}'
        for path, data in files.items():
            self.files[path] = bytes(data)
            self.commits[path] = commit
        self.history.append(commit)
        self.commit = commit
        return CommitReceipt(commit, parent, 'f' * 40, record_fingerprint, 'current')


class TestAnalysisCancellation(SummaryScenario, unittest.IsolatedAsyncioTestCase):
    def service(self, handler):
        self.value = self.attempt()
        self.journal = CancellationMemoryJournal(self.value)
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

    async def advance(self, service):
        return await service.advance(self.actor, self.project.id, self.stage.id, self.value.attempt_id,
                                     backend=self.value.backend)

    def running_snapshot(self):
        snapshot, _ = self.responses(self.value)
        snapshot['state'] = 'running'
        snapshot['terminalAt'] = None
        snapshot['result'] = {'availability': 'pending', 'sha256': None, 'mediaType': None, 'expiresAt': None}
        return snapshot

    def cancel_response(self, *, run_id='run-fixture', remote_stop='confirmed', cancel_applied=True):
        snapshot = self.running_snapshot()
        snapshot['runId'] = run_id
        snapshot['state'] = 'canceled'
        snapshot['terminalAt'] = '2026-11-02T00:00:40.000Z'
        snapshot['result'] = {'availability': 'not_produced', 'sha256': None, 'mediaType': None, 'expiresAt': None}
        snapshot['dispatch']['remoteStop'] = remote_stop
        return {'contractVersion': 'task-run/1', 'cancelApplied': cancel_applied, 'run': snapshot}

    async def test_shouldPersistCancelIntentAndSkipSdkWhenAttemptWasNeverDispatched(self):
        service = self.service(lambda request: self.fail('No HTTP request may occur.'))
        result = await service.cancel(self.actor, self.project.id, self.stage.id, self.value.attempt_id,
                                      backend=self.value.backend)
        step = await service.advance(self.actor, self.project.id, self.stage.id, self.value.attempt_id,
                                     backend=self.value.backend)
        self.assertEqual(('canceled', self.value.attempt_id, None, 'not_requested'),
                         (result.state, result.attempt_id, result.run_id, result.remote_stop))
        self.assertEqual(('canceled', 1, 0, []),
                         (step.state, self.journal.cancel_requests, self.journal.dispatch_claims, self.requests))

    async def test_shouldLookupOriginalKeyOnlyWhenDispatchedRunIsUnknown(self):
        def handler(request):
            if request.method == 'GET' and request.url.path == '/api/runs/by-client-key':
                return httpx.Response(404, json={
                    'contractVersion': 'task-run/1',
                    'error': {'code': 'run_not_found', 'recovery': 'stop'},
                })
            self.fail(f'Unexpected request: {request.method} {request.url.path}')

        service = self.service(handler)
        self.journal.attempt = replace(self.value, dispatched=True)
        result = await service.cancel(self.actor, self.project.id, self.stage.id, self.value.attempt_id,
                                      backend=self.value.backend)
        self.assertEqual(('cancel_requested', None, 'unknown', 'run_not_found'),
                         (result.state, result.run_id, result.remote_stop, result.error_code))
        self.assertEqual([('GET', '/api/runs/by-client-key', self.value.attempt_id)], self.requests)
        self.assertEqual(('cancel_requested', 'unknown'), (self.journal.observations[-1]['state'],
                                                           self.journal.observations[-1]['remote_stop']))

    async def test_shouldCancelObservedRunOnceAndReplayStoredOutcome(self):
        def handler(request):
            self.assertEqual(('POST', '/api/runs/run-fixture/cancel'), (request.method, request.url.path))
            return httpx.Response(200, json=self.cancel_response(remote_stop='confirmed'))

        service = self.service(handler)
        self.journal.attempt = replace(self.value, dispatched=True)
        self.journal.observations.append({'snapshot': self.running_snapshot()})
        first = await service.cancel(self.actor, self.project.id, self.stage.id, self.value.attempt_id,
                                     backend=self.value.backend)
        replay = await service.cancel(self.actor, self.project.id, self.stage.id, self.value.attempt_id,
                                      backend=self.value.backend)
        self.assertEqual(('canceled', 'run-fixture', 'confirmed'),
                         (first.state, first.run_id, first.remote_stop))
        self.assertEqual((first, [('POST', '/api/runs/run-fixture/cancel', None)]), (replay, self.requests))
        self.assertEqual(True, self.journal.observations[-1]['cancel']['cancelApplied'])

    async def test_shouldRejectRetainedCancelWhenNestedRunIdIsCorrupted(self):
        service = self.service(lambda request: httpx.Response(200, json=self.cancel_response()))
        self.journal.attempt = replace(self.value, dispatched=True)
        self.journal.observations.append({'snapshot': self.running_snapshot()})
        await service.cancel(self.actor, self.project.id, self.stage.id, self.value.attempt_id,
                             backend=self.value.backend)
        self.journal.observations[-1]['cancel']['run']['runId'] = 'another-run'
        with self.assertRaises(AnalysisError) as caught:
            await service.cancel(self.actor, self.project.id, self.stage.id, self.value.attempt_id,
                                 backend=self.value.backend)
        self.assertEqual(('ANALYSIS_RESULT_INVALID', [('POST', '/api/runs/run-fixture/cancel', None)]),
                         (caught.exception.code, self.requests))

    async def test_shouldReplayLookupFirstCancelFromStoredRunIdWithoutAnotherRequest(self):
        def handler(request):
            if request.method == 'GET':
                return httpx.Response(200, json=self.running_snapshot())
            if request.method == 'POST':
                return httpx.Response(200, json=self.cancel_response(remote_stop='confirmed'))
            self.fail(f'Unexpected request: {request.method} {request.url.path}')

        service = self.service(handler)
        self.journal.attempt = replace(self.value, dispatched=True)
        first = await service.cancel(self.actor, self.project.id, self.stage.id, self.value.attempt_id,
                                     backend=self.value.backend)
        replay = await service.cancel(self.actor, self.project.id, self.stage.id, self.value.attempt_id,
                                      backend=self.value.backend)
        self.assertEqual(('canceled', 'run-fixture', 'confirmed'), (first.state, first.run_id, first.remote_stop))
        self.assertEqual((first, 'run-fixture',
                          [('GET', '/api/runs/by-client-key', self.value.attempt_id),
                           ('POST', '/api/runs/run-fixture/cancel', None)]),
                         (replay, self.journal.observations[-1]['run_id'], self.requests))

    async def test_shouldRejectWrongBackendAndInvalidCancelIdentityWithoutRecordingOutcome(self):
        service = self.service(lambda request: self.fail('Wrong backend must not use HTTP.'))
        with self.assertRaises(AnalysisError) as caught:
            await service.cancel(self.actor, self.project.id, self.stage.id, self.value.attempt_id,
                                 backend=replace(self.value.backend, run_store_id='another-store'))
        self.assertEqual(('ANALYSIS_BACKEND_MISMATCH', [], []),
                         (caught.exception.code, self.requests, self.journal.observations))

        def handler(request):
            return httpx.Response(200, json=self.cancel_response(run_id='another-run'))

        service = self.service(handler)
        self.journal.attempt = replace(self.value, dispatched=True)
        self.journal.observations.append({'snapshot': self.running_snapshot()})
        with self.assertRaises(AnalysisError) as invalid:
            await service.cancel(self.actor, self.project.id, self.stage.id, self.value.attempt_id,
                                 backend=self.value.backend)
        self.assertEqual(('ANALYSIS_RESULT_INVALID', 1),
                         (invalid.exception.code, len(self.journal.observations)))

    async def test_shouldReturnCanceledWhenIntentWinsDispatchOrAcceptanceRace(self):
        service = self.service(lambda request: self.fail('Dispatch race must not use HTTP.'))
        self.journal.cancel_on_claim = True
        first = await self.advance(service)
        self.assertEqual(('canceled', 'ANALYSIS_CANCELED', []),
                         (first.state, first.error_code, self.requests))

        def handler(request):
            snapshot, result = self.responses(self.value)
            return httpx.Response(200, json=result if request.url.path.endswith('/result') else snapshot)

        service = self.service(handler)
        self.journal.cancel_on_accept = True
        second = await self.advance(service)
        self.assertEqual(('canceled', 'ANALYSIS_CANCELED',
                          [('POST', '/api/runs', None), ('GET', '/api/runs/run-fixture/result', None)]),
                         (second.state, second.error_code, self.requests))

    async def test_shouldUseOneSharedControlBudgetForLookupAndCancel(self):
        service = self.service(lambda request: self.fail('Custom client factory is used.'))
        self.journal.attempt = replace(self.value, dispatched=True)
        client = SlowCancelClient(self.running_snapshot(), self.cancel_response(), delay=0.02)
        service.client_factory = lambda backend: client
        service.control_timeout_seconds = 0.01
        result = await service.cancel(self.actor, self.project.id, self.stage.id, self.value.attempt_id,
                                      backend=self.value.backend)
        self.assertEqual(('cancel_requested', None, 'unknown', 'transport_outcome_unknown', ['lookup']),
                         (result.state, result.run_id, result.remote_stop, result.error_code, client.calls))

    async def test_shouldHonorPerCallCancellationTimeoutAtMostTenSeconds(self):
        service = self.service(lambda request: self.fail('Custom client factory is used.'))
        self.journal.attempt = replace(self.value, dispatched=True)
        client = SlowCancelClient(self.running_snapshot(), self.cancel_response(), delay=0.02)
        service.client_factory = lambda backend: client
        result = await service.cancel(
            self.actor,
            self.project.id,
            self.stage.id,
            self.value.attempt_id,
            backend=self.value.backend,
            timeout_seconds=0.01,
        )
        with self.assertRaises(AnalysisError):
            await service.cancel(
                self.actor,
                self.project.id,
                self.stage.id,
                self.value.attempt_id,
                backend=self.value.backend,
                timeout_seconds=11,
            )
        self.assertEqual(('cancel_requested', 'transport_outcome_unknown', ['lookup']),
                         (result.state, result.error_code, client.calls))

    async def test_shouldRequeryOriginalKeyWhenPriorUnknownCancelHasObservationRoom(self):
        def handler(request):
            if request.method == 'GET':
                return httpx.Response(200, json=self.running_snapshot())
            if request.method == 'POST':
                return httpx.Response(200, json=self.cancel_response(remote_stop='unsupported',
                                                                     cancel_applied=False))
            self.fail(f'Unexpected request: {request.method} {request.url.path}')

        service = self.service(handler)
        self.journal.attempt = replace(self.value, dispatched=True)
        self.journal.observations.append({
            'state': 'cancel_requested', 'remote_stop': 'unknown', 'code': 'run_not_found',
        })
        result = await service.cancel(self.actor, self.project.id, self.stage.id, self.value.attempt_id,
                                      backend=self.value.backend)
        self.assertEqual(('canceled', 'run-fixture', 'unsupported',
                          [('GET', '/api/runs/by-client-key', self.value.attempt_id),
                           ('POST', '/api/runs/run-fixture/cancel', None)]),
                         (result.state, result.run_id, result.remote_stop, self.requests))


class TestAnalysisCancellationJournal(SummaryScenario, unittest.TestCase):
    def attempt_variant(self, label, *, dispatched=False):
        attempt = self.attempt()
        value = json.loads(attempt.prepared.input_content)
        value['test_variant'] = label
        content = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        input_hash = sha256_bytes(content.encode())
        prepared = replace(attempt.prepared, input_content=content, input_hash=input_hash)
        attempt_id = str(uuid.uuid5(uuid.UUID(self.stage.id), input_hash))
        request = deepcopy(attempt.request)
        request['clientRunKey'] = attempt_id
        request['input'] = dict(request['input'], content=content, sha256=input_hash)
        request['logicalInputHash'] = dict(request['logicalInputHash'], digest=input_hash)
        return replace(attempt, attempt_id=attempt_id, prepared=prepared, request=request, dispatched=dispatched)

    def analysis_files(self, attempts):
        files = {}
        for attempt in attempts:
            stored = replace(attempt, dispatched=False, cancel_requested=False)
            intent = {'schema_version': 1, 'kind': 'intent', 'attempt_id': attempt.attempt_id, 'payload': stored}
            files[f'analysis_attempts/{attempt.attempt_id}/intent.json'] = canonical_bytes(intent)
            if attempt.dispatched:
                dispatch = {
                    'schema_version': 1,
                    'kind': 'dispatch',
                    'attempt_id': attempt.attempt_id,
                    'payload': {'intent_hash': content_hash(intent),
                                'claimed_at': datetime.now(UTC).isoformat()},
                }
                files[f'analysis_attempts/{attempt.attempt_id}/dispatch.json'] = canonical_bytes(dispatch)
        return files

    @contextmanager
    def memory_archive(self, files):
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / 'memory-archive-root'
            root.mkdir()
            repository = WritableMemoryRepository(self.project, self.stage, files, root)
            archive = MemoryCaptureArchiveService(
                ProjectApiStub(self.project, self.stage),
                MemoryRepositoryFactory(repository),
                ArchiveStorageConfig(root, 'Archive Test', 'archive@example.test', self.limits()),
            )
            yield archive

    def capture_source(self, archive):
        intent = replace(self.intent(), required_parts=('facts', 'comments', 'history'))
        archive.prepare(self.actor, intent)
        page = archive.append_page(self.actor, intent, self.page())
        _, original = self.summary_source()
        snapshot = replace(original, raw_page_ids=(page.page_id,))
        archive.append_snapshot(self.actor, intent, snapshot)
        archive.finalize(self.actor, intent, MembershipInput((snapshot.identity,), self.complete_part(), (page.page_id,)),
                         complete=True)
        return self.source_key(intent, snapshot.identity)

    def prepare(self, archive, source_key):
        return archive.prepare_analysis(self.actor, self.project.id, self.stage.id, source_key, self.contract,
                                        self.backend(), datetime.now(UTC) + timedelta(minutes=5)).attempt

    def cancel_response(self, attempt):
        snapshot, _ = self.responses(attempt)
        snapshot['state'] = 'canceled'
        snapshot['terminalAt'] = '2026-11-02T00:00:40.000Z'
        snapshot['result'] = {'availability': 'not_produced', 'sha256': None, 'mediaType': None, 'expiresAt': None}
        snapshot['dispatch']['remoteStop'] = 'confirmed'
        return {'contractVersion': 'task-run/1', 'cancelApplied': True, 'run': snapshot}

    def test_shouldFenceDispatchAndReserveCancelObservationUsingMemoryRepository(self):
        cancel_attempt = self.attempt_variant('cancel-before-dispatch')
        observed_attempt = self.attempt_variant('reserved-observation', dispatched=True)
        files = self.analysis_files((cancel_attempt, observed_attempt))
        with self.memory_archive(files) as archive:
            canceled = archive.request_analysis_cancel(self.actor, self.project.id, self.stage.id,
                                                       cancel_attempt.attempt_id)
            with self.assertRaises(AnalysisError) as dispatch_refused:
                archive.claim_analysis_dispatch(self.actor, self.project.id, self.stage.id, cancel_attempt.attempt_id)
            for index in range(16):
                archive.record_analysis_observation(self.actor, self.project.id, self.stage.id,
                                                    observed_attempt.attempt_id,
                                                    {'state': 'unknown', 'code': f'transport_{index}'})
            with self.assertRaises(AnalysisError) as ordinary_overflow:
                archive.record_analysis_observation(self.actor, self.project.id, self.stage.id,
                                                    observed_attempt.attempt_id, {'state': 'unknown'})
            archive.request_analysis_cancel(self.actor, self.project.id, self.stage.id, observed_attempt.attempt_id)
            archive.record_analysis_observation(self.actor, self.project.id, self.stage.id,
                                                observed_attempt.attempt_id,
                                                {'cancel': self.cancel_response(observed_attempt)},
                                                cancellation=True)
            observations = archive.read_analysis_observations(self.actor, self.project.id, self.stage.id,
                                                              observed_attempt.attempt_id)

        self.assertEqual(('ANALYSIS_CANCELED', 'ANALYSIS_OBSERVATION_LIMIT', True),
                         (dispatch_refused.exception.code, ordinary_overflow.exception.code,
                          canceled.cancel_requested))
        self.assertEqual((17, True), (len(observations), observations[-1]['cancel']['cancelApplied']))

    def test_shouldReplayAcceptedSummaryAfterLaterCancelRequestUsingMemoryRepository(self):
        with self.memory_archive({}) as archive:
            # Replay re-verifies accepted history, so acceptance must come from the real journal path.
            attempt = self.prepare(archive, self.capture_source(archive))
            archive.claim_analysis_dispatch(self.actor, self.project.id, self.stage.id, attempt.attempt_id)
            snapshot, result = self.responses(attempt)
            accepted = archive.accept_analysis(self.actor, self.project.id, self.stage.id,
                                               attempt.attempt_id, snapshot, result, self.contract)
            canceled = archive.request_analysis_cancel(self.actor, self.project.id, self.stage.id, attempt.attempt_id)
            replay = archive.accept_analysis(self.actor, self.project.id, self.stage.id,
                                             attempt.attempt_id, snapshot, result, self.contract)

        self.assertEqual((True, str(uuid.uuid5(uuid.UUID(attempt.attempt_id), 'accepted')), accepted),
                         (canceled.cancel_requested, replay.summary_id, replay))

    def test_shouldRefuseDamagedCancelIntentHashWithoutNetworkOrJournalGrowth(self):
        attempt = self.attempt_variant('damaged-cancel-intent')
        files = self.analysis_files((attempt,))
        cancel_path = f'analysis_attempts/{attempt.attempt_id}/cancel.json'
        files[cancel_path] = canonical_bytes({
            'schema_version': 1,
            'kind': 'cancel',
            'attempt_id': attempt.attempt_id,
            'payload': {'intent_hash': '0' * 64, 'requested_at': datetime.now(UTC).isoformat()},
        })
        with self.memory_archive(files) as archive:
            repository = archive.repository_factory.repository
            before = deepcopy(repository.files)

            with self.assertRaises(AnalysisError) as read_error:
                archive.read_analysis_attempt(self.actor, self.project.id, self.stage.id, attempt.attempt_id)

            def client_factory(backend):
                raise AssertionError('Damaged cancel intent must not construct SDK client.')

            service = SummaryAnalysisService(archive, self.contract, client_factory)
            with self.assertRaises(AnalysisError) as cancel_error:
                asyncio.run(service.cancel(self.actor, self.project.id, self.stage.id, attempt.attempt_id,
                                           backend=attempt.backend))

            self.assertEqual(('ANALYSIS_INVALID', 'ANALYSIS_INVALID', before),
                             (read_error.exception.code, cancel_error.exception.code, repository.files))

    def test_shouldPersistReloadAndProtectCancelNamespaceUsingMinimalRealGit(self):
        with self.archive_service() as (root, archive):
            cancel_attempt = self.prepare(archive, self.capture_source(archive))
            canceled = archive.request_analysis_cancel(self.actor, self.project.id, self.stage.id,
                                                       cancel_attempt.attempt_id)
            reloaded = type(archive)(archive.project_api, archive.repository_factory, archive.config)
            reloaded_attempt = reloaded.read_analysis_attempt(self.actor, self.project.id, self.stage.id,
                                                             cancel_attempt.attempt_id)
            cancel_path = f'analysis_attempts/{cancel_attempt.attempt_id}/cancel.json'
            cancel_record = decode_json(self.git(self.archive_path(root), 'show', f'main:{cancel_path}'))
            intent_record = decode_json(self.git(self.archive_path(root), 'show',
                                                f'main:analysis_attempts/{cancel_attempt.attempt_id}/intent.json'))
            repository = reloaded.repository_factory.open(reloaded.config, reloaded.project_api.project,
                                                          reloaded.project_api.stage, self.actor.subject)
            repository.verify_identity()
            with self.assertRaises(ArchiveError) as unsafe:
                repository.append_record(
                    str(uuid.uuid5(uuid.UUID(cancel_attempt.attempt_id), 'cancel')),
                    'analysis_attempts',
                    {f'analysis_attempts/{cancel_attempt.attempt_id}/cancel-extra.json': b'{}'},
                    expected_head=repository.head(),
                    record_fingerprint=sha256_bytes(b'{}'),
                )
            with self.assertRaises(ProjectError):
                reloaded.request_analysis_cancel(ProjectActor('other-owner'), self.project.id, self.stage.id,
                                                 cancel_attempt.attempt_id)

            self.assertEqual((True, True), (canceled.cancel_requested, reloaded_attempt.cancel_requested))
            self.assertEqual(('cancel', cancel_attempt.attempt_id, content_hash(intent_record), 'UNSAFE_PATH'),
                             (cancel_record['kind'], cancel_record['attempt_id'],
                              cancel_record['payload']['intent_hash'], unsafe.exception.code))

    def test_shouldFencePrepareClaimAndAcceptWithTrustedCallbackInArchiveLock(self):
        with self.memory_archive({}) as archive:
            source_key = self.capture_source(archive)
            with self.assertRaises(AnalysisError) as prepare_error:
                archive.prepare_analysis(
                    self.actor,
                    self.project.id,
                    self.stage.id,
                    source_key,
                    self.contract,
                    self.backend(),
                    datetime.now(UTC) + timedelta(minutes=5),
                    cancel_requested=lambda: True,
                )
            attempt = self.prepare(archive, source_key)
            with self.assertRaises(AnalysisError) as claim_error:
                archive.claim_analysis_dispatch(
                    self.actor,
                    self.project.id,
                    self.stage.id,
                    attempt.attempt_id,
                    cancel_requested=lambda: True,
                )
            archive.claim_analysis_dispatch(self.actor, self.project.id, self.stage.id, attempt.attempt_id)
            snapshot, result = self.responses(attempt)
            with self.assertRaises(AnalysisError) as accept_error:
                archive.accept_analysis(
                    self.actor,
                    self.project.id,
                    self.stage.id,
                    attempt.attempt_id,
                    snapshot,
                    result,
                    self.contract,
                    cancel_requested=lambda: True,
                )

        self.assertEqual(('ANALYSIS_CANCELED', 'ANALYSIS_CANCELED', 'ANALYSIS_CANCELED'),
                         (prepare_error.exception.code, claim_error.exception.code, accept_error.exception.code))

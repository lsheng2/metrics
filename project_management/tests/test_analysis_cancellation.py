from copy import deepcopy
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import uuid

from project_management.app.api import ProjectActor, ProjectError
from project_management.app.api.capture_archive import MembershipInput
from project_management.app.domain.capture_values import canonical_bytes, content_hash, decode_json, sha256_bytes
from project_management.app.domain.captures import ArchiveError, ArchiveStorageConfig
from project_management.app.domain.summary_contracts import AcceptedSummary, AnalysisError
from project_management.app.api.summary_analysis import SummaryAnalysisService
from project_management.app.domain.task_runs import TaskResultSummary, TaskRunCancellation
from project_management.app.spi.archive import CommitReceipt
from project_management.storage.paths import safe_relative_path
from project_management.tests.capture_archive_fixtures import ProjectApiStub
from project_management.tests.report_source_memory import (
    MemoryCaptureArchiveService, MemoryRepository, MemoryRepositoryFactory,
)
from project_management.tests.summary_fixtures import SummaryScenario
from project_management.tests.test_summary_analysis import MemoryJournal, RecordingPort


class CancellationMemoryJournal(MemoryJournal):
    def __init__(self, attempt):
        super().__init__(attempt)
        self.cancel_requests = 0
        self.dispatch_claims = 0
        self.cancel_on_claim = False
        self.cancel_on_accept = False

    def read_analysis_attempt(self, *args):
        return self.attempt

    def request_analysis_cancel(self, *args):
        self.cancel_requests += 1
        self.attempt = replace(self.attempt, cancel_requested=True)
        return self.attempt

    def read_analysis_observations(self, *args):
        return tuple(deepcopy(row) for row in self.observations)

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
        candidate = contract.validate_result(self.attempt.prepared, self.attempt.request, snapshot, result)
        return AcceptedSummary('summary-fixture', 1, self.attempt.prepared.target_capture_id,
                               self.attempt.prepared.source_hash, contract.definition_hash,
                               self.attempt.prepared.input_hash, candidate, decode_json(canonical_bytes(result)))


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


class TestAnalysisCancellation(SummaryScenario, unittest.TestCase):
    def service(self, handler):
        self.value = self.attempt()
        self.journal = CancellationMemoryJournal(self.value)
        self.port = RecordingPort(handler)
        return SummaryAnalysisService(self.journal, self.contract, self.port)

    def advance(self, service):
        return service.advance(
            self.actor, self.project.id, self.stage.id, self.value.attempt_id,
            principal=self.value.principal,
        )

    def cancel(self, service, *, principal=None, timeout_seconds=10):
        return service.cancel(
            self.actor, self.project.id, self.stage.id, self.value.attempt_id,
            principal=principal or self.value.principal,
            timeout_seconds=timeout_seconds,
        )

    def running_snapshot(self):
        snapshot, _ = self.responses(self.value)
        return replace(
            snapshot,
            status='running',
            result=TaskResultSummary(output_sha256=None, output_schema_sha256=None, usage=None),
        )

    def canceled_snapshot(self, run_id='run-fixture'):
        return replace(
            self.running_snapshot(),
            run_id=run_id,
            status='canceled',
            result=TaskResultSummary(output_sha256=None, output_schema_sha256=None, usage=None),
        )

    def cancel_response(self, *, run_id='run-fixture', canceled=True):
        return TaskRunCancellation(run_id=run_id, canceled=canceled)

    def test_shouldPersistCancelIntentAndSkipSdkWhenAttemptWasNeverDispatched(self):
        service = self.service(lambda *args: self.fail('No task-run port call may occur.'))
        result = self.cancel(service)
        step = self.advance(service)
        self.assertEqual(('canceled', self.value.attempt_id, None, None),
                         (result.state, result.attempt_id, result.run_id, result.acknowledged))
        self.assertEqual(('canceled', 2, 0, []),
                         (step.state, self.journal.cancel_requests, self.journal.dispatch_claims, self.port.calls))

    def test_shouldLookupOriginalKeyOnlyWhenDispatchedRunIsUnknown(self):
        service = self.service(lambda method, *args: None if method == 'lookup' else self.fail('Unexpected admission'))
        self.journal.attempt = replace(self.value, dispatched=True)
        result = self.cancel(service)
        lookup_request = self.port.calls[0][1][1]
        self.assertEqual(('cancel_requested', None, None, None),
                         (result.state, result.run_id, result.acknowledged, result.error_code))
        self.assertEqual(['lookup'], [call[0] for call in self.port.calls])
        self.assertEqual((self.value.attempt_id, self.value.request.deadline_at),
                         (lookup_request.client_run_key, lookup_request.deadline_at))
        self.assertEqual('cancel_requested', self.journal.observations[-1]['state'])

    def test_shouldCancelObservedRunOnceAndReplayStoredOutcome(self):
        def handler(method, *args):
            if method == 'cancel':
                return self.cancel_response()
            if method == 'get':
                return self.canceled_snapshot()
            self.fail(f'Unexpected port call: {method}')

        service = self.service(handler)
        self.journal.attempt = replace(self.value, dispatched=True)
        self.journal.observations.append({'snapshot': decode_json(canonical_bytes(self.running_snapshot()))})
        first = self.cancel(service)
        replay = self.cancel(service)
        self.assertEqual(('canceled', 'run-fixture', True),
                         (first.state, first.run_id, first.acknowledged))
        self.assertEqual((first, ['cancel', 'get']), (replay, [call[0] for call in self.port.calls]))
        self.assertEqual(True, self.journal.observations[-1]['cancel']['canceled'])

    def test_shouldRejectRetainedCancelWhenNestedRunIdIsCorrupted(self):
        service = self.service(lambda method, *args: self.cancel_response() if method == 'cancel'
                               else self.canceled_snapshot())
        self.journal.attempt = replace(self.value, dispatched=True)
        self.journal.observations.append({'snapshot': decode_json(canonical_bytes(self.running_snapshot()))})
        self.cancel(service)
        self.journal.observations[-1]['cancel']['run_id'] = 'another-run'
        with self.assertRaises(AnalysisError) as caught:
            self.cancel(service)
        self.assertEqual(('ANALYSIS_RESULT_INVALID', ['cancel', 'get']),
                         (caught.exception.code, [call[0] for call in self.port.calls]))

    def test_shouldReplayLookupFirstCancelFromStoredRunIdWithoutAnotherRequest(self):
        def handler(method, *args):
            if method == 'lookup':
                return self.running_snapshot()
            if method == 'cancel':
                return self.cancel_response()
            if method == 'get':
                return self.canceled_snapshot()
            self.fail(f'Unexpected port call: {method}')

        service = self.service(handler)
        self.journal.attempt = replace(self.value, dispatched=True)
        first = self.cancel(service)
        replay = self.cancel(service)
        self.assertEqual(('canceled', 'run-fixture', True), (first.state, first.run_id, first.acknowledged))
        self.assertEqual((first, 'run-fixture', ['lookup', 'cancel', 'get']),
                         (replay, self.journal.observations[-1]['run_id'], [call[0] for call in self.port.calls]))

    def test_shouldRejectWrongPrincipalAndInvalidCancelIdentityWithoutRecordingOutcome(self):
        service = self.service(lambda *args: self.fail('Wrong principal must not use task-run port.'))
        with self.assertRaises(AnalysisError) as caught:
            self.cancel(service, principal=replace(self.value.principal, subject='other-owner'))
        self.assertEqual(('ANALYSIS_PRINCIPAL_MISMATCH', [], []),
                         (caught.exception.code, self.port.calls, self.journal.observations))

        def handler(method, *args):
            if method == 'cancel':
                return self.cancel_response(run_id='another-run')
            if method == 'get':
                return self.canceled_snapshot()
            self.fail(f'Unexpected port call: {method}')

        service = self.service(handler)
        self.journal.attempt = replace(self.value, dispatched=True)
        self.journal.observations.append({'snapshot': decode_json(canonical_bytes(self.running_snapshot()))})
        with self.assertRaises(AnalysisError) as invalid:
            self.cancel(service)
        self.assertEqual(('ANALYSIS_RESULT_INVALID', 1),
                         (invalid.exception.code, len(self.journal.observations)))

    def test_shouldReturnCanceledWhenIntentWinsDispatchOrAcceptanceRace(self):
        service = self.service(lambda *args: self.fail('Dispatch race must not use task-run port.'))
        self.journal.cancel_on_claim = True
        first = self.advance(service)
        self.assertEqual(('canceled', 'ANALYSIS_CANCELED', []),
                         (first.state, first.error_code, self.port.calls))

        def handler(method, *args):
            snapshot, result = self.responses(self.value)
            return result if method == 'result' else snapshot

        service = self.service(handler)
        self.journal.cancel_on_accept = True
        second = self.advance(service)
        self.assertEqual(('canceled', 'ANALYSIS_CANCELED',
                          ['start', 'result']),
                         (second.state, second.error_code, [call[0] for call in self.port.calls]))

    def test_shouldUseOneSharedControlBudgetForLookupAndCancel(self):
        service = self.service(lambda method, *args: self.running_snapshot() if method == 'lookup'
                               else self.fail(f'Unexpected port call: {method}'))
        self.journal.attempt = replace(self.value, dispatched=True)
        with patch('project_management.services.summary_analysis.time.monotonic',
                   side_effect=[100.0, 100.002, 100.012]):
            result = self.cancel(service, timeout_seconds=0.01)
        self.assertEqual(('cancel_requested', 'run-fixture', None, 'runtime_call_timeout', ['lookup']),
                         (result.state, result.run_id, result.acknowledged, result.error_code,
                          [call[0] for call in self.port.calls]))
        self.assertAlmostEqual(0.008, self.port.timeouts[0], places=3)

    def test_shouldHonorPerCallCancellationTimeoutAndRejectInvalidValues(self):
        def handler(method, *args):
            if method == 'lookup':
                return self.running_snapshot()
            if method == 'cancel':
                return self.cancel_response()
            if method == 'get':
                return self.canceled_snapshot()
            self.fail(f'Unexpected port call: {method}')

        service = self.service(handler)
        self.journal.attempt = replace(self.value, dispatched=True)
        with patch('project_management.services.summary_analysis.time.monotonic',
                   side_effect=[100.0, 100.0, 100.001, 100.002]):
            result = self.cancel(service, timeout_seconds=0.01)
        with self.assertRaises(AnalysisError):
            self.cancel(service, timeout_seconds=0)
        self.assertEqual(('canceled', True, ['lookup', 'cancel', 'get']),
                         (result.state, result.acknowledged, [call[0] for call in self.port.calls]))
        self.assertEqual(3, len(self.port.timeouts))
        self.assertAlmostEqual(0.01, self.port.timeouts[0], places=3)
        self.assertAlmostEqual(0.009, self.port.timeouts[1], places=3)
        self.assertAlmostEqual(0.008, self.port.timeouts[2], places=3)

    def test_shouldRequeryOriginalKeyWhenPriorUnknownCancelHasObservationRoom(self):
        def handler(method, *args):
            if method == 'lookup':
                return self.running_snapshot()
            if method == 'cancel':
                return self.cancel_response(canceled=False)
            if method == 'get':
                return self.canceled_snapshot()
            self.fail(f'Unexpected port call: {method}')

        service = self.service(handler)
        self.journal.attempt = replace(self.value, dispatched=True)
        self.journal.observations.append({
            'state': 'cancel_requested', 'code': 'run_not_found',
        })
        result = self.cancel(service)
        lookup_request = self.port.calls[0][1][1]
        self.assertEqual(('canceled', 'run-fixture', False, ['lookup', 'cancel', 'get']),
                         (result.state, result.run_id, result.acknowledged,
                          [call[0] for call in self.port.calls]))
        self.assertEqual((self.value.attempt_id, self.value.request.deadline_at),
                         (lookup_request.client_run_key, lookup_request.deadline_at))


class TestAnalysisCancellationJournal(SummaryScenario, unittest.TestCase):
    def attempt_variant(self, label, *, dispatched=False):
        attempt = self.attempt()
        value = json.loads(attempt.prepared.input_content)
        value['test_variant'] = label
        content = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        input_hash = sha256_bytes(content.encode())
        prepared = replace(attempt.prepared, input_content=content, input_hash=input_hash)
        attempt_id = str(uuid.uuid5(uuid.UUID(self.stage.id), input_hash))
        request = replace(
            attempt.request,
            client_run_key=attempt_id,
            input_json=content,
            input_sha256=input_hash,
        )
        return replace(attempt, attempt_id=attempt_id, prepared=prepared, request=request, dispatched=dispatched)

    def analysis_files(self, attempts):
        files = {}
        for attempt in attempts:
            stored = replace(attempt, dispatched=False, cancel_requested=False)
            intent = {'schema_version': 2, 'kind': 'intent', 'attempt_id': attempt.attempt_id, 'payload': stored}
            files[f'analysis_attempts/{attempt.attempt_id}/intent.json'] = canonical_bytes(intent)
            if attempt.dispatched:
                dispatch = {
                    'schema_version': 2,
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
                                        self.principal(), datetime.now(UTC) + timedelta(minutes=5)).attempt

    def cancel_response(self, attempt):
        snapshot, _ = self.responses(attempt)
        return TaskRunCancellation(run_id=snapshot.run_id, canceled=True)

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
        self.assertEqual((17, True), (len(observations), observations[-1]['cancel']['canceled']))

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
            'schema_version': 2,
            'kind': 'cancel',
            'attempt_id': attempt.attempt_id,
            'payload': {'intent_hash': '0' * 64, 'requested_at': datetime.now(UTC).isoformat()},
        })
        with self.memory_archive(files) as archive:
            repository = archive.repository_factory.repository
            before = deepcopy(repository.files)

            with self.assertRaises(AnalysisError) as read_error:
                archive.read_analysis_attempt(self.actor, self.project.id, self.stage.id, attempt.attempt_id)

            service = SummaryAnalysisService(archive, self.contract, object())
            with self.assertRaises(AnalysisError) as cancel_error:
                service.cancel(self.actor, self.project.id, self.stage.id, attempt.attempt_id,
                               principal=attempt.principal)

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
                    self.principal(),
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

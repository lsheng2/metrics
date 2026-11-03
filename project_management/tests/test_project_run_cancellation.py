from dataclasses import replace
from pathlib import Path
import uuid

from ai_base_application_sdk import TaskRunClient
import httpx
import pytest

from project_management.app.api.project_runs import RunPolicy
from project_management.app.api.project_runs import ItemRunResult, ProjectRunWorker, RunError
from project_management.app.domain.capture_values import content_hash
from project_management.app.domain.capture_values import decode_json
from project_management.tests.project_run_fixtures import ManualRunEnvironment


def test_FS05_canceling_queued_operation_persists_terminal_canceled_without_capture(tmp_path):
    environment = ManualRunEnvironment(tmp_path / 'archive-root')
    operation = environment.run_service.submit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        environment.request(str(uuid.uuid4())),
    )

    canceled = environment.run_service.cancel(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        operation.operation_id,
        expected_revision=operation.revision,
    )

    assert (canceled.state, canceled.cancel_requested, environment.provider.open_count) == ('canceled', True, 0)


def test_FS05_archived_owner_may_cancel_historical_nonterminal_operation(tmp_path):
    environment = ManualRunEnvironment(tmp_path / 'archive-root')
    operation = environment.run_service.submit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        environment.request(str(uuid.uuid4())),
    )
    environment.project_api.project = replace(environment.project, archived=True)
    environment.archive.project_api.project = environment.project_api.project

    canceled = environment.run_service.cancel(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        operation.operation_id,
        expected_revision=operation.revision,
    )

    assert canceled.state == 'canceled'


def test_FS05_canceling_analyzing_operation_records_attempt_intent_before_return(tmp_path):
    environment = ManualRunEnvironment(tmp_path / 'archive-root')
    operation = environment.run_service.submit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        environment.request(str(uuid.uuid4())),
    )
    context = environment.run_service.capture_context(operation)
    environment.capture_service.capture(context, cancel_requested=lambda: False)
    manifest = environment.archive.read_capture(environment.actor, environment.project.id, environment.stage.id, operation.capture_id)
    source_key = environment.archive._source_key(manifest.intent, manifest.membership.items[0])
    prepared = environment.analysis_service.prepare(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        source_key,
        backend=environment.backend(environment.actor, environment.project.id, environment.stage.id),
        deadline_at=environment.run_service.operation_deadline(operation),
    )
    from project_management.app.api.project_runs import ItemRunResult

    store = environment.archive.project_operation_repository(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        write=True,
    )
    capturing = replace(operation, state='capturing', revision=2)
    store.transition(capturing, expected_revision=operation.revision)
    analyzing = replace(
        capturing,
        state='analyzing',
        revision=3,
        item_results=(ItemRunResult('a' * 64, 'running', prepared.attempt.attempt_id, None, None),),
    )
    store.transition(analyzing, expected_revision=capturing.revision)

    canceled = environment.run_service.cancel(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        operation.operation_id,
        expected_revision=analyzing.revision,
    )

    reloaded = environment.archive.read_analysis_attempt(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        prepared.attempt.attempt_id,
    )
    assert (canceled.state, canceled.cancel_requested, reloaded.cancel_requested) == ('cancel_requested', True, True)


def test_FS05_late_worker_result_cannot_clear_cancel_intent(tmp_path):
    environment = ManualRunEnvironment(tmp_path / 'archive-root')
    operation = environment.run_service.submit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        environment.request(str(uuid.uuid4())),
    )
    canceled = environment.run_service.cancel(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        operation.operation_id,
        expected_revision=operation.revision,
    )

    with pytest.raises(RunError) as error:
        environment.archive.project_operation_repository(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            write=True,
        ).transition(replace(canceled, state='draft_ready', revision=canceled.revision + 1,
                             cancel_requested=False), expected_revision=canceled.revision)

    assert error.value.code == 'RUN_REVISION_CONFLICT'
    operation_root = (
        Path(tmp_path / 'archive-root')
        / 'projects'
        / environment.project.id
        / 'stages'
        / environment.stage.id
        / 'runtime'
        / 'operations'
        / operation.operation_id
    )
    state = decode_json((operation_root / 'state.json').read_bytes())['operation']['state']
    assert state == 'canceled'


def terminal_event_states(root):
    terminal = []
    for event_path in sorted((root / 'events').glob('*.json')):
        state = decode_json(event_path.read_bytes())['operation']['state']
        if state in {'draft_ready', 'partial', 'canceled', 'failed'}:
            terminal.append(state)
    return terminal


def test_FS05b_cancel_after_first_member_fences_later_prepare_and_reconciles_attempt(tmp_path):
    items = (
        {
            'stable_id': 'ALPHA-1',
            'summary': 'First item',
            'status': 'Fixed',
            'assignee': {'key': 'dev-a', 'displayName': 'Alice'},
            'reporter': {'key': 'qa-b', 'displayName': 'Bob'},
            'comments': {
                '201': {'id': '201', 'body': 'Failure observed.', 'author': {'key': 'dev-a'}},
                '202': {'id': '202', 'body': 'Logs attached. Failure reproduced on build r7.'},
                '203': {'id': '203', 'body': 'Bob (qa-b), please rerun validation on build r8.'},
            },
        },
        {
            'stable_id': 'ALPHA-2',
            'summary': 'Second item',
            'status': 'Open',
            'assignee': {'key': 'dev-b', 'displayName': 'Bob'},
            'reporter': {'key': 'qa-b', 'displayName': 'Bob'},
            'comments': {
                '401': {'id': '401', 'body': 'Failure observed.', 'author': {'key': 'dev-b'}},
                '402': {'id': '402', 'body': 'Logs attached. Failure reproduced on build r7.'},
                '403': {'id': '403', 'body': 'Bob (qa-b), please rerun validation on build r8.'},
            },
        },
    )
    environment = ManualRunEnvironment(tmp_path / 'archive-root', items=items, policy=RunPolicy(max_analysis_items=2))
    operation = environment.run_service.submit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        environment.request(str(uuid.uuid4())),
    )

    def cancel_after_first_result():
        current = environment.run_service.get(environment.actor, environment.project.id, environment.stage.id, operation.operation_id)
        environment.run_service.cancel(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            operation.operation_id,
            expected_revision=current.revision,
        )

    environment.http.on_result = cancel_after_first_result

    completed = environment.worker.execute(environment.actor, environment.project.id, environment.stage.id, operation.operation_id)
    operation_root = (
        Path(tmp_path / 'archive-root')
        / 'projects'
        / environment.project.id
        / 'stages'
        / environment.stage.id
        / 'runtime'
        / 'operations'
        / operation.operation_id
    )

    assert completed.cancel_requested is True
    assert completed.state == 'canceled'
    assert terminal_event_states(operation_root) == ['canceled']
    assert [item.attempt_id is not None for item in completed.item_results] == [True, False]
    assert [request for request in environment.http.requests if request == ('POST', '/api/runs')] == [('POST', '/api/runs')]
    assert [request for request in environment.http.requests if request[1].endswith('/cancel')]


def test_FS05b_shared_cancel_window_does_not_renew_for_second_retained_attempt(tmp_path):
    items = (
        {
            'stable_id': 'ALPHA-1',
            'summary': 'First item',
            'status': 'Fixed',
            'assignee': {'key': 'dev-a', 'displayName': 'Alice'},
            'reporter': {'key': 'qa-b', 'displayName': 'Bob'},
            'comments': {
                '201': {'id': '201', 'body': 'Failure observed.', 'author': {'key': 'dev-a'}},
                '202': {'id': '202', 'body': 'Logs attached. Failure reproduced on build r7.'},
                '203': {'id': '203', 'body': 'Bob (qa-b), please rerun validation on build r8.'},
            },
        },
        {
            'stable_id': 'ALPHA-2',
            'summary': 'Second item',
            'status': 'Open',
            'assignee': {'key': 'dev-b', 'displayName': 'Bob'},
            'reporter': {'key': 'qa-b', 'displayName': 'Bob'},
            'comments': {
                '401': {'id': '401', 'body': 'Failure observed.', 'author': {'key': 'dev-b'}},
                '402': {'id': '402', 'body': 'Logs attached. Failure reproduced on build r7.'},
                '403': {'id': '403', 'body': 'Bob (qa-b), please rerun validation on build r8.'},
            },
        },
    )
    environment = ManualRunEnvironment(tmp_path / 'archive-root', items=items, policy=RunPolicy(max_analysis_items=2))
    operation = environment.run_service.submit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        environment.request(str(uuid.uuid4())),
    )
    environment.capture_service.capture(environment.run_service.capture_context(operation), cancel_requested=lambda: False)
    manifest = environment.archive.read_capture(environment.actor, environment.project.id, environment.stage.id, operation.capture_id)
    prepared = []
    item_results = []
    backend = environment.backend(environment.actor, environment.project.id, environment.stage.id)
    for identity in manifest.membership.items:
        source_key = environment.archive._source_key(manifest.intent, identity)
        attempt = environment.analysis_service.prepare(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            source_key,
            backend=backend,
            deadline_at=environment.run_service.operation_deadline(operation),
        ).attempt
        environment.archive.claim_analysis_dispatch(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            attempt.attempt_id,
        )
        prepared.append(attempt)
        item_results.append(ItemRunResult(content_hash(source_key), 'running', attempt.attempt_id, None, None))
    store = environment.archive.project_operation_repository(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        write=True,
    )
    capturing = replace(operation, state='capturing', revision=2)
    analyzing = replace(capturing, state='analyzing', revision=3, item_results=tuple(item_results))
    store.transition(capturing, expected_revision=operation.revision)
    store.transition(analyzing, expected_revision=capturing.revision)
    canceled = environment.run_service.cancel(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        operation.operation_id,
        expected_revision=analyzing.revision,
    )
    calls = []

    class FakeMonotonic:
        def __init__(self):
            self.value = 100.0

        def __call__(self):
            return self.value

    clock = FakeMonotonic()

    def transport(request):
        calls.append((request.method, request.url.path, request.url.params.get('clientRunKey')))
        clock.value = 111.0
        return httpx.Response(404, json={
            'contractVersion': 'task-run/1',
            'error': {'code': 'run_not_found', 'recovery': 'stop'},
        })

    def client(target):
        return TaskRunClient(
            base_url=target.base_url,
            source_app_id=target.source_app_id,
            run_store_id=target.run_store_id,
            credential_ref='synthetic-test',
            token='synthetic-only',
            transport=httpx.MockTransport(transport),
        )

    environment.analysis_service.client_factory = client
    worker = ProjectRunWorker(environment.run_service, monotonic=clock)

    completed = worker.execute(environment.actor, environment.project.id, environment.stage.id, operation.operation_id)
    operation_root = (
        Path(tmp_path / 'archive-root')
        / 'projects'
        / environment.project.id
        / 'stages'
        / environment.stage.id
        / 'runtime'
        / 'operations'
        / operation.operation_id
    )

    assert calls == [('GET', '/api/runs/by-client-key', prepared[0].attempt_id)]
    assert completed.state == 'partial'
    assert terminal_event_states(operation_root) == ['partial']
    assert completed.item_results[0].state == 'pending'
    assert completed.item_results[1].state == 'pending'
    assert completed.item_results[1].error_code == 'ANALYSIS_CANCELED'

from dataclasses import replace
from pathlib import Path
import uuid

import portalocker
import pytest

from project_management.app.api.capture_archive import ArchiveLimits
from project_management.app.api.project_runs import ItemRunResult, RunError, RunPolicy
from project_management.app.domain.capture_values import canonical_bytes, content_hash, decode_json
from project_management.tests.project_run_fixtures import ManualRunEnvironment


def test_FS06a_missing_state_replays_valid_event_tail_without_repairing_disk(tmp_path):
    environment = ManualRunEnvironment(tmp_path / 'archive-root')
    operation = environment.run_service.submit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        environment.request(str(uuid.uuid4())),
    )
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
    (operation_root / 'state.json').unlink()

    recovered = environment.run_service.get(environment.actor, environment.project.id, environment.stage.id, operation.operation_id)

    assert recovered == operation
    assert not (operation_root / 'state.json').exists()


def test_FS06a_stale_revision_cannot_transition_operation(tmp_path):
    environment = ManualRunEnvironment(tmp_path / 'archive-root')
    operation = environment.run_service.submit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        environment.request(str(uuid.uuid4())),
    )

    with pytest.raises(RunError) as error:
        environment.run_service.cancel(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            operation.operation_id,
            expected_revision=0,
        )

    assert error.value.code == 'RUN_REVISION_CONFLICT'
    assert environment.run_service.get(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        operation.operation_id,
    ).state == 'queued'


def test_FS06a_transition_quota_failure_leaves_no_partial_event_state_or_active_growth(tmp_path):
    environment = ManualRunEnvironment(tmp_path / 'archive-root')
    operation = environment.run_service.submit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        environment.request(str(uuid.uuid4())),
    )
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
    before = {path.relative_to(operation_root).as_posix(): path.read_bytes()
              for path in operation_root.rglob('*') if path.is_file()}
    environment.archive.config = replace(
        environment.archive.config,
        limits=ArchiveLimits(
            max_root_bytes=4096,
            max_root_files=10000,
            max_stage_bytes=4096,
            max_stage_files=5000,
            max_capture_bytes=4096,
            max_capture_files=1000,
            max_raw_page_bytes=1024 * 1024,
            max_object_bytes=2 * 1024 * 1024,
        ),
    )

    with pytest.raises(RunError) as error:
        environment.run_service.cancel(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            operation.operation_id,
            expected_revision=operation.revision,
        )

    after = {path.relative_to(operation_root).as_posix(): path.read_bytes()
             for path in operation_root.rglob('*') if path.is_file()}
    assert error.value.code == 'RUN_LIMIT'
    assert after == before


def test_FS06a_corrupted_backend_or_actor_identity_refuses_before_http(tmp_path):
    environment = ManualRunEnvironment(tmp_path / 'archive-root')
    operation = environment.run_service.submit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        environment.request(str(uuid.uuid4())),
    )
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
    request = decode_json((operation_root / 'request.json').read_bytes())
    request['backend']['run_store_id'] = 'tampered-store'
    request['admission_hash'] = content_hash({
        key: value for key, value in request.items()
        if key not in {'request_hash', 'admission_hash'}
    })
    (operation_root / 'request.json').write_bytes(canonical_bytes(request))

    with pytest.raises(RunError) as error:
        environment.worker.execute(environment.actor, environment.project.id, environment.stage.id, operation.operation_id)

    assert error.value.code == 'RUN_STORAGE_INVALID'
    assert environment.http.requests == []


def test_FS06a_hash_consistent_illegal_event_transition_refuses_before_http(tmp_path):
    environment = ManualRunEnvironment(tmp_path / 'archive-root')
    operation = environment.run_service.submit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        environment.request(str(uuid.uuid4())),
    )
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
    event_path = operation_root / 'events' / '00000001.json'
    event = decode_json(event_path.read_bytes())
    event['operation']['state'] = 'draft_ready'
    event_path.write_bytes(canonical_bytes(event))

    with pytest.raises(RunError) as error:
        environment.worker.execute(environment.actor, environment.project.id, environment.stage.id, operation.operation_id)

    assert error.value.code == 'RUN_STORAGE_INVALID'
    assert environment.http.requests == []


def test_FS06a_resume_validates_expected_revision_for_every_nonterminal_state(tmp_path):
    environment = ManualRunEnvironment(tmp_path / 'archive-root')
    operation = environment.run_service.submit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        environment.request(str(uuid.uuid4())),
    )

    with pytest.raises(RunError) as wrong_type:
        environment.run_service.resume(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            operation.operation_id,
            expected_revision=True,
        )
    with pytest.raises(RunError) as stale:
        environment.run_service.resume(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            operation.operation_id,
            expected_revision=operation.revision - 1,
        )

    assert (wrong_type.value.code, stale.value.code) == ('RUN_INVALID', 'RUN_REVISION_CONFLICT')


def test_FS06b_worker_reuses_complete_capture_after_lost_receipt_transition(tmp_path):
    environment = ManualRunEnvironment(tmp_path / 'archive-root')
    operation = environment.run_service.submit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        environment.request(str(uuid.uuid4())),
    )
    context = environment.run_service.capture_context(operation)
    receipt = environment.capture_service.capture(context, cancel_requested=lambda: False)
    assert receipt.complete is True
    before_provider_opens = environment.provider.open_count

    completed = environment.worker.execute(environment.actor, environment.project.id, environment.stage.id, operation.operation_id)

    assert completed.state == 'draft_ready'
    assert completed.capture_id == receipt.capture_id
    assert environment.provider.open_count == before_provider_opens
    assert completed.deadline_at == operation.deadline_at


def test_FS06e_resume_preserves_accepted_progress_and_processes_only_remaining_member(tmp_path):
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
    context = environment.run_service.capture_context(operation)
    environment.capture_service.capture(context, cancel_requested=lambda: False)
    manifest = environment.archive.read_capture(environment.actor, environment.project.id, environment.stage.id, operation.capture_id)
    hashes = [content_hash(environment.archive._source_key(manifest.intent, identity)) for identity in manifest.membership.items]
    store = environment.archive.project_operation_repository(environment.actor, environment.project.id, environment.stage.id, write=True)
    capturing = replace(operation, state='capturing', revision=2)
    analyzing = replace(
        capturing,
        state='analyzing',
        revision=3,
        item_results=(
            ItemRunResult(hashes[0], 'accepted', str(uuid.uuid4()), str(uuid.uuid4()), None),
            ItemRunResult(hashes[1], 'pending', None, None, None),
        ),
    )
    store.transition(capturing, expected_revision=operation.revision)
    store.transition(analyzing, expected_revision=capturing.revision)

    completed = environment.worker.execute(environment.actor, environment.project.id, environment.stage.id, operation.operation_id)

    assert completed.item_results[0] == analyzing.item_results[0]
    assert completed.item_results[1].attempt_id is not None
    assert [request[0] for request in environment.http.requests].count('POST') == 1


def test_FS06e_transition_refuses_clearing_bound_attempt_or_accepted_summary(tmp_path):
    environment = ManualRunEnvironment(tmp_path / 'archive-root')
    operation = environment.run_service.submit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        environment.request(str(uuid.uuid4())),
    )
    accepted = ItemRunResult('a' * 64, 'accepted', str(uuid.uuid4()), str(uuid.uuid4()), None)
    capturing = replace(operation, state='capturing', revision=2)
    current = replace(capturing, state='analyzing', revision=3, item_results=(accepted,))
    store = environment.archive.project_operation_repository(environment.actor, environment.project.id, environment.stage.id, write=True)
    store.transition(capturing, expected_revision=operation.revision)
    store.transition(current, expected_revision=capturing.revision)

    with pytest.raises(RunError) as error:
        store.transition(
            replace(current, revision=3, item_results=(ItemRunResult('a' * 64, 'pending', None, None, None),)),
            expected_revision=current.revision,
        )

    assert error.value.code == 'RUN_REVISION_CONFLICT'


def test_FS06e_terminal_transition_refuses_revision_growth_without_file_changes(tmp_path):
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
    before = {path.relative_to(operation_root).as_posix(): path.read_bytes()
              for path in operation_root.rglob('*') if path.is_file()}
    store = environment.archive.project_operation_repository(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        write=True,
    )

    with pytest.raises(RunError) as error:
        store.transition(replace(canceled, revision=canceled.revision + 1), expected_revision=canceled.revision)

    after = {path.relative_to(operation_root).as_posix(): path.read_bytes()
             for path in operation_root.rglob('*') if path.is_file()}
    assert error.value.code == 'RUN_REVISION_CONFLICT'
    assert after == before


def test_FS06c_nonblocking_execution_lock_prevents_second_worker_and_get_has_no_side_effect(tmp_path):
    environment = ManualRunEnvironment(tmp_path / 'archive-root')
    operation = environment.run_service.submit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        environment.request(str(uuid.uuid4())),
    )
    operations_root = (
        Path(tmp_path / 'archive-root')
        / 'projects'
        / environment.project.id
        / 'stages'
        / environment.stage.id
        / 'runtime'
        / 'operations'
    )
    before = sorted(path.relative_to(operations_root).as_posix() for path in operations_root.rglob('*')
                    if path.is_file() and path.name != 'execution.lock')
    with portalocker.Lock(operations_root / 'execution.lock', timeout=0, flags=portalocker.LOCK_EX | portalocker.LOCK_NB):
        with pytest.raises(RunError) as busy:
            environment.worker.execute(environment.actor, environment.project.id, environment.stage.id, operation.operation_id)
        inspected = environment.run_service.get(environment.actor, environment.project.id, environment.stage.id, operation.operation_id)
    after = sorted(path.relative_to(operations_root).as_posix() for path in operations_root.rglob('*')
                   if path.is_file() and path.name != 'execution.lock')

    assert busy.value.code == 'RUN_BUSY'
    assert inspected.state == 'queued'
    assert after == before


def test_FS06c_derived_selection_write_uses_operation_mutation_lock(tmp_path):
    environment = ManualRunEnvironment(tmp_path / 'archive-root')
    operation = environment.run_service.submit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        environment.request(str(uuid.uuid4())),
    )
    runtime = (
        Path(tmp_path / 'archive-root')
        / 'projects'
        / environment.project.id
        / 'stages'
        / environment.stage.id
        / 'runtime'
    )
    with portalocker.Lock(runtime / 'archive.lock', timeout=0, flags=portalocker.LOCK_EX | portalocker.LOCK_NB):
        with pytest.raises(RunError) as error:
            environment.run_service.write_draft_selection(
                environment.actor,
                environment.project.id,
                environment.stage.id,
                operation.operation_id,
                {'schema_version': 1, 'payload_hash': 'a' * 64},
            )

    assert error.value.code == 'RUN_BUSY'

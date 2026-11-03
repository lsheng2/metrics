from dataclasses import replace
from pathlib import Path
import uuid

import pytest

from project_management.app.api.capture_archive import ArchiveLimits
from project_management.app.api.project_runs import RunError, RunPolicy
from project_management.tests.project_run_fixtures import ManualRunEnvironment


def test_FS01_same_command_replays_original_request_without_new_backend_or_capture(tmp_path):
    environment = ManualRunEnvironment(tmp_path / 'archive-root', policy=RunPolicy(timeout_seconds=5))
    command_id = str(uuid.uuid4())
    request = environment.request(command_id)

    first = environment.run_service.submit(environment.actor, environment.project.id, environment.stage.id, request)
    environment.clock.advance(60)
    second = environment.run_service.submit(environment.actor, environment.project.id, environment.stage.id, request)

    assert (first.operation_id, first.capture_id, first.deadline_at, first.state) == (
        second.operation_id,
        second.capture_id,
        second.deadline_at,
        'queued',
    )
    assert first.deadline_at.endswith('.123Z')
    assert environment.backend_calls == 1
    assert environment.provider.open_count == 0


def test_FS01_conflicting_payload_and_foreign_owner_have_no_capture_or_backend_side_effects(tmp_path):
    environment = ManualRunEnvironment(tmp_path / 'archive-root')
    request = environment.request(str(uuid.uuid4()))
    environment.run_service.submit(environment.actor, environment.project.id, environment.stage.id, request)

    with pytest.raises(RunError) as conflict:
        environment.run_service.submit(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            replace(request, timezone='UTC'),
        )
    with pytest.raises(RunError) as foreign:
        environment.run_service.get(
            type(environment.actor)('other-owner'),
            environment.project.id,
            environment.stage.id,
            str(uuid.uuid5(uuid.UUID(environment.stage.id), f'run:{request.command_id}')),
        )

    assert (conflict.value.code, foreign.value.code, environment.backend_calls, environment.provider.open_count) == (
        'RUN_COMMAND_CONFLICT',
        'RUN_NOT_FOUND',
        1,
        0,
    )


def test_FS01_new_offline_submit_refuses_without_initializing_archive(tmp_path):
    root = tmp_path / 'archive-root'
    environment = ManualRunEnvironment(root, notifier=None)

    with pytest.raises(RunError) as error:
        environment.run_service.submit(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            environment.request(str(uuid.uuid4())),
        )

    assert error.value.code == 'RUN_UNAVAILABLE'
    assert not (root / 'archive-root.json').exists()
    assert not (root / 'projects').exists()


def test_FS01_exact_submit_replay_precedes_runtime_readiness_and_archived_write_checks(tmp_path):
    environment = ManualRunEnvironment(tmp_path / 'archive-root')
    request = environment.request(str(uuid.uuid4()))
    accepted = environment.run_service.submit(environment.actor, environment.project.id, environment.stage.id, request)
    offline = ManualRunEnvironment(tmp_path / 'archive-root', notifier=None)
    offline.project = environment.project
    offline.stage = replace(environment.stage, source_status='unavailable')
    offline.project_api.project = replace(environment.project, archived=True)
    offline.project_api.stage = offline.stage
    offline.archive.project_api.project = offline.project_api.project
    offline.archive.project_api.stage = offline.stage

    replay = offline.run_service.submit(offline.actor, environment.project.id, environment.stage.id, request)

    assert replay == accepted


def test_FS01_quota_refusal_does_not_leave_request_event_state_or_active_files(tmp_path):
    limits = ArchiveLimits(
        max_root_bytes=64 * 1024 * 1024,
        max_root_files=10000,
        max_stage_bytes=32 * 1024 * 1024,
        max_stage_files=5000,
        max_capture_bytes=1024,
        max_capture_files=2,
        max_raw_page_bytes=1024 * 1024,
        max_object_bytes=2 * 1024 * 1024,
    )
    environment = ManualRunEnvironment(tmp_path / 'archive-root', limits=limits)

    with pytest.raises(RunError) as error:
        environment.run_service.submit(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            environment.request(str(uuid.uuid4())),
        )

    operations = (
        tmp_path / 'archive-root' / 'projects' / environment.project.id / 'stages' / environment.stage.id
        / 'runtime' / 'operations'
    )
    assert error.value.code == 'RUN_LIMIT'
    assert not any(operations.rglob('request.json')) if operations.exists() else True


def test_FS02_actual_capture_analysis_and_report_services_create_unfinalized_draft(tmp_path):
    environment = ManualRunEnvironment(tmp_path / 'archive-root')
    operation = environment.run_service.submit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        environment.request(str(uuid.uuid4())),
    )

    completed = environment.worker.execute(environment.actor, environment.project.id, environment.stage.id, operation.operation_id)

    assert completed.state == 'draft_ready'
    assert completed.draft_revision == 1
    assert completed.draft_id is not None
    assert completed.draft_revision_hash is not None
    assert completed.snapshot_hash is not None
    assert completed.template_hash is not None
    assert completed.item_results[0].state == 'accepted'
    assert environment.http.requests == [('POST', '/api/runs'), ('GET', '/api/runs/run-fixture/result')]
    archive_root = Path(tmp_path / 'archive-root' / 'projects' / environment.project.id / 'stages' / environment.stage.id)
    assert (archive_root / 'runtime' / 'operations' / operation.operation_id / 'draft-selection.json').exists()
    assert not tuple((archive_root / 'archive').glob('report_publications/*/manifest.json'))


def test_FS03_second_unchanged_capture_reuses_original_summary_without_another_sdk_post(tmp_path):
    environment = ManualRunEnvironment(tmp_path / 'archive-root')
    first = environment.run_service.submit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        environment.request(str(uuid.uuid4())),
    )
    completed_first = environment.worker.execute(environment.actor, environment.project.id, environment.stage.id, first.operation_id)
    second = environment.run_service.submit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        environment.request(str(uuid.uuid4())),
    )

    completed_second = environment.worker.execute(environment.actor, environment.project.id, environment.stage.id, second.operation_id)

    assert (completed_first.state, completed_second.state) == ('draft_ready', 'draft_ready')
    assert completed_second.item_results[0].state == 'no_work'
    assert completed_second.item_results[0].accepted_summary_id == completed_first.item_results[0].accepted_summary_id
    assert environment.http.requests == [('POST', '/api/runs'), ('GET', '/api/runs/run-fixture/result')]


def test_FS04_analysis_limit_retains_whole_population_as_explicit_pending(tmp_path):
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
            'comments': {'301': {'id': '301', 'body': 'Waiting for owner.'}},
        },
    )
    environment = ManualRunEnvironment(
        tmp_path / 'archive-root',
        items=items,
        policy=RunPolicy(max_analysis_items=1),
    )
    operation = environment.run_service.submit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        environment.request(str(uuid.uuid4())),
    )

    completed = environment.worker.execute(environment.actor, environment.project.id, environment.stage.id, operation.operation_id)

    assert completed.state == 'partial'
    assert [item.state for item in completed.item_results] == ['accepted', 'pending']
    assert completed.item_results[1].error_code == 'ANALYSIS_INPUT_LIMIT'
    assert completed.draft_id is not None


def test_FS04_unknown_exposure_stops_later_member_dispatch(tmp_path):
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
    environment = ManualRunEnvironment(
        tmp_path / 'archive-root',
        items=items,
        policy=RunPolicy(max_observations_per_attempt=1),
    )
    environment.http.force_running = True
    operation = environment.run_service.submit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        environment.request(str(uuid.uuid4())),
    )

    completed = environment.worker.execute(environment.actor, environment.project.id, environment.stage.id, operation.operation_id)

    assert completed.state == 'partial'
    assert [item.attempt_id is not None for item in completed.item_results] == [True, False]
    assert [request[0] for request in environment.http.requests].count('POST') == 1

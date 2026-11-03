from dataclasses import replace
import importlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import threading
import time
import uuid

import httpx
import portalocker
import pytest
from django.test import override_settings

from project_management.app.api.project_runs import RunError, RunPolicy
from project_management.app.domain.summary_contracts import AiBackendTarget
from project_management.tests.project_run_fixtures import ManualRunEnvironment
from project_management.tests.report_draft_fixtures import (
    DraftArchive,
    FixedClock,
    StaticSourceReader,
    draft_command,
    draft_note,
    draft_selection,
)
from project_management.tests.report_render_fixtures import daily_template
from project_management.app.api import reports as report_api


def runtime_module():
    spec = importlib.util.find_spec('project_management.runtime')
    assert spec is not None, 'HOST runtime registry module must exist'
    return importlib.import_module('project_management.runtime')


def discovery_module():
    spec = importlib.util.find_spec('project_management.storage.project_operation_discovery')
    assert spec is not None, 'HOST operation discovery module must exist'
    return importlib.import_module('project_management.storage.project_operation_discovery')


class BlockingWorker:
    def __init__(self, delegate):
        self.delegate = delegate
        self.started = threading.Event()
        self.release = threading.Event()
        self.count = 0

    def execute(self, actor, project_id, stage_id, operation_id):
        self.count += 1
        self.started.set()
        assert self.release.wait(5)
        return self.delegate.execute(actor, project_id, stage_id, operation_id)


class FailingOnceWorker:
    def __init__(self, delegate):
        self.delegate = delegate
        self.count = 0
        self.failed = threading.Event()

    def execute(self, actor, project_id, stage_id, operation_id):
        self.count += 1
        if self.count == 1:
            self.failed.set()
            raise RuntimeError('worker boom')
        return self.delegate.execute(actor, project_id, stage_id, operation_id)


def wait_until(assertion, timeout=15):
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            return assertion()
        except AssertionError as error:
            last_error = error
            time.sleep(0.02)
    if last_error is not None:
        raise last_error
    raise AssertionError('condition was not reached')


def wait_for_state(environment, operation_id, state):
    def check():
        operation = environment.run_service.get(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            operation_id,
        )
        assert operation.state == state
        return operation

    return wait_until(check)


def operation_root(root, environment, operation_id):
    return (
        Path(root)
        / 'projects'
        / environment.project.id
        / 'stages'
        / environment.stage.id
        / 'runtime'
        / 'operations'
        / operation_id
    )


def test_get_runtime_does_not_build_worker_or_enable_offline_submit(tmp_path):
    module = runtime_module()
    registered = module.get_project_runtime()
    if registered is not None:
        module.clear_project_runtime(registered)
    environment = ManualRunEnvironment(tmp_path / 'archive-root', notifier=None)

    with pytest.raises(RunError) as error:
        environment.run_service.submit(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            environment.request(str(uuid.uuid4())),
        )

    assert module.get_project_runtime() is None
    assert error.value.code == 'RUN_UNAVAILABLE'
    assert environment.provider.open_count == 0
    assert environment.http.requests == []
    assert not (tmp_path / 'archive-root' / 'projects').exists()


def test_runtime_start_is_idempotent_and_coalesces_active_duplicate_notify(tmp_path):
    module = runtime_module()
    environment = ManualRunEnvironment(tmp_path / 'archive-root', notifier=None)
    worker = BlockingWorker(environment.worker)
    runtime = module.ProjectRunRuntime(environment.run_service, worker)
    runtime.start()
    runtime.start()
    try:
        operation = environment.run_service.submit(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            environment.request(str(uuid.uuid4())),
        )
        assert worker.started.wait(5)
        runtime.notify(environment.actor, environment.project.id, environment.stage.id, operation.operation_id)
        worker.release.set()

        completed = wait_for_state(environment, operation.operation_id, 'draft_ready')

        assert completed.state == 'draft_ready'
        assert worker.count == 1
    finally:
        worker.release.set()
        runtime.stop(5)


def test_runtime_stop_reports_unresolved_active_operation_until_worker_exits(tmp_path):
    module = runtime_module()
    environment = ManualRunEnvironment(tmp_path / 'archive-root', notifier=None)
    worker = BlockingWorker(environment.worker)
    runtime = module.ProjectRunRuntime(environment.run_service, worker)
    runtime.start()
    try:
        operation = environment.run_service.submit(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            environment.request(str(uuid.uuid4())),
        )
        assert worker.started.wait(5)

        stopped = runtime.stop(0.01)
        worker.release.set()
        drained = runtime.stop(5)

        assert stopped.stopped is False
        assert stopped.active_operation_id == operation.operation_id
        assert operation.operation_id in stopped.unresolved
        assert drained.stopped is True
    finally:
        worker.release.set()
        runtime.stop(5)


def test_runtime_stop_detaches_notifier_so_later_submit_has_no_growth(tmp_path):
    module = runtime_module()
    environment = ManualRunEnvironment(tmp_path / 'archive-root', notifier=None)
    runtime = module.ProjectRunRuntime(environment.run_service, environment.worker)
    runtime.start()
    runtime.stop(5)
    operations = tmp_path / 'archive-root' / 'projects' / environment.project.id / 'stages' / environment.stage.id / 'runtime' / 'operations'
    before = tuple(operations.rglob('request.json')) if operations.exists() else ()

    with pytest.raises(RunError) as error:
        environment.run_service.submit(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            environment.request(str(uuid.uuid4())),
        )

    after = tuple(operations.rglob('request.json')) if operations.exists() else ()
    assert error.value.code == 'RUN_UNAVAILABLE'
    assert after == before


def test_runtime_stop_reports_cancel_failure_unresolved_even_when_worker_exits(tmp_path):
    module = runtime_module()
    environment = ManualRunEnvironment(tmp_path / 'archive-root', notifier=None)
    worker = BlockingWorker(environment.worker)
    runtime = module.ProjectRunRuntime(environment.run_service, worker)
    runtime.start()
    operation = environment.run_service.submit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        environment.request(str(uuid.uuid4())),
    )
    assert worker.started.wait(5)
    stage_lock = tmp_path / 'archive-root' / 'projects' / environment.project.id / 'stages' / environment.stage.id / 'runtime' / 'archive.lock'
    with portalocker.Lock(stage_lock, timeout=0, flags=portalocker.LOCK_EX | portalocker.LOCK_NB):
        worker.release.set()
        stopped = runtime.stop(5)

    assert stopped.stopped is True
    assert operation.operation_id in stopped.unresolved


def test_worker_exception_fails_operation_and_later_queue_still_runs(tmp_path):
    module = runtime_module()
    environment = ManualRunEnvironment(tmp_path / 'archive-root', notifier=None)
    worker = FailingOnceWorker(environment.worker)
    runtime = module.ProjectRunRuntime(environment.run_service, worker)
    runtime.start()
    try:
        first = environment.run_service.submit(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            environment.request(str(uuid.uuid4())),
        )
        failed = wait_for_state(environment, first.operation_id, 'failed')
        assert failed.state == 'failed'
        assert failed.error_code == 'RUN_INTERRUPTED'
        wait_until(lambda: (assert_runtime_idle(runtime)))

        second = environment.run_service.submit(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            environment.request(str(uuid.uuid4())),
        )
        completed = wait_for_state(environment, second.operation_id, 'draft_ready')

        assert completed.state == 'draft_ready'
        assert worker.count >= 2
    finally:
        runtime.stop(5)


def assert_runtime_idle(runtime):
    assert runtime._active is None
    return True


def test_startup_reconcile_interrupts_only_unlocked_running_operations(tmp_path):
    environment = ManualRunEnvironment(tmp_path / 'archive-root')
    operation = environment.run_service.submit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        environment.request(str(uuid.uuid4())),
    )
    store = environment.archive.project_operation_repository(
        environment.actor, environment.project.id, environment.stage.id, write=True,
    )
    capturing = store.transition(replace(operation, state='capturing', revision=2), expected_revision=1)

    changed = environment.run_service.reconcile_interrupted()

    assert changed == (operation.operation_id,)
    assert environment.run_service.get(
        environment.actor, environment.project.id, environment.stage.id, operation.operation_id,
    ).state == 'interrupted'
    assert environment.provider.open_count == 0
    assert environment.http.requests == []

    locked = ManualRunEnvironment(tmp_path / 'locked-root')
    locked_operation = locked.run_service.submit(
        locked.actor, locked.project.id, locked.stage.id, locked.request(str(uuid.uuid4())),
    )
    locked_store = locked.archive.project_operation_repository(
        locked.actor, locked.project.id, locked.stage.id, write=True,
    )
    locked_store.transition(replace(locked_operation, state='capturing', revision=2), expected_revision=1)
    operations = operation_root(tmp_path / 'locked-root', locked, locked_operation.operation_id).parent
    with portalocker.Lock(operations / 'execution.lock', timeout=0, flags=portalocker.LOCK_EX | portalocker.LOCK_NB):
        assert locked.run_service.reconcile_interrupted() == ()
    assert locked.run_service.get(
        locked.actor, locked.project.id, locked.stage.id, locked_operation.operation_id,
    ).state == 'capturing'
    assert capturing.state == 'capturing'


def test_startup_reconcile_repairs_request_only_candidate_without_interrupted_claim(tmp_path):
    environment = ManualRunEnvironment(tmp_path / 'archive-root')
    operation = environment.run_service.submit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        environment.request(str(uuid.uuid4())),
    )
    root = operation_root(tmp_path / 'archive-root', environment, operation.operation_id)
    for path in (root / 'events').glob('*.json'):
        path.unlink()
    (root / 'state.json').unlink()
    active = root.parent / 'active.json'
    if active.exists():
        active.unlink()

    changed = environment.run_service.reconcile_interrupted()
    repaired = environment.run_service.get(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        operation.operation_id,
    )

    assert changed == ()
    assert repaired.state == 'queued'
    assert repaired.operation_id == operation.operation_id
    assert environment.provider.open_count == 0
    assert environment.http.requests == []


def test_startup_reconcile_request_only_repair_skips_only_execution_lock_contention(tmp_path):
    environment = ManualRunEnvironment(tmp_path / 'archive-root')
    operation = environment.run_service.submit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        environment.request(str(uuid.uuid4())),
    )
    root = operation_root(tmp_path / 'archive-root', environment, operation.operation_id)
    for path in (root / 'events').glob('*.json'):
        path.unlink()
    (root / 'state.json').unlink()
    operations = root.parent

    with portalocker.Lock(operations / 'execution.lock', timeout=0, flags=portalocker.LOCK_EX | portalocker.LOCK_NB):
        changed = environment.run_service.reconcile_interrupted()

    assert changed == ()
    assert not tuple((root / 'events').glob('*.json'))


def test_operation_discovery_is_bounded_and_validates_candidate_hash(tmp_path):
    discovery = discovery_module()
    environment = ManualRunEnvironment(tmp_path / 'archive-root')
    operation = environment.run_service.submit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        environment.request(str(uuid.uuid4())),
    )
    locations = discovery.list_operation_locations(tmp_path / 'archive-root')
    candidate = discovery.read_operation_recovery_candidate(
        tmp_path / 'archive-root',
        locations[0],
        environment.archive.config.limits,
    )
    extra = operation_root(tmp_path / 'archive-root', environment, str(uuid.uuid4()))
    extra.mkdir()
    request = operation_root(tmp_path / 'archive-root', environment, operation.operation_id) / 'request.json'
    payload = request.read_text(encoding='utf-8').replace('"actor_subject":"archive-owner"', '"actor_subject":"other-owner"')
    request.write_text(payload, encoding='utf-8')

    with pytest.raises(RunError) as overflow:
        discovery.list_operation_locations(tmp_path / 'archive-root', limit=1)
    with pytest.raises(RunError) as invalid:
        discovery.read_operation_recovery_candidate(
            tmp_path / 'archive-root',
            locations[0],
            environment.archive.config.limits,
        )

    assert len(locations) == 1
    assert candidate.location.operation_id == operation.operation_id
    assert candidate.actor_subject == environment.actor.subject
    assert candidate.has_initial_event is True
    assert overflow.value.code == 'RUN_LIMIT'
    assert invalid.value.code == 'RUN_STORAGE_INVALID'


def test_operation_discovery_uses_root_lock_and_shared_scan_cap(tmp_path):
    discovery = discovery_module()
    environment = ManualRunEnvironment(tmp_path / 'archive-root')
    environment.run_service.submit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        environment.request(str(uuid.uuid4())),
    )
    with pytest.raises(RunError) as overflow:
        discovery.list_operation_locations(tmp_path / 'archive-root', limit=2)

    root_lock = tmp_path / 'archive-root' / 'budget.lock'
    with portalocker.Lock(root_lock, timeout=0, flags=portalocker.LOCK_EX | portalocker.LOCK_NB):
        with pytest.raises(RunError) as busy:
            discovery.list_operation_locations(tmp_path / 'archive-root')

    assert overflow.value.code == 'RUN_LIMIT'
    assert busy.value.code == 'RUN_BUSY'


def test_rendering_older_revision_after_later_finalization_stays_draft(tmp_path):
    archive = DraftArchive(tmp_path / 'draft-archive')
    service = report_api.ReportDraftService(
        archive,
        StaticSourceReader(rule_hash=archive.stage.definition_hash),
        report_api.ReportRenderer(),
        clock=FixedClock(),
    )
    draft = service.create(
        archive.actor,
        archive.project.id,
        archive.stage.id,
        command_id=draft_command(700),
        selection=draft_selection(),
        template=daily_template(),
    )
    saved = service.save(
        archive.actor,
        archive.project.id,
        archive.stage.id,
        draft.draft_id,
        command_id=draft_command(701),
        expected_revision=1,
        edits=(draft_note(702),),
        template=daily_template(),
    )
    service.finalize_and_commit(
        archive.actor,
        archive.project.id,
        archive.stage.id,
        draft.draft_id,
        command_id=draft_command(703),
        expected_revision=saved.revision,
    )

    old_revision = service.render(
        archive.actor,
        archive.project.id,
        archive.stage.id,
        draft.draft_id,
        revision=1,
    )
    finalized_revision = service.render(
        archive.actor,
        archive.project.id,
        archive.stage.id,
        draft.draft_id,
        revision=saved.revision,
    )

    assert f'Edition: draft draft {draft.draft_id} rev 1' in old_revision.plain_text
    assert f'Edition: final draft {draft.draft_id} rev {saved.revision}' in finalized_revision.plain_text


def test_read_service_builds_with_invalid_ai_target_without_provider_or_sdk(monkeypatch, tmp_path):
    factories = importlib.import_module('project_management.app.api.run_factories')
    monkeypatch.setattr(factories, 'TaskRunClient', lambda **kwargs: (_ for _ in ()).throw(AssertionError('no sdk')))
    with override_settings(METRICS_PROJECT_ARCHIVE_ROOT=str(tmp_path / 'archive-root'),
                           METRICS_PROJECT_ARCHIVE_AUTHOR_NAME='Archive Test',
                           METRICS_PROJECT_ARCHIVE_AUTHOR_EMAIL='archive@example.test',
                           METRICS_PROJECT_AI_TARGET='invalid-live-target'):
        service = factories.build_run_read_service()

    assert service.notifier is None
    with pytest.raises(RunError) as error:
        service.backend_resolver(None, str(uuid.uuid4()), str(uuid.uuid4()))
    assert error.value.code == 'RUN_UNAVAILABLE'


def test_ordinary_enabled_settings_fail_closed_without_fixture_factory(monkeypatch, tmp_path):
    factories = importlib.import_module('project_management.app.api.run_factories')
    monkeypatch.setattr(factories, 'build_capture_archive_service',
                        lambda **kwargs: (_ for _ in ()).throw(AssertionError('no archive')))
    with override_settings(
        METRICS_PROJECT_RUN_ENABLED=True,
        METRICS_PROJECT_RUNTIME_FACTORY=None,
        METRICS_PROJECT_ARCHIVE_ROOT=str(tmp_path / 'archive-root'),
        METRICS_PROJECT_ARCHIVE_AUTHOR_NAME='Archive Test',
        METRICS_PROJECT_ARCHIVE_AUTHOR_EMAIL='archive@example.test',
        METRICS_PROJECT_AI_TARGET={
            'execution_mode': 'synthetic',
            'base_url': 'http://127.0.0.1:48300',
            'source_app_id': 'metrics-dashboard',
            'run_store_id': 'store',
            'grant_revision': 'grant',
            'limit_policy_revision': 'limits',
        },
    ):
        with pytest.raises(RunError) as error:
            factories.build_project_runtime()

    assert error.value.code == 'RUN_UNAVAILABLE'


def test_task_run_client_factory_uses_safe_transport_constructor_only(tmp_path):
    factories = importlib.import_module('project_management.app.api.run_factories')
    settings = SimpleNamespace(METRICS_PROJECT_AI_CREDENTIAL_REF='synthetic', METRICS_PROJECT_AI_TOKEN='token')
    factory = factories._client_factory_from_settings(settings)
    backend = AiBackendTarget(
        'http://127.0.0.1:1',
        'metrics-dashboard',
        'store',
        'projects.p.stages.s',
        'grant',
        'limits',
    )

    client = factory(backend)

    assert client is not None

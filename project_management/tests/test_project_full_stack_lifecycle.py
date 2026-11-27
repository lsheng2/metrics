from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
from types import SimpleNamespace
import uuid

import pytest

from scripts.service_lifecycle_engine import ProcessExitObservation, ServiceLifecycleEngine, ServiceSpec, StopResult
from scripts.validation import project_full_stack
from scripts.validation.project_full_stack_identity import (
    create_launch,
    current_launch_for_service,
    normal_stop_evidence,
    validate_model_connection,
    validate_process_proof,
    wait_valid_model_connection,
    write_exit_receipt,
)
from scripts.validation.project_full_stack_support import base_environment, ensure_data_root, initialize_run_dir, read_json, write_json


def test_should_stop_project_services_with_qualification_grace_without_forcing(tmp_path, monkeypatch):
    run_dir, engine, platform = running_owned_services(tmp_path, graceful_after=10.0)
    monkeypatch.setattr(project_full_stack, 'lifecycle', lambda run_dir_value: engine)
    append_worker_stop(engine.read_state()[project_full_stack.APP_NAME], stopped=True)

    result = project_full_stack.stop(SimpleNamespace(run_dir=run_dir))

    assert result['normal'] is True
    assert platform.terminate_calls == []
    assert platform.kill_calls == []
    assert platform.wait_timeouts[0] == project_full_stack.SAFE_STOP_SECONDS


def test_should_classify_forced_project_stop_as_abnormal(tmp_path, monkeypatch):
    run_dir, engine, platform = running_owned_services(tmp_path, graceful_after=None)
    monkeypatch.setattr(project_full_stack, 'lifecycle', lambda run_dir_value: engine)
    append_worker_stop(engine.read_state()[project_full_stack.APP_NAME], stopped=True)

    result = project_full_stack.stop(SimpleNamespace(run_dir=run_dir))

    assert result['normal'] is False
    assert platform.terminate_calls
    assert platform.kill_calls


def test_should_start_sle_service_with_allowlisted_inherited_environment(tmp_path, monkeypatch):
    engine = ServiceLifecycleEngine('project', tmp_path, state_directory=tmp_path / 'state',
                                    platform_ops=FakePlatform(graceful_after=1.0))
    spec = ServiceSpec.from_values('project-app', [8100], ['python', '-m', 'server', '--port', '{port}'],
                                   env={'DJANGO_SETTINGS_MODULE': 'synthetic'})
    monkeypatch.setenv('METRICS_JIRA_API_TOKEN', 'CANARY_TOKEN')
    monkeypatch.setenv('OPENAI_API_KEY', 'CANARY_MODEL')

    receipt = project_full_stack.start_sanitized(engine, spec, tmp_path / 'env')

    env = engine.platform_ops.captured_envs[0]
    assert receipt['service'] == 'project-app'
    assert 'METRICS_JIRA_API_TOKEN' not in env
    assert 'OPENAI_API_KEY' not in env
    assert env['DJANGO_SETTINGS_MODULE'] == 'synthetic'
    assert any(key.upper() == 'PATH' for key in env)
    assert os.environ['METRICS_JIRA_API_TOKEN'] == 'CANARY_TOKEN'


def test_should_restart_only_app_and_preserve_closed_logs(tmp_path, monkeypatch):
    run_dir, engine, platform = running_owned_services(tmp_path, graceful_after=1.0)
    monkeypatch.setattr(project_full_stack, 'lifecycle', lambda run_dir_value: engine)
    app_state = engine.read_state()[project_full_stack.APP_NAME]

    result = project_full_stack.restart_app(SimpleNamespace(run_dir=run_dir))

    assert result['status'] == 'running'
    assert platform.stop_commands == [tuple(app_state['stop_command'])]
    assert platform.started_names.count('project-app') == 2
    assert platform.started_names.count(project_full_stack.MODEL_NAME) == 1
    assert any((run_dir / 'evidence' / 'restart').glob('*/closed-app.out.log'))


def test_should_wait_for_current_launch_connection_publication(tmp_path, monkeypatch):
    run_dir, engine, platform = running_owned_services(tmp_path, graceful_after=1.0)
    state = engine.read_state()[project_full_stack.MODEL_NAME]
    launch = current_launch_for_service(run_dir, state, project_full_stack.MODEL_NAME)
    launch.connection_file.unlink()
    connection = model_connection(state['pid'], launch)
    opened = threading.Event()
    release = threading.Event()
    publisher_errors = []
    original_open = Path.open
    original_exists = Path.exists

    def hold_unfinished_publication(path, mode='r', *args, **kwargs):
        # Let the reader inspect visibility while the real writer is unfinished.
        stream = original_open(path, mode, *args, **kwargs)
        if (threading.current_thread() is timer and mode in {'w', 'x'}
                and path.parent == launch.directory
                and path.name.startswith(launch.connection_file.name)):
            opened.set()
            if not release.wait(timeout=2.0):
                stream.close()
                raise AssertionError('Connection publication barrier was not released.')
        return stream

    def observe_publication(path):
        exists = original_exists(path)
        if path == launch.connection_file and opened.is_set() and not exists:
            release.set()
        return exists

    def publish():
        try:
            write_json(launch.connection_file, connection, replace=True)
        except BaseException as error:
            publisher_errors.append(error)

    timer = threading.Timer(0.1, publish)
    monkeypatch.setattr(Path, 'open', hold_unfinished_publication)
    monkeypatch.setattr(Path, 'exists', observe_publication)
    timer.start()
    try:
        observed = wait_valid_model_connection(run_dir, launch, state, read_json(run_dir / 'runtime-manifest.json'),
                                               platform_ops=engine.platform_ops, seconds=2.0)
    finally:
        release.set()
        timer.cancel()
        timer.join(timeout=2.0)
        assert not timer.is_alive()
        if publisher_errors:
            raise publisher_errors[0]

    assert opened.is_set()
    assert observed['launch_id'] == launch.launch_id


@pytest.mark.parametrize('mutation', ['malformed', 'wrong_identity'])
def test_should_reject_invalid_published_connection_without_retry(tmp_path, monkeypatch, mutation):
    run_dir, engine, platform = running_owned_services(tmp_path, graceful_after=1.0)
    state = engine.read_state()[project_full_stack.MODEL_NAME]
    launch = current_launch_for_service(run_dir, state, project_full_stack.MODEL_NAME)
    if mutation == 'malformed':
        launch.connection_file.write_text('{', encoding='utf-8')
        expected_error = json.JSONDecodeError
    else:
        connection = model_connection(state['pid'], launch)
        connection['launch_id'] = 'another-launch'
        write_json(launch.connection_file, connection, replace=True)
        expected_error = ValueError

    def unexpected_retry(_seconds):
        raise AssertionError('Invalid published connection must not be retried.')

    monkeypatch.setattr('scripts.validation.project_full_stack_identity.time.sleep', unexpected_retry)
    with pytest.raises(expected_error):
        wait_valid_model_connection(run_dir, launch, state, read_json(run_dir / 'runtime-manifest.json'),
                                    platform_ops=engine.platform_ops, seconds=2.0)
    assert not (launch.directory / 'process-proof.json').exists()


def test_should_reject_wrong_connection_identity(tmp_path):
    run_dir, engine, platform = running_owned_services(tmp_path, graceful_after=1.0)
    state = engine.read_state()[project_full_stack.MODEL_NAME]
    launch = current_launch_for_service(run_dir, state, project_full_stack.MODEL_NAME)
    connection = model_connection(state['pid'], launch)
    connection['base_url'] = 'http://127.0.0.1:49999/v1'

    with pytest.raises(ValueError):
        validate_model_connection(connection, launch, state, read_json(run_dir / 'runtime-manifest.json'),
                                  platform_ops=engine.platform_ops)


@pytest.mark.parametrize('mutation', [
    'runStoreId', 'grantRevision', 'sourceAppId', 'limitPolicyRevision',
    'execution_mode', 'missing_with_extra', 'not_object',
])
def test_model_connection_rejects_noncanonical_fields_before_process_proof(tmp_path, mutation):
    run_dir, engine, _ = running_owned_services(tmp_path, graceful_after=1.0)
    state = engine.read_state()[project_full_stack.MODEL_NAME]
    launch = current_launch_for_service(run_dir, state, project_full_stack.MODEL_NAME)
    connection = model_connection(state['pid'], launch)
    if mutation == 'not_object':
        connection = list(connection)
    elif mutation == 'missing_with_extra':
        connection.pop('api_key')
        connection['grantRevision'] = 'retired'
    else:
        connection[mutation] = 'retired'

    with pytest.raises(ValueError):
        validate_model_connection(
            connection, launch, state, read_json(run_dir / 'runtime-manifest.json'),
            platform_ops=engine.platform_ops,
        )
    assert not (launch.directory / 'process-proof.json').exists()


def test_should_cleanup_only_services_started_by_failed_start_invocation(tmp_path, monkeypatch):
    run_dir = prepared_run_without_services(tmp_path)
    platform = FakePlatform(graceful_after=1.0)
    engine = ServiceLifecycleEngine(project_full_stack.PROJECT_NAME, run_dir,
                                    instance_name=project_full_stack.INSTANCE,
                                    state_directory=run_dir / 'lifecycle',
                                    log_directory=run_dir / 'logs',
                                    platform_ops=platform)
    monkeypatch.setattr(project_full_stack, 'lifecycle', lambda run_dir_value: engine)
    monkeypatch.setattr(project_full_stack, 'wait_valid_model_connection', lambda *args, **kwargs: (_ for _ in ()).throw(ValueError('bad connection')))

    result = project_full_stack.main(['start', '--run-dir', str(run_dir), '--lifetime-seconds', '1800'])

    assert result == 1
    assert platform.started_names == [project_full_stack.MODEL_NAME]
    assert platform.stop_commands


def test_should_reject_stale_worker_event_before_stop_offset(tmp_path):
    run_dir, engine, platform = running_owned_services(tmp_path, graceful_after=1.0)
    state = engine.read_state()[project_full_stack.APP_NAME]
    launch = current_launch_for_service(run_dir, state, project_full_stack.APP_NAME)
    validate_process_proof(launch, state, platform_ops=engine.platform_ops)
    append_worker_stop(state, stopped=True)
    offset = Path(state['stdout_log']).stat().st_size
    write_exit_receipt(launch.exit_file, service=project_full_stack.APP_NAME, launch_id=launch.launch_id,
                       pid=state['pid'], exit_code=0)

    with pytest.raises(ValueError):
        normal_stop_evidence(launch, state, stop_result(state), stdout_start=offset, require_worker_event=True)


def test_should_reject_nonzero_exit_receipt(tmp_path):
    run_dir, engine, platform = running_owned_services(tmp_path, graceful_after=1.0)
    state = engine.read_state()[project_full_stack.APP_NAME]
    launch = current_launch_for_service(run_dir, state, project_full_stack.APP_NAME)
    validate_process_proof(launch, state, platform_ops=engine.platform_ops)
    offset = Path(state['stdout_log']).stat().st_size
    append_worker_stop(state, stopped=True)
    write_exit_receipt(launch.exit_file, service=project_full_stack.APP_NAME, launch_id=launch.launch_id,
                       pid=state['pid'], exit_code=7)

    with pytest.raises(ValueError):
        normal_stop_evidence(launch, state, stop_result(state), stdout_start=offset, require_worker_event=True)


def test_should_refuse_restart_after_nonzero_app_exit_receipt(tmp_path, monkeypatch):
    run_dir, engine, platform = running_owned_services(tmp_path, graceful_after=1.0)
    platform.exit_code_by_service[project_full_stack.APP_NAME] = 7
    monkeypatch.setattr(project_full_stack, 'lifecycle', lambda run_dir_value: engine)

    with pytest.raises(ValueError):
        project_full_stack.restart_app(SimpleNamespace(run_dir=run_dir))

    assert platform.started_names.count(project_full_stack.APP_NAME) == 1


def test_should_accept_null_listener_with_valid_worker_process_proof(tmp_path, monkeypatch):
    run_dir, engine, platform = running_owned_services(tmp_path, graceful_after=1.0)
    state = dict(engine.read_state()[project_full_stack.MODEL_NAME])
    launch = current_launch_for_service(run_dir, state, project_full_stack.MODEL_NAME)
    state['provenance'] = {**dict(state['provenance']), 'listener_pid': None, 'capability': 'registered_process'}
    connection = model_connection(95564, launch)
    calls = []

    def matches(worker_pid, process):
        calls.append((worker_pid, process.pid, process.args))
        return worker_pid == 95564 and process.pid == state['pid'] and tuple(process.args) == tuple(state['command'])

    monkeypatch.setattr('scripts.validation.project_full_stack_identity.worker_matches_process', matches)

    validate_model_connection(connection, launch, state, read_json(run_dir / 'runtime-manifest.json'), platform_ops=engine.platform_ops)

    proof = read_json(launch.directory / 'process-proof.json')
    assert proof['worker_pid'] == 95564
    assert proof['relation'] == 'worker_child'
    assert calls


def test_should_reject_worker_process_with_wrong_parent_or_command(tmp_path, monkeypatch):
    run_dir, engine, platform = running_owned_services(tmp_path, graceful_after=1.0)
    state = dict(engine.read_state()[project_full_stack.MODEL_NAME])
    launch = current_launch_for_service(run_dir, state, project_full_stack.MODEL_NAME)
    state['provenance'] = {**dict(state['provenance']), 'listener_pid': None, 'capability': 'registered_process'}
    connection = model_connection(95564, launch)
    monkeypatch.setattr('scripts.validation.project_full_stack_identity.worker_matches_process', lambda worker_pid, process: False)

    with pytest.raises(ValueError):
        validate_model_connection(connection, launch, state, read_json(run_dir / 'runtime-manifest.json'), platform_ops=engine.platform_ops)


def test_should_match_worker_exit_receipt_against_process_proof(tmp_path, monkeypatch):
    run_dir, engine, platform = running_owned_services(tmp_path, graceful_after=1.0)
    state = dict(engine.read_state()[project_full_stack.MODEL_NAME])
    launch = current_launch_for_service(run_dir, state, project_full_stack.MODEL_NAME)
    monkeypatch.setattr('scripts.validation.project_full_stack_identity.worker_matches_process',
                        lambda worker_pid, process: worker_pid == 95564)
    validate_process_proof(launch, state, platform_ops=engine.platform_ops, worker_pid=95564)
    write_exit_receipt(launch.exit_file, service=project_full_stack.MODEL_NAME, launch_id=launch.launch_id,
                       pid=95564, exit_code=0)

    evidence = normal_stop_evidence(launch, state, StopResult(project_full_stack.MODEL_NAME, state['port'], state['pid'], True, False, 'stop_command'))

    assert evidence['process_proof']['worker_pid'] == 95564


def test_should_reject_manifest_vector_route_mismatch(tmp_path):
    run_dir = prepared_run_without_services(tmp_path)
    manifest_payload = read_json(run_dir / 'runtime-manifest.json')
    manifest_payload['routes']['project_stage_reports'] = '/projects/wrong/stages/wrong/reports/'
    write_json(run_dir / 'runtime-manifest.json', manifest_payload, replace=True)

    with pytest.raises(ValueError):
        project_full_stack.status_result(run_dir, next_action='stop')


def running_owned_services(tmp_path, *, graceful_after):
    run_dir = prepared_run_without_services(tmp_path)
    platform = FakePlatform(graceful_after=graceful_after)
    engine = ServiceLifecycleEngine(project_full_stack.PROJECT_NAME, run_dir,
                                    instance_name=project_full_stack.INSTANCE,
                                    state_directory=run_dir / 'lifecycle',
                                    log_directory=run_dir / 'logs',
                                    platform_ops=platform)
    model_launch = create_launch(run_dir, project_full_stack.MODEL_NAME, connection=True)
    app_launch = create_launch(run_dir, project_full_stack.APP_NAME)
    engine.start_service(project_full_stack.model_spec(run_dir, 1800, model_launch), port=48600)
    model_state = engine.read_state()[project_full_stack.MODEL_NAME]
    connection = model_connection(model_state['pid'], model_launch)
    write_json(model_launch.connection_file, connection)
    write_json(run_dir / 'model' / 'connection.json', connection)
    engine.start_service(project_full_stack.app_spec(run_dir, 1800, app_launch, 8127, connection), port=8127)
    return run_dir, engine, platform


def prepared_run_without_services(tmp_path):
    data_root = tmp_path / 'data'
    ensure_data_root(data_root)
    run_dir = data_root / str(uuid.uuid4())
    run_dir.mkdir(parents=True)
    initialize_run_dir(run_dir, data_root)
    write_json(run_dir / 'fixture-vector.json', {'schema_version': 1})
    write_json(run_dir / 'runtime-manifest.json', manifest(run_dir))
    return run_dir


def manifest(run_dir: Path):
    project_id = str(uuid.uuid4())
    stage_id = str(uuid.uuid4())
    return {
        'schema_version': 2,
        'run_dir': str(run_dir),
        'repository': str(Path.cwd()),
        'app_python': sys.executable,
        'catalog': {
            'project_id': project_id,
            'stage_id': stage_id,
            'scope_key': f'projects.{project_id}.stages.{stage_id}',
            'fixture_vector_sha256': hashlib.sha256((run_dir / 'fixture-vector.json').read_bytes()).hexdigest(),
        },
        'routes': {'project_stage_reports': f'/projects/{project_id}/stages/{stage_id}/reports/'},
        'lifetime_seconds': 1800,
    }


def test_should_import_app_command_under_isolated_python_without_server(tmp_path):
    data_root = ensure_data_root(tmp_path / 'data')
    run_dir = data_root / str(uuid.uuid4())
    run_dir.mkdir()
    initialize_run_dir(run_dir, data_root)
    write_json(run_dir / 'fixture-vector.json', {'schema_version': 1})
    write_json(run_dir / 'runtime-manifest.json', manifest(run_dir))
    launch = create_launch(run_dir, project_full_stack.APP_NAME)
    environment = base_environment(tmp_path / 'env')
    environment['METRICS_PROJECT_FULL_STACK_RUN_DIR'] = str(run_dir)
    command = [
        sys.executable,
        '-I',
        str(Path.cwd() / 'scripts' / 'validation' / 'project_full_stack_app_entry.py'),
        '--qualify-launch-id',
        launch.launch_id,
        '--qualify-exit-file',
        str(launch.exit_file),
        'check',
        '--settings',
        'scripts.validation.project_full_stack_settings',
    ]

    result = subprocess.run(command, cwd=Path.cwd(), env=environment, capture_output=True, text=True, timeout=30)

    assert result.returncode == 0, result.stdout + result.stderr


def model_connection(pid, launch):
    return {
        'schema_version': 1,
        'qualification': 'loopback_openai_compatible',
        'pid': pid,
        'base_url': 'http://127.0.0.1:48600/v1',
        'model': 'scripted',
        'api_key': 'not-printed',
        'stop_file': str(launch.stop_file),
        'launch_id': launch.launch_id,
        'exit_file': str(launch.exit_file),
    }


def append_worker_stop(app_state, *, stopped):
    with Path(app_state['stdout_log']).open('ab') as stream:
        stream.write(json.dumps({
            'schema_version': 1,
            'event': 'project_runtime_stopped',
            'stopped': stopped,
            'active_operation_id': None,
            'unresolved': [],
        }, separators=(',', ':')).encode('utf-8') + b'\n')


class FakeProcess:
    def __init__(self, pid):
        self.pid = pid

    def poll(self):
        return None


class FakePlatform:
    def __init__(self, *, graceful_after):
        self.processes = {}
        self.commands = {}
        self.service_by_pid = {}
        self.stdout_by_pid = {}
        self.exit_code_by_pid = {}
        self.ports = {}
        self.next_pid = 1000
        self.graceful_after = graceful_after
        self.graceful_requested = set()
        self.terminated = set()
        self.killed = set()
        self.terminate_calls = []
        self.kill_calls = []
        self.stop_commands = []
        self.started_names = []
        self.exit_code_by_service = {}
        self.captured_envs = []
        self.wait_timeouts = []
        self.process_group_id = lambda pid: pid
        self.process_command_line = lambda pid: ' '.join(self.commands.get(pid, ()))
        self.process_start_marker = lambda pid: f'marker-{pid}'
        self.http_status_ok = lambda url: True
        self.http_probe = lambda url: {'body_sha256': 'identity'}
        self.wait_port_available = lambda host, port, timeout: True
        self.creation_flags = lambda: 0

    def owned_listener_pids(self, host, port, wrapper_pid):
        return ()

    def start_process(self, command, cwd, env, stdout, stderr, creationflags):
        self.next_pid += 1
        pid = self.next_pid
        self.processes[pid] = True
        self.commands[pid] = tuple(command)
        self.captured_envs.append(dict(env))
        name = self.service_name(command)
        self.service_by_pid[pid] = name
        self.stdout_by_pid[pid] = Path(stdout.name)
        self.started_names.append(name)
        port = int(command[command.index('--port') + 1]) if '--port' in command else int(command[-1])
        self.ports[port] = pid
        return FakeProcess(pid)

    def is_port_available(self, host, port):
        pid = self.ports.get(int(port))
        return not (pid and self.processes.get(pid))

    def process_exists(self, pid):
        return bool(self.processes.get(int(pid)))

    def process_matches_command(self, pid, command):
        return tuple(command) == self.commands.get(int(pid))

    def get_listening_process_ids(self, host, port):
        pid = self.ports.get(int(port))
        return (pid,) if pid and self.processes.get(pid) else ()

    def run_command(self, command, cwd):
        self.stop_commands.append(tuple(command))
        stop_file = self.stop_file_from_command(command)
        target_service = None
        if stop_file is not None:
            target_service = json.loads((stop_file.parent / 'launch.json').read_text(encoding='utf-8'))['service']
        for pid, running in self.processes.items():
            if running and (target_service is None or self.service_by_pid.get(pid) == target_service):
                self.graceful_requested.add(pid)
                launch = json.loads((stop_file.parent / 'launch.json').read_text(encoding='utf-8')) if stop_file else None
                if launch:
                    self.exit_code_by_pid[pid] = self.exit_code_by_service.get(launch['service'], 0)
                    write_exit_receipt(Path(launch['exit_file']), service=launch['service'], launch_id=launch['launch_id'],
                                       pid=pid, exit_code=self.exit_code_by_pid[pid])
                if self.service_by_pid.get(pid) == project_full_stack.APP_NAME:
                    append_worker_stop({'stdout_log': str(self.stdout_by_pid[pid])}, stopped=True)

    def observe_process_exit(self, pid):
        @contextmanager
        def observation():
            pid_value = int(pid)
            yield ProcessExitObservation(
                lambda: self.exit_code_by_pid.get(pid_value) if not self.processes.get(pid_value) else None,
                lambda timeout: self.wait_process_exit(pid_value, timeout),
            )

        return observation()

    def terminate_process(self, pid):
        self.terminate_calls.append(int(pid))
        self.terminated.add(int(pid))

    def kill_process(self, pid):
        self.kill_calls.append(int(pid))
        self.killed.add(int(pid))

    def wait_process_exit(self, pid, timeout):
        self.wait_timeouts.append(timeout)
        pid = int(pid)
        if pid in self.graceful_requested and self.graceful_after is not None and timeout >= self.graceful_after:
            self.processes[pid] = False
            return True
        if pid in self.killed:
            self.processes[pid] = False
            return True
        return not self.processes.get(pid)

    def service_name(self, command):
        text = ' '.join(str(part) for part in command)
        if 'project_model_fixture.py' in text:
            return project_full_stack.MODEL_NAME
        return project_full_stack.APP_NAME

    def stop_file_from_command(self, command):
        text = ' '.join(str(part) for part in command)
        match = re.search(r"Path\('([^']+)'\)\.touch", text)
        return Path(match.group(1)) if match else None


def stop_result(state):
    return StopResult(project_full_stack.APP_NAME, state['port'], state['pid'], True, False, 'stop_command')

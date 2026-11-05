from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
from types import SimpleNamespace
import uuid

import pytest

from scripts.service_lifecycle_engine import ServiceLifecycleEngine, ServiceSpec, StopResult
from scripts.validation import project_full_stack
from scripts.validation.project_full_stack_base import prepare_store_directory
from scripts.validation.project_full_stack_identity import (
    create_launch,
    current_launch_for_service,
    normal_stop_evidence,
    validate_connection,
    validate_process_proof,
    wait_valid_connection,
    write_exit_receipt,
)
from scripts.validation.project_full_stack_support import base_environment, ensure_data_root, initialize_run_dir, read_json, write_json
from scripts.validation.project_summary_support import WHEEL_SHA, child_environment, verify_base_source


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
    base_state = engine.read_state()[project_full_stack.BASE_NAME]

    result = project_full_stack.restart_app(SimpleNamespace(run_dir=run_dir))

    assert result['status'] == 'running'
    assert platform.stop_commands == [tuple(app_state['stop_command'])]
    assert platform.started_names.count('project-app') == 2
    assert platform.started_names.count('ai-base') == 1
    assert any((run_dir / 'evidence' / 'restart').glob('*/closed-app.out.log'))


def test_should_wait_for_current_launch_connection_publication(tmp_path):
    run_dir, engine, platform = running_owned_services(tmp_path, graceful_after=1.0)
    state = engine.read_state()[project_full_stack.BASE_NAME]
    launch = current_launch_for_service(run_dir, state, project_full_stack.BASE_NAME)
    launch.connection_file.unlink()
    connection = base_connection(state['pid'], launch)

    def publish():
        write_json(launch.connection_file, connection)

    timer = threading.Timer(0.1, publish)
    timer.start()
    try:
        observed = wait_valid_connection(run_dir, launch, state, read_json(run_dir / 'runtime-manifest.json'),
                                         platform_ops=engine.platform_ops, seconds=2.0)
    finally:
        timer.cancel()

    assert observed['launchId'] == launch.launch_id


def test_should_reject_wrong_connection_identity(tmp_path):
    run_dir, engine, platform = running_owned_services(tmp_path, graceful_after=1.0)
    state = engine.read_state()[project_full_stack.BASE_NAME]
    launch = current_launch_for_service(run_dir, state, project_full_stack.BASE_NAME)
    connection = base_connection(state['pid'], launch)
    connection['baseUrl'] = 'http://127.0.0.1:49999'

    with pytest.raises(ValueError):
        validate_connection(connection, launch, state, read_json(run_dir / 'runtime-manifest.json'),
                            platform_ops=engine.platform_ops)


def test_should_cleanup_only_services_started_by_failed_start_invocation(tmp_path, monkeypatch):
    run_dir = prepared_run_without_services(tmp_path)
    platform = FakePlatform(graceful_after=1.0)
    engine = ServiceLifecycleEngine(project_full_stack.PROJECT_NAME, run_dir,
                                    instance_name=project_full_stack.INSTANCE,
                                    state_directory=run_dir / 'lifecycle',
                                    log_directory=run_dir / 'logs',
                                    platform_ops=platform)
    monkeypatch.setattr(project_full_stack, 'lifecycle', lambda run_dir_value: engine)
    monkeypatch.setattr(project_full_stack, 'wait_valid_connection', lambda *args, **kwargs: (_ for _ in ()).throw(ValueError('bad connection')))

    result = project_full_stack.main(['start', '--run-dir', str(run_dir), '--lifetime-seconds', '1800'])

    assert result == 1
    assert platform.started_names == ['ai-base']
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


def test_should_accept_null_listener_with_valid_w5_worker_process_proof(tmp_path, monkeypatch):
    run_dir, engine, platform = running_owned_services(tmp_path, graceful_after=1.0)
    state = dict(engine.read_state()[project_full_stack.BASE_NAME])
    launch = current_launch_for_service(run_dir, state, project_full_stack.BASE_NAME)
    state['provenance'] = {**dict(state['provenance']), 'listener_pid': None, 'capability': 'registered_process'}
    connection = base_connection(95564, launch)
    calls = []

    def matches(worker_pid, process):
        calls.append((worker_pid, process.pid, process.args))
        return worker_pid == 95564 and process.pid == state['pid'] and tuple(process.args) == tuple(state['command'])

    monkeypatch.setattr('scripts.validation.project_full_stack_identity.worker_matches_process', matches)

    validate_connection(connection, launch, state, read_json(run_dir / 'runtime-manifest.json'), platform_ops=engine.platform_ops)

    proof = read_json(launch.directory / 'process-proof.json')
    assert proof['worker_pid'] == 95564
    assert proof['relation'] == 'w5_worker_child'
    assert calls


def test_should_reject_worker_process_with_wrong_parent_or_command(tmp_path, monkeypatch):
    run_dir, engine, platform = running_owned_services(tmp_path, graceful_after=1.0)
    state = dict(engine.read_state()[project_full_stack.BASE_NAME])
    launch = current_launch_for_service(run_dir, state, project_full_stack.BASE_NAME)
    state['provenance'] = {**dict(state['provenance']), 'listener_pid': None, 'capability': 'registered_process'}
    connection = base_connection(95564, launch)
    monkeypatch.setattr('scripts.validation.project_full_stack_identity.worker_matches_process', lambda worker_pid, process: False)

    with pytest.raises(ValueError):
        validate_connection(connection, launch, state, read_json(run_dir / 'runtime-manifest.json'), platform_ops=engine.platform_ops)


def test_should_match_worker_exit_receipt_against_process_proof(tmp_path, monkeypatch):
    run_dir, engine, platform = running_owned_services(tmp_path, graceful_after=1.0)
    state = dict(engine.read_state()[project_full_stack.BASE_NAME])
    launch = current_launch_for_service(run_dir, state, project_full_stack.BASE_NAME)
    monkeypatch.setattr('scripts.validation.project_full_stack_identity.worker_matches_process',
                        lambda worker_pid, process: worker_pid == 95564)
    validate_process_proof(launch, state, platform_ops=engine.platform_ops, worker_pid=95564)
    write_exit_receipt(launch.exit_file, service=project_full_stack.BASE_NAME, launch_id=launch.launch_id,
                       pid=95564, exit_code=0)

    evidence = normal_stop_evidence(launch, state, StopResult(project_full_stack.BASE_NAME, state['port'], state['pid'], True, False, 'stop_command'))

    assert evidence['process_proof']['worker_pid'] == 95564


def test_should_reject_manifest_vector_route_mismatch(tmp_path):
    run_dir = prepared_run_without_services(tmp_path)
    manifest_payload = read_json(run_dir / 'runtime-manifest.json')
    manifest_payload['routes']['project_stage_reports'] = '/projects/wrong/stages/wrong/reports/'
    write_json(run_dir / 'runtime-manifest.json', manifest_payload, replace=True)

    with pytest.raises(ValueError):
        project_full_stack.status_result(run_dir, next_action='stop')


def test_should_prepare_new_owned_base_store(tmp_path):
    run_dir = prepared_run_without_services(tmp_path)
    launch = create_launch(run_dir, project_full_stack.BASE_NAME, connection=True)

    directory = prepare_store_directory(store_args(run_dir, launch))

    assert directory == run_dir / 'base' / 'store'
    assert (run_dir / 'base' / 'store-owner.json').exists()
    assert (launch.directory / 'store-proof.json').exists()


def test_should_reopen_known_existing_owned_base_store_without_deleting_content(tmp_path):
    run_dir = prepared_run_without_services(tmp_path)
    launch1 = create_launch(run_dir, project_full_stack.BASE_NAME, connection=True)
    directory = prepare_store_directory(store_args(run_dir, launch1))
    sentinel = directory / 'sentinel.txt'
    sentinel.write_text('keep', encoding='utf-8')
    launch2 = create_launch(run_dir, project_full_stack.BASE_NAME, connection=True)

    reopened = prepare_store_directory(store_args(run_dir, launch2))

    assert reopened == directory
    assert sentinel.read_text(encoding='utf-8') == 'keep'
    assert read_json(launch2.directory / 'store-proof.json')['store_existed'] is True


def test_should_reject_unowned_base_store_path(tmp_path):
    run_dir = prepared_run_without_services(tmp_path)
    launch = create_launch(run_dir, project_full_stack.BASE_NAME, connection=True)
    args = store_args(run_dir, launch)
    args.data_dir = tmp_path / 'other-store'

    with pytest.raises(ValueError):
        prepare_store_directory(args)


def test_should_repeat_base_factory_without_server_and_retain_store(tmp_path):
    base_python = Path.cwd().parent / 'Report_creater_agent' / '.venv' / 'Scripts' / 'python.exe'
    work = Path.cwd() / '.tmp' / 'task-run-w5-clean-merged-20261103'
    if not work.is_dir():
        pytest.skip('approved clean W5 work root is not available yet')
    source = work / 'base-source'
    verify_base_source(work, source)
    run_dir = prepared_run_without_services(tmp_path)
    launch = create_launch(run_dir, project_full_stack.BASE_NAME, connection=True)
    store = prepare_store_directory(store_args(run_dir, launch))
    script = base_repeat_script()
    env_root = tmp_path / 'base-env'
    env_root.mkdir()
    environment = child_environment(env_root)
    try:
        result = subprocess.run([
            str(base_python), '-I', '-B', '-X', f'pycache_prefix={tmp_path / "base-pycache"}', '-c', script,
            str(store), str(source / 'services' / 'app-service'), str(work / 'artifacts' / 'contract-pack'),
            'projects.p.stages.s',
        ], cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=40)
    finally:
        verify_base_source(work, source)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload['same_store'] is True
    assert payload['sentinel'] == 'keep'


def running_owned_services(tmp_path, *, graceful_after):
    run_dir = prepared_run_without_services(tmp_path)
    platform = FakePlatform(graceful_after=graceful_after)
    engine = ServiceLifecycleEngine(project_full_stack.PROJECT_NAME, run_dir,
                                    instance_name=project_full_stack.INSTANCE,
                                    state_directory=run_dir / 'lifecycle',
                                    log_directory=run_dir / 'logs',
                                    platform_ops=platform)
    base_launch = create_launch(run_dir, project_full_stack.BASE_NAME, connection=True)
    app_launch = create_launch(run_dir, project_full_stack.APP_NAME)
    engine.start_service(project_full_stack.base_spec(run_dir, 1800, base_launch), port=48600)
    engine.start_service(project_full_stack.app_spec(run_dir, 1800, app_launch, 8127), port=8127)
    base_state = engine.read_state()[project_full_stack.BASE_NAME]
    connection = base_connection(base_state['pid'], base_launch)
    write_json(base_launch.connection_file, connection)
    write_json(run_dir / 'base' / 'connection.json', connection)
    return run_dir, engine, platform


def prepared_run_without_services(tmp_path, *, work=None):
    data_root = tmp_path / 'data'
    ensure_data_root(data_root)
    run_dir = data_root / str(uuid.uuid4())
    run_dir.mkdir(parents=True)
    initialize_run_dir(run_dir, data_root)
    write_json(run_dir / 'fixture-vector.json', {'schema_version': 1})
    write_json(run_dir / 'runtime-manifest.json', manifest(run_dir, work=work))
    return run_dir


def store_args(run_dir, launch):
    return SimpleNamespace(
        data_dir=run_dir / 'base' / 'store',
        connection_file=launch.connection_file,
        launch_id=launch.launch_id,
    )


def base_repeat_script():
    return r"""
import json, sys
import socket
from dataclasses import replace
from pathlib import Path
store = Path(sys.argv[1])
source = Path(sys.argv[2])
pack = Path(sys.argv[3])
scope = sys.argv[4]
def deny(*args, **kwargs):
    raise RuntimeError('external connections are forbidden')
socket.socket.connect = deny
socket.socket.connect_ex = deny
socket.create_connection = deny
sys.path.insert(0, str(source))
manifest = json.loads((pack / 'manifest.json').read_text(encoding='utf-8'))
profile_path = manifest['profiles']['project-reporting.summary@review-1']['profile']
profile = json.loads((pack / profile_path).read_text(encoding='utf-8'))
candidate = __import__('app.task_run_candidate', fromlist=['create_task_run_candidate'])
registration = __import__('app.services.app_chat_registration', fromlist=['BUILTIN_APP_REGISTRATIONS', 'AppAuthPolicy'])
class Backend:
    execution_mode = 'synthetic'
    backend_id = 'repeat-check'
    async def execute(self, compiled):
        raise RuntimeError('not dispatched')
def make():
    return candidate.create_task_run_candidate(
        data_directory=store,
        registrations={'metrics-dashboard': replace(
            registration.BUILTIN_APP_REGISTRATIONS['metrics-dashboard'],
            auth=registration.AppAuthPolicy('service_account', 'synthetic-integration'))},
        credential_secrets={'synthetic-integration': 'secret'},
        profiles=[profile],
        grants=[{'sourceAppId': 'metrics-dashboard', 'scopeKey': scope, 'enabled': True,
                 'grantRevision': 'dashboard-join-1',
                 'allowedProfiles': [{'key': profile['key'], 'revision': profile['revision']}]}],
        backend=Backend(),
    )
first = make()
store_id = first.state.task_run_service.run_store_id
(store / 'sentinel.txt').write_text('keep', encoding='utf-8')
second = make()
print(json.dumps({'same_store': second.state.task_run_service.run_store_id == store_id,
                  'sentinel': (store / 'sentinel.txt').read_text(encoding='utf-8')}))
"""


def manifest(run_dir: Path, *, work=None):
    work = work or Path.cwd() / '.tmp' / 'task-run-w5-clean-merged-20261103'
    pack_root = work / 'artifacts' / 'contract-pack'
    project_id = str(uuid.uuid4())
    stage_id = str(uuid.uuid4())
    return {
        'schema_version': 1,
        'execution_mode': 'synthetic',
        'run_dir': str(run_dir),
        'repository': str(Path.cwd()),
        'base_source': str(work / 'base-source'),
        'base_python': str((Path.cwd().parent / 'Report_creater_agent' / '.venv' / 'Scripts' / 'python.exe')),
        'pack_root': str(pack_root),
        'app_python': sys.executable,
        'sdk_wheel_sha256': WHEEL_SHA,
        'contract_pack_manifest_sha256': hashlib.sha256((pack_root / 'manifest.json').read_bytes()).hexdigest(),
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


def base_connection(pid, launch):
    return {
        'executionMode': 'synthetic',
        'qualification': 'synthetic_only',
        'contractVersion': 'task-run/1',
        'packVersion': '0.1.0a2',
        'pid': pid,
        'scopeKey': read_json(launch.directory.parents[2] / 'runtime-manifest.json')['catalog']['scope_key'],
        'sourceAppId': 'metrics-dashboard',
        'credentialRef': 'synthetic-integration',
        'token': 'not-printed',
        'baseUrl': 'http://127.0.0.1:48600',
        'runStoreId': 'store-1',
        'grantRevision': 'dashboard-join-1',
        'limitPolicyRevision': 'base-b-cancel-synthetic-1',
        'stopFile': str(launch.stop_file),
        'packRoot': read_json(launch.directory.parents[2] / 'runtime-manifest.json')['pack_root'],
        'launchId': launch.launch_id,
        'exitFile': str(launch.exit_file),
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
                    write_exit_receipt(Path(launch['exit_file']), service=launch['service'], launch_id=launch['launch_id'],
                                       pid=pid, exit_code=self.exit_code_by_service.get(launch['service'], 0))
                if self.service_by_pid.get(pid) == project_full_stack.APP_NAME:
                    append_worker_stop({'stdout_log': str(self.stdout_by_pid[pid])}, stopped=True)

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
        if 'project_full_stack_base.py' in text:
            return project_full_stack.BASE_NAME
        return project_full_stack.APP_NAME

    def stop_file_from_command(self, command):
        text = ' '.join(str(part) for part in command)
        match = re.search(r"Path\('([^']+)'\)\.touch", text)
        return Path(match.group(1)) if match else None


def stop_result(state):
    return StopResult(project_full_stack.APP_NAME, state['port'], state['pid'], True, False, 'stop_command')

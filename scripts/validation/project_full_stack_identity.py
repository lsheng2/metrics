from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import importlib
import time
import uuid
from urllib.parse import urlsplit

from scripts.service_lifecycle_engine import StopResult
from scripts.service_lifecycle_engine.provenance import command_fingerprint
from scripts.validation.project_full_stack_support import digest_file, json_lines, read_json, safe_url, write_json
from scripts.validation.project_summary_support import worker_matches_process
from scripts.validation.project_summary_support import (
    owned_work_root, sdk_selection, sdk_selection_digest, verify_base_source, verify_installed_sdk,
)


APP_ID = 'metrics-dashboard'
CREDENTIAL_REF = 'synthetic-integration'
CONTRACT_VERSION = 'task-run/1'
PACK_VERSION = '0.1.0a2'
GRANT_REVISION = 'dashboard-join-1'
LIMIT_REVISION = 'base-b-cancel-synthetic-1'


@dataclass(frozen=True, slots=True)
class LaunchDescriptor:
    service: str
    launch_id: str
    directory: Path
    stop_file: Path
    exit_file: Path
    connection_file: Path | None


class ProcessReference:
    def __init__(self, pid: int, command: tuple[str, ...], platform_ops):
        self.pid = int(pid)
        self.args = tuple(command)
        self.platform_ops = platform_ops

    def poll(self):
        return None if self.platform_ops.process_exists(self.pid) else 1


def create_launch(run_dir: Path, service: str, *, connection=False) -> LaunchDescriptor:
    launch_id = str(uuid.uuid4())
    directory = run_dir / 'lifecycle' / 'launches' / launch_id
    descriptor = LaunchDescriptor(
        service=service,
        launch_id=launch_id,
        directory=directory,
        stop_file=directory / 'stop.handle',
        exit_file=directory / 'exit.json',
        connection_file=(directory / 'connection.json') if connection else None,
    )
    write_json(directory / 'launch.json', launch_payload(run_dir, descriptor))
    return descriptor


def launch_payload(run_dir: Path, descriptor: LaunchDescriptor) -> dict:
    return {
        'schema_version': 1,
        'run_uuid': run_dir.name,
        'service': descriptor.service,
        'launch_id': descriptor.launch_id,
        'stop_file': str(descriptor.stop_file),
        'exit_file': str(descriptor.exit_file),
        'connection_file': str(descriptor.connection_file) if descriptor.connection_file else None,
    }


def load_launch(path: Path) -> LaunchDescriptor:
    payload = read_json(path)
    descriptor = LaunchDescriptor(
        service=payload['service'],
        launch_id=payload['launch_id'],
        directory=path.parent,
        stop_file=Path(payload['stop_file']).resolve(strict=False),
        exit_file=Path(payload['exit_file']).resolve(strict=False),
        connection_file=Path(payload['connection_file']).resolve(strict=False) if payload.get('connection_file') else None,
    )
    if read_json(path) != launch_payload(path.parents[3], descriptor):
        raise ValueError('Launch descriptor identity is invalid.')
    return descriptor


def current_launch_for_service(run_dir: Path, service_state: dict, service: str) -> LaunchDescriptor:
    stop_command = tuple(str(part) for part in service_state.get('stop_command', ()))
    stop_command_text = ' '.join(stop_command)
    command_text = ' '.join(str(part) for part in service_state.get('command', ()))
    for path in sorted((run_dir / 'lifecycle' / 'launches').glob('*/launch.json')):
        descriptor = load_launch(path)
        if descriptor.service == service and (descriptor.launch_id in command_text or str(descriptor.stop_file) in stop_command_text):
            return descriptor
    raise ValueError('Current service launch descriptor was not found.')


def write_exit_receipt(path: Path, *, service: str, launch_id: str, pid: int, exit_code: int) -> None:
    from datetime import UTC, datetime

    write_json(path, {
        'schema_version': 1,
        'service': service,
        'launch_id': launch_id,
        'pid': pid,
        'exit_code': exit_code,
        'finished_at': datetime.now(UTC).isoformat(),
    }, replace=path.exists())


def validate_manifest(run_dir: Path, manifest: dict, *, root: Path, default_base_python: Path, app_python: Path, allowed_work_roots=()) -> None:
    work = work_root_for_manifest(manifest, root, allowed_work_roots)
    if manifest.get('schema_version') != 1 or manifest.get('execution_mode') != 'synthetic':
        raise ValueError('Runtime manifest schema is invalid.')
    expected_paths = {
        'repository': root.resolve(),
        'run_dir': run_dir.resolve(),
        'base_source': work / 'base-source',
        'pack_root': work / 'artifacts' / 'contract-pack',
    }
    for key, expected in expected_paths.items():
        if Path(manifest[key]).resolve(strict=True) != expected:
            raise ValueError(f'Runtime manifest {key} is not trusted.')
    if Path(manifest['base_python']).resolve(strict=True) != default_base_python.resolve(strict=True):
        raise ValueError('Runtime manifest Base interpreter is not trusted.')
    if Path(manifest['app_python']).resolve(strict=True) != app_python.resolve(strict=True):
        raise ValueError('Runtime manifest app interpreter is not trusted.')
    selection = sdk_selection(work)
    if (manifest.get('sdk_version', '0.1.0a2') != selection['sdk_version']
            or manifest.get('sdk_selection_sha256') != sdk_selection_digest(work)):
        raise ValueError('Runtime manifest SDK identity mismatch.')
    verify_base_source(work, Path(manifest['base_source']).resolve(strict=True))
    sdk = importlib.import_module('ai_base_application_sdk')
    if verify_installed_sdk(work, sdk) != manifest.get('sdk_wheel_sha256'):
        raise ValueError('Runtime manifest SDK identity mismatch.')
    if digest_file(Path(manifest['pack_root']) / 'manifest.json') != manifest.get('contract_pack_manifest_sha256'):
        raise ValueError('Runtime manifest contract pack identity mismatch.')
    if selection.get('contract_pack_manifest_sha256', manifest['contract_pack_manifest_sha256']) != manifest['contract_pack_manifest_sha256']:
        raise ValueError('Selected SDK contract pack identity mismatch.')
    if digest_file(run_dir / 'fixture-vector.json') != manifest['catalog'].get('fixture_vector_sha256'):
        raise ValueError('Runtime manifest vector identity mismatch.')
    from scripts.validation.project_week_scenarios import validate_scenario
    validate_scenario(manifest, read_json(run_dir / 'fixture-vector.json'))
    validate_catalog_route(manifest)


def resolve_qualification_work_root(value: Path, root: Path, approved_work_roots) -> Path:
    try:
        return owned_work_root(value, root)
    except ValueError:
        candidate = Path(value).resolve(strict=True)
        if candidate not in {path.resolve(strict=False) for path in approved_work_roots}:
            raise
        return candidate


def relocated_manifest(run_dir: Path, manifest: dict, work: Path, *, root: Path, default_base_python: Path, app_python: Path, allowed_work_roots=()) -> dict:
    if manifest.get('sdk_version', '0.1.0a2') != sdk_selection(work)['sdk_version']:
        raise ValueError('SDK selection cannot be changed for a retained run.')
    base_source = (work / 'base-source').resolve(strict=True)
    pack_root = (work / 'artifacts' / 'contract-pack').resolve(strict=True)
    provenance = verify_base_source(work, base_source)
    sdk = importlib.import_module('ai_base_application_sdk')
    updated = {
        **manifest,
        'base_source': str(base_source),
        'pack_root': str(pack_root),
        'base_source_provenance': provenance,
        'sdk_wheel_sha256': verify_installed_sdk(work, sdk),
        'sdk_selection_sha256': sdk_selection_digest(work),
        'contract_pack_manifest_sha256': digest_file(pack_root / 'manifest.json'),
    }
    validate_manifest(run_dir, updated, root=root, default_base_python=default_base_python,
                      app_python=app_python, allowed_work_roots=allowed_work_roots)
    return updated


def work_root_for_manifest(manifest: dict, root: Path, allowed_work_roots) -> Path:
    base_source = Path(manifest['base_source']).resolve(strict=True)
    work = base_source.parent
    allowed = {Path(value).resolve(strict=False) for value in allowed_work_roots}
    allowed.add((root / '.tmp' / 'task-run-w5').resolve(strict=False))
    if work not in allowed or base_source != work / 'base-source':
        raise ValueError('Runtime manifest work root is not trusted.')
    return work


def validate_catalog_route(manifest: dict) -> None:
    catalog = manifest.get('catalog', {})
    project_id, stage_id = catalog.get('project_id'), catalog.get('stage_id')
    if catalog.get('scope_key') != f'projects.{project_id}.stages.{stage_id}':
        raise ValueError('Runtime manifest scope relation is invalid.')
    expected_route = f'/projects/{project_id}/stages/{stage_id}/reports/'
    if manifest.get('routes', {}).get('project_stage_reports') != expected_route:
        raise ValueError('Runtime manifest route relation is invalid.')


def status_url(port: int, manifest: dict) -> str:
    return safe_url(port, manifest['routes']['project_stage_reports'])


def wait_valid_connection(run_dir: Path, descriptor: LaunchDescriptor, state: dict, manifest: dict, *, platform_ops, expected_store=None, seconds=20.0) -> dict:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if descriptor.connection_file and descriptor.connection_file.exists():
            connection = read_json(descriptor.connection_file)
            validate_connection(connection, descriptor, state, manifest, platform_ops=platform_ops, expected_store=expected_store)
            write_json(run_dir / 'base' / 'connection.json', connection, replace=True)
            return connection
        time.sleep(0.05)
    raise TimeoutError('Timed out waiting for current Base connection publication.')


def validate_connection(connection: dict, descriptor: LaunchDescriptor, state: dict, manifest: dict, *, platform_ops, expected_store=None) -> None:
    required = {'executionMode', 'qualification', 'contractVersion', 'packVersion', 'pid', 'scopeKey',
                'sourceAppId', 'baseUrl', 'credentialRef', 'token', 'runStoreId', 'stopFile',
                'grantRevision', 'limitPolicyRevision', 'packRoot', 'launchId', 'exitFile'}
    if set(connection) < required:
        raise ValueError('Base connection schema is incomplete.')
    url = urlsplit(connection['baseUrl'])
    if (connection['executionMode'] != 'synthetic' or connection['qualification'] != 'synthetic_only'
            or connection['contractVersion'] != CONTRACT_VERSION or connection['packVersion'] != PACK_VERSION
            or connection['sourceAppId'] != APP_ID or connection['credentialRef'] != CREDENTIAL_REF
            or connection['grantRevision'] != GRANT_REVISION or connection['limitPolicyRevision'] != LIMIT_REVISION
            or connection['scopeKey'] != manifest['catalog']['scope_key']
            or connection['launchId'] != descriptor.launch_id
            or Path(connection['stopFile']).resolve(strict=False) != descriptor.stop_file
            or Path(connection['exitFile']).resolve(strict=False) != descriptor.exit_file
            or Path(connection['packRoot']).resolve(strict=True) != Path(manifest['pack_root']).resolve(strict=True)
            or not isinstance(connection['token'], str) or not connection['token']
            or not isinstance(connection['runStoreId'], str) or not connection['runStoreId']
            or (expected_store is not None and connection['runStoreId'] != expected_store)
            or url.scheme != 'http' or url.hostname != '127.0.0.1' or url.port != int(state['port'])
            or url.username or url.password or url.query or url.fragment or url.path not in ('', '/')):
        raise ValueError('Base connection identity is invalid.')
    proof = validate_process_proof(descriptor, state, platform_ops=platform_ops, worker_pid=int(connection['pid']))
    if int(connection['pid']) != int(proof['worker_pid']):
        raise ValueError('Base connection does not match SLE process provenance.')


def validate_process_proof(descriptor: LaunchDescriptor, state: dict, *, platform_ops, worker_pid: int | None = None) -> dict:
    wrapper_pid = int(state['pid'])
    command = tuple(str(part) for part in state['command'])
    candidates = process_candidates(state, platform_ops, worker_pid)
    for candidate in candidates:
        relation = process_relation(int(candidate), wrapper_pid, command, platform_ops)
        if relation is None:
            continue
        proof = {
            'schema_version': 1,
            'service': descriptor.service,
            'launch_id': descriptor.launch_id,
            'wrapper_pid': wrapper_pid,
            'worker_pid': int(candidate),
            'relation': relation,
            'command_fingerprint': command_fingerprint(command),
        }
        write_json(descriptor.directory / 'process-proof.json', proof, replace=True)
        return proof
    raise ValueError('SLE process proof could not be established while live.')


def process_candidates(state: dict, platform_ops, worker_pid: int | None) -> list[int]:
    values = []
    if worker_pid is not None:
        values.append(int(worker_pid))
    provenance = state.get('provenance') or {}
    if provenance.get('listener_pid') is not None:
        values.append(int(provenance['listener_pid']))
    values.extend(int(pid) for pid in platform_ops.get_listening_process_ids(str(state.get('host', '127.0.0.1')), int(state['port'])))
    values.append(int(state['pid']))
    result = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def process_relation(candidate: int, wrapper_pid: int, command: tuple[str, ...], platform_ops) -> str | None:
    if candidate == wrapper_pid:
        if platform_ops.process_exists(wrapper_pid) and platform_ops.process_matches_command(wrapper_pid, command):
            return 'registered_wrapper'
        return None
    reference = ProcessReference(wrapper_pid, command, platform_ops)
    return 'w5_worker_child' if worker_matches_process(candidate, reference) else None


def stdout_offset(service_state: dict) -> int:
    path = Path(service_state['stdout_log'])
    return path.stat().st_size if path.exists() else 0


def normal_stop_evidence(descriptor: LaunchDescriptor, service_state: dict, result: StopResult, *, stdout_start=0, require_worker_event=False) -> dict:
    receipt = read_json(descriptor.exit_file)
    proof = read_json(descriptor.directory / 'process-proof.json')
    if (receipt.get('schema_version') != 1 or receipt.get('service') != descriptor.service
            or receipt.get('launch_id') != descriptor.launch_id or int(receipt.get('pid')) != int(proof['worker_pid'])
            or receipt.get('exit_code') != 0):
        raise ValueError('Launch exit receipt is invalid.')
    worker_event = None
    if require_worker_event:
        worker_event = fresh_worker_event(Path(service_state['stdout_log']), stdout_start)
    if not result.stopped or result.forced or result.reason not in {'stop_command', 'owned_listener:stop_command'}:
        raise ValueError('SLE stop result is abnormal.')
    return {'exit_receipt': receipt, 'process_proof': proof, 'worker_event': worker_event, 'sle_reason': result.reason}


def validate_before_stop(launch, state, platform_ops):
    if launch is None or state is None:
        return
    try:
        validate_process_proof(launch, state, platform_ops=platform_ops)
    except Exception:
        return


def classify_stop_evidence(app_launch, app_state, app_result, base_launch, base_state, base_result, app_offset) -> str:
    try:
        if app_launch is not None:
            normal_stop_evidence(app_launch, app_state, app_result, stdout_start=app_offset, require_worker_event=True)
        if base_launch is not None:
            normal_stop_evidence(base_launch, base_state, base_result)
        return 'normal'
    except Exception:
        return 'abnormal'


def fresh_worker_event(stdout_log: Path, start: int) -> dict:
    data = stdout_log.read_bytes()[start:]
    for line in data.decode('utf-8', errors='replace').splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get('event') == 'project_runtime_stopped' and event.get('stopped') is True and not event.get('unresolved'):
            return event
    raise ValueError('Fresh worker stop event was not found.')

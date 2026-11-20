"""Owned native fixture launches through the existing lifecycle engine."""
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, dataclass
from http.client import HTTPException
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import time

import httpx
from ai_host.exit_processes import living_children
from scripts.service_lifecycle_engine import ServiceLifecycleEngine, ServiceSpec
from scripts.validation.project_full_stack import start_sanitized
from scripts.validation.project_full_stack_support import base_environment, write_json
from scripts.validation.windows_host_samples import ARMS, PAGE_KEYS, client
from scripts.validation.windows_qualification_inputs import canonical, overlaps


ROOT = Path(__file__).resolve().parents[2]
ENTRY = ROOT / 'ai_host/tests/windows_perf_entry.py'


@dataclass(slots=True)
class RunningArms:
    engine: ServiceLifecycleEngine
    record: dict
    bases: dict
    instances: dict


def free_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


def cleanup_is_normal(cleanup):
    services = cleanup.get('services') or {}
    if cleanup.get('owned_descendants_absent') is not True or cleanup.get('listeners_absent') is not True:
        return False
    services_normal = bool(services) and all(
        row.get('stopped') is True and row.get('exit_code') == 0
        and row.get('forced') is False and row.get('force_requested') is False
        and row.get('reason') == 'stop_command'
        for row in services.values()
    )
    return bool(
        services_normal
        and cleanup.get('normal') is True
        and cleanup.get('owned_descendants_absent') is True
        and cleanup.get('listeners_absent') is True
    )


def process_identity(pid, created, command_line):
    if not pid or not created or not command_line:
        return None
    return hashlib.sha256(f"{int(pid)}:{created}:{command_line}".encode("utf-8")).hexdigest()


def _split_command(command_line):
    if not command_line:
        return None
    from scripts.service_lifecycle_engine import platform_ops

    return list(platform_ops.split_command_line(command_line))


def _normalized_text(*parts):
    return " ".join(str(part or "").replace("\\", "/").casefold() for part in parts)


def _python_like(row):
    name = str(row.get("name") or "").casefold()
    executable = str(row.get("executable_path") or "").replace("\\", "/").casefold()
    return name.startswith("python") or name == "py.exe" or "/python" in executable


def _metrics_relevant(row, *, source_root, owned_root):
    if row.get("metrics_workload") is True:
        return True
    command_line = str(row.get("command_line") or "")
    if not command_line:
        return bool(row.get("sensor_error") and _python_like(row))
    text = _normalized_text(command_line, row.get("executable_path"))
    source = _normalized_text(source_root)
    owned = _normalized_text(owned_root)
    if source and source in text and ("windows_perf_entry.py" in text or "manage.py" in text):
        return True
    return bool(owned and owned in text and "windows_perf_entry.py" in text)


def enrich_process_observations(records, details_by_pid, *, source_root, owned_root):
    enriched = []
    for row in records:
        item = dict(row)
        details = dict(details_by_pid.get(int(item.get("pid", -1)), {}) or {})
        command_line = details.get("command_line") or item.get("command_line") or ""
        created = details.get("creation_date") or details.get("created") or item.get("created") or ""
        item.update({key: value for key, value in details.items() if value not in (None, "")})
        if command_line:
            item["command_line"] = command_line
            item["command"] = item.get("command") or _split_command(command_line)
        identity = item.get("identity") or process_identity(item.get("pid"), created, command_line)
        if identity:
            item["identity"] = identity
        if "metrics_workload" not in item:
            item["metrics_workload"] = _metrics_relevant(item, source_root=source_root, owned_root=owned_root)
        enriched.append(item)
    return enriched


def _command_fingerprint(command):
    if command is None:
        return None
    sanitized = [Path(str(command[0])).name] if command else []
    if len(command) > 1:
        sanitized.append(f'argc={len(command)}')
    digest = hashlib.sha256(json.dumps([str(part) for part in command], sort_keys=True).encode()).hexdigest()
    return {'display': ' '.join(sanitized), 'sha256': digest}


def classify_process_observations(records, *, owned_identities):
    processes, blockers = [], []
    for row in records:
        relevant = row.get('metrics_workload') is True
        identity = row.get('identity')
        if relevant and identity in owned_identities:
            classification = 'owned_measurement'
        elif relevant and identity:
            classification = 'foreign_relevant'
        elif relevant:
            classification = 'unresolved_relevant'
        else:
            classification = 'tooling_unrelated'
        item = {
            'pid': row.get('pid'),
            'identity': identity,
            'classification': classification,
            'command_fingerprint': _command_fingerprint(row.get('command')),
        }
        processes.append(item)
        if classification in {'foreign_relevant', 'unresolved_relevant'}:
            blockers.append(f'{classification}:{row.get("pid")}')
    return {'processes': processes, 'certification_blockers': blockers}


def _service_pid(state, result):
    pid = result.get('pid') if isinstance(result, dict) else None
    pid = pid if pid is not None else state.get('pid')
    try:
        return int(pid)
    except (TypeError, ValueError):
        return None


def _service_port(state, result):
    port = state.get('port', result.get('port') if isinstance(result, dict) else None)
    try:
        return int(port)
    except (TypeError, ValueError):
        return None


def _provenance_listener_pid(state):
    provenance = state.get('provenance') if isinstance(state, dict) else None
    if not isinstance(provenance, dict):
        return None
    try:
        return int(provenance.get('listener_pid'))
    except (TypeError, ValueError):
        return None


def _capture_owned_process_observations(name, state, ops, stack):
    errors, owned = [], {}
    if ops is None:
        return {'owned_processes': owned, 'observation_errors': ['platform_ops_unavailable']}
    pid = _service_pid(state, {})
    if pid is None:
        errors.append('pid_unavailable')
    else:
        owned[pid] = {'pid': pid, 'role': 'service_root'}
        try:
            for child in living_children(root_pid=pid):
                child_pid = int(child['pid'])
                owned[child_pid] = {'pid': child_pid, 'role': 'descendant', **child}
        except Exception as error:
            errors.append(f'descendant_inventory_failed:{type(error).__name__}')
    listener_pid = _provenance_listener_pid(state)
    if listener_pid is not None and listener_pid not in owned:
        owned[listener_pid] = {'pid': listener_pid, 'role': 'listener'}
    for process in owned.values():
        try:
            process['_exit_observation'] = stack.enter_context(ops.observe_process_exit(int(process['pid'])))
        except Exception as error:
            errors.append(f'exit_observation_failed:{process["pid"]}:{type(error).__name__}')
    return {'owned_processes': owned, 'observation_errors': errors}


def _finalize_owned_process_observations(capture, ops):
    errors = list(capture.get('observation_errors') or [])
    all_absent = not errors
    for pid, row in list(capture.get('owned_processes', {}).items()):
        observation = row.pop('_exit_observation', None)
        terminal = observation() if observation is not None else None
        running = bool(ops and ops.process_exists(int(pid)))
        row['terminal_exit_code'] = terminal
        row['process_running'] = running
        if running:
            all_absent = False
            errors.append(f'owned_process_still_running:{pid}')
        elif terminal is None:
            all_absent = False
            errors.append(f'owned_process_exit_unknown:{pid}')
    capture['observation_errors'] = errors
    return all_absent, errors


def owned_process_identities_from_state(state, ops):
    identities = set()
    provenance = state.get('provenance') if isinstance(state, dict) else None
    if isinstance(provenance, dict):
        marker = provenance.get('process_start_marker')
        if marker:
            identities.add(str(marker))
        listener_pid = provenance.get('listener_pid')
        try:
            if listener_pid is not None:
                marker = ops.process_start_marker(int(listener_pid))
                if marker:
                    identities.add(str(marker))
        except Exception:
            pass
    try:
        pid = int(state.get('pid'))
        marker = ops.process_start_marker(pid)
        if marker:
            identities.add(str(marker))
    except Exception:
        pass
    return identities


def stop_arms(engine, names):
    states = engine.read_state() if hasattr(engine, 'read_state') else {}
    results = {}
    ops = getattr(engine, 'platform_ops', None)
    observations = {}
    owned_descendants_absent = True
    listeners_absent = True
    with ExitStack() as stack:
        captures = {
            name: _capture_owned_process_observations(name, states.get(name, {}) if isinstance(states, dict) else {}, ops, stack)
            for name in names
        }
        for name in reversed(names):
            try:
                result = engine.stop_service(name, graceful_timeout_seconds=15)
                results[name] = asdict(result)
            except Exception as error:
                results[name] = {'error': type(error).__name__, 'stopped': False}
        for name in names:
            state = states.get(name, {}) if isinstance(states, dict) else {}
            result = results.get(name, {})
            pid = _service_pid(state, result)
            host, port = state.get('host', '127.0.0.1'), _service_port(state, result)
            errors = list(captures[name].get('observation_errors') or [])
            if port is None or port == -1:
                listener_pids = []
                errors.append('port_unavailable')
                listeners_absent = False
            elif ops is None:
                listener_pids = []
                errors.append('listener_sensor_unavailable')
                listeners_absent = False
            else:
                listener_pids = list(ops.get_listening_process_ids(str(host), int(port)))
                listeners_absent = listeners_absent and not listener_pids
            absent, process_errors = _finalize_owned_process_observations(captures[name], ops)
            errors.extend(error for error in process_errors if error not in errors)
            owned_descendants_absent = owned_descendants_absent and absent
            running = bool(ops and pid is not None and ops.process_exists(int(pid)))
            observations[name] = {
                'pid': pid, 'host': host, 'port': port, 'process_running': running,
                'listener_pids': listener_pids,
                'owned_processes': captures[name].get('owned_processes', {}),
                'observation_errors': errors,
            }
            if errors:
                owned_descendants_absent = False
    services_normal = bool(results) and all(
        row.get('stopped') is True and row.get('exit_code') == 0
        and row.get('forced') is False and row.get('force_requested') is False
        and row.get('reason') == 'stop_command'
        for row in results.values()
    )
    cleanup = {
        'services': results,
        'observations': observations,
        'owned_descendants_absent': owned_descendants_absent,
        'listeners_absent': listeners_absent,
        'normal': services_normal and owned_descendants_absent and listeners_absent,
    }
    return cleanup


def fixture_spec(name, root, instance, python, *, production, spacing_events=8):
    stop_file = instance / 'stop'
    return ServiceSpec.from_values(
        name, (free_port(),),
        [str(python), '-I', str(ENTRY), 'serve', '--root', str(root), '--instance', str(instance),
         '--role', 'baseline' if name == 'baseline' else 'candidate', '--port', '{port}',
         '--spacing-events', str(spacing_events),
         *(['--production'] if production else [])],
        stop_command=[
            str(python), '-I', '-c',
            'import sys,time; from pathlib import Path; Path(sys.argv[1]).write_text(str(time.monotonic()), encoding="utf-8")',
            str(stop_file),
        ],
        cwd=ROOT, startup_timeout_seconds=45, graceful_timeout_seconds=15,
    )


def ready_metadata(base, engine, name):
    deadline = time.monotonic() + 45
    with client() as http:
        while True:
            state = engine.read_state().get(name)
            if not state or not engine.platform_ops.process_exists(state['pid']):
                raise ValueError(f'{name} exited before semantic readiness')
            try:
                response = http.get(base + '/qualification/pages/')
                if response.status_code == 200:
                    result = response.json()
                    if (set(result['pages']) != set(PAGE_KEYS) or result['worker_started'] is not True
                            or result['worker_executed']):
                        raise ValueError('Baseline fixture or idle worker is not equivalent')
                    return result
            except (OSError, TimeoutError, HTTPException, httpx.TransportError):
                pass
            if time.monotonic() >= deadline:
                raise TimeoutError('Native fixture did not become ready')
            time.sleep(0.1)


@contextmanager
def running_arms(root, python, *, production, names=ARMS, spacing_events=8, window=None):
    root = canonical(root)
    python = canonical(python)
    if overlaps(root, ROOT) or not names or len(set(names)) != len(names) or not set(names) <= set(ARMS):
        raise ValueError('Invalid native fixture scope')
    marker = root / 'owner.json'
    if marker.exists() or (root / 'catalog.sqlite3').exists():
        raise ValueError('Native fixture root must be new')
    write_json(marker, {'owner': 'windows-host-qualification', 'root': str(root)})
    with (root / 'seed.stdout.log').open('wb') as stdout, (root / 'seed.stderr.log').open('wb') as stderr:
        seeded = subprocess.run(
            [str(python), '-I', str(ENTRY), 'seed', '--root', str(root)],
            cwd=ROOT, env=base_environment(root / 'seed-environment'), stdout=stdout, stderr=stderr, timeout=90,
        )
    if seeded.returncode:
        raise ValueError('Native fixture seeding failed')
    engine = ServiceLifecycleEngine('windows-host-qualification', root, instance_name='qualification',
                                   state_directory=root / 'lifecycle', log_directory=root / 'logs')
    record = {'production': production, 'root': str(root), 'arms': {}, 'cleanup': None}
    started, bases, instances = [], {}, {}
    try:
        for name in names:
            if name not in ARMS:
                raise ValueError('Unknown measurement arm')
            instance = root / name
            instance.mkdir()
            instances[name] = instance
            spec = fixture_spec(name, root, instance, python, production=production, spacing_events=spacing_events)
            started.append(name)
            environment = start_sanitized(engine, spec, instance / 'environment')
            state = engine.read_state()[name]
            identities = owned_process_identities_from_state(state, engine.platform_ops)
            if window is not None and hasattr(window, 'register_owned_process_identities'):
                window.register_owned_process_identities(identities)
            bases[name] = f'http://127.0.0.1:{state["port"]}'
            record['arms'][name] = {'environment': environment, 'state': state, 'owned_identities': sorted(identities)}
            record['arms'][name]['metadata'] = ready_metadata(bases[name], engine, name)
        yield RunningArms(engine, record, bases, instances)
    finally:
        record['cleanup'] = stop_arms(engine, started)
        write_json(root / 'processes.json', record)
        if started and not record['cleanup']['normal']:
            raise ValueError('Native fixture did not stop normally')

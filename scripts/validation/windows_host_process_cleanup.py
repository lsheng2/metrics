"""Cleanup observations for owned Windows performance fixture processes."""
from __future__ import annotations

from contextlib import ExitStack
from dataclasses import asdict

from ai_host.exit_processes import living_children
from scripts.validation.windows_host_process_window import native_process_fact


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


def _capture_owned_process_observations(state, ops, stack, *, run_id=None):
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
        if run_id is not None:
            process['run_id'] = run_id
        try:
            native = native_process_fact(
                int(process['pid']),
                parent_pid=process.get('parent_pid'),
                image_name=process.get('name') or '',
            )
            if process.get('created') is not None and process['created'] != native.get('native_creation'):
                errors.append(f'native_incarnation_changed:{process["pid"]}')
            if native.get('native_creation') not in (None, ''):
                process['native_creation'] = native['native_creation']
            if native.get('parent_pid') is not None:
                process['native_parent_pid'] = native['parent_pid']
            if native.get('image_name'):
                process['native_image_name'] = native['image_name']
            process['native_handle_opened'] = native.get('handle_opened') is True
            process['native_handle_closed'] = native.get('handle_closed') is True
            if (not process['native_handle_opened'] or not process['native_handle_closed']
                    or type(native.get('native_creation')) is not int or native['native_creation'] <= 0):
                errors.append(f'native_observation_failed:{process["pid"]}')
        except Exception as error:
            errors.append(f'native_identity_failed:{process["pid"]}:{type(error).__name__}')
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


def stop_arms(engine, names, *, run_id=None):
    states = engine.read_state() if hasattr(engine, 'read_state') else {}
    results = {}
    ops = getattr(engine, 'platform_ops', None)
    observations = {}
    owned_descendants_absent = True
    listeners_absent = True
    with ExitStack() as stack:
        captures = {
            name: _capture_owned_process_observations(
                states.get(name, {}) if isinstance(states, dict) else {}, ops, stack, run_id=run_id,
            )
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
    return {
        'services': results,
        'observations': observations,
        'owned_descendants_absent': owned_descendants_absent,
        'listeners_absent': listeners_absent,
        'normal': services_normal and owned_descendants_absent and listeners_absent,
    }

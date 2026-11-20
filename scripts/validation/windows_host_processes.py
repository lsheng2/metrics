"""Owned native fixture launches through the existing lifecycle engine."""
from contextlib import contextmanager
from dataclasses import dataclass
from http.client import HTTPException
from pathlib import Path
import socket
import subprocess
import time

import httpx
from scripts.service_lifecycle_engine import ServiceLifecycleEngine, ServiceSpec
from scripts.validation.project_full_stack import start_sanitized
from scripts.validation.project_full_stack_support import base_environment, write_json
from scripts.validation.windows_host_process_cleanup import cleanup_is_normal, stop_arms
from scripts.validation.windows_host_process_identity import (
    classify_process_observations,
    enrich_process_observations,
    owned_process_identity_facts_from_state,
    process_identity,
)
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
            identity_facts = owned_process_identity_facts_from_state(state, engine.platform_ops)
            identities = identity_facts["identities"]
            if window is not None and hasattr(window, 'register_owned_process_identities'):
                window.register_owned_process_identities(identities)
            bases[name] = f'http://127.0.0.1:{state["port"]}'
            record['arms'][name] = {
                'environment': environment,
                'state': state,
                'owned_identities': sorted(identities),
                'owned_identity_facts': {key: value for key, value in identity_facts.items() if key != "identities"},
            }
            record['arms'][name]['metadata'] = ready_metadata(bases[name], engine, name)
        yield RunningArms(engine, record, bases, instances)
    finally:
        record['cleanup'] = stop_arms(engine, started)
        write_json(root / 'processes.json', record)
        if started and not record['cleanup']['normal']:
            raise ValueError('Native fixture did not stop normally')

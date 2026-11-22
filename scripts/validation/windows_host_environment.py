"""Exclusive measurement window with native Windows CPU/process observations."""
import ctypes
from ctypes import wintypes
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid

from scripts.validation.project_full_stack_support import read_json, write_json
from scripts.validation.windows_host_processes import classify_process_observations, enrich_process_observations
from scripts.validation.windows_host_process_identity import (
    _command_is_bound_to_run_root, driver_process_identities, sanitize_process_rows, startup_owned_identities_from_run,
)
from scripts.validation.windows_host_process_window import capture_process_window


def source_snapshot(root):
    def git(*args):
        result = subprocess.run(['git', *args], cwd=root, capture_output=True, text=True, timeout=30, check=True)
        return result.stdout.strip()

    status = git('status', '--porcelain=v1', '--untracked-files=all')
    if status:
        raise ValueError('Measurement source must be committed and clean')
    return {'head': git('rev-parse', 'HEAD'), 'status_sha256': hashlib.sha256(status.encode()).hexdigest()}


def _windows_process_details(processes):
    target_pids = {
        int(row['pid']) for row in processes
        if str(row.get('name') or '').casefold().startswith(('python', 'py.', 'git'))
    }
    if not target_pids:
        return {}
    script = (
        "Get-CimInstance Win32_Process | "
        "Select-Object ProcessId,Name,CommandLine,@{Name='CreationDate';Expression={$_.CreationDate.ToString()}},ExecutablePath | "
        "ConvertTo-Json -Compress"
    )
    completed = subprocess.run(
        ['powershell', '-NoProfile', '-Command', script],
        capture_output=True, text=True, timeout=20, check=False,
    )
    if completed.returncode or not completed.stdout.strip():
        return {pid: {'sensor_error': 'process_detail_unavailable'} for pid in target_pids}
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {pid: {'sensor_error': 'process_detail_malformed'} for pid in target_pids}
    if isinstance(payload, dict):
        payload = [payload]
    details = {}
    for row in payload or []:
        try:
            pid = int(row.get('ProcessId'))
        except (TypeError, ValueError):
            continue
        if pid not in target_pids:
            continue
        details[pid] = {
            'command_line': row.get('CommandLine') or '',
            'creation_date': row.get('CreationDate') or '',
            'executable_path': row.get('ExecutablePath') or '',
        }
        if not details[pid]['command_line'] or not details[pid]['creation_date']:
            details[pid]['sensor_error'] = 'process_detail_incomplete'
    for pid in target_pids - set(details):
        details[pid] = {'sensor_error': 'process_detail_missing'}
    return details


def machine_snapshot(*, source_root=None, owned_root=None):
    if sys.platform != 'win32':
        raise ValueError('Only Windows qualification is authorized')
    from ai_host.exit_processes import ProcessEntry, _windows_api

    api = _windows_api()
    api.GetSystemTimes.argtypes = [ctypes.POINTER(wintypes.FILETIME)] * 3
    api.GetSystemTimes.restype = wintypes.BOOL
    values = [wintypes.FILETIME() for _ in range(3)]
    if not api.GetSystemTimes(*(ctypes.byref(value) for value in values)):
        raise ctypes.WinError(ctypes.get_last_error())
    cpu = {name: (value.dwHighDateTime << 32) | value.dwLowDateTime
           for name, value in zip(('idle', 'kernel', 'user'), values)}
    snapshot = api.CreateToolhelp32Snapshot(0x2, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    processes = []
    try:
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        present = api.Process32FirstW(snapshot, ctypes.byref(entry))
        while present:
            processes.append({'pid': entry.th32ProcessID, 'parent_pid': entry.th32ParentProcessID,
                              'name': entry.szExeFile, 'threads': entry.cntThreads})
            present = api.Process32NextW(snapshot, ctypes.byref(entry))
        if ctypes.get_last_error() != 18:
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        api.CloseHandle(snapshot)
    if source_root is not None or owned_root is not None:
        with capture_process_window(processes) as process_window:
            details = _windows_process_details(processes)
            process_window_facts = process_window.finalize()
        for pid, fact in process_window_facts.items():
            details.setdefault(pid, {})['process_window'] = fact
        processes = enrich_process_observations(
            processes, details,
            source_root=source_root or '', owned_root=owned_root or '',
        )
    return {'cpu': cpu, 'processes': processes}


class MeasurementWindow:
    def __init__(self, owned_root, run_root, source_root, *, owned_process_identities=None):
        self.guard = Path(owned_root) / 'HEAVY_RUN_ACTIVE'
        self.run_root, self.source_root = Path(run_root), Path(source_root)
        self.identity = str(uuid.uuid4())
        self.record = {'id': self.identity, 'pid': os.getpid(), 'snapshots': [], 'errors': []}
        self.owned_process_identities = set(owned_process_identities or ())
        self.owned_process_facts = []
        self.launch_intents = []
        self._stop = threading.Event()
        self._thread = None
        self._stream = None
        self._verdict_writer = None
        self._verdict_path = None

    def __enter__(self):
        if (self.run_root / 'measurement-window.json').exists():
            raise FileExistsError('Measurement receipt already exists')
        write_json(self.guard, {'id': self.identity, 'pid': os.getpid(), 'run_root': str(self.run_root)})
        try:
            self.record['started_at'] = datetime.now(UTC).isoformat()
            self.record['started_monotonic'] = time.monotonic()
            self.record['source_before'] = source_snapshot(self.source_root)
            self._stream = (self.run_root / 'machine.jsonl').open('x', encoding='utf-8')
            self._collect()
            self._thread = threading.Thread(target=self._monitor, name='qualification-cpu-snapshot', daemon=True)
            self._thread.start()
            return self
        except BaseException:
            if self._stream is not None:
                self._stream.close()
            self._remove_own_guard()
            raise

    def register_owned_process_identities(self, identities):
        self.owned_process_identities.update(str(identity) for identity in identities if identity)

    def register_owned_process_identity_facts(self, facts):
        for fact in facts or ():
            if not isinstance(fact, dict):
                continue
            pid = fact.get('pid')
            native_creation = fact.get('native_creation')
            if pid is None or native_creation in (None, ''):
                continue
            row = dict(fact)
            row['run_id'] = self.identity
            row['owner_key'] = f'{self.identity}:{int(pid)}:{native_creation}'
            self.owned_process_facts.append(row)

    def register_launch_intent(self, command):
        self.check()
        if not _command_is_bound_to_run_root(command, self.run_root):
            raise ValueError('Measurement launch command is not bound to the run root')
        self.launch_intents.append({'command': tuple(command), 'parent_pid': os.getpid()})

    def _collect(self):
        snapshot = machine_snapshot(source_root=self.source_root, owned_root=self.guard.parent)
        row = {
            'utc': datetime.now(UTC).isoformat(),
            'monotonic': time.monotonic(),
            **snapshot,
        }
        setup_started = time.monotonic()
        startup_identities = startup_owned_identities_from_run(
            self.run_root, row.get('processes', []), pending_launches=tuple(self.launch_intents),
        )
        driver_identities = driver_process_identities(row.get('processes', []), os.getpid())
        owned_identities = self.owned_process_identities | startup_identities['identities'] | driver_identities
        owner_facts = list(self.owned_process_facts)
        row['observed_owned_identities'] = sorted(owned_identities)
        row['ownership_setup'] = {
            'elapsed_ms': (time.monotonic() - setup_started) * 1000,
            'registered_identity_count': len(self.owned_process_identities),
            'registered_owner_fact_count': len(owner_facts),
            'driver_identity_count': len(driver_identities),
            'startup_identity_count': len(startup_identities['identities']),
            'startup_matches': startup_identities['matches'],
        }
        row['process_owner_registrations'] = owner_facts
        classification = classify_process_observations(
            row.get('processes', []), owned_identities=owned_identities,
            owned_process_facts=owner_facts, current_run_id=self.identity,
        )
        row['process_classification'] = classification
        row['process_resolution_facts'] = classification.get('process_resolution_facts', [])
        self.record['process_classification'] = classification
        if classification['certification_blockers']:
            self.record['errors'].append('relevant_process:' + ','.join(classification['certification_blockers']))
        previous = self.record['snapshots']
        if previous:
            old = previous[-1]['cpu']
            total = row['cpu']['kernel'] - old['kernel'] + row['cpu']['user'] - old['user']
            idle = row['cpu']['idle'] - old['idle']
            row['cpu_busy_percent'] = None if total <= 0 else 100 * (total - idle) / total
        persisted = {**row, 'processes': sanitize_process_rows(row.get('processes', []))}
        self.record['snapshots'].append(persisted)
        self._stream.write(json.dumps(persisted, allow_nan=False) + '\n')
        self._stream.flush()

    def _monitor(self):
        while not self._stop.wait(60):
            try:
                self._collect()
            except Exception as error:
                self.record['errors'].append(type(error).__name__)
                return

    def check(self):
        if self.record['errors']:
            raise ValueError('Measurement environment observation failed')
        if read_json(self.guard).get('id') != self.identity:
            raise ValueError('Measurement guard changed')

    def bind_verdict(self, path, writer=None):
        path = Path(path)
        self.check()
        if writer is None and not path.is_file():
            raise ValueError('Measurement verdict is missing')
        self.record['verdict'] = {
            'path': str(path),
            'guard_id': self.identity,
            'written_monotonic': time.monotonic(),
        }
        if path.is_file():
            self.record['verdict']['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        self._verdict_writer = writer
        self._verdict_path = path

    def _write_receipt_witness(self, write_started):
        if self._verdict_path is None or not self._verdict_path.is_file():
            raise ValueError('Measurement verdict is missing')
        completed = time.monotonic()
        guard = read_json(self.guard)
        observed = time.monotonic()
        witness = {
            'schema_version': 1,
            'kind': 'windows-performance-receipt-write-witness',
            'receipt_path': str(self._verdict_path),
            'receipt_sha256': hashlib.sha256(self._verdict_path.read_bytes()).hexdigest(),
            'guard_expected_id': self.identity,
            'guard_observed_id': guard.get('id'),
            'guard_matches': guard.get('id') == self.identity,
            'write_started_monotonic': write_started,
            'write_completed_monotonic': completed,
            'guard_observed_monotonic': observed,
            'writer_pid': os.getpid(),
        }
        if witness['guard_matches'] is not True:
            raise ValueError('Measurement guard changed before receipt witness')
        write_json(self.run_root / 'receipt-write-witness.json', witness)

    def _remove_own_guard(self):
        if read_json(self.guard).get('id') != self.identity:
            raise ValueError('Measurement guard changed; refusing to remove it')
        self.guard.unlink()

    def __exit__(self, exc_type, exc, traceback):
        self._stop.set()
        self._thread.join(2)
        try:
            if self._thread.is_alive():
                raise ValueError('Measurement observer did not stop')
            self._collect()
            self.record['source_after'] = source_snapshot(self.source_root)
            if self.record['source_before'] != self.record['source_after']:
                raise ValueError('Measurement source changed')
            self.check()
        except Exception as error:
            self.record['errors'].append(str(error))
        finally:
            self._stream.close()
            self.record['ended_at'] = datetime.now(UTC).isoformat()
            self.record['ended_monotonic'] = time.monotonic()
            self.record['result'] = 'PASS' if exc_type is None and not self.record['errors'] else 'FAIL'
            write_json(self.run_root / 'measurement-window.json', self.record)
            try:
                if self._verdict_writer is not None:
                    write_started = time.monotonic()
                    self._verdict_writer()
                    self._write_receipt_witness(write_started)
                self._remove_own_guard()
            except Exception as error:
                self.record['result'] = 'FAIL'
                self.record['errors'].append(str(error))
                write_json(self.run_root / 'measurement-window.json', self.record, replace=True)
        if self.record['errors']:
            raise ValueError('; '.join(self.record['errors']))
        return False

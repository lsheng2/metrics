from contextlib import ExitStack
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

import pytest
from ai_host.exit_processes import living_children
from scripts.service_lifecycle_engine.process_exit import observe_process_exit

ROOT = Path(__file__).resolve().parents[2]


def send_native_break(process):
    script = """
import json, sys, time
sys.path.insert(0, sys.argv[1])
from scripts.service_lifecycle_engine.controlled_stop import send_windows_control_event
sent_at = time.monotonic()
result = send_windows_control_event(int(sys.argv[2]), 1)
print(json.dumps({'sent_at': sent_at, **result}), flush=True)
"""
    sender = subprocess.run(
        [sys.executable, '-I', '-c', script, str(ROOT), str(process.pid)],
        capture_output=True, text=True, timeout=4, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert sender.returncode == 0, sender.stderr
    sent = json.loads(sender.stdout)
    assert sent['sent'], sent
    return sent


def native_stop_case(tmp_path, *, trigger, phase):
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    stop_file, marker = tmp_path / 'stop', tmp_path / 'phase'
    log_file = tmp_path / 'serve.log'
    command = [
        sys.executable, '-I', str(ROOT / 'ai_host/tests/serve_signal_entry.py'),
        str(tmp_path), str(port), str(stop_file), str(marker), phase, trigger,
    ]
    forced = False
    with log_file.open('wb') as log, ExitStack() as observations:
        process = subprocess.Popen(
            command, stdout=log, stderr=subprocess.STDOUT, startupinfo=startup,
            creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        try:
            opener = build_opener(ProxyHandler({}))
            deadline = time.monotonic() + 40
            while True:
                assert process.poll() is None, log_file.read_text(encoding='utf-8')
                try:
                    with opener.open(f'http://127.0.0.1:{port}/', timeout=1) as response:
                        assert response.status == 200
                        break
                except (URLError, TimeoutError):
                    assert time.monotonic() < deadline
                    time.sleep(0.1)
            inventory = living_children()
            family = {process.pid}
            for _ in inventory:
                family.update(row['pid'] for row in inventory if row['parent_pid'] in family)
            descendants = [(row['pid'], row['created']) for row in inventory if row['pid'] in family - {process.pid}]
            exits = {pid: observations.enter_context(observe_process_exit(pid)) for pid, _ in descendants}
            assert all(observer.wait is not None for observer in exits.values())
            triggered_at = time.monotonic()
            if trigger == 'stop-file':
                stop_file.write_text('stop', encoding='utf-8')
            elif trigger in {'SIGINT', 'SIGTERM'}:
                marker.with_suffix('.signal').touch()
            elif trigger == 'CTRL_BREAK_EVENT':
                triggered_at = send_native_break(process)['sent_at']
            sent = None
            if phase != 'normal':
                deadline = time.monotonic() + 8
                while not marker.exists():
                    assert process.poll() is None, log_file.read_text(encoding='utf-8')
                    assert time.monotonic() < deadline
                    time.sleep(0.02)
                assert marker.read_text(encoding='utf-8') == phase
                sent = send_native_break(process)
                triggered_at = sent['sent_at']
            expected = 0 if phase == 'normal' else 130
            assert process.wait(timeout=15 if phase == 'normal' else 2) == expected, log_file.read_text(encoding='utf-8')
            elapsed = time.monotonic() - triggered_at
            assert elapsed <= (10.0 if phase == 'normal' else 1.0)
            for observer in exits.values():
                assert observer.wait(max(0, triggered_at + 10.0 - time.monotonic()))
                assert observer() is not None
            (tmp_path / 'signal.json').write_text(json.dumps({
                'pid': process.pid, 'returncode': process.returncode,
                'trigger': trigger, 'phase': phase, 'descendants': descendants,
                'descendant_exit_codes': {pid: observer() for pid, observer in exits.items()},
                'elapsed': elapsed, 'event': sent, 'forced_cleanup': False,
            }, indent=2), encoding='utf-8')
        finally:
            if process.poll() is None:
                forced = True
                process.kill()
                process.wait(timeout=3)
    assert not forced
    output = log_file.read_text(encoding='utf-8')
    if phase == 'normal':
        events = []
        for line in output.splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                continue
        stopped = next(item for item in events if item.get('event') == 'project_runtime_stopped')
        assert stopped['stopped'] and not stopped['unresolved']
        assert 'serve_exit_inventory' in output
        assert 'serve cleanup failed.' not in output
        assert not tuple((tmp_path / 'tmp_ui_validation').iterdir())
    else:
        assert 'serve forced exit.' in output
    with socket.socket() as probe:
        assert probe.connect_ex(('127.0.0.1', port)) != 0


@pytest.mark.parametrize('trigger', ['stop-file', 'lifetime', 'SIGINT', 'SIGTERM', 'CTRL_BREAK_EVENT'])
def test_native_normal_stop_triggers_complete_cleanup_and_exit_zero(tmp_path, trigger):
    native_stop_case(tmp_path, trigger=trigger, phase='normal')


@pytest.mark.parametrize('trigger', ['stop-file', 'lifetime', 'SIGINT', 'SIGTERM', 'CTRL_BREAK_EVENT'])
@pytest.mark.parametrize('phase', ['drain', 'flush'])
def test_native_second_signal_during_cleanup_exits_130_in_one_second(tmp_path, trigger, phase):
    native_stop_case(tmp_path, trigger=trigger, phase=phase)


def test_native_second_control_event_after_stop_file_exits_130_in_one_second(tmp_path):
    native_stop_case(tmp_path, trigger='stop-file', phase='final')

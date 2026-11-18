import threading
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai_host.tests.test_lifecycle import FakeHandle, FakeRuntime, FakeServer, FakeThread
from project_management.app.domain.run_contracts import RuntimeStopResult


def test_stop_budget_uses_absolute_stages_and_only_an_active_run_can_extend_it():
    from ai_host.serve_control import StopBudget

    budget = StopBudget(started_at=100.0)
    assert budget.http_close_deadline == 102.0
    assert budget.drain_deadline == 103.0
    assert budget.flush_deadline == 106.5
    assert budget.server_deadline == 107.5
    assert budget.watchdog_deadline == 109.2
    budget.project_requested(active=False)
    assert budget.watchdog_deadline == 109.2
    budget.project_requested(active=True)
    assert budget.watchdog_deadline == 759.2
    budget.project_returned(at=115.0)
    assert budget.watchdog_deadline == 116.2
    budget.project_returned(at=120.0)
    assert budget.watchdog_deadline == 116.2


def test_idle_project_return_can_never_add_to_the_initial_deadline():
    from ai_host.serve_control import StopBudget

    budget = StopBudget(started_at=10.0)
    budget.project_returned(at=19.0)
    assert budget.watchdog_deadline == 19.2


@pytest.mark.parametrize('failed_stage', [None, 'listener', 'http', 'drain', 'flush', 'server'])
def test_cleanup_uses_shared_deadlines_and_attempts_later_owners_after_each_failure(monkeypatch, failed_stage):
    from ai_host import lifecycle
    from ai_host.serve_control import StopBudget

    events = []
    budget = StopBudget(started_at=100)
    handle = FakeHandle()
    runtime = FakeRuntime(RuntimeStopResult(True, None, ()))
    server = FakeServer()
    original_http = handle.close_http

    def step(name):
        def invoke(*args):
            events.append((name, args[-1] if name in {'listener', 'flush', 'server'} else None))
            if name == failed_stage:
                raise RuntimeError('synthetic cleanup failure')
            return original_http() if name == 'http' else None
        return invoke

    def drain(deadline):
        events.append(('drain', deadline))
        return failed_stage != 'drain'

    requests = SimpleNamespace(stop_accepting=lambda: events.append(('stop_admission', None)), wait_empty=drain)
    handle.close_http = step('http')
    monkeypatch.setattr(lifecycle, '_stop_listener', step('listener'))
    monkeypatch.setattr(lifecycle, '_flush_waitress_channels', step('flush'))
    monkeypatch.setattr(lifecycle, '_close_server', step('server'))
    monkeypatch.setattr(lifecycle.time, 'monotonic', lambda: 100.0)

    result = lifecycle.stop_owned_resources(
        handle=handle, server=server, server_thread=FakeThread(),
        project_runtime=runtime, budget=budget, requests=requests,
    )
    assert [name for name, _ in events] == ['stop_admission', 'listener', 'http', 'drain', 'flush', 'server']
    assert dict(events)['drain'] == 103.0
    assert dict(events)['flush'] == 106.5
    assert dict(events)['server'] == 107.5
    assert runtime.requested and runtime.waited
    assert result.exit_code == (0 if failed_stage is None else 3)


def test_waitress_dispatcher_shutdown_belongs_to_the_server_thread():
    from ai_host.lifecycle import run_http_server

    events = []
    server = SimpleNamespace(
        run=lambda: events.append(('run', threading.get_ident())),
        task_dispatcher=SimpleNamespace(
            shutdown=lambda **kwargs: events.append(('shutdown', threading.get_ident(), kwargs)),
            threads=set(),
        ),
    )
    errors = []
    thread = threading.Thread(target=run_http_server, args=(server, errors))
    thread.start()
    thread.join(1)
    assert not thread.is_alive()
    assert errors == []
    assert events == [
        ('run', thread.ident),
        ('shutdown', thread.ident, {'cancel_pending': True, 'timeout': 0.5}),
    ]


def test_main_thread_join_remains_signal_responsive(monkeypatch):
    from ai_host.lifecycle import join_until

    now = [0.0]
    waits = []

    class Pending:
        def is_alive(self):
            return True

        def join(self, timeout):
            waits.append(timeout)
            now[0] += timeout

    monkeypatch.setattr('ai_host.lifecycle.time.monotonic', lambda: now[0])
    assert join_until(Pending(), 1.2) is False
    assert waits == pytest.approx([0.5, 0.5, 0.2])


def test_watchdog_hard_exit_does_not_wait_for_blocked_output():
    script = """
import os, sys, threading, time
sys.path.insert(0, sys.argv[1])
from ai_host.serve_control import StopBudget, start_watchdog
budget = StopBudget(started_at=time.monotonic() - 9.15)
start_watchdog(budget, write_output=lambda: threading.Event().wait(), exit_process=os._exit)
threading.Event().wait(5)
raise SystemExit(99)
"""
    result = subprocess.run(
        [sys.executable, '-I', '-c', script, str(Path(__file__).resolve().parents[2])],
        capture_output=True, timeout=8,
    )
    assert result.returncode == 3, result.stderr


def test_emergency_exit_keeps_its_exit_code_when_output_is_blocked():
    script = """
import os, sys, threading
sys.path.insert(0, sys.argv[1])
from ai_host.serve_control import bounded_output_exit
bounded_output_exit(130, lambda: threading.Event().wait(), exit_process=os._exit)
raise SystemExit(99)
"""
    result = subprocess.run(
        [sys.executable, '-I', '-c', script, str(Path(__file__).resolve().parents[2])],
        capture_output=True, timeout=8,
    )
    assert result.returncode == 130, result.stderr


def test_dispatcher_success_boolean_cannot_hide_live_worker_threads():
    from ai_host.lifecycle import run_http_server

    server = SimpleNamespace(
        run=lambda: None,
        task_dispatcher=SimpleNamespace(shutdown=lambda **kwargs: True, threads={1}),
    )
    errors = []
    run_http_server(server, errors)
    assert 'dispatcher_threads_alive' in errors

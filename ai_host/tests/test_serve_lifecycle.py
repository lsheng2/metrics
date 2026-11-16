import io
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
from django.core.management import get_commands

import ai_base_runtime
from ai_host.management.commands.serve import Command
from ai_host.state import attach, detach, get_handle
from ai_host.tests.test_lifecycle import FakeHandle, FakeRuntime, FakeServer
from project_management.app.api.project_runs import (
    RunError, RuntimeStopResult, clear_project_runtime, get_project_runtime, install_project_runtime,
)


class ControlledRuntime(FakeRuntime):
    def __init__(self, result, *, start_error=None):
        super().__init__(result)
        self.started = False
        self.start_error = start_error

    def start(self):
        self.started = True
        if self.start_error is not None:
            raise self.start_error


def configured_command(monkeypatch, runtime, *, startup_failure=None):
    from project_management import runtime as project_runtime_module
    import waitress

    handle = FakeHandle()
    stopped = handle.stop_result
    handle.stop_result = None
    handle.blocking = SimpleNamespace(task_runs=object())
    handle.wsgi_app = lambda: lambda environ, start_response: []

    class Context:
        def __init__(self):
            self.startup_failure = startup_failure

        def __enter__(self):
            if startup_failure is not None:
                raise ai_base_runtime.RuntimeStartTimeout()
            return handle

        def __exit__(self, *args):
            handle.stop_result = stopped

    server = FakeServer()
    server.run = lambda: None
    monkeypatch.setattr(ai_base_runtime, 'start_blocking', lambda *args, **kwargs: Context())
    monkeypatch.setattr(project_runtime_module, 'build_project_runtime', lambda **kwargs: runtime)
    monkeypatch.setattr(waitress, 'create_server', lambda *args, **kwargs: server)
    command = Command(stdout=io.StringIO())
    monkeypatch.setattr(command, 'check', lambda: None)
    monkeypatch.setattr(command, '_install_signal_handlers', lambda event: {})
    monkeypatch.setattr(command, '_wait_for_stop', lambda *args: None)
    return command, handle, server


def run_bound(command):
    return command._run_bound_server(object(), {'stop_file': None, 'lifetime_seconds': None})


def test_command_discovery_exposes_only_the_new_metrics_host():
    get_commands.cache_clear()
    commands = get_commands()
    assert 'project_serve' not in commands
    assert commands['serve'] == 'ai_host'


@pytest.mark.parametrize('value', [0, -1, float('nan'), float('inf'), True])
def test_host_rejects_invalid_lifetime_controls(value):
    with pytest.raises(ValueError):
        Command()._lifetime(value)


def test_host_requires_an_absolute_stop_file(tmp_path):
    command = Command()
    with pytest.raises(ValueError):
        command._stop_file('relative-stop-file')
    assert command._stop_file(str(tmp_path / 'stop')) == tmp_path / 'stop'


def test_host_reports_unresolved_project_stop_and_cleans_its_registry(monkeypatch):
    runtime = ControlledRuntime(RuntimeStopResult(True, None, ('operation-1',)))
    command, handle, server = configured_command(monkeypatch, runtime)
    assert run_bound(command) == 3
    event = json.loads(command.stdout._out.getvalue())
    assert event['event'] == 'project_runtime_stopped'
    assert event['unresolved'] == ['operation-1']
    assert runtime.started and runtime.requested and runtime.waited
    assert handle.closed_http and server.closed
    assert get_project_runtime() is None and get_handle() is None


@pytest.mark.parametrize('error', [RuntimeError('synthetic startup failure'), RunError('RUN_UNAVAILABLE')])
def test_failed_project_start_still_drains_the_owned_runtime(monkeypatch, error):
    runtime = ControlledRuntime(RuntimeStopResult(True, None, ()), start_error=error)
    command, handle, _ = configured_command(monkeypatch, runtime)
    try:
        with pytest.raises(type(error)):
            run_bound(command)
        assert runtime.requested and runtime.waited
        assert handle.closed_http
        assert get_project_runtime() is None and get_handle() is None
        assert json.loads(command.stdout._out.getvalue())['stopped'] is True
    finally:
        clear_project_runtime(runtime)
        detach(handle)


def test_install_conflict_does_not_stop_or_replace_existing_owners(monkeypatch):
    existing = ControlledRuntime(RuntimeStopResult(True, None, ()))
    existing_handle = FakeHandle()
    candidate = ControlledRuntime(RuntimeStopResult(True, None, ()))
    command, _, _ = configured_command(monkeypatch, candidate)
    install_project_runtime(existing)
    attach(existing_handle)
    try:
        with pytest.raises((RunError, ai_base_runtime.RuntimeBusy)):
            run_bound(command)
        assert get_project_runtime() is existing
        assert get_handle() is existing_handle
        assert not existing.requested and not candidate.started and not candidate.requested
    finally:
        clear_project_runtime(existing)
        detach(existing_handle)


@pytest.mark.parametrize('completed', [False, True])
def test_startup_rollback_outcome_controls_cleanup_failure(monkeypatch, completed):
    from project_management.app.api.task_runtime import LocalRuntimeCleanupError

    rollback = ai_base_runtime.StopResult(
        completed, not completed, completed, (),
        () if completed else ('loop_thread',), () if completed else ('stop_timeout',), 0.01,
    )
    failure = ai_base_runtime.StartupFailure(
        reason_code='start_timeout', state_lock_released=completed,
        loop_thread_joined=completed, rollback_result=rollback,
    )
    runtime = ControlledRuntime(RuntimeStopResult(True, None, ()))
    command, _, _ = configured_command(monkeypatch, runtime, startup_failure=failure)
    expected = ai_base_runtime.RuntimeStartTimeout if completed else LocalRuntimeCleanupError
    with pytest.raises(expected):
        run_bound(command)
    assert not runtime.started
    assert get_project_runtime() is None and get_handle() is None


@pytest.mark.parametrize('code', [3, 130])
def test_fatal_host_exit_flushes_output_without_waiting_for_non_daemon_threads(tmp_path, code):
    runner = Path(__file__).resolve().parents[2] / 'scripts/validation/run_report_authoring_tests.py'
    script = """
import runpy, sys, threading
from pathlib import Path
scope = runpy.run_path(sys.argv[1])
scope['run_tests'].__globals__['ROOT'] = Path(sys.argv[2])
def exit_owned_process(arguments):
    from ai_host.management.commands.serve import Command
    threading.Thread(target=threading.Event().wait, daemon=False).start()
    print('owned-exit-output', end='')
    Command()._exit(int(sys.argv[3]))
scope['pytest'].main = exit_owned_process
scope['run_tests']([])
"""
    result = subprocess.run(
        [sys.executable, '-I', '-c', script, str(runner), str(tmp_path), str(code)],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == code, result.stderr
    assert 'owned-exit-output' in result.stdout

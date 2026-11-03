import importlib
import io
import json
import uuid

import pytest
from django.core.management.base import CommandError

from project_management.app.api.project_runs import RunError, RuntimeStopResult


class ControlledRuntime:
    def __init__(self, stop_result, *, start_error=None, stop_error=None):
        self.stop_result = stop_result
        self.start_error = start_error
        self.stop_error = stop_error
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True
        if self.start_error is not None:
            raise self.start_error

    def stop(self, timeout_seconds):
        self.stopped = True
        if self.stop_error is not None:
            raise self.stop_error
        return self.stop_result


class ControlledServeCommand:
    def __init__(self, module, runtime, events, *, serve_error=None, install_error=None):
        self.module = module
        self.runtime = runtime
        self.events = events
        self.serve_error = serve_error
        self.install_error = install_error
        self.stdout = io.StringIO()
        self.stderr = io.StringIO()

    def __enter__(self):
        self.originals = (
            self.module.build_project_runtime,
            self.module.install_project_runtime,
            self.module.clear_project_runtime,
            self.module.get_internal_wsgi_application,
            self.module.StaticFilesHandler,
            self.module.Command._serve,
        )
        self.module.build_project_runtime = lambda: self.runtime
        self.module.install_project_runtime = self.install
        self.module.clear_project_runtime = self.clear
        self.module.get_internal_wsgi_application = lambda: 'wsgi-app'
        self.module.StaticFilesHandler = lambda app: ('static', app)
        self.module.Command._serve = self.serve
        return self

    def __exit__(self, exc_type, exc, traceback):
        (
            self.module.build_project_runtime,
            self.module.install_project_runtime,
            self.module.clear_project_runtime,
            self.module.get_internal_wsgi_application,
            self.module.StaticFilesHandler,
            self.module.Command._serve,
        ) = self.originals

    def install(self, runtime):
        if self.install_error is not None:
            raise self.install_error
        self.events.append(('install', runtime))
        return runtime

    def clear(self, runtime):
        self.events.append(('clear', runtime))

    def serve(self, host, port, application, stop_file, lifetime_seconds):
        self.events.append(('serve', host, port, application, stop_file, lifetime_seconds))
        if self.serve_error is not None:
            raise self.serve_error

    def command(self):
        command = self.module.Command(stdout=self.stdout, stderr=self.stderr)
        command.handle(host='127.0.0.1', port=8023, stop_file=None, lifetime_seconds=1)

    def output_event(self):
        return json.loads(self.stdout.getvalue().strip())


def test_project_serve_validates_trusted_shutdown_controls(tmp_path):
    command = importlib.import_module('project_management.management.commands.project_serve').Command()
    stop_file = tmp_path / 'stop'

    with pytest.raises(CommandError):
        command._stop_file('relative-stop-file')
    with pytest.raises(CommandError):
        command._lifetime(0)

    assert command._stop_file(str(stop_file)) == stop_file
    assert command._lifetime(5) == 5


def test_project_serve_emits_stop_event_and_nonzero_on_unresolved(monkeypatch):
    module = importlib.import_module('project_management.management.commands.project_serve')
    unresolved = str(uuid.uuid4())
    runtime = ControlledRuntime(RuntimeStopResult(True, None, (unresolved,)))
    events = []
    with ControlledServeCommand(module, runtime, events) as harness:
        with pytest.raises(CommandError):
            harness.command()
        event = harness.output_event()

    assert event == {
        'schema_version': 1,
        'event': 'project_runtime_stopped',
        'stopped': True,
        'active_operation_id': None,
        'unresolved': [unresolved],
    }
    assert runtime.started is True
    assert runtime.stopped is True
    assert ('clear', runtime) in events


def test_project_serve_cleans_registry_on_startup_failure_and_not_install_conflict(monkeypatch):
    module = importlib.import_module('project_management.management.commands.project_serve')
    runtime = ControlledRuntime(RuntimeStopResult(True, None, ()), start_error=RuntimeError('startup failed'))
    events = []
    with ControlledServeCommand(module, runtime, events) as harness:
        with pytest.raises(CommandError):
            harness.command()
        event = harness.output_event()

    assert event['event'] == 'project_runtime_stopped'
    assert runtime.stopped is True
    assert ('clear', runtime) in events

    conflict_events = []
    conflict_runtime = ControlledRuntime(RuntimeStopResult(True, None, ()))
    with ControlledServeCommand(
        module,
        conflict_runtime,
        conflict_events,
        install_error=RunError('RUN_BUSY'),
    ) as harness:
        with pytest.raises(CommandError):
            harness.command()

    assert conflict_runtime.started is False
    assert conflict_runtime.stopped is False
    assert conflict_events == []

from contextlib import contextmanager
from dataclasses import dataclass
from io import StringIO
from types import SimpleNamespace

import pytest

from project_management.management.commands import project_run


@dataclass
class Result:
    state: str


def test_execute_local_owns_a_port_context_and_injects_it_into_the_real_factory_boundary(monkeypatch):
    events = []
    port = object()
    resolver = lambda *args: None
    runtime = SimpleNamespace(run_service=SimpleNamespace(notifier=lambda *args: None))

    @contextmanager
    def local_port():
        events.append('enter')
        try:
            yield SimpleNamespace(task_runs=port, principal_resolver=resolver)
        finally:
            events.append('exit')

    def build(*, task_runs, principal_resolver):
        assert task_runs is port and principal_resolver is resolver
        events.append('build')
        return runtime

    monkeypatch.setattr(project_run, 'get_project_runtime', lambda: None)
    monkeypatch.setattr(project_run, 'open_local_task_run_port', local_port, raising=False)
    monkeypatch.setattr(project_run, 'build_project_runtime', build)
    command = project_run.Command(stdout=StringIO())
    monkeypatch.setattr(command, '_execute', lambda *args: Result('draft_ready'))
    command.handle(operation='start', execute_local=True)
    assert events == ['enter', 'build', 'exit']
    assert '"draft_ready"' in command.stdout._out.getvalue()


def test_local_runtime_cleanup_failure_reports_json_before_forced_exit(monkeypatch):
    from project_management.app.api.task_runtime import LocalRuntimeCleanupError

    @contextmanager
    def failed_cleanup():
        yield SimpleNamespace(task_runs=object(), principal_resolver=lambda *args: None)
        raise LocalRuntimeCleanupError()

    monkeypatch.setattr(project_run, 'get_project_runtime', lambda: None)
    monkeypatch.setattr(project_run, 'open_local_task_run_port', failed_cleanup)
    monkeypatch.setattr(project_run, 'build_project_runtime', lambda **kwargs: SimpleNamespace(run_service=object()))
    stdout, stderr = StringIO(), StringIO()
    command = project_run.Command(stdout=stdout, stderr=stderr)
    monkeypatch.setattr(command, '_execute', lambda *args: Result('draft_ready'))

    def exit_failed():
        assert '"error"' in stdout.getvalue()
        assert 'project_run cleanup failed.' in stderr.getvalue()
        raise SystemExit(3)

    monkeypatch.setattr(command, '_exit_after_cleanup_failure', exit_failed)
    with pytest.raises(SystemExit) as error:
        command.handle(operation='start', execute_local=True)
    assert error.value.code == 3

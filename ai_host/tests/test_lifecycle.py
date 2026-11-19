from types import SimpleNamespace
import threading

import pytest

from ai_base_runtime import StopResult, HttpCloseResult
from ai_host.lifecycle import StopOutcome, stop_owned_resources
from ai_host.serve_control import StopBudget
from project_management.app.domain.run_contracts import RuntimeStopResult


class FakeHandle:
    def __init__(self, *, http_result=None, stop_result=None):
        self.http_result = http_result or HttpCloseResult(True, 0, 0, 0, (), (), (), 0.01)
        self.stop_result = stop_result or StopResult(True, False, True, (), (), (), 0.01)
        self.closed_http = False

    def close_http(self):
        self.closed_http = True
        return self.http_result


class FakeServer:
    def __init__(self):
        self.closed = False
        self.task_dispatcher = SimpleNamespace(
            active_count=0, threads=set(), shutdown=lambda cancel_pending, timeout: True,
        )
        self.trigger = SimpleNamespace(pull_trigger=lambda callback: callback())
        self.socket = None

    def del_channel(self):
        return None

    def close(self):
        self.closed = True


class FakeThread:
    def __init__(self, alive=False):
        self._alive = alive

    def join(self, timeout):
        return None

    def is_alive(self):
        return self._alive


class FakeRuntime:
    def __init__(self, result):
        self.requested = False
        self.waited = False
        self.result = result

    def request_stop(self):
        self.requested = True
        return self.result.active_operation_id is not None

    def wait_stopped(self, timeout_seconds):
        self.waited = True
        return self.result


def test_shouldDeriveStopOutcomeFromActualOwners():
    project_result = RuntimeStopResult(True, None, ())
    project_runtime = FakeRuntime(project_result)
    handle = FakeHandle()
    server = FakeServer()

    outcome = stop_owned_resources(
        handle=handle,
        server=server,
        server_thread=FakeThread(),
        project_runtime=project_runtime,
        budget=StopBudget(),
    )

    assert outcome == StopOutcome(
        exit_code=0,
        project_result=project_result,
        http_result=handle.http_result,
        runtime_result=handle.stop_result,
        cleanup_errors=(),
    )
    assert handle.closed_http is True
    assert server.closed is True
    assert project_runtime.requested is True
    assert project_runtime.waited is True


def test_shouldReportAbsentProjectRuntimeWithoutInventingStoppedEvent():
    handle = FakeHandle()

    outcome = stop_owned_resources(
        handle=handle,
        server=FakeServer(),
        server_thread=FakeThread(),
        project_runtime=None,
        budget=StopBudget(),
    )

    assert outcome.exit_code == 0
    assert outcome.project_result is None


def test_shouldFailCleanupWhenPublicRuntimeStopResultIsIncomplete():
    stop_result = StopResult(False, True, False, ('run-1',), ('loop-thread',), ('stop_timeout',), 1.0)
    handle = FakeHandle(stop_result=stop_result)

    outcome = stop_owned_resources(
        handle=handle,
        server=FakeServer(),
        server_thread=FakeThread(),
        project_runtime=None,
        budget=StopBudget(),
    )

    assert outcome.exit_code == 3
    assert outcome.runtime_result == stop_result
    assert 'runtime_stop_incomplete' in outcome.cleanup_errors


@pytest.mark.parametrize("completed", [True, False])
def test_ended_runtime_does_not_schedule_http_on_a_closed_loop(completed):
    handle = FakeHandle(stop_result=StopResult(completed, not completed, completed, (), (), (), 0.01))
    handle.ended = threading.Event()
    handle.ended.set()

    def unavailable_http():
        raise AssertionError("closed runtime loop must not receive another coroutine")

    handle.close_http = unavailable_http
    runtime = FakeRuntime(RuntimeStopResult(True, None, ()))
    server = FakeServer()
    outcome = stop_owned_resources(
        handle=handle, server=server, server_thread=FakeThread(),
        project_runtime=runtime, budget=StopBudget(),
    )
    assert server.closed and runtime.requested and runtime.waited
    assert outcome.http_result is None
    assert outcome.exit_code == (0 if completed else 3)
    assert "http_close_failed" not in outcome.cleanup_errors

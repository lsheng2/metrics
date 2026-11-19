from dataclasses import dataclass
import threading
import time

from ai_host.settings import HOST_WAIT_SLICE_SECONDS, PROJECT_STOP_SECONDS



@dataclass(frozen=True, slots=True)
class StopOutcome:
    exit_code: int
    project_result: object | None
    http_result: object | None
    runtime_result: object | None
    cleanup_errors: tuple[str, ...]


def stop_owned_resources(*, handle, server, server_thread, project_runtime, budget, requests=None):
    errors = []
    http_result = None
    project_result = None
    runtime_result = getattr(handle, 'stop_result', None)
    if requests is not None:
        requests.stop_accepting()
    if server is not None:
        try:
            _stop_listener(server, budget.http_close_deadline)
        except Exception:
            errors.append('listener_close_failed')
    ended = getattr(handle, 'ended', None)
    # An ended loop cannot accept HTTP-close work. The context's final stop
    # still owns runtime cleanup and its StopResult decides completeness.
    if ended is None or not ended.is_set():
        try:
            http_result = handle.close_http()
            if http_result is None or not http_result.completed:
                errors.append('http_close_incomplete')
            if time.monotonic() > budget.http_close_deadline:
                errors.append('http_close_deadline')
        except Exception:
            errors.append('http_close_failed')
    if requests is not None:
        try:
            if not requests.wait_empty(budget.drain_deadline):
                errors.append('requests_drain_incomplete')
        except Exception:
            errors.append('requests_drain_failed')
    if server is not None:
        try:
            _flush_waitress_channels(server, budget.flush_deadline)
        except Exception:
            errors.append('server_flush_failed')
        try:
            _close_server(server, budget.server_deadline)
        except Exception:
            errors.append('server_close_failed')
    if server_thread is not None:
        if not join_until(server_thread, budget.server_deadline):
            errors.append('server_thread_alive')
    if project_runtime is not None:
        try:
            budget.project_requested(active=project_runtime.request_stop())
        except Exception:
            errors.append('project_runtime_request_stop_failed')
        try:
            project_result = project_runtime.wait_stopped(PROJECT_STOP_SECONDS)
            if not project_result.stopped or project_result.unresolved:
                errors.append('project_runtime_incomplete')
        except Exception:
            errors.append('project_runtime_stop_failed')
        finally:
            budget.project_returned()
        if project_result is None:
            from project_management.app.domain.run_contracts import RuntimeStopResult
            project_result = RuntimeStopResult(False, None, ())
    runtime_result = getattr(handle, 'stop_result', runtime_result)
    if runtime_result is not None and not runtime_result.completed:
        errors.append('runtime_stop_incomplete')
    return StopOutcome(
        exit_code=3 if errors else 0,
        project_result=project_result,
        http_result=http_result,
        runtime_result=runtime_result,
        cleanup_errors=tuple(errors),
    )


def run_http_server(server, errors):
    try:
        server.run()
    except Exception:
        errors.append('http_server_failed')
    finally:
        try:
            server.task_dispatcher.shutdown(cancel_pending=True, timeout=HOST_WAIT_SLICE_SECONDS)
            if server.task_dispatcher.threads:
                errors.append('dispatcher_threads_alive')
        except Exception:
            errors.append('dispatcher_shutdown_failed')


def join_until(thread, deadline):
    while thread.is_alive():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        thread.join(min(HOST_WAIT_SLICE_SECONDS, remaining))
    return True


def _stop_listener(server, deadline):
    from waitress.wasyncore import dispatcher
    _on_waitress_loop(server, dispatcher.close, deadline)


def _flush_waitress_channels(server, deadline):
    while server.task_dispatcher.active_count and time.monotonic() < deadline:
        time.sleep(0.025)
    _on_waitress_loop(server, _mark_waitress_channels_close_when_flushed, deadline)
    _wait_for_no_active_channels(server, deadline)


def _close_server(server, deadline):
    def close_all(owner):
        _force_close_waitress_channels(owner)
        owner.close()

    _on_waitress_loop(server, close_all, deadline)


def _mark_waitress_channels_close_when_flushed(server) -> None:
    for channel in tuple(getattr(server, 'active_channels', {}).values()):
        lock = getattr(channel, 'requests_lock', None)
        if lock is None:
            channel.close_when_flushed = True
            continue
        with lock:
            channel.close_when_flushed = True


def _force_close_waitress_channels(server) -> None:
    for channel in tuple(getattr(server, 'active_channels', {}).values()):
        close = getattr(channel, 'handle_close', None) or getattr(channel, 'close', None)
        if close is not None:
            close()


def _wait_for_no_active_channels(server, deadline: float) -> None:
    while getattr(server, 'active_channels', None) and time.monotonic() < deadline:
        time.sleep(0.025)


def _on_waitress_loop(server, callback, deadline: float) -> None:
    completed = threading.Event()
    errors = []

    def thunk():
        try:
            callback(server)
        except Exception as error:
            errors.append(error)
        finally:
            completed.set()

    server.trigger.pull_trigger(thunk)
    while not completed.is_set():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('waitress_callback_timeout')
        completed.wait(min(HOST_WAIT_SLICE_SECONDS, remaining))
    if errors:
        raise errors[0]

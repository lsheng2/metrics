from dataclasses import dataclass
import threading
import time


SERVER_THREAD_STOP_SECONDS = 2.0


@dataclass(frozen=True, slots=True)
class StopOutcome:
    exit_code: int
    project_result: object | None
    http_result: object | None
    runtime_result: object | None
    cleanup_errors: tuple[str, ...]


def stop_owned_resources(*, handle, server, server_thread, project_runtime):
    errors = []
    http_result = None
    project_result = None
    runtime_result = getattr(handle, 'stop_result', None)
    try:
        http_result = handle.close_http()
        if http_result is None or not http_result.completed:
            errors.append('http_close_incomplete')
    except Exception:
        errors.append('http_close_failed')
    if server is not None:
        server_deadline = time.monotonic() + SERVER_THREAD_STOP_SECONDS
        try:
            _drain_waitress_channels(server, server_deadline)
            server.close()
            dispatcher = getattr(server, 'task_dispatcher', None)
            if dispatcher is not None:
                dispatcher.shutdown(cancel_pending=True, timeout=0.5)
        except Exception:
            errors.append('server_close_failed')
    if server_thread is not None:
        timeout = max(0.0, (server_deadline if server is not None else time.monotonic() + SERVER_THREAD_STOP_SECONDS) - time.monotonic())
        server_thread.join(timeout)
        if server_thread.is_alive():
            errors.append('server_thread_alive')
    if project_runtime is not None:
        try:
            project_runtime.request_stop()
            project_result = project_runtime.wait_stopped(620)
            if not project_result.stopped or project_result.unresolved:
                errors.append('project_runtime_incomplete')
        except Exception:
            errors.append('project_runtime_stop_failed')
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


def _drain_waitress_channels(server, deadline: float) -> None:
    channels = getattr(server, 'active_channels', None)
    if not channels:
        return
    _on_waitress_loop(server, _mark_waitress_channels_close_when_flushed, deadline)
    _wait_for_no_active_channels(server, min(deadline, time.monotonic() + 0.5))
    if channels:
        _on_waitress_loop(server, _force_close_waitress_channels, deadline)
        _wait_for_no_active_channels(server, deadline)


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
    trigger = getattr(server, 'trigger', None)
    pull_trigger = getattr(trigger, 'pull_trigger', None)
    if pull_trigger is None:
        callback(server)
        return
    completed = threading.Event()

    def thunk():
        try:
            callback(server)
        finally:
            completed.set()

    pull_trigger(thunk)
    completed.wait(max(0.0, min(0.5, deadline - time.monotonic())))

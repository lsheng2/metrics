from dataclasses import dataclass


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
        try:
            server.close()
            server.task_dispatcher.shutdown(cancel_pending=True, timeout=0.5)
        except Exception:
            errors.append('server_close_failed')
    if server_thread is not None:
        server_thread.join(2.0)
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

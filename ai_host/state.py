from dataclasses import dataclass, replace
import threading


@dataclass(frozen=True, slots=True)
class LifecycleSnapshot:
    phase: str = 'stopped'
    handle: object | None = None
    error_codes: tuple[str, ...] = ()
    http_result: object | None = None
    project_result: object | None = None
    runtime_result: object | None = None


_LOCK = threading.RLock()
_LIFECYCLE = LifecycleSnapshot()


def begin_start():
    global _LIFECYCLE
    with _LOCK:
        if _LIFECYCLE.handle is not None:
            from ai_base_runtime import RuntimeBusy
            raise RuntimeBusy()
        _LIFECYCLE = LifecycleSnapshot(phase='starting')


def attach(handle):
    global _LIFECYCLE
    with _LOCK:
        if _LIFECYCLE.handle is not None and _LIFECYCLE.handle is not handle:
            from ai_base_runtime import RuntimeBusy
            raise RuntimeBusy()
        _LIFECYCLE = LifecycleSnapshot(phase='running', handle=handle)
    return handle


def detach(handle=None):
    global _LIFECYCLE
    with _LOCK:
        if handle is None or _LIFECYCLE.handle is handle:
            _LIFECYCLE = replace(_LIFECYCLE, handle=None)


def get_handle():
    with _LOCK:
        return _LIFECYCLE.handle


def get_lifecycle():
    with _LOCK:
        return _LIFECYCLE


def begin_stop(handle):
    global _LIFECYCLE
    with _LOCK:
        if _LIFECYCLE.handle is handle and _LIFECYCLE.phase != 'failed':
            _LIFECYCLE = replace(_LIFECYCLE, phase='stopping')


def mark_failed(code):
    global _LIFECYCLE
    with _LOCK:
        _LIFECYCLE = replace(
            _LIFECYCLE, phase='failed',
            error_codes=tuple(dict.fromkeys((*_LIFECYCLE.error_codes, code))),
        )


def record_stop(outcome):
    global _LIFECYCLE
    with _LOCK:
        failed = _LIFECYCLE.phase == 'failed' or outcome.exit_code != 0
        _LIFECYCLE = replace(
            _LIFECYCLE, phase='failed' if failed else 'stopped',
            error_codes=tuple(dict.fromkeys((*_LIFECYCLE.error_codes, *outcome.cleanup_errors))),
            http_result=outcome.http_result, project_result=outcome.project_result,
            runtime_result=outcome.runtime_result,
        )


def record_startup_failure(code, rollback_result=None):
    global _LIFECYCLE
    with _LOCK:
        mark_failed(code)
        _LIFECYCLE = replace(_LIFECYCLE, runtime_result=rollback_result)


def get_running_handle():
    with _LOCK:
        handle = _LIFECYCLE.handle
        if handle is None or _LIFECYCLE.phase != 'running':
            return None
        if handle.ended.is_set():
            mark_failed(handle.end_code or 'runtime_not_running')
            return None
        return handle

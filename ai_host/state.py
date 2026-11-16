import threading


_LOCK = threading.RLock()
_HANDLE = None
_STOPPING = False


def attach(handle):
    global _HANDLE, _STOPPING
    with _LOCK:
        if _HANDLE is not None and _HANDLE is not handle:
            from ai_base_runtime import RuntimeBusy
            raise RuntimeBusy()
        _HANDLE = handle
        _STOPPING = False
    return handle


def detach(handle=None):
    global _HANDLE
    with _LOCK:
        if handle is None or _HANDLE is handle:
            _HANDLE = None


def get_handle():
    with _LOCK:
        return _HANDLE


def begin_stop(handle):
    global _STOPPING
    with _LOCK:
        if _HANDLE is handle:
            _STOPPING = True


def get_running_handle():
    with _LOCK:
        if _HANDLE is None or _STOPPING or _HANDLE.ended.is_set():
            return None
        return _HANDLE

import threading


_LOCK = threading.RLock()
_HANDLE = None


def attach(handle):
    global _HANDLE
    with _LOCK:
        if _HANDLE is not None and _HANDLE is not handle:
            from ai_base_runtime import RuntimeBusy
            raise RuntimeBusy()
        _HANDLE = handle
    return handle


def detach(handle=None):
    global _HANDLE
    with _LOCK:
        if handle is None or _HANDLE is handle:
            _HANDLE = None


def get_handle():
    with _LOCK:
        return _HANDLE

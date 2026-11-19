"""Observe an existing process without starting or registering another owner."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from collections.abc import Callable
import subprocess
import sys
import time


@dataclass(frozen=True, slots=True)
class ProcessExitObservation:
    read: Callable[[], int | None]
    wait: Callable[[float], bool] | None = None

    def __call__(self):
        return self.read()


@contextmanager
def observe_process_exit(pid: int):
    from . import platform_ops

    with platform_ops._SPAWNED_CHILDREN_LOCK:
        child = platform_ops._SPAWNED_CHILDREN.get(pid)
    if child is not None:
        def wait_child(seconds):
            deadline = time.monotonic() + max(0, seconds)
            while True:
                remaining = max(0, deadline - time.monotonic())
                try:
                    child.wait(timeout=min(0.5, remaining))
                    return True
                except subprocess.TimeoutExpired:
                    if time.monotonic() >= deadline:
                        return False

        yield ProcessExitObservation(child.poll, wait_child)
        return
    if sys.platform != "win32" or pid <= 0:
        yield ProcessExitObservation(lambda: None)
        return

    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(0x1000 | 0x00100000, False, pid)

    def read_exit():
        # A retained handle remains usable after a separately launched service exits.
        if not handle or kernel32.WaitForSingleObject(handle, 0) != 0:
            return None
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return None
        return int(code.value)

    def wait_exit(seconds):
        deadline = time.monotonic() + max(0, seconds)
        while True:
            remaining = max(0, deadline - time.monotonic())
            status = kernel32.WaitForSingleObject(handle, min(500, max(0, int(remaining * 1000))))
            if status == 0:
                return True
            if status != 258:
                raise OSError(ctypes.get_last_error(), "Process wait failed")
            if time.monotonic() >= deadline:
                return False

    try:
        yield ProcessExitObservation(read_exit, wait_exit if handle else None)
    finally:
        if handle:
            kernel32.CloseHandle(handle)

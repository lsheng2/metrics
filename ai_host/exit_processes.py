"""Read-only Windows child inventory, without launching a helper process."""
import ctypes
from ctypes import wintypes
import os
import sys


class ProcessEntry(ctypes.Structure):
    _fields_ = [
        ('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD),
        ('th32ProcessID', wintypes.DWORD), ('th32DefaultHeapID', ctypes.c_size_t),
        ('th32ModuleID', wintypes.DWORD), ('cntThreads', wintypes.DWORD),
        ('th32ParentProcessID', wintypes.DWORD), ('pcPriClassBase', wintypes.LONG),
        ('dwFlags', wintypes.DWORD), ('szExeFile', wintypes.WCHAR * 260),
    ]


def _windows_api():
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    signatures = (
        ('CreateToolhelp32Snapshot', [wintypes.DWORD, wintypes.DWORD], wintypes.HANDLE),
        ('Process32FirstW', [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)], wintypes.BOOL),
        ('Process32NextW', [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)], wintypes.BOOL),
        ('OpenProcess', [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
        ('GetProcessTimes', [wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)], wintypes.BOOL),
        ('CloseHandle', [wintypes.HANDLE], wintypes.BOOL),
    )
    for name, args, result in signatures:
        function = getattr(api, name)
        function.argtypes, function.restype = args, result
    return api


def _created_at(api, pid):
    handle = api.OpenProcess(0x1000, False, pid)
    if not handle:
        if ctypes.get_last_error() == 87:
            return None
        raise ctypes.WinError(ctypes.get_last_error())
    values = [wintypes.FILETIME() for _ in range(4)]
    try:
        if not api.GetProcessTimes(handle, *(ctypes.byref(value) for value in values)):
            raise ctypes.WinError(ctypes.get_last_error())
        return (values[0].dwHighDateTime << 32) | values[0].dwLowDateTime
    finally:
        api.CloseHandle(handle)


def living_children():
    if sys.platform != 'win32':
        raise NotImplementedError('Host process inventory is not yet qualified on this platform')
    api = _windows_api()
    snapshot = api.CreateToolhelp32Snapshot(0x2, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    parents = {}
    try:
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        present = api.Process32FirstW(snapshot, ctypes.byref(entry))
        while present:
            parents[int(entry.th32ProcessID)] = int(entry.th32ParentProcessID)
            present = api.Process32NextW(snapshot, ctypes.byref(entry))
        if ctypes.get_last_error() != 18:
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        api.CloseHandle(snapshot)
    current = os.getpid()
    created = {current: _created_at(api, current)}
    children = []
    pending = set(parents) - {current}
    while True:
        found = [pid for pid in pending if parents[pid] in created]
        if not found:
            return children
        for pid in found:
            pending.remove(pid)
            started = _created_at(api, pid)
            if started is None or started < created[parents[pid]]:
                continue
            created[pid] = started
            children.append({'pid': pid, 'parent_pid': parents[pid], 'created': started})

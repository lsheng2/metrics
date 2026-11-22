"""Private native process-window capture for Windows performance observation."""
from __future__ import annotations

from contextlib import AbstractContextManager
import ctypes
from ctypes import wintypes
from copy import deepcopy
import re
import sys

from scripts.validation.windows_qualification_inputs import QualificationError


PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SYNCHRONIZE = 0x00100000
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 258
STILL_ACTIVE = 259
SCHEMA_VERSION = 1


def _is_target(row: dict) -> bool:
    name = str(row.get("name") or "").casefold()
    return name.startswith(("python", "py.", "git"))


def _filetime_value(value) -> int:
    return int((value.dwHighDateTime << 32) | value.dwLowDateTime)


def _set_signature(function, argtypes, restype) -> None:
    try:
        function.argtypes = argtypes
        function.restype = restype
    except AttributeError:
        pass


def _configure_api(api):
    from ai_host.exit_processes import ProcessEntry

    for name, args, result in (
        ("CreateToolhelp32Snapshot", [wintypes.DWORD, wintypes.DWORD], wintypes.HANDLE),
        ("Process32FirstW", [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)], wintypes.BOOL),
        ("Process32NextW", [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)], wintypes.BOOL),
    ):
        if hasattr(api, name):
            _set_signature(getattr(api, name), args, result)
    _set_signature(api.OpenProcess, (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD), wintypes.HANDLE)
    _set_signature(api.GetProcessTimes, (wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)), wintypes.BOOL)
    if hasattr(api, "WaitForSingleObject"):
        _set_signature(api.WaitForSingleObject, (wintypes.HANDLE, wintypes.DWORD), wintypes.DWORD)
    if hasattr(api, "GetExitCodeProcess"):
        _set_signature(api.GetExitCodeProcess, (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)), wintypes.BOOL)
    _set_signature(api.CloseHandle, (wintypes.HANDLE,), wintypes.BOOL)
    return api


def _default_api():
    if sys.platform != "win32":
        raise ValueError("Only Windows process-window capture is authorized")
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    return _configure_api(api)


def _native_creation(api, handle: int) -> int | None:
    values = [wintypes.FILETIME() for _ in range(4)]
    if not api.GetProcessTimes(handle, *(ctypes.byref(value) for value in values)):
        return None
    return _filetime_value(values[0])


class ProcessWindowCapture(AbstractContextManager):
    """Retain read-only process handles across the CIM detail window."""

    def __init__(self, processes, *, api=None):
        self._processes = [dict(row) for row in processes]
        self._api = _configure_api(api) if api is not None else _default_api()
        self._handles: dict[int, int] = {}
        self._facts: dict[int, dict] = {}
        self._closed = False

    def __enter__(self):
        try:
            for row in self._processes:
                self._open(row)
        except BaseException:
            self._close_without_terminal()
            raise
        return self

    def _open(self, row):
        pid = int(row["pid"])
        fact = {"schema_version": SCHEMA_VERSION, "pid": pid, "parent_pid": row.get("parent_pid"),
                "image_name": row.get("name") or "", "native_creation": None, "handle_opened": False,
                "terminal_exit_code": None, "terminal_running": None, "terminal_observed": False,
                "handle_closed": False}
        self._facts[pid] = fact
        handle = self._api.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid)
        if not handle:
            fact["handle_error"] = "open_failed"
            return
        self._handles[pid] = int(handle)
        fact["handle_opened"] = True
        fact["native_creation"] = _native_creation(self._api, handle)
        if fact["native_creation"] is None:
            fact["handle_error"] = "native_creation_unavailable"

    def facts(self) -> dict[int, dict]:
        return deepcopy(self._facts)

    def finalize(self) -> dict[int, dict]:
        if self._closed:
            self._require_released()
            return self.facts()
        for pid, handle in list(self._handles.items()):
            fact = self._facts[pid]
            try:
                try:
                    self._observe_terminal(handle, fact)
                except Exception as error:
                    fact["terminal_error"] = type(error).__name__
            finally:
                self._close_one(pid, handle)
        self._closed = True
        self._require_released()
        return self.facts()

    def _close_without_terminal(self):
        for pid, handle in list(self._handles.items()):
            self._close_one(pid, handle)
        self._closed = True
        self._require_released()

    def _require_released(self):
        if any(row.get("handle_close_error") for row in self._facts.values()):
            raise QualificationError("native process observation handle release failed")

    def _close_one(self, pid: int, handle: int) -> None:
        fact = self._facts[pid]
        try:
            closed = self._api.CloseHandle(handle)
            fact["handle_closed"] = bool(closed)
            if not closed:
                fact["handle_close_error"] = "close_failed"
        except Exception as error:
            fact["handle_closed"] = False
            fact["handle_close_error"] = type(error).__name__
        finally:
            self._handles.pop(pid, None)

    def _observe_terminal(self, handle: int, fact: dict) -> None:
        wait = getattr(self._api, "WaitForSingleObject", None)
        exit_code = getattr(self._api, "GetExitCodeProcess", None)
        if wait is None or exit_code is None:
            fact["terminal_error"] = "terminal_api_unavailable"
            return
        status = int(wait(handle, 0))
        if status == WAIT_TIMEOUT:
            fact["terminal_running"] = True
            return
        if status != WAIT_OBJECT_0:
            fact["terminal_error"] = f"wait_status:{status}"
            return
        code = wintypes.DWORD()
        if not exit_code(handle, ctypes.byref(code)):
            fact["terminal_error"] = "exit_code_unavailable"
            return
        fact["terminal_exit_code"] = int(code.value)
        fact["terminal_running"] = fact["terminal_exit_code"] == STILL_ACTIVE
        fact["terminal_observed"] = fact["terminal_running"] is False

    def __exit__(self, exc_type, exc, traceback):
        self.finalize()
        return False


def capture_process_window(processes, *, api=None) -> ProcessWindowCapture:
    return ProcessWindowCapture([row for row in processes if _is_target(row)], api=api)


def native_process_rows_by_pid(pids, *, api=None) -> dict[int, dict]:
    from ai_host.exit_processes import ProcessEntry

    wanted = {int(pid) for pid in pids if int(pid) > 0}
    if not wanted:
        return {}
    api = _configure_api(api) if api is not None else _default_api()
    if not hasattr(api, "CreateToolhelp32Snapshot"):
        return {}
    snapshot = api.CreateToolhelp32Snapshot(0x2, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    rows = {}
    try:
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        present = api.Process32FirstW(snapshot, ctypes.byref(entry))
        while present:
            pid = int(entry.th32ProcessID)
            if pid in wanted:
                rows[pid] = {
                    "pid": pid,
                    "parent_pid": int(entry.th32ParentProcessID),
                    "name": str(entry.szExeFile),
                    "threads": int(entry.cntThreads),
                }
            present = api.Process32NextW(snapshot, ctypes.byref(entry))
        if ctypes.get_last_error() != 18:
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        try:
            released = api.CloseHandle(snapshot)
        except Exception as error:
            raise QualificationError("native census handle release failed") from error
        if not released:
            raise QualificationError("native census handle release failed")
    return rows


def native_process_fact(pid: int, *, parent_pid=None, image_name: str = "", api=None) -> dict:
    row = native_process_rows_by_pid([int(pid)], api=api).get(int(pid), {
        "pid": int(pid), "parent_pid": parent_pid, "name": image_name or "",
    })
    with ProcessWindowCapture([row], api=api) as capture:
        return capture.finalize().get(int(pid), {})


def registration_key(pid, native_creation):
    if not all(type(value) is int and value > 0 for value in (pid, native_creation)):
        return None
    return pid, native_creation


def valid_owner_registration(fact, current_run_id):
    if not isinstance(fact, dict) or type(fact.get("schema_version")) is not int or fact["schema_version"] != 1:
        return False
    key = registration_key(fact.get("pid"), fact.get("native_creation"))
    fingerprint = fact.get("command_fingerprint")
    return bool(
        key and isinstance(current_run_id, str) and current_run_id
        and fact.get("run_id") == current_run_id
        and fact.get("owner_key") == f"{current_run_id}:{key[0]}:{key[1]}"
        and type(fact.get("parent_pid")) is int and fact["parent_pid"] > 0
        and isinstance(fact.get("image_name"), str) and fact["image_name"]
        and isinstance(fact.get("sensor_identity"), str) and fact["sensor_identity"]
        and isinstance(fingerprint, dict)
        and isinstance(fingerprint.get("sha256"), str)
        and re.fullmatch(r"[0-9a-f]{64}", fingerprint["sha256"])
    )


def owner_registrations_by_instance(facts, current_run_id):
    result = {}
    for fact in facts or ():
        if not valid_owner_registration(fact, current_run_id):
            continue
        key = registration_key(fact.get("pid"), fact.get("native_creation"))
        if key in result:
            raise QualificationError("ambiguous native owner registration")
        result[key] = fact
    return result


def terminal_resolution_fact(row, registration, command_fingerprint):
    window = row.get("process_window") if isinstance(row.get("process_window"), dict) else {}
    if row.get("sensor_error") == "process_detail_malformed" or row.get("identity"):
        return None
    if row.get("sensor_error") not in {"process_detail_missing", "process_detail_incomplete"}:
        return None
    if (
        type(window.get("schema_version")) is not int or window["schema_version"] != 1
        or window.get("handle_opened") is not True
        or window.get("handle_closed") is not True
        or not registration_key(window.get("pid"), window.get("native_creation"))
        or type(window.get("terminal_exit_code")) is not int
        or window.get("terminal_exit_code") != 0
        or window.get("terminal_running") is not False
        or window.get("terminal_observed") is not True
        or any(key in window for key in ("handle_error", "terminal_error", "handle_close_error"))
    ):
        return None
    if not valid_owner_registration(registration, registration.get("run_id")):
        return None
    if any(window.get(key) != registration.get(key) for key in ("pid", "native_creation", "parent_pid", "image_name")):
        return None
    if (row.get("pid") != registration["pid"] or row.get("parent_pid") != registration["parent_pid"]
            or row.get("name") != registration["image_name"]):
        return None
    observed = (
        command_fingerprint(row["command"]) if row.get("command") is not None
        else row.get("command_fingerprint")
    )
    if observed is not None:
        if not isinstance(observed, dict):
            return None
        if observed.get("sha256") != registration["command_fingerprint"].get("sha256"):
            return None
    return {
        "schema_version": 1,
        "decision": "owned_terminal",
        "reason": "registered_exact_terminal_exit0",
        "pid": int(row["pid"]),
        "parent_pid": row.get("parent_pid"),
        "image_name": row.get("name") or window.get("image_name") or "",
        "native_creation": window.get("native_creation"),
        "run_id": registration.get("run_id"),
        "owner_key": registration.get("owner_key"),
        "terminal_exit_code": int(window["terminal_exit_code"]),
        "terminal_running": False,
        "command_fingerprint": registration.get("command_fingerprint"),
    }

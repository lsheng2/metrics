"""Bounded native process detail reader for borrowed Windows handles."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from datetime import UTC, datetime, timedelta
import sys


PROCESS_COMMAND_LINE_INFORMATION = 60
MAX_COMMAND_INFORMATION_BYTES = 128 * 1024
IMAGE_PATH_CHARS = 32768
FILETIME_UNIX_EPOCH = 116444736000000000
FILETIME_TICKS_PER_SECOND = 10_000_000

STATUS_INVALID_INFO_CLASS = 0xC0000003
STATUS_ACCESS_DENIED = 0xC0000022
STATUS_PROCESS_IS_TERMINATING = 0xC000010A


class _UnicodeString(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.USHORT),
        ("MaximumLength", wintypes.USHORT),
        ("Buffer", ctypes.c_void_p),
    ]


class WindowsProcessDetailsApi:
    """Duck-typed native facade used by read_process_details.

    Tests may inject any object exposing GetProcessTimes,
    NtQueryInformationProcess and QueryFullProcessImageNameW with the same
    call signatures. The facade never opens or closes process handles.
    """

    def __init__(self):
        if sys.platform != "win32":
            raise OSError("native process details are only available on Windows")
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
        self.GetProcessTimes = kernel32.GetProcessTimes
        self.QueryFullProcessImageNameW = kernel32.QueryFullProcessImageNameW
        self.NtQueryInformationProcess = getattr(ntdll, "NtQueryInformationProcess", None)
        _set_signature(
            self.GetProcessTimes,
            (wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)),
            wintypes.BOOL,
        )
        _set_signature(
            self.QueryFullProcessImageNameW,
            (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)),
            wintypes.BOOL,
        )
        if self.NtQueryInformationProcess is not None:
            _set_signature(
                self.NtQueryInformationProcess,
                (wintypes.HANDLE, wintypes.ULONG, ctypes.c_void_p, wintypes.ULONG, ctypes.POINTER(wintypes.ULONG)),
                wintypes.LONG,
            )


def read_process_details(handle, native_creation, *, api=None) -> dict:
    """Read command, creation and executable details from a borrowed handle.

    On success the returned dict contains only complete identity fields:
    command_line, creation_date and executable_path. Any failed native boundary
    returns only sensor_error so callers cannot confuse partial evidence with a
    complete process identity.
    """

    if type(native_creation) is not int or native_creation <= 0:
        return _sensor_error("process_detail_creation_invalid")
    try:
        native = api if api is not None else WindowsProcessDetailsApi()
    except Exception:
        return _sensor_error("process_detail_unsupported")
    observed_creation = _query_creation(handle, native)
    if observed_creation is None:
        return _sensor_error("process_detail_creation_unavailable")
    if observed_creation != native_creation:
        return _sensor_error("process_detail_creation_mismatch")
    command = _query_command_line(handle, native)
    if isinstance(command, dict):
        return command
    executable = _query_executable_path(handle, native)
    if isinstance(executable, dict):
        return executable
    try:
        creation_date = _filetime_to_local_iso(native_creation)
    except (OverflowError, OSError, ValueError):
        return _sensor_error("process_detail_creation_unrepresentable")
    if not command or not creation_date or not executable:
        return _sensor_error("process_detail_incomplete")
    return {
        "command_line": command,
        "creation_date": creation_date,
        "executable_path": executable,
    }


def _set_signature(function, argtypes, restype) -> None:
    try:
        function.argtypes = argtypes
        function.restype = restype
    except AttributeError:
        pass


def _sensor_error(value: str) -> dict:
    return {"sensor_error": value}


def _filetime_value(value) -> int:
    return int((value.dwHighDateTime << 32) | value.dwLowDateTime)


def _query_creation(handle, api) -> int | None:
    values = [wintypes.FILETIME() for _ in range(4)]
    try:
        ok = api.GetProcessTimes(handle, *(ctypes.byref(value) for value in values))
    except Exception:
        return None
    if not ok:
        return None
    return _filetime_value(values[0])


def _filetime_to_local_iso(value: int) -> str:
    ticks_since_unix = value - FILETIME_UNIX_EPOCH
    seconds, remainder = divmod(ticks_since_unix, FILETIME_TICKS_PER_SECOND)
    microseconds = remainder // 10
    utc_value = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(seconds=seconds, microseconds=microseconds)
    return utc_value.astimezone().replace(tzinfo=None, microsecond=0).isoformat()


def _query_command_line(handle, api):
    query = getattr(api, "NtQueryInformationProcess", None)
    if query is None:
        return _sensor_error("process_detail_unsupported")
    buffer = ctypes.create_string_buffer(MAX_COMMAND_INFORMATION_BYTES)
    return_length = wintypes.ULONG(0)
    try:
        status = query(
            handle,
            PROCESS_COMMAND_LINE_INFORMATION,
            buffer,
            MAX_COMMAND_INFORMATION_BYTES,
            ctypes.byref(return_length),
        )
    except Exception:
        return _sensor_error("process_detail_unavailable")
    reported_length = int(return_length.value)
    if reported_length > MAX_COMMAND_INFORMATION_BYTES:
        return _sensor_error("process_detail_oversized")
    if status:
        return _sensor_error(_status_sensor_error(status))
    if reported_length < ctypes.sizeof(_UnicodeString):
        return _sensor_error("process_detail_malformed")
    return _parse_command_buffer(buffer, reported_length)


def _status_sensor_error(status) -> str:
    code = int(status) & 0xFFFFFFFF
    if code == STATUS_INVALID_INFO_CLASS:
        return "process_detail_unsupported"
    if code == STATUS_ACCESS_DENIED:
        return "process_detail_access_denied"
    if code == STATUS_PROCESS_IS_TERMINATING:
        return "process_detail_terminated"
    return "process_detail_unavailable"


def _parse_command_buffer(buffer, buffer_size: int):
    if buffer_size < ctypes.sizeof(_UnicodeString):
        return _sensor_error("process_detail_malformed")
    base = ctypes.addressof(buffer)
    limit = base + buffer_size
    try:
        header = _UnicodeString.from_buffer_copy(buffer.raw[:ctypes.sizeof(_UnicodeString)])
    except Exception:
        return _sensor_error("process_detail_malformed")
    length = int(header.Length)
    maximum = int(header.MaximumLength)
    pointer = int(header.Buffer or 0)
    header_size = ctypes.sizeof(_UnicodeString)
    if (
        length <= 0
        or length % 2
        or maximum < length
        or pointer < base + header_size
        or pointer > limit
        or pointer + length > limit
        or pointer + maximum > limit
    ):
        return _sensor_error("process_detail_malformed" if length else "process_detail_incomplete")
    offset = pointer - base
    raw = bytes(buffer.raw[offset:offset + length])
    try:
        command = raw.decode("utf-16-le", "strict")
    except UnicodeDecodeError:
        return _sensor_error("process_detail_malformed")
    if any(0xD800 <= ord(character) <= 0xDFFF for character in command):
        return _sensor_error("process_detail_malformed")
    if not command.strip():
        return _sensor_error("process_detail_incomplete")
    return command


def _query_executable_path(handle, api):
    query_image = getattr(api, "QueryFullProcessImageNameW", None)
    if query_image is None:
        return _sensor_error("process_detail_executable_unavailable")
    buffer = ctypes.create_unicode_buffer(IMAGE_PATH_CHARS)
    size = wintypes.DWORD(IMAGE_PATH_CHARS)
    try:
        ok = query_image(handle, 0, buffer, ctypes.byref(size))
    except Exception:
        return _sensor_error("process_detail_executable_unavailable")
    reported = int(size.value)
    if not ok or reported <= 0 or reported >= IMAGE_PATH_CHARS:
        return _sensor_error("process_detail_executable_unavailable")
    try:
        executable = "".join(buffer[index] for index in range(reported))
        terminator = buffer[reported]
    except (IndexError, ValueError):
        return _sensor_error("process_detail_executable_unavailable")
    if "\x00" in executable or terminator != "\x00" or buffer.value != executable:
        return _sensor_error("process_detail_executable_unavailable")
    if not executable:
        return _sensor_error("process_detail_executable_unavailable")
    return executable


__all__ = ["WindowsProcessDetailsApi", "read_process_details"]

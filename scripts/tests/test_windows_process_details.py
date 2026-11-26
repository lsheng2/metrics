from __future__ import annotations

import ctypes
from ctypes import wintypes
from datetime import datetime

import pytest


PROCESS_HANDLE = 0xCAFE
CREATION_FILETIME = 116444736000000000


class UnicodeString(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.USHORT),
        ("MaximumLength", wintypes.USHORT),
        ("Buffer", ctypes.c_void_p),
    ]


def _write_filetime(pointer, value: int) -> None:
    pointer._obj.dwLowDateTime = value & 0xFFFFFFFF
    pointer._obj.dwHighDateTime = value >> 32


class NativeDetailsApi:
    def __init__(
        self,
        *,
        command_line: str = '"C:/Tools/python.exe" -I script.py',
        command_bytes: bytes | None = None,
        executable_path: str = "C:/Tools/python.exe",
        executable_buffer_text: str | None = None,
        reported_executable_chars: int | None = None,
        creation: int = CREATION_FILETIME,
        process_times_ok: bool = True,
        nt_status: int = 0,
        query_image_ok: bool = True,
        header_length_delta: int = 0,
        maximum_length_delta: int = 2,
        pointer_offset: int | None = None,
        return_length: int | None = None,
    ):
        self.command_line = command_line
        self.command_bytes = command_bytes
        self.executable_path = executable_path
        self.executable_buffer_text = executable_buffer_text
        self.reported_executable_chars = reported_executable_chars
        self.creation = creation
        self.process_times_ok = process_times_ok
        self.nt_status = nt_status
        self.query_image_ok = query_image_ok
        self.header_length_delta = header_length_delta
        self.maximum_length_delta = maximum_length_delta
        self.pointer_offset = pointer_offset
        self.return_length = return_length
        self.calls: list[tuple[str, int]] = []

    def OpenProcess(self, *_args):
        raise AssertionError("read_process_details must borrow the supplied handle")

    def CloseHandle(self, *_args):
        raise AssertionError("read_process_details must not close the borrowed handle")

    def GetProcessTimes(self, handle, creation, *_unused):
        self.calls.append(("GetProcessTimes", int(handle)))
        if not self.process_times_ok:
            return False
        _write_filetime(creation, self.creation)
        return True

    def QueryFullProcessImageNameW(self, handle, _flags, buffer, size):
        self.calls.append(("QueryFullProcessImageNameW", int(handle)))
        if not self.query_image_ok:
            return False
        text = self.executable_path if self.executable_buffer_text is None else self.executable_buffer_text
        if len(text) >= size._obj.value:
            return False
        for index, character in enumerate(text):
            buffer[index] = character
        buffer[len(text)] = "\x00"
        size._obj.value = self.reported_executable_chars if self.reported_executable_chars is not None else len(text)
        return True

    def NtQueryInformationProcess(self, handle, information_class, process_information, buffer_size, return_length):
        self.calls.append(("NtQueryInformationProcess", int(handle)))
        assert information_class == 60
        if self.nt_status:
            return self.nt_status
        base = ctypes.addressof(process_information)
        raw = self.command_bytes if self.command_bytes is not None else self.command_line.encode("utf-16-le")
        text_at = base + ctypes.sizeof(UnicodeString) if self.pointer_offset is None else base + self.pointer_offset
        if base <= text_at and text_at + len(raw) <= base + int(buffer_size):
            ctypes.memmove(text_at, raw, len(raw))
        header = UnicodeString.from_address(base)
        header.Length = len(raw) + self.header_length_delta
        header.MaximumLength = len(raw) + self.maximum_length_delta
        header.Buffer = text_at
        if return_length is not None:
            return_length._obj.value = (
                self.return_length if self.return_length is not None
                else ctypes.sizeof(UnicodeString) + int(header.MaximumLength)
            )
        return 0


def _local_epoch_iso() -> str:
    return datetime.fromtimestamp(0).replace(microsecond=0).isoformat()


def test_read_process_details_returns_complete_identity_from_borrowed_handle():
    from scripts.validation.windows_host_process_details import read_process_details

    api = NativeDetailsApi()

    details = read_process_details(PROCESS_HANDLE, CREATION_FILETIME, api=api)

    assert details == {
        "command_line": '"C:/Tools/python.exe" -I script.py',
        "creation_date": _local_epoch_iso(),
        "executable_path": "C:/Tools/python.exe",
    }
    assert [name for name, _handle in api.calls] == [
        "GetProcessTimes",
        "NtQueryInformationProcess",
        "QueryFullProcessImageNameW",
    ]
    assert all(handle == PROCESS_HANDLE for _name, handle in api.calls)


def test_read_process_details_preserves_exact_command_and_executable_text():
    from scripts.validation.windows_host_process_details import read_process_details

    command = '  "C:/Tools/python.exe" -I script.py  '
    executable = " C:/Tools/python.exe "

    details = read_process_details(
        PROCESS_HANDLE,
        CREATION_FILETIME,
        api=NativeDetailsApi(command_line=command, executable_path=executable),
    )

    assert details["command_line"] == command
    assert details["executable_path"] == executable


@pytest.mark.parametrize(
    ("native_creation", "sensor_error"),
    [
        (None, "process_detail_creation_invalid"),
        (False, "process_detail_creation_invalid"),
        (0, "process_detail_creation_invalid"),
        (CREATION_FILETIME + 1, "process_detail_creation_mismatch"),
    ],
)
def test_read_process_details_refuses_missing_bool_zero_or_stale_creation(native_creation, sensor_error):
    from scripts.validation.windows_host_process_details import read_process_details

    result = read_process_details(PROCESS_HANDLE, native_creation, api=NativeDetailsApi())

    assert result == {"sensor_error": sensor_error}


@pytest.mark.parametrize(
    ("api", "sensor_error"),
    [
        (NativeDetailsApi(process_times_ok=False), "process_detail_creation_unavailable"),
        (NativeDetailsApi(nt_status=0xC0000003), "process_detail_unsupported"),
        (NativeDetailsApi(nt_status=0xC0000022), "process_detail_access_denied"),
        (NativeDetailsApi(nt_status=0xC000010A), "process_detail_terminated"),
        (NativeDetailsApi(return_length=0), "process_detail_malformed"),
        (NativeDetailsApi(return_length=ctypes.sizeof(UnicodeString) - 1), "process_detail_malformed"),
        (NativeDetailsApi(return_length=ctypes.sizeof(UnicodeString)), "process_detail_malformed"),
        (NativeDetailsApi(return_length=(128 * 1024) + 1), "process_detail_oversized"),
        (NativeDetailsApi(pointer_offset=(128 * 1024) + 8), "process_detail_malformed"),
        (NativeDetailsApi(header_length_delta=1), "process_detail_malformed"),
        (NativeDetailsApi(maximum_length_delta=-2), "process_detail_malformed"),
        (NativeDetailsApi(command_line=""), "process_detail_incomplete"),
        (NativeDetailsApi(command_bytes=b"\x00\xd8A\x00"), "process_detail_malformed"),
        (NativeDetailsApi(query_image_ok=False), "process_detail_executable_unavailable"),
        (NativeDetailsApi(reported_executable_chars=len("C:/Tools/python.exe") - 2), "process_detail_executable_unavailable"),
        (
            NativeDetailsApi(
                executable_buffer_text="C:/Tools/python.exe\x00hidden",
                reported_executable_chars=len("C:/Tools/python.exe\x00hidden"),
            ),
            "process_detail_executable_unavailable",
        ),
    ],
)
def test_read_process_details_fails_closed_without_partial_identity_fields(api, sensor_error):
    from scripts.validation.windows_host_process_details import read_process_details

    result = read_process_details(PROCESS_HANDLE, CREATION_FILETIME, api=api)

    assert result == {"sensor_error": sensor_error}


def test_read_process_details_fails_closed_when_filetime_cannot_be_formatted():
    from scripts.validation.windows_host_process_details import read_process_details

    too_large_for_datetime = 2**63 - 1

    result = read_process_details(
        PROCESS_HANDLE,
        too_large_for_datetime,
        api=NativeDetailsApi(creation=too_large_for_datetime),
    )

    assert result == {"sensor_error": "process_detail_creation_unrepresentable"}


def _enriched_git(command_line: str) -> dict:
    from scripts.validation.windows_host_process_identity import enrich_process_observations

    return enrich_process_observations(
        [{"pid": 777, "name": "git.exe"}],
        {777: {"command_line": command_line, "creation_date": "created"}},
        source_root="D:/repo",
        owned_root="D:/run",
    )[0]


@pytest.mark.parametrize(
    "command_line",
    [
        '"git" "-C" "D:/repo" "rev-parse" "HEAD"',
        '"C:/Program Files/Git/cmd/git.exe" -C D:/repo status --porcelain',
    ],
)
def test_git_classifier_keeps_quoted_rev_parse_and_status_reads_non_relevant(command_line):
    row = _enriched_git(command_line)

    assert row["relevance"] == "git_read"
    assert row["metrics_workload"] is False


@pytest.mark.parametrize(
    "command_line",
    [
        "git -C status commit -m synthetic",
        "git -C log push origin main",
    ],
)
def test_git_classifier_treats_write_subcommand_after_global_option_value_as_relevant(command_line):
    row = _enriched_git(command_line)

    assert row["relevance"] == "git_write"
    assert row["metrics_workload"] is True


@pytest.mark.parametrize(
    "command_line",
    [
        "git --git-dir status --work-tree log rev-parse HEAD",
        "git -c status.showUntrackedFiles=no status --short",
    ],
)
def test_git_classifier_skips_value_taking_global_options_before_read_subcommand(command_line):
    row = _enriched_git(command_line)

    assert row["relevance"] == "git_read"
    assert row["metrics_workload"] is False


@pytest.mark.parametrize(
    "command_line",
    [
        "git",
        "git --definitely-unknown status",
        "git frobnicate",
    ],
)
def test_git_classifier_keeps_missing_unknown_options_or_subcommands_relevant(command_line):
    row = _enriched_git(command_line)

    assert row["relevance"] == "git_unknown"
    assert row["metrics_workload"] is True

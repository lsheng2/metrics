from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from scripts.tests.test_windows_performance_evidence import _artifact, _read_json, _receipt_case
from scripts.validation.windows_qualification_inputs import QualificationError


def _terminal_row(pid: int, *, native_creation=111, terminal_exit_code=0, terminal_running=False):
    return {
        "pid": pid,
        "parent_pid": 50,
        "name": "python.exe",
        "sensor_error": "process_detail_missing",
        "metrics_workload": True,
        "relevance": "sensor_unresolved",
        "process_window": {
            "schema_version": 1,
            "pid": pid,
            "parent_pid": 50,
            "image_name": "python.exe",
            "native_creation": native_creation,
            "handle_opened": True,
            "handle_closed": True,
            "handle_closed": True,
            "terminal_exit_code": terminal_exit_code,
            "terminal_running": terminal_running,
            "terminal_observed": terminal_exit_code is not None and terminal_running is False,
        },
    }


def _owner_registration(pid: int, *, native_creation=111, run_id="window-1"):
    return {
        "schema_version": 1,
        "run_id": run_id,
        "owner_key": f"{run_id}:{pid}:{native_creation}",
        "pid": pid,
        "parent_pid": 50,
        "image_name": "python.exe",
        "native_creation": native_creation,
        "command_fingerprint": {"display": "python.exe argc=4", "sha256": "a" * 64},
        "sensor_identity": "owned-sensor",
        "role": "service_root",
    }


def _install_terminal_resolution(receipt, *, include_raw=True, include_registration=True,
                                 duplicate_registration=False, raw_creation=90001,
                                 classification="owned_terminal", extra_fact=False):
    run = Path(receipt["run_directory"])
    window_path = Path(receipt["measurement_window"]["path"])
    window = _read_json(window_path)
    row = _terminal_row(1001, native_creation=raw_creation)
    registration = _owner_registration(1001, native_creation=90001)
    fact = {
        "schema_version": 1,
        "decision": "owned_terminal",
        "reason": "registered_exact_terminal_exit0",
        "pid": 1001,
        "parent_pid": 50,
        "image_name": "python.exe",
        "native_creation": 90001,
        "run_id": "window-1",
        "owner_key": "window-1:1001:90001",
        "terminal_exit_code": 0,
        "terminal_running": False,
        "command_fingerprint": {"display": "python.exe argc=4", "sha256": "a" * 64},
    }
    process_rows = [{
        "pid": 1001, "classification": classification, "identity": None,
        "relevance": "sensor_unresolved", "command_fingerprint": None,
    }]
    facts = [fact]
    if extra_fact:
        facts.append({**fact, "pid": 1002, "owner_key": "window-1:1002:90001"})
    window["snapshots"][0].update({
        "processes": [row] if include_raw else [],
        "observed_owned_identities": [],
        "process_owner_registrations": (
            [registration, {**registration, "owner_key": "window-1:1001:duplicate"}]
            if duplicate_registration else [registration] if include_registration else []
        ),
        "process_classification": {
            "certification_blockers": [],
            "processes": process_rows,
            "process_resolution_facts": facts,
        },
        "process_resolution_facts": facts,
    })
    receipt["measurement_window"] = _artifact(window_path, window)
    cleanup_path = Path(receipt["cleanup"]["path"])
    cleanup = _read_json(cleanup_path)
    owned = cleanup["services"]["development"]["observations"]["candidate"]["owned_processes"]["1001"]
    owned["native_creation"] = 90001
    owned["run_id"] = "window-1"
    receipt["cleanup"] = _artifact(cleanup_path, cleanup)
    return run, window, cleanup


def test_windows_process_details_marks_omitted_target_as_missing():
    from scripts.validation import windows_host_environment as environment

    details = environment._windows_process_details([
        {"pid": 4100, "name": "python.exe", "parent_pid": 1},
        {"pid": 4200, "name": "explorer.exe", "parent_pid": 1},
    ], capture=SimpleNamespace(details=lambda: {}))

    assert details == {4100: {"sensor_error": "process_detail_missing"}}


def test_windows_process_details_refuses_malformed_native_identity():
    from scripts.validation import windows_host_environment as environment

    details = environment._windows_process_details([
        {"pid": 4100, "name": "python.exe", "parent_pid": 1},
        {"pid": 5100, "name": "git.exe", "parent_pid": 1},
    ], capture=SimpleNamespace(details=lambda: {
        4100: {"command_line": "python.exe", "creation_date": ""},
        5100: {"sensor_error": "native_query_terminated"},
    }))

    assert details == {
        4100: {"sensor_error": "process_detail_malformed"},
        5100: {"sensor_error": "native_query_terminated"},
    }


def test_owned_terminal_requires_registered_exact_incarnation():
    from scripts.validation.windows_host_process_identity import classify_process_observations

    result = classify_process_observations(
        [_terminal_row(4100)],
        owned_identities=set(),
        owned_process_facts=[_owner_registration(4100)],
        current_run_id="window-1",
    )

    assert result["certification_blockers"] == []
    assert result["processes"][0]["classification"] == "owned_terminal"
    assert result["process_resolution_facts"] == [{
        "schema_version": 1,
        "decision": "owned_terminal",
        "reason": "registered_exact_terminal_exit0",
        "pid": 4100,
        "parent_pid": 50,
        "image_name": "python.exe",
        "native_creation": 111,
        "run_id": "window-1",
        "owner_key": "window-1:4100:111",
        "terminal_exit_code": 0,
        "terminal_running": False,
        "command_fingerprint": {"display": "python.exe argc=4", "sha256": "a" * 64},
    }]

    reused = classify_process_observations(
        [_terminal_row(4100, native_creation=222)],
        owned_identities=set(),
        owned_process_facts=[_owner_registration(4100, native_creation=111)],
        current_run_id="window-1",
    )
    assert reused["certification_blockers"] == ["unresolved_relevant:4100"]


@pytest.mark.parametrize("fault", ["live", "unknown", "nonzero", "wrong_run", "malformed"])
def test_owned_terminal_rejects_unproven_terminal_boundaries(fault):
    from scripts.validation.windows_host_process_identity import classify_process_observations

    row = _terminal_row(4100)
    fact = _owner_registration(4100)
    run_id = "window-1"
    if fault == "live":
        row = _terminal_row(4100, terminal_exit_code=None, terminal_running=True)
    elif fault == "unknown":
        row = _terminal_row(4100, terminal_exit_code=None, terminal_running=False)
    elif fault == "nonzero":
        row = _terminal_row(4100, terminal_exit_code=7, terminal_running=False)
    elif fault == "wrong_run":
        fact = _owner_registration(4100, run_id="other-window")
    elif fault == "malformed":
        row["sensor_error"] = "process_detail_malformed"

    result = classify_process_observations(
        [row],
        owned_identities=set(),
        owned_process_facts=[fact],
        current_run_id=run_id,
    )

    assert result["certification_blockers"] == ["unresolved_relevant:4100"]
    assert result.get("process_resolution_facts", []) == []


def test_process_window_capture_closes_retained_handles_after_exception():
    from scripts.validation.windows_host_process_window import ProcessWindowCapture

    class Api:
        def __init__(self):
            self.closed = []

        def OpenProcess(self, access, inherit, pid):
            return 7000 + pid

        def GetProcessTimes(self, handle, creation, *_unused):
            creation._obj.dwHighDateTime = 0
            creation._obj.dwLowDateTime = handle
            return True

        def WaitForSingleObject(self, handle, milliseconds):
            return 0

        def GetExitCodeProcess(self, handle, code):
            code._obj.value = 0
            return True

        def CloseHandle(self, handle):
            self.closed.append(handle)
            return True

    api = Api()
    observed = []

    def reader(handle, created):
        observed.append((handle, created, tuple(api.closed)))
        return {"command_line": "python.exe --token=synthetic-only",
                "creation_date": "2026-11-26T12:00:00",
                "executable_path": "C:/Python/python.exe"}

    with pytest.raises(RuntimeError):
        with ProcessWindowCapture(
            [{"pid": 41, "parent_pid": 1, "name": "python.exe"}],
            api=api, detail_reader=reader,
        ) as capture:
            assert capture.details()[41]["command_line"].endswith("synthetic-only")
            assert "command_line" not in capture.facts()[41]
            raise RuntimeError("boom")

    assert observed == [(7041, 7041, ())]
    assert api.closed == [7041]


def test_process_window_capture_closes_first_handle_when_second_open_raises():
    from scripts.validation.windows_host_process_window import ProcessWindowCapture

    class Api:
        def __init__(self):
            self.closed = []

        def OpenProcess(self, access, inherit, pid):
            if pid == 42:
                raise OSError("open failed")
            return 7000 + pid

        def GetProcessTimes(self, handle, creation, *_unused):
            creation._obj.dwLowDateTime = handle
            return True

        def CloseHandle(self, handle):
            self.closed.append(handle)
            return True

    api = Api()
    with pytest.raises(OSError):
        ProcessWindowCapture([
            {"pid": 41, "parent_pid": 1, "name": "python.exe"},
            {"pid": 42, "parent_pid": 1, "name": "python.exe"},
        ], api=api).__enter__()

    assert api.closed == [7041]


def test_process_window_capture_closes_remaining_handles_after_terminal_error():
    from scripts.validation.windows_host_process_window import ProcessWindowCapture

    class Api:
        def __init__(self):
            self.closed = []

        def OpenProcess(self, access, inherit, pid):
            return 7000 + pid

        def GetProcessTimes(self, handle, creation, *_unused):
            creation._obj.dwLowDateTime = handle
            return True

        def WaitForSingleObject(self, handle, milliseconds):
            if handle == 7041:
                raise OSError("terminal failed")
            return 0

        def GetExitCodeProcess(self, handle, code):
            code._obj.value = 0
            return True

        def CloseHandle(self, handle):
            self.closed.append(handle)
            return True

    api = Api()
    with ProcessWindowCapture([
        {"pid": 41, "parent_pid": 1, "name": "python.exe"},
        {"pid": 42, "parent_pid": 1, "name": "python.exe"},
    ], api=api) as capture:
        facts = capture.finalize()

    assert api.closed == [7041, 7042]
    assert facts[41]["terminal_error"] == "OSError"
    assert facts[42]["terminal_exit_code"] == 0


def test_process_window_capture_does_not_claim_closed_when_close_fails():
    from scripts.validation.windows_host_process_window import ProcessWindowCapture

    class Api:
        def OpenProcess(self, access, inherit, pid):
            return 7000 + pid

        def GetProcessTimes(self, handle, creation, *_unused):
            creation._obj.dwLowDateTime = handle
            return True

        def WaitForSingleObject(self, handle, milliseconds):
            return 0

        def GetExitCodeProcess(self, handle, code):
            code._obj.value = 0
            return True

        def CloseHandle(self, handle):
            return False

    capture = ProcessWindowCapture([{"pid": 41, "parent_pid": 1, "name": "python.exe"}], api=Api())
    with pytest.raises(QualificationError):
        with capture:
            capture.finalize()
    facts = capture.facts()

    assert facts[41]["handle_closed"] is False
    assert facts[41]["handle_close_error"] == "close_failed"


@pytest.mark.parametrize("fault", [
    "missing_raw",
    "missing_registration",
    "duplicate_registration",
    "raw_creation_mismatch",
    "classification_downgraded",
    "orphan_resolution_fact",
])
def test_replay_rejects_owned_terminal_without_exact_raw_registration_relation(tmp_path, fault):
    from scripts.tests.windows_performance_support import seal_receipt
    from scripts.validation.windows_host_performance_evidence import validate_performance_result

    receipt, request = _receipt_case(tmp_path, mode="certify")
    _install_terminal_resolution(
        receipt,
        include_raw=fault != "missing_raw",
        include_registration=fault != "missing_registration",
        duplicate_registration=fault == "duplicate_registration",
        raw_creation=90002 if fault == "raw_creation_mismatch" else 90001,
        classification="owned_measurement" if fault == "classification_downgraded" else "owned_terminal",
        extra_fact=fault == "orphan_resolution_fact",
    )
    seal_receipt(receipt)

    with pytest.raises(QualificationError):
        validate_performance_result(receipt, request)


def test_replay_binds_owned_terminal_raw_registry_and_cleanup_to_same_run(tmp_path):
    from scripts.tests.windows_performance_support import seal_receipt
    from scripts.validation.windows_host_performance_evidence import validate_bound_receipt
    from scripts.validation.windows_host_performance_evidence import validate_performance_result

    receipt, request = _receipt_case(tmp_path, mode="certify")
    run, _window, _cleanup = _install_terminal_resolution(receipt)
    seal_receipt(receipt)

    result = validate_performance_result(receipt, request)
    assert result["acceptance_eligible"] is True
    bound = validate_bound_receipt("clause:10.4:B3-incremental-timing:performance", run / "receipt.json", request)
    assert bound["acceptance_eligible"] is True

    bad_receipt = deepcopy(receipt)
    bad_cleanup = _read_json(Path(receipt["cleanup"]["path"]))
    bad_cleanup["services"]["development"]["observations"]["candidate"]["owned_processes"]["1001"]["native_creation"] = 90002
    bad_receipt["cleanup"] = _artifact(run / "cleanup-bad.json", bad_cleanup)
    seal_receipt(bad_receipt)

    with pytest.raises(QualificationError):
        validate_performance_result(bad_receipt, request)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows native process observation is required")
def test_real_child_owner_registration_to_terminal_replay_join(tmp_path):
    from scripts.service_lifecycle_engine import PlatformOperationSet
    from scripts.validation.windows_host_process_identity import classify_process_observations
    from scripts.validation.windows_host_process_identity import owned_process_identity_facts_from_state
    from scripts.validation.windows_host_process_window import capture_process_window
    from scripts.validation.windows_host_performance_evidence import validate_bound_receipt, validate_performance_result
    from scripts.tests.windows_performance_support import seal_receipt

    ready = tmp_path / "ready.txt"
    release = tmp_path / "release.txt"
    code = "\n".join([
        "import sys, time",
        "from pathlib import Path",
        "Path(sys.argv[1]).write_text('ready', encoding='utf-8')",
        "deadline = time.monotonic() + 30",
        "while not Path(sys.argv[2]).exists() and time.monotonic() < deadline:",
        "    time.sleep(0.02)",
    ])
    command = [sys.executable, "-I", "-c", code, str(ready), str(release)]
    child = subprocess.Popen(command, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        deadline = time.monotonic() + 5
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ready.exists()

        ops = PlatformOperationSet()
        facts = owned_process_identity_facts_from_state(
            {"pid": child.pid, "provenance": {"process_start_marker": ops.process_start_marker(child.pid)}},
            ops,
        )
        registration = next(row for row in facts["registrations"] if row["pid"] == child.pid)
        with capture_process_window([{
            "pid": child.pid,
            "parent_pid": registration["parent_pid"],
            "name": registration["image_name"],
        }]) as capture:
            opened = capture.facts()[child.pid]
            assert registration["parent_pid"] == opened["parent_pid"]
            assert registration["image_name"] == opened["image_name"]
            assert child.poll() is None
            release.write_text("stop", encoding="utf-8")
            assert child.wait(timeout=5) == 0
            terminal = capture.finalize()[child.pid]
        row = {
            "pid": child.pid,
            "parent_pid": opened["parent_pid"],
            "name": opened["image_name"],
            "sensor_error": "process_detail_missing",
            "metrics_workload": True,
            "relevance": "sensor_unresolved",
            "process_window": terminal,
        }
        registration = {**registration, "run_id": "window-1", "owner_key": f"window-1:{child.pid}:{opened['native_creation']}"}
        classification = classify_process_observations(
            [row], owned_identities=set(), owned_process_facts=[registration], current_run_id="window-1",
        )
        assert classification["certification_blockers"] == []
        assert classification["processes"][0]["classification"] == "owned_terminal"

        receipt, request = _receipt_case(tmp_path, mode="certify")
        run = Path(receipt["run_directory"])
        window_path = Path(receipt["measurement_window"]["path"])
        window = _read_json(window_path)
        window["snapshots"][0].update({
            "processes": [row],
            "observed_owned_identities": [],
            "process_owner_registrations": [registration],
            "process_classification": classification,
            "process_resolution_facts": classification["process_resolution_facts"],
        })
        receipt["measurement_window"] = _artifact(window_path, window)
        cleanup_path = Path(receipt["cleanup"]["path"])
        cleanup = _read_json(cleanup_path)
        cleanup_row = cleanup["services"]["development"]["observations"]["candidate"]["owned_processes"]["1001"]
        cleanup_row.update({
            "pid": child.pid,
            "native_creation": opened["native_creation"],
            "run_id": "window-1",
            "terminal_exit_code": 0,
            "process_running": False,
        })
        cleanup["services"]["development"]["observations"]["candidate"]["owned_processes"] = {str(child.pid): cleanup_row}
        cleanup["services"]["development"]["services"]["candidate"]["pid"] = child.pid
        cleanup["services"]["development"]["observations"]["candidate"]["pid"] = child.pid
        receipt["cleanup"] = _artifact(cleanup_path, cleanup)
        seal_receipt(receipt)

        assert validate_performance_result(receipt, request)["acceptance_eligible"] is True
        assert validate_bound_receipt("clause:10.4:B3-incremental-timing:performance", run / "receipt.json", request)["acceptance_eligible"] is True
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=5)

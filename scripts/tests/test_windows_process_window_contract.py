"""Fail-closed contracts for process-window observation and replay."""
from contextlib import ExitStack, contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.tests.test_windows_performance_evidence import _artifact, _read_json, _receipt_case
from scripts.tests.test_windows_process_window import _install_terminal_resolution
from scripts.tests.windows_performance_support import seal_receipt
from scripts.validation.windows_qualification_inputs import QualificationError


@pytest.mark.parametrize("fault", [
    "erase_claims", "downgrade_and_erase", "close_failure_without_claims",
    "conflicting_mirror", "empty_fingerprint", "zero_creation",
    "boolean_schema", "missing_sensor_identity",
])
def test_raw_terminal_observations_cannot_be_promoted_by_summary_edits(tmp_path, fault):
    from scripts.validation.windows_host_performance_evidence import validate_performance_result

    receipt, request = _receipt_case(tmp_path, mode="certify")
    _install_terminal_resolution(receipt)
    window_path = Path(receipt["measurement_window"]["path"])
    window = _read_json(window_path)
    snapshot = window["snapshots"][0]
    classification = snapshot["process_classification"]
    if fault in {"erase_claims", "downgrade_and_erase", "close_failure_without_claims"}:
        snapshot.pop("process_resolution_facts")
        classification.pop("process_resolution_facts", None)
        classification["processes"] = (
            [{"pid": 1001, "classification": "tooling_unrelated"}]
            if fault == "downgrade_and_erase" else []
        )
        if fault == "close_failure_without_claims":
            snapshot["processes"][0]["process_window"]["handle_closed"] = False
    elif fault == "conflicting_mirror":
        classification["process_resolution_facts"] = []
    elif fault == "empty_fingerprint":
        for row in [
            *snapshot["process_resolution_facts"], *classification["process_resolution_facts"],
            *snapshot["process_owner_registrations"],
        ]:
            row["command_fingerprint"] = {}
    elif fault == "zero_creation":
        rows = [
            *snapshot["process_resolution_facts"], *classification["process_resolution_facts"],
            *snapshot["process_owner_registrations"], snapshot["processes"][0]["process_window"],
        ]
        for row in rows:
            row["native_creation"] = 0
            if "owner_key" in row:
                row["owner_key"] = "window-1:1001:0"
        cleanup_path = Path(receipt["cleanup"]["path"])
        cleanup = _read_json(cleanup_path)
        cleanup["services"]["development"]["observations"]["candidate"]["owned_processes"]["1001"]["native_creation"] = 0
        receipt["cleanup"] = _artifact(cleanup_path, cleanup)
    elif fault == "boolean_schema":
        for row in [
            *snapshot["process_resolution_facts"], *classification["process_resolution_facts"],
            *snapshot["process_owner_registrations"], snapshot["processes"][0]["process_window"],
        ]:
            row["schema_version"] = True
    else:
        snapshot["process_owner_registrations"][0].pop("sensor_identity", None)
    receipt["measurement_window"] = _artifact(window_path, window)
    seal_receipt(receipt)
    with pytest.raises(QualificationError):
        validate_performance_result(receipt, request)


@pytest.fixture
def registered_owner(monkeypatch):
    from scripts.service_lifecycle_engine import platform_ops
    from scripts.validation import windows_host_process_identity as identity

    state = {
        "pid": 4100,
        "provenance": {"process_start_marker": "original-marker"},
        "native_creation": {4100: 41000, 4101: 41010},
        "native_parent": {4100: 50, 4101: 4100},
        "native_image": {4100: "python.exe", 4101: "conhost.exe"},
        "native_details": {
            4100: {
                "command_line": "python.exe root-4100",
                "creation_date": "created-4100",
                "executable_path": r"C:\Python\python.exe",
            },
            4101: {
                "command_line": "conhost.exe child-4101",
                "creation_date": "created-4101",
                "executable_path": r"C:\Windows\System32\conhost.exe",
            },
        },
        "close_failure": False,
    }

    class Capture:
        def __init__(self, rows, *, detail_reader=None):
            self.rows = rows
            self.detail_reader = detail_reader

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            if state["close_failure"]:
                raise QualificationError("native process observation handle release failed")
            return False

        def facts(self):
            return {
                row["pid"]: {
                    "handle_opened": True,
                    "native_creation": state["native_creation"].get(row["pid"]),
                    "parent_pid": state["native_parent"].get(row["pid"]),
                    "image_name": state["native_image"].get(row["pid"]),
                } for row in self.rows
            }

        def details(self):
            if self.detail_reader is None:
                raise ValueError("Native process details were not requested")
            return {
                row["pid"]: dict(state["native_details"].get(row["pid"], {}))
                for row in self.rows
            }

    monkeypatch.setattr(identity, "ProcessWindowCapture", Capture)
    monkeypatch.setattr(identity, "native_process_rows_by_pid", lambda pids: {
        pid: {
            "pid": pid,
            "parent_pid": state["native_parent"].get(pid),
            "name": state["native_image"].get(pid),
        }
        for pid in pids
    })
    monkeypatch.setattr(identity, "living_children", lambda root_pid: [
        {"pid": 4101, "parent_pid": root_pid, "created": state["native_creation"][4101]},
    ])

    def legacy_sensor_unavailable(pid):
        raise AssertionError("registration must use retained native process details")

    monkeypatch.setattr(platform_ops, "get_process_created_at", legacy_sensor_unavailable)
    ops = SimpleNamespace(
        process_command_line=legacy_sensor_unavailable,
        process_start_marker=lambda pid: "original-marker" if pid == 4100 else "child-marker",
    )
    return identity, state, ops


def test_admitted_root_can_authorize_current_native_descendants(registered_owner):
    identity, state, ops = registered_owner
    facts = identity.owned_process_identity_facts_from_state(state, ops)
    assert {row["pid"] for row in facts["registrations"]} == {4100, 4101}
    assert {row["pid"] for row in facts["descendant_identities"]} == {4101}


def test_descendant_registration_keeps_non_python_native_row(registered_owner):
    identity, state, ops = registered_owner
    facts = identity.owned_process_identity_facts_from_state(state, ops)
    child = next(row for row in facts["registrations"] if row["pid"] == 4101)
    assert child["image_name"] == "conhost.exe"


@pytest.mark.parametrize("marker", [None, "", "stale-marker"])
def test_stale_or_missing_root_provenance_cannot_authorize_descendants(registered_owner, marker):
    identity, state, ops = registered_owner
    state["provenance"]["process_start_marker"] = marker
    facts = identity.owned_process_identity_facts_from_state(state, ops)
    assert facts["registrations"] == []
    assert facts["identities"] == set()


def test_descendant_registration_does_not_require_an_unowned_sle_marker(registered_owner):
    identity, state, ops = registered_owner

    def marker(pid):
        if pid != state["pid"]:
            raise AssertionError("A descendant has no independent SLE launch marker")
        return "original-marker"

    ops.process_start_marker = marker
    facts = identity.owned_process_identity_facts_from_state(state, ops)
    assert {row["pid"] for row in facts["registrations"]} == {4100, 4101}


@pytest.mark.parametrize("details", [
    {"sensor_error": "process_detail_access_denied"},
    {"command_line": "", "creation_date": "created-4101", "executable_path": r"C:\Windows\System32\conhost.exe"},
    {"command_line": "conhost.exe child-4101", "creation_date": "", "executable_path": r"C:\Windows\System32\conhost.exe"},
    {"command_line": "conhost.exe child-4101", "creation_date": "created-4101", "executable_path": ""},
    {"command_line": ["conhost.exe"], "creation_date": "created-4101", "executable_path": r"C:\Windows\System32\conhost.exe"},
    {"command_line": "conhost.exe child-4101", "creation_date": "created-4101"},
])
def test_incomplete_native_details_refuse_descendant_without_legacy_fallback(registered_owner, details):
    identity, state, ops = registered_owner
    state["native_details"][4101] = details
    facts = identity.owned_process_identity_facts_from_state(state, ops)
    assert {row["pid"] for row in facts["registrations"]} == {4100}
    assert facts["descendant_identities"] == [{"pid": 4101, "parent_pid": 4100, "created": 41010, "sensor_identity": None}]


def test_descendant_registration_rejects_native_parent_mismatch(registered_owner):
    identity, state, ops = registered_owner
    state["native_parent"][4101] = 9999
    facts = identity.owned_process_identity_facts_from_state(state, ops)
    assert {row["pid"] for row in facts["registrations"]} == {4100}
    assert facts["descendant_identities"][0]["sensor_identity"] is None


def test_registration_native_handle_close_failure_stays_fatal(registered_owner):
    identity, state, ops = registered_owner
    state["close_failure"] = True
    with pytest.raises(QualificationError, match="native process observation handle release failed"):
        identity.owned_process_identity_facts_from_state(state, ops)


class CloseFailureApi:
    def __init__(self):
        self.closed = []

    def OpenProcess(self, access, inherit, pid):
        return 7000 + pid

    def GetProcessTimes(self, handle, creation, *_args):
        creation._obj.dwLowDateTime = handle
        return True

    def WaitForSingleObject(self, handle, timeout):
        return 0

    def GetExitCodeProcess(self, handle, code):
        code._obj.value = 0
        return True

    def CloseHandle(self, handle):
        self.closed.append(handle)
        return handle != 7041


def test_failed_release_is_a_fatal_capture_outcome_after_all_handles_are_attempted():
    from scripts.validation.windows_host_process_window import ProcessWindowCapture

    api = CloseFailureApi()
    capture = ProcessWindowCapture([
        {"pid": 41, "name": "python.exe"}, {"pid": 42, "name": "python.exe"},
    ], api=api)
    with pytest.raises(QualificationError):
        with capture:
            capture.finalize()
    assert api.closed == [7041, 7042]
    assert capture.facts()[41]["handle_closed"] is False
    with pytest.raises(QualificationError):
        capture.finalize()
    assert api.closed == [7041, 7042]


def test_cleanup_retains_native_release_failure_as_an_observation_error(monkeypatch):
    from scripts.validation import windows_host_process_cleanup as cleanup

    monkeypatch.setattr(cleanup, "living_children", lambda root_pid: [])
    monkeypatch.setattr(cleanup, "native_process_fact", lambda *args, **kwargs: {
        "native_creation": 123, "handle_opened": True, "handle_closed": False,
        "handle_close_error": "close_failed",
    })

    @contextmanager
    def observe(pid):
        yield lambda: 0

    with ExitStack() as stack:
        capture = cleanup._capture_owned_process_observations(
            {"pid": 321}, SimpleNamespace(observe_process_exit=observe), stack, run_id="window-1",
        )
    assert capture["observation_errors"]


def test_cleanup_rejects_reused_descendant_incarnation(monkeypatch):
    from scripts.validation import windows_host_process_cleanup as cleanup

    monkeypatch.setattr(cleanup, "living_children", lambda root_pid: [
        {"pid": 322, "parent_pid": root_pid, "created": 111},
    ])
    monkeypatch.setattr(cleanup, "native_process_fact", lambda *args, **kwargs: {
        "native_creation": 222, "handle_opened": True, "handle_closed": True,
    })

    @contextmanager
    def observe(pid):
        yield lambda: 0

    with ExitStack() as stack:
        capture = cleanup._capture_owned_process_observations(
            {"pid": 321}, SimpleNamespace(observe_process_exit=observe), stack, run_id="window-1",
        )
    assert "native_incarnation_changed:322" in capture["observation_errors"]


def test_cleanup_replay_rejects_native_release_failure_even_without_terminal_resolution(tmp_path):
    from scripts.validation.windows_host_performance_evidence import validate_performance_result

    receipt, request = _receipt_case(tmp_path, mode="certify")
    cleanup_path = Path(receipt["cleanup"]["path"])
    cleanup = _read_json(cleanup_path)
    row = cleanup["services"]["development"]["observations"]["candidate"]["owned_processes"]["1001"]
    row.update(native_handle_opened=True, native_handle_closed=False)
    receipt["cleanup"] = _artifact(cleanup_path, cleanup)
    seal_receipt(receipt)
    with pytest.raises(QualificationError):
        validate_performance_result(receipt, request)


def complete_process_receipt(tmp_path, *, owned=True, relevant=True):
    receipt, request = _receipt_case(tmp_path, mode="certify")
    path = Path(receipt["measurement_window"]["path"])
    window = _read_json(path)
    row = {
        "pid": 7100, "parent_pid": 50, "name": "python.exe", "identity": "observed-identity",
        "metrics_workload": relevant, "relevance": "metrics_runtime" if relevant else "tooling_unrelated",
        "command_fingerprint": {"display": "python.exe argc=4", "sha256": "b" * 64},
    }
    snapshot = window["snapshots"][0]
    snapshot.update(
        processes=[row], observed_owned_identities=["observed-identity"] if owned else [],
        process_owner_registrations=[], process_resolution_facts=[],
        process_classification={
            "certification_blockers": [],
            "processes": [{
                "pid": row["pid"], "identity": row["identity"], "relevance": row["relevance"],
                "classification": "owned_measurement" if relevant else "tooling_unrelated",
                "command_fingerprint": row["command_fingerprint"],
            }],
        },
    )
    return receipt, request, path, window


@pytest.mark.parametrize("owned,relevant", [(True, True), (False, False)])
def test_complete_raw_rows_replay_the_actual_admission_input(tmp_path, owned, relevant):
    from scripts.validation.windows_host_performance_evidence import validate_performance_result

    receipt, request, path, window = complete_process_receipt(tmp_path, owned=owned, relevant=relevant)
    receipt["measurement_window"] = _artifact(path, window)
    seal_receipt(receipt)
    assert validate_performance_result(receipt, request)["acceptance_eligible"] is True


@pytest.mark.parametrize("fault", [
    "foreign_erased", "foreign_unrelated", "foreign_owned", "missing_admission",
    "duplicate_admission", "different_admission", "workload_relabel", "command_hash_mismatch",
    "owned_claim_erased",
])
def test_complete_raw_process_classification_cannot_be_forged(tmp_path, fault):
    from scripts.validation.windows_host_performance_evidence import validate_performance_result

    receipt, request, path, window = complete_process_receipt(tmp_path, owned=not fault.startswith("foreign"))
    snapshot = window["snapshots"][0]
    claims = snapshot["process_classification"]["processes"]
    if fault in {"foreign_erased", "owned_claim_erased"}:
        snapshot["process_classification"]["processes"] = []
    elif fault == "foreign_unrelated":
        claims[0]["classification"] = "tooling_unrelated"
    elif fault == "missing_admission":
        del snapshot["observed_owned_identities"]
    elif fault == "duplicate_admission":
        snapshot["observed_owned_identities"].append("observed-identity")
    elif fault == "different_admission":
        snapshot["observed_owned_identities"] = ["other-identity"]
    elif fault == "workload_relabel":
        snapshot["processes"][0]["metrics_workload"] = False
        claims[0]["classification"] = "tooling_unrelated"
    elif fault == "command_hash_mismatch":
        claims[0]["command_fingerprint"] = {"display": "python.exe argc=4", "sha256": "c" * 64}
    receipt["measurement_window"] = _artifact(path, window)
    seal_receipt(receipt)
    with pytest.raises(QualificationError):
        validate_performance_result(receipt, request)


def test_collected_ownership_input_and_private_command_hash_replay_together(tmp_path, monkeypatch):
    import json
    from scripts.validation import windows_host_environment as environment
    from scripts.validation.windows_host_process_window_evidence import check_window_terminal_facts

    run = tmp_path / "run"
    run.mkdir()
    monkeypatch.setattr(environment, "source_snapshot", lambda root: {"head": "source", "status_sha256": "clean"})
    monkeypatch.setattr(environment, "machine_snapshot", lambda **kwargs: {
        "cpu": {"kernel": 10, "user": 10, "idle": 5},
        "processes": [{
            "pid": 7100, "parent_pid": 50, "name": "python.exe", "identity": "admitted",
            "metrics_workload": True, "relevance": "metrics_runtime",
            "command": ["python.exe", "--private", "DO_NOT_PERSIST"],
        }],
    })
    output = run / "verdict.json"
    with environment.MeasurementWindow(
        tmp_path, run, tmp_path / "repo", owned_process_identities={"admitted"},
    ) as window:
        window.bind_verdict(output, writer=lambda: output.write_text('{"status":"PASS"}', encoding="utf-8"))
    record = json.loads((run / "measurement-window.json").read_text(encoding="utf-8"))
    assert record["snapshots"][0]["observed_owned_identities"] == ["admitted"]
    assert "DO_NOT_PERSIST" not in json.dumps(record)
    assert check_window_terminal_facts(record) == []

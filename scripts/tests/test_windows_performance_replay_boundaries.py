from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.tests.test_windows_performance_evidence import _artifact, _read_json, _receipt_case
from scripts.tests.windows_performance_support import performance_phase_cleanup, seal_receipt
from scripts.validation.windows_host_performance_evidence import (
    _check_cleanup,
    _check_resolved_measurement_identity,
    validate_performance_result,
)
from scripts.validation.windows_qualification_inputs import QualificationError


def test_real_manifest_producer_preserves_page_specific_asset_sets():
    from scripts.validation.windows_host_benchmark import resolved_inputs
    from scripts.validation.windows_host_samples import ARMS, PAGE_KEYS

    common = {"url": "/static/base.css", "sha256": "a" * 64, "bytes": 42, "status": 200}
    editor = {"url": "/static/editor.js", "sha256": "b" * 64, "bytes": 99, "status": 200}
    pages = {page: "/" + page for page in PAGE_KEYS}
    sanity = {
        arm: {
            page: {"assets": [common, editor] if page == "draft_edit" else [common]}
            for page in PAGE_KEYS
        } for arm in ARMS
    }
    metadata = {arm: {"pages": pages, "worker_started": True, "worker_executed": []} for arm in ARMS}
    arms = SimpleNamespace(bases={arm: "http://127.0.0.1:1234" for arm in ARMS})
    resolved = resolved_inputs(arms, sanity, metadata, production=False, recipe={}, direct_asset=None)
    measured = {
        "sanity": sanity,
        "pages": {
            mode: {
                page: {arm: [deepcopy(sanity[arm][page])] for arm in ARMS}
                for page in PAGE_KEYS
            } for mode in ("seq", "c4")
        },
    }

    _check_resolved_measurement_identity(resolved, measured)
    measured["pages"]["seq"]["home"]["candidate"][0]["assets"].append(editor)
    with pytest.raises(QualificationError):
        _check_resolved_measurement_identity(resolved, measured)


@pytest.mark.parametrize("fault", ["failed_stop", "child_nonzero", "child_unknown", "missing_sensor"])
def test_cleanup_replay_rejects_failed_facts_even_with_consistent_summaries(fault):
    cleanup = {
        "services": {phase: performance_phase_cleanup() for phase in ("development", "production")},
        "normal": True, "forced": False, "listeners_absent": True, "owned_descendants_absent": True,
    }
    phase = cleanup["services"]["development"]
    observed = phase["observations"]["candidate"]
    process = observed["owned_processes"]["1001"]
    if fault == "failed_stop":
        phase["services"]["candidate"]["stopped"] = False
        phase["normal"] = False
        cleanup["normal"] = False
    elif fault == "child_nonzero":
        process["terminal_exit_code"] = 7
    elif fault == "child_unknown":
        del process["process_running"]
    else:
        del observed["observation_errors"]

    with pytest.raises(QualificationError):
        _check_cleanup(cleanup)


@pytest.mark.parametrize("fault", ["missing_receipt", "different_payload", "missing_classification", "wrong_source"])
def test_window_replay_cannot_accept_unresolved_or_unbound_proof(tmp_path, fault):
    receipt, request = _receipt_case(tmp_path, mode="certify")
    run = Path(receipt["run_directory"])
    if fault == "missing_receipt":
        witness = _read_json(run / "receipt-write-witness.json")
        witness["receipt_path"] = str(run / "missing.json")
        _artifact(run / "receipt-write-witness.json", witness)
    elif fault == "different_payload":
        receipt["unbound_receipt_field"] = "not the witnessed bytes"
    else:
        path = Path(receipt["measurement_window"]["path"])
        window = _read_json(path)
        if fault == "missing_classification":
            window["snapshots"] = [{}]
        else:
            window["source_before"] = window["source_after"] = {"head": "other-source"}
        receipt["measurement_window"] = _artifact(path, window)

    with pytest.raises(QualificationError):
        validate_performance_result(receipt, request)


def test_discovered_direct_asset_is_bound_before_sampling(monkeypatch):
    import hashlib
    from scripts.validation import windows_host_benchmark as benchmark

    class Http:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def get(self, url):
            if url.endswith("/ai/"):
                return SimpleNamespace(status_code=200, text='<script src="/ai/assets/runtime.js"></script>')
            return SimpleNamespace(status_code=200, content=b"runtime")

    monkeypatch.setattr(benchmark, "client", Http)
    result = benchmark.discover_direct_asset("http://127.0.0.1:1234")
    assert result == {
        "url": "/ai/assets/runtime.js",
        "sha256": hashlib.sha256(b"runtime").hexdigest(),
        "bytes": 7,
    }


def test_replay_rejects_complete_measurements_copied_from_another_window(tmp_path):
    receipt, request = _receipt_case(tmp_path, mode="certify")
    run = Path(receipt["run_directory"])
    path = Path(receipt["measurement_window"]["path"])
    window = _read_json(path)
    window.update(started_monotonic=1000.0, ended_monotonic=2000.0)
    window["verdict"]["written_monotonic"] = 1900.0
    receipt["measurement_window"] = _artifact(path, window)
    witness = _read_json(run / "receipt-write-witness.json")
    witness.update(write_started_monotonic=2001.0, write_completed_monotonic=2002.0,
                   guard_observed_monotonic=2003.0)
    _artifact(run / "receipt-write-witness.json", witness)
    seal_receipt(receipt)

    with pytest.raises(QualificationError, match="window"):
        validate_performance_result(receipt, request)


@pytest.mark.parametrize("kind", ["excess_stream", "excess"])
def test_performance_rejects_extra_off_cadence_excess_probe(kind):
    from scripts.tests.windows_performance_support import performance_transport_payload
    from scripts.validation.windows_host_transport import validate_transport

    payload = performance_transport_payload(slots=6)
    extra = deepcopy(next(row for row in payload["saturation"]["probes"] if row["kind"] == "excess_stream"))
    for key in ("scheduled", "started", "ended"):
        extra[key] += 1
    extra["slot"] = 1
    extra["kind"] = kind
    payload["saturation"]["probes"].append(extra)
    with pytest.raises(ValueError):
        validate_transport(payload, spacing_events=50, require_direct_asset=True)


@pytest.mark.parametrize("foreign", [False, True])
def test_launch_intent_covers_prepublication_without_owning_foreign_parent(tmp_path, monkeypatch, foreign):
    import os
    from scripts.validation import windows_host_environment as environment

    run = tmp_path / "run"
    run.mkdir()
    command = ["python.exe", "windows_perf_entry.py", "serve", "--root", str(run / "raw" / "development")]
    rows = []
    monkeypatch.setattr(environment, "source_snapshot", lambda root: {"head": "source"})
    monkeypatch.setattr(environment, "machine_snapshot", lambda **kwargs: {
        "processes": rows, "cpu": {"idle": 1, "kernel": 2, "user": 3},
    })

    def exercise():
        with environment.MeasurementWindow(tmp_path, run, tmp_path) as window:
            window.register_launch_intent(command)
            rows.extend([
                {"pid": 17, "parent_pid": -1 if foreign else os.getpid(), "command": command,
                 "identity": "wrapper-identity", "metrics_workload": True},
                {"pid": 18, "parent_pid": 17, "command": ["python.exe", "-c", "redirector"],
                 "identity": "child-identity", "metrics_workload": True},
            ])
            window._collect()
            window.check()
            verdict = run / "receipt.json"
            verdict.write_text("{}\n", encoding="utf-8")
            window.bind_verdict(verdict)
        return window.record

    if foreign:
        with pytest.raises(ValueError, match="observation|relevant"):
            exercise()
    else:
        record = exercise()
        assert record["result"] == "PASS"
        assert record["snapshots"][1]["ownership_setup"]["startup_identity_count"] == 2
        assert not list(run.glob("raw/*/lifecycle/*.json"))


def test_platform_adapter_declares_exact_resolved_command_before_os_spawn(monkeypatch):
    from scripts.service_lifecycle_engine import PlatformOperationSet
    from scripts.validation import windows_host_processes as processes

    declarations = []
    window = SimpleNamespace(register_launch_intent=lambda command: declarations.append(tuple(command)))
    command = ("python.exe", "--root", "D:/owned/run", "--port", "1234")

    def spawn(actual, *_args):
        assert declarations == [command]
        assert tuple(actual) == command
        return SimpleNamespace(pid=123)

    operations = processes.measurement_platform_ops(window, PlatformOperationSet(start_process=spawn))
    assert operations.start_process(command).pid == 123


@pytest.mark.parametrize("fault", ["prefix_sibling", "different_command", "duplicate_roots"])
def test_predeclared_launch_rejects_near_miss_ownership(tmp_path, fault):
    from scripts.validation.windows_host_process_identity import startup_owned_identities_from_run

    run = tmp_path / "run"
    root = tmp_path / "run-other" if fault == "prefix_sibling" else run / "raw"
    command = ["python.exe", "windows_perf_entry.py", "serve", "--root", str(root)]
    actual = [*command, "--unexpected"] if fault == "different_command" else command
    rows = [{"pid": 17, "parent_pid": 1, "command": actual, "identity": "root"}]
    if fault == "duplicate_roots":
        rows.append({"pid": 18, "parent_pid": 1, "command": actual, "identity": "duplicate"})
    result = startup_owned_identities_from_run(run, rows, pending_launches=[
        {"command": command, "parent_pid": 1},
    ])
    assert result["identities"] == set()

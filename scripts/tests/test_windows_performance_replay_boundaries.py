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

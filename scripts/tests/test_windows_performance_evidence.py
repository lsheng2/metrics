from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from scripts.tests.windows_performance_support import (
    environment_payload,
    import_probe_payload,
    performance_driver_request,
    performance_measurement_payload,
    performance_identity_payloads,
    performance_phase_cleanup,
    performance_transport_payload,
    resolved_inputs_payload,
    seal_receipt,
    shift_measurement,
)
from scripts.tests.test_windows_performance_inputs import functional_acceptance_payload, performance_policy_payload
from scripts.validation.windows_host_performance_contract import FUNCTIONAL_RELATIVE, POLICY_RELATIVE


def test_performance_transport_rejects_functional_eight_frame_spacing():
    from scripts.validation.windows_host_transport import validate_transport

    payload = performance_measurement_payload()
    payload["spacing"]["indices"] = list(range(8))
    payload["spacing"]["arrivals"] = payload["spacing"]["arrivals"][:8]

    with pytest.raises(ValueError):
        validate_transport(payload, spacing_events=50, require_direct_asset=True)


def test_performance_transport_rejects_echo_only_saturation_proof():
    from scripts.validation.windows_host_transport import validate_transport

    payload = performance_measurement_payload()
    payload["saturation"]["probes"] = [
        probe for probe in payload["saturation"]["probes"] if probe["kind"] != "direct_asset"
    ]

    with pytest.raises(ValueError):
        validate_transport(payload, spacing_events=50, require_direct_asset=True)


def test_performance_transport_rejects_copied_or_bunched_slot_observations():
    from scripts.validation.windows_host_transport import validate_transport

    payload = performance_measurement_payload()
    first = payload["saturation"]["probes"][0]["started"]
    for probe in payload["saturation"]["probes"]:
        if probe["kind"] in {"loop_short", "direct_asset"}:
            probe["started"] = first

    with pytest.raises(ValueError):
        validate_transport(payload, spacing_events=50, require_direct_asset=True)


def test_performance_transport_rejects_missing_fifth_slot_excess_probe():
    from scripts.validation.windows_host_transport import validate_transport

    payload = performance_measurement_payload()
    payload.update(performance_transport_payload(slots=6))
    payload["saturation"]["probes"] = [
        probe for probe in payload["saturation"]["probes"]
        if not (probe["kind"] == "excess_stream" and probe["slot"] == 5)
    ]

    with pytest.raises(ValueError):
        validate_transport(payload, spacing_events=50, require_direct_asset=True)


def test_performance_transport_rejects_displaced_schedule_or_elapsed_mismatch():
    from scripts.validation.windows_host_transport import validate_transport

    payload = performance_measurement_payload()
    payload.update(performance_transport_payload(slots=2))
    payload["saturation"]["probes"][0]["scheduled"] = payload["saturation"]["started"] + 0.4
    payload["saturation"]["probes"][0]["started"] = payload["saturation"]["started"] + 0.41
    with pytest.raises(ValueError):
        validate_transport(payload, spacing_events=50, require_direct_asset=True)

    payload = performance_measurement_payload()
    payload.update(performance_transport_payload(slots=2))
    payload["saturation"]["probes"][0]["ms"] = 1.0
    with pytest.raises(ValueError):
        validate_transport(payload, spacing_events=50, require_direct_asset=True)


def test_performance_checker_derives_certify_acceptance_from_raw_artifacts(tmp_path):
    from scripts.validation.windows_host_performance_evidence import validate_performance_result

    receipt, request = _receipt_case(tmp_path, mode="certify")

    result = validate_performance_result(receipt, request)

    assert result["acceptance_eligible"] is True
    assert result["collection_status"] == "COMPLETE"
    assert result["violations"] == []


def test_performance_checker_rejects_summary_only_cleanup(tmp_path):
    from scripts.validation.windows_host_performance_evidence import validate_performance_result
    from scripts.validation.windows_qualification_inputs import QualificationError

    receipt, request = _receipt_case(tmp_path, mode="certify")
    run = Path(receipt["run_directory"])
    receipt["cleanup"] = _artifact(run / "cleanup.json", {
        "normal": True,
        "owned_descendants_absent": True,
        "listeners_absent": True,
        "forced": False,
    })

    with pytest.raises(QualificationError):
        validate_performance_result(receipt, request)


def test_performance_checker_rejects_missing_page_intervals_or_block_inventory(tmp_path):
    from scripts.validation.windows_host_performance_evidence import validate_performance_result
    from scripts.validation.windows_qualification_inputs import QualificationError

    receipt, request = _receipt_case(tmp_path, mode="certify")
    measurement = _read_json(Path(receipt["measurements"]["development"]["path"]))
    del measurement["pages"]["seq"]["home"]["baseline"][0]["started"]
    receipt["measurements"]["development"] = _artifact(Path(receipt["measurements"]["development"]["path"]), measurement)
    with pytest.raises(QualificationError):
        validate_performance_result(receipt, request)

    receipt, request = _receipt_case(tmp_path, mode="certify")
    measurement = _read_json(Path(receipt["measurements"]["development"]["path"]))
    measurement["blocks"] = []
    receipt["measurements"]["development"] = _artifact(Path(receipt["measurements"]["development"]["path"]), measurement)
    with pytest.raises(QualificationError):
        validate_performance_result(receipt, request)


def test_performance_checker_rejects_resolved_asset_mismatch(tmp_path):
    from scripts.validation.windows_host_performance_evidence import validate_performance_result
    from scripts.validation.windows_qualification_inputs import QualificationError

    receipt, request = _receipt_case(tmp_path, mode="certify")
    resolved = _read_json(Path(receipt["resolved_inputs"]["development"]["path"]))
    resolved["arms"]["baseline"]["assets"]["/static/app.js"]["sha256"] = "f" * 64
    receipt["resolved_inputs"]["development"] = _artifact(Path(receipt["resolved_inputs"]["development"]["path"]), resolved)

    with pytest.raises(QualificationError):
        validate_performance_result(receipt, request)


def test_performance_checker_rejects_missing_receipt_write_witness(tmp_path):
    from scripts.validation.windows_host_performance_evidence import validate_performance_result
    from scripts.validation.windows_qualification_inputs import QualificationError

    receipt, request = _receipt_case(tmp_path, mode="certify")
    witness = Path(receipt["run_directory"]) / "receipt-write-witness.json"
    witness.unlink(missing_ok=True)

    with pytest.raises(QualificationError):
        validate_performance_result(receipt, request)


def test_performance_checker_rejects_semantically_wrong_environment_artifact(tmp_path):
    from scripts.validation.windows_host_performance_evidence import validate_performance_result
    from scripts.validation.windows_qualification_inputs import QualificationError

    receipt, request = _receipt_case(tmp_path, mode="certify")
    environment = _read_json(Path(receipt["environment_before"]["path"]))
    observed_path = Path(environment["observed_environment"]["path"])
    observed = _read_json(observed_path)
    observed["python"] = "9.9.9"
    environment["observed_environment"] = _artifact(observed_path, observed)
    receipt["environment_before"] = _artifact(Path(receipt["environment_before"]["path"]), environment)

    with pytest.raises(QualificationError):
        validate_performance_result(receipt, request)


def test_certify_rejects_reduced_raw_recipe_even_when_samples_are_fast(tmp_path):
    from scripts.validation.windows_host_performance_evidence import validate_performance_result
    from scripts.validation.windows_qualification_inputs import QualificationError

    receipt, request = _receipt_case(tmp_path, mode="certify", blocks=1, per_block=5)

    with pytest.raises(QualificationError):
        validate_performance_result(receipt, request)


def test_diagnostic_retains_numeric_violations_without_collection_failure(tmp_path):
    from scripts.validation.windows_host_performance_evidence import validate_performance_result

    receipt, request = _receipt_case(tmp_path, mode="diagnostic")
    measurement_path = Path(receipt["run_directory"]) / "measurement-development.json"
    measurement = performance_measurement_payload()
    for sample in measurement["pages"]["seq"]["home"]["candidate"][-9:]:
        sample["ms"] = 20.0
        sample["ended"] = sample["started"] + 0.02
    receipt["measurements"]["development"] = _artifact(measurement_path, measurement)
    seal_receipt(receipt)

    result = validate_performance_result(receipt, request)

    assert result["collection_status"] == "COMPLETE"
    assert result["acceptance_eligible"] is False
    assert any(row["metric"] == "page_ratio" and row["page"] == "home" for row in result["violations"])


def test_performance_checker_refuses_pilot_diagnostic_or_false_certify_label(tmp_path):
    from scripts.validation.windows_host_performance_evidence import validate_performance_result
    from scripts.validation.windows_qualification_inputs import QualificationError

    for mode in ("pilot", "diagnostic"):
        receipt, request = _receipt_case(tmp_path, mode=mode)
        receipt["status"] = "PASS"
        receipt["acceptance_eligible"] = True
        seal_receipt(receipt)
        result = validate_performance_result(receipt, request)
        assert result["acceptance_eligible"] is False

    receipt, request = _receipt_case(tmp_path, mode="certify")
    receipt["cleanup"] = _artifact(Path(receipt["run_directory"]) / "cleanup.json", {"normal": False})
    with pytest.raises(QualificationError):
        validate_performance_result(receipt, request)


def test_performance_checker_rejects_missing_same_window_or_partial_phase(tmp_path):
    from scripts.validation.windows_host_performance_evidence import validate_performance_result
    from scripts.validation.windows_qualification_inputs import QualificationError

    receipt, request = _receipt_case(tmp_path, mode="certify")
    receipt["measurement_window"] = _artifact(Path(receipt["run_directory"]) / "window.json", {"result": "PASS"})
    with pytest.raises(QualificationError):
        validate_performance_result(receipt, request)

    receipt, request = _receipt_case(tmp_path, mode="certify")
    del receipt["measurements"]["production"]
    with pytest.raises(QualificationError):
        validate_performance_result(receipt, request)


def test_performance_checker_consumes_resolved_inputs_and_asset_prefix(tmp_path):
    from scripts.validation.windows_host_performance_evidence import validate_performance_result
    from scripts.validation.windows_qualification_inputs import QualificationError

    receipt, request = _receipt_case(tmp_path, mode="certify", asset_prefix="/conformance/ai/assets/")
    result = validate_performance_result(receipt, request)
    assert result["acceptance_eligible"] is True

    receipt, request = _receipt_case(tmp_path, mode="certify", asset_prefix="/conformance/ai/assets/")
    receipt["resolved_inputs"]["development"] = _artifact(
        Path(receipt["run_directory"]) / "resolved-development.json",
        {"phase": "development", "recipe_id": "windows-mdb2-s0b-r1"},
    )
    with pytest.raises(QualificationError):
        validate_performance_result(receipt, request)


def test_performance_cli_returns_nonzero_when_late_error_survives_pass(monkeypatch, tmp_path):
    from scripts.validation import windows_host_performance as performance

    monkeypatch.setattr(performance, "load_performance_request", lambda *args, **kwargs: {"request": True})
    monkeypatch.setattr(performance, "run_performance", lambda *args, **kwargs: {
        "status": "PASS",
        "errors": [{"type": "guard_release", "message": "failed after verdict"}],
        "acceptance_eligible": True,
    })

    assert performance.main(["--mode", "certify", "--inputs", str(tmp_path / "in.json"), "--output", str(tmp_path / "out.json")]) == 1


def test_performance_driver_prepares_raw_root_before_benchmark(monkeypatch, tmp_path):
    from scripts.validation import windows_host_environment as environment
    from scripts.validation import windows_host_performance as performance
    from scripts.validation import windows_host_benchmark as benchmark

    request = _driver_request(tmp_path)
    monkeypatch.setattr(performance, "environment_identity", lambda request, directory: _environment_identity_payload(directory, request))
    monkeypatch.setattr(environment, "source_snapshot", lambda root: {"head": "dashboard-source"})
    monkeypatch.setattr(environment, "machine_snapshot", lambda **kwargs: {"processes": [], "cpu": {"idle": 1, "kernel": 2, "user": 3}})

    def fake_benchmark(root, python, window, *, recipe):
        assert not root.exists()
        root.mkdir(parents=True)
        return _benchmark_payload(window)

    monkeypatch.setattr(benchmark, "run_benchmark", fake_benchmark)

    receipt = performance.run_performance(request, mode="certify")

    assert receipt["status"] == "PASS"
    assert (tmp_path / "out-performance-run" / "raw").is_dir()


def test_performance_driver_captures_environment_under_guard(monkeypatch, tmp_path):
    from scripts.validation import windows_host_environment as environment
    from scripts.validation import windows_host_performance as performance
    from scripts.validation import windows_host_benchmark as benchmark

    request = _driver_request(tmp_path)
    calls = []

    def guarded_environment_identity(request_arg, directory):
        calls.append(Path(directory).name)
        assert (request_arg["_paths"]["owned_root"] / "HEAVY_RUN_ACTIVE").exists()
        return _environment_identity_payload(directory, request_arg)

    monkeypatch.setattr(performance, "environment_identity", guarded_environment_identity)
    monkeypatch.setattr(environment, "source_snapshot", lambda root: {"head": "dashboard-source"})
    monkeypatch.setattr(environment, "machine_snapshot", lambda **kwargs: {"processes": [], "cpu": {"idle": 1, "kernel": 2, "user": 3}})
    monkeypatch.setattr(benchmark, "run_benchmark", lambda root, python, window, *, recipe: _benchmark_payload(window))

    receipt = performance.run_performance(request, mode="certify")

    assert receipt["status"] == "PASS"
    assert calls == ["before-capture", "after-capture"]


def test_performance_driver_lets_real_benchmark_own_raw_root(monkeypatch, tmp_path):
    from scripts.validation import windows_host_environment as environment
    from scripts.validation import windows_host_performance as performance
    from scripts.validation import windows_host_benchmark as benchmark

    request = _driver_request(tmp_path)
    monkeypatch.setattr(performance, "environment_identity", lambda request, directory: _environment_identity_payload(directory, request))
    monkeypatch.setattr(environment, "source_snapshot", lambda root: {"head": "dashboard-source"})
    monkeypatch.setattr(environment, "machine_snapshot", lambda **kwargs: {"processes": [], "cpu": {"idle": 1, "kernel": 2, "user": 3}})

    phase_roots = []

    def fake_phase(root, python, *, production, window, recipe=None):
        window.record["started_monotonic"] = 0.0
        phase_roots.append(root)
        assert root.parent.name == "raw"
        assert root.parent.is_dir()
        payload = performance_measurement_payload()
        payload.update(performance_transport_payload())
        payload["resolved_inputs"] = resolved_inputs_payload(production=production)
        payload["processes"] = {"cleanup": performance_phase_cleanup()}
        return shift_measurement(payload, 500 if production else 0)

    monkeypatch.setattr(benchmark, "phase", fake_phase)

    receipt = performance.run_performance(request, mode="certify")

    assert receipt["status"] == "PASS"
    assert [root.name for root in phase_roots] == ["development", "production"]


def test_real_benchmark_refuses_reused_nonempty_raw_root(tmp_path):
    from scripts.validation.windows_host_benchmark import run_benchmark

    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "stale.json").write_text("stale\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        run_benchmark(raw, tmp_path / "python.exe", object(), recipe={"blocks": 1, "per_block": 1, "warmup": 1})


def test_late_guard_release_failure_replaces_authoritative_pass_output(monkeypatch, tmp_path):
    from scripts.validation import windows_host_environment as environment
    from scripts.validation import windows_host_performance as performance
    from scripts.validation import windows_host_benchmark as benchmark

    request = _driver_request(tmp_path)
    monkeypatch.setattr(performance, "environment_identity", lambda request, directory: _environment_identity_payload(directory, request))
    monkeypatch.setattr(environment, "source_snapshot", lambda root: {"head": "dashboard-source"})
    monkeypatch.setattr(environment, "machine_snapshot", lambda **kwargs: {"processes": [], "cpu": {"idle": 1, "kernel": 2, "user": 3}})

    def fake_benchmark(root, python, window, *, recipe):
        return _benchmark_payload(window)

    monkeypatch.setattr(benchmark, "run_benchmark", fake_benchmark)
    monkeypatch.setattr(environment.MeasurementWindow, "_remove_own_guard", lambda self: (_ for _ in ()).throw(ValueError("guard release failed")))

    receipt = performance.run_performance(request, mode="certify")

    assert receipt["status"] == "FAIL"
    assert _read_json(request["_paths"]["output"])["status"] == "FAIL"


def _benchmark_payload(window):
    # The external benchmark double uses a synthetic monotonic epoch.
    window.record["started_monotonic"] = 0.0
    payload = performance_measurement_payload()
    payload.update(performance_transport_payload())
    payload["resolved_inputs"] = resolved_inputs_payload()
    payload["processes"] = {"cleanup": performance_phase_cleanup()}
    return {"development": payload, "production": {
        **shift_measurement(payload, 500), "resolved_inputs": resolved_inputs_payload(production=True),
    }}

def _receipt_case(tmp_path, *, mode: str, blocks: int | None = None, per_block: int | None = None,
                  asset_prefix: str = "/ai/assets/"):
    owned = tmp_path / "owned"
    run = owned / "run"
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    owned.mkdir(exist_ok=True)
    identity = performance_identity_payloads(repo, owned)
    proof = owned / "functional-proof.json"
    _artifact(proof, {"status": "PASS"})
    python = owned / "venv" / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True, exist_ok=True)
    python.write_text("python", encoding="utf-8")
    environment = _artifact(owned / "environment.json", environment_payload(python, owned / "venv"))
    inputs = owned / "inputs.json"
    request = {
        "schema_version": 1,
        "acceptance_profile": "full",
        "performance": {"recipe_id": "windows-mdb2-s0b-r1", "mode": mode},
        "source": identity["source"],
        "python": {"candidate": str(python), "version": "3.13.7", "environments": {"candidate": environment}},
        "candidate": {
            "version": "1.0.0",
            "wheel": str(owned / "wheels" / "ai_base_runtime-1.0.0-py3-none-any.whl"),
            "wheel_sha256": "c" * 64,
            "source_commit": "aib-source",
        },
        "owned_root": identity["owned_root"],
        "fixtures": identity["fixtures"],
        "_paths": {"inputs": inputs, "owned_root": owned, "python": python},
    }
    policy = _artifact(
        repo / POLICY_RELATIVE,
        performance_policy_payload(request),
    )
    functional = _artifact(
        repo / FUNCTIONAL_RELATIVE,
        functional_acceptance_payload(request, proof),
    )
    request["performance"].update(policy_ref=policy, functional_acceptance_ref=functional)
    producer = {key: value for key, value in request.items() if key != "_paths"}
    selected_blocks = blocks if blocks is not None else 1 if mode == "pilot" else 4
    selected_per_block = per_block if per_block is not None else 5 if mode == "pilot" else 40
    selected_warmup = 1 if mode == "pilot" else 10
    measurement = performance_measurement_payload(
        blocks=selected_blocks,
        per_block=selected_per_block,
        warmup=selected_warmup,
    )
    measurement.update(performance_transport_payload(asset_prefix=asset_prefix))
    window = {
        "id": "window-1",
        "result": "PASS",
        "started_monotonic": 10.0,
        "ended_monotonic": 1000.0,
        "errors": [],
        "source_before": {"head": "dashboard-source"},
        "source_after": {"head": "dashboard-source"},
        "snapshots": [{"observed_owned_identities": [], "processes": [],
                       "process_classification": {"certification_blockers": []}}],
        "verdict": {"guard_id": "window-1", "written_monotonic": 990.0, "path": str(run / "receipt.json")},
    }
    receipt = {
        "schema_version": 1,
        "kind": "windows-host-performance",
        "phase": "performance",
        "mode": mode,
        "status": "PASS",
        "collection_status": "COMPLETE",
        "violations": [],
        "acceptance_eligible": mode == "certify",
        "producer_input": _artifact(inputs, producer),
        "source": deepcopy(request["source"]),
        "candidate": deepcopy(request["candidate"]),
        "fixtures": deepcopy(request["fixtures"]),
        "run_directory": str(run),
        "environment_before": _artifact(run / "environment-before.json", {
            "source_head": "dashboard-source",
            "candidate_wheel_sha256": "c" * 64,
            "observed_environment": _artifact(run / "environment-before-capture" / "environment.json", environment_payload(python, owned / "venv")),
            "runtime_import_probe": _artifact(run / "environment-before-capture" / "runtime.json", import_probe_payload(owned / "venv", repo)),
        }),
        "environment_after": _artifact(run / "environment-after.json", {
            "source_head": "dashboard-source",
            "candidate_wheel_sha256": "c" * 64,
            "observed_environment": _artifact(run / "environment-after-capture" / "environment.json", environment_payload(python, owned / "venv")),
            "runtime_import_probe": _artifact(run / "environment-after-capture" / "runtime.json", import_probe_payload(owned / "venv", repo)),
        }),
        "resolved_inputs": {
            "development": _artifact(run / "resolved-development.json", resolved_inputs_payload(
                asset_prefix=asset_prefix,
                blocks=1 if mode == "pilot" else 4,
                per_block=5 if mode == "pilot" else 40,
                warmup=1 if mode == "pilot" else 10,
            )),
            "production": _artifact(
                run / "resolved-production.json",
                resolved_inputs_payload(
                    production=True,
                    asset_prefix=asset_prefix,
                    blocks=1 if mode == "pilot" else 4,
                    per_block=5 if mode == "pilot" else 40,
                    warmup=1 if mode == "pilot" else 10,
                ),
            ),
        },
        "measurements": {
            "development": _artifact(run / "measurement-development.json", measurement),
            "production": _artifact(run / "measurement-production.json", shift_measurement(measurement, 500)),
        },
        "measurement_window": _artifact(run / "window.json", window),
        "cleanup": _artifact(run / "cleanup.json", {
            "services": {"development": performance_phase_cleanup(), "production": performance_phase_cleanup()},
            "normal": True, "owned_descendants_absent": True, "listeners_absent": True, "forced": False,
        }),
        "errors": [],
    }
    receipt_file = run / "receipt.json"
    from scripts.tests.windows_performance_support import write_json
    from scripts.validation.windows_qualification_inputs import digest_file
    write_json(receipt_file, receipt)
    _artifact(run / "receipt-write-witness.json", {
        "schema_version": 1,
        "kind": "windows-performance-receipt-write-witness",
        "receipt_path": str(receipt_file),
        "receipt_sha256": digest_file(receipt_file),
        "guard_expected_id": "window-1",
        "guard_observed_id": "window-1",
        "guard_matches": True,
        "write_started_monotonic": 1001.0,
        "write_completed_monotonic": 1001.5,
        "guard_observed_monotonic": 1001.6,
    })
    return receipt, request


def _artifact(path, payload):
    from scripts.validation.windows_qualification_inputs import digest_file
    from scripts.tests.windows_performance_support import write_json

    write_json(path, payload)
    return {"path": str(path), "sha256": digest_file(path)}


def _read_json(path):
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def _environment_identity_payload(directory, request):
    directory = Path(directory)
    prefix = request["_paths"]["python"].parent.parent
    source = Path(request["source"]["repository"])
    return {
        "source_head": "dashboard-source",
        "candidate_wheel_sha256": "c" * 64,
        "observed_environment": _artifact(directory / "environment.json", environment_payload(request["_paths"]["python"], prefix)),
        "runtime_import_probe": _artifact(directory / "runtime.json", import_probe_payload(prefix, source)),
    }


def _driver_request(tmp_path):
    return performance_driver_request(tmp_path)

from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.tests.windows_performance_support import (
    performance_measurement_payload,
    performance_transport_payload,
    resolved_inputs_payload,
)


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


def test_performance_checker_derives_certify_acceptance_from_raw_artifacts(tmp_path):
    from scripts.validation.windows_host_performance_evidence import validate_performance_result

    receipt, request = _receipt_case(tmp_path, mode="certify")

    result = validate_performance_result(receipt, request)

    assert result["acceptance_eligible"] is True
    assert result["collection_status"] == "COMPLETE"
    assert result["violations"] == []


def test_certify_rejects_reduced_raw_recipe_even_when_samples_are_fast(tmp_path):
    from scripts.validation.windows_host_performance_evidence import validate_performance_result
    from scripts.validation.windows_qualification_inputs import QualificationError

    receipt, request = _receipt_case(tmp_path, mode="certify", blocks=1, per_block=5)

    with pytest.raises(QualificationError):
        validate_performance_result(receipt, request)


def test_diagnostic_retains_numeric_violations_without_collection_failure(tmp_path):
    from scripts.validation.windows_host_performance_evidence import validate_performance_result

    receipt, request = _receipt_case(tmp_path, mode="diagnostic")
    measurement_path = tmp_path / "run" / "measurement-development.json"
    measurement = performance_measurement_payload()
    for sample in measurement["pages"]["seq"]["home"]["candidate"][-9:]:
        sample["ms"] = 20.0
    receipt["measurements"]["development"] = _artifact(measurement_path, measurement)

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
        result = validate_performance_result(receipt, request)
        assert result["acceptance_eligible"] is False

    receipt, request = _receipt_case(tmp_path, mode="certify")
    receipt["cleanup"] = _artifact(tmp_path / "run" / "cleanup.json", {"normal": False})
    with pytest.raises(QualificationError):
        validate_performance_result(receipt, request)


def test_performance_checker_rejects_missing_same_window_or_partial_phase(tmp_path):
    from scripts.validation.windows_host_performance_evidence import validate_performance_result
    from scripts.validation.windows_qualification_inputs import QualificationError

    receipt, request = _receipt_case(tmp_path, mode="certify")
    receipt["measurement_window"] = _artifact(tmp_path / "run" / "window.json", {"result": "PASS"})
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
        tmp_path / "run" / "resolved-development.json",
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
    monkeypatch.setattr(performance, "environment_identity", lambda request: {
        "source_head": "dashboard-source",
        "candidate_wheel_sha256": "c" * 64,
    })
    monkeypatch.setattr(environment, "source_snapshot", lambda root: {"head": "dashboard-source"})
    monkeypatch.setattr(environment, "machine_snapshot", lambda: {"processes": [], "cpu": {"idle": 1, "kernel": 2, "user": 3}})

    def fake_benchmark(root, python, window, *, recipe):
        assert root.exists()
        payload = performance_measurement_payload()
        payload.update(performance_transport_payload())
        payload["resolved_inputs"] = resolved_inputs_payload()
        payload["processes"] = {"cleanup": _normal_cleanup()}
        return {"development": payload, "production": {**payload, "resolved_inputs": resolved_inputs_payload(production=True)}}

    monkeypatch.setattr(benchmark, "run_benchmark", fake_benchmark)

    receipt = performance.run_performance(request, mode="certify")

    assert receipt["status"] == "PASS"
    assert (tmp_path / "out-performance-run" / "raw").is_dir()


def test_late_guard_release_failure_replaces_authoritative_pass_output(monkeypatch, tmp_path):
    from scripts.validation import windows_host_environment as environment
    from scripts.validation import windows_host_performance as performance
    from scripts.validation import windows_host_benchmark as benchmark

    request = _driver_request(tmp_path)
    monkeypatch.setattr(performance, "environment_identity", lambda request: {
        "source_head": "dashboard-source",
        "candidate_wheel_sha256": "c" * 64,
    })
    monkeypatch.setattr(environment, "source_snapshot", lambda root: {"head": "dashboard-source"})
    monkeypatch.setattr(environment, "machine_snapshot", lambda: {"processes": [], "cpu": {"idle": 1, "kernel": 2, "user": 3}})

    def fake_benchmark(root, python, window, *, recipe):
        payload = performance_measurement_payload()
        payload.update(performance_transport_payload())
        payload["resolved_inputs"] = resolved_inputs_payload()
        payload["processes"] = {"cleanup": _normal_cleanup()}
        return {"development": payload, "production": {**payload, "resolved_inputs": resolved_inputs_payload(production=True)}}

    monkeypatch.setattr(benchmark, "run_benchmark", fake_benchmark)
    monkeypatch.setattr(environment.MeasurementWindow, "_remove_own_guard", lambda self: (_ for _ in ()).throw(ValueError("guard release failed")))

    receipt = performance.run_performance(request, mode="certify")

    assert receipt["status"] == "FAIL"
    assert _read_json(request["_paths"]["output"])["status"] == "FAIL"

def _receipt_case(tmp_path, *, mode: str, blocks: int | None = None, per_block: int | None = None,
                  asset_prefix: str = "/ai/assets/"):
    run = tmp_path / "run"
    request = {
        "acceptance_profile": "full",
        "performance": {"recipe_id": "windows-mdb2-s0b-r1", "mode": mode},
        "source": {"commit": "dashboard-source"},
        "candidate": {"wheel_sha256": "c" * 64},
        "fixtures": {"fixture_vector_sha256": "d" * 64},
        "_paths": {"inputs": tmp_path / "inputs.json", "owned_root": tmp_path},
    }
    (tmp_path / "inputs.json").write_text("{}\n", encoding="utf-8")
    policy = _artifact(tmp_path / "policy.json", {
        "schema_version": 1,
        "kind": "windows-performance-policy",
        "recipe_id": "windows-mdb2-s0b-r1",
        "status": "method-frozen-not-measured",
    })
    functional = _artifact(tmp_path / "functional.json", {"schema_version": 1, "status": "PASS"})
    request["performance"].update(policy_ref=policy, functional_acceptance_ref=functional)
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
        "ended_monotonic": 20.0,
        "verdict": {"guard_id": "window-1", "written_monotonic": 19.0},
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
        "producer_input": _artifact(tmp_path / "inputs.json", {}),
        "source": deepcopy(request["source"]),
        "candidate": deepcopy(request["candidate"]),
        "fixtures": deepcopy(request["fixtures"]),
        "run_directory": str(run),
        "environment_before": _artifact(run / "environment-before.json", {
            "source_head": "dashboard-source",
            "candidate_wheel_sha256": "c" * 64,
        }),
        "environment_after": _artifact(run / "environment-after.json", {
            "source_head": "dashboard-source",
            "candidate_wheel_sha256": "c" * 64,
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
            "production": _artifact(run / "measurement-production.json", measurement),
        },
        "measurement_window": _artifact(run / "window.json", window),
        "cleanup": _artifact(run / "cleanup.json", {
            "normal": True,
            "owned_descendants_absent": True,
            "listeners_absent": True,
            "forced": False,
        }),
        "errors": [],
    }
    return receipt, request


def _artifact(path, payload):
    from scripts.validation.windows_qualification_inputs import digest_file
    from scripts.tests.windows_performance_support import write_json

    write_json(path, payload)
    return {"path": str(path), "sha256": digest_file(path)}


def _read_json(path):
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def _normal_cleanup():
    return {
        "services": {"candidate": {"stopped": True, "exit_code": 0, "forced": False, "force_requested": False, "reason": "stop_command"}},
        "normal": True,
        "owned_descendants_absent": True,
        "listeners_absent": True,
    }


def _driver_request(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    inputs = tmp_path / "inputs.json"
    inputs.write_text("{}\n", encoding="utf-8")
    python = tmp_path / "python.exe"
    python.write_text("python", encoding="utf-8")
    return {
        "acceptance_profile": "full",
        "performance": {
            "recipe_id": "windows-mdb2-s0b-r1",
            "mode": "certify",
            "policy_ref": _artifact(tmp_path / "policy.json", {
                "schema_version": 1,
                "kind": "windows-performance-policy",
                "recipe_id": "windows-mdb2-s0b-r1",
                "status": "method-frozen-not-measured",
            }),
            "functional_acceptance_ref": _artifact(tmp_path / "functional.json", {"schema_version": 1, "status": "PASS"}),
        },
        "source": {"commit": "dashboard-source", "repository": str(repo)},
        "candidate": {"version": "1.0.0", "wheel_sha256": "c" * 64},
        "fixtures": {"fixture_vector_sha256": "d" * 64},
        "_paths": {"inputs": inputs, "output": tmp_path / "out.json", "owned_root": tmp_path, "python": python},
    }

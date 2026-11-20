from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.tests.windows_performance_support import performance_measurement_payload


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


def _receipt_case(tmp_path, *, mode: str):
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
    measurement = performance_measurement_payload(blocks=1 if mode == "pilot" else 4, per_block=5 if mode == "pilot" else 40)
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
        "resolved_inputs": {
            "development": _artifact(run / "resolved-development.json", {"setting": "development"}),
            "production": _artifact(run / "resolved-production.json", {"setting": "production"}),
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


from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.tests.test_qualify_ai_runtime import _base_case, _sha, _write_json


def performance_case(tmp_path, monkeypatch, *, mode="certify"):
    case = _base_case(tmp_path, monkeypatch)
    manifest = case["manifest"]
    manifest["acceptance_profile"] = "full"
    policy = case["root"] / "openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-performance-inputs.json"
    policy.parent.mkdir(parents=True, exist_ok=True)
    _write_json(policy, {
        "schema_version": 1,
        "kind": "windows-performance-policy",
        "recipe_id": "windows-mdb2-s0b-r1",
        "status": "method-frozen-not-measured",
    })
    functional = case["root"] / "openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-functional-acceptance.json"
    _write_json(functional, {"schema_version": 1, "status": "PASS"})
    manifest["performance"] = {
        "recipe_id": "windows-mdb2-s0b-r1",
        "mode": mode,
        "policy_ref": {"path": str(policy), "sha256": _sha(policy)},
        "functional_acceptance_ref": {"path": str(functional), "sha256": _sha(functional)},
    }
    _write_json(case["inputs"], manifest)
    return case


def test_performance_request_reuses_common_input_boundaries_without_copying_external_inputs(tmp_path, monkeypatch):
    from scripts.validation.windows_host_performance_contract import load_performance_request

    case = performance_case(tmp_path, monkeypatch, mode="certify")

    request = load_performance_request(case["inputs"], case["output"], mode="certify")

    assert request["performance"]["recipe_id"] == "windows-mdb2-s0b-r1"
    assert Path(request["performance"]["policy_ref"]["path"]).is_relative_to(case["root"])
    assert Path(request["performance"]["functional_acceptance_ref"]["path"]).is_relative_to(case["root"])
    assert request["_paths"]["output"] == case["output"]


def test_performance_contract_validates_policy_and_functional_reference_content(tmp_path, monkeypatch):
    from scripts.validation.windows_host_performance_contract import load_performance_request

    case = performance_case(tmp_path, monkeypatch, mode="certify")
    policy = Path(case["manifest"]["performance"]["policy_ref"]["path"])
    _write_json(policy, {"schema_version": 1, "kind": "wrong", "recipe_id": "windows-mdb2-s0b-r1"})
    case["manifest"]["performance"]["policy_ref"]["sha256"] = _sha(policy)
    _write_json(case["inputs"], case["manifest"])

    with pytest.raises(Exception):
        load_performance_request(case["inputs"], case["output"], mode="certify")


@pytest.mark.parametrize("mutation", ["mode", "recipe", "policy_hash", "caller_counts", "functional_escape"])
def test_performance_request_rejects_unbound_or_caller_selected_recipe_inputs(tmp_path, monkeypatch, mutation):
    from scripts.validation.windows_host_performance_contract import load_performance_request

    case = performance_case(tmp_path, monkeypatch, mode="certify")
    manifest = json.loads(case["inputs"].read_text(encoding="utf-8"))
    if mutation == "mode":
        manifest["performance"]["mode"] = "pilot"
    elif mutation == "recipe":
        manifest["performance"]["recipe_id"] = "caller-smaller-recipe"
    elif mutation == "policy_hash":
        manifest["performance"]["policy_ref"]["sha256"] = "0" * 64
    elif mutation == "caller_counts":
        manifest["performance"]["blocks"] = 1
    else:
        external = tmp_path / "external-functional.json"
        _write_json(external, {"status": "PASS"})
        manifest["performance"]["functional_acceptance_ref"] = {"path": str(external), "sha256": _sha(external)}
    _write_json(case["inputs"], manifest)

    with pytest.raises(Exception):
        load_performance_request(case["inputs"], case["output"], mode="certify")

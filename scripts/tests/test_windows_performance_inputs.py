from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.tests.test_qualify_ai_runtime import _base_case, _sha, _write_json


def performance_policy_payload(manifest):
    return {
        "schema_version": 1,
        "kind": "windows-performance-policy",
        "recipe_id": "windows-mdb2-s0b-r1",
        "status": "method-frozen-not-measured",
        "runtime": {
            "distribution": "ai-base-runtime",
            "version": manifest["candidate"]["version"],
            "source_commit": manifest["candidate"]["source_commit"],
            "wheel_sha256": manifest["candidate"]["wheel_sha256"],
        },
        "environment": {
            "platform": "win32",
            "python_version": manifest["python"]["version"],
            "version_pin_count": 83,
            "artifact_id": "pf1120",
        },
        "full_recipe": {
            "settings": ["development", "production"],
            "page_keys": ["home", "projects", "project_detail", "stage_reports", "draft_edit", "bug_trend"],
            "arms": ["baseline", "candidate", "candidate_saturated"],
            "modes": {"seq": 1, "c4": 4},
            "warmup": 10,
            "blocks": 4,
            "per_block": 40,
            "page_ratio_max": 1.2,
            "spacing": {"events": 50, "interval_seconds": 0.1, "first_event_max_ms": 200, "inter_arrival_p95_max_ms": 150},
            "saturation": {
                "probe_kinds": ["loop_short", "direct_asset", "excess_stream"],
                "short_status": 200,
                "short_ms_exclusive_limit": 100,
                "excess_status": 503,
                "retry_after": "2",
                "asset_prefix": "/ai/assets/",
            },
            "production": {"debug": False, "collectstatic_required": True},
        },
        "execution_modes": {
            "pilot": {"warmup": 1, "blocks": 1, "per_block": 5, "acceptance_eligible": False},
            "diagnostic": {"uses_full_recipe": True, "acceptance_eligible": False},
            "certify": {"uses_full_recipe": True, "acceptance_eligible": True},
        },
        "identity_rule": "Per-run immutable requests bind actual clean source, installed environment and this policy hash.",
        "acceptance_rule": "The owning semantic checker recomputes the complete raw recipe, identities, same-window evidence and normal cleanup.",
        "non_claims": ["No performance measurement or certification is recorded by this method freeze."],
    }


def functional_acceptance_payload(manifest, receipt):
    return {
        "schema_version": 1,
        "acceptance_profile": "functional",
        "scope": "Windows Dashboard MDB-2 synthetic functional acceptance",
        "status": "PASS",
        "functional_status": "PASS",
        "performance_status": "NOT_RUN",
        "candidate": {
            "version": manifest["candidate"]["version"],
            "wheel_sha256": manifest["candidate"]["wheel_sha256"],
            "source_commit": manifest["candidate"]["source_commit"],
        },
        "validated_source": {"commit": manifest["source"]["commit"], "status": ""},
        "required_functional_evidence_keys": 1,
        "validated_functional_evidence_keys": 1,
        "performance_deferred_aspects": ["task:10.4", "clause:10.4:source-and-cleanup:performance"],
        "producers": {"windows-host-conformance": {"path": str(receipt), "sha256": _sha(receipt)}},
        "qualification": {"path": str(receipt), "sha256": _sha(receipt)},
        "qualification_inputs": {"path": str(receipt), "sha256": _sha(receipt)},
    }


def performance_case(tmp_path, monkeypatch, *, mode="certify"):
    case = _base_case(tmp_path, monkeypatch)
    manifest = case["manifest"]
    manifest["acceptance_profile"] = "full"
    environment = case["owned"] / "environment.json"
    _write_json(environment, {
        "executable": str(case["owned"] / "python.exe"),
        "python": manifest["python"]["version"],
        "packages": {"ai-base-runtime": {"version": manifest["candidate"]["version"], "location": str(case["owned"])}},
        "shadowed_distributions": {},
        "selected_imports": {"ai_base_runtime": str(case["owned"] / "Lib/site-packages/ai_base_runtime/__init__.py")},
        "sys_path": [str(case["owned"] / "Lib/site-packages")],
    })
    manifest["python"]["environments"] = {"candidate": {"path": str(environment), "sha256": _sha(environment)}}
    functional_proof = case["owned"] / "receipts" / "functional-proof.json"
    _write_json(functional_proof, {"status": "PASS"})
    policy = case["root"] / "openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-performance-inputs.json"
    policy.parent.mkdir(parents=True, exist_ok=True)
    _write_json(policy, performance_policy_payload(manifest))
    functional = case["root"] / "openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-functional-acceptance.json"
    _write_json(functional, functional_acceptance_payload(manifest, functional_proof))
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


def test_performance_contract_rejects_owned_marker_only_policy_or_functional_reference(tmp_path, monkeypatch):
    from scripts.validation.windows_host_performance_contract import load_performance_request

    case = performance_case(tmp_path, monkeypatch, mode="certify")
    forged_policy = case["owned"] / "not-the-reviewed-policy.json"
    forged_functional = case["owned"] / "not-functional-evidence.json"
    _write_json(forged_policy, {
        "kind": "windows-performance-policy",
        "recipe_id": "windows-mdb2-s0b-r1",
        "status": "method-frozen-not-measured",
    })
    _write_json(forged_functional, {"status": "PASS"})
    case["manifest"]["performance"]["policy_ref"] = {"path": str(forged_policy), "sha256": _sha(forged_policy)}
    case["manifest"]["performance"]["functional_acceptance_ref"] = {
        "path": str(forged_functional),
        "sha256": _sha(forged_functional),
    }
    _write_json(case["inputs"], case["manifest"])

    with pytest.raises(Exception):
        load_performance_request(case["inputs"], case["output"], mode="certify")


def test_environment_identity_captures_actual_environment_and_runtime_admission(tmp_path, monkeypatch):
    from scripts.validation import windows_host_performance_contract as contract

    case = performance_case(tmp_path, monkeypatch, mode="certify")
    request = contract.load_performance_request(case["inputs"], case["output"], mode="certify")
    expected = json.loads(Path(request["python"]["environments"]["candidate"]["path"]).read_text(encoding="utf-8"))
    environment_probe = tmp_path / "captured-environment.json"
    import_probe = tmp_path / "import-probe.json"
    _write_json(environment_probe, expected)
    _write_json(import_probe, {
        "distribution": {"version": request["candidate"]["version"]},
        "package": {"root": str(case["root"] / "ai_host")},
    })
    calls = []

    def capture_environment(python, directory):
        calls.append(("environment", python, directory))
        return expected, {"path": str(environment_probe), "sha256": _sha(environment_probe)}

    def capture_import_probe(request_arg, directory):
        calls.append(("import_probe", request_arg["_paths"]["python"], directory))
        return {"path": str(import_probe), "sha256": _sha(import_probe)}

    monkeypatch.setattr(contract, "_source_head", lambda repo: request["source"]["commit"])
    monkeypatch.setattr(contract, "capture_environment", capture_environment)
    monkeypatch.setattr(contract, "capture_import_probe", capture_import_probe)

    identity = contract.environment_identity(request, tmp_path / "capture")

    assert identity["source_head"] == request["source"]["commit"]
    assert identity["observed_environment"]["sha256"] == _sha(environment_probe)
    assert identity["runtime_import_probe"]["sha256"] == _sha(import_probe)
    assert [call[0] for call in calls] == ["environment", "import_probe"]


def test_environment_identity_rejects_source_or_environment_drift(tmp_path, monkeypatch):
    from scripts.validation import windows_host_performance_contract as contract

    case = performance_case(tmp_path, monkeypatch, mode="certify")
    request = contract.load_performance_request(case["inputs"], case["output"], mode="certify")
    expected = json.loads(Path(request["python"]["environments"]["candidate"]["path"]).read_text(encoding="utf-8"))

    monkeypatch.setattr(contract, "_source_head", lambda repo: "different-head")
    with pytest.raises(Exception):
        contract.environment_identity(request, tmp_path / "source-drift")

    monkeypatch.setattr(contract, "_source_head", lambda repo: request["source"]["commit"])
    monkeypatch.setattr(contract, "capture_environment", lambda python, directory: ({**expected, "python": "9.9.9"}, {
        "path": str(tmp_path / "env.json"),
        "sha256": "0" * 64,
    }))
    with pytest.raises(Exception):
        contract.environment_identity(request, tmp_path / "environment-drift")


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

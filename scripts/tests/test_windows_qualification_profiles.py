"""Functional-first acceptance must not hide safety gaps or promote partial proof."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from scripts.tests.test_qualify_ai_runtime import _base_case, _fake_subprocess, _sha, _write_json
from scripts.tests.test_windows_performance_inputs import functional_acceptance_payload, performance_policy_payload
from scripts.validation import qualify_ai_runtime as qualifier
from scripts.validation import windows_qualification_evidence as evidence
from scripts.validation.windows_qualification_inputs import QualificationError


def phase_case(tmp_path, monkeypatch):
    case = _base_case(tmp_path, monkeypatch)
    manifest = case["manifest"]
    manifest["acceptance_profile"] = "functional"
    coverage_path = Path(manifest["checks"]["coverage"]["path"])
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    task_row = "10.4 mixed functional and performance qualification"
    task_path = case["root"] / evidence.TASKS_PATH
    with task_path.open("a", encoding="utf-8") as stream:
        stream.write(f"\n- [ ] {task_row}\n")
    coverage["source_requirement_digests"]["10.4"] = hashlib.sha256(task_row.encode()).hexdigest()
    coverage["task_groups"].append({"task_ids": ["10.4"], "classification": "implement"})
    for name in ("B3-incremental-timing", "B9-saturation", "B5-stream-stop"):
        coverage["clauses"].append({
            "task_id": "10.4", "clause_id": name, "classification": "implement", "required_check": name,
        })
    _write_json(coverage_path, coverage)
    canonical = case["root"] / "openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-coverage.json"
    _write_json(canonical, coverage)
    manifest["checks"]["coverage"]["sha256"] = _sha(coverage_path)
    binding = deepcopy(manifest["checks"]["evidence_bindings"]["task:1.1"])
    for key in ("clause:10.4:B9-saturation:functional", "clause:10.4:B5-stream-stop:functional"):
        bound = deepcopy(binding)
        bound["covers"] = [key]
        manifest["checks"]["evidence_bindings"][key] = bound
    _write_json(case["inputs"], manifest)
    return case, coverage


def invoke(case, profile="functional"):
    return qualifier.main(["--profile", profile, "--inputs", str(case["inputs"]), "--output", str(case["output"])])


def bind_performance_refs(case, manifest, *, mode="certify"):
    policy = case["root"] / "openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-performance-inputs.json"
    functional = case["root"] / "openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-functional-acceptance.json"
    proof = case["owned"] / "receipts" / "functional-proof.json"
    _write_json(proof, {"status": "PASS"})
    _write_json(policy, performance_policy_payload(manifest))
    _write_json(functional, functional_acceptance_payload(manifest, proof))
    manifest["performance"] = {
        "recipe_id": "windows-mdb2-s0b-r1",
        "mode": mode,
        "policy_ref": {"path": str(policy), "sha256": _sha(policy)},
        "functional_acceptance_ref": {"path": str(functional), "sha256": _sha(functional)},
    }


def test_cli_requires_explicit_profile_before_any_execution(tmp_path, monkeypatch):
    case, _ = phase_case(tmp_path, monkeypatch)
    commands = _fake_subprocess(monkeypatch)
    with pytest.raises(SystemExit) as error:
        qualifier.main(["--inputs", str(case["inputs"]), "--output", str(case["output"])])
    assert error.value.code == 2
    assert commands == []


def test_functional_receipt_defers_only_performance_and_does_not_run_its_lane(tmp_path, monkeypatch):
    case, _ = phase_case(tmp_path, monkeypatch)
    commands = _fake_subprocess(monkeypatch)
    assert invoke(case) == 0
    receipt = json.loads(case["output"].read_text(encoding="utf-8"))
    assert receipt["acceptance_profile"] == "functional"
    assert receipt["functional_status"] == "PASS"
    assert receipt["performance_status"] == "NOT_RUN"
    assert "clause:10.4:B9-saturation:functional" in receipt["coverage"]["required_input_evidence"]
    assert "clause:10.4:B5-stream-stop:functional" in receipt["coverage"]["required_input_evidence"]
    assert "clause:10.4:B3-incremental-timing:performance" in receipt["coverage"]["deferred_input_evidence"]
    assert "task:10.4" in receipt["coverage"]["deferred_input_evidence"]
    for command in commands:
        if "ai_host/tests" in command:
            index = command.index("--ignore")
            assert command[index + 1] == "ai_host/tests/test_windows_baseline_equivalence.py"
        if "scripts/tests" in command:
            index = command.index("--ignore")
            assert command[index + 1] == "scripts/tests/test_windows_host_qualification.py"
    assert receipt["performance_lanes"] == {}


@pytest.mark.parametrize("name", ["B9-saturation", "B5-stream-stop"])
def test_functional_profile_rejects_missing_safety_or_saturation_evidence(tmp_path, monkeypatch, name):
    case, _ = phase_case(tmp_path, monkeypatch)
    del case["manifest"]["checks"]["evidence_bindings"][f"clause:10.4:{name}:functional"]
    _write_json(case["inputs"], case["manifest"])
    commands = _fake_subprocess(monkeypatch)
    assert invoke(case) == 1
    assert not case["output"].exists()
    assert not any("run_report_authoring_tests.py" in part for argv in commands for part in argv)


def test_functional_inputs_cannot_be_promoted_to_full_by_the_cli(tmp_path, monkeypatch):
    case, _ = phase_case(tmp_path, monkeypatch)
    commands = _fake_subprocess(monkeypatch)
    assert invoke(case, "full") == 1
    assert commands == []
    assert not case["output"].exists()


def test_full_profile_requires_performance_even_with_all_functional_bindings(tmp_path, monkeypatch):
    case, _ = phase_case(tmp_path, monkeypatch)
    case["manifest"]["acceptance_profile"] = "full"
    _write_json(case["inputs"], case["manifest"])
    _fake_subprocess(monkeypatch)
    assert invoke(case, "full") == 1
    assert not case["output"].exists()


def test_full_profile_cannot_use_ordinary_junit_as_numeric_performance_proof(tmp_path, monkeypatch):
    case, _ = phase_case(tmp_path, monkeypatch)
    manifest = case["manifest"]
    manifest["acceptance_profile"] = "full"
    source = manifest["checks"]["evidence_bindings"]["task:1.1"]
    for key in ("task:10.4", "clause:10.4:B3-incremental-timing:performance",
                "clause:10.4:B9-saturation:performance"):
        binding = deepcopy(source)
        binding["covers"] = [key]
        manifest["checks"]["evidence_bindings"][key] = binding
    _write_json(case["inputs"], manifest)
    commands = _fake_subprocess(monkeypatch)
    assert invoke(case, "full") == 1
    assert not case["output"].exists()
    assert not any("run_report_authoring_tests.py" in part for argv in commands for part in argv)


def test_performance_evidence_routes_to_dedicated_semantic_checker(tmp_path, monkeypatch):
    case, _ = phase_case(tmp_path, monkeypatch)
    manifest = case["manifest"]
    key = "clause:10.4:B3-incremental-timing:performance"
    receipt = case["owned"] / "receipts" / "performance.json"
    _write_json(receipt, {"kind": "windows-host-performance", "status": "PASS"})
    binding = deepcopy(manifest["checks"]["evidence_bindings"]["task:1.1"])
    binding.update(kind="windows-host-performance", path=str(receipt), sha256=_sha(receipt), covers=[key])
    bind_performance_refs(case, manifest)

    from scripts.validation import windows_host_performance_evidence as performance_evidence

    monkeypatch.setattr(
        performance_evidence,
        "validate_bound_receipt",
        lambda received_key, path, request: {"kind": "windows-host-performance", "key": received_key},
    )

    result = evidence.validate_binding(key, binding, manifest, (case["root"], case["owned"]))

    assert result == {"kind": "windows-host-performance", "key": key}


def test_conformance_native_receipt_cannot_substitute_for_performance_binding(tmp_path, monkeypatch):
    case, _ = phase_case(tmp_path, monkeypatch)
    manifest = case["manifest"]
    key = "clause:10.4:B3-incremental-timing:performance"
    receipt = case["owned"] / "receipts" / "native.json"
    _write_json(receipt, {"kind": "windows-host-conformance", "status": "PASS"})
    binding = deepcopy(manifest["checks"]["evidence_bindings"]["task:1.1"])
    binding.update(kind="native", path=str(receipt), sha256=_sha(receipt), covers=[key])

    with pytest.raises(QualificationError):
        evidence.validate_binding(key, binding, manifest, (case["root"], case["owned"]))


def test_aggregate_performance_replay_revalidates_policy_identity(tmp_path, monkeypatch):
    case, _ = phase_case(tmp_path, monkeypatch)
    manifest = case["manifest"]
    key = "clause:10.4:B3-incremental-timing:performance"
    receipt = case["owned"] / "receipts" / "performance.json"
    _write_json(receipt, {"kind": "windows-host-performance", "status": "PASS"})
    binding = deepcopy(manifest["checks"]["evidence_bindings"]["task:1.1"])
    binding.update(kind="windows-host-performance", path=str(receipt), sha256=_sha(receipt), covers=[key])
    manifest["performance"] = {
        "recipe_id": "windows-mdb2-s0b-r1",
        "mode": "certify",
        "policy_ref": {"path": str(case["owned"] / "missing-policy.json"), "sha256": "0" * 64},
        "functional_acceptance_ref": {"path": str(case["owned"] / "missing-functional.json"), "sha256": "0" * 64},
    }

    with pytest.raises(QualificationError):
        evidence.validate_binding(key, binding, manifest, (case["root"], case["owned"]))


@pytest.mark.parametrize("mutation", ["defer", "remove", "duplicate", "unknown"])
def test_caller_cannot_change_the_canonical_clause_census(tmp_path, monkeypatch, mutation):
    case, coverage = phase_case(tmp_path, monkeypatch)
    target = next(row for row in coverage["clauses"] if row["clause_id"] == "B5-stream-stop")
    if mutation == "defer":
        target["classification"] = "deferred-performance"
    elif mutation == "remove":
        coverage["clauses"].remove(target)
    elif mutation == "duplicate":
        coverage["clauses"].append(deepcopy(target))
    else:
        coverage["clauses"].append({"task_id": "10.4", "clause_id": "unreviewed", "classification": "implement"})
    coverage_path = Path(case["manifest"]["checks"]["coverage"]["path"])
    _write_json(coverage_path, coverage)
    case["manifest"]["checks"]["coverage"]["sha256"] = _sha(coverage_path)
    _write_json(case["inputs"], case["manifest"])
    _fake_subprocess(monkeypatch)
    assert invoke(case) == 1
    assert not case["output"].exists()


def test_real_census_keeps_all_native_safety_and_mixed_b9_aspects():
    root = Path(__file__).resolve().parents[2]
    coverage = json.loads((root / "openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-coverage.json").read_text(encoding="utf-8"))
    selected = evidence.required_evidence_keys(coverage, profile="functional")
    for name in ("B1-native-second-signal", "B4-disconnect-leaks", "M5-capacity-return", "B5-stream-stop",
                 "B7-browser-parity", "cold-and-stalled-assets", "repeat-order-matrix", "B9-saturation", "source-and-cleanup"):
        assert f"clause:10.4:{name}:functional" in selected
    assert "clause:10.4:B3-incremental-timing:performance" not in selected
    assert "task:10.4" not in selected

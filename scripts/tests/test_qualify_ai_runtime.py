from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

import pytest

from scripts.validation import qualify_ai_runtime as qualifier
from scripts.validation import windows_install_smoke as install_smoke
from scripts.validation import windows_qualification_inputs as input_validator


APP_COMMIT = "dashboard-1dbdd338"
AIB_COMMIT = "aib-d589ac8"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return path


def _write_junit(
    path: Path,
    *,
    tests: int = 1,
    failures: int = 0,
    errors: int = 0,
    skipped: int = 0,
    duplicate: bool = False,
    hidden_failure: bool = False,
) -> None:
    if duplicate:
        cases = '<testcase classname="lane" name="case_0"/><testcase classname="lane" name="case_0"/>'
    elif hidden_failure:
        cases = '<testcase classname="lane" name="case_0"><failure message="boom"/></testcase>'
    else:
        cases = "\n".join(f'<testcase classname="lane" name="case_{index}"/>' for index in range(tests))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'<testsuite tests="{tests}" failures="{failures}" errors="{errors}" skipped="{skipped}">{cases}</testsuite>',
        encoding="utf-8",
    )


def _wheel(path: Path, *, version: str = "1.0.0") -> tuple[str, dict[str, str]]:
    package_payload = b"VERSION = '1.0.0'\n"
    package_hash = hashlib.sha256(package_payload).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("ai_base_runtime/__init__.py", package_payload)
        archive.writestr("ai_base_runtime-1.0.0.dist-info/METADATA", f"Name: ai-base-runtime\nVersion: {version}\n")
    return _sha(path), {"ai_base_runtime/__init__.py": package_hash}


def _base_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    root = tmp_path / "repo"
    owned = tmp_path / "owned"
    wheelhouse = owned / "wheels"
    root.mkdir()
    owned.mkdir()
    (owned / "python.exe").write_text("synthetic python", encoding="utf-8")
    (root / "frozen.txt").write_text("frozen source\n", encoding="utf-8")
    fixture = owned / "fixtures" / "fixture.json"
    _write_json(fixture, {"fixture": "stable"})
    vector = owned / "fixtures" / "fixture-vector.json"
    _write_json(vector, {"files": [{"path": str(fixture), "sha256": _sha(fixture)}]})
    wheel = wheelhouse / "ai_base_runtime-1.0.0-py3-none-any.whl"
    wheel_hash, package_files = _wheel(wheel)
    _write_json(
        root / "ai_host" / "runtime_artifact.json",
        {
            "distribution": "ai-base-runtime",
            "version": "1.0.0",
            "wheelSha256": wheel_hash,
            "packageFiles": package_files,
            "sourceCommit": AIB_COMMIT,
        },
    )
    _write_json(owned / "owner.json", {"owner": "mdb2-windows-closure", "root": str(owned), "repository": str(root)})
    monkeypatch.setattr(qualifier, "ROOT", root)
    monkeypatch.setattr(input_validator, "ROOT", root)
    monkeypatch.setattr(install_smoke, "ROOT", root)

    task_rows = {
        "1.1": "1.1 install",
        "5.10": "5.10 host contract",
        "5.11": "5.11 qualifier",
        "6.2": "6.2 linux image",
        "10.2": "10.2 module lanes",
    }
    task_path = root / "openspec/changes/embed-ai-base-runtime-in-process/tasks.md"
    task_path.parent.mkdir(parents=True)
    task_path.write_text(
        "## Original Requirements And Evidence\n" + "\n".join(f"- [ ] {row}" for row in task_rows.values()),
        encoding="utf-8",
    )
    coverage = {
        "schema_version": 1,
        "requirement_digest_policy": "Original row text excluding its mutable checkbox; this is the initial census generation.",
        "task_groups": [
            {"task_ids": ["1.1"], "classification": "verify-existing", "owner_node": "W1.INSTALL", "required_check": "install"},
            {"task_ids": ["5.10"], "classification": "verify-existing", "owner_node": "W2.HOST", "required_check": "host"},
            {"task_ids": ["5.11"], "classification": "implement", "owner_node": "W2.HOST", "required_check": "qualifier"},
            {"task_ids": ["10.2"], "classification": "implement", "owner_node": "W3.JOIN", "required_check": "module lanes"},
            {"task_ids": ["6.2"], "classification": "deferred-with-trigger", "owner_node": "WIN.ACCEPT", "required_check": "linux"},
        ],
        "clauses": [
            {"task_id": "5.10", "clause_id": "host-order-matrix", "classification": "verify-existing", "required_check": "host order"},
            {"task_id": "5.10", "clause_id": "asgi-nonapplicability", "classification": "verify-existing", "required_check": "not a pass"},
        ],
        "source_requirement_digests": {key: hashlib.sha256(row.encode()).hexdigest() for key, row in task_rows.items()},
    }
    coverage_path = _write_json(owned / "coverage.json", coverage)
    _write_json(root / "openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-coverage.json", coverage)
    receipt_path = owned / "receipts" / "input-evidence.xml"
    _write_junit(receipt_path)
    binding = {
        "kind": "junit",
        "path": str(receipt_path),
        "sha256": _sha(receipt_path),
        "source_commit": APP_COMMIT,
        "candidate_wheel_sha256": wheel_hash,
        "fixture_vector_sha256": _sha(vector),
        "covers": ["task:1.1", "task:5.10", "clause:5.10:host-order-matrix"],
        "cases": ["lane::case_0"],
        "reuse": {"dependency_scope_unchanged": True, "scope": "same runtime, source, fixtures and dependencies"},
    }
    manifest = {
        "schema_version": 1,
        "acceptance_profile": "functional",
        "source": {
            "kind": "commit",
            "repository": str(root),
            "commit": APP_COMMIT,
            "files": [{"path": "frozen.txt", "sha256": _sha(root / "frozen.txt")}],
        },
        "candidate": {"version": "1.0.0", "wheel": str(wheel), "wheel_sha256": wheel_hash, "source_commit": AIB_COMMIT},
        "python": {"candidate": str(owned / "python.exe"), "version": "3.13.7"},
        "owned_root": {"path": str(owned), "marker": str(owned / "owner.json"), "owner": "mdb2-windows-closure"},
        "fixtures": {
            "fixture_vector": {"path": str(vector), "sha256": _sha(vector)},
            "fixture_vector_sha256": _sha(vector),
            "files": [{"path": str(fixture), "sha256": _sha(fixture)}],
        },
        "checks": {
            "coverage": {"path": str(coverage_path), "sha256": _sha(coverage_path)},
            "evidence_bindings": {"task:1.1": binding, "task:5.10": binding, "clause:5.10:host-order-matrix": binding},
        },
    }
    inputs = _write_json(owned / "inputs.json", manifest)
    return {"root": root, "owned": owned, "inputs": inputs, "output": owned / "out" / "receipt.json", "manifest": manifest}


def _fake_subprocess(
    monkeypatch: pytest.MonkeyPatch,
    *,
    lane_failures: dict[str, int] | None = None,
    fail_lane: str | None = None,
    hidden_failure_lane: str | None = None,
    duplicate_lane: str | None = None,
    mutate_source: Path | None = None,
):
    commands: list[list[str]] = []
    lane_failures = lane_failures or {}

    def fake_run(argv, cwd=None, capture_output=True, text=True, timeout=None, env=None, stdout=None, stderr=None):
        command = [str(part) for part in argv]
        commands.append(command)
        if command[:3] == ["git", "rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(command, 0, stdout=f"{APP_COMMIT}\n", stderr="")
        if command[:3] == ["git", "status", "--porcelain"]:
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        if len(command) >= 4 and command[1:4] == ["-I", "-m", "pip"]:
            return subprocess.CompletedProcess(command, 0, stdout="No broken requirements found.\n", stderr="")
        junit_path = None
        for index, item in enumerate(command):
            if item == "--junitxml":
                junit_path = Path(command[index + 1])
            elif item.startswith("--junitxml="):
                junit_path = Path(item.split("=", 1)[1])
        lane = next((part for part in command if part in qualifier.MODULE_LANES or part == "ai_host/tests/test_admission.py"), "")
        if junit_path is not None:
            _write_junit(
                junit_path,
                tests=0 if lane_failures.get(lane) == -1 else 1,
                failures=max(lane_failures.get(lane, 0), 0),
                hidden_failure=lane == hidden_failure_lane,
                duplicate=lane == duplicate_lane,
            )
        if mutate_source is not None and lane == "project_management/tests":
            mutate_source.write_text("changed during lanes\n", encoding="utf-8")
        returncode = 5 if fail_lane and lane == fail_lane else 0
        if stdout is not None:
            stdout.write(f"{lane} stdout\n")
        if stderr is not None:
            stderr.write("" if returncode == 0 else f"{lane} stderr\n")
        return subprocess.CompletedProcess(command, returncode, stdout=f"{lane} stdout\n", stderr="")

    monkeypatch.setattr(qualifier.subprocess, "run", fake_run)
    return commands


def test_qualifier_runs_registry_commands_and_writes_receipt(tmp_path, monkeypatch):
    case = _base_case(tmp_path, monkeypatch)
    commands = _fake_subprocess(monkeypatch)

    assert qualifier.main(["--profile", "functional", "--inputs", str(case["inputs"]), "--output", str(case["output"])]) == 0

    receipt = json.loads(case["output"].read_text(encoding="utf-8"))
    assert receipt["status"] == "PASS"
    assert set(receipt["module_lanes"]) == set(qualifier.MODULE_LANES)
    assert receipt["coverage"]["required_input_evidence"] == ["clause:5.10:host-order-matrix", "task:1.1", "task:5.10"]
    lane_targets = [part for command in commands for part in command if part in qualifier.MODULE_LANES]
    assert lane_targets == qualifier.MODULE_LANES
    assert all("--collect-only" not in command and "-k" not in command for command in commands)
    basetemps = [
        Path(command[index + 1])
        for command in commands
        for index, item in enumerate(command)
        if item == "--basetemp"
    ]
    assert len(basetemps) == len(set(basetemps)) == len(qualifier.MODULE_LANES) + 1


def test_input_accepts_distinct_dashboard_and_aib_commits_without_mutating_install_root(tmp_path, monkeypatch):
    case = _base_case(tmp_path, monkeypatch)
    sentinel = tmp_path / "sentinel-root"
    monkeypatch.setattr(install_smoke, "ROOT", sentinel)

    def validate_wheel_without_root(wheel, candidate):
        assert Path(wheel).is_file()
        assert candidate["source_commit"] == AIB_COMMIT

    monkeypatch.setattr(install_smoke, "validate_wheel", validate_wheel_without_root)
    request = qualifier.load_request(case["inputs"], case["output"], profile="functional")

    assert request["source"]["commit"] == APP_COMMIT
    assert request["candidate"]["source_commit"] == AIB_COMMIT
    assert install_smoke.ROOT == sentinel


def test_rejects_working_tree_release_inputs_without_writing_output(tmp_path, monkeypatch):
    case = _base_case(tmp_path, monkeypatch)
    manifest = json.loads(case["inputs"].read_text(encoding="utf-8"))
    manifest["source"]["kind"] = "working-tree"
    _write_json(case["inputs"], manifest)
    commands = _fake_subprocess(monkeypatch)

    assert qualifier.main(["--profile", "functional", "--inputs", str(case["inputs"]), "--output", str(case["output"])]) == 1

    assert not case["output"].exists()
    assert commands == []


def test_rejects_wrong_candidate_identity(tmp_path, monkeypatch):
    case = _base_case(tmp_path, monkeypatch)
    manifest = json.loads(case["inputs"].read_text(encoding="utf-8"))
    manifest["candidate"]["wheel_sha256"] = "0" * 64
    _write_json(case["inputs"], manifest)
    _fake_subprocess(monkeypatch)

    assert qualifier.main(["--profile", "functional", "--inputs", str(case["inputs"]), "--output", str(case["output"])]) == 1
    assert not case["output"].exists()


def test_rejects_missing_mandatory_coverage_binding(tmp_path, monkeypatch):
    case = _base_case(tmp_path, monkeypatch)
    manifest = json.loads(case["inputs"].read_text(encoding="utf-8"))
    del manifest["checks"]["evidence_bindings"]["clause:5.10:host-order-matrix"]
    _write_json(case["inputs"], manifest)
    _fake_subprocess(monkeypatch)

    assert qualifier.main(["--profile", "functional", "--inputs", str(case["inputs"]), "--output", str(case["output"])]) == 1
    assert not case["output"].exists()


def test_rejects_failed_junit_semantics_even_after_successful_exit(tmp_path, monkeypatch):
    case = _base_case(tmp_path, monkeypatch)
    _fake_subprocess(monkeypatch, lane_failures={"metrics/tests": 1})

    assert qualifier.main(["--profile", "functional", "--inputs", str(case["inputs"]), "--output", str(case["output"])]) == 1
    assert not case["output"].exists()


def test_rejects_case_failure_even_when_suite_totals_claim_zero_failures(tmp_path, monkeypatch):
    case = _base_case(tmp_path, monkeypatch)
    _fake_subprocess(monkeypatch, hidden_failure_lane="metrics/tests")

    assert qualifier.main(["--profile", "functional", "--inputs", str(case["inputs"]), "--output", str(case["output"])]) == 1
    assert not case["output"].exists()


def test_rejects_duplicate_or_unmapped_junit_evidence(tmp_path, monkeypatch):
    case = _base_case(tmp_path, monkeypatch)
    manifest = json.loads(case["inputs"].read_text(encoding="utf-8"))
    binding = manifest["checks"]["evidence_bindings"]["task:1.1"]
    _write_junit(Path(binding["path"]), tests=2, duplicate=True)
    binding["sha256"] = _sha(Path(binding["path"]))
    binding["cases"] = ["lane::case_0"]
    del manifest["checks"]["evidence_bindings"]["clause:5.10:host-order-matrix"]
    _write_json(case["inputs"], manifest)
    _fake_subprocess(monkeypatch)

    assert qualifier.main(["--profile", "functional", "--inputs", str(case["inputs"]), "--output", str(case["output"])]) == 1
    assert not case["output"].exists()


def test_rejects_empty_selection(tmp_path, monkeypatch):
    case = _base_case(tmp_path, monkeypatch)
    _fake_subprocess(monkeypatch, lane_failures={"ui_web/tests": -1})

    assert qualifier.main(["--profile", "functional", "--inputs", str(case["inputs"]), "--output", str(case["output"])]) == 1
    assert not case["output"].exists()


def test_rejects_command_failure(tmp_path, monkeypatch):
    case = _base_case(tmp_path, monkeypatch)
    _fake_subprocess(monkeypatch, fail_lane="scripts/tests")

    assert qualifier.main(["--profile", "functional", "--inputs", str(case["inputs"]), "--output", str(case["output"])]) == 1
    assert not case["output"].exists()


def test_rejects_collect_only_evidence_and_stale_receipt_hash(tmp_path, monkeypatch):
    case = _base_case(tmp_path, monkeypatch)
    manifest = json.loads(case["inputs"].read_text(encoding="utf-8"))
    binding = manifest["checks"]["evidence_bindings"]["task:1.1"]
    Path(binding["path"]).write_text('{"result":"PASS"}\n', encoding="utf-8")
    binding["argv"] = ["python", "-m", "pytest", "--collect-only", "ai_host/tests"]
    _write_json(case["inputs"], manifest)
    _fake_subprocess(monkeypatch)

    assert qualifier.main(["--profile", "functional", "--inputs", str(case["inputs"]), "--output", str(case["output"])]) == 1
    assert not case["output"].exists()


def test_rejects_receipt_kind_until_owned_schema_checker_exists(tmp_path, monkeypatch):
    case = _base_case(tmp_path, monkeypatch)
    manifest = json.loads(case["inputs"].read_text(encoding="utf-8"))
    binding = manifest["checks"]["evidence_bindings"]["task:1.1"]
    receipt = {
        "result": "PASS",
        "verified": {"artifact": True, "payload": True, "source": True, "candidate": True, "fixtures": True},
        "source": {"commit": APP_COMMIT},
        "candidate": {"version": "1.0.0", "wheel_sha256": manifest["candidate"]["wheel_sha256"]},
        "fixtures": {"fixture_vector_sha256": manifest["fixtures"]["fixture_vector_sha256"]},
    }
    _write_json(Path(binding["path"]), receipt)
    binding["kind"] = "receipt"
    binding["sha256"] = _sha(Path(binding["path"]))
    _write_json(case["inputs"], manifest)
    _fake_subprocess(monkeypatch)

    assert qualifier.main(["--profile", "functional", "--inputs", str(case["inputs"]), "--output", str(case["output"])]) == 1
    assert not case["output"].exists()


def test_rejects_native_false_pass_without_semantic_cleanup(tmp_path, monkeypatch):
    case = _base_case(tmp_path, monkeypatch)
    manifest = json.loads(case["inputs"].read_text(encoding="utf-8"))
    binding = manifest["checks"]["evidence_bindings"]["task:1.1"]
    native_receipt = {
        "result": "PASS",
        "cleanup": {"normal": False, "forced": False},
        "verified": {"semantic": False},
        "source": {"commit": APP_COMMIT},
        "candidate": {"version": "1.0.0", "wheel_sha256": manifest["candidate"]["wheel_sha256"]},
        "fixtures": {"fixture_vector_sha256": manifest["fixtures"]["fixture_vector_sha256"]},
    }
    _write_json(Path(binding["path"]), native_receipt)
    binding["kind"] = "native"
    binding["sha256"] = _sha(Path(binding["path"]))
    _write_json(case["inputs"], manifest)
    _fake_subprocess(monkeypatch)

    assert qualifier.main(["--profile", "functional", "--inputs", str(case["inputs"]), "--output", str(case["output"])]) == 1
    assert not case["output"].exists()


def test_rejects_empty_coverage_or_missing_requirement_digests(tmp_path, monkeypatch):
    case = _base_case(tmp_path, monkeypatch)
    manifest = json.loads(case["inputs"].read_text(encoding="utf-8"))
    coverage_path = Path(manifest["checks"]["coverage"]["path"])
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    coverage["task_groups"] = []
    coverage["source_requirement_digests"] = {}
    _write_json(coverage_path, coverage)
    manifest["checks"]["coverage"]["sha256"] = _sha(coverage_path)
    _write_json(case["inputs"], manifest)
    _fake_subprocess(monkeypatch)

    assert qualifier.main(["--profile", "functional", "--inputs", str(case["inputs"]), "--output", str(case["output"])]) == 1
    assert not case["output"].exists()


def test_rejects_unknown_requirement_digest_policy(tmp_path, monkeypatch):
    case = _base_case(tmp_path, monkeypatch)
    manifest = json.loads(case["inputs"].read_text(encoding="utf-8"))
    coverage_path = Path(manifest["checks"]["coverage"]["path"])
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    coverage["requirement_digest_policy"] = "Original row text excluding its mutable checkbox"
    _write_json(coverage_path, coverage)
    manifest["checks"]["coverage"]["sha256"] = _sha(coverage_path)
    _write_json(case["inputs"], manifest)
    _fake_subprocess(monkeypatch)

    assert qualifier.main(["--profile", "functional", "--inputs", str(case["inputs"]), "--output", str(case["output"])]) == 1
    assert not case["output"].exists()


@pytest.mark.parametrize("mutation", ["text", "missing_task", "missing_policy"])
def test_requirement_integrity_is_checked_against_the_actual_task_source(tmp_path, monkeypatch, mutation):
    case = _base_case(tmp_path, monkeypatch)
    manifest = json.loads(case["inputs"].read_text(encoding="utf-8"))
    if mutation == "text":
        task_path = case["root"] / "openspec/changes/embed-ai-base-runtime-in-process/tasks.md"
        task_path.write_text(task_path.read_text(encoding="utf-8").replace("host contract", "relaxed"), encoding="utf-8")
    else:
        coverage_path = Path(manifest["checks"]["coverage"]["path"])
        coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
        if mutation == "missing_policy":
            del coverage["requirement_digest_policy"]
        else:
            coverage["task_groups"] = [row for row in coverage["task_groups"] if row["task_ids"] != ["1.1"]]
            del coverage["source_requirement_digests"]["1.1"]
        _write_json(coverage_path, coverage)
        manifest["checks"]["coverage"]["sha256"] = _sha(coverage_path)
        _write_json(case["inputs"], manifest)
    _fake_subprocess(monkeypatch)
    assert qualifier.main(["--profile", "functional", "--inputs", str(case["inputs"]), "--output", str(case["output"])]) == 1
    assert not case["output"].exists()


def test_actual_census_preserves_both_numbered_and_publication_requirements():
    from scripts.validation.windows_qualification_evidence import validate_requirement_digests

    change = Path(__file__).resolve().parents[2] / "openspec/changes/embed-ai-base-runtime-in-process"
    coverage = json.loads((change / "evidence/windows-coverage.json").read_text(encoding="utf-8"))
    assert "PUB.CORRELATION" in coverage["source_requirement_digests"]
    validate_requirement_digests(coverage, change / "tasks.md")


def test_rejects_empty_source_fixture_bindings_and_fixture_escape(tmp_path, monkeypatch):
    case = _base_case(tmp_path, monkeypatch)
    manifest = json.loads(case["inputs"].read_text(encoding="utf-8"))
    external = tmp_path / "external-fixture.json"
    _write_json(external, {"fixture": "outside"})
    manifest["source"]["files"] = []
    manifest["fixtures"]["files"] = [{"path": str(external), "sha256": _sha(external)}]
    manifest["fixtures"]["fixture_vector"] = {"path": str(external), "sha256": _sha(external)}
    manifest["fixtures"]["fixture_vector_sha256"] = _sha(external)
    for binding in manifest["checks"]["evidence_bindings"].values():
        binding["fixture_vector_sha256"] = _sha(external)
    _write_json(case["inputs"], manifest)
    _fake_subprocess(monkeypatch)

    assert qualifier.main(["--profile", "functional", "--inputs", str(case["inputs"]), "--output", str(case["output"])]) == 1
    assert not case["output"].exists()


def test_rejects_wrong_aib_source_commit_mismatch(tmp_path, monkeypatch):
    case = _base_case(tmp_path, monkeypatch)
    manifest = json.loads(case["inputs"].read_text(encoding="utf-8"))
    manifest["candidate"]["source_commit"] = "wrong-aib-commit"
    _write_json(case["inputs"], manifest)
    _fake_subprocess(monkeypatch)

    assert qualifier.main(["--profile", "functional", "--inputs", str(case["inputs"]), "--output", str(case["output"])]) == 1
    assert not case["output"].exists()


def test_checks_untracked_source_and_rehashes_after_lanes(tmp_path, monkeypatch):
    case = _base_case(tmp_path, monkeypatch)
    commands = _fake_subprocess(monkeypatch, mutate_source=case["root"] / "frozen.txt")

    assert qualifier.main(["--profile", "functional", "--inputs", str(case["inputs"]), "--output", str(case["output"])]) == 1
    assert not case["output"].exists()
    status_commands = [command for command in commands if command[:3] == ["git", "status", "--porcelain"]]
    assert status_commands
    assert all("--untracked-files=no" not in command for command in status_commands)


def test_command_failure_preserves_command_receipt_and_logs(tmp_path, monkeypatch):
    case = _base_case(tmp_path, monkeypatch)
    _fake_subprocess(monkeypatch, fail_lane="scripts/tests")

    assert qualifier.main(["--profile", "functional", "--inputs", str(case["inputs"]), "--output", str(case["output"])]) == 1

    command_receipts = list((case["owned"] / "qualifier-runs").glob("*/logs/lane-7.command.json"))
    assert command_receipts
    payload = json.loads(command_receipts[0].read_text(encoding="utf-8"))
    assert payload["returncode"] == 5
    assert payload["argv"]
    assert Path(payload["stdout"]).is_file()
    assert Path(payload["stderr"]).is_file()


@pytest.mark.parametrize("mutation", ["source", "fixture"])
def test_rejects_stale_source_or_fixture_hashes(tmp_path, monkeypatch, mutation):
    case = _base_case(tmp_path, monkeypatch)
    if mutation == "source":
        (case["root"] / "frozen.txt").write_text("changed\n", encoding="utf-8")
    else:
        fixture = case["owned"] / "fixtures" / "fixture.json"
        _write_json(fixture, {"fixture": "changed"})
    _fake_subprocess(monkeypatch)

    assert qualifier.main(["--profile", "functional", "--inputs", str(case["inputs"]), "--output", str(case["output"])]) == 1
    assert not case["output"].exists()


def test_rejects_output_reuse_or_escape(tmp_path, monkeypatch):
    case = _base_case(tmp_path, monkeypatch)
    _fake_subprocess(monkeypatch)
    case["output"].parent.mkdir(parents=True)
    case["output"].write_text("exists", encoding="utf-8")

    assert qualifier.main(["--profile", "functional", "--inputs", str(case["inputs"]), "--output", str(case["output"])]) == 1
    assert qualifier.main(["--profile", "functional", "--inputs", str(case["inputs"]), "--output", str(tmp_path / "escape.json")]) == 1

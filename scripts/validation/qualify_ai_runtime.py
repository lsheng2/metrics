"""Fail-closed Windows final qualifier for the embedded AI runtime."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import time
import uuid


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.validation.project_full_stack_support import write_json
from scripts.validation import windows_qualification_inputs as inputs
from scripts.validation.windows_qualification_evidence import (
    MODULE_LANES,
    validate_argv,
    validate_coverage,
    validate_junit,
)
from scripts.validation.windows_qualification_inputs import QualificationError
from scripts.validation.windows_qualification_profiles import (
    PERFORMANCE_TESTS,
    PROFILES,
    functional_lane_exclusions,
    require_profile,
)


BASE_PYTEST_ARGS = ["-q", "--tb=short", "-p", "no:cacheprovider", "-o", "asyncio_default_fixture_loop_scope=function"]


def load_request(input_arg: str | Path, output_arg: str | Path, *, profile: str) -> dict:
    return inputs.load_request(input_arg, output_arg, profile=require_profile(profile))


def git_value(args: list[str], repo: Path) -> str:
    completed = subprocess.run(args, cwd=repo, capture_output=True, text=True, timeout=30)
    if completed.returncode:
        raise QualificationError(f"git command failed: {' '.join(args)}")
    return completed.stdout.strip()


def source_identity(repo: Path, expected_commit: str) -> dict:
    head = git_value(["git", "rev-parse", "HEAD"], repo)
    status = git_value(["git", "status", "--porcelain"], repo)
    if head != expected_commit:
        raise QualificationError("source commit mismatch")
    if status:
        raise QualificationError("source tree is not frozen")
    return {"commit": head, "status": status}


def pytest_command(python: Path, target: str, junit: Path, basetemp: Path) -> list[str]:
    selection = [part for path in functional_lane_exclusions(target) for part in ("--ignore", path)]
    if target == "ai_host/tests/conformance_performance_cases.py":
        selection += [
            "-p", "ai_base_runtime.testkit.pytest_plugin", "-p", "ai_host.tests.conformance_fixtures",
            "-o", "ai_host_modes=blocking_wsgi",
        ]
    return [
        str(python),
        "-I",
        "scripts/validation/run_report_authoring_tests.py",
        target,
        *selection,
        "-p", "scripts.validation.pytest_execution_inventory",
        "--execution-inventory", str(junit.with_suffix(".inventory.json")),
        *BASE_PYTEST_ARGS,
        "--basetemp",
        str(basetemp),
        "--junitxml",
        str(junit),
    ]


def run_command(argv: list[str], *, cwd: Path, log_dir: Path, label: str, timeout: int = 3600,
                env: dict[str, str] | None = None, expected_returncode: int = 0) -> dict:
    validate_argv(argv)
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / f"{label}.stdout.txt"
    stderr_path = log_dir / f"{label}.stderr.txt"
    record_path = log_dir / f"{label}.command.json"
    result = {
        "label": label, "argv": argv, "stdout": str(stdout_path), "stderr": str(stderr_path),
        "cwd": str(cwd), "timeout_seconds": timeout, "expected_returncode": expected_returncode,
    }
    try:
        with stdout_path.open("w", encoding="utf-8", errors="replace") as stdout, stderr_path.open("w", encoding="utf-8", errors="replace") as stderr:
            completed = subprocess.run(argv, cwd=cwd, stdout=stdout, stderr=stderr, text=True, timeout=timeout, env=env)
        result["returncode"] = completed.returncode
        result["timed_out"] = False
    except subprocess.TimeoutExpired as error:
        result.update(returncode=None, timed_out=True, timeout=str(error), cleanup_uncertain=True)
        result.update(stdout_sha256=inputs.digest_file(stdout_path), stderr_sha256=inputs.digest_file(stderr_path))
        write_json(record_path, result)
        raise QualificationError(f"{label} command timed out; cleanup uncertain; receipt={record_path}") from error
    result.update(stdout_sha256=inputs.digest_file(stdout_path), stderr_sha256=inputs.digest_file(stderr_path))
    write_json(record_path, result)
    if result["returncode"] != expected_returncode:
        raise QualificationError(f"{label} command failed; receipt={record_path}")
    return {**result, "receipt": str(record_path)}


def run_pytest_lane(python: Path, target: str, *, run_root: Path, label: str,
                    basetemp_root: Path | None = None) -> dict:
    junit = run_root / "junit" / f"{label}.xml"
    basetemp = (basetemp_root or run_root / "basetemp") / label
    basetemp.parent.mkdir(parents=True, exist_ok=True)
    result = run_command(pytest_command(python, target, junit, basetemp), cwd=ROOT, log_dir=run_root / "logs", label=label)
    from scripts.validation.pytest_junit_reconciliation import reconcile_junit, validate_reconciled_junit
    inventory = junit.with_suffix(".inventory.json")
    derived = junit.with_suffix(".verified.xml")
    reconciliation = reconcile_junit(
        junit, inventory, derived, pytest_args=result["argv"][3:], repo_root=ROOT,
    )
    proof_path = junit.with_suffix(".reconciliation.json")
    write_json(proof_path, reconciliation)
    result["junit"] = {
        **validate_reconciled_junit(reconciliation, pytest_args=result["argv"][3:], repo_root=ROOT),
        "path": str(derived),
    }
    result["report_reconciliation"] = {"path": str(proof_path), "sha256": inputs.digest_file(proof_path)}
    result["raw_junit"] = reconciliation["sources"]["raw_junit"]
    result["execution_inventory"] = reconciliation["sources"]["execution_inventory"]
    result["basetemp"] = str(basetemp)
    return result


def revalidate_frozen_inputs(request: dict) -> None:
    paths = request["_paths"]
    inputs.validate_frozen_hashes(ROOT.resolve(), request["source"], request["fixtures"], (ROOT.resolve(), paths["owned_root"]))


def qualify(request: dict) -> dict:
    paths = request["_paths"]
    owned_root = paths["owned_root"]
    run_id = uuid.uuid4()
    run_root = owned_root / "qualifier-runs" / str(run_id)
    # Keep Git fixture metadata below Windows repository-path limits without
    # changing the archive format or weakening any tested path/ownership guard.
    basetemp_root = inputs.canonical(owned_root / "qt" / run_id.hex, must_exist=False)
    (run_root / "logs").mkdir(parents=True)
    (run_root / "junit").mkdir()
    source_before = source_identity(ROOT, request["source"]["commit"])
    revalidate_frozen_inputs(request)
    coverage = validate_coverage(request, paths["coverage"], (ROOT.resolve(), owned_root))
    python = paths["python"]
    commands = [run_pytest_lane(
        python, "ai_host/tests/test_admission.py", run_root=run_root, label="admission",
        basetemp_root=basetemp_root,
    )]
    commands.append(run_command([str(python), "-I", "-m", "pip", "check"], cwd=ROOT, log_dir=run_root / "logs", label="pip-check"))
    module_results = {
        lane: run_pytest_lane(
            python, lane, run_root=run_root, label=f"lane-{index}", basetemp_root=basetemp_root,
        )
        for index, lane in enumerate(MODULE_LANES, start=1)
    }
    performance_results = {
        target: run_pytest_lane(
            python, target, run_root=run_root, label=f"performance-{index}", basetemp_root=basetemp_root,
        )
        for index, target in enumerate(PERFORMANCE_TESTS, start=1)
    } if request["acceptance_profile"] == "full" else {}
    revalidate_frozen_inputs(request)
    source_after = source_identity(ROOT, request["source"]["commit"])
    return {
        "schema_version": 1,
        "status": "PASS",
        "acceptance_profile": request["acceptance_profile"],
        "functional_status": "PASS",
        "performance_status": "PASS" if request["acceptance_profile"] == "full" else "NOT_RUN",
        "tool": "qualify_ai_runtime.py",
        "created_at_unix": time.time(),
        "source_before": source_before,
        "source_after": source_after,
        "candidate": {"version": request["candidate"]["version"], "wheel_sha256": request["candidate"]["wheel_sha256"]},
        "coverage": coverage,
        "commands": commands,
        "module_lanes": module_results,
        "performance_lanes": performance_results,
        "deferred_test_paths": list(PERFORMANCE_TESTS) if request["acceptance_profile"] == "functional" else [],
        "run_root": str(run_root),
    }


def write_failure(request: dict | None, error: BaseException) -> None:
    if request is None or "_paths" not in request:
        return
    try:
        failure = request["_paths"]["owned_root"] / "qualifier-failures" / f"{uuid.uuid4()}.json"
        write_json(failure, {"status": "FAIL", "error": str(error), "type": type(error).__name__, "cleanup_uncertain": "timed out" in str(error)})
    except Exception:
        return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--profile", required=True, choices=PROFILES)
    args = parser.parse_args(argv)
    request = None
    try:
        request = load_request(args.inputs, args.output, profile=args.profile)
        receipt = qualify(request)
        write_json(request["_paths"]["output"], receipt)
        return 0
    except Exception as error:
        print(f"qualify_ai_runtime: {error}", file=sys.stderr)
        write_failure(request, error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

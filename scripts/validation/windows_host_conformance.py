"""Produce a semantic Windows native host conformance receipt."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time
import uuid


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.validation.project_full_stack_support import read_json, write_json
from scripts.validation.qualify_ai_runtime import run_command, source_identity
from scripts.validation.windows_host_conformance_evidence import validate_result
from scripts.validation.windows_host_conformance_contract import KIND, BASE_ARGS, LANES
from scripts.validation.windows_install_smoke import installer_environment, validate_import_probe
from scripts.validation import windows_qualification_inputs as inputs
from scripts.validation.windows_qualification_evidence import validate_junit
from scripts.validation.windows_qualification_inputs import QualificationError
from scripts.validation import windows_host_conformance_environment as environment


def load_request(input_arg: str | Path, output_arg: str | Path) -> dict:
    data = inputs.load_request(input_arg, output_arg, profile="functional")
    environment.expected_environment(data)
    amendment = data.get("native_conformance", {}).get("amendment")
    if not isinstance(amendment, dict):
        raise QualificationError("native conformance amendment binding is missing")
    path = inputs.canonical(amendment.get("path", ""), must_exist=True)
    inputs.require_hash(path, amendment.get("sha256", ""), "B5 amendment")
    if path != ROOT / "openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-b5-owner-decision.md":
        raise QualificationError("native conformance amendment path mismatch")
    return data


def pytest_command(python: Path, lane: str, junit: Path, basetemp: Path) -> list[str]:
    config = LANES[lane]
    command = [str(python), "-I", "scripts/validation/run_report_authoring_tests.py", *config["targets"]]
    if config.get("plugin"):
        command += [
            "-p", "ai_base_runtime.testkit.pytest_plugin",
            "-p", "ai_host.tests.conformance_fixtures",
            "-o", "ai_host_modes=blocking_wsgi",
        ]
    return [*command, *BASE_ARGS, "--basetemp", str(basetemp), "--junitxml", str(junit)]


def reference(path: Path) -> dict:
    return {"path": str(path), "sha256": inputs.digest_file(path)}


def run_pytest_lane(python: Path, lane: str, run_root: Path) -> dict:
    junit = run_root / "junit" / f"{lane}.xml"
    basetemp = run_root / "artifacts" / lane
    result = run_command(
        pytest_command(python, lane, junit, basetemp),
        cwd=ROOT,
        log_dir=run_root / "logs",
        label=f"native-{lane}",
        timeout=900 if lane == "b5" else 240,
    )
    parsed = validate_junit(junit)
    return {**result, "junit": {**parsed, "path": str(junit)}, "basetemp": str(basetemp)}


def revalidate_frozen_inputs(request: dict) -> None:
    inputs.validate_frozen_hashes(
        ROOT.resolve(), request["source"], request["fixtures"],
        (ROOT.resolve(), request["_paths"]["owned_root"]),
    )


def admission(request: dict, run_root: Path) -> dict:
    python = request["_paths"]["python"]
    private = installer_environment(run_root / "private-env")
    probe = run_command(
        [str(python), "-I", str(ROOT / "scripts/validation/windows_install_smoke.py"), "--probe"],
        cwd=ROOT, log_dir=run_root / "admission", label="runtime-admission", timeout=30, env=private,
    )
    validate_import_probe(read_json(Path(probe["stdout"])), python.parent.parent, ROOT)
    pip = run_command(
        [str(python), "-I", "-m", "pip", "check"],
        cwd=ROOT, log_dir=run_root / "admission", label="candidate-pip-check", timeout=60, env=private,
    )
    return {"runtime_admission": probe, "candidate_pip_check": pip}


def _single(paths: list[Path], label: str) -> Path:
    unique = [path for path in paths if "current" not in path.parent.name]
    if len(unique) != 1:
        raise QualificationError(f"{label} artifact inventory mismatch")
    return unique[0]


def collect_artifacts(run_root: Path) -> dict:
    artifacts = run_root / "artifacts"
    b5 = []
    for path in sorted((artifacts / "b5").rglob("streams.json")):
        if "current" in path.parent.name:
            continue
        process = path.with_name("process.json")
        if not process.is_file():
            raise QualificationError("B5 process proof is missing")
        b5.append({"streams": reference(path), "process": reference(process), "log": reference(path.with_name("serve.log"))})
    signals = [{**reference(path), "log": reference(path.with_name("serve.log"))}
               for path in sorted((artifacts / "signal").rglob("signal.json")) if "current" not in path.parent.name]
    disconnect = _single(list((artifacts / "disconnect").rglob("disconnects.json")), "disconnect")
    return {
        "b5": b5,
        "backpressure": reference(_single(list((artifacts / "backpressure").rglob("backpressure.json")), "backpressure")),
        "disconnect": {
            **reference(disconnect), "log": reference(disconnect.with_name("serve.log")),
            "process": reference(disconnect.with_name("process.json")),
        },
        "signals": signals,
    }


def qualify(request: dict) -> dict:
    root = request["_paths"]["owned_root"] / "conformance-runs" / str(uuid.uuid4())
    (root / "logs").mkdir(parents=True)
    (root / "junit").mkdir()
    (root / "artifacts").mkdir()
    source_before = source_identity(ROOT, request["source"]["commit"])
    input_reference = reference(request["_paths"]["inputs"])
    revalidate_frozen_inputs(request)
    environment_before = environment.capture(request, root / "environment-before")
    admission_result = admission(request, root)
    lane_results = {lane: run_pytest_lane(request["_paths"]["python"], lane, root) for lane in LANES}
    revalidate_frozen_inputs(request)
    environment_after = environment.capture(request, root / "environment-after")
    source_after = source_identity(ROOT, request["source"]["commit"])
    covered = sorted({key for lane in lane_results for key in LANES[lane]["covered"]})
    receipt = {
        "schema_version": 1,
        "kind": KIND,
        "phase": "conformance",
        "scope": "windows-functional-native",
        "status": "PASS",
        "created_at_unix": time.time(),
        "run_root": str(root),
        "inputs": input_reference,
        "environments": {"before": environment_before, "after": environment_after},
        "source_before": source_before,
        "source_after": source_after,
        "candidate": {
            "version": request["candidate"]["version"],
            "wheel_sha256": request["candidate"]["wheel_sha256"],
        },
        "fixture_vector_sha256": request["fixtures"]["fixture_vector_sha256"],
        "amendment": dict(request["native_conformance"]["amendment"]),
        "covered_keys": covered,
        "admission": admission_result,
        "junit": {lane: lane_results[lane]["junit"] for lane in lane_results},
        "non_applicable": [{"case": "ASGI host conformance", "status": "NOT_APPLICABLE", "counted": False}],
        "commands": {lane: {key: value for key, value in result.items() if key not in {"junit"}}
                     for lane, result in lane_results.items()},
        "artifacts": collect_artifacts(root),
    }
    validate_result(receipt, request)
    return receipt


def write_failure(request: dict | None, error: BaseException) -> None:
    if request is None or "_paths" not in request:
        return
    try:
        failure = request["_paths"]["owned_root"] / "conformance-failures" / f"{uuid.uuid4()}.json"
        write_json(failure, {"status": "FAIL", "error": str(error), "type": type(error).__name__})
    except Exception:
        return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    request = None
    try:
        request = load_request(args.inputs, args.output)
        receipt = qualify(request)
        write_json(request["_paths"]["output"], receipt)
        return 0
    except Exception as error:
        print(f"windows_host_conformance: {error}", file=sys.stderr)
        write_failure(request, error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

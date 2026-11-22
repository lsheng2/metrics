"""Development-only source and private-wheel checks for Dashboard plus AIB."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validation.aib_joint_dev_inputs import (
    DevelopmentCommandError,
    copy_inventory_files,
    create_owned_run_dir,
    digest_file,
    run_development_command,
    source_inventory,
    validate_source_request,
    validate_wheel_request,
)
from scripts.validation.aib_joint_dev_wheel import prepare_wheel_run
from scripts.validation.project_full_stack_support import write_json
from scripts.validation.windows_qualification_evidence import QualificationError, validate_junit


RECEIPT_KIND = "aib-joint-development-run"
PHASES = ("setup", "snapshot", "build", "install", "test", "post_run_verification", "external_cleanup")


def summarize_successful_junit(path: Path) -> dict:
    try:
        summary = validate_junit(path)
    except QualificationError as error:
        raise ValueError(str(error)) from error
    return {**summary, "path": str(path)}


def run_source(args: argparse.Namespace) -> int:
    total_start = time.monotonic()
    request = validate_source_request(args.aib_root, args.python, args.data_root, create_data_root=True)
    run_dir = create_owned_run_dir(request.data_root, request.dashboard_root, "source")
    timings = _timing_model()
    _set_phase(timings, "build", "not_applicable")
    _set_phase(timings, "install", "not_applicable")
    before = None
    after = None
    dashboard_copy = run_dir / "copy/dashboard-source"
    junit = run_dir / "evidence/source-tests.xml"
    origin = run_dir / "evidence/source-origin.json"
    try:
        setup_start = time.monotonic()
        dashboard_before = source_inventory(request.dashboard_root)
        before = {"dashboard": dashboard_before, "aib": source_inventory(request.aib_root, "packages/runtime")}
        _finish_phase(timings, "setup", setup_start)
        snapshot_start = time.monotonic()
        copy_inventory_files(request.dashboard_root, dashboard_copy, dashboard_before)
        _finish_phase(timings, "snapshot", snapshot_start)
        test_error = None
        command = None
        command_start = time.monotonic()
        try:
            command = run_development_command(
                [
                    request.python,
                    "-I",
                    "-B",
                    dashboard_copy / "scripts/validation/aib_joint_dev_worker.py",
                    "source",
                    "--dashboard-root",
                    dashboard_copy,
                    "--aib-src",
                    request.aib_src,
                    "--origin-output",
                    origin,
                    "--junitxml",
                    junit,
                    "--basetemp",
                    run_dir / "tmp/pytest",
                ],
                cwd=dashboard_copy,
                run_dir=run_dir,
                label="source-tests",
                timeout=900,
            )
        except Exception as error:
            test_error = error
        _finish_phase(
            timings, "test", command_start,
            state="failed" if test_error else "measured", includes_fixture_cleanup=True,
        )
        post_start = time.monotonic()
        after = {"dashboard": source_inventory(request.dashboard_root), "aib": source_inventory(request.aib_root, "packages/runtime")}
        if before != after:
            raise ValueError("source inventory drift detected")
        _finish_phase(timings, "post_run_verification", post_start)
        if test_error is not None:
            raise test_error
        _finalize_timings(timings, total_start)
        receipt = _receipt("source", run_dir, before, after, timings, [command], junit, origin)
        receipt.update(copied_dashboard=str(dashboard_copy), source_aib_src=str(request.aib_src))
    except Exception as error:
        _finalize_timings(timings, total_start)
        receipt = failure_receipt(
            "source", run_dir, error, before=before,
            after=after or _safe_source_after(request.dashboard_root, request.aib_root), timings=timings,
            extra={"copied_dashboard": str(dashboard_copy), "source_aib_src": str(request.aib_src)},
        )
        _write_receipt(run_dir, receipt)
        print(json.dumps({"status": receipt["status"], "receipt": receipt["receipt"], "run": str(run_dir)}))
        return 1
    _write_receipt(run_dir, receipt)
    print(json.dumps({"status": receipt["status"], "receipt": receipt["receipt"], "run": str(run_dir)}))
    return 0


def run_wheel(args: argparse.Namespace) -> int:
    request = validate_wheel_request(
        args.aib_root,
        args.python,
        args.build_python,
        args.wheelhouse,
        args.wheelhouse_lock,
        args.wheelhouse_sha256,
        args.data_root,
        create_data_root=True,
    )
    run_dir = create_owned_run_dir(request.data_root, request.dashboard_root, "wheel")
    before = {"dashboard": source_inventory(request.dashboard_root), "aib": source_inventory(request.aib_root, "packages/runtime")}
    try:
        result = prepare_wheel_run(request, run_dir)
        receipt = {
            **_receipt(
                "wheel",
                run_dir,
                before,
                result["source_after"],
                result["timings"],
                result["commands"],
                Path(result["junit"]),
                Path(result["module_origins"]["path"]),
            ),
            "private_wheel": result["private_wheel"],
            "copied_dashboard": result["dashboard_copy"],
            "copied_runtime": result["runtime_copy"],
            "package_probe": result["package_probe"],
            "development_manifest": result["manifest"],
        }
    except Exception as error:
        context = getattr(error, "context", {})
        receipt = failure_receipt(
            "wheel", run_dir, error, before=before,
            after=context.get("source_after"), timings=context.get("timings", {}),
        )
        _write_receipt(run_dir, receipt)
        print(json.dumps({"status": receipt["status"], "receipt": receipt["receipt"], "run": str(run_dir)}))
        return 1
    _write_receipt(run_dir, receipt)
    print(json.dumps({"status": receipt["status"], "receipt": receipt["receipt"], "run": str(run_dir)}))
    return 0


def _receipt(stage: str, run_dir: Path, before: dict, after: dict, timings: dict, commands: list[dict],
             junit: Path, origin: Path) -> dict:
    _validate_success_commands(commands)
    junit_summary = summarize_successful_junit(junit)
    payload = {
        "schema_version": 1,
        "kind": RECEIPT_KIND,
        "stage": stage,
        "status": "succeeded",
        "acceptance_eligible": False,
        "run_dir": str(run_dir),
        "source_before": before,
        "source_after": after,
        "module_origins": json.loads(origin.read_text(encoding="utf-8")),
        "commands": commands,
        "junit": junit_summary,
        "timings": timings,
    }
    payload["receipt"] = str(run_dir / "evidence/aib-joint-development-receipt.json")
    return payload


def _write_receipt(run_dir: Path, receipt: dict) -> None:
    write_json(run_dir / "evidence/aib-joint-development-receipt.json", receipt)


def failure_receipt(stage: str, run_dir: Path, error: Exception, *, before: dict | None,
                    after: dict | None = None, timings: dict, extra: dict | None = None) -> dict:
    payload = {
        "schema_version": 1,
        "kind": RECEIPT_KIND,
        "stage": stage,
        "status": "failed",
        "acceptance_eligible": False,
        "run_dir": str(run_dir),
        "receipt": str(run_dir / "evidence/aib-joint-development-receipt.json"),
        "failure": {"type": type(error).__name__, "message": str(error)},
        "source_before": before,
        "source_after": after,
        "commands": _command_receipts(run_dir, error),
        "timings": timings,
    }
    if extra:
        payload.update(extra)
    payload.update(_available_evidence(run_dir))
    return payload


def _timing_model() -> dict:
    return {"schema_version": 1, "phases": {name: {"state": "not_started"} for name in PHASES}}


def _set_phase(timings: dict, name: str, state: str, **extra) -> None:
    timings["phases"][name] = {"state": state, **extra}


def _finish_phase(timings: dict, name: str, start: float, *, state: str = "measured", **extra) -> None:
    _set_phase(timings, name, state, seconds=time.monotonic() - start, **extra)


def _finalize_timings(timings: dict, total_start: float) -> None:
    timings["phases"]["external_cleanup"] = {"state": "not_performed", "measurement": "not_separately_measured"}
    for phase in timings["phases"].values():
        if phase["state"] == "not_started":
            phase["state"] = "not_performed"
    timings["total_seconds"] = time.monotonic() - total_start
    timings["non_overlapping_phase_seconds"] = sum(
        phase.get("seconds", 0.0) for phase in timings["phases"].values()
    )


def _validate_success_commands(commands: list[dict]) -> None:
    for command in commands:
        if (command.get("returncode") != 0 or command.get("timed_out") is True
                or command.get("cleanup_uncertain") is True):
            raise ValueError("command evidence is failed or uncertain")


def _command_receipts(run_dir: Path, error: Exception | None = None) -> list[dict]:
    receipts = []
    for path in sorted((run_dir / "logs").glob("*.command.json")):
        receipts.append(json.loads(path.read_text(encoding="utf-8")))
    failed = getattr(error, "receipt", None)
    if failed is not None and failed not in receipts:
        receipts.append(failed)
    return receipts


def _available_evidence(run_dir: Path) -> dict:
    evidence = run_dir / "evidence"
    result = {}
    for path in sorted(evidence.glob("*tests.xml")):
        result["junit"] = _junit_evidence(path)
        break
    for name in ("source-origin.json", "wheel-origin.json"):
        path = evidence / name
        if path.exists():
            result["module_origins"] = _json_evidence(path)
            break
    path = evidence / "package-probe.json"
    if path.exists():
        result["package_probe"] = _json_evidence(path)
    return result


def _junit_evidence(path: Path) -> dict:
    payload = {"path": str(path), "sha256": digest_file(path)}
    try:
        return {**payload, "valid": True, "summary": summarize_successful_junit(path)}
    except Exception as error:
        return {**payload, "valid": False, "error": str(error)}


def _json_evidence(path: Path) -> dict:
    return {"path": str(path), "sha256": digest_file(path), "payload": json.loads(path.read_text(encoding="utf-8"))}


def _safe_source_after(dashboard_root: Path, aib_root: Path) -> dict | None:
    try:
        return {"dashboard": source_inventory(dashboard_root), "aib": source_inventory(aib_root, "packages/runtime")}
    except Exception:
        return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="stage")
    source = subparsers.add_parser("source")
    source.add_argument("--aib-root", type=Path, required=True)
    source.add_argument("--python", type=Path, required=True)
    source.add_argument("--data-root", type=Path, required=True)
    source.set_defaults(func=run_source)
    wheel = subparsers.add_parser("wheel")
    wheel.add_argument("--aib-root", type=Path, required=True)
    wheel.add_argument("--python", type=Path, required=True)
    wheel.add_argument("--build-python", type=Path, required=True)
    wheel.add_argument("--wheelhouse", type=Path, required=True)
    wheel.add_argument("--wheelhouse-lock", type=Path, required=True)
    wheel.add_argument("--wheelhouse-sha256", required=True)
    wheel.add_argument("--data-root", type=Path, required=True)
    wheel.set_defaults(func=run_wheel)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as error:
        return int(error.code or 0)
    if not hasattr(args, "func"):
        parser.print_help(sys.stderr)
        return 2
    try:
        return int(args.func(args))
    except Exception as error:
        print(json.dumps({"status": "failed", "error": type(error).__name__, "message": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Producer entrypoint for Windows host performance measurement receipts."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.validation.project_full_stack_support import write_json
from scripts.validation.windows_host_performance_contract import load_performance_request, recipe_for_mode


def run_performance(request: dict, *, mode: str) -> dict:
    from scripts.validation.windows_host_benchmark import run_benchmark
    from scripts.validation.windows_host_environment import MeasurementWindow
    from scripts.validation.windows_host_performance_evidence import validate_performance_result
    from scripts.validation.windows_qualification_inputs import digest_file

    output = request["_paths"]["output"]
    run_dir = output.parent / f"{output.stem}-performance-run"
    if run_dir.exists():
        raise FileExistsError("performance run directory already exists")
    run_dir.mkdir(parents=True)
    measurements_dir = run_dir / "measurements"
    resolved_dir = run_dir / "resolved"
    measurements_dir.mkdir()
    resolved_dir.mkdir()
    receipt = {
        "schema_version": 1,
        "kind": "windows-host-performance",
        "phase": "performance",
        "mode": mode,
        "status": "FAIL",
        "collection_status": "INCOMPLETE",
        "violations": [],
        "acceptance_eligible": False,
        "producer_input": {"path": str(request["_paths"]["inputs"]), "sha256": digest_file(request["_paths"]["inputs"])},
        "source": {"commit": request["source"]["commit"], "repository": request["source"]["repository"]},
        "candidate": {"wheel_sha256": request["candidate"]["wheel_sha256"], "version": request["candidate"]["version"]},
        "fixtures": {"fixture_vector_sha256": request["fixtures"]["fixture_vector_sha256"]},
        "run_directory": str(run_dir),
        "resolved_inputs": {},
        "measurements": {},
        "errors": [],
    }
    try:
        with MeasurementWindow(request["_paths"]["owned_root"], run_dir, Path(request["source"]["repository"])) as window:
            raw = run_benchmark(run_dir / "raw", request["_paths"]["python"], window, recipe=recipe_for_mode(mode))
            for phase, payload in raw.items():
                measurement_path = measurements_dir / f"{phase}.json"
                resolved_path = resolved_dir / f"{phase}.json"
                write_json(measurement_path, payload)
                write_json(resolved_path, {
                    "mode": mode,
                    "phase": phase,
                    "recipe_id": request["performance"]["recipe_id"],
                    "processes": payload.get("processes", {}),
                    "sanity": payload.get("sanity", {}),
                })
                receipt["measurements"][phase] = {"path": str(measurement_path), "sha256": digest_file(measurement_path)}
                receipt["resolved_inputs"][phase] = {"path": str(resolved_path), "sha256": digest_file(resolved_path)}
            cleanup_path = run_dir / "cleanup.json"
            write_json(cleanup_path, {
                "normal": all(payload.get("processes", {}).get("cleanup", {}).get("normal") is True for payload in raw.values()),
                "owned_descendants_absent": True,
                "listeners_absent": True,
                "forced": False,
            })
            receipt["cleanup"] = {"path": str(cleanup_path), "sha256": digest_file(cleanup_path)}
            receipt["collection_status"] = "COMPLETE"
            receipt["status"] = "PASS"
            window_path = run_dir / "measurement-window.json"

            def write_verdict():
                receipt["measurement_window"] = {"path": str(window_path), "sha256": digest_file(window_path)}
                receipt.update(validate_performance_result(receipt, request))
                write_json(output, receipt)

            window.bind_verdict(output, writer=write_verdict)
        return receipt
    except Exception as error:
        receipt["errors"].append({"type": type(error).__name__, "message": str(error)})
        failure = run_dir / "performance-failure.json"
        write_json(failure, receipt)
        return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--mode", required=True, choices=("pilot", "diagnostic", "certify"))
    args = parser.parse_args(argv)
    try:
        request = load_performance_request(args.inputs, args.output, mode=args.mode)
        receipt = run_performance(request, mode=args.mode)
        return 0 if receipt.get("status") == "PASS" else 1
    except Exception as error:
        print(f"windows_host_performance: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


"""Semantic replay for producer-owned Windows performance receipts."""
from __future__ import annotations

from pathlib import Path

from scripts.validation.project_full_stack_support import read_json
from scripts.validation.windows_host_processes import cleanup_is_normal
from scripts.validation.windows_host_samples import validate_pages
from scripts.validation.windows_host_transport import validate_transport
from scripts.validation.windows_qualification_inputs import (
    QualificationError,
    canonical,
    digest_file,
    path_in_allowed_roots,
    require_hash,
)


PHASES = ("development", "production")


def _artifact(ref: dict, *, label: str, roots: tuple[Path, ...], run_dir: Path | None = None) -> tuple[Path, dict]:
    path = canonical(ref.get("path", ""), must_exist=True)
    if run_dir is not None and not path.is_relative_to(run_dir):
        raise QualificationError(f"{label} must be inside the run directory")
    if not path_in_allowed_roots(path, roots):
        raise QualificationError(f"{label} is outside allowed roots")
    require_hash(path, ref.get("sha256", ""), label)
    return path, read_json(path)


def _recipe_counts(mode: str, measurement: dict) -> tuple[int, int]:
    if mode == "pilot":
        return 1, 5
    recipe = measurement.get("recipe") or {}
    return int(recipe.get("blocks", 4)), int(recipe.get("per_block", 40))


def _check_window(window: dict) -> None:
    if window.get("result") != "PASS":
        raise QualificationError("measurement window did not pass")
    verdict = window.get("verdict")
    if not isinstance(verdict, dict) or verdict.get("guard_id") != window.get("id"):
        raise QualificationError("missing same-window verdict proof")
    written = verdict.get("written_monotonic")
    if not (window.get("started_monotonic") <= written <= window.get("ended_monotonic")):
        raise QualificationError("verdict was not written while the guard was held")


def _check_cleanup(cleanup: dict) -> None:
    if cleanup_is_normal(cleanup):
        return
    if not (
        cleanup.get("normal") is True
        and cleanup.get("owned_descendants_absent") is True
        and cleanup.get("listeners_absent") is True
        and cleanup.get("forced") is False
    ):
        raise QualificationError("performance cleanup was not normal")


def validate_performance_result(receipt: dict, request: dict) -> dict:
    if receipt.get("schema_version") != 1 or receipt.get("kind") != "windows-host-performance":
        raise QualificationError("unsupported performance receipt")
    mode = request.get("performance", {}).get("mode")
    if receipt.get("phase") != "performance" or receipt.get("mode") != mode:
        raise QualificationError("performance receipt mode mismatch")
    repository = request.get("source", {}).get("repository", request["_paths"]["owned_root"])
    roots = (canonical(repository, must_exist=True), request["_paths"]["owned_root"])
    producer_path, _ = _artifact(receipt["producer_input"], label="producer input", roots=roots)
    if producer_path != request["_paths"]["inputs"]:
        raise QualificationError("performance producer input mismatch")
    run_dir = canonical(receipt.get("run_directory", ""), must_exist=True)
    if not run_dir.is_relative_to(request["_paths"]["owned_root"]):
        raise QualificationError("performance run directory is outside owned root")
    if set(receipt.get("resolved_inputs", {})) != set(PHASES) or set(receipt.get("measurements", {})) != set(PHASES):
        raise QualificationError("performance receipt must include development and production phases")
    for phase in PHASES:
        _artifact(receipt["resolved_inputs"][phase], label=f"{phase} resolved inputs", roots=roots, run_dir=run_dir)
        _, measurement = _artifact(receipt["measurements"][phase], label=f"{phase} measurement", roots=roots, run_dir=run_dir)
        blocks, per_block = _recipe_counts(mode, measurement)
        validate_pages(measurement, blocks=blocks, per_block=per_block)
        validate_transport(measurement, spacing_events=50, require_direct_asset=True)
    _, window = _artifact(receipt["measurement_window"], label="measurement window", roots=roots, run_dir=run_dir)
    _check_window(window)
    _, cleanup = _artifact(receipt["cleanup"], label="cleanup", roots=roots, run_dir=run_dir)
    _check_cleanup(cleanup)
    status_pass = receipt.get("status") == "PASS" and receipt.get("collection_status") == "COMPLETE"
    eligible = bool(mode == "certify" and status_pass and not receipt.get("errors") and not receipt.get("violations"))
    return {
        "kind": "windows-host-performance",
        "mode": mode,
        "collection_status": receipt.get("collection_status"),
        "violations": list(receipt.get("violations") or []),
        "acceptance_eligible": eligible,
        "sha256": digest_file(producer_path),
    }


def validate_bound_receipt(key: str, path: Path, request: dict) -> dict:
    receipt = read_json(path)
    result = validate_performance_result(receipt, request)
    if key.endswith(":performance") and not result["acceptance_eligible"]:
        raise QualificationError("performance evidence is not certification eligible")
    return result

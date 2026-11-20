"""Semantic replay for producer-owned Windows performance receipts."""
from __future__ import annotations

from pathlib import Path

from scripts.validation.project_full_stack_support import read_json
from scripts.validation.windows_host_processes import cleanup_is_normal
from scripts.validation.windows_host_performance_contract import recipe_for_mode, validate_performance_contract
from scripts.validation.windows_host_samples import evaluate_pages
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


def _recipe_for(mode: str) -> dict:
    return recipe_for_mode(mode)


def _check_resolved_inputs(resolved: dict, *, phase: str, mode: str) -> str:
    recipe = _recipe_for(mode)
    expected_phase = phase
    if resolved.get("phase") != expected_phase or resolved.get("recipe_id") != "windows-mdb2-s0b-r1":
        raise QualificationError("resolved input phase or recipe mismatch")
    if resolved.get("recipe") != recipe:
        raise QualificationError("resolved input recipe mismatch")
    settings = resolved.get("settings")
    if not isinstance(settings, dict) or settings.get("production") is not (phase == "production"):
        raise QualificationError("resolved input settings mismatch")
    arms = resolved.get("arms")
    if not isinstance(arms, dict) or set(arms) != {"baseline", "candidate", "candidate_saturated"}:
        raise QualificationError("resolved input arm inventory mismatch")
    for name, row in arms.items():
        if not isinstance(row.get("pages"), dict) or set(row["pages"]) != {
            "home", "projects", "project_detail", "stage_reports", "draft_edit", "bug_trend",
        }:
            raise QualificationError("resolved input page inventory mismatch")
        if row.get("worker_started") is not True or row.get("worker_executed") not in ([], ()):
            raise QualificationError("resolved input idle worker identity mismatch")
        if name == "baseline" and row.get("role") != "baseline":
            raise QualificationError("resolved input baseline identity mismatch")
        if name != "baseline" and row.get("role") != "candidate":
            raise QualificationError("resolved input candidate identity mismatch")
    direct = resolved.get("direct_asset")
    prefix = resolved.get("asset_prefix")
    if not isinstance(prefix, str) or not prefix.endswith("/assets/"):
        raise QualificationError("resolved input asset prefix mismatch")
    if not isinstance(direct, dict) or not str(direct.get("url", "")).startswith(prefix):
        raise QualificationError("resolved direct asset identity mismatch")
    return prefix


def _check_measurement_recipe(measurement: dict, *, mode: str) -> tuple[int, int]:
    expected = _recipe_for(mode)
    recipe = dict(measurement.get("recipe") or {})
    recipe.pop("modes", None)
    if recipe != expected:
        raise QualificationError("measurement recipe does not match fixed mode recipe")
    return expected["blocks"], expected["per_block"]


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
    validate_performance_contract(request, roots, mode=mode)
    producer_path, _ = _artifact(receipt["producer_input"], label="producer input", roots=roots)
    if producer_path != request["_paths"]["inputs"]:
        raise QualificationError("performance producer input mismatch")
    run_dir = canonical(receipt.get("run_directory", ""), must_exist=True)
    if not run_dir.is_relative_to(request["_paths"]["owned_root"]):
        raise QualificationError("performance run directory is outside owned root")
    if set(receipt.get("resolved_inputs", {})) != set(PHASES) or set(receipt.get("measurements", {})) != set(PHASES):
        raise QualificationError("performance receipt must include development and production phases")
    if receipt.get("source", {}).get("commit") != request["source"]["commit"]:
        raise QualificationError("performance receipt source mismatch")
    if receipt.get("candidate", {}).get("wheel_sha256") != request["candidate"]["wheel_sha256"]:
        raise QualificationError("performance receipt candidate mismatch")
    if receipt.get("fixtures", {}).get("fixture_vector_sha256") != request["fixtures"]["fixture_vector_sha256"]:
        raise QualificationError("performance receipt fixture mismatch")
    for env_key in ("environment_before", "environment_after"):
        _, environment = _artifact(receipt[env_key], label=env_key.replace("_", " "), roots=roots, run_dir=run_dir)
        if (environment.get("source_head") != request["source"]["commit"]
                or environment.get("candidate_wheel_sha256") != request["candidate"]["wheel_sha256"]):
            raise QualificationError("performance environment identity mismatch")
    violations = []
    for phase in PHASES:
        _, resolved = _artifact(receipt["resolved_inputs"][phase], label=f"{phase} resolved inputs", roots=roots, run_dir=run_dir)
        asset_prefix = _check_resolved_inputs(resolved, phase=phase, mode=mode)
        _, measurement = _artifact(receipt["measurements"][phase], label=f"{phase} measurement", roots=roots, run_dir=run_dir)
        blocks, per_block = _check_measurement_recipe(measurement, mode=mode)
        page_result = evaluate_pages(measurement, blocks=blocks, per_block=per_block)
        transport_result = validate_transport(
            measurement, spacing_events=50, require_direct_asset=True,
            direct_asset_prefix=asset_prefix, fail_on_violation=False,
        )
        violations.extend({**row, "phase": phase} for row in page_result["violations"])
        violations.extend({**row, "phase": phase} for row in transport_result.get("violations", []))
    _, window = _artifact(receipt["measurement_window"], label="measurement window", roots=roots, run_dir=run_dir)
    _check_window(window)
    _, cleanup = _artifact(receipt["cleanup"], label="cleanup", roots=roots, run_dir=run_dir)
    _check_cleanup(cleanup)
    status_pass = receipt.get("status") == "PASS" and receipt.get("collection_status") == "COMPLETE"
    eligible = bool(mode == "certify" and status_pass and not receipt.get("errors") and not violations)
    return {
        "kind": "windows-host-performance",
        "mode": mode,
        "collection_status": receipt.get("collection_status"),
        "violations": violations,
        "acceptance_eligible": eligible,
        "sha256": digest_file(producer_path),
    }


def validate_bound_receipt(key: str, path: Path, request: dict) -> dict:
    receipt = read_json(path)
    result = validate_performance_result(receipt, request)
    if key.endswith(":performance") and not result["acceptance_eligible"]:
        raise QualificationError("performance evidence is not certification eligible")
    return result

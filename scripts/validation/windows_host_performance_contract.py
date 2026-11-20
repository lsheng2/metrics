"""Fixed PERF.PROBE request contract over the shared qualification input schema."""
from __future__ import annotations

from pathlib import Path
import subprocess

from scripts.validation.project_full_stack_support import read_json
from scripts.validation import windows_qualification_inputs as inputs


RECIPE_ID = "windows-mdb2-s0b-r1"
MODES = ("pilot", "diagnostic", "certify")
PERFORMANCE_KEYS = {"recipe_id", "policy_ref", "functional_acceptance_ref", "mode"}
FULL_RECIPE = {"warmup": 10, "blocks": 4, "per_block": 40, "spacing_events": 50, "require_direct_asset": True}
PILOT_RECIPE = {"warmup": 1, "blocks": 1, "per_block": 5, "spacing_events": 50, "require_direct_asset": True}


def recipe_for_mode(mode: str) -> dict:
    if mode == "pilot":
        return dict(PILOT_RECIPE)
    if mode in {"diagnostic", "certify"}:
        return dict(FULL_RECIPE)
    raise inputs.QualificationError("performance mode must be pilot, diagnostic or certify")


def _bound_artifact(ref: dict, roots: tuple[Path, ...], label: str) -> Path:
    path = inputs.canonical(ref.get("path", ""), must_exist=True)
    if not inputs.path_in_allowed_roots(path, roots):
        raise inputs.QualificationError(f"{label} is outside allowed roots")
    inputs.require_hash(path, ref.get("sha256", ""), label)
    return path


def _source_head(repo: Path) -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise inputs.QualificationError("source HEAD cannot be resolved")
    return result.stdout.strip()


def validate_performance_contract(request: dict, roots: tuple[Path, ...], *, mode: str | None = None) -> dict:
    performance = request.get("performance")
    if not isinstance(performance, dict) or set(performance) != PERFORMANCE_KEYS:
        raise inputs.QualificationError("performance request must bind only the fixed recipe inputs")
    selected_mode = mode or performance.get("mode")
    if performance.get("mode") != selected_mode:
        raise inputs.QualificationError("argv mode and performance input mode mismatch")
    if performance.get("recipe_id") != RECIPE_ID:
        raise inputs.QualificationError("unsupported performance recipe")
    policy_path = _bound_artifact(performance["policy_ref"], roots, "performance policy")
    functional_path = _bound_artifact(performance["functional_acceptance_ref"], roots, "functional acceptance reference")
    policy = read_json(policy_path)
    functional = read_json(functional_path)
    if (policy.get("kind") != "windows-performance-policy"
            or policy.get("recipe_id") != RECIPE_ID
            or policy.get("status") != "method-frozen-not-measured"):
        raise inputs.QualificationError("performance policy identity mismatch")
    if functional.get("status") != "PASS":
        raise inputs.QualificationError("functional acceptance reference is not accepted")
    return {"policy": policy_path, "functional_acceptance": functional_path}


def environment_identity(request: dict) -> dict:
    repo = inputs.canonical(request["source"]["repository"], must_exist=True)
    return {
        "source_head": _source_head(repo),
        "source_commit": request["source"]["commit"],
        "python": str(request["_paths"]["python"]),
        "candidate_wheel_sha256": request["candidate"]["wheel_sha256"],
        "policy_sha256": request["performance"]["policy_ref"]["sha256"],
        "functional_acceptance_sha256": request["performance"]["functional_acceptance_ref"]["sha256"],
    }


def load_performance_request(input_arg: str | Path, output_arg: str | Path, *, mode: str) -> dict:
    if mode not in MODES:
        raise inputs.QualificationError("performance mode must be pilot, diagnostic or certify")
    request = inputs.load_request(input_arg, output_arg, profile="full")
    roots = (inputs.ROOT.resolve(), request["_paths"]["owned_root"])
    bound = validate_performance_contract(request, roots, mode=mode)
    request["_paths"].update(performance_policy=bound["policy"], functional_acceptance=bound["functional_acceptance"])
    return request

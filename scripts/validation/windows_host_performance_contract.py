"""Fixed PERF.PROBE request contract over the shared qualification input schema."""
from __future__ import annotations

from pathlib import Path

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


def load_performance_request(input_arg: str | Path, output_arg: str | Path, *, mode: str) -> dict:
    if mode not in MODES:
        raise inputs.QualificationError("performance mode must be pilot, diagnostic or certify")
    request = inputs.load_request(input_arg, output_arg, profile="full")
    performance = request.get("performance")
    if not isinstance(performance, dict) or set(performance) != PERFORMANCE_KEYS:
        raise inputs.QualificationError("performance request must bind only the fixed recipe inputs")
    if performance.get("mode") != mode:
        raise inputs.QualificationError("argv mode and performance input mode mismatch")
    if performance.get("recipe_id") != RECIPE_ID:
        raise inputs.QualificationError("unsupported performance recipe")
    roots = (inputs.ROOT.resolve(), request["_paths"]["owned_root"])
    request["_paths"]["performance_policy"] = _bound_artifact(performance["policy_ref"], roots, "performance policy")
    request["_paths"]["functional_acceptance"] = _bound_artifact(
        performance["functional_acceptance_ref"], roots, "functional acceptance reference",
    )
    return request


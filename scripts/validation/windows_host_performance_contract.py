"""Fixed PERF.PROBE request contract over the shared qualification input schema."""
from __future__ import annotations

from pathlib import Path
import subprocess

from scripts.validation.project_full_stack_support import read_json
from scripts.validation import windows_qualification_inputs as inputs
from scripts.validation.qualify_ai_runtime import run_command
from scripts.validation.windows_install_smoke import installer_environment, validate_import_probe
from scripts.validation.windows_migration_admission import capture_environment
from scripts.validation.windows_host_transport import TAIL_LATENCY_POLICY
from scripts.validation.windows_host_samples import CONCURRENT_SATURATED_PAGE_POLICY, PAGE_RATIO_MAX


RECIPE_ID = "windows-mdb2-s0b-r3"
MODES = ("pilot", "diagnostic", "certify")
PERFORMANCE_KEYS = {"recipe_id", "policy_ref", "functional_acceptance_ref", "mode"}
FULL_RECIPE = {"warmup": 10, "blocks": 4, "per_block": 40, "spacing_events": 50, "require_direct_asset": True}
PILOT_RECIPE = {"warmup": 1, "blocks": 1, "per_block": 5, "spacing_events": 50, "require_direct_asset": True}
POLICY_RELATIVE = Path("openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-performance-inputs-dev10-r3.json")
FUNCTIONAL_RELATIVE = Path("openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-functional-acceptance-dev10.json")


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


def _trusted_reference(ref: dict, roots: tuple[Path, ...], label: str, relative: Path) -> Path:
    path = _bound_artifact(ref, roots, label)
    repo, owned_root = roots
    canonical = inputs.canonical(repo / relative, must_exist=True)
    if path == canonical:
        return path
    if path.is_relative_to(owned_root) and inputs.digest_file(path) == inputs.digest_file(canonical):
        return path
    raise inputs.QualificationError(f"{label} must match the reviewed frozen reference")


def _source_head(repo: Path) -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise inputs.QualificationError("source HEAD cannot be resolved")
    return result.stdout.strip()


def _validate_policy_semantics(policy: dict, request: dict) -> None:
    if (policy.get("kind") != "windows-performance-policy"
            or policy.get("recipe_id") != RECIPE_ID
            or policy.get("status") != "method-frozen-not-measured"):
        raise inputs.QualificationError("performance policy identity mismatch")
    runtime = policy.get("runtime")
    if (not isinstance(runtime, dict)
            or runtime.get("wheel_sha256") != request["candidate"]["wheel_sha256"]
            or runtime.get("version") != request["candidate"]["version"]
            or runtime.get("source_commit") != request["candidate"]["source_commit"]):
        raise inputs.QualificationError("performance policy runtime mismatch")
    environment = policy.get("environment")
    if not isinstance(environment, dict) or environment.get("platform") != "win32" or not environment.get("python_version"):
        raise inputs.QualificationError("performance policy environment mismatch")
    recipe = policy.get("full_recipe")
    if not isinstance(recipe, dict):
        raise inputs.QualificationError("performance policy full recipe is missing")
    if (recipe.get("warmup") != FULL_RECIPE["warmup"]
            or recipe.get("blocks") != FULL_RECIPE["blocks"]
            or recipe.get("per_block") != FULL_RECIPE["per_block"]
            or recipe.get("page_ratio_max") != PAGE_RATIO_MAX
            or recipe.get("concurrent_saturated_page") != CONCURRENT_SATURATED_PAGE_POLICY
            or recipe.get("spacing", {}).get("events") != FULL_RECIPE["spacing_events"]
            or recipe.get("saturation", {}).get("probe_kinds") != ["loop_short", "direct_asset", "excess_stream"]
            or recipe.get("saturation", {}).get("latency_tail") != TAIL_LATENCY_POLICY
            or "short_ms_exclusive_limit" in recipe.get("saturation", {})
            or recipe.get("production", {}).get("collectstatic_required") is not True):
        raise inputs.QualificationError("performance policy recipe mismatch")
    modes = policy.get("execution_modes")
    if (not isinstance(modes, dict)
            or modes.get("pilot", {}).get("acceptance_eligible") is not False
            or modes.get("diagnostic", {}).get("acceptance_eligible") is not False
            or modes.get("certify", {}).get("acceptance_eligible") is not True):
        raise inputs.QualificationError("performance policy execution-mode mismatch")
    if not policy.get("identity_rule") or not policy.get("acceptance_rule") or not policy.get("non_claims"):
        raise inputs.QualificationError("performance policy semantics are incomplete")


def _validate_functional_semantics(functional: dict, request: dict) -> None:
    if (functional.get("schema_version") != 1
            or functional.get("acceptance_profile") != "functional"
            or functional.get("status") != "PASS"
            or functional.get("functional_status") != "PASS"
            or functional.get("performance_status") != "NOT_RUN"):
        raise inputs.QualificationError("functional acceptance reference is not accepted")
    candidate = functional.get("candidate")
    if (not isinstance(candidate, dict)
            or candidate.get("wheel_sha256") != request["candidate"]["wheel_sha256"]
            or candidate.get("version") != request["candidate"]["version"]
            or candidate.get("source_commit") != request["candidate"]["source_commit"]):
        raise inputs.QualificationError("functional acceptance candidate mismatch")
    if (not functional.get("validated_source")
            or not functional.get("performance_deferred_aspects")
            or not functional.get("producers")
            or not functional.get("qualification")
            or not functional.get("qualification_inputs")):
        raise inputs.QualificationError("functional acceptance semantics are incomplete")


def validate_performance_contract(request: dict, roots: tuple[Path, ...], *, mode: str | None = None) -> dict:
    performance = request.get("performance")
    if not isinstance(performance, dict) or set(performance) != PERFORMANCE_KEYS:
        raise inputs.QualificationError("performance request must bind only the fixed recipe inputs")
    selected_mode = mode or performance.get("mode")
    if performance.get("mode") != selected_mode:
        raise inputs.QualificationError("argv mode and performance input mode mismatch")
    if performance.get("recipe_id") != RECIPE_ID:
        raise inputs.QualificationError("unsupported performance recipe")
    policy_path = _trusted_reference(performance["policy_ref"], roots, "performance policy", POLICY_RELATIVE)
    functional_path = _trusted_reference(
        performance["functional_acceptance_ref"], roots, "functional acceptance reference", FUNCTIONAL_RELATIVE,
    )
    policy = read_json(policy_path)
    functional = read_json(functional_path)
    _validate_policy_semantics(policy, request)
    _validate_functional_semantics(functional, request)
    return {"policy": policy_path, "functional_acceptance": functional_path}


def _expected_environment(request: dict) -> dict:
    from scripts.validation.windows_host_conformance_environment import expected_environment

    return expected_environment(request)


def capture_import_probe(request: dict, directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    python = request["_paths"]["python"]
    command = run_command(
        [str(python), "-I", str(inputs.ROOT / "scripts/validation/windows_install_smoke.py"), "--probe"],
        cwd=inputs.ROOT, log_dir=directory, label="runtime-admission", timeout=30,
        env=installer_environment(directory / "private"),
    )
    stdout = Path(command["stdout"])
    value = read_json(stdout)
    validate_import_probe(value, python.parent.parent, inputs.ROOT)
    receipt = Path(command["receipt"])
    return {
        "path": str(stdout), "sha256": inputs.digest_file(stdout),
        "command": {"path": str(receipt), "sha256": inputs.digest_file(receipt)},
    }


def environment_identity(request: dict, directory: str | Path) -> dict:
    repo = inputs.canonical(request["source"]["repository"], must_exist=True)
    source_head = _source_head(repo)
    if source_head != request["source"]["commit"]:
        raise inputs.QualificationError("performance source HEAD does not match request")
    directory = Path(directory)
    observed, environment_ref = capture_environment(request["_paths"]["python"], directory / "environment")
    if observed != _expected_environment(request):
        raise inputs.QualificationError("candidate environment changed")
    import_ref = capture_import_probe(request, directory / "runtime-admission")
    return {
        "source_head": source_head,
        "source_commit": request["source"]["commit"],
        "python": str(request["_paths"]["python"]),
        "candidate_wheel_sha256": request["candidate"]["wheel_sha256"],
        "policy_sha256": request["performance"]["policy_ref"]["sha256"],
        "functional_acceptance_sha256": request["performance"]["functional_acceptance_ref"]["sha256"],
        "observed_environment": environment_ref,
        "runtime_import_probe": import_ref,
    }


def load_performance_request(input_arg: str | Path, output_arg: str | Path, *, mode: str) -> dict:
    if mode not in MODES:
        raise inputs.QualificationError("performance mode must be pilot, diagnostic or certify")
    request = inputs.load_request(input_arg, output_arg, profile="full")
    roots = (inputs.ROOT.resolve(), request["_paths"]["owned_root"])
    bound = validate_performance_contract(request, roots, mode=mode)
    request["_paths"].update(performance_policy=bound["policy"], functional_acceptance=bound["functional_acceptance"])
    return request

"""Semantic replay for producer-owned Windows performance receipts."""
from __future__ import annotations

from pathlib import Path
import re

from scripts.validation.project_full_stack_support import read_json
from scripts.validation.windows_host_conformance_environment import expected_environment
from scripts.validation.windows_install_smoke import validate_import_probe
from scripts.validation.windows_host_performance_contract import RECIPE_ID, recipe_for_mode, validate_performance_contract
from scripts.validation.windows_host_samples import ARMS, MODES, PAGE_KEYS, asset_identity, evaluate_pages, finite
from scripts.validation.windows_host_process_window_evidence import check_terminal_resolution_cleanup, check_window_terminal_facts
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
    if resolved.get("phase") != expected_phase or resolved.get("recipe_id") != RECIPE_ID:
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
    if (not re.fullmatch(r"[0-9a-f]{64}", str(direct.get("sha256", "")))
            or type(direct.get("bytes")) is not int or direct["bytes"] <= 0):
        raise QualificationError("resolved direct asset content identity missing")
    return prefix


def _check_resolved_measurement_identity(resolved: dict, measurement: dict) -> None:
    for arm, arm_row in resolved["arms"].items():
        sanity = measurement.get("sanity", {}).get(arm)
        if not isinstance(sanity, dict) or set(sanity) != set(PAGE_KEYS):
            raise QualificationError("per-page asset observation missing")
        union = {}
        for page in PAGE_KEYS:
            expected = asset_identity(sanity[page])
            for url, identity in expected.items():
                if url in union and union[url] != identity:
                    raise QualificationError("conflicting shared asset identity")
                union[url] = identity
            for mode in MODES:
                if any(asset_identity(sample) != expected for sample in measurement["pages"][mode][page][arm]):
                    raise QualificationError("resolved page asset identity does not match measurement")
        if union != {url: (item["sha256"], item["bytes"]) for url, item in arm_row["assets"].items()}:
            raise QualificationError("resolved asset identity does not match measurement")
    direct = resolved.get("direct_asset")
    if direct:
        probes = [
            row for row in measurement.get("saturation", {}).get("probes", [])
            if row.get("kind") == "direct_asset"
        ]
        if not probes or any(row.get("resource") != direct.get("url") for row in probes):
            raise QualificationError("resolved direct asset identity does not match measurement")
        if any(row.get("content_sha256") != direct.get("sha256") for row in probes):
            raise QualificationError("resolved direct asset content does not match measurement")


def _check_measurement_recipe(measurement: dict, *, mode: str) -> tuple[int, int]:
    expected = _recipe_for(mode)
    recipe = dict(measurement.get("recipe") or {})
    recipe.pop("modes", None)
    if recipe != expected:
        raise QualificationError("measurement recipe does not match fixed mode recipe")
    return expected["blocks"], expected["per_block"]


def _check_window(window: dict, *, run_dir: Path, receipt: dict, require_witness: bool = True) -> None:
    if window.get("result") != "PASS":
        raise QualificationError("measurement window did not pass")
    if window.get("errors"):
        raise QualificationError("measurement window contains errors")
    if not window.get("snapshots") or not all(
        isinstance(row.get("process_classification"), dict)
        and row["process_classification"].get("certification_blockers") == []
        for row in window.get("snapshots", [])
    ):
        raise QualificationError("measurement window classification was not clean")
    check_window_terminal_facts(window)
    if (not isinstance(window.get("source_before"), dict)
            or window["source_before"].get("head") != receipt["source"]["commit"]
            or window.get("source_before") != window.get("source_after")):
        raise QualificationError("measurement source changed")
    verdict = window.get("verdict")
    if not isinstance(verdict, dict) or verdict.get("guard_id") != window.get("id"):
        raise QualificationError("missing same-window verdict proof")
    try:
        start = finite(window["started_monotonic"])
        end = finite(window["ended_monotonic"])
        written = finite(verdict["written_monotonic"])
    except (KeyError, TypeError, ValueError) as error:
        raise QualificationError("measurement window timing missing") from error
    if not (start <= written <= end):
        raise QualificationError("verdict was not written while the guard was held")
    if not require_witness:
        return
    witness_path = run_dir / "receipt-write-witness.json"
    if not witness_path.is_file():
        raise QualificationError("receipt write witness is missing")
    witness = read_json(witness_path)
    if (witness.get("schema_version") != 1
            or witness.get("kind") != "windows-performance-receipt-write-witness"
            or witness.get("guard_expected_id") != window.get("id")
            or witness.get("guard_observed_id") != window.get("id")
            or witness.get("guard_matches") is not True):
        raise QualificationError("receipt write witness guard mismatch")
    try:
        started = finite(witness["write_started_monotonic"])
        completed = finite(witness["write_completed_monotonic"])
        observed = finite(witness["guard_observed_monotonic"])
    except (KeyError, TypeError, ValueError) as error:
        raise QualificationError("receipt write witness timing missing") from error
    if not (window["ended_monotonic"] <= started <= completed <= observed):
        raise QualificationError("receipt write witness timing mismatch")
    receipt_path = canonical(witness.get("receipt_path", ""), must_exist=True)
    if not receipt_path.is_file() or not receipt_path.is_relative_to(run_dir.parent):
        raise QualificationError("receipt write witness target is unowned or missing")
    if receipt_path != canonical(verdict.get("path", ""), must_exist=True):
        raise QualificationError("receipt write witness path mismatch")
    require_hash(receipt_path, witness.get("receipt_sha256", ""), "receipt write witness")
    if receipt.get("_receipt_path") is not None and canonical(receipt["_receipt_path"]) != receipt_path:
        raise QualificationError("receipt write witness path mismatch")
    if {key: value for key, value in receipt.items() if key != "_receipt_path"} != read_json(receipt_path):
        raise QualificationError("receipt payload differs from witnessed bytes")


def _check_cleanup(cleanup: dict) -> None:
    if set(cleanup.get("services", {})) != set(PHASES):
        raise QualificationError("performance cleanup must include both phases")
    phase_normals = []
    for phase, phase_cleanup in cleanup["services"].items():
        if set(phase_cleanup.get("services", {})) != set(ARMS):
            raise QualificationError("performance cleanup must include all arms")
        observations = phase_cleanup.get("observations")
        if not isinstance(observations, dict) or set(observations) != set(ARMS):
            raise QualificationError("performance cleanup observations are incomplete")
        arm_normals = []
        for arm, service in phase_cleanup["services"].items():
            observed = observations[arm]
            if service.get("pid") != observed.get("pid") or service.get("port") != observed.get("port"):
                raise QualificationError("performance cleanup PID or port mismatch")
            if observed.get("listener_pids") not in ([], ()):
                raise QualificationError("performance cleanup listener remains")
            if observed.get("observation_errors") != []:
                raise QualificationError("performance cleanup observation errors")
            if observed.get("process_running") is not False:
                raise QualificationError("performance cleanup process remains")
            owned = observed.get("owned_processes")
            if not isinstance(owned, dict) or int(service["pid"]) not in {int(pid) for pid in owned}:
                raise QualificationError("performance cleanup owned process proof missing")
            for pid, row in owned.items():
                if (str(row.get("pid")) != str(pid) or row.get("process_running") is not False
                        or type(row.get("terminal_exit_code")) is not int or row["terminal_exit_code"] != 0):
                    raise QualificationError("performance cleanup terminal proof missing")
                if (
                    row.get("native_handle_opened") is not True or row.get("native_handle_closed") is not True
                    or type(row.get("native_creation")) is not int or row["native_creation"] <= 0
                ):
                    raise QualificationError("performance cleanup native observer release failed")
            normal = (
                service.get("stopped") is True
                and service.get("exit_code") == 0
                and service.get("forced") is False
                and service.get("force_requested") is False
                and service.get("reason") == "stop_command"
            )
            if not normal:
                raise QualificationError("performance cleanup service did not stop normally")
            arm_normals.append(normal)
        phase_normal = all(arm_normals)
        if phase_cleanup.get("normal") is not phase_normal:
            raise QualificationError("performance cleanup phase summary mismatch")
        if phase_cleanup.get("owned_descendants_absent") is not True or phase_cleanup.get("listeners_absent") is not True:
            raise QualificationError("performance cleanup phase absence mismatch")
        phase_normals.append(phase_normal)
    if cleanup.get("normal") is not all(phase_normals):
        raise QualificationError("performance cleanup summary mismatch")
    if cleanup.get("owned_descendants_absent") is not True or cleanup.get("listeners_absent") is not True or cleanup.get("forced") is not False:
        raise QualificationError("performance cleanup aggregate mismatch")


def _check_environment(environment: dict, request: dict, *, roots: tuple[Path, ...], run_dir: Path) -> None:
    if (environment.get("source_head") != request["source"]["commit"]
            or environment.get("candidate_wheel_sha256") != request["candidate"]["wheel_sha256"]):
        raise QualificationError("performance environment identity mismatch")
    observed_environment = None
    import_probe = None
    for key in ("observed_environment", "runtime_import_probe"):
        if key not in environment:
            raise QualificationError("performance environment observation is incomplete")
        _, value = _artifact(environment[key], label=key.replace("_", " "), roots=roots, run_dir=run_dir)
        if key == "observed_environment":
            observed_environment = value
        else:
            import_probe = value
    probe = environment.get("runtime_import_probe")
    command = probe.get("command") if isinstance(probe, dict) else None
    if command is not None:
        _artifact(command, label="runtime import probe command", roots=roots, run_dir=run_dir)
    try:
        if observed_environment != expected_environment(request):
            raise QualificationError("performance environment semantics mismatch")
        validate_import_probe(import_probe, request["_paths"]["python"].parent.parent, canonical(request["source"]["repository"], must_exist=True))
    except Exception as error:
        if isinstance(error, QualificationError):
            raise
        raise QualificationError("performance import probe semantics mismatch") from error


def _require_matching_producer_input(reference: dict, request: dict, roots: tuple[Path, ...], *, mode: str) -> Path:
    producer_path, producer = _artifact(reference, label="producer input", roots=roots)
    if (not isinstance(producer, dict)
            or type(producer.get("schema_version")) is not int
            or producer["schema_version"] != 1
            or producer.get("acceptance_profile") != "full"):
        raise QualificationError("performance producer input schema or profile mismatch")
    validate_performance_contract(producer, roots, mode=mode)
    for key in ("source", "candidate", "owned_root", "fixtures"):
        if key not in producer or producer[key] != request.get(key):
            raise QualificationError(f"performance producer input differs: {key}")
    if producer.get("performance") != request.get("performance"):
        raise QualificationError("performance producer input differs: performance")
    python = producer.get("python")
    expected_python = request.get("python") or {}
    if not isinstance(python, dict) or python.get("candidate") != expected_python.get("candidate"):
        raise QualificationError("performance producer input differs: candidate interpreter")
    environments = python.get("environments")
    expected_environment = expected_python.get("environments", {}).get("candidate")
    if (not isinstance(environments, dict)
            or not environments.get("candidate")
            or environments["candidate"] != expected_environment):
        raise QualificationError("performance producer input differs: candidate environment")
    return producer_path


def validate_performance_result(receipt: dict, request: dict, *, require_witness: bool = True) -> dict:
    receipt = dict(receipt)
    if receipt.get("schema_version") != 1 or receipt.get("kind") != "windows-host-performance":
        raise QualificationError("unsupported performance receipt")
    mode = request.get("performance", {}).get("mode")
    if receipt.get("phase") != "performance" or receipt.get("mode") != mode:
        raise QualificationError("performance receipt mode mismatch")
    repository = request.get("source", {}).get("repository", request["_paths"]["owned_root"])
    roots = (canonical(repository, must_exist=True), request["_paths"]["owned_root"])
    validate_performance_contract(request, roots, mode=mode)
    producer_path = _require_matching_producer_input(receipt.get("producer_input"), request, roots, mode=mode)
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
        _check_environment(environment, request, roots=roots, run_dir=run_dir)
    _, window = _artifact(receipt["measurement_window"], label="measurement window", roots=roots, run_dir=run_dir)
    _check_window(window, run_dir=run_dir, receipt=receipt, require_witness=False)
    previous_end = window["started_monotonic"]
    violations = []
    for phase in PHASES:
        _, resolved = _artifact(receipt["resolved_inputs"][phase], label=f"{phase} resolved inputs", roots=roots, run_dir=run_dir)
        asset_prefix = _check_resolved_inputs(resolved, phase=phase, mode=mode)
        _, measurement = _artifact(receipt["measurements"][phase], label=f"{phase} measurement", roots=roots, run_dir=run_dir)
        blocks, per_block = _check_measurement_recipe(measurement, mode=mode)
        _check_resolved_measurement_identity(resolved, measurement)
        try:
            page_result = evaluate_pages(measurement, blocks=blocks, per_block=per_block)
            transport_result = validate_transport(
                measurement, spacing_events=50, require_direct_asset=True,
                direct_asset_prefix=asset_prefix, fail_on_violation=False,
            )
        except ValueError as error:
            raise QualificationError(str(error)) from error
        if not (previous_end <= measurement["spacing"]["started"]
                <= measurement["spacing"]["arrivals"][-1]
                <= measurement["saturation"]["started"]
                <= measurement["saturation"]["ended"] <= window["ended_monotonic"]):
            raise QualificationError("measurement phase is outside its ordered source-bound window")
        previous_end = measurement["saturation"]["ended"]
        violations.extend({**row, "phase": phase} for row in page_result["violations"])
        violations.extend({**row, "phase": phase} for row in transport_result.get("violations", []))
    _, cleanup = _artifact(receipt["cleanup"], label="cleanup", roots=roots, run_dir=run_dir)
    _check_cleanup(cleanup)
    check_terminal_resolution_cleanup(window, cleanup)
    if require_witness:
        _check_window(window, run_dir=run_dir, receipt=receipt)
    status_pass = receipt.get("status") == "PASS" and receipt.get("collection_status") == "COMPLETE"
    eligible = bool(mode == "certify" and status_pass and not receipt.get("errors") and not violations)
    return {
        "kind": "windows-host-performance",
        "mode": mode,
        "collection_status": receipt.get("collection_status"),
        "violations": violations,
        "acceptance_eligible": eligible,
        "producer_input_sha256": digest_file(producer_path),
    }


def validate_bound_receipt(key: str, path: Path, request: dict) -> dict:
    receipt = read_json(path)
    receipt["_receipt_path"] = str(path)
    result = validate_performance_result(receipt, request)
    if not result["acceptance_eligible"]:
        raise QualificationError("performance evidence is not certification eligible")
    return {**result, "sha256": digest_file(path)}

"""Bind native host evidence to the candidate's resolved dependency environment."""
from pathlib import Path

from scripts.validation import windows_qualification_inputs as inputs
from scripts.validation.project_full_stack_support import read_json
from scripts.validation.windows_migration_admission import ENVIRONMENT_PROBE, capture_environment
from scripts.validation.windows_qualification_inputs import QualificationError
from scripts.validation.windows_install_smoke import LEGACY_SDK_MODULES


def read_reference(reference, root, label):
    if not isinstance(reference, dict) or not {"path", "sha256"} <= reference.keys():
        raise QualificationError(f"{label} environment reference is missing")
    path = inputs.owned_file(reference["path"], root)
    inputs.require_hash(path, reference["sha256"], f"{label} environment")
    return path, read_json(path)


def expected_environment(request):
    reference = request["python"].get("environments", {}).get("candidate")
    _, value = read_reference(reference, request["_paths"]["owned_root"], "frozen candidate")
    if (inputs.canonical(value.get("executable", "")) != request["_paths"]["python"]
            or not value.get("python") or not isinstance(value.get("packages"), dict) or not value["packages"]
            or value.get("shadowed_distributions") != {}
            or not isinstance(value.get("sys_path"), list)
            or not value.get("selected_imports", {}).get("ai_base_runtime")
            or any(value["selected_imports"].get(name) is not None for name in LEGACY_SDK_MODULES)):
        raise QualificationError("frozen candidate environment is not an isolated modern runtime")
    return value


def capture(request, directory: Path):
    expected = expected_environment(request)
    observed, reference = capture_environment(request["_paths"]["python"], directory)
    if observed != expected:
        raise QualificationError("candidate environment changed")
    return reference


def validate(reference, request, root: Path, *, command_check):
    path, observed = read_reference(reference, root, "observed candidate")
    if observed != expected_environment(request):
        raise QualificationError("candidate environment changed")
    command_path, command = read_reference(reference.get("command"), root, "candidate probe command")
    if inputs.canonical(command.get("stdout", "")) != path:
        raise QualificationError("candidate environment stdout does not match its probe")
    command_check(
        {**command, "receipt": str(command_path)}, root, label="environment",
        argv=[str(request["_paths"]["python"]), "-I", "-c", ENVIRONMENT_PROBE],
    )

"""Semantic checks for migration output, never a Boolean receipt shortcut."""
from pathlib import Path
import re
from types import SimpleNamespace
from uuid import UUID

from project_management.app.domain.report_publication_contracts import publication_path
from project_management.storage.git import GitRunner
from scripts.service_lifecycle_engine import PlatformOperationSet
from scripts.service_lifecycle_engine.provenance import command_fingerprint
from scripts.validation.project_full_stack_identity import current_launch_for_service, normal_stop_evidence, validate_manifest
from scripts.validation.project_full_stack_support import read_json
from scripts.validation.windows_migration_inventory import (
    validate_archive_bindings, validate_source_owner, verify_preserved_archive, verify_snapshot_inventory,
)
from scripts.validation.windows_qualification_inputs import QualificationError, canonical, digest_file, require_hash
from scripts.validation.windows_install_smoke import LEGACY_SDK_MODULES


KIND = "windows-migration-rehearsal"
COMMAND_RETURNS = {
    "new-migrate": 0, "new-start": 0, "new-busy": 1, "new-restart-app": 0,
    "new-stop": 0, "old-start": 0, "old-stop": 0,
}
HTTP_STEPS = {
    "new-health", "new-pane", "sessions-empty", "session-open", "new-report",
    "session-read", "session-reopen", "new-report-reopened", "old-report",
}


def reference(path: Path) -> dict:
    return {"path": str(path), "sha256": digest_file(path)}


def artifact(value: dict, root: Path) -> Path:
    path = canonical(value["path"])
    if not path.is_relative_to(root) or path == root:
        raise QualificationError("migration artifact is outside the owned run")
    require_hash(path, value["sha256"], "migration artifact")
    return path


def command_artifact(value: dict, root: Path, expected: int) -> dict:
    record = read_json(artifact(value, root))
    if (type(record.get("returncode")) is not int or record["returncode"] != expected
            or record.get("expected_returncode") != expected or record.get("timed_out") is not False):
        raise QualificationError("migration command result is invalid")
    if not record.get("argv") or not record.get("cwd"):
        raise QualificationError("migration command lacks executor identity")
    for name in ("stdout", "stderr"):
        artifact({"path": record[name], "sha256": record[f"{name}_sha256"]}, root)
    return record


def validate_command_identity(record: dict, label: str, request, runs: dict, root: Path) -> None:
    if label not in COMMAND_RETURNS:
        raise QualificationError("unknown migration command")
    role, action = label.split("-", 1)
    identity = request.current if role == "new" else request.old
    if canonical(record["cwd"]) != identity.repository:
        raise QualificationError("migration command source directory mismatch")
    argv = record["argv"]
    if action in {"start", "stop", "restart-app"}:
        expected = [
            str(identity.app_python), "-I", str(identity.repository / "scripts/validation/project_full_stack.py"),
            action, "--run-dir", str(runs[role]),
        ]
        if action == "start":
            expected += ["--lifetime-seconds", "600"]
        if argv != expected:
            raise QualificationError("migration stack command identity mismatch")
        return
    prefix = [
        str(identity.app_python), "-I",
        str(identity.repository / "scripts/validation/project_full_stack_app_entry.py"),
    ]
    if argv[:3] != prefix or len(argv) < 8 or argv[3] != "--qualify-launch-id" or argv[5] != "--qualify-exit-file":
        raise QualificationError("migration management command identity mismatch")
    if str(UUID(argv[4])) != argv[4] or argv[6] != str(root / f"{label}-exit.json"):
        raise QualificationError("migration management exit identity mismatch")
    catalog = read_json(Path(request.snapshot.run_dir) / "runtime-manifest.json")["catalog"]
    expected = ["migrate", "--noinput", "--verbosity", "0"] if action == "migrate" else [
        "project_run", "start", catalog["project_id"], catalog["stage_id"],
        "--expected-stage-hash", catalog["stage_hash"], "--execute-local",
    ]
    if role != "new" or argv[7:] != expected:
        raise QualificationError("migration management arguments mismatch")


def validate_session(value: dict, session_key: str) -> dict:
    keys = {"sessionId", "appId", "agent", "contextRef", "sessionKey", "embedPath"}
    if (not isinstance(value, dict) or set(value) != keys
            or not isinstance(value["sessionId"], str) or not re.fullmatch(r"[A-Za-z0-9._:-]+", value["sessionId"])
            or value["appId"] != "metrics" or value["agent"] != "dashboard"
            or value["sessionKey"] != session_key or value["contextRef"] is not None
            or not str(value["embedPath"]).startswith("/ai/")):
        raise QualificationError("runtime session identity mismatch")
    return value


def publication_hashes(run: Path, seed: dict) -> dict:
    validate_archive_bindings(run)
    stage = run / "archive/projects" / seed["project_id"] / "stages" / seed["stage_id"]
    git = GitRunner(stage / "archive", stage / "runtime/empty-hooks")
    result = {}
    from hashlib import sha256
    for packet in seed["packets"]:
        hashes = {}
        for name, expected in packet["files"].items():
            path = publication_path(packet["publication_id"], name)
            observed = sha256(git.run(["show", f'{packet["commit"]}:{path}']).stdout).hexdigest()
            if observed != expected:
                raise QualificationError("retained publication bytes changed")
            hashes[name] = observed
        result[packet["publication_id"]] = hashes
    return result


def validate_old_wire(source_run: Path, new_run: Path, current) -> dict:
    source = source_run / "runtime-manifest.json"
    value = {
        **read_json(source), "repository": str(current.repository), "run_dir": str(new_run),
        "app_python": str(current.app_python),
    }
    try:
        validate_manifest(new_run, value, root=current.repository, app_python=current.app_python)
    except ValueError as error:
        if str(error) != "Runtime manifest schema is invalid.":
            raise QualificationError("legacy wire failed for an unrelated reason") from error
        return {"manifest": reference(source), "error": str(error)}
    raise QualificationError("new host accepted the legacy manifest")


def validate_stop_summary(payload: dict, run: Path, *, before: dict | None = None, stdout_offset: int = 0) -> dict:
    if payload.get("status") != "stopped" or payload.get("normal") is not True:
        raise QualificationError("migration stop was not normal")
    path = canonical(payload["evidence"])
    if not path.is_relative_to(run / "evidence/stop"):
        raise QualificationError("stop receipt is outside the owned run")
    raw = read_json(path)
    if raw.get("classification") != "normal" or set(raw) not in ({"app", "model", "classification"}, {"app", "base", "classification"}):
        raise QualificationError("stop receipt classification is invalid")
    state = before or read_json(run / "lifecycle/dashboard-full-stack-qualify.json")["services"]
    names = {"app": "project-app", "model": "scripted-model", "base": "ai-base"}
    proofs = {}
    platform = PlatformOperationSet()
    for key in set(raw) - {"classification"}:
        result, name = raw[key], names[key]
        if (result.get("stopped") is not True or result.get("forced") is not False
                or result.get("reason") not in {"stop_command", "owned_listener:stop_command"}):
            raise QualificationError("forced or incomplete migration stop")
        service = state[name]
        launch = current_launch_for_service(run, service, name)
        process = read_json(launch.directory / "process-proof.json")
        relation = process.get("relation")
        if (process.get("schema_version") != 1 or process.get("service") != name
                or process.get("launch_id") != launch.launch_id or process.get("wrapper_pid") != service["pid"]
                or process.get("command_fingerprint") != command_fingerprint(tuple(service["command"]))
                or relation not in {"registered_wrapper", "worker_child"}
                or (process.get("worker_pid") == service["pid"]) != (relation == "registered_wrapper")):
            raise QualificationError("migration process proof identity mismatch")
        proof = normal_stop_evidence(
            launch, service, SimpleNamespace(**result),
            stdout_start=stdout_offset if key == "app" else 0, require_worker_event=key == "app",
        )
        pids = {int(service["pid"]), int(proof["process_proof"]["worker_pid"])}
        if any(platform.process_exists(pid) for pid in pids):
            raise QualificationError("migration service process remains")
        if platform.get_listening_process_ids(str(service.get("host", "127.0.0.1")), int(service["port"])):
            raise QualificationError("migration listener remains")
        proofs[key] = {
            "exit": reference(launch.exit_file),
            "process": reference(launch.directory / "process-proof.json"),
            "stdout": reference(Path(service["stdout_log"])),
        }
    return {"receipt": reference(path), "proofs": proofs, "stdout_offset": stdout_offset}


def validate_http(receipt: dict, request, root: Path) -> None:
    http = receipt["http"]
    if set(http) != HTTP_STEPS:
        raise QualificationError("migration HTTP inventory incomplete")
    for row in http.values():
        if type(row["status"]) is not int or row["status"] != 200:
            raise QualificationError("migration HTTP request did not succeed")
        artifact(row["body"], root)
    if read_json(artifact(http["sessions-empty"]["body"], root)) != []:
        raise QualificationError("new host imported old chat state")
    sessions = [
        validate_session(read_json(artifact(http[key]["body"], root)), receipt["session_key"])
        for key in ("session-open", "session-read", "session-reopen")
    ]
    if sessions[1:] != [sessions[0], sessions[0]]:
        raise QualificationError("session did not survive restart by the same key")
    manifest = read_json(Path(request.snapshot.run_dir) / "runtime-manifest.json")
    paths = {
        "new-health": manifest["routes"]["project_stage_reports"], "new-pane": "/ai/",
        "sessions-empty": "/ai/api/chat/sessions?appId=metrics&limit=100",
        "session-open": "/ai/api/chat/sessions", "session-reopen": "/ai/api/chat/sessions",
        "session-read": f'/ai/api/chat/sessions/{sessions[0]["sessionId"]}',
        "new-report": request.seed["route"], "new-report-reopened": request.seed["route"],
        "old-report": request.seed["route"],
    }
    ports = {
        role: read_json(artifact(receipt["stops"][role]["before"], root))["project-app"]["port"]
        for role in ("new", "old")
    }
    for label, row in http.items():
        method = "POST" if label in {"session-open", "session-reopen"} else "GET"
        role = "old" if label == "old-report" else "new"
        url = f'http://127.0.0.1:{ports[role]}{paths[label]}'
        content_type = "application/json" if label.startswith("session") else "text/html"
        if (row["method"] != method or row["path"] != paths[label] or row.get("url") != url
                or not row["content_type"].lower().startswith(content_type)):
            raise QualificationError("migration HTTP phase identity mismatch")
    for key in ("new-report", "new-report-reopened", "old-report"):
        body = artifact(http[key]["body"], root).read_text(encoding="utf-8")
        if any(identifier not in body for identifier in request.seed["publications"]):
            raise QualificationError("retained publication missing from page")


def validate_admission(phase: dict, request, root: Path) -> None:
    from scripts.validation.windows_migration_admission import ENVIRONMENT_PROBE
    from scripts.validation.windows_install_smoke import validate_import_probe
    interpreters = {
        "candidate": request.current.app_python, "old_app": request.old.app_python, "old_base": request.old.base_python,
    }
    for role, ref in phase["environments"].items():
        observed = read_json(artifact(ref, root))
        if observed != request.environments[role]:
            raise QualificationError("migration environment mismatch")
        if role == "candidate" and (
            observed["shadowed_distributions"]
            or any(observed["selected_imports"].get(name) is not None for name in LEGACY_SDK_MODULES)
        ):
            raise QualificationError("candidate environment is not isolated")
        command = command_artifact(ref["command"], root, 0)
        if command["argv"] != [str(interpreters[role]), "-I", "-c", ENVIRONMENT_PROBE] or command["stdout"] != ref["path"]:
            raise QualificationError("environment probe command identity mismatch")
    if set(phase["environments"]) != {"candidate", "old_app", "old_base"}:
        raise QualificationError("migration environment role missing")
    admission_commands = [command_artifact(ref, root, 0) for ref in phase["commands"]]
    admission_labels = [record["label"] for record in admission_commands]
    if admission_labels != ["runtime-admission", "candidate-pip-check"]:
        raise QualificationError("migration admission command inventory incomplete")
    for record in admission_commands:
        label = record["label"]
        expected = (
            [str(request.current.app_python), "-I", str(request.current.repository / "scripts/validation/windows_install_smoke.py"), "--probe"]
            if label == "runtime-admission" else [str(interpreters[label.removesuffix("-pip-check")]), "-I", "-m", "pip", "check"]
        )
        if record["argv"] != expected or canonical(record["cwd"]) != request.current.repository:
            raise QualificationError("migration admission executor mismatch")
    validate_import_probe(
        read_json(Path(admission_commands[0]["stdout"])), request.current.app_python.parent.parent,
        request.current.repository,
    )


def validate_result(receipt: dict, request) -> None:
    root = canonical(receipt["run_root"])
    if not root.is_relative_to(request.paths["owned_root"] / "migration-runs"):
        raise QualificationError("migration run root mismatch")
    if receipt.get("kind") != KIND or receipt.get("scope") != "windows-functional" or receipt.get("status") != "PASS":
        raise QualificationError("migration receipt scope mismatch")
    if not isinstance(receipt.get("postflight"), dict):
        raise QualificationError("migration postflight is missing")
    input_path = canonical(receipt["inputs"]["path"])
    if not (input_path.is_relative_to(request.current.repository) or input_path.is_relative_to(request.paths["owned_root"])):
        raise QualificationError("migration input reference is outside allowed roots")
    require_hash(input_path, receipt["inputs"]["sha256"], "migration producer input")
    produced_from = read_json(input_path)
    for key in ("source", "candidate", "python", "owned_root", "fixtures", "migration", "rollback"):
        if produced_from.get(key) != request.data.get(key):
            raise QualificationError(f"migration producer input differs: {key}")
    if produced_from.get("acceptance_profile") != "functional":
        raise QualificationError("migration producer input is not functional")
    expected_sources = {
        "dashboard": {"commit": request.current.commit, "status": ""},
        "old_dashboard": {"commit": request.old.commit, "status": ""},
    }
    if (receipt["preflight"]["sources"] != expected_sources or receipt["sources_after"] != expected_sources
            or receipt["postflight"].get("sources") != expected_sources):
        raise QualificationError("migration source identity mismatch")
    if receipt.get("candidate") != request.data["candidate"] or receipt.get("fixture_vector_sha256") != request.data["fixtures"]["fixture_vector_sha256"]:
        raise QualificationError("migration candidate or fixture mismatch")
    runs = {}
    if set(receipt["runs"]) != {"new", "old"}:
        raise QualificationError("migration copy inventory mismatch")
    for role, value in receipt["runs"].items():
        run = canonical(value)
        if run.parent != root / f"{role}-data" or run.name != request.snapshot.run_uuid:
            raise QualificationError("migration copy identity mismatch")
        identity = request.current if role == "new" else request.old
        validate_source_owner(run, identity.as_record())
        runs[role] = run
    copies = read_json(artifact(receipt["copies"], root))
    expected_files = [{"path": item["path"], "sha256": item["sha256"], "size": item["size"]} for item in request.snapshot.files]
    for role in ("new", "old"):
        copied = copies[role]
        if (copied["snapshot_id"] != request.snapshot.snapshot_id or copied["mode"] != role
                or copied["source_run"] != request.snapshot.run_dir or copied["destination_run"] != str(runs[role])):
            raise QualificationError("migration copy-map identity mismatch")
        for field in ("source_verified_before", "source_verified_after", "copied_files"):
            if copied[field] != expected_files:
                raise QualificationError("migration copy-map inventory mismatch")
        backup = runs[role] / "evidence/migration-backup" / request.snapshot.snapshot_id
        if copied.get("backup_root") != str(backup):
            raise QualificationError("migration backup identity mismatch")
        if role == "new":
            for item in request.snapshot.files:
                if item["path"].startswith("base/"):
                    require_hash(canonical(backup / item["path"]), item["sha256"], "preserved legacy backup")
    validate_admission(receipt["preflight"], request, root)
    validate_admission(receipt["postflight"], request, root)
    commands = receipt["commands"]
    if set(commands) != set(COMMAND_RETURNS):
        raise QualificationError("migration command inventory incomplete")
    for label, expected in COMMAND_RETURNS.items():
        record = command_artifact(commands[label], root, expected)
        if record.get("label") != label:
            raise QualificationError(f"migration command failed: {label}")
        validate_command_identity(record, label, request, runs, root)
        if label in {"new-migrate", "new-busy"}:
            exit_path = artifact(receipt["management_exits"][label], root)
            exit_record = read_json(exit_path)
            if (str(exit_path) != record["argv"][6] or exit_record.get("schema_version") != 1
                    or exit_record.get("service") != "project-app" or exit_record.get("launch_id") != record["argv"][4]
                    or type(exit_record.get("pid")) is not int or exit_record["pid"] <= 0
                    or type(exit_record.get("exit_code")) is not int or exit_record["exit_code"] != expected):
                raise QualificationError("migration management exit receipt mismatch")
    if set(receipt["management_exits"]) != {"new-migrate", "new-busy"}:
        raise QualificationError("migration management exit inventory mismatch")
    validate_http(receipt, request, root)
    for role in ("new", "old"):
        run = runs[role]
        if verify_preserved_archive(run, request.snapshot, retire_operations=role == "new") != receipt["archive_files_preserved"][role]:
            raise QualificationError("native archive preservation evidence mismatch")
        if publication_hashes(run, request.seed) != receipt["publications"][role]:
            raise QualificationError("migration publication evidence mismatch")
        stop = receipt["stops"][role]
        before = read_json(artifact(stop["before"], root))
        record = read_json(artifact(commands[f"{role}-stop"], root))
        summary = read_json(Path(record["stdout"]))
        validated = validate_stop_summary(summary, run, before=before, stdout_offset=stop["stdout_offset"])
        if validated != stop["verified"]:
            raise QualificationError("migration cleanup evidence mismatch")
    if receipt["old_wire"] != validate_old_wire(Path(request.snapshot.run_dir), Path(receipt["runs"]["new"]), request.current):
        raise QualificationError("legacy wire refusal evidence mismatch")
    busy = read_json(artifact(commands["new-busy"], root))
    error_text = Path(busy["stderr"]).read_text(encoding="utf-8").strip().removeprefix("CommandError: ")
    import json
    if json.loads(error_text).get("error", {}).get("code") != "RUN_BUSY":
        raise QualificationError("local execution did not refuse the owned runtime")
    source_files = verify_snapshot_inventory(Path(request.snapshot.run_dir), request.snapshot)
    if list(source_files) != receipt["source_files_after"]:
        raise QualificationError("original snapshot preservation mismatch")


def validate_bound_receipt(key: str, path: Path, data: dict) -> dict:
    if key != "task:10.3":
        raise QualificationError(f"migration receipt cannot cover {key}")
    receipt = read_json(path)
    if receipt.get("kind") != KIND or receipt.get("scope") != "windows-functional" or receipt.get("status") != "PASS":
        raise QualificationError("migration receipt scope mismatch")
    from scripts.validation.windows_migration_admission import from_validated_input
    validate_result(receipt, from_validated_input(data))
    return {"kind": KIND, "scope": "windows-functional", "sha256": digest_file(path), "mapped_keys": [key]}

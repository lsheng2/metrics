"""Execute the frozen, synthetic Windows old/new migration rehearsal."""
import argparse
import json
from pathlib import Path
import sys
import uuid

import requests

from scripts.validation.project_full_stack_support import read_json, write_json
from scripts.validation.qualify_ai_runtime import run_command
from scripts.validation.windows_install_smoke import installer_environment
from scripts.validation.windows_migration_admission import load_request, preflight, recheck_inputs
from scripts.validation.windows_migration_evidence import (
    KIND, publication_hashes, reference, validate_old_wire, validate_result,
    validate_session, validate_stop_summary,
)
from scripts.validation.windows_migration_inventory import verify_preserved_archive, verify_snapshot_inventory
from scripts.validation.windows_migration_rehearsal import copy_snapshot_for_new_host, copy_snapshot_for_old_restore
from scripts.validation.windows_qualification_inputs import QualificationError


def stack_command(request, role: str, run: Path, action: str) -> list[str]:
    if role not in {"new", "old"} or action not in {"start", "restart-app", "stop"}:
        raise QualificationError("unregistered migration command")
    identity = request.current if role == "new" else request.old
    command = [
        str(identity.app_python), "-I", str(identity.repository / "scripts/validation/project_full_stack.py"),
        action, "--run-dir", str(run),
    ]
    return command + ["--lifetime-seconds", "600"] if action == "start" else command


class Rehearsal:
    def __init__(self, request, directory: Path):
        self.request, self.directory = request, directory
        self.environment = installer_environment(directory / "private")
        self.receipt = {
            "schema_version": 1, "kind": KIND, "scope": "windows-functional", "status": "RUNNING",
            "run_root": str(directory), "inputs": reference(request.paths["inputs"]),
            "candidate": request.data["candidate"],
            "fixture_vector_sha256": request.data["fixtures"]["fixture_vector_sha256"],
            "session_key": f"metrics.migration.{directory.name}", "commands": {},
            "http": {}, "runs": {}, "stops": {}, "publications": {}, "management_exits": {},
        }

    def command(self, label, argv, *, cwd, env=None, expected=0):
        record_path = self.directory / "commands" / f"{label}.command.json"
        try:
            return run_command(
                argv, cwd=cwd, log_dir=record_path.parent, label=label, timeout=180,
                env=env or self.environment, expected_returncode=expected,
            )
        finally:
            if record_path.exists():
                self.receipt["commands"][label] = reference(record_path)

    def stack(self, role, run, action):
        identity = self.request.current if role == "new" else self.request.old
        before, offset, before_path = None, 0, None
        if action == "stop":
            state_path = run / "lifecycle/dashboard-full-stack-qualify.json"
            before = read_json(state_path)["services"] if state_path.exists() else {}
            if "project-app" in before:
                app_log = Path(before["project-app"]["stdout_log"])
                offset = app_log.stat().st_size if app_log.exists() else 0
            before_path = self.directory / f"{role}-before-stop.json"
            write_json(before_path, before)
        result = self.command(f"{role}-{action}", stack_command(self.request, role, run, action), cwd=identity.repository)
        payload = read_json(Path(result["stdout"]))
        if action == "stop":
            self.receipt["stops"][role] = {
                "before": reference(before_path), "stdout_offset": offset,
                "verified": validate_stop_summary(payload, run, before=before, stdout_offset=offset),
            }
        elif payload.get("status") != "running":
            raise QualificationError("migration service did not become ready")
        return payload

    def management(self, run, label, arguments, *, expected=0):
        manifest = read_json(run / "runtime-manifest.json")
        env = {
            **self.environment, "DJANGO_SETTINGS_MODULE": "scripts.validation.project_full_stack_settings",
            "METRICS_PROJECT_FULL_STACK_RUN_DIR": str(run), "METRICS_PROJECT_FULL_STACK_BOOTSTRAP": "1",
        }
        if "model" in manifest:
            env.update({
                "METRICS_AI_MODEL_BASE_URL": manifest["model"]["base_url"],
                "METRICS_AI_MODEL_NAME": manifest["model"]["model"],
                "METRICS_AI_MODEL_API_KEY": manifest["model"]["api_key"],
            })
        identity = self.request.current
        argv = [
            str(identity.app_python), "-I", str(identity.repository / "scripts/validation/project_full_stack_app_entry.py"),
            "--qualify-launch-id", str(uuid.uuid4()),
            "--qualify-exit-file", str(self.directory / f"{label}-exit.json"), *arguments,
        ]
        try:
            return self.command(label, argv, cwd=identity.repository, env=env, expected=expected)
        finally:
            exit_path = self.directory / f"{label}-exit.json"
            if exit_path.exists():
                self.receipt["management_exits"][label] = reference(exit_path)

    def observe(self, client, run, label, path, *, payload=None):
        if not path.startswith("/") or path.startswith("//"):
            raise QualificationError("untrusted migration HTTP path")
        manifest = read_json(run / "runtime-manifest.json")
        method = "GET" if payload is None else "POST"
        owner = manifest["auth"]["alice"]
        response = client.request(
            method, f'http://127.0.0.1:{manifest["app_port"]}{path}', json=payload,
            auth=(owner["username"], owner["password"]), timeout=20, allow_redirects=False,
        )
        body = self.directory / "http" / f"{label}.body"
        body.parent.mkdir(exist_ok=True)
        body.write_bytes(response.content)
        self.receipt["http"][label] = {
            "method": method, "path": path, "url": response.url, "status": response.status_code,
            "body": reference(body), "content_type": response.headers.get("Content-Type", ""),
        }
        if response.status_code != 200:
            raise QualificationError(f"migration HTTP failure: {label}")
        if label in {"new-report", "new-report-reopened", "old-report"}:
            if any(identifier not in response.text for identifier in self.request.seed["publications"]):
                raise QualificationError("retained publication missing from page")
        return response

    def new_host(self, run):
        self.management(run, "new-migrate", ["migrate", "--noinput", "--verbosity", "0"])
        attempted = False
        try:
            attempted = True
            self.stack("new", run, "start")
            with requests.Session() as client:
                client.trust_env = False
                manifest = read_json(run / "runtime-manifest.json")
                self.observe(client, run, "new-health", manifest["routes"]["project_stage_reports"])
                self.observe(client, run, "new-pane", "/ai/")
                empty = self.observe(client, run, "sessions-empty", "/ai/api/chat/sessions?appId=metrics&limit=100")
                if empty.json() != []:
                    raise QualificationError("new host imported old chat state")
                opening = {"appId": "metrics", "agent": "dashboard", "sessionKey": self.receipt["session_key"]}
                session = self.observe(client, run, "session-open", "/ai/api/chat/sessions", payload=opening).json()
                validate_session(session, self.receipt["session_key"])
                self.observe(client, run, "new-report", self.request.seed["route"])
                catalog = manifest["catalog"]
                busy = self.management(run, "new-busy", [
                    "project_run", "start", catalog["project_id"], catalog["stage_id"],
                    "--expected-stage-hash", catalog["stage_hash"], "--execute-local",
                ], expected=1)
                error = Path(busy["stderr"]).read_text(encoding="utf-8").strip().removeprefix("CommandError: ")
                if json.loads(error).get("error", {}).get("code") != "RUN_BUSY":
                    raise QualificationError("local execution did not refuse the owned runtime")
                self.stack("new", run, "restart-app")
                restored = self.observe(client, run, "session-read", f'/ai/api/chat/sessions/{session["sessionId"]}').json()
                reopened = self.observe(client, run, "session-reopen", "/ai/api/chat/sessions", payload=opening).json()
                if restored != session or reopened != session:
                    raise QualificationError("session did not survive restart by the same key")
                self.observe(client, run, "new-report-reopened", self.request.seed["route"])
        finally:
            if attempted:
                self.stack("new", run, "stop")

    def old_host(self, run):
        try:
            self.stack("old", run, "start")
            with requests.Session() as client:
                client.trust_env = False
                self.observe(client, run, "old-report", self.request.seed["route"])
        finally:
            self.stack("old", run, "stop")


def rehearse(request) -> dict:
    directory = request.paths["owned_root"] / "migration-runs" / str(uuid.uuid4())
    directory.mkdir(parents=True)
    execution = Rehearsal(request, directory)
    receipt = execution.receipt
    try:
        receipt["preflight"] = preflight(request, directory / "admission")
        new = copy_snapshot_for_new_host(
            request.snapshot, directory / "new-data", current_identity=request.current, old_identity=request.old,
        )
        old = copy_snapshot_for_old_restore(request.snapshot, directory / "old-data", old_identity=request.old)
        write_json(directory / "copies.json", {"new": new, "old": old})
        receipt["copies"] = reference(directory / "copies.json")
        receipt["runs"] = {"new": new.destination_run, "old": old.destination_run}
        new_run, old_run = Path(new.destination_run), Path(old.destination_run)
        publication_hashes(new_run, request.seed)
        receipt["old_wire"] = validate_old_wire(Path(request.snapshot.run_dir), new_run, request.current)
        execution.new_host(new_run)
        execution.old_host(old_run)
        receipt["publications"] = {
            "new": publication_hashes(new_run, request.seed), "old": publication_hashes(old_run, request.seed),
        }
        receipt["archive_files_preserved"] = {
            "new": verify_preserved_archive(new_run, request.snapshot, retire_operations=True),
            "old": verify_preserved_archive(old_run, request.snapshot, retire_operations=False),
        }
        receipt["source_files_after"] = list(verify_snapshot_inventory(Path(request.snapshot.run_dir), request.snapshot))
        recheck_inputs(request)
        receipt["postflight"] = preflight(request, directory / "postflight")
        receipt["sources_after"] = receipt["postflight"]["sources"]
        receipt["status"] = "PASS"
        validate_result(receipt, request)
        return receipt
    except BaseException as error:
        receipt.update(status="FAIL", error_type=type(error).__name__, error=str(error))
        write_json(directory / "failed-rehearsal.json", receipt)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        request = load_request(args.inputs, args.output)
        receipt = rehearse(request)
        write_json(request.paths["output"], receipt)
        return 0
    except Exception as error:
        print(f"windows_migration_rehearsal: {error}", file=sys.stderr)
        return 1

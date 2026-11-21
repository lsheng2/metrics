import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from scripts.tests.test_windows_migration_admission import migration_case
from scripts.validation.windows_qualification_inputs import QualificationError


@pytest.mark.parametrize("role", ["new", "old"])
def test_stack_command_uses_the_selected_source_and_interpreter(tmp_path, monkeypatch, role):
    from scripts.validation import windows_migration_admission as admission
    from scripts.validation import windows_migration_driver as driver

    case = migration_case(tmp_path, monkeypatch)
    request = admission.load_request(case["inputs"], case["output"])
    run = case["owned"] / "fresh-copy"
    identity = request.current if role == "new" else request.old
    command = driver.stack_command(request, role, run, "start")
    assert command == [
        str(identity.app_python), "-I", str(identity.repository / "scripts/validation/project_full_stack.py"),
        "start", "--run-dir", str(run), "--lifetime-seconds", "600",
    ]
    with pytest.raises(QualificationError):
        driver.stack_command(request, role, run, "arbitrary-user-command")


def test_cli_rejects_invalid_inputs_without_starting_a_rehearsal(tmp_path, monkeypatch):
    from scripts.validation import windows_migration_driver as driver

    case = migration_case(tmp_path, monkeypatch)
    case["snapshot"].write_text("{}", encoding="utf-8")
    calls = []
    monkeypatch.setattr(driver, "rehearse", lambda request: calls.append(request))
    assert driver.main(["--inputs", str(case["inputs"]), "--output", str(case["output"])]) != 0
    assert calls == []
    assert not case["output"].exists()


def test_preflight_failure_cannot_copy_or_start_services(tmp_path, monkeypatch):
    from scripts.validation import windows_migration_admission as admission
    from scripts.validation import windows_migration_driver as driver

    case = migration_case(tmp_path, monkeypatch)
    request = admission.load_request(case["inputs"], case["output"])
    calls = []
    monkeypatch.setattr(driver, "preflight", lambda *args: (_ for _ in ()).throw(QualificationError("environment changed")))
    monkeypatch.setattr(driver, "copy_snapshot_for_new_host", lambda *args, **kwargs: calls.append("copy"))
    with pytest.raises(QualificationError, match="environment changed"):
        driver.rehearse(request)
    assert calls == []


@pytest.mark.parametrize("payload", [
    {"status": "stopped", "normal": False},
    {"status": "running", "normal": True},
    {"status": "stopped", "normal": "true"},
    {"status": "stopped", "normal": True, "evidence": "missing.json"},
])
def test_stop_summary_cannot_bypass_semantic_cleanup_proof(tmp_path, payload):
    from scripts.validation.windows_migration_driver import validate_stop_summary

    with pytest.raises((QualificationError, ValueError, FileNotFoundError)):
        validate_stop_summary(payload, tmp_path)


def test_http_evidence_rejects_redirects_and_wrong_session_identity(tmp_path):
    from scripts.validation.windows_migration_driver import validate_session

    opened = {
        "sessionId": "session_1", "appId": "metrics", "agent": "dashboard",
        "contextRef": None, "sessionKey": "metrics.migration.test", "embedPath": "/ai/session_1",
    }
    assert validate_session(opened, "metrics.migration.test") == opened
    for field, wrong in (("sessionKey", "other.key"), ("appId", "another-app"), ("agent", "another-agent")):
        with pytest.raises(QualificationError):
            validate_session({**opened, field: wrong}, "metrics.migration.test")


def test_partial_start_still_delegates_stop_without_an_app_record(tmp_path, monkeypatch):
    from scripts.validation import windows_migration_admission as admission
    from scripts.validation import windows_migration_driver as driver
    from scripts.validation.project_full_stack_support import write_json

    case = migration_case(tmp_path, monkeypatch)
    request = admission.load_request(case["inputs"], case["output"])
    directory = case["owned"] / "migration-run"
    directory.mkdir()
    run = case["owned"] / "partial-start"
    write_json(run / "lifecycle/dashboard-full-stack-qualify.json", {"services": {"scripted-model": {"pid": 12}}})
    output = directory / "stop.json"
    write_json(output, {"status": "stopped", "normal": False})
    calls = []

    def stopped(argv, **kwargs):
        calls.append(argv)
        return {"stdout": str(output)}

    monkeypatch.setattr(driver, "run_command", stopped)
    execution = driver.Rehearsal(request, directory)
    with pytest.raises(QualificationError):
        execution.stack("new", run, "stop")
    assert calls == [driver.stack_command(request, "new", run, "stop")]


def test_command_evidence_rechecks_raw_output_hashes_and_exit_types(tmp_path):
    from scripts.validation.qualify_ai_runtime import run_command
    from scripts.validation.windows_migration_evidence import command_artifact, reference

    result = run_command(
        [sys.executable, "-I", "-c", "print('observed')"], cwd=tmp_path,
        log_dir=tmp_path / "logs", label="probe", timeout=10,
    )
    ref = reference(Path(result["receipt"]))
    assert command_artifact(ref, tmp_path, 0)["returncode"] == 0
    Path(result["stdout"]).write_text("forged", encoding="utf-8")
    with pytest.raises(QualificationError, match="hash"):
        command_artifact(ref, tmp_path, 0)
    record = json.loads(Path(result["receipt"]).read_text(encoding="utf-8"))
    record["returncode"] = False
    Path(result["receipt"]).write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(QualificationError, match="result"):
        command_artifact(reference(Path(result["receipt"])), tmp_path, 0)


@pytest.mark.parametrize("mutation", ["failed_worker_exit", "process_service", "command_fingerprint"])
def test_stop_validation_resolves_and_verifies_process_receipts(tmp_path, monkeypatch, mutation):
    from scripts.validation import windows_migration_evidence as evidence
    from scripts.validation.project_full_stack_identity import create_launch, write_exit_receipt
    from scripts.validation.project_full_stack_support import write_json
    from scripts.service_lifecycle_engine.provenance import command_fingerprint

    run = tmp_path / "11111111-1111-4111-8111-111111111111"
    before, raw = {}, {"classification": "normal"}
    app_launch = None
    for index, (key, name) in enumerate((("app", "project-app"), ("model", "scripted-model")), start=1):
        launch = create_launch(run, name)
        command = ["synthetic-python", "--launch-id", launch.launch_id]
        output = run / f"{key}.log"
        output.write_text('{"event":"project_runtime_stopped","stopped":true,"unresolved":[]}\n', encoding="utf-8")
        before[name] = {
            "pid": index, "port": 12340 + index, "host": "127.0.0.1",
            "command": command, "stop_command": ["touch", str(launch.stop_file)],
            "stdout_log": str(output),
        }
        write_exit_receipt(launch.exit_file, service=name, launch_id=launch.launch_id, pid=index, exit_code=0)
        write_json(launch.directory / "process-proof.json", {
            "schema_version": 1, "service": name, "launch_id": launch.launch_id,
            "wrapper_pid": index, "worker_pid": index, "relation": "registered_wrapper",
            "command_fingerprint": command_fingerprint(tuple(command)),
        })
        raw[key] = {"stopped": True, "forced": False, "reason": "stop_command"}
        if key == "app":
            app_launch = launch
    stop_path = run / "evidence/stop/stopped/stop-receipt.json"
    write_json(stop_path, raw)
    summary = {"status": "stopped", "normal": True, "evidence": str(stop_path)}
    monkeypatch.setattr(evidence, "PlatformOperationSet", lambda: SimpleNamespace(
        process_exists=lambda pid: False, get_listening_process_ids=lambda host, port: [],
    ))
    assert evidence.validate_stop_summary(summary, run, before=before)["proofs"].keys() == {"app", "model"}
    if mutation == "failed_worker_exit":
        write_exit_receipt(app_launch.exit_file, service="project-app", launch_id=app_launch.launch_id, pid=1, exit_code=3)
        message = "exit receipt"
    else:
        path = app_launch.directory / "process-proof.json"
        proof = json.loads(path.read_text(encoding="utf-8"))
        proof["service" if mutation == "process_service" else "command_fingerprint"] = "wrong"
        path.write_text(json.dumps(proof), encoding="utf-8")
        message = "process proof"
    with pytest.raises((ValueError, QualificationError), match=message):
        evidence.validate_stop_summary(summary, run, before=before)


@pytest.mark.parametrize("mutation", [None, "redirect", "wrong-path", "wrong-port", "new-session", "missing-report", "tampered-body"])
def test_http_replay_requires_the_actual_phase_paths_and_persisted_payload(tmp_path, mutation):
    from scripts.validation import windows_migration_evidence as evidence
    from scripts.validation.project_full_stack_support import write_json

    source = tmp_path / "source"
    write_json(source / "runtime-manifest.json", {"routes": {"project_stage_reports": "/projects/catalog/"}})
    request = SimpleNamespace(
        snapshot=SimpleNamespace(run_dir=str(source)),
        seed={"route": "/projects/retained/", "publications": ["pub-1"]},
    )
    session = {"sessionId": "session_1", "appId": "metrics", "agent": "dashboard",
               "contextRef": None, "sessionKey": "metrics.migration.test", "embedPath": "/ai/session_1"}
    paths = {
        "new-health": "/projects/catalog/", "new-pane": "/ai/",
        "sessions-empty": "/ai/api/chat/sessions?appId=metrics&limit=100",
        "session-open": "/ai/api/chat/sessions", "session-read": "/ai/api/chat/sessions/session_1",
        "session-reopen": "/ai/api/chat/sessions", "new-report": "/projects/retained/",
        "new-report-reopened": "/projects/retained/", "old-report": "/projects/retained/",
    }
    receipt = {"session_key": session["sessionKey"], "http": {}, "stops": {}}
    for role in ("new", "old"):
        before = tmp_path / f"{role}-before.json"
        write_json(before, {"project-app": {"port": 8127}})
        receipt["stops"][role] = {"before": evidence.reference(before)}
    for label, path in paths.items():
        api = label.startswith("session")
        body = tmp_path / f"{label}.body"
        body.write_text(json.dumps([] if label == "sessions-empty" else session) if api else "<html>pub-1</html>", encoding="utf-8")
        receipt["http"][label] = {
            "path": path, "url": f"http://127.0.0.1:8127{path}",
            "method": "POST" if label in {"session-open", "session-reopen"} else "GET",
            "status": 200, "content_type": "application/json" if api else "text/html",
            "body": evidence.reference(body),
        }
    row = receipt["http"]["new-report"]
    if mutation == "redirect":
        row["status"] = 302
    elif mutation == "wrong-path":
        row["path"] = "/another-page"
    elif mutation == "wrong-port":
        row["url"] = "http://127.0.0.1:8128/projects/retained/"
    elif mutation == "new-session":
        body = Path(receipt["http"]["session-read"]["body"]["path"])
        body.write_text(json.dumps({**session, "sessionId": "different"}), encoding="utf-8")
        receipt["http"]["session-read"]["body"] = evidence.reference(body)
    elif mutation in {"missing-report", "tampered-body"}:
        body = Path(row["body"]["path"])
        body.write_text("<html>no publication</html>", encoding="utf-8")
        if mutation == "missing-report":
            row["body"] = evidence.reference(body)
    if mutation is None:
        evidence.validate_http(receipt, request, tmp_path)
    else:
        with pytest.raises(QualificationError):
            evidence.validate_http(receipt, request, tmp_path)


@pytest.mark.parametrize("mutation", [None, "interpreter", "script", "cwd", "data-root"])
def test_command_replay_binds_the_actual_source_and_owned_copy(tmp_path, monkeypatch, mutation):
    from scripts.validation import windows_migration_admission as admission
    from scripts.validation import windows_migration_driver as driver
    from scripts.validation import windows_migration_evidence as evidence

    case = migration_case(tmp_path, monkeypatch)
    request = admission.load_request(case["inputs"], case["output"])
    root = case["owned"] / "migration-runs/11111111-1111-4111-8111-111111111111"
    runs = {role: root / f"{role}-data" / request.snapshot.run_uuid for role in ("new", "old")}
    record = {
        "argv": driver.stack_command(request, "new", runs["new"], "start"),
        "cwd": str(request.current.repository),
    }
    if mutation == "interpreter":
        record["argv"][0] = str(request.old.app_python)
    elif mutation == "script":
        record["argv"][2] = str(request.old.repository / "scripts/validation/project_full_stack.py")
    elif mutation == "cwd":
        record["cwd"] = str(request.old.repository)
    elif mutation == "data-root":
        record["argv"][5] = str(case["source_run"])
    if mutation is None:
        evidence.validate_command_identity(record, "new-start", request, runs, root)
    else:
        with pytest.raises(QualificationError):
            evidence.validate_command_identity(record, "new-start", request, runs, root)


def test_receipt_cannot_omit_the_post_run_environment_check(tmp_path, monkeypatch):
    from scripts.validation import windows_migration_admission as admission
    from scripts.validation import windows_migration_evidence as evidence

    case = migration_case(tmp_path, monkeypatch)
    request = admission.load_request(case["inputs"], case["output"])
    root = case["owned"] / "migration-runs/11111111-1111-4111-8111-111111111111"
    root.mkdir(parents=True)
    sources = {
        "dashboard": {"commit": request.current.commit, "status": ""},
        "old_dashboard": {"commit": request.old.commit, "status": ""},
    }
    receipt = {
        "kind": evidence.KIND, "scope": "windows-functional", "status": "PASS", "run_root": str(root),
        "preflight": {"sources": sources}, "sources_after": sources,
        "candidate": request.data["candidate"], "fixture_vector_sha256": request.data["fixtures"]["fixture_vector_sha256"],
    }
    with pytest.raises(QualificationError, match="postflight"):
        evidence.validate_result(receipt, request)


def test_producer_consumer_binding_includes_historical_input_declaration(tmp_path, monkeypatch):
    from scripts.tests.test_qualify_ai_runtime import _sha, _write_json
    from scripts.tests.test_windows_migration_history import _historical_case
    from scripts.validation import windows_migration_admission as admission
    from scripts.validation import windows_migration_evidence as evidence

    case = _historical_case(tmp_path, monkeypatch)
    request = admission.load_request(case["inputs"], case["output"])
    root = case["owned"] / "migration-runs/11111111-1111-4111-8111-111111111111"
    root.mkdir(parents=True)
    produced = json.loads(case["inputs"].read_text(encoding="utf-8"))
    produced["migration"]["historical_inputs"]["root"] = str(case["history"].parent)
    producer_inputs = _write_json(case["owned"] / "producer-inputs.json", produced)
    receipt = {
        "kind": evidence.KIND,
        "scope": "windows-functional",
        "status": "PASS",
        "run_root": str(root),
        "postflight": {},
        "inputs": {"path": str(producer_inputs), "sha256": _sha(producer_inputs)},
    }

    with pytest.raises(QualificationError, match="migration producer input differs: migration"):
        evidence.validate_result(receipt, request)


def test_historical_dev4_receipt_cannot_bind_to_dev5_request(tmp_path, monkeypatch):
    from scripts.tests.test_qualify_ai_runtime import _sha, _write_json
    from scripts.tests.test_windows_migration_history import _historical_case
    from scripts.validation import windows_migration_admission as admission
    from scripts.validation import windows_migration_evidence as evidence

    case = _historical_case(tmp_path, monkeypatch)
    request = admission.load_request(case["inputs"], case["output"])
    root = case["owned"] / "migration-runs/11111111-1111-4111-8111-111111111111"
    root.mkdir(parents=True)
    produced = json.loads(case["inputs"].read_text(encoding="utf-8"))
    produced["candidate"] = {**produced["candidate"], "source_commit": "dev4-candidate"}
    producer_inputs = _write_json(case["owned"] / "dev4-producer-inputs.json", produced)
    receipt_path = _write_json(case["owned"] / "dev4-migration-receipt.json", {
        "kind": evidence.KIND,
        "scope": "windows-functional",
        "status": "PASS",
        "run_root": str(root),
        "postflight": {},
        "inputs": {"path": str(producer_inputs), "sha256": _sha(producer_inputs)},
    })

    with pytest.raises(QualificationError, match="migration producer input differs: candidate"):
        evidence.validate_bound_receipt("task:10.3", receipt_path, request.data)


@pytest.mark.parametrize("key, message", [("task:10.3", "migration receipt scope"), ("task:1.1", "cannot cover")])
def test_qualifier_routes_only_the_registered_migration_scope(tmp_path, monkeypatch, key, message):
    from scripts.tests.test_qualify_ai_runtime import _base_case, _sha, _write_json
    from scripts.validation.windows_qualification_evidence import validate_binding

    case = _base_case(tmp_path, monkeypatch)
    binding = case["manifest"]["checks"]["evidence_bindings"]["task:1.1"].copy()
    path = Path(binding["path"])
    _write_json(path, {"kind": "windows-migration-rehearsal", "status": "PASS", "scope": "wrong-scope"})
    binding.update(kind="windows-migration-rehearsal", sha256=_sha(path), covers=[key])
    with pytest.raises(QualificationError, match=message):
        validate_binding(key, binding, case["manifest"], (case["root"], case["owned"]))

from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.tests.test_qualify_ai_runtime import APP_COMMIT, _base_case, _sha, _write_json, _write_junit
from scripts.validation import qualify_ai_runtime as qualifier
from scripts.validation import windows_install_smoke as install_smoke
from scripts.validation import windows_qualification_inputs as input_validator
from scripts.validation.windows_qualification_inputs import QualificationError
from scripts.validation.windows_install_smoke import PINS


TRIGGERS = ["stop-file", "SIGINT", "SIGTERM", "CTRL_BREAK_EVENT", "lifetime"]
NATIVE_BREAKS = ["stop-file", "CTRL_BREAK_EVENT"]
LIMITS = {"heartbeat": 2.0, "streams": 4, "requests": 4, "terminal_grace": 2.0}


def _set_roots(monkeypatch, root: Path) -> None:
    from scripts.validation import windows_host_conformance as conformance
    from scripts.validation import windows_host_conformance_evidence as native_evidence

    for module in (qualifier, input_validator, install_smoke, conformance, native_evidence):
        monkeypatch.setattr(module, "ROOT", root)


def _case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    case = _base_case(tmp_path, monkeypatch)
    _set_roots(monkeypatch, case["root"])
    (case["root"] / "ai_host/tests").mkdir(parents=True, exist_ok=True)
    (case["root"] / "ai_host/tests/serve_stream_entry.py").write_text("# synthetic entry\n", encoding="utf-8")
    amendment = case["root"] / "openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-b5-owner-decision.md"
    amendment.parent.mkdir(parents=True, exist_ok=True)
    amendment.write_text("# B5 Owner Amendment B5-r1\n", encoding="utf-8")
    case["manifest"]["native_conformance"] = {
        "amendment": {"path": str(amendment), "sha256": _sha(amendment)}
    }
    environment = _write_json(case["owned"] / "candidate-environment.json", {
        "executable": case["manifest"]["python"]["candidate"], "python": "3.13.7",
        "packages": {"ai-base-runtime": {"version": "1.0.0", "record_sha256": "synthetic"}},
        "sys_path": ["synthetic-site-packages"], "shadowed_distributions": {},
        "selected_imports": {"ai_base_runtime": "synthetic-site-packages/ai_base_runtime/__init__.py",
                             "ai_base_application_sdk": None},
    })
    case["manifest"]["python"]["environments"] = {
        "candidate": {"path": str(environment), "sha256": _sha(environment)},
    }
    _write_json(case["inputs"], case["manifest"])
    return case


def _server_records(*, pending: int = 0) -> list[dict]:
    return [
        {"event": "stream_host_ready", "threads": 14, "deadline": 100.0},
        {"event": "stream_stop_started", "started_at": 10.0},
        {"event": "stream_flush_started", "pending_bytes": pending},
        {"event": "stream_flush_finished", "pending_bytes": pending},
        {"event": "stream_stop_finished", "outcome": {
            "exit_code": 0,
            "http_result": {
                "completed": True, "unfinished_stream_ids": [], "undelivered_stream_ids": [],
                "error_codes": [], "elapsed_seconds": 1.5,
            },
            "cleanup_errors": [],
        }},
        {"event": "project_runtime_stopped", "stopped": True, "unresolved": [], "active_operation_id": None},
        {"event": "serve_exit_inventory", "threads": [], "children": [], "errors": []},
        {"event": "serve_exit_cleanup", "errors": [], "finalizers": []},
    ]


def _observation(identity: dict | None = None, *, backlog: bool = False) -> dict:
    events = [{"at": 10.2, "payload": {"type": "heartbeat"}}]
    if identity is not None:
        events.append({"at": 10.3, "payload": {"type": "chat.state", **identity, "status": "running"}})
    if backlog:
        events.extend({"at": 13.1 + index / 1000, "payload": {"type": "backlog", "index": index, "data": "x" * 16300}}
                      for index in range(512))
    events.append({"at": 13.8 if backlog else 11.0, "payload": {"type": "stream.terminated", "reason": "http_closing"}})
    return {"events": events, "terminal_at": events[-1]["at"], "eof_at": events[-1]["at"] + 0.01}


def _process(path: Path, python: Path, repo: Path, trigger: str, *, returncode: int = 0, forced: bool = False) -> None:
    _write_json(path / "process.json", {
        "argv": [str(python), "-I", str(repo / "ai_host/tests/serve_stream_entry.py"), str(path), "1234",
                 str(path / "stop"), "-", trigger],
        "pid": 123,
        "port": 1234,
        "returncode": returncode,
        "forced_cleanup": forced,
        "descendants": [{"pid": 456, "parent_pid": 123}],
        "descendant_exit_codes": {"456": 0},
    })


def _stream_case(root: Path, python: Path, repo: Path, name: str, payload: dict) -> dict:
    case = root / name
    case.mkdir(parents=True)
    _write_json(case / "streams.json", payload)
    (case / "serve.log").write_text(
        "\n".join(json.dumps(row) for row in payload["server"]), encoding="utf-8",
    )
    _process(case, python, repo, payload["trigger"])
    return {"streams": case / "streams.json", "process": case / "process.json", "log": case / "serve.log"}


def _b5_artifacts(root: Path, python: Path, repo: Path) -> list[dict]:
    refs = []
    for trigger in TRIGGERS:
        identities = [{"sessionId": f"s{index}-{trigger}", "runId": f"r{index}-{trigger}"} for index in range(2)]
        refs.append(_stream_case(root, python, repo, f"chat-{trigger}", {
            "amendment": "B5-r1", "proof_id": "B5-chat", "trigger": trigger,
            "triggered_at": 10.0, "stop_started_at": 10.0, "exited_at": 10.3,
            "before": {"limits": LIMITS}, "identities": identities,
            "observations": [_observation(identity) for identity in identities],
            "server": _server_records(),
        }))
    for trigger in TRIGGERS:
        refs.append(_stream_case(root, python, repo, f"slow-{trigger}", {
            "amendment": "B5-r1", "proof_id": "B5-transport", "trigger": trigger, "workload": "slow",
            "triggered_at": 10.0, "stop_started_at": 10.0, "resumed_at": 13.1, "exited_at": 13.3,
            "before": {"limits": LIMITS, "pending_bytes": 8_141_716, "counts": {"backlog_blocks": 512}},
            "observations": [_observation(), _observation(), _observation(backlog=True)],
            "server": _server_records(pending=8_141_716),
        }))
    for trigger in NATIVE_BREAKS:
        refs.append(_stream_case(root, python, repo, f"never-{trigger}", {
            "amendment": "B5-r1", "proof_id": "B5-transport", "trigger": trigger, "workload": "never-read",
            "triggered_at": 10.0, "stop_started_at": 10.0, "exited_at": 16.8,
            "before": {"limits": LIMITS, "pending_bytes": 8_141_716, "counts": {"backlog_blocks": 512}},
            "observations": [], "server": _server_records(pending=8_141_716),
        }))
    return refs


def _backpressure(path: Path) -> Path:
    return _write_json(path, {
        "paused_producer_blocks": 16,
        "after_consumption_blocks": 20,
        "block_bytes": 65532,
        "consumed_bytes": 20 * 65532,
        "stream_in_flight_after_close": 0,
        "host_in_flight_after_close": 0,
        "generator_closed": True,
    })


def _disconnect(path: Path, python: Path, repo: Path) -> Path:
    baseline = {"probe": {"limits": LIMITS, "counts": {}, "pending_bytes": 0, "tasks": {}, "threads": ["main"]},
                "diagnostics": {"streamInFlightCount": 0}, "ready": {"threads": 14}}
    cycles = []
    for index in range(20):
        cycles.append({
            "index": index, "closed_at": 20.0 + index, "reclaimed_at": 20.5 + index, "elapsed": 0.5,
            "active": {"probe": {"counts": {"streams": 1}}, "diagnostics": {"streamInFlightCount": 1}},
            "after": {"probe": {"counts": {"streams": 0, "streams_done": index + 1}, "pending_bytes": 0,
                                 "tasks": {}, "threads": ["main"]},
                      "diagnostics": {"streamInFlightCount": 0}},
        })
    path.parent.mkdir(parents=True, exist_ok=True)
    _process(path.parent, python, repo, "stop-file")
    records = _server_records()
    (path.parent / "serve.log").write_text("\n".join(json.dumps(row) for row in records), encoding="utf-8")
    return _write_json(path, {
        "schema_version": 1, "proof_id": "W2.HOST.native_disconnect", "endpoint": "/ai/apps/metrics/api/qualification/idle",
        "repeat": 20, "trigger": "stop-file", "baseline": baseline, "cycles": cycles,
        "final": {"probe": {"counts": {"streams": 0, "streams_done": 20}, "pending_bytes": 0,
                             "tasks": {}, "threads": ["main"]},
                  "diagnostics": {"streamInFlightCount": 0}},
        "server": records, "process": json.loads((path.parent / "process.json").read_text(encoding="utf-8")),
    })


def _signals(root: Path) -> list[Path]:
    paths = []
    for trigger in TRIGGERS:
        path = _write_json(root / f"normal-{trigger}" / "signal.json", {
            "trigger": trigger, "phase": "normal", "returncode": 0, "elapsed": 0.3,
            "forced_cleanup": False, "descendant_exit_codes": {"456": 0},
        })
        paths.append(path)
        path.with_name("serve.log").write_text(
            "\n".join(json.dumps(row) for row in _server_records()) + "\nserve stopped.\n", encoding="utf-8",
        )
        for phase in ("drain", "flush"):
            path = _write_json(root / f"{phase}-{trigger}" / "signal.json", {
                "trigger": trigger, "phase": phase, "returncode": 130, "elapsed": 0.3,
                "forced_cleanup": False, "descendant_exit_codes": {"456": 130}, "event": {"sent": True},
            })
            paths.append(path)
            path.with_name("serve.log").write_text("serve forced exit.\n", encoding="utf-8")
    path = _write_json(root / "final-stop-file" / "signal.json", {
        "trigger": "stop-file", "phase": "final", "returncode": 130, "elapsed": 0.3,
        "forced_cleanup": False, "descendant_exit_codes": {"456": 130}, "event": {"sent": True},
    })
    paths.append(path)
    path.with_name("serve.log").write_text("serve forced exit.\n", encoding="utf-8")
    return paths


def _import_probe(python: Path, repo: Path) -> dict:
    prefix = python.parent.parent
    site = prefix / "Lib/site-packages"
    return {
        "prefix": str(prefix), "base_prefix": str(prefix.parent / "base"), "user_site": False,
        "paths": [str(prefix), str(repo)],
        "versions": dict(PINS),
        "modules": {name: str(prefix / name.replace("-", "_") / "__init__.py") for name in PINS},
        "distributions": {name: str(site) for name in PINS},
        "legacy_sdk": False, "unowned_pth": [],
    }


def _command_record(root: Path, label: str, argv: list[str], cwd: Path, stdout_payload: dict | None = None) -> dict:
    stdout = root / "logs" / f"{label}.stdout.txt"
    stderr = root / "logs" / f"{label}.stderr.txt"
    record = root / "logs" / f"{label}.command.json"
    stdout.parent.mkdir(parents=True, exist_ok=True)
    stdout.write_text(json.dumps(stdout_payload or {}, sort_keys=True) + "\n", encoding="utf-8")
    stderr.write_text("", encoding="utf-8")
    payload = {
        "label": label, "argv": argv, "cwd": str(cwd), "returncode": 0, "expected_returncode": 0,
        "timed_out": False, "stdout": str(stdout), "stderr": str(stderr),
        "stdout_sha256": _sha(stdout), "stderr_sha256": _sha(stderr),
    }
    _write_json(record, payload)
    return {**payload, "receipt": str(record)}


def _junit_inventory(root: Path) -> dict:
    from scripts.validation.windows_host_conformance_contract import EXPECTED_JUNIT_CASES

    result = {}
    for label, cases in EXPECTED_JUNIT_CASES.items():
        path = root / "junit" / f"{label}.xml"
        path.parent.mkdir(parents=True, exist_ok=True)
        case_xml = "".join(f'<testcase classname="{case.rsplit("::", 1)[0]}" name="{case.rsplit("::", 1)[1]}"/>' for case in cases)
        path.write_text(f'<testsuite tests="{len(cases)}" failures="0" errors="0" skipped="0">{case_xml}</testsuite>', encoding="utf-8")
        result[label] = {"path": str(path), "sha256": _sha(path), "cases": list(cases)}
    return result


def _lane_commands(root: Path, python: Path, junit: dict, cwd: Path) -> dict:
    from scripts.validation.windows_host_conformance_contract import BASE_ARGS, LANE_TARGETS

    result = {}
    for lane, targets in LANE_TARGETS.items():
        argv = [str(python), "-I", "scripts/validation/run_report_authoring_tests.py", *targets]
        if lane == "backpressure":
            argv += ["-p", "ai_base_runtime.testkit.pytest_plugin", "-p", "ai_host.tests.conformance_fixtures", "-o", "ai_host_modes=blocking_wsgi"]
        basetemp = str(root / "artifacts" / lane)
        result[lane] = {
            **_command_record(root, f"native-{lane}", [*argv, *BASE_ARGS, "--basetemp", basetemp, "--junitxml", junit[lane]["path"]], cwd),
            "basetemp": basetemp,
        }
    return result


def _valid_receipt(case: dict) -> tuple[dict, Path]:
    from scripts.validation import windows_host_conformance_evidence as native_evidence

    run = case["owned"] / "conformance-runs" / "11111111-1111-4111-8111-111111111111"
    run.mkdir(parents=True)
    b5_refs = _b5_artifacts(run / "b5", Path(case["manifest"]["python"]["candidate"]), case["root"])
    backpressure = _backpressure(run / "backpressure/backpressure.json")
    disconnect = _disconnect(
        run / "disconnect/disconnects.json", Path(case["manifest"]["python"]["candidate"]), case["root"],
    )
    signals = _signals(run / "signal")
    python = Path(case["manifest"]["python"]["candidate"])
    junit = _junit_inventory(run)
    from scripts.validation.windows_migration_admission import ENVIRONMENT_PROBE
    expected = json.loads(Path(case["manifest"]["python"]["environments"]["candidate"]["path"]).read_text(encoding="utf-8"))
    environments = {}
    for phase in ("before", "after"):
        command = _command_record(
            run / phase, "environment", [str(python), "-I", "-c", ENVIRONMENT_PROBE],
            case["root"], expected,
        )
        environments[phase] = {
            "path": command["stdout"], "sha256": command["stdout_sha256"],
            "command": {"path": command["receipt"], "sha256": _sha(Path(command["receipt"]))},
        }
    receipt = {
        "schema_version": 1,
        "kind": native_evidence.KIND,
        "phase": "conformance",
        "scope": "windows-functional-native",
        "status": "PASS",
        "run_root": str(run),
        "inputs": {"path": str(case["inputs"]), "sha256": _sha(case["inputs"])},
        "environments": environments,
        "source_before": {"commit": APP_COMMIT, "status": ""},
        "source_after": {"commit": APP_COMMIT, "status": ""},
        "candidate": {
            "version": case["manifest"]["candidate"]["version"],
            "wheel_sha256": case["manifest"]["candidate"]["wheel_sha256"],
        },
        "fixture_vector_sha256": case["manifest"]["fixtures"]["fixture_vector_sha256"],
        "amendment": deepcopy(case["manifest"]["native_conformance"]["amendment"]),
        "covered_keys": [
            "clause:10.4:B1-native-second-signal:functional",
            "clause:10.4:B4-disconnect-leaks:functional",
            "clause:10.4:B5-stream-stop:functional",
        ],
        "admission": {
            "runtime_admission": _command_record(
                run, "runtime-admission",
                [str(python), "-I", str(case["root"] / "scripts/validation/windows_install_smoke.py"), "--probe"],
                case["root"], _import_probe(python, case["root"]),
            ),
            "candidate_pip_check": _command_record(
                run, "candidate-pip-check", [str(python), "-I", "-m", "pip", "check"], case["root"],
            ),
        },
        "non_applicable": [{"case": "ASGI host conformance", "status": "NOT_APPLICABLE", "counted": False}],
        "commands": _lane_commands(run, python, junit, case["root"]),
        "artifacts": {
            "b5": [{"streams": {"path": str(ref["streams"]), "sha256": _sha(ref["streams"])},
                    "process": {"path": str(ref["process"]), "sha256": _sha(ref["process"])},
                    "log": {"path": str(ref["log"]), "sha256": _sha(ref["log"])}} for ref in b5_refs],
            "backpressure": {"path": str(backpressure), "sha256": _sha(backpressure)},
            "disconnect": {
                "path": str(disconnect), "sha256": _sha(disconnect),
                "process": {"path": str(disconnect.with_name("process.json")), "sha256": _sha(disconnect.with_name("process.json"))},
                "log": {"path": str(disconnect.with_name("serve.log")), "sha256": _sha(disconnect.with_name("serve.log"))},
            },
            "signals": [{"path": str(path), "sha256": _sha(path),
                         "log": {"path": str(path.with_name("serve.log")), "sha256": _sha(path.with_name("serve.log"))}}
                        for path in signals],
        },
        "junit": junit,
    }
    return receipt, run


def test_valid_native_receipt_maps_only_semantically_checked_clause_keys(tmp_path, monkeypatch):
    from scripts.validation import windows_host_conformance_evidence as native_evidence

    case = _case(tmp_path, monkeypatch)
    request = input_validator.load_request(case["inputs"], case["output"], profile="functional")
    receipt, _ = _valid_receipt(case)

    result = native_evidence.validate_result(receipt, request)

    assert result["covered_keys"] == receipt["covered_keys"]
    assert "clause:10.4:B5-stream-stop:functional" in result["covered_keys"]
    assert "task:10.4" not in result["covered_keys"]
    assert result["b5"]["chat_triggers"] == TRIGGERS
    assert result["b5"]["transport_slow_triggers"] == TRIGGERS
    assert result["b5"]["transport_never_read_triggers"] == NATIVE_BREAKS
    assert result["backpressure"]["paused_producer_blocks"] == 16


@contextmanager
def _changed_receipt(original, mutation):
    receipt, originals = deepcopy(original), {}

    def load(path, *, json_value=True):
        originals[path] = path.read_bytes()
        return json.loads(originals[path]) if json_value else None

    try:
        _mutate_receipt(receipt, mutation, load)
        yield receipt
    finally:
        for path, content in originals.items():
            path.write_bytes(content)


def _mutate_receipt(receipt, mutation, load):
    if mutation == "scope":
        receipt["scope"] = "windows-performance"
    elif mutation == "schema":
        receipt["schema_version"] = 2
    elif mutation == "raw_log":
        ref = receipt["artifacts"]["b5"][0]["log"]
        path = Path(ref["path"])
        load(path, json_value=False)
        path.write_text('{"event":"different-run"}\n', encoding="utf-8")
        ref["sha256"] = _sha(path)
    elif mutation == "missing_chat":
        receipt["artifacts"]["b5"] = receipt["artifacts"]["b5"][1:]
    elif mutation == "command_replay":
        record = Path(receipt["admission"]["candidate_pip_check"]["receipt"])
        payload = load(record)
        payload["argv"] = ["python", "-I", "-m", "pip", "check"]
        _write_json(record, payload)
    elif mutation == "junit_skip":
        row = receipt["junit"]["backpressure"]
        path = Path(row["path"])
        load(path, json_value=False)
        path.write_text('<testsuite tests="1" failures="0" errors="0" skipped="1"><testcase classname="x" name="y"><skipped /></testcase></testsuite>', encoding="utf-8")
        row["sha256"] = _sha(path)
        row["cases"] = ["x::y"]
    elif mutation == "disconnect_cycle":
        path = Path(receipt["artifacts"]["disconnect"]["path"])
        payload = load(path)
        payload["cycles"].pop()
        _write_json(path, payload)
        receipt["artifacts"]["disconnect"]["sha256"] = _sha(path)
    elif mutation == "backpressure":
        path = Path(receipt["artifacts"]["backpressure"]["path"])
        payload = load(path)
        payload["paused_producer_blocks"] = 512
        _write_json(path, payload)
        receipt["artifacts"]["backpressure"]["sha256"] = _sha(path)
    else:
        streams_path = Path(receipt["artifacts"]["b5"][0]["streams"]["path"])
        payload = load(streams_path)
        if mutation == "timing":
            payload["observations"][0]["events"][-1]["at"] = 13.0
            payload["observations"][0]["terminal_at"] = 13.0
        elif mutation == "identity":
            payload["observations"][0]["events"][1]["payload"]["runId"] = "wrong"
        elif mutation == "server_cleanup":
            cleanup = next(row for row in payload["server"] if row["event"] == "serve_exit_cleanup")
            cleanup["errors"] = ["leak"]
        elif mutation == "nan_terminal":
            payload["observations"][0]["terminal_at"] = float("nan")
        else:
            process_path = Path(receipt["artifacts"]["b5"][0]["process"]["path"])
            process = load(process_path)
            process["returncode"] = 1
            _write_json(process_path, process)
            receipt["artifacts"]["b5"][0]["process"]["sha256"] = _sha(process_path)
        _write_json(streams_path, payload)
        receipt["artifacts"]["b5"][0]["streams"]["sha256"] = _sha(streams_path)
        if mutation == "server_cleanup":
            log = receipt["artifacts"]["b5"][0]["log"]
            path = Path(log["path"])
            load(path, json_value=False)
            path.write_text("\n".join(json.dumps(row) for row in payload["server"]), encoding="utf-8")
            log["sha256"] = _sha(path)


def test_native_receipt_rejects_missing_or_weakened_semantics(tmp_path, monkeypatch):
    from scripts.validation import windows_host_conformance_evidence as native_evidence

    case = _case(tmp_path, monkeypatch)
    request = input_validator.load_request(case["inputs"], case["output"], profile="functional")
    original, _ = _valid_receipt(case)
    rejected = []
    # Restore changed bytes between boundary attacks instead of rewriting
    # the same 40 MiB fixture for every rejection case.
    for mutation in (
        "missing_chat", "timing", "identity", "process", "backpressure", "server_cleanup",
        "disconnect_cycle", "command_replay", "junit_skip", "nan_terminal",
        "scope", "schema", "raw_log",
    ):
        with _changed_receipt(original, mutation) as receipt:
            with pytest.raises(QualificationError):
                native_evidence.validate_result(receipt, request)
        rejected.append(mutation)
    _write_json(tmp_path / "rejected-mutations.json", rejected)
    assert native_evidence.validate_result(original, request)["kind"] == "windows-host-conformance"


def test_qualifier_rejects_generic_junit_for_native_b5_key(tmp_path, monkeypatch):
    from scripts.validation import windows_qualification_evidence as qualifier_evidence

    case = _case(tmp_path, monkeypatch)
    request = input_validator.load_request(case["inputs"], case["output"], profile="functional")
    junit = case["owned"] / "native.xml"
    _write_junit(junit)
    binding = {
        "kind": "junit", "path": str(junit), "sha256": _sha(junit),
        "source_commit": APP_COMMIT,
        "candidate_wheel_sha256": case["manifest"]["candidate"]["wheel_sha256"],
        "fixture_vector_sha256": case["manifest"]["fixtures"]["fixture_vector_sha256"],
        "covers": ["clause:10.4:B5-stream-stop:functional"], "cases": ["lane::case_0"], "fresh": True,
    }
    with pytest.raises(QualificationError, match="native conformance"):
        qualifier_evidence.validate_binding(
            "clause:10.4:B5-stream-stop:functional", binding, request, (case["root"], case["owned"]),
        )


def test_qualifier_accepts_owned_native_conformance_receipt_for_b5_key(tmp_path, monkeypatch):
    from scripts.validation import windows_qualification_evidence as qualifier_evidence

    case = _case(tmp_path, monkeypatch)
    request = input_validator.load_request(case["inputs"], case["output"], profile="functional")
    receipt, _ = _valid_receipt(case)
    receipt_path = _write_json(case["owned"] / "native-receipt.json", receipt)
    binding = {
        "kind": "windows-host-conformance", "path": str(receipt_path), "sha256": _sha(receipt_path),
        "source_commit": APP_COMMIT,
        "candidate_wheel_sha256": case["manifest"]["candidate"]["wheel_sha256"],
        "fixture_vector_sha256": case["manifest"]["fixtures"]["fixture_vector_sha256"],
        "covers": ["clause:10.4:B5-stream-stop:functional"], "fresh": True,
    }
    result = qualifier_evidence.validate_binding(
        "clause:10.4:B5-stream-stop:functional", binding, request, (case["root"], case["owned"]),
    )
    assert result["kind"] == "windows-host-conformance"
    assert result["mapped_keys"] == ["clause:10.4:B5-stream-stop:functional"]


def test_phase_performance_rejects_before_perf_helper_import_or_execution(tmp_path, monkeypatch, capsys):
    from scripts.validation import windows_host_qualification as host_qualification
    import sys

    case = _case(tmp_path, monkeypatch)
    sys.modules.pop("scripts.validation.windows_host_benchmark", None)
    assert host_qualification.main(["--phase", "performance", "--inputs", str(case["inputs"]), "--output", str(case["output"])]) == 1
    assert "deferred" in capsys.readouterr().err
    assert "scripts.validation.windows_host_benchmark" not in sys.modules
    assert not case["output"].exists()


def test_conformance_rejects_dirty_source_before_running_native_lanes(tmp_path, monkeypatch):
    from scripts.validation import windows_host_qualification as host_qualification
    from scripts.validation import windows_host_conformance as conformance

    case = _case(tmp_path, monkeypatch)
    commands = []
    monkeypatch.setattr(conformance, "source_identity", lambda repo, commit: (_ for _ in ()).throw(
        QualificationError("source tree is not frozen")
    ))
    monkeypatch.setattr(conformance, "run_command", lambda *args, **kwargs: commands.append(args))
    assert host_qualification.main(["--phase", "conformance", "--inputs", str(case["inputs"]), "--output", str(case["output"])]) == 1
    assert commands == []
    assert not case["output"].exists()


def test_isolated_native_cli_reaches_validation_without_import_failure(tmp_path):
    root = Path(__file__).resolve().parents[2]
    output = tmp_path / "receipt.json"
    result = subprocess.run([
        sys.executable, "-I", str(root / "scripts/validation/windows_host_qualification.py"),
        "--phase", "conformance", "--inputs", str(tmp_path / "missing.json"), "--output", str(output),
    ], cwd=tmp_path, capture_output=True, text=True, timeout=20)
    assert result.returncode == 1
    assert "windows_host_conformance:" in result.stderr, result.stderr
    assert "Traceback" not in result.stderr, result.stderr
    assert not output.exists()

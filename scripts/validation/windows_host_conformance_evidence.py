"""Semantic evidence checks for native Windows host conformance."""
from __future__ import annotations

import math
from pathlib import Path
from uuid import UUID

from scripts.validation.project_full_stack_support import read_json
from scripts.validation.windows_host_conformance_records import (
    require_matching_server_log, require_terminal_exits, server_log, validate_descendant_exits,
)
from scripts.validation.windows_host_conformance_contract import (
    B1_KEY, B4_KEY, B5_KEY, KIND, NATIVE_KEYS, TRIGGERS, NATIVE_BREAKS, LIMITS,
    EXPECTED_JUNIT_CASES, BASE_ARGS, LANE_TARGETS,
)
from scripts.validation.windows_qualification_inputs import (
    QualificationError, canonical, digest_file, require_hash, validate_frozen_hashes,
)

ROOT = Path(__file__).resolve().parents[2]

def _num(value, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise QualificationError(f"{label} must be a finite non-negative number")
    return float(value)

def _artifact(ref: dict, root: Path, label: str) -> Path:
    path = canonical(ref["path"], must_exist=True)
    if not path.is_relative_to(root) or path == root:
        raise QualificationError(f"{label} artifact is outside the conformance run")
    require_hash(path, ref["sha256"], label)
    return path

def _bound_file(value: str, digest: str, root: Path, label: str) -> Path:
    path = canonical(value, must_exist=True)
    if not path.is_relative_to(root):
        raise QualificationError(f"{label} is outside the conformance run")
    require_hash(path, digest, label)
    return path

def _command(record: dict, root: Path, *, label: str, argv: list[str]) -> None:
    if (record.get("label") != label or [str(item) for item in record.get("argv", [])] != argv
            or canonical(record.get("cwd", ""), must_exist=True) != ROOT
            or type(record.get("returncode")) is not int or record["returncode"] != 0
            or type(record.get("expected_returncode")) is not int or record["expected_returncode"] != 0
            or record.get("timed_out") is not False):
        raise QualificationError(f"{label} command identity mismatch")
    saved_path = _bound_file(record["receipt"], digest_file(canonical(record["receipt"], must_exist=True)), root, f"{label} receipt")
    saved = read_json(saved_path)
    if saved != {key: value for key, value in record.items() if key not in {"receipt", "basetemp"}}:
        raise QualificationError(f"{label} command receipt replay mismatch")
    _bound_file(record["stdout"], record["stdout_sha256"], root, f"{label} stdout")
    _bound_file(record["stderr"], record["stderr_sha256"], root, f"{label} stderr")

def _validate_admission(receipt: dict, request: dict, root: Path) -> None:
    admission = receipt.get("admission") or {}
    python = request["_paths"]["python"]
    _command(
        admission.get("runtime_admission") or {}, root, label="runtime-admission",
        argv=[str(python), "-I", str(ROOT / "scripts/validation/windows_install_smoke.py"), "--probe"],
    )
    from scripts.validation.windows_install_smoke import validate_import_probe
    validate_import_probe(read_json(canonical(admission["runtime_admission"]["stdout"], must_exist=True)), python.parent.parent, ROOT)
    _command(
        admission.get("candidate_pip_check") or {}, root, label="candidate-pip-check",
        argv=[str(python), "-I", "-m", "pip", "check"],
    )

def _validate_junit_inventory(receipt: dict, root: Path) -> None:
    from scripts.validation.windows_qualification_evidence import validate_junit

    required = {"b5", "backpressure", "failure", "recovery"}
    covered = set(receipt.get("covered_keys") or [])
    if B1_KEY in covered:
        required.add("signal")
    if B4_KEY in covered:
        required.add("disconnect")
    junit = receipt.get("junit") or {}
    if set(junit) != required:
        raise QualificationError("native conformance JUnit inventory mismatch")
    for label, row in junit.items():
        path = _bound_file(row["path"], row["sha256"], root, f"{label} JUnit")
        parsed = validate_junit(path)
        if (set(parsed["cases"]) != set(EXPECTED_JUNIT_CASES[label])
                or set(row.get("cases") or []) != set(EXPECTED_JUNIT_CASES[label])
                or parsed["sha256"] != row.get("sha256")):
            raise QualificationError("native conformance JUnit case inventory changed")

def _lane_argv(python: Path, lane: str, junit: dict, command: dict) -> list[str]:
    argv = [str(python), "-I", "scripts/validation/run_report_authoring_tests.py", *LANE_TARGETS[lane]]
    if lane == "backpressure":
        argv += ["-p", "ai_base_runtime.testkit.pytest_plugin", "-p", "ai_host.tests.conformance_fixtures", "-o", "ai_host_modes=blocking_wsgi"]
    return [*argv, *BASE_ARGS, "--basetemp", command["basetemp"], "--junitxml", junit["path"]]

def _validate_lane_commands(receipt: dict, request: dict, root: Path) -> None:
    commands, junit = receipt.get("commands") or {}, receipt.get("junit") or {}
    if set(commands) != set(junit):
        raise QualificationError("native conformance command inventory mismatch")
    for lane, record in commands.items():
        _command(record, root, label=f"native-{lane}", argv=_lane_argv(request["_paths"]["python"], lane, junit[lane], record))

def _event(records: list[dict], name: str) -> dict:
    matches = [row for row in records if row.get("event") == name]
    if len(matches) != 1:
        raise QualificationError(f"native server event missing or duplicated: {name}")
    return matches[0]

def _limits(value: dict) -> None:
    if {key: float(value.get(key)) for key in LIMITS} != LIMITS:
        raise QualificationError("native runtime limits mismatch")

def _process(path: Path, request: dict, trigger: str) -> dict:
    value = read_json(path)
    argv = [str(item) for item in value.get("argv") or []]
    if (not isinstance(value.get("pid"), int) or value["pid"] <= 0
            or not isinstance(value.get("port"), int) or value["port"] <= 0
            or value.get("returncode") != 0 or value.get("forced_cleanup") is not False
            or argv[:2] != [str(request["_paths"]["python"]), "-I"] or argv[-1:] != [trigger]):
        raise QualificationError("native process did not exit cleanly with the expected identity")
    entry = canonical(argv[2], must_exist=True)
    if entry != ROOT / "ai_host/tests/serve_stream_entry.py":
        raise QualificationError("native process entrypoint mismatch")
    if canonical(argv[3], must_exist=True) != path.parent or canonical(argv[5], must_exist=False) != path.parent / "stop":
        raise QualificationError("native process artifact root or stop-file identity mismatch")
    exits = value.get("descendant_exit_codes") or {}
    descendants = value.get("descendants")
    if not isinstance(descendants, list) or set(map(str, exits)) != {str(row.get("pid")) for row in descendants}:
        raise QualificationError("native descendant inventory mismatch")
    require_terminal_exits({str(row["pid"]) for row in descendants}, exits)
    if any(row.get("parent_pid") != value["pid"] for row in descendants):
        raise QualificationError("native descendant process identity mismatch")
    return value

def _server(payload: dict) -> float:
    records = payload.get("server") or []
    ready = _event(records, "stream_host_ready")
    if ready.get("threads") != 14:
        raise QualificationError("native server thread count mismatch")
    started = _event(records, "stream_stop_started")
    stopped = _event(records, "stream_stop_finished")
    http = stopped.get("outcome", {}).get("http_result", {})
    if (stopped.get("outcome", {}).get("exit_code") != 0 or http.get("completed") is not True
            or _num(http.get("elapsed_seconds"), "HTTP close elapsed") > 2
            or http.get("unfinished_stream_ids") or http.get("undelivered_stream_ids") or http.get("error_codes")
            or stopped.get("outcome", {}).get("cleanup_errors")):
        raise QualificationError("native HTTP close or cleanup failed")
    project = _event(records, "project_runtime_stopped")
    if project.get("stopped") is not True or project.get("unresolved") or project.get("active_operation_id") is not None:
        raise QualificationError("native project runtime did not stop cleanly")
    inventory = _event(records, "serve_exit_inventory")
    if inventory.get("threads") or inventory.get("children") or inventory.get("errors"):
        raise QualificationError("native exit inventory is not clean")
    cleanup = _event(records, "serve_exit_cleanup")
    if cleanup.get("errors"):
        raise QualificationError("native exit cleanup is not clean")
    return _num(started["started_at"], "stop started")

def _terminal(observation: dict, *, started_at: float, identity: dict | None = None, backlog: bool = False) -> int:
    events = observation.get("events") or []
    terminals = [row for row in events if row.get("payload", {}).get("type") == "stream.terminated"]
    if not events or len(terminals) != 1 or events[-1] != terminals[0]:
        raise QualificationError("stream terminal event missing or not last")
    terminal_at = _num(observation.get("terminal_at"), "terminal_at")
    eof_at = _num(observation.get("eof_at"), "eof_at")
    event_times = [_num(row.get("at"), "event time") for row in events]
    if event_times != sorted(event_times) or terminal_at != event_times[-1]:
        raise QualificationError("stream event timestamps are not ordered")
    if events[-1]["payload"].get("reason") != "http_closing" or terminal_at > eof_at:
        raise QualificationError("stream terminal/EOF order mismatch")
    if identity is not None:
        states = [row["payload"] for row in events if row.get("payload", {}).get("type") == "chat.state"]
        if not states or any(row.get("sessionId") != identity["sessionId"] or row.get("runId") != identity["runId"] for row in states):
            raise QualificationError("chat stream identity mismatch")
        if states[-1].get("status") != "running":
            raise QualificationError("chat stream did not prove running state before stop")
    if identity is not None and terminal_at - started_at > 2:
        raise QualificationError("chat stream terminal event exceeded native grace")
    if not backlog:
        return 0
    rows = [row["payload"] for row in events if row.get("payload", {}).get("type") == "backlog"]
    if [row.get("index") for row in rows] != list(range(512)):
        raise QualificationError("slow-reader backlog inventory mismatch")
    total = sum(len(row.get("data", "")) for row in rows)
    if total != 512 * 16300:
        raise QualificationError("slow-reader backlog payload size mismatch")
    return total

def _validate_b5(refs: list[dict], request: dict, root: Path) -> dict:
    seen: dict[tuple[str, str, str], tuple[dict, Path]] = {}
    for ref in refs:
        stream = _artifact(ref["streams"], root, "b5 stream")
        process = _artifact(ref["process"], root, "b5 process")
        payload = read_json(stream)
        if process != stream.with_name("process.json"):
            raise QualificationError("native process proof belongs to a different case")
        require_matching_server_log(ref.get("log"), payload, root, stream.parent)
        if payload.get("amendment") != "B5-r1":
            raise QualificationError("B5 amendment identity mismatch")
        key = (payload.get("proof_id"), payload.get("workload", ""), payload.get("trigger"))
        if key in seen:
            if "current" in stream.parent.name:
                continue
            raise QualificationError("duplicate native B5 proof key")
        _process(process, request, key[2])
        seen[key] = (payload, stream)
    chats, slow, never = [], [], []
    for key, (payload, _) in seen.items():
        _limits(payload.get("before", {}).get("limits", {}))
        started_at = _server(payload)
        triggered_at, exited_at = _num(payload.get("triggered_at"), "triggered_at"), _num(payload.get("exited_at"), "exited_at")
        if not triggered_at <= started_at <= exited_at or exited_at - triggered_at > 10:
            raise QualificationError("native stream host exceeded normal stop budget")
        if key[0] == "B5-chat" and key[1] == "":
            identities, observations = payload.get("identities") or [], payload.get("observations") or []
            if len(identities) != 2 or len(observations) != 2:
                raise QualificationError("B5-chat proof did not include two public chat streams")
            for identity, observation in zip(identities, observations, strict=True):
                _terminal(observation, started_at=started_at, identity=identity)
            chats.append(key[2])
        elif key[0] == "B5-transport" and key[1] == "slow":
            before, observations = payload["before"], payload.get("observations") or []
            # The fixed workload is unread across Waitress and TCP buffers;
            # Waitress alone need not retain all approximately 8 MiB.
            if len(observations) != 3 or _num(before.get("pending_bytes"), "pending_bytes") <= 1_048_576:
                raise QualificationError("B5 slow-reader proof lacks backlog pressure")
            if before.get("counts", {}).get("backlog_blocks") != 512 or _num(payload.get("resumed_at"), "resumed_at") - triggered_at < 3:
                raise QualificationError("B5 slow-reader pause/backlog count mismatch")
            for observation in observations[:2]:
                if _num(observation.get("terminal_at"), "terminal_at") - started_at > 2:
                    raise QualificationError("active/idle stream terminal exceeded native grace")
                _terminal(observation, started_at=started_at)
            _terminal(observations[2], started_at=started_at, backlog=True)
            slow.append(key[2])
        elif key[0] == "B5-transport" and key[1] == "never-read":
            before = payload["before"]
            flush = _event(payload["server"], "stream_flush_finished")
            if (payload.get("observations") or _num(before.get("pending_bytes"), "pending_bytes") <= 1_048_576
                    or before.get("counts", {}).get("backlog_blocks") != 512
                    or _num(flush.get("pending_bytes"), "flush pending_bytes") <= 0):
                raise QualificationError("B5 never-reader proof lacks retained flush backlog")
            never.append(key[2])
    if chats != TRIGGERS or slow != TRIGGERS or never != NATIVE_BREAKS:
        raise QualificationError("B5 trigger matrix is incomplete")
    return {"chat_triggers": chats, "transport_slow_triggers": slow, "transport_never_read_triggers": never}

def _validate_backpressure(ref: dict, root: Path) -> dict:
    payload = read_json(_artifact(ref, root, "backpressure"))
    if (payload.get("paused_producer_blocks") != 16 or payload.get("block_bytes") != 65532
            or payload.get("after_consumption_blocks", 0) <= 16
            or payload.get("consumed_bytes", 0) < 20 * 65532
            or payload.get("stream_in_flight_after_close") != 0
            or payload.get("host_in_flight_after_close") != 0
            or payload.get("generator_closed") is not True):
        raise QualificationError("producer queue backpressure proof is invalid")
    return payload

def _validate_disconnect(ref: dict, root: Path, request: dict) -> dict:
    path = _artifact(ref, root, "disconnect")
    payload = read_json(path)
    require_matching_server_log(ref.get("log"), payload, root, path.parent)
    baseline = payload.get("baseline", {}).get("probe", {})
    _limits(baseline.get("limits", {}))
    if payload.get("repeat") != 20 or payload.get("proof_id") != "W2.HOST.native_disconnect":
        raise QualificationError("disconnect proof identity mismatch")
    cycles = payload.get("cycles") or []
    if len(cycles) != 20 or [row.get("index") for row in cycles] != list(range(20)):
        raise QualificationError("disconnect cycle inventory mismatch")
    base_tasks, base_threads = baseline.get("tasks"), baseline.get("threads")
    for cycle in cycles:
        if cycle.get("active", {}).get("probe", {}).get("counts", {}).get("streams") != 1:
            raise QualificationError("disconnect cycle never became active")
        after = cycle.get("after", {})
        elapsed = _num(cycle.get("reclaimed_at"), "reclaimed_at") - _num(cycle.get("closed_at"), "closed_at")
        if (abs(elapsed - _num(cycle.get("elapsed"), "elapsed")) > 0.01 or elapsed > LIMITS["heartbeat"] + 1
                or after.get("probe", {}).get("counts", {}).get("streams") != 0
                or after.get("probe", {}).get("tasks") != base_tasks
                or after.get("probe", {}).get("threads") != base_threads
                or after.get("probe", {}).get("pending_bytes") != 0
                or after.get("diagnostics", {}).get("streamInFlightCount") != 0):
            raise QualificationError("disconnect resources were not reclaimed")
    final = payload.get("final", {})
    if (final.get("probe", {}).get("counts", {}).get("streams_done") != 20
            or final.get("probe", {}).get("tasks") != base_tasks
            or final.get("probe", {}).get("threads") != base_threads
            or final.get("diagnostics", {}).get("streamInFlightCount") != 0):
        raise QualificationError("disconnect final diagnostics mismatch")
    _server(payload)
    process_path = _artifact(ref["process"], root, "disconnect process")
    if process_path != path.with_name("process.json"):
        raise QualificationError("disconnect process proof belongs to a different case")
    if payload.get("process") != _process(process_path, request, "stop-file"):
        raise QualificationError("disconnect process observation disagrees")
    return {"repeat": 20}

def _validate_signals(refs: list[dict], root: Path) -> dict:
    matrix = set()
    for ref in refs:
        path = _artifact(ref, root, "signal")
        payload = read_json(path)
        text, records = server_log(ref.get("log"), root, path.parent)
        trigger, phase = payload.get("trigger"), payload.get("phase")
        expected = 0 if phase == "normal" else 130
        bound = 10 if phase == "normal" else 1
        if (trigger not in TRIGGERS or payload.get("returncode") != expected
                or _num(payload.get("elapsed"), "signal elapsed") > bound or payload.get("forced_cleanup") is not False):
            raise QualificationError("native signal proof mismatch")
        validate_descendant_exits(payload)
        if (trigger, phase) in matrix:
            raise QualificationError("duplicate native signal proof")
        if phase == "normal":
            project = _event(records, "project_runtime_stopped")
            inventory = _event(records, "serve_exit_inventory")
            cleanup = _event(records, "serve_exit_cleanup")
            if (project.get("stopped") is not True or project.get("unresolved")
                    or inventory.get("threads") or inventory.get("children") or inventory.get("errors")
                    or cleanup.get("errors") or "serve stopped." not in text):
                raise QualificationError("native normal signal log is not clean")
        elif "serve forced exit." not in text or not payload.get("event", {}).get("sent"):
            raise QualificationError("native second control-event proof is missing")
        matrix.add((trigger, phase))
    expected = {(trigger, "normal") for trigger in TRIGGERS}
    expected |= {(trigger, phase) for trigger in TRIGGERS for phase in ("drain", "flush")}
    expected.add(("stop-file", "final"))
    if matrix != expected:
        raise QualificationError("native signal matrix is incomplete")
    return {"cases": len(matrix)}

def validate_result(receipt: dict, request: dict) -> dict:
    root = canonical(receipt["run_root"])
    if root.parent != request["_paths"]["owned_root"] / "conformance-runs" or str(UUID(root.name)) != root.name:
        raise QualificationError("conformance run root mismatch")
    if (receipt.get("kind") != KIND or receipt.get("phase") != "conformance" or receipt.get("status") != "PASS"
            or type(receipt.get("schema_version")) is not int or receipt["schema_version"] != 1
            or receipt.get("scope") != "windows-functional-native"):
        raise QualificationError("native conformance receipt scope mismatch")
    inputs_ref = receipt.get("inputs") or {}
    if canonical(inputs_ref.get("path", ""), must_exist=True) != request["_paths"]["inputs"]:
        raise QualificationError("native conformance input reference mismatch")
    require_hash(request["_paths"]["inputs"], inputs_ref.get("sha256", ""), "native conformance inputs")
    validate_frozen_hashes(ROOT.resolve(), request["source"], request["fixtures"], (ROOT.resolve(), request["_paths"]["owned_root"]))
    if receipt.get("source_before") != {"commit": request["source"]["commit"], "status": ""}:
        raise QualificationError("native conformance source-before mismatch")
    if receipt.get("source_after") != {"commit": request["source"]["commit"], "status": ""}:
        raise QualificationError("native conformance source-after mismatch")
    if receipt.get("candidate") != {"version": request["candidate"]["version"], "wheel_sha256": request["candidate"]["wheel_sha256"]}:
        raise QualificationError("native conformance candidate mismatch")
    if receipt.get("fixture_vector_sha256") != request["fixtures"]["fixture_vector_sha256"]:
        raise QualificationError("native conformance fixture mismatch")
    amendment = request.get("native_conformance", {}).get("amendment") or {}
    amendment_path = canonical(amendment.get("path", ""), must_exist=True)
    require_hash(amendment_path, amendment.get("sha256", ""), "B5 amendment")
    if receipt.get("amendment") != amendment:
        raise QualificationError("native conformance amendment binding mismatch")
    covered = receipt.get("covered_keys") or []
    if not covered or set(covered) - NATIVE_KEYS or B5_KEY not in covered:
        raise QualificationError("native conformance covered keys are unsupported or incomplete")
    if any(row.get("counted") is not False or row.get("status") != "NOT_APPLICABLE" for row in receipt.get("non_applicable", [])):
        raise QualificationError("native non-applicable rows must not be counted")
    from scripts.validation import windows_host_conformance_environment as environment
    environments = receipt.get("environments", {})
    if set(environments) != {"before", "after"}:
        raise QualificationError("native before/after environment proof is incomplete")
    for reference in environments.values():
        environment.validate(reference, request, root, command_check=_command)
    _validate_admission(receipt, request, root)
    _validate_junit_inventory(receipt, root)
    _validate_lane_commands(receipt, request, root)
    artifacts, result = receipt.get("artifacts") or {}, {}
    result["b5"] = _validate_b5(artifacts.get("b5") or [], request, root)
    result["backpressure"] = _validate_backpressure(artifacts.get("backpressure") or {}, root)
    if B4_KEY in covered:
        result["disconnect"] = _validate_disconnect(artifacts.get("disconnect") or {}, root, request)
    if B1_KEY in covered:
        result["signals"] = _validate_signals(artifacts.get("signals") or [], root)
    return {"kind": KIND, "scope": "windows-functional-native", "sha256": digest_file(canonical(receipt["self"])) if "self" in receipt else None, "covered_keys": covered, **result}

def validate_bound_receipt(key: str, path: Path, request: dict) -> dict:
    receipt = read_json(path)
    receipt = {**receipt, "self": str(path)}
    result = validate_result(receipt, request)
    if key not in result["covered_keys"]:
        raise QualificationError(f"native conformance receipt cannot cover {key}")
    return {"kind": KIND, "scope": result["scope"], "sha256": digest_file(path), "mapped_keys": [key]}

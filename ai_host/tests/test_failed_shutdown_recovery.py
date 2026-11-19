import json
from contextlib import ExitStack
from http.client import HTTPConnection, HTTPException
from pathlib import Path
import subprocess
import sys
import time

import pytest
from ai_base_runtime.testkit import scripted_model_endpoint
from ai_base_runtime.testkit.host_support._domain_assertions import _response

from ai_host.exit_processes import living_children
from ai_host.tests.conformance_recovery_cases import ApprovalRequest
from ai_host.tests.failed_shutdown_observations import read_observation
from ai_host.tests.test_serve_native_failure import (
    assert_listener_released,
    event_named,
    free_port,
    json_events,
)
from scripts.service_lifecycle_engine import platform_ops
from scripts.service_lifecycle_engine.process_exit import observe_process_exit


ROOT = Path(__file__).resolve().parents[2]
ENTRY = ROOT / "ai_host/tests/failed_shutdown_recovery_entry.py"


def responses():
    return [_response('{"answer":"task-complete"}'), ApprovalRequest(), _response("approved-complete")]


def request_json(port, path="/ai/api/apps"):
    connection = HTTPConnection("127.0.0.1", port, timeout=3)
    try:
        connection.request("GET", path, headers={"Connection": "close"})
        response = connection.getresponse()
        body = response.read()
        assert response.status == 200, (response.status, body)
        return json.loads(body)
    finally:
        connection.close()


def wait_ready(process, port, log_path):
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        assert process.poll() is None, log_path.read_text(encoding="utf-8", errors="replace")
        try:
            request_json(port)
            return
        except (OSError, HTTPException, TimeoutError, AssertionError):
            time.sleep(0.05)
    raise AssertionError("native failed-shutdown host did not become ready")


def wait_observation(path, process, log_path, predicate):
    deadline = time.monotonic() + 40
    latest = {}
    while time.monotonic() < deadline:
        if path.exists():
            try:
                latest = read_observation(path)
            except (FileNotFoundError, json.JSONDecodeError):
                latest = {}
            if predicate(latest) and process.poll() is None:
                return latest
        assert process.poll() is None, log_path.read_text(encoding="utf-8", errors="replace")
        time.sleep(0.05)
    raise AssertionError(f"observation did not satisfy predicate: {latest}")


def owned_descendants(pid):
    inventory = living_children(root_pid=pid)
    family = {pid}
    changed = True
    while changed:
        changed = False
        for row in inventory:
            if row["parent_pid"] in family and row["pid"] not in family:
                family.add(row["pid"])
                changed = True
    return [row for row in inventory if row["pid"] in family and row["pid"] != pid]


def start_child(root, mode, endpoint):
    root.mkdir(parents=True, exist_ok=True)
    port = free_port()
    stop = root / f"{mode}.stop"
    observation = root / f"{mode}.observations"
    log_path = root / f"{mode}.log"
    command = [
        sys.executable, "-I", str(ENTRY), str(root), str(port), str(stop), mode, str(observation), endpoint,
    ]
    log = log_path.open("wb")
    process = subprocess.Popen(
        command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    return {
        "command": command, "process": process, "log": log, "log_path": log_path,
        "observation": observation, "port": port, "stop": stop,
    }


def finish_child(child, expected_code, *, stop=True, wait_timeout=15, check=True, raise_wait_error=True):
    process, log, stop_file = child["process"], child["log"], child["stop"]
    forced = False
    cleanup_uncertain = False
    cleanup_errors = []
    inventory_error = None
    wait_error = None
    descendants = []
    if process.poll() is None:
        try:
            descendants = owned_descendants(process.pid)
        except Exception as error:
            cleanup_uncertain = True
            cleanup_errors.append(f"descendant_inventory_failed:{type(error).__name__}")
            inventory_error = {
                "type": type(error).__name__, "winerror": getattr(error, "winerror", None),
                "notes": getattr(error, "__notes__", []),
            }
    with ExitStack() as stack:
        observers = {row["pid"]: stack.enter_context(observe_process_exit(row["pid"])) for row in descendants}
        try:
            if stop:
                stop_file.touch()
            try:
                process.wait(timeout=wait_timeout)
            except subprocess.TimeoutExpired as error:
                wait_error = error
        finally:
            if process.poll() is None:
                stop_file.touch()
                try:
                    process.wait(timeout=12)
                except subprocess.TimeoutExpired:
                    forced = True
                    platform_ops.kill_process(process.pid)
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        cleanup_uncertain = True
                        cleanup_errors.append("wrapper_kill_timeout")
            for pid, observer in observers.items():
                if observer.wait is None:
                    cleanup_uncertain = True
                    cleanup_errors.append(f"descendant_unobservable:{pid}")
                    continue
                if observer.wait(2):
                    continue
                forced = True
                platform_ops.kill_process(pid)
                if not observer.wait(3):
                    cleanup_uncertain = True
                    cleanup_errors.append(f"descendant_kill_timeout:{pid}")
            log.close()
        descendant_exit_codes = {pid: observer() for pid, observer in observers.items()}
        info = {
            "argv": child["command"], "pid": process.pid, "port": child["port"],
            "returncode": process.returncode, "expected_code": expected_code,
            "wait_error": None if wait_error is None else type(wait_error).__name__,
            "forced_cleanup": forced, "cleanup_uncertain": cleanup_uncertain,
            "cleanup_errors": cleanup_errors, "descendants": descendants,
            "inventory_error": inventory_error,
            "descendant_exit_codes": descendant_exit_codes,
        }
        (Path(child["log_path"]).parent / f"{Path(child['log_path']).stem}-process.json").write_text(
            json.dumps(info, indent=2, sort_keys=True), encoding="utf-8",
        )
    if wait_error is not None and raise_wait_error:
        raise wait_error
    if not check:
        return info
    assert process.returncode == expected_code, child["log_path"].read_text(encoding="utf-8", errors="replace")
    assert not forced
    assert not cleanup_uncertain, info
    assert not cleanup_errors, info
    assert_listener_released(child["port"])
    return info


def run_ready_then_stop(root, mode, endpoint, expected_code):
    child = start_child(root, mode, endpoint)
    finish_started = False
    try:
        wait_ready(child["process"], child["port"], child["log_path"])
        wait_observation(
            child["observation"], child["process"], child["log_path"],
            lambda value: value.get("ready_for_stop") is True,
        )
        finish_started = True
        process_info = finish_child(child, expected_code)
    except BaseException:
        if not finish_started:
            finish_child(child, expected_code, check=False, raise_wait_error=False)
        raise
    observation = read_observation(child["observation"])
    output = child["log_path"].read_text(encoding="utf-8", errors="replace")
    return {"observation": observation, "output": output, "events": json_events(output), "process": process_info}


def run_expected_failure(root, mode, endpoint):
    child = start_child(root, mode, endpoint)
    finish_started = False
    try:
        finish_started = True
        process_info = finish_child(child, 1, stop=False, wait_timeout=20)
    except BaseException:
        if not finish_started:
            finish_child(child, 1, stop=False, check=False, raise_wait_error=False)
        raise
    output = child["log_path"].read_text(encoding="utf-8", errors="replace")
    observation = {}
    if child["observation"].exists():
        observation = read_observation(child["observation"])
    return {"observation": observation, "output": output, "events": json_events(output), "process": process_info}

def test_finish_child_records_descendants_and_receipt_when_initial_wait_times_out(tmp_path):
    stop, ready = tmp_path / "stop", tmp_path / "ready"
    descendant_ready, log_path = tmp_path / "descendant-ready", tmp_path / "timeout-child.log"
    port = free_port()
    descendant_code = (
        "import pathlib,sys,time\nstop=pathlib.Path(sys.argv[1])\n"
        "pathlib.Path(sys.argv[2]).write_text('ready', encoding='utf-8')\n"
        "while not stop.exists(): time.sleep(0.01)\n"
    )
    child_code = (
        "import pathlib,subprocess,sys,time\n"
        "stop=pathlib.Path(sys.argv[1]); ready=pathlib.Path(sys.argv[2]); child_ready=pathlib.Path(sys.argv[3])\n"
        "child=subprocess.Popen([sys.executable, '-I', '-c', sys.argv[4], str(stop), str(child_ready)])\n"
        "while not child_ready.exists(): time.sleep(0.01)\n"
        "ready.write_text('ready', encoding='utf-8')\n"
        "while not stop.exists(): time.sleep(0.01)\n"
        "child.wait(timeout=5)\n"
    )
    command = [sys.executable, "-I", "-c", child_code, str(stop), str(ready), str(descendant_ready), descendant_code]
    log = log_path.open("wb")
    process = subprocess.Popen(
        command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    child = {
        "command": command, "process": process, "log": log, "log_path": log_path,
        "observation": tmp_path / "unused.json", "port": port, "stop": stop}
    deadline = time.monotonic() + 5
    while not ready.exists():
        assert process.poll() is None, log_path.read_text(encoding="utf-8", errors="replace")
        assert time.monotonic() < deadline
        time.sleep(0.01)
    with pytest.raises(subprocess.TimeoutExpired):
        finish_child(child, 0, stop=False, wait_timeout=0.01)
    receipt = json.loads((tmp_path / "timeout-child-process.json").read_text(encoding="utf-8"))
    assert receipt["wait_error"] == "TimeoutExpired"
    assert receipt["returncode"] == 0 and receipt["forced_cleanup"] is False
    assert receipt["cleanup_uncertain"] is False
    assert receipt["descendants"]
    assert all(code == 0 for code in receipt["descendant_exit_codes"].values())

def test_native_failed_shutdown_reopens_completed_public_state_without_duplicate_effects(tmp_path):
    with scripted_model_endpoint(responses()) as clean_model:
        clean = run_ready_then_stop(tmp_path / "clean-control", "write-clean-control", clean_model.model.base_url, 0)
        clean_stop = clean["observation"]["stop"]["stop_result"]
        assert clean_stop["completed"] is True
        assert clean_stop["persistent_state_flushed"] is True
        assert "serve cleanup failed." not in clean["output"]
        assert len(clean_model.requests) == 3

    root = tmp_path / "failed-stop"
    with scripted_model_endpoint(responses()) as model:
        failed = run_ready_then_stop(root, "write-failed", model.model.base_url, 3)
        failed_observation = failed["observation"]
        assert failed_observation["fault"]["entered"] is True
        assert failed_observation["fault"]["future_done"] is False
        assert failed_observation["fault"]["pending_work_count"] >= 1
        assert failed_observation["store_close"]["entered"] is True
        assert failed_observation["store_close"]["pending_at_enter"] >= 1
        assert failed_observation["store_close"]["returned"] is True
        assert failed_observation["store_close"]["result"] is False
        stop_result = failed_observation["stop"]["stop_result"]
        assert stop_result["completed"] is False
        assert stop_result["timed_out"] is True
        assert stop_result["persistent_state_flushed"] is False
        assert stop_result["unclosed_resources"]
        assert "runtime_stop_incomplete" in failed_observation["stop"]["result"]["cleanup_errors"]
        assert "stop_timeout" in stop_result["error_codes"]
        assert "serve cleanup failed." in failed["output"]
        inventory = event_named(failed["events"], "serve_exit_inventory")
        assert inventory["children"] == []
        assert "Traceback (most recent call last)" not in failed["output"]
        assert len(model.requests) == 3

        read = run_ready_then_stop(root, "read-normal", model.model.base_url, 0)
        readback = read["observation"]["readback"]
        assert readback["reacquired_runtime"] is True
        assert readback["state_lock_present"] is True
        assert readback["new_effects"] == 0
        assert readback["new_resolves"] == 0
        reopened_stop = read["observation"]["stop"]["stop_result"]
        assert reopened_stop["completed"] is True
        assert reopened_stop["persistent_state_flushed"] is True
        assert len(model.requests) == 3
        assert model.remaining == 0

        mutated = run_expected_failure(root, "read-mutated-identity", model.model.base_url)
        assert mutated["observation"]["mutation"]["kind"] == "task_identity"
        assert len(model.requests) == 3

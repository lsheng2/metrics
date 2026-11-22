import json
from http.client import HTTPException
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

import pytest


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_RUNTIME_VERSION = "0.1.1.dev7"


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def wait_ready(process, port, log):
    opener = build_opener(ProxyHandler({}))
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        assert process.poll() is None, log.read_text(encoding="utf-8", errors="replace")
        try:
            with opener.open(f"http://127.0.0.1:{port}/ai/", timeout=1) as response:
                assert response.status == 200
                return
        except (URLError, TimeoutError, HTTPException):
            time.sleep(0.05)
    pytest.fail("owned native fault host did not become ready")


def native_child(root, mode):
    port = free_port()
    stop, trigger = root / f"{mode}.stop", root / f"{mode}.trigger"
    observation = root / f"{mode}.json"
    log_path = root / f"{mode}.log"
    log = log_path.open("wb")
    process = subprocess.Popen(
        [
            sys.executable, "-I", str(ROOT / "ai_host/tests/serve_failure_entry.py"),
            str(root), str(port), str(stop), mode, str(observation), str(trigger),
        ],
        cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return process, log, log_path, observation, port, stop, trigger


def reap(process, log, stop):
    if process.poll() is None:
        stop.touch()
        try:
            process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
            pytest.fail("native fault required emergency test cleanup")
    log.close()


def assert_listener_released(port):
    with socket.socket() as probe:
        probe.settimeout(1)
        assert probe.connect_ex(("127.0.0.1", port)) != 0


def assert_state_can_be_reopened(root):
    process, log, log_path, _, port, stop, _ = native_child(root, "normal")
    try:
        wait_ready(process, port, log_path)
        stop.touch()
        assert process.wait(timeout=12) == 0, log_path.read_text(encoding="utf-8", errors="replace")
    finally:
        reap(process, log, stop)
    assert_listener_released(port)


def json_events(output):
    decoder = json.JSONDecoder()
    events = []
    index = 0
    while True:
        start = output.find("{", index)
        if start == -1:
            return events
        try:
            value, consumed = decoder.raw_decode(output[start:])
        except json.JSONDecodeError:
            index = start + 1
            continue
        events.append(value)
        index = start + consumed


def event_named(events, name):
    matches = [event for event in events if event.get("event") == name]
    assert len(matches) == 1, events
    return matches[0]


def test_real_serve_observes_ended_runtime_and_exits_one(tmp_path):
    process, log, log_path, observation, port, stop, trigger = native_child(tmp_path, "ended")
    try:
        wait_ready(process, port, log_path)
        trigger.touch()
        code = process.wait(timeout=12)
        exited_at = time.monotonic()
        assert code == 1, log_path.read_text(encoding="utf-8", errors="replace")
    finally:
        reap(process, log, stop)
    evidence = json.loads(observation.read_text(encoding="utf-8"))
    assert evidence["ended"] is True
    assert evidence["stop_result"]["completed"] is True
    assert exited_at - evidence["ended_at"] <= 1.0
    output = log_path.read_text(encoding="utf-8")
    assert f'serve runtime failed ({evidence["end_code"]}).' in output
    assert "serve cleanup failed." not in output
    assert_listener_released(port)
    assert_state_can_be_reopened(tmp_path)


def test_real_serve_observes_internal_loop_fault_without_public_stop_and_releases_resources(tmp_path):
    process, log, log_path, observation, port, stop, trigger = native_child(tmp_path, "loop-fault")
    try:
        wait_ready(process, port, log_path)
        trigger.touch()
        code = process.wait(timeout=12)
        output = log_path.read_text(encoding="utf-8", errors="replace")
        assert code == 1, output
    finally:
        reap(process, log, stop)
    evidence = json.loads(observation.read_text(encoding="utf-8"))
    assert evidence["runtime_version"] == EXPECTED_RUNTIME_VERSION
    assert evidence["fault_thread"].startswith("ai-runtime-loop-")
    assert evidence["ended"] is True
    assert evidence["end_code"] == "runtime_failed"
    assert evidence["observed_at"] - evidence["ended_at"] <= 1.0
    assert evidence["stop_calls"]
    assert all(call["ended_before_call"] is True for call in evidence["stop_calls"])
    assert evidence["stop_result"]["completed"] is True
    assert evidence["stop_result"]["persistent_state_flushed"] is True
    assert evidence["stop_result"]["unfinished_run_ids"] == []
    assert evidence["stop_result"]["unclosed_resources"] == []
    assert evidence["stop_result"]["error_codes"] == []
    assert evidence["result_exit_code"] == 0
    assert evidence["result_cleanup_errors"] == []

    output = log_path.read_text(encoding="utf-8")
    assert f'serve runtime failed ({evidence["end_code"]}).' in output
    assert "serve cleanup failed." not in output
    assert "Traceback (most recent call last)" not in output
    assert "synthetic-only-token" not in output
    assert "METRICS_JIRA_API_TOKEN" not in output
    events = json_events(output)
    inventory = event_named(events, "serve_exit_inventory")
    cleanup = event_named(events, "serve_exit_cleanup")
    assert inventory["threads"] == []
    assert inventory["children"] == []
    assert inventory["errors"] == []
    assert cleanup["errors"] == []
    assert_listener_released(port)
    assert_state_can_be_reopened(tmp_path)


@pytest.mark.parametrize("mode, expected_code, completed", [
    ("timeout-clean", 1, True), ("timeout-stuck", 3, False),
])
def test_real_start_timeout_reports_rollback_and_releases_lock_after_exit(tmp_path, mode, expected_code, completed):
    process, log, log_path, observation, port, stop, _ = native_child(tmp_path, mode)
    try:
        assert process.wait(timeout=40) == expected_code, log_path.read_text(encoding="utf-8", errors="replace")
    finally:
        reap(process, log, stop)
    evidence = json.loads(observation.read_text(encoding="utf-8"))
    assert evidence["injection"]["lock_owned"] is True
    assert evidence["injection"]["thread"].startswith("ai-runtime-loop-")
    assert evidence["failure"]["reason_code"] == "start_timeout"
    assert evidence["failure"]["rollback_result"]["completed"] is completed
    assert evidence["failure"]["state_lock_released"] is completed
    assert evidence["failure"]["loop_thread_joined"] is completed
    assert evidence["loop_alive"] is not completed
    assert evidence["elapsed"] <= 4.0
    output = log_path.read_text(encoding="utf-8")
    assert "serve startup failed (start_timeout)." in output
    assert ("serve cleanup failed." in output) is not completed
    assert "Traceback (most recent call last)" not in output
    assert_listener_released(port)
    assert_state_can_be_reopened(tmp_path)

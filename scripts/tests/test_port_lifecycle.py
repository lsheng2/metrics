from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import port_lifecycle.port_lifecycle as lifecycle_module
from port_lifecycle import PortLifecycle, ServiceSpec, is_port_available, load_project_name, load_service_specs, process_exists
from port_lifecycle.platform_ops import creation_flags, kill_process, wait_process_exit


def test_resolve_port_skips_occupied_port(tmp_path):
    lifecycle = PortLifecycle("test-project", tmp_path, state_directory=tmp_path / "state")
    occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    occupied.bind(("127.0.0.1", 0))
    occupied.listen(1)
    occupied_port = occupied.getsockname()[1]
    free_port = find_free_port()

    try:
        spec = ServiceSpec.from_values("web", [occupied_port, free_port], [sys.executable, "--version"])
        assert lifecycle.resolve_port(spec) == free_port
    finally:
        occupied.close()


def test_resolve_plan_does_not_assign_same_available_port_twice(tmp_path):
    lifecycle = PortLifecycle("test-project", tmp_path, state_directory=tmp_path / "state")
    shared_port = find_free_port()
    fallback_port = find_free_port()
    api_spec = ServiceSpec.from_values("api", [shared_port], [sys.executable, "--version"])
    ui_spec = ServiceSpec.from_values("ui", [shared_port, fallback_port], [sys.executable, "--version"])

    plan = lifecycle.resolve_plan((api_spec, ui_spec))

    assert plan == {"api": shared_port, "ui": fallback_port}


def test_wait_ready_rejects_dead_child_even_when_health_url_responds(tmp_path):
    lifecycle = PortLifecycle("test-project", tmp_path, state_directory=tmp_path / "state")
    port = find_free_port()
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=tmp_path,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags(),
    )

    class DeadProcess:
        def poll(self):
            return 1

    try:
        wait_until_listening(port)
        spec = http_server_spec(tmp_path, [port])
        try:
            lifecycle.wait_ready(spec, port, DeadProcess())
        except RuntimeError as error:
            assert "exited before becoming ready" in str(error)
        else:
            raise AssertionError("dead launched process was treated as ready")
    finally:
        if process_exists(server.pid):
            kill_process(server.pid)
            wait_process_exit(server.pid, 2.0)


def test_start_and_stop_service(tmp_path):
    lifecycle = PortLifecycle("test-project", tmp_path, state_directory=tmp_path / "state")
    port = find_free_port()
    spec = http_server_spec(tmp_path, [port])

    state = lifecycle.start_service(spec, port=port)
    assert state.port == port
    assert not is_port_available("127.0.0.1", port)

    result = lifecycle.stop_service("web", graceful_timeout_seconds=0.1)
    assert result.stopped
    assert not process_exists(state.pid)
    assert lifecycle.termination_ledger.exists()
    ledger_record = json.loads(lifecycle.termination_ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert ledger_record["service"] == "web"
    assert ledger_record["port"] == port


def test_start_service_stops_existing_same_service_before_new_port(tmp_path):
    lifecycle = PortLifecycle("test-project", tmp_path, state_directory=tmp_path / "state")
    old_port = find_free_port()
    new_port = find_free_port()
    spec = http_server_spec(tmp_path, [old_port, new_port])

    old_state = lifecycle.start_service(spec, port=old_port)
    try:
        new_state = lifecycle.start_service(spec, port=new_port)
        assert not process_exists(old_state.pid)
        assert new_state.port == new_port
        assert lifecycle.read_state()["web"]["pid"] == new_state.pid
    finally:
        lifecycle.stop_service("web", graceful_timeout_seconds=0.1)


def test_stop_all_recovers_from_pid_file_when_state_is_missing(tmp_path):
    lifecycle = PortLifecycle("test-project", tmp_path, state_directory=tmp_path / "state")
    port = find_free_port()
    spec = http_server_spec(tmp_path, [port])

    state = lifecycle.start_service(spec, port=port)
    lifecycle.state_file.unlink()

    results = lifecycle.stop_all(graceful_timeout_seconds=0.1)
    assert any(result.pid == state.pid and result.stopped for result in results)
    assert not process_exists(state.pid)
    ledger_records = [json.loads(line) for line in lifecycle.termination_ledger.read_text(encoding="utf-8").splitlines()]
    assert any(record["pid"] == state.pid and record["reason"].startswith("pid_file_recovery:") for record in ledger_records)


def test_stop_all_skips_legacy_pid_file_without_command_identity(monkeypatch, tmp_path):
    lifecycle = PortLifecycle("test-project", tmp_path, state_directory=tmp_path / "state")
    pid_file = lifecycle._pid_file("web", 12345)
    pid_file.write_text(json.dumps({"name": "web", "port": 12345, "pid": 999999}), encoding="utf-8")
    killed = False

    def fake_kill(pid):
        nonlocal killed
        killed = True

    monkeypatch.setattr(lifecycle_module, "process_exists", lambda pid: True)
    monkeypatch.setattr(lifecycle_module, "kill_process", fake_kill)

    results = lifecycle.stop_all(graceful_timeout_seconds=0.1)

    assert len(results) == 1
    assert results[0].reason == "pid_file_recovery:missing_identity"
    assert not killed
    assert pid_file.exists()
    ledger_record = json.loads(lifecycle.termination_ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert ledger_record["reason"] == "pid_file_recovery:missing_identity"


def test_start_service_writes_launch_authority(tmp_path):
    lifecycle = PortLifecycle("test-project", tmp_path, instance_name="instance-a", state_directory=tmp_path / "state")
    port = find_free_port()
    spec = http_server_spec(tmp_path, [port], listener_identity_url="http://{host}:{port}/")

    state = lifecycle.start_service(spec, port=port)
    try:
        assert Path(state.launch_authority_file).name == "test-project-instance-a-web.json"
        authority = json.loads(Path(state.launch_authority_file).read_text(encoding="utf-8"))
        assert authority["service"] == "web"
        assert authority["port"] == port
        assert authority["health_reachable"] is True
        assert authority["listener_identity_probe"]["reachable"] is True
        assert state.listener_identity_fingerprint
    finally:
        lifecycle.stop_service("web", graceful_timeout_seconds=0.1)


def test_launch_authority_is_scoped_by_instance(tmp_path):
    lifecycle_a = PortLifecycle("test-project", tmp_path, instance_name="instance-a", state_directory=tmp_path / "state")
    lifecycle_b = PortLifecycle("test-project", tmp_path, instance_name="instance-b", state_directory=tmp_path / "state")

    assert lifecycle_a._authority_file("web") != lifecycle_b._authority_file("web")


def test_check_services_calls_watchdog_callback_for_missing_pid(tmp_path):
    lifecycle = PortLifecycle("test-project", tmp_path, state_directory=tmp_path / "state")
    lifecycle.write_state({"api": {"port": 12345, "pid": 999999, "health_url": "", "listener_identity_url": ""}})
    events = []

    result = lifecycle.check_services(callback=events.append)

    assert result == events
    assert events[0]["kind"] == "pid_missing"
    assert events[0]["service"] == "api"


def test_check_services_detects_listener_identity_change(tmp_path):
    lifecycle = PortLifecycle("test-project", tmp_path, state_directory=tmp_path / "state")
    port = find_free_port()
    spec = http_server_spec(tmp_path, [port], listener_identity_url="http://{host}:{port}/")

    lifecycle.start_service(spec, port=port)
    try:
        state = lifecycle.read_state()
        state["web"]["listener_identity_fingerprint"] = "not-the-current-fingerprint"
        lifecycle.write_state(state)

        events = lifecycle.check_services()

        assert any(event["kind"] == "listener_identity_changed" for event in events)
    finally:
        lifecycle.stop_service("web", graceful_timeout_seconds=0.1)


def test_state_roundtrip(tmp_path):
    lifecycle = PortLifecycle("test-project", tmp_path, instance_name="instance-a", state_directory=tmp_path / "state")
    lifecycle.write_state({"api": {"port": 12345, "pid": 999999}})

    state = lifecycle.read_state()
    assert state["api"]["port"] == 12345
    assert lifecycle.state_file.name == "test-project-instance-a.json"


def test_force_stop_by_ports_uses_project_supplied_resolver(tmp_path):
    lifecycle = PortLifecycle("test-project", tmp_path, state_directory=tmp_path / "state")
    port = find_free_port()
    process = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=tmp_path,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags(),
    )
    try:
        wait_until_listening(port)
        spec = ServiceSpec.from_values("web", [port], [])
        results = lifecycle.force_stop_by_ports((spec,), port_process_resolver=lambda host, candidate: [process.pid])

        assert len(results) == 1
        assert results[0].stopped
        assert results[0].reason.startswith("force_by_port:")
        assert not process_exists(process.pid)
    finally:
        if process_exists(process.pid):
            kill_process(process.pid)
            wait_process_exit(process.pid, 2.0)


def test_prepare_startup_stops_owned_services(tmp_path):
    lifecycle = PortLifecycle("test-project", tmp_path, state_directory=tmp_path / "state")
    port = find_free_port()
    spec = http_server_spec(tmp_path, [port])

    state = lifecycle.start_service(spec, port=port)

    results = lifecycle.prepare_startup((spec,), graceful_timeout_seconds=0.1)

    assert any(result.pid == state.pid and result.stopped for result in results)
    assert not process_exists(state.pid)


def test_prepare_startup_does_not_force_stop_unowned_ports_by_default(tmp_path):
    lifecycle = PortLifecycle("test-project", tmp_path, state_directory=tmp_path / "state")
    port = find_free_port()
    process = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=tmp_path,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags(),
    )
    try:
        wait_until_listening(port)
        spec = ServiceSpec.from_values("web", [port], [])

        results = lifecycle.prepare_startup(
            (spec,),
            graceful_timeout_seconds=0.1,
            port_process_resolver=lambda host, candidate: [process.pid],
        )

        assert results == []
        assert process_exists(process.pid)
    finally:
        if process_exists(process.pid):
            kill_process(process.pid)
            wait_process_exit(process.pid, 2.0)


def test_prepare_startup_force_stops_unowned_ports_when_requested(tmp_path):
    lifecycle = PortLifecycle("test-project", tmp_path, state_directory=tmp_path / "state")
    port = find_free_port()
    process = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=tmp_path,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags(),
    )
    try:
        wait_until_listening(port)
        spec = ServiceSpec.from_values("web", [port], [])

        results = lifecycle.prepare_startup(
            (spec,),
            graceful_timeout_seconds=0.1,
            force_by_port=True,
            port_process_resolver=lambda host, candidate: [process.pid],
        )

        assert len(results) == 1
        assert results[0].stopped
        assert results[0].reason.startswith("force_by_port:")
        assert not process_exists(process.pid)
    finally:
        if process_exists(process.pid):
            kill_process(process.pid)
            wait_process_exit(process.pid, 2.0)


def test_profile_step_writes_startup_ledger(tmp_path):
    lifecycle = PortLifecycle("test-project", tmp_path, state_directory=tmp_path / "state")

    result = lifecycle.profile_step("sample_step", lambda: "done", run_id="run-1")

    assert result == "done"
    record = json.loads(lifecycle.startup_ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert record["event"] == "step_timing"
    assert record["label"] == "sample_step"
    assert record["run_id"] == "run-1"
    assert record["status"] == "completed"
    assert record["elapsed_seconds"] >= 0


def test_restart_services_records_standard_timing(monkeypatch, tmp_path):
    lifecycle = PortLifecycle("test-project", tmp_path, state_directory=tmp_path / "state")
    api = ServiceSpec.from_values("api", [8100], [sys.executable, "api.py"])
    ui = ServiceSpec.from_values("ui", [8200], [sys.executable, "ui.py"])
    stop_result = lifecycle_module.StopResult("api", 8100, 123, True, False, "terminated")
    calls = []

    def fake_prepare_startup(service_specs, graceful_timeout_seconds=5.0, force_by_port=False, force_graceful_timeout_seconds=0.5, port_process_resolver=None):
        calls.append(("prepare_startup", tuple(spec.name for spec in service_specs), force_by_port))
        return [stop_result]

    def fake_resolve_plan(service_specs):
        calls.append(("resolve_plan", tuple(spec.name for spec in service_specs)))
        return {"api": 8100, "ui": 8200}

    def fake_start_service(spec, port=None):
        calls.append(("start_service", spec.name, port))
        return lifecycle_module.ServiceState(spec.name, spec.host, int(port), 999, tuple(spec.command), "now", "out", "err", "authority", (), None, None, None, 0.0)

    monkeypatch.setattr(lifecycle, "prepare_startup", fake_prepare_startup)
    monkeypatch.setattr(lifecycle, "resolve_plan", fake_resolve_plan)
    monkeypatch.setattr(lifecycle, "start_service", fake_start_service)

    result = lifecycle.restart_services((api, ui), force_by_port=True, run_id="restart-1")

    assert result.run_id == "restart-1"
    assert result.stop_results == (stop_result,)
    assert result.port_plan == {"api": 8100, "ui": 8200}
    assert [state.name for state in result.service_states] == ["api", "ui"]
    assert [timing.label for timing in result.timings] == ["prepare_startup", "resolve_ports", "start:api", "start:ui"]
    assert calls == [
        ("prepare_startup", ("api", "ui"), True),
        ("resolve_plan", ("api", "ui")),
        ("start_service", "api", 8100),
        ("start_service", "ui", 8200),
    ]
    ledger_records = [json.loads(line) for line in lifecycle.startup_ledger.read_text(encoding="utf-8").splitlines()]
    assert [record["label"] for record in ledger_records] == ["prepare_startup", "resolve_ports", "start:api", "start:ui"]
    assert {record["run_id"] for record in ledger_records} == {"restart-1"}


def test_stop_service_reports_stop_command_success(monkeypatch, tmp_path):
    lifecycle = PortLifecycle("test-project", tmp_path, state_directory=tmp_path / "state")
    lifecycle.write_state(
        {
            "web": {
                "port": 12345,
                "pid": 999999,
                "host": "127.0.0.1",
                "command": ["owned-process"],
                "stop_command": ["noop"],
                "port_release_timeout_seconds": 0.0,
            }
        }
    )
    process_states = iter((True, False, False))
    waited = []

    monkeypatch.setattr(lifecycle_module, "process_exists", lambda pid: next(process_states))
    monkeypatch.setattr(lifecycle_module, "process_matches_command", lambda pid, command: True)
    monkeypatch.setattr(lifecycle_module, "wait_process_exit", lambda pid, timeout: waited.append(timeout) or True)
    monkeypatch.setattr(lifecycle, "_run_stop_command", lambda command, port, host: None)

    result = lifecycle.stop_service("web")

    assert result.stopped
    assert result.reason == "stop_command"
    assert waited == [5.0]


def test_stop_command_expands_host_port_and_workspace(monkeypatch, tmp_path):
    lifecycle = PortLifecycle("test-project", tmp_path, state_directory=tmp_path / "state")
    captured = []

    def fake_run(command, cwd, stdout, stderr, check):
        captured.append((command, cwd, stdout, stderr, check))

    monkeypatch.setattr(lifecycle_module.subprocess, "run", fake_run)

    lifecycle._run_stop_command((sys.executable, "stop.py", "--url", "http://{host}:{port}/stop", "--root", "{workspace}"), 4567, "127.0.0.1")

    assert captured[0][0] == (sys.executable, "stop.py", "--url", "http://127.0.0.1:4567/stop", "--root", str(tmp_path.resolve()))


def test_stop_service_does_not_report_stop_command_when_pid_was_already_missing(monkeypatch, tmp_path):
    lifecycle = PortLifecycle("test-project", tmp_path, state_directory=tmp_path / "state")
    lifecycle.write_state(
        {
            "web": {
                "port": 12345,
                "pid": 999999,
                "host": "127.0.0.1",
                "stop_command": ["noop"],
                "port_release_timeout_seconds": 0.0,
            }
        }
    )
    stop_command_called = False

    def fake_stop_command(command, port):
        nonlocal stop_command_called
        stop_command_called = True

    monkeypatch.setattr(lifecycle_module, "process_exists", lambda pid: False)
    monkeypatch.setattr(lifecycle, "_run_stop_command", lambda command, port, host: fake_stop_command(command, port))

    result = lifecycle.stop_service("web")

    assert not stop_command_called
    assert not result.stopped
    assert result.reason == "not_running"


def test_stop_service_keeps_recovery_artifacts_when_termination_fails(monkeypatch, tmp_path):
    lifecycle = PortLifecycle("test-project", tmp_path, state_directory=tmp_path / "state")
    lifecycle.write_state(
        {
            "web": {
                "port": 12345,
                "pid": 999999,
                "host": "127.0.0.1",
                "command": ["owned-process"],
                "stop_command": [],
                "port_release_timeout_seconds": 0.0,
            }
        }
    )
    pid_file = lifecycle._pid_file("web", 12345)
    authority_file = lifecycle._authority_file("web")
    pid_file.write_text(json.dumps({"name": "web", "port": 12345, "pid": 999999}), encoding="utf-8")
    authority_file.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(lifecycle_module, "process_exists", lambda pid: True)
    monkeypatch.setattr(lifecycle_module, "process_matches_command", lambda pid, command: True)
    monkeypatch.setattr(lifecycle_module, "terminate_process", lambda pid: None)
    monkeypatch.setattr(lifecycle_module, "kill_process", lambda pid: None)
    monkeypatch.setattr(lifecycle_module, "wait_process_exit", lambda pid, timeout: False)

    result = lifecycle.stop_service("web", graceful_timeout_seconds=0.1)

    assert not result.stopped
    assert result.reason == "kill_attempted"
    assert "web" in lifecycle.read_state()
    assert pid_file.exists()
    assert authority_file.exists()


def test_stop_service_keeps_artifacts_and_skips_kill_when_identity_mismatches(monkeypatch, tmp_path):
    lifecycle = PortLifecycle("test-project", tmp_path, state_directory=tmp_path / "state")
    lifecycle.write_state(
        {
            "web": {
                "port": 12345,
                "pid": 999999,
                "host": "127.0.0.1",
                "command": ["owned-process"],
                "stop_command": [],
                "port_release_timeout_seconds": 0.0,
            }
        }
    )
    pid_file = lifecycle._pid_file("web", 12345)
    authority_file = lifecycle._authority_file("web")
    pid_file.write_text(json.dumps({"name": "web", "port": 12345, "pid": 999999, "command": ["owned-process"]}), encoding="utf-8")
    authority_file.write_text("{}", encoding="utf-8")
    killed = False

    def fake_kill(pid):
        nonlocal killed
        killed = True

    monkeypatch.setattr(lifecycle_module, "process_exists", lambda pid: True)
    monkeypatch.setattr(lifecycle_module, "process_matches_command", lambda pid, command: False)
    monkeypatch.setattr(lifecycle_module, "kill_process", fake_kill)

    result = lifecycle.stop_service("web", graceful_timeout_seconds=0.1)

    assert not killed
    assert not result.stopped
    assert result.reason == "identity_mismatch"
    assert "web" in lifecycle.read_state()
    assert pid_file.exists()
    assert authority_file.exists()


def test_orphaned_pid_file_is_kept_when_recovery_stop_fails(monkeypatch, tmp_path):
    lifecycle = PortLifecycle("test-project", tmp_path, state_directory=tmp_path / "state")
    pid_file = lifecycle._pid_file("web", 12345)
    pid_file.write_text(json.dumps({"name": "web", "port": 12345, "pid": 999999, "command": ["owned-process"]}), encoding="utf-8")

    monkeypatch.setattr(lifecycle, "_stop_pid_payload", lambda payload, timeout: lifecycle_module.StopResult("web", 12345, 999999, False, True, "pid_file_recovery:kill_attempted"))
    monkeypatch.setattr(lifecycle_module, "process_exists", lambda pid: True)

    results = lifecycle.stop_orphaned_pid_files(graceful_timeout_seconds=0.1)

    assert not results[0].stopped
    assert pid_file.exists()
    ledger_record = json.loads(lifecycle.termination_ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert ledger_record["reason"] == "pid_file_recovery:kill_attempted"


def test_load_service_specs_from_json_keeps_runtime_port_template(tmp_path):
    config = tmp_path / "services.json"
    config.write_text(
        json.dumps(
            {
                "project_name": "sample-project",
                "services": [
                    {
                        "name": "api",
                        "preferred_ports": [8100, 8110],
                        "command": ["{python}", "server.py", "--bind", "{host}:{port}"],
                        "cwd": "app",
                        "health_url": "http://{host}:{port}/health",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    specs = load_service_specs(config, tmp_path, {"python": sys.executable})

    assert load_project_name(config, "fallback") == "sample-project"
    assert specs["api"].preferred_ports == (8100, 8110)
    assert specs["api"].command[0] == sys.executable
    assert specs["api"].command[-1] == "{host}:{port}"
    assert specs["api"].cwd == tmp_path / "app"


def http_server_spec(tmp_path: Path, ports: list[int], listener_identity_url: str | None = None) -> ServiceSpec:
    return ServiceSpec.from_values(
        name="web",
        preferred_ports=ports,
        command=[sys.executable, "-m", "http.server", "{port}", "--bind", "{host}"],
        cwd=tmp_path,
        health_url="http://{host}:{port}/",
        listener_identity_url=listener_identity_url,
        startup_timeout_seconds=10.0,
    )


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_until_listening(port: int) -> None:
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        if not is_port_available("127.0.0.1", port):
            return
        time.sleep(0.05)
    raise AssertionError(f"port did not start listening: {port}")

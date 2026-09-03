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

from service_lifecycle_engine import ServiceLifecycleEngine, ServiceSpec, is_port_available, process_exists
from service_lifecycle_engine.platform_ops import creation_flags, kill_process, wait_process_exit


def test_resolve_port_skips_occupied_port(tmp_path):
    lifecycle = ServiceLifecycleEngine("test-project", tmp_path, state_directory=tmp_path / "state")
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
    lifecycle = ServiceLifecycleEngine("test-project", tmp_path, state_directory=tmp_path / "state")
    shared_port = find_free_port()
    fallback_port = find_free_port()
    api_spec = ServiceSpec.from_values("api", [shared_port], [sys.executable, "--version"])
    ui_spec = ServiceSpec.from_values("ui", [shared_port, fallback_port], [sys.executable, "--version"])

    assert lifecycle.resolve_plan((api_spec, ui_spec)) == {"api": shared_port, "ui": fallback_port}


def test_wait_ready_rejects_dead_child_even_when_health_url_responds(tmp_path):
    lifecycle = ServiceLifecycleEngine("test-project", tmp_path, state_directory=tmp_path / "state")
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
        stop_process(server.pid)


def test_start_and_stop_service_writes_termination_ledger(tmp_path):
    lifecycle = ServiceLifecycleEngine("test-project", tmp_path, state_directory=tmp_path / "state")
    port = find_free_port()
    state = lifecycle.start_service(http_server_spec(tmp_path, [port]), port=port)

    result = lifecycle.stop_service("web", graceful_timeout_seconds=0.1)

    assert result.stopped
    assert not process_exists(state.pid)
    ledger_record = json.loads(lifecycle.termination_ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert ledger_record["service"] == "web"
    assert ledger_record["port"] == port


def test_stop_all_recovers_from_pid_file_when_state_is_missing(tmp_path):
    lifecycle = ServiceLifecycleEngine("test-project", tmp_path, state_directory=tmp_path / "state")
    port = find_free_port()
    state = lifecycle.start_service(http_server_spec(tmp_path, [port]), port=port)
    lifecycle.state_file.unlink()

    results = lifecycle.stop_all(graceful_timeout_seconds=0.1)

    assert any(result.pid == state.pid and result.stopped for result in results)
    assert not process_exists(state.pid)


def test_start_service_writes_launch_authority_with_identity_probe(tmp_path):
    lifecycle = ServiceLifecycleEngine("test-project", tmp_path, instance_name="instance-a", state_directory=tmp_path / "state")
    port = find_free_port()

    state = lifecycle.start_service(http_server_spec(tmp_path, [port], listener_identity_url="http://{host}:{port}/"), port=port)
    try:
        authority = json.loads(Path(state.launch_authority_file).read_text(encoding="utf-8"))
        assert authority["service"] == "web"
        assert authority["listener_identity_probe"]["reachable"] is True
        assert state.listener_identity_fingerprint
    finally:
        lifecycle.stop_service("web", graceful_timeout_seconds=0.1)


def test_prepare_startup_does_not_force_stop_unowned_ports_by_default(tmp_path):
    lifecycle = ServiceLifecycleEngine("test-project", tmp_path, state_directory=tmp_path / "state")
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
        results = lifecycle.prepare_startup((spec,), graceful_timeout_seconds=0.1, port_process_resolver=lambda host, candidate: [process.pid])
        assert results == []
        assert process_exists(process.pid)
    finally:
        stop_process(process.pid)


def test_prepare_startup_force_stops_unowned_ports_when_requested(tmp_path):
    lifecycle = ServiceLifecycleEngine("test-project", tmp_path, state_directory=tmp_path / "state")
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
        results = lifecycle.prepare_startup((spec,), graceful_timeout_seconds=0.1, force_by_port=True, port_process_resolver=lambda host, candidate: [process.pid])
        assert len(results) == 1
        assert results[0].stopped
        assert results[0].force_requested
        assert not process_exists(process.pid)
    finally:
        stop_process(process.pid)


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


def stop_process(pid: int) -> None:
    if process_exists(pid):
        kill_process(pid)
        wait_process_exit(pid, 2.0)

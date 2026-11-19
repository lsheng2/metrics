from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from service_lifecycle_engine import LifecycleState, PlatformOperationSet, ServiceExitedBeforeReadyError, ServiceLifecycleEngine, ServiceSpec

FOREIGN_PID = 999


class FakeProcess:
    def __init__(self, host: FakeHost, pid: int, exit_code: int) -> None:
        self.host = host
        self.pid = pid
        self.exit_code = exit_code

    def poll(self) -> int | None:
        return None if self.pid in self.host.alive else self.exit_code


class FakeHost:
    def __init__(self) -> None:
        self.listeners: dict[int, int] = {}
        self.alive: set[int] = set()
        self.commands: dict[int, tuple[str, ...]] = {}
        self.claim_on_start: dict[int, int] = {}
        self.crash_on_start: dict[int, int] = {}
        self.started: list[tuple[int, str | None]] = []
        self.terminated: list[int] = []
        self.next_pid = 100

    def occupy(self, port: int, pid: int = FOREIGN_PID) -> None:
        self.alive.add(pid)
        self.listeners[port] = pid

    def start_process(self, command, cwd, env, stdout, stderr, flags) -> FakeProcess:
        port = int(command[-1])
        self.next_pid += 1
        pid = self.next_pid
        self.started.append((port, env.get("PEER_API_PORT")))
        if port in self.claim_on_start:
            self.occupy(port, self.claim_on_start.pop(port))
        if port in self.crash_on_start:
            return FakeProcess(self, pid, self.crash_on_start.pop(port))
        if port in self.listeners:
            return FakeProcess(self, pid, 1)
        self.alive.add(pid)
        self.commands[pid] = tuple(command)
        self.listeners[port] = pid
        return FakeProcess(self, pid, 0)

    def stop(self, pid: int) -> None:
        self.terminated.append(pid)
        self.alive.discard(pid)
        self.listeners = {port: owner for port, owner in self.listeners.items() if owner != pid}

    def operations(self) -> PlatformOperationSet:
        return PlatformOperationSet(
            is_port_available=lambda host, port: port not in self.listeners,
            process_exists=lambda pid: pid in self.alive,
            process_matches_command=lambda pid, command: pid in self.alive and self.commands.get(pid) == tuple(command),
            process_command_line=lambda pid: " ".join(self.commands.get(pid, ())),
            process_start_marker=lambda pid: f"started:{pid}" if pid in self.alive else "",
            get_listening_process_ids=lambda host, port: (self.listeners[port],) if port in self.listeners else (),
            http_status_ok=lambda url: False,
            http_probe=lambda url: {},
            start_process=self.start_process,
            terminate_process=self.stop,
            kill_process=self.stop,
            wait_process_exit=lambda pid, timeout: pid not in self.alive,
            wait_port_available=lambda host, port, timeout: port not in self.listeners,
            creation_flags=lambda: 0,
        )


def make_engine(tmp_path: Path, host: FakeHost, events: list) -> ServiceLifecycleEngine:
    return ServiceLifecycleEngine("replan", tmp_path, state_directory=tmp_path / "state", event_handler=events.append, platform_ops=host.operations())


def service(name: str, ports: list[int]) -> ServiceSpec:
    return ServiceSpec.from_values(name, ports, ["python", f"{name}.py", "--port", "{port}"], startup_timeout_seconds=2.0)


def event_trace(events: list) -> list[tuple[str, LifecycleState, str, int]]:
    return [(event.service_name, event.state, event.reason, event.port) for event in events]


def test_restartShouldMoveServiceToNextFreePortWhenPortIsTakenBeforeStart(tmp_path):
    host = FakeHost()
    events = []
    engine = make_engine(tmp_path, host, events)
    plans = []

    def before_start(plan, specs):
        plans.append(dict(plan))
        if len(plans) == 1:
            host.occupy(8100)
        return [replace(spec, env={"PEER_API_PORT": str(plan["api"])}) for spec in specs]

    result = engine.restart_services((service("api", [8100, 8200, 8300]), service("worker", [8200])), run_id="replan-1", before_start=before_start)

    assert plans == [{"api": 8100, "worker": 8200}, {"api": 8300, "worker": 8200}]
    assert result.port_plan == {"api": 8300, "worker": 8200}
    assert host.started == [(8300, "8300"), (8200, "8300")]
    assert event_trace(events) == [
        ("api", LifecycleState.PREPARED, "port_resolved", 8100),
        ("worker", LifecycleState.PREPARED, "port_resolved", 8200),
        ("api", LifecycleState.PREPARED, "port_reresolved", 8300),
        ("api", LifecycleState.READY, "readiness_passed", 8300),
        ("worker", LifecycleState.READY, "readiness_passed", 8200),
    ]
    assert host.terminated == []


def test_restartShouldRetryOnNextPortWhenServiceExitsBecauseAnotherProcessClaimedItsPort(tmp_path):
    host = FakeHost()
    host.claim_on_start[8100] = FOREIGN_PID
    events = []
    engine = make_engine(tmp_path, host, events)

    result = engine.restart_services((service("api", [8100, 8200]),), run_id="replan-1")

    assert result.port_plan == {"api": 8200}
    assert [port for port, _ in host.started] == [8100, 8200]
    assert event_trace(events) == [
        ("api", LifecycleState.PREPARED, "port_resolved", 8100),
        ("api", LifecycleState.ABORTED, "failed:ServiceExitedBeforeReadyError", 8100),
        ("api", LifecycleState.PREPARED, "port_reresolved", 8200),
        ("api", LifecycleState.READY, "readiness_passed", 8200),
    ]
    assert host.listeners[8100] == FOREIGN_PID
    assert FOREIGN_PID not in host.terminated


def test_restartShouldFailWithoutRetryWhenServiceExitsWhileItsPortStaysFree(tmp_path):
    host = FakeHost()
    host.crash_on_start[8100] = 2
    events = []
    engine = make_engine(tmp_path, host, events)

    with pytest.raises(ServiceExitedBeforeReadyError) as raised:
        engine.restart_services((service("api", [8100, 8200]),), run_id="replan-1")

    assert raised.value.exit_code == 2
    assert [port for port, _ in host.started] == [8100]
    assert event_trace(events) == [
        ("api", LifecycleState.PREPARED, "port_resolved", 8100),
        ("api", LifecycleState.ABORTED, "failed:ServiceExitedBeforeReadyError", 8100),
    ]


def test_restartShouldAbortWhenNoPreferredPortRemainsAfterPortIsTaken(tmp_path):
    host = FakeHost()
    events = []
    engine = make_engine(tmp_path, host, events)

    def before_start(plan, specs):
        host.occupy(8100)
        return specs

    with pytest.raises(RuntimeError, match="No available port for api"):
        engine.restart_services((service("api", [8100]),), run_id="replan-1", before_start=before_start)

    assert host.started == []
    assert event_trace(events) == [
        ("api", LifecycleState.PREPARED, "port_resolved", 8100),
        ("api", LifecycleState.ABORTED, "failed:RuntimeError", 8100),
    ]


def test_failedStartShouldNeitherAdoptNorStopForeignListenerOnItsPort(tmp_path):
    host = FakeHost()
    host.claim_on_start[8100] = FOREIGN_PID
    events = []
    engine = make_engine(tmp_path, host, events)

    with pytest.raises(ServiceExitedBeforeReadyError):
        engine.start_service(service("api", [8100]), port=8100)

    aborted = engine.read_state()["api"]
    assert aborted["lifecycle_state"] == LifecycleState.ABORTED
    assert aborted["provenance"]["listener_pid"] is None
    assert events[-1].provenance.listener_pid is None

    result = engine.stop_service("api", graceful_timeout_seconds=0.1)

    assert result.reason == "not_running"
    assert host.terminated == []
    assert host.listeners[8100] == FOREIGN_PID

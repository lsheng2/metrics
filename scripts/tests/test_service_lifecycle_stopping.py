from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from service_lifecycle_engine import (
    LifecycleState,
    LifecycleStateStoreError,
    PlatformOperationSet,
    ProvenanceCapability,
    ServiceLifecycleEngine,
    ServiceSpec,
    StopResult,
    StopSource,
)


def test_shouldRepresentStopSourceSeparatelyFromKillEscalation():
    result = StopResult(
        name="api",
        port=8100,
        pid=12345,
        stopped=True,
        forced=False,
        reason="force_by_port:terminated",
        stop_source=StopSource.FORCE_BY_PORT,
        force_requested=True,
    )

    assert result.stop_source == StopSource.FORCE_BY_PORT
    assert result.force_requested is True
    assert result.forced is False


def test_shouldReportForceByPortSourceSeparatelyFromKillEscalation(tmp_path):
    process_states = iter((True, False))
    operations = PlatformOperationSet(
        process_exists=lambda pid: next(process_states),
        terminate_process=lambda pid: None,
        wait_process_exit=lambda pid, timeout: True,
    )
    lifecycle = ServiceLifecycleEngine("test-project", tmp_path, state_directory=tmp_path / "state", platform_ops=operations)

    result = lifecycle._stop_process("api", 8100, 12345, 0.1, "force_by_port")

    assert result.stop_source == StopSource.FORCE_BY_PORT
    assert result.force_requested is True
    assert result.forced is False


def test_shouldEmitStoppedEventWithPersistedProvenance(tmp_path):
    events = []
    process_states = iter((True, True, False))
    operations = PlatformOperationSet(
        process_exists=lambda pid: next(process_states),
        process_matches_command=lambda pid, command: True,
        terminate_process=lambda pid: None,
        wait_process_exit=lambda pid, timeout: True,
        wait_port_available=lambda host, port, timeout: True,
    )
    lifecycle = ServiceLifecycleEngine("test-project", tmp_path, state_directory=tmp_path / "state", event_handler=events.append, platform_ops=operations)
    lifecycle.write_state({
        "api": {
            "host": "127.0.0.1",
            "port": 8100,
            "pid": 12345,
            "lifecycle_state": "ready",
            "command": ["python", "api.py"],
            "stop_command": [],
            "provenance": {
                "wrapper_pid": 12345,
                "capability": "registered_process",
            },
        }
    })

    result = lifecycle.stop_service("api", graceful_timeout_seconds=0.1)

    assert [(event.service_name, event.state, event.reason) for event in events] == [
        ("api", LifecycleState.STOPPED, "terminated"),
    ]
    assert lifecycle.read_state()["api"]["lifecycle_state"] == LifecycleState.STOPPED
    assert result.provenance.wrapper_pid == 12345
    assert events[0].provenance.wrapper_pid == 12345
    assert events[0].provenance.capability == ProvenanceCapability.REGISTERED_PROCESS


def test_stopServiceShouldNotMarkStoppedWhenOwnedListenerSurvivesWrapperExit(tmp_path):
    events = []
    terminated_pids = []
    killed_pids = []
    operations = PlatformOperationSet(
        process_exists=lambda pid: pid == 22345,
        get_listening_process_ids=lambda host, port: (22345,),
        terminate_process=lambda pid: terminated_pids.append(pid),
        kill_process=lambda pid: killed_pids.append(pid),
        wait_process_exit=lambda pid, timeout: False,
    )
    lifecycle = ServiceLifecycleEngine("test-project", tmp_path, state_directory=tmp_path / "state", event_handler=events.append, platform_ops=operations)
    lifecycle.write_state({
        "api": {
            "host": "127.0.0.1",
            "port": 8100,
            "pid": 12345,
            "lifecycle_state": "ready",
            "command": ["python", "wrapper.py"],
            "stop_command": [],
            "provenance": {
                "wrapper_pid": 12345,
                "listener_pid": 22345,
                "capability": "owned_listener",
            },
        }
    })

    result = lifecycle.stop_service("api", graceful_timeout_seconds=0.1)

    assert result.stopped is False
    assert result.pid == 22345
    assert result.reason == "owned_listener:kill_attempted"
    assert terminated_pids == [22345]
    assert killed_pids == [22345]
    assert lifecycle.read_state()["api"]["lifecycle_state"] == "ready"
    assert events == []


def test_stopServiceShouldIgnoreOwnedListenerPidWhenItNoLongerListensOnServicePort(tmp_path):
    terminated_pids = []
    killed_pids = []
    operations = PlatformOperationSet(
        process_exists=lambda pid: pid == 22345,
        get_listening_process_ids=lambda host, port: (),
        terminate_process=lambda pid: terminated_pids.append(pid),
        kill_process=lambda pid: killed_pids.append(pid),
        wait_process_exit=lambda pid, timeout: False,
    )
    lifecycle = ServiceLifecycleEngine("test-project", tmp_path, state_directory=tmp_path / "state", platform_ops=operations)
    lifecycle.write_state({
        "api": {
            "host": "127.0.0.1",
            "port": 8100,
            "pid": 12345,
            "lifecycle_state": "ready",
            "command": ["python", "wrapper.py"],
            "stop_command": [],
            "provenance": {
                "wrapper_pid": 12345,
                "listener_pid": 22345,
                "capability": "owned_listener",
            },
        }
    })

    lifecycle.stop_service("api", graceful_timeout_seconds=0.1)

    assert terminated_pids == []
    assert killed_pids == []
    assert lifecycle.read_state()["api"]["lifecycle_state"] == LifecycleState.STOPPED


def test_startServiceShouldNotBeBlockedByStaleOwnedListenerPid(tmp_path):
    terminated_pids = []
    operations = PlatformOperationSet(
        start_process=lambda *args, **kwargs: FakeProcess(32345),
        process_exists=lambda pid: pid == 22345,
        get_listening_process_ids=lambda host, port: (),
        terminate_process=lambda pid: terminated_pids.append(pid),
        process_matches_command=lambda pid, command: True,
        process_command_line=lambda pid: "python api.py",
        process_start_marker=lambda pid: "started:32345",
        http_status_ok=lambda url: True,
    )
    lifecycle = ServiceLifecycleEngine("test-project", tmp_path, state_directory=tmp_path / "state", platform_ops=operations)
    lifecycle.write_state({
        "api": {
            "host": "127.0.0.1",
            "port": 8100,
            "pid": 12345,
            "lifecycle_state": "ready",
            "command": ["python", "old-wrapper.py"],
            "stop_command": [],
            "provenance": {
                "wrapper_pid": 12345,
                "listener_pid": 22345,
                "capability": "owned_listener",
            },
        }
    })
    spec = ServiceSpec.from_values("api", [8100], ["python", "api.py"], health_url="http://{host}:{port}/health")

    state = lifecycle.start_service(spec, port=8100)

    assert state.pid == 32345
    assert terminated_pids == []


def test_startServiceShouldNotBeBlockedByStaleRegisteredPidWithCommandMismatch(tmp_path):
    terminated_pids = []
    operations = PlatformOperationSet(
        start_process=lambda *args, **kwargs: FakeProcess(32345),
        process_exists=lambda pid: pid in {12345, 32345},
        process_matches_command=lambda pid, command: pid == 32345,
        process_command_line=lambda pid: "python api.py" if pid == 32345 else "python unrelated.py",
        process_start_marker=lambda pid: f"started:{pid}",
        terminate_process=lambda pid: terminated_pids.append(pid),
        http_status_ok=lambda url: True,
    )
    lifecycle = ServiceLifecycleEngine("test-project", tmp_path, state_directory=tmp_path / "state", platform_ops=operations)
    lifecycle.write_state({
        "api": {
            "host": "127.0.0.1",
            "port": 8100,
            "pid": 12345,
            "lifecycle_state": "ready",
            "command": ["python", "old-api.py"],
            "stop_command": [],
            "provenance": {
                "wrapper_pid": 12345,
                "capability": "registered_process",
            },
        }
    })
    spec = ServiceSpec.from_values("api", [8100], ["python", "api.py"], health_url="http://{host}:{port}/health")

    state = lifecycle.start_service(spec, port=8100)

    assert state.pid == 32345
    assert terminated_pids == []


def test_resolvePortShouldNotReusePortFromStaleRegisteredPidWithCommandMismatch(tmp_path):
    operations = PlatformOperationSet(
        process_exists=lambda pid: pid == 12345,
        process_matches_command=lambda pid, command: False,
        is_port_available=lambda host, port: port == 8200,
    )
    lifecycle = ServiceLifecycleEngine("test-project", tmp_path, state_directory=tmp_path / "state", platform_ops=operations)
    lifecycle.write_state({
        "api": {
            "host": "127.0.0.1",
            "port": 8100,
            "pid": 12345,
            "lifecycle_state": "ready",
            "command": ["python", "old-api.py"],
            "stop_command": [],
            "provenance": {
                "wrapper_pid": 12345,
                "capability": "registered_process",
            },
        }
    })
    spec = ServiceSpec.from_values("api", [8100, 8200], ["python", "api.py"])

    assert lifecycle.resolve_port(spec) == 8200


def test_stopServiceShouldRejectOwnedListenerWhenIdentityFingerprintChanges(tmp_path):
    terminated_pids = []
    operations = PlatformOperationSet(
        process_exists=lambda pid: pid == 22345,
        get_listening_process_ids=lambda host, port: (22345,),
        http_probe=lambda url: {"body_sha256": "observed"},
        terminate_process=lambda pid: terminated_pids.append(pid),
    )
    lifecycle = ServiceLifecycleEngine("test-project", tmp_path, state_directory=tmp_path / "state", platform_ops=operations)
    lifecycle.write_state({
        "api": {
            "host": "127.0.0.1",
            "port": 8100,
            "pid": 12345,
            "lifecycle_state": "ready",
            "command": ["python", "wrapper.py"],
            "stop_command": [],
            "listener_identity_url": "http://127.0.0.1:8100/identity",
            "provenance": {
                "wrapper_pid": 12345,
                "listener_pid": 22345,
                "listener_identity_fingerprint": "expected",
                "capability": "http_identity",
            },
        }
    })

    lifecycle.stop_service("api", graceful_timeout_seconds=0.1)

    assert terminated_pids == []
    assert lifecycle.read_state()["api"]["lifecycle_state"] == LifecycleState.STOPPED


def test_shouldFailClosedWhenStoppingStateWithUnknownProvenanceCapability(tmp_path):
    events = []
    process_states = iter((True, True, False))
    operations = PlatformOperationSet(
        process_exists=lambda pid: next(process_states),
        process_matches_command=lambda pid, command: True,
        terminate_process=lambda pid: None,
        wait_process_exit=lambda pid, timeout: True,
        wait_port_available=lambda host, port, timeout: True,
    )
    lifecycle = ServiceLifecycleEngine("test-project", tmp_path, state_directory=tmp_path / "state", event_handler=events.append, platform_ops=operations)
    lifecycle.write_state({
        "api": {
            "host": "127.0.0.1",
            "port": 8100,
            "pid": 12345,
            "lifecycle_state": "ready",
            "command": ["python", "api.py"],
            "stop_command": [],
            "provenance": {
                "wrapper_pid": 12345,
                "capability": "future_capability",
            },
        }
    })

    try:
        lifecycle.stop_service("api", graceful_timeout_seconds=0.1)
    except LifecycleStateStoreError as error:
        assert error.failure_kind == "state_corrupt"
    else:
        raise AssertionError("unknown persisted provenance capability should fail closed")
    assert events == []


def test_stopServiceShouldUseInjectedStopCommandRunner(tmp_path):
    commands = []
    process_states = iter((True, True, False, False))
    operations = PlatformOperationSet(
        process_exists=lambda pid: next(process_states),
        process_matches_command=lambda pid, command: True,
        run_command=lambda command, cwd: commands.append((command, cwd)),
        wait_process_exit=lambda pid, timeout: True,
    )
    lifecycle = ServiceLifecycleEngine("project", tmp_path, state_directory=tmp_path / "state", platform_ops=operations)
    lifecycle.write_state({
        "api": {
            "host": "127.0.0.1",
            "port": 8100,
            "pid": 12345,
            "lifecycle_state": "ready",
            "command": ["python", "api.py"],
            "stop_command": ["python", "stop.py", "{port}"],
        }
    })

    result = lifecycle.stop_service("api", graceful_timeout_seconds=0.1)

    assert result.reason == "stop_command"
    assert commands == [(("python", "stop.py", "8100"), tmp_path.resolve())]


class FakeProcess:
    def __init__(self, pid):
        self.pid = pid

    def poll(self):
        return None

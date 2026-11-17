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
    ServiceState,
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


def test_shouldMarkTerminateProcessAsForcedWhenPlatformClassifiesItThatWay(tmp_path):
    class ForcefulTerminateOps:
        terminate_is_forceful = True

        def __init__(self):
            self.process_states = iter((True, True, False, False))

        def process_exists(self, pid):
            return next(self.process_states)

        def process_matches_command(self, pid, command):
            return True

        def terminate_process(self, pid):
            return None

        def wait_process_exit(self, pid, timeout):
            return True

        def wait_port_available(self, host, port, timeout):
            return True

        def observe_process_exit(self, pid):
            from contextlib import nullcontext
            from service_lifecycle_engine import ProcessExitObservation
            return nullcontext(ProcessExitObservation(lambda: None))

    lifecycle = ServiceLifecycleEngine("test-project", tmp_path, state_directory=tmp_path / "state", platform_ops=ForcefulTerminateOps())
    lifecycle.write_state({
        "api": {
            "host": "127.0.0.1",
            "port": 8100,
            "pid": 12345,
            "lifecycle_state": "ready",
            "command": ["python", "api.py"],
            "stop_command": [],
        }
    })

    result = lifecycle.stop_service("api", graceful_timeout_seconds=0.1)

    assert result.reason == "terminated"
    assert result.forced is True
    assert result.force_requested is False


def test_restartServicesStopsEachPlannedServiceWithItsOwnGrace(tmp_path):
    observed: list[tuple[str, float]] = []
    operations = PlatformOperationSet(is_port_available=lambda host, port: True)
    lifecycle = ServiceLifecycleEngine("test-project", tmp_path, state_directory=tmp_path / "state", platform_ops=operations)
    api = ServiceSpec.from_values("api", [8100], ["python", "api.py"], graceful_timeout_seconds=15.0)
    worker = ServiceSpec.from_values("worker", [8200], ["python", "worker.py"], graceful_timeout_seconds=3.0)

    def fake_stop_service(name, graceful_timeout_seconds=5.0):
        observed.append((name, graceful_timeout_seconds))
        return StopResult(name, -1, None, True, False, "stop_command")

    lifecycle.read_state = lambda: {"api": {}, "worker": {}}  # type: ignore[method-assign]
    lifecycle.stop_service = fake_stop_service  # type: ignore[method-assign]
    lifecycle.stop_orphaned_pid_files = lambda graceful_timeout_seconds=5.0: []  # type: ignore[method-assign]
    lifecycle.start_service = lambda spec, port=None, **kwargs: ServiceState(  # type: ignore[method-assign]
        spec.name,
        spec.host,
        int(port),
        12345,
        tuple(spec.command),
        "now",
        "out",
        "err",
        "authority",
        (),
        None,
        None,
        None,
        0.0,
    )

    lifecycle.restart_services((api, worker), run_id="restart-1")

    assert observed == [("api", 15.0), ("worker", 3.0)]


def test_shouldReportForceByPortSourceSeparatelyFromKillEscalation(tmp_path):
    process_states = iter((True, False))
    operations = PlatformOperationSet(
        process_exists=lambda pid: next(process_states),
        terminate_process=lambda pid: None,
        wait_process_exit=lambda pid, timeout: True,
        terminate_is_forceful=False,
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


def test_stopServiceShouldValidatePersistedStoppedStateAgainstRunningProcess(tmp_path):
    terminated_pids = []
    running_pids = {12345}
    operations = PlatformOperationSet(
        process_exists=lambda pid: pid in running_pids,
        process_matches_command=lambda pid, command: True,
        terminate_process=lambda pid: terminated_pids.append(pid),
        wait_process_exit=lambda pid, timeout: running_pids.discard(pid) is None,
        wait_port_available=lambda host, port, timeout: True,
    )
    lifecycle = ServiceLifecycleEngine("test-project", tmp_path, state_directory=tmp_path / "state", platform_ops=operations)
    lifecycle.write_state({
        "api": {
            "host": "127.0.0.1",
            "port": 8100,
            "pid": 12345,
            "lifecycle_state": "stopped",
            "command": ["python", "api.py"],
            "stop_command": [],
            "provenance": {
                "wrapper_pid": 12345,
                "capability": "registered_process",
            },
        }
    })

    result = lifecycle.stop_service("api", graceful_timeout_seconds=0.1)

    assert result.reason == "terminated"
    assert result.stopped is True
    assert terminated_pids == [12345]
    assert lifecycle.read_state()["api"]["lifecycle_state"] == LifecycleState.STOPPED


def test_stopServiceShouldNotMarkStoppedWhenOwnedListenerSurvivesWrapperExit(tmp_path):
    events = []
    terminated_pids = []
    killed_pids = []
    operations = PlatformOperationSet(
        process_exists=lambda pid: pid == 22345,
        process_matches_command=lambda pid, command: pid == 22345,
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


def test_stopServiceShouldRejectRegisteredPidWhenStartMarkerChanges(tmp_path):
    terminated_pids = []
    operations = PlatformOperationSet(
        process_exists=lambda pid: True,
        process_matches_command=lambda pid, command: True,
        process_start_marker=lambda pid: "observed-start",
        terminate_process=lambda pid: terminated_pids.append(pid),
    )
    lifecycle = ServiceLifecycleEngine("test-project", tmp_path, state_directory=tmp_path / "state", platform_ops=operations)
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
                "process_start_marker": "expected-start",
                "capability": "registered_process",
            },
        }
    })

    result = lifecycle.stop_service("api", graceful_timeout_seconds=0.1)

    assert result.stopped is False
    assert result.reason == "identity_mismatch"
    assert terminated_pids == []
    assert lifecycle.read_state()["api"]["lifecycle_state"] == "ready"


def test_stopServiceShouldRecheckIdentityAfterStopCommandGraceBeforeEscalating(tmp_path):
    terminated_pids = []
    killed_pids = []
    markers = iter(("expected-start", "reused-start"))
    operations = PlatformOperationSet(
        process_exists=lambda pid: True,
        process_matches_command=lambda pid, command: True,
        process_start_marker=lambda pid: next(markers, "reused-start"),
        run_command=lambda command, cwd: None,
        wait_process_exit=lambda pid, timeout: False,
        terminate_process=lambda pid: terminated_pids.append(pid),
        kill_process=lambda pid: killed_pids.append(pid),
    )
    lifecycle = ServiceLifecycleEngine("test-project", tmp_path, state_directory=tmp_path / "state", platform_ops=operations)
    lifecycle.write_state({
        "api": {
            "host": "127.0.0.1",
            "port": 8100,
            "pid": 12345,
            "lifecycle_state": "ready",
            "command": ["python", "api.py"],
            "stop_command": ["python", "stop.py"],
            "provenance": {
                "wrapper_pid": 12345,
                "process_start_marker": "expected-start",
                "capability": "registered_process",
            },
        }
    })

    result = lifecycle.stop_service("api", graceful_timeout_seconds=0.1)

    assert result.stopped is False
    assert result.reason == "identity_changed_after_stop_command"
    assert terminated_pids == []
    assert killed_pids == []
    assert lifecycle.read_state()["api"]["lifecycle_state"] == "ready"


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


def test_pid_reuse_during_termination_wait_prevents_followup_kill(tmp_path):
    marker = {"value": "original"}
    kills = []

    def waited(pid, timeout):
        marker["value"] = "reused"
        return False

    operations = PlatformOperationSet(
        process_exists=lambda pid: True,
        process_matches_command=lambda pid, command: True,
        process_start_marker=lambda pid: marker["value"],
        terminate_process=lambda pid: None,
        terminate_is_forceful=True,
        wait_process_exit=waited,
        kill_process=kills.append,
    )
    lifecycle = ServiceLifecycleEngine("identity-proof", tmp_path, state_directory=tmp_path / "state", platform_ops=operations)
    lifecycle.write_state({
        "api": {
            "host": "127.0.0.1", "port": 8100, "pid": 12345,
            "lifecycle_state": "ready", "command": ["python", "api.py"], "stop_command": [],
            "provenance": {"wrapper_pid": 12345, "process_start_marker": "original", "capability": "registered_process"},
        },
    })
    result = lifecycle.stop_service("api", graceful_timeout_seconds=0.1)
    assert kills == []
    assert result.stopped is False
    assert result.forced is True
    assert result.reason == "identity_changed_before_kill"

from __future__ import annotations

import importlib.util
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from service_lifecycle_engine import (
    LifecycleEvent,
    LifecycleOperationResult,
    LifecycleState,
    LifecycleStateStoreError,
    LifecycleTransition,
    LiveServiceResolution,
    LiveServiceResolutionSource,
    PlatformOperationSet,
    ProcessProvenance,
    ProvenanceCapability,
    ResolvedPortPlan,
    ServiceLifecycleEngine,
    ServiceSpec,
    ServiceState,
)


def test_shouldExposeGenericEngineImportWithoutPortLifecycleAlias():
    assert ServiceLifecycleEngine.__name__ == "ServiceLifecycleEngine"
    assert not hasattr(sys.modules["service_lifecycle_engine"], "PortLifecycle")


def test_legacyPortLifecyclePackageShouldNotRemainPublicImport():
    assert importlib.util.find_spec("port_lifecycle") is None


def test_shouldRejectUnsafeProjectInstanceAndServiceIdentifiers(tmp_path):
    try:
        ServiceLifecycleEngine("../bad", tmp_path)
    except ValueError as error:
        assert "project_name" in str(error)
    else:
        raise AssertionError("unsafe project_name should be rejected")

    lifecycle = ServiceLifecycleEngine("project", tmp_path, instance_name="safe", state_directory=tmp_path / "state")
    try:
        lifecycle.write_state({"../api": {"pid": 12345, "port": 8100}})
    except ValueError as error:
        assert "service_name" in str(error)
    else:
        raise AssertionError("unsafe service name should be rejected")


def test_startServiceShouldRejectUnsafeServiceNameBeforeStartingProcess(tmp_path):
    started = []
    operations = PlatformOperationSet(start_process=lambda *args, **kwargs: started.append(args) or FakeProcess(12345))
    lifecycle = ServiceLifecycleEngine("project", tmp_path, state_directory=tmp_path / "state", platform_ops=operations)
    spec = ServiceSpec.from_values("../api", [8100], ["python", "api.py"])

    try:
        lifecycle.start_service(spec, port=8100)
    except ValueError as error:
        assert "service_name" in str(error)
    else:
        raise AssertionError("unsafe service name should fail before process start")

    assert started == []


def test_restartServicesShouldRejectUnsafeServiceNameBeforePrepareSideEffects(tmp_path):
    prepared = []
    lifecycle = ServiceLifecycleEngine("project", tmp_path, state_directory=tmp_path / "state")
    spec = ServiceSpec.from_values("../api", [8100], ["python", "api.py"])

    try:
        lifecycle.restart_services((spec,), after_prepare=lambda results: prepared.append(results))
    except ValueError as error:
        assert "service_name" in str(error)
    else:
        raise AssertionError("unsafe service name should fail before prepare_startup")

    assert prepared == []
    assert lifecycle.read_state() == {}


def test_prepareStartupShouldRejectUnsafeServiceNameBeforeStoppingExistingService(tmp_path):
    operations = PlatformOperationSet(
        process_exists=lambda pid: True,
        process_matches_command=lambda pid, command: True,
        terminate_process=lambda pid: (_ for _ in ()).throw(AssertionError("stop should not run")),
    )
    lifecycle = ServiceLifecycleEngine("project", tmp_path, state_directory=tmp_path / "state", platform_ops=operations)
    lifecycle.write_state({"api": {"pid": 12345, "port": 8100, "lifecycle_state": "ready", "command": ["python", "api.py"]}})
    spec = ServiceSpec.from_values("../bad", [8200], ["python", "bad.py"])

    try:
        lifecycle.prepare_startup((spec,), graceful_timeout_seconds=0.1)
    except ValueError as error:
        assert "service_name" in str(error)
    else:
        raise AssertionError("unsafe service name should fail before stop_all")

    assert lifecycle.read_state()["api"]["lifecycle_state"] == "ready"


def test_startServiceShouldUseInjectedProcessStarterAndEmitReadyEvent(tmp_path):
    events = []
    operations = PlatformOperationSet(
        start_process=lambda *args, **kwargs: FakeProcess(12345),
        process_exists=lambda pid: True,
        process_matches_command=lambda pid, command: True,
        process_command_line=lambda pid: "python api.py",
        process_start_marker=lambda pid: "started:12345",
        http_status_ok=lambda url: True,
    )
    lifecycle = ServiceLifecycleEngine("project", tmp_path, state_directory=tmp_path / "state", platform_ops=operations, event_handler=events.append)
    spec = ServiceSpec.from_values("api", [8100], ["python", "api.py"], health_url="http://{host}:{port}/health")

    state = lifecycle.start_service(spec, port=8100)

    assert state.lifecycle_state == LifecycleState.READY
    assert [(event.service_name, event.state, event.reason) for event in events] == [
        ("api", LifecycleState.READY, "readiness_passed"),
    ]
    assert events[0].provenance.wrapper_pid == 12345


def test_shouldSerializeLifecycleModelsWithStableGenericValues():
    provenance = ProcessProvenance(
        wrapper_pid=12345,
        listener_pid=12346,
        process_group_id=7,
        process_start_marker="started:12345",
        command_fingerprint="command-sha",
        command_line="python api.py",
        listener_identity_fingerprint="identity-sha",
        capability=ProvenanceCapability.HTTP_IDENTITY,
    )
    event = LifecycleEvent(
        service_name="api",
        state=LifecycleState.ABORTED,
        reason="readiness_timeout",
        generation=3,
        host="127.0.0.1",
        port=8100,
        provenance=provenance,
    )

    assert asdict(event) == {
        "service_name": "api",
        "state": LifecycleState.ABORTED,
        "reason": "readiness_timeout",
        "generation": 3,
        "host": "127.0.0.1",
        "port": 8100,
        "metadata": {},
        "provenance": {
            "wrapper_pid": 12345,
            "listener_pid": 12346,
            "process_group_id": 7,
            "process_start_marker": "started:12345",
            "start_time": "",
            "command_fingerprint": "command-sha",
            "command_line": "python api.py",
            "listener_identity_fingerprint": "identity-sha",
            "capability": ProvenanceCapability.HTTP_IDENTITY,
        },
    }


def test_shouldRepresentAllPersistedLifecycleStatesWithoutFailedState():
    assert {state.value for state in LifecycleState} == {
        "planned",
        "prepared",
        "ready",
        "stopped",
        "aborted",
    }


def test_shouldRepresentFailedAsOperationResultReasonNotPersistedState():
    transition = LifecycleTransition(
        service_name="api",
        from_state=LifecycleState.PREPARED,
        to_state=LifecycleState.ABORTED,
        reason="readiness_timeout",
    )
    result = LifecycleOperationResult(
        service_name="api",
        succeeded=False,
        reason="failed:readiness_timeout",
        transition=transition,
    )

    assert result.transition.to_state == LifecycleState.ABORTED
    assert result.reason == "failed:readiness_timeout"


def test_shouldRepresentTypedLiveServiceResolution():
    resolution = LiveServiceResolution(
        service_name="api",
        host="127.0.0.1",
        port=8100,
        source=LiveServiceResolutionSource.EXPLICIT,
    )

    assert resolution.base_url == "http://127.0.0.1:8100"
    assert resolution.diagnostics == ()


def test_shouldRepresentResolvedPortPlanWithoutDuplicateServicePorts():
    plan = ResolvedPortPlan(ports_by_service={"api": 8100, "ui": 8200})

    assert plan.port_for("api") == 8100
    assert plan.ports == (8100, 8200)


def test_shouldKeepServiceSpecFactoryAvailableFromGenericModule():
    spec = ServiceSpec.from_values("api", [8100], [sys.executable, "-m", "http.server", "{port}"])

    assert spec.name == "api"
    assert spec.preferred_ports == (8100,)


def test_shouldExposeCapabilityBasedProvenanceValues():
    assert ProvenanceCapability.WRAPPER_ONLY.value == "wrapper_only"
    assert ProvenanceCapability.ENDPOINT_GRADE.value == "endpoint_grade"


def test_shouldPersistServiceStateProvenance():
    provenance = ProcessProvenance(
        wrapper_pid=12345,
        listener_pid=12346,
        command_fingerprint="command-sha",
        capability=ProvenanceCapability.OWNED_LISTENER,
    )
    state = ServiceState(
        "api",
        "127.0.0.1",
        8100,
        12345,
        ("python", "api.py"),
        "now",
        "out",
        "err",
        "authority",
        (),
        None,
        None,
        None,
        0.0,
        provenance,
    )

    assert asdict(state)["provenance"]["capability"] == ProvenanceCapability.OWNED_LISTENER


def test_shouldPersistReadyLifecycleStateWithServiceState():
    state = ServiceState(
        "api",
        "127.0.0.1",
        8100,
        12345,
        ("python", "api.py"),
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

    assert asdict(state)["lifecycle_state"] == LifecycleState.READY


def test_shouldUseInjectedPlatformOpsForPortResolutionAndReadiness(tmp_path):
    checked_ports = []
    checked_urls = []
    operations = PlatformOperationSet(
        is_port_available=lambda host, port: checked_ports.append(port) or port == 8200,
        http_status_ok=lambda url: checked_urls.append(url) or True,
    )
    lifecycle = ServiceLifecycleEngine("test-project", tmp_path, state_directory=tmp_path / "state", platform_ops=operations)
    spec = ServiceSpec.from_values("api", [8100, 8200], [sys.executable, "api.py"], health_url="http://{host}:{port}/health")

    port = lifecycle.resolve_port(spec)
    lifecycle.wait_ready(spec, port)

    assert port == 8200
    assert checked_ports == [8100, 8200]
    assert checked_urls
    assert set(checked_urls) == {"http://127.0.0.1:8200/health"}


def test_shouldFailClosedWhenCompatibilityStateFileIsCorrupt(tmp_path):
    lifecycle = ServiceLifecycleEngine("test-project", tmp_path, state_directory=tmp_path / "state")
    lifecycle.state_file.write_text("{", encoding="utf-8")

    try:
        lifecycle.stop_all(graceful_timeout_seconds=0.1)
    except LifecycleStateStoreError as error:
        assert error.failure_kind == "state_corrupt"
    else:
        raise AssertionError("corrupt lifecycle state should fail closed")
    assert lifecycle.state_file.exists()


def test_shouldEmitPreparedAndReadyEventsDuringRestart(monkeypatch, tmp_path):
    events = []
    lifecycle = ServiceLifecycleEngine("test-project", tmp_path, state_directory=tmp_path / "state", event_handler=events.append)
    spec = ServiceSpec.from_values("api", [8100], [sys.executable, "api.py"])

    monkeypatch.setattr(lifecycle, "prepare_startup", lambda service_specs, **kwargs: [])
    monkeypatch.setattr(lifecycle, "resolve_plan", lambda service_specs: {"api": 8100})
    monkeypatch.setattr(
        lifecycle,
        "start_service",
        lambda service_spec, port=None, **kwargs: ServiceState(
            service_spec.name,
            service_spec.host,
            int(port),
            12345,
            tuple(service_spec.command),
            "now",
            "out",
            "err",
            "authority",
            (),
            None,
            None,
            None,
            0.0,
            ProcessProvenance(wrapper_pid=12345, capability=ProvenanceCapability.REGISTERED_PROCESS),
        ),
    )

    lifecycle.restart_services((spec,), run_id="restart-1")

    assert [(event.service_name, event.state, event.reason) for event in events] == [
        ("api", LifecycleState.PREPARED, "port_resolved"),
        ("api", LifecycleState.READY, "readiness_passed"),
    ]
    assert events[1].provenance.wrapper_pid == 12345
    assert events[1].provenance.capability == ProvenanceCapability.REGISTERED_PROCESS


def test_shouldPersistPreparedThenAbortedWhenDirectStartFails(monkeypatch, tmp_path):
    observed_states = []
    operations = PlatformOperationSet(
        process_exists=lambda pid: True,
        process_matches_command=lambda pid, command: True,
        process_command_line=lambda pid: "python api.py",
        process_start_marker=lambda pid: "started",
    )
    lifecycle = ServiceLifecycleEngine("test-project", tmp_path, state_directory=tmp_path / "state", platform_ops=operations)
    spec = ServiceSpec.from_values("api", [8100], [sys.executable, "-c", "import time; time.sleep(10)"])

    def fail_after_prepared(service_spec, port, process=None):
        observed_states.append(lifecycle.read_state()["api"]["lifecycle_state"])
        raise TimeoutError("not ready")

    monkeypatch.setattr(lifecycle, "wait_ready", fail_after_prepared)

    try:
        lifecycle.start_service(spec, port=8100)
    except TimeoutError:
        pass
    else:
        raise AssertionError("start_service should propagate readiness failure")

    assert observed_states == [LifecycleState.PREPARED]
    assert lifecycle.read_state()["api"]["lifecycle_state"] == LifecycleState.ABORTED


class FakeProcess:
    def __init__(self, pid: int) -> None:
        self.pid = pid

    def poll(self):
        return None




def test_shouldEmitAbortedEventWhenRestartStartFails(monkeypatch, tmp_path):
    events = []
    lifecycle = ServiceLifecycleEngine("test-project", tmp_path, state_directory=tmp_path / "state", event_handler=events.append)
    spec = ServiceSpec.from_values("api", [8100], [sys.executable, "api.py"])

    monkeypatch.setattr(lifecycle, "prepare_startup", lambda service_specs, **kwargs: [])
    monkeypatch.setattr(lifecycle, "resolve_plan", lambda service_specs: {"api": 8100})

    def fail_start(service_spec, port=None, **kwargs):
        raise TimeoutError("not ready")

    monkeypatch.setattr(lifecycle, "start_service", fail_start)

    try:
        lifecycle.restart_services((spec,), run_id="restart-1")
    except TimeoutError:
        pass
    else:
        raise AssertionError("restart should fail when service start fails")

    assert [(event.service_name, event.state, event.reason) for event in events] == [
        ("api", LifecycleState.PREPARED, "port_resolved"),
        ("api", LifecycleState.ABORTED, "failed:TimeoutError"),
    ]


def test_restartServicesShouldEmitAbortedEventWithPersistedProvenanceWhenStartFails(monkeypatch, tmp_path):
    events = []
    operations = PlatformOperationSet(
        start_process=lambda *args, **kwargs: FakeProcess(12345),
        process_exists=lambda pid: True,
        process_matches_command=lambda pid, command: True,
        process_command_line=lambda pid: "python api.py",
        process_start_marker=lambda pid: "started:12345",
        terminate_process=lambda pid: None,
        wait_process_exit=lambda pid, timeout: True,
    )
    lifecycle = ServiceLifecycleEngine("project", tmp_path, state_directory=tmp_path / "state", event_handler=events.append, platform_ops=operations)
    spec = ServiceSpec.from_values("api", [8100], ["python", "api.py"], health_url="http://{host}:{port}/")

    monkeypatch.setattr(lifecycle, "resolve_plan", lambda specs: {"api": 8100})
    monkeypatch.setattr(lifecycle, "wait_ready", lambda service_spec, port, process=None: (_ for _ in ()).throw(TimeoutError("not ready")))

    try:
        lifecycle.restart_services((spec,), run_id="restart-1")
    except TimeoutError:
        pass
    else:
        raise AssertionError("restart should fail when start readiness fails")

    assert [(event.service_name, event.state, event.reason) for event in events] == [
        ("api", LifecycleState.PREPARED, "port_resolved"),
        ("api", LifecycleState.ABORTED, "failed:TimeoutError"),
    ]
    assert events[1].provenance.wrapper_pid == 12345
    assert lifecycle.read_state()["api"]["lifecycle_state"] == LifecycleState.ABORTED

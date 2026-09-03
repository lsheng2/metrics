from __future__ import annotations

import importlib.util
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import service_lifecycle_engine.engine as lifecycle_module
from service_lifecycle_engine import (
    LifecycleEvent,
    LifecycleOperationResult,
    LifecycleState,
    LifecycleStateStoreError,
    LifecycleTransition,
    LiveServiceResolution,
    LiveServiceResolutionSource,
    ProvenanceCapability,
    ResolvedPortPlan,
    ServiceLifecycleEngine,
    ServiceSpec,
    ServiceState,
    StopResult,
    StopSource,
)


def test_shouldExposeGenericEngineImportWithoutPortLifecycleAlias():
    assert ServiceLifecycleEngine.__name__ == "ServiceLifecycleEngine"
    assert not hasattr(sys.modules["service_lifecycle_engine"], "PortLifecycle")


def test_legacyPortLifecyclePackageShouldNotRemainPublicImport():
    assert importlib.util.find_spec("port_lifecycle") is None


def test_shouldSerializeLifecycleModelsWithStableGenericValues():
    event = LifecycleEvent(
        service_name="api",
        state=LifecycleState.ABORTED,
        reason="readiness_timeout",
        generation=3,
        host="127.0.0.1",
        port=8100,
    )

    assert asdict(event) == {
        "service_name": "api",
        "state": LifecycleState.ABORTED,
        "reason": "readiness_timeout",
        "generation": 3,
        "host": "127.0.0.1",
        "port": 8100,
        "metadata": {},
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


def test_shouldReportForceByPortSourceSeparatelyFromKillEscalation(monkeypatch, tmp_path):
    lifecycle = ServiceLifecycleEngine("test-project", tmp_path, state_directory=tmp_path / "state")
    process_states = iter((True, False))

    monkeypatch.setattr(lifecycle_module, "process_exists", lambda pid: next(process_states))
    monkeypatch.setattr(lifecycle_module, "terminate_process", lambda pid: None)
    monkeypatch.setattr(lifecycle_module, "wait_process_exit", lambda pid, timeout: True)

    result = lifecycle._stop_process("api", 8100, 12345, 0.1, "force_by_port")

    assert result.stop_source == StopSource.FORCE_BY_PORT
    assert result.force_requested is True
    assert result.forced is False


def test_shouldEmitPreparedAndReadyEventsDuringRestart(monkeypatch, tmp_path):
    events = []
    lifecycle = ServiceLifecycleEngine("test-project", tmp_path, state_directory=tmp_path / "state", event_handler=events.append)
    spec = ServiceSpec.from_values("api", [8100], [sys.executable, "api.py"])

    monkeypatch.setattr(lifecycle, "prepare_startup", lambda service_specs, **kwargs: [])
    monkeypatch.setattr(lifecycle, "resolve_plan", lambda service_specs: {"api": 8100})
    monkeypatch.setattr(
        lifecycle,
        "start_service",
        lambda service_spec, port=None: ServiceState(
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
        ),
    )

    lifecycle.restart_services((spec,), run_id="restart-1")

    assert [(event.service_name, event.state, event.reason) for event in events] == [
        ("api", LifecycleState.PREPARED, "port_resolved"),
        ("api", LifecycleState.READY, "readiness_passed"),
    ]


def test_shouldEmitAbortedEventWhenRestartStartFails(monkeypatch, tmp_path):
    events = []
    lifecycle = ServiceLifecycleEngine("test-project", tmp_path, state_directory=tmp_path / "state", event_handler=events.append)
    spec = ServiceSpec.from_values("api", [8100], [sys.executable, "api.py"])

    monkeypatch.setattr(lifecycle, "prepare_startup", lambda service_specs, **kwargs: [])
    monkeypatch.setattr(lifecycle, "resolve_plan", lambda service_specs: {"api": 8100})

    def fail_start(service_spec, port=None):
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

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from service_lifecycle_engine import (
    FilesystemLifecycleStateStore,
    HealthProbeProvider,
    HealthProbeRequirement,
    LaunchMetadataProvider,
    LifecycleState,
    ProcessMetadataProvider,
    ServiceDiagnosticCode,
    ServiceHealthSnapshot,
    ServiceHealthStatus,
    ServiceLaunchMetadata,
    ServiceLifecycleEngine,
    ServiceLiveSnapshot,
    ServiceOperatorAction,
    ServiceOperatorLink,
    build_external_service_state,
    build_service_health_snapshot,
    health_requirement_affects_liveness,
    health_requirement_affects_startup,
    merge_service_launch_metadata,
    pid_is_alive,
    read_pid_file_value,
    resolve_lifecycle_service_launch_metadata,
    resolve_pid_file_launch_metadata,
    resolve_service_health_status,
)
from service_lifecycle_engine.conformance import (
    ServiceLifecycleConformanceFixture,
    assert_service_lifecycle_conformance,
    run_service_lifecycle_conformance_checks,
)
from service_lifecycle_engine.lifecycle_state_cli import main as lifecycle_state_cli_main


class FakeProcessProvider:
    def pid_is_alive(self, pid: int | None) -> bool:
        return pid == 4242

    def read_process_started_at(self, pid: int) -> str | None:
        return "2026-09-09T03:34:13.180000+00:00" if pid == 4242 else None


class FakeLaunchProvider:
    def resolve_launch_metadata(self, service_name: str) -> ServiceLaunchMetadata:
        return ServiceLaunchMetadata(
            started_at="2026-09-09T03:34:13.180000+00:00",
            source=f"{service_name}-launcher",
        )


class FakeHealthProvider:
    def probe_health(self, service_name: str) -> ServiceHealthSnapshot:
        return build_service_health_snapshot(
            service_name=service_name,
            checked_at="2026-09-09T03:40:00+00:00",
            reachable=True,
            requirement=HealthProbeRequirement.REQUIRED_FOR_LIVE_STATUS,
        )


def test_live_metadata_shouldExposeGenericHealthSnapshotWithCanonicalReason() -> None:
    snapshot = build_service_health_snapshot(
        service_name="api",
        checked_at="2026-09-09T03:40:00+00:00",
        explicit_status="queue_saturated",
        probe_name="readiness",
        diagnostics=(ServiceDiagnosticCode.PROBE_TIMEOUT,),
    )

    assert snapshot.status == ServiceHealthStatus.DEGRADED
    assert snapshot.reason == "queue_saturated"
    assert snapshot.special_state == "queue_saturated"
    assert snapshot.as_dict()["diagnostics"] == ["probe_timeout"]


def test_live_metadata_shouldClassifyGenericHealthAndProbeRequirements() -> None:
    assert resolve_service_health_status(reachable=True) == ServiceHealthStatus.READY
    assert resolve_service_health_status(reachable=True, unhealthy_count=1) == ServiceHealthStatus.DEGRADED
    assert resolve_service_health_status(reachable=False, http_status=401) == ServiceHealthStatus.AUTH_REQUIRED
    assert resolve_service_health_status(reachable=False) == ServiceHealthStatus.UNREACHABLE
    assert health_requirement_affects_startup(HealthProbeRequirement.REQUIRED_FOR_STARTUP) is True
    assert health_requirement_affects_liveness(HealthProbeRequirement.REQUIRED_FOR_LIVE_STATUS) is True
    assert health_requirement_affects_startup(HealthProbeRequirement.OPTIONAL_OBSERVABILITY) is False


def test_live_metadata_shouldResolveLaunchMetadataFromLifecycleAndPidProviders(tmp_path: Path) -> None:
    pid_file = tmp_path / "api.pid"
    pid_file.write_text('{"pid": 4242}\n', encoding="utf-8")
    lifecycle_metadata = resolve_lifecycle_service_launch_metadata(
        {"api": {"lifecycle_state": "ready", "started_at": "2026-09-09T03:34:13.180000+00:00"}},
        "api",
    )
    pid_metadata = resolve_pid_file_launch_metadata(
        pid_file,
        source="test-launcher",
        process_provider=FakeProcessProvider(),
    )

    assert lifecycle_metadata.started_at == "2026-09-09T03:34:13.180000+00:00"
    assert pid_metadata.started_at == "2026-09-09T03:34:13.180000+00:00"
    assert isinstance(FakeProcessProvider(), ProcessMetadataProvider)
    assert isinstance(FakeLaunchProvider(), LaunchMetadataProvider)
    assert isinstance(FakeHealthProvider(), HealthProbeProvider)


def test_live_metadata_shouldFailClosedForNonLiveLifecycleState() -> None:
    metadata = resolve_lifecycle_service_launch_metadata(
        {"api": {"lifecycle_state": "stopped", "started_at": "2026-09-09T03:34:13.180000+00:00"}},
        "api",
    )

    assert metadata.started_at == ""
    assert metadata.diagnostics == (ServiceDiagnosticCode.STATE_NOT_LIVE,)


def test_live_metadata_shouldMergeLaunchMetadataWithoutOverwritingExistingValue() -> None:
    metadata = ServiceLaunchMetadata(started_at="2026-09-09T03:34:13.180000+00:00", source="test-launcher")
    empty_payload = merge_service_launch_metadata({"service_id": "api", "started_at": ""}, metadata)
    existing_payload = merge_service_launch_metadata({"service_id": "api", "started_at": "existing"}, metadata)

    assert empty_payload["started_at"] == "2026-09-09T03:34:13.180000+00:00"
    assert empty_payload["launch_metadata_source"] == "test-launcher"
    assert existing_payload["started_at"] == "existing"
    assert "launch_metadata_source" not in existing_payload


def test_live_metadata_shouldPreserveLaunchMetadataSourceAndDiagnosticsWhenNoStartedAt() -> None:
    payload = merge_service_launch_metadata(
        {
            "service_id": "api",
            "launch_metadata_diagnostics": ["state_corrupt"],
        },
        ServiceLaunchMetadata(
            source="service-lifecycle-engine",
            diagnostics=(ServiceDiagnosticCode.STATE_NOT_LIVE, "state_corrupt"),
        ),
    )

    assert payload["launch_metadata_source"] == "service-lifecycle-engine"
    assert payload["launch_metadata_diagnostics"] == ["state_corrupt", "state_not_live"]


def test_live_metadata_shouldSerializeDisplaySnapshotWithoutEndpointAuthority() -> None:
    snapshot = ServiceLiveSnapshot(
        service_name="api",
        configured=True,
        lifecycle_state=LifecycleState.READY,
        health=build_service_health_snapshot(
            service_name="api",
            checked_at="2026-09-09T03:40:00+00:00",
            reachable=True,
        ),
        launch_metadata=ServiceLaunchMetadata(
            started_at="2026-09-09T03:34:13.180000+00:00",
            source="test-launcher",
        ),
        base_url="http://127.0.0.1:8123",
        health_url="http://127.0.0.1:8123/health",
        links=(ServiceOperatorLink(rel="health", href="http://127.0.0.1:8123/health"),),
        actions=(ServiceOperatorAction(kind="open_url", label="Open"),),
        diagnostics=(ServiceDiagnosticCode.NOT_REGISTERED,),
    )

    payload = snapshot.as_dict()

    assert payload["service_id"] == "api"
    assert payload["health"]["status"] == "ready"
    assert payload["launch_metadata"]["source"] == "test-launcher"
    assert payload["links"] == [{"rel": "health", "href": "http://127.0.0.1:8123/health", "label": ""}]
    assert payload["actions"] == [{"kind": "open_url", "label": "Open", "href": ""}]
    assert "endpoint_authority" not in payload


def test_live_metadata_shouldProvideReusableConformanceChecks() -> None:
    fixture = ServiceLifecycleConformanceFixture(
        service_name="api",
        live_pid=4242,
        dead_pid=4343,
        process_provider=FakeProcessProvider(),
        launch_provider=FakeLaunchProvider(),
        health_provider=FakeHealthProvider(),
    )

    results = run_service_lifecycle_conformance_checks(fixture)

    assert [result.name for result in results] == [
        "process_provider",
        "launch_provider",
        "health_provider",
        "health_requirements",
        "live_snapshot",
    ]
    assert all(result.passed for result in results)
    assert_service_lifecycle_conformance(fixture)


def test_live_metadata_shouldDetectForbiddenConformancePayloadMarkers() -> None:
    fixture = ServiceLifecycleConformanceFixture(
        service_name="api",
        live_pid=4242,
        dead_pid=4343,
        process_provider=FakeProcessProvider(),
        launch_provider=FakeLaunchProvider(),
        health_provider=FakeHealthProvider(),
        forbidden_payload_markers=("api-launcher",),
    )

    failed = [result for result in run_service_lifecycle_conformance_checks(fixture) if not result.passed]

    assert [result.name for result in failed] == ["live_snapshot"]
    assert "forbidden payload marker" in failed[0].detail


def test_live_metadata_shouldBuildExternalStateAndPreservePriorLaunchTimeOnStop() -> None:
    state = build_external_service_state(
        service_name="api",
        lifecycle_state=LifecycleState.STOPPED,
        host="127.0.0.1",
        port=8123,
        prior_state={
            "pid": 4242,
            "started_at": "2026-09-09T03:34:13.180000+00:00",
            "stdout_log": "/tmp/api.out.log",
        },
        now=lambda: "2026-09-09T03:40:00+00:00",
    )

    assert state.lifecycle_state == LifecycleState.STOPPED
    assert state.pid == 4242
    assert state.started_at == "2026-09-09T03:34:13.180000+00:00"
    assert state.stdout_log == "/tmp/api.out.log"


def test_live_metadata_shouldRecordExternalLauncherStateThroughCli(tmp_path: Path) -> None:
    result = lifecycle_state_cli_main(
        [
            "ready",
            "--workspace-root",
            str(tmp_path),
            "--project-name",
            "local-tools",
            "--service-id",
            "api",
            "--host",
            "127.0.0.1",
            "--port",
            "8123",
            "--process-id",
            "4242",
            "--listener-process-id",
            "4343",
            "--started-at",
            "2026-09-09T03:34:13.180000+00:00",
            "--health-url",
            "http://127.0.0.1:8123/health",
            "--launcher-id",
            "test-launcher",
            "--launch-mode",
            "detached",
            "--process-start-time-ticks",
            "start-4343",
            "--command-fingerprint",
            "cmd-hash",
        ]
    )
    store = FilesystemLifecycleStateStore(tmp_path / "state" / "service-lifecycle-engine")
    payload = store.read_json(store.base_directory / "local-tools-default.json")
    service = payload["services"]["api"]

    assert result == 0
    assert service["lifecycle_state"] == LifecycleState.READY.value
    assert service["started_at"] == "2026-09-09T03:34:13.180000+00:00"
    assert service["pid"] == 4242
    assert service["provenance"]["listener_pid"] == 4343
    assert json.loads(str(service["provenance"]["command_line"])) == {
        "launcher_id": "test-launcher",
        "launch_mode": "detached",
    }


def test_live_metadata_shouldKeepRootHelpersSafeOnUnsupportedProcessInputs(tmp_path: Path) -> None:
    pid_file = tmp_path / "api.pid"
    pid_file.write_text("4242\n", encoding="utf-8")

    assert read_pid_file_value(pid_file) == 4242
    assert pid_is_alive(-1) is False

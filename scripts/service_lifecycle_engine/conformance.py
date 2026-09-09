from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .health import HealthProbeRequirement, HealthProbeProvider, ServiceHealthSnapshot
from .health import health_requirement_affects_liveness, health_requirement_affects_startup
from .live_status import LaunchMetadataProvider, ProcessMetadataProvider, ServiceLaunchMetadata, ServiceLiveSnapshot
from .models import LifecycleState


@dataclass(frozen=True, slots=True)
class ServiceLifecycleConformanceFixture:
    service_name: str
    live_pid: int
    dead_pid: int
    process_provider: ProcessMetadataProvider
    launch_provider: LaunchMetadataProvider
    health_provider: HealthProbeProvider
    forbidden_payload_markers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ServiceLifecycleConformanceResult:
    name: str
    passed: bool
    detail: str = ""


def run_service_lifecycle_conformance_checks(
    fixture: ServiceLifecycleConformanceFixture,
) -> tuple[ServiceLifecycleConformanceResult, ...]:
    process_result = _check_process_provider(fixture)
    launch_result = _check_launch_provider(fixture)
    health_result = _check_health_provider(fixture)
    results = [process_result, launch_result, health_result, _check_health_requirements()]
    if launch_result.passed and health_result.passed:
        results.append(_check_live_snapshot(fixture))
    else:
        results.append(ServiceLifecycleConformanceResult("live_snapshot", True, "skipped because provider checks failed"))
    return tuple(results)


def assert_service_lifecycle_conformance(fixture: ServiceLifecycleConformanceFixture) -> None:
    failures = [result for result in run_service_lifecycle_conformance_checks(fixture) if not result.passed]
    if failures:
        detail = "; ".join(f"{failure.name}: {failure.detail}" for failure in failures)
        raise AssertionError(detail)


def _check_process_provider(fixture: ServiceLifecycleConformanceFixture) -> ServiceLifecycleConformanceResult:
    provider = fixture.process_provider
    if not provider.pid_is_alive(fixture.live_pid):
        return ServiceLifecycleConformanceResult("process_provider", False, "live_pid was not reported alive")
    if provider.pid_is_alive(fixture.dead_pid):
        return ServiceLifecycleConformanceResult("process_provider", False, "dead_pid was reported alive")
    if not provider.read_process_started_at(fixture.live_pid):
        return ServiceLifecycleConformanceResult("process_provider", False, "live_pid started_at was empty")
    return ServiceLifecycleConformanceResult("process_provider", True)


def _check_launch_provider(fixture: ServiceLifecycleConformanceFixture) -> ServiceLifecycleConformanceResult:
    metadata = fixture.launch_provider.resolve_launch_metadata(fixture.service_name)
    if not isinstance(metadata, ServiceLaunchMetadata):
        return ServiceLifecycleConformanceResult("launch_provider", False, "provider did not return ServiceLaunchMetadata")
    if not metadata.started_at:
        return ServiceLifecycleConformanceResult("launch_provider", False, "started_at was empty")
    if not metadata.source:
        return ServiceLifecycleConformanceResult("launch_provider", False, "source was empty")
    return ServiceLifecycleConformanceResult("launch_provider", True)


def _check_health_provider(fixture: ServiceLifecycleConformanceFixture) -> ServiceLifecycleConformanceResult:
    snapshot = fixture.health_provider.probe_health(fixture.service_name)
    if not isinstance(snapshot, ServiceHealthSnapshot):
        return ServiceLifecycleConformanceResult("health_provider", False, "provider did not return ServiceHealthSnapshot")
    if snapshot.service_name != fixture.service_name:
        return ServiceLifecycleConformanceResult("health_provider", False, "snapshot service name did not match fixture")
    if not snapshot.checked_at:
        return ServiceLifecycleConformanceResult("health_provider", False, "checked_at was empty")
    return ServiceLifecycleConformanceResult("health_provider", True)


def _check_health_requirements() -> ServiceLifecycleConformanceResult:
    if not health_requirement_affects_startup(HealthProbeRequirement.REQUIRED_FOR_STARTUP):
        return ServiceLifecycleConformanceResult("health_requirements", False, "startup requirement did not affect startup")
    if not health_requirement_affects_liveness(HealthProbeRequirement.REQUIRED_FOR_STARTUP):
        return ServiceLifecycleConformanceResult("health_requirements", False, "startup requirement did not affect liveness")
    if health_requirement_affects_startup(HealthProbeRequirement.OPTIONAL_OBSERVABILITY):
        return ServiceLifecycleConformanceResult("health_requirements", False, "optional observability affected startup")
    if health_requirement_affects_liveness(HealthProbeRequirement.ADVISORY):
        return ServiceLifecycleConformanceResult("health_requirements", False, "advisory affected liveness")
    return ServiceLifecycleConformanceResult("health_requirements", True)


def _check_live_snapshot(fixture: ServiceLifecycleConformanceFixture) -> ServiceLifecycleConformanceResult:
    metadata = fixture.launch_provider.resolve_launch_metadata(fixture.service_name)
    health = fixture.health_provider.probe_health(fixture.service_name)
    snapshot = ServiceLiveSnapshot(
        service_name=fixture.service_name,
        configured=True,
        lifecycle_state=LifecycleState.READY,
        health=health,
        launch_metadata=metadata,
        base_url="http://127.0.0.1:8123",
    )
    payload = snapshot.as_dict()
    if "endpoint_authority" in payload:
        return ServiceLifecycleConformanceResult("live_snapshot", False, "snapshot exposed endpoint authority")
    forbidden_marker = _first_forbidden_payload_marker(payload, fixture.forbidden_payload_markers)
    if forbidden_marker:
        return ServiceLifecycleConformanceResult(
            "live_snapshot",
            False,
            f"snapshot included forbidden payload marker: {forbidden_marker}",
        )
    return ServiceLifecycleConformanceResult("live_snapshot", True)


def _first_forbidden_payload_marker(payload: dict[str, Any], markers: tuple[str, ...]) -> str:
    haystack = str(payload).lower()
    return next((marker for marker in markers if marker.lower() in haystack), "")


__all__ = [
    "ServiceLifecycleConformanceFixture",
    "ServiceLifecycleConformanceResult",
    "assert_service_lifecycle_conformance",
    "run_service_lifecycle_conformance_checks",
]

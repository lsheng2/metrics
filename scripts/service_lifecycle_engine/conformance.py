from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Any

from .diagnostics import ServiceDiagnosticCode
from .health import (
    HealthProbeRequirement,
    HealthProbeProvider,
    ServiceHealthSnapshot,
    health_requirement_affects_liveness,
    health_requirement_affects_startup,
)
from .live_status import (
    LaunchMetadataProvider,
    ProcessMetadataProvider,
    ServiceLaunchMetadata,
    ServiceLiveSnapshot,
)
from .models import LifecycleState
from .startup_models import (
    ServiceActivationPolicy,
    ServiceDependency,
    ServiceDependencyRequirement,
    ServiceLaunchStatus,
    ServiceStartNode,
    ServiceStartupGraphError,
)
from .startup_orchestration import plan_service_startup, start_services_in_dependency_order


@dataclass(frozen=True, slots=True)
class ServiceLifecycleConformanceFixture:
    service_name: str
    live_pid: int
    dead_pid: int
    process_provider: ProcessMetadataProvider
    launch_provider: LaunchMetadataProvider
    health_provider: HealthProbeProvider
    startup_nodes: tuple[ServiceStartNode, ...] = ()
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
    results = [
        process_result,
        launch_result,
        health_result,
        _check_health_requirements(),
        *run_startup_orchestration_conformance_checks(
            startup_nodes=fixture.startup_nodes,
            service_name=fixture.service_name,
        ),
    ]
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


def run_startup_orchestration_conformance_checks(
    *,
    startup_nodes: tuple[ServiceStartNode, ...] = (),
    service_name: str = "dashboard",
) -> tuple[ServiceLifecycleConformanceResult, ...]:
    return (
        _check_startup_project_graph(startup_nodes, service_name),
        _check_startup_required_failure_skip(),
        _check_startup_optional_failure_non_blocking(),
        _check_startup_lazy_manual_selection(),
        _check_startup_invalid_graphs(),
        _check_startup_parallelism_and_ordering(),
    )


def assert_startup_orchestration_conformance(
    *,
    startup_nodes: tuple[ServiceStartNode, ...] = (),
    service_name: str = "dashboard",
) -> None:
    failures = [
        result
        for result in run_startup_orchestration_conformance_checks(
            startup_nodes=startup_nodes,
            service_name=service_name,
        )
        if not result.passed
    ]
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


def _check_startup_project_graph(
    startup_nodes: tuple[ServiceStartNode, ...],
    service_name: str,
) -> ServiceLifecycleConformanceResult:
    nodes = startup_nodes or (ServiceStartNode(service_name),)
    try:
        plan = plan_service_startup(nodes, include_services=(service_name,))
        result = start_services_in_dependency_order(
            nodes,
            lambda node: {"service": node.service_name},
            include_services=(service_name,),
            max_parallelism=2,
        )
    except Exception as error:
        return ServiceLifecycleConformanceResult("startup_project_graph", False, f"{type(error).__name__}: {error}")
    if service_name not in plan.service_names:
        return ServiceLifecycleConformanceResult("startup_project_graph", False, "fixture service was not included in startup plan")
    if not result.succeeded:
        return ServiceLifecycleConformanceResult("startup_project_graph", False, "startup graph result did not succeed")
    if service_name not in {attempt.service_name for attempt in result.attempts}:
        return ServiceLifecycleConformanceResult("startup_project_graph", False, "fixture service launch attempt was missing")
    return ServiceLifecycleConformanceResult("startup_project_graph", True)


def _check_startup_required_failure_skip() -> ServiceLifecycleConformanceResult:
    calls: list[str] = []

    def start(node: ServiceStartNode) -> object:
        calls.append(node.service_name)
        if node.service_name == "database":
            raise RuntimeError("database unavailable")
        return {"service": node.service_name}

    result = start_services_in_dependency_order(
        (
            ServiceStartNode("database"),
            ServiceStartNode("api", dependencies=(ServiceDependency("database"),)),
            ServiceStartNode("worker", dependencies=(ServiceDependency("api"),)),
        ),
        start,
    )
    if calls != ["database"]:
        return ServiceLifecycleConformanceResult("startup_required_failure_skip", False, f"unexpected starter calls: {calls}")
    if result.attempt_for("api").status != ServiceLaunchStatus.SKIPPED:
        return ServiceLifecycleConformanceResult("startup_required_failure_skip", False, "required dependent was not skipped")
    if ServiceDiagnosticCode.DEPENDENCY_FAILED not in result.attempt_for("api").diagnostics:
        return ServiceLifecycleConformanceResult("startup_required_failure_skip", False, "skip diagnostic missing")
    return ServiceLifecycleConformanceResult("startup_required_failure_skip", True)


def _check_startup_optional_failure_non_blocking() -> ServiceLifecycleConformanceResult:
    calls: list[str] = []

    def start(node: ServiceStartNode) -> object:
        calls.append(node.service_name)
        if node.service_name == "cache":
            raise RuntimeError("cache unavailable")
        return {"service": node.service_name}

    result = start_services_in_dependency_order(
        (
            ServiceStartNode("cache"),
            ServiceStartNode(
                "api",
                dependencies=(ServiceDependency("cache", requirement=ServiceDependencyRequirement.OPTIONAL),),
            ),
        ),
        start,
    )
    if calls != ["cache", "api"]:
        return ServiceLifecycleConformanceResult("startup_optional_failure_non_blocking", False, f"unexpected starter calls: {calls}")
    if result.attempt_for("api").status != ServiceLaunchStatus.SUCCEEDED:
        return ServiceLifecycleConformanceResult("startup_optional_failure_non_blocking", False, "optional dependent did not start")
    if ServiceDiagnosticCode.DEPENDENCY_OPTIONAL_FAILED not in result.attempt_for("api").diagnostics:
        return ServiceLifecycleConformanceResult("startup_optional_failure_non_blocking", False, "optional diagnostic missing")
    return ServiceLifecycleConformanceResult("startup_optional_failure_non_blocking", True)


def _check_startup_lazy_manual_selection() -> ServiceLifecycleConformanceResult:
    nodes = (
        ServiceStartNode("database"),
        ServiceStartNode("api", dependencies=(ServiceDependency("database"),)),
        ServiceStartNode("reporting", dependencies=(ServiceDependency("database"),), activation_policy=ServiceActivationPolicy.LAZY),
        ServiceStartNode("admin", activation_policy=ServiceActivationPolicy.MANUAL),
        ServiceStartNode(
            "dashboard",
            dependencies=(ServiceDependency("reporting", requirement=ServiceDependencyRequirement.OPTIONAL),),
        ),
    )
    default_plan = plan_service_startup(nodes)
    reporting_plan = plan_service_startup(nodes, include_services=("reporting",))
    if default_plan.service_names != ("database", "api", "dashboard"):
        return ServiceLifecycleConformanceResult("startup_lazy_manual_selection", False, f"unexpected default plan: {default_plan.service_names}")
    if reporting_plan.service_names != ("database", "reporting"):
        return ServiceLifecycleConformanceResult("startup_lazy_manual_selection", False, f"unexpected explicit plan: {reporting_plan.service_names}")
    return ServiceLifecycleConformanceResult("startup_lazy_manual_selection", True)


def _check_startup_invalid_graphs() -> ServiceLifecycleConformanceResult:
    try:
        plan_service_startup((ServiceStartNode("api", dependencies=(ServiceDependency("missing"),)),))
    except ServiceStartupGraphError as error:
        if error.failure_kind != "unknown_dependency":
            return ServiceLifecycleConformanceResult("startup_invalid_graphs", False, f"wrong unknown failure: {error.failure_kind}")
    else:
        return ServiceLifecycleConformanceResult("startup_invalid_graphs", False, "unknown dependency was accepted")

    try:
        plan_service_startup(
            (
                ServiceStartNode("api", dependencies=(ServiceDependency("worker"),)),
                ServiceStartNode("worker", dependencies=(ServiceDependency("api"),)),
            )
        )
    except ServiceStartupGraphError as error:
        if error.failure_kind != "dependency_cycle":
            return ServiceLifecycleConformanceResult("startup_invalid_graphs", False, f"wrong cycle failure: {error.failure_kind}")
    else:
        return ServiceLifecycleConformanceResult("startup_invalid_graphs", False, "dependency cycle was accepted")
    return ServiceLifecycleConformanceResult("startup_invalid_graphs", True)


def _check_startup_parallelism_and_ordering() -> ServiceLifecycleConformanceResult:
    lock = threading.Lock()
    active = 0
    observed_max = 0

    def start(node: ServiceStartNode) -> object:
        nonlocal active, observed_max
        with lock:
            active += 1
            observed_max = max(observed_max, active)
        time.sleep(0.01)
        with lock:
            active -= 1
        return {"service": node.service_name}

    result = start_services_in_dependency_order(
        (ServiceStartNode("one"), ServiceStartNode("two"), ServiceStartNode("three")),
        start,
        max_parallelism=2,
    )
    if observed_max > 2:
        return ServiceLifecycleConformanceResult("startup_parallelism_and_ordering", False, f"observed max parallelism {observed_max}")
    if tuple(attempt.service_name for attempt in result.attempts) != ("one", "two", "three"):
        return ServiceLifecycleConformanceResult("startup_parallelism_and_ordering", False, "result ordering was not deterministic")
    return ServiceLifecycleConformanceResult("startup_parallelism_and_ordering", True)


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
    "assert_startup_orchestration_conformance",
    "assert_service_lifecycle_conformance",
    "run_startup_orchestration_conformance_checks",
    "run_service_lifecycle_conformance_checks",
]

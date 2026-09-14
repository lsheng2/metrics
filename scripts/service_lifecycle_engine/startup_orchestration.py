from __future__ import annotations

import time
import uuid
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime

from .diagnostics import ServiceDiagnosticCode
from .startup_models import (
    NowCallback,
    ServiceActivationPolicy,
    ServiceDependencyRequirement,
    ServiceLaunchAttempt,
    ServiceLaunchStatus,
    ServiceStartGraphResult,
    ServiceStartNode,
    ServiceStartPlan,
    ServiceStartWave,
    ServiceStartupGraphError,
    StartServiceCallback,
    TimerCallback,
    validated_service_name,
)


def plan_service_startup(
    nodes: Sequence[ServiceStartNode],
    *,
    include_services: Sequence[str] | None = None,
) -> ServiceStartPlan:
    ordered_nodes = tuple(nodes)
    nodes_by_name = _nodes_by_name(ordered_nodes)
    _validate_dependencies(ordered_nodes, nodes_by_name)
    included_names = _included_service_names(ordered_nodes, nodes_by_name, include_services)
    included_nodes = tuple(node for node in ordered_nodes if node.service_name in included_names)
    waves = _build_waves(included_nodes)
    return ServiceStartPlan(included_nodes, waves)


def start_services_in_dependency_order(
    nodes: Sequence[ServiceStartNode],
    start: StartServiceCallback,
    *,
    max_parallelism: int = 4,
    include_services: Sequence[str] | None = None,
    run_id: str | None = None,
    now: NowCallback | None = None,
    timer: TimerCallback | None = None,
) -> ServiceStartGraphResult:
    if max_parallelism < 1:
        raise ServiceStartupGraphError(
            "max_parallelism must be at least 1",
            failure_kind="invalid_parallelism",
            diagnostics=("invalid_parallelism",),
        )
    clock = now or _utc_now
    monotonic = timer or time.perf_counter
    start_run_id = run_id or str(uuid.uuid4())
    plan = plan_service_startup(nodes, include_services=include_services)
    attempts: list[ServiceLaunchAttempt] = []
    attempts_by_name: dict[str, ServiceLaunchAttempt] = {}

    for wave in plan.waves:
        eligible: list[tuple[ServiceStartNode, tuple[ServiceDiagnosticCode | str, ...]]] = []
        for service_name in wave.service_names:
            node = plan.node_for(service_name)
            required_failures = _dependency_failures(node, attempts_by_name, ServiceDependencyRequirement.REQUIRED)
            if required_failures:
                attempt = _skipped_attempt(node.service_name, required_failures, clock)
                attempts.append(attempt)
                attempts_by_name[node.service_name] = attempt
                continue
            eligible.append((node, _optional_dependency_diagnostics(node, attempts_by_name)))

        wave_attempts: dict[str, ServiceLaunchAttempt] = {}
        with ThreadPoolExecutor(max_workers=max_parallelism) as executor:
            futures = {
                executor.submit(_launch_node, node, start, clock, monotonic, diagnostics): node.service_name
                for node, diagnostics in eligible
            }
            for future in as_completed(futures):
                wave_attempts[futures[future]] = future.result()
        for service_name in wave.service_names:
            if service_name in wave_attempts:
                attempt = wave_attempts[service_name]
                attempts.append(attempt)
                attempts_by_name[service_name] = attempt

    return ServiceStartGraphResult(start_run_id, plan, tuple(attempts))


def _nodes_by_name(nodes: Sequence[ServiceStartNode]) -> dict[str, ServiceStartNode]:
    nodes_by_name: dict[str, ServiceStartNode] = {}
    for node in nodes:
        if node.service_name in nodes_by_name:
            raise ServiceStartupGraphError(
                f"Duplicate service id in startup graph: {node.service_name}",
                failure_kind="duplicate_service",
                diagnostics=(ServiceDiagnosticCode.DUPLICATE_SERVICE,),
            )
        nodes_by_name[node.service_name] = node
    return nodes_by_name


def _validate_dependencies(nodes: Sequence[ServiceStartNode], nodes_by_name: Mapping[str, ServiceStartNode]) -> None:
    for node in nodes:
        for dependency in node.dependencies:
            if dependency.service_name not in nodes_by_name:
                raise ServiceStartupGraphError(
                    f"Unknown dependency {dependency.service_name!r} for service {node.service_name!r}",
                    failure_kind="unknown_dependency",
                    diagnostics=(ServiceDiagnosticCode.DEPENDENCY_UNKNOWN,),
                )


def _included_service_names(
    nodes: Sequence[ServiceStartNode],
    nodes_by_name: Mapping[str, ServiceStartNode],
    include_services: Sequence[str] | None,
) -> set[str]:
    if include_services is None:
        selected = {node.service_name for node in nodes if node.activation_policy == ServiceActivationPolicy.EAGER}
    else:
        selected = {validated_service_name(service_name) for service_name in include_services}
        missing = selected.difference(nodes_by_name)
        if missing:
            raise ServiceStartupGraphError(
                f"Unknown selected service {sorted(missing)[0]!r}",
                failure_kind="unknown_dependency",
                diagnostics=(ServiceDiagnosticCode.DEPENDENCY_UNKNOWN,),
            )

    included: set[str] = set()
    for service_name in selected:
        _include_with_dependencies(service_name, nodes_by_name, included)
    return included


def _include_with_dependencies(
    service_name: str,
    nodes_by_name: Mapping[str, ServiceStartNode],
    included: set[str],
) -> None:
    if service_name in included:
        return
    included.add(service_name)
    for dependency in nodes_by_name[service_name].dependencies:
        if dependency.requirement == ServiceDependencyRequirement.REQUIRED:
            _include_with_dependencies(dependency.service_name, nodes_by_name, included)


def _build_waves(nodes: Sequence[ServiceStartNode]) -> tuple[ServiceStartWave, ...]:
    order = tuple(node.service_name for node in nodes)
    remaining = set(order)
    nodes_by_name = {node.service_name: node for node in nodes}
    waves: list[ServiceStartWave] = []

    while remaining:
        ready = tuple(
            service_name
            for service_name in order
            if service_name in remaining and all(dependency.service_name not in remaining for dependency in nodes_by_name[service_name].dependencies)
        )
        if not ready:
            raise ServiceStartupGraphError(
                "Dependency cycle in service startup graph",
                failure_kind="dependency_cycle",
                diagnostics=(ServiceDiagnosticCode.DEPENDENCY_CYCLE,),
            )
        waves.append(ServiceStartWave(len(waves), ready))
        remaining.difference_update(ready)
    return tuple(waves)


def _dependency_failures(
    node: ServiceStartNode,
    attempts_by_name: Mapping[str, ServiceLaunchAttempt],
    requirement: ServiceDependencyRequirement,
) -> tuple[str, ...]:
    failures: list[str] = []
    for dependency in node.dependencies:
        if dependency.requirement != requirement:
            continue
        attempt = attempts_by_name.get(dependency.service_name)
        if attempt is not None and attempt.status != ServiceLaunchStatus.SUCCEEDED:
            failures.append(dependency.service_name)
    return tuple(failures)


def _optional_dependency_diagnostics(
    node: ServiceStartNode,
    attempts_by_name: Mapping[str, ServiceLaunchAttempt],
) -> tuple[ServiceDiagnosticCode | str, ...]:
    failures = _dependency_failures(node, attempts_by_name, ServiceDependencyRequirement.OPTIONAL)
    diagnostics: list[ServiceDiagnosticCode | str] = []
    for failed_service_name in failures:
        if not diagnostics:
            diagnostics.append(ServiceDiagnosticCode.DEPENDENCY_OPTIONAL_FAILED)
        diagnostics.append(f"optional_dependency_failed:{failed_service_name}")
    return tuple(diagnostics)


def _skipped_attempt(service_name: str, failed_dependencies: Sequence[str], now: NowCallback) -> ServiceLaunchAttempt:
    timestamp = now()
    diagnostics: list[ServiceDiagnosticCode | str] = [ServiceDiagnosticCode.DEPENDENCY_FAILED]
    diagnostics.extend(f"dependency_failed:{dependency_name}" for dependency_name in failed_dependencies)
    return ServiceLaunchAttempt(
        service_name=service_name,
        status=ServiceLaunchStatus.SKIPPED,
        started_at=timestamp,
        finished_at=timestamp,
        elapsed_seconds=0.0,
        reason="skipped:dependency_failed",
        diagnostics=tuple(diagnostics),
    )


def _launch_node(
    node: ServiceStartNode,
    start: StartServiceCallback,
    now: NowCallback,
    timer: TimerCallback,
    diagnostics: tuple[ServiceDiagnosticCode | str, ...],
) -> ServiceLaunchAttempt:
    started_at = now()
    started_seconds = timer()
    try:
        result = start(node)
    except Exception as error:
        finished_at = now()
        elapsed_seconds = timer() - started_seconds
        return ServiceLaunchAttempt(
            service_name=node.service_name,
            status=ServiceLaunchStatus.FAILED,
            started_at=started_at,
            finished_at=finished_at,
            elapsed_seconds=elapsed_seconds,
            reason=f"failed:{type(error).__name__}",
            diagnostics=tuple(diagnostics) + (ServiceDiagnosticCode.START_FAILED,),
            exception_type=type(error).__name__,
        )
    finished_at = now()
    elapsed_seconds = timer() - started_seconds
    return ServiceLaunchAttempt(
        service_name=node.service_name,
        status=ServiceLaunchStatus.SUCCEEDED,
        started_at=started_at,
        finished_at=finished_at,
        elapsed_seconds=elapsed_seconds,
        reason="started",
        diagnostics=diagnostics,
        result=dict(result) if isinstance(result, Mapping) else None,
    )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


__all__ = [
    "plan_service_startup",
    "start_services_in_dependency_order",
]

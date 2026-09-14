from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from service_lifecycle_engine import (
    ServiceActivationPolicy,
    ServiceDependency,
    ServiceDependencyRequirement,
    ServiceDiagnosticCode,
    ServiceLaunchAttempt,
    ServiceLaunchStatus,
    ServiceStartNode,
    ServiceStartupGraphError,
    plan_service_startup,
    start_services_in_dependency_order,
)


def test_start_plan_groups_independent_services_before_dependents() -> None:
    plan = plan_service_startup(
        (
            ServiceStartNode("db"),
            ServiceStartNode("cache"),
            ServiceStartNode("api", dependencies=(ServiceDependency("db"), ServiceDependency("cache"))),
            ServiceStartNode("worker", dependencies=(ServiceDependency("api"),)),
        )
    )

    assert [wave.service_names for wave in plan.waves] == [("db", "cache"), ("api",), ("worker",)]
    assert plan.as_dict()["waves"] == [
        {"index": 0, "services": ["db", "cache"]},
        {"index": 1, "services": ["api"]},
        {"index": 2, "services": ["worker"]},
    ]


def test_start_plan_rejects_unknown_dependencies_before_starting() -> None:
    with pytest.raises(ServiceStartupGraphError) as exc_info:
        plan_service_startup((ServiceStartNode("api", dependencies=(ServiceDependency("db"),)),))

    assert exc_info.value.failure_kind == "unknown_dependency"
    assert exc_info.value.diagnostics == (ServiceDiagnosticCode.DEPENDENCY_UNKNOWN,)


def test_start_plan_rejects_dependency_cycles_before_starting() -> None:
    with pytest.raises(ServiceStartupGraphError) as exc_info:
        plan_service_startup(
            (
                ServiceStartNode("api", dependencies=(ServiceDependency("worker"),)),
                ServiceStartNode("worker", dependencies=(ServiceDependency("api"),)),
            )
        )

    assert exc_info.value.failure_kind == "dependency_cycle"
    assert exc_info.value.diagnostics == (ServiceDiagnosticCode.DEPENDENCY_CYCLE,)


def test_parallel_start_skips_required_dependents_after_failure() -> None:
    calls: list[str] = []

    def start(node: ServiceStartNode) -> object:
        calls.append(node.service_name)
        if node.service_name == "db":
            raise RuntimeError("db unavailable")
        return {"started": node.service_name}

    result = start_services_in_dependency_order(
        (
            ServiceStartNode("db"),
            ServiceStartNode("api", dependencies=(ServiceDependency("db"),)),
            ServiceStartNode("worker", dependencies=(ServiceDependency("api"),)),
        ),
        start,
        now=_fake_now(),
        timer=_fake_timer(),
    )

    assert calls == ["db"]
    assert [(attempt.service_name, attempt.status) for attempt in result.attempts] == [
        ("db", ServiceLaunchStatus.FAILED),
        ("api", ServiceLaunchStatus.SKIPPED),
        ("worker", ServiceLaunchStatus.SKIPPED),
    ]
    assert result.attempt_for("api").diagnostics == (ServiceDiagnosticCode.DEPENDENCY_FAILED, "dependency_failed:db")
    assert result.succeeded is False


def test_parallel_start_allows_optional_dependency_failure() -> None:
    calls: list[str] = []

    def start(node: ServiceStartNode) -> object:
        calls.append(node.service_name)
        if node.service_name == "cache":
            raise RuntimeError("cache unavailable")
        return {"started": node.service_name}

    result = start_services_in_dependency_order(
        (
            ServiceStartNode("cache"),
            ServiceStartNode(
                "api",
                dependencies=(ServiceDependency("cache", requirement=ServiceDependencyRequirement.OPTIONAL),),
            ),
        ),
        start,
        now=_fake_now(),
        timer=_fake_timer(),
    )

    assert calls == ["cache", "api"]
    assert result.attempt_for("cache").status == ServiceLaunchStatus.FAILED
    assert result.attempt_for("api").status == ServiceLaunchStatus.SUCCEEDED
    assert result.attempt_for("api").diagnostics == (ServiceDiagnosticCode.DEPENDENCY_OPTIONAL_FAILED, "optional_dependency_failed:cache")


def test_optional_dependency_is_soft_ordering_edge_when_upstream_is_selected() -> None:
    plan = plan_service_startup(
        (
            ServiceStartNode("cache"),
            ServiceStartNode(
                "api",
                dependencies=(ServiceDependency("cache", requirement=ServiceDependencyRequirement.OPTIONAL),),
            ),
        )
    )

    assert [wave.service_names for wave in plan.waves] == [("cache",), ("api",)]


def test_parallel_start_honors_max_parallelism() -> None:
    lock = threading.Lock()
    active = 0
    observed_max = 0

    def start(node: ServiceStartNode) -> object:
        nonlocal active, observed_max
        with lock:
            active += 1
            observed_max = max(observed_max, active)
        time.sleep(0.03)
        with lock:
            active -= 1
        return {"started": node.service_name}

    result = start_services_in_dependency_order(
        (
            ServiceStartNode("one"),
            ServiceStartNode("two"),
            ServiceStartNode("three"),
        ),
        start,
        max_parallelism=2,
    )

    assert observed_max <= 2
    assert [(attempt.service_name, attempt.status) for attempt in result.attempts] == [
        ("one", ServiceLaunchStatus.SUCCEEDED),
        ("two", ServiceLaunchStatus.SUCCEEDED),
        ("three", ServiceLaunchStatus.SUCCEEDED),
    ]


def test_launch_attempt_serializes_timing_and_error_details() -> None:
    attempt = ServiceLaunchAttempt(
        service_name="api",
        status=ServiceLaunchStatus.FAILED,
        started_at="2026-09-11T01:00:00+00:00",
        finished_at="2026-09-11T01:00:02+00:00",
        elapsed_seconds=2.0,
        reason="failed:RuntimeError",
        diagnostics=(ServiceDiagnosticCode.START_FAILED,),
        exception_type="RuntimeError",
    )

    assert attempt.as_dict() == {
        "service_id": "api",
        "status": "failed",
        "started_at": "2026-09-11T01:00:00+00:00",
        "finished_at": "2026-09-11T01:00:02+00:00",
        "elapsed_seconds": 2.0,
        "reason": "failed:RuntimeError",
        "diagnostics": ["start_failed"],
        "exception_type": "RuntimeError",
    }


def test_start_plan_excludes_lazy_services_by_default() -> None:
    nodes = (
        ServiceStartNode("db"),
        ServiceStartNode("api", dependencies=(ServiceDependency("db"),)),
        ServiceStartNode("reports", dependencies=(ServiceDependency("db"),), activation_policy=ServiceActivationPolicy.LAZY),
        ServiceStartNode("admin", activation_policy=ServiceActivationPolicy.MANUAL),
    )

    default_plan = plan_service_startup(nodes)
    explicit_plan = plan_service_startup(nodes, include_services=("reports",))

    assert [wave.service_names for wave in default_plan.waves] == [("db",), ("api",)]
    assert [wave.service_names for wave in explicit_plan.waves] == [("db",), ("reports",)]


def test_default_start_plan_does_not_promote_lazy_optional_dependencies() -> None:
    plan = plan_service_startup(
        (
            ServiceStartNode("cache", activation_policy=ServiceActivationPolicy.LAZY),
            ServiceStartNode(
                "api",
                dependencies=(ServiceDependency("cache", requirement=ServiceDependencyRequirement.OPTIONAL),),
            ),
        )
    )

    assert [wave.service_names for wave in plan.waves] == [("api",)]


def _fake_now() -> object:
    values = iter(
        (
            "2026-09-11T01:00:00+00:00",
            "2026-09-11T01:00:01+00:00",
            "2026-09-11T01:00:02+00:00",
            "2026-09-11T01:00:03+00:00",
            "2026-09-11T01:00:04+00:00",
            "2026-09-11T01:00:05+00:00",
        )
    )

    return lambda: next(values)


def _fake_timer() -> object:
    values = iter((0.0, 1.0, 2.0, 3.0, 4.0, 5.0))
    return lambda: next(values)

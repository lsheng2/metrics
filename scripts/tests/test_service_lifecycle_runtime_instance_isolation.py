from __future__ import annotations

from dataclasses import asdict
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from service_lifecycle_engine import (
    ExternalServiceBinding,
    ExternalServiceMode,
    RuntimeInstanceIdentity,
    RuntimeIsolationConflictCode,
    RuntimeResourceNamespace,
    ServiceLifecycleConformanceFixture,
    ServiceLifecycleConformanceResult,
    StopAuthorityDecision,
    assert_runtime_instance_isolation_conformance,
    detect_runtime_isolation_conflicts,
    run_runtime_instance_isolation_conformance_checks,
    run_service_lifecycle_conformance_checks,
)


def test_runtime_instance_identity_is_generic_safe_and_serializable() -> None:
    identity = RuntimeInstanceIdentity(project_name="local-tools", instance_id="dashboard-dev-1")

    assert identity.key == "local-tools:dashboard-dev-1"
    assert identity.as_dict() == {"project_name": "local-tools", "instance_id": "dashboard-dev-1"}
    assert "scrum_dashboard" not in str(asdict(identity)).lower()


def test_runtime_instance_identity_rejects_unsafe_values() -> None:
    with pytest.raises(ValueError, match="instance_id"):
        RuntimeInstanceIdentity(project_name="local-tools", instance_id="../other")


def test_runtime_instance_id_derivation_is_stable_and_seed_sensitive() -> None:
    first = RuntimeInstanceIdentity.derive(project_name="local-tools", seed="/tmp/worktree-a", label="dev")
    same = RuntimeInstanceIdentity.derive(project_name="local-tools", seed="/tmp/worktree-a", label="dev")
    second = RuntimeInstanceIdentity.derive(project_name="local-tools", seed="/tmp/worktree-b", label="dev")

    assert first == same
    assert first != second
    assert first.instance_id.startswith("dev-")
    assert len(first.instance_id) <= 32


def test_resource_namespace_derives_runtime_safe_values_from_identity() -> None:
    identity = RuntimeInstanceIdentity(project_name="local-tools", instance_id="dashboard-dev-1")
    namespace = RuntimeResourceNamespace.from_identity(identity, service_group="cache")

    assert namespace.key_prefix == "local-tools:dashboard-dev-1:cache:"
    assert namespace.database_name == "local_tools_dashboard_dev_1_cache"
    assert namespace.compose_project_name == "local-tools-dashboard-dev-1-cache"
    assert namespace.state_dir_name == "local-tools-dashboard-dev-1-cache"
    assert namespace.telemetry_attributes == {
        "service.instance.id": "dashboard-dev-1",
        "service.namespace": "local-tools",
        "service.group": "cache",
    }


def test_shared_consumed_service_never_grants_stop_authority() -> None:
    consumer = RuntimeInstanceIdentity(project_name="local-tools", instance_id="consumer")
    binding = ExternalServiceBinding(
        service_name="database",
        mode=ExternalServiceMode.SHARED_CONSUMED,
        consumer=consumer,
        endpoint="http://127.0.0.1:5432",
    )

    decision = binding.stop_decision(actor=consumer)

    assert decision == StopAuthorityDecision(
        allowed=False,
        reason="shared_consumed_cannot_stop_external_service",
        clear_local_binding=True,
    )


def test_shared_consumed_identity_key_belongs_to_consumer_binding() -> None:
    owner = RuntimeInstanceIdentity(project_name="local-tools", instance_id="owner")
    consumer = RuntimeInstanceIdentity(project_name="local-tools", instance_id="consumer")
    binding = ExternalServiceBinding(
        service_name="database",
        mode=ExternalServiceMode.SHARED_CONSUMED,
        owner=owner,
        consumer=consumer,
        endpoint="http://127.0.0.1:5432",
    )

    assert binding.identity_key == consumer.key


def test_dedicated_service_requires_actor_to_match_owner() -> None:
    owner = RuntimeInstanceIdentity(project_name="local-tools", instance_id="owner")
    rival = RuntimeInstanceIdentity(project_name="local-tools", instance_id="rival")
    binding = ExternalServiceBinding(
        service_name="api",
        mode=ExternalServiceMode.DEDICATED,
        owner=owner,
        namespace=RuntimeResourceNamespace.from_identity(owner, service_group="api"),
    )

    assert binding.stop_decision(actor=owner).allowed is True
    assert binding.stop_decision(actor=rival).allowed is False
    assert binding.stop_decision(actor=rival).reason == "actor_does_not_own_dedicated_service"
    assert binding.stop_decision(actor=rival, force=True).allowed is True


def test_conflict_detector_reports_duplicate_instances_ports_and_namespaces() -> None:
    first = RuntimeInstanceIdentity(project_name="local-tools", instance_id="dev")
    duplicate = RuntimeInstanceIdentity(project_name="local-tools", instance_id="dev")
    other = RuntimeInstanceIdentity(project_name="local-tools", instance_id="other")
    first_namespace = RuntimeResourceNamespace.from_identity(first, service_group="api", ports={"http": 8123})
    duplicate_namespace = RuntimeResourceNamespace.from_identity(duplicate, service_group="api", ports={"http": 8124})
    port_collision = RuntimeResourceNamespace.from_identity(other, service_group="worker", ports={"http": 8123})

    conflicts = detect_runtime_isolation_conflicts(
        [
            ExternalServiceBinding("api", ExternalServiceMode.DEDICATED, owner=first, namespace=first_namespace),
            ExternalServiceBinding("api", ExternalServiceMode.DEDICATED, owner=duplicate, namespace=duplicate_namespace),
            ExternalServiceBinding("worker", ExternalServiceMode.DEDICATED, owner=other, namespace=port_collision),
        ]
    )

    assert {conflict.code for conflict in conflicts} == {
        RuntimeIsolationConflictCode.DUPLICATE_INSTANCE_SERVICE,
        RuntimeIsolationConflictCode.DUPLICATE_NAMESPACE,
        RuntimeIsolationConflictCode.DUPLICATE_PORT,
    }


def test_runtime_isolation_conformance_fixture_is_reusable() -> None:
    owner = RuntimeInstanceIdentity(project_name="local-tools", instance_id="owner")
    consumer = RuntimeInstanceIdentity(project_name="local-tools", instance_id="consumer")
    results = run_runtime_instance_isolation_conformance_checks(
        owner=owner,
        consumer=consumer,
        service_name="database",
    )

    assert all(isinstance(result, ServiceLifecycleConformanceResult) for result in results)
    assert all(result.passed for result in results)
    assert_runtime_instance_isolation_conformance(owner=owner, consumer=consumer, service_name="database")


def test_service_lifecycle_conformance_can_include_runtime_isolation() -> None:
    fixture = ServiceLifecycleConformanceFixture(
        service_name="api",
        live_pid=101,
        dead_pid=202,
        process_provider=ProcessProvider(),
        launch_provider=LaunchProvider(),
        health_provider=HealthProvider(),
        runtime_isolation_owner=RuntimeInstanceIdentity("local-tools", "owner"),
        runtime_isolation_consumer=RuntimeInstanceIdentity("local-tools", "consumer"),
    )

    results = run_service_lifecycle_conformance_checks(fixture)

    assert all(result.passed for result in results)
    assert "runtime_stop_authority" in {result.name for result in results}


class ProcessProvider:
    def pid_is_alive(self, pid: int) -> bool:
        return pid == 101

    def read_process_started_at(self, pid: int) -> str | None:
        return "2026-09-16T00:00:00+00:00" if pid == 101 else None


class LaunchProvider:
    def resolve_launch_metadata(self, service_name: str):  # noqa: ANN001
        from service_lifecycle_engine import ServiceLaunchMetadata

        return ServiceLaunchMetadata(
            started_at="2026-09-16T00:00:00+00:00",
            source=f"{service_name}-launcher",
        )


class HealthProvider:
    def probe_health(self, service_name: str):  # noqa: ANN001
        from service_lifecycle_engine import HealthProbeRequirement, ServiceHealthSnapshot, ServiceHealthStatus

        return ServiceHealthSnapshot(
            service_name=service_name,
            status=ServiceHealthStatus.READY,
            checked_at="2026-09-16T00:00:01+00:00",
            probe_name="readiness",
            requirement=HealthProbeRequirement.REQUIRED_FOR_LIVE_STATUS,
        )

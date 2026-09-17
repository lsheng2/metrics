from __future__ import annotations

from .runtime_instance import (
    ExternalServiceBinding,
    ExternalServiceMode,
    RuntimeInstanceIdentity,
    RuntimeResourceNamespace,
    detect_runtime_isolation_conflicts,
)


def run_runtime_instance_isolation_conformance_checks(
    *,
    owner: RuntimeInstanceIdentity,
    consumer: RuntimeInstanceIdentity,
    service_name: str = "service",
):
    return (
        _check_runtime_identity_distinct(owner, consumer),
        _check_runtime_namespace_derivation(owner, service_name),
        _check_runtime_stop_authority(owner, consumer, service_name),
        _check_runtime_conflict_detection(owner, consumer, service_name),
    )


def assert_runtime_instance_isolation_conformance(
    *,
    owner: RuntimeInstanceIdentity,
    consumer: RuntimeInstanceIdentity,
    service_name: str = "service",
) -> None:
    failures = [
        result
        for result in run_runtime_instance_isolation_conformance_checks(
            owner=owner,
            consumer=consumer,
            service_name=service_name,
        )
        if not result.passed
    ]
    if failures:
        detail = "; ".join(f"{failure.name}: {failure.detail}" for failure in failures)
        raise AssertionError(detail)


def _check_runtime_identity_distinct(owner: RuntimeInstanceIdentity, consumer: RuntimeInstanceIdentity):
    from .conformance import ServiceLifecycleConformanceResult

    if owner == consumer:
        return ServiceLifecycleConformanceResult("runtime_identity_distinct", False, "owner and consumer identities were identical")
    if not owner.key or not consumer.key:
        return ServiceLifecycleConformanceResult("runtime_identity_distinct", False, "identity key was empty")
    return ServiceLifecycleConformanceResult("runtime_identity_distinct", True)


def _check_runtime_namespace_derivation(owner: RuntimeInstanceIdentity, service_name: str):
    from .conformance import ServiceLifecycleConformanceResult

    namespace = RuntimeResourceNamespace.from_identity(owner, service_group=service_name, ports={"http": 8123})
    payload = namespace.as_dict()
    if owner.instance_id not in namespace.key_prefix:
        return ServiceLifecycleConformanceResult("runtime_namespace_derivation", False, "key prefix omitted instance id")
    if payload["ports"] != {"http": 8123}:
        return ServiceLifecycleConformanceResult("runtime_namespace_derivation", False, "ports were not serialized")
    return ServiceLifecycleConformanceResult("runtime_namespace_derivation", True)


def _check_runtime_stop_authority(
    owner: RuntimeInstanceIdentity,
    consumer: RuntimeInstanceIdentity,
    service_name: str,
):
    from .conformance import ServiceLifecycleConformanceResult

    namespace = RuntimeResourceNamespace.from_identity(owner, service_group=service_name)
    dedicated = ExternalServiceBinding(service_name, ExternalServiceMode.DEDICATED, owner=owner, namespace=namespace)
    shared = ExternalServiceBinding(
        service_name,
        ExternalServiceMode.SHARED_CONSUMED,
        consumer=consumer,
        endpoint="http://127.0.0.1:8123",
    )
    if not dedicated.stop_decision(actor=owner).allowed:
        return ServiceLifecycleConformanceResult("runtime_stop_authority", False, "owner could not stop dedicated service")
    if dedicated.stop_decision(actor=consumer).allowed:
        return ServiceLifecycleConformanceResult("runtime_stop_authority", False, "consumer could stop dedicated service")
    shared_decision = shared.stop_decision(actor=consumer)
    if shared_decision.allowed or not shared_decision.clear_local_binding:
        return ServiceLifecycleConformanceResult("runtime_stop_authority", False, "shared consumer stop decision was unsafe")
    return ServiceLifecycleConformanceResult("runtime_stop_authority", True)


def _check_runtime_conflict_detection(
    owner: RuntimeInstanceIdentity,
    consumer: RuntimeInstanceIdentity,
    service_name: str,
):
    from .conformance import ServiceLifecycleConformanceResult

    namespace = RuntimeResourceNamespace.from_identity(owner, service_group=service_name, ports={"http": 8123})
    duplicate = ExternalServiceBinding(service_name, ExternalServiceMode.DEDICATED, owner=owner, namespace=namespace)
    port_collision = ExternalServiceBinding(
        "worker",
        ExternalServiceMode.DEDICATED,
        owner=consumer,
        namespace=RuntimeResourceNamespace.from_identity(consumer, service_group="worker", ports={"http": 8123}),
    )
    conflicts = detect_runtime_isolation_conflicts((duplicate, duplicate, port_collision))
    codes = {conflict.code.value for conflict in conflicts}
    required = {"duplicate_instance_service", "duplicate_namespace", "duplicate_port"}
    if not required.issubset(codes):
        return ServiceLifecycleConformanceResult("runtime_conflict_detection", False, f"missing conflicts: {sorted(required.difference(codes))}")
    return ServiceLifecycleConformanceResult("runtime_conflict_detection", True)


__all__ = [
    "assert_runtime_instance_isolation_conformance",
    "run_runtime_instance_isolation_conformance_checks",
]

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum

from .storage import validate_lifecycle_identifier


_UNSAFE_SLUG_CHARS = re.compile(r"[^A-Za-z0-9_.-]+")


class ExternalServiceMode(str, Enum):
    DEDICATED = "dedicated"
    SHARED_CONSUMED = "shared_consumed"
    SHARED_MANAGED = "shared_managed"


class RuntimeIsolationConflictCode(str, Enum):
    DUPLICATE_INSTANCE_SERVICE = "duplicate_instance_service"
    DUPLICATE_NAMESPACE = "duplicate_namespace"
    DUPLICATE_PORT = "duplicate_port"
    FOREIGN_OWNER = "foreign_owner"
    SHARED_OWNER_MISMATCH = "shared_owner_mismatch"
    STALE_PROVENANCE = "stale_provenance"


@dataclass(frozen=True, slots=True)
class RuntimeInstanceIdentity:
    project_name: str
    instance_id: str

    def __post_init__(self) -> None:
        validate_lifecycle_identifier("project_name", self.project_name)
        validate_lifecycle_identifier("instance_id", self.instance_id)

    @classmethod
    def derive(cls, *, project_name: str, seed: str, label: str = "instance") -> "RuntimeInstanceIdentity":
        slug = _safe_slug(label, fallback="instance", max_length=20)
        digest = hashlib.sha256(str(seed).encode("utf-8")).hexdigest()[:10]
        return cls(project_name=project_name, instance_id=f"{slug}-{digest}")

    @property
    def key(self) -> str:
        return f"{self.project_name}:{self.instance_id}"

    def as_dict(self) -> dict[str, str]:
        return {"project_name": self.project_name, "instance_id": self.instance_id}


@dataclass(frozen=True, slots=True)
class RuntimeResourceNamespace:
    identity: RuntimeInstanceIdentity
    service_group: str
    key_prefix: str
    database_name: str
    compose_project_name: str
    state_dir_name: str
    telemetry_attributes: Mapping[str, str] = field(default_factory=dict)
    ports: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_lifecycle_identifier("service_group", self.service_group)
        _validate_namespace_value("key_prefix", self.key_prefix)
        _validate_namespace_value("database_name", self.database_name)
        _validate_namespace_value("compose_project_name", self.compose_project_name)
        _validate_namespace_value("state_dir_name", self.state_dir_name)
        object.__setattr__(self, "telemetry_attributes", dict(self.telemetry_attributes))
        object.__setattr__(self, "ports", {str(name): _validate_port(port) for name, port in self.ports.items()})
        for port_name in self.ports:
            validate_lifecycle_identifier("port_name", str(port_name))

    @classmethod
    def from_identity(
        cls,
        identity: RuntimeInstanceIdentity,
        *,
        service_group: str,
        ports: Mapping[str, int] | None = None,
    ) -> "RuntimeResourceNamespace":
        group = _safe_slug(service_group, fallback="service")
        base = f"{identity.project_name}:{identity.instance_id}:{group}"
        file_safe_base = _safe_slug(f"{identity.project_name}-{identity.instance_id}-{group}", fallback="service")
        database_name = _database_safe(f"{identity.project_name}_{identity.instance_id}_{group}")
        return cls(
            identity=identity,
            service_group=group,
            key_prefix=f"{base}:",
            database_name=database_name,
            compose_project_name=file_safe_base,
            state_dir_name=file_safe_base,
            telemetry_attributes={
                "service.instance.id": identity.instance_id,
                "service.namespace": identity.project_name,
                "service.group": group,
            },
            ports=dict(ports or {}),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "identity": self.identity.as_dict(),
            "service_group": self.service_group,
            "key_prefix": self.key_prefix,
            "database_name": self.database_name,
            "compose_project_name": self.compose_project_name,
            "state_dir_name": self.state_dir_name,
            "telemetry_attributes": dict(self.telemetry_attributes),
            "ports": dict(self.ports),
        }


@dataclass(frozen=True, slots=True)
class StopAuthorityDecision:
    allowed: bool
    reason: str
    clear_local_binding: bool = False
    forced: bool = False


@dataclass(frozen=True, slots=True)
class ExternalServiceBinding:
    service_name: str
    mode: ExternalServiceMode | str
    owner: RuntimeInstanceIdentity | None = None
    namespace: RuntimeResourceNamespace | None = None
    consumer: RuntimeInstanceIdentity | None = None
    endpoint: str = ""

    def __post_init__(self) -> None:
        validate_lifecycle_identifier("service_name", self.service_name)
        object.__setattr__(self, "mode", external_service_mode(self.mode))
        if self.mode in {ExternalServiceMode.DEDICATED, ExternalServiceMode.SHARED_MANAGED} and self.owner is None:
            raise ValueError(f"{self.mode.value} service requires owner identity")
        if self.mode == ExternalServiceMode.SHARED_CONSUMED and self.consumer is None:
            raise ValueError("shared_consumed service requires consumer identity")

    @property
    def identity_key(self) -> str:
        if self.mode == ExternalServiceMode.SHARED_CONSUMED and self.consumer is not None:
            return self.consumer.key
        if self.owner is not None:
            return self.owner.key
        if self.consumer is not None:
            return self.consumer.key
        return ""

    def stop_decision(self, *, actor: RuntimeInstanceIdentity, force: bool = False) -> StopAuthorityDecision:
        if force:
            return StopAuthorityDecision(allowed=True, reason="force_requested", forced=True)
        if self.mode == ExternalServiceMode.SHARED_CONSUMED:
            return StopAuthorityDecision(
                allowed=False,
                reason="shared_consumed_cannot_stop_external_service",
                clear_local_binding=True,
            )
        if self.owner == actor:
            reason = "owned_dedicated_service" if self.mode == ExternalServiceMode.DEDICATED else "owned_shared_managed_service"
            return StopAuthorityDecision(allowed=True, reason=reason)
        if self.mode == ExternalServiceMode.DEDICATED:
            return StopAuthorityDecision(allowed=False, reason="actor_does_not_own_dedicated_service")
        return StopAuthorityDecision(allowed=False, reason="actor_does_not_own_shared_managed_service")

    def as_dict(self) -> dict[str, object]:
        return {
            "service_name": self.service_name,
            "mode": self.mode.value,
            "owner": self.owner.as_dict() if self.owner else None,
            "consumer": self.consumer.as_dict() if self.consumer else None,
            "namespace": self.namespace.as_dict() if self.namespace else None,
            "endpoint": self.endpoint,
        }


@dataclass(frozen=True, slots=True)
class RuntimeIsolationConflict:
    code: RuntimeIsolationConflictCode
    subject: str
    details: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code.value, "subject": self.subject, "details": list(self.details)}


def external_service_mode(value: ExternalServiceMode | str) -> ExternalServiceMode:
    if isinstance(value, ExternalServiceMode):
        return value
    return ExternalServiceMode(str(value))


def detect_runtime_isolation_conflicts(
    bindings: Sequence[ExternalServiceBinding],
) -> tuple[RuntimeIsolationConflict, ...]:
    conflicts: list[RuntimeIsolationConflict] = []
    service_identity_index: dict[tuple[str, str], list[ExternalServiceBinding]] = defaultdict(list)
    namespace_index: dict[str, list[ExternalServiceBinding]] = defaultdict(list)
    port_index: dict[int, list[ExternalServiceBinding]] = defaultdict(list)

    for binding in bindings:
        if binding.identity_key:
            service_identity_index[(binding.identity_key, binding.service_name)].append(binding)
        if binding.namespace is not None:
            namespace_index[binding.namespace.key_prefix].append(binding)
            for port in binding.namespace.ports.values():
                port_index[int(port)].append(binding)

    for (identity_key, service_name), rows in sorted(service_identity_index.items()):
        if len(rows) > 1:
            conflicts.append(
                RuntimeIsolationConflict(
                    RuntimeIsolationConflictCode.DUPLICATE_INSTANCE_SERVICE,
                    f"{identity_key}/{service_name}",
                    tuple(_binding_label(row) for row in rows),
                )
            )

    for key_prefix, rows in sorted(namespace_index.items()):
        if len(rows) > 1:
            conflicts.append(
                RuntimeIsolationConflict(
                    RuntimeIsolationConflictCode.DUPLICATE_NAMESPACE,
                    key_prefix,
                    tuple(_binding_label(row) for row in rows),
                )
            )

    for port, rows in sorted(port_index.items()):
        if len(rows) > 1:
            conflicts.append(
                RuntimeIsolationConflict(
                    RuntimeIsolationConflictCode.DUPLICATE_PORT,
                    str(port),
                    tuple(_binding_label(row) for row in rows),
                )
            )

    return tuple(conflicts)


def _binding_label(binding: ExternalServiceBinding) -> str:
    return f"{binding.identity_key}/{binding.service_name}/{binding.mode.value}"


def _validate_namespace_value(label: str, value: str) -> None:
    if not value:
        raise ValueError(f"{label} must not be empty")
    if any(char.isspace() for char in value):
        raise ValueError(f"{label} must not contain whitespace: {value!r}")


def _validate_port(value: int) -> int:
    port = int(value)
    if port < 1 or port > 65535:
        raise ValueError(f"port must be between 1 and 65535: {value!r}")
    return port


def _safe_slug(value: str, *, fallback: str, max_length: int | None = None) -> str:
    slug = _UNSAFE_SLUG_CHARS.sub("-", str(value).strip()).strip("-._")
    if not slug:
        slug = fallback
    if max_length is not None and len(slug) > max_length:
        slug = slug[:max_length].rstrip("-._") or fallback
    validate_lifecycle_identifier("slug", slug)
    return slug


def _database_safe(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_").lower() or "service"


__all__ = [
    "ExternalServiceBinding",
    "ExternalServiceMode",
    "RuntimeInstanceIdentity",
    "RuntimeIsolationConflict",
    "RuntimeIsolationConflictCode",
    "RuntimeResourceNamespace",
    "StopAuthorityDecision",
    "detect_runtime_isolation_conflicts",
    "external_service_mode",
]

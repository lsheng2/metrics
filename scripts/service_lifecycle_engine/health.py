from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from .diagnostics import ServiceDiagnosticCode, diagnostic_values


AUTH_REQUIRED_HTTP_STATUSES = frozenset({401, 403})


class ServiceHealthStatus(str, Enum):
    UNKNOWN = "unknown"
    STARTING = "starting"
    READY = "ready"
    DEGRADED = "degraded"
    AUTH_REQUIRED = "auth_required"
    UNREACHABLE = "unreachable"
    STOPPED = "stopped"


class HealthProbeRequirement(str, Enum):
    REQUIRED_FOR_STARTUP = "required_for_startup"
    REQUIRED_FOR_LIVE_STATUS = "required_for_live_status"
    OPTIONAL_OBSERVABILITY = "optional_observability"
    ADVISORY = "advisory"


@runtime_checkable
class Clock(Protocol):
    def now(self) -> str:
        ...


@runtime_checkable
class HealthProbeProvider(Protocol):
    def probe_health(self, service_name: str) -> "ServiceHealthSnapshot":
        ...


class SystemClock:
    def now(self) -> str:
        return datetime.now(UTC).isoformat(timespec="microseconds")


@dataclass(frozen=True, slots=True)
class ServiceHealthSnapshot:
    service_name: str
    status: ServiceHealthStatus
    checked_at: str
    probe_name: str = ""
    requirement: HealthProbeRequirement = HealthProbeRequirement.REQUIRED_FOR_LIVE_STATUS
    reachable: bool | None = None
    http_status: int | None = None
    latency_ms: float | None = None
    reason: str = ""
    special_state: str = ""
    failure_kind: str = ""
    message: str = ""
    diagnostics: tuple[ServiceDiagnosticCode | str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "service_id": self.service_name,
            "status": self.status.value,
            "checked_at": self.checked_at,
            "probe_name": self.probe_name,
            "requirement": self.requirement.value,
            "diagnostics": diagnostic_values(self.diagnostics),
        }
        if self.reachable is not None:
            payload["reachable"] = self.reachable
        if self.http_status is not None:
            payload["http_status"] = self.http_status
        if self.latency_ms is not None:
            payload["latency_ms"] = self.latency_ms
        if self.reason:
            payload["reason"] = self.reason
        if self.special_state:
            payload["special_state"] = self.special_state
        if self.failure_kind:
            payload["failure_kind"] = self.failure_kind
        if self.message:
            payload["message"] = self.message
        return payload


def resolve_service_health_status(
    *,
    reachable: bool | None = None,
    http_status: int | None = None,
    unhealthy_count: int | None = None,
    explicit_status: ServiceHealthStatus | str | None = None,
) -> ServiceHealthStatus:
    if explicit_status is not None:
        return _coerce_service_health_status(explicit_status, default=ServiceHealthStatus.DEGRADED)
    if http_status in AUTH_REQUIRED_HTTP_STATUSES:
        return ServiceHealthStatus.AUTH_REQUIRED
    if reachable is True:
        if isinstance(unhealthy_count, int) and unhealthy_count > 0:
            return ServiceHealthStatus.DEGRADED
        return ServiceHealthStatus.READY
    if reachable is False:
        return ServiceHealthStatus.UNREACHABLE
    return ServiceHealthStatus.UNKNOWN


def build_service_health_snapshot(
    *,
    service_name: str,
    checked_at: str | None = None,
    clock: Clock | None = None,
    reachable: bool | None = None,
    http_status: int | None = None,
    unhealthy_count: int | None = None,
    explicit_status: ServiceHealthStatus | str | None = None,
    probe_name: str = "",
    requirement: HealthProbeRequirement = HealthProbeRequirement.REQUIRED_FOR_LIVE_STATUS,
    latency_ms: float | None = None,
    reason: str = "",
    special_state: str = "",
    failure_kind: str = "",
    message: str = "",
    diagnostics: tuple[ServiceDiagnosticCode | str, ...] = (),
) -> ServiceHealthSnapshot:
    unknown_explicit_status = _unknown_explicit_status(explicit_status)
    if unknown_explicit_status and not reason:
        reason = unknown_explicit_status
    if unknown_explicit_status and not special_state:
        special_state = unknown_explicit_status
    return ServiceHealthSnapshot(
        service_name=service_name,
        status=resolve_service_health_status(
            reachable=reachable,
            http_status=http_status,
            unhealthy_count=unhealthy_count,
            explicit_status=explicit_status,
        ),
        checked_at=checked_at or (clock or SystemClock()).now(),
        probe_name=probe_name,
        requirement=requirement,
        reachable=reachable,
        http_status=http_status,
        latency_ms=latency_ms,
        reason=reason,
        special_state=special_state,
        failure_kind=failure_kind,
        message=message,
        diagnostics=diagnostics,
    )


def health_requirement_affects_startup(requirement: HealthProbeRequirement | str) -> bool:
    return _coerce_health_probe_requirement(requirement) == HealthProbeRequirement.REQUIRED_FOR_STARTUP


def health_requirement_affects_liveness(requirement: HealthProbeRequirement | str) -> bool:
    return _coerce_health_probe_requirement(requirement) in {
        HealthProbeRequirement.REQUIRED_FOR_STARTUP,
        HealthProbeRequirement.REQUIRED_FOR_LIVE_STATUS,
    }


def _coerce_service_health_status(
    value: ServiceHealthStatus | str,
    *,
    default: ServiceHealthStatus | None = None,
) -> ServiceHealthStatus:
    if isinstance(value, ServiceHealthStatus):
        return value
    try:
        return ServiceHealthStatus(str(value))
    except ValueError:
        if default is not None:
            return default
        raise


def _unknown_explicit_status(value: ServiceHealthStatus | str | None) -> str:
    if value is None or isinstance(value, ServiceHealthStatus):
        return ""
    try:
        ServiceHealthStatus(str(value))
    except ValueError:
        return str(value)
    return ""


def _coerce_health_probe_requirement(value: HealthProbeRequirement | str) -> HealthProbeRequirement:
    if isinstance(value, HealthProbeRequirement):
        return value
    return HealthProbeRequirement(str(value))


__all__ = [
    "AUTH_REQUIRED_HTTP_STATUSES",
    "Clock",
    "HealthProbeRequirement",
    "HealthProbeProvider",
    "ServiceHealthSnapshot",
    "ServiceHealthStatus",
    "SystemClock",
    "build_service_health_snapshot",
    "health_requirement_affects_liveness",
    "health_requirement_affects_startup",
    "resolve_service_health_status",
]

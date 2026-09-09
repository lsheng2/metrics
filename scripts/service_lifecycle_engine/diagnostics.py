from __future__ import annotations

from enum import Enum


class ServiceDiagnosticCode(str, Enum):
    NOT_REGISTERED = "not_registered"
    STATE_MISSING = "state_missing"
    STATE_NOT_LIVE = "state_not_live"
    PID_UNAVAILABLE = "pid_unavailable"
    PID_NOT_ALIVE = "pid_not_alive"
    IDENTITY_MISMATCH = "identity_mismatch"
    STARTED_AT_UNAVAILABLE = "started_at_unavailable"
    PROBE_AUTH_REQUIRED = "probe_auth_required"
    PROBE_TIMEOUT = "probe_timeout"


def diagnostic_value(value: ServiceDiagnosticCode | str) -> str:
    if isinstance(value, ServiceDiagnosticCode):
        return value.value
    return str(value)


def diagnostic_values(values: tuple[ServiceDiagnosticCode | str, ...]) -> list[str]:
    return [diagnostic_value(value) for value in values]


__all__ = ["ServiceDiagnosticCode", "diagnostic_value", "diagnostic_values"]

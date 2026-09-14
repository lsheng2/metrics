from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum

from .diagnostics import ServiceDiagnosticCode, diagnostic_values
from .storage import json_ready, validate_lifecycle_identifier


class ServiceDependencyRequirement(str, Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"


class ServiceActivationPolicy(str, Enum):
    EAGER = "eager"
    LAZY = "lazy"
    MANUAL = "manual"


class ServiceRestartPolicy(str, Enum):
    NEVER = "never"
    ON_FAILURE = "on_failure"
    EXPLICIT = "explicit"


class ServiceLaunchStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class ServiceStartupGraphError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        failure_kind: str,
        diagnostics: Sequence[ServiceDiagnosticCode | str] = (),
    ) -> None:
        super().__init__(message)
        self.failure_kind = failure_kind
        self.diagnostics = tuple(diagnostics)


@dataclass(frozen=True, slots=True)
class ServiceDependency:
    service_name: str
    requirement: ServiceDependencyRequirement | str = ServiceDependencyRequirement.REQUIRED
    reason: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "service_name", validated_service_name(self.service_name))
        object.__setattr__(self, "requirement", dependency_requirement(self.requirement))

    def as_dict(self) -> dict[str, str]:
        payload = {
            "service_id": self.service_name,
            "requirement": self.requirement.value,
        }
        if self.reason:
            payload["reason"] = self.reason
        return payload


@dataclass(frozen=True, slots=True)
class ServiceStartNode:
    service_name: str
    dependencies: tuple[ServiceDependency, ...] = ()
    activation_policy: ServiceActivationPolicy | str = ServiceActivationPolicy.EAGER
    restart_policy: ServiceRestartPolicy | str = ServiceRestartPolicy.EXPLICIT
    metadata: Mapping[str, object] = field(default_factory=dict)
    startup_timeout_seconds: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "service_name", validated_service_name(self.service_name))
        object.__setattr__(
            self,
            "dependencies",
            tuple(dependency if isinstance(dependency, ServiceDependency) else ServiceDependency(str(dependency)) for dependency in self.dependencies),
        )
        object.__setattr__(self, "activation_policy", activation_policy(self.activation_policy))
        object.__setattr__(self, "restart_policy", restart_policy(self.restart_policy))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "service_id": self.service_name,
            "dependencies": [dependency.as_dict() for dependency in self.dependencies],
            "activation_policy": self.activation_policy.value,
            "restart_policy": self.restart_policy.value,
            "metadata": json_ready(dict(self.metadata)),
        }
        if self.startup_timeout_seconds is not None:
            payload["startup_timeout_seconds"] = self.startup_timeout_seconds
        return payload


@dataclass(frozen=True, slots=True)
class ServiceStartWave:
    index: int
    service_names: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {"index": self.index, "services": list(self.service_names)}


@dataclass(frozen=True, slots=True)
class ServiceStartPlan:
    nodes: tuple[ServiceStartNode, ...]
    waves: tuple[ServiceStartWave, ...]

    def node_for(self, service_name: str) -> ServiceStartNode:
        for node in self.nodes:
            if node.service_name == service_name:
                return node
        raise KeyError(service_name)

    @property
    def service_names(self) -> tuple[str, ...]:
        return tuple(node.service_name for node in self.nodes)

    def as_dict(self) -> dict[str, object]:
        return {
            "services": [node.as_dict() for node in self.nodes],
            "waves": [wave.as_dict() for wave in self.waves],
        }


@dataclass(frozen=True, slots=True)
class ServiceLaunchAttempt:
    service_name: str
    status: ServiceLaunchStatus | str
    started_at: str
    finished_at: str
    elapsed_seconds: float
    reason: str = ""
    diagnostics: tuple[ServiceDiagnosticCode | str, ...] = ()
    result: Mapping[str, object] | None = None
    exception_type: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "service_name", validated_service_name(self.service_name))
        object.__setattr__(self, "status", launch_status(self.status))

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "service_id": self.service_name,
            "status": self.status.value,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "elapsed_seconds": round(float(self.elapsed_seconds), 3),
            "reason": self.reason,
            "diagnostics": diagnostic_values(self.diagnostics),
        }
        if self.result is not None:
            payload["result"] = json_ready(dict(self.result))
        if self.exception_type:
            payload["exception_type"] = self.exception_type
        return payload


@dataclass(frozen=True, slots=True)
class ServiceStartGraphResult:
    run_id: str
    plan: ServiceStartPlan
    attempts: tuple[ServiceLaunchAttempt, ...]

    @property
    def succeeded(self) -> bool:
        return all(attempt.status == ServiceLaunchStatus.SUCCEEDED for attempt in self.attempts)

    def attempt_for(self, service_name: str) -> ServiceLaunchAttempt:
        for attempt in self.attempts:
            if attempt.service_name == service_name:
                return attempt
        raise KeyError(service_name)

    def as_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "succeeded": self.succeeded,
            "plan": self.plan.as_dict(),
            "attempts": [attempt.as_dict() for attempt in self.attempts],
        }


StartServiceCallback = Callable[[ServiceStartNode], object]
NowCallback = Callable[[], str]
TimerCallback = Callable[[], float]


def validated_service_name(service_name: str) -> str:
    value = str(service_name)
    validate_lifecycle_identifier("service_name", value)
    return value


def dependency_requirement(value: ServiceDependencyRequirement | str) -> ServiceDependencyRequirement:
    if isinstance(value, ServiceDependencyRequirement):
        return value
    return ServiceDependencyRequirement(str(value))


def activation_policy(value: ServiceActivationPolicy | str) -> ServiceActivationPolicy:
    if isinstance(value, ServiceActivationPolicy):
        return value
    return ServiceActivationPolicy(str(value))


def restart_policy(value: ServiceRestartPolicy | str) -> ServiceRestartPolicy:
    if isinstance(value, ServiceRestartPolicy):
        return value
    return ServiceRestartPolicy(str(value))


def launch_status(value: ServiceLaunchStatus | str) -> ServiceLaunchStatus:
    if isinstance(value, ServiceLaunchStatus):
        return value
    return ServiceLaunchStatus(str(value))


__all__ = [
    "NowCallback",
    "ServiceActivationPolicy",
    "ServiceDependency",
    "ServiceDependencyRequirement",
    "ServiceLaunchAttempt",
    "ServiceLaunchStatus",
    "ServiceRestartPolicy",
    "ServiceStartGraphResult",
    "ServiceStartNode",
    "ServiceStartPlan",
    "ServiceStartWave",
    "ServiceStartupGraphError",
    "StartServiceCallback",
    "TimerCallback",
]

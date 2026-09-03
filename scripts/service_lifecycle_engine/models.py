from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Mapping, Sequence


class LifecycleState(str, Enum):
    PLANNED = "planned"
    PREPARED = "prepared"
    READY = "ready"
    STOPPED = "stopped"
    ABORTED = "aborted"


class ProvenanceCapability(str, Enum):
    WRAPPER_ONLY = "wrapper_only"
    REGISTERED_PROCESS = "registered_process"
    OWNED_LISTENER = "owned_listener"
    ENDPOINT_GRADE = "endpoint_grade"
    HTTP_IDENTITY = "http_identity"


class StopSource(str, Enum):
    REGISTERED_PROCESS = "registered_process"
    PID_FILE_RECOVERY = "pid_file_recovery"
    FORCE_BY_PORT = "force_by_port"
    NOT_REGISTERED = "not_registered"


class LiveServiceResolutionSource(str, Enum):
    EXPLICIT = "explicit"
    LIFECYCLE_STATE = "lifecycle_state"
    PROJECT_PROJECTION = "project_projection"
    DEFAULT = "default"


class LifecycleStateStoreError(RuntimeError):
    def __init__(self, message: str, failure_kind: str) -> None:
        super().__init__(message)
        self.failure_kind = failure_kind


@dataclass(frozen=True, slots=True)
class ServiceSpec:
    name: str
    preferred_ports: tuple[int, ...]
    command: tuple[str, ...]
    stop_command: tuple[str, ...] = ()
    host: str = "127.0.0.1"
    cwd: Path | None = None
    env: Mapping[str, str] = field(default_factory=dict)
    health_url: str | None = None
    listener_identity_url: str | None = None
    startup_timeout_seconds: float = 30.0
    graceful_timeout_seconds: float = 5.0
    port_release_timeout_seconds: float = 2.0

    @classmethod
    def from_values(
        cls,
        name: str,
        preferred_ports: Sequence[int],
        command: Sequence[str],
        stop_command: Sequence[str] | None = None,
        host: str = "127.0.0.1",
        cwd: str | Path | None = None,
        env: Mapping[str, str] | None = None,
        health_url: str | None = None,
        listener_identity_url: str | None = None,
        startup_timeout_seconds: float = 30.0,
        graceful_timeout_seconds: float = 5.0,
        port_release_timeout_seconds: float = 2.0,
    ) -> "ServiceSpec":
        return cls(
            name=name,
            preferred_ports=tuple(int(port) for port in preferred_ports),
            command=tuple(str(part) for part in command),
            stop_command=tuple(str(part) for part in (stop_command or ())),
            host=host,
            cwd=Path(cwd) if cwd is not None else None,
            env=dict(env or {}),
            health_url=health_url,
            listener_identity_url=listener_identity_url,
            startup_timeout_seconds=startup_timeout_seconds,
            graceful_timeout_seconds=graceful_timeout_seconds,
            port_release_timeout_seconds=port_release_timeout_seconds,
        )


@dataclass(frozen=True, slots=True)
class ServiceState:
    name: str
    host: str
    port: int
    pid: int
    command: tuple[str, ...]
    started_at: str
    stdout_log: str
    stderr_log: str
    launch_authority_file: str
    stop_command: tuple[str, ...]
    health_url: str | None
    listener_identity_url: str | None
    listener_identity_fingerprint: str | None
    port_release_timeout_seconds: float


@dataclass(frozen=True, slots=True)
class StopResult:
    name: str
    port: int
    pid: int | None
    stopped: bool
    forced: bool
    reason: str
    stop_source: StopSource = StopSource.REGISTERED_PROCESS
    force_requested: bool = False


@dataclass(frozen=True, slots=True)
class LifecycleEvent:
    service_name: str
    state: LifecycleState
    reason: str
    generation: int
    host: str
    port: int
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LifecycleTransition:
    service_name: str
    from_state: LifecycleState | None
    to_state: LifecycleState
    reason: str


@dataclass(frozen=True, slots=True)
class LifecycleOperationResult:
    service_name: str
    succeeded: bool
    reason: str
    transition: LifecycleTransition | None = None


@dataclass(frozen=True, slots=True)
class ProcessProvenance:
    wrapper_pid: int | None = None
    listener_pid: int | None = None
    process_group_id: int | None = None
    start_time: str = ""
    command_fingerprint: str = ""
    command_line: str = ""
    listener_identity_fingerprint: str | None = None
    capability: ProvenanceCapability = ProvenanceCapability.WRAPPER_ONLY


@dataclass(frozen=True, slots=True)
class LiveServiceResolution:
    service_name: str
    host: str
    port: int
    source: LiveServiceResolutionSource
    scheme: str = "http"
    diagnostics: tuple[str, ...] = ()

    @property
    def base_url(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}"


@dataclass(frozen=True, slots=True)
class ResolvedPortPlan:
    ports_by_service: Mapping[str, int]

    def port_for(self, service_name: str) -> int:
        return int(self.ports_by_service[service_name])

    @property
    def ports(self) -> tuple[int, ...]:
        return tuple(int(port) for port in self.ports_by_service.values())


@dataclass(frozen=True, slots=True)
class LifecycleStepTiming:
    label: str
    elapsed_seconds: float
    status: str


@dataclass(frozen=True, slots=True)
class RestartResult:
    run_id: str
    stop_results: tuple[StopResult, ...]
    port_plan: Mapping[str, int]
    service_states: tuple[ServiceState, ...]
    timings: tuple[LifecycleStepTiming, ...]

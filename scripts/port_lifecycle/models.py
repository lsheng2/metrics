from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence


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

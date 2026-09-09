from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from . import platform_ops
from .diagnostics import ServiceDiagnosticCode, diagnostic_values
from .health import ServiceHealthSnapshot


_LIVE_LAUNCH_METADATA_STATES = {"prepared", "ready"}


@dataclass(frozen=True, slots=True)
class ServiceLaunchMetadata:
    started_at: str = ""
    source: str = ""
    diagnostics: tuple[ServiceDiagnosticCode | str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "started_at": self.started_at,
            "source": self.source,
            "diagnostics": diagnostic_values(self.diagnostics),
        }


ReadPidFileValue = Callable[[Path], int | None]
PidIsAlive = Callable[[int | None], bool]
ReadProcessStartedAt = Callable[[int], str | None]


@runtime_checkable
class PidFileReader(Protocol):
    def read_pid_file_value(self, path: Path) -> int | None:
        ...


@runtime_checkable
class ProcessMetadataProvider(Protocol):
    def pid_is_alive(self, pid: int | None) -> bool:
        ...

    def read_process_started_at(self, pid: int) -> str | None:
        ...


@runtime_checkable
class LifecycleStateReader(Protocol):
    def read_state(self) -> Mapping[str, Mapping[str, Any]]:
        ...


@runtime_checkable
class LaunchMetadataProvider(Protocol):
    def resolve_launch_metadata(self, service_name: str) -> ServiceLaunchMetadata:
        ...


@dataclass(frozen=True, slots=True)
class DefaultPidFileReader:
    def read_pid_file_value(self, path: Path) -> int | None:
        return read_pid_file_value(path)


@dataclass(frozen=True, slots=True)
class DefaultProcessMetadataProvider:
    def pid_is_alive(self, pid: int | None) -> bool:
        return pid_is_alive(pid)

    def read_process_started_at(self, pid: int) -> str | None:
        return read_process_started_at(pid)


@dataclass(frozen=True, slots=True)
class ServiceOperatorLink:
    rel: str
    href: str
    label: str = ""

    def as_dict(self) -> dict[str, str]:
        return {"rel": self.rel, "href": self.href, "label": self.label}


@dataclass(frozen=True, slots=True)
class ServiceOperatorAction:
    kind: str
    label: str = ""
    href: str = ""

    def as_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "label": self.label, "href": self.href}


@dataclass(frozen=True, slots=True)
class ServiceLiveSnapshot:
    service_name: str
    configured: bool
    lifecycle_state: object = "unknown"
    health: ServiceHealthSnapshot | None = None
    launch_metadata: ServiceLaunchMetadata = field(default_factory=ServiceLaunchMetadata)
    provenance: Mapping[str, Any] | None = None
    base_url: str = ""
    health_url: str = ""
    links: tuple[ServiceOperatorLink, ...] = ()
    actions: tuple[ServiceOperatorAction, ...] = ()
    diagnostics: tuple[ServiceDiagnosticCode | str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        lifecycle_state = getattr(self.lifecycle_state, "value", self.lifecycle_state)
        payload: dict[str, Any] = {
            "service_id": self.service_name,
            "configured": self.configured,
            "lifecycle_state": str(lifecycle_state or "unknown"),
            "launch_metadata": self.launch_metadata.as_dict(),
            "links": [link.as_dict() for link in self.links],
            "actions": [action.as_dict() for action in self.actions],
            "diagnostics": diagnostic_values(self.diagnostics),
        }
        if self.health is not None:
            payload["health"] = self.health.as_dict()
        if self.provenance is not None:
            payload["provenance"] = dict(self.provenance)
        if self.base_url:
            payload["base_url"] = self.base_url
        if self.health_url:
            payload["health_url"] = self.health_url
        return payload


def resolve_lifecycle_service_launch_metadata(
    services: Mapping[str, Mapping[str, Any]] | LifecycleStateReader,
    service_name: str,
    *,
    source: str = "service-lifecycle-engine",
) -> ServiceLaunchMetadata:
    state = services.read_state() if hasattr(services, "read_state") else services
    service = state.get(service_name)
    if service is None:
        return ServiceLaunchMetadata(source=source, diagnostics=(ServiceDiagnosticCode.NOT_REGISTERED,))

    lifecycle_state = str(service.get("lifecycle_state") or "").strip().lower()
    if not lifecycle_state:
        return ServiceLaunchMetadata(source=source, diagnostics=(ServiceDiagnosticCode.STATE_MISSING,))
    if lifecycle_state not in _LIVE_LAUNCH_METADATA_STATES:
        return ServiceLaunchMetadata(source=source, diagnostics=(ServiceDiagnosticCode.STATE_NOT_LIVE,))

    started_at = service.get("started_at")
    if not isinstance(started_at, str) or not started_at:
        return ServiceLaunchMetadata(source=source, diagnostics=(ServiceDiagnosticCode.STARTED_AT_UNAVAILABLE,))
    return ServiceLaunchMetadata(started_at=started_at, source=source)


def resolve_pid_file_launch_metadata(
    pid_file: str | Path,
    *,
    source: str,
    pid_file_reader: PidFileReader | None = None,
    process_provider: ProcessMetadataProvider | None = None,
    read_pid_file_value: ReadPidFileValue | None = None,
    pid_is_alive: PidIsAlive | None = None,
    read_process_started_at: ReadProcessStartedAt | None = None,
) -> ServiceLaunchMetadata:
    resolved_read_pid_file_value = (
        pid_file_reader.read_pid_file_value
        if pid_file_reader is not None
        else read_pid_file_value or globals()["read_pid_file_value"]
    )
    resolved_pid_is_alive = (
        process_provider.pid_is_alive
        if process_provider is not None
        else pid_is_alive or globals()["pid_is_alive"]
    )
    resolved_read_process_started_at = (
        process_provider.read_process_started_at
        if process_provider is not None
        else read_process_started_at or globals()["read_process_started_at"]
    )
    pid = resolved_read_pid_file_value(Path(pid_file))
    if pid is None:
        return ServiceLaunchMetadata(source=source, diagnostics=(ServiceDiagnosticCode.PID_UNAVAILABLE,))
    if not resolved_pid_is_alive(pid):
        return ServiceLaunchMetadata(source=source, diagnostics=(ServiceDiagnosticCode.PID_NOT_ALIVE,))
    started_at = resolved_read_process_started_at(pid)
    if not started_at:
        return ServiceLaunchMetadata(source=source, diagnostics=(ServiceDiagnosticCode.STARTED_AT_UNAVAILABLE,))
    return ServiceLaunchMetadata(started_at=started_at, source=source)


def merge_service_launch_metadata(
    payload: Mapping[str, Any],
    metadata: ServiceLaunchMetadata,
) -> dict[str, Any]:
    enriched = dict(payload)
    existing_started_at = enriched.get("started_at")
    if metadata.started_at and (not isinstance(existing_started_at, str) or not existing_started_at):
        enriched["started_at"] = metadata.started_at
        enriched["launch_metadata_source"] = metadata.source
    if metadata.diagnostics:
        enriched["launch_metadata_diagnostics"] = diagnostic_values(metadata.diagnostics)
    return enriched


def read_pid_file_value(path: Path) -> int | None:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = text
    if isinstance(payload, Mapping):
        value = payload.get("pid")
    else:
        value = payload
    try:
        pid = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return pid if pid > 0 else None


def pid_is_alive(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False
    return platform_ops.process_exists(pid)


def read_process_started_at(pid: int) -> str | None:
    if pid <= 0 or os.name != "posix":
        return None
    try:
        stat_path = Path("/proc") / str(pid) / "stat"
        raw_stat = stat_path.read_text(encoding="utf-8").strip()
        _prefix, stat_suffix = raw_stat.rsplit(") ", 1)
        stat_fields = stat_suffix.split()
        if len(stat_fields) <= 19:
            return None
        start_ticks = int(stat_fields[19])
        clock_ticks = os.sysconf("SC_CLK_TCK")
        boot_time_epoch = _linux_boot_time_epoch()
        if boot_time_epoch is None or clock_ticks <= 0:
            return None
        return datetime.fromtimestamp(boot_time_epoch + (start_ticks / clock_ticks), tz=UTC).isoformat(timespec="microseconds")
    except (AttributeError, OSError, ValueError, IndexError):
        return None


def _linux_boot_time_epoch() -> float | None:
    try:
        for line in Path("/proc/stat").read_text(encoding="utf-8").splitlines():
            if line.startswith("btime "):
                return float(line.split()[1])
    except (OSError, ValueError, IndexError):
        return None
    return None


__all__ = [
    "DefaultPidFileReader",
    "DefaultProcessMetadataProvider",
    "LaunchMetadataProvider",
    "LifecycleStateReader",
    "PidFileReader",
    "PidIsAlive",
    "ProcessMetadataProvider",
    "ReadPidFileValue",
    "ReadProcessStartedAt",
    "ServiceLaunchMetadata",
    "ServiceLiveSnapshot",
    "ServiceOperatorAction",
    "ServiceOperatorLink",
    "merge_service_launch_metadata",
    "pid_is_alive",
    "read_pid_file_value",
    "read_process_started_at",
    "resolve_lifecycle_service_launch_metadata",
    "resolve_pid_file_launch_metadata",
]

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime

from .models import LifecycleState, ProcessProvenance, ServiceState
from .provenance import process_provenance_from_mapping


def build_external_service_state(
    *,
    service_name: str,
    lifecycle_state: LifecycleState | str,
    host: str,
    port: int,
    pid: int | None = None,
    command: Sequence[str] | None = None,
    started_at: str = "",
    stdout_log: str = "",
    stderr_log: str = "",
    launch_authority_file: str = "",
    stop_command: Sequence[str] | None = None,
    health_url: str | None = None,
    listener_identity_url: str | None = None,
    listener_identity_fingerprint: str | None = None,
    port_release_timeout_seconds: float = 2.0,
    provenance: ProcessProvenance | None = None,
    prior_state: Mapping[str, object] | None = None,
    now: Callable[[], str] | None = None,
) -> ServiceState:
    prior = prior_state or {}
    resolved_state = lifecycle_state if isinstance(lifecycle_state, LifecycleState) else LifecycleState(str(lifecycle_state))
    return ServiceState(
        name=service_name,
        host=host or str(prior.get("host") or "127.0.0.1"),
        port=int(port or prior.get("port") or 0),
        pid=_int_or_none(pid) or _int_or_none(prior.get("pid")) or 0,
        command=tuple(command or _string_sequence(prior.get("command"))),
        started_at=started_at or str(prior.get("started_at") or "") or _utc_now(now),
        stdout_log=stdout_log or str(prior.get("stdout_log") or ""),
        stderr_log=stderr_log or str(prior.get("stderr_log") or ""),
        launch_authority_file=launch_authority_file or str(prior.get("launch_authority_file") or ""),
        stop_command=tuple(stop_command or _string_sequence(prior.get("stop_command"))),
        health_url=health_url if health_url is not None else _optional_str(prior.get("health_url")),
        listener_identity_url=listener_identity_url
        if listener_identity_url is not None
        else _optional_str(prior.get("listener_identity_url")),
        listener_identity_fingerprint=listener_identity_fingerprint
        if listener_identity_fingerprint is not None
        else _optional_str(prior.get("listener_identity_fingerprint")),
        port_release_timeout_seconds=float(port_release_timeout_seconds or prior.get("port_release_timeout_seconds") or 2.0),
        provenance=provenance or process_provenance_from_mapping(prior.get("provenance")),
        lifecycle_state=resolved_state,
    )


def _utc_now(now: Callable[[], str] | None) -> str:
    return now() if now is not None else datetime.now(UTC).isoformat(timespec="microseconds")


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _int_or_none(value: object) -> int | None:
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        return None
    return resolved if resolved > 0 else None


def _string_sequence(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item) for item in value)


__all__ = ["build_external_service_state"]

from __future__ import annotations

import hashlib
import json

from .models import ProcessProvenance, ProvenanceCapability
from .platform import PlatformOperationSet


def capture_process_provenance(
    platform_ops: PlatformOperationSet,
    wrapper_pid: int | None,
    command: tuple[str, ...],
    host: str,
    port: int,
    health_url: str | None = None,
    listener_identity_url: str | None = None,
) -> ProcessProvenance:
    command_matches = bool(wrapper_pid and platform_ops.process_exists(wrapper_pid) and platform_ops.process_matches_command(wrapper_pid, command))
    listener_pid = resolve_owned_listener(platform_ops, host, port, wrapper_pid)
    identity_fingerprint = capture_listener_identity(platform_ops, listener_identity_url)
    endpoint_reachable = platform_ops.http_status_ok(health_url) if health_url else False
    if listener_pid is None and endpoint_reachable:
        listener_pids = tuple(int(pid) for pid in platform_ops.get_listening_process_ids(host, port))
        if len(listener_pids) == 1:
            listener_pid = listener_pids[0]
    return ProcessProvenance(
        wrapper_pid=wrapper_pid,
        listener_pid=listener_pid,
        process_group_id=platform_ops.process_group_id(wrapper_pid) if wrapper_pid else None,
        process_start_marker=platform_ops.process_start_marker(wrapper_pid) if wrapper_pid else "",
        command_fingerprint=command_fingerprint(command),
        command_line=platform_ops.process_command_line(wrapper_pid) if wrapper_pid else "",
        listener_identity_fingerprint=identity_fingerprint,
        capability=provenance_capability_for(
            wrapper_pid=wrapper_pid,
            command_matches=command_matches,
            listener_pid=listener_pid,
            endpoint_reachable=endpoint_reachable,
            listener_identity_fingerprint=identity_fingerprint,
        ),
    )


def resolve_owned_listener(platform_ops: PlatformOperationSet, host: str, port: int, wrapper_pid: int | None) -> int | None:
    if wrapper_pid is None:
        return None
    listener_pids = tuple(int(pid) for pid in platform_ops.get_listening_process_ids(host, port))
    if wrapper_pid in listener_pids:
        return wrapper_pid
    owned_pids = platform_ops.owned_listener_pids(host, port, wrapper_pid)
    if owned_pids:
        return owned_pids[0]
    if not platform_ops.process_exists(wrapper_pid) and len(listener_pids) == 1:
        return listener_pids[0]
    return None


def provenance_capability_for(
    wrapper_pid: int | None,
    command_matches: bool,
    listener_pid: int | None,
    endpoint_reachable: bool,
    listener_identity_fingerprint: str | None,
) -> ProvenanceCapability:
    if wrapper_pid is None:
        return ProvenanceCapability.WRAPPER_ONLY
    if listener_identity_fingerprint and listener_pid is not None:
        return ProvenanceCapability.HTTP_IDENTITY
    if endpoint_reachable and listener_pid is not None:
        return ProvenanceCapability.ENDPOINT_GRADE
    if listener_pid is not None:
        return ProvenanceCapability.OWNED_LISTENER
    if command_matches:
        return ProvenanceCapability.REGISTERED_PROCESS
    if wrapper_pid is not None:
        return ProvenanceCapability.WRAPPER_ONLY
    return ProvenanceCapability.WRAPPER_ONLY


def capture_listener_identity(platform_ops: PlatformOperationSet, listener_identity_url: str | None) -> str | None:
    if listener_identity_url is None:
        return None
    probe = platform_ops.http_probe(listener_identity_url)
    fingerprint = probe.get("body_sha256")
    return str(fingerprint) if isinstance(fingerprint, str) else None


def command_fingerprint(command: tuple[str, ...]) -> str:
    payload = json.dumps(list(command), separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def process_provenance_from_mapping(value: object) -> ProcessProvenance | None:
    if not isinstance(value, dict):
        return None
    capability = value.get("capability")
    return ProcessProvenance(
        wrapper_pid=optional_int(value.get("wrapper_pid")),
        listener_pid=optional_int(value.get("listener_pid")),
        process_group_id=optional_int(value.get("process_group_id")),
        process_start_marker=str(value.get("process_start_marker") or ""),
        start_time=str(value.get("start_time") or ""),
        command_fingerprint=str(value.get("command_fingerprint") or ""),
        command_line=str(value.get("command_line") or ""),
        listener_identity_fingerprint=str(value["listener_identity_fingerprint"]) if value.get("listener_identity_fingerprint") else None,
        capability=provenance_capability_from_value(capability),
    )


def optional_int(value: object) -> int | None:
    if value is None:
        return None
    return int(value)


def provenance_capability_from_value(value: object) -> ProvenanceCapability:
    if value is None:
        return ProvenanceCapability.WRAPPER_ONLY
    try:
        return ProvenanceCapability(str(value))
    except ValueError:
        return ProvenanceCapability.WRAPPER_ONLY

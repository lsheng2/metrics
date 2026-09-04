from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Mapping

from .models import LifecycleState, LifecycleStateStoreError, ProvenanceCapability, ServiceSpec, ServiceState, StopResult
from .provenance import process_provenance_from_mapping

SAFE_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


class LifecycleStorageMixin:
    def write_launch_authority(self, spec: ServiceSpec, port: int, pid: int, stdout_log: Path, stderr_log: Path, command: tuple[str, ...]) -> None:
        self._validate_service_name(spec.name)
        health_url = spec.health_url.format(port=port, host=spec.host, workspace=str(self.workspace)) if spec.health_url else None
        identity_probe = self.platform_ops.http_probe(self._format_url(spec.listener_identity_url, port, spec.host)) if spec.listener_identity_url else None
        authority = {
            "project": self.project_name,
            "instance": self.instance_name,
            "service": spec.name,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "host": spec.host,
            "port": port,
            "wrapper_pid": pid,
            "health_url": health_url,
            "health_reachable": self.platform_ops.http_status_ok(health_url) if health_url else None,
            "listener_identity_url": self._format_url(spec.listener_identity_url, port, spec.host) if spec.listener_identity_url else None,
            "listener_identity_probe": identity_probe,
            "command": list(command),
            "stdout_log": str(stdout_log),
            "stderr_log": str(stderr_log),
            "notes": [
                "Cross-platform launcher records owned wrapper PID and health endpoint.",
                "If a service uses a wrapper that outlives or detaches from its listener, provide a service-specific stop_command.",
            ],
        }
        self._authority_file(spec.name).write_text(json.dumps(authority, indent=2, sort_keys=True), encoding="utf-8")

    def write_termination_record(self, result: StopResult) -> None:
        record = {
            "project": self.project_name,
            "instance": self.instance_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": result.name,
            "port": result.port,
            "pid": result.pid,
            "stopped": result.stopped,
            "forced": result.forced,
            "reason": result.reason,
            "stop_source": result.stop_source.value,
            "force_requested": result.force_requested,
        }
        if result.provenance:
            record["provenance"] = asdict(result.provenance)
        with self.state_store.lock(self._store_lock_key("termination-ledger")):
            self.state_store.append_jsonl(self.termination_ledger, json_ready(record))

    def write_startup_record(self, label: str, elapsed_seconds: float, status: str, run_id: str | None = None, details: Mapping[str, object] | None = None) -> None:
        record = {
            "project": self.project_name,
            "instance": self.instance_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "step_timing",
            "label": label,
            "elapsed_seconds": round(elapsed_seconds, 3),
            "status": status,
        }
        if run_id:
            record["run_id"] = run_id
        if details:
            record["details"] = dict(details)
        with self.state_store.lock(self._store_lock_key("startup-ledger")):
            self.state_store.append_jsonl(self.startup_ledger, json_ready(record))

    def read_state(self) -> dict[str, dict[str, object]]:
        return self._read_state_unlocked()

    def _read_state_unlocked(self) -> dict[str, dict[str, object]]:
        if not self.state_store.exists(self.state_file):
            return {}
        try:
            payload = self.state_store.read_json(self.state_file)
        except LifecycleStateStoreError:
            raise
        services = payload.get("services", {})
        if not isinstance(services, dict):
            raise LifecycleStateStoreError(f"Lifecycle services payload is not an object: {self.state_file}", "state_corrupt")
        for service_name, service in services.items():
            self._validate_service_name(str(service_name))
            if not isinstance(service, dict):
                raise LifecycleStateStoreError(f"Lifecycle service record is not an object: {service_name}", "state_corrupt")
            self._validate_service_record(str(service_name), service)
        return dict(services)

    def write_state(self, services: Mapping[str, Mapping[str, object]]) -> None:
        with self.state_store.lock(self._store_lock_key("state")):
            self._write_state_unlocked(services)

    def _write_state_unlocked(self, services: Mapping[str, Mapping[str, object]]) -> None:
        for service_name in services:
            self._validate_service_name(str(service_name))
        payload = {
            "project": self.project_name,
            "instance": self.instance_name,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "services": json_ready(services),
        }
        self.state_store.write_json_atomic(self.state_file, payload)

    def _write_service_state(self, service_state: ServiceState) -> None:
        with self.state_store.lock(self._store_lock_key("state")):
            state = self._read_state_unlocked()
            state[service_state.name] = asdict(service_state)
            self._write_state_unlocked(state)

    def _replace_service_record(self, name: str, service: Mapping[str, object]) -> None:
        with self.state_store.lock(self._store_lock_key("state")):
            state = self._read_state_unlocked()
            state[name] = service
            self._write_state_unlocked(state)

    def _pid_file(self, name: str, port: int) -> Path:
        self._validate_service_name(name)
        return self.pid_directory / f"{self.project_name}-{self.instance_name}-{name}-{port}.pid"

    def _authority_file(self, name: str) -> Path:
        self._validate_service_name(name)
        return self.authority_directory / f"{self.project_name}-{self.instance_name}-{name}.json"

    def _write_pid_file(self, name: str, port: int, pid: int, command: tuple[str, ...]) -> None:
        payload = {"name": name, "port": port, "pid": pid, "command": list(command)}
        self._pid_file(name, port).write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    def _read_pid_file(self, pid_file: Path) -> dict[str, int | str] | None:
        try:
            payload = json.loads(pid_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not {"name", "port", "pid"}.issubset(payload):
            return None
        result: dict[str, int | str] = {"name": str(payload["name"]), "port": int(payload["port"]), "pid": int(payload["pid"])}
        result["command"] = json.dumps([str(part) for part in payload["command"]]) if isinstance(payload.get("command"), list) else "[]"
        return result

    def _service_event(self, name: str, port: int, pid: int, kind: str, details: Mapping[str, object] | None = None) -> dict[str, object]:
        event = {"project": self.project_name, "instance": self.instance_name, "service": name, "port": port, "pid": pid, "kind": kind, "timestamp": datetime.now(timezone.utc).isoformat()}
        if details:
            event.update(details)
        return event

    def _store_lock_key(self, scope: str) -> str:
        return f"{self.project_name}:{self.instance_name}:{scope}"

    def _validate_service_name(self, value: str) -> None:
        validate_lifecycle_identifier("service_name", value)

    def _validate_service_record(self, service_name: str, service: Mapping[str, object]) -> None:
        required_fields = ("pid", "port", "lifecycle_state")
        missing_fields = [field for field in required_fields if field not in service]
        if missing_fields:
            raise LifecycleStateStoreError(f"Lifecycle service record {service_name} is missing: {', '.join(missing_fields)}", "state_corrupt")
        try:
            int(service["pid"])
            int(service["port"])
            LifecycleState(str(service["lifecycle_state"]))
            self._validate_provenance_record(str(service_name), service.get("provenance"))
        except (TypeError, ValueError) as error:
            raise LifecycleStateStoreError(f"Lifecycle service record {service_name} has invalid identity or state", "state_corrupt") from error

    def _validate_provenance_record(self, service_name: str, provenance: object) -> None:
        if provenance is None:
            return
        if not isinstance(provenance, dict):
            raise LifecycleStateStoreError(f"Lifecycle service record {service_name} has invalid provenance", "state_corrupt")
        capability = provenance.get("capability")
        if capability is not None:
            ProvenanceCapability(str(capability))
        process_provenance_from_mapping(provenance)

    def _diagnostic_status(self, service: Mapping[str, object] | None, process_running: bool, command_matches: bool | None, health_reachable: bool | None, identity_changed: bool = False) -> str:
        if service is None:
            return "not_registered"
        if not process_running:
            return "pid_missing"
        if command_matches is None:
            return "identity_unknown"
        if command_matches is False:
            return "identity_mismatch"
        if health_reachable is False:
            return "health_unreachable"
        if identity_changed:
            return "listener_identity_changed"
        return "ok"


def validate_lifecycle_identifier(label: str, value: str) -> None:
    if not SAFE_IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"{label} must contain only letters, numbers, dot, underscore or hyphen: {value!r}")


def json_ready(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    return value

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from .models import LifecycleStateStoreError, ServiceSpec, ServiceState, StopResult
from .platform_ops import http_probe, http_status_ok


class LifecycleStorageMixin:
    def write_launch_authority(self, spec: ServiceSpec, port: int, pid: int, stdout_log: Path, stderr_log: Path) -> None:
        health_url = spec.health_url.format(port=port, host=spec.host, workspace=str(self.workspace)) if spec.health_url else None
        identity_probe = http_probe(self._format_url(spec.listener_identity_url, port, spec.host)) if spec.listener_identity_url else None
        authority = {
            "project": self.project_name,
            "instance": self.instance_name,
            "service": spec.name,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "host": spec.host,
            "port": port,
            "wrapper_pid": pid,
            "health_url": health_url,
            "health_reachable": http_status_ok(health_url) if health_url else None,
            "listener_identity_url": self._format_url(spec.listener_identity_url, port, spec.host) if spec.listener_identity_url else None,
            "listener_identity_probe": identity_probe,
            "command": list(spec.command),
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
        self.state_store.append_jsonl(self.termination_ledger, record)

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
        self.state_store.append_jsonl(self.startup_ledger, record)

    def read_state(self) -> dict[str, dict[str, object]]:
        if not self.state_file.exists():
            return {}
        try:
            payload = self.state_store.read_json(self.state_file)
        except LifecycleStateStoreError:
            raise
        services = payload.get("services", {})
        return dict(services) if isinstance(services, dict) else {}

    def write_state(self, services: Mapping[str, Mapping[str, object]]) -> None:
        payload = {
            "project": self.project_name,
            "instance": self.instance_name,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "services": services,
        }
        self.state_store.write_json_atomic(self.state_file, payload)

    def _write_service_state(self, service_state: ServiceState) -> None:
        state = self.read_state()
        state[service_state.name] = asdict(service_state)
        self.write_state(state)

    def _pid_file(self, name: str, port: int) -> Path:
        return self.pid_directory / f"{self.project_name}-{self.instance_name}-{name}-{port}.pid"

    def _authority_file(self, name: str) -> Path:
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

    def _diagnostic_status(self, service: Mapping[str, object] | None, process_running: bool, command_matches: bool | None, health_reachable: bool | None) -> str:
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
        return "ok"

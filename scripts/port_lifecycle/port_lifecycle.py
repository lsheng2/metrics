from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping, Sequence

from .models import ServiceSpec, ServiceState, StopResult
from .platform_ops import creation_flags, get_listening_process_ids, http_probe, http_status_ok, is_port_available, kill_process, process_exists, process_matches_command, terminate_process, wait_port_available, wait_process_exit


class PortLifecycle:
    def __init__(
        self,
        project_name: str,
        workspace: str | Path,
        instance_name: str = "default",
        state_directory: str | Path | None = None,
        pid_directory: str | Path | None = None,
        log_directory: str | Path | None = None,
    ) -> None:
        self.project_name = project_name
        self.instance_name = instance_name
        self.workspace = Path(workspace).resolve()
        self.state_directory = Path(state_directory) if state_directory else self.workspace / "state" / "port-lifecycle"
        self.pid_directory = Path(pid_directory) if pid_directory else self.state_directory / "pids"
        self.log_directory = Path(log_directory) if log_directory else self.state_directory / "logs"
        self.authority_directory = self.state_directory / "launch-authority"
        self.termination_ledger = self.state_directory / "termination-ledger.jsonl"
        self.state_file = self.state_directory / f"{self.project_name}-{self.instance_name}.json"
        self.state_directory.mkdir(parents=True, exist_ok=True)
        self.pid_directory.mkdir(parents=True, exist_ok=True)
        self.log_directory.mkdir(parents=True, exist_ok=True)
        self.authority_directory.mkdir(parents=True, exist_ok=True)

    def resolve_port(self, spec: ServiceSpec) -> int:
        return self._resolve_port(spec, set())

    def resolve_plan(self, specs: Sequence[ServiceSpec]) -> dict[str, int]:
        plan: dict[str, int] = {}
        reserved_ports: set[int] = set()
        for spec in specs:
            port = self._resolve_port(spec, reserved_ports)
            plan[spec.name] = port
            reserved_ports.add(port)
        return plan

    def _resolve_port(self, spec: ServiceSpec, reserved_ports: set[int]) -> int:
        state = self.read_state()
        owned_port = state.get(spec.name, {}).get("port")
        owned_pid = state.get(spec.name, {}).get("pid")
        if owned_port in spec.preferred_ports and int(owned_port) not in reserved_ports and owned_pid and process_exists(int(owned_pid)):
            return int(owned_port)

        for port in spec.preferred_ports:
            if port not in reserved_ports and is_port_available(spec.host, port):
                return port
        raise RuntimeError(f"No available port for {spec.name}: {', '.join(str(port) for port in spec.preferred_ports)}")

    def start_service(self, spec: ServiceSpec, port: int | None = None) -> ServiceState:
        selected_port = port if port is not None else self.resolve_port(spec)
        existing = self.read_state().get(spec.name)
        if existing:
            self.stop_service(spec.name, graceful_timeout_seconds=spec.graceful_timeout_seconds)
            if spec.name in self.read_state():
                raise RuntimeError(f"Existing {spec.name} did not stop; refusing to overwrite lifecycle state")

        stdout_log = self.log_directory / f"{spec.name}-{selected_port}.out.log"
        stderr_log = self.log_directory / f"{spec.name}-{selected_port}.err.log"
        command = tuple(part.format(port=selected_port, host=spec.host, workspace=str(self.workspace)) for part in spec.command)
        environment = os.environ.copy()
        environment.update(spec.env)

        with stdout_log.open("wb") as stdout, stderr_log.open("wb") as stderr:
            process = subprocess.Popen(
                command,
                cwd=str(spec.cwd or self.workspace),
                env=environment,
                stdout=stdout,
                stderr=stderr,
                creationflags=creation_flags(),
            )

        try:
            self.wait_ready(spec, selected_port, process)
            authority_file = self._authority_file(spec.name)
            state = ServiceState(
                name=spec.name,
                host=spec.host,
                port=selected_port,
                pid=process.pid,
                command=command,
                started_at=datetime.now(timezone.utc).isoformat(),
                stdout_log=str(stdout_log),
                stderr_log=str(stderr_log),
                launch_authority_file=str(authority_file),
                stop_command=spec.stop_command,
                health_url=self._format_url(spec.health_url, selected_port, spec.host) if spec.health_url else None,
                listener_identity_url=self._format_url(spec.listener_identity_url, selected_port, spec.host) if spec.listener_identity_url else None,
                listener_identity_fingerprint=self._listener_identity_fingerprint(spec, selected_port),
                port_release_timeout_seconds=spec.port_release_timeout_seconds,
            )
            self._write_service_state(state)
            self._write_pid_file(spec.name, selected_port, process.pid, command)
            self.write_launch_authority(spec, selected_port, process.pid, stdout_log, stderr_log)
        except Exception:
            if process.poll() is None:
                terminate_process(process.pid)
                if not wait_process_exit(process.pid, 0.5):
                    kill_process(process.pid)
            raise
        return state

    def wait_ready(self, spec: ServiceSpec, port: int, process: subprocess.Popen[bytes] | None = None) -> None:
        deadline = time.monotonic() + spec.startup_timeout_seconds
        health_url = spec.health_url.format(port=port, host=spec.host, workspace=str(self.workspace)) if spec.health_url else None

        while time.monotonic() < deadline:
            if process and process.poll() is not None:
                raise RuntimeError(f"{spec.name} exited before becoming ready")
            if health_url and http_status_ok(health_url):
                return
            if not health_url and not is_port_available(spec.host, port):
                return
            time.sleep(0.2)
        raise TimeoutError(f"Timed out waiting for {spec.name} on {spec.host}:{port}")

    def write_launch_authority(
        self,
        spec: ServiceSpec,
        port: int,
        pid: int,
        stdout_log: Path,
        stderr_log: Path,
    ) -> None:
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

    def stop_service(self, name: str, graceful_timeout_seconds: float = 5.0) -> StopResult:
        state = self.read_state()
        service = state.get(name)
        if not service:
            return StopResult(name=name, port=-1, pid=None, stopped=False, forced=False, reason="not_registered")

        pid = int(service["pid"])
        port = int(service["port"])
        forced = False
        stopped = False
        reason = "not_running"
        command = tuple(str(part) for part in service.get("command", ()))

        spec_stop_command = tuple(str(part) for part in service.get("stop_command", ()))
        was_running = process_exists(pid)
        owns_running_process = was_running and process_matches_command(pid, command)
        if was_running and not owns_running_process:
            reason = "identity_mismatch"

        if spec_stop_command and owns_running_process:
            self._run_stop_command(spec_stop_command, port, str(service.get("host", "127.0.0.1")))
            if wait_process_exit(pid, graceful_timeout_seconds):
                stopped = True
                reason = "stop_command"

        if not stopped and owns_running_process and process_exists(pid):
            terminate_process(pid)
            if wait_process_exit(pid, graceful_timeout_seconds):
                stopped = True
                reason = "terminated"
            else:
                kill_process(pid)
                forced = True
                stopped = wait_process_exit(pid, 2.0)
                reason = "killed" if stopped else "kill_attempted"

            if stopped and not wait_port_available(str(service.get("host", "127.0.0.1")), port, float(service.get("port_release_timeout_seconds", 2.0))):
                reason = "process_stopped_port_still_busy"

        result = StopResult(name=name, port=port, pid=pid, stopped=stopped, forced=forced, reason=reason)
        if not process_exists(pid):
            self._pid_file(name, port).unlink(missing_ok=True)
            self._authority_file(name).unlink(missing_ok=True)
            state.pop(name, None)
            self.write_state(state)
        self.write_termination_record(result)
        return result

    def stop_all(self, graceful_timeout_seconds: float = 5.0) -> list[StopResult]:
        service_names = list(self.read_state().keys())
        results = [self.stop_service(name, graceful_timeout_seconds=graceful_timeout_seconds) for name in service_names]
        results.extend(self.stop_orphaned_pid_files(graceful_timeout_seconds=graceful_timeout_seconds))
        if not self.read_state():
            self.state_file.unlink(missing_ok=True)
        return results

    def force_stop_by_ports(
        self,
        service_specs: Sequence[ServiceSpec],
        graceful_timeout_seconds: float = 0.5,
        port_process_resolver: Callable[[str, int], Sequence[int]] = get_listening_process_ids,
    ) -> list[StopResult]:
        results: list[StopResult] = []
        for spec in service_specs:
            for port in spec.preferred_ports:
                for pid in sorted({int(value) for value in port_process_resolver(spec.host, port)}):
                    result = self._stop_process(spec.name, port, pid, graceful_timeout_seconds, "force_by_port")
                    self.write_termination_record(result)
                    results.append(result)
        return results

    def check_services(self, callback: Callable[[dict[str, object]], None] | None = None) -> list[dict[str, object]]:
        events: list[dict[str, object]] = []
        for name, service in self.read_state().items():
            pid = int(service["pid"])
            port = int(service["port"])
            if not process_exists(pid):
                events.append(self._service_event(name, port, pid, "pid_missing"))
                continue
            health_url = service.get("health_url")
            if isinstance(health_url, str) and health_url and not http_status_ok(health_url):
                events.append(self._service_event(name, port, pid, "health_unreachable", {"health_url": health_url}))
            identity_url = service.get("listener_identity_url")
            expected_fingerprint = service.get("listener_identity_fingerprint")
            if isinstance(identity_url, str) and identity_url and isinstance(expected_fingerprint, str):
                observed = http_probe(identity_url)
                if observed.get("body_sha256") != expected_fingerprint:
                    events.append(self._service_event(name, port, pid, "listener_identity_changed", {"identity_url": identity_url, "observed": observed}))
        if callback:
            for event in events:
                callback(event)
        return events

    def stop_orphaned_pid_files(self, graceful_timeout_seconds: float = 5.0) -> list[StopResult]:
        results: list[StopResult] = []
        known_services = set(self.read_state().keys())
        for pid_file in self.pid_directory.glob(f"{self.project_name}-{self.instance_name}-*.pid"):
            payload = self._read_pid_file(pid_file)
            if payload is None or payload["name"] in known_services:
                continue
            result = self._stop_pid_payload(payload, graceful_timeout_seconds)
            self.write_termination_record(result)
            results.append(result)
            if not process_exists(int(payload["pid"])):
                pid_file.unlink(missing_ok=True)
        return results

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
        }
        with self.termination_ledger.open("a", encoding="utf-8") as ledger:
            ledger.write(json.dumps(record, sort_keys=True) + "\n")

    def read_state(self) -> dict[str, dict[str, object]]:
        if not self.state_file.exists():
            return {}
        payload = json.loads(self.state_file.read_text(encoding="utf-8"))
        return dict(payload.get("services", {}))

    def write_state(self, services: Mapping[str, Mapping[str, object]]) -> None:
        payload = {
            "project": self.project_name,
            "instance": self.instance_name,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "services": services,
        }
        self.state_file.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def _write_service_state(self, service_state: ServiceState) -> None:
        state = self.read_state()
        state[service_state.name] = asdict(service_state)
        self.write_state(state)

    def _run_stop_command(self, stop_command: tuple[str, ...], port: int, host: str) -> None:
        command = tuple(part.format(port=port, host=host, workspace=str(self.workspace)) for part in stop_command)
        subprocess.run(command, cwd=self.workspace, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

    def _format_url(self, value: str | None, port: int, host: str) -> str:
        if value is None:
            return ""
        return value.format(port=port, host=host, workspace=str(self.workspace))

    def _listener_identity_fingerprint(self, spec: ServiceSpec, port: int) -> str | None:
        if spec.listener_identity_url is None:
            return None
        probe = http_probe(self._format_url(spec.listener_identity_url, port, spec.host))
        fingerprint = probe.get("body_sha256")
        return str(fingerprint) if isinstance(fingerprint, str) else None

    def _service_event(self, name: str, port: int, pid: int, kind: str, details: Mapping[str, object] | None = None) -> dict[str, object]:
        event = {"project": self.project_name, "instance": self.instance_name, "service": name, "port": port, "pid": pid, "kind": kind, "timestamp": datetime.now(timezone.utc).isoformat()}
        if details:
            event.update(details)
        return event

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

    def _stop_pid_payload(self, payload: Mapping[str, int | str], graceful_timeout_seconds: float) -> StopResult:
        expected_command = tuple(json.loads(str(payload.get("command", "[]"))))
        if not expected_command:
            return StopResult(str(payload["name"]), int(payload["port"]), int(payload["pid"]), False, False, "pid_file_recovery:missing_identity")
        return self._stop_process(str(payload["name"]), int(payload["port"]), int(payload["pid"]), graceful_timeout_seconds, "pid_file_recovery", expected_command)

    def _stop_process(self, name: str, port: int, pid: int, graceful_timeout_seconds: float, source: str, expected_command: tuple[str, ...] = ()) -> StopResult:
        forced = False
        stopped = False
        reason = "not_running"
        if process_exists(pid):
            if expected_command and not process_matches_command(pid, expected_command):
                return StopResult(name=name, port=port, pid=pid, stopped=False, forced=False, reason=f"{source}:identity_mismatch")
            terminate_process(pid)
            if wait_process_exit(pid, graceful_timeout_seconds):
                stopped = True
                reason = "terminated"
            else:
                kill_process(pid)
                forced = True
                stopped = wait_process_exit(pid, 2.0)
                reason = "killed" if stopped else "kill_attempted"
        return StopResult(name=name, port=port, pid=pid, stopped=stopped, forced=forced, reason=f"{source}:{reason}")

__all__ = [
    "PortLifecycle",
    "ServiceSpec",
    "ServiceState",
    "StopResult",
    "is_port_available",
    "process_exists",
]

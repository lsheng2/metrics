from __future__ import annotations

import json
from typing import Callable, Mapping, Sequence

from .models import LifecycleState, ProcessProvenance, ProvenanceCapability, ServiceSpec, StopResult, StopSource
from .state_store import FilesystemLifecycleStateStore


class LifecycleStoppingMixin:
    def stop_service(self, name: str, graceful_timeout_seconds: float = 5.0) -> StopResult:
        state = self.read_state()
        service = state.get(name)
        if not service:
            return StopResult(name=name, port=-1, pid=None, stopped=False, forced=False, reason="not_registered", stop_source=StopSource.NOT_REGISTERED)
        if service.get("lifecycle_state") == LifecycleState.STOPPED.value:
            return StopResult(name=name, port=int(service.get("port", -1)), pid=int(service["pid"]) if service.get("pid") is not None else None, stopped=True, forced=False, reason="already_stopped")

        pid = int(service["pid"])
        port = int(service["port"])
        host = str(service.get("host", "127.0.0.1"))
        listener_identity_url = str(service.get("listener_identity_url") or "")
        provenance = self._provenance_from_service(service)
        forced = False
        stopped = False
        reason = "not_running"
        command = tuple(str(part) for part in service.get("command", ()))
        spec_stop_command = tuple(str(part) for part in service.get("stop_command", ()))
        stop_pid = pid
        reason_prefix = ""
        was_running = self.platform_ops.process_exists(pid)
        owns_running_process = was_running and self.platform_ops.process_matches_command(pid, command)
        if was_running and not owns_running_process:
            reason = "identity_mismatch"
        if not was_running:
            owned_listener_pid = self._running_owned_listener_pid(provenance, pid, host, port, listener_identity_url)
            if owned_listener_pid is not None:
                stop_pid = owned_listener_pid
                owns_running_process = True
                reason = "owned_listener_running"
                reason_prefix = "owned_listener:"
        if spec_stop_command and owns_running_process:
            self._run_stop_command(spec_stop_command, port, host)
            if self.platform_ops.wait_process_exit(stop_pid, graceful_timeout_seconds):
                stopped = True
                reason = f"{reason_prefix}stop_command"
        if not stopped and owns_running_process and self.platform_ops.process_exists(stop_pid):
            self.platform_ops.terminate_process(stop_pid)
            if self.platform_ops.wait_process_exit(stop_pid, graceful_timeout_seconds):
                stopped = True
                reason = f"{reason_prefix}terminated"
            else:
                self.platform_ops.kill_process(stop_pid)
                forced = True
                stopped = self.platform_ops.wait_process_exit(stop_pid, 2.0)
                reason = f"{reason_prefix}{'killed' if stopped else 'kill_attempted'}"
            if stopped and not self.platform_ops.wait_port_available(host, port, float(service.get("port_release_timeout_seconds", 2.0))):
                reason = "process_stopped_port_still_busy"
        result = StopResult(name=name, port=port, pid=stop_pid, stopped=stopped, forced=forced, reason=reason, provenance=provenance)
        if self._service_process_fully_stopped(pid, provenance, host, port, listener_identity_url):
            self._pid_file(name, port).unlink(missing_ok=True)
            self._authority_file(name).unlink(missing_ok=True)
            self._replace_service_record(name, {**service, "lifecycle_state": LifecycleState.STOPPED})
            self._emit_lifecycle_event(name, LifecycleState.STOPPED, reason, "stop", str(service.get("host", "127.0.0.1")), port, provenance)
        self.write_termination_record(result)
        return result

    def stop_all(self, graceful_timeout_seconds: float = 5.0) -> list[StopResult]:
        service_names = list(self.read_state().keys())
        results = [self.stop_service(name, graceful_timeout_seconds=graceful_timeout_seconds) for name in service_names]
        results.extend(self.stop_orphaned_pid_files(graceful_timeout_seconds=graceful_timeout_seconds))
        if isinstance(self.state_store, FilesystemLifecycleStateStore) and not self.read_state():
            self.state_file.unlink(missing_ok=True)
        return results

    def force_stop_by_ports(
        self,
        service_specs: Sequence[ServiceSpec],
        graceful_timeout_seconds: float = 0.5,
        port_process_resolver: Callable[[str, int], Sequence[int]] | None = None,
    ) -> list[StopResult]:
        resolved_port_process_resolver = port_process_resolver or self.platform_ops.get_listening_process_ids
        results: list[StopResult] = []
        for spec in service_specs:
            for port in spec.preferred_ports:
                for pid in sorted({int(value) for value in resolved_port_process_resolver(spec.host, port)}):
                    result = self._stop_process(spec.name, port, pid, graceful_timeout_seconds, "force_by_port", stop_source=StopSource.FORCE_BY_PORT, force_requested=True)
                    self.write_termination_record(result)
                    results.append(result)
        return results

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
            if not self.platform_ops.process_exists(int(payload["pid"])):
                pid_file.unlink(missing_ok=True)
        return results

    def _run_stop_command(self, stop_command: tuple[str, ...], port: int, host: str) -> None:
        command = tuple(part.format(port=port, host=host, workspace=str(self.workspace)) for part in stop_command)
        self.platform_ops.run_command(command, self.workspace)

    def _stop_pid_payload(self, payload: Mapping[str, int | str], graceful_timeout_seconds: float) -> StopResult:
        expected_command = tuple(json.loads(str(payload.get("command", "[]"))))
        if not expected_command:
            return StopResult(str(payload["name"]), int(payload["port"]), int(payload["pid"]), False, False, "pid_file_recovery:missing_identity", stop_source=StopSource.PID_FILE_RECOVERY)
        return self._stop_process(str(payload["name"]), int(payload["port"]), int(payload["pid"]), graceful_timeout_seconds, "pid_file_recovery", expected_command, StopSource.PID_FILE_RECOVERY)

    def _stop_process(
        self,
        name: str,
        port: int,
        pid: int,
        graceful_timeout_seconds: float,
        source: str,
        expected_command: tuple[str, ...] = (),
        stop_source: StopSource = StopSource.REGISTERED_PROCESS,
        force_requested: bool = False,
    ) -> StopResult:
        if source == "force_by_port" and stop_source == StopSource.REGISTERED_PROCESS:
            stop_source = StopSource.FORCE_BY_PORT
            force_requested = True
        forced = False
        stopped = False
        reason = "not_running"
        if self.platform_ops.process_exists(pid):
            if expected_command and not self.platform_ops.process_matches_command(pid, expected_command):
                return StopResult(name=name, port=port, pid=pid, stopped=False, forced=False, reason=f"{source}:identity_mismatch", stop_source=stop_source, force_requested=force_requested)
            self.platform_ops.terminate_process(pid)
            if self.platform_ops.wait_process_exit(pid, graceful_timeout_seconds):
                stopped = True
                reason = "terminated"
            else:
                self.platform_ops.kill_process(pid)
                forced = True
                stopped = self.platform_ops.wait_process_exit(pid, 2.0)
                reason = "killed" if stopped else "kill_attempted"
        return StopResult(name=name, port=port, pid=pid, stopped=stopped, forced=forced, reason=f"{source}:{reason}", stop_source=stop_source, force_requested=force_requested)

    def _service_process_fully_stopped(self, registered_pid: int, provenance: ProcessProvenance | None, host: str, port: int, listener_identity_url: str = "") -> bool:
        if self.platform_ops.process_exists(registered_pid):
            return False
        return self._running_owned_listener_pid(provenance, registered_pid, host, port, listener_identity_url) is None

    def _running_owned_listener_pid(self, provenance: ProcessProvenance | None, registered_pid: int, host: str, port: int, listener_identity_url: str = "") -> int | None:
        if provenance is None or provenance.listener_pid is None or provenance.listener_pid == registered_pid:
            return None
        if provenance.capability not in {
            ProvenanceCapability.OWNED_LISTENER,
            ProvenanceCapability.ENDPOINT_GRADE,
            ProvenanceCapability.HTTP_IDENTITY,
        }:
            return None
        listener_pid = int(provenance.listener_pid)
        if listener_pid not in {int(pid) for pid in self.platform_ops.get_listening_process_ids(host, port)}:
            return None
        if provenance.listener_identity_fingerprint and listener_identity_url:
            observed_identity = self.platform_ops.http_probe(listener_identity_url)
            if observed_identity.get("body_sha256") != provenance.listener_identity_fingerprint:
                return None
        return listener_pid if self.platform_ops.process_exists(listener_pid) else None

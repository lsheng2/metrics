from __future__ import annotations

import json
from contextlib import nullcontext
from typing import Callable, Mapping, Sequence

from .models import LifecycleState, ProcessProvenance, ProvenanceCapability, ServiceSpec, StopResult, StopSource
from .process_exit import ProcessExitObservation
from .state_store import FilesystemLifecycleStateStore


class LifecycleStoppingMixin:
    def stop_service(self, name: str, graceful_timeout_seconds: float = 5.0) -> StopResult:
        state = self.read_state()
        service = state.get(name)
        if not service:
            return StopResult(name=name, port=-1, pid=None, stopped=False, forced=False, reason="not_registered", stop_source=StopSource.NOT_REGISTERED)
        pid = int(service["pid"])
        port = int(service["port"])
        host = str(service.get("host", "127.0.0.1"))
        listener_identity_url = str(service.get("listener_identity_url") or "")
        provenance = self._provenance_from_service(service)
        if service.get("lifecycle_state") == LifecycleState.STOPPED.value and self._service_process_fully_stopped(pid, provenance, host, port, listener_identity_url):
            return StopResult(name=name, port=port, pid=pid, stopped=True, forced=False, reason="already_stopped", provenance=provenance, exit_code=service.get("exit_code"))
        forced = False
        stopped = False
        reason = "not_running"
        command = tuple(str(part) for part in service.get("command", ()))
        spec_stop_command = tuple(str(part) for part in service.get("stop_command", ()))
        stop_pid = pid
        reason_prefix = ""
        was_running = self.platform_ops.process_exists(pid)
        owns_running_process = was_running and self._registered_process_matches(pid, command, provenance)
        if was_running and not owns_running_process:
            reason = "identity_mismatch"
        if not was_running:
            owned_listener_pid = self._running_owned_listener_pid(provenance, pid, host, port, listener_identity_url)
            if owned_listener_pid is not None:
                stop_pid = owned_listener_pid
                owns_running_process = True
                reason = "owned_listener_running"
                reason_prefix = "owned_listener:"
        observation = self.platform_ops.observe_process_exit(stop_pid) if owns_running_process else nullcontext(ProcessExitObservation(lambda: None))
        with observation as read_exit:
            wait_exit = read_exit.wait or (lambda seconds: self.platform_ops.wait_process_exit(stop_pid, seconds))
            last_action = ""
            if spec_stop_command and owns_running_process:
                last_action = "stop_command"
                try:
                    self._run_stop_command(spec_stop_command, port, host, stop_pid, provenance)
                except Exception:
                    if not self._registered_process_matches(stop_pid, command, provenance):
                        owns_running_process = False
                        reason = f"{reason_prefix}identity_changed_after_stop_command"
                    else:
                        reason = f"{reason_prefix}stop_command_failed"
                if wait_exit(graceful_timeout_seconds):
                    stopped = True
                    reason = f"{reason_prefix}stop_command"
                elif not self._registered_process_matches(stop_pid, command, provenance):
                    owns_running_process = False
                    reason = f"{reason_prefix}identity_changed_after_stop_command"
            if not stopped and owns_running_process and self.platform_ops.process_exists(stop_pid):
                if not self._registered_process_matches(stop_pid, command, provenance):
                    reason = f"{reason_prefix}identity_changed_before_terminate"
                else:
                    self.platform_ops.terminate_process(stop_pid)
                    last_action = "terminated"
                    forced = bool(getattr(self.platform_ops, "terminate_is_forceful", False))
                    if wait_exit(graceful_timeout_seconds):
                        stopped = True
                        reason = f"{reason_prefix}terminated"
                    elif not self._registered_process_matches(stop_pid, command, provenance):
                        reason = f"{reason_prefix}identity_changed_before_kill"
                    else:
                        self.platform_ops.kill_process(stop_pid)
                        last_action = "killed"
                        forced = True
                        stopped = wait_exit(2.0)
                        reason = f"{reason_prefix}{'killed' if stopped else 'kill_attempted'}"
            observed_exit = read_exit()
            # PID lookup can disappear after a timed wait; only the retained
            # original process observation can turn that race into a known exit.
            if not stopped and type(observed_exit) is int:
                stopped = True
                no_action_reason = "already_stopped" if observed_exit == 0 else "exited_before_terminate"
                reason = f"{reason_prefix}{last_action or no_action_reason}"
            if (stopped and last_action in {"terminated", "killed"}
                    and not self.platform_ops.wait_port_available(host, port, float(service.get("port_release_timeout_seconds", 2.0)))):
                reason = "process_stopped_port_still_busy"
            exit_code = observed_exit if stopped else None
            result = StopResult(name=name, port=port, pid=stop_pid, stopped=stopped, forced=forced, reason=reason, provenance=provenance, exit_code=exit_code)
            if self._service_process_fully_stopped(pid, provenance, host, port, listener_identity_url):
                self._pid_file(name, port).unlink(missing_ok=True)
                self._authority_file(name).unlink(missing_ok=True)
                self._replace_service_record(name, {**service, "lifecycle_state": LifecycleState.STOPPED, "exit_code": exit_code})
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

    def _run_stop_command(self, stop_command: tuple[str, ...], port: int, host: str, pid: int, provenance: ProcessProvenance | None = None) -> None:
        values = {
            "port": str(port),
            "host": host,
            "workspace": str(self.workspace),
            "pid": str(pid),
            "process_start_marker": provenance.process_start_marker if provenance is not None else "",
            "command_line": provenance.command_line if provenance is not None else "",
            "command_fingerprint": provenance.command_fingerprint if provenance is not None else "",
        }
        command = tuple(part.format_map(values) for part in stop_command)
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
        exit_code = None
        if self.platform_ops.process_exists(pid):
            if expected_command and not self.platform_ops.process_matches_command(pid, expected_command):
                return StopResult(name=name, port=port, pid=pid, stopped=False, forced=False, reason=f"{source}:identity_mismatch", stop_source=stop_source, force_requested=force_requested)
            with self.platform_ops.observe_process_exit(pid) as read_exit:
                wait_exit = read_exit.wait or (lambda seconds: self.platform_ops.wait_process_exit(pid, seconds))
                self.platform_ops.terminate_process(pid)
                forced = bool(getattr(self.platform_ops, "terminate_is_forceful", False))
                last_action = "terminated"
                if wait_exit(graceful_timeout_seconds) or type(read_exit()) is int:
                    stopped = True
                    reason = "terminated"
                elif expected_command and not self.platform_ops.process_matches_command(pid, expected_command):
                    reason = "identity_changed_before_kill"
                else:
                    self.platform_ops.kill_process(pid)
                    last_action = "killed"
                    forced = True
                    stopped = wait_exit(2.0)
                    reason = "killed" if stopped else "kill_attempted"
                observed_exit = read_exit()
                if not stopped and type(observed_exit) is int:
                    stopped = True
                    reason = last_action
                exit_code = observed_exit if stopped else None
        return StopResult(name=name, port=port, pid=pid, stopped=stopped, forced=forced, reason=f"{source}:{reason}", stop_source=stop_source, force_requested=force_requested, exit_code=exit_code)

    def _service_process_fully_stopped(self, registered_pid: int, provenance: ProcessProvenance | None, host: str, port: int, listener_identity_url: str = "") -> bool:
        if self.platform_ops.process_exists(registered_pid):
            return False
        return self._running_owned_listener_pid(provenance, registered_pid, host, port, listener_identity_url) is None

    def _registered_process_matches(self, pid: int, command: tuple[str, ...], provenance: ProcessProvenance | None = None) -> bool:
        if not self.platform_ops.process_matches_command(pid, command):
            return False
        expected_marker = provenance.process_start_marker if provenance is not None else ""
        if expected_marker and self.platform_ops.process_start_marker(pid) != expected_marker:
            return False
        return True

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

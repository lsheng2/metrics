from __future__ import annotations

import json
import subprocess
from typing import Callable, Mapping, Sequence

from .models import ServiceSpec, StopResult, StopSource
from .platform_ops import get_listening_process_ids, kill_process, process_exists, process_matches_command, terminate_process, wait_port_available, wait_process_exit


class LifecycleStoppingMixin:
    def stop_service(self, name: str, graceful_timeout_seconds: float = 5.0) -> StopResult:
        state = self.read_state()
        service = state.get(name)
        if not service:
            return StopResult(name=name, port=-1, pid=None, stopped=False, forced=False, reason="not_registered", stop_source=StopSource.NOT_REGISTERED)

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
            if not process_exists(int(payload["pid"])):
                pid_file.unlink(missing_ok=True)
        return results

    def _run_stop_command(self, stop_command: tuple[str, ...], port: int, host: str) -> None:
        command = tuple(part.format(port=port, host=host, workspace=str(self.workspace)) for part in stop_command)
        subprocess.run(command, cwd=self.workspace, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

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
        if process_exists(pid):
            if expected_command and not process_matches_command(pid, expected_command):
                return StopResult(name=name, port=port, pid=pid, stopped=False, forced=False, reason=f"{source}:identity_mismatch", stop_source=stop_source, force_requested=force_requested)
            terminate_process(pid)
            if wait_process_exit(pid, graceful_timeout_seconds):
                stopped = True
                reason = "terminated"
            else:
                kill_process(pid)
                forced = True
                stopped = wait_process_exit(pid, 2.0)
                reason = "killed" if stopped else "kill_attempted"
        return StopResult(name=name, port=port, pid=pid, stopped=stopped, forced=forced, reason=f"{source}:{reason}", stop_source=stop_source, force_requested=force_requested)

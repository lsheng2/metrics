from __future__ import annotations

import os
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping, Sequence, TypeVar

from .models import LifecycleEvent, LifecycleState, LifecycleStepTiming, ProcessProvenance, RestartResult, ServiceSpec, ServiceState, StopResult
from .platform import PlatformOperationSet
from .provenance import capture_listener_identity, capture_process_provenance, process_provenance_from_mapping
from .state_store import FilesystemLifecycleStateStore, LifecycleStateStore
from .stopping import LifecycleStoppingMixin
from .storage import LifecycleStorageMixin, validate_lifecycle_identifier

T = TypeVar("T")


class ServiceLifecycleEngine(LifecycleStoppingMixin, LifecycleStorageMixin):
    def __init__(
        self,
        project_name: str,
        workspace: str | Path,
        instance_name: str = "default",
        state_directory: str | Path | None = None,
        pid_directory: str | Path | None = None,
        log_directory: str | Path | None = None,
        event_handler: Callable[[LifecycleEvent], None] | None = None,
        platform_ops: PlatformOperationSet | None = None,
        state_store: LifecycleStateStore | None = None,
    ) -> None:
        validate_lifecycle_identifier("project_name", project_name)
        validate_lifecycle_identifier("instance_name", instance_name)
        self.project_name = project_name
        self.instance_name = instance_name
        self.workspace = Path(workspace).resolve()
        self.state_directory = Path(state_directory) if state_directory else self.workspace / "state" / "service-lifecycle-engine"
        self.pid_directory = Path(pid_directory) if pid_directory else self.state_directory / "pids"
        self.log_directory = Path(log_directory) if log_directory else self.state_directory / "logs"
        self.authority_directory = self.state_directory / "launch-authority"
        self.termination_ledger = self.state_directory / "termination-ledger.jsonl"
        self.startup_ledger = self.state_directory / "startup-ledger.jsonl"
        self.state_file = self.state_directory / f"{self.project_name}-{self.instance_name}.json"
        self.platform_ops = platform_ops or PlatformOperationSet()
        self.state_store = state_store or FilesystemLifecycleStateStore(self.state_directory)
        self.event_handler = event_handler
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
            self._validate_service_name(spec.name)
            port = self._resolve_port(spec, reserved_ports)
            plan[spec.name] = port
            reserved_ports.add(port)
        return plan

    def start_service(self, spec: ServiceSpec, port: int | None = None, emit_events: bool = True) -> ServiceState:
        self._validate_service_name(spec.name)
        selected_port = port if port is not None else self.resolve_port(spec)
        existing = self.read_state().get(spec.name)
        if existing and self._service_process_running(existing):
            self.stop_service(spec.name, graceful_timeout_seconds=spec.graceful_timeout_seconds)
            remaining = self.read_state().get(spec.name)
            if remaining and self._service_process_running(remaining):
                raise RuntimeError(f"Existing {spec.name} did not stop; refusing to overwrite lifecycle state")
        stdout_log = self.log_directory / f"{spec.name}-{selected_port}.out.log"
        stderr_log = self.log_directory / f"{spec.name}-{selected_port}.err.log"
        command = tuple(part.format(port=selected_port, host=spec.host, workspace=str(self.workspace)) for part in spec.command)
        environment = os.environ.copy()
        environment.update(spec.env)
        with stdout_log.open("wb") as stdout, stderr_log.open("wb") as stderr:
            process = self.platform_ops.start_process(command, str(spec.cwd or self.workspace), environment, stdout, stderr, self.platform_ops.creation_flags())
        authority_file = self._authority_file(spec.name)
        health_url = self._format_url(spec.health_url, selected_port, spec.host) if spec.health_url else None
        listener_identity_url = self._format_url(spec.listener_identity_url, selected_port, spec.host) if spec.listener_identity_url else None
        prepared_provenance = capture_process_provenance(self.platform_ops, process.pid, command, spec.host, selected_port)
        prepared_state = self._service_state(
            spec,
            selected_port,
            process.pid,
            command,
            stdout_log,
            stderr_log,
            authority_file,
            health_url,
            listener_identity_url,
            prepared_provenance,
            LifecycleState.PREPARED,
        )
        self._write_service_state(prepared_state)
        try:
            self.wait_ready(spec, selected_port, process)
            provenance = capture_process_provenance(
                self.platform_ops,
                process.pid,
                command,
                spec.host,
                selected_port,
                health_url=health_url,
                listener_identity_url=listener_identity_url,
            )
            state = self._service_state(spec, selected_port, process.pid, command, stdout_log, stderr_log, authority_file, health_url, listener_identity_url, provenance, LifecycleState.READY)
            self._write_service_state(state)
            self._write_pid_file(spec.name, selected_port, process.pid, command)
            self.write_launch_authority(spec, selected_port, process.pid, stdout_log, stderr_log, command)
            if emit_events:
                self._emit_lifecycle_event(spec.name, LifecycleState.READY, "readiness_passed", "start", spec.host, state.port, state.provenance)
        except Exception as error:
            provenance = capture_process_provenance(self.platform_ops, process.pid, command, spec.host, selected_port)
            aborted_state = self._service_state(spec, selected_port, process.pid, command, stdout_log, stderr_log, authority_file, health_url, listener_identity_url, provenance, LifecycleState.ABORTED)
            self._write_service_state(aborted_state)
            if emit_events:
                self._emit_lifecycle_event(spec.name, LifecycleState.ABORTED, f"failed:{type(error).__name__}", "start", spec.host, selected_port, provenance)
                setattr(error, "_service_lifecycle_aborted_emitted", True)
            stopped = False
            forced = False
            reason = "startup_aborted:not_running"
            if process.poll() is None:
                self.platform_ops.terminate_process(process.pid)
                if not self.platform_ops.wait_process_exit(process.pid, 0.5):
                    self.platform_ops.kill_process(process.pid)
                    forced = True
                    stopped = self.platform_ops.wait_process_exit(process.pid, 2.0)
                    reason = "startup_aborted:killed" if stopped else "startup_aborted:kill_attempted"
                else:
                    stopped = True
                    reason = "startup_aborted:terminated"
            else:
                stopped = True
            self.write_termination_record(StopResult(spec.name, selected_port, process.pid, stopped, forced, reason, provenance=provenance))
            raise
        return state

    def _service_state(
        self,
        spec: ServiceSpec,
        port: int,
        pid: int,
        command: tuple[str, ...],
        stdout_log: Path,
        stderr_log: Path,
        authority_file: Path,
        health_url: str | None,
        listener_identity_url: str | None,
        provenance: ProcessProvenance,
        lifecycle_state: LifecycleState,
    ) -> ServiceState:
        return ServiceState(
            spec.name,
            spec.host,
            port,
            pid,
            command,
            datetime.now(timezone.utc).isoformat(),
            str(stdout_log),
            str(stderr_log),
            str(authority_file),
            spec.stop_command,
            health_url,
            listener_identity_url,
            provenance.listener_identity_fingerprint,
            spec.port_release_timeout_seconds,
            provenance,
            lifecycle_state,
        )

    def prepare_startup(
        self,
        service_specs: Sequence[ServiceSpec],
        graceful_timeout_seconds: float = 5.0,
        force_by_port: bool = False,
        force_graceful_timeout_seconds: float = 0.5,
        port_process_resolver: Callable[[str, int], Sequence[int]] | None = None,
    ) -> list[StopResult]:
        for spec in service_specs:
            self._validate_service_name(spec.name)
        results = self.stop_all(graceful_timeout_seconds=graceful_timeout_seconds)
        if force_by_port:
            results.extend(self.force_stop_by_ports(service_specs, force_graceful_timeout_seconds, port_process_resolver))
        return results

    def restart_services(
        self,
        service_specs: Sequence[ServiceSpec],
        graceful_timeout_seconds: float = 5.0,
        force_by_port: bool = False,
        force_graceful_timeout_seconds: float = 0.5,
        port_process_resolver: Callable[[str, int], Sequence[int]] | None = None,
        run_id: str | None = None,
        after_prepare: Callable[[Sequence[StopResult]], None] | None = None,
        before_start: Callable[[Mapping[str, int], Sequence[ServiceSpec]], Sequence[ServiceSpec]] | None = None,
    ) -> RestartResult:
        restart_run_id = run_id or str(uuid.uuid4())
        timings: list[LifecycleStepTiming] = []
        active_specs = tuple(service_specs)
        for spec in active_specs:
            self._validate_service_name(spec.name)
        stop_results, timing = self._profile_step(
            "prepare_startup",
            lambda: self.prepare_startup(
                active_specs,
                graceful_timeout_seconds=graceful_timeout_seconds,
                force_by_port=force_by_port,
                force_graceful_timeout_seconds=force_graceful_timeout_seconds,
                port_process_resolver=port_process_resolver,
            ),
            run_id=restart_run_id,
        )
        timings.append(timing)
        if after_prepare:
            after_prepare(stop_results)
        port_plan, timing = self._profile_step("resolve_ports", lambda: self.resolve_plan(active_specs), run_id=restart_run_id)
        timings.append(timing)
        for spec in active_specs:
            self._emit_lifecycle_event(spec.name, LifecycleState.PREPARED, "port_resolved", restart_run_id, spec.host, port_plan[spec.name])
        if before_start:
            active_specs = tuple(before_start(port_plan, active_specs))
        service_states, start_timings = self._start_planned_services(active_specs, port_plan, restart_run_id)
        timings.extend(start_timings)
        return RestartResult(restart_run_id, tuple(stop_results), port_plan, tuple(service_states), tuple(timings))

    def profile_step(self, label: str, callback: Callable[[], T], run_id: str | None = None, prefix: str = "ServiceLifecycleEngine timing") -> T:
        result, _ = self._profile_step(label, callback, run_id=run_id, prefix=prefix)
        return result

    def wait_ready(self, spec: ServiceSpec, port: int, process: subprocess.Popen[bytes] | None = None) -> None:
        deadline = time.monotonic() + spec.startup_timeout_seconds
        health_url = spec.health_url.format(port=port, host=spec.host, workspace=str(self.workspace)) if spec.health_url else None
        healthy_since: float | None = None
        while time.monotonic() < deadline:
            if health_url:
                if self.platform_ops.http_status_ok(health_url):
                    healthy_since = healthy_since or time.monotonic()
                    if time.monotonic() - healthy_since >= 0.2:
                        return
                    time.sleep(0.05)
                    continue
                healthy_since = None
            if not health_url and not self.platform_ops.is_port_available(spec.host, port):
                return
            if process and process.poll() is not None:
                raise RuntimeError(f"{spec.name} exited before becoming ready")
            time.sleep(0.2)
        raise TimeoutError(f"Timed out waiting for {spec.name} on {spec.host}:{port}")

    def check_services(self, callback: Callable[[dict[str, object]], None] | None = None) -> list[dict[str, object]]:
        events = self._service_health_events()
        if callback:
            for event in events:
                callback(event)
        return events

    def diagnose_services(self, service_specs: Sequence[ServiceSpec], port_process_resolver: Callable[[str, int], Sequence[int]] | None = None) -> list[dict[str, object]]:
        state = self.read_state()
        resolved_port_process_resolver = port_process_resolver or self.platform_ops.get_listening_process_ids
        diagnostics = []
        for spec in service_specs:
            service = state.get(spec.name)
            registered_pid = int(service["pid"]) if service and service.get("pid") is not None else None
            registered_port = int(service["port"]) if service and service.get("port") is not None else None
            process_running = self.platform_ops.process_exists(registered_pid) if registered_pid is not None else False
            command = tuple(str(part) for part in service.get("command", ())) if service else ()
            command_matches = self.platform_ops.process_matches_command(registered_pid, command) if registered_pid is not None and process_running and command else None
            health_url = str(service.get("health_url") or "") if service else ""
            health_reachable = self.platform_ops.http_status_ok(health_url) if health_url else None
            identity_url = str(service.get("listener_identity_url") or "") if service else ""
            expected_fingerprint = str(service.get("listener_identity_fingerprint") or "") if service else ""
            observed_identity = self.platform_ops.http_probe(identity_url) if identity_url and expected_fingerprint else {}
            identity_changed = bool(observed_identity and observed_identity.get("body_sha256") != expected_fingerprint)
            diagnostics.append(
                {
                    "project": self.project_name,
                    "instance": self.instance_name,
                    "service": spec.name,
                    "status": self._diagnostic_status(service, process_running, command_matches, health_reachable, identity_changed),
                    "registered": service is not None,
                    "registered_pid": registered_pid,
                    "registered_port": registered_port,
                    "process_running": process_running,
                    "command_matches": command_matches,
                    "health_url": health_url,
                    "health_reachable": health_reachable,
                    "listener_identity_url": identity_url,
                    "listener_identity_changed": identity_changed,
                    "provenance": service.get("provenance") if service else None,
                    "authority_file": str(self._authority_file(spec.name)),
                    "authority_exists": self._authority_file(spec.name).exists(),
                    "preferred_ports": list(spec.preferred_ports),
                    "listener_pids_by_port": {str(port): list(resolved_port_process_resolver(spec.host, port)) for port in spec.preferred_ports},
                }
            )
        return diagnostics

    def _service_process_running(self, service: Mapping[str, object]) -> bool:
        pid = service.get("pid")
        if pid is None:
            return False
        registered_pid = int(pid)
        command = tuple(str(part) for part in service.get("command", ()))
        registered_process_owned = self.platform_ops.process_exists(registered_pid) and bool(command) and self.platform_ops.process_matches_command(registered_pid, command)
        return registered_process_owned or self._running_owned_listener_pid(
            self._provenance_from_service(service),
            registered_pid,
            str(service.get("host", "127.0.0.1")),
            int(service.get("port", 0)),
            str(service.get("listener_identity_url") or ""),
        ) is not None

    def _resolve_port(self, spec: ServiceSpec, reserved_ports: set[int]) -> int:
        state = self.read_state()
        owned_service = state.get(spec.name, {})
        owned_port = owned_service.get("port")
        if owned_port in spec.preferred_ports and int(owned_port) not in reserved_ports and self._service_process_running(owned_service):
            return int(owned_port)
        for port in spec.preferred_ports:
            if port not in reserved_ports and self.platform_ops.is_port_available(spec.host, port):
                return port
        raise RuntimeError(f"No available port for {spec.name}: {', '.join(str(port) for port in spec.preferred_ports)}")

    def _start_planned_services(self, active_specs: Sequence[ServiceSpec], port_plan: Mapping[str, int], run_id: str) -> tuple[list[ServiceState], list[LifecycleStepTiming]]:
        service_states: list[ServiceState] = []
        timings: list[LifecycleStepTiming] = []
        for spec in active_specs:
            if spec.name not in port_plan:
                raise RuntimeError(f"Restart service {spec.name} has no resolved port")
            try:
                state, timing = self._profile_step(f"start:{spec.name}", lambda spec=spec: self.start_service(spec, port=port_plan[spec.name], emit_events=False), run_id=run_id)
            except Exception as error:
                if not getattr(error, "_service_lifecycle_aborted_emitted", False):
                    provenance = self._provenance_from_state(spec.name)
                    self._emit_lifecycle_event(spec.name, LifecycleState.ABORTED, f"failed:{type(error).__name__}", run_id, spec.host, port_plan[spec.name], provenance)
                raise
            timings.append(timing)
            service_states.append(state)
            self._emit_lifecycle_event(spec.name, LifecycleState.READY, "readiness_passed", run_id, spec.host, state.port, state.provenance)
        return service_states, timings

    def _profile_step(self, label: str, callback: Callable[[], T], run_id: str | None = None, prefix: str = "ServiceLifecycleEngine timing") -> tuple[T, LifecycleStepTiming]:
        started_at = time.perf_counter()
        try:
            result = callback()
        except Exception as error:
            elapsed_seconds = time.perf_counter() - started_at
            self.write_startup_record(label, elapsed_seconds, "failed", run_id=run_id, details={"error": type(error).__name__})
            print(f"{prefix} {label}: {elapsed_seconds:.2f}s failed")
            raise
        elapsed_seconds = time.perf_counter() - started_at
        self.write_startup_record(label, elapsed_seconds, "completed", run_id=run_id)
        print(f"{prefix} {label}: {elapsed_seconds:.2f}s")
        return result, LifecycleStepTiming(label, elapsed_seconds, "completed")

    def _emit_lifecycle_event(self, service_name: str, state: LifecycleState, reason: str, run_id: str, host: str, port: int, provenance: ProcessProvenance | None = None) -> None:
        if self.event_handler:
            self.event_handler(LifecycleEvent(service_name, state, reason, 1, host, port, {"run_id": run_id}, provenance))

    def _listener_identity_fingerprint(self, spec: ServiceSpec, port: int) -> str | None:
        if spec.listener_identity_url is None:
            return None
        return capture_listener_identity(self.platform_ops, self._format_url(spec.listener_identity_url, port, spec.host))

    def _provenance_from_service(self, service: Mapping[str, object]) -> ProcessProvenance | None:
        return process_provenance_from_mapping(service.get("provenance"))

    def _provenance_from_state(self, service_name: str) -> ProcessProvenance | None:
        service = self.read_state().get(service_name)
        return self._provenance_from_service(service) if service else None

    def _service_health_events(self) -> list[dict[str, object]]:
        events: list[dict[str, object]] = []
        for name, service in self.read_state().items():
            pid = int(service["pid"])
            port = int(service["port"])
            if not self.platform_ops.process_exists(pid):
                events.append(self._service_event(name, port, pid, "pid_missing"))
                continue
            health_url = service.get("health_url")
            if isinstance(health_url, str) and health_url and not self.platform_ops.http_status_ok(health_url):
                events.append(self._service_event(name, port, pid, "health_unreachable", {"health_url": health_url}))
            identity_url = service.get("listener_identity_url")
            expected_fingerprint = service.get("listener_identity_fingerprint")
            if isinstance(identity_url, str) and identity_url and isinstance(expected_fingerprint, str):
                observed = self.platform_ops.http_probe(identity_url)
                if observed.get("body_sha256") != expected_fingerprint:
                    events.append(self._service_event(name, port, pid, "listener_identity_changed", {"identity_url": identity_url, "observed": observed}))
        return events

    def _format_url(self, value: str | None, port: int, host: str) -> str:
        if value is None:
            return ""
        return value.format(port=port, host=host, workspace=str(self.workspace))

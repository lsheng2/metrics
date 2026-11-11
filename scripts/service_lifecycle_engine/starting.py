from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

from .models import LifecycleState, LifecycleStepTiming, RestartResult, ServiceExitedBeforeReadyError, ServiceSpec, ServiceState, StopResult

BeforeStartCallback = Callable[[Mapping[str, int], Sequence[ServiceSpec]], Sequence[ServiceSpec]]


@dataclass(slots=True)
class _StartQueue:
    plan: dict[str, int]
    planned_by_name: dict[str, ServiceSpec]
    pending: list[ServiceSpec]
    run_id: str
    before_start: BeforeStartCallback | None
    rejected_ports: dict[str, set[int]] = field(default_factory=dict)


class LifecycleStartingMixin:
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
        before_start: BeforeStartCallback | None = None,
    ) -> RestartResult:
        restart_run_id = run_id or str(uuid.uuid4())
        timings: list[LifecycleStepTiming] = []
        planned_specs = tuple(service_specs)
        for spec in planned_specs:
            self._validate_service_name(spec.name)
        stop_results, timing = self._profile_step(
            "prepare_startup",
            lambda: self.prepare_startup(
                planned_specs,
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
        port_plan, timing = self._profile_step("resolve_ports", lambda: self.resolve_plan(planned_specs), run_id=restart_run_id)
        timings.append(timing)
        for spec in planned_specs:
            self._emit_lifecycle_event(spec.name, LifecycleState.PREPARED, "port_resolved", restart_run_id, spec.host, port_plan[spec.name])
        active_specs = tuple(before_start(dict(port_plan), planned_specs)) if before_start else planned_specs
        final_plan, service_states, start_timings = self._start_planned_services(planned_specs, active_specs, port_plan, restart_run_id, before_start)
        timings.extend(start_timings)
        return RestartResult(restart_run_id, tuple(stop_results), final_plan, tuple(service_states), tuple(timings))

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

    def _start_planned_services(
        self,
        planned_specs: Sequence[ServiceSpec],
        active_specs: Sequence[ServiceSpec],
        port_plan: Mapping[str, int],
        run_id: str,
        before_start: BeforeStartCallback | None = None,
    ) -> tuple[dict[str, int], list[ServiceState], list[LifecycleStepTiming]]:
        queue = _StartQueue(dict(port_plan), {spec.name: spec for spec in planned_specs}, list(active_specs), run_id, before_start)
        service_states: list[ServiceState] = []
        timings: list[LifecycleStepTiming] = []
        while queue.pending:
            spec = queue.pending[0]
            if spec.name not in queue.plan:
                raise RuntimeError(f"Restart service {spec.name} has no resolved port")
            port = queue.plan[spec.name]
            if self._port_held_by_other(spec, port):
                self._reresolve_port(queue, spec, "occupied_before_start", emit_aborted=True)
                continue
            try:
                state, timing = self._profile_step(f"start:{spec.name}", lambda: self.start_service(spec, port=port, emit_events=False), run_id=run_id)
            except Exception as error:
                if not getattr(error, "_service_lifecycle_aborted_emitted", False):
                    self._emit_lifecycle_event(spec.name, LifecycleState.ABORTED, f"failed:{type(error).__name__}", run_id, spec.host, port, self._provenance_from_state(spec.name))
                if isinstance(error, ServiceExitedBeforeReadyError) and self._port_held_by_other(spec, port):
                    self._reresolve_port(queue, spec, "occupied_after_exit", emit_aborted=False)
                    continue
                raise
            timings.append(timing)
            service_states.append(state)
            self._emit_lifecycle_event(spec.name, LifecycleState.READY, "readiness_passed", run_id, spec.host, state.port, state.provenance)
            queue.pending.pop(0)
        return queue.plan, service_states, timings

    def _port_held_by_other(self, spec: ServiceSpec, port: int) -> bool:
        if self.platform_ops.is_port_available(spec.host, port):
            return False
        registered = self.read_state().get(spec.name)
        registered_on_port = bool(registered) and registered.get("port") is not None and int(registered["port"]) == port
        return not (registered_on_port and self._service_process_running(registered))

    def _reresolve_port(self, queue: _StartQueue, spec: ServiceSpec, reason: str, emit_aborted: bool) -> None:
        previous_port = queue.plan[spec.name]
        rejected = queue.rejected_ports.setdefault(spec.name, set())
        rejected.add(previous_port)
        reserved = {port for name, port in queue.plan.items() if name != spec.name} | rejected
        try:
            port = self._resolve_port(queue.planned_by_name[spec.name], reserved)
        except RuntimeError as error:
            if emit_aborted:
                self._emit_lifecycle_event(spec.name, LifecycleState.ABORTED, f"failed:{type(error).__name__}", queue.run_id, spec.host, previous_port, self._provenance_from_state(spec.name))
            raise
        queue.plan[spec.name] = port
        print(f"ServiceLifecycleEngine port {spec.name}: {previous_port} -> {port} ({reason})")
        self._emit_lifecycle_event(spec.name, LifecycleState.PREPARED, "port_reresolved", queue.run_id, spec.host, port)
        if queue.before_start is None:
            return
        refreshed = {item.name: item for item in queue.before_start(dict(queue.plan), tuple(queue.planned_by_name.values()))}
        missing = [item.name for item in queue.pending if item.name not in refreshed]
        if missing:
            raise RuntimeError(f"before_start returned no spec for {', '.join(missing)}")
        queue.pending = [refreshed[item.name] for item in queue.pending]

# service_lifecycle_engine

`service_lifecycle_engine` is a generic Python module for local service lifecycle management: service specs, port planning, process start/stop, readiness, provenance, state storage, safe stopping, live service resolution, and display-safe health/launch metadata.

## Public API

Core lifecycle:

- `ServiceLifecycleEngine`
- `ServiceSpec`
- `ServiceState`
- `build_external_service_state(...)`
- `LifecycleState`
- `LifecycleEvent`
- `ProcessProvenance`
- `ProvenanceCapability`
- `StopResult`
- `StopSource`
- `FilesystemLifecycleStateStore`
- `LifecycleStateStore`
- `ServiceLifecycleEngine.record_service_state(service_state)`

Live service resolution:

- `LiveServiceResolver`
- `LiveServiceResolution`
- `LiveServiceResolutionSource`
- `ServiceLiveSnapshot`
- `ServiceOperatorLink`
- `ServiceOperatorAction`

Launch metadata:

- `ServiceLaunchMetadata`
- `ProcessMetadataProvider`
- `PidFileReader`
- `LifecycleStateReader`
- `LaunchMetadataProvider`
- `DefaultProcessMetadataProvider`
- `DefaultPidFileReader`
- `resolve_lifecycle_service_launch_metadata(...)`
- `resolve_pid_file_launch_metadata(...)`
- `merge_service_launch_metadata(payload, metadata)`
- `read_pid_file_value(path)`
- `pid_is_alive(pid)`
- `read_process_started_at(pid)`

Health metadata:

- `ServiceHealthStatus`
- `HealthProbeRequirement`
- `ServiceHealthSnapshot`
- `HealthProbeProvider`
- `Clock`
- `SystemClock`
- `resolve_service_health_status(...)`
- `build_service_health_snapshot(...)`
- `health_requirement_affects_startup(requirement)`
- `health_requirement_affects_liveness(requirement)`

Startup orchestration:

- `ServiceStartNode`
- `ServiceDependency`
- `ServiceDependencyRequirement`
- `ServiceActivationPolicy`
- `ServiceRestartPolicy`
- `ServiceStartPlan`
- `ServiceStartWave`
- `ServiceLaunchAttempt`
- `ServiceLaunchStatus`
- `ServiceStartGraphResult`
- `ServiceStartupGraphError`
- `plan_service_startup(nodes, include_services=None)`
- `start_services_in_dependency_order(nodes, start, max_parallelism=4, include_services=None, run_id=None, now=None, timer=None)`

Runtime instance isolation:

- `RuntimeInstanceIdentity`
- `RuntimeResourceNamespace`
- `ExternalServiceMode`
- `ExternalServiceBinding`
- `StopAuthorityDecision`
- `RuntimeIsolationConflict`
- `RuntimeIsolationConflictCode`
- `detect_runtime_isolation_conflicts(bindings)`
- `run_runtime_instance_isolation_conformance_checks(owner=..., consumer=..., service_name="service")`
- `assert_runtime_instance_isolation_conformance(owner=..., consumer=..., service_name="service")`

Diagnostics and conformance:

- `ServiceDiagnosticCode`
- `diagnostic_value(value)`
- `diagnostic_values(values)`
- `ServiceLifecycleConformanceFixture`
- `ServiceLifecycleConformanceResult`
- `run_service_lifecycle_conformance_checks(fixture)`
- `assert_service_lifecycle_conformance(fixture)`
- `run_startup_orchestration_conformance_checks(startup_nodes=(), service_name="dashboard")`
- `assert_startup_orchestration_conformance(startup_nodes=(), service_name="dashboard")`

## Adapter Pattern

Projects should keep their own launcher paths, health probes, links, authorization behavior, and runtime endpoint authority outside this package. The generic module provides common models and helpers; adapters translate project facts into those models.

Runtime instance isolation follows the same adapter boundary. The generic engine validates and derives safe identities, namespaces, external service ownership modes, stop decisions, and conflict diagnostics. A project adapter decides how one `RuntimeInstanceIdentity` maps to ports, state roots, Docker compose project names, database names, queue prefixes, generated env files, browser caches, and endpoint bindings.

The authority order for project adapters should be explicit CLI/env values first, durable runtime profile second, generated compatibility projections third, and hardcoded defaults last. Generated env files are projections of the durable profile; they are not the durable source of truth.

External launchers that do not call `ServiceLifecycleEngine.start_service()` can still publish generic state:

```python
from service_lifecycle_engine import LifecycleState, ServiceLifecycleEngine, build_external_service_state

engine = ServiceLifecycleEngine("local-tools", workspace_root)
state = build_external_service_state(
    service_name="api",
    lifecycle_state=LifecycleState.READY,
    host="127.0.0.1",
    port=8123,
    pid=4242,
    started_at="2026-09-09T03:34:13.180000+00:00",
    health_url="http://127.0.0.1:8123/health",
)
engine.record_service_state(state)
```

Shell launchers may use the generic CLI instead of writing lifecycle JSON directly:

```bash
python -m service_lifecycle_engine.lifecycle_state_cli ready \
  --workspace-root "$workspace_root" \
  --project-name local-tools \
  --service-id api \
  --base-url http://127.0.0.1:8123 \
  --process-id 4242 \
  --health-url http://127.0.0.1:8123/health
```

Canonical health statuses are intentionally small: `unknown`, `starting`, `ready`, `degraded`, `auth_required`, `unreachable`, and `stopped`. Project-specific conditions should use `reason`, `special_state`, or diagnostics rather than expanding the core enum.

Startup orchestration remains app-neutral. Projects describe services as nodes and dependencies, then provide their own starter callback:

```python
from service_lifecycle_engine import ServiceDependency, ServiceStartNode, start_services_in_dependency_order

nodes = (
    ServiceStartNode("database"),
    ServiceStartNode("api", dependencies=(ServiceDependency("database"),)),
)

result = start_services_in_dependency_order(
    nodes,
    lambda node: {"service": node.service_name},
    max_parallelism=2,
)
```

Required dependency failures skip downstream services. Optional dependencies are soft ordering edges only when the upstream service is part of the selected plan: the engine tries the optional upstream first, records diagnostics if it fails, and does not block the dependent service. Optional dependencies do not force lazy services to start. Lazy and manual services are omitted from the default eager plan unless explicitly selected by the caller or needed as required prerequisites. Restart policy is metadata for adapters and supervisors; the module does not schedule project-specific restarts by itself.

Downstream projects can run the reusable startup orchestration conformance pack directly:

```python
from service_lifecycle_engine import ServiceDependency, ServiceStartNode, assert_startup_orchestration_conformance

assert_startup_orchestration_conformance(
    startup_nodes=(
        ServiceStartNode("database"),
        ServiceStartNode("api", dependencies=(ServiceDependency("database"),)),
    ),
    service_name="api",
)
```

Downstream projects can also run the reusable runtime isolation conformance pack:

```python
from service_lifecycle_engine import (
    RuntimeInstanceIdentity,
    assert_runtime_instance_isolation_conformance,
)

assert_runtime_instance_isolation_conformance(
    owner=RuntimeInstanceIdentity("local-tools", "owner"),
    consumer=RuntimeInstanceIdentity("local-tools", "consumer"),
    service_name="api",
)
```

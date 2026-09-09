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

Diagnostics and conformance:

- `ServiceDiagnosticCode`
- `diagnostic_value(value)`
- `diagnostic_values(values)`
- `ServiceLifecycleConformanceFixture`
- `ServiceLifecycleConformanceResult`
- `run_service_lifecycle_conformance_checks(fixture)`
- `assert_service_lifecycle_conformance(fixture)`

## Adapter Pattern

Projects should keep their own launcher paths, health probes, links, authorization behavior, and runtime endpoint authority outside this package. The generic module provides common models and helpers; adapters translate project facts into those models.

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

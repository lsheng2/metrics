## 1. Breaking Migration Surface

- [x] 1.1 Move lifecycle implementation into `scripts/service_lifecycle_engine/` as the only public package and verify `PYTHONPATH=scripts python -c "import service_lifecycle_engine"` succeeds.
- [x] 1.2 Remove `scripts/port_lifecycle/` public package after internal callers migrate and verify `rg "\bport_lifecycle\b" scripts openspec .github -S` reports only intentional historical/archive references, or none in active code.
- [x] 1.3 Remove or replace `scripts/port_lifecycle_cli.py` with `scripts/service_lifecycle_engine_cli.py` and verify old CLI invocation is absent or fails explicitly while new CLI doctor works.
- [x] 1.4 Replace `PortLifecycle` public usage with `ServiceLifecycleEngine` in launchers, tests and docs, and verify no active code imports `PortLifecycle`.

## 2. Generic Models, Store, And Platform Seams

- [x] 2.1 Define lifecycle state, transition, event, provenance, stop result, port plan, and live service resolution models with `@dataclass(slots=True)` where applicable, and verify serialization/unit tests cover planned/prepared/ready/stopped/aborted plus failed result reasons.
- [x] 2.2 Implement `LifecycleStateStore` protocol and filesystem implementation with schema version, project/instance/service isolation, atomic JSON writes, ordered JSONL appends, and lock scope, and verify unit tests cover each store behavior.
- [x] 2.3 Add corrupt/unsupported state handling that fails closed for destructive operations and verify tests prove corrupt state is reported without deleting or overwriting recovery evidence.
- [x] 2.4 Introduce injectable platform operations for process existence, command identity, process group/descendant check, listener discovery, port availability, HTTP readiness, terminate, kill, and wait, and verify fake-ops tests exercise ownership decisions without real process kills.

## 3. Lifecycle Engine Behavior

- [x] 3.1 Implement `ServiceLifecycleEngine` start/prepare/restart/stop/check/diagnose behavior as the direct implementation, and verify existing E2E launcher start/stop/restart commands use it without old imports.
- [x] 3.2 Emit synchronous lifecycle hooks/events for prepared, ready, aborted, and stopped transitions, and verify tests assert event order, payload identity, transition result, and failed result reason on startup failure.
- [x] 3.3 Implement capability-based provenance levels for wrapper-only, command-matched registered process, owned listener, endpoint-grade provenance, and HTTP semantic identity, and verify tests cover degraded diagnostics versus strong listener ownership.
- [x] 3.4 Separate stop source/force request from kill escalation in stop results, and verify tests distinguish explicit force-by-port cleanup from graceful terminate escalation to kill.
- [x] 3.5 Keep diagnostics launch authority as evidence only and verify tests show ready endpoint authority is not inferred from launch-authority files alone.

## 4. Live Service Resolution

- [x] 4.1 Implement typed live service resolver returning service id, host, port, base URL, resolution source, and diagnostics, and verify tests cover explicit input, lifecycle state, optional project projection, and default fallback.
- [x] 4.2 Add resolver policy for disabling projection sources during hermetic commands, and verify tests prove disabled projections are ignored in favor of explicit inputs or defaults.
- [x] 4.3 Update Scrum Dashboard E2E summary/diagnostic consumers that need service endpoints to use the typed resolver where practical, and verify existing E2E focused tests still report the same selected Django/Grafana URLs.

## 5. Validation Coverage

- [x] 5.1 Add positive public API tests for `service_lifecycle_engine` imports and `service_lifecycle_engine_cli.py doctor`, and verify they pass.
- [x] 5.2 Add negative regression tests proving old `port_lifecycle` imports and `port_lifecycle_cli.py` are not active public entrypoints after zero-compatibility migration.
- [x] 5.3 Add launcher migration regression tests proving `scripts/e2e_bug_trend.py` and `scripts/e2e_provider_parity.py` import the new engine and preserve selected port propagation, summary URLs, restart orchestration, and force-by-port intent.
- [x] 5.4 Keep process-backed lifecycle tests for lightweight HTTP service start/stop/restart, pid recovery, launch authority, readiness and explicit force-by-port, and verify they pass under the new package name.
- [x] 5.5 Keep fake platform/store/resolver tests to cover behavior without launching real business services, and verify they pass.

## 6. Docs And Final Gates

- [x] 6.1 Update `openspec/docs/validation/service-lifecycle-engine.zh.md` and remove or archive active `port-lifecycle` instructions so docs describe zero compatibility and the new command/import names.
- [x] 6.2 Run `python -m pytest scripts/tests/test_service_lifecycle_engine.py scripts/tests/test_service_lifecycle_state_store.py scripts/tests/test_service_lifecycle_platform_ops.py scripts/tests/test_service_lifecycle_resolver.py -q` and verify all generic tests pass.
- [x] 6.3 Run focused launcher/lifecycle regression tests and verify no `port_lifecycle` imports remain in active code.
- [x] 6.4 Run `python scripts/check_file_size_limits.py --include-untracked` and verify no changed or new file exceeds project limits.
- [x] 6.5 Run `python scripts/check_diff_whitespace.py --include-untracked` and verify the diff has no whitespace issues.
- [x] 6.6 Run `openspec validate generalize-service-lifecycle-engine --strict` and verify the execution OpenSpec remains valid.

## 7. Provenance And Injection Hardening

- [x] 7.1 Add optional `ProcessProvenance` to `LifecycleEvent` and verify ready/aborted/stopped events can carry degraded or strong provenance without requiring every field.
- [x] 7.2 Persist wrapper/listener provenance in `ServiceState` when available and verify state serialization keeps provenance capability evidence.
- [x] 7.3 Add `ServiceLifecycleEngine(..., platform_ops=PlatformOperationSet(...))` and route start/stop/readiness/diagnostics/provenance behavior through the injected operations.
- [x] 7.4 Add `ServiceLifecycleEngine(..., state_store=...)` and verify state snapshots, startup ledger and termination ledger use the injected store while default filesystem behavior remains unchanged.
- [x] 7.5 Expose generic provenance helpers `capture_process_provenance(...)`, `resolve_owned_listener(...)`, and `provenance_capability_for(...)` with fake platform tests covering wrapper-only, registered-process, owned-listener, endpoint-grade and HTTP-identity evidence.
- [x] 7.6 Re-run focused lifecycle tests, launcher tests, OpenSpec strict validation, file-size and whitespace gates.

## 8. Consumer Conformance Pack

- [x] 8.1 Add an app-neutral conformance test pack for `service_lifecycle_engine` that does not import Dashboard/Grafana runtime helpers.
- [x] 8.2 Cover wrapper/listener split with persisted/event provenance.
- [x] 8.3 Cover stale registered PID reuse where process existence alone is insufficient without command identity.
- [x] 8.4 Cover endpoint-grade provenance capture for a sole reachable listener.
- [x] 8.5 Cover injected `PlatformOperationSet` and injected `LifecycleStateStore` through public engine behavior.
- [x] 8.6 Cover `force_requested` / `StopSource.FORCE_BY_PORT` separately from `forced` kill escalation.

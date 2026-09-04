## Purpose

定义一个可跨项目复用的 local service lifecycle engine，用于管理 launcher-owned local services 的端口规划、进程启停、readiness、provenance、诊断证据、安全 stop、状态存储和 typed live service resolution，同时把外部 endpoint authority 发布留给项目 adapter。

## ADDED Requirements

### Requirement: Service lifecycle engine owns local service process and port lifecycle
系统 SHALL 为 launcher-managed local services 提供 service-centric lifecycle seam，用于解析 host/port plan、启动进程、等待 readiness、记录诊断证据，并执行默认安全的 stop 行为。

#### Scenario: Resolve a port plan for managed services
- **WHEN** launcher 为一组本地 service 请求启动计划
- **THEN** lifecycle engine SHALL 返回每个 service 的 resolved host/port，并 SHALL 避免同一 plan 内端口冲突

#### Scenario: Start a managed service
- **WHEN** lifecycle engine 启动一个 service 并 readiness 成功
- **THEN** lifecycle engine SHALL 返回 service identity、host、port、process evidence、listener evidence if available、log paths 和 readiness evidence

#### Scenario: Startup fails before readiness
- **WHEN** service process exits、readiness timeout、或 required provenance 无法满足
- **THEN** lifecycle engine SHALL report failed startup as operation result reason and SHALL NOT publish a ready lifecycle state

### Requirement: Persisted lifecycle states have explicit transitions
系统 SHALL 使用明确的 persisted lifecycle states 和 transitions。Persisted lifecycle states SHALL include `planned`, `prepared`, `ready`, `stopped`, and `aborted`; persisted lifecycle states SHALL NOT use `failed` as a terminal state.

#### Scenario: Prepared service becomes ready
- **WHEN** a prepared service reaches readiness and satisfies the provenance level required by the caller
- **THEN** lifecycle state SHALL transition from `prepared` to `ready`

#### Scenario: Prepared service startup fails
- **WHEN** startup fails after a prepared state is created and before readiness is accepted
- **THEN** lifecycle state SHALL transition from `prepared` to `aborted`, and failure details SHALL be recorded as operation result reason or event reason

#### Scenario: Ready service is stopped
- **WHEN** an owned ready service is stopped by the lifecycle owner
- **THEN** lifecycle state SHALL transition from `ready` to `stopped`

#### Scenario: Operation fails without valid transition
- **WHEN** an operation fails but no lifecycle transition is valid
- **THEN** the prior persisted lifecycle state SHALL remain unchanged and the operation failure SHALL be returned as result reason

### Requirement: Lifecycle events are adapter-neutral
系统 SHALL expose lifecycle events for prepared, ready, aborted, and stopped transitions. The engine SHALL NOT know how external projects persist endpoint truth, runtime bindings, dashboards, or service registries.

#### Scenario: Ready event is consumed by a project adapter
- **WHEN** a service reaches ready and the engine emits a ready event
- **THEN** the event SHALL include enough service identity, endpoint, lifecycle generation, and provenance data for an external adapter to decide whether to publish external endpoint authority

#### Scenario: Event carries available provenance
- **WHEN** lifecycle engine emits ready, aborted, or stopped events
- **THEN** the event SHALL include optional `ProcessProvenance` when process or listener evidence is available
- **AND** missing provenance fields SHALL NOT prevent wrapper-only services from emitting lifecycle events

#### Scenario: External adapter rejects an event
- **WHEN** an external adapter rejects or ignores a lifecycle event
- **THEN** lifecycle engine SHALL preserve its local lifecycle result and SHALL NOT retry project-specific publication without an explicit caller action

### Requirement: Provenance requirements are capability-based
系统 SHALL support graded provenance. Strong listener provenance SHALL be required only for actions that publish endpoint authority or stop an owned listener; wrapper-only services SHALL remain supported with degraded diagnostics when they do not publish endpoint authority.

#### Scenario: Wrapper-only service starts
- **WHEN** a service can prove only wrapper process identity
- **THEN** lifecycle engine SHALL allow diagnostics and registered process management, but SHALL NOT claim strong listener ownership

#### Scenario: Registered process identity is command-matched
- **WHEN** stored process identity and current process command evidence match
- **THEN** lifecycle engine SHALL allow normal registered process stop according to the configured stop policy

#### Scenario: Service publishes endpoint authority
- **WHEN** a lifecycle event is used by an adapter to publish runtime endpoint authority
- **THEN** the event SHALL include enough process/listener provenance for that adapter to reject stale or mismatched listeners

#### Scenario: HTTP identity is available
- **WHEN** a service exposes an HTTP health or identity fingerprint
- **THEN** lifecycle engine SHALL treat it as semantic identity evidence and SHALL NOT use it as the only proof of OS listener ownership when strong listener ownership is required

#### Scenario: Persist service provenance
- **WHEN** a managed service reaches readiness and provenance evidence can be observed
- **THEN** persisted `ServiceState` SHALL retain wrapper/listener provenance evidence
- **AND** later diagnostics SHALL be able to report degraded wrapper-only versus stronger listener provenance

#### Scenario: Capture provenance through reusable helpers
- **WHEN** a launcher or adapter needs wrapper/listener evidence
- **THEN** the package SHALL expose generic helpers for process provenance capture, owned listener resolution, and provenance capability classification
- **AND** these helpers SHALL depend on `PlatformOperationSet` rather than app-specific code

### Requirement: Stop defaults are ownership-first and force is explicit
系统 SHALL 默认只停止 lifecycle state 中证明归属的 managed service process 或 owned listener。系统 MUST NOT kill unproven listener processes by port unless the caller explicitly requests force-by-port cleanup.

#### Scenario: Default stop sees a foreign listener
- **WHEN** a target port has a listener that is not proven to belong to the managed service
- **THEN** default stop SHALL fail closed with a diagnostic and SHALL leave the listener running

#### Scenario: Force stop is explicitly requested
- **WHEN** the caller explicitly requests force-by-port cleanup
- **THEN** lifecycle engine MAY stop listeners on the requested ports and SHALL report stop source or force request separately from kill escalation

#### Scenario: Graceful termination escalates to kill
- **WHEN** an owned process does not exit after graceful termination timeout
- **THEN** lifecycle engine MAY escalate to kill according to policy and SHALL mark kill escalation separately from caller force-by-port intent

### Requirement: Lifecycle diagnostics are separate from endpoint truth
系统 SHALL keep process lifecycle diagnostics separate from external endpoint truth. Launch-authority style diagnostics SHALL NOT be treated as effective endpoint authority unless a project-specific adapter explicitly chooses and validates that evidence for a bounded diagnostic use case.

#### Scenario: Diagnostics exist without ready endpoint authority
- **WHEN** lifecycle diagnostics exist but no ready endpoint authority has been published by an external adapter
- **THEN** runtime consumers SHALL NOT infer a ready endpoint from diagnostics alone

#### Scenario: External project publishes endpoint authority
- **WHEN** an external project needs endpoint authority for runtime consumers
- **THEN** it SHALL publish that authority through an adapter using lifecycle events and its own freshness/provenance rules

### Requirement: Lifecycle state store is explicit and isolated
系统 SHALL define lifecycle state storage with explicit schema versioning, instance isolation, lock scope, corruption handling, atomic write behavior, and append ledger behavior.

#### Scenario: Multiple instances use the same workspace
- **WHEN** two launcher instances use the same workspace
- **THEN** lifecycle state keys and locks SHALL isolate records by project, instance, and service identity

#### Scenario: Stored state is corrupt
- **WHEN** lifecycle state cannot be parsed or fails schema validation
- **THEN** lifecycle engine SHALL fail closed for destructive operations and SHALL report a recoverable diagnostic rather than silently deleting or overwriting the state

#### Scenario: State mutation occurs
- **WHEN** lifecycle engine writes state or appends lifecycle records
- **THEN** state replacement SHALL be atomic, append ledgers SHALL preserve event order, and lock scope SHALL cover the identity being mutated

#### Scenario: Custom state store is injected
- **WHEN** a caller constructs `ServiceLifecycleEngine` with a custom `LifecycleStateStore`
- **THEN** all state snapshots and append ledgers SHALL use that injected store
- **AND** default construction SHALL continue to use `FilesystemLifecycleStateStore`

### Requirement: Platform operations are injectable
系统 SHALL route process, port, HTTP readiness, listener discovery, termination, kill and wait behavior through `PlatformOperationSet`.

#### Scenario: Fake platform ops drive engine behavior
- **WHEN** tests or downstream adapters inject a fake `PlatformOperationSet`
- **THEN** start/stop/readiness/diagnostics/provenance decisions SHALL use the injected operations
- **AND** those tests SHALL NOT need real ports, real subprocess kills, or real HTTP probes

### Requirement: Live service resolution is typed and generic
系统 SHALL provide a typed live service resolution surface for launcher-adjacent tools that need to contact a managed service. Consumers SHOULD use explicit inputs or this typed service view before falling back to default ports.

#### Scenario: Tool resolves a managed service endpoint
- **WHEN** a validation, smoke, dev-task, signoff, or live probe tool requests a managed service endpoint
- **THEN** the resolver SHALL return service id, host, port, base URL, resolution source, and diagnostics explaining fallback or degraded resolution

#### Scenario: Explicit input is supplied
- **WHEN** the caller supplies an explicit service URL or port
- **THEN** live service resolution SHALL use the explicit input and SHALL report it as the resolution source

#### Scenario: Projection source is disabled
- **WHEN** the caller disables a runtime projection source for hermetic execution
- **THEN** live service resolution SHALL ignore that projection source and use explicit inputs or default fallback according to policy

### Requirement: Legacy port lifecycle public surfaces are removed
系统 SHALL remove legacy `port_lifecycle` public imports, `PortLifecycle` public class usage, and `port_lifecycle_cli.py` public CLI after internal callers migrate to `service_lifecycle_engine`.

#### Scenario: Internal launcher imports lifecycle engine
- **WHEN** a Scrum Dashboard launcher needs lifecycle behavior
- **THEN** it SHALL import `ServiceLifecycleEngine`, `ServiceSpec`, and related helpers from `service_lifecycle_engine`

#### Scenario: Legacy package import is attempted
- **WHEN** code imports the old `port_lifecycle` package after migration
- **THEN** the import SHALL fail or be absent from the repository rather than silently aliasing the new engine

#### Scenario: Legacy CLI is invoked
- **WHEN** a user or script invokes the old `port_lifecycle_cli.py` entrypoint after migration
- **THEN** the entrypoint SHALL be absent or fail explicitly, and the supported command SHALL be `service_lifecycle_engine_cli.py`

### Requirement: Validation coverage prevents lifecycle migration regressions
系统 SHALL include validation coverage for the new generic engine behavior, old-surface removal, launcher behavior equivalence, fake platform/store/resolver seams, and process-backed lifecycle behavior.

#### Scenario: New public imports are validated
- **WHEN** validation runs for the lifecycle engine
- **THEN** tests SHALL prove `service_lifecycle_engine` imports expose the generic engine, models, store, platform ops and resolver APIs

#### Scenario: Legacy public imports are rejected
- **WHEN** validation runs after zero-compatibility migration
- **THEN** tests SHALL prove `port_lifecycle` and `port_lifecycle_cli` are no longer used by repository code and no longer succeed as public entrypoints

#### Scenario: Launcher behavior is preserved after import migration
- **WHEN** E2E bug trend or provider parity launcher tests run after import migration
- **THEN** tests SHALL prove selected ports, summary URLs, force-by-port intent, and restart orchestration remain behaviorally equivalent

#### Scenario: Generic seams are covered without real process kills
- **WHEN** fake platform, state store, and resolver tests run
- **THEN** they SHALL cover ownership decisions, corrupt state fail-closed behavior, projection disabling, explicit/default resolution, and diagnostics-not-endpoint-truth behavior without requiring real service kills

#### Scenario: Process-backed lifecycle smoke remains covered
- **WHEN** focused lifecycle tests run against lightweight local HTTP processes
- **THEN** they SHALL prove start/stop/restart, readiness wait, launch authority evidence, pid recovery, and explicit force-by-port behavior still work

### Requirement: App-neutral conformance pack covers downstream reuse contract
系统 SHALL include an app-neutral conformance test pack for downstream projects that reuse `service_lifecycle_engine` at source level. The pack SHALL NOT import Dashboard, Grafana, or project-specific launcher helpers.

#### Scenario: Wrapper and listener split is proven generically
- **WHEN** a wrapper process starts a distinct owned listener
- **THEN** conformance tests SHALL prove lifecycle events and persisted service state retain wrapper/listener provenance and graded capability

#### Scenario: Stale PID reuse is rejected generically
- **WHEN** a persisted registered PID exists but current command identity does not match the managed service command
- **THEN** conformance tests SHALL prove process existence alone is not treated as service ownership

#### Scenario: Endpoint-grade provenance is captured without app helpers
- **WHEN** only a single reachable listener can be observed for an endpoint
- **THEN** conformance tests SHALL prove generic provenance helpers can report endpoint-grade evidence without Dashboard or Grafana code

#### Scenario: Injected seams are exercised by conformance tests
- **WHEN** conformance tests run
- **THEN** they SHALL use injected `PlatformOperationSet` and injected `LifecycleStateStore` to avoid real ports, real subprocess kills, or project-specific stores

#### Scenario: Force request and kill escalation remain distinct
- **WHEN** explicit force-by-port cleanup gracefully terminates a process
- **THEN** conformance tests SHALL prove `force_requested` is true, stop source is force-by-port, and `forced` remains false because no kill escalation occurred

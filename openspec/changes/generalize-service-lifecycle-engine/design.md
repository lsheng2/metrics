## Context

See `proposal.md` for motivation. 当前 `scripts/port_lifecycle/` 已经提供跨平台端口选择、进程启动、health wait、PID/state files、launch authority、termination/startup ledgers、doctor CLI 和 explicit force-by-port。此前计划保留 compatibility wrapper；现在 owner 明确要求 zero compatibility，因此本 change 的目标改为直接迁移到 `scripts/service_lifecycle_engine/`，并删除旧 `port_lifecycle` public surface。

Agora 的 `adopt-service-lifecycle-engine` change 对同一抽象提出约束：generic engine 只负责 local service lifecycle；endpoint truth、runtime binding 或外部消费者发布必须由项目 adapter 负责；launcher-adjacent tools 需要 typed live service resolver，避免每个脚本重新读取默认端口或临时 projection。

## Goals / Non-Goals

**Goals:**

- 将现有 `port_lifecycle` 能力迁移为 `service_lifecycle_engine`，不保留 `port_lifecycle` import、package、class alias 或 CLI alias。
- 本 repo launchers、tests、docs 直接使用 `ServiceLifecycleEngine`、generic models 和 `service_lifecycle_engine_cli.py`。
- 让 lifecycle states、events、provenance、stop result、state store 和 resolver 语义足够通用，可被 Scrum Dashboard、Agora 或其他本地多服务 launcher 复用。
- 通过 adapter-neutral event model 支持外部项目把 ready/aborted/stopped 映射到自己的 endpoint authority，而不把任何外部 store 写入 engine。
- 用足够 validation coverage 防止 regression：包括 old surface negative tests、new import tests、launcher behavior regression、fake platform/store/resolver tests、process-backed lifecycle tests 和 hygiene gates。

**Non-Goals:**

- 不把 Agora 的 `RuntimeServiceEndpointBindingStore`、service names、environment variables 或 Linux shell launcher 语义加入 Scrum Dashboard engine。
- 不保留 `port_lifecycle` 兼容入口；旧 import/CLI fail 是预期行为。
- 不在本 change 中发布独立 pip package；先保持 repo-local generic module，未来可再抽取。
- 不改变 E2E runtime 语义：selected Django/Grafana ports、summary URLs、stop safety 和 force-by-port behavior 必须保持等价。

## Decisions

### 1. Zero compatibility migration

`scripts/service_lifecycle_engine/` becomes the only public lifecycle package. `scripts/port_lifecycle/` and `scripts/port_lifecycle_cli.py` are removed after all internal callers migrate. `PortLifecycle` is not retained as an alias; callers use `ServiceLifecycleEngine`.

Alternative considered: 留 deprecated shim。Rejected because owner explicitly requested zero compatibility and wants this repo to adopt the generic name directly.

### 2. Move implementation before deleting old package

Implementation should first create/move the generic module and update direct imports, then remove old package and CLI after tests prove no internal code still imports them. This avoids a broad red state where unrelated launcher tests fail only due unresolved imports.

### 3. `ServiceLifecycleEngine` 保持 adapter-neutral

Engine 只产生 lifecycle result 和 events。外部项目若需要 endpoint truth，应注册 event hook 或 adapter，把 ready/prepared/aborted/stopped event 映射到自己的 store。Engine 不知道 Agora runtime binding，也不读取 Scrum Dashboard business APIs。

Alternative considered: 在 engine 内置 endpoint binding file。Rejected because diagnostics state 和 runtime endpoint authority 必须分离，且各项目 freshness/provenance rules 不同。

### 4. 使用明确 transition table

Persisted lifecycle state 只表达 service lifecycle，不表达操作失败本身。

| From | Event | To | Notes |
| --- | --- | --- | --- |
| none/planned | prepare accepted | prepared | Startup transaction has begun; not consumer-ready. |
| prepared | readiness and required provenance passed | ready | Adapter may publish endpoint authority. |
| prepared | startup failed or cancelled | aborted | Terminal non-ready state; failure details live in result/event reason. |
| ready | owned stop completed | stopped | Terminal stopped state. |
| ready | stale listener detected by check | ready | State remains ready; diagnostic reports stale until owner stop/restart resolves it. |
| any | operation failed without valid transition | unchanged | `failed` is a result/event reason, not persisted state. |

### 5. Provenance is graded, not mandatory-maximal

The engine records what can be proven and lets caller policy decide what is sufficient:

1. wrapper-only provenance: diagnostics and registered process management;
2. command-matched registered process: normal registered process stop;
3. process-group or descendant listener provenance: owned listener stop;
4. endpoint-grade provenance: enough for external endpoint authority adapters to reject stale listeners;
5. HTTP identity fingerprint: semantic evidence, never sole proof of OS listener ownership.

This matches Agora's expectation without forcing every Scrum Dashboard local service to expose Linux `/proc`-style evidence.

### 5a. P1 provenance is part of event and state payloads

`ProcessProvenance` is the generic evidence bundle carried by lifecycle events and persisted service state when the engine can observe it. The bundle remains optional because wrapper-only launchers, OS limitations, and short-lived failed starts may provide only degraded evidence.

The same provenance object is used for:

- ready events consumed by endpoint authority adapters;
- aborted events used for failure diagnostics;
- stopped events and termination ledgers;
- persisted `ServiceState` snapshots used by later diagnostics.

The engine SHALL NOT require all provenance fields. Capability level tells consumers whether the evidence is wrapper-only, command-matched registered process, owned listener, endpoint-grade, or HTTP identity enriched.

### 6. Stop result separates source from escalation

`StopResult.forced` means kill escalation after graceful termination failed. Generic stop result adds source/intent fields such as `stop_source`, `stop_mode`, or `force_requested`. Force-by-port request is caller intent; force kill is termination escalation.

### 7. Platform operations and state store are constructor-injected

`ServiceLifecycleEngine` defaults to production filesystem/platform operations, but callers can inject:

- `PlatformOperationSet` for fake process tables, fake ports, fake HTTP probes, and deterministic termination tests;
- `LifecycleStateStore` for in-memory state, project-owned storage, or filesystem storage.

All start, stop, readiness, diagnostics, provenance and force-by-port paths route through the injected operations. Filesystem storage remains the default for Scrum Dashboard launchers.

### 8. State store becomes a protocol

Engine code writes through a state store protocol. The contract covers:

- schema version on persisted state;
- project/instance/service identity in keys and lock scope;
- atomic snapshot replacement;
- ordered append ledgers;
- fail-closed corruption handling for destructive operations.

### 9. Reusable provenance helpers are public generic API

The generic package exposes helper functions that are useful to downstream adapters without importing launcher internals:

- `capture_process_provenance(...)`;
- `resolve_owned_listener(...)`;
- `provenance_capability_for(...)`.

Helpers use `PlatformOperationSet` and avoid app-specific service names, routes or workspaces.

### 10. Live service resolver is generic read-side surface

The resolver returns typed service endpoint information: service id, host, port, base URL, resolution source, and diagnostics. It can read explicit input, current lifecycle state, project-provided runtime projection, or defaults according to caller policy. Diagnostics launch authority is evidence, not normal endpoint truth, unless a project-specific signoff adapter explicitly opts into it.

### 11. Validation coverage is part of the migration contract

Zero compatibility raises regression risk, so validation must prove both the new behavior and the intentional break:

- positive import tests: `service_lifecycle_engine` and `service_lifecycle_engine_cli` work;
- negative import/CLI tests: `port_lifecycle` and `port_lifecycle_cli` no longer work as public entrypoints;
- launcher regression tests: E2E bug trend and provider parity import the new engine and preserve selected ports, summary URLs and stop/restart behavior;
- fake unit tests: state store, platform ops and resolver avoid real process kills;
- process-backed tests: start/stop/restart still work against lightweight HTTP services;
- hygiene gates: file-size, whitespace and OpenSpec strict validation pass.

## Risks / Trade-offs

- [Breaking external users] -> This is intentional for zero compatibility; docs and tests must make the new import/CLI explicit.
- [Mechanical rename hides behavior regression] -> Use behavior tests around existing launcher workflows, not only import tests.
- [Generic model becomes too broad] -> Keep endpoint publishing, project runtime stores, and app-specific workflow hooks outside the engine.
- [Cross-platform provenance differs] -> Model provenance capabilities explicitly and make platform ops injectable.
- [State migration bugs] -> Fail closed on corrupt or unsupported state and keep recovery evidence.
- [Resolver becomes endpoint authority by accident] -> Resolver reports source and diagnostics; runtime endpoint authority remains external adapter policy.

## Migration Plan

1. Move generic models and implementation from `scripts/port_lifecycle/` into `scripts/service_lifecycle_engine/`.
2. Replace all internal imports in launchers, CLI, tests and docs from `port_lifecycle` / `PortLifecycle` to `service_lifecycle_engine` / `ServiceLifecycleEngine`.
3. Add negative tests proving old package and old CLI are not public entrypoints.
4. Add `LifecycleStateStore` protocol and filesystem implementation, then route state, authority and ledgers through it.
5. Add injectable platform ops seam and migrate process/port/http operations behind it.
6. Add lifecycle event hooks to restart/start/stop paths.
7. Add typed live service resolver with explicit input, lifecycle state, optional projection and default fallback sources.
8. Delete `scripts/port_lifecycle/` and `scripts/port_lifecycle_cli.py` after internal callers are migrated.
9. Update validation docs and OpenSpec notes to describe zero compatibility and new commands.
10. P1 hardening: add event/state provenance and constructor injection for platform ops/state store.
11. P2 hardening: expose reusable provenance helpers.
12. Run full focused lifecycle validation, negative legacy-surface tests, file-size/whitespace checks and OpenSpec strict validation before implementation closure.

## Open Questions

- 是否在第一版提供 async event sinks？Current recommendation: defer async sinks; ship synchronous hooks plus appendable event ledger first.

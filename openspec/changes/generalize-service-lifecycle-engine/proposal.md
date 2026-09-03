## Why

`scripts/port_lifecycle` 已经承担了 service spec、端口规划、进程启停、readiness、诊断证据和 ledgers，但名称与模型仍偏向端口管理。现在需要更激进地把本项目迁到 generic `service_lifecycle_engine`，并与 Agora 对 generic lifecycle engine、adapter-neutral events、typed live service resolver 和 ownership-first stop policy 的期望保持一致。

## What Changes

- **BREAKING**: 删除 `port_lifecycle` public import surface 与 `port_lifecycle_cli.py` legacy CLI，不保留 compatibility wrapper。
- **BREAKING**: 本 repo 内所有 launcher、tests、docs 和 OpenSpec references SHALL 改用 `service_lifecycle_engine` / `service_lifecycle_engine_cli`。
- 将 lifecycle engine 作为 generic module：service spec / port plan、process start/stop、readiness、provenance、events、state store、diagnostics ledgers、safe stop policy 和 typed live service resolution 都归入 `service_lifecycle_engine`。
- 引入明确 lifecycle states 与 transition model：`planned`、`prepared`、`ready`、`stopped`、`aborted`；`failed` 仅作为 operation result/event reason。
- 引入 adapter-neutral lifecycle event hooks：prepared、ready、aborted、stopped；engine 只发 event，不直接写任何外部项目的 endpoint authority。
- 将 process/listener provenance 改为 capability-based：wrapper-only、registered process、owned listener、endpoint-grade provenance 和 HTTP semantic identity 分层表达。
- 明确 stop safety：默认只停止 identity-matched registered process 或 proven owned listener；unproven listener by port fail closed；force-by-port 必须显式请求，并与 kill escalation 的 `forced` 语义分离。
- 引入 `LifecycleStateStore` protocol 与 filesystem implementation，定义 schema version、instance isolation、lock scope、corruption handling、atomic write 和 append ledger 语义。
- 提供 generic live service resolver/read-side surface，使 smoke、validation、dev task、signoff 和 live probes 通过 typed service view 读取 host/port/base URL，而不是继续复制默认端口常量。
- 强化 validation coverage：新增 negative tests 确认 legacy imports/CLI 已移除；新增 migration/regression tests 确认 existing launchers direct-import new engine 后 start/stop/restart 行为不回退。
- P1 hardening：`LifecycleEvent` 和 persisted `ServiceState` SHALL carry optional `ProcessProvenance` when available; `ServiceLifecycleEngine` SHALL accept injected `PlatformOperationSet` and `LifecycleStateStore` so downstream adapters can test launcher behavior without real ports/process kills.
- P2 hardening：公开 generic provenance helpers，例如 `capture_process_provenance(...)`、`resolve_owned_listener(...)` 和 `provenance_capability_for(...)`，用于明确 wrapper/listener separation 和 graded provenance。

## Capabilities

### New Capabilities

- `service-lifecycle-engine`: generic local service lifecycle engine，覆盖 service spec、port plan、process start/stop、readiness、provenance、events、state store、diagnostics ledgers、safe stop policy、typed live service resolution，以及 zero-compatibility migration requirements。

### Modified Capabilities

- 无。

## Impact

- Affected code: `scripts/port_lifecycle/` removal/migration、`scripts/port_lifecycle_cli.py` removal/migration、E2E launchers、focused lifecycle tests、OpenSpec validation docs。
- Public API impact: `port_lifecycle` and `PortLifecycle` imports are removed; consumers must use `service_lifecycle_engine.ServiceLifecycleEngine` and related generic names.
- CLI impact: `port_lifecycle_cli.py doctor` is removed or replaced by `service_lifecycle_engine_cli.py doctor`.
- Behavior impact: runtime behavior for selected ports, stop safety, force-by-port, diagnostics and E2E start/stop/restart SHALL remain equivalent after migration, but old import/CLI names intentionally fail.
- Cross-project alignment: engine 保持 generic，不引用 Agora 或 Scrum Dashboard business model；Agora-style endpoint binding remains an adapter concern, not engine responsibility。P1 hardening makes the event stream sufficient for an adapter such as Agora `RuntimeServiceEndpointBindingStore` without embedding that store in the engine.

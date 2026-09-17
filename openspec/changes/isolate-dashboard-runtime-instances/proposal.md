## Why

当前本地 E2E/AI stack 的 service identity 仍主要由 launcher、默认端口和 state path 拼出来；多个 worktree 并行时会互相抢端口，同一个 main worktree 重复启动时也可能因为旧 state/provenance 不一致而把同一 service 启到多个端口。现在需要把 runtime instance 作为单一 authority，让端口、state、PID、log、Grafana runtime、external service stop 权限和后续 VS Code task 语义都从同一个 identity 派生。

## What Changes

- 在 `service_lifecycle_engine` 中加入 app-neutral runtime instance primitives：runtime identity、resource namespace、external service mode、stop authority decision、runtime isolation conflict detection 和 conformance checks。
- 为 Scrum Dashboard 增加 project adapter：一个 durable `state/local/runtime-instance.json` 作为 authority，并生成 `state/local/worktree-runtime.env` 作为兼容 projection。
- Dashboard E2E launcher SHALL 使用 runtime profile 决定 lifecycle instance name、state root 和 preferred primary ports；重复启动同一 worktree SHALL 复用同一个 instance identity。
- Dashboard AI stack audit/stop path SHALL 读取 runtime profile 派生的 lifecycle state path，而不是 hardcode `metrics-bug-trend-default.json`。
- 增加 architecture doc，明确 `runtime-instance.json = durable authority`、`worktree-runtime.env = generated compatibility projection`、`explicit CLI/env = highest precedence`。
- 增加 focused tests，覆盖 generic runtime isolation、Dashboard profile projection、launcher profile consumption 和 stack lifecycle state path。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `service-lifecycle-engine`: 增加 runtime instance identity、namespace、external service mode、stop authority 和 isolation conflict/conformance 行为，供 Dashboard 和后续 worktree tooling 复用。

## Impact

- Affected code: `scripts/service_lifecycle_engine/`, `scripts/e2e_bug_trend.py`, `scripts/e2e_dashboard_ai_stack.ps1`, new Dashboard runtime profile adapter, focused lifecycle/launcher tests。
- Runtime impact: future local starts create or reuse `state/local/runtime-instance.json`; lifecycle state moves under `state/local/instances/<instance_id>/service-lifecycle-engine` for profile-managed E2E runs.
- Compatibility impact: `state/e2e/bug_trend_ports.json` remains as the Dashboard AI stack compatibility summary for now; generated runtime profile/env files are under ignored `state/`.

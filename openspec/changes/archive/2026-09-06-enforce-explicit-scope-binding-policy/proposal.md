## Why

Scope binding 已经有 readiness 和批量确认能力，但 runtime 仍然只有兼容迁移模式；产品化阶段需要一个可配置的 explicit-only enforcement，把“准备好了没有”变成真正可启用的运行时边界。同时，binding audit 已经写入事件表，但还没有用户可见的历史视图，operator 很难回答“谁在什么时候改了哪个 scope binding”。

## What Changes

- 增加 scope binding runtime policy：`compatibility_allowed` 保持迁移期兼容推断，`explicit_only` 只允许 explicit binding 参与 provider-backed flows。
- Scope Library/Data Health 显示当前 policy、readiness 和切换到 explicit-only 后的阻塞原因。
- Scope Library 或 Data Health 增加 Binding Audit History，展示 confirm/save/bulk confirm 的 old/new binding snapshot。
- 把当前本地 sample scopes 批量确认到 explicit，验证 explicit-only readiness 进入 ready。
- 尝试执行 full AI chat publish smoke；如果模型 gateway 或外部依赖不可用，必须记录为 blocked evidence，而不是当作通过。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `provider-profile-registry`: 增加 runtime policy enforcement contract 和 audit history projection。
- `dashboard-ui-baseline`: 增加 Data Health/Scope Library 的 policy/audit 可视化要求。
- `unified-metrics-workbench-ui`: 增加 explicit-only policy 下 Workbench 对 compatibility binding 的阻断行为。

## Impact

- Affected code: `bug_metrics` scope binding resolver/API、settings defaults、`ui_web` facades/views/templates/CSS/tests、stack validation path。
- APIs: 内部 Dashboard API 增加 policy-aware binding resolution 和 audit event listing。
- Runtime config: 新增 `METRICS_SCOPE_BINDING_POLICY`，默认保持 `compatibility_allowed` 以避免升级即破坏现有环境。
- UI: 仅影响 Metrics Dashboard 的 Scope Library、Data Health、Workbench；不修改 Grafana UI 或 AI Base app UI。

## Why

Scope provider binding 已经成为 Workbench 的状态 authority，但目前只支持显示和确认 compatibility binding。产品化还需要让用户能修复未绑定/冲突状态、在 Data Health 里看到全局风险、逐步收紧 runtime fallback，并把 AI workspace sync 提示与 scope binding 状态合并说明。

## What Changes

- 增加 Scope Binding 编辑能力：在 Scope Library 中为 configuration_required/ambiguous/compatibility scope 提供 provider profile 选择和保存操作。
- 在 Data Health 中增加 Scope Binding 汇总和明细，显示 explicit/compatibility/configuration_required/ambiguous 数量和修复入口。
- 增加 runtime compatibility policy：保持当前 compatibility 可用，但在 UI/health 中明确标识，作为未来收紧到 explicit-only 的前置数据。
- 在 Workbench AI pane 中把 scope binding 状态与 AI workspace sync/availability 状态放到同一个诊断提示中。
- 优化 Scope Library 高密度展示：减少 Actions 列行高，把 binding 信息压缩为可扫描的状态块。

## Capabilities

### New Capabilities

- 无。该变更继续产品化既有 provider profile registry、scope wizard/library、data health 和 unified workbench。

### Modified Capabilities

- `provider-scope-wizard`: 增加 scope binding editor、修复入口和高密度 scope library 操作区。
- `provider-profile-registry`: 增加 explicit binding 编辑/保存、compatibility policy visibility 和 binding health projection。
- `dashboard-ui-baseline`: Data Health SHALL expose scope binding health and repair links.
- `unified-metrics-workbench-ui`: Workbench AI diagnostics SHALL include scope binding state alongside AI workspace sync status.

## Impact

- 代码：`bug_metrics` binding API、`ui_web` facade/view/templates/tests、Data Health facade/template、Workbench AI unavailable context。
- 数据：更新已有 `BugTrendScopeProviderBinding` 记录；不新增 migration，除非实现中发现需要额外持久字段。
- UI：Scope Library、Data Health、Workbench AI pane。
- 验证：Scope Library editor tests、Data Health view tests、Workbench AI diagnostic tests、OpenSpec validation、full stack UI inspection。

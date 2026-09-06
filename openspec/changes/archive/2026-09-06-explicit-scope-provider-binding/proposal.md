## Why

Workbench 已经把 scope 切换改成可用，但当前实现仍依赖兼容推断：当 saved scope 没有显式 provider profile 绑定时，系统会从 scope name、JQL 或 registry source population 猜测 `profile_id/provider_id`。这会让后续产品化阶段继续暴露同类风险：URL、localStorage、AI host action 或可变 display label 都可能再次让 profile/provider 漂移。

现在需要把 `scope_id -> provider profile` 变成后端一等 authority，使 Workbench、Grafana、evidence 和 AI context 都从同一个 binding resolver 得到 canonical state。

## What Changes

- 新增显式 scope provider binding contract，记录每个 Dashboard saved scope 对应的 canonical `profile_id/provider_id`、binding status、provenance 和 blockers。
- 新增 server-side `ScopeProviderBindingResolver`，优先读取显式 binding，legacy scope 只作为 migration/compatibility 输入。
- Workbench PageQueryState 继续以 `scope_id/range/chart/selection/filter` 为 canonical input；`profile_id/provider_id/workspace/AI binding` 由 resolver 派生。
- Workbench toolbar 中 profile/provider 继续是只读 display field，不能作为 primary toolbar query authority。
- 增加 canonical URL 行为：当 `scope_id` 存在时，Workbench pushed URL SHALL omit derived `profile_id/provider_id`。
- 增加 migration/seed/backfill，使已有 scope 有明确 binding 或明确 configuration-required 状态。
- 增加测试覆盖：显式 binding 优先、legacy fallback 标记、stale URL 被忽略、ambiguous/missing binding 不复用旧 profile/provider。

## Capabilities

### New Capabilities

- 无。该变更强化现有 provider registry 和 unified workbench 行为，不新增独立产品 capability。

### Modified Capabilities

- `provider-profile-registry`: 增加 Dashboard saved scope 到 provider profile 的显式 binding authority。
- `unified-metrics-workbench-ui`: 增加 Workbench binding resolver、canonical URL 和 derived profile/provider display 规则。

## Impact

- 代码：`bug_metrics` model/migration/API 或 service、`ui_web` facade/view/template/JS/tests。
- 数据：新增或扩展 provider scope binding 存储；需要 backfill 当前 sample/local scopes。
- UI：Workbench profile/provider 仍显示，但来源改为 binding resolver；未绑定 scope 显示 configuration-required。
- Grafana/AI：继续通过 normalized Workbench state 获取 provider/profile/workspace，不从 UI 参数或 stale URL 推断。

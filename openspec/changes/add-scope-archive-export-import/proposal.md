## Why

Scope Library 现在已经是 Dashboard、Workbench 和 AI Assistant 共用的 scope 管理入口，但 scope 只有 Disable 操作，用户容易把它理解成删除，也缺少可迁移/备份的 Export、Import 流程。由于 saved scope 下面挂有历史 calculation、evidence、Jira history、sync cursor、binding 和 audit，硬删除必须被视为高风险操作。

## What Changes

- 将用户可见的 Disable 语义产品化为 Archive：从正常 Dashboard/Workbench/AI scope 选择中移除，但保留历史数据和审计。
- 为 Scope Library 增加单 scope JSON export，导出 semantic scope config 和可选 provider binding metadata，不导出历史事实数据。
- 为 Scope Library 增加 JSON import，导入为 archived/draft scope，避免导入后立刻进入正常工作流。
- 增加 archived scope 的受保护 hard delete：只允许 archived scope，必须显式确认，并在 UI 中提示影响范围。
- 统一 Scope Library 操作文案和审计语义，避免用户把 archive 误解成已删除。

## Capabilities

### New Capabilities

### Modified Capabilities

- `provider-scope-wizard`: Scope Library 管理 saved scope 的 archive、delete、export、import 行为和风险边界。

## Impact

- `bug_metrics.app.api.scope_config` 增加 export/import/delete/impact 操作。
- `ui_web` Scope Library 增加 Archive、Export、Import 和 Delete archived 操作。
- 模板和 CSS 保持高密度表格，但危险操作必须可见、可确认。
- 测试覆盖 archive 不删除历史、hard delete 限制、export/import round-trip 和 UI 文案。

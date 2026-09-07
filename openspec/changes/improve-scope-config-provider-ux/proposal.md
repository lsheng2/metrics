## Why

当前 Bug Trend Scope Config 页面让用户直接面对 Jira-style raw fields，却没有把 provider/profile 选择、metadata refresh 前置条件、保存/启用必填层级，以及 metadata 如何落到 Dashboard 语义字段讲清楚。用户在新建或编辑 scope 时容易误以为 `IP`、`Project label` 会驱动 Jira/HSD-ES metadata 查找，也难以发现 provider binding 实际藏在 Scope Library。

## What Changes

- 在 Scope Config 页面显式展示 provider/profile binding context，让用户能看到当前 scope 绑定到哪个 provider profile，以及未绑定时该去哪里修复或选择。
- 将 provider 作为 Scope Config 的第一层 pillar 选择，先让用户选择 Jira、HSD-ES 或后续 provider，再展示对应 source/detail 表格。
- 增加 provider setup template registry，使每个 provider 的 query label、metadata 支持状态、必填/详情字段说明和 profile options 由可扩展配置生成，而不是散落在模板条件里。
- 将必填项拆成 `Save draft`、`Enable scope`、`Provider metadata`、`Dashboard/AI readiness` 四类，使用户知道哪些字段只是 display label，哪些会影响 provider metadata、sync、calculation 和 Dashboard/Workbench/AI 可用性。
- 将 Metadata options 从无序 tag 堆改为按 project/type/status/priority/resolution/field/component/version 分组，并为常用 mapping 提供可见的“添加到 Dashboard 语义字段”入口。
- 将 metadata refresh 明确限制为当前支持的 Jira metadata adapter；HSD-ES provider profile 不在本页伪造 metadata，而是展示 registry/provider-owned source 的边界和后续 readiness 路径。
- 保持 Bulma + htmx + server-rendered 形态，不引入重型前端框架。

## Capabilities

### New Capabilities

### Modified Capabilities

- `provider-scope-wizard`: Scope Config 编辑体验必须呈现 provider/profile context、metadata 前置条件、Dashboard semantic mapping 与 readiness 分层。

## Impact

- `ui_web` Scope Config view/facade/template/partial/css。
- `ui_web` provider setup template registry for Jira、HSD-ES and future GitHub-style providers。
- `ui_web` focused view tests for provider visibility、required field guidance、metadata grouping 和 mapping links。
- OpenSpec delta under `openspec/changes/improve-scope-config-provider-ux/specs/provider-scope-wizard/spec.md`。
- 不新增 HSD-ES metadata adapter，不改变 provider registry authority，也不改变 durable sync/calculation semantics。

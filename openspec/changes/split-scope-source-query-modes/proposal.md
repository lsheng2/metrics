## Why

Scope Config 页面当前把 JQL、Selected Jira projects、metadata refresh、field/value mapping 放在同一连续表单里，用户容易误以为 JQL 和下面的项目、类型、组件、版本选择同时作为运行时 filter 生效。现在需要把 source population authority 与 semantic mapping 明确分层，并用互斥 source mode 防止同一个 scope 出现两个查询来源。

## What Changes

- Scope Config SHALL 引入互斥的 source mode：`Custom JQL` 与 `Query Builder`。
- `Custom JQL` mode SHALL 以用户手写 JQL 作为唯一 source query authority；项目/type/field metadata 只作为 discovery context 与 semantic mapping 辅助。
- `Query Builder` mode SHALL 由用户选择 Jira project、issue type 和支持的 filter fields 生成 JQL preview，并把生成结果作为保存的 source query。
- 页面 SHALL 把 source population、metadata discovery context、semantic mapping 和 optional display fields 分成清楚的 sections。
- 保存逻辑 SHALL 持久化 selected source mode、builder selections、最终 source query 和 semantic mappings，并确保 config version hash 随 source authority 改变。
- Metadata refresh SHALL 使用当前 source mode 的 project/type context，但 SHALL NOT 作为隐藏的第二运行时 filter。
- 本 change 不引入 HSD-ES live metadata，也不改变 Workbench/Grafana/AI 的 provider binding authority。

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `provider-scope-wizard`: Scope Config/Scope Wizard 的 source mode、query builder、metadata discovery context 和 semantic mapping UI 行为发生变化。
- `bug-trend-baseline`: Saved Jira scope config 的 source query authority 与 persisted semantics 需要记录互斥 source mode 及 builder-derived source query。

## Impact

- Affected UI: `ui_web/templates/bug_trend_scope_config.html`、metadata partials、Scope Config focused browser/view tests。
- Affected facade/view logic: `ui_web/facades/bug_trend_scope_config_facade.py`、`ui_web/views/bug_trend_scope_views.py`。
- Affected persistence/domain: `bug_metrics.models.JiraScopeConfig`、`bug_metrics.app.api.scope_config`、config hash/model migrations。
- Affected Jira metadata/query support: Jira metadata adapter parsing for paged `values`/`options` payloads and query-builder projection helpers.
- Validation: focused Scope Config/metadata tests, migration check, Django check, OpenSpec strict validate, and UI smoke where feasible.

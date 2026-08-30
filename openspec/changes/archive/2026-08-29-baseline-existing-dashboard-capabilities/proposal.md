## Why

项目已经从半成品代码和若干 `docs/` 设计文档推进到可运行的 Django metrics dashboard，但 OpenSpec 是中途引入的；如果继续用 OpenSpec 方式实施，必须先把“当前代码已经具备什么能力”转成标准 spec baseline。

这次 change 的目标是建立现有能力基线，让后续 Jira-first、HSD-ES-second、Grafana-first 和 AI 能力的变更可以从明确 baseline 出发，而不是把旧文档、已实现代码和未来目标混在一起。

## What Changes

- 新增当前 Django dashboard runtime baseline：记录现有 server-rendered Django、Bulma、HTMX、Chart.js 页面、partial、facade 和模块边界。
- 新增当前 engineering metrics baseline：记录现有 tasks、forecast、velocity、pull_requests 模块提供的 task board、forecast、velocity 和 PR review gate 能力。
- 新增当前 Jira Bug Trend baseline：记录现有 saved Jira scope config、durable Jira sync/history、calculation run、bucket/evidence、scope audit、data health、chart catalog、Grafana data surface 和 AI chart draft governance。
- 将 `docs/` 中已经反映现有实现的历史设计内容纳入 OpenSpec baseline 的追溯来源；后续 apply 可按任务把旧 docs 迁移、归档或替换为 OpenSpec 主规格。
- 明确非目标：本 change 不实现 HSD-ES provider、不把最终 UI 切到 Grafana、不新增生产代码、不声明 execution / automation / shift-left / escaped bug charts 已完成。

## Capabilities

### New Capabilities

- `dashboard-ui-baseline`: 覆盖现有 Django modular-monolith dashboard 的页面、HTMX partial、facade federation、frontend stack 和 graceful degradation 规则。
- `engineering-metrics-baseline`: 覆盖现有 task search/current tasks、forecast、velocity、pull request review gate 和相关 provider/config 行为。
- `bug-trend-baseline`: 覆盖现有 Jira Bug Trend 的 saved scope、durable facts/sync/history、calculation artifacts、evidence drilldown/export、scope audit、data health、chart catalog、Grafana contract 和 AI chart draft governance。

### Modified Capabilities

- `provider-facts-and-sync`: 将当前已落地的 Jira sync/history/facts implementation 记录为 provider facts 的现有 Jira baseline，并明确它是未来 provider-neutral platform extraction 的输入。

## Impact

- 受影响规划目录：`openspec/changes/baseline-existing-dashboard-capabilities/`。
- 受影响现有代码区域（仅作为 baseline 来源，不在本 change 中修改）：`ui_web/`、`tasks/`、`forecast/`、`velocity/`、`pull_requests/`、`bug_metrics/`、`jira_sync/`、`jira_history/`、`metrics/settings/defaults_metrics.py`。
- 受影响历史文档：旧 `docs/` 下的迁移来源已记录在 `openspec/docs/baseline-docs-inventory.md`。
- 后续 apply 影响：只应迁移/同步规格和文档，除非另一个 OpenSpec change 明确进入产品代码实施。

# Spec Delta

## MODIFIED Requirements

### Requirement: Jira-first profile publish readiness is explicit
Dashboard SHALL determine whether a Jira profile and coverage range are ready for AI Grafana publish before `metrics.publish_chart` requests approval.

#### Scenario: Jira profile has completed aggregate coverage
- **WHEN** profile `chiplet-2a-jira` has a completed aggregate artifact for chart `open_bug_trend` and the requested WW/date range
- **THEN** chart data SHALL return `supported` with non-empty provider-neutral `grafana_rows`
- **THEN** readiness SHALL expose provider id, profile id, chart id, coverage range, calculation run id, fact snapshot id and freshness status

#### Scenario: Jira profile lacks completed aggregate coverage
- **WHEN** profile `chiplet-2a-jira` lacks a completed aggregate artifact for the requested chart/range
- **THEN** readiness SHALL return `unavailable` or `stale` with a clear action label for sync
- **THEN** `metrics.publish_chart` 的 preview SHALL 以该就绪原因失败，运行时 SHALL NOT 创建审批
- **THEN** AI publish SHALL NOT silently fall back to HSD-ES or another profile

#### Scenario: Jira sync is triggered for publish readiness
- **WHEN** an operator requests Jira-first AI publish readiness for a range without current coverage
- **THEN** the system MAY run or guide a provider profile sync for `chiplet-2a-jira`
- **THEN** successful sync SHALL materialize aggregate artifacts before the chart is treated as publish-ready

### Requirement: Durable dashboard consumption
Dashboard render paths SHALL consume durable local history、facts、calculation runs 或 approved aggregate artifacts，不得在每次 dashboard render 时 live-query external provider。

#### Scenario: Bug Trend chart render
- **WHEN** Bug Trend dashboard 渲染趋势图或 evidence drilldown
- **THEN** 它 SHALL 使用本地 durable Jira history、bucket facts 和 matching calculation run，而不是直接调用 Jira REST API

#### Scenario: HSD-ES-backed chart render
- **WHEN** dashboard 渲染 HSD-ES-backed trend、quality、triage 或 correlation view
- **THEN** 它 SHALL 使用本地 durable HSD-ES facts、snapshots 或 approved aggregate artifacts，而不是每次 render 时 live-query HSD-ES API

#### Scenario: Scope setup preview
- **WHEN** Scope Wizard 只做 metadata discovery、query validation 或 issue count preview
- **THEN** 它 MAY live-query provider read-only endpoints，因为这是 setup workflow，不是 dashboard render source of truth

#### Scenario: Provider 未配置时渲染本地数据
- **WHEN** Jira 地址或凭据没有配置，Bug Trend 页面、workbench 页面或 `/api/charts/data/` 读取已有的本地 durable 数据
- **THEN** 它们 SHALL 正常返回，不创建 Jira client
- **THEN** 只有需要 Jira scope 元数据或同步的操作 SHALL 返回 provider 配置错误

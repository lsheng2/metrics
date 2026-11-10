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

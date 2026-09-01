## Why

HSD-ES local demo 已经证明 AI Base Chat 可以通过 Dashboard/Metrics validation、dry-run proof、approval 和 Grafana import 形成可见图表。项目的第一优先 provider 是 Jira，因此下一步必须把同一条链路提升为 Jira-first 可发布工作流，并补齐 approval、recipe-driven chart authoring 和 publish history/audit 的产品化边界。

## What Changes

- 让 `chiplet-2a-jira` 在目标 WW/date range 上有可验证的 completed aggregate artifact，并让 AI/Grafana publish 前能主动检查 Jira profile 数据是否 ready。
- 把当前 `approval_chat_demo_...` 本地 demo approval 发展为 Dashboard-owned approval object/state，区分 pending、approved、rejected、published。
- 将 Chat chart authoring 从固定 `open_bug_trend + new_critical_high` 扩展为基于 Metrics catalog/chart recipe 的受控生成。
- 增加 AI-generated Grafana dashboard publish history/list/audit，让用户看到生成过哪些 chart、来自哪个 profile/range/request、当前状态和 Grafana URL。
- 保持安全边界：unsupported series 继续返回 `needs_metric_recipe`；AI Base 不拥有 provider credentials、metric semantics、Grafana JSON authority 或 production approval policy。

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `provider-facts-and-sync`: Jira-first profile sync SHALL produce publish-ready aggregate artifacts for configured coverage and expose readiness before AI publish.
- `dashboard-ai-sidecar-integration`: AI Base / Dashboard Chat publish flow SHALL use formal approval state and Jira-first readiness checks.
- `provider-ai-dashboard-composition`: AI chart authoring SHALL be recipe-driven and publish SHALL operate on approved Metrics catalog recipes rather than fixed demo literals.
- `grafana-render-config`: AI-generated Grafana dashboards SHALL be tracked as managed publish artifacts with list/history/audit metadata.

## Impact

- Dashboard backend: provider sync readiness, AI dashboard workflow/publish APIs, approval state model or equivalent persistence, publish artifact history, tests.
- Dashboard docs/OpenSpec: milestone requirements, runbook updates, case-study follow-up notes.
- AI Base integration: may require a matching AI Base connector/chat update after Dashboard contract changes; Dashboard must keep backward-compatible dry-run behavior until AI Base catches up.
- Runtime validation: Jira live sync or deterministic Jira fixture must prove `chiplet-2a-jira` can publish a nonblank Grafana chart for the selected coverage.

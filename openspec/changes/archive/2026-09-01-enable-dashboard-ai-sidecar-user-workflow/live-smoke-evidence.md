# Live Smoke Evidence

Date: 2026-09-01

## AI Base Runtime

Checked `http://127.0.0.1:48300/api/runtime/info`.

- profileId: `dashboard_query_agent`
- serviceId: `dashboard-query-agent-app-service`
- featureCapabilities:
  - `dashboardQuery=true`
  - `metricsConnector=true`
  - `grafanaOperations=true`

## Dashboard Workflow

Checked `http://127.0.0.1:8002/api/ai-dashboard/workflow/` with `METRICS_AI_SIDECAR_ENABLED=true`.

- `nvu-ttl-hsdes` / `new_critical_high`: `ready draft_validated draft_validated precondition_passed gcx_dry_run`
- `chiplet-2a-jira` / `new_critical_high`: `jira draft_validated draft_validated precondition_passed gcx_dry_run`
- `nvu-ttl-hsdes` / `new_critical`: `hsdes needs_metric_recipe not_checked not_checked update_metrics_chart_recipe`

Checked `http://127.0.0.1:8002/ai-dashboard/workflow/`.

- HTTP 200
- Page contains `AI Dashboard Workflow`
- Page contains configured `dashboard_query_agent`
- Page contains `gcx Precondition`

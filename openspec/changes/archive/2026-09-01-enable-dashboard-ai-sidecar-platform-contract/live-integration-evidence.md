## Live Integration Evidence

日期：2026-08-31

## Runtime Setup

- Dashboard app: `http://127.0.0.1:8002`
- AI Base app: `http://127.0.0.1:48300`
- AI Base source checkout used for smoke: `C:/Users/lsheng2/.codex/worktrees/45a1/Report_creater_agent`
- Dashboard sidecar settings used:
  - `METRICS_AI_SIDECAR_ENABLED=true`
  - `METRICS_AI_BASE_URL=http://127.0.0.1:48300`
  - `METRICS_AI_BASE_SERVICE_ID=dashboard-query-agent-app-service`
  - `METRICS_AI_BASE_PROFILE_ID=dashboard_query_agent`
- AI Base settings used:
  - `RCA_APP_PROFILE=dashboard_query_agent`
  - `RCA_APP_PORT=48300`
  - `RCA_APP_SERVICE_ID=dashboard-query-agent-app-service`
  - `DASHBOARD_METRICS_BASE_URL=http://127.0.0.1:8002`

## Handshake Evidence

- AI Base `/health/handshake` returned:
  - `status=ok`
  - `profile=dashboard_query_agent`
  - `serviceId=dashboard-query-agent-app-service`
- AI Base `/api/runtime/info` returned:
  - `profileId=dashboard_query_agent`
  - `featureCapabilities.dashboardQuery=true`
  - `featureCapabilities.metricsConnector=true`
  - `featureCapabilities.grafanaOperations=true`
- Dashboard Data Health rendered AI Sidecar Health as:
  - `status=ready`
  - `profile=dashboard_query_agent`
  - `capabilities: dashboardQuery=True metricsConnector=True grafanaOperations=True`

## Metrics Connector Evidence

AI Base Metrics connector invoked real Dashboard endpoints rather than mocked fixtures:

- `catalog.lookup`
  - envelope status: `ok`
  - Dashboard catalog returned `contract_version=0.2`
- `intent.validate` for `open_bug_trend`, `requested_series=["new_critical_high"]`, `range_start=26WW10`, `range_end=26WW35`
  - envelope status: `ok`
  - Metrics status: `draft_validated`
  - `valid=true`
  - `draft_render_config` present
- `intent.validate` for `requested_series=["new_critical"]`
  - envelope status: `needs_metric_recipe`
  - Metrics status: `needs_metric_recipe`
  - `valid=false`
  - requested series preserved as `new_critical`
  - no fake or substituted `new_critical_high` series generated
- `render_config.validate` using the supported draft
  - envelope status: `ok`
  - Metrics status: `draft_validated`
  - `valid=true`
- `gcx.precondition` using the supported draft
  - envelope status: `ok`
  - Metrics status: `precondition_passed`
  - `mutation_allowed=true`
- `gcx.precondition` using an invalid draft containing unapproved `new_critical`
  - envelope status: `ok`
  - Metrics status: `blocked`
  - `mutation_allowed=false`
  - finding code includes `render_config_validation_failed`

## Validation Evidence

Dashboard repo:

- `.venv/Scripts/python.exe manage.py test bug_metrics.tests.test_api_ai_sidecar ui_web.tests.test_data_health_views ui_web.tests.test_ai_dashboard_api_surface bug_metrics.tests.test_ai_sidecar_contract_fixtures -v 2` -> `18 tests OK`
- `.venv/Scripts/python.exe manage.py check` -> OK
- `.venv/Scripts/python.exe scripts/check_file_size_limits.py --include-untracked` -> OK
- `.venv/Scripts/python.exe scripts/check_diff_whitespace.py --include-untracked` -> OK
- `openspec validate enable-dashboard-ai-sidecar-platform-contract --strict` -> OK

AI Base worktree:

- `d:/AIGC/Report_creater_agent/.venv/Scripts/python.exe -m pytest tests/test_dashboard_profile_metrics_connector.py tests/test_dashboard_gcx_safety.py -q` -> `17 passed`
- `openspec validate add-dashboard-query-agent-metrics-connector --strict` -> OK

## Residual Risks

- AI Base implementation is still in Codex worktree `C:/Users/lsheng2/.codex/worktrees/45a1/Report_creater_agent`; it must be committed/pushed or handed off before the main checkout at `D:/AIGC/Report_creater_agent` can run the same profile.
- Live smoke covered Metrics connector and precondition paths, but not real Grafana mutation or publish/import. Keep write mutation disabled until explicit approval and dry-run proof review.
- HSD-ES provider data was stale during smoke; this does not block sidecar contract validation but should be refreshed before a product-quality chart review.

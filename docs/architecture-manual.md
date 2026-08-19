# Internal Jira Dashboard Architecture Manual

Date: 2026-08-19

## Decision

Use `clutcher/metrics` as the engineering baseline for the internal Jira dashboard.

Baseline repository: [clutcher/metrics](https://github.com/clutcher/metrics)

Rationale:

- MIT license is suitable for fork-and-customize work.
- It is already a Django web application, not just a BI/report template.
- It already has Jira integration, task search, velocity, forecasting, Docker setup, configuration via environment variables, and a modular monolith structure.
- Its existing query-result cache and lazy loading are useful for interactive dashboard performance.

Important constraint:

- The baseline cache is not a durable analytics store. We must add our own sync/history layer before building reliable daily or weekly bug trends.

## Current Baseline Architecture

`clutcher/metrics` is organized as a modular Django application.

```text
metrics/                 Django project and settings
tasks/                   Jira/Azure task search and task domain model
velocity/                Velocity calculations
forecast/                Forecasting and capacity calculations
pull_requests/           PR integration
ui_web/                  Server-rendered dashboard UI, HTMX partials, Chart.js charts
```

Current data flow:

```text
Browser
  -> Django view / HTMX partial
      -> ui_web facade
          -> module API
              -> TaskSearchService
                  -> JiraTaskRepository
                      -> sd_metrics_lib JiraTaskProvider
                          -> Intel Jira REST API
```

Current cache behavior:

- `JiraTaskRepository` wraps `JiraTaskProvider` in `CachingTaskProvider`.
- Cache key is based on generated JQL plus requested additional fields.
- Requesting `changelog` changes the cache key because it is an additional field.
- Development cache: Django `FileBasedCache`, `/tmp/metrics_task_search_cache`, 300 second timeout.
- Production cache: Django `FileBasedCache`, `/tmp/metrics_task_search_cache_prod`, 900 second timeout.
- Current Tasks page can lazy-load expensive changelog/time-tracking rows only when a stage is expanded.

Architecture implication:

- Keep the baseline cache for UI responsiveness.
- Do not use it as the source of truth for trend analytics.

## Intel Jira Connectivity Findings

Example issue URL provided:

```text
https://jira.devtools.intel.com/browse/STDEL-8942
```

Unauthenticated endpoint probes from this workspace:

| Endpoint | Result | Interpretation |
| --- | --- | --- |
| `https://jira.devtools.intel.com/rest/api/2/serverInfo` | `401`, `X-AUSERNAME: anonymous` | REST API path exists and is reachable; authentication required. |
| `https://jira.devtools.intel.com/rest/api/latest/serverInfo` | `401`, `X-AUSERNAME: anonymous` | Symbolic `latest` path exists and is reachable; authentication required. |
| `https://jira.devtools.intel.com/rest/api/2/issue/STDEL-8942?...` | `401`, `X-AUSERNAME: anonymous` | Issue API path exists; issue access requires authentication. |
| `https://jira.devtools.intel.com/rest/api/latest/issue/STDEL-8942?...` | `401`, `X-AUSERNAME: anonymous` | `latest` issue API path exists; authentication required. |
| `https://jira.devtools.intel.com/rest/agile/1.0/board?maxResults=1` | `401`, `X-AUSERNAME: anonymous` | Agile API path exists; authentication required. |

Conclusion:

- The machine can reach Intel Jira REST endpoints.
- The API family appears compatible with Jira Server/Data Center style paths: `/rest/api/2`, `/rest/api/latest`, and `/rest/agile/1.0`.
- We cannot confirm authenticated access until a PAT is supplied locally outside chat.

Atlassian documentation notes:

- Jira Server/Data Center URI shape is `http://host/context/rest/api-name/api-version/resource-name`.
- `api` current version is `2`.
- `agile` current version is `1`.
- `latest` is a symbolic API version supported by the instance.
- Personal access token is a recommended authentication option for Jira Server/Data Center.
- Pagination uses `startAt` and `maxResults`; clients must tolerate changing or omitted `total`.

## Minimal Baseline Change For Intel Jira Access

`clutcher/metrics` currently initializes Jira as:

```python
Jira(
    url=jira_config.jira_server_url,
    username=jira_config.jira_email,
    password=jira_config.jira_api_token,
    cloud=True,
)
```

That is appropriate for Jira Cloud basic/API-token style auth. Intel's Jira URL looks like Jira Server/Data Center, and Atlassian's Python API supports Server/Data Center PAT usage with:

```python
Jira(url="https://jira.devtools.intel.com", token="server-or-dc-pat")
```

Required minimal change:

1. Add a config value such as `METRICS_JIRA_AUTH_MODE`.
2. Support at least two modes:
   - `cloud_basic`: existing behavior, `username + password/api token + cloud=True`.
   - `server_pat`: new behavior, `token=<PAT>`, no `cloud=True`.
3. `server_pat` is explicit and mandatory for Intel Jira Server/Data Center; no implicit auth-mode inference is part of the MVP contract.
4. Rename or alias token env var later if desired, for example `METRICS_JIRA_PAT`, but preserve `METRICS_JIRA_API_TOKEN` during the fork to minimize churn.
5. Use `METRICS_JIRA_CA_BUNDLE` for trusted corporate CA bundles. `METRICS_JIRA_VERIFY_SSL=false` is local troubleshooting only.

Minimal connectivity validation after the auth change:

```powershell
$env:METRICS_JIRA_SERVER_URL = "https://jira.devtools.intel.com"
$env:METRICS_JIRA_API_TOKEN = "<set locally, do not paste into chat>"
$env:METRICS_JIRA_AUTH_MODE = "server_pat"
$env:METRICS_PROJECT_KEYS = "STDEL"
python manage.py check
```

Independent curl validation without exposing the token in source:

```powershell
$env:JIRA_PAT = "<set locally, do not paste into chat>"
curl.exe --noproxy jira.devtools.intel.com `
  -H "Authorization: Bearer $env:JIRA_PAT" `
  -H "Accept: application/json" `
  "https://jira.devtools.intel.com/rest/api/2/issue/STDEL-8942?fields=summary,status,issuetype,created,updated"
```

If this returns issue JSON, the access path is good enough for the MVP spike.

## Target Architecture For Our Fork

```text
Browser UI
  -> Django / HTMX / Chart.js dashboard
      -> PM metric facades
          -> metrics modules
              -> durable Jira history store
                  -> incremental Jira sync worker
                      -> Intel Jira REST API
```

Add these modules to the baseline:

```text
jira_sync/               Incremental sync, REST client checks, cursors
jira_history/            Normalized issues, raw snapshots, transitions
bug_metrics/             Daily/weekly bug created/fixed/open/reopened aggregates
feature_metrics/         Feature completion and aging aggregates
pm_dashboard/            PM-focused overview pages and drilldowns
```

Keep these baseline modules:

```text
tasks/                   Reuse task search concepts and Jira provider where practical
velocity/                Reuse for scrum/velocity views where aligned
forecast/                Reuse later for completion forecast
ui_web/                  Reuse server-rendered dashboard conventions
```

## Data Model Additions

MVP tables:

### `jira_sync_cursor`

Tracks incremental sync state.

Fields:

- `scope_key`
- `jql`
- `last_successful_sync_at`
- `last_jira_updated_cutoff`
- `status`
- `error_message`

### `jira_issue`

Current normalized issue state.

Fields:

- `issue_id`
- `issue_key`
- `project_key`
- `issue_type`
- `summary`
- `status`
- `status_category`
- `resolution`
- `priority`
- `severity`
- `assignee`
- `reporter`
- `created_at`
- `updated_at`
- `resolved_at`
- `feature_group_key`
- `epic_key`
- `fix_versions`
- `components`
- `labels`
- `raw_fields_json`

### `jira_issue_snapshot`

Traceable raw Jira payload history.

Fields:

- `issue_key`
- `synced_at`
- `jira_updated_at`
- `payload_json`
- `payload_hash`

### `jira_transition`

Status and resolution transitions parsed from changelog.

Fields:

- `issue_key`
- `transitioned_at`
- `author`
- `field`
- `from_value`
- `to_value`
- `from_status_category`
- `to_status_category`

### `metric_daily_bug`

Precomputed bug trend aggregate.

Fields:

- `metric_date`
- `scope_key`
- `project_key`
- `created_count`
- `fixed_count`
- `reopened_count`
- `open_count`
- `critical_open_count`
- `major_open_count`

### `metric_feature_progress`

Precomputed feature completion aggregate.

Fields:

- `metric_date`
- `scope_key`
- `feature_group_key`
- `total_count`
- `done_count`
- `blocked_count`
- `in_progress_count`
- `completion_percent`
- `total_story_points`
- `done_story_points`

## MVP Scope

MVP goal:

Prove that we can securely connect to Intel Jira, sync enough issue history, and show PM-relevant feature and bug trends without live-querying every dashboard view.

MVP pages:

1. Connectivity page
   - Shows configured Jira base URL.
   - Shows authenticated user from `/rest/api/2/myself` if allowed.
   - Shows API family availability: `api/2`, `latest`, `agile/1.0`.
   - Shows last sync status and error details.

2. Bug trend page
   - Daily created bugs.
   - Daily fixed bugs.
   - Open bug backlog.
   - Weekly rollup toggle.
   - Drilldown table for selected date/series.

3. Feature completion page
   - Completion by feature group, epic, fixVersion, component, or configured custom field.
   - Done/in-progress/blocked breakdown.
   - Aging features and overdue features.

4. Sync admin page
   - Manual sync button.
   - Last sync time.
   - Number of issues scanned, updated, and failed.
   - Cursor details for debugging.

MVP non-goals:

- Full Jira clone.
- Editing Jira issues.
- Replacing Jira sprint boards.
- Multi-tenant enterprise deployment.
- AI-generated summaries before the data layer is trusted.

## MVP Milestones

### M0: Auth And Connectivity Spike

Objective:

Confirm the baseline plus minimal auth change can access Intel Jira.

Tasks:

- Fork or clone `clutcher/metrics`.
- Add `METRICS_JIRA_AUTH_MODE=server_pat`.
- Instantiate `Jira(url=..., token=...)` for Server/Data Center PAT mode.
- Prefer a trusted CA bundle through `METRICS_JIRA_CA_BUNDLE`; use `METRICS_JIRA_VERIFY_SSL=false` only for local troubleshooting.
- Test `/rest/api/2/serverInfo`.
- Test `/rest/api/2/issue/STDEL-8942` with limited fields.
- Test `/rest/api/2/search` with `project = STDEL ORDER BY updated DESC` and small `maxResults`.
- Test `expand=changelog` on one accessible issue.
- Test `/rest/agile/1.0/board?maxResults=1` only if scrum/sprint views need Agile APIs.

Exit criteria:

- Authenticated request returns JSON from at least one issue endpoint.
- Search returns at least one issue for a configured project/JQL.
- Changelog can be fetched for at least one issue, or we document the fallback strategy.
- No token is stored in git or logs.

### M1: Durable Jira History Store

Objective:

Stop depending on live Jira queries for trend pages.

Tasks:

- Add Django models for cursor, issue, snapshot, transition, and daily aggregates.
- Implement incremental sync with a safety overlap window.
- Parse changelog status and resolution transitions.
- Store raw payload snapshots with hashes.
- Add management command: `python manage.py sync_jira --scope STDEL --limit ...`.

Exit criteria:

- Re-running sync is idempotent.
- Updated issues refresh local state.
- Transition rows are deduplicated.

### M2: Bug Trend MVP

Objective:

Show reliable bug trend charts from local data.

Tasks:

- Define bug issue types and done statuses via config.
- Compute daily created/fixed/reopened/open counts.
- Add daily and weekly chart views.
- Add drilldown issue table.

Exit criteria:

- Daily counts match spot-check JQL for selected days.
- Dashboard loads without live Jira calls except manual refresh.

### M3: Feature Completion MVP

Objective:

Show feature progress from local data.

Tasks:

- Configure feature grouping field: epic, fixVersion, component, or custom field.
- Compute completion by count and optionally story points.
- Add blocked/aging feature list.

Exit criteria:

- PM can identify completed, in-progress, blocked, and at-risk features for the selected scope.

## Open Questions

1. What exact Intel Jira API version is deployed? We can infer from authenticated `/serverInfo`.
2. Does Intel Jira PAT use `Authorization: Bearer <token>` as standard Jira Server/Data Center PAT? Needs authenticated curl validation.
3. Is `/rest/agile/1.0` enabled for this instance and for the PAT's permissions?
4. Which Jira fields define feature grouping, severity, team, release train, and story points for this project?
5. Is `STDEL` the initial MVP project scope, or only an example?
6. Should MVP run as a local PM tool first, or as a shared internal service?

## Recommendation

Proceed with `clutcher/metrics` as baseline, but make M0 connectivity the first gate.

If M0 passes, continue with durable history store work before building charts. If M0 fails because of auth mode only, fix the Jira client configuration. If M0 fails because of network/proxy/permission restrictions, pause feature work and resolve access with the Jira/admin team first.

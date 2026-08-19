# Jira Dashboard Research And Architecture Plan

Date: 2026-08-19

## Executive Recommendation

Build an internal self-hosted Jira dashboard, but do not start from a blank page.

Recommended baseline path:

1. Use `clutcher/metrics` as the strongest fork candidate if we want a Python/Django service baseline under a permissive MIT license.
2. Use `FlowViz-Jira` as a metrics and visualization reference, not as the app baseline, because it is primarily a Power BI template.
3. Use `FlowBoard` as a product/UX and domain-model reference only unless legal approves AGPL-3.0 obligations for internal deployment and derivative work.
4. Avoid Jira Forge gadget projects as the main baseline unless the product direction becomes "inside Jira dashboard gadget" rather than a standalone internal dashboard.

The most pragmatic architecture is a small internal web app with a Jira ingestion layer, normalized issue history store, metric calculation layer, and dashboard UI. This lets us compute daily and weekly bug trends reliably instead of relying only on live Jira queries.

## Open Source Shortlist

| Project | License | Stack | Fit | Notes |
| --- | --- | --- | --- | --- |
| [clutcher/metrics](https://github.com/clutcher/metrics) | MIT | Python, Django, HTMX, Bulma, Chart.js | High | Connects to Jira/Azure DevOps, has velocity, forecasts, task views, Docker path, environment-based configuration, modular architecture. Good permissive baseline. Needs bug trend and feature completion extensions. |
| [nbrown02/FlowViz-Jira](https://github.com/nbrown02/FlowViz-Jira) | MIT | Power BI template | Medium | Strong flow-metrics model for Jira Cloud/Server/Data Center. Useful for metric definitions and stakeholder-friendly visualizations. Less suitable if we need a custom web app and internal deployment without Power BI dependency. |
| [POLPROG-TECH/FlowBoard](https://github.com/POLPROG-TECH/FlowBoard) | AGPL-3.0 | Python 3.12, FastAPI/Jinja, CLI, Chart.js | Functionally high, license risk high | Very close feature set: sprint health, capacity, epic progress, blockers, dependencies, risk detection, Jira Cloud/Server/DC, PAT support. AGPL is the blocker for forking into an internal derivative unless legal approves. |
| [dsnasciimento/jira-analytics-dashboard](https://github.com/dsnasciimento/jira-analytics-dashboard) | MIT | Python, Streamlit | Medium-low | Simple Jira REST v3 dashboard with sprint/burndown/performance views. Easy to understand, but small single-author app and likely needs significant hardening. |
| [rgies/agile-dashboard](https://github.com/rgies/agile-dashboard) | MIT | PHP 5.x/Symfony-era stack, MySQL | Low | Historically relevant lean metrics dashboard, but stack is old and likely expensive to modernize. |
| [red-hat-data-services/rhai-org-pulse](https://github.com/red-hat-data-services/rhai-org-pulse) | No clear license found from fetched page | Vue 3, Express, Chart.js | Medium technically, license/portability risk | Modern internal engineering dashboard using Jira/GitHub/GitLab/rosters. Good architectural reference, but no license surfaced in fetched metadata and it is Red Hat-specific. |
| [remarkablemark/jira-dashboard-gadget](https://github.com/remarkablemark/jira-dashboard-gadget) | MIT | Atlassian Forge, React/TypeScript | Low for standalone app | Good template if embedding as Jira dashboard gadget is required. Not a full PM dashboard baseline. |
| [remarkablemark/issue-formula](https://github.com/remarkablemark/issue-formula) | MIT | Atlassian Forge, React/TypeScript | Low for standalone app | Mature Forge gadget example with releases. Useful only for Jira-native gadget direction. |
| [atlassian-labs/data-center-grafana-dashboards](https://github.com/atlassian-labs/data-center-grafana-dashboards) | Apache-2.0 | Grafana JSON, Prometheus/JMX | Low for PM metrics | Official-ish Atlassian Labs dashboards for Jira Data Center operational monitoring, not feature/bug delivery metrics. Useful only if we also need Jira instance health dashboards. |

## License Position

This is not legal advice, but for engineering planning:

| License            | Practical impact                                                                                                                                                                                     |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| MIT / Apache-2.0   | Best candidates for fork-and-customize, subject to normal attribution and notice requirements.                                                                                                       |
| AGPL-3.0           | Treat as high-risk for an internal web service derivative. If users interact with the service over a network, AGPL source-disclosure obligations may matter. Legal approval required before forking. |
| No license visible | Do not fork or copy code. Use only as public inspiration unless license is confirmed.                                                                                                                |

## Proposed Product Scope

### MVP Dashboards

1. Feature completion overview

   - Features by status category: not started, in progress, blocked, done.
   - Completion percentage by epic, fixVersion, component, team, or custom field.
   - Feature aging and overdue features.
   - Scope change count during sprint or release window.
2. Bug trend dashboard

   - Daily new bugs.
   - Daily fixed/resolved bugs.
   - Open bug backlog by severity/priority.
   - Reopen count.
   - Net bug burn-down: created minus resolved.
   - Weekly rollup for management review.
3. Scrum/sprint health

   - Sprint committed vs completed.
   - Sprint burndown/burnup.
   - Carry-over items.
   - Blocked item count and blocked aging.
   - Velocity trend by sprint.
4. Drilldown table

   - Click any chart segment to list matching Jira issues.
   - Columns configurable for Intel Jira custom fields.
   - Export CSV for weekly status reports.

### Later Extensions

1. Program/release view across multiple Jira projects.
2. Engineering quality view: escaped defects, reopen rate, fix latency.
3. Forecasting: likely completion date based on recent throughput.
4. AI summary: weekly natural-language PM summary generated from metric deltas and top issue changes.
5. Slack/Teams/email snapshot delivery.

## Proposed Architecture

```text
Browser UI
  -> Dashboard API
      -> Metrics service
          -> Normalized issue/history store
              -> Jira ingestion worker
                  -> Intel Jira REST API
```

### Components

1. Jira connector

   - Auth: Personal Access Token stored in environment variables or local secret store, never committed.
   - API patterns to verify against Intel wiki:
     - Issue search using JQL.
     - Changelog retrieval for status transitions.
     - Agile board/sprint endpoints if enabled.
     - Custom field discovery for story points, severity, feature/bug type, teams, releases.
   - Supports Jira Server/Data Center style bearer PAT first; Jira Cloud basic/API-token can remain optional.
2. Ingestion and snapshots

   - Scheduled incremental sync, for example every 30-60 minutes.
   - Store raw issue JSON snapshots for traceability.
   - Store normalized issue facts and transition events separately.
   - Compute daily/weekly trend from history, not just current issue state.
3. Data store

   - MVP: SQLite if single-user/local desktop deployment.
   - Team deployment: PostgreSQL.
   - Tables:
     - `jira_issue`: current normalized issue state.
     - `jira_issue_snapshot`: raw payload by sync time.
     - `jira_transition`: status/category changes from changelog.
     - `metric_daily`: precomputed daily aggregates.
     - `dashboard_config`: project/JQL/custom-field mappings.
4. Metrics engine

   - Inputs: normalized issues and transition facts.
   - Outputs: chart-ready series and drilldown issue keys.
   - Important metric definitions:
     - New bug on day D: issue type is Bug and created date falls on D.
     - Fixed bug on day D: Bug transitions into configured done/resolved statuses on D.
     - Open bug backlog on day D: bugs created on or before D minus bugs resolved on or before D, with reopen transitions handled explicitly.
     - Feature completion: done feature count or story points divided by total committed feature count/story points within selected scope.
5. Dashboard API

   - `GET /api/health`
   - `POST /api/sync`
   - `GET /api/projects`
   - `GET /api/metrics/bugs?granularity=daily|weekly&from=&to=&scope=`
   - `GET /api/metrics/features?scope=`
   - `GET /api/metrics/sprints?boardId=&sprintId=`
   - `GET /api/issues?metric=&date=&filters=`
6. UI

   - Management overview page first, not a Jira clone.
   - Use chart cards for trend and completion, plus issue drilldown tables.
   - Keep filters persistent: project, board, sprint, release, component, team, severity.
   - Favor Chart.js/Recharts/ECharts; avoid overbuilding custom chart primitives.

## Baseline Implementation Options

### Option A: Fork `clutcher/metrics` And Extend

Best when we want quickest route to an internal service.

Pros:

- MIT license.
- Existing Jira connector and Docker setup.
- Modular Python architecture with task, velocity, forecast, and UI modules.
- Server-rendered UI is simpler to deploy in constrained enterprise environments.

Cons:

- Current focus is velocity/task tracking, not PM bug trend and feature completion.
- Django/HTMX UI may need redesign if we want a highly interactive executive dashboard.
- Need code audit before trusting data model and Jira pagination/changelog handling.

Cache and database assessment:

- `clutcher/metrics` does have a Jira data cache, but it is a query-result cache, not a durable Jira data warehouse.
- The Jira repository wraps `sd_metrics_lib.sources.jira.tasks.JiraTaskProvider` in `CachingTaskProvider`.
- Cache keys are based on the generated JQL query plus requested additional fields, including whether `changelog` is requested.
- Development cache uses Django `FileBasedCache` at `/tmp/metrics_task_search_cache` with `TIMEOUT: 300` seconds.
- Production cache overrides this to `/tmp/metrics_task_search_cache_prod` with `TIMEOUT: 900` seconds.
- The app has lazy loading for expensive current-task rows: it first fetches structural issue data without changelog/time tracking, then fetches per-stage rows with changelog only when expanded.
- I did not find repository-owned Django models/migrations for normalized Jira issue snapshots or transition history. The included `db.sqlite3` appears to support Django app state rather than a designed Jira analytics store.

Implication for our project:

- This cache is useful to reduce repeated Jira calls during interactive dashboard use.
- It is not sufficient for reliable daily/weekly bug trend analytics, because trends need historical snapshots and status-transition facts that survive cache expiry and app restarts.
- If we choose this baseline, Milestone 1 must add a durable sync layer for `jira_issue`, `jira_issue_snapshot`, `jira_transition`, and precomputed daily aggregates.
- For "near real-time" bug trends, use scheduled incremental sync plus manual refresh: for example, sync recently updated issues every 5-15 minutes and recompute affected daily aggregates.

Recommended next step:

- Fork and run demo/local setup.
- Audit the Jira provider's pagination, changelog, and PAT behavior against Intel Jira.
- Add a durable `jira_sync` or `jira_history` module before building trend charts.
- Add a `bugs` module and `feature_progress` module on top of the durable data layer.
- Add Intel Jira field mapping config.

### Option B: Build New App, Borrow Metric Ideas

Best when we want clean architecture and stronger long-term ownership.

Suggested stack:

- Backend: Python FastAPI or Django.
- Worker: APScheduler/Celery/RQ depending on deployment complexity.
- DB: SQLite for local MVP, PostgreSQL for shared service.
- Frontend: React/Vite or server-rendered HTMX depending on deployment and UX needs.
- Charts: ECharts, Recharts, or Chart.js.

Pros:

- Clean support for Intel Jira quirks and internal auth.
- No license uncertainty beyond dependencies.
- Easier to design data model correctly for historical trends.

Cons:

- More initial implementation effort.
- Need to build auth, config UI, ingestion reliability, and charts ourselves.

### Option C: Power BI / Grafana Route

Best only if the organization already standardizes on BI/observability tooling.

Pros:

- Fast charting and sharing.
- FlowViz has MIT Power BI reference.
- Grafana is strong for time-series dashboards.

Cons:

- Needs a separate Jira extraction pipeline anyway for issue history.
- Less flexible drilldown and custom PM workflows.
- Power BI/Grafana may be harder for PAT-per-user access and custom field mapping.

## Security And Enterprise Constraints

1. Do not paste PAT into chat or source files.
2. Use environment variables, OS keychain, Vault, or a company-approved secret store.
3. Mask tokens in logs and error messages.
4. Support corporate proxy and custom CA bundle.
5. Keep raw Jira payload access limited because issue descriptions/comments may contain confidential data.
6. Add role-based access if deployed beyond one PM machine.
7. Make sync scopes explicit with JQL allowlists to avoid accidentally indexing all Jira data.

## Intel Jira Integration Questions To Resolve

The internal wiki page could not be fetched through the tool, likely due to SSO/VPN/browser-session access. These need verification from that page or a browser session:

1. Base URL for the Jira REST API.
2. API version: `/rest/api/2`, `/rest/api/latest`, or custom Intel gateway path.
3. PAT auth header format: likely `Authorization: Bearer <token>`, but must confirm.
4. Whether Agile endpoints are enabled: `/rest/agile/1.0/...`.
5. Rate limits, pagination limits, and any internal proxy/TLS requirements.
6. Required fields for company workflow: severity, priority, team, release train, component, story points, sprint, epic link, labels.

## MVP Milestones

### Milestone 0: Spike

- Pick baseline: `clutcher/metrics` fork or new FastAPI/Django app.
- Confirm Intel Jira REST auth using a token supplied through local environment only.
- Run one JQL query for a limited test project.
- Discover custom fields and status categories.

Exit criteria:

- Can fetch 50 issues from one project without exposing secrets.
- Can fetch changelog for at least one bug.
- Can map Jira statuses into `todo`, `in_progress`, `blocked`, `done`.

### Milestone 1: Data Foundation

- Implement incremental Jira sync.
- Store normalized issues and transitions.
- Keep `clutcher/metrics` query-result cache for UI responsiveness, but do not use it as the source of truth for trends.
- Add sync cursors, cache invalidation or refresh endpoints, and recomputation for affected daily buckets.
- Add config for project/JQL/custom fields.
- Add unit tests for pagination and transition parsing.

Exit criteria:

- Daily new/fixed/open bug counts match equivalent JQL spot checks for selected dates.

### Milestone 2: PM Dashboard MVP

- Bug daily/weekly trend chart.
- Feature completion chart.
- Sprint health summary.
- Drilldown issue table.
- CSV export.

Exit criteria:

- PM can answer: what changed this week, are bugs burning down, which features are at risk, and which issues explain the chart movement.

### Milestone 3: Hardening

- Background scheduled sync.
- Auth for dashboard users.
- Deployment docs.
- Secret handling docs.
- Performance tuning for large projects.

Exit criteria:

- Runs as a stable internal service or local PM tool with repeatable setup.

## Immediate Next Step

I recommend we start with a short technical spike against `clutcher/metrics` before committing to a fork:

1. Clone/fork it into this workspace.
2. Run its local setup and tests.
3. Inspect the Jira connector for Server/Data Center PAT support and changelog support.
4. Estimate the patch size for adding bug trend and feature completion modules.

If the connector/data model is too narrow, switch to a clean new app while still borrowing its MIT-licensed structural ideas and FlowViz's metrics vocabulary.

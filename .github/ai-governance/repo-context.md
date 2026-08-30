# Repo Context

Status: active BKM.

## Summary

This is a Django modular monolith for software delivery metrics. It integrates Jira, Azure DevOps, Bitbucket/Azure Repos, and `sd-metrics-lib` to render task, forecast, velocity, and pull-request dashboards.

Current MVP goal: Intel Jira bug trend indicator dashboard for saved Jira scopes. Normative baseline requirements live in `openspec/specs/`; supporting history and architecture notes live under `openspec/docs/`.

## Modules

| Module | Owner Boundary |
| --- | --- |
| `tasks/` | Task search, hierarchy, enrichment, tracker task conversion |
| `forecast/` | Forecast estimations, task health, scheduling parameters |
| `velocity/` | Developer and team velocity calculations |
| `pull_requests/` | PR discovery, review conversion, reviewer policy gates |
| `ui_web/` | Django views, facades, templates, htmx partials, UI data federation |
| `metrics/` | Django settings, URLs, middleware, deployment settings |

Planned MVP owner additions:

| Module | Owner Boundary |
| --- | --- |
| `jira_sync/` | Intel Jira fetches, incremental sync, cursors, and sync status |
| `jira_history/` | Normalized issue state, raw snapshots, transitions, and durable persistence APIs |
| `bug_metrics/` | `jira_scope_config`, trend calculation, bucket aggregation, and drilldown membership |

## Architecture Rules

1. Modules communicate through public APIs under `app/api/`.
2. Domain code remains pure Python and framework-free.
3. UI uses semantic HTML, Bulma, htmx, and Chart.js.
4. Dataclasses use `@dataclass(slots=True)`.
5. External tracker behavior should reuse `sd-metrics-lib` when practical.
6. Secrets stay in `.env` or deployment environment variables and must not appear in committed files, docs, tests, or chat output.
7. `jira_scope_config` is the single authority for project-specific bug trend semantics; environment variables own connectivity only.
8. Bug trend dashboards read durable local history and aggregate artifacts, not live Jira queries on every page load.
9. Multi-provider first: Jira is the first rich work-item provider, not the architecture boundary. New tracker/work-item/AI workflow designs must define provider-neutral contracts and UI semantics first, then implement Jira, GitHub, Azure DevOps, or other systems as adapters with declared capabilities.
10. Do not create parallel product surfaces per provider. Shared concepts such as connection profile, work-item facts, metadata discovery, scope query/filter, action plan, approval/audit, and dashboard consumption belong in provider-neutral contracts; provider-specific modules own only external API quirks, auth, pagination, field identity, and sync implementation.

## Common Validation

```powershell
python -m pytest path\to\test_file.py::TestClass::test_method -q
python manage.py check
python scripts/check_file_size_limits.py --include-untracked
python scripts/check_diff_whitespace.py --include-untracked
```

## Local Pitfalls

1. `pytest.ini` default `testpaths` excludes `pull_requests/tests/`; run pull-request tests explicitly when touching that module.
2. `README.md` uses `python manage.py runserver 8000`, while `CLAUDE.md` mentions port `8002`. Follow the task's current runtime context unless you are intentionally reconciling the docs.
3. Azure PR list pagination can return short or overlapping pages. Keep fixed-stride paging and de-duplication in the repository adapter.
4. Intel Jira MVP setup/current-state notes live under `openspec/docs/historical/`, architecture details live under `openspec/docs/current-baseline/`, and normative requirements live under `openspec/specs/`; link to those docs instead of copying their content into AI guidance.
5. If a Jira token, PAT, cookie, or Authorization header appears in chat or logs, treat it as exposed and recommend rotation.
6. Do not hardcode Intel Jira status names globally. Example workflows belong in saved scope config records.
7. If no severity mapping exists for a scope, hide critical/high series instead of guessing severity.
8. Chart buckets and drilldown issue rows must share the same `calculation_run_id`; do not reconstruct drilldown membership from mutable current issue state.
9. Avoid naming new shared abstractions `Jira*` unless the abstraction truly cannot apply to GitHub, Azure DevOps, or another work-item provider. Prefer `Provider*`, `WorkItem*`, `Tracker*`, or provider-neutral domain names and put Jira vocabulary in adapter-local code or UI helper text.

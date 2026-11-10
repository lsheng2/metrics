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
| `project_management/` | Provider-neutral projects, immutable stage source definitions and local project_catalog CLI; report/UI work continues in add-provider-neutral-project-reporting |

Planned MVP owner additions:

| Module | Owner Boundary |
| --- | --- |
| `jira_sync/` | Intel Jira fetches, incremental sync, cursors, and sync status |
| `jira_history/` | Normalized issue state, raw snapshots, transitions, and durable persistence APIs |
| `bug_metrics/` | `jira_scope_config`, trend calculation, bucket aggregation, and drilldown membership |

## Architecture Rules

1. Modules communicate through public APIs under `app/api/`.
2. Domain code remains pure Python and framework-free.
3. UI uses semantic HTML, htmx, the Meridian design system and Chart.js (via `DashboardCharts`), plus the approved local Milkdown report editor. UI work follows `openspec/docs/current-baseline/frontend-design-requirements.md`.
4. Dataclasses use `@dataclass(slots=True)`.
5. External tracker behavior should reuse `sd-metrics-lib` when practical.
6. Secrets stay in `.env` or deployment environment variables and must not appear in committed files, docs, tests, or chat output.
7. `jira_scope_config` is the single authority for project-specific bug trend semantics; environment variables own connectivity only.
8. Bug trend dashboards read durable local history and aggregate artifacts, not live Jira queries on every page load.
9. Multi-provider first: Jira is the first rich work-item provider, not the architecture boundary. New tracker/work-item/AI workflow designs must define provider-neutral contracts and UI semantics first, then implement Jira, GitHub, Azure DevOps, or other systems as adapters with declared capabilities.
10. Project-management execution now lives in this Dashboard checkout. Chiplet is an instance only; never use its project ID, query or name as a production default. Jira and HSD-ES use the same project/stage contracts with honest per-provider coverage.
11. Do not create parallel product surfaces per provider. Shared concepts such as connection profile, work-item facts, metadata discovery, scope query/filter, action plan, approval/audit, and dashboard consumption belong in provider-neutral contracts; provider-specific modules own only external API quirks, auth, pagination, field identity, and sync implementation.
12. AI Base/SDK early-development policy (2026-11-01): coordinated breaking API changes are allowed and preferred over unnecessary permanent compatibility layers. Follow [API-EVO-01](../../openspec/changes/add-provider-neutral-project-reporting/ai-api-evolution.md) for versioned change records and per-app Agent handoffs; preserve security, evidence and business acceptance, not obsolete signatures. This is a design policy, not proof of migration or permission to delete data. Once a consumer migrates, delete its legacy path outright, with no fallback or mode switch (`AI_CONTRACT.md` §3).

## Common Validation

```powershell
python -m pytest path\to\test_file.py::TestClass::test_method -q
python manage.py check
python scripts/check_file_size_limits.py --include-untracked
python scripts/check_diff_whitespace.py --include-untracked
npm --prefix ui_web/frontend run check   # UI changes: token/vendor drift, Stylelint, WCAG contrast
```

## OpenSpec Authoring

Rules learned with OpenSpec CLI 1.14.x. Validate the change with
`npx --no-install openspec validate <change> --strict` and, after archiving,
`npx --no-install openspec validate --specs --strict`.

1. A `MODIFIED` requirement restates the whole main-spec requirement and keeps every scenario heading that requirement already has.
2. When a scenario's premise disappears, do not drop or rename it under `MODIFIED`: move the requirement to `## REMOVED Requirements` with `**Reason**:` and `**Migration**:` lines, and put the new behavior under `## ADDED Requirements` with a new title.
3. Archiving can create a main spec whose Purpose is "TBD - created by archiving ..."; replace it with the real purpose in the same change.

## Local Pitfalls

1. Default pytest paths omit `pull_requests`, `project_management` and `provider_sync`, and plain `pytest` loads `.env`.
   Select affected paths explicitly; reporting, `ui_web` and `project_management` tests use the isolated no-dotenv runner,
   selected SDK interpreter and real `ReportDraftService` doubles in `docs/development/reporting-delivery.md`; present but
   invalid stage archives are `REPORT_ARTIFACT_INVALID` (`openspec/docs/current-baseline/project-reporting.md`).
2. Follow the task's owned runtime/port. Do not reuse the unrelated 8017 service or silently upgrade
   the retained legacy `.venv`; current reporting validation uses SDK 0.2.0a1 with the original a2 pack.
3. Azure PR list pagination can return short or overlapping pages. Keep fixed-stride paging and de-duplication in the repository adapter.
4. Intel Jira MVP setup/current-state notes live under `openspec/docs/historical/`, architecture details live under `openspec/docs/current-baseline/`, and normative requirements live under `openspec/specs/`; link to those docs instead of copying their content into AI guidance.
5. If a Jira token, PAT, cookie, or Authorization header appears in chat or logs, treat it as exposed and recommend rotation.
6. Do not hardcode Intel Jira status names globally. Example workflows belong in saved scope config records.
7. If no severity mapping exists for a scope, hide critical/high series instead of guessing severity.
8. Chart buckets and drilldown issue rows must share the same `calculation_run_id`; do not reconstruct drilldown membership from mutable current issue state.
9. Avoid naming new shared abstractions `Jira*` unless the abstraction truly cannot apply to GitHub, Azure DevOps, or another work-item provider. Prefer `Provider*`, `WorkItem*`, `Tracker*`, or provider-neutral domain names and put Jira vocabulary in adapter-local code or UI helper text.
10. `.github/file-size-limits.json` must claim every tracked file (first matching rule wins; a file matching no rule or exemption fails, as does a run that checks nothing). Split by concern before a file reaches its limit: templates into partials, CSS into `css/foundation/`, `css/shell/` or `css/pages/<feature>.css`, browser JS into feature modules. Legacy allowances allow zero growth, apply only in changed-file mode and only while the base revision is already oversized; never raise a limit or add an exemption to make new code fit.
11. Every stylesheet and script is registered once in `ui_web/static_assets.py`, in cascade/dependency order; `base.html` renders it and browser tests inline the same list. Icon classes must be literal `iconoir-<name>` strings so `npm --prefix ui_web/frontend run build:vendor` can vendor the subset.

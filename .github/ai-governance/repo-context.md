# Repo Context

Status: active BKM.

## Summary

This is a Django modular monolith for software delivery metrics. It integrates Jira, Azure DevOps, Bitbucket/Azure Repos, and `sd-metrics-lib` to render task, forecast, velocity, and pull-request dashboards.

## Modules

| Module | Owner Boundary |
| --- | --- |
| `tasks/` | Task search, hierarchy, enrichment, tracker task conversion |
| `forecast/` | Forecast estimations, task health, scheduling parameters |
| `velocity/` | Developer and team velocity calculations |
| `pull_requests/` | PR discovery, review conversion, reviewer policy gates |
| `ui_web/` | Django views, facades, templates, htmx partials, UI data federation |
| `metrics/` | Django settings, URLs, middleware, deployment settings |

## Architecture Rules

1. Modules communicate through public APIs under `app/api/`.
2. Domain code remains pure Python and framework-free.
3. UI uses semantic HTML, Bulma, htmx, and Chart.js.
4. Dataclasses use `@dataclass(slots=True)`.
5. External tracker behavior should reuse `sd-metrics-lib` when practical.
6. Secrets stay in `.env` or deployment environment variables and must not appear in committed files, docs, tests, or chat output.

## Common Validation

```powershell
python -m pytest path\to\test_file.py::TestClass::test_method -q
python manage.py check
python scripts/check_file_size_limits.py --include-untracked
python scripts/check_diff_whitespace.py --include-untracked
```

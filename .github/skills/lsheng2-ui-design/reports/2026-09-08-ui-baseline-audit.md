# UI Baseline Audit - 2026-09-08

This audit is owned by the repo-local `lsheng2-ui-design` overlay and is intended to stop repeated UI drift in setup-heavy Dashboard pages.

The extracted component contract is maintained in `openspec/docs/current-baseline/ui-design-system.md`.

## Scope

Reviewed surfaces:

- Provider Setup inventory and Provider Profile Config editor
- Bug Trend Scope Config editor
- Scope Library
- Data Health
- Workbench

Framework contract:

- Django templates
- Bulma classes
- htmx for server interactions
- shared CSS and JavaScript in `ui_web/static`

## Baseline Decisions

- Setup/editor forms use `dashboard-edit-form`, `dashboard-form-grid`, `dashboard-form-field`, `dashboard-action-bar`, `dashboard-unsaved-banner`, `dashboard-validation-banner`, and `data-required-form`.
- Filter, import, and destructive action forms do not inherit setup-editor validation unless they explicitly opt in.
- Provider choice is represented as local tabs/cards using `provider-tab-shell`, `scope-provider-choice`, and `provider-tab-check`.
- Provider colors remain Jira green, HSD-ES blue, GitHub purple.
- Dense tables must use `responsive-admin-table`; table-local horizontal scroll is acceptable, page-level horizontal overflow is not.
- Required, dirty, disabled, success, warning, and error states must be visible in the changed page and covered by tests before UI closure.

## Current Coverage

Automated coverage now includes:

- Static contract checks for editor forms and shared required classes.
- Static contract checks for tool/filter forms that should not inherit editor dirty/required behavior.
- Browser layout checks for Provider Setup, Provider Profile Config, Scope Config, Scope Library, Data Health, and Workbench at desktop and phone widths.
- Required-field visual checks for Provider Profile and Scope Config.
- Dirty-field visual checks for Provider Profile and Scope Config.
- Provider Profile connection-test status rendering.
- Monkey-user flow that creates provider profiles, tests Jira and HSD-ES connection paths, creates a bound scope, and verifies Workbench chart/evidence handoff.

## Audit Findings

- Provider Profile and Scope Config share the same editor form and action-bar primitives.
- Scope Library and Data Health use responsive admin table primitives.
- Workbench uses its own shell because it is a dense split-pane tool, but it is included in the cross-page overflow gate.
- No new CSS primitive is required for this pass; the missing piece was project-level regression coverage rather than another local style.

## Required Validation

Run this when a UI change touches provider setup, scope setup, data-health, workbench, or shared CSS/JS:

```powershell
.venv\Scripts\python.exe manage.py test ui_web.tests.test_ui_design_baseline_gate
.venv\Scripts\python.exe manage.py test ui_web.tests.test_dashboard_ui_design_system ui_web.tests.test_provider_setup_views ui_web.tests.test_bug_trend_scope_config_views
.venv\Scripts\python.exe manage.py test ui_web.tests.test_data_health_views ui_web.tests.test_workbench_views ui_web.tests.test_workbench_ai_host_actions ui_web.tests.test_ai_dashboard_api_surface
scripts\validate_ui_design_gate.ps1 -Broad
```

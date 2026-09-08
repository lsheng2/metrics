# Dashboard UI Design System Contract

This document is the current implemented UI component contract for `scrum_dashboard`.
Normative behavior still lives in OpenSpec specs and active changes; this file explains the shared implementation primitives that UI changes must reuse.

## Stack Boundary

- Rendering: Django templates.
- Styling: Bulma plus dashboard tokens and component classes in `ui_web/static/css/main.css`.
- Interaction: htmx plus local JavaScript in `ui_web/static/js/main.js`.
- Browser validation: Django tests with Playwright for layout, required state, dirty state, and monkey-user flows.
- External design services: not used by default. Local screenshots and local browser metrics are the review evidence.

## Contract Table

| Contract | Owner | Required Classes Or Attributes | Used By | Validation |
| --- | --- | --- | --- | --- |
| Editor form | `main.css`, `main.js` | `dashboard-edit-form`, `data-dirty-form`, `data-required-form` | Provider Profile Config, Scope Config | `test_dashboard_ui_design_system`, `test_ui_design_baseline_gate` |
| Form grid | `main.css` | `dashboard-form-grid`, `dashboard-form-field` | Provider connection fields, profile identity, scope semantic fields | Browser control-height assertions |
| Required state | `main.css`, `main.js` | `dashboard-required-tag`, `dashboard-validation-banner`, `dashboard-required-message`, `is-missing-required`, `is-required-missing-control` | Save Draft, Enable, Test Connection | Action-specific required tests |
| Dirty state | `main.css`, `main.js` | `dashboard-unsaved-banner`, `is-dirty-field`, `is-dirty-control`, `dirty-marker` | Editable setup forms | Dirty/cancel browser tests |
| Action bar | `main.css` | `dashboard-action-bar`, `dashboard-action-group`, `dashboard-action-cancel` | Editor save/test/cancel/navigation controls | Button-height and gap assertions |
| Provider tabs | `main.css`, setup templates | `provider-tab-shell`, `provider-tab-list`, `provider-tab-body`, `scope-provider-choice`, `provider-tab-check`, `role="tablist"`, `role="tab"`, `role="tabpanel"` | Provider Profile Config, Scope Config | Tab shell and selected-check browser tests |
| Provider colors | `main.css` | `is-provider-green`, `is-provider-blue`, `is-provider-purple` | Jira, HSD-ES, GitHub provider identity | Static CSS/template tests |
| Responsive admin table | `main.css` | `responsive-admin-table-box`, `responsive-admin-table`, optional `is-cardable` | Scope Library, Provider Setup, Data Health, audit/readiness tables | Desktop/phone overflow tests |
| Help tip | `partials/help_tip.html`, `main.css` | `help-tip`, optional `is-icon` | Field labels, table headers, low-discoverability actions | Existing help-tip browser tests |
| Workbench shell | `main.css`, `main.js`, `workbench.html` | `workbench-shell`, `workbench-grid`, `workbench-pane`, `workbench-toolbar`, `workbench-control-grid`, `data-workbench-*` | Workbench chart/evidence/AI split-pane tool | Workbench browser tests and baseline gate |

## Usage Rules

- Persistent setup editors must use the Editor form, Form grid, Required state, Dirty state, and Action bar contracts.
- Filter, search, import, and destructive confirmation forms must not opt into `data-dirty-form` or `data-required-form` unless they become persistent editors.
- Provider Profile Config and Scope Config must use the same Provider tabs contract so Jira, HSD-ES, GitHub, and future providers are visually and structurally consistent.
- Provider colors are identity cues only: Jira green, HSD-ES blue, GitHub purple. Do not create separate provider color systems.
- Dense admin tables may scroll inside their table container, but the page itself must not horizontally overflow at desktop or phone widths.
- Workbench is allowed to keep a separate split-pane shell, but it remains part of the same browser overflow and interaction gate.

## State Matrix

Each setup/editor change must cover these states when affected:

- Default data present.
- Empty inventory or empty evidence.
- Dirty unsaved field.
- Missing required field.
- Disabled unavailable action.
- Loading or htmx refresh where applicable.
- Successful save, test, import, export, archive, or binding update.
- Failed save, test, import, delete, or workspace/sync action.
- Desktop and phone viewport.

## Required Commands

Run the focused design-system gate for UI contract changes:

```powershell
.venv\Scripts\python.exe manage.py test ui_web.tests.test_dashboard_ui_design_system ui_web.tests.test_ui_design_baseline_gate
```

Run the broader UI gate for provider, scope, data-health, workbench, or shared CSS/JS changes:

```powershell
.venv\Scripts\python.exe manage.py test ui_web.tests.test_dashboard_ui_design_system ui_web.tests.test_provider_setup_views ui_web.tests.test_bug_trend_scope_config_views ui_web.tests.test_data_health_views ui_web.tests.test_workbench_views ui_web.tests.test_workbench_ai_host_actions ui_web.tests.test_ai_dashboard_api_surface ui_web.tests.test_ui_design_baseline_gate
```

Also run:

```powershell
git diff --check
.venv\Scripts\python.exe manage.py check
```


# Dashboard UI Design System Contract

This document is the current implemented UI component contract for `scrum_dashboard`.
Normative behavior still lives in OpenSpec specs and active changes; this file explains the shared implementation primitives that UI changes must reuse.

## Stack Boundary

- Rendering: Django templates.
- Styling: Bulma plus dashboard tokens and component classes in `ui_web/static/css/main.css`.
- Interaction: htmx plus local JavaScript in `ui_web/static/js/main.js`.
- Browser validation: Django tests with Playwright for layout, required state, dirty state, and monkey-user flows.
- External design services: not used by default. Local screenshots and local browser metrics are the review evidence.
- Component token baseline: `C:/Users/lsheng2/.agents/skills/lsheng2-ui-design/data/component-tokens/dashboard-admin-v1.json`, calibrated through the repo overlay before subjective button, typography, form, table, tab, or feedback-state changes.
- Component catalog: `.github/skills/lsheng2-ui-design/component-catalog/dashboard-admin-v1.html`.
- Visual regression manifest: `.github/skills/lsheng2-ui-design/visual-regression/manifest.json`.

## Contract Table

| Contract | Owner | Required Classes Or Attributes | Used By | Validation |
| --- | --- | --- | --- | --- |
| Editor form | `main.css`, `main.js` | `dashboard-edit-form`, `data-dirty-form`, `data-required-form` | Provider Profile Config, Scope Config | `test_dashboard_ui_design_system`, `test_ui_design_baseline_gate` |
| Form grid | `main.css` | `dashboard-form-grid`, `dashboard-form-field` | Provider connection fields, profile identity, scope semantic fields | Browser control-height assertions |
| Required state | `main.css`, `main.js` | `dashboard-required-tag`, `dashboard-validation-banner`, `dashboard-required-message`, `is-missing-required`, `is-required-missing-control` | Save Draft, Enable, Test Connection | Action-specific required tests |
| Dirty state | `main.css`, `main.js` | `dashboard-unsaved-banner`, `is-dirty-field`, `is-dirty-control`, `dirty-marker` | Editable setup forms | Dirty/cancel browser tests |
| Editor state banners | `partials/dashboard_editor_state_banners.html` | `dashboard-unsaved-banner`, `dashboard-validation-banner`, `data-dirty-banner`, `data-required-summary` | Provider Profile Config, Scope Config | Static partial ownership tests |
| Action bar | `main.css` | `dashboard-action-bar`, `dashboard-action-group`, `dashboard-action-cancel` | Editor save/test/cancel/navigation controls | Button-height and gap assertions |
| Tool/filter form | `main.css` | `dashboard-tool-form`, `dashboard-tool-grid`, `dashboard-tool-field`, `dashboard-tool-actions` | Bug Trend filters, Task Forecast parameters, AI Workflow request, Current Tasks filters, Pull Request filters | Static template checks and browser layout gate |
| Action form | `main.css` | `dashboard-action-form`, optional `is-stacked` or `is-inline` | Import, export, duplicate, bind, archive, delete, sync, and confirmation forms | Static form ownership tests and visual manifest runner |
| Component token profile | `lsheng2-ui-design` core, project overlay | `dashboard-admin-v1.json`, `compactDashboard`, project overrides | Buttons, forms, tables, tabs, status feedback | Overlay/static audit plus browser layout gate |
| Audit exceptions | project overlay | `lsheng2-ui-design-audit-exceptions` JSON block | Narrow generated/synthetic table exceptions only | Static audit and browser table metrics audit |
| Component catalog and visual manifest | `lsheng2-ui-design` core, project overlay | local static HTML catalog, manifest JSON | Shared UI reviews and screenshot capture planning | Static artifact tests plus local UI gate |
| Provider tabs | `main.css`, setup templates | `provider-tab-shell`, `provider-tab-list`, `provider-tab-body`, `scope-provider-choice`, `provider-tab-check`, `role="tablist"`, `role="tab"`, `role="tabpanel"` | Provider Profile Config, Scope Config | Tab shell and selected-check browser tests |
| Provider colors | `main.css` | `is-provider-green`, `is-provider-blue`, `is-provider-purple` | Jira, HSD-ES, GitHub provider identity | Static CSS/template tests |
| Responsive admin table | `main.css` | `responsive-admin-table-box`, `responsive-admin-table`, optional `is-cardable` | Scope Library, Provider Setup, Data Health, audit/readiness tables | Desktop/phone overflow tests |
| Dense dashboard table | `main.css` | `dashboard-dense-table` | Current Tasks, Pull Requests, Task Forecast, velocity task tables, Workbench evidence | Static table-contract audit plus browser padding, row-height, button-height, and overflow metrics |
| Help tip | `partials/help_tip.html`, `main.css` | `help-tip`, optional `is-icon` | Field labels, table headers, low-discoverability actions | Existing help-tip browser tests |
| Workbench shell | `main.css`, `main.js`, `workbench.html` | `workbench-shell`, `workbench-grid`, `workbench-pane`, `workbench-toolbar`, `workbench-control-grid`, `data-workbench-*` | Workbench chart/evidence/AI split-pane tool | Workbench browser tests and baseline gate |

## Usage Rules

- Persistent setup editors must use the Editor form, Form grid, Required state, Dirty state, and Action bar contracts.
- Filter, search, import, and destructive confirmation forms must not opt into `data-dirty-form` or `data-required-form` unless they become persistent editors.
- Lightweight dashboard query forms must use the Tool/filter form contract instead of page-local `columns` and button sizing rules.
- Non-editor mutation, import/export, binding, archive, delete, and sync forms must declare the Action form contract so they remain visible to UI audits without inheriting editor dirty state.
- Subjective UI quality work must start from the component token profile and project overlay instead of one-off page-level button, font, spacing, or radius decisions.
- Provider Profile Config and Scope Config must use the same Provider tabs contract so Jira, HSD-ES, GitHub, and future providers are visually and structurally consistent.
- Provider colors are identity cues only: Jira green, HSD-ES blue, GitHub purple. Do not create separate provider color systems.
- Runtime data tables must use either `responsive-admin-table` for admin/cardable inventory tables or `dashboard-dense-table` for complex dashboard tables that need compact typography without changing their table structure.
- Dense admin tables may scroll inside their table container, but the page itself must not horizontally overflow at desktop or phone widths.
- Table contract or browser metric exceptions must live in the project overlay `lsheng2-ui-design-audit-exceptions` block with a narrow match and reason; reusable scripts must not hardcode project-specific special cases.
- Workbench is allowed to keep a separate split-pane shell, but it remains part of the same browser overflow and interaction gate.
- React/Next/Tailwind support is reserved through the reusable adapter interface; this Django/Bulma/htmx project should keep using the Django validation commands unless the frontend stack changes.

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
scripts\validate_ui_design_gate.ps1
```

Run the broader UI gate for provider, scope, data-health, workbench, or shared CSS/JS changes:

```powershell
scripts\validate_ui_design_gate.ps1 -Broad
```

Also run:

```powershell
git diff --check
python "C:\Users\lsheng2\.agents\skills\lsheng2-ui-design\scripts\audit_project_ui.py" --project-root .
.venv\Scripts\python.exe "C:\Users\lsheng2\.agents\skills\lsheng2-ui-design\scripts\audit_table_metrics.py" --project-root . --html-file ".github\skills\lsheng2-ui-design\component-catalog\dashboard-admin-v1.html"
python "C:\Users\lsheng2\.agents\skills\lsheng2-ui-design\scripts\render_component_catalog.py" --project-root . --output ".github/skills/lsheng2-ui-design/component-catalog/dashboard-admin-v1.html"
python "C:\Users\lsheng2\.agents\skills\lsheng2-ui-design\scripts\create_visual_regression_manifest.py" --project-root . --output ".github/skills/lsheng2-ui-design/visual-regression/manifest.json"
scripts\validate_ui_visual_manifest.ps1
.venv\Scripts\python.exe manage.py check
```

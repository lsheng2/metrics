# Dashboard UI Design System Contract

This document is the current implemented UI component contract for `scrum_dashboard`.
Normative behavior still lives in OpenSpec specs and active changes; this file explains the shared implementation primitives that UI changes must reuse.
Visual language, tokens, themes, navigation and the frontend QA gates are defined by the binding
[frontend design requirements](frontend-design-requirements.md); read both before any UI change.
Exact values, markup recipes and pitfalls live in [frontend design recipes](frontend-design-recipes.md),
and tooling, testing and review practice in [frontend delivery playbook](frontend-delivery-playbook.md).

## Stack Boundary

- Rendering: Django templates.
- Styling: the Meridian design system. DTCG tokens in `ui_web/frontend/tokens/` generate `ui_web/static/css/theme.css`; primitives live in `ui_web/static/css/foundation/*.css` (split by concern), the app frame in `ui_web/static/css/shell/*.css`, and page patterns plus the shared contracts below in the page layer, one file per feature under `ui_web/static/css/pages/<feature>.css`; there is no catch-all stylesheet. `ui_web/static_assets.py` is the single ordered manifest of stylesheets and scripts; browser tests inline the same lists.
- Interaction: htmx plus `shell.js` (theme, sidebar, drawer, popovers; `window.DashboardShell`), `command-palette.js`, `charts.js` (the `DashboardCharts` theme bridge), and one feature module per concern in `ui_web/static/js/<feature>.js` (listed in `FEATURE_SCRIPTS`; there is no catch-all script).
- Browser validation: Django tests with Playwright for layout, required state, dirty state, and monkey-user flows.
- Frontend toolchain gate: `npm run check` in `ui_web/frontend` (token drift, vendor manifest, Stylelint, WCAG contrast) and `npm run qa:browser` (axe, overflow and console checks across themes and widths).
- File-size gate: `python -I scripts/check_file_size_limits.py --include-untracked` (templates 300, CSS 400, browser JS 400 lines and so on); a file near its cap is split by concern before more is added. Dashboard templates, stylesheets and shell/feature scripts have no legacy allowances. The only frontend allowance is the report editor scripts (`legacy-report-editor-scripts`); it and the few non-frontend allowances are temporary freezes until their owners split them.
- Reusable layout audit: `lsheng2-ui-design/scripts/audit_layout_metrics.py` measures rendered page overflow, table density, button groups, and form controls.
- Live route/state audit: `scripts/validate_ui_live_routes.ps1` runs manifest scenarios against a local server, with hooked data states skipped by default.
- Hooked visual state audit: `scripts/ui_design_fixture_hooks.py` renders local-only synthetic Django fixtures for data-heavy/provider states when the runner is invoked with `-IncludeHooked`.
- Aggregate report: `lsheng2-ui-design/scripts/create_ui_gate_report.py` writes `.github/skills/lsheng2-ui-design/reports/ui-gate-report.json` and `.github/skills/lsheng2-ui-design/reports/ui-gate-report.md`.
- Full manifest gate: `scripts/validate_ui_full_manifest_gate.ps1` runs every manifest route with hooked scenarios and refreshes the aggregate report.
- Screenshot baseline/diff: required for the sanitized component catalog through `scripts/validate_ui_visual_diff_gate.ps1`; live route screenshot diffs remain local/untracked unless explicitly accepted.
- External design services: not used by default. Local screenshots and local browser metrics are the review evidence.
- Component token baseline: `C:/Users/lsheng2/.agents/skills/lsheng2-ui-design/data/component-tokens/dashboard-admin-v1.json`, calibrated through the repo overlay before subjective button, typography, form, table, tab, or feedback-state changes.
- Skill portability self-test: `lsheng2-ui-design/scripts/validate_synthetic_fixture.py` validates the reusable server-rendered Django adapter (id `django-bulma-htmx`) against a non-product fixture.
- Component catalog: `.github/skills/lsheng2-ui-design/component-catalog/dashboard-admin-v1.html`.
- Visual regression manifest: `.github/skills/lsheng2-ui-design/visual-regression/manifest.json`.

## Contract Table

| Contract | Owner | Required Classes Or Attributes | Used By | Validation |
| --- | --- | --- | --- | --- |
| Editor form | `pages/editor-forms.css`, `editor-forms.js`, `form-validation.js` | `dashboard-edit-form`, `data-dirty-form`, `data-required-form` | Provider Profile Config, Scope Config | `test_dashboard_ui_design_system`, `test_ui_design_baseline_gate` |
| Form grid | `pages/editor-forms.css` | `dashboard-form-grid`, `dashboard-form-field` | Provider connection fields, profile identity, scope semantic fields | Browser control-height assertions |
| Required state | `pages/editor-forms.css`, `foundation/forms.css` (`is-required-missing-control` hook), `form-validation.js` | `dashboard-required-tag`, `dashboard-validation-banner`, `dashboard-required-message`, `is-missing-required`, `is-required-missing-control` | Save Draft, Enable, Test Connection | Action-specific required tests |
| Dirty state | `pages/editor-forms.css`, `pages/provider-editor.css`, `foundation/forms.css` (`is-dirty-control` hook), `editor-forms.js` | `dashboard-unsaved-banner`, `is-dirty-field`, `is-dirty-control`, `dirty-marker` | Editable setup forms | Dirty/cancel browser tests |
| Editor state banners | `partials/dashboard_editor_state_banners.html` | `dashboard-unsaved-banner`, `dashboard-validation-banner`, `data-dirty-banner`, `data-required-summary` | Provider Profile Config, Scope Config | Static partial ownership tests |
| Action bar | `pages/provider-editor.css`, `pages/editor-responsive.css` | `dashboard-action-bar`, `dashboard-action-group`, `dashboard-action-cancel` | Editor save/test/cancel/navigation controls | Button-height and gap assertions |
| Signature grid | `pages/editor-responsive.css` | `dashboard-signature-grid`, `dashboard-signature-item`, `dashboard-signature-value` | Editor bottom config/hash/profile signatures after action bars | Browser gap, overflow, and value-fit assertions |
| Tool/filter form | `pages/editor-forms.css`, `pages/delivery-views.css` | `dashboard-tool-form`, `dashboard-tool-grid`, `dashboard-tool-field`, `dashboard-tool-actions` | Bug Trend filters, Task Forecast parameters, AI Workflow request, Current Tasks filters, Pull Request filters | Static template checks and browser layout gate |
| Dense top toolbar | `pages/editor-forms.css` | `dashboard-top-toolbar`, safe label row height, compact control height | Workbench top state bar, Bug Trend, Task Forecast, Current Tasks, Pull Requests, AI Dashboard Workflow page-top filter/request bars | Browser label clipping/out-of-field checks, form control height, and overflow checks |
| Action form | `pages/editor-forms.css` | `dashboard-action-form`, optional `is-stacked` or `is-row` | Import, export, duplicate, bind, archive, delete, sync, and confirmation forms | Static form ownership tests and visual manifest runner |
| Component token profile | `lsheng2-ui-design` core, project overlay | `dashboard-admin-v1.json`, `compactDashboard`, project overrides | Buttons, forms, tables, tabs, status feedback | Overlay/static audit plus browser layout gate |
| Audit exceptions | project overlay | `lsheng2-ui-design-audit-exceptions` JSON block | Narrow generated/synthetic exceptions only | Static audit plus browser table/layout metrics audit |
| Component catalog and visual manifest | `lsheng2-ui-design` core, project overlay | local static HTML catalog, manifest JSON | Shared UI reviews and screenshot capture planning | Static artifact tests plus local UI gate |
| Visual state scenarios | `lsheng2-ui-design` core, project overlay | `lsheng2-ui-design-state-scenarios`, `stateScenarios`, `requiresHook` | Required/dirty/provider tab/filter/chart states on live routes | `scripts\validate_ui_live_routes.ps1` plus manifest tests |
| Visual state hooks | project overlay, `scripts/ui_design_fixture_hooks.py` | `lsheng2-ui-design-hook-modules`, scenario `hook` names | Provider connection success, PR filter data, forecast hierarchy, velocity drilldown fixtures | Hooked visual state runner |
| UI gate report | `lsheng2-ui-design` core, project reports | `ui-gate-report.json`, `ui-gate-report.md` | Dashboard-style evidence summary with route counts, live/hooked counts, top risks, and failure screenshots | `create_ui_gate_report.py`, `refresh_ui_gate_report.ps1` |
| Full manifest live gate | project scripts | `validate_ui_full_manifest_gate.ps1` | One local command for full manifest route/state validation before scoped UI publication | Playwright route metrics, hooked visual states, aggregate report refresh |
| Synthetic visual diff gate | project scripts and committed baselines | `validate_ui_visual_diff_gate.ps1`, `synthetic-baseline-manifest.json`, `visual-regression/baselines/*.png` | Safe screenshot regression for shared component visual drift without provider/project data | `validate_ui_visual_diff_gate.ps1`, baseline refresh only with `-UpdateBaseline` |
| Provider tabs | `pages/provider-setup.css`, `pages/scope-query.css`, setup templates | `provider-tab-shell`, `provider-tab-list`, `provider-tab-body`, `scope-provider-choice`, `provider-tab-check`, `role="tablist"`, `role="tab"`, `role="tabpanel"` | Provider Profile Config, Scope Config | Tab shell and selected-check browser tests |
| Provider colors | `pages/provider-setup.css`, `pages/scope-config.css`, `pages/scope-query.css` | `is-provider-green`, `is-provider-blue`, `is-provider-purple` | Jira, HSD-ES, GitHub provider identity | Static CSS/template tests |
| Responsive admin table | `pages/dense-tables.css`, `pages/provider-setup.css` | `responsive-admin-table-box`, `responsive-admin-table`, optional `is-cardable` | Scope Library, Provider Setup, Data Health, audit/readiness tables | Desktop/phone overflow tests |
| Dense dashboard table | `pages/dense-tables.css` | `dashboard-dense-table` | Current Tasks, Pull Requests, Task Forecast, velocity task tables, Workbench evidence | Static table-contract audit, visual manifest route coverage, plus browser padding, row-height, button-height, and overflow metrics |
| Help tip | `partials/help_tip.html`, `foundation/page-patterns.css`, `pages/common.css` | `help-tip`, optional `is-icon` | Field labels, table headers, low-discoverability actions | Existing help-tip browser tests |
| Page header and results bar | `foundation/page-patterns.css`, `foundation/work-items.css` | `page-header`, `page-header__title`, `page-header__meta`, `page-header__actions`, `results-bar`, `results-bar__count`, `results-bar__actions` | Every data page (header, then filters, then results bar) | Browser overflow metrics, `qa:browser`; recipes §3 |
| KPI and facts | `foundation/page-patterns.css`, `foundation/work-items.css` | `stat-grid`, `stat`, `description-list`, `meta-strip`, `pipeline` | KPI rows, run manifests, publication and preview facts | Template contract tests; recipes §7 |
| Tags and status | `foundation/tables.css`, `foundation/status.css` | `tag`, `is-success\|is-warning\|is-danger\|is-info`, `count-badge`, `status-dot`, `health`, `dashboard_format` `status_tag` and `status_tone` | Status columns, counts, forecast health | Static template tests; recipes §5 |
| Disclosure and board | `foundation/disclosure.css`, `foundation/work-items.css` | `disclosure`, `disclosure__summary`, `disclosure__body`, `chip-disclosure`, `board`, `board__column`, `board-card` | Grouped rows, Pull Request activity, Current Tasks board | Template tests and browser metrics; recipes §7 |
| Chart card | `foundation/charts.css`, `charts.js` | `chart-grid`, `chart-card`, `chart-frame`, `series-toggles`, `data-palette-slot`, `window.DashboardCharts` | Bug Trend, Task Forecast, velocity and Workbench charts | Chart browser tests; recipes §8 |
| Report paper | `foundation/typography.css`, `report_editor.css` | `paper`, `--color-paper-*`, `:where(:not(.paper *))` guards | Report editor, preview and exports | Report browser contrast tests; recipes §9 |
| Workbench shell | `pages/workbench-{shell,panes,evidence}.css`, `workbench-state.js`, `pane-layout.js`, `workbench-evidence.js`, `workbench.html` | `workbench-shell`, `workbench-grid`, `workbench-pane`, `workbench-toolbar`, `workbench-control-grid`, `data-workbench-*` | Workbench chart/evidence/AI split-pane tool | Workbench browser tests and baseline gate |

## Usage Rules

- Persistent setup editors must use the Editor form, Form grid, Required state, Dirty state, Action bar, and Signature grid contracts when they render bottom hashes or configuration fingerprints.
- Filter, search, import, and destructive confirmation forms must not opt into `data-dirty-form` or `data-required-form` unless they become persistent editors.
- Lightweight dashboard query forms must use the Tool/filter form contract instead of page-local `columns` and button sizing rules.
- Page-top dense filter bars must use the Dense top toolbar contract so labels, controls, and action buttons align without clipping at compact height.
- Non-editor mutation, import/export, binding, archive, delete, and sync forms must declare the Action form contract so they remain visible to UI audits without inheriting editor dirty state.
- Subjective UI quality work must start from the component token profile and project overlay instead of one-off page-level button, font, spacing, or radius decisions.
- Provider Profile Config and Scope Config must use the same Provider tabs contract so Jira, HSD-ES, GitHub, and future providers are visually and structurally consistent.
- Provider colors are identity cues only: Jira green, HSD-ES blue, GitHub purple. Do not create separate provider color systems.
- Runtime data tables must use either `responsive-admin-table` for admin/cardable inventory tables or `dashboard-dense-table` for complex dashboard tables that need compact typography without changing their table structure.
- Dense admin tables may scroll inside their table container, but the page itself must not horizontally overflow at desktop or phone widths.
- Table, button, form, or browser metric exceptions must live in the project overlay `lsheng2-ui-design-audit-exceptions` block with a narrow match and reason; reusable scripts must not hardcode project-specific special cases.
- Nontrivial UI changes should generate or update a local checklist before implementation so route, state, component, token, and validation expectations are explicit before CSS or template edits.
- Live route state scenarios must declare `requiresHook` whenever they need fake provider responses, seeded facade data, or fixture-only chart/table content.
- Hooked state scenarios must declare a project-local hook name and must use synthetic or sanitized data.
- Broad UI gates should refresh the aggregate UI gate report so users can review one consolidated pass/fail artifact before scoped commit/push.
- Workbench is allowed to keep a separate split-pane shell, but it remains part of the same browser overflow and interaction gate.
- The Owner column names the current owner files. A contract style belongs to the ``ui_web/static/css/pages/<feature>.css`` of the feature it serves and its behavior to the ``ui_web/static/js/<feature>.js`` module of its concern, registered only in ``ui_web/static_assets.py``; when ownership moves, update this column in the same change.
- Every ``<form>`` declares ``dashboard-edit-form``, ``dashboard-tool-form`` or ``dashboard-action-form``, and every ``<table>`` declares ``responsive-admin-table`` or ``dashboard-dense-table``; the baseline gate fails unclassed ones. Tool forms and top toolbars carry no ``is-small`` buttons and no ``data-dirty-form``.
- Required markers are quiet neutral text (``dashboard-required-tag``), never red ``tag is-danger`` pills; dirty and validation banners come only from ``partials/dashboard_editor_state_banners.html``.
- Geometry limits live once in `ui_web/tests/ui_geometry_contract.py`; `python ui_web/tests/ui_geometry_contract.py` prints them by surface with unit, comparison, viewports and enforcing modules. The baseline gate measures the shared and table limits at 1440x900 and 390x900 and reports every violation in one failure, one line per rule, metric, page and viewport. Change a limit only in the registry, with design approval.
- The sanitized component-catalog PNG baselines predate the Meridian redesign and need an explicit re-baseline (``-UpdateBaseline``) once the new visuals are accepted.
- ``scripts\validate_ui_*.ps1`` hard-code a ``.venv``; when it is absent run the same checks with the selected Python (playbook §4.2).
- React/Next/Tailwind support is reserved through the reusable adapter interface; this server-rendered Django/htmx project keeps using the Django validation commands and the frontend toolchain gates unless the frontend stack changes.

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
python -I scripts/check_file_size_limits.py --include-untracked
python -I scripts/check_diff_whitespace.py --include-untracked
python "C:\Users\lsheng2\.agents\skills\lsheng2-ui-design\scripts\audit_project_ui.py" --project-root .
.venv\Scripts\python.exe "C:\Users\lsheng2\.agents\skills\lsheng2-ui-design\scripts\audit_table_metrics.py" --project-root . --html-file ".github\skills\lsheng2-ui-design\component-catalog\dashboard-admin-v1.html"
.venv\Scripts\python.exe "C:\Users\lsheng2\.agents\skills\lsheng2-ui-design\scripts\audit_layout_metrics.py" --project-root . --html-file ".github\skills\lsheng2-ui-design\component-catalog\dashboard-admin-v1.html" --checks overflow,tables,buttons,forms
python "C:\Users\lsheng2\.agents\skills\lsheng2-ui-design\scripts\generate_ui_checklist.py" --project-root . --target "Dashboard UI change"
python "C:\Users\lsheng2\.agents\skills\lsheng2-ui-design\scripts\render_component_catalog.py" --project-root . --output ".github/skills/lsheng2-ui-design/component-catalog/dashboard-admin-v1.html"
python "C:\Users\lsheng2\.agents\skills\lsheng2-ui-design\scripts\create_visual_regression_manifest.py" --project-root . --output ".github/skills/lsheng2-ui-design/visual-regression/manifest.json"
python "C:\Users\lsheng2\.agents\skills\lsheng2-ui-design\scripts\create_ui_gate_report.py" --project-root . --write
python "C:\Users\lsheng2\.agents\skills\lsheng2-ui-design\scripts\validate_synthetic_fixture.py"
scripts\validate_ui_visual_manifest.ps1
scripts\validate_ui_live_routes.ps1 -BaseUrl http://127.0.0.1:8000 -NoScreenshots
scripts\validate_ui_live_routes.ps1 -BaseUrl http://127.0.0.1:8000 -NoScreenshots -AllManifestRoutes -IncludeHooked
scripts\validate_ui_full_manifest_gate.ps1 -BaseUrl http://127.0.0.1:8000 -NoScreenshots
scripts\validate_ui_visual_diff_gate.ps1
scripts\validate_ui_visual_diff_gate.ps1 -UpdateBaseline
scripts\refresh_ui_gate_report.ps1 -BaseUrl http://127.0.0.1:8000 -IncludeHooked
.venv\Scripts\python.exe manage.py check
```

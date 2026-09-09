# lsheng2-ui-design Project Overlay

This is the repo-local overlay for the reusable `lsheng2-ui-design` core skill.

The reusable core lives at `C:/Users/lsheng2/.agents/skills/lsheng2-ui-design`. This overlay owns only `scrum_dashboard`-specific UI facts, commands, privacy boundaries, and accepted design decisions.

## Project Identity

- Project: `scrum_dashboard`
- Product area: Metrics Dashboard for software development, provider-backed bug trend setup, Workbench, AI/Grafana workflows, current tasks, velocity, forecasting, pull requests, and data health.
- Primary users: local dashboard operators, engineering leads, and developers configuring provider profiles/scopes or reviewing delivery metrics.
- UI risk level: normal for ordinary visual polish; high for setup flows that affect provider bindings, credentials, deletion/archive actions, data sync, AI/Grafana publication, or user-visible runtime selection.

## Framework Adapter

- Adapter: Django/Bulma/htmx.
- Rendering: server-rendered Django templates with partial templates.
- Styling: Bulma plus `ui_web/static/css/main.css` design tokens and compatibility aliases.
- Interaction model: htmx for partial swaps, server-rendered forms, and small local JavaScript in `ui_web/static/js/main.js`.
- Component/story surface: Django templates, partials, CSS classes, JS behaviors, and Playwright-backed Django tests.

## Design System Source

- Token files:
  - `ui_web/static/css/main.css`
  - `ui_web/static/css/vendor_fallbacks.css`
- Shared CSS/components:
  - `ui_web/static/css/main.css`
  - `ui_web/static/js/main.js`
  - `ui_web/templates/base.html`
  - `ui_web/templates/partials/help_tip.html`
  - `ui_web/templates/partials/dashboard_editor_state_banners.html`
  - `ui_web/templates/partials/provider_profile_editor.html`
  - `ui_web/templates/bug_trend_scope_config.html`
- `openspec/docs/current-baseline/ui-design-system.md`
- Typography source: `--dashboard-font-*` variables in `ui_web/static/css/main.css` plus Bulma base typography.
- Color source: `--dashboard-*` variables in `ui_web/static/css/main.css`; provider identity colors are Jira green, HSD-ES blue, GitHub purple.
- Spacing/radius source: `--dashboard-radius-*`, form-grid gaps, action-bar gaps, and Bulma spacing utilities in `ui_web/static/css/main.css`.
- Icon source: existing Iconoir/Bulma usage and project helper templates; prefer existing icon families before adding new icon systems.

## Component Token Profile

- Core token pack: `C:/Users/lsheng2/.agents/skills/lsheng2-ui-design/data/component-tokens/dashboard-admin-v1.json`
- Selected density profile: `compactDashboard` for operational dashboard forms, filters, tables, and setup editors.
- Project overrides: `dashboard-tool-*` uses 2rem controls; setup editors use `dashboard-edit-form`, `dashboard-form-grid`, `dashboard-form-field`, `dashboard-action-bar`, and `dashboard-action-group`; cards/panels stay at 8px radius or below unless an existing Bulma component requires otherwise.
- Golden/accepted UI surfaces: Provider Profile Config, Bug Trend Scope Config, Provider Setup inventory, Scope Library, Data Health, Workbench, AI Dashboard Workflow, Current Tasks, Pull Requests, Task Forecast.
- Component catalog location: `.github/skills/lsheng2-ui-design/component-catalog/dashboard-admin-v1.html`
- Visual regression manifest: `.github/skills/lsheng2-ui-design/visual-regression/manifest.json`
- Screenshot artifact policy: keep screenshots in `tmp_ui_validation/visual-regression` unless explicitly requested; commit only synthetic catalog HTML and manifest JSON.
- Screenshot baseline/diff policy: keep baselines and diffs in `tmp_ui_validation/visual-baselines` and `tmp_ui_validation/visual-diffs` by default; commit no screenshots unless a future review explicitly adopts sanitized baselines.
- Monkey-user E2E checklist: `.github/skills/lsheng2-ui-design/reports/provider-profile-scope-monkey-e2e-checklist.md`
- `ui-ux-pro-max` style references: use local dense-dashboard style and UX searches for guidance only; `lsheng2-ui-design` remains the implementation and validation authority.

## Route / Page Inventory

| route/page | source files | validation command | notes |
| --- | --- | --- | --- |
| `/provider-setup/` | `ui_web/views/bug_trend_view.py`, `ui_web/templates/provider_setup.html`, `ui_web/templates/provider_profile_config.html`, `ui_web/templates/partials/provider_profile_editor.html`, `ui_web/facades/bug_trend_facade.py`, `ui_web/facades/provider_scope_setup.py`, `ui_web/static/css/main.css`, `ui_web/static/js/main.js` | `.venv\Scripts\python.exe manage.py test ui_web.tests.test_provider_setup_views ui_web.tests.test_dashboard_ui_design_system` | Provider profile inventory, create/edit/test/import/export/archive/delete, provider color tabs, connection/auth/probe fields. |
| `/bug-trend/scope-config/` | `ui_web/views/bug_trend_view.py`, `ui_web/templates/bug_trend_scope_config.html`, `ui_web/facades/bug_trend_facade.py`, `ui_web/facades/provider_scope_setup.py`, `ui_web/static/css/main.css`, `ui_web/static/js/main.js` | `.venv\Scripts\python.exe manage.py test ui_web.tests.test_bug_trend_scope_config_views ui_web.tests.test_dashboard_ui_design_system` | Scope editor, provider binding, metadata refresh, action-specific required validation, dirty/cancel state. |
| `/bug-trend/scopes/` | `ui_web/views/bug_trend_view.py`, `ui_web/templates/bug_trend_scope_library.html`, `ui_web/static/css/main.css`, `ui_web/templates/partials/help_tip.html` | `.venv\Scripts\python.exe manage.py test ui_web.tests.test_bug_trend_scope_config_views` | Scope inventory, binding controls, import/export/archive/delete, responsive table behavior. |
| `/data-health/` | `ui_web/templates/data_health.html`, `ui_web/static/css/main.css`, data-health views/facades | `.venv\Scripts\python.exe manage.py test ui_web.tests.test_data_health_views` | Health/status tables, binding status, AI/provider sync readiness. |
| `/workbench/` | `ui_web/templates/workbench.html`, `ui_web/static/js/main.js`, workbench views/facades | `.venv\Scripts\python.exe manage.py test ui_web.tests.test_workbench_views ui_web.tests.test_workbench_ai_host_actions` | htmx workbench shell, evidence filters, AI host action state. |
| `/ai-dashboard/workflow/` | `ui_web/templates/ai_dashboard_workflow.html`, `ui_web/views/ai_dashboard_view.py`, `ui_web/static/css/main.css` | `.venv\Scripts\python.exe manage.py test ui_web.tests.test_ai_dashboard_api_surface` | AI/Grafana workflow forms and publication status surfaces. |
| `/current-tasks/` | `ui_web/views/current_tasks_view.py`, `ui_web/templates/current_tasks.html`, `ui_web/templates/partials/current_tasks_content.html`, `ui_web/templates/partials/task_table.html`, `ui_web/static/css/main.css` | `.venv\Scripts\python.exe manage.py test ui_web.tests.test_ui_design_baseline_gate` | Current task filters, lazy/eager task tables, available members, dense task rows. |
| `/pull-requests/` | `ui_web/views/pull_requests_view.py`, `ui_web/templates/pull_requests.html`, `ui_web/templates/partials/pull_requests_table.html`, `ui_web/templates/partials/pull_request_summary_table.html`, `ui_web/static/css/main.css` | `.venv\Scripts\python.exe manage.py test ui_web.tests.test_ui_design_baseline_gate` | Pull request summary, filters, review/gate dense tables. |
| `/task-forecast/` | `ui_web/views/task_forecast_view.py`, `ui_web/templates/task_forecast.html`, `ui_web/templates/partials/task_forecast_content.html`, `ui_web/static/css/main.css` | `.venv\Scripts\python.exe manage.py test ui_web.tests.test_ui_design_baseline_gate` | Forecast parameter form, task breakdown dense table, timeline chart shell. |
| `/team-velocity/` | `ui_web/views/team_velocity_view.py`, `ui_web/templates/team_velocity.html`, `ui_web/templates/partials/team_velocity_content.html`, `ui_web/static/css/main.css` | `.venv\Scripts\python.exe manage.py test ui_web.tests.test_ui_design_baseline_gate` | Team velocity chart controls and task drilldown placeholder. |
| `/dev-velocity/` | `ui_web/views/dev_velocity_view.py`, `ui_web/templates/dev_velocity.html`, `ui_web/templates/partials/dev_velocity_content.html`, `ui_web/static/css/main.css` | `.venv\Scripts\python.exe manage.py test ui_web.tests.test_ui_design_baseline_gate` | Developer velocity chart controls and task drilldown placeholder. |
| `/bug-trend/scope-audit/` | `ui_web/views/bug_trend_view.py`, `ui_web/templates/bug_trend_scope_audit.html`, `ui_web/static/css/main.css` | `.venv\Scripts\python.exe manage.py test ui_web.tests.test_ui_design_baseline_gate` | Scope audit coverage and observed-values responsive table. |
| `/partials/bug-trend/evidence/` | `ui_web/views/bug_trend_view.py`, `ui_web/templates/partials/bug_trend_evidence.html`, `ui_web/static/css/main.css` | `.venv\Scripts\python.exe manage.py test ui_web.tests.test_ui_design_baseline_gate` | Bug Trend evidence filters, dense evidence table, and ticket detail shell. |

## Shared UI Contracts

| contract | owner files | use for | avoid |
| --- | --- | --- | --- |
| `dashboard-edit-form` | `ui_web/static/css/main.css`, setup templates | Any persistent setup/editor form with save/cancel behavior. | Filter/search/action-only forms. |
| `dashboard-form-grid` and `dashboard-form-field` | `ui_web/static/css/main.css`, setup templates | Aligned label/control grids for setup forms. | One-off nested cards or page-local grid variants. |
| `dashboard-action-bar` and `dashboard-action-group` | `ui_web/static/css/main.css`, setup templates | Bottom action bars with grouped primary/secondary/cancel actions. | Per-page button height, spacing, or typography overrides. |
| `dashboard-tool-form`, `dashboard-tool-grid`, `dashboard-tool-field`, `dashboard-tool-actions` | `ui_web/static/css/main.css`, dashboard query/filter templates | Lightweight non-editor forms for filters, forecast parameters, and workflow request controls. | Persistent setup/edit forms that need dirty or required-state handling. |
| `dashboard-action-form` | `ui_web/static/css/main.css`, setup/library/workbench templates | Import, export, duplicate, bind, archive, delete, sync, and other non-editor action forms. | Applying dirty editor behavior to confirmation/action forms. |
| `dashboard-required-tag` | `ui_web/static/css/main.css`, setup templates | Required, required-to-save, required-for-enable, and required-for-test markers. | Raw Bulma danger tags in setup forms without shared class. |
| `dashboard-validation-banner`, `data-required-form` | `ui_web/static/css/main.css`, `ui_web/static/js/main.js` | Action-specific required-field visual validation. | Browser-only authority without backend validation. |
| `dashboard-unsaved-banner`, `data-dirty-form` | `ui_web/static/css/main.css`, `ui_web/static/js/main.js` | Dirty/unsaved field marking and cancel guard. | Treating dirty state as validation error. |
| `provider-tab-shell`, `scope-provider-choice`, `provider-tab-check` | `ui_web/static/css/main.css`, provider/scope templates | Provider selection tabs/cards and provider color identity. | Replacing provider identity with unrelated color systems. |
| `.help-tip` and `partials/help_tip.html` | `ui_web/templates/partials/help_tip.html`, `ui_web/static/css/main.css` | Text-hover help and selective icon help. | Adding visible question icons for every label. |
| responsive admin tables | `ui_web/static/css/main.css`, library/data-health templates | Dense dashboard tables with responsive card fallback. | Wide tables that create horizontal page overflow on phone. |
| `dashboard-dense-table` | `ui_web/static/css/main.css`, dashboard partial templates | Compact typography and control density for complex tables that should keep native table structure. | Raw Bulma tables without a shared density contract. |

The expanded component-level contract is documented in `openspec/docs/current-baseline/ui-design-system.md`.

## State Matrix Requirements

- default: every changed target renders normal data without layout shift.
- hover/focus: links, buttons, tabs, menus, and help affordances are keyboard-visible.
- loading: htmx and expensive table/chart regions show a local loading indicator.
- empty: inventory, table, and dashboard sections show useful empty states.
- error: failed save/test/import/export/sync actions render visible feedback without exposing secrets.
- required validation: setup/editor forms use action-specific missing-field highlights.
- dirty/unsaved: editable forms show field-level dirty state and a cancel path.
- disabled: unavailable actions explain why they are disabled when the reason is not obvious.
- success: save/test/import/export flows render confirmation or status near the affected editor.

## Validation Commands

Use a target-specific subset for small UI changes and the broader group for shared form/style changes.

```sh
git diff --check
python "C:\Users\lsheng2\.agents\skills\lsheng2-ui-design\scripts\audit_project_ui.py" --project-root .
python "C:\Users\lsheng2\.agents\skills\lsheng2-ui-design\scripts\generate_ui_checklist.py" --project-root . --target "Dashboard UI change"
.venv\Scripts\python.exe "C:\Users\lsheng2\.agents\skills\lsheng2-ui-design\scripts\audit_table_metrics.py" --project-root . --html-file ".github\skills\lsheng2-ui-design\component-catalog\dashboard-admin-v1.html"
.venv\Scripts\python.exe "C:\Users\lsheng2\.agents\skills\lsheng2-ui-design\scripts\audit_layout_metrics.py" --project-root . --html-file ".github\skills\lsheng2-ui-design\component-catalog\dashboard-admin-v1.html" --checks overflow,tables,buttons,forms
python "C:\Users\lsheng2\.agents\skills\lsheng2-ui-design\scripts\render_component_catalog.py" --project-root . --output ".github/skills/lsheng2-ui-design/component-catalog/dashboard-admin-v1.html"
python "C:\Users\lsheng2\.agents\skills\lsheng2-ui-design\scripts\create_visual_regression_manifest.py" --project-root . --output ".github/skills/lsheng2-ui-design/visual-regression/manifest.json"
python "C:\Users\lsheng2\.agents\skills\lsheng2-ui-design\scripts\create_ui_gate_report.py" --project-root . --write
scripts\validate_ui_design_gate.ps1
scripts\validate_ui_design_gate.ps1 -Broad
scripts\validate_ui_visual_manifest.ps1
scripts\validate_ui_live_routes.ps1 -BaseUrl http://127.0.0.1:8000 -NoScreenshots
scripts\validate_ui_live_routes.ps1 -BaseUrl http://127.0.0.1:8000 -NoScreenshots -AllManifestRoutes -IncludeHooked
scripts\refresh_ui_gate_report.ps1 -BaseUrl http://127.0.0.1:8000 -IncludeHooked
scripts\validate_ui_full_manifest_gate.ps1 -BaseUrl http://127.0.0.1:8000 -NoScreenshots
.venv\Scripts\python.exe manage.py test ui_web.tests.test_ui_design_baseline_gate
.venv\Scripts\python.exe manage.py test ui_web.tests.test_dashboard_ui_design_system
.venv\Scripts\python.exe manage.py test ui_web.tests.test_provider_setup_views ui_web.tests.test_bug_trend_scope_config_views
.venv\Scripts\python.exe manage.py test ui_web.tests.test_data_health_views ui_web.tests.test_workbench_views ui_web.tests.test_workbench_ai_host_actions ui_web.tests.test_ai_dashboard_api_surface
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
openspec validate standardize-dashboard-ui-design-system --strict
openspec validate consolidate-provider-onboarding-profile --strict
```

## Screenshot / Visual Diff Procedure

- Server command: `.venv\Scripts\python.exe manage.py runserver 127.0.0.1:<free-port>`
- Desktop viewport: 1440x900
- Tablet viewport: 768x1024
- Phone viewport: 390x900
- Routes to capture: changed route plus nearest sibling page that shares the same UI contract.
- Output directory: local temp directory or project-local ignored folder selected for that run.
- Diff threshold: target-specific; any horizontal overflow, clipped text, hidden required marker, or misaligned action bar is a failure regardless of pixel threshold.
- Manifest: `.github/skills/lsheng2-ui-design/visual-regression/manifest.json`
- Suggested browser evidence: use Playwright from Django tests or a short one-off local script to assert overflow, control-height delta, state visibility, and focus target.
- Live route state runner: `scripts\validate_ui_live_routes.ps1 -BaseUrl http://127.0.0.1:8000`; default scope is Provider Setup and Scope Config because those routes can be validated without external provider data.
- Full manifest live gate: `scripts\validate_ui_full_manifest_gate.ps1 -BaseUrl http://127.0.0.1:8000 -NoScreenshots`; this runs all manifest routes with project fixture hooks and refreshes the aggregate report.
- Screenshot diff command: `scripts\validate_ui_full_manifest_gate.ps1 -BaseUrl http://127.0.0.1:8000 -WithScreenshotDiff`; use `-UpdateBaseline` only after accepting a new local baseline.

## Privacy Boundary

Never include these in scratch diagrams, screenshots intended for sharing, or external tools:

- tokens and passwords
- environment files
- internal URLs
- customer or project identifiers
- query text containing internal product data
- Jira/HSD-ES profile ids
- provider base URLs
- saved query ids and tenant/subject values
- AI/Grafana publication identifiers when they contain internal context

Synthetic replacements:

| sensitive data | replacement |
| --- | --- |
| provider URL | `https://provider.example.test` |
| token/password | `********` |
| profile id | `sample-profile` |
| query text | `project = SAMPLE` |

## Known UI Pitfalls

- UI changes have repeatedly drifted in button size, tag typography, field alignment, action spacing, and page-specific CSS.
- Provider Profile and Bug Trend Scope Config must remain visually consistent but action-specific required rules differ.
- Filter/search forms, import forms, and destructive confirm forms should not inherit setup-editor validation behavior unless they explicitly opt in.
- Temporary screenshots and UI validation folders are local artifacts and should not be staged unless explicitly requested.
- The current UI baseline audit lives at `.github/skills/lsheng2-ui-design/reports/2026-09-08-ui-baseline-audit.md`.
- The current shared component contract lives at `openspec/docs/current-baseline/ui-design-system.md`.

## Accepted Design Decisions

- Keep the existing Django + Bulma + htmx stack.
- Prefer shared dashboard-level classes over page-local CSS variants.
- Provider color identity: Jira green, HSD-ES blue, GitHub purple.
- Provider selection should be visually prominent and connected to provider-specific form content.
- Provider Profile owns provider-level onboarding/connection defaults; Scope owns project/range/query operation and binds to a profile.
- Use local-first scratch diagrams or static wireframes before broad UI redesign; do not use external design services by default.
- `ui-ux-pro-max` is optional design intelligence; `lsheng2-ui-design` remains the implementation and validation gate.

## Autonomous Audit Scope

- Default pages: Provider Setup, Provider Profile Config, Bug Trend Scope Config, Scope Library, Data Health, Workbench, AI Dashboard Workflow, Current Tasks, Pull Requests, and Task Forecast.
- Extended pages: Team Velocity and Dev Velocity chart controls plus velocity task drilldown tables are included in visual-manifest coverage.
- Component focus: buttons, typography, forms, tables, tabs/cards, action bars, required/dirty/error/loading/success states, browser-measured table metrics, and horizontal overflow.
- Ignored/generated paths: temporary screenshots, `tmp_ui_validation/`, generated caches, vendored assets, migrations unless a migration UI exists.
- Findings report location: `.github/skills/lsheng2-ui-design/reports/` for curated reports; temporary audit output stays local unless explicitly committed.
- Apply-fixes policy: shared tokens/classes/partials first, then template migration, then page-local exceptions only when the pattern is unique and documented; data-driven avatar colors are allowed inline until a CSS custom-property helper exists.
- Scoped commit/push policy: refresh `.github/skills/lsheng2-ui-design/reports/ui-gate-report.md` and `.github/skills/lsheng2-ui-design/reports/ui-gate-report.json` before staging UI work; stage only intended UI/skill files and keep `tmp_ui_validation/` local.

## Audit Exceptions / Allowlist

Runtime product templates should not use table exceptions. Generated or synthetic local design artifacts can be allowlisted when they intentionally demonstrate raw component structure.

```json lsheng2-ui-design-audit-exceptions
{
  "tableContractAllowlist": [
    {
      "pathContains": ".github/skills/lsheng2-ui-design/component-catalog/",
      "reason": "Synthetic local component catalog output is not runtime product UI; runtime Django templates must still use shared table contracts."
    }
  ],
  "tableMetricsAllowlist": [],
  "layoutMetricsAllowlist": []
}
```

## Browser Metric Thresholds

These values match the current `compactDashboard` density profile and are enforced by the local browser metric gate.

```json lsheng2-ui-design-metric-thresholds
{
  "tableMetrics": {
    "maxPaddingBlock": 12,
    "maxButtonHeightDelta": 1,
    "maxDenseRowHeight": 72
  },
  "buttonMetrics": {
    "maxButtonHeightDelta": 1
  },
  "formMetrics": {
    "maxControlHeightDelta": 1,
    "maxButtonHeightDelta": 1
  },
  "layoutSelectors": {
    "buttonGroups": [
      ".dashboard-action-bar",
      ".dashboard-action-group",
      ".dashboard-tool-actions",
      ".scope-primary-actions",
      ".provider-row-primary-actions",
      ".workbench-evidence-actions",
      ".buttons.are-small",
      "[data-ui-action-group]"
    ],
    "forms": [
      ".dashboard-tool-form",
      ".dashboard-edit-form",
      "form[data-ui-form]"
    ],
    "formControls": [
      ".dashboard-tool-field .input",
      ".dashboard-tool-field select",
      ".dashboard-form-field .input",
      ".dashboard-form-field select",
      "[data-ui-form-control]"
    ],
    "formButtons": [
      ".dashboard-tool-actions .button",
      ".dashboard-action-bar .button",
      ".dashboard-action-group .button",
      "[data-ui-form-button]"
    ]
  }
}
```

## Visual State Hook Modules

Hooked scenarios use local-only Django fixtures. These hooks render existing templates with synthetic data and do not register production routes or call external providers.

```json lsheng2-ui-design-hook-modules
{
  "modules": ["scripts/ui_design_fixture_hooks.py"]
}
```

## Visual State Scenarios

These route scenarios feed `.github/skills/lsheng2-ui-design/visual-regression/manifest.json`. Scenarios with `requiresHook` need seeded Django fakes or a local fixture server and are skipped by the live route runner unless `-IncludeHooked` is passed. Hooked dashboard scenarios map to `scripts/ui_design_fixture_hooks.py`.

```json lsheng2-ui-design-state-scenarios
{
  "routes": {
    "/provider-setup/": [
      {
        "name": "jira-tab-selected",
        "stateTarget": "tabs/default-selected-hover-focus-disabled",
        "query": {"mode": "new", "provider_id": "jira"},
        "checks": ["no-page-horizontal-overflow", "no-clipped-buttons", "no-unnamed-icon-buttons", "selected-provider-check-visible"]
      },
      {
        "name": "hsdes-tab-selected",
        "stateTarget": "tabs/default-selected-hover-focus-disabled",
        "query": {"mode": "new", "provider_id": "hsdes"},
        "checks": ["no-page-horizontal-overflow", "no-clipped-buttons", "no-unnamed-icon-buttons", "selected-provider-check-visible"]
      },
      {
        "name": "profile-required-missing",
        "stateTarget": "form/default-required-missing-dirty-saving-success-failure",
        "query": {"mode": "new", "provider_id": "jira"},
        "steps": [{"action": "click", "selector": "button[name='action'][value='test_connection']"}],
        "checks": ["no-page-horizontal-overflow", "no-clipped-buttons", "required-summary-visible", "missing-required-visible", "selected-provider-check-visible"]
      },
      {
        "name": "profile-dirty-unsaved",
        "stateTarget": "form/default-required-missing-dirty-saving-success-failure",
        "query": {"mode": "new", "provider_id": "jira"},
        "steps": [{"action": "fill", "selector": "#provider-profile-id", "value": "sample-jira-profile"}],
        "checks": ["no-page-horizontal-overflow", "no-clipped-buttons", "dirty-banner-visible", "selected-provider-check-visible"]
      },
      {
        "name": "profile-test-success",
        "stateTarget": "status-feedback/info-success-warning-danger",
        "query": {"mode": "new", "provider_id": "jira"},
        "checks": ["no-page-horizontal-overflow", "no-clipped-buttons", "no-unnamed-icon-buttons", "selected-provider-check-visible", "status-feedback-visible"],
        "hook": "provider_profile_test_success",
        "requiresHook": "mock provider connection response"
      },
      {
        "name": "profile-test-failure",
        "stateTarget": "status-feedback/info-success-warning-danger",
        "query": {"mode": "new", "provider_id": "jira"},
        "checks": ["no-page-horizontal-overflow", "no-clipped-buttons", "no-unnamed-icon-buttons", "selected-provider-check-visible", "status-feedback-visible"],
        "hook": "provider_profile_test_failure",
        "requiresHook": "mock provider connection failure"
      }
    ],
    "/bug-trend/scope-config/": [
      {
        "name": "default",
        "stateTarget": "default",
        "query": {"mode": "new", "provider_id": "jira"},
        "checks": ["no-page-horizontal-overflow", "no-clipped-buttons", "no-unnamed-icon-buttons", "selected-provider-check-visible"]
      },
      {
        "name": "jira-scope-tab-selected",
        "stateTarget": "tabs/default-selected-hover-focus-disabled",
        "query": {"mode": "new", "provider_id": "jira"},
        "checks": ["no-page-horizontal-overflow", "no-clipped-buttons", "selected-provider-check-visible"]
      },
      {
        "name": "hsdes-scope-tab-selected",
        "stateTarget": "tabs/default-selected-hover-focus-disabled",
        "query": {"mode": "new", "provider_id": "hsdes"},
        "checks": ["no-page-horizontal-overflow", "no-clipped-buttons", "selected-provider-check-visible"]
      },
      {
        "name": "scope-required-missing",
        "stateTarget": "form/default-required-missing-dirty-saving-success-failure",
        "query": {"mode": "new", "provider_id": "jira"},
        "steps": [{"action": "click", "selector": "button[name='action'][value='save_enable']"}],
        "checks": ["no-page-horizontal-overflow", "no-clipped-buttons", "required-summary-visible", "missing-required-visible", "selected-provider-check-visible"]
      },
      {
        "name": "scope-dirty-unsaved",
        "stateTarget": "form/default-required-missing-dirty-saving-success-failure",
        "query": {"mode": "new", "provider_id": "jira"},
        "steps": [{"action": "fill", "selector": "#scope-name", "value": "Sample Scope"}],
        "checks": ["no-page-horizontal-overflow", "no-clipped-buttons", "dirty-banner-visible", "selected-provider-check-visible"]
      }
    ],
    "/pull-requests/": [
      {
        "name": "pull-request-filter-applied",
        "stateTarget": "table/default-empty-loading-selected-archived-error",
        "query": {"author": "Monkey User"},
        "checks": ["no-page-horizontal-overflow", "no-clipped-buttons", "table-contracts-present", "filter-applied-visible"],
        "hook": "pull_request_filter_applied",
        "requiresHook": "fake pull request facade data"
      }
    ],
    "/current-tasks/": [
      {
        "name": "default",
        "stateTarget": "table/default-empty-loading-selected-archived-error",
        "query": {},
        "checks": ["no-page-horizontal-overflow", "no-clipped-buttons", "no-unnamed-icon-buttons", "table-contracts-present"],
        "hook": "current_tasks_fake_data",
        "requiresHook": "fake current tasks facade data"
      }
    ],
    "/task-forecast/": [
      {
        "name": "forecast-filter-applied",
        "stateTarget": "table/default-empty-loading-selected-archived-error",
        "query": {"task_id": "TASK-101", "include_done_tasks": "true"},
        "checks": ["no-page-horizontal-overflow", "no-clipped-buttons", "table-contracts-present"],
        "hook": "task_forecast_fake_data",
        "requiresHook": "fake task forecast facade data"
      }
    ],
    "/team-velocity/": [
      {
        "name": "default",
        "stateTarget": "chart-drilldown-selected",
        "query": {"period": "2026-09", "member_group_id": "core"},
        "checks": ["no-page-horizontal-overflow", "no-clipped-buttons", "table-contracts-present"],
        "hook": "team_velocity_fake_data",
        "requiresHook": "fake team velocity facade data"
      },
      {
        "name": "team-velocity-drilldown-selected",
        "stateTarget": "chart-drilldown-selected",
        "query": {"period": "2026-09", "member_group_id": "core"},
        "checks": ["no-page-horizontal-overflow", "no-clipped-buttons", "table-contracts-present"],
        "hook": "team_velocity_fake_data",
        "requiresHook": "fake team velocity facade data"
      }
    ],
    "/dev-velocity/": [
      {
        "name": "default",
        "stateTarget": "chart-drilldown-selected",
        "query": {"period": "2026-09", "developers": "Monkey User", "member_group_id": "core"},
        "checks": ["no-page-horizontal-overflow", "no-clipped-buttons", "table-contracts-present"],
        "hook": "dev_velocity_fake_data",
        "requiresHook": "fake developer velocity facade data"
      },
      {
        "name": "dev-velocity-drilldown-selected",
        "stateTarget": "chart-drilldown-selected",
        "query": {"period": "2026-09", "developers": "Monkey User", "member_group_id": "core"},
        "checks": ["no-page-horizontal-overflow", "no-clipped-buttons", "table-contracts-present"],
        "hook": "dev_velocity_fake_data",
        "requiresHook": "fake developer velocity facade data"
      }
    ],
    "/partials/bug-trend/evidence/": [
      {
        "name": "default",
        "stateTarget": "table/default-empty-loading-selected-archived-error",
        "query": {},
        "checks": ["no-page-horizontal-overflow", "no-clipped-buttons", "no-unnamed-icon-buttons", "table-contracts-present"],
        "hook": "bug_trend_evidence_fake_data",
        "requiresHook": "fake bug trend evidence data"
      }
    ]
  }
}
```

## React / Next / Tailwind Notes

- Applies: not currently; this project uses Django/Bulma/htmx.
- Component/story surface: Django templates and Playwright-backed tests, not a React component tree.
- Token source: `ui_web/static/css/main.css`.
- Storybook/harness: none.
- Build/test commands: use Django validation commands in this overlay.
- Adapter status: reserved for future React/Next/Tailwind/component-tree projects; do not apply React-specific rules to this repo unless the frontend stack changes.
- Adapter resolver: `C:/Users/lsheng2/.agents/skills/lsheng2-ui-design/scripts/resolve_framework_adapter.py --project-root .` should continue to select Django/Bulma/htmx for this repo.

## OpenSpec Integration

- UI spec location: active change under `openspec/changes/<change-id>/specs/.../spec.md`.
- Required UI sections: target, user goal, required data, state matrix, layout rules, component mapping, token impact, privacy notes, validation plan.
- Review gates: OpenSpec strict validation, focused Django/Playwright tests, local browser evidence for nontrivial visual changes.
- Archive/sync notes: when a UI change becomes durable, sync the accepted rules into the relevant main spec or project overlay before archiving.

## Discovery Warnings

- Generated overlay was curated after helper discovery; rerun helper dry-run after major UI stack changes and compare before replacing this file.

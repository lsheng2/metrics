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
  - `ui_web/templates/partials/provider_profile_editor.html`
  - `ui_web/templates/bug_trend_scope_config.html`
- Typography source: `--dashboard-font-*` variables in `ui_web/static/css/main.css` plus Bulma base typography.
- Color source: `--dashboard-*` variables in `ui_web/static/css/main.css`; provider identity colors are Jira green, HSD-ES blue, GitHub purple.
- Spacing/radius source: `--dashboard-radius-*`, form-grid gaps, action-bar gaps, and Bulma spacing utilities in `ui_web/static/css/main.css`.
- Icon source: existing Iconoir/Bulma usage and project helper templates; prefer existing icon families before adding new icon systems.

## Route / Page Inventory

| route/page | source files | validation command | notes |
| --- | --- | --- | --- |
| `/provider-setup/` | `ui_web/views/bug_trend_view.py`, `ui_web/templates/provider_setup.html`, `ui_web/templates/provider_profile_config.html`, `ui_web/templates/partials/provider_profile_editor.html`, `ui_web/facades/bug_trend_facade.py`, `ui_web/facades/provider_scope_setup.py`, `ui_web/static/css/main.css`, `ui_web/static/js/main.js` | `.venv\Scripts\python.exe manage.py test ui_web.tests.test_provider_setup_views ui_web.tests.test_dashboard_ui_design_system` | Provider profile inventory, create/edit/test/import/export/archive/delete, provider color tabs, connection/auth/probe fields. |
| `/bug-trend/scope-config/` | `ui_web/views/bug_trend_view.py`, `ui_web/templates/bug_trend_scope_config.html`, `ui_web/facades/bug_trend_facade.py`, `ui_web/facades/provider_scope_setup.py`, `ui_web/static/css/main.css`, `ui_web/static/js/main.js` | `.venv\Scripts\python.exe manage.py test ui_web.tests.test_bug_trend_scope_config_views ui_web.tests.test_dashboard_ui_design_system` | Scope editor, provider binding, metadata refresh, action-specific required validation, dirty/cancel state. |
| `/bug-trend/scope-library/` | `ui_web/views/bug_trend_view.py`, `ui_web/templates/bug_trend_scope_library.html`, `ui_web/static/css/main.css`, `ui_web/templates/partials/help_tip.html` | `.venv\Scripts\python.exe manage.py test ui_web.tests.test_bug_trend_scope_config_views` | Scope inventory, binding controls, import/export/archive/delete, responsive table behavior. |
| `/data-health/` | `ui_web/templates/data_health.html`, `ui_web/static/css/main.css`, data-health views/facades | `.venv\Scripts\python.exe manage.py test ui_web.tests.test_data_health_views` | Health/status tables, binding status, AI/provider sync readiness. |
| `/workbench/` | `ui_web/templates/workbench.html`, `ui_web/static/js/main.js`, workbench views/facades | `.venv\Scripts\python.exe manage.py test ui_web.tests.test_workbench_views ui_web.tests.test_workbench_ai_host_actions` | htmx workbench shell, evidence filters, AI host action state. |
| `/ai-dashboard-workflow/` | `ui_web/templates/ai_dashboard_workflow.html`, `ui_web/views/ai_dashboard_view.py`, `ui_web/static/css/main.css` | `.venv\Scripts\python.exe manage.py test ui_web.tests.test_ai_dashboard_api_surface` | AI/Grafana workflow forms and publication status surfaces. |

## Shared UI Contracts

| contract | owner files | use for | avoid |
| --- | --- | --- | --- |
| `dashboard-edit-form` | `ui_web/static/css/main.css`, setup templates | Any persistent setup/editor form with save/cancel behavior. | Filter/search/action-only forms. |
| `dashboard-form-grid` and `dashboard-form-field` | `ui_web/static/css/main.css`, setup templates | Aligned label/control grids for setup forms. | One-off nested cards or page-local grid variants. |
| `dashboard-action-bar` and `dashboard-action-group` | `ui_web/static/css/main.css`, setup templates | Bottom action bars with grouped primary/secondary/cancel actions. | Per-page button height, spacing, or typography overrides. |
| `dashboard-required-tag` | `ui_web/static/css/main.css`, setup templates | Required, required-to-save, required-for-enable, and required-for-test markers. | Raw Bulma danger tags in setup forms without shared class. |
| `dashboard-validation-banner`, `data-required-form` | `ui_web/static/css/main.css`, `ui_web/static/js/main.js` | Action-specific required-field visual validation. | Browser-only authority without backend validation. |
| `dashboard-unsaved-banner`, `data-dirty-form` | `ui_web/static/css/main.css`, `ui_web/static/js/main.js` | Dirty/unsaved field marking and cancel guard. | Treating dirty state as validation error. |
| `provider-tab-shell`, `scope-provider-choice`, `provider-tab-check` | `ui_web/static/css/main.css`, provider/scope templates | Provider selection tabs/cards and provider color identity. | Replacing provider identity with unrelated color systems. |
| `.help-tip` and `partials/help_tip.html` | `ui_web/templates/partials/help_tip.html`, `ui_web/static/css/main.css` | Text-hover help and selective icon help. | Adding visible question icons for every label. |
| responsive admin tables | `ui_web/static/css/main.css`, library/data-health templates | Dense dashboard tables with responsive card fallback. | Wide tables that create horizontal page overflow on phone. |

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
- Phone viewport: 390x900
- Routes to capture: changed route plus nearest sibling page that shares the same UI contract.
- Output directory: local temp directory or project-local ignored folder selected for that run.
- Diff threshold: target-specific; any horizontal overflow, clipped text, hidden required marker, or misaligned action bar is a failure regardless of pixel threshold.
- Suggested browser evidence: use Playwright from Django tests or a short one-off local script to assert overflow, control-height delta, state visibility, and focus target.

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

## Accepted Design Decisions

- Keep the existing Django + Bulma + htmx stack.
- Prefer shared dashboard-level classes over page-local CSS variants.
- Provider color identity: Jira green, HSD-ES blue, GitHub purple.
- Provider selection should be visually prominent and connected to provider-specific form content.
- Provider Profile owns provider-level onboarding/connection defaults; Scope owns project/range/query operation and binds to a profile.
- Use local-first scratch diagrams or static wireframes before broad UI redesign; do not use external design services by default.
- `ui-ux-pro-max` is optional design intelligence; `lsheng2-ui-design` remains the implementation and validation gate.

## OpenSpec Integration

- UI spec location: active change under `openspec/changes/<change-id>/specs/.../spec.md`.
- Required UI sections: target, user goal, required data, state matrix, layout rules, component mapping, token impact, privacy notes, validation plan.
- Review gates: OpenSpec strict validation, focused Django/Playwright tests, local browser evidence for nontrivial visual changes.
- Archive/sync notes: when a UI change becomes durable, sync the accepted rules into the relevant main spec or project overlay before archiving.

## Discovery Warnings

- Generated overlay was curated after helper discovery; rerun helper dry-run after major UI stack changes and compare before replacing this file.

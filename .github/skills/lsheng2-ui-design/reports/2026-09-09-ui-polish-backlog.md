# UI Polish Backlog - 2026-09-09

This report is the current `lsheng2-ui-design` polish pass for `scrum_dashboard`.

The durable component contract is maintained in `openspec/docs/current-baseline/ui-design-system.md`.

## Gate Evidence

- Static UI audit scanned 283 UI files with `Findings: 0`.
- Browser table metrics passed for the local component catalog at desktop and phone widths.
- Broad UI gate passed after adding visual-manifest coverage for Current Tasks, Pull Requests, and Task Forecast.
- Dense dashboard table synthetic browser coverage passed for Current Tasks, Pull Requests, and Task Forecast partials.
- Shared button/action-group and form-control browser metrics are now checked in the baseline gate.
- Reusable `lsheng2-ui-design` layout metrics now cover tables, shared button groups, and editor/tool forms.
- Velocity task drilldown dense table coverage is now included in the synthetic browser gate.
- Visual state scenarios now cover Provider Setup, Scope Config, Pull Requests, Task Forecast, Team Velocity, and Dev Velocity; states that need fake data are marked with `requiresHook`.
- Hooked visual state fixtures now use `scripts/ui_design_fixture_hooks.py` through the overlay-declared `lsheng2-ui-design-hook-modules` block.
- Aggregate UI gate evidence is written to `.github/skills/lsheng2-ui-design/reports/ui-gate-report.md` and `.github/skills/lsheng2-ui-design/reports/ui-gate-report.json`.
- Optional CI/pre-push snippets are generated under `.github/skills/lsheng2-ui-design/ci/`.

## Compact Dashboard Review

`compactDashboard` remains the right density profile for this project.

Why:

- The app is an operational dashboard, not a marketing or editorial surface.
- Primary users scan dense tables, filters, status, and setup state repeatedly.
- Current shared contracts now cover setup editors, tool forms, action forms, responsive admin tables, and dense dashboard tables.
- The browser gate verifies page overflow, row density, button text clipping, table button height consistency, and form/control height deltas.

Current decision:

- Keep `compactDashboard`.
- Keep `responsive-admin-table` for cardable admin/inventory tables.
- Keep `dashboard-dense-table` for complex dashboard data tables that need native table structure and horizontal scrolling.

## Monkey-User Flow Review

The existing monkey-user UI path remains covered by browser-backed tests:

1. Create a Jira Provider Profile.
2. Test the Jira connection state without leaking tokens.
3. Create and enable an HSD-ES Provider Profile.
4. Create a Jira Scope bound to the Jira profile.
5. Verify Workbench receives provider/profile/scope handoff context.

Current decision:

- No new blocking UX issue was found in the profile-to-scope-to-workbench path during this pass.
- Continue to use Provider Profile as provider onboarding identity and Scope as project/range/query selection.

## Polish Backlog

No blocking static UI contract findings are open.

Recommended optional improvements:

| priority | area | opportunity | validation |
| --- | --- | --- | --- |
| P3 | Visual catalog | Review the generated component catalog with stakeholders before changing token values. | component catalog plus screenshot review |
| P3 | Hooked live routes | Add production-safe server-side fixture toggles only if future CI needs full live-route data state coverage instead of local rendered HTML fixtures. | `scripts\validate_ui_live_routes.ps1 -IncludeHooked` |

## Closure

This pass did not find a reason to redesign the current visual language. Future UI work should continue through the same overlay, static audit, browser metrics, and visual-manifest gate.

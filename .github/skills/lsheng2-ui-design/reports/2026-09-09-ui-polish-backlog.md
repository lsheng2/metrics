# UI Polish Backlog - 2026-09-09

This report is the current `lsheng2-ui-design` polish pass for `scrum_dashboard`.

The durable component contract is maintained in `openspec/docs/current-baseline/ui-design-system.md`.

## Gate Evidence

- Static UI audit scanned 283 UI files with `Findings: 0`.
- Browser table metrics passed for the local component catalog at desktop and phone widths.
- Broad UI gate passed after adding visual-manifest coverage for Current Tasks, Pull Requests, and Task Forecast.
- Dense dashboard table synthetic browser coverage passed for Current Tasks, Pull Requests, and Task Forecast partials.
- Shared button/action-group and form-control browser metrics are now checked in the baseline gate.

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
| P3 | Velocity pages | Add synthetic dense-table state coverage for Team Velocity and Dev Velocity task drilldown partials once their fake facade data is centralized. | `ui_web.tests.test_ui_design_baseline_gate` |
| P3 | Button metrics | Consider promoting the project-proven button/action-group browser metrics into the reusable `lsheng2-ui-design` skill. | skill self-tests plus project broad gate |
| P3 | Form metrics | Add browser label/control alignment metrics for complex setup forms beyond existing control/button height checks. | Provider Setup and Scope Config Playwright tests |
| P3 | Visual catalog | Review the generated component catalog with stakeholders before changing token values. | component catalog plus screenshot review |

## Closure

This pass did not find a reason to redesign the current visual language. Future UI work should continue through the same overlay, static audit, browser metrics, and visual-manifest gate.

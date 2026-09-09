# lsheng2-ui-design UI Change Checklist

- Target: Dashboard UI change
- Project: `C:\Users\lsheng2\OneDrive - Intel Corporation\Documents\my_project\scrum_dashboard`
- Overlay: `C:\Users\lsheng2\OneDrive - Intel Corporation\Documents\my_project\scrum_dashboard\.github\skills\lsheng2-ui-design\templates\project-overlay.md`
- Framework adapter: Django/Bulma/htmx
- Focus: buttons, typography, forms, tables, tabs, states

## Before Editing

- [ ] Read the project overlay and current UI design-system contract.
- [ ] Confirm the target route, user goal, and monkey-user happy path.
- [ ] Map each changed surface to an existing shared contract before adding CSS.
- [ ] Check whether the change needs a local scratch diagram or OpenSpec UI section.
- [ ] Keep source, screenshots, DOM, tokens, provider URLs, profile IDs, and customer data local.

## Routes And States

- [ ] `/provider-setup/`
- [ ] `/bug-trend/scope-config/`
- [ ] `/bug-trend/scopes/`
- [ ] `/data-health/`
- [ ] `/workbench/`
- [ ] `/ai-dashboard/workflow/`
- [ ] `/current-tasks/`
- [ ] `/pull-requests/`
- [ ] `/task-forecast/`
- [ ] `/team-velocity/`
- [ ] `/dev-velocity/`
- [ ] `/bug-trend/scope-audit/`
- [ ] `/partials/bug-trend/evidence/`

- [ ] Default data-present state.
- [ ] Empty state for lists, tables, or inventory surfaces.
- [ ] Loading state for htmx, chart, or async regions.
- [ ] Required/error state for forms.
- [ ] Dirty/unsaved state for persistent editors.
- [ ] Success/failure feedback for save, test, import, export, archive, delete, sync, or publish actions.
- [ ] Disabled/unavailable actions explain why when the reason is not obvious.
- [ ] Desktop, tablet when useful, and phone viewports.

## Component Contract

- [ ] Buttons use shared action/tool sizing and one clear primary action per group.
- [ ] Forms use editor/tool/action form contracts rather than page-local grids.
- [ ] Tables use `responsive-admin-table` or `dashboard-dense-table`.
- [ ] Tabs/cards show selected state, focus state, and provider identity color when applicable.
- [ ] Typography uses project font tokens and compact dashboard scale.
- [ ] Help affordances are close to confusing labels without adding noisy icons everywhere.

## Validation

- [ ] Run static UI audit for the affected focus.
- [ ] Run `audit_layout_metrics.py` for tables, buttons, and forms.
- [ ] Run visual manifest or focused browser checks for affected routes.
- [ ] Run `run_visual_state_scenarios.py` or the project live-route gate for required, dirty, tab, filter, and chart states.
- [ ] Run focused project tests named in the overlay.
- [ ] Run `git diff --check` before committing.

## Future Adapter Note

- [ ] If this is React, Next.js, Tailwind, Storybook, or a component-tree frontend, use the reserved adapter contract and do not apply Django/Bulma assumptions.

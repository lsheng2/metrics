## Why

Provider Profile Config and Bug Trend Scope Config have repeatedly drifted in button size, tag size, label typography, form grid spacing and unsaved-edit feedback because each page can add page-specific CSS and template structure. The dashboard needs a reusable design-system contract so future UI changes reference shared tokens/components instead of tuning one page at a time.

## What Changes

- Define dashboard-level UI tokens for control height, font scale, tag scale, spacing, radius, borders, focus and dirty-state affordances.
- Introduce shared component classes for edit forms, form grids, form fields, action bars, action groups, required tags, status tags, panels and unsaved banners.
- Migrate Provider Profile Config and Bug Trend Scope Config to the shared classes while keeping compatibility aliases for existing selectors.
- Add project-wide UI consistency tests that scan templates/CSS for drift-prone page-specific action bars and validate desktop/mobile button, tag, font and dirty-state behavior in browser.
- Keep the existing Django + Bulma + HTMX stack; this change standardizes presentation contracts, not frontend architecture.

## Impact

- `ui_web/static/css/main.css` shared tokens and component classes.
- `ui_web/static/js/main.js` shared dirty-form field marking.
- Provider Profile and Scope Config templates and tests.
- OpenSpec dashboard UI baseline contract.

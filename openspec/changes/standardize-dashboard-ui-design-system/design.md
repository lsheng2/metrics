## Design

### Design-System Layers

1. **Primitive tokens**
   - Color, spacing, radius, border, focus, font and control-height variables live under `:root`.
   - Page CSS must consume tokens instead of hardcoding alternate button/font scales.

2. **Shared component classes**
   - `.dashboard-edit-form`
   - `.dashboard-form-grid`
   - `.dashboard-form-field`
   - `.dashboard-action-bar`
   - `.dashboard-action-group`
   - `.dashboard-action-cancel`
   - `.dashboard-unsaved-banner`
   - `.dashboard-required-tag`
   - `.dashboard-status-tag`

3. **Compatibility aliases**
   - Existing page classes such as `.provider-editor-actions`, `.provider-form-field` and `.scope-config-form-field` remain as aliases during migration.
   - New or touched templates must add the dashboard-level class beside the page-specific class.

### Enforcement

- Browser tests validate edited-field highlighting, unsaved marker, action button height, action gap and mobile overflow on each setup editor.
- Static tests scan changed Dashboard templates/CSS for drift-prone patterns:
  - dirty forms must use `.dashboard-edit-form`
  - editor action bars must use `.dashboard-action-bar`
  - required-field tags inside setup forms must use `.dashboard-required-tag`
  - new action bars should not introduce page-specific button/font sizing without a shared-token alias

### Scope

This pass migrates the known setup editors:
- Provider Profile Config
- Bug Trend Scope Config

Other pages are covered by global button/tag/font tokens and static drift tests. Future page redesigns must adopt the same shared classes before adding local variants.

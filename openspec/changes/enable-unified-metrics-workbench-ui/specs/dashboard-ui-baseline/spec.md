## ADDED Requirements

### Requirement: Existing Dashboard surfaces are pane-compatible
当前 Django dashboard surfaces SHALL be reusable inside the unified workbench shell without duplicating business logic or bypassing facade/module boundaries.

#### Scenario: Workbench mounts an existing Dashboard page surface
- **WHEN** workbench loads a Django-owned page or component such as Bug Trend evidence、scope config、data health、publish history or diagnostics
- **THEN** the surface SHALL be delivered through an explicit pane route, partial, or view mode
- **AND** it SHALL continue to obtain data through UI facades and owning module public APIs

#### Scenario: Pane refreshes a Django partial
- **WHEN** a workbench pane refreshes after PageQueryState changes
- **THEN** only the pane or its target partial SHALL be replaced
- **AND** unrelated panes SHALL preserve their scroll position, form state and layout unless the new query state invalidates them

#### Scenario: A full page remains directly accessible
- **WHEN** 用户访问 legacy/full-page Dashboard URL
- **THEN** system SHALL continue to render the existing page unless that page has an approved migration path
- **AND** the page SHALL link or redirect to the workbench only when the target workbench behavior is functionally equivalent

### Requirement: Workbench shell preserves Dashboard UI technology baseline
Workbench shell SHALL preserve the existing Dashboard baseline of server-rendered Django, semantic HTML, Bulma and HTMX for Dashboard-owned surfaces, while permitting a narrowly scoped client-side dock layout layer for pane composition.

#### Scenario: Dashboard-owned pane needs dynamic refresh
- **WHEN** a Dashboard-owned pane refreshes chart state, evidence rows, settings or publish/audit content
- **THEN** it SHALL prefer server-rendered HTML or JSON-backed HTMX/vanilla browser behavior consistent with the existing Dashboard UI baseline
- **AND** it SHALL NOT require rewriting existing Dashboard pages into a new frontend framework

#### Scenario: Dock layout layer is introduced
- **WHEN** implementation adds a dock/window frame dependency for pane placement
- **THEN** the dependency SHALL be isolated to shell layout responsibilities
- **AND** Dashboard-owned domain interactions SHALL remain in existing views, facades, APIs and templates

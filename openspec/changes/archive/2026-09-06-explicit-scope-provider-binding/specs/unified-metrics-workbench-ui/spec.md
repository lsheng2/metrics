# unified-metrics-workbench-ui Specification Delta

## ADDED Requirements

### Requirement: Workbench state is normalized through explicit scope bindings
Workbench shell SHALL own shared PageQueryState for canonical scope/range/chart/selection/list-filter state, while server-side binding resolution SHALL derive profile、provider、workspace 和 AI context from the selected scope or selected provider profile. Workbench SHALL NOT treat profile/provider display fields as independent query authority when a canonical scope binding is available.

#### Scenario: User changes profile or range
- **WHEN** 用户修改 provider profile、provider-derived scope、range mode、begin/end 或 chart filter
- **THEN** shell SHALL update PageQueryState
- **AND** shell SHALL clear selected bucket and selected series
- **AND** chart pane and evidence pane SHALL refresh from the updated state

#### Scenario: User changes scope
- **WHEN** 用户在 workbench toolbar 选择不同 scope
- **THEN** shell SHALL immediately submit or HTMX-refresh the workbench using `scope_id` as the user-selected authority
- **AND** server-side PageQueryState normalization SHALL resolve `profile_id`、`provider_id`、workspace key and AI binding context from the selected scope binding
- **AND** profile/provider controls SHALL be rendered as read-only derived display fields, without `name` attributes in the primary toolbar form
- **AND** applying the toolbar SHALL refresh chart, evidence and AI panes for the resolved scope binding

#### Scenario: Workbench receives stale profile or provider query parameters
- **WHEN** a URL, local storage restore, AI host action or legacy bookmark includes `profile_id` or `provider_id` that contradict the selected `scope_id`
- **THEN** server-side normalization SHALL ignore the stale profile/provider values for provider-backed state and use the selected scope binding
- **AND** the shell SHALL generate a canonical pushed URL that omits derived profile/provider parameters when `scope_id` is present
- **AND** downstream chart, evidence, Grafana panel and AI context requests SHALL use only the normalized binding values

#### Scenario: Scope binding requires configuration
- **WHEN** selected scope has no safe explicit or compatibility binding to a provider profile
- **THEN** Workbench SHALL display a configuration-required state for provider-backed panes
- **AND** the state SHALL identify the selected scope and the missing binding action
- **AND** Workbench SHALL NOT keep rendering stale profile/provider values from a previously selected scope

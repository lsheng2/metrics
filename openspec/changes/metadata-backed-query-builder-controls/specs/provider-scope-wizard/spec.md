## ADDED Requirements

### Requirement: Metadata-backed Query Builder controls
For Jira-backed Scope Config, Query Builder source population controls SHALL prefer Jira metadata-backed selectable options for supported fields and SHALL preserve manual fallback input when metadata is unavailable, incomplete, or not enumerable.

#### Scenario: Metadata refresh populates source controls
- **WHEN** 用户刷新 Jira metadata and the current source mode is `Query Builder`
- **THEN** Scope Config SHALL render selectable source controls for discovered issue types、components、affected versions、fix versions、priorities 和 resolutions
- **AND** those controls SHALL show previously selected builder values as selected when the page or partial re-renders

#### Scenario: Metadata context is colocated with source population
- **WHEN** the selected provider is Jira
- **THEN** metadata discovery controls and status SHALL be rendered inside the Source population Query Builder working area
- **AND** Scope Config SHALL NOT render a separate Jira Metadata discovery context section below Source population
- **AND** Scope Config SHALL NOT render a visible discovered metadata catalog for either `Custom JQL` or `Query Builder`
- **AND** discovered metadata SHALL still power field pickers and validation results

#### Scenario: Picker opening refreshes metadata
- **WHEN** the operator opens a Query Builder field picker
- **THEN** Scope Config SHALL refresh Jira metadata using the current form payload
- **AND** the refreshed picker SHALL open with a type-in search input and filtered results
- **AND** the refresh SHALL update all related Query Builder metadata-backed fields from the same response

#### Scenario: Manual fallback remains available
- **WHEN** Jira metadata does not include a value the operator needs
- **THEN** each metadata-backed source field SHALL still provide an editable input for additional values
- **AND** saving a Query Builder scope SHALL merge selected metadata values and manual fallback values into the generated source query without duplicates

#### Scenario: Labels remain manual
- **WHEN** the operator configures Jira labels in Query Builder
- **THEN** Scope Config SHALL keep labels as a manual text/list input unless the provider returns label metadata
- **AND** labels SHALL be included in the generated query only in `Query Builder` mode

#### Scenario: Custom field can use metadata field picker
- **WHEN** Jira metadata includes field definitions
- **THEN** Query Builder SHALL allow choosing a custom query field from discovered field metadata
- **AND** it SHALL still allow manual field ids for fields missing from metadata
- **AND** field values SHALL remain editable manually when allowed values cannot be discovered for the selected field

#### Scenario: Custom JQL isolation
- **WHEN** 用户选择 `Custom JQL` mode and metadata-backed Query Builder controls contain selected values
- **THEN** saving the scope SHALL persist the user-authored JQL as the only runtime source query
- **AND** Query Builder selections SHALL NOT be appended as hidden filters or persisted as active builder state

#### Scenario: Metadata refresh does not save scope
- **WHEN** metadata refresh re-renders discovered options and Query Builder source controls
- **THEN** the saved scope SHALL NOT be mutated
- **AND** generated preview state SHALL come only from the current form payload and metadata response

#### Scenario: Pre-save metadata validation reports unconfirmed values
- **WHEN** the operator clicks Validate values before saving a Jira Query Builder scope
- **THEN** Scope Config SHALL refresh metadata for the current form payload without saving the scope
- **AND** it SHALL report which Query Builder values match discovered metadata and which typed values remain unconfirmed
- **AND** unconfirmed values SHALL remain editable and saveable as manual fallback values

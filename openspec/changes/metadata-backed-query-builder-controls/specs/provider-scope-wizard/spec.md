## ADDED Requirements

### Requirement: Metadata-backed Query Builder controls
For Jira-backed Scope Config, Query Builder source population controls SHALL prefer Jira metadata-backed selectable options for supported fields and SHALL preserve manual fallback input when metadata is unavailable, incomplete, or not enumerable.

#### Scenario: Metadata refresh populates source controls
- **WHEN** 用户刷新 Jira metadata and the current source mode is `Query Builder`
- **THEN** Scope Config SHALL render selectable source controls for discovered issue types、components、affected versions、fix versions、priorities 和 resolutions
- **AND** those controls SHALL show previously selected builder values as selected when the page or partial re-renders

#### Scenario: Manual fallback remains available
- **WHEN** Jira metadata does not include a value the operator needs
- **THEN** each metadata-backed source field SHALL still provide a manual fallback input for additional values
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

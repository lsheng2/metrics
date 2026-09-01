## ADDED Requirements

### Requirement: AI chart authoring is recipe-driven
AI dashboard composition SHALL derive supported chart authoring options from Metrics catalog and chart recipes instead of fixed demo literals.

#### Scenario: User asks for a supported chart recipe
- **WHEN** user asks for a chart whose requested chart id, series, profile and range can be matched to a Metrics catalog recipe
- **THEN** the workflow SHALL generate a render-config draft from that recipe and preserve the approved chart id, chart version, value fields, category field, evidence capability and provider binding

#### Scenario: User asks for unsupported recipe or series
- **WHEN** user asks for a chart id or series not listed in Metrics catalog
- **THEN** the workflow SHALL return `needs_metric_recipe` or structured validation findings
- **THEN** it SHALL NOT publish, synthesize or rename the unsupported semantic

#### Scenario: Multiple approved chart recipes exist
- **WHEN** the catalog contains multiple supported chart recipes for a selected profile
- **THEN** AI Base MAY choose among those recipes only by passing an explicit chart id and requested series to Metrics validation
- **THEN** Dashboard SHALL remain the authority that validates the final draft

### Requirement: Publish response includes recipe and provenance metadata
AI dashboard publish responses SHALL expose enough metadata for audit and history views.

#### Scenario: Publish succeeds
- **WHEN** a chart is published to Grafana
- **THEN** the response SHALL include chart id, chart version, provider id, profile id, requested series, range, render visualization, approval id, dry-run proof id, dashboard uid, Grafana URL and audit status

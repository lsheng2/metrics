## ADDED Requirements

### Requirement: AI-authored chart artifacts are workspace artifacts
AI dashboard composition SHALL treat AI-generated render config or Grafana JSON as versioned workspace artifacts before Dashboard validation or publication.

#### Scenario: AI creates a chart artifact from workspace context
- **WHEN** a user asks AI Base chat to create a chart from available Metrics data blocks
- **THEN** AI Base SHALL generate a workspace artifact containing chart intent, selected profile, range, canonical data fields, visualization choice and render config draft
- **THEN** the artifact SHALL have an artifact id, version, source workspace id and correlation id
- **THEN** AI SHALL NOT modify Dashboard application code, provider profile configuration, native provider query text or Metrics-owned chart recipe code

#### Scenario: AI artifact references unsupported semantics
- **WHEN** the artifact references a chart id, series, canonical field, transform or provider boundary that Metrics does not approve
- **THEN** Dashboard validation SHALL return structured findings or `needs_metric_recipe`
- **THEN** Dashboard SHALL NOT publish or import a Grafana dashboard

### Requirement: Dashboard validates AI workspace artifacts before publish
Dashboard SHALL accept AI-authored chart artifacts only through validation and precondition contracts that preserve Metrics ownership of data semantics.

#### Scenario: Artifact passes validation
- **WHEN** AI Base submits a workspace artifact for Dashboard validation
- **THEN** Dashboard SHALL validate profile boundary, chart recipe or data-block references, canonical fields, render shape, datasource allowlist, range, secret safety and provider-native literal bans
- **THEN** Dashboard SHALL return `draft_validated`, normalized render config preview, correlation id and next-action guidance

#### Scenario: Artifact fails validation
- **WHEN** the artifact violates Metrics validation policy
- **THEN** Dashboard SHALL return actionable findings with field paths and reasons
- **THEN** Dashboard SHALL keep precondition and publish states unavailable

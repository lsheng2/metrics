## MODIFIED Requirements

### Requirement: Render config publication is validated and auditable
System SHALL require validation, immutable artifact versioning, dry-run proof and approved publish authorization before generated Grafana artifacts are imported, published, or treated as approved dashboard definitions.

#### Scenario: Developer publishes dashboard config
- **WHEN** developer updates render config or generated dashboard JSON
- **THEN** validation SHALL verify chart recipes、allowed API surfaces、evidence links、category axes、daily metric ownership、secret safety and provider-native literal bans before publication

#### Scenario: AI-generated dashboard draft is submitted
- **WHEN** AI sidecar submits a render-config draft
- **THEN** system SHALL validate it using the same rules as developer-authored render config
- **THEN** system SHALL keep it unpublished until artifact validation, dry-run proof, human approval and publish authorization all match the same artifact version and content hash

### Requirement: AI-generated Grafana dashboards are listed and auditable
Dashboard SHALL track AI-generated Grafana dashboard publish artifacts so operators can inspect previous AI chart publications.

#### Scenario: Published AI dashboard is listed
- **WHEN** an AI-generated dashboard is published to Grafana
- **THEN** Dashboard SHALL record a publish artifact entry with dashboard uid, title, Grafana URL, profile id, provider id, chart id, range, requested series, actor, authorization id, approval id, dry-run proof id, artifact ref, artifact version, artifact hash, status and timestamps

#### Scenario: Operator views publish history
- **WHEN** an operator opens the AI publish history surface or calls its API
- **THEN** the system SHALL list recent AI-generated dashboard artifacts with enough metadata to distinguish Jira vs HSD-ES, profile, range, chart recipe and publish status

#### Scenario: Publish artifact is superseded
- **WHEN** a later publish overwrites or replaces the same demo dashboard uid
- **THEN** history SHALL retain previous audit metadata and mark the latest artifact clearly rather than silently losing prior publications

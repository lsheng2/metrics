## ADDED Requirements

### Requirement: AI-generated Grafana dashboards are listed and auditable
Dashboard SHALL track AI-generated Grafana dashboard publish artifacts so operators can inspect previous AI chart publications.

#### Scenario: Published AI dashboard is listed
- **WHEN** an AI-generated dashboard is published to Grafana
- **THEN** Dashboard SHALL record a publish artifact entry with dashboard uid, title, Grafana URL, profile id, provider id, chart id, range, requested series, actor, approval id, dry-run proof id, status and timestamps

#### Scenario: Operator views publish history
- **WHEN** an operator opens the AI publish history surface or calls its API
- **THEN** the system SHALL list recent AI-generated dashboard artifacts with enough metadata to distinguish Jira vs HSD-ES, profile, range, chart recipe and publish status

#### Scenario: Publish artifact is superseded
- **WHEN** a later publish overwrites or replaces the same demo dashboard uid
- **THEN** history SHALL retain previous audit metadata and mark the latest artifact clearly rather than silently losing prior publications

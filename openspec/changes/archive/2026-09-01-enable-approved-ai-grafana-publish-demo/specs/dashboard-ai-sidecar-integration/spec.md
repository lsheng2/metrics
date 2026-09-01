## ADDED Requirements

### Requirement: Approved AI chart publish demo creates a visible Grafana dashboard
Dashboard SHALL expose a local operator-approved publish step for AI-generated chart demos after dry-run proof is available.

#### Scenario: Approved publish imports a validated draft
- **WHEN** AI Base submits a publish request for `chiplet-2a-jira` with an approved `open_bug_trend` series, a dry-run proof id, and an explicit approval id
- **THEN** Dashboard SHALL regenerate and validate the Metrics-owned render config before import
- **THEN** Dashboard SHALL import the generated Grafana dashboard into the configured local Grafana instance
- **THEN** Dashboard SHALL return a visible Grafana URL for the imported dashboard
- **THEN** Dashboard SHALL record publication callback audit containing operation, actor, dashboard uid, correlation id and dry-run proof id

#### Scenario: Publish request lacks approval
- **WHEN** a publish request omits approval id or dry-run proof id
- **THEN** Dashboard SHALL reject the request before Grafana import
- **THEN** Dashboard SHALL NOT record a successful publication callback

#### Scenario: Publish request uses unsupported semantics
- **WHEN** a publish request asks for a series not approved by the Metrics chart recipe catalog
- **THEN** Dashboard SHALL return `needs_metric_recipe` or validation failure
- **THEN** Dashboard SHALL NOT import a Grafana dashboard

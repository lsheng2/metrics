## ADDED Requirements

### Requirement: AI composition publish envelope is Metrics-owned
Metrics SHALL own the envelope that converts a validated AI render draft into an imported Grafana dashboard.

#### Scenario: Publish envelope succeeds
- **WHEN** the workflow request validates, render config validation passes, gcx precondition passes, approval id is present and dry-run proof id is present
- **THEN** Metrics SHALL generate the Grafana dashboard from its render config generator
- **THEN** Metrics SHALL import only that generated dashboard to Grafana
- **THEN** the response SHALL include publication status, dashboard uid, dashboard URL, correlation id, dry-run proof id and audit status

#### Scenario: Publish envelope cannot reach Grafana
- **WHEN** Metrics validation passes but Grafana import fails or Grafana runtime is unavailable
- **THEN** Metrics SHALL return a structured error without hiding validation status
- **THEN** Metrics SHALL NOT report publication success

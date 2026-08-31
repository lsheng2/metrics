## ADDED Requirements

### Requirement: Dashboard exposes an operator-facing AI sidecar workflow
Metrics dashboard SHALL expose an operator-facing workflow that lets a user run the AI dashboard composition contract from a selected provider profile without requiring direct API calls.

#### Scenario: Sidecar workflow page opens
- **WHEN** a user opens the AI sidecar workflow surface
- **THEN** the system SHALL show AI sidecar readiness, configured AI Base profile, supported capabilities, selected provider profile, range, chart recipe, requested series, validation result, draft preview status and gcx precondition status

#### Scenario: Sidecar is unavailable
- **WHEN** AI Base is disabled, unavailable, identity-mismatched or missing required dashboard capabilities
- **THEN** the workflow SHALL still allow Metrics-local validation of catalog、intent、render config and gcx precondition, while clearly showing that external AI Base orchestration is not ready

### Requirement: Workflow validates supported and unsupported requests explicitly
Metrics dashboard SHALL provide deterministic try-run scenarios for supported and unsupported AI chart requests so operators can understand whether a request is ready to publish or requires Metrics-owned semantic work.

#### Scenario: Supported HSD-ES request produces draft
- **WHEN** the workflow validates profile `nvu-ttl-hsdes` for chart `open_bug_trend` with requested series `new_critical_high`
- **THEN** the result SHALL be `draft_validated` with a safe render config preview and SHALL NOT expose native HSD-ES query text, credentials or private paths

#### Scenario: Unsupported HSD-ES semantic is blocked
- **WHEN** the workflow validates profile `nvu-ttl-hsdes` for chart `open_bug_trend` with requested series `new_critical`
- **THEN** the result SHALL be `needs_metric_recipe`, SHALL preserve the exact requested series identity and SHALL NOT silently map it to `new_critical_high`

#### Scenario: Jira profile uses same workflow
- **WHEN** the workflow validates profile `chiplet-2a-jira` for chart `open_bug_trend` with requested series `new_critical_high`
- **THEN** the result SHALL use the same workflow envelope and validation statuses as HSD-ES without requiring provider-specific UI branches

### Requirement: gcx precondition is visible before any mutation
Metrics dashboard SHALL make the gcx mutation gate visible in the sidecar workflow before any Grafana import, push or publish action can be treated as executable.

#### Scenario: Draft passes precondition
- **WHEN** a validated draft render config is checked for `grafana_import`
- **THEN** the workflow SHALL show `precondition_passed`, mutation eligibility, approval policy and correlation metadata without performing a write mutation

#### Scenario: Draft fails precondition
- **WHEN** a draft render config fails Metrics validation
- **THEN** the workflow SHALL show `blocked`, structured findings and mutation disallowed before any gcx mutation command is run

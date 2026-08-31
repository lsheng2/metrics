## ADDED Requirements

### Requirement: AI Base prefers Dashboard workflow operation
AI Base Dashboard Query Agent SHALL use Dashboard `workflow.run` as the preferred end-to-end operation for chart try-runs when the connector contract exposes it.

#### Scenario: Workflow operation is available
- **WHEN** AI Base executes an open bug trend try-run and the Metrics connector exposes `workflow.run`
- **THEN** AI Base SHALL call `POST /api/ai-dashboard/workflow/` with profile id, dashboard uid, chart id, requested series, range and gcx operation, and SHALL display the returned intent/render/precondition states

#### Scenario: Workflow operation is unavailable
- **WHEN** AI Base runs against an older Dashboard connector contract without `workflow.run`
- **THEN** AI Base MAY fall back to catalog and intent validation operations without losing unsupported-series safety

### Requirement: Dashboard workflow page explains profile-driven Jira and HSD-ES paths
Dashboard AI workflow page SHALL make profile selection, provider identity, supported/unsupported status and next action visible for both Jira and HSD-ES profiles.

#### Scenario: Operator runs Jira workflow
- **WHEN** the operator selects `chiplet-2a-jira` and runs the workflow
- **THEN** the page SHALL show provider `jira`, validation status, render preview status, gcx precondition status and a next action without showing raw Jira credentials

#### Scenario: Operator runs unsupported series workflow
- **WHEN** the operator requests an unapproved series such as `new_critical`
- **THEN** the page SHALL show `needs_metric_recipe` and SHALL preserve the exact requested series

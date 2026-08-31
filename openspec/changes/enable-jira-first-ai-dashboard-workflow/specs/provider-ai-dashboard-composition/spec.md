## ADDED Requirements

### Requirement: Workflow result is the preferred AI composition envelope
Dashboard SHALL expose a single workflow result envelope that combines catalog/profile context, intent validation, render-config validation, gcx precondition, correlation id and next-action guidance for AI dashboard composition.

#### Scenario: Supported Jira chart request
- **WHEN** AI requests `open_bug_trend` for `chiplet-2a-jira` with approved series
- **THEN** the workflow result SHALL include `draft_validated`, render validation, gcx precondition result and Jira provider/profile provenance in one response

#### Scenario: Supported HSD-ES chart request
- **WHEN** AI requests `open_bug_trend` for `nvu-ttl-hsdes` with approved series
- **THEN** the workflow result SHALL include the same envelope shape as Jira with HSD-ES profile/provider provenance

#### Scenario: Unsupported semantic request
- **WHEN** AI requests a series not approved by the Metrics chart recipe
- **THEN** the workflow result SHALL return `needs_metric_recipe`, SHALL keep render/precondition as `not_checked`, and SHALL NOT fabricate a valid draft

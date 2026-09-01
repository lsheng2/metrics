## ADDED Requirements

### Requirement: AI Base chat can trigger Dashboard chart workflow demo
AI Base Dashboard Query Agent SHALL provide a deterministic chat path that can trigger a supported Dashboard chart workflow and return dry-run proof guidance.

#### Scenario: User asks for an approved Jira chart in chat
- **WHEN** a user asks AI Base Chat to create a weekly open bug trend chart for Jira `chiplet-2a-jira` from `26WW32` to `26WW35` with `new_critical_high`
- **THEN** AI Base SHALL call the Metrics connector workflow, return the validation and precondition states, include dry-run proof id when available, and state that human approval is required before Grafana mutation

#### Scenario: User asks for unsupported chart semantics in chat
- **WHEN** a user asks AI Base Chat for a series not approved by Metrics
- **THEN** AI Base SHALL return the `needs_metric_recipe` state and SHALL NOT create a dry-run proof

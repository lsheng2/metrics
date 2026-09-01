## ADDED Requirements

### Requirement: Jira-first AI publish flow uses formal approval state
Dashboard SHALL use a persisted or otherwise queryable approval state for AI Grafana publish requests instead of treating local approval text as the only approval boundary.

#### Scenario: Publish request is created
- **WHEN** AI Base submits a valid Jira-first chart publish request after dry-run proof
- **THEN** Dashboard SHALL create or reference an approval record containing profile id, chart id, requested series, range, dry-run proof id, actor, status and correlation id
- **THEN** the initial state SHALL be visible as `pending_approval` unless the request is explicitly local-demo auto-approved by policy

#### Scenario: Publish request is approved
- **WHEN** an approval record is approved for the same profile, chart, series, range and dry-run proof
- **THEN** Dashboard SHALL allow Grafana publish and record transition to `published` after successful import

#### Scenario: Publish request is rejected or mismatched
- **WHEN** approval is rejected, missing, expired, or mismatched with the dry-run proof or publish request
- **THEN** Dashboard SHALL block Grafana import and SHALL return a structured approval error

### Requirement: Jira-first publish is validated end to end from AI Base Chat
The E2E demo SHALL support the Jira-first prompt after Jira data readiness is established.

#### Scenario: Jira Chat publish succeeds
- **WHEN** the user asks AI Base Chat to approve and publish `open_bug_trend` for `chiplet-2a-jira` from `26WW32` to `26WW35` with `new_critical_high`
- **THEN** the system SHALL verify Jira readiness, create dry-run proof, require or resolve approval, publish to Grafana, return a Grafana URL, and render a nonblank chart

#### Scenario: Jira Chat publish is not data-ready
- **WHEN** the same request is made before Jira aggregate coverage exists
- **THEN** Chat SHALL explain the readiness blocker and sync action instead of returning a Grafana URL with `No data`

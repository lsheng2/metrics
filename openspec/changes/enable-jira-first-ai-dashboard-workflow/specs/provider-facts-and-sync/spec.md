## ADDED Requirements

### Requirement: Jira provider profiles can be synced by profile id
Generic provider-profile sync SHALL support Jira profiles by resolving the selected Project Provider Profile to its mapped durable Jira scope and running the existing Jira read-only sync/materialization workflow.

#### Scenario: Jira profile sync succeeds
- **WHEN** an operator runs provider profile sync for `chiplet-2a-jira` with a WW/date coverage range
- **THEN** the system SHALL resolve the Jira profile, find the matching enabled Jira scope, fetch Jira issues through the existing read-only Jira sync adapter, persist durable Jira history, recalculate the selected coverage, update sync health, and return a JSON result with provider id, profile id, scope id, status and coverage

#### Scenario: Jira profile has no mapped scope
- **WHEN** an operator runs provider profile sync for a Jira profile without a matching enabled Jira scope
- **THEN** the system SHALL return `configuration_required` or `unavailable` with a clear blocker and SHALL NOT silently fall back to another profile or provider

#### Scenario: Non-Jira provider remains adapter-dispatched
- **WHEN** generic provider-profile sync is run for HSD-ES or future providers
- **THEN** the system SHALL dispatch to the provider-specific adapter for that profile and SHALL preserve existing HSD-ES live-sync gating behavior

### Requirement: Jira profile sync enables Jira-first Grafana and AI validation
After a successful Jira profile sync, Grafana and AI workflow consumers SHALL be able to read supported Jira chart aggregates by profile id without raw Jira JQL or provider-native field logic in the UI.

#### Scenario: Jira aggregate is requested after profile sync
- **WHEN** Grafana or AI requests `open_bug_trend` for `chiplet-2a-jira` and the synced coverage contains a matching calculation run
- **THEN** the response SHALL be `supported`, SHALL include Jira provider/profile/source/calculation provenance, and SHALL expose provider-neutral rows only

#### Scenario: Jira aggregate is requested before profile sync
- **WHEN** Grafana or AI requests a Jira profile/range without a matching durable calculation run
- **THEN** the response SHALL remain `unavailable` or `stale` with a clear reason and SHALL NOT live-query Jira during dashboard render

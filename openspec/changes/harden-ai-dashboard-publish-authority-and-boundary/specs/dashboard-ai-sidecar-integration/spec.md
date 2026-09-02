## MODIFIED Requirements

### Requirement: AI Grafana workflow records dry-run proof before mutation
AI Base Dashboard Query Agent SHALL create or surface a durable dry-run proof before any Grafana import, publish or push mutation is considered eligible.

#### Scenario: Workflow reaches dry-run state
- **WHEN** Dashboard `workflow.run` returns `ready_for_dry_run`
- **THEN** AI Base SHALL run or simulate the configured gcx dry-run path through the governed CLI runner
- **THEN** AI Base SHALL record a dry-run proof bound to artifact ref, artifact version, artifact hash, workspace key, profile id, dashboard uid, chart id, requested series, range, operation and executable/env fingerprints
- **THEN** AI Base SHALL show the proof status to the operator

#### Scenario: Workflow does not reach dry-run state
- **WHEN** Dashboard `workflow.run` returns `needs_metric_recipe`, `blocked`, validation failed, or precondition not checked
- **THEN** AI Base SHALL NOT create a dry-run proof and SHALL surface the blocking status instead

### Requirement: Human approval is required after dry-run proof
AI Base SHALL NOT execute Grafana mutation after dry-run proof unless explicit human approval is attached to the same immutable artifact/proof scope.

#### Scenario: Dry-run proof exists without approval
- **WHEN** a valid dry-run proof exists but no matching approved authorization exists
- **THEN** UI SHALL show approval required and mutation SHALL remain unavailable

#### Scenario: Mutation is requested without matching proof
- **WHEN** a mutation request lacks a matching proof, matching artifact version/hash, matching workspace boundary or approved authorization
- **THEN** AI Base SHALL block mutation before running gcx and SHALL NOT call Dashboard publication callback

### Requirement: AI Base calls Metrics contracts before generating outputs
AI Base SHALL use Metrics-provided catalog、intent validation、draft render validation、evidence and precondition APIs before returning chart or dashboard operation outputs.

#### Scenario: Metrics connector routes are published
- **WHEN** AI Base profile `dashboard_query_agent` is configured with the Metrics connector
- **THEN** it SHALL call Dashboard-owned HTTP contracts:
  - `GET /api/ai-dashboard/catalog/`
  - `POST /api/ai-dashboard/intent/validate/`
  - `POST /api/ai-dashboard/render-config/validate/`
  - `POST /api/ai-dashboard/gcx/precondition/`
  - `POST /api/ai-dashboard/gcx/publication-callback/`
  - `GET /api/ai-dashboard/context/`
- **AND** Dashboard SHALL keep these routes provider/profile neutral and backed by Metrics-owned profile registry、chart recipes、Grafana render config validator、provider facts and aggregate artifacts

#### Scenario: AI creates a chart draft
- **WHEN** user requests a chart change
- **THEN** AI Base SHALL call Metrics catalog/intent validation and SHALL return either a validated draft render config, structured validation findings, or `needs_metric_recipe`

#### Scenario: User requests unsupported semantics
- **WHEN** user asks for a series such as `new_critical` but Metrics only approves `new_critical_high`
- **THEN** AI Base SHALL preserve the exact series identity, return `needs_metric_recipe`, and SHALL NOT rename, filter, relabel or synthesize unsupported Metrics semantics

#### Scenario: Model-visible connector route is invoked
- **WHEN** AI Base exposes Metrics connector tools to the model
- **THEN** only read/validate operations with explicit safe policy SHALL be model-visible
- **THEN** AI Base SHALL enforce the active workspace boundary before invoking those operations

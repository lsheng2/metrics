## ADDED Requirements

### Requirement: AI Grafana workflow records dry-run proof before mutation
AI Base Dashboard Query Agent SHALL create or surface a durable dry-run proof before any Grafana import, publish or push mutation is considered eligible.

#### Scenario: Workflow reaches dry-run state
- **WHEN** Dashboard `workflow.run` returns `ready_for_dry_run`
- **THEN** AI Base SHALL run or simulate the configured gcx dry-run path through the governed CLI runner, record a `dry_run_proof_id`, and show the proof status to the operator

#### Scenario: Workflow does not reach dry-run state
- **WHEN** Dashboard `workflow.run` returns `needs_metric_recipe`, `blocked`, validation failed, or precondition not checked
- **THEN** AI Base SHALL NOT create a dry-run proof and SHALL surface the blocking status instead

### Requirement: Human approval is required after dry-run proof
AI Base SHALL NOT execute Grafana mutation after dry-run proof unless an explicit human approval id is attached to the mutation request and the proof still matches.

#### Scenario: Dry-run proof exists without approval
- **WHEN** a valid dry-run proof exists but no approval id exists
- **THEN** UI SHALL show approval required and mutation SHALL remain unavailable

#### Scenario: Mutation is requested without matching proof
- **WHEN** a mutation request lacks a matching dry-run proof, matching scope, or matching artifact reference
- **THEN** AI Base SHALL block mutation before running gcx and SHALL NOT call Dashboard publication callback

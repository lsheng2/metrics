## ADDED Requirements

### Requirement: Workflow envelope supports dry-run proof handoff
Dashboard AI composition workflow SHALL expose enough status, correlation and artifact guidance for AI Base to create a dry-run proof while keeping mutation approval external to composition validation.

#### Scenario: Valid workflow result is used for dry-run
- **WHEN** Dashboard returns `ready_for_dry_run`
- **THEN** the result SHALL include correlation id, selected profile/range/chart, render validation result and gcx precondition result sufficient for AI Base dry-run proof correlation

#### Scenario: Dry-run proof is produced
- **WHEN** AI Base produces a dry-run proof for a Dashboard-generated artifact
- **THEN** downstream UI SHALL distinguish `dry_run_proof_id` from final publication callback or mutation status

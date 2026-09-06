## ADDED Requirements

### Requirement: Data Health exposes explicit-only scope binding readiness
Data Health SHALL show whether the current scope binding inventory is ready for explicit-only runtime policy, separate from the current compatibility-allowed health summary.

#### Scenario: Operator views explicit-only gate
- **WHEN** operator opens Data Health
- **THEN** page SHALL show an explicit-only readiness state
- **AND** it SHALL show impacted scope count and repair guidance when not ready

#### Scenario: Operator views impacted scopes
- **WHEN** explicit-only readiness is blocked
- **THEN** Data Health SHALL list impacted scopes with status, profile, provider, provenance and blockers
- **AND** each impacted row SHALL provide a repair link to Scope Library

#### Scenario: Current runtime remains compatibility-allowed
- **WHEN** compatibility runtime is still allowed
- **THEN** Data Health SHALL distinguish current runtime health from explicit-only readiness
- **AND** compatibility bindings SHALL be warning-level until policy changes

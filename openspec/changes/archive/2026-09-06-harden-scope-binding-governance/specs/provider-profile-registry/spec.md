## ADDED Requirements

### Requirement: Scope binding governance supports bulk confirmation
Provider profile registry boundary SHALL allow operators to promote multiple safely resolved compatibility scope bindings to explicit bindings in one operation, without changing scope semantic configs or provider profile registry records.

#### Scenario: Bulk confirm compatibility bindings
- **WHEN** operator requests bulk confirmation for compatibility bindings that have resolved profile and provider values
- **THEN** system SHALL promote only eligible compatibility bindings to explicit
- **AND** system SHALL preserve each binding's resolved profile id and provider id
- **AND** system SHALL return counts and skipped reasons for ineligible scopes

#### Scenario: Bulk confirmation skips unsafe bindings
- **WHEN** a selected or discovered scope binding is configuration_required, ambiguous, disabled, missing profile, or missing provider
- **THEN** system SHALL skip that binding with an actionable reason
- **AND** system SHALL NOT fabricate profile/provider values or reuse stale request parameters

### Requirement: Scope binding governance exposes explicit-only readiness
Provider profile registry boundary SHALL expose a readiness projection that shows whether every enabled scope participating in provider-backed flows has an explicit binding, so operators can assess a future explicit-only runtime policy before enabling it.

#### Scenario: Explicit-only readiness is ready
- **WHEN** all enabled provider-backed scopes have explicit bindings
- **THEN** health projection SHALL report explicit-only ready
- **AND** it SHALL show zero impacted scopes

#### Scenario: Explicit-only readiness is blocked
- **WHEN** one or more enabled provider-backed scopes still use compatibility, configuration_required, ambiguous, or disabled bindings
- **THEN** health projection SHALL report explicit-only blocked
- **AND** it SHALL list impacted scopes with status, profile, provider, provenance and repair action context

### Requirement: Scope binding operations are audited
Provider profile registry boundary SHALL write an audit event for each scope binding mutation that can change runtime provider/profile behavior.

#### Scenario: Operator confirms one binding
- **WHEN** operator confirms a compatibility binding
- **THEN** system SHALL write an audit event containing scope id, operation type, actor, old status/profile/provider, new status/profile/provider, provenance and timestamp

#### Scenario: Operator saves an explicit binding
- **WHEN** operator changes or creates an explicit binding from Scope Library
- **THEN** system SHALL write an audit event containing the old binding snapshot and the new binding snapshot
- **AND** the audit event SHALL distinguish manual repair from compatibility confirmation

#### Scenario: Operator bulk confirms bindings
- **WHEN** operator bulk confirms compatibility bindings
- **THEN** system SHALL write auditable mutation events for the changed bindings
- **AND** system SHALL expose the bulk operation summary with changed and skipped counts

# provider-profile-registry Specification Delta

## ADDED Requirements

### Requirement: Scope provider bindings are auditable and confirmable
Scope provider bindings SHALL expose enough metadata for UI and diagnostics to distinguish explicit operator-approved bindings from compatibility bindings produced during migration.

#### Scenario: Binding metadata is listed
- **WHEN** Dashboard UI lists saved scopes
- **THEN** the provider profile registry boundary SHALL expose binding status, profile id, provider id, provenance and blockers for each scope

#### Scenario: Compatibility binding is confirmed
- **WHEN** an operator confirms a compatibility binding
- **THEN** the system SHALL change the binding status to `explicit`
- **AND** it SHALL record confirmation provenance without changing the scope semantic config or provider profile registry record

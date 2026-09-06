# provider-profile-registry Specification Delta

## ADDED Requirements

### Requirement: Scope binding operations support explicit repair and policy visibility
Provider profile registry boundary SHALL expose operations and projections needed to repair scope bindings and communicate compatibility policy.

#### Scenario: Explicit binding is saved from UI
- **WHEN** Dashboard UI submits a scope id and provider profile id
- **THEN** the registry boundary SHALL validate the provider profile exists and is enabled
- **AND** it SHALL save an explicit binding with resolved provider id and provenance
- **AND** it SHALL reject unknown or disabled provider profiles without changing the prior binding

#### Scenario: Runtime compatibility remains allowed
- **WHEN** a scope uses compatibility binding during the migration period
- **THEN** registry health projection SHALL mark the binding as compatibility and include provenance
- **AND** UI SHALL communicate that explicit confirmation is recommended

#### Scenario: Explicit-only mode is introduced later
- **WHEN** a future deployment disables compatibility runtime
- **THEN** compatibility bindings SHALL be treated as configuration_required until confirmed or rebound
- **AND** existing health projection SHALL make the impact visible before the policy switch

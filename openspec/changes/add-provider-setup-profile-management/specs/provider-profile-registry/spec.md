## ADDED Requirements

### Requirement: Registry supports managed provider profile lifecycle
Provider Profile Registry SHALL support managed profile lifecycle states for UI-created profiles while preserving stable profile resolution for existing consumers.

#### Scenario: Managed profile is resolved
- **WHEN** Dashboard、sync、aggregate、Grafana 或 AI consumer requests an enabled managed `profile_id`
- **THEN** registry SHALL return the same provider-neutral profile contract as for bundled profiles
- **AND** response SHALL include lifecycle state、mapping/source version fingerprints and provenance

#### Scenario: Archived profile is requested
- **WHEN** consumer requests an archived provider profile
- **THEN** registry SHALL return unavailable/configuration_required state with blockers
- **AND** consumer SHALL NOT silently fall back to another profile or provider

#### Scenario: Profile id remains stable
- **WHEN** 用户 edits display name、scope labels、source population or mappings
- **THEN** registry SHALL keep profile id stable unless the user explicitly duplicates or imports as a new profile
- **AND** all downstream audit/readiness records SHALL retain enough provenance to compare old and new profile versions

### Requirement: Profile packages are portable and non-secret
Provider Profile Registry SHALL export and import versioned profile packages that are portable across environments and safe to review in source control or support tickets.

#### Scenario: Profile package is exported
- **WHEN** 用户 exports a provider profile
- **THEN** package SHALL include format、version、provider id、profile id、display name、source population、scope labels、field bindings、value mappings、chart bindings、sync policy、readiness policy and mapping/source fingerprints
- **AND** package SHALL exclude credentials、tokens、raw issue/article payloads、sync cursors、calculation runs、AI workspace artifacts and user secrets

#### Scenario: Profile package is imported
- **WHEN** 用户 imports a provider profile package
- **THEN** registry SHALL validate format version、provider template compatibility、required non-secret fields and profile id conflict policy
- **AND** imported profile SHALL start archived or draft
- **AND** import SHALL record provenance without marking data freshness as current

### Requirement: Managed profile mutations are audited
Provider Profile Registry SHALL write auditable events for mutations that can change provider/profile behavior.

#### Scenario: Profile is created or edited
- **WHEN** 用户 creates or edits a provider profile
- **THEN** system SHALL record actor、operation、profile id、provider id、before/after lifecycle state、mapping/source version fingerprints and validation outcome

#### Scenario: Profile lifecycle changes
- **WHEN** 用户 archives、restores、duplicates、imports、exports or deletes a profile
- **THEN** system SHALL record the operation and impact summary
- **AND** destructive operations SHALL record confirmation evidence

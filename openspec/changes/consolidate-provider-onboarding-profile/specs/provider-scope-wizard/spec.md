## MODIFIED Requirements

### Requirement: Scope Config consumes Provider Setup handoff
Scope Config SHALL treat Provider Profile as provider onboarding/connection authority and Scope Config as the concrete project/range/source authority.

#### Scenario: User creates a scope from provider profile
- **WHEN** Provider Setup launches Scope Config with a provider profile
- **THEN** Scope Config SHALL preselect the provider profile
- **AND** Scope Config SHALL keep Jira JQL or HSD-ES saved query as the scope-owned source input
- **AND** Scope Config SHALL NOT require users to edit provider credentials or onboarding details

#### Scenario: Scope references a provider profile
- **WHEN** a scope is saved with provider/profile selection
- **THEN** the scope-provider binding SHALL point to the provider onboarding profile
- **AND** source/range values SHALL remain owned by the scope editor or compatibility source fields

#### Scenario: Draft scope shows selected provider binding
- **WHEN** a user saves a draft scope from a selected provider profile
- **THEN** the saved scope editor SHALL still show the selected provider profile identity
- **AND** the binding SHALL remain visible even though the scope runtime status is disabled until the scope is enabled

#### Scenario: Scope Library lists scopes only
- **WHEN** a provider profile exists but is not referenced by any saved scope
- **THEN** Scope Library SHALL NOT append a standalone provider profile row for it
- **AND** Scope Library SHALL continue to show the provider profile as an available binding choice when a saved scope can be bound
- **AND** Provider Setup SHALL remain the profile inventory and management surface

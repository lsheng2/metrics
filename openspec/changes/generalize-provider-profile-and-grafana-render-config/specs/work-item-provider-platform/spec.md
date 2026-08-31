## ADDED Requirements

### Requirement: Provider platform consumes profile registry
Provider platform SHALL expose provider capabilities through Project Provider Profiles so dashboard、sync、Grafana and AI consumers can resolve provider/project behavior without hardcoded first-profile logic.

#### Scenario: Provider capability is requested through profile
- **WHEN** consumer requests capabilities for a `profile_id`
- **THEN** platform SHALL resolve the profile to provider adapter、source population、capability manifest、field binding coverage、chart support and unsupported/deferred reasons

#### Scenario: Provider adapter is added later
- **WHEN** a future provider such as GitHub、Azure DevOps or another HSD-ES project is added
- **THEN** platform SHALL add provider/profile registry entries and adapter bindings without creating a parallel dashboard product module for that provider

### Requirement: Provider-specific implementation remains behind adapter boundaries
Provider platform SHALL keep native API mechanics、credentials、query syntax、pagination、field expansion and error normalization inside provider-specific adapters, while shared products consume canonical profile/fact/chart contracts.

#### Scenario: Jira and HSD-ES source populations differ
- **WHEN** Jira uses Metrics-managed JQL and HSD-ES uses provider-owned saved query
- **THEN** both SHALL appear to dashboard/Grafana/AI as source population metadata from the selected profile, and consumers SHALL NOT branch on JQL versus HSD-ES query id

#### Scenario: Provider API behavior is uncertain
- **WHEN** implementation needs provider-specific auth、endpoint shape、pagination、field semantics or permission behavior
- **THEN** provider adapter work SHALL verify the authoritative Jira or HSD-ES documentation before changing code or claiming support

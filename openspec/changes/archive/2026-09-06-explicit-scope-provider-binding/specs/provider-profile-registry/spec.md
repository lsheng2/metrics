# provider-profile-registry Specification Delta

## ADDED Requirements

### Requirement: Dashboard scopes bind to provider profiles through explicit registry-backed bindings
Dashboard saved scopes SHALL NOT infer provider/profile identity from mutable display text or stale browser query parameters. The platform SHALL expose a scope binding contract that maps each enabled Dashboard scope to one canonical provider profile when that scope participates in provider-backed Workbench, Grafana, evidence or AI flows.

#### Scenario: Scope has an explicit provider profile binding
- **WHEN** Workbench, Grafana selection handling, AI context creation, sync diagnostics or evidence APIs load a Dashboard scope
- **THEN** the platform SHALL resolve `scope_id` to a canonical binding containing `scope_id`, `profile_id`, `provider_id`, source population provenance, binding status and optional blockers
- **AND** consumers SHALL treat `profile_id` and `provider_id` as resolver outputs rather than independent user-editable inputs

#### Scenario: Scope has only legacy metadata
- **WHEN** a legacy Jira scope has no explicit provider profile binding
- **THEN** the resolver MAY produce a compatibility binding from registry source population, exact profile id, source query hash, or provider-specific saved-query evidence
- **AND** the compatibility binding SHALL mark its status/provenance so product code can migrate it to an explicit binding
- **AND** compatibility binding SHALL NOT silently select an unrelated profile when multiple candidate profiles match

#### Scenario: Scope binding cannot be resolved safely
- **WHEN** no explicit binding exists and compatibility matching is missing, ambiguous, disabled or contradictory
- **THEN** provider-backed consumers SHALL show `configuration_required` with an action to bind the scope to a provider profile
- **AND** they SHALL NOT reuse stale `profile_id` or `provider_id` values from URL, form controls, local storage or AI host actions

#### Scenario: Scope display label changes
- **WHEN** a user renames a saved scope or changes its display labels such as IP, project or milestone
- **THEN** the provider profile binding SHALL remain stable by explicit binding id or canonical profile id
- **AND** Workbench, Grafana, evidence and AI context SHALL continue to use the same resolved provider/profile unless the binding itself is changed through an approved configuration path

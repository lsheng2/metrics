## ADDED Requirements

### Requirement: Scope binding runtime policy is enforceable
Provider profile registry boundary SHALL support a runtime policy that controls whether compatibility bindings are accepted by provider-backed consumers.

#### Scenario: Compatibility policy allows migration behavior
- **WHEN** runtime policy is `compatibility_allowed`
- **THEN** resolver SHALL continue returning safe compatibility bindings as resolved
- **AND** health projection SHALL show compatibility bindings as warning-level migration risk

#### Scenario: Explicit-only policy rejects compatibility bindings
- **WHEN** runtime policy is `explicit_only`
- **AND** a scope has only a compatibility binding
- **THEN** resolver SHALL return configuration_required for provider-backed consumption
- **AND** it SHALL include a blocker explaining that explicit confirmation is required
- **AND** it SHALL NOT reuse the compatibility profile/provider as runtime authority

#### Scenario: Explicit binding remains accepted in explicit-only mode
- **WHEN** runtime policy is `explicit_only`
- **AND** a scope has an explicit binding with valid profile and provider
- **THEN** resolver SHALL return the explicit profile/provider as resolved

### Requirement: Scope binding audit history is queryable
Provider profile registry boundary SHALL expose recent scope binding audit events so operators can inspect binding mutations without reading raw database rows.

#### Scenario: Operator queries binding audit history
- **WHEN** binding audit history is requested
- **THEN** system SHALL return recent binding mutation events with event type, actor, scope, old status/profile/provider, new status/profile/provider and timestamp

#### Scenario: Audit history contains non-binding events
- **WHEN** audit table contains evidence export, chart publish, or other non-binding events
- **THEN** binding audit history SHALL exclude those events

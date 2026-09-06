## ADDED Requirements

### Requirement: Dashboard UI exposes scope binding policy and audit history
Dashboard UI SHALL make current scope binding runtime policy and recent binding changes visible to operators from the existing admin-style Dashboard surfaces.

#### Scenario: Operator views current binding policy
- **WHEN** operator opens Scope Library or Data Health
- **THEN** page SHALL show the current scope binding policy
- **AND** it SHALL distinguish compatibility-allowed runtime from explicit-only runtime

#### Scenario: Operator views binding audit history
- **WHEN** operator opens Scope Library or Data Health
- **THEN** page SHALL show recent scope binding audit events
- **AND** each event SHALL show actor, operation, scope and old/new binding state

#### Scenario: No audit events exist yet
- **WHEN** no binding audit events exist
- **THEN** page SHALL render an empty state instead of hiding the audit section

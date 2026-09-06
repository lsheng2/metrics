# provider-scope-wizard Specification Delta

## ADDED Requirements

### Requirement: Scope Library exposes provider binding management
Scope Library SHALL show each saved scope's provider binding status so operators can tell whether Workbench/Grafana/AI will use an explicit profile binding, a compatibility binding, or a configuration-required state.

#### Scenario: Operator views scope bindings
- **WHEN** operator opens Scope Library
- **THEN** each scope row SHALL show binding status, resolved profile id, resolved provider id, provenance summary and blockers when present
- **AND** compatibility bindings SHALL be visually distinct from explicit bindings

#### Scenario: Operator confirms compatibility binding
- **WHEN** a scope has a compatibility binding with resolved profile/provider
- **THEN** Scope Library SHALL offer a confirmation action that promotes the binding to explicit
- **AND** the action SHALL preserve profile/provider values and record confirmation provenance

#### Scenario: Scope binding needs configuration
- **WHEN** a scope binding is missing, ambiguous or disabled
- **THEN** Scope Library SHALL display an actionable configuration-required state rather than hiding the scope or silently reusing stale profile/provider values

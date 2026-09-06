## ADDED Requirements

### Requirement: Scope Library supports bulk binding operations
Scope Library SHALL provide a bulk confirmation operation for compatibility bindings so operators can finish migration without editing each row individually.

#### Scenario: Operator confirms all compatible bindings
- **WHEN** Scope Library contains one or more compatibility bindings with resolved profile/provider values
- **THEN** UI SHALL offer a bulk confirmation action
- **AND** submitting it SHALL promote eligible compatibility bindings to explicit
- **AND** UI SHALL show how many bindings changed and how many were skipped

#### Scenario: Bulk operation has no eligible rows
- **WHEN** Scope Library has no eligible compatibility bindings
- **THEN** UI SHALL disable or hide the destructive-looking bulk action
- **AND** it SHALL still show repair actions for unresolved rows

### Requirement: Scope Library binding controls remain high density
Scope Library SHALL present binding status, profile/provider, provenance and actions in compact row controls that preserve scan density for large scope sets.

#### Scenario: Operator scans many scopes
- **WHEN** Scope Library renders binding rows
- **THEN** binding status, provider/profile, provenance and primary actions SHALL fit in a compact row layout
- **AND** secondary actions MAY move behind compact controls or help affordances
- **AND** row height SHALL NOT grow only to explain policy text that can be shown in tooltip/help or Data Health

#### Scenario: Operator repairs one binding
- **WHEN** a row needs configuration or the operator chooses a different provider profile
- **THEN** the provider profile selector and save action SHALL remain available inline
- **AND** the compact layout SHALL preserve Edit, Duplicate and Disable actions

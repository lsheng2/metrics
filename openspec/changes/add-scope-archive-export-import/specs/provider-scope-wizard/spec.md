## ADDED Requirements

### Requirement: Scope Library archives saved scopes before deletion
Scope Library SHALL expose Archive as the primary removal action for saved scopes. Archive SHALL remove a scope from normal Dashboard, Workbench and AI Assistant scope selection while preserving historical calculations, evidence, sync state and audit records.

#### Scenario: Operator archives an enabled saved scope
- **WHEN** an operator archives an enabled saved scope from Scope Library
- **THEN** the scope SHALL no longer appear in normal dashboard scope selectors
- **AND** historical calculation runs, bucket evidence, provider binding, source history and audit records SHALL remain persisted
- **AND** Scope Library SHALL continue to list the archived scope with an archived/draft status

#### Scenario: Archive action warns about selection impact
- **WHEN** Scope Library renders the archive action for a saved scope
- **THEN** the UI SHALL warn that Dashboard, Workbench and AI Assistant normal scope selection will no longer include that scope
- **AND** the UI SHALL state that historical records are preserved

### Requirement: Scope Library exports portable scope configuration
Scope Library SHALL allow operators to export a saved scope as a JSON package containing semantic scope configuration and binding metadata needed to recreate the scope in another environment.

#### Scenario: Operator exports a saved scope
- **WHEN** an operator exports a saved scope
- **THEN** the response SHALL be a JSON file containing package metadata, semantic scope config fields and provider binding metadata
- **AND** the response SHALL NOT include calculation runs, bucket memberships, Jira issue payloads, Jira snapshots, sync cursor state or audit event history

### Requirement: Scope Library imports scopes safely
Scope Library SHALL allow operators to import a JSON scope package into a new saved scope without overwriting an existing scope by default.

#### Scenario: Operator imports a scope package
- **WHEN** an operator imports a valid scope package
- **THEN** the system SHALL create a new saved scope as archived/draft by default
- **AND** name collisions SHALL be resolved by assigning a distinct imported-copy name
- **AND** imported provider binding metadata SHALL be restored only as editable explicit binding metadata when a provider profile id is present

#### Scenario: Operator imports malformed package
- **WHEN** an operator imports malformed JSON or a package without scope config
- **THEN** Scope Library SHALL reject the import with an operator-visible error
- **AND** no scope SHALL be created

### Requirement: Hard delete is protected and limited to archived scopes
Scope Library SHALL support physical deletion only for archived saved scopes and only after explicit operator confirmation.

#### Scenario: Operator attempts to delete enabled scope
- **WHEN** an operator requests hard delete for an enabled scope
- **THEN** the system SHALL reject the request
- **AND** the scope and all associated records SHALL remain unchanged

#### Scenario: Operator deletes archived scope after confirmation
- **WHEN** an operator requests hard delete for an archived scope and provides the required confirmation token
- **THEN** the system MAY physically delete the saved scope
- **AND** the UI SHALL warn that related historical calculations, bucket evidence, source history, sync cursor, provider binding and audit records may be removed by cascade

#### Scenario: Operator opens destructive action without confirmation
- **WHEN** an operator has not provided the required confirmation token
- **THEN** Scope Library SHALL NOT perform hard delete
- **AND** the UI SHALL keep the safer Archive action available

### Requirement: Scope lifecycle validates readiness before deployment
Scope Library SHALL distinguish saved configuration validity from deployment readiness. A scope SHALL NOT enter normal Metrics Dashboard, Workbench or AI Assistant scope selection unless required configuration fields pass validation.

#### Scenario: Operator saves invalid scope
- **WHEN** an operator saves a scope without required identity, query, type, status, severity or bucket configuration
- **THEN** the system SHALL reject the save or deployment with field-level validation errors
- **AND** no calculation, sync, Workbench or AI workflow SHALL treat that scope as ready

#### Scenario: Operator deploys valid scope
- **WHEN** an operator saves and enables a scope whose required fields pass validation
- **THEN** the scope SHALL become eligible for Dashboard selector use
- **AND** downstream readiness SHALL still depend on provider binding, sync/cache freshness and calculation freshness

#### Scenario: User views readiness matrix
- **WHEN** Scope Library or Data Health reports scope readiness
- **THEN** the system SHALL distinguish at least config validity, Dashboard selection eligibility, provider binding readiness, sync/cache readiness, calculation freshness, Workbench evidence readiness and AI/Grafana readiness
- **AND** missing optional fields SHALL reduce only the capabilities that depend on those fields rather than blocking every workflow

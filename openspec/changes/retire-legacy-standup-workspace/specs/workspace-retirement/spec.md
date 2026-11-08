## ADDED Requirements

### Requirement: Preserve A Retired Workspace Completely

The retirement process SHALL preserve all ordinary source files, including Git
objects/refs/index, dirty, untracked, ignored, binary and credential files, in
an independently verified private local archive outside code repositories.

#### Scenario: Unpublished and ignored material exists

- **WHEN** the source includes unpublished commits, working edits and ignored data
- **THEN** the snapshot SHALL retain each ordinary file with identical bytes
- **AND** a self-contained Git bundle SHALL retain all reachable refs
- **AND** deletion readiness SHALL require successful source and recovery checks

#### Scenario: Source or archive changes during validation

- **WHEN** a source/manifest/payload/bundle mismatch or I/O failure is observed
- **THEN** validation SHALL fail without advancing readiness
- **AND** the original source and failed evidence SHALL remain available

### Requirement: Respect Filesystem And Credential Boundaries

The tool SHALL refuse unsafe or overlapping roots and SHALL NOT follow reparse
points, export credentials, inspect free disk space or delete the source.

#### Scenario: A link points outside the source

- **WHEN** a source junction or symbolic link targets shared or unrelated data
- **THEN** the link metadata SHALL be retained without following the target
- **AND** no live old-root link SHALL be introduced into the archive

#### Scenario: A target already exists or belongs to a code repository

- **WHEN** Capture receives an existing, overlapping, relative or Git-contained target
- **THEN** it SHALL refuse without overwriting source or target content

#### Scenario: Sensitive local files are preserved

- **WHEN** raw data or a secret is copied
- **THEN** its archive SHALL be readable only by the current Windows user and SYSTEM
- **AND** command output and code-repository receipts SHALL contain no secret values

### Requirement: Separate Retirement From Product Feature Completion

Dashboard SHALL use relocated current references and preserved donor sources
without requiring the old checkout at runtime. Historical provenance SHALL
remain unchanged. Product import/deployment/backlog SHALL not be falsely closed.

#### Scenario: Original source is inaccessible to the validation process

- **WHEN** selected Dashboard capture/publication/recovery consumers run
- **THEN** they SHALL complete without reading/importing the old workspace
- **AND** external providers/models and existing production services SHALL be untouched

#### Scenario: User removes the retired directory later

- **WHEN** the verified source has not changed and old workspace sessions are closed
- **THEN** current development SHALL use Dashboard and the private archive locator
- **AND** preserved history SHALL remain recoverable without the deleted directory

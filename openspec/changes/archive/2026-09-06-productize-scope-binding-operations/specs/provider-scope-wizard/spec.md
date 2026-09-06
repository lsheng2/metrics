# provider-scope-wizard Specification Delta

## ADDED Requirements

### Requirement: Scope Library provides a scope binding editor
Scope Library SHALL allow operators to repair provider binding states without editing raw scope semantic fields.

#### Scenario: Operator binds an unbound scope
- **WHEN** a scope binding is `configuration_required`, `ambiguous`, or otherwise missing profile/provider
- **THEN** Scope Library SHALL show a provider profile selector and save action for that scope
- **AND** saving SHALL create or update an explicit binding for the selected provider profile
- **AND** the scope semantic config SHALL remain unchanged

#### Scenario: Operator changes a compatibility binding
- **WHEN** a scope has a compatibility binding
- **THEN** Scope Library SHALL allow either confirming the current binding or selecting a different provider profile
- **AND** the resulting saved binding SHALL be explicit and auditable

#### Scenario: Binding action is compact
- **WHEN** Scope Library shows scope actions
- **THEN** binding actions SHALL be presented as compact controls that do not force excessive row height
- **AND** Edit, Duplicate and Disable SHALL remain available

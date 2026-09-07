## ADDED Requirements

### Requirement: Scope Config consumes Provider Setup handoff
Scope Config SHALL accept Provider Setup handoff inputs so a profile created or selected in Provider Setup can become a scope without re-entering provider identity and mapping context.

#### Scenario: Provider Setup launches new scope
- **WHEN** 用户 selects Create Scope from a provider profile
- **THEN** Scope Config SHALL open with provider and profile preselected
- **AND** it SHALL show the same provider color and provider-specific labels used in Provider Setup
- **AND** it SHALL prefill safe display labels、source query hints and semantic mapping defaults from the selected profile

#### Scenario: Provider Setup binds existing scope
- **WHEN** 用户 selects Bind Existing Scope from Provider Setup
- **THEN** Scope Config or Scope Library SHALL show candidate scopes and bind the selected scope to the provider profile through explicit binding
- **AND** binding SHALL NOT mutate provider profile source population、field bindings or value mappings

### Requirement: Scope and profile lifecycle states are compatible
Scope Config SHALL respect Provider Profile lifecycle state so archived or invalid profiles cannot be used as silent runtime authorities.

#### Scenario: Profile is archived after scope binding
- **WHEN** a scope is bound to an archived provider profile
- **THEN** Scope Config SHALL show an archived-profile blocker
- **AND** Workbench/Grafana/AI handoff SHALL require profile restore or rebinding before fresh runtime use

#### Scenario: Profile import creates a first scope
- **WHEN** 用户 imports a provider profile package and chooses to create a scope
- **THEN** imported profile SHALL remain draft/archived until reviewed
- **AND** the created scope SHALL also start as draft unless the user explicitly completes validation and enablement

### Requirement: Provider visual language stays consistent
Provider Setup and Scope Config SHALL use the same provider-first visual language so users can recognize Jira、HSD-ES and future providers across setup, binding and dashboard readiness flows.

#### Scenario: Jira is shown across setup and scope pages
- **WHEN** Jira provider/profile appears in Provider Setup、Scope Config or Scope Library
- **THEN** Jira SHALL use the green provider style and the same provider label

#### Scenario: HSD-ES is shown across setup and scope pages
- **WHEN** HSD-ES provider/profile appears in Provider Setup、Scope Config or Scope Library
- **THEN** HSD-ES SHALL use the blue provider style and the same provider label

#### Scenario: GitHub is shown across setup and scope pages
- **WHEN** GitHub provider/profile appears in Provider Setup、Scope Config or Scope Library
- **THEN** GitHub SHALL use the purple provider style and the same provider label

# dashboard-ui-baseline Specification Delta

## ADDED Requirements

### Requirement: Data Health exposes scope binding health
Data Health SHALL expose scope provider binding health so operators can identify Workbench/Grafana/AI context risks before users hit a broken scope.

#### Scenario: Operator views binding summary
- **WHEN** operator opens Data Health
- **THEN** page SHALL show counts for explicit, compatibility, configuration_required, ambiguous and disabled bindings
- **AND** page SHALL show total scopes covered by binding projection

#### Scenario: Operator views binding details
- **WHEN** binding details are rendered
- **THEN** each row SHALL show scope, status, profile, provider, provenance, blockers and a repair link to Scope Library
- **AND** compatibility/configuration-required rows SHALL be visually distinguishable from explicit rows

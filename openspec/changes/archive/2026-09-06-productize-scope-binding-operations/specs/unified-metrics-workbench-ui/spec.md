# unified-metrics-workbench-ui Specification Delta

## ADDED Requirements

### Requirement: AI pane diagnostics include scope binding state
Workbench AI pane SHALL show whether AI workspace problems are caused by AI Base readiness or by unresolved Dashboard scope binding.

#### Scenario: AI workspace is not synced for a resolved binding
- **WHEN** AI Base is reachable but reports a workspace sync/setup problem
- **THEN** Workbench AI pane SHALL include current scope binding status, profile and provider in the diagnostic state
- **AND** it SHALL distinguish "bind or confirm scope first" from "sync AI workspace first"

#### Scenario: Scope binding is unresolved
- **WHEN** current scope binding is configuration_required or ambiguous
- **THEN** AI pane SHALL point the user to Scope Library binding repair before suggesting AI workspace sync

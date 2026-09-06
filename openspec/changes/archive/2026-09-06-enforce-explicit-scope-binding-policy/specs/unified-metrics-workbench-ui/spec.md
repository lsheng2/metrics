## ADDED Requirements

### Requirement: Workbench honors explicit-only scope binding policy
Workbench SHALL apply the configured scope binding runtime policy when deciding whether chart, evidence, Grafana and AI panes can consume provider-backed state.

#### Scenario: Compatibility binding under compatibility-allowed policy
- **WHEN** runtime policy is `compatibility_allowed`
- **AND** selected scope resolves through compatibility binding
- **THEN** Workbench SHALL keep provider-backed panes usable with a warning

#### Scenario: Compatibility binding under explicit-only policy
- **WHEN** runtime policy is `explicit_only`
- **AND** selected scope has only compatibility binding
- **THEN** Workbench SHALL block provider-backed panes with explicit-confirmation-required guidance
- **AND** Workbench SHALL NOT display stale chart, evidence, Grafana or AI content from a prior explicit scope

#### Scenario: Explicit binding under explicit-only policy
- **WHEN** runtime policy is `explicit_only`
- **AND** selected scope has explicit binding
- **THEN** Workbench SHALL render provider-backed panes normally

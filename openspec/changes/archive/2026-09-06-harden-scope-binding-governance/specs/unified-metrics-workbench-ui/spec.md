## ADDED Requirements

### Requirement: Workbench applies a consistent scope binding warning policy
Workbench SHALL render provider-backed panes according to the resolved scope binding status instead of allowing stale chart, evidence, Grafana or AI data to survive after scope changes.

#### Scenario: Compatibility binding is selected
- **WHEN** selected scope resolves through a compatibility binding
- **THEN** Workbench SHALL keep provider-backed panes usable
- **AND** it SHALL show a warning that explicit confirmation is recommended
- **AND** it SHALL provide a repair or confirmation entry point without blocking chart and evidence analysis

#### Scenario: Scope binding is unresolved or unsafe
- **WHEN** selected scope binding is configuration_required, ambiguous, disabled, or missing provider/profile values
- **THEN** Workbench SHALL block provider-backed panes with a configuration-required state
- **AND** it SHALL clear stale provider/profile display values from the selected scope
- **AND** it SHALL provide a Scope Library repair link

#### Scenario: Scope changes after a prior valid selection
- **WHEN** user switches from a valid scope to an unresolved scope
- **THEN** chart, evidence, Grafana and AI panes SHALL stop showing rows or iframe content from the previous scope
- **AND** non-provider shell controls SHALL remain usable

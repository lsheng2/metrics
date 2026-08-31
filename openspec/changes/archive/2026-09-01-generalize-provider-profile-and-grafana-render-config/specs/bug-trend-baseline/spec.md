## ADDED Requirements

### Requirement: Bug trend chart catalog is provider-neutral
Bug Trend chart catalog SHALL define provider-neutral chart recipes and series contracts that can be consumed by Jira, HSD-ES and future provider profiles.

#### Scenario: Existing Jira chart is exposed through provider chart API
- **WHEN** a Jira-backed bug trend chart is requested through selected profile contract
- **THEN** chart catalog SHALL expose the same approved chart id、series names、category fields、bucket grains、evidence capability and metric semantics used by non-Grafana consumers

#### Scenario: HSD-ES chart uses equivalent quality facts
- **WHEN** an HSD-ES profile supports the same quality chart recipe
- **THEN** chart catalog SHALL allow HSD-ES binding only after its canonical facts satisfy the recipe, and SHALL keep Jira-specific scope config details out of the recipe

### Requirement: Bug trend AI chart drafts cannot invent series
AI-created bug trend chart drafts SHALL reference published chart recipes and approved series, or explicitly request a new Metrics-owned metric recipe before publication.

#### Scenario: AI requests exact critical-only series
- **WHEN** AI draft asks for `new_critical` but current chart catalog only defines `new_critical_high`
- **THEN** validator SHALL reject the draft or mark it `needs_metric_recipe`, and SHALL NOT publish a panel that claims critical-only semantics from the existing critical/high aggregate

#### Scenario: AI requests display-only series selection
- **WHEN** AI draft asks to show only an already approved series such as `new_critical_high`
- **THEN** validator MAY approve a render-only visibility change if datasource、profile、range、evidence and chart recipe references remain valid

### Requirement: Bug trend render contracts separate chart semantics from visualization
Bug Trend SHALL keep lifecycle、severity、component、aging and daily-count semantics in Metrics-owned recipes and aggregate artifacts, while Grafana render config controls only visualization choices.

#### Scenario: Render config changes panel type
- **WHEN** a chart changes from table to bar chart or adjusts legend/axis/stacking/color choices
- **THEN** the chart recipe and aggregate calculation SHALL remain unchanged unless the requested data semantics also change

#### Scenario: User asks for a new business definition
- **WHEN** user asks for a new bug trend meaning such as critical-only, escaped-only or shift-left-only
- **THEN** system SHALL require a Metrics-owned chart recipe/profile mapping update before Grafana or AI can render the new series as authoritative

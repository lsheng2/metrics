## ADDED Requirements

### Requirement: AI Base participates as a workbench pane
AI Base dashboard agent experience SHALL be available as an optional workbench pane or sidebar that receives the current Metrics context without owning Metrics facts, chart semantics, validation, evidence or publication authority.

#### Scenario: User opens AI assistant inside workbench
- **WHEN** 用户打开 AI assistant pane from the unified workbench
- **THEN** the pane SHALL receive current profile id, provider id, range mode, range bounds, active chart id and selected bucket/series when available
- **AND** AI Base SHALL use Metrics-approved context and APIs rather than direct provider credentials or private Dashboard internals
- **AND** the compact pane SHALL NOT render full AI Base App chrome, settings navigation, workspace catalog, or duplicate service status strip

#### Scenario: User resizes or collapses AI assistant
- **WHEN** 用户拖动 AI pane splitter、折叠 AI pane 或从 right rail 恢复 AI pane
- **THEN** Dashboard SHALL treat that as layout state only
- **AND** AI Base chat session、pending approvals、artifact cards and active turn context SHALL remain available after restore

#### Scenario: User asks AI about selected chart evidence
- **WHEN** selected chart state includes a validated bucket/series evidence selection
- **THEN** AI Base MAY request or receive deterministic evidence context from Metrics
- **AND** AI response SHALL preserve provider/profile/run or snapshot provenance and disclose unavailable evidence states

#### Scenario: User asks AI about selected tickets
- **WHEN** user has selected one or more evidence tickets as an explicit working set
- **THEN** AI Base MAY receive the selected ticket ids and safe summaries from Metrics
- **AND** AI Base SHALL distinguish selected tickets from chart bucket/series selection and from evidence list filters
- **AND** the selected-ticket payload SHALL be bounded and expose truncation metadata when the UI selection is larger than the handoff limit

#### Scenario: User asks AI to create or publish a chart from workbench
- **WHEN** AI Base drafts, validates, dry-runs or publishes a chart from workbench context
- **THEN** Dashboard SHALL remain the authority for chart recipe validation, artifact validation, publish approval, Grafana import and audit
- **AND** the AI pane SHALL surface required approval or validation failures without bypassing Dashboard-owned workflow APIs

### Requirement: Workbench context handoff is bounded and explicit
Workbench-to-AI context handoff SHALL include only approved state and safe artifact references, not raw credentials, private paths, provider-native secrets or unrestricted query text.

#### Scenario: Workbench sends context to AI
- **WHEN** shell updates AI pane context after profile/range/chart/selection changes
- **THEN** the payload SHALL include safe Metrics context fields and bounded evidence summaries only
- **AND** sensitive provider configuration SHALL be omitted or redacted according to existing AI dashboard context rules

#### Scenario: AI Base is absent or disconnected
- **WHEN** workbench cannot reach AI Base
- **THEN** the AI pane SHALL show unavailable diagnostics
- **AND** Dashboard charts, evidence, settings, publish/audit and Grafana rendering SHALL remain usable

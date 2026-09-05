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

### Requirement: Dashboard AI integration is isolated behind an adapter layer
Dashboard SHALL support both standalone operation and with-AI operation, and AI Base-specific integration code SHALL be isolated behind a Dashboard-owned adapter layer.

#### Scenario: Dashboard runs without AI Base
- **WHEN** AI Base is disabled, not configured or unreachable
- **THEN** Dashboard SHALL keep chart rendering, evidence list, ticket detail, scope/profile sync, settings, Grafana preview and Dashboard-owned publish/audit workflows usable
- **AND** Dashboard SHALL show accurate AI diagnostics without starting AI Base as a side effect of rendering a web request
- **AND** Dashboard SHALL NOT require AI Base SDK code to initialize core chart/evidence workbench behavior

#### Scenario: Dashboard runs with AI Base enabled
- **WHEN** AI Base is enabled and reachable
- **THEN** Dashboard SHALL load AI capability through a single AI workbench adapter layer
- **AND** the adapter SHALL translate `WorkbenchPageQueryState`, selected bucket/series, selected ticket working set and safe summaries into AI Base binding/context requests
- **AND** the adapter SHALL own AI Base SDK URL building, binding request construction, context patch construction and host action handler registration

#### Scenario: Implementation adds new AI-assisted behavior
- **WHEN** a future change adds AI chat, artifact, approval, host action or context synchronization behavior to Dashboard
- **THEN** the change SHALL route that behavior through the AI workbench adapter layer
- **AND** provider, chart, evidence, ticket detail and core PageQueryState modules SHALL remain usable without importing AI Base SDK or depending on AI Base runtime objects
- **AND** tests SHALL cover both standalone mode and with-AI mode for the affected user workflow

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

# provider-ai-dashboard-composition Specification

## Purpose
Provider AI Dashboard Composition 定义外部 AI base、gcx 或未来 AI sidecar 如何安全地读取 Metrics catalog/profile/facts，并生成可验证的 dashboard/chart draft，而不直接修改 Metrics 后端代码或绕过 provider governance。

## Requirements

### Requirement: AI dashboard composition uses structured Metrics contracts
AI dashboard composition SHALL use Metrics-provided catalog、profile、chart recipe、render config validation、evidence 和 artifact publication APIs instead of free-form code edits or direct provider access.

#### Scenario: AI sidecar starts a dashboard edit
- **WHEN** user asks the AI sidecar to create or adjust a Grafana chart
- **THEN** AI SHALL first read Metrics capability/catalog/profile metadata and SHALL produce a structured draft intent or render config, not a patch to dashboard backend code

#### Scenario: AI base is absent
- **WHEN** the external AI base app is unavailable, disabled or not installed
- **THEN** Metrics dashboard SHALL still support provider sync、profile selection、approved charts、Grafana rendering、evidence and deterministic APIs without AI runtime dependency

### Requirement: AI cannot own business semantics
AI SHALL NOT invent metric semantics、provider field mappings、series names、classification rules、SQL calculations or direct provider queries that are not approved by Metrics-owned profile registry and chart recipe catalog.

#### Scenario: User asks for unapproved series
- **WHEN** user asks for “weekly open bug trend from WW10 to WW35, only show new critical, not New critical/high” and the selected chart recipe only approves `new_critical_high`
- **THEN** AI SHALL return a validation failure or a `needs_metric_recipe` draft requiring Metrics-owned recipe/profile changes, and SHALL NOT silently filter, rename or fabricate a `new_critical` series

#### Scenario: User asks for supported subset
- **WHEN** user asks AI to hide all approved series except `new_critical_high`
- **THEN** AI MAY generate a render-config draft that changes visualization visibility while preserving the approved `chart_id`、series identity、evidence capability and Metrics API target

### Requirement: AI-generated render drafts are validation-gated
AI-generated chart/dashboard drafts SHALL remain unpublished until Metrics validates data surfaces、profile references、series、category fields、range、limits、evidence links and secret safety.

#### Scenario: Draft passes validation
- **WHEN** AI draft references existing profile、approved chart recipe、approved series and approved render shape
- **THEN** Metrics MAY store the draft as unpublished/personal or publish it according to configured approval policy, and SHALL record validation/audit metadata

#### Scenario: Draft fails validation
- **WHEN** AI draft contains unapproved datasource、raw JQL/EQL、provider-native field literal、secret-like value、unbounded SQL、unsupported chart id or unsupported profile
- **THEN** Metrics SHALL reject the draft with structured findings and SHALL NOT generate importable Grafana JSON from it

### Requirement: AI base and gcx operate as optional clients
External AI base app `D:\AIGC\Report_creater_agent\` and `gcx` SHALL be treated as optional clients/operators over Metrics contracts, not as owners of Metrics facts、provider credentials、profile registry or chart semantics.

#### Scenario: AI base calls Metrics
- **WHEN** AI base invokes dashboard tools
- **THEN** it SHALL call bounded Metrics endpoints with service/user identity and SHALL receive only allowed catalog、profile、aggregate、evidence、render-draft or Grafana operation responses

#### Scenario: gcx operates Grafana
- **WHEN** gcx imports, updates, snapshots or validates a Grafana dashboard for the AI workflow
- **THEN** it SHALL operate on Metrics-generated or Metrics-validated artifacts and SHALL NOT bypass Metrics validators or publish arbitrary dashboard JSON as approved

### Requirement: AI request context is bounded by selected profile and range
AI dashboard requests SHALL carry explicit profile、range、chart intent、requested series/dimensions and output type, and SHALL be constrained by row/time limits and authorization.

#### Scenario: User asks from a Grafana dashboard context
- **WHEN** user asks AI from an open dashboard
- **THEN** AI SHALL include current `profile_id`、range mode、WW/date range、dashboard id and selected panel context in its structured request when available

#### Scenario: Request is too broad
- **WHEN** AI intent omits profile/range or asks for more data than configured limits allow
- **THEN** Metrics SHALL reject or narrow the request with structured warnings, and AI SHALL explain the constraint instead of broadening scope on its own

### Requirement: AI explanations cite deterministic evidence
AI answers about dashboard metrics SHALL cite Metrics facts、aggregate artifacts、chart recipe versions、profile mapping versions and evidence rows where applicable.

#### Scenario: AI explains a trend spike
- **WHEN** user asks why a weekly trend changed
- **THEN** AI SHALL use Metrics evidence APIs for the selected bucket/series and include provider/profile/snapshot provenance in the response context

#### Scenario: Evidence is unavailable
- **WHEN** selected chart only supports summary evidence or the underlying artifact is stale/unavailable
- **THEN** AI SHALL disclose the evidence limitation and SHALL NOT imply ticket-level certainty

### Requirement: AI workflow envelope is provider neutral
Metrics SHALL expose a workflow envelope for AI dashboard requests that describes profile、range、chart recipe、requested series、validation、draft preview、precondition and audit state without embedding provider-native query language.

#### Scenario: Workflow envelope is returned
- **WHEN** a user submits an AI chart request through the dashboard workflow
- **THEN** Metrics SHALL return a structured envelope containing profile id, provider id, dashboard uid, chart id, requested series, range mode, range bounds, intent validation result, render config preview summary, gcx precondition result and safe user-facing guidance

#### Scenario: Provider-native secrets are present in source configuration
- **WHEN** the selected profile contains Jira JQL、HSD-ES saved query metadata、credentials、tokens、private paths or native field mappings
- **THEN** the workflow envelope SHALL omit or redact those values and SHALL expose only approved catalog/profile provenance, canonical metric names and safe artifact references

### Requirement: AI generated chart workflow is preview-first
AI dashboard workflow SHALL treat generated render configs as drafts until validation and precondition checks complete.

#### Scenario: Draft render config is valid
- **WHEN** intent validation produces a render config draft and Metrics render-config validation passes
- **THEN** the workflow SHALL show the draft as previewable and eligible for gcx dry-run or import precondition, not as already published

#### Scenario: Draft render config is invalid
- **WHEN** render-config validation fails
- **THEN** the workflow SHALL show structured findings and SHALL NOT expose a publish-ready state

### Requirement: Jira and HSD-ES profiles share the same AI composition surface
Metrics SHALL use the same AI dashboard composition workflow for Jira and HSD-ES profiles, with provider differences handled by profile registry、fact adapters、chart recipes and render config validation rather than separate UI logic.

#### Scenario: Jira first provider uses the workflow
- **WHEN** profile `chiplet-2a-jira` is selected for an AI dashboard request
- **THEN** Metrics SHALL validate the request through the same catalog, intent and render-config endpoints used for HSD-ES

#### Scenario: HSD-ES second provider uses the workflow
- **WHEN** profile `nvu-ttl-hsdes` is selected for an AI dashboard request
- **THEN** Metrics SHALL validate the request through the same catalog, intent and render-config endpoints used for Jira

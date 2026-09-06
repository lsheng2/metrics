# provider-profile-registry Specification

## Purpose
Provider Profile Registry 定义 provider/project/dashboard profile 的单一配置入口，使 Jira、HSD-ES 和后续 provider 可以通过同一套 profile contract 暴露 source population、field bindings、scope labels、chart support 和 readiness。

## Requirements

### Requirement: Project Provider Profile Registry is the profile authority
系统 SHALL 使用 Project Provider Profile Registry 作为 dashboard、sync、aggregate、Grafana 和 AI 读取 provider/project profile 的单一 authority，并 SHALL 避免在业务代码、Grafana JSON 或 AI prompt 中硬编码 first-profile 常量。

#### Scenario: Consumer resolves a profile
- **WHEN** Grafana、Metrics UI、sync command、aggregate API 或 AI catalog 请求 `profile_id`
- **THEN** 系统 SHALL 从 registry 返回 provider id、profile display name、source population、scope labels、field bindings、value normalization、mapping version、chart support 和 readiness metadata

#### Scenario: Unknown profile is requested
- **WHEN** consumer 请求 registry 中不存在或 disabled 的 `profile_id`
- **THEN** 系统 SHALL 返回 structured unsupported/unavailable 状态，并 SHALL NOT silently fall back to Jira、HSD-ES 或任何默认 profile

### Requirement: Profile source population is provider-neutral
每个 profile SHALL 以 provider-neutral source population contract 表达 source query ownership、reference、hash、tenant/site、subject/item type、criteria snapshot、permission assumptions 和 observed result contract。

#### Scenario: Jira profile uses Metrics-managed JQL
- **WHEN** `chiplet-2a-jira` 或其他 Jira profile 使用 Metrics-managed native query
- **THEN** registry SHALL 记录 `source_query_ownership=metrics_managed_native_query`、JQL text/hash、site/project context、mapping version 和 permission assumptions

#### Scenario: HSD-ES profile uses provider saved query
- **WHEN** `nvu-ttl-hsdes` 或其他 HSD-ES profile 使用 HSD-ES saved query
- **THEN** registry SHALL 记录 `source_query_ownership=provider_owned_saved_query`、query id、tenant、subject、criteria/hash、field-set expectation 和 permission assumptions

### Requirement: Profile field bindings map native fields to canonical facts
Profile SHALL declare native-to-canonical field bindings and value normalization rules needed by chart recipes、evidence、correlation 和 AI explanations, while preserving raw provider fields for audit.

#### Scenario: Provider fields differ by project
- **WHEN** two Jira projects or two HSD-ES projects use different native field names for status、severity、component、release target 或 milestone
- **THEN** each profile SHALL bind its own native fields to shared canonical roles without changing chart recipe ids or Grafana panel definitions

#### Scenario: Field binding is missing for a requested chart
- **WHEN** a chart recipe requires canonical fields not bound by the selected profile
- **THEN** registry/chart support SHALL return `configuration_required` or `unsupported` with missing binding reasons, and SHALL NOT compute or display fabricated values

### Requirement: Static scope labels are explicit profile facts
Profile MAY expose static scope labels such as IP、Project、Milestone 或 release target, but those labels SHALL carry provenance and SHALL NOT be mistaken for provider item-level fields unless separately bound.

#### Scenario: Dashboard displays static profile labels
- **WHEN** selected profile defines user-configured static scope labels
- **THEN** readiness/catalog responses SHALL expose label value、label source、mapping version 和 effective profile id for display and audit

#### Scenario: Dynamic grouping needs item-level fields
- **WHEN** a chart、evidence query、correlation query 或 AI request requires grouping/filtering by item-level IP、project 或 milestone
- **THEN** system SHALL require confirmed provider field bindings or aggregate artifact dimensions rather than reusing static text labels as item-level truth

### Requirement: Chart support is resolved from profile and recipe compatibility
Registry SHALL expose chart support per profile by combining provider capability manifest、profile field bindings、chart recipe requirements、mapping version 和 data freshness.

#### Scenario: Supported chart is requested
- **WHEN** selected profile satisfies a chart recipe's required fields and aggregate freshness policy
- **THEN** chart support SHALL be `supported` and SHALL include chart id、chart version、evidence capability、required canonical fields and provider binding provenance

#### Scenario: Deferred chart is requested
- **WHEN** chart semantics are intentionally outside the current wave, such as execution、automation、shift-left 或 escaped bugs
- **THEN** chart support SHALL be `deferred` with a reason and SHALL NOT be hidden as a successful empty chart

### Requirement: Provider sync dispatch uses profile registry
Provider sync operations SHALL accept provider-neutral profile inputs and dispatch to the correct provider adapter through registry/capability metadata rather than one command per hardcoded profile.

#### Scenario: Operator syncs a supported profile
- **WHEN** operator requests sync for `profile_id` with a valid range and optional force refresh
- **THEN** system SHALL resolve the provider adapter and source population from registry, execute the matching provider sync capability, and record profile provenance in snapshot and aggregate artifacts

#### Scenario: Profile has no live sync capability
- **WHEN** operator requests live sync for a profile whose provider capability or credentials are not configured
- **THEN** system SHALL return `configuration_required` or `unsupported` with actionable blockers, and SHALL preserve any latest successful or seed-backed artifacts

### Requirement: Dashboard scopes bind to provider profiles through explicit registry-backed bindings
Dashboard saved scopes SHALL NOT infer provider/profile identity from mutable display text or stale browser query parameters. The platform SHALL expose a scope binding contract that maps each enabled Dashboard scope to one canonical provider profile when that scope participates in provider-backed Workbench, Grafana, evidence or AI flows.

#### Scenario: Scope has an explicit provider profile binding
- **WHEN** Workbench, Grafana selection handling, AI context creation, sync diagnostics or evidence APIs load a Dashboard scope
- **THEN** the platform SHALL resolve `scope_id` to a canonical binding containing `scope_id`, `profile_id`, `provider_id`, source population provenance, binding status and optional blockers
- **AND** consumers SHALL treat `profile_id` and `provider_id` as resolver outputs rather than independent user-editable inputs

#### Scenario: Scope has only legacy metadata
- **WHEN** a legacy Jira scope has no explicit provider profile binding
- **THEN** the resolver MAY produce a compatibility binding from registry source population, exact profile id, source query hash, or provider-specific saved-query evidence
- **AND** the compatibility binding SHALL mark its status/provenance so product code can migrate it to an explicit binding
- **AND** compatibility binding SHALL NOT silently select an unrelated profile when multiple candidate profiles match

#### Scenario: Scope binding cannot be resolved safely
- **WHEN** no explicit binding exists and compatibility matching is missing, ambiguous, disabled or contradictory
- **THEN** provider-backed consumers SHALL show `configuration_required` with an action to bind the scope to a provider profile
- **AND** they SHALL NOT reuse stale `profile_id` or `provider_id` values from URL, form controls, local storage or AI host actions

#### Scenario: Scope display label changes
- **WHEN** a user renames a saved scope or changes its display labels such as IP, project or milestone
- **THEN** the provider profile binding SHALL remain stable by explicit binding id or canonical profile id
- **AND** Workbench, Grafana, evidence and AI context SHALL continue to use the same resolved provider/profile unless the binding itself is changed through an approved configuration path

### Requirement: Scope provider bindings are auditable and confirmable
Scope provider bindings SHALL expose enough metadata for UI and diagnostics to distinguish explicit operator-approved bindings from compatibility bindings produced during migration.

#### Scenario: Binding metadata is listed
- **WHEN** Dashboard UI lists saved scopes
- **THEN** the provider profile registry boundary SHALL expose binding status, profile id, provider id, provenance and blockers for each scope

#### Scenario: Compatibility binding is confirmed
- **WHEN** an operator confirms a compatibility binding
- **THEN** the system SHALL change the binding status to `explicit`
- **AND** it SHALL record confirmation provenance without changing the scope semantic config or provider profile registry record

### Requirement: Scope binding operations support explicit repair and policy visibility
Provider profile registry boundary SHALL expose operations and projections needed to repair scope bindings and communicate compatibility policy.

#### Scenario: Explicit binding is saved from UI
- **WHEN** Dashboard UI submits a scope id and provider profile id
- **THEN** the registry boundary SHALL validate the provider profile exists and is enabled
- **AND** it SHALL save an explicit binding with resolved provider id and provenance
- **AND** it SHALL reject unknown or disabled provider profiles without changing the prior binding

#### Scenario: Runtime compatibility remains allowed
- **WHEN** a scope uses compatibility binding during the migration period
- **THEN** registry health projection SHALL mark the binding as compatibility and include provenance
- **AND** UI SHALL communicate that explicit confirmation is recommended

#### Scenario: Explicit-only mode is introduced later
- **WHEN** a future deployment disables compatibility runtime
- **THEN** compatibility bindings SHALL be treated as configuration_required until confirmed or rebound
- **AND** existing health projection SHALL make the impact visible before the policy switch

### Requirement: Scope binding governance supports bulk confirmation
Provider profile registry boundary SHALL allow operators to promote multiple safely resolved compatibility scope bindings to explicit bindings in one operation, without changing scope semantic configs or provider profile registry records.

#### Scenario: Bulk confirm compatibility bindings
- **WHEN** operator requests bulk confirmation for compatibility bindings that have resolved profile and provider values
- **THEN** system SHALL promote only eligible compatibility bindings to explicit
- **AND** system SHALL preserve each binding's resolved profile id and provider id
- **AND** system SHALL return counts and skipped reasons for ineligible scopes

#### Scenario: Bulk confirmation skips unsafe bindings
- **WHEN** a selected or discovered scope binding is configuration_required, ambiguous, disabled, missing profile, or missing provider
- **THEN** system SHALL skip that binding with an actionable reason
- **AND** system SHALL NOT fabricate profile/provider values or reuse stale request parameters

### Requirement: Scope binding governance exposes explicit-only readiness
Provider profile registry boundary SHALL expose a readiness projection that shows whether every enabled scope participating in provider-backed flows has an explicit binding, so operators can assess a future explicit-only runtime policy before enabling it.

#### Scenario: Explicit-only readiness is ready
- **WHEN** all enabled provider-backed scopes have explicit bindings
- **THEN** health projection SHALL report explicit-only ready
- **AND** it SHALL show zero impacted scopes

#### Scenario: Explicit-only readiness is blocked
- **WHEN** one or more enabled provider-backed scopes still use compatibility, configuration_required, ambiguous, or disabled bindings
- **THEN** health projection SHALL report explicit-only blocked
- **AND** it SHALL list impacted scopes with status, profile, provider, provenance and repair action context

### Requirement: Scope binding operations are audited
Provider profile registry boundary SHALL write an audit event for each scope binding mutation that can change runtime provider/profile behavior.

#### Scenario: Operator confirms one binding
- **WHEN** operator confirms a compatibility binding
- **THEN** system SHALL write an audit event containing scope id, operation type, actor, old status/profile/provider, new status/profile/provider, provenance and timestamp

#### Scenario: Operator saves an explicit binding
- **WHEN** operator changes or creates an explicit binding from Scope Library
- **THEN** system SHALL write an audit event containing the old binding snapshot and the new binding snapshot
- **AND** the audit event SHALL distinguish manual repair from compatibility confirmation

#### Scenario: Operator bulk confirms bindings
- **WHEN** operator bulk confirms compatibility bindings
- **THEN** system SHALL write auditable mutation events for the changed bindings
- **AND** system SHALL expose the bulk operation summary with changed and skipped counts

### Requirement: Scope binding runtime policy is enforceable
Provider profile registry boundary SHALL support a runtime policy that controls whether compatibility bindings are accepted by provider-backed consumers.

#### Scenario: Compatibility policy allows migration behavior
- **WHEN** runtime policy is `compatibility_allowed`
- **THEN** resolver SHALL continue returning safe compatibility bindings as resolved
- **AND** health projection SHALL show compatibility bindings as warning-level migration risk

#### Scenario: Explicit-only policy rejects compatibility bindings
- **WHEN** runtime policy is `explicit_only`
- **AND** a scope has only a compatibility binding
- **THEN** resolver SHALL return configuration_required for provider-backed consumption
- **AND** it SHALL include a blocker explaining that explicit confirmation is required
- **AND** it SHALL NOT reuse the compatibility profile/provider as runtime authority

#### Scenario: Explicit binding remains accepted in explicit-only mode
- **WHEN** runtime policy is `explicit_only`
- **AND** a scope has an explicit binding with valid profile and provider
- **THEN** resolver SHALL return the explicit profile/provider as resolved

### Requirement: Scope binding audit history is queryable
Provider profile registry boundary SHALL expose recent scope binding audit events so operators can inspect binding mutations without reading raw database rows.

#### Scenario: Operator queries binding audit history
- **WHEN** binding audit history is requested
- **THEN** system SHALL return recent binding mutation events with event type, actor, scope, old status/profile/provider, new status/profile/provider and timestamp

#### Scenario: Audit history contains non-binding events
- **WHEN** audit table contains evidence export, chart publish, or other non-binding events
- **THEN** binding audit history SHALL exclude those events

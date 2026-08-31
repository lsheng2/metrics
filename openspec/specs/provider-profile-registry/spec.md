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

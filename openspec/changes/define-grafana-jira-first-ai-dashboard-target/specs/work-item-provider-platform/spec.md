## ADDED Requirements

### Requirement: Jira first and HSD-ES second provider sequencing
系统 SHALL 把 Jira 作为第一个生产落地 provider，把 Intel HSD-ES 作为第二个平行 provider；参考 HSD-ES Grafana dashboard SHALL 用于定义 dashboard 功能 parity，而不是改变 provider 落地顺序。

#### Scenario: First dashboard parity implementation starts
- **WHEN** 团队开始实现与参考 dashboard 对齐的 Grafana dashboard
- **THEN** 第一阶段 SHALL 使用 Jira provider facts 作为生产数据来源，并 SHALL 使用 provider-neutral DTO/API 命名以便 HSD-ES 后续接入

#### Scenario: First Grafana dashboard release selects one provider profile
- **WHEN** the first Grafana dashboard is released for supported quality charts
- **THEN** it SHALL render one selected Project Provider Profile at a time using provider-neutral chart contracts, even if Jira facts are implemented before HSD-ES facts during development; Jira/HSD-ES side-by-side comparison SHALL require an explicit comparison/correlation mode

#### Scenario: HSD-ES provider is added after Jira
- **WHEN** HSD-ES 成为第二 provider
- **THEN** HSD-ES adapter SHALL 通过同一 provider-neutral capability manifest、facts、query state 和 dashboard contracts 接入，而不是创建一套与 Jira dashboard 分离的产品体系

#### Scenario: Provider capabilities are asymmetric
- **WHEN** Jira 支持某些 planning/workflow 能力而 HSD-ES 支持不同的 article/tenant/subject/facts 能力
- **THEN** 系统 SHALL 通过 manifest 显示真实支持能力和 unsupported reason，不得要求任一 provider 伪造另一个 provider 的原生概念

### Requirement: Dashboard parity uses provider-neutral semantics
Work item provider platform SHALL 以 provider-neutral semantic roles 支持 Grafana parity dashboard，包括 space、work item、state、outcome、area/component、release target、owner、severity/priority、execution bucket 和 WW range。

#### Scenario: Jira maps to parity dimensions
- **WHEN** Jira provider 驱动 parity dashboard
- **THEN** Jira project、issue type、status、resolution、component、fix version、assignee、priority/severity 和 date/week fields SHALL 映射到 provider-neutral semantic roles

#### Scenario: HSD-ES maps to parity dimensions
- **WHEN** HSD-ES provider 驱动 parity dashboard
- **THEN** HSD-ES tenant、subject、article fields、configured static scope labels、state、component/family、release/milestone、owner、priority/severity 和 date/week fields SHALL 映射到同一 provider-neutral semantic roles

### Requirement: Provider seed queries are separate from dashboard query state
系统 SHALL 把 provider-specific saved filters、JQL、EQL、tenant、subject 和 base population rules 作为 provider adapter configuration，而不是作为 Grafana dashboard 的 canonical query state。

#### Scenario: Jira uses a saved filter or configured JQL
- **WHEN** Jira provider 需要从 saved filter、JQL 或 project-specific scope 产生事实
- **THEN** adapter SHALL 把该 native query 记录为 provider seed provenance，并 SHALL 输出 provider-neutral facts that can be queried by Grafana variables

#### Scenario: First Jira profile uses Metrics-managed JQL
- **WHEN** the first Jira Project Provider Profile is configured
- **THEN** it SHALL store `project = "131600" AND component = "team_int_qemu"` as Metrics-managed JQL in the profile/config as the default source population, SHALL version and audit that JQL, and SHALL treat Jira saved filters only as a future optional source ownership mode

#### Scenario: HSD-ES uses the discovered NVU saved query
- **WHEN** HSD-ES provider 使用 `NVU All Bugs` 或类似 saved query 作为 source seed
- **THEN** adapter SHALL treat `ip_fw_sw_sensing.tenant`、`ip_fw_sw_sensing.bug`、base criteria 和 exclusions as provider configuration, and SHALL NOT expose them as the only product-level dashboard schema

#### Scenario: HSD-ES quality facts use the first saved-query seed
- **WHEN** the first HSD-ES Project Provider Profile produces quality facts
- **THEN** it SHALL use `NVU All Bugs` (`queryId=15017652869`) as the base seed for all HSD-ES quality facts unless a later profile version explicitly replaces it with a narrower seed

#### Scenario: Dashboard applies scope over provider facts
- **WHEN** Grafana variables select provider、project/product、milestone/release target、begin WW 或 end WW
- **THEN** 系统 SHALL apply those selections over canonical facts or approved aggregates and SHALL preserve the provider seed/query provenance separately

### Requirement: Project Provider Profile owns per-project mapping
系统 SHALL 为每个 provider/project combination 定义 Project Provider Profile，并通过 profile 管理 source population、field bindings、value normalization、chart support、evidence rules 和 mapping version。

#### Scenario: Project uses Jira profile
- **WHEN** a Jira-backed project has custom fields or project-specific JQL
- **THEN** its Project Provider Profile SHALL declare the Jira site/project scope, source query ownership, JQL/filter/scope parameters, field bindings, value normalization and mapping version

#### Scenario: Project uses HSD-ES profile
- **WHEN** an HSD-ES-backed project uses a tenant/subject and saved query
- **THEN** its Project Provider Profile SHALL declare tenant, subject, saved query id or EQL seed, field bindings, value normalization and mapping version

#### Scenario: Project uses static scope labels
- **WHEN** provider fields for dashboard-level `IP`, `Project`, or `Milestone` are not yet confirmed
- **THEN** Project Provider Profile MAY declare user-configured raw/static text labels for those dimensions, SHALL use `IP=chiplet_ip`, `Project=chiplet`, `Milestone=2a` for the first Jira profile and `IP=NVU`, `Project=NVU1.0_TTL`, `Milestone=NVU_TTL_FWSW0.8` for the first HSD-ES profile, and SHALL mark them as fixed profile scope labels with source, mapping version and provenance rather than provider-derived item fields

#### Scenario: Grafana uses a project profile
- **WHEN** Grafana requests chart data
- **THEN** Grafana SHALL pass provider-neutral profile/query identifiers and SHALL NOT include Jira custom field ids, raw JQL, HSD-ES article field names or HSD-ES EQL in panel-local business logic

#### Scenario: Grafana resolves provider from profile
- **WHEN** Grafana requests chart data with a selected Project Provider Profile
- **THEN** provider platform SHALL be able to resolve the provider from `profile_id`, SHALL reject or flag mismatched explicit provider/profile pairs, and SHALL preserve the resolved provider in response provenance

#### Scenario: Profile mapping is invalid
- **WHEN** a required chart field binding is missing or refers to a provider field unavailable in the source population
- **THEN** provider platform SHALL mark affected charts as `configuration_required` or `unsupported` with reasons instead of producing partial or misleading aggregates

### Requirement: Source query ownership is explicit
Provider platform SHALL distinguish provider-owned saved queries from Metrics-owned native queries while normalizing both into the same source population provenance contract.

#### Scenario: HSD-ES provider owns the saved query
- **WHEN** HSD-ES source population is based on a saved query such as `queryId=15017652869`
- **THEN** profile SHALL record source query ownership as provider-owned and SHALL store the query id, tenant, subject, expected criteria snapshot or hash, permission assumptions and observed result contract

#### Scenario: Metrics owns Jira JQL
- **WHEN** Jira source population is based on JQL stored in project configuration
- **THEN** profile SHALL record source query ownership as Metrics-managed and SHALL version the JQL with the profile, validate allowed fields/functions, and record query text/hash in fact snapshot provenance

#### Scenario: Jira provider owns a saved filter
- **WHEN** Jira source population is based on a Jira saved filter instead of profile-managed JQL
- **THEN** profile SHALL record source query ownership as provider-owned and SHALL store filter id, expected owner/scope and effective query provenance when available

### Requirement: Canonical fields preserve provider and project-specific fields
Provider platform SHALL define canonical fields for dashboard/evidence/AI/correlation, while preserving provider-native fields and per-project mapping fields without flattening them into one global schema.

#### Scenario: Jira fields are normalized
- **WHEN** Jira issue data is projected into platform facts
- **THEN** system SHALL map configured Jira fields into canonical roles such as source item id/type, state, outcome, priority/severity, component/area, release target, owner, submitter and WW bucket, and SHALL retain unmapped custom fields under project or provider field payloads

#### Scenario: HSD-ES article fields are normalized
- **WHEN** HSD-ES article data is projected into platform facts
- **THEN** system SHALL map fields such as id, HSD_type, status, reason, priority, exposure, component, release, release_affected, target_MS, owner, submitted_by, submitted_date, updated_date, implemented_date, closed_date, team_found, pss_escape and days_open into canonical or project fields, and SHALL retain the full native article payload as provider fields

#### Scenario: A chart needs a project-specific dimension
- **WHEN** a chart requires a field not present in the canonical field set, such as an NVU-specific milestone, automation, shift-left or escaped-defect classification
- **THEN** the chart SHALL declare that field as project mapping input and SHALL render `configuration_required` until the mapping is supplied and validated

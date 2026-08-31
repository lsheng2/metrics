## Purpose
Work Item Provider Operations Platform 定义 Metrics Dashboard 面向 Jira、Intel HSD-ES、GitHub、Azure DevOps 等 work item provider 的长期统一能力层。它的目标是让 dashboard、AI chat、automation、planning、correlation 和 reporting 复用同一套 provider-neutral contracts，而不是为每个 provider 建立平行产品系统。

## Requirements

### Requirement: Provider-neutral capability core
系统 SHALL 提供 provider-neutral core 来表达 connection、metadata、search、facts、actions、planning、release 和 code review 等能力，并允许每个 provider adapter 只声明和实现自己真实支持的 capability。

#### Scenario: Provider declares asymmetric capabilities
- **WHEN** Jira adapter 支持 planning、HSD-ES adapter 支持 defect/record facts and correlation、GitHub adapter 只支持部分 issue、PR、release 和 code review facts
- **THEN** shared core SHALL 接受这种能力不对称，并且不得要求 HSD-ES 或 GitHub adapter 伪造 Jira board、sprint 或 workflow 概念

#### Scenario: UI resolves unsupported capability
- **WHEN** UI 或 AI workflow 请求 provider manifest 中不支持的 capability
- **THEN** 系统 SHALL 返回明确的 unsupported reason，而不是显示不可执行的步骤或静默降级

### Requirement: Provider capability manifest
每个 provider adapter SHALL 暴露 `ProviderCapabilityManifest`，描述 provider 名称、query language、支持的 read/write/planning/release/code-review capability，以及不支持能力的原因。

#### Scenario: Scope Wizard loads a provider
- **WHEN** Scope Wizard 选择某个 provider connection
- **THEN** UI SHALL 根据 manifest 决定显示 search、metadata、field options、planning 或 release 控件

#### Scenario: AI chooses an action
- **WHEN** AI workflow 准备生成 provider action proposal
- **THEN** workflow SHALL 先读取 manifest，并只生成 adapter 声明支持的 action type

### Requirement: Shared terminology with provider-specific hints
用户可见 workflow SHALL 优先使用 provider-neutral terms，例如 Provider、Space、Work item、Item type、State、Outcome、Area、Release target、Owner、Planning bucket 和 Query；provider-specific terms 只作为上下文提示出现。

#### Scenario: Jira scope configuration
- **WHEN** 用户配置 Jira-backed scope
- **THEN** UI SHALL 使用 provider-neutral labels，并可以在 hint 中显示 Jira Project、Issue Type、JQL、Fix Version 等术语

#### Scenario: GitHub provider arrives later
- **WHEN** 第二个 provider 映射到 GitHub organization、repository、issue、pull request、label、milestone 或 project field
- **THEN** shared UI SHALL 复用 provider-neutral workflow，而不是复制一套 GitHub-only 产品页面

#### Scenario: HSD-ES provider arrives as the second provider
- **WHEN** HSD-ES adapter 映射到 HSD-ES tenant、subject、article/record、status、owner、priority/severity、component、family、release 或 stepping 字段
- **THEN** shared UI SHALL 复用 provider-neutral workflow，并只在 provider-specific hints 中显示 HSD-ES 原生术语

### Requirement: Adapter boundary
系统 SHALL 把 external provider quirks 放在 provider-specific adapter 中，把 action plan、approval、audit、query/filter semantic model、metadata DTO、scope wizard UI pattern 和 AI citation contract 放在 shared core 中。

#### Scenario: Jira-specific pagination
- **WHEN** Jira API 需要处理 JQL pagination、custom field id 或 changelog endpoint 差异
- **THEN** Jira adapter SHALL 封装这些细节，并向 shared core 输出稳定 DTO

#### Scenario: HSD-ES-specific API mechanics
- **WHEN** HSD-ES API 使用 Kerberos 或 `/rest/auth/...` token/basic auth、EQL query grammar、article id/rev、`tenant`/`subject` schema、`fieldValues` payload、`start_at`/`max_results` pagination、lookup APIs、relation links 或 comments-as-articles endpoints
- **THEN** HSD-ES adapter SHALL 封装这些细节，并向 shared core 输出稳定 DTO

#### Scenario: Product feature consumes provider facts
- **WHEN** Bug Trend、Velocity、Forecast、AI Chat 或 future reporting feature 需要 work item facts
- **THEN** consumer SHALL 依赖 provider-neutral facts 或 semantic services，而不是直接调用 provider REST API

### Requirement: Python-native production runtime
生产 runtime SHALL 使用 Python/Django-native provider subset 作为核心执行路径，并把 `jira-cli` 仅作为 optional developer/operator diagnostic sidecar，除非未来 review 明确提升其生产地位。

#### Scenario: Dashboard request path
- **WHEN** dashboard 页面、HTMX partial、durable sync 或 AI workflow 在生产路径读取 provider data
- **THEN** 系统 SHALL 使用 Python-native typed API，而不是通过 subprocess 调用本地 `jira` binary

#### Scenario: Developer compares adapter behavior
- **WHEN** 开发者需要对照 Jira REST adapter 与 `jira-cli` 查询结果
- **THEN** 可选 wrapper MAY 调用 `jira-cli`，但结果不得成为生产 source of truth

### Requirement: Provider-specific modules implement integration only
Provider-specific modules SHALL 只拥有外部系统集成、同步、auth、pagination、error mapping 和 raw projection，不得复制 shared product workflows。

#### Scenario: New HSD-ES adapter
- **WHEN** HSD-ES 成为 Jira 之后的第二个 provider
- **THEN** 项目 MAY 增加 HSD-ES adapter module 来实现 HSD-ES API 细节，但 SHALL NOT 复制 Scope Wizard、AI action approval、audit、correlation 或 dashboard consumption 的完整产品层

### Requirement: Provider platform extraction timing
在只有 Jira provider 的阶段，项目 MAY 继续把实现放在 `jira_sync` 和相关现有模块中；当第二个 provider 落地或多个 consumers 证明 contract 形状稳定时，系统 SHALL 将 shared contracts 提取到 `provider_ops` 或 `work_items` 模块。

#### Scenario: Jira-only Phase 1
- **WHEN** Phase 1 只实现 Jira-backed Scope Wizard
- **THEN** public DTO/API names SHALL 尽量使用 `Provider*`、`WorkItem*` 或 provider-neutral 命名，以降低未来提取 shared module 的成本

#### Scenario: Jira and HSD-ES parallelization pressure
- **WHEN** HSD-ES is accepted as the second provider before Jira Phase 1 finishes
- **THEN** Phase 1 SHALL keep shared provider contracts provider-neutral from the start and MAY implement thin Jira/HSD-ES capability manifests early to expose asymmetry and correlation needs before deeper feature work

### Requirement: Provider platform consumes profile registry
Provider platform SHALL expose provider capabilities through Project Provider Profiles so dashboard、sync、Grafana and AI consumers can resolve provider/project behavior without hardcoded first-profile logic.

#### Scenario: Provider capability is requested through profile
- **WHEN** consumer requests capabilities for a `profile_id`
- **THEN** platform SHALL resolve the profile to provider adapter、source population、capability manifest、field binding coverage、chart support and unsupported/deferred reasons

#### Scenario: Provider adapter is added later
- **WHEN** a future provider such as GitHub、Azure DevOps or another HSD-ES project is added
- **THEN** platform SHALL add provider/profile registry entries and adapter bindings without creating a parallel dashboard product module for that provider

### Requirement: Provider-specific implementation remains behind adapter boundaries
Provider platform SHALL keep native API mechanics、credentials、query syntax、pagination、field expansion and error normalization inside provider-specific adapters, while shared products consume canonical profile/fact/chart contracts.

#### Scenario: Jira and HSD-ES source populations differ
- **WHEN** Jira uses Metrics-managed JQL and HSD-ES uses provider-owned saved query
- **THEN** both SHALL appear to dashboard/Grafana/AI as source population metadata from the selected profile, and consumers SHALL NOT branch on JQL versus HSD-ES query id

#### Scenario: Provider API behavior is uncertain
- **WHEN** implementation needs provider-specific auth、endpoint shape、pagination、field semantics or permission behavior
- **THEN** provider adapter work SHALL verify the authoritative Jira or HSD-ES documentation before changing code or claiming support

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

### Requirement: Shared provider cache and materialization core
Provider sync cache and artifact materialization SHALL be modeled as shared provider platform behavior, while provider-specific modules own only external API mechanics and raw-to-normalized projection。

#### Scenario: A provider adapter participates in cached sync
- **WHEN** Jira、HSD-ES、GitHub、Azure DevOps or a future provider is configured for live sync
- **THEN** the adapter SHALL expose provider-specific fetch/projection capability through provider-neutral sync inputs and outputs, and SHALL NOT define a separate dashboard-specific cache model

#### Scenario: Product features consume provider artifacts
- **WHEN** Grafana, Metrics UI, AI chat, reporting or correlation consumes provider data
- **THEN** consumers SHALL depend on provider-neutral facts, snapshots, aggregate artifacts and freshness metadata rather than provider-specific cache tables, raw API payloads or live provider calls

#### Scenario: Provider capability manifest includes sync/cache status
- **WHEN** UI or AI reads a provider capability manifest
- **THEN** the manifest SHALL distinguish read/search support, live sync readiness, cache/materialization readiness, write/action support and unsupported capabilities so consumers do not infer production data readiness from generic connectivity alone

### Requirement: Provider-specific modules keep external quirks local
Provider-specific sync modules SHALL encapsulate auth, paging, rate limits, retries, endpoint differences, native query execution and secret handling, while shared cache rules remain provider/profile agnostic。

#### Scenario: HSD-ES and Jira use different source query ownership
- **WHEN** HSD-ES uses provider-owned saved query references and Jira uses Metrics-managed JQL
- **THEN** both SHALL map to the same source population provenance contract, cache identity shape and freshness behavior, while preserving native query details inside provider-specific provenance

#### Scenario: A new provider is added
- **WHEN** a future provider adds live sync support
- **THEN** it SHALL reuse the shared cache identity, freshness states, failure fallback and test expectations instead of introducing a provider-only dashboard rendering path

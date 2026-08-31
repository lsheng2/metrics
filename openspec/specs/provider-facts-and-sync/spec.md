## Purpose
Provider Facts and Sync 定义 work item provider 的 read-only discovery、search、facts projection、durable sync 和 cross-provider fact provenance 规则。它保证 dashboard 和 AI answer 基于可追溯的 provider facts，而不是 prompt memory、临时 live query 或未审计的 CLI output。

## Requirements

### Requirement: Read-only discovery and search capabilities
系统 SHALL 提供 read-only provider capabilities 来搜索 work items、读取 detail、comments、history/timeline、transitions/worklogs，以及列出 spaces、item types、fields、field allowed values、components、versions、boards、sprints 或 iterations。

#### Scenario: Provider search
- **WHEN** consumer 调用 `WorkItemSearchCapability.search`
- **THEN** adapter SHALL 返回稳定 `WorkItemSearchPage`，包含分页信息、work item identity、requested fields 和 normalized errors

#### Scenario: Query validation
- **WHEN** consumer 调用 provider query validator
- **THEN** adapter SHALL 返回 syntax、permission、empty-result 和 provider-specific error feedback，而不是把 raw exception 暴露给 UI

#### Scenario: HSD-ES read/search API is used
- **WHEN** consumer 调用 HSD-ES adapter 的 read/search capability
- **THEN** adapter SHALL normalize HSD-ES `article` identity (`id` and `rev` when available)、tenant、subject、requested fields、pagination、permissions 和 errors into provider-neutral DTOs using `/rest/article/{id}` and `/rest/query/execution/eql` style APIs

### Requirement: Durable dashboard consumption
Dashboard render paths SHALL consume durable local history、facts、calculation runs 或 approved aggregate artifacts，不得在每次 dashboard render 时 live-query external provider。

#### Scenario: Bug Trend chart render
- **WHEN** Bug Trend dashboard 渲染趋势图或 evidence drilldown
- **THEN** 它 SHALL 使用本地 durable Jira history、bucket facts 和 matching calculation run，而不是直接调用 Jira REST API

#### Scenario: HSD-ES-backed chart render
- **WHEN** dashboard 渲染 HSD-ES-backed trend、quality、triage 或 correlation view
- **THEN** 它 SHALL 使用本地 durable HSD-ES facts、snapshots 或 approved aggregate artifacts，而不是每次 render 时 live-query HSD-ES API

#### Scenario: Scope setup preview
- **WHEN** Scope Wizard 只做 metadata discovery、query validation 或 issue count preview
- **THEN** 它 MAY live-query provider read-only endpoints，因为这是 setup workflow，不是 dashboard render source of truth

### Requirement: Provider facts for AI answers
AI answer SHALL 基于 provider facts payload，并在回答中保留可追溯的 work item identity、field source、timeline/comment source 或 calculation artifact reference。

#### Scenario: User asks a work item question
- **WHEN** 用户询问某个 scope 下的 bug risk、root cause、component cluster 或 release readiness
- **THEN** AI workflow SHALL retrieve provider facts first，并基于 facts 生成回答，不得凭空生成 ticket、status、priority、assignee 或 PR state

### Requirement: Facts projection separates provider raw data from semantic use
Provider adapters SHALL 把 raw API response 投影为 provider-neutral facts，并保留足够 provenance 供 audit、debug 和 evidence drilldown 使用。

#### Scenario: Jira changelog projection
- **WHEN** Jira adapter 读取 issue changelog
- **THEN** 它 SHALL 输出 normalized timeline/fact projection，并保留 provider issue key、field id/name、timestamp 和 raw value provenance

#### Scenario: HSD-ES history projection
- **WHEN** HSD-ES API exposes record comments through comments-as-articles, relation links through `/rest/article/{id}/links`, children through `/rest/article/{id}/children`, or history/state-change APIs
- **THEN** HSD-ES adapter SHALL project them into normalized timeline/fact payloads and preserve HSD-ES article id、parent id、subject、field identity、timestamp、actor when available 和 raw value provenance

### Requirement: Provider-specific sync owns external quirks
Provider-specific sync modules SHALL own auth、pagination、rate limit、retry、timeout、secret redaction、error normalization 和 endpoint quirks。

#### Scenario: GitHub GraphQL pagination
- **WHEN** future GitHub adapter 读取 issue/PR facts
- **THEN** GraphQL cursor mechanics SHALL remain inside GitHub adapter while shared consumers receive stable facts DTOs

#### Scenario: HSD-ES API mechanics
- **WHEN** HSD-ES adapter handles Kerberos/token auth、`/rest/auth/...` URL shape for token/basic auth、`start_at`/`max_results` pagination、EQL body payloads、bulk partial/error responses、field expansion、error payloads or permission filters
- **THEN** those mechanics SHALL remain inside HSD-ES adapter while shared consumers receive stable facts DTOs

### Requirement: Current Jira facts baseline is durable and scope-bound
当前 Jira facts baseline SHALL 以 saved scope 为边界，将 Jira raw payload、normalized issue state、status/resolution transitions、sync cursor、calculation run、bucket aggregates 和 bucket membership evidence 保存在本地 durable store 中。

#### Scenario: Jira facts are consumed by Bug Trend
- **WHEN** Bug Trend calculator 或 chart API 需要 Jira bug trend facts
- **THEN** 系统 SHALL 从本地 durable issue/history/calculation artifacts 读取 facts，而不是在 dashboard render path 中 live-query Jira

#### Scenario: Jira facts are prepared for future provider-neutral extraction
- **WHEN** 后续 provider platform 抽取 shared contracts
- **THEN** 当前 Jira facts baseline SHALL 作为 provider-neutral WorkItem/Facts contract 的输入，并保留 Jira-specific JQL、field ids、changelog 和 auth mechanics 在 Jira-specific adapter/sync boundary 内

### Requirement: Current Jira metadata discovery is cached and read-only
当前 Jira metadata discovery SHALL 提供 read-only scope metadata options，包括 projects、item types、statuses、resolutions、priorities、fields、components 和 versions，并按 provider、base URL、auth mode、query、project 和 item type context 缓存。

#### Scenario: Scope config page requests metadata
- **WHEN** scope config UI 请求 Jira scope metadata options
- **THEN** 系统 SHALL 通过 Jira metadata provider 返回 options 或 warnings，并不得修改 Jira provider state

#### Scenario: Unsupported metadata provider is requested
- **WHEN** consumer 请求当前未注册的 metadata provider
- **THEN** 系统 SHALL 返回明确 unsupported error，而不是静默退回 Jira 或返回空成功结果

### Requirement: Providers emit canonical facts before chart aggregation
Provider sync SHALL normalize Jira、HSD-ES and future provider payloads into canonical provider facts before chart recipes calculate aggregates.

#### Scenario: Jira and HSD-ES feed the same chart
- **WHEN** `open_bug_trend` or another approved quality chart is requested for a Jira profile and an HSD-ES profile
- **THEN** each provider adapter SHALL produce provider-specific raw provenance plus canonical fields sufficient for the same chart recipe to calculate provider-neutral aggregate rows

#### Scenario: Chart calculator receives provider-native payload
- **WHEN** aggregate calculation would require direct Jira issue JSON or HSD-ES article field shape
- **THEN** system SHALL first add or fix profile field bindings and canonical fact projection rather than embedding provider-native branching in the chart calculator

### Requirement: Aggregate artifact identity is range-mode neutral
Provider aggregate artifacts SHALL identify requested ranges with provider-neutral range mode、range start/end、range grain and display labels, rather than assuming every cache key is WW-only.

#### Scenario: WW range artifact is stored
- **WHEN** `range_mode=ww`
- **THEN** artifact identity SHALL include range mode, normalized calendar start/end resolved from `begin_ww`/`end_ww`, WW labels and chart version

#### Scenario: Date range artifact is stored
- **WHEN** `range_mode=date`
- **THEN** artifact identity SHALL include range mode, normalized date start/end, date display labels and chart version, and SHALL NOT reuse a WW artifact solely because old URL WW variables match

### Requirement: Aggregate generation is profile-dispatched
Sync and aggregate generation SHALL dispatch by selected profile and chart recipe compatibility, not by hardcoded provider/profile ids in consumer code.

#### Scenario: Generic profile sync command is used
- **WHEN** operator runs a provider/profile sync for any configured profile
- **THEN** system SHALL resolve adapter、source query、field set、mapping version、range mode and chart materialization plan from registry

#### Scenario: Latest artifact is requested
- **WHEN** Grafana or AI requests chart data for a selected profile
- **THEN** aggregate service SHALL find matching local artifacts by provider/profile/chart/range identity and SHALL return freshness/provenance state without invoking the external provider in the render path

### Requirement: Provider-specific artifacts remain auditable
Provider facts and aggregate artifacts SHALL preserve source query、field-set、mapping-version、snapshot、calculation-run and freshness provenance for both dashboard and AI use.

#### Scenario: AI explains a chart
- **WHEN** AI reads an aggregate artifact or evidence result
- **THEN** response payload SHALL include enough provenance for AI to state provider id、profile id、source population、fact snapshot、mapping version、calculation run and freshness status

#### Scenario: Profile mapping changes
- **WHEN** field bindings、value normalization、source query or chart binding changes for a profile
- **THEN** previously materialized facts and aggregates SHALL be treated as stale/non-authoritative unless their identity matches the current profile contract

### Requirement: Jira-derived facts drive the first Grafana parity dashboard
第一阶段 Grafana parity dashboard SHALL 使用 Jira provider 的 durable facts、snapshots、calculation runs 或 approved aggregate artifacts 作为数据来源，不得每次 render 直接 live-query Jira。

#### Scenario: Grafana renders reference-equivalent quality panel from Jira
- **WHEN** Grafana 渲染 component bug、valid bug、open bug trend、aging 或 total bug trend panel
- **THEN** panel SHALL 使用 Jira-derived durable facts 或 Metrics-approved aggregates，并 SHALL 保留 scope、date/WW、series 和 provider provenance

#### Scenario: First wave encounters deferred semantic categories
- **WHEN** Grafana 渲染 execution、automation、shift-left 或 escaped bug panel in the first wave
- **THEN** system SHALL return explicit `deferred`, `configuration_required`, or `unsupported` state with a reason, and SHALL NOT generate unverified Jira facts or aggregate rows for those categories

### Requirement: HSD-ES-derived facts reuse the same dashboard contracts
第二阶段 HSD-ES provider SHALL 生成与 Jira phase 兼容的 durable facts 或 approved aggregate artifacts，使同一 Grafana parity dashboard 可以按 provider query state 切换或并行显示。

#### Scenario: HSD-ES facts become available
- **WHEN** HSD-ES adapter 完成 tenant/subject、EQL、lookup、article detail、pagination 和 permission contract review
- **THEN** HSD-ES sync SHALL 输出与 dashboard contracts 兼容的 quality、execution、efficiency、evidence 和 provenance facts

#### Scenario: HSD-ES seed query is known but chart mappings remain incomplete
- **WHEN** HSD-ES seed information such as `queryId=15017652869`, `ip_fw_sw_sensing.tenant`, `ip_fw_sw_sensing.bug` and NVU-FW bug criteria is known
- **THEN** system SHALL record it as provider seed configuration and SHALL still require chart-level field mappings before declaring a parity chart supported for HSD-ES

#### Scenario: HSD-ES seed facts are available before live sync
- **WHEN** the `nvu-ttl-hsdes` profile has a local normalized seed fact artifact but no configured live HSD-ES backend credential
- **THEN** Metrics MAY generate first-wave quality aggregate rows from the seed artifact, SHALL label freshness as seed-backed/materialized, SHALL preserve saved-query provenance, and SHALL NOT mark the live HSD-ES provider connection as production-ready

#### Scenario: Browser SSO is completed but backend sync is not configured
- **WHEN** an operator opens the HSD-ES saved-query link and successfully signs in through the browser
- **THEN** system SHALL treat that as a human access/configuration check only, and SHALL NOT infer that Django, Grafana, or scheduled sync now has a reusable HSD-ES backend credential

#### Scenario: First HSD-ES quality facts are synced
- **WHEN** the first HSD-ES quality-facts sync runs
- **THEN** HSD-ES sync SHALL use `NVU All Bugs` (`queryId=15017652869`) as the base source seed for all HSD-ES quality facts and SHALL record tenant, subject, query id, expected criteria snapshot or hash and permission assumptions in snapshot provenance

#### Scenario: HSD-ES chart mapping remains unknown
- **WHEN** a target HSD-ES field mapping for IP, project, milestone, execution, automation, shift-left or escaped-defect semantics is not confirmed
- **THEN** 系统 SHALL 允许 Jira-first dashboard 继续实现，并 SHALL 把该 HSD-ES chart binding 标记为 configuration-required 或 deferred，而不是阻塞 Jira phase 或猜测 tenant-specific fields

### Requirement: Approved aggregates may mirror reference dashboard shapes
系统 MAY 生成与参考 dashboard Mongo aggregate collection 等价的 approved aggregate artifacts，但这些 artifacts SHALL 由 Metrics 后端生成、验证和版本化。

#### Scenario: Reference query uses Mongo aggregate fields
- **WHEN** 参考 dashboard 使用 `ip_name`、`prj_name`、`milestone`、`xData` 或类似聚合字段
- **THEN** Metrics SHALL 可以输出 provider-neutral 等价字段，但 SHALL 保留原始 provider identity 和 mapping provenance

#### Scenario: Scope labels are configured as raw text
- **WHEN** a profile defines `IP`, `Project`, `Milestone` or equivalent dashboard dimensions as user-provided raw/static text
- **THEN** approved aggregate rows SHALL expose `IP=chiplet_ip`, `Project=chiplet`, `Milestone=2a` for the first Jira profile and `IP=NVU`, `Project=NVU1.0_TTL`, `Milestone=NVU_TTL_FWSW0.8` for the first HSD-ES profile as fixed profile scope labels with source `user_configured_static_text`, mapping version and profile provenance, and SHALL NOT claim they were extracted from provider item fields

#### Scenario: Aggregate artifact is stale
- **WHEN** Grafana 请求的 aggregate artifact 与当前 scope、WW range、provider snapshot 或 calculation run 不匹配
- **THEN** 系统 SHALL 返回 stale or unavailable state，而不是 silently rendering mismatched panel data

#### Scenario: Date-mode request overlaps a WW-keyed cache artifact
- **WHEN** Grafana requests a provider aggregate with `range_mode=date`
- **THEN** Metrics SHALL resolve the requested range from `begin_date` and `end_date`, SHALL NOT reuse a cached aggregate artifact only because its `begin_ww` and `end_ww` match stale URL variables, and SHALL rebuild the date-window aggregate from the latest provider facts or return an explicit unavailable/configuration state

### Requirement: Provider fact records separate canonical, project, and native fields
Durable facts SHALL expose canonical fields required by dashboard and AI while retaining project-specific fields and provider-native fields as separate payload layers.

#### Scenario: Jira fact is stored
- **WHEN** Jira sync stores an issue fact
- **THEN** the fact SHALL include canonical dashboard fields, Project Provider Profile id/version, Jira source query ownership provenance, configured project fields, and native Jira field values needed for audit or remapping

#### Scenario: HSD-ES fact is stored
- **WHEN** HSD-ES sync stores an article fact
- **THEN** the fact SHALL include canonical dashboard fields, Project Provider Profile id/version, HSD-ES tenant/subject/query provenance, project fields derived from mapped article fields, and native provider fields needed for audit or remapping

#### Scenario: A mapping changes
- **WHEN** a project field mapping is revised for Jira or HSD-ES
- **THEN** new fact snapshots or aggregate runs SHALL record the mapping version so Grafana and AI can distinguish old results from reinterpreted results

#### Scenario: Source query ownership differs by provider
- **WHEN** one profile uses an HSD-ES provider-owned saved query and another profile uses Metrics-managed Jira JQL
- **THEN** facts SHALL expose both through a common source population provenance shape including profile id, provider id, ownership type, query reference, optional query text/hash and fact snapshot id

#### Scenario: First Jira facts are synced
- **WHEN** the first Jira facts sync runs for the parity dashboard
- **THEN** Jira sync SHALL use Metrics-managed JQL `project = "131600" AND component = "team_int_qemu"` stored in the Project Provider Profile as the default source population and SHALL preserve the JQL text or hash, version and profile id in fact snapshot provenance

### Requirement: Project Provider Profiles are validated before sync
Provider sync SHALL validate Project Provider Profile configuration before producing durable facts or aggregate rows.

#### Scenario: Required field binding is missing
- **WHEN** a profile lacks a field required by enabled chart recipes
- **THEN** sync SHALL report profile validation errors or chart-level `configuration_required` state and SHALL NOT silently emit zero-valued metrics

#### Scenario: Provider-owned query has drifted
- **WHEN** a provider-owned saved query's observed tenant, subject, field set or criteria snapshot no longer matches profile expectations
- **THEN** sync SHALL mark the snapshot as query-drifted or unavailable until the profile is reviewed

#### Scenario: Metrics-owned Jira JQL changes
- **WHEN** profile-managed Jira JQL changes
- **THEN** sync SHALL increment or record a new mapping/query version so historical aggregates remain tied to the query that produced them

### Requirement: Chart aggregate contracts are generated from chart recipes and provider bindings
Metrics SHALL generate Grafana-facing aggregates from provider-neutral chart recipes plus provider-specific bindings, rather than from panel-local query logic.

#### Scenario: Jira provider supports a chart recipe
- **WHEN** a chart recipe is bound to Jira facts
- **THEN** the generated aggregate SHALL name the chart id/version, provider id, required canonical fields, project field mappings, evidence capability and calculation provenance

#### Scenario: HSD-ES provider supports a chart recipe
- **WHEN** a chart recipe is bound to HSD-ES facts
- **THEN** the generated aggregate SHALL name the HSD-ES tenant/subject/query seed provenance in addition to the same provider-neutral chart id/version, fields, evidence capability and calculation provenance

#### Scenario: Provider does not support a chart recipe
- **WHEN** required canonical or project fields are unavailable for a provider
- **THEN** aggregate generation SHALL return `unsupported`, `configuration_required`, or `deferred` state with a reason, not zero-valued chart rows

### Requirement: Daily metric aggregates are materialized by Metrics
Metrics SHALL own daily or WW-bucketed metric calculation results, including values displayed by Grafana charts such as daily new standard bug counts.

#### Scenario: Daily new standard bug count is calculated from Jira facts
- **WHEN** Jira facts are aggregated for `daily_new_standard_bug_count`
- **THEN** Metrics SHALL use the selected Project Provider Profile to identify creation date, work item type, standard-bug eligibility and dashboard scope, and SHALL emit aggregate rows with metric id, bucket grain/date or WW, dimensions, value, chart version, mapping version, provider id, profile id, fact snapshot id and calculation run id

#### Scenario: Daily new standard bug count is calculated from HSD-ES facts
- **WHEN** HSD-ES facts are aggregated for `daily_new_standard_bug_count`
- **THEN** Metrics SHALL use confirmed HSD-ES field bindings and saved-query/EQL provenance from the Project Provider Profile, and SHALL emit the same provider-neutral aggregate contract used by Jira

#### Scenario: Grafana requests a daily metric
- **WHEN** Grafana requests daily or WW-bucketed chart data
- **THEN** the response SHALL come from Metrics-approved aggregate rows, materialized views or chart-data APIs, and SHALL NOT require Grafana to execute Jira JQL, HSD-ES EQL, provider custom-field mapping, standard-bug classification or count aggregation logic

#### Scenario: Aggregate calculation rules change
- **WHEN** the definition of standard bug, bucket grain, field binding, chart recipe or source population changes
- **THEN** subsequent aggregate rows SHALL record a new chart version, mapping version, source query version, fact snapshot id or calculation run id sufficient for Grafana and AI to distinguish the new results from older results

### Requirement: Live provider sync materializes facts before dashboard use
Live provider sync SHALL convert external provider search/detail results into durable local facts and approved aggregate artifacts before those facts are used by Grafana, Metrics UI or AI dashboard answers。

#### Scenario: Live sync succeeds for a provider profile
- **WHEN** a provider profile live sync fetches work item data from its external provider
- **THEN** the system SHALL persist provider raw snapshot provenance、normalized facts、source query identity、field-set hash、mapping version、sync cursor/freshness metadata and generated aggregate artifacts before marking the profile data current

#### Scenario: Dashboard renders after live sync
- **WHEN** Grafana renders a provider-backed chart after live sync has succeeded
- **THEN** chart data SHALL be read from matching local aggregate artifacts and SHALL include provider/profile/source/snapshot freshness metadata

#### Scenario: Dashboard renders before live sync is configured
- **WHEN** a selected profile has no configured live backend credential or required provider configuration
- **THEN** chart APIs SHALL return seeded-preview, configuration-required, stale or unavailable state according to available local artifacts, and SHALL NOT infer backend readiness from browser SSO

### Requirement: HSD-ES saved query uses the generic live sync contract
The first live HSD-ES implementation SHALL use the same provider-neutral sync/cache/facts contract as other providers while preserving HSD-ES native provenance inside the adapter boundary。

#### Scenario: HSD-ES NVU saved query is synced
- **WHEN** live sync runs for profile `nvu-ttl-hsdes`
- **THEN** sync SHALL use the configured HSD-ES source query `queryId=15017652869` as the source population, preserve tenant、subject、query id、criteria/hash、field set、permission assumptions and observed result contract, and emit normalized facts compatible with the existing provider chart aggregate contract

#### Scenario: HSD-ES API behavior is uncertain
- **WHEN** implementation needs endpoint shape、auth mode、pagination、field expansion、permission behavior、saved-query execution semantics or response schema details
- **THEN** implementers SHALL consult the authoritative Intel HSD-ES API documentation or project-owner-provided source before coding or changing the provider contract

#### Scenario: HSD-ES browser access exists
- **WHEN** an operator can view or download the saved query data in a browser
- **THEN** the system SHALL treat that as user access evidence only and SHALL still require backend sync credentials/configuration before live synced dashboard data is claimed

### Requirement: Provider sync preserves previous successful artifacts on failure
Provider sync SHALL never replace a previously successful fact snapshot or aggregate artifact with empty or partial data unless the new artifact is explicitly marked complete and authoritative。

#### Scenario: Provider returns partial or failed data
- **WHEN** a provider sync receives timeout, auth failure, permission failure, rate-limit response, schema drift, partial page, malformed payload or projection error
- **THEN** the system SHALL record failed sync status and error category, preserve previous successful artifacts, and expose stale or unavailable status rather than silently publishing incomplete current data

#### Scenario: Mapping drift is detected
- **WHEN** live provider data no longer matches the profile's expected field set, source query hash, tenant/space, subject/item type or mapping version
- **THEN** sync SHALL mark the profile or snapshot drifted/configuration-required and SHALL NOT publish current aggregate artifacts until the profile is reviewed or refreshed

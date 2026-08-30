## ADDED Requirements

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

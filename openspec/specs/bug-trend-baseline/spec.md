# Bug Trend Baseline Specification

## Purpose

Bug Trend Baseline 定义当前已落地的 Jira bug trend durable analytics 能力，包括 saved scope、sync/history、calculation artifacts、evidence、audit、chart catalog、Grafana-compatible payload 和 AI chart draft governance。

## Requirements

### Requirement: Saved Jira scope config owns project-specific semantics
系统 SHALL 使用 saved Jira scope config 作为 bug trend 的 project-specific semantic authority，包括 JQL、IP label、project label、bug type values、status/resolution lifecycle mappings、severity mappings、field mappings、display fields、timezone、bucket granularity、enabled state 和 config version hash。

#### Scenario: User saves scope semantics
- **WHEN** 用户创建、修改、启用或禁用一个 Jira bug trend scope
- **THEN** 系统 SHALL normalize list fields、validate required fields、persist semantic values、calculate config version hash，并记录 scope audit event

#### Scenario: Scope semantics change
- **WHEN** JQL、status mapping、severity mapping、field mapping、timezone 或 bucket granularity 改变
- **THEN** 系统 SHALL 产生新的 config version hash，使旧 calculation runs 不再作为当前 chart 的 authoritative result

### Requirement: Jira sync materializes durable history before charting
系统 SHALL 通过 explicit Jira scope sync 将 saved scope 的 Jira issues、raw snapshots、status/resolution transitions 和 sync cursor materialize 到本地 durable store。

#### Scenario: Full scope sync runs
- **WHEN** operator 对 saved scope 执行 full sync
- **THEN** 系统 SHALL 使用 scope JQL 和 scope field mappings 拉取 Jira payload、清理当前 scope state、存储 snapshots/issues/transitions、记录 reliable coverage window，并触发 calculation run

#### Scenario: Incremental sync runs
- **WHEN** operator 对已有 cursor 的 saved scope 执行 incremental sync
- **THEN** 系统 SHALL 使用 updated overlap query、同步当前匹配 issues、检查已知 issue 的 out-of-scope changes，并拒绝 config hash 不匹配或 coverage expansion 的 unsafe incremental sync

### Requirement: Calculation runs produce stable bug trend artifacts
系统 SHALL 为每次 successful recalculation 写入 calculation run、bucket aggregates 和 bucket issue memberships，并以同一个 calculation run identity 连接 chart count 与 evidence rows。

#### Scenario: Bug trend buckets are calculated
- **WHEN** saved scope 在 coverage window 内完成 recalculation
- **THEN** 系统 SHALL 生成 daily 或 weekly buckets，并计算 `all_open_bugs`、`all_open_critical_high`、`new_critical_high`、`new_medium_low` 和 `fixed_or_closed_bugs` series 中启用且可计算的 counts

#### Scenario: Severity mapping is unavailable
- **WHEN** saved scope 没有配置 severity field 或 critical/high values
- **THEN** 系统 SHALL 不凭空推断 critical/high series，并只暴露 scope semantics 支持的 active series

### Requirement: Chart queries require fresh matching coverage
系统 SHALL 只把 status completed、config version hash 匹配当前 scope、且 source coverage 覆盖请求 date range 的 calculation run 作为当前 chart 的 authoritative source。

#### Scenario: No completed run covers selected range
- **WHEN** 用户请求一个没有 completed matching run 覆盖的 date range
- **THEN** 系统 SHALL 返回 empty chart payload 和 clear unavailable reason，而不是 live-query Jira 或显示不完整 counts

#### Scenario: Latest run is stale after config edit
- **WHEN** latest completed run 的 config version hash 与当前 scope 不一致
- **THEN** 系统 SHALL 返回 stale-config metadata 和 unavailable reason，并要求重新 sync/recalculate 后再作为当前结果展示

### Requirement: Evidence drilldown and export are run-pinned
系统 SHALL 通过 calculation run id、bucket id、series name 和 visible range 查询 persisted bucket issue memberships，并支持 evidence list filtering 与 CSV export audit。

#### Scenario: User selects a chart bucket and series
- **WHEN** 用户从 chart 选择一个 bucket/series
- **THEN** 系统 SHALL 返回同一个 calculation run 和 bucket artifact 下的 issue evidence rows，包括 issue key、source URL、summary、series、status、severity、owner、component、timestamps 和 configured extra fields

#### Scenario: User exports evidence
- **WHEN** 用户导出 evidence tickets
- **THEN** 系统 SHALL 输出 CSV 内容并记录包含 actor、scope、calculation run、chart id、range、filters 和 row count 的 audit event

### Requirement: Scope audit exposes mapping coverage
系统 SHALL 提供 scope audit 能力，把 durable Jira history 中观察到的 issue type、status、resolution、severity 和 component values 与 saved scope mappings 对比。

#### Scenario: User audits a scope
- **WHEN** 用户打开 bug trend scope audit
- **THEN** 系统 SHALL 展示 observed values、counts、mapped state、mapping group 和 coverage counts，使 scope owner 能发现未映射或异常 provider values

### Requirement: Data health exposes calculation freshness
系统 SHALL 提供 data health view/API，展示 enabled scopes 的 latest calculation status、freshness、run hash、current hash、coverage range 和 completed time。

#### Scenario: Dashboard health is inspected
- **WHEN** 用户打开 Data Health 页面
- **THEN** 系统 SHALL 区分 no run、fresh、stale config、running 和 failed 状态

### Requirement: Chart catalog governs renderable and AI-created charts
系统 SHALL 通过 chart catalog 管理 enabled/published chart definitions、evidence contracts、renderer route decisions、AI chart drafts 和 publish governance。

#### Scenario: AI creates a chart draft
- **WHEN** AI workflow 创建 Bug Trend chart draft
- **THEN** 系统 SHALL validate chart spec 不包含 SQL、secrets 或 direct data-source logic，要求引用 Metrics-owned evidence contract，并把 draft 置为 unpublished/personal state

#### Scenario: Chart is published
- **WHEN** chart 被请求发布
- **THEN** 系统 SHALL validate renderer type、integration route、evidence contract 和 series references；personal governance MAY publish directly, cloud governance SHALL create pending approval request

### Requirement: Grafana-compatible data surface is derived from Metrics facts
系统 SHALL 从 Metrics-owned chart payload 派生 Grafana-compatible rows，而不是让 Grafana panel query 直接拥有 Jira semantics 或 SQL logic。

#### Scenario: Grafana-compatible payload is requested
- **WHEN** consumer 读取 Bug Trend chart payload 中的 Grafana rows
- **THEN** 每一行 SHALL 包含 calculation run id、bucket id、bucket label、bucket start/end、bucket granularity 和每个 exposed series 的 count

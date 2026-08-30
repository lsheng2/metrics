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

## ADDED Requirements

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

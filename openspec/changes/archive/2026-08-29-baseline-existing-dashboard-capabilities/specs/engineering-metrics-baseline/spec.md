## Purpose

Engineering Metrics Baseline 定义当前 scrum dashboard 已经提供的 work item、forecast、velocity 和 pull request review 能力，确保后续 provider platform、Grafana 和 AI work 不会覆盖或误判这些既有功能。

## ADDED Requirements

### Requirement: Work item search supports Jira and Azure providers
系统 SHALL 通过 task module 的 public search capabilities 支持 Jira 和 Azure DevOps work item 查询，并返回 provider-neutral task domain objects。

#### Scenario: Consumer searches tasks
- **WHEN** UI、forecast 或 pull request workflow 通过 task search API 请求 tasks
- **THEN** 系统 SHALL 返回 task identity、title、status、assignment、metadata、story points、time tracking 和 requested enrichment 中可用的数据

#### Scenario: Consumer requests tasks by id
- **WHEN** consumer 通过 task ids 请求一组 tasks
- **THEN** 系统 SHALL 使用 provider adapter 获取对应 items，并按同一 task domain contract 返回结果

### Requirement: Current Tasks page supports staged task operations
系统 SHALL 提供 Current Tasks dashboard，把 tasks 按 member group 和 workflow stage 组织，并支持 lazy loading、filtering、sorting、available members 和 child-task expansion。

#### Scenario: Lazy current tasks board renders first paint
- **WHEN** lazy loading 被启用且用户打开 Current Tasks 页面
- **THEN** 系统 SHALL 先渲染不含昂贵 time tracking/changelog enrichment 的结构化 stage skeleton，并在 stage 展开时加载该 stage rows

#### Scenario: User applies task filters
- **WHEN** 用户提交 Current Tasks filter form
- **THEN** 系统 SHALL 以 AND 语义应用已配置 task filter fields，并在选择需要 enrichment 的 health filter 时切换到 full fetch path

### Requirement: Forecast page exposes task completion risk and scope control
系统 SHALL 提供 task forecast 能力，为 active-only 或 all tasks 生成 forecast、health、remaining work 和 completion-oriented summary。

#### Scenario: User includes completed tasks
- **WHEN** 用户在 Task Forecast 页面选择包含 completed tasks
- **THEN** 系统 SHALL 使用对应 task scope 生成 forecast，并在 UI 中区分 completed 与 remaining work

### Requirement: Velocity pages expose team and developer trends
系统 SHALL 提供 team velocity 和 developer velocity 页面，并支持 member group filtering、rolling average、story point chart 和 task detail partial。

#### Scenario: User changes velocity filter
- **WHEN** 用户调整 velocity 页面中的 member group、rolling average 或 task inclusion control
- **THEN** 系统 SHALL 通过对应 partial endpoint 返回更新后的 chart 或 task detail 数据

### Requirement: Pull request dashboard exposes review state and gates
系统 SHALL 提供 Pull Requests dashboard，从 Azure Repos 或 Bitbucket 读取 open pull requests，并展示 author activity、linked ticket、reviewer approval chips、internal gate 和 required reviewer gate。

#### Scenario: Jira tracker uses Bitbucket pull requests
- **WHEN** active tracker 为 Jira
- **THEN** 系统 SHALL 使用 Bitbucket workspace、repositories 和 app password configuration 查询 PR，并通过 task search API 解析 linked ticket

#### Scenario: Azure tracker uses Azure Repos pull requests
- **WHEN** active tracker 为 Azure DevOps
- **THEN** 系统 SHALL 使用 Azure configuration 查询 PR，并保留 Azure pagination 去重行为，避免 short page 或 overlapping page 导致遗漏或重复

### Requirement: Engineering dashboard behavior is configuration-driven
系统 SHALL 通过 environment-backed configuration 管理 tracker、members、member groups、workflow stages、status mappings、release/iteration fields、sort criteria、task filters 和 PR review gate thresholds。

#### Scenario: Project changes custom field names
- **WHEN** project owner 修改 release、iteration、story point、sort 或 filter field configuration
- **THEN** 系统 SHALL 通过配置解析这些字段，而不是要求修改 dashboard business logic

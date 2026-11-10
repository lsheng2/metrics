# Spec Delta

## ADDED Requirements

### Requirement: Workbench runs as one local Metrics server
本地运行路径 SHALL 只启动 Metrics 和 Grafana：Metrics 由 `manage.py serve` 启动，同一进程服务 Django 和嵌入的 AI 运行时；用户只打开统一的 workbench。launcher SHALL NOT 启动、停止或探测任何 AI Base 进程或端口；workbench SHALL NOT 在渲染请求时启动任何进程。

#### Scenario: Local launcher starts the stack
- **WHEN** 用户运行 unified workbench local launcher
- **THEN** launcher SHALL 用 `manage.py serve` 启动或检测 Metrics，并启动或检测 Grafana
- **AND** launcher SHALL open one workbench URL
- **AND** launcher SHALL expose service health/status inside the workbench instead of asking the user to manually manage multiple browser windows
- **AND** launcher SHALL use one lifecycle state source for start, stale-process cleanup, boot-log audit and process-inventory audit
- **AND** launcher SHALL NOT clean up the current Metrics or Grafana process tree after smoke checks have proven them ready

#### Scenario: AI model is not configured
- **WHEN** Metrics 经 `manage.py serve` 启动，但没有配置 AI 模型
- **THEN** workbench SHALL 仍然支持图表、证据、设置、发布历史和诊断页面
- **AND** AI pane SHALL 显示 `not_configured`，列出缺少的设置项名称，SHALL NOT 显示设置值

#### Scenario: AI chat is embedded in the workbench
- **WHEN** AI pane 状态是 `ready`，workbench 渲染 AI assistant pane
- **THEN** pane SHALL 渲染一个同源 iframe，指向运行时在 `<URL 前缀>/ai` 下提供的嵌入聊天页
- **AND** 页面 SHALL 加载 `ui.asset_url` 返回的 `embed-host.js`，并通过它把当前亮色或暗色主题同步给 iframe
- **AND** 嵌入聊天 SHALL 是侧栏形态，SHALL NOT 显示完整应用导航、会话列表、会话文件面板或状态栏

#### Scenario: Embedded chat is bound to the workbench context
- **WHEN** workbench 为 binding 已解析的 scope 渲染 AI pane
- **THEN** `ai_host` SHALL 为当前 principal、app `metrics` 和由 profile 推导的 session key `metrics.workbench.<profile_id>` 打开或恢复会话，并绑定当前 `ContextRef`
- **AND** 同一 principal 再次打开同一 profile 的 workbench 时 SHALL 恢复同一个会话
- **AND** iframe URL 和页面 SHALL NOT 包含 token、credential ref 或 actor 身份
- **AND** 嵌入聊天 SHALL 使用 Metrics agent，SHALL NOT 提供 agent、app 或会话选择控件
- **AND** scope 变化时 shell SHALL 只向 iframe 发送新的 `ContextRef`

### Requirement: AI pane diagnostics separate scope binding from runtime readiness
Workbench AI pane SHALL 区分三类问题：scope binding 未解析、AI 模型未配置、进程不是经 `manage.py serve` 启动。scope binding 未解析时，AI pane SHALL 先指向 Scope Library 的 binding 修复入口，SHALL NOT 继续使用之前 scope 的 `ContextRef`。

#### Scenario: Runtime is not ready for a resolved binding
- **WHEN** scope binding 已解析，但 AI pane 状态是 `not_configured` 或 `not_running`
- **THEN** AI pane SHALL 显示当前 scope binding 状态、profile 和 provider
- **AND** AI pane SHALL 区分"配置 AI 模型"和"用 `manage.py serve` 启动"两种下一步操作

#### Scenario: Scope binding is unresolved
- **WHEN** 当前 scope binding 是 configuration_required 或 ambiguous
- **THEN** AI pane SHALL 显示 Scope Library 的 binding 修复入口，不渲染聊天
- **AND** shell SHALL NOT 向 iframe 发送之前 scope 的 `ContextRef`

## MODIFIED Requirements

### Requirement: PageQueryState is normalized through a server-side binding resolver
Workbench shell SHALL own shared PageQueryState for canonical scope/range/chart/selection/list-filter state, while server-side binding resolution SHALL derive profile、provider 和 AI `ContextRef` from the selected scope or selected provider profile. Workbench SHALL NOT treat profile/provider display fields as independent query authority when a canonical scope binding is available.

#### Scenario: User changes profile or range
- **WHEN** 用户修改 provider profile、provider-derived scope、range mode、begin/end 或 chart filter
- **THEN** shell SHALL update PageQueryState
- **AND** shell SHALL clear selected bucket and selected series
- **AND** chart pane and evidence pane SHALL refresh from the updated state

#### Scenario: User changes scope
- **WHEN** 用户在 workbench toolbar 选择不同 scope
- **THEN** shell SHALL immediately submit or HTMX-refresh the workbench using `scope_id` as the user-selected authority
- **AND** server-side PageQueryState normalization SHALL resolve `profile_id`、`provider_id` and the AI `ContextRef` from the selected scope binding
- **AND** profile/provider controls SHALL be rendered as read-only derived display fields, without `name` attributes in the primary toolbar form
- **AND** applying the toolbar SHALL refresh chart, evidence and AI panes for the resolved scope binding

#### Scenario: Workbench receives stale profile or provider query parameters
- **WHEN** a URL, local storage restore, AI host action or legacy bookmark includes `profile_id` or `provider_id` that contradict the selected `scope_id`
- **THEN** server-side normalization SHALL ignore the stale profile/provider values for provider-backed state and use the selected scope binding
- **AND** the shell SHALL generate a canonical pushed URL that omits derived profile/provider parameters when `scope_id` is present
- **AND** downstream chart, evidence, Grafana panel and AI context requests SHALL use only the normalized binding values

#### Scenario: Scope binding requires configuration
- **WHEN** selected scope has no safe explicit or compatibility binding to a provider profile
- **THEN** Workbench SHALL display a configuration-required state for provider-backed panes
- **AND** the state SHALL identify the selected scope and the missing binding action
- **AND** Workbench SHALL NOT keep rendering stale profile/provider values from a previously selected scope

#### Scenario: User changes evidence list filter
- **WHEN** 用户修改 text、status、severity、owner、component 或其它 list-local filter
- **THEN** shell SHALL update only list-local filter state
- **AND** active chart query SHALL remain unchanged
- **AND** evidence pane SHALL refresh within the current chart/range/selection

#### Scenario: User configures the evidence table view
- **WHEN** 用户选择 evidence table 可见字段或多字段排序
- **THEN** shell SHALL update evidence table view state without changing Metrics provider facts
- **AND** evidence pane SHALL keep the controls close to the table header rather than opening a separate settings page
- **AND** table view state SHALL NOT mutate chart bucket/series selection

#### Scenario: User selects tickets as a working set
- **WHEN** 用户勾选一个或多个 ticket rows
- **THEN** shell SHALL track selected tickets as an explicit working set
- **AND** selected tickets MAY be used by local bulk actions or AI grounding
- **AND** selected tickets SHALL remain distinct from chart bucket/series selection and evidence filters

#### Scenario: User opens a ticket detail pane
- **WHEN** 用户点击单个 ticket row
- **THEN** evidence pane SHALL open a local ticket detail pane inside the evidence window
- **AND** detail pane SHALL render normalized ticket fields, summary, latest activity, links and local actions from Metrics/provider APIs
- **AND** detail pane SHALL NOT embed the full Jira/HSD-ES browser page or depend on external provider cookies/session navigation
- **AND** full Jira/HSD-ES UI MAY be opened through an explicit external link

### Requirement: Workbench state is normalized through explicit scope bindings
Workbench shell SHALL own shared PageQueryState for canonical scope/range/chart/selection/list-filter state, while server-side binding resolution SHALL derive profile、provider 和 AI `ContextRef` from the selected scope or selected provider profile. Workbench SHALL NOT treat profile/provider display fields as independent query authority when a canonical scope binding is available.

#### Scenario: User changes profile or range
- **WHEN** 用户修改 provider profile、provider-derived scope、range mode、begin/end 或 chart filter
- **THEN** shell SHALL update PageQueryState
- **AND** shell SHALL clear selected bucket and selected series
- **AND** chart pane and evidence pane SHALL refresh from the updated state

#### Scenario: User changes scope
- **WHEN** 用户在 workbench toolbar 选择不同 scope
- **THEN** shell SHALL immediately submit or HTMX-refresh the workbench using `scope_id` as the user-selected authority
- **AND** server-side PageQueryState normalization SHALL resolve `profile_id`、`provider_id` and the AI `ContextRef` from the selected scope binding
- **AND** profile/provider controls SHALL be rendered as read-only derived display fields, without `name` attributes in the primary toolbar form
- **AND** applying the toolbar SHALL refresh chart, evidence and AI panes for the resolved scope binding

#### Scenario: Workbench receives stale profile or provider query parameters
- **WHEN** a URL, local storage restore, AI host action or legacy bookmark includes `profile_id` or `provider_id` that contradict the selected `scope_id`
- **THEN** server-side normalization SHALL ignore the stale profile/provider values for provider-backed state and use the selected scope binding
- **AND** the shell SHALL generate a canonical pushed URL that omits derived profile/provider parameters when `scope_id` is present
- **AND** downstream chart, evidence, Grafana panel and AI context requests SHALL use only the normalized binding values

#### Scenario: Scope binding requires configuration
- **WHEN** selected scope has no safe explicit or compatibility binding to a provider profile
- **THEN** Workbench SHALL display a configuration-required state for provider-backed panes
- **AND** the state SHALL identify the selected scope and the missing binding action
- **AND** Workbench SHALL NOT keep rendering stale profile/provider values from a previously selected scope

## REMOVED Requirements

### Requirement: Workbench supports one-window local runtime
**Reason**: launcher 不再管理 AI Base 进程，AI 也不再能被启用或禁用；原 scenario "Optional AI Base is disabled" 和 "AI Base compact embed runs in Dashboard app context" 以 sidecar、workspace key 为前提。
**Migration**: 由 "Workbench runs as one local Metrics server" 承接：launcher 只管理 Metrics 和 Grafana；嵌入聊天是同源 iframe，会话按 profile 绑定 `ContextRef`。

### Requirement: AI pane diagnostics include scope binding state
**Reason**: 原 scenario "AI workspace is not synced for a resolved binding" 以 workspace 同步为前提，workspace 已删除。
**Migration**: 由 "AI pane diagnostics separate scope binding from runtime readiness" 承接；scope binding 优先于 AI 就绪操作的规则保留。

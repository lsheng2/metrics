## Purpose

Unified Metrics Workbench UI 定义一个 Dashboard-owned single Web UI，用于把 Metrics charts、Grafana panels、Jira/HSD-ES evidence lists、AI chat、settings、publish 和 audit surfaces 组织在同一个可组合工作台中，同时保持 Metrics 后端对 state、evidence 和 authority 的所有权。

## ADDED Requirements

### Requirement: Workbench shell provides one application entry point
系统 SHALL 提供一个 unified workbench entry point，使用户可以在同一个 Web UI 内访问 chart、evidence、AI chat、settings、publish 和 audit surfaces，而不需要分别打开 Django、Grafana 和 AI Base 三个浏览器窗口。

#### Scenario: User opens the workbench
- **WHEN** 用户访问 unified workbench URL
- **THEN** 系统 SHALL 渲染包含全局 toolbar、primary chart region、evidence region、AI assistant region 和 utility/settings region 的单一 application shell
- **AND** shell SHALL 显示当前 profile、provider、range、active chart 和 evidence support 状态

#### Scenario: One dependent service is unavailable
- **WHEN** Grafana、AI Base 或某个 provider sync service 不可用
- **THEN** workbench SHALL 保持 shell 可用
- **AND** 对应 pane SHALL 显示 scoped unavailable 状态和 next action
- **AND** 其它可用 pane SHALL NOT 被整个页面失败阻断

### Requirement: Workbench panes are explicit and replaceable
系统 SHALL 用 pane registry 描述 workbench 可挂载 surface，包括 chart pane、ticket evidence pane、AI chat pane、Django settings pane、publish approval pane、audit/history pane 和 diagnostics pane。

#### Scenario: Pane is mounted in a placeholder
- **WHEN** shell 根据默认 layout 或用户保存 layout 加载 pane
- **THEN** 系统 SHALL 根据 pane id、title、capability、source type、URL/API target 和 allowed placement 渲染 pane
- **AND** pane SHALL NOT 通过未声明的全局变量或跨模块 private API 读取业务数据

#### Scenario: Pane is moved or resized
- **WHEN** 用户调整 pane placement、size、tab group 或 visibility
- **THEN** shell SHALL 保持当前 PageQueryState 不变
- **AND** shell MAY 保存 layout preference
- **AND** evidence selection SHALL NOT 因纯 layout 操作被清除

#### Scenario: User resets layout
- **WHEN** 用户选择 reset layout
- **THEN** shell SHALL 恢复默认工作台布局
- **AND** shell SHALL 保留当前 profile/range/chart selection unless the reset action explicitly says it also resets query state

### Requirement: PageQueryState is the shared source of truth
Workbench shell SHALL own shared PageQueryState for profile、provider、range、active chart、calculation run or fact snapshot、selected bucket、selected series 和 list-local filters.

#### Scenario: User changes profile or range
- **WHEN** 用户修改 profile、provider-derived scope、range mode、begin/end 或 chart filter
- **THEN** shell SHALL update PageQueryState
- **AND** shell SHALL clear selected bucket and selected series
- **AND** chart pane and evidence pane SHALL refresh from the updated state

#### Scenario: User changes evidence list filter
- **WHEN** 用户修改 text、status、severity、owner、component 或其它 list-local filter
- **THEN** shell SHALL update only list-local filter state
- **AND** active chart query SHALL remain unchanged
- **AND** evidence pane SHALL refresh within the current chart/range/selection

### Requirement: Chart selection can drive ticket evidence
Workbench SHALL allow evidence-backed chart interactions to update the ticket evidence pane through a Metrics-validated selection contract.

#### Scenario: User selects an evidence-backed bucket series point
- **WHEN** 用户点击支持 `bucket_series` evidence 的 chart point、bar 或 linked Grafana data point
- **THEN** shell SHALL receive or resolve selected calculation run or fact snapshot, bucket id and series name
- **AND** shell SHALL request Metrics evidence API with chart id, chart version, profile/range and selected bucket/series
- **AND** evidence pane SHALL render only Jira/HSD-ES tickets belonging to that validated selection

#### Scenario: Grafana chart is displayed in primary chart pane
- **WHEN** workbench displays a Grafana-rendered chart in the primary chart region
- **THEN** shell SHALL prefer compact chart/panel-only embed sized to the pane
- **AND** shell SHALL NOT require users to interact with the full Grafana dashboard UI for normal chart-to-evidence analysis

#### Scenario: User clears chart selection
- **WHEN** 用户清除 selected bucket/series
- **THEN** shell SHALL remove selected bucket and selected series from PageQueryState
- **AND** evidence pane SHALL return to the active chart default evidence state for the visible range

#### Scenario: Selection cannot be validated
- **WHEN** chart selection references an unknown run、snapshot、bucket、series、chart id、profile or range
- **THEN** Metrics SHALL reject or ignore the selection
- **AND** evidence pane SHALL show a validation failure state
- **AND** shell SHALL NOT display stale ticket rows as if they belonged to the selected chart point

### Requirement: Charts declare evidence capability
每个 chart definition exposed in the workbench SHALL declare whether it supports `bucket_series`、`range_only`、`summary_only` 或 `unsupported` evidence behavior.

#### Scenario: Active chart supports bucket series evidence
- **WHEN** active chart declares `bucket_series`
- **THEN** shell SHALL enable point-level drilldown affordances
- **AND** evidence pane SHALL describe the current bucket/series selection when selected

#### Scenario: Active chart supports only range evidence
- **WHEN** active chart declares `range_only`
- **THEN** shell SHALL render evidence for the current visible range
- **AND** shell SHALL NOT present point-level drilldown as available

#### Scenario: Active chart does not support ticket evidence
- **WHEN** active chart declares `summary_only` or `unsupported`
- **THEN** evidence pane SHALL show an explicit unsupported or summary-only state
- **AND** it SHALL clear any previous ticket rows that came from another chart

### Requirement: Workbench supports one-window local runtime
系统 SHALL provide a local runtime path that starts required Dashboard, Grafana and optional AI Base services but opens only the unified workbench UI for the user.

#### Scenario: Local E2E launcher starts the stack
- **WHEN** 用户运行 unified workbench local launcher
- **THEN** launcher SHALL start or detect Dashboard, Grafana and optional AI Base services
- **AND** launcher SHALL open one workbench URL
- **AND** launcher SHALL expose service health/status inside the workbench instead of asking the user to manually manage three browser windows

#### Scenario: Optional AI Base is disabled
- **WHEN** AI Base is disabled or not configured
- **THEN** workbench SHALL still support charts、evidence、settings、publish/audit and diagnostics surfaces
- **AND** AI pane SHALL render an unavailable or disabled state without blocking the rest of the app

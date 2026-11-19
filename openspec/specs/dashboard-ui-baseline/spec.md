# Dashboard UI Baseline Specification

## Purpose

Dashboard UI Baseline 定义当前 Django metrics dashboard 已经对用户暴露的页面、partial、facade federation 和前端技术边界，作为后续 Grafana-first 和 AI dashboard 变更的现有系统基线。

## Requirements

### Requirement: Server-rendered dashboard page surface
系统 SHALL 以 Django server-rendered 页面提供当前 dashboard surface，包括 homepage、current tasks、team velocity、developer velocity、task forecast、pull requests、bug trend、data health、bug trend scope audit、scope library 和 scope config 页面。

#### Scenario: User opens a full dashboard page
- **WHEN** 用户访问当前 dashboard 的 full page URL
- **THEN** 系统 SHALL 通过 Django view 渲染对应页面，并使用 configured base URL prefix 保持部署路径一致

#### Scenario: Existing page list is used as baseline
- **WHEN** 后续 OpenSpec change 规划 Grafana-first 或 AI-enhanced dashboard
- **THEN** 该 change SHALL 显式说明会保留、替换或迁移哪些当前 Django 页面，而不是假设页面不存在

### Requirement: HTMX partials load independent dashboard components
系统 SHALL 使用 HTMX partial endpoint 独立加载可单独失败、刷新或延迟加载的组件，包括：

- current tasks stage rows
- available members
- child tasks
- task PR gateway
- pull request review state
- velocity tasks drilldown
- bug trend evidence
- bug trend scope metadata

Velocity 图表 SHALL 随所在页面内容一起渲染，不再作为单独的 partial 加载。

#### Scenario: A current-tasks stage is expanded
- **WHEN** 用户展开 current tasks 页面中的一个 workflow stage
- **THEN** 系统 SHALL 只加载该 stage 的 task rows，其它 stage 和页面 shell SHALL NOT 重新渲染

#### Scenario: A component request fails
- **WHEN** 某个 partial 的数据源不可用，或 facade 抛出错误
- **THEN** 系统 SHALL 把失败限制在该组件自身的渲染范围内，SHALL NOT 将整个 dashboard surface 判定为不可用

#### Scenario: User drills into velocity tasks
- **WHEN** 用户在 team velocity 或 developer velocity 页面中选择一个周期或成员
- **THEN** 系统 SHALL 只通过 velocity tasks partial 加载对应的任务明细
- **AND** 页面中已渲染的 velocity 图表 SHALL NOT 重新请求

### Requirement: UI layer federates through facades
UI layer SHALL 通过 facade methods 获取每个页面或组件的数据，并通过模块 public APIs 聚合 tasks、forecast、velocity、pull request、bug metrics、sync 和 history 数据。

#### Scenario: Page needs data from multiple modules
- **WHEN** 一个页面需要 task、forecast、velocity 或 pull request enrichment
- **THEN** UI facade SHALL 调用 owning module 的 public API 或 container-provided API，而不是直接访问另一个 module 的 private domain/out layer

### Requirement: Existing frontend stack remains the baseline
当前 Django dashboard baseline SHALL 以 semantic HTML、Meridian design system、HTMX、Chart.js 和 chartjs-plugin-annotation 作为页面、交互和图表的基础。

#### Scenario: A baseline page adds or updates an interactive component
- **WHEN** 新增或修改的组件属于当前 Django dashboard baseline
- **THEN** 系统 SHALL 优先使用 server-rendered template、Meridian primitives、HTMX partial refresh 和 Chart.js chart payload
- **AND** 系统 SHALL NOT 引入以下任何一项：
  - React 或 Vue
  - Tailwind runtime 或其他平行的 CSS framework
  - ECharts 或 Plotly
  - 平行的 chart abstraction

### Requirement: Dashboard data APIs expose chart and evidence payloads
系统 SHALL 为 Bug Trend chart 和 evidence 提供 JSON API surface，使页面内 Chart.js、Grafana compatibility checks 或外部验证脚本可以消费稳定 payload。

#### Scenario: Chart data API is requested
- **WHEN** consumer 请求 chart data API
- **THEN** 系统 SHALL 返回 scope id、chart id、contract version、calculation run id、bucket ids、datasets、Grafana rows、run metadata 和 unavailable reason

#### Scenario: Evidence API is requested
- **WHEN** consumer 请求 evidence API
- **THEN** 系统 SHALL 返回与请求 run/range/selection 对应的 ticket rows、display fields、counts 和 selection metadata

### Requirement: Existing Dashboard surfaces are pane-compatible
当前 Django dashboard surfaces SHALL be reusable inside the unified workbench shell without duplicating business logic or bypassing facade/module boundaries.

#### Scenario: Workbench mounts an existing Dashboard page surface
- **WHEN** workbench loads a Django-owned page or component such as Bug Trend evidence、scope config、data health、publish history or diagnostics
- **THEN** the surface SHALL be delivered through an explicit pane route, partial, or view mode
- **AND** it SHALL continue to obtain data through UI facades and owning module public APIs

#### Scenario: Pane refreshes a Django partial
- **WHEN** a workbench pane refreshes after PageQueryState changes
- **THEN** only the pane or its target partial SHALL be replaced
- **AND** unrelated panes SHALL preserve their scroll position, form state and layout unless the new query state invalidates them

#### Scenario: Evidence pane opens ticket detail
- **WHEN** a user clicks a ticket row inside the evidence pane
- **THEN** Dashboard SHALL render a local ticket detail partial or JSON-backed view using Dashboard/provider APIs
- **AND** the detail pane SHALL NOT iframe the full Jira/HSD-ES web UI
- **AND** closing or resizing the detail pane SHALL preserve the evidence list and current selected ticket working set

#### Scenario: A full page remains directly accessible
- **WHEN** 用户访问 legacy/full-page Dashboard URL
- **THEN** system SHALL continue to render the existing page unless that page has an approved migration path
- **AND** the page SHALL link or redirect to the workbench only when the target workbench behavior is functionally equivalent

### Requirement: Workbench shell preserves Dashboard UI technology baseline
Workbench shell SHALL 为 Dashboard-owned surfaces 保留现有的 Dashboard baseline：server-rendered Django、semantic HTML、Meridian design system 和 HTMX。同时，为了组合 pane，允许引入一个范围严格受限的 client-side dock layout layer。

#### Scenario: Dashboard-owned pane needs dynamic refresh
- **WHEN** a Dashboard-owned pane refreshes chart state, evidence rows, settings or publish/audit content
- **THEN** it SHALL prefer server-rendered HTML or JSON-backed HTMX/vanilla browser behavior consistent with the existing Dashboard UI baseline
- **AND** it SHALL NOT require rewriting existing Dashboard pages into a new frontend framework

#### Scenario: Dock layout layer is introduced
- **WHEN** implementation adds a dock/window frame dependency for pane placement
- **THEN** the dependency SHALL be isolated to shell layout responsibilities
- **AND** Dashboard-owned domain interactions SHALL remain in existing views, facades, APIs and templates

#### Scenario: Native splitters are sufficient
- **WHEN** resizable chart/evidence、evidence/detail and main/AI boundaries can be implemented with scoped CSS and vanilla browser behavior
- **THEN** implementation SHOULD prefer the native splitter path over adding a dock dependency
- **AND** any persisted layout state SHALL remain separate from provider query state and business filters

### Requirement: Data Health exposes scope binding health
Data Health SHALL expose scope provider binding health so operators can identify Workbench/Grafana/AI context risks before users hit a broken scope.

#### Scenario: Operator views binding summary
- **WHEN** operator opens Data Health
- **THEN** page SHALL show counts for explicit, compatibility, configuration_required, ambiguous and disabled bindings
- **AND** page SHALL show total scopes covered by binding projection

#### Scenario: Operator views binding details
- **WHEN** binding details are rendered
- **THEN** each row SHALL show scope, status, profile, provider, provenance, blockers and a repair link to Scope Library
- **AND** compatibility/configuration-required rows SHALL be visually distinguishable from explicit rows

### Requirement: Data Health exposes explicit-only scope binding readiness
Data Health SHALL show whether the current scope binding inventory is ready for explicit-only runtime policy, separate from the current compatibility-allowed health summary.

#### Scenario: Operator views explicit-only gate
- **WHEN** operator opens Data Health
- **THEN** page SHALL show an explicit-only readiness state
- **AND** it SHALL show impacted scope count and repair guidance when not ready

#### Scenario: Operator views impacted scopes
- **WHEN** explicit-only readiness is blocked
- **THEN** Data Health SHALL list impacted scopes with status, profile, provider, provenance and blockers
- **AND** each impacted row SHALL provide a repair link to Scope Library

#### Scenario: Current runtime remains compatibility-allowed
- **WHEN** compatibility runtime is still allowed
- **THEN** Data Health SHALL distinguish current runtime health from explicit-only readiness
- **AND** compatibility bindings SHALL be warning-level until policy changes

### Requirement: Dashboard UI exposes scope binding policy and audit history
Dashboard UI SHALL make current scope binding runtime policy and recent binding changes visible to operators from the existing admin-style Dashboard surfaces.

#### Scenario: Operator views current binding policy
- **WHEN** operator opens Scope Library or Data Health
- **THEN** page SHALL show the current scope binding policy
- **AND** it SHALL distinguish compatibility-allowed runtime from explicit-only runtime

#### Scenario: Operator views binding audit history
- **WHEN** operator opens Scope Library or Data Health
- **THEN** page SHALL show recent scope binding audit events
- **AND** each event SHALL show actor, operation, scope and old/new binding state

#### Scenario: No audit events exist yet
- **WHEN** no binding audit events exist
- **THEN** page SHALL render an empty state instead of hiding the audit section

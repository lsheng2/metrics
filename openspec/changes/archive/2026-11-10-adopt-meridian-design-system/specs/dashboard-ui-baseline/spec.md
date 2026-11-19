## MODIFIED Requirements

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

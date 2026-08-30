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
系统 SHALL 使用 HTMX partial endpoint 独立加载可独立失败、刷新或延迟加载的组件，包括 current tasks stage rows、available members、child tasks、task PR gateway、pull request review state、velocity charts/tasks、bug trend evidence 和 bug trend scope metadata。

#### Scenario: A current-tasks stage is expanded
- **WHEN** 用户展开 current tasks 页面中的一个 workflow stage
- **THEN** 系统 SHALL 只加载该 stage 的 task rows，并保持其它 stage 和页面 shell 不需要重新渲染

#### Scenario: A component request fails
- **WHEN** 某个 partial 的数据源不可用或 facade 抛出错误
- **THEN** 系统 SHALL 将失败限制在该组件的 rendering context，并避免把整个 dashboard surface 定义为不可用

### Requirement: UI layer federates through facades
UI layer SHALL 通过 facade methods 获取每个页面或组件的数据，并通过模块 public APIs 聚合 tasks、forecast、velocity、pull request、bug metrics、sync 和 history 数据。

#### Scenario: Page needs data from multiple modules
- **WHEN** 一个页面需要 task、forecast、velocity 或 pull request enrichment
- **THEN** UI facade SHALL 调用 owning module 的 public API 或 container-provided API，而不是直接访问另一个 module 的 private domain/out layer

### Requirement: Existing frontend stack remains the baseline
当前 Django dashboard baseline SHALL 使用 semantic HTML、Bulma、HTMX、Chart.js 和 chartjs-plugin-annotation 作为页面、交互和图表基础。

#### Scenario: A baseline page adds or updates an interactive component
- **WHEN** 该组件属于当前 Django dashboard baseline
- **THEN** 系统 SHALL 优先使用 server-rendered template、Bulma controls、HTMX partial refresh 和 Chart.js chart payload，而不是引入 React、Vue、ECharts、Plotly 或平行 chart abstraction

### Requirement: Dashboard data APIs expose chart and evidence payloads
系统 SHALL 为 Bug Trend chart 和 evidence 提供 JSON API surface，使页面内 Chart.js、Grafana compatibility checks 或外部验证脚本可以消费稳定 payload。

#### Scenario: Chart data API is requested
- **WHEN** consumer 请求 chart data API
- **THEN** 系统 SHALL 返回 scope id、chart id、contract version、calculation run id、bucket ids、datasets、Grafana rows、run metadata 和 unavailable reason

#### Scenario: Evidence API is requested
- **WHEN** consumer 请求 evidence API
- **THEN** 系统 SHALL 返回与请求 run/range/selection 对应的 ticket rows、display fields、counts 和 selection metadata

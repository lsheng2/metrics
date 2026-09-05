# grafana-dashboard-parity Specification

## Purpose
Grafana Dashboard Parity 定义 Metrics Dashboard 最终以 Grafana 为主界面时，如何对齐 Intel HSD-ES `In-fly Indicator v2.0` 的功能水平，同时保留 Metrics 后端对 provider facts、指标语义、证据和 AI governance 的所有权。

## Requirements

### Requirement: Grafana is the primary dashboard interface
系统 SHALL 使用 Grafana 作为最终用户主 dashboard 界面和图表渲染层，并 SHALL 保留 Metrics 后端作为 provider facts、指标定义、evidence、权限、audit 和 AI governance 的 source of truth。

#### Scenario: User opens the production dashboard
- **WHEN** 用户打开最终 dashboard
- **THEN** 用户 SHALL 看到 Grafana 承载的 dashboard 页面或 Grafana App/Scenes 页面，而不是长期以 Django Chart.js 页面作为主图表界面

#### Scenario: Dashboard needs semantic data
- **WHEN** Grafana panel 查询业务数据
- **THEN** Grafana SHALL 查询 Metrics-approved facts、chart-data API、materialized view 或 approved aggregate artifact，而不是在 panel query 中自行定义 bug、valid bug、critical/high、closed、execution 或 evidence 语义

### Requirement: Reference dashboard functional parity
系统 SHALL 把参考 HSD-ES `In-fly Indicator v2.0` dashboard 的功能元素作为 parity target，但 SHALL NOT 把其 Mongo query 或 HSD-ES 数据源顺序视为本项目第一 provider 要求。

#### Scenario: Parity scope is evaluated
- **WHEN** 产品或 reviewer 检查 Grafana parity
- **THEN** 系统 SHALL 至少覆盖 `QUALITY`、`EXECUTION`、`EFFICIENCY` 三个 dashboard section，以及 component bug、rolling valid bug、open bug trend、escaped bug、execution statistics、milestone schedule、milestone progress、automation、shift-left、aging 和 total bug trend 这些 panel 级能力

#### Scenario: First wave defers unresolved semantic categories
- **WHEN** 第一版 Grafana dashboard renders panels that contain execution、automation、shift-left 或 escaped bug semantics
- **THEN** those panels SHALL render `deferred`, `configuration_required`, or `unsupported` states with reasons, and SHALL NOT display fabricated zero values or unverified Jira/HSD-ES mappings

#### Scenario: Reference query source differs from project source
- **WHEN** 参考 dashboard 使用 Mongo aggregate collections 或 HSD-ES-derived artifacts
- **THEN** 本项目 SHALL 只把它们作为目标指标形状和字段线索；第一落地实现 SHALL 从 Jira provider durable facts 生成等价指标

### Requirement: Provider-neutral dashboard variables
Grafana dashboard SHALL 使用 provider-neutral query state 来表达 scope，而不是把 Jira 或 HSD-ES 的原生术语硬编码成唯一产品概念。

#### Scenario: Jira-backed dashboard variables are rendered
- **WHEN** 第一阶段 dashboard 使用 Jira provider 数据
- **THEN** Grafana variables SHALL 表达 provider、space/project、release target or milestone、begin WW 和 end WW，并 MAY 在 label 或 hint 中显示 Jira-specific terms

#### Scenario: HSD-ES-backed dashboard variables are rendered
- **WHEN** 第二阶段 dashboard 使用 HSD-ES provider 数据
- **THEN** Grafana variables SHALL 复用同一 provider-neutral query state，并 MAY 显示 HSD-ES `tenant`、`subject`、IP、project、milestone、family、release 或 component hints

#### Scenario: Provider seed differs from dashboard variable state
- **WHEN** HSD-ES uses a saved query seed or Jira uses a configured JQL/filter as its base population
- **THEN** Grafana variables SHALL remain provider-neutral and SHALL NOT require users to understand native query criteria in order to select provider, project/product, milestone/release target, begin WW or end WW

#### Scenario: Dashboard selects a project provider profile
- **WHEN** 用户在 Grafana 中选择 provider/project scope
- **THEN** Grafana SHALL resolve the selection to a Project Provider Profile or profile-compatible query state, and SHALL leave native field binding, native query execution and value normalization to Metrics backend

#### Scenario: Profile selection derives provider and scope defaults
- **WHEN** 用户在 Grafana 中选择 `profile_id`
- **THEN** Metrics SHALL derive `provider_id`, fixed profile scope labels, source query ownership, mapping version and provider binding defaults from the selected Project Provider Profile, and Grafana SHALL NOT require the user to manually select a separate provider dropdown to keep dashboard data correct

#### Scenario: User overrides a profile-derived runtime scope field
- **WHEN** 用户临时修改由 profile 提供默认值的 scope field such as IP、project/release target or milestone
- **THEN** the dashboard state SHALL treat that value as an explicit runtime override, SHALL keep `profile_id` as provenance, and SHALL provide a product path to save the override as a new profile or controlled profile update when profile management UI is available

#### Scenario: Native provider fields differ across projects
- **WHEN** two Jira projects or two HSD-ES projects use different native field names for the same dashboard concept
- **THEN** Grafana SHALL still request the same chart recipe and canonical dimensions, while Metrics uses the selected Project Provider Profile to produce provider-specific aggregates

#### Scenario: Dashboard uses configured static labels
- **WHEN** a selected profile exposes `IP`, `Project`, or `Milestone` as user-configured static labels
- **THEN** Grafana SHALL display those labels as profile scope dimensions while preserving their provenance as configured text, and SHALL NOT assume they came from native Jira or HSD-ES item fields

#### Scenario: Dashboard explains selected profile readiness
- **WHEN** 用户选择 `profile_id`
- **THEN** Grafana SHALL render a top-level profile status surface backed by Metrics, showing the resolved `provider_id`, static scope labels, source query ownership, mapping version, readiness status and actionable blockers or reasons

#### Scenario: HSD-ES readiness requires access or configuration validation
- **WHEN** the selected HSD-ES profile returns `configuration_required`
- **THEN** Grafana SHALL make clear that this state can include authentication/access, saved-query permission, lookup metadata and chart field-binding validation, and SHALL provide an approved access-check link when Metrics knows the profile-specific HSD-ES saved-query or sign-in target

#### Scenario: HSD-ES seed-backed quality chart renders before live sync
- **WHEN** the selected HSD-ES profile has seed-backed aggregate rows for a quality chart
- **THEN** Grafana SHALL render those rows through the same approved Metrics chart-data surface, SHALL show HSD-ES provider provenance, and SHALL expose freshness/status text that distinguishes seed-backed data from live HSD-ES sync

#### Scenario: Selected-profile charts do not render inactive provider series
- **WHEN** Grafana renders a normal selected-profile chart from `profile_id`
- **THEN** chart value fields SHALL use provider-neutral metric names such as `component_bug_count` or `all_open_bugs`, SHALL NOT declare both `jira_*` and `hsdes_*` value fields in the same selected-profile panel, and SHALL keep provenance fields such as `provider_id`, `profile_id` and `mapping_version` as metadata rather than plotted numeric series

#### Scenario: Categorical quality charts render category dimensions on the x-axis
- **WHEN** Grafana renders `component_bug`
- **THEN** the panel SHALL use a provider-neutral component/category label such as `component_label` as the chart category field instead of using the selected date or WW bucket label as the x-axis

#### Scenario: Aging distribution charts render age buckets on the x-axis
- **WHEN** Grafana renders `open_bug_aging`
- **THEN** the panel SHALL use provider-neutral age bucket labels such as `age_bucket_label` as the chart category field, and SHALL render the measured count as `open_bug_count` instead of using date or WW bucket labels as the primary x-axis

#### Scenario: UI review validates semantic chart axes
- **WHEN** a UI/UX review is performed for dashboard chart panels
- **THEN** the review SHALL compare each panel title and business intent against the target API contract, approved category field, Grafana x-axis field and visible rendered axis, and SHALL flag categorical charts that use date or WW buckets unless the title explicitly describes a time trend

#### Scenario: Local Grafana runtime is refreshed after provider contract changes
- **WHEN** the Metrics provider aggregate code, HSD-ES seed facts, or Grafana dashboard artifact changes during local validation
- **THEN** the local Django backend SHALL be restarted and the Grafana dashboard SHALL be re-imported before the operator evaluates whether the selected HSD-ES profile has chart data

#### Scenario: Stock Grafana keeps profile-derived fields non-editable
- **WHEN** the stock Grafana dashboard is used without a richer profile editor
- **THEN** profile-derived fields such as provider, IP, project/release target and milestone SHALL be displayed as resolved profile facts rather than exposed as independent dropdowns, and any stale URL variables for those fields SHALL NOT affect Metrics chart requests

#### Scenario: Override-capable UI marks changed profile defaults
- **WHEN** a future Grafana App/Scenes or Metrics profile editor allows users to override profile-derived fields
- **THEN** each overridden field SHALL be visually marked as an override, SHALL retain the selected `profile_id` as provenance, and SHALL offer a controlled path to save the override as a new profile or approved profile update

### Requirement: Dashboard range mode is explicit
Grafana dashboard SHALL clearly distinguish the Metrics backend data range from Grafana's native browser time picker, and SHALL provide a selected range mode so users can align the two concepts intentionally.

#### Scenario: Dashboard explains the two date-period controls
- **WHEN** 用户查看 dashboard 顶部 controls
- **THEN** Grafana SHALL present the selected `profile_id` as the first dashboard variable
- **AND** Grafana SHALL present `range_mode`, `begin_ww`, `end_ww` and Refresh as the provider fetch/cache control group
- **AND** Grafana SHALL present the native Grafana time picker as the display time window control, with a nearby `Sync Range` action for aligning the browser window after WW edits
- **AND** Grafana SHALL explain through compact control copy and variable help text that `Work Week` mode uses `Begin WW` / `End WW` for backend data while the Grafana time picker controls the visible display window, and that `Date` mode uses the Grafana time picker dates for backend data while `Begin WW` / `End WW` are ignored by the API

#### Scenario: User chooses Work Week mode
- **WHEN** `range_mode=ww`
- **THEN** Grafana SHALL pass `begin_ww` and `end_ww` to Metrics chart/evidence APIs, and Metrics SHALL resolve the backend range from those WW values while preserving the browser time picker as a Grafana display-window control

#### Scenario: Work Week mode opens with an aligned Grafana time picker
- **WHEN** stock Grafana dashboard is launched or imported with `range_mode=ww`
- **THEN** the dashboard URL or imported dashboard default time SHALL align Grafana native `from` / `to` to the calendar dates resolved from `begin_ww` / `end_ww`
- **AND** the dashboard SHALL explain that stock Grafana does not hard-lock manual time picker edits, so Metrics still treats `begin_ww` / `end_ww` as the authoritative backend range in `ww` mode

#### Scenario: User changes Work Week variables after dashboard load
- **WHEN** a user changes `begin_ww` or `end_ww` inside stock Grafana without changing native `from` / `to`
- **THEN** Metrics SHALL expose a selected-range sync action in a Metrics-owned status payload that reopens the same dashboard with `from` / `to` recalculated from the selected WW range
- **AND** the dashboard SHALL present that action as an explicit `Sync Range` control in the display time window group rather than implying stock Grafana automatically binds template variable changes to the native time picker

#### Scenario: User chooses Date mode
- **WHEN** `range_mode=date`
- **THEN** Grafana SHALL pass `${__from:date:YYYY-MM-DD}` and `${__to:date:YYYY-MM-DD}` as `begin_date` and `end_date`, and Metrics SHALL resolve the backend range from those calendar dates rather than from `begin_ww` / `end_ww`

### Requirement: Grafana panels are backed by chart recipes
每个 Grafana parity panel SHALL have a Metrics-owned chart recipe and provider binding that defines semantic metric, required fields, series contract, evidence capability and support status per provider.

#### Scenario: Jira-first panel is rendered
- **WHEN** a parity panel renders from Jira data
- **THEN** Grafana SHALL query an approved chart data surface generated from the chart recipe and Jira binding, and SHALL show supported, unsupported or configuration-required state according to the binding

#### Scenario: HSD-ES panel is rendered
- **WHEN** the same parity panel renders from HSD-ES data
- **THEN** Grafana SHALL query the same chart recipe through an HSD-ES binding and SHALL preserve HSD-ES tenant/subject/query provenance in the chart data surface

#### Scenario: Explicit provider comparison is rendered
- **WHEN** a future comparison/correlation surface explicitly displays Jira and HSD-ES series in the same chart or section
- **THEN** each series SHALL identify provider source, SHALL be generated from the same chart recipe version or an explicit compatible-version mapping, and SHALL NOT be mixed into the normal selected-profile dashboard

#### Scenario: First dashboard release renders one selected profile
- **WHEN** the first Grafana dashboard release includes supported quality charts
- **THEN** the dashboard SHALL render one selected `profile_id` at a time, SHALL derive the active provider from that profile, and SHALL render provider-specific unavailable/configuration states only for the selected profile

### Requirement: Grafana panels do not own daily metric calculations
Daily calculated metrics SHALL be computed by Metrics-owned facts, profiles, chart recipes and aggregate runs, not by Grafana panel-local query logic.

#### Scenario: Daily new standard bug count is rendered
- **WHEN** Grafana renders a chart such as `daily_new_standard_bug_count`
- **THEN** Grafana SHALL query an approved Metrics data surface containing bucketed values, provider/profile identity, chart version, mapping version, source snapshot or calculation run provenance, and SHALL NOT define `standard bug`, native creation-date fields, native issue/article type fields, or count aggregation semantics inside the panel configuration

#### Scenario: Same daily metric is rendered from different providers
- **WHEN** the same daily metric is rendered from Jira first and HSD-ES second
- **THEN** Jira and HSD-ES SHALL use their own Project Provider Profile field bindings and source query ownership, but SHALL expose the same provider-neutral metric id, bucket grain, dimensions, series name, value and provenance contract to Grafana

#### Scenario: Daily metric needs ticket evidence
- **WHEN** a user drills into a daily bug count bucket
- **THEN** Metrics evidence API SHALL resolve the bucket through the chart recipe, provider binding, profile, fact snapshot and calculation run, rather than through Grafana reconstructing native Jira JQL or HSD-ES EQL

### Requirement: Dashboard evidence behavior
每个 Grafana panel SHALL 声明 evidence capability，说明它是否支持 ticket-level drilldown、range-only evidence 或 summary-only display。

#### Scenario: Evidence-backed panel is clicked
- **WHEN** 用户点击支持 evidence 的 Grafana panel 数据点
- **THEN** 系统 SHALL 使用 Metrics evidence API 返回对应 provider facts 或 work item rows，并 SHALL 保留 provider identity、calculation run 或 fact snapshot provenance

#### Scenario: Summary-only panel is clicked
- **WHEN** 用户查看 automation、shift-left 或 execution gauge 等 summary-only panel
- **THEN** UI SHALL 明确显示该 panel 不支持 ticket-level evidence，或只提供被批准的 summary explanation，不得展示旧的或不相关的 evidence rows

### Requirement: AI-enabled Grafana dashboard
Grafana dashboard SHALL 能被 AI 能力增强，但 AI 生成或解释的内容必须通过 Metrics 后端 contract 约束。

#### Scenario: User asks AI to explain dashboard risk
- **WHEN** 用户询问某个 provider scope 下的质量、执行或效率风险
- **THEN** AI SHALL 先读取 Metrics provider facts、chart data、evidence 或 correlation payload，再生成带 provider provenance 的回答

#### Scenario: User asks AI to create a chart
- **WHEN** 用户要求新增或调整 Grafana chart
- **THEN** AI SHALL 生成 draft chart spec，并由 Metrics validator 验证 datasource、series、evidence contract 和 publication policy 后才能进入 Grafana

#### Scenario: AI placement is selected
- **WHEN** the product chooses the first AI entry point
- **THEN** the preferred placements SHALL be Grafana App/Scenes and Metrics UI sidebar, with a permitted fallback to a separate AI dashboard surface if dashboard layout or interaction constraints make embedded placement poor

### Requirement: Grafana evidence interactions synchronize with workbench state
Grafana panels that participate in the unified workbench SHALL expose Metrics-approved evidence interaction metadata so a selected data point can update workbench PageQueryState and ticket evidence.

#### Scenario: Grafana panel exposes bucket-series evidence
- **WHEN** a Grafana panel declares `bucket_series` evidence capability
- **THEN** its Metrics contract SHALL identify the fields needed to resolve calculation run or fact snapshot, bucket id and series name
- **AND** its user-facing click/data-link behavior SHALL carry those values to the workbench or to a Metrics evidence URL accepted by the workbench

#### Scenario: Grafana data link is opened inside workbench
- **WHEN** 用户 clicks a Grafana data link for an evidence-backed bucket/series point inside the workbench
- **THEN** workbench SHALL update PageQueryState from the validated link parameters
- **AND** evidence pane SHALL refresh without requiring the user to leave the unified UI

#### Scenario: Grafana panel cannot emit a valid selection
- **WHEN** a Grafana panel cannot map interaction to Metrics-approved run/snapshot, bucket and series fields
- **THEN** the panel SHALL be treated as read-only for point-level evidence
- **AND** the workbench SHALL show range-only, summary-only or unsupported evidence state according to the chart contract

### Requirement: Workbench embeds Grafana at panel scope
Grafana content embedded in the unified workbench primary chart pane SHALL prefer compact panel-level embed or solo panel URLs rather than the full Grafana dashboard page.

#### Scenario: Workbench shows a Grafana chart pane
- **WHEN** active renderer is Grafana stock panel
- **THEN** workbench SHALL render a compact panel-level Grafana embed sized for the chart pane
- **AND** it SHALL avoid displaying Grafana global navigation, dashboard sidebar, unrelated panels or admin chrome inside the primary chart container

#### Scenario: User needs full Grafana page
- **WHEN** 用户 needs Grafana dashboard editing, diagnostics or admin controls
- **THEN** workbench MAY provide a separate full-dashboard link or diagnostics/admin pane
- **AND** that full Grafana page SHALL NOT be the default embedded chart pane for normal analysis

#### Scenario: Panel embed cannot satisfy interaction requirements
- **WHEN** compact panel embed cannot reliably support Metrics-approved evidence selection sync
- **THEN** implementation SHALL keep the Metrics-owned reference renderer as the interactive evidence path
- **AND** future work MAY move the Grafana path to App Plugin or Scenes instead of expanding the primary pane to full Grafana UI

### Requirement: Grafana iframe state is not source of truth
Workbench SHALL NOT treat Grafana iframe internal state as authoritative for Metrics evidence; all evidence queries SHALL be derived from workbench PageQueryState and Metrics-validated chart/evidence contracts.

#### Scenario: Grafana variable differs from workbench state
- **WHEN** Grafana iframe variable, time picker or local panel state differs from workbench PageQueryState
- **THEN** Metrics evidence request SHALL follow workbench PageQueryState
- **AND** shell SHALL show a sync or stale-state indicator when the mismatch affects visible chart/evidence consistency

#### Scenario: Workbench refreshes Grafana panel
- **WHEN** workbench PageQueryState changes profile, range or chart
- **THEN** Grafana pane SHALL be reloaded or updated with URL variables that reflect the shell state
- **AND** evidence pane SHALL NOT rely on reading hidden Grafana iframe state

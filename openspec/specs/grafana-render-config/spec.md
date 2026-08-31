# grafana-render-config Specification

## Purpose
Grafana Render Config 定义 Metrics 如何用受控的 dashboard/render configuration 生成 Grafana JSON，并保证 Grafana 只负责显示和交互，不拥有 provider 查询、业务语义或计算逻辑。

## Requirements

### Requirement: Dashboard JSON is generated from render config
系统 SHALL 使用 versioned Grafana render config 生成 dashboard JSON，并 SHALL 将手写大型 dashboard JSON 限制为生成产物或临时迁移输入。

#### Scenario: Dashboard artifact is generated
- **WHEN** developer 或 AI-approved workflow 生成 Grafana dashboard artifact
- **THEN** generator SHALL read render config、profile variables、panel layout、chart recipe references、datasource binding 和 evidence link rules, and SHALL output deterministic Grafana JSON

#### Scenario: Generated artifact is regenerated
- **WHEN** the same render config and catalog inputs are used twice
- **THEN** generated Grafana JSON SHOULD be semantically stable so code review can focus on render-config intent rather than noisy panel JSON churn

### Requirement: Render config references approved chart recipes
每个 render-config panel SHALL reference an approved Metrics chart recipe, chart version, category field, value fields, evidence capability and render shape.

#### Scenario: Panel renders a provider chart
- **WHEN** render config defines a provider-backed panel
- **THEN** it SHALL identify `chart_id`、`chart_version`、`profile_variable`、`range_mode` inputs、approved value fields、category field、render root 和 evidence capability

#### Scenario: Panel requests an unapproved series
- **WHEN** render config references a value field not listed by the selected chart recipe
- **THEN** validator SHALL reject the render config and SHALL NOT generate or publish Grafana JSON

#### Scenario: Categorical panel is configured
- **WHEN** panel intent is categorical, such as component bugs or aging buckets
- **THEN** render config SHALL declare a category field such as `component_label` or `age_bucket_label`, and SHALL NOT default to date/WW buckets unless the chart recipe declares a time-series shape

### Requirement: Grafana datasource and query surfaces are allowlisted
Generated Grafana JSON SHALL only use approved Metrics API paths、datasource UIDs、query params、contract versions and render roots.

#### Scenario: Render config contains provider-native query text
- **WHEN** render config or generated dashboard includes raw JQL、EQL、HSD-ES field literals、saved-query ids、SQL business calculations、secret-shaped values or unapproved datasource references
- **THEN** validator SHALL fail the artifact with actionable findings

#### Scenario: Dashboard panel calls Metrics API
- **WHEN** generated Grafana JSON calls Metrics chart/evidence/readiness API
- **THEN** each target SHALL use relative approved API paths and SHALL include required query params without extra unapproved params

### Requirement: Profile-first variable model is preserved
Render config SHALL model normal dashboards as selected-profile dashboards where `profile_id` drives provider、scope labels、source query ownership and mapping version.

#### Scenario: User selects profile
- **WHEN** generated dashboard exposes profile selection
- **THEN** `profile_id` SHALL be the primary selector and provider-derived values SHALL be shown through readiness/status panels rather than as independent provider/project dropdowns that can drift from the selected profile

#### Scenario: Override-capable surface is introduced
- **WHEN** a future Grafana App/Scenes or Metrics profile editor allows profile-derived overrides
- **THEN** render config SHALL mark overridden fields, SHALL preserve original profile provenance, and SHALL include a save-as-new-profile or controlled update action path

### Requirement: Range controls distinguish fetch/cache from display window
Render config SHALL describe provider fetch/cache range and Grafana display time window separately, including a user-visible sync action when stock Grafana cannot bind them automatically.

#### Scenario: Work-week range mode is used
- **WHEN** `range_mode=ww`
- **THEN** generated panel targets SHALL pass `begin_ww` and `end_ww` to Metrics APIs, and dashboard help/status copy SHALL explain that Grafana native time picker is the display window until the user uses Sync Range

#### Scenario: Date range mode is used
- **WHEN** `range_mode=date`
- **THEN** generated panel targets SHALL pass Grafana native time macros as `begin_date` and `end_date`, and Metrics SHALL ignore stale WW variables for backend filtering

### Requirement: Render config publication is validated and auditable
System SHALL require validation before generated Grafana artifacts are imported, published, or treated as approved dashboard definitions.

#### Scenario: Developer publishes dashboard config
- **WHEN** developer updates render config or generated dashboard JSON
- **THEN** validation SHALL verify chart recipes、allowed API surfaces、evidence links、category axes、daily metric ownership、secret safety and provider-native literal bans before publication

#### Scenario: AI-generated dashboard draft is submitted
- **WHEN** AI sidecar submits a render-config draft
- **THEN** system SHALL validate it using the same rules as developer-authored render config and SHALL keep it unpublished until validation and approval policy pass

# Spec Delta

## MODIFIED Requirements

### Requirement: Render config publication is validated and auditable
System SHALL require validation and an approved preview digest before generated Grafana dashboards are imported, published, or treated as approved dashboard definitions.

#### Scenario: Developer publishes dashboard config
- **WHEN** developer updates render config or generated dashboard JSON
- **THEN** validation SHALL verify chart recipes、allowed API surfaces、evidence links、category axes、daily metric ownership、secret safety and provider-native literal bans before publication

#### Scenario: AI-generated dashboard draft is submitted
- **WHEN** AI 通过 `metrics.chart_workflow` 或 `metrics.publish_chart` 提交 render-config 草稿
- **THEN** system SHALL validate it using the same rules as developer-authored render config
- **THEN** 草稿 SHALL 保持未发布，直到人工批准了绑定其 preview 摘要的审批，且执行前重新 preview 的摘要一致

### Requirement: AI-generated Grafana dashboards are listed and auditable
Dashboard SHALL track AI-generated Grafana dashboard publish artifacts so operators can inspect previous AI chart publications.

#### Scenario: Published AI dashboard is listed
- **WHEN** an AI-generated dashboard is published to Grafana
- **THEN** Dashboard SHALL record a publish artifact entry with dashboard uid, title, Grafana URL, profile id, provider id, chart id, range, requested series, `decided_by` actor, approval id, `tool_call_id`, preview digest, status and timestamps

#### Scenario: Operator views publish history
- **WHEN** an operator opens the AI publish history surface or calls its API
- **THEN** the system SHALL list recent AI-generated dashboard artifacts with enough metadata to distinguish Jira vs HSD-ES, profile, range, chart recipe and publish status

#### Scenario: Publish artifact is superseded
- **WHEN** a later publish overwrites or replaces the same dashboard uid
- **THEN** history SHALL retain previous audit metadata and mark the latest artifact clearly rather than silently losing prior publications

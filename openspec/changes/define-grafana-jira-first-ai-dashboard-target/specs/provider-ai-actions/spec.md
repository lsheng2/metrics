## ADDED Requirements

### Requirement: AI capability spans Jira and HSD-ES providers
AI workflow SHALL 同时支持 Jira first provider 和 HSD-ES second provider 的 read/search/facts/chart/correlation 场景，但 SHALL 通过 provider manifest 判断每个 provider 当前支持的能力。

#### Scenario: AI answers from Jira first provider
- **WHEN** 第一阶段只有 Jira facts 可以用于 parity dashboard
- **THEN** AI SHALL 基于 Jira provider facts、chart data、evidence rows、approved aggregates 和 deferred/configuration-required reasons 回答 supported quality charts and dashboard explanation questions

#### Scenario: AI answers from HSD-ES second provider
- **WHEN** HSD-ES facts 和 correlation artifacts 可用
- **THEN** AI SHALL 使用相同 answer contract 支持 HSD-ES scope、Jira-HSD-ES correlation、HSD-ES-native facts 和 cross-provider risk explanation

### Requirement: AI entry placement remains flexible
AI UI entry points SHALL prefer Grafana App/Scenes and Metrics UI sidebar, while preserving the option to move AI interaction to a separate dashboard agent or page if embedded layout or interaction constraints are poor.

#### Scenario: Embedded AI layout is acceptable
- **WHEN** Grafana App/Scenes or Metrics UI sidebar can display AI explanations, evidence links, chart drafts and action-plan previews clearly
- **THEN** the first AI entry SHALL use one or both embedded placements while continuing to call Metrics backend contracts

#### Scenario: Embedded AI layout is not acceptable
- **WHEN** dashboard layout, Grafana interaction limits or sidebar usability make the embedded AI experience poor
- **THEN** the product MAY split AI into a separate AI dashboard surface, but SHALL reuse the same provider facts, chart catalog, evidence, correlation and action-plan contracts

### Requirement: AI generated chart specs remain provider-neutral
AI SHALL 生成 provider-neutral chart intent 和 Metrics-validated chart spec；provider-specific query language SHALL 由 Metrics 后端或 provider adapter 生成和验证。

#### Scenario: User asks for a Grafana chart
- **WHEN** 用户要求 AI 生成类似参考 dashboard 的 Grafana panel
- **THEN** AI SHALL 返回 chart intent、required semantic dimensions、series、evidence capability 和 visualization preference，而不是直接生成未经验证的 Jira JQL、HSD-ES EQL、Mongo aggregate 或 Grafana datasource query 作为 production artifact

#### Scenario: Provider-specific query is required
- **WHEN** chart spec 需要 Jira JQL 或 HSD-ES EQL 支撑
- **THEN** provider adapter SHALL 生成或验证 provider-specific query，并 SHALL 记录 query provenance、scope、permission 和 validation result

#### Scenario: User references an existing provider query
- **WHEN** 用户要求 AI 基于 Jira saved filter、JQL、HSD-ES saved query 或 HSD-ES Query Builder criteria 创建 chart
- **THEN** AI SHALL classify that query as provider seed or evidence input, then produce provider-neutral chart intent and mapping requirements instead of publishing the native query as Grafana panel logic

### Requirement: AI explanations respect field layering
AI SHALL distinguish canonical dashboard fields, project-specific mapping fields and provider-native fields when explaining charts, evidence or correlation.

#### Scenario: AI explains a Jira-backed chart
- **WHEN** AI explains a Jira-backed parity panel
- **THEN** AI SHALL name the canonical metric and may mention Jira-native fields only as mapping provenance or caveats

#### Scenario: AI explains an HSD-ES-backed chart
- **WHEN** AI explains an HSD-ES-backed parity panel
- **THEN** AI SHALL name the canonical metric and may mention HSD-ES tenant, subject, saved query, article field or Query Builder criteria only as provider provenance or mapping evidence

#### Scenario: AI compares providers
- **WHEN** AI compares Jira and HSD-ES data for the same chart recipe
- **THEN** AI SHALL distinguish provider-native truth, canonical normalized facts, project mappings and correlation state before making risk or discrepancy claims

#### Scenario: AI explains query provenance
- **WHEN** AI explains why a Jira-backed or HSD-ES-backed chart contains a set of items
- **THEN** AI SHALL identify whether the source population came from a provider-owned saved query/filter or a Metrics-managed native query, and SHALL reference Project Provider Profile provenance rather than inventing hidden filters

### Requirement: AI write support remains action-plan gated
AI SHALL NOT directly write Jira or HSD-ES. Jira writes MAY become available through approved action plans; HSD-ES writes SHALL remain unavailable until tenant/subject、required fields、permission、`send_mail` behavior 和 approval policy 完成 review。

#### Scenario: AI suggests a Jira update from dashboard analysis
- **WHEN** AI 根据 Grafana dashboard/evidence 建议更新 Jira issue
- **THEN** AI SHALL 创建 ProviderActionPlan with before/after preview、reason、risk 和 required approval，而不是直接调用 Jira write API

#### Scenario: AI suggests an HSD-ES update before write approval
- **WHEN** AI 根据 HSD-ES facts 建议更新 HSD-ES article
- **THEN** 系统 SHALL 只允许生成 non-executable proposal 或 explanation，并 SHALL 返回 HSD-ES write unsupported reason

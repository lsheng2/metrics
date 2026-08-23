# Chart Spec Catalog for AI-generated Grafana specs

| Field | Value |
| --- | --- |
| `id` | `BLG-20260823-chart-spec-catalog` |
| `title` | Chart Spec Catalog for AI-generated Grafana specs |
| `status` | `accepted` |
| `source` | [grafana-ai-dashboard-composition-design.zh.md](../grafana-ai-dashboard-composition-design.zh.md), [grafana-chart-render-contract-architecture.md](../grafana-chart-render-contract-architecture.md) |
| `problem` | Future AI-generated Grafana dashboards need a stable catalog of approved chart specs, contract versions, data surfaces, and validation expectations before generation can be repeatable. |
| `user_value` | Maintainers can ask AI to generate or modify dashboards without losing data-contract traceability or bypassing Grafana validation. |
| `owner_paths` | `docs/`, `ops/grafana/`, `scripts/grafana_artifact_contract.py`, `docs/grafana-approved-data-surfaces.json` |
| `authority` | Grafana chart render contract, approved data surfaces, Bug Trend API payload contract |
| `risk` | `medium`: without a catalog, AI can generate plausible dashboards that do not match approved data contracts. |
| `trigger_to_start` | User asks to generate a second Grafana chart/dashboard, or a new chart family needs to reuse the Bug Trend contract pattern. |
| `non_goals` | Do not implement a chart generator, new API endpoint, or dashboard registry as part of this backlog capture. |
| `dependencies` | Existing Bug Trend contract versioning remains stable at `default_bug_trend@0.1`. |
| `validation_gates` | `python scripts/validate_grafana_artifacts.py`, focused tests for catalog parsing/contract validation, and architecture review before generator work. |
| `review_gate` | Architecture review required before implementation. |
| `last_reviewed` | 2026-08-23: captured after chart contract stabilization and deferred until a second chart/dashboard request creates demand. |

## Deferred With Trigger

This item is intentionally not implementation-ready. Promote it to `ready-for-plan` only when the trigger occurs and the implementation owner can name the catalog storage format, validator behavior, and at least one non-Bug-Trend chart consumer.

## Spec: Chart Spec Catalog

如果未来要让 AI 稳定地产生 Grafana chart spec，不能让 AI 从空白 JSON 开始写 dashboard。正确边界是：Metrics 提供一个 `Chart Spec Catalog`，AI 只能选择 catalog 中已经批准的 chart family、shape、template 和 evidence capability，再填入受控参数。Catalog 是“AI 可以怎么生成图”的产品化 schema，不是 Grafana 的任意 JSON 仓库。

这个 catalog 的目标不是一次性覆盖所有 Grafana 能力，而是把最容易出错的跨层决策固定下来：

1. 这个图消费哪个 Metrics API root。
2. 这个 root 是什么 shape。
3. Grafana 应该选择哪些 columns。
4. 哪些 numeric fields 可以成为 rendered series。
5. 点击图形时如何映射回 Metrics evidence API。
6. 这个 shape 支持哪些 visualization family。
7. AI 哪些字段可以填，哪些字段不能碰。
8. Validator 和 parity check 应该检查什么。

### 为什么需要 Catalog

这次 Bug Trend Grafana spike 暴露了一个重要事实：图表问题不只是“Grafana JSON 写错了”。真正风险横跨多层：scope semantic config、calculation run、API shape、Grafana target、field type、evidence link、runtime data 和视觉渲染。AI 可以很快生成一个看起来合理的 Grafana panel，但如果没有 catalog 约束，它很容易出现这些问题：

| 风险 | 例子 | Catalog 如何防住 |
| --- | --- | --- |
| 读错 root | 选择 `$.points` 但按 wide table 配 columns。 | Catalog 固定 `root_selector` 和 shape。 |
| 字段名猜测 | 使用 `label`、`value`、`series_name` 让 Grafana 猜含义。 | Catalog 声明 required fields、category field、value fields。 |
| 证据错位 | 点击图形后查不到同一个 run/bucket/series。 | Catalog 声明 evidence link policy 和 required link fields。 |
| 业务语义漂移 | AI 在 Grafana SQL 里写 status/severity mapping。 | Catalog 只允许 Metrics-owned API/shape，不允许 SQL 语义。 |
| 空图或单线图 | API 有 5 个 series，但 4 个实际为 0 或未被渲染。 | Catalog 要求 parity + runtime sample validation，而不只验证 JSON。 |
| 难以扩展 | 每种新图都临时手写 Grafana spec。 | Catalog 让新图复用 shape/template/validator。 |

### Catalog 的最小数据模型

第一版可以先做成 machine-readable JSON/YAML 文件或 Django seed data，不急着做完整 UI。关键是让 AI 和 validator 都读同一个 catalog。

```yaml
chart_spec_catalog_entry:
  catalog_id: wide_bucket_series_timeseries_v0_1
  chart_family: bucket_series_trend
  contract_version: "0.1"
  supported_renderer:
    renderer_type: grafana
    integration_route: c_stock
    grafana_panel_type: timeseries
  data_contract:
    endpoint: /api/charts/data/
    root: grafana_rows
    shape: wide_bucket_series
    required_query_params:
      - scope_id
      - begin
      - end
      - chart_id
    required_fields:
      - calculation_run_id
      - bucket_id
      - bucket_label
      - bucket_start
      - bucket_end
      - bucket_granularity
    category_field: bucket_label
    time_field: bucket_start
    value_field_policy: declared_series_only
    series_field_source: __field.name
  evidence_contract:
    capability: bucket_series
    endpoint: /api/charts/evidence/
    required_link_fields:
      - calculation_run_id
      - bucket_id
    required_link_params:
      run: __data.fields.calculation_run_id
      bucket: __data.fields.bucket_id
      series: __field.name
      chart_id: chart_id
  ai_fillable_fields:
    - chart_id
    - title
    - value_fields
    - field_styles
    - description
  ai_forbidden_fields:
    - datasource.uid
    - endpoint
    - rawSql
    - root_selector
    - evidence endpoint
    - required_fields
    - scope semantics
  validation:
    static_validator: scripts/validate_grafana_artifacts.py
    parity_validator: scripts/compare_grafana_bug_trend_parity.py
    requires_runtime_sample: true
```

这不是最终 schema，只是最小可执行表达。它的重点是把“AI 允许生成什么”变成一个显式 contract。

### Catalog、ChartDefinition、RendererSpec 的关系

Catalog 不应该替代 `ChartDefinition`。建议关系如下：

```text
Chart Spec Catalog Entry
  owns: allowed shape/template/renderer/evidence policy

ChartDefinition
  references: catalog_id
  owns: chart_id, title, owner, lifecycle status, selected series, chart version

RendererSpec
  generated from: catalog entry + ChartDefinition parameters
  owns: concrete Grafana target/panel JSON fragment after validation
```

换句话说：

- Catalog 说明“这种图怎么安全地生成”。
- ChartDefinition 说明“用户/AI 生成了哪一个具体图”。
- RendererSpec 说明“这个具体图落到 Grafana 时长什么样”。

这样未来新增 `wide_category_series`、`summary_value`、`evidence_rows` 时，只需要新增 catalog entry 和 validator coverage，不需要让 AI 自由发明新结构。

### AI 生成时的受控流程

AI 生成 Grafana spec 的流程应该是“选择 catalog entry + 填参数 + validator 修正循环”，不是“自由写 dashboard JSON”。

```text
User prompt
  -> Metrics parses chart intent
  -> Metrics selects allowed catalog entries
  -> AI picks one catalog entry and proposes fillable fields
  -> Metrics materializes draft Grafana target/panel from template
  -> Static validator checks datasource/root/shape/fields/evidence link
  -> Parity validator checks API payload vs rendered valueFields
  -> Runtime sample check confirms non-empty/non-degenerate rendering
  -> Draft enters Chart Catalog lifecycle
```

AI 的输出应该类似：

```yaml
catalog_id: wide_bucket_series_timeseries_v0_1
chart_id: ai_bug_in_out_daily
title: Daily Bug In / Bug Out
value_fields:
  - new_critical_high
  - new_medium_low
  - fixed_or_closed_bugs
field_styles:
  fixed_or_closed_bugs:
    polarity: negative_bar
explanation: Shows bug inflow and outflow by day for the selected scope.
```

AI 不应该输出完整 datasource、API path、raw SQL、status mapping 或 arbitrary Grafana dashboard JSON。完整 JSON 由 Metrics 用 catalog template materialize。

### Catalog Template 示例

Catalog template 是把 AI 输出变成 Grafana target 的受控模板。下面示例展示模板思路，不要求第一版就实现模板引擎。

```json
{
  "datasource": {"type": "yesoreyeram-infinity-datasource", "uid": "metrics-bug-trend-api"},
  "type": "json",
  "source": "url",
  "parser": "backend",
  "format": "table",
  "url": "/api/charts/data/?scope_id=$scope_id&begin=$begin&end=$end&chart_id={{ chart_id }}",
  "root_selector": "$.grafana_rows",
  "columns": "{{ catalog.columns(required_fields + value_fields) }}",
  "metricsContract": {
    "chartId": "{{ chart_id }}",
    "contractVersion": "0.1",
    "root": "grafana_rows",
    "shape": "wide_bucket_series",
    "categoryField": "bucket_label",
    "requiredFields": ["calculation_run_id", "bucket_id", "bucket_label", "bucket_start", "bucket_end", "bucket_granularity"],
    "valueFields": "{{ value_fields }}",
    "evidenceLinkFields": ["calculation_run_id", "bucket_id"],
    "seriesFieldSource": "__field.name"
  }
}
```

Template 的作用是让 AI 只能改变 `chart_id`、`title`、`value_fields` 和 style hints。`datasource`、`endpoint`、`root_selector`、`metricsContract.root`、`shape`、`evidenceLinkFields` 都由 catalog 固定。

### Validator 需要增加的 Catalog 检查

现有 validator 已经检查 datasource、API path、query params、root、shape、contractVersion、valueFields、evidence link。引入 Catalog 后，validator 还应增加几类检查：

| 检查 | 目的 |
| --- | --- |
| `catalog_id` 必须存在且启用。 | 防止 AI 使用未注册 shape/template。 |
| `metricsContract.shape` 必须等于 catalog shape。 | 防止 template 和声明漂移。 |
| `valueFields` 必须是 ChartDefinition 声明或 IndicatorDefinition 允许的 series。 | 防止 AI 发明数字列。 |
| `columns` 必须等于 catalog required fields + approved value fields。 | 防止 Grafana 隐式猜字段。 |
| `evidenceLinkFields` 和 `seriesFieldSource` 必须等于 catalog policy。 | 防止 click 到错误 evidence。 |
| `rawSql`、外部 URL、未批准 datasource 仍然禁止。 | 防止第二套语义系统。 |
| sample payload 中至少一个 rendered series 非空或显式允许 empty。 | 防止“验证通过但图是空的”。 |
| 若 evidence capability 是 `bucket_series`，必须能用 sample `run+bucket+series` 查到 evidence 或记录 allowed-empty reason。 | 防止声称可解释但 drilldown 不通。 |

### Degenerate Chart Gate

这次只看到一条线的问题说明，仅验证 JSON schema 不够。Catalog 应该要求一个轻量的 degenerate chart gate：

| 情况 | 默认处理 |
| --- | --- |
| 所有 value fields 都是 0/null。 | fail，除非 chart definition 明确 `allow_empty=true` 并给出说明。 |
| 多个 value fields 里只有一个非零。 | warn 或 fail，取决于 chart family。对于 bug in/out trend，应该 fail；对于 single-series chart，可以 pass。 |
| bar series 全为 0 但 line series 有值。 | 对 mixed in/out trend fail；对 backlog-only trend pass。 |
| evidence capability 是 `bucket_series`，但 sample membership 为 0。 | fail 或要求 `range_only/summary_only`。 |

这个 gate 应该跑在 Metrics 后端 sample payload 上，而不是让 Grafana runtime 自己发现。Grafana screenshot 仍然有价值，但它应该是最后一道视觉确认，不是唯一验证。

### Catalog 第一版不要过度设计

第一版推荐只实现三个 catalog entries：

| Catalog entry | Shape | 用途 |
| --- | --- | --- |
| `wide_bucket_series_timeseries_v0_1` | `wide_bucket_series` | 当前 Bug Trend mixed line/bar 主路径。 |
| `evidence_rows_table_v0_1` | `evidence_rows` | 只展示 ticket/evidence table。 |
| `summary_value_stat_v0_1` | `summary_value` | 单 KPI/stat panel，占位给 summary dashboard。 |

不要一开始就做完整自然语言图表平台。先把 catalog 写成 JSON/YAML 或 seed data，让 validator 读它；等 2-3 个 chart family 证明稳定后，再做 UI 和 AI 接入。

### 对当前代码的最小落地路径

当前仓库已经有 `BugTrendChartDefinition`、`BugTrendEvidenceContract`、`docs/grafana-approved-data-surfaces.json` 和 `metricsContract`。所以第一步不需要大重构，可以按下面顺序推进：

1. 新增 `docs/grafana-chart-spec-catalog.json` 或 `bug_metrics/app/api/chart_spec_catalog.py`，注册 `wide_bucket_series_timeseries_v0_1`。
2. 在当前 `ops/grafana/bug_trend_dashboard.json` 的 `metricsContract` 增加 `catalogId`。
3. 让 `scripts/validate_grafana_artifacts.py` 读取 catalog 并校验 `catalogId/root/shape/valueFields/evidence policy`。
4. 让 `scripts/compare_grafana_bug_trend_parity.py` 输出 degenerate chart warning/fail 信息。
5. 将 AI draft 先限制为 catalog fillable fields，不允许直接提交完整 Grafana JSON。
6. 最后再实现 AI-base integration。

这个路径把 AI 的自由度压到合理范围内，同时保留未来扩展不同 chart family 的空间。

### AI chart lifecycle

AI-generated chart 必须有明确生命周期。`personal` 模式可以在 validator 通过后直接个人发布；`cloud` 模式需要审批后才能进入公共 chart selector 或 Grafana provisioning。

```text
requested
  -> generated
  -> validation_failed | draft
  -> previewed
  -> personal: published
  -> cloud: pending_approval -> approved | rejected -> published
  -> disabled | rolled_back | archived
```

| 状态 | Owner | 用户可见性 | 要求 |
| --- | --- | --- | --- |
| `requested` | user / Metrics UI | 请求者可见。 | 记录 prompt 摘要、scope、time range，不记录 secret。 |
| `generated` | AI-base | 请求者可见。 | 产出 candidate spec，不写生产 dashboard。 |
| `validation_failed` | Metrics validator | 请求者和 maintainer 可见。 | 显示错误和可修复建议。 |
| `draft` | chart author | 作者可见。 | 可 preview，不进入 shared selector。 |
| `previewed` | chart author | 作者可见。 | 使用受控 sample/PageQueryState 预览。 |
| `pending_approval` | chart author / approver | approver 和 maintainer 可见。 | cloud 模式下提交审批后进入该状态。 |
| `approved` | chart approver/admin | cloud 模式需要。 | 审批人确认 spec、evidence、权限和 Grafana renderer。 |
| `rejected` | chart approver/admin | 作者、approver 和 maintainer 可见。 | 显示拒绝原因，可回到 draft 修改。 |
| `published` | Metrics Chart Catalog | 授权用户可见。 | published version 不可原地修改。 |
| `disabled` / `rolled_back` / `archived` | maintainer/approver | 按权限可见。 | 保留 audit 和历史版本。 |

`personal` 模式可以在 validator 通过后从 `draft` 或 `previewed` 直接进入个人 `published`，但不能跳过 audit。`cloud` 模式必须经过 `pending_approval` 和 `approved` 后才能进入 shared `published` 或 Grafana provisioning。

阻止发布的条件：

1. 使用未批准 datasource、任意业务 SQL 或外部 URL。
2. 引入新的 bug/fixed/critical/high 语义但没有 IndicatorDefinition。
3. 声称支持 evidence，但没有可验证 EvidenceContract。
4. Grafana renderer 不能映射 PageQueryState 或缺少 fallback。
5. scope/time range 权限不合法。

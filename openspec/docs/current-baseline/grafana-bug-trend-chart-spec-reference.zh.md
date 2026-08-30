# Grafana Bug Trend Chart Spec 直白参考

日期：2026-08-22

本文只解释当前 Bug Trend Grafana stock dashboard spec：[`ops/grafana/bug_trend_dashboard.json`](../../../ops/grafana/bug_trend_dashboard.json)。目标是让读者能直接看懂这个 JSON 里每一块在做什么、它如何变成最终图形、以及每个数据域从哪里来。

## 一句话版本

`bug_trend_dashboard.json` 描述的是一个 Grafana `timeseries` panel。它用 Infinity datasource 调用 Metrics Django API：

```text
/api/charts/data/?scope_id=$scope_id&begin=$begin&end=$end&chart_id=default_bug_trend
```

API 返回一个 JSON envelope，并在 envelope 顶层声明 `contract_version: "0.1"`。Grafana 只读取其中的 `grafana_rows`：一行代表一个 bucket，一列代表一个 series。Grafana 用 `bucket_start` 当时间轴，用几个 number column 当图上的线或柱子；点击某个点/柱时，再用同一行里的 `calculation_run_id`、`bucket_id` 和被点击的 field name 去调用 `/api/charts/evidence/`。

## Spec 顶层在说什么

| JSON 字段 | 当前值/形态 | 直白解释 | 最终影响 |
| --------- | ----------- | -------- | -------- |
| `uid` | `metrics-bug-trend-c-stock` | Grafana dashboard 的稳定 id。 | 本地 URL 和 provisioning 用它找到这个 dashboard。 |
| `title` | `Metrics Bug Trend C-stock Spike` | Dashboard 标题。 | 显示在 Grafana 页面顶部。 |
| `schemaVersion` / `version` | `39` / `1` | Grafana dashboard JSON 的版本信息。 | 给 Grafana 解析和迁移用，不定义业务语义。 |
| `tags` | `metrics`、`bug-trend`、`c-stock` | Dashboard 标签。 | 方便 Grafana 搜索和分类。 |
| `templating.list` | `scope_id`、`begin`、`end` | Dashboard 变量。 | 用户或 URL 可以切换 scope 和时间范围。 |
| `panels[0]` | `Bug Trend` panel | 真正的图表定义。 | 决定数据怎么取、怎么转字段、怎么画。 |

当前 chart data contract baseline 是 `default_bug_trend@0.1`。其中 `default_bug_trend` 来自 target URL 的 `chart_id`，`0.1` 来自 target 的 `metricsContract.contractVersion`，并且必须和 API response 的 `contract_version` 对齐。

## Dashboard 变量如何进入 API

Grafana spec 里定义了三个 textbox 变量：

| 变量 | 默认值 | 进入哪里 | 含义 |
| ---- | ------ | -------- | ---- |
| `$scope_id` | `1` | `url` query string | 选择哪个 saved Jira scope。 |
| `$begin` | `2025-04-07` | `url` query string | 查询开始日期，ISO date。 |
| `$end` | `2026-08-09` | `url` query string | 查询结束日期，ISO date。 |

Grafana 实际请求会变成类似：

```text
/api/charts/data/?scope_id=3&begin=2026-06-01&end=2026-08-09&chart_id=default_bug_trend
```

这个 URL 在 Django 里由 [`ui_web/urls.py`](../../../ui_web/urls.py) 路由到 `BugTrendChartDataApiView`，view 会校验 `scope_id`、`begin`、`end`、`chart_id` 都存在，然后调用 facade 生成 JSON。

## Panel 如何取数据

当前 panel 的核心 target 是：

```json
{
  "type": "json",
  "source": "url",
  "parser": "backend",
  "format": "table",
  "url": "/api/charts/data/?scope_id=$scope_id&begin=$begin&end=$end&chart_id=default_bug_trend",
  "root_selector": "$.grafana_rows",
  "metricsContract": {
    "chartId": "default_bug_trend",
    "contractVersion": "0.1",
    "root": "grafana_rows",
    "shape": "wide_bucket_series"
  }
}
```

直白解释：

- `type: json`：返回值是 JSON。
- `source: url`：Infinity datasource 通过 URL 拉数据。
- `parser: backend`：让 Infinity datasource 后端解析 JSON。
- `format: table`：把 JSON 转成表格字段，再交给 Grafana panel。
- `url`：Metrics Django 拥有的 chart data API。
- `root_selector: $.grafana_rows`：不要读整个 response，只读 `grafana_rows` 这个数组。
- `metricsContract.chartId: default_bug_trend`：声明这个 target 消费的是哪个 chart contract。
- `metricsContract.contractVersion: 0.1`：声明这个 target 按哪一版 contract 读取字段。

这里最重要的是 `root_selector`。如果它读 `$.points`，Grafana 会拿到 long-form rows，字段会变成 `bucket_label`、`series_name`、`value` 这种结构；当前 stock `timeseries` panel 更稳定的输入是 wide rows，所以必须读 `$.grafana_rows`。

## API 返回的 `grafana_rows` 长什么样

`grafana_rows` 由 [`ui_web/facades/bug_trend_facade.py`](../../../ui_web/facades/bug_trend_facade.py) 的 `_grafana_rows()` 生成。API envelope 顶层有 `contract_version`，`grafana_rows` 里的每一行代表一个 bucket，大概长这样：

```json
{
  "calculation_run_id": "run-123",
  "bucket_id": "bucket-123",
  "bucket_label": "2026-06-01",
  "bucket_start": "2026-06-01",
  "bucket_end": "2026-06-01",
  "bucket_granularity": "daily",
  "all_open_bugs": 7,
  "all_open_critical_high": 1,
  "new_critical_high": 0,
  "new_medium_low": 2,
  "fixed_or_closed_bugs": -1
}
```

可以把它想成一张表：

| bucket_start | all_open_bugs | all_open_critical_high | new_critical_high | new_medium_low | fixed_or_closed_bugs |
| ------------ | ------------- | ---------------------- | ----------------- | -------------- | -------------------- |
| 2026-06-01 | 7 | 1 | 0 | 2 | -1 |
| 2026-06-02 | 8 | 1 | 1 | 1 | 0 |

Grafana 最终画图时，`bucket_start` 是横轴时间；每个 number column 是一条 series。

## `columns` 如何对应最终图形

Spec 里的 `columns` 告诉 Infinity datasource 从 `grafana_rows` 每一行里取哪些字段，以及字段类型是什么。

| Column selector | Type | 最终用途 | 数据从哪里来 |
| --------------- | ---- | -------- | ------------ |
| `bucket_label` | `string` | 人类可读 bucket 标签。 | `BugTrendChart.labels[index]`，由 calculation bucket 的日期/周期派生。 |
| `bucket_start` | `timestamp` | Grafana timeseries 横轴。 | `BugTrendBucket.bucket_start` -> `BugTrendChart.bucket_starts` -> `grafana_rows[].bucket_start`。 |
| `bucket_end` | `string` | 隐藏字段；用于调试或 tooltip 扩展。 | `BugTrendBucket.bucket_end` -> `BugTrendChart.bucket_ends`。 |
| `bucket_granularity` | `string` | 隐藏字段；说明 daily/weekly。 | `JiraScopeConfig.bucket_granularity` -> `BugTrendCalculationRun.bucket_granularity` -> bucket/chart data。 |
| `calculation_run_id` | `string` | 隐藏字段；data link 必需。 | `BugTrendCalculationRun.id`，通过 chart API 带到每一 row。 |
| `bucket_id` | `string` | 隐藏字段；data link 必需。 | `BugTrendBucket.id`，通过 chart API 带到每一 row。 |
| `all_open_bugs` | `number` | 画一条 open bug 总数 series。 | `BugTrendBucket.open_count` -> `BugTrendSeriesDefinition('all_open_bugs')`。 |
| `all_open_critical_high` | `number` | 画一条 critical/high open bug series。 | `BugTrendBucket.open_critical_high_count` -> `BugTrendSeriesDefinition('all_open_critical_high')`。 |
| `new_critical_high` | `number` | 画新增 critical/high bug 柱。 | `BugTrendBucket.new_critical_high_count` -> `BugTrendSeriesDefinition('new_critical_high')`。 |
| `new_medium_low` | `number` | 画新增 medium/low bug 柱。 | `BugTrendBucket.new_medium_low_count` -> `BugTrendSeriesDefinition('new_medium_low')`。 |
| `fixed_or_closed_bugs` | `number` | 画 fixed/closed bug 柱，当前是负数向下。 | `BugTrendBucket.fixed_or_closed_count` 经过 `chart_sign=-1` 转成负值。 |

`contract_version` 不在 `columns` 里，因为它描述整个 API payload 的契约版本，不是某个 bucket row 的字段。Grafana spec 通过 `metricsContract.contractVersion` 声明自己期望的版本，parity check 会把它和 API response 的 `contract_version` 对齐检查。

这些 series 的定义在 [`bug_metrics/app/api/series.py`](../../../bug_metrics/app/api/series.py)。那里定义了 series id、图形类型 hint、对应的 bucket count field、颜色和正负号。

## 为什么有些字段隐藏，有些字段显示

Grafana 会把 table 里的字段交给 timeseries panel。我们只希望 number series 出现在图上，metadata 字段不要画出来。

所以 spec 里用 `fieldConfig.overrides` 隐藏这些字段：

| Field | 为什么隐藏 |
| ----- | ---------- |
| `bucket_end` | 对绘图不是 Y 值，只是 bucket metadata。 |
| `bucket_granularity` | 对绘图不是 Y 值，只是 daily/weekly metadata。 |
| `calculation_run_id` | 对绘图不是 Y 值，但点击 evidence 时需要。 |
| `bucket_id` | 对绘图不是 Y 值，但点击 evidence 时需要。 |

`bucket_start` 没有隐藏，因为它是 time axis。`bucket_label` 是 string category/label 字段，当前主要用于可读性和 contract 完整性；timeseries panel 的关键横轴字段是 `bucket_start`。

## 线和柱如何对应

Panel 默认设置是：

```json
"drawStyle": "bars"
```

这意味着默认所有 numeric series 都按柱状画。然后 spec 用 overrides 把两个累计类 series 改成线：

| Series | Override | 最终图形含义 |
| ------ | -------- | ------------ |
| `all_open_bugs` | `drawStyle: line`、`lineWidth: 2`、`fillOpacity: 0` | 当前仍然 open 的 bug 总量趋势。 |
| `all_open_critical_high` | `drawStyle: line`、`lineWidth: 2`、`fillOpacity: 0` | 当前仍然 open 的 critical/high bug 总量趋势。 |
| `new_critical_high` | 使用默认 bars | 每个 bucket 新增的 critical/high bug。 |
| `new_medium_low` | 使用默认 bars | 每个 bucket 新增的 medium/low bug。 |
| `fixed_or_closed_bugs` | 使用默认 bars，值为负数 | 每个 bucket fixed/closed 的 bug，向下显示。 |

所以最终图形不是“纯柱状图”或“纯折线图”，而是同一个 timeseries panel 里混合了两条线和三组柱。

## 点击图形如何回到 evidence

Spec 给所有字段配置了同一个 data link：

```text
/api/charts/evidence/?scope_id=$scope_id&begin=$begin&end=$end&chart_id=default_bug_trend&run=${__data.fields.calculation_run_id}&bucket=${__data.fields.bucket_id}&series=${__field.name}
```

点击某个 series 的某个 bucket 时，Grafana 会替换这些变量：

| Link 参数 | 来自哪里 | 用途 |
| --------- | -------- | ---- |
| `scope_id` | dashboard variable `$scope_id` | 限定 Jira scope。 |
| `begin` / `end` | dashboard variables `$begin` / `$end` | 保持和图表同一个查询范围。 |
| `chart_id` | spec 固定为 `default_bug_trend` | 告诉后端使用哪个 chart/evidence contract。 |
| `run` | 当前 row 的 `calculation_run_id` | 保证 evidence list 和图上的 calculation run 完全一致。 |
| `bucket` | 当前 row 的 `bucket_id` | 限定点击的是哪一个 bucket。 |
| `series` | `${__field.name}` | 限定点击的是哪一条 series，例如 `new_medium_low`。 |

这里的关键是 `series=${__field.name}`。因为 `grafana_rows` 是 wide shape，没有单独的 `series_name` 列；被点击的 numeric column name 本身就是 series id。

这个 evidence URL 在 Django 里由 [`ui_web/urls.py`](../../../ui_web/urls.py) 路由到 `BugTrendEvidenceApiView`，最后调用 [`ui_web/facades/bug_trend_facade.py`](../../../ui_web/facades/bug_trend_facade.py) 的 `get_evidence_data()`。真正的 evidence rows 来自 `BugTrendBucketIssue` membership artifact。

## 每个数据域的来源链路

下面是从最终 Grafana field 反查到后端 source 的路径。

| Grafana field | API shape | Facade 来源 | Domain 来源 | 数据库 artifact / source |
| ------------- | --------- | ----------- | ----------- | ------------------------ |
| `bucket_label` | `grafana_rows[].bucket_label` | `chart_data.labels[index]` | `BugTrendChart.labels` | `BugTrendBucket.bucket_start`/weekly label 规则。 |
| `bucket_start` | `grafana_rows[].bucket_start` | `chart_data.bucket_starts[index]` | `BugTrendChart.bucket_starts` | `BugTrendBucket.bucket_start`。 |
| `bucket_end` | `grafana_rows[].bucket_end` | `chart_data.bucket_ends[index]` | `BugTrendChart.bucket_ends` | `BugTrendBucket.bucket_end`。 |
| `bucket_granularity` | `grafana_rows[].bucket_granularity` | `chart_data.bucket_granularity` | `BugTrendChart.bucket_granularity` | `JiraScopeConfig.bucket_granularity` copied to calculation run/buckets。 |
| `calculation_run_id` | `grafana_rows[].calculation_run_id` | `chart_data.calculation_run_id` | `BugTrendChart.calculation_run_id` | `BugTrendCalculationRun.id`。 |
| `bucket_id` | `grafana_rows[].bucket_id` | `chart_data.bucket_ids[index]` | `BugTrendChart.bucket_ids` | `BugTrendBucket.id`。 |
| `all_open_bugs` | numeric column | `row[dataset['series_name']]` | `BugTrendDataset.values` | `BugTrendBucket.open_count`。 |
| `all_open_critical_high` | numeric column | `row[dataset['series_name']]` | `BugTrendDataset.values` | `BugTrendBucket.open_critical_high_count`。 |
| `new_critical_high` | numeric column | `row[dataset['series_name']]` | `BugTrendDataset.values` | `BugTrendBucket.new_critical_high_count`。 |
| `new_medium_low` | numeric column | `row[dataset['series_name']]` | `BugTrendDataset.values` | `BugTrendBucket.new_medium_low_count`。 |
| `fixed_or_closed_bugs` | numeric column | `row[dataset['series_name']]` | `BugTrendDataset.values` | `BugTrendBucket.fixed_or_closed_count * -1`。 |

`BugTrendBucket` 和 `BugTrendBucketIssue` 的模型定义在 [`bug_metrics/models.py`](../../../bug_metrics/models.py)。bucket 数值由 [`bug_metrics/app/api/calculation.py`](../../../bug_metrics/app/api/calculation.py) 计算，输入来自 [`jira_history/models.py`](../../../jira_history/models.py) 的 `JiraIssue`、`JiraIssueSnapshot`、`JiraTransition` durable history。

## 从 Jira 到图形的最短路径

1. Jira REST payload 被同步成本地 durable history：`JiraIssue`、`JiraIssueSnapshot`、`JiraTransition`。
2. `JiraScopeConfig` 定义哪些 issue 算 bug，哪些 status/resolution 算 open/fixed/closed，以及 bucket 是 daily 还是 weekly。保存时会统一拆分真实换行、escaped `\n` 和逗号分隔值，避免某个 chart 看到 `['P1-Critical\\nP2-High']` 这种不可匹配配置。
3. `BugTrendCalculationService` 生成一个 `BugTrendCalculationRun`。
4. 每个 bucket 生成一个 `BugTrendBucket`，里面有 open/new/fixed 的 count。
5. 每个 bucket/series 的 issue membership 写入 `BugTrendBucketIssue`，供 evidence drilldown 使用。
6. `bug_metrics` chart API 把 buckets 转成 `BugTrendChart`：包括 `labels`、`bucket_ids`、`bucket_starts`、`datasets`。
7. `BugTrendFacade.get_chart_payload()` 同时生成 `datasets`、`points`、`grafana_rows`。
8. Grafana target 选择 `$.grafana_rows`，把 rows 转成 table fields。
9. Grafana timeseries panel 用 `bucket_start` 做 X 轴，用 number fields 画线/柱。
10. 用户点击图形时，data link 带 `run + bucket + series` 回到 Metrics evidence API。

## `metricsContract` 为什么要写在 Grafana JSON 里

`metricsContract` 不是 Grafana 原生必须字段，它是 Metrics 自己放进 dashboard JSON 的机器可检查声明。它告诉 validator：这个 target 声称自己在消费什么 contract。

当前值是：

```json
{
  "chartId": "default_bug_trend",
  "contractVersion": "0.1",
  "root": "grafana_rows",
  "shape": "wide_bucket_series",
  "categoryField": "bucket_label",
  "requiredFields": ["calculation_run_id", "bucket_id", "bucket_label", "bucket_start", "bucket_end", "bucket_granularity"],
  "valueFields": ["all_open_bugs", "all_open_critical_high", "new_critical_high", "new_medium_low", "fixed_or_closed_bugs"],
  "evidenceLinkFields": ["calculation_run_id", "bucket_id"],
  "seriesFieldSource": "__field.name"
}
```

它和最终图形的关系是：

| Contract 字段 | 约束什么 | 为什么重要 |
| ------------- | -------- | ---------- |
| `chartId` | 必须匹配 target URL 里的 `chart_id`。 | 防止 URL 查 A 图，但 contract 声称自己是 B 图。 |
| `contractVersion` | 必须匹配 API response 的 `contract_version`，且在 allowlist 中。 | 防止 Grafana 用旧字段假设读取新 payload。 |
| `root` | Grafana target 必须读 `grafana_rows`。 | 防止误读 `points` 或其他 root。 |
| `shape` | 当前数据是 `wide_bucket_series`。 | 说明一行一个 bucket、多列 series。 |
| `categoryField` | 可读 category 是 `bucket_label`。 | 防止退回泛化 `label`。 |
| `requiredFields` | 每行必须带哪些 metadata。 | 保证图形和 evidence 可以追溯。 |
| `valueFields` | 哪些 number fields 是可画的 series。 | validator 能检查 Grafana 画的 series 是否被批准。 |
| `evidenceLinkFields` | evidence link 必须能拿到 run 和 bucket。 | 防止点击图形后查到别的 run 或别的 bucket。 |
| `seriesFieldSource` | series 来自被点击的 field name。 | 适配 wide row，没有 `series_name` 列。 |

机器 gate 在 [`scripts/validate_grafana_artifacts.py`](../../../scripts/validate_grafana_artifacts.py)。允许的 root/shape/API surface 在 [`openspec/docs/current-baseline/grafana-approved-data-surfaces.json`](grafana-approved-data-surfaces.json)。

## 修改这个 spec 时最容易犯的错

- 把 `root_selector` 改成 `$.points`，但仍然用 timeseries wide table 的 columns。
- 新增一个 numeric series，却忘了同时更新 `columns`、`metricsContract.valueFields`、series definition 和 parity check。
- 把 `calculation_run_id` 或 `bucket_id` 从 columns 里删掉，导致图能画但 evidence link 失去精确定位。
- 把 `series=${__field.name}` 改成 `series=${__data.fields.series_name}`，但 `grafana_rows` 里没有 `series_name`。
- 在 Grafana JSON 里硬编码 Jira status/severity 业务语义。业务语义必须留在 `JiraScopeConfig` 和 calculation artifacts 里。

## 修改后应该跑什么检查

最小检查：

```powershell
.venv\Scripts\python.exe scripts\validate_grafana_artifacts.py --artifact-root ops\grafana --allowlist openspec/docs/current-baseline/grafana-approved-data-surfaces.json
```

如果改了 API shape、series、evidence link 或 chart data projection，再跑 parity check：

```powershell
.venv\Scripts\python.exe scripts\compare_grafana_bug_trend_parity.py --calculation-run-id <run-id> --begin <YYYY-MM-DD> --end <YYYY-MM-DD>
```

如果改了 Django route/view/facade，再加：

```powershell
.venv\Scripts\python.exe manage.py check
```

# AI Base 与 gcx 的 Metrics Dashboard Contract

日期：2026-08-31

## 目标

本文件定义 `D:\AIGC\Report_creater_agent\` 中的可选 AI base，以及其中通过 `gcx` 操作 Grafana 的工具，如何与 Metrics dashboard 协作。

核心原则是：AI 可以提出 dashboard/chart 变更方案，Grafana/gcx 可以执行受控的渲染或导入动作，但 Metrics 仍然拥有 provider profile、chart recipe、facts、aggregate、evidence、validator、publication audit 和 source credentials。

## 运行依赖关系

AI base 是 optional client，不是 Metrics dashboard 的 runtime dependency。

- 当 AI base 未安装、未启动或禁用时，Metrics 仍 SHALL 支持 provider sync、profile selection、cache、approved charts、Grafana render config 生成、evidence API 和 deterministic dashboard API。
- AI base SHALL 只通过 Metrics 暴露的 catalog、intent validation、render-config validation 和 evidence/query contract 读取能力。
- AI base SHALL NOT 直接读取 Jira/HSD-ES credentials、直接调用 provider API、直接 patch Metrics backend code/API、生成任意 SQL，或绕过 Metrics validator 发布 Grafana artifact。

## Metrics 侧 Contract

Metrics 侧首版 contract 对应 `bug_metrics.app.api.ai_context` 中的 structured DTO/service：

| Contract | 作用 |
| --- | --- |
| `DashboardCompositionIntent` | 表达 AI 从用户 prompt 中解析出的 dashboard/chart intent，包括 `profile_id`、`dashboard_uid`、`chart_id`、requested series、range mode、range start/end 和 output type。 |
| composition catalog response | 给 AI base 的只读 catalog，包含可用 profiles、chart recipes、allowed series、range modes、support status 和 row/time limits；不包含 provider credentials 或可直接执行的 native query text。 |
| draft render config | AI 可以生成的小型 Grafana render config draft；它只引用 approved profile、chart recipe、category field、value fields、evidence capability 和 Metrics API data surface。 |
| validation findings | Metrics 返回结构化 `code/message/severity/field`，由 AI base 展示给用户或决定下一步。 |
| `needs_metric_recipe` | 当用户要求新的业务语义，例如 `new_critical` 而当前只有 `new_critical_high`，Metrics 返回该状态，要求先新增 Metrics-owned chart recipe/profile mapping。 |
| `GcxPublicationPreconditionRequest` | gcx mutation 前的 Metrics precondition gate；只有通过 Metrics render-config/artifact validator 后才允许进入 gcx import/push/snapshot 流程。 |
| publication/audit metadata | 记录 actor、operation、validation status、approval state 和 mutation allowed，用于 Metrics audit 与 AI base activity 对齐。 |

## 推荐交互流程

```text
User prompt
  -> AI base Dashboard Query Agent
  -> Metrics composition catalog
  -> DashboardCompositionIntent
  -> Metrics intent validator
  -> Draft render config or needs_metric_recipe
  -> Metrics gcx publication precondition
  -> gcx validate/import/push dry-run
  -> user/operator approval
  -> gcx mutation
  -> Metrics audit record
```

## 关键规则

1. `profile_id` 是第一选择器。AI base 不应让 provider、project、tenant、milestone 这些 profile-derived 字段脱离 profile 独立漂移。
2. `range_mode` 只允许使用 selected profile 支持的 mode，例如 `ww` 或 `date`。
3. Requested series 必须 exact-match Metrics chart recipe 的 approved series。`new_critical` 不能自动映射成 `new_critical_high`。
4. Render-only 变更可以只隐藏或显示已有 series；业务语义变更必须先进入 Metrics-owned chart recipe。
5. gcx mutation 前必须调用 Metrics precondition validator。precondition failure SHALL block mutation before any Grafana import/push command runs。
6. AI base/gcx 不保存 Jira、HSD-ES、Intel source credentials。Grafana service account credentials 如果需要，应只属于 Grafana operation boundary，并受 AI base 的 tool governance 与 deployment secret policy 管理。
7. AI absence 不影响 non-AI dashboard；AI integration failure 不应破坏现有 provider sync/cache/chart render path。

## 示例：`new_critical` 请求

用户请求：

```text
Create a weekly open bug trend from WW10 to WW35, only show new critical, not New critical/high.
```

当前 `open_bug_trend` recipe 只批准：

```text
all_open_bugs
all_open_critical_high
new_critical_high
new_medium_low
fixed_or_closed_bugs
```

因此 Metrics SHALL 返回：

```text
status = needs_metric_recipe
finding.code = unapproved_series
needs_metric_recipe.requested_series = ["new_critical"]
needs_metric_recipe.available_series includes "new_critical_high"
```

AI base 可以向用户解释需要新增 Metrics-owned critical-only series。它不能把 `new_critical_high` 改 label 伪装成 critical-only，也不能 patch Metrics code 临时计算。

如果用户改成：

```text
Only show existing new_critical_high.
```

Metrics MAY 返回 `draft_validated`，并生成 render config draft，其中 `value_fields = ["new_critical_high"]`。

## gcx 集成边界

`gcx` 是 Grafana operation interface/skill，不是 Metrics semantic owner。建议 AI base 中的 `dashboard_query_agent` 使用 typed tools 绑定 `gcx` 的有限命令形态：

| Tool class | Mutation | Precondition |
| --- | --- | --- |
| catalog/search/snapshot/read-only validate | no or low-risk | Metrics catalog context recommended |
| resources validate | no | Metrics artifact validator must pass first |
| resources push dry-run | no production mutation | Metrics precondition must pass |
| resources push/import/update | yes | Metrics precondition pass + dry-run evidence + user/operator approval |

禁止开放 raw shell 或任意 `gcx api` passthrough 作为默认工具。若以后需要 raw API，需要独立 allowlisted path/method wrapper。

## 测试要求

- Metrics focused tests SHALL cover catalog response without credentials/native query text。
- Metrics focused tests SHALL cover `needs_metric_recipe` for unapproved exact series。
- Metrics focused tests SHALL cover render-only draft approval for approved series subset。
- Metrics focused tests SHALL cover gcx precondition blocking invalid render configs before mutation。
- AI base repo SHOULD add mocked Metrics contract tests，确保其 connector 不直接读取 provider credentials、不生成 raw SQL、不绕过 precondition。


## Context

See `proposal.md` for motivation. 当前实现已经具备几个正确方向：Grafana panel 调用 Metrics-owned `/api/provider-charts/data/`，chart payload 带 `profile_id`、`chart_id`、`chart_version`、range 和 provenance；HSD-ES live sync/cache 已经能把 `nvu-ttl-hsdes` materialize 到 local artifacts；Grafana allowlist validator 已经禁止 unapproved datasource、provider-native literals、secret-like fields 和 panel-local business calculations。

但实现仍有几个会阻碍 Jira 扩展和 AI composition 的点：

- Profile truth 仍散在常量和条件分支里，例如 `FIRST_JIRA_PROFILE_ID`、`FIRST_HSDES_PROFILE_ID`、`FIRST_PROVIDER_STATIC_SCOPE_LABELS`、`SUPPORTED_JIRA_CHARTS` 和 `SUPPORTED_HSDES_SEED_CHARTS`。
- `ProviderChartAggregateService` 仍按 provider 分支分别构造 Jira rows 与 HSD-ES rows，chart behavior 有重复。
- `ProviderAggregateArtifact` 和 `ProviderCacheIdentity` 已经 provider/profile agnostic，但 range identity 仍以 `begin_ww` / `end_ww` 为核心。
- `sync_hsdes_profile` 是 single-profile command，无法作为 Jira/HSD-ES/future provider 的统一 sync入口。
- `ops/grafana/provider_parity_dashboard.json` 是大型手写 JSON，validator 有效，但作者体验和 AI 生成体验都太重。
- AI base `D:\AIGC\Report_creater_agent\` 已有 profile manifest、shared runtime、tool binding 和 `gcx` CLI tool runner 方向；它适合做 optional sidecar/operator，不适合成为 Metrics 的 data/semantic owner。

## Goals / Non-Goals

**Goals:**

- 用 registry 把 provider/profile/source/field/chart support 从代码常量迁到 versioned configuration。
- 让 chart recipe 和 aggregate calculator 尽量基于 canonical facts，而不是 provider-specific row builders。
- 用小型 render config 生成 Grafana JSON，让 dashboard layout/style/evidence links 可维护、可验证、可被 AI 安全提案。
- 定义 Metrics 与 AI base/gcx 的 contract：AI 可以生成 draft config 和调用受控 Grafana operation，但不能改 Metrics 后端代码或绕过 Metrics validator。
- 给 Jira provider 后续 dashboard 实现提供与 HSD-ES 同级的通用路径。

**Non-Goals:**

- 不在本 change 中实现 AI base 的 `dashboard_query_agent` profile。
- 不让 AI、gcx 或 Grafana 直接访问 Jira/HSD-ES credentials。
- 不把 user natural language 自动转换成新的 business metric 并立即发布。
- 不一次性重写全部 legacy Jira durable history tables；可以通过 adapter/compatibility layer 渐进迁移。
- 不在此阶段开启 execution、automation、shift-left、escaped bug 的未确认 provider mappings。

## Decisions

### Decision 1: Profile registry becomes the first lookup for provider behavior

Metrics 增加 Project Provider Profile Registry，先支持文件/YAML 或 settings-backed config，后续可迁移到 DB-backed profile editor。Registry 输出一个稳定 DTO：

```text
ProjectProviderProfile
  profile_id
  provider_id
  display_name
  enabled
  source_population
  scope_labels
  field_bindings
  value_mappings
  chart_bindings
  mapping_version
  mapping_version_hash
  sync_policy
  readiness_policy
```

所有入口先解析 `profile_id`：Grafana chart API、readiness API、sync command、AI catalog API。显式 `provider_id` 如果存在，只能作为一致性校验，不能覆盖 profile 派生结果。

Alternative considered：保留代码常量，只给 Jira 新增一个分支。放弃，因为它会把第二个 Jira project、第二个 HSD-ES query 和未来 provider 都推向复制粘贴。

### Decision 2: Provider adapters produce canonical facts, chart recipes consume canonical facts

目标 flow：

```text
ProjectProviderProfile
  -> ProviderAdapter sync/read
  -> ProviderFactSnapshot + ProviderFact(canonical_fields, project_fields, provider_fields)
  -> ChartRecipeCalculator
  -> ProviderAggregateArtifact
  -> Grafana render config / AI evidence
```

短期可以保留 Jira legacy calculation run 与 HSD-ES live fact snapshot 的 compatibility adapters，但新的 chart calculator 接口应接收 canonical facts 或 materialized bucket facts，而不是 Jira model 或 HSD-ES article shape。这样 Jira dashboard 的新增 chart 和 HSD-ES dashboard 的同类 chart 共享 recipe contract。

Alternative considered：为 Jira 和 HSD-ES 各自维护一套 calculators。放弃，因为同一 chart 的 series 语义会漂移，AI 也无法可靠知道某个 series 在两个 provider 之间是否等价。

### Decision 3: Chart recipe catalog is separate from Grafana render config

Chart Recipe Catalog 定义业务语义：

```text
chart_id
chart_version
metric_family
required_canonical_fields
required_project_fields
series_contract
bucket_grains
evidence_capability
provider_binding_requirements
support_state_policy
```

Grafana Render Config 定义显示语义：

```text
dashboard_uid
variables
rows/sections
panels
panel_type
layout
chart_recipe_ref
category_field
value_fields
legend/axis/color/stacking
evidence_link
```

这两个 catalog 版本化但分开演进。新增 business meaning，例如 `new_critical`，必须先进入 Chart Recipe Catalog；仅隐藏某个已有 series 可以只改 Render Config。

Alternative considered：让 Grafana JSON 同时定义 chart 语义和显示。放弃，因为这会绕过 Metrics audit，并让 AI 生成配置时很容易生成不可验证的业务逻辑。

### Decision 4: Grafana JSON is generated, not authored as the main truth

`ops/grafana/provider_parity_dashboard.json` 后续应成为 generated artifact。人工和 AI 都编辑小型 render config，例如：

```yaml
dashboard_id: ip-quality-dashboard
profile_variable: profile_id
range_controls:
  modes: [ww, date]
sections:
  - id: quality
    panels:
      - panel_id: open_bug_trend
        chart_id: open_bug_trend
        chart_version: 1
        type: timeseries
        category_field: bucket_label
        value_fields:
          - all_open_bugs
          - all_open_critical_high
          - new_critical_high
          - new_medium_low
          - fixed_or_closed_bugs
```

Generator 输出 deterministic dashboard JSON，validator 同时检查 render config 与 generated JSON。Generated JSON 可提交，但 code review 的核心对象应是 render config diff。

Alternative considered：继续手改 JSON，并只加强 validator。放弃，因为 panel JSON 过大，不适合 AI 产出、人工 review 或多 dashboard 变体维护。

### Decision 5: AI sidecar generates proposals, Metrics validates and publishes

AI base/gcx 的安全边界如下：

```text
User prompt in AI sidecar or Metrics sidebar
  -> AI base parses DashboardCompositionIntent
  -> Metrics catalog/profile APIs validate vocabulary
  -> AI returns DraftRenderConfig or NeedsMetricRecipe
  -> Metrics validator checks draft
  -> optional gcx validate/import/push through approved CLI templates
  -> Metrics records publication/audit
```

AI base 可以拥有 chat UX、model routing、tool execution、approval UX 和 `gcx` operation tools。Metrics 仍拥有 profile registry、chart recipe catalog、fact/evidence APIs、render-config validator、publication approval 和 provider credentials。

对于用户例子“WW10-WW35 weekly open bug trend，只显示 new critical，不要 New critical/high”：如果 catalog 只有 `new_critical_high`，正确结果不是改代码，也不是改 Grafana label，而是返回 `needs_metric_recipe` 或 validation failure，说明需要先定义 critical-only 的 Metrics-owned recipe/series 和 provider field mapping。若用户改为“只显示 existing `new_critical_high`”，AI 可生成 render-only visibility draft。

Alternative considered：AI 直接 patch Python/API 或让 gcx 导入 AI 写的 dashboard JSON。放弃，因为 audit、code quality、provider credentials 和 semantic ownership 都无法控制。

### Decision 6: Cache identity becomes range-neutral

现有 cache 已有 provider/profile/source/mapping/chart/snapshot identity，但 `ProviderAggregateArtifact` 和 query API 仍偏向 WW。下一步应增加 normalized fields：

```text
range_mode
range_start
range_end
range_grain
range_label_start
range_label_end
```

迁移期可保留 `begin_ww` / `end_ww` 作为 compatibility fields。`range_mode=date` 不能命中仅由 WW identity 产生的 artifact；`range_mode=ww` 应把 WW 解析成 calendar start/end 并记录两套 label/provenance。

Alternative considered：只在 URL 层做 WW/date 转换。放弃，因为 AI、cache、evidence 和 performance tests 都需要统一 artifact identity。

### Decision 7: AI/Grafana public APIs expose catalog before mutation

Metrics 应提供 read-only catalog endpoints 或 equivalent internal services，供 AI base、Metrics UI 和 validators 使用：

```text
GET /api/provider-profiles/
GET /api/provider-profiles/{profile_id}/readiness
GET /api/provider-chart-recipes/
POST /api/grafana/render-config/validate
POST /api/grafana/render-config/preview
POST /api/grafana/render-config/publish
POST /api/ai-dashboard/intent/validate
```

第一阶段可以用 Django internal services and management scripts 驱动，不必一次公开所有 HTTP endpoints。但 DTO/schema 必须先稳定，避免 AI base 与 Metrics 两边各自猜字段。

Alternative considered：让 AI base 读取 repository files 自己推断 catalog。放弃，因为文件结构不是 runtime contract，也不能表达当前 profile enablement、permissions、freshness 和 user authorization。

## Risks / Trade-offs

- [Risk] 抽象过早导致实现变慢。Mitigation：先做 registry + render config + validators 的最小纵切，保留 compatibility adapters，逐步删除 hardcode。
- [Risk] AI 用户期望“说一句就生成任意 chart”。Mitigation：明确 `render-only`、`needs_metric_recipe`、`unsupported` 三类输出，业务新语义必须走 Metrics recipe/profile change。
- [Risk] Generated Grafana JSON diff 仍然很大。Mitigation：code review 以 render config 和 generator tests 为主，generated JSON 只看 validator结果和关键 snapshot。
- [Risk] Cross-repo AI base contract drift。Mitigation：Metrics 输出 schema snapshots；AI base 用 contract tests mock Metrics API；gcx mutation 要求 Metrics precondition validator。
- [Risk] Jira legacy tables 与 provider-neutral facts 并存一段时间。Mitigation：定义 compatibility adapter，要求新 APIs 返回 provider-neutral DTO，迁移完成后再减少 legacy coupling。
- [Risk] `new_critical` 与 `new_critical_high` 这类语义差异被 UI label 模糊。Mitigation：validator 要求 exact series id 与 recipe version，label 不能改变 metric meaning。

## Migration Plan

1. 建立 profile registry schema 和 loader，将 `chiplet-2a-jira`、`nvu-ttl-hsdes` 从代码常量迁到 versioned profile configs。
2. 建立 chart recipe catalog loader，将 allowlist 中的 provider chart recipes 提升为 runtime/test 共用 catalog，并保留现有 allowlist作为 validator 输入。
3. 把 provider readiness、chart aggregate query、sync command 改为从 registry dispatch，保留 legacy profile id compatibility tests。
4. 将 HSD-ES/Jira chart row builders 收敛到 canonical-fact calculator interface；无法一次迁移的 Jira calculation runs 通过 compatibility adapter 输出 canonical facts/bucket facts。
5. 增加 range-neutral artifact identity fields，迁移旧 `begin_ww` / `end_ww` artifact 查询为 compatibility path。
6. 新增 render config schema、generator 和 validator，生成现有 `ip-quality-dashboard` JSON，并验证生成物与现有 dashboard 的关键 panel/API contract 等价。
7. 新增 AI dashboard composition DTO/schema and validator，包括 `DashboardCompositionIntent`、`DraftRenderConfig`、`NeedsMetricRecipe`、validation findings 和 audit record。
8. 与 AI base/gcx 集成时，先走 read-only/validate/preview，再允许 operator-approved `gcx` import/push；任何 publish 都要求 Metrics validator pass。

Rollback strategy：保留现有 `ops/grafana/provider_parity_dashboard.json` 和 current chart API contract；如果 registry/generator 失败，可继续使用当前 selected-profile dashboard，同时不启用 AI draft publish。

## Open Questions

- `gcx` 的生产发布动作最终是由 Metrics repo 命令触发、AI base tool 触发，还是 CI/CD 触发；这影响 publish approval UI，但不影响本 change 的 contract。
- Profile registry 首版使用 YAML 文件还是 DB-backed model；建议先 YAML/config file，等 profile editor 成熟后迁移 DB。
- 是否要把 `grafana-dashboard-parity` 从之前 completed change archive 到 main specs 后再 apply 本 change；这影响 archive 顺序，但不影响本 change 的新增 `grafana-render-config` capability。

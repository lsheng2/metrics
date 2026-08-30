## Context

当前 dashboard 已经形成几个重要约束：Grafana panel 通过 Metrics-owned provider chart API 读取 `grafana_rows`；HSD-ES offline seed 通过 `HsdesProviderProjectionService` 投影成 normalized facts 后进入同一个 aggregate contract；Jira sync 已有 cursor、running guard、config hash stale 判断和 failure status 先例；metadata discovery 已有 TTL cache 和 refresh bypass 先例。

本 change 需要把 HSD-ES 从 seed-backed preview 推进到 live sync，同时避免把缓存机制做成 HSD-ES 专属。新的设计应抽象为 provider/profile agnostic 的 sync/cache/materialization contract，HSD-ES `nvu-ttl-hsdes` saved query 只是第一个落地 profile。

## Goals / Non-Goals

**Goals:**

- 让 live provider data 通过 explicit sync/materialization 进入本地 durable facts 和 aggregate artifacts。
- 保持 Grafana、Metrics UI 和 AI 的 dashboard read path 低延迟、只读本地 artifacts。
- 定义 provider-neutral cache identity、freshness states、debug bypass、single-flight 和 failure fallback。
- 让 HSD-ES live sync 复用现有 provider chart aggregate contract，并保留 `queryId=15017652869`、tenant、subject、criteria/hash 和 field-set provenance。
- 建立 focused、fake、performance 和 live smoke test 的实施边界。

**Non-Goals:**

- 不在本 change 中启用 provider writes。
- 不让 Grafana panel 直接调用 Jira JQL、HSD-ES EQL 或任何 external provider API。
- 不把浏览器 SSO session 当作 Django backend credential。
- 不把 execution、automation、shift-left、escaped bug 的未确认 HSD-ES field mappings 顺手补齐。
- 不在首轮强制抽象所有 Jira history models；可以先新增 provider-neutral cache/fact artifact 边界，再逐步迁移 Jira。

## Decisions

### Decision 1: Dashboard render path reads local artifacts only

选择：Grafana 和 Metrics UI 继续通过 Metrics provider chart API 读取本地 aggregate artifacts。Live HSD-ES API 只在 sync/preflight/debug 操作中出现。

原因：HSD-ES API latency、auth、permission、rate limit 和 internal network 稳定性不应影响 dashboard page load。这个选择也延续了现有 Jira durable sync 原则。

Alternative considered：Grafana panel refresh 时直接 live-query HSD-ES。放弃，因为它会导致高延迟、凭证暴露风险、provider outage 影响页面、测试不可确定，并且违背现有 durable dashboard consumption spec。

### Decision 2: Cache identity is provider/profile agnostic

选择：cache key 和 artifact identity 使用 provider-neutral fields：provider id、profile id、source query ownership/ref/hash、tenant or space、subject or item type、field-set hash、mapping version hash、chart id/version、range 和 fact snapshot id。

原因：HSD-ES 的 `queryId`、Jira 的 JQL、未来 GitHub 的 search query 或 Azure WIQL 都是 source population 的不同 native 表达；缓存机制关心的是“这个 profile 的哪个 source population 和哪个 mapping 生成了哪个 artifact”，不是 provider 的具体语法。

Alternative considered：为 HSD-ES 建 `hsdes_cache_key` 并包含 raw HSD-ES 字段。放弃，因为后续 Jira/HSD-ES/GitHub 会产生多套缓存规则，Grafana 和 AI 也更容易泄露 native query 语义。

### Decision 3: Use layered cache/materialization

设计分层：

- L0 request/process cache：同一 render window 内减少重复本地读取或重复计算，不作为事实来源。
- L1 durable provider snapshot/facts：保存 raw snapshot provenance 和 normalized facts，是 sync 后的 provider fact authority。
- L2 aggregate artifact cache：保存 Grafana-ready chart rows，是 dashboard 低延迟读取的直接来源。
- Metadata cache：保存 provider metadata/options，使用 TTL 和 refresh bypass，类似现有 Jira metadata discovery。

原因：raw provider response、normalized facts、chart aggregate rows 的失效条件不同；混在一个 cache 里会让 debugging、stale 判断和 evidence provenance 都变难。

Alternative considered：只缓存最终 Grafana JSON。放弃，因为 AI/evidence/drilldown 需要 fact-level provenance，且 mapping 或 chart recipe 变化时需要重新 aggregate。

### Decision 4: Cache is enabled by default, but disabling cache does not change source-of-truth

选择：提供 generic config knobs，例如 `METRICS_PROVIDER_CACHE_ENABLED=true`、`METRICS_PROVIDER_CACHE_TTL_SECONDS`、`METRICS_PROVIDER_METADATA_CACHE_SECONDS`、`METRICS_PROVIDER_SYNC_STALE_AFTER_SECONDS`。Provider-specific overrides 可以后续增加，但默认语义必须来自 generic knobs。

禁用 cache 时，sync/debug operation 可以绕过 cache read 并重新拉 provider；dashboard render path 仍读这次物化后的本地 artifacts。

原因：用户需要 debugging knob，但不应因为 debug 而把 Grafana 改成 live external-query path。

Alternative considered：只提供 `METRICS_HSDES_CACHE_ENABLED`。放弃，除非作为 optional override，因为用户明确要求 cache design provider/profile agnostic。

### Decision 5: Preserve last successful data on sync failure

选择：sync 失败时记录 cursor/status/error category，不清空上一份成功 artifacts。Chart API 可以返回 latest successful artifact 并标记 stale，也可以在 chart policy 不允许 stale 时返回 unavailable。

原因：生产 dashboard 中“旧但明确标记的数据”通常比“失败后变成 0 或空图”更安全。错误状态必须由 Data Health/readiness 暴露。

Alternative considered：失败即删除或覆盖 artifacts。放弃，因为这会制造 misleading zero data，也破坏问题诊断。

### Decision 6: Add single-flight protection for refresh

选择：对同一 provider/profile/source/range identity 的 sync/refresh 使用 running cursor、database lock 或 equivalent single-flight guard。并发请求看到 running/stale/latest-successful 状态，而不是同时打 provider。

原因：Grafana 多 panel、多人打开 dashboard 或自动刷新时容易造成 stampede；HSD-ES saved query 可能比本地 aggregate 昂贵得多。

Alternative considered：只依赖 provider rate limit 或 retry。放弃，因为那会把压力推给外部系统，并降低本地 dashboard 的可预测性。

### Decision 7: HSD-ES live adapter is thin and documented-first

选择：HSD-ES adapter 负责 auth、saved query/EQL execution、pagination、field expansion、permission/error normalization、raw response capture 和 projection call。Endpoint shape、auth mode、pagination 和 schema 必须以 Intel HSD-ES authoritative API wiki 为准。

原因：现有 browser SSO 和 UI download 只能证明人能看到数据，不能证明 Django backend 已有可复用 credential，也不能替代 API contract review。

Alternative considered：直接复用浏览器 session/cookies 或下载文件作为 production path。放弃，因为不可自动化、不可审计，也不适合 scheduled sync。

## Risks / Trade-offs

- [Risk] Live HSD-ES API auth mode 与本地开发环境不一致 -> Mitigation：先做 API preflight 和 backend credential doc，live tests 只在显式配置后运行。
- [Risk] Saved query criteria or field set drift 导致图表语义变化 -> Mitigation：记录 query/hash、field-set hash、mapping version；drift 时标记 configuration-required/stale。
- [Risk] Cache disabled 被误认为 Grafana 会实时查询 provider -> Mitigation：spec 和 docs 明确 disable cache 只影响 sync/debug cache read，不改变 dashboard local-artifact source-of-truth。
- [Risk] Large HSD-ES result set 导致 sync 慢 -> Mitigation：分页、dedupe、incremental cutoff when supported、aggregate materialization、performance tests 和 single-flight。
- [Risk] Provider-neutral abstraction过早导致复杂 -> Mitigation：先定义 cache identity/status/freshness 的最小 shared contract；HSD-ES 具体 API 仍保留在 adapter module。

## Migration Plan

1. 保留当前 seed-backed HSD-ES preview，不破坏现有 Grafana dashboard。
2. 添加 generic cache/freshness settings，默认启用 cache。
3. 添加 provider-neutral sync/cache DTOs、status values 和 fake provider tests。
4. 添加 HSD-ES live adapter preflight，并根据官方 API 文档实现 saved query fetch。
5. 添加 durable HSD-ES snapshot/facts/cursor/materialized aggregate artifacts。
6. 将 `nvu-ttl-hsdes` readiness 从 `seeded_preview` 升级为 live-aware 状态：未配置时仍明确 blocked/configuration-required，配置并成功同步后显示 live synced。
7. 扩展 Data Health 和 runtime validation，确认 Grafana 渲染路径仍不调用 HSD-ES live API。

Rollback strategy：关闭 live sync 配置后回到 seed-backed preview 或 latest successful local artifact；保留旧 artifacts 和 sync failure 状态用于诊断。

## Open Questions

- HSD-ES backend credential 的最终 production 形式是 Kerberos、token、basic auth 还是其他 Intel 内部机制，需要以官方 API wiki 和环境约束确认。
- 首版 performance thresholds 建议在实现时用本地 fake 10k/50k articles 测量后定稿，但 chart API p95 应以低延迟本地读取为目标。

## Implementation Notes

### 2026-08-30 live sync checkout

- 已基于项目记录的 HSD-ES API wiki 摘要实现 adapter 边界：production REST base 默认为 `https://hsdes-api.intel.com/rest`，saved query 使用 `/query/execution/{queryId}`，分页使用 `start_at` / `max_results`，Windows 本地 Kerberos/Integrated Auth 通过 PowerShell `Invoke-WebRequest -UseDefaultCredentials -UseBasicParsing` transport 封装在 HSD-ES adapter 内。
- 已验证 `queryId=15017652869` live access：`nvu-ttl-hsdes` sync 成功返回并物化 390 条 facts、6 个 aggregate artifacts；Grafana/API read path 返回 `live_synced`，并保持只读本地 aggregate artifacts。
- Live API 返回的 article 字段是扁平字段 shape，seed preview 使用 `fieldValues` 嵌套 shape；projection 已统一支持两种输入并映射到相同 canonical fields。
- Cache/materialization 仍是 provider/profile agnostic：shared cache identity、fresh/stale/unavailable/running/failed/configuration-required states、TTL/stale fallback、debug bypass、single-flight cursor、Data Health、readiness 和 AI context 都走 provider-neutral status/provenance。
- Live/performance tests 默认显式门控：`METRICS_HSDES_LIVE_SYNC_ENABLED=true` 才运行 live smoke；`METRICS_RUN_PROVIDER_PERF_TESTS=true` 才运行 10k/50k synthetic performance gate。

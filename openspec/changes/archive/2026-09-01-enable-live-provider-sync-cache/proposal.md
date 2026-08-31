## Why

当前 HSD-ES dashboard 已能通过 offline seed data 渲染，但 production 目标需要从同一个 HSD-ES saved query 拉取 live data，同时保持 Grafana 低延迟、可追溯、可测试。这个能力不应做成 HSD-ES 专属缓存，而应成为 provider/profile agnostic 的通用同步与缓存机制，供 Jira、HSD-ES 和后续 provider 复用。

## What Changes

- 引入 provider-neutral sync/cache contract：以 provider、profile、source query、field set、mapping version、chart recipe 和时间范围作为缓存与物化边界。
- 增加 durable provider facts snapshot 和 aggregate artifact cache，Grafana render path 继续只读 Metrics-owned local artifacts，不直接 live-query external provider。
- 支持 cache enabled by default，并通过配置开关禁用缓存用于 debugging；禁用缓存不改变 dashboard source-of-truth，仍需通过 sync/materialization 生成本地 artifacts。
- 为 live provider sync 增加 stale-while-revalidate、last-successful artifact fallback、single-flight/stampede protection、cache freshness metadata 和 Data Health 可观测状态。
- 将 HSD-ES `nvu-ttl-hsdes` / `queryId=15017652869` 定义为第一个使用该 generic cache contract 的 live sync 场景。
- 增加 fake/deterministic/live/performance test strategy，覆盖功能正确性、缓存行为、并发保护、性能门槛和真实 provider smoke test。

## Capabilities

### New Capabilities

- `provider-sync-cache`: 定义 provider/profile agnostic live sync、durable facts snapshot、aggregate artifact cache、freshness/status 和测试要求。

### Modified Capabilities

- `provider-facts-and-sync`: 明确 live provider sync 如何产生 durable facts/aggregate artifacts，并规定 HSD-ES saved query live data 接入同一 provider-neutral contract。
- `work-item-provider-platform`: 明确通用 cache/materialization 属于 shared provider platform contract，provider-specific modules 只拥有外部 API quirks。

## Impact

- Affected modules likely include future `provider_sync` or `hsdes_sync`, `bug_metrics` provider aggregate APIs, Data Health APIs/UI, settings, management commands, and focused tests.
- Existing Grafana dashboard/data API contracts should remain stable; panels should continue requesting Metrics chart data by `profile_id`, `begin_ww`, `end_ww`, `chart_id`, and optional snapshot/run identifiers.
- HSD-ES implementation must consult the Intel HSD-ES authoritative API wiki before coding endpoint, auth, pagination, permission, or response-schema behavior.
- No breaking changes are intended for the current seed-backed HSD-ES preview; live sync should upgrade freshness/status when configured and preserve explicit fallback states when not configured.

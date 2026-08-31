## Why

当前 HSD-ES offline/live dashboard 已经证明 provider chart API、cache 和 Grafana allowlist 可行，但实现仍把 `chiplet-2a-jira`、`nvu-ttl-hsdes`、chart support、scope labels 和部分 chart rendering 规则写在代码或单个大型 Grafana JSON 中。下一步要启动 Jira dashboard 扩展和 AI 侧栏/sidecar，就需要先把 provider profile、chart recipe、Grafana render config 和 AI-generated dashboard draft 的边界固化，否则 Jira 与 HSD-ES 会继续变成两套平行逻辑。

## What Changes

- 新增 Project Provider Profile Registry，统一管理 provider id、profile id、source population、field bindings、value normalization、scope labels、mapping version、chart support 和 readiness，不再依赖 first-profile 常量。
- 新增 provider-neutral Chart Recipe Catalog 与 calculator binding contract，让 Jira/HSD-ES adapter 输出 canonical facts，Metrics chart calculators 基于 canonical fields 计算 aggregates，减少 provider-specific branch duplication。
- 新增 Grafana Render Config capability，用 YAML/JSON render config 生成 Grafana dashboard JSON，并用 validator 保证 panel 只引用 approved Metrics APIs、chart recipes、series、category fields、evidence capabilities 和 datasource。
- 新增 AI Dashboard Composition contract：AI base app `D:\AIGC\Report_creater_agent\` 与 `gcx` 只能通过 Metrics 暴露的 catalog/profile/render APIs 生成 draft render config 或 Grafana artifact proposal，不能直接改 dashboard backend code/API、调用 provider credentials、写任意 SQL 或发布未验证 dashboard。
- 明确 AI chart request 的治理：例如用户要求“WW10 到 WW35 weekly open bug trend，只显示 new critical，不包含 new critical/high”时，AI SHALL 先解析 intent，再向 Metrics catalog 验证是否存在 approved `new_critical` series；如果当前只有 `new_critical_high`，AI SHALL 生成 rejected/needs-metric-proposal 状态或要求新增 Metrics-owned chart recipe，而不是伪造 series 或改代码。
- 将 provider sync/cache 的 identity 从 WW-only 继续推进到 range-mode-neutral，使 `ww` 和 `date` 两种 range 都能作为 aggregate artifact identity 的一部分。
- 将 HSD-ES-specific sync command 目标推广为 generic provider/profile sync 命令，具体 provider 逻辑通过 registry/adapter dispatch。
- 不在本 change 中实现 AI base app 或 `gcx` 本身；本 change 只定义 Metrics 侧 contract、validator、artifact 和实施任务。

## Capabilities

### New Capabilities
- `provider-profile-registry`: 定义 Project Provider Profile Registry、profile schema、source population、field binding、scope labels、chart support/readiness 和 provider dispatch。
- `grafana-render-config`: 定义从 Metrics-owned render config 生成 Grafana JSON 的 contract、validator、dashboard/panel schema、profile selector/range controls、approved data-surface binding 和 publication workflow。
- `provider-ai-dashboard-composition`: 定义 AI base/gcx 与 Metrics dashboard 的只读 catalog/query/render draft contract，以及 AI 生成 chart/dashboard draft 的验证、拒绝、发布和审计边界。

### Modified Capabilities
- `work-item-provider-platform`: 将 provider-neutral core 扩展为 profile-registry-first，要求 provider adapter 通过 registry capability 暴露 profile、chart support 和 sync dispatch，而不是硬编码特定 provider/project。
- `provider-facts-and-sync`: 将 durable facts、aggregate artifact 和 cache identity 对齐到 profile registry 与 range-neutral artifact identity，并要求 provider adapter 只输出 canonical facts。
- `bug-trend-baseline`: 将 existing chart catalog / AI chart draft governance 从 Jira bug trend baseline 扩展到 provider-neutral chart recipe validation，确保 AI/Grafana 不能创建未批准 series 或 business calculation。

## Impact

- Affected specs: `work-item-provider-platform`、`provider-facts-and-sync`、`bug-trend-baseline`，以及新增 `provider-profile-registry`、`grafana-render-config`、`provider-ai-dashboard-composition`。
- Future affected modules: `bug_metrics/app/api/`、`bug_metrics/domain/`、`provider_sync/`、`ui_web/facades/`、`ui_web/views/`、`ops/grafana/`、`scripts/`、`metrics/settings/`。
- Future affected artifacts: profile YAML/config files、chart recipe catalog、Grafana render config、generated dashboard JSON、Grafana artifact validators、AI catalog/schema snapshots。
- External integration impact: Jira remains first production provider; HSD-ES remains second provider with live sync/cache; AI base at `D:\AIGC\Report_creater_agent\` and `gcx` are optional external consumers/operators, not new sources of truth.
- Security/governance impact: secrets stay in Metrics/provider adapter configuration; AI receives only bounded catalog/facts/render-draft APIs; publish operations require Metrics validation and audit.

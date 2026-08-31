## Context

Dashboard 侧已经有 AI Base handshake、catalog、intent validation、render config validation、gcx precondition、publication callback 和 safe context API。AI Base 侧也已经提供 `dashboard_query_agent` profile 与 metrics connector lane。当前缺口不是底层 contract，而是 Dashboard 侧缺少一个 operator 能直接使用和验证的 workflow surface。

现有约束：
- Metrics/Dashboard 继续拥有 provider profile、canonical metric、render config validator、gcx precondition 与 audit。
- AI Base 是 optional platform dependency；Dashboard 在 AI Base 不可用时必须保持可用。
- Jira 与 HSD-ES 不应在 UI 中出现分叉逻辑；差异来自 provider profile、chart support 与 facts/aggregate adapters。

## Goals / Non-Goals

**Goals:**
- 增加 Dashboard 本地 AI sidecar workflow 页面/API envelope，让用户可提交 profile/range/chart/series request 并看到完整 validation/precondition 结果。
- 让同一 workflow 可跑 HSD-ES `nvu-ttl-hsdes` 与 Jira `chiplet-2a-jira` profile。
- 展示 unsupported semantics 的 `needs_metric_recipe` 状态，并保留用户原始 requested series。
- 使 gcx precondition 对用户可见，并保持 preview/dry-run-first。
- 增加 focused tests 和 OpenSpec 验证，避免 AI workflow 绕过 Metrics validation。

**Non-Goals:**
- 不实现真实 Grafana mutation/import 发布按钮。
- 不让 Dashboard 直接驱动 AI Base chat completion。
- 不把 raw Jira JQL、HSD-ES native query、credential 或 private file path 暴露给 AI Base 或 UI envelope。
- 不新增 provider-specific chart semantics；缺失 series 继续返回 `needs_metric_recipe`。

## Decisions

1. **Dashboard 先提供 Metrics-local workflow envelope。**
   - Rationale: 这能在 AI Base 可用或不可用时都验证 Metrics 合约，并给 AI Base 一个稳定、可复用的接口。
   - Alternative: 只在 AI Base desktop page 上实现 UI。放弃，因为 Dashboard 侧无法独立证明 contract 与 profile abstraction。

2. **Workflow envelope 复用现有 catalog/intent/render/precondition 服务。**
   - Rationale: 避免第二套 validation 逻辑；所有语义仍由 Metrics-owned services 判定。
   - Alternative: 在 view 里拼接结果。放弃，因为会产生 UI-specific validation drift。

3. **页面采用普通 Django Template + Bulma form。**
   - Rationale: 符合项目 UI 栈和“少 JavaScript”原则；first version 重点是可见 workflow 与验证结果。
   - Alternative: 嵌入 Grafana App/Scenes。暂不做，因为当前 Dashboard repo 能更快闭环 contract 与测试。

4. **gcx 只展示 precondition/dry-run eligibility，不执行 mutation。**
   - Rationale: 用户还没有审批 UX；真实 publish/import 应由后续 change 增加明确 approval。
   - Alternative: 直接调用 gcx import dry-run。暂不做，因为跨 app proof store 与 approval UI 还需要更强端到端验收。

## Risks / Trade-offs

- [Risk] Workflow 页面与 AI Base desktop route 有重复入口 → Mitigation: Dashboard 页面定位为 Metrics-owned contract/diagnostic surface；AI Base 页面定位为 orchestrator/chat surface。
- [Risk] 用户把 `precondition_passed` 理解为已经发布 → Mitigation: UI 文案明确显示 draft/precondition only，mutation 状态仍为 not executed。
- [Risk] Jira profile 当前可能没有 live facts → Mitigation: try-run 验证只依赖 catalog/intent/render/precondition abstraction，不要求 Jira live data 已同步。
- [Risk] 后续 Grafana embedded UX 需要不同布局 → Mitigation: 后端 envelope provider-neutral，未来可被 Grafana Scenes 或 AI Base UI 复用。

## Context

Dashboard 现在已经能导出 Metrics workspace context bundle，并且 AI Base 已经能用 generic app-workspace context bundle API 创建 workspace、保存 context source、按 visibility 注入 chat prompt。Dashboard 也已有 catalog、intent validation、render config validation、gcx precondition、approval 和 publish demo API。缺口不在单点能力，而在把这些能力串成一个 artifact-first、chat-triggered、human-approved 的稳定闭环。

这个 change 以 Dashboard repo 的 OpenSpec 为 integration source of truth；AI Base repo 需要配套实现，但跨 repo 的契约以 Dashboard specs 为准。Dashboard 仍是 Metrics facts、profile boundary、chart semantics、render validation 和 Grafana publish 的 owner。AI Base 是 workspace/chat/artifact/gcx orchestration platform。

## Goals / Non-Goals

**Goals:**
- AI Base `dashboard_query_agent` 能基于 synced workspace context 回答 data block、canonical field、boundary 和 Grafana constraint 问题。
- AI Base 能把 chat 请求转换为 workspace artifact，而不是修改 Dashboard 代码。
- Dashboard 能验证 AI workspace artifact，并给出 pass/fail、findings、correlation id 和 next action。
- E2E demo 能从 chat request 走到 dry-run proof、approval、Dashboard publish，再到 Grafana URL。
- 所有失败路径都要 deterministic：missing context、unsupported series、invalid artifact、missing approval、missing proof 都有结构化 blocker。

**Non-Goals:**
- 不实现 AI 自由创建新的 Metrics semantic recipe 或 provider query。
- 不让 AI Base 直接访问 Jira/HSD-ES credentials、database 或 Dashboard 内部 Python modules。
- 不要求第一版支持任意 Grafana panel 类型；先覆盖 `open_bug_trend` / `new_critical_high` 的 artifact-first path，并保留 data-block gap reporting。
- 不在此 change 中解决远端部署、多用户权限模型或生产级 persistent DB migration。

## Decisions

### Decision 1: Artifact-first, not code-first

AI Base SHALL create a versioned workspace artifact containing user intent、selected profile/range、candidate render config and metadata. Dashboard validates the artifact through HTTP contract. This avoids letting AI mutate Dashboard code or provider configuration.

Alternative considered: 让 AI 直接修改 render config 或 Dashboard source file。拒绝原因是审计难、代码质量难控，且会绕过 Metrics-owned validator。

### Decision 2: Dashboard validation consumes normalized artifact payloads

Dashboard should accept a structured artifact payload, not a path into AI Base local filesystem. AI Base may store artifacts locally, but submit the artifact content plus `artifact_ref` and `artifact_version` to Dashboard validation/publish APIs. This keeps Dashboard independent of AI Base storage layout.

Alternative considered: Dashboard 拉取 AI Base artifact URL。第一版不采用，因为会引入 AI Base auth、artifact download、lifetime 和 path exposure 问题。

### Decision 3: Workspace context answers are generated from model-visible context only

AI Base chat grounding should use `model_context` files for boundary、canonical fields、data block catalog and Metrics help. `catalog_only` files may be listed or used by tools, but not injected by default. This matches the generic context bundle contract and avoids leaking internal or audit-only material.

Alternative considered: 每次 chat 都调用 Dashboard catalog APIs。保留为 tool fallback，但不是第一优先级，因为 workspace context 是用户选择 provider/project 后的 stable interaction medium。

### Decision 4: Dry-run proof and approval stay separate

Dry-run proof proves the exact artifact and environment were checked. Approval proves the human allowed mutation. Publish requires both and Dashboard revalidates the artifact before Grafana import.

Alternative considered: dry-run automatically authorizes publish。拒绝原因是 human-approved publish 是 audit boundary，不能由 tool success 替代。

### Decision 5: Same contract for Jira and HSD-ES

Provider differences stay inside Metrics profile/fact/data-block layers. AI artifact and Dashboard validation should use canonical fields and profile id only. This lets the first demo use HSD-ES offline/live data while the same flow later supports Jira.

Alternative considered: 为 HSD-ES 和 Jira 建两个 chat workflows。拒绝原因是会重复 provider branching，并破坏后续泛化。

## Risks / Trade-offs

- AI Base artifact store 可能已有 draft/report 概念，新增 dashboard artifact 可能重复 → 先使用最小 artifact record，后续可并入通用 workspace artifact registry。
- 第一版 artifact validation 可能仍依赖已有 chart recipe，data-block-only arbitrary charts 会返回 `needs_metric_recipe` → 这是安全 trade-off，避免 AI 创造未批准 semantics。
- Chat grounding 依赖 source context 注入长度限制 → 保留 deterministic API/tool fallback，并在回答中报告缺失 context。
- Cross-repo implementation 需要两边版本匹配 → 用 contract version、artifact schema version 和 focused E2E script 降低 drift。

## Migration Plan

1. Dashboard 保持已有 catalog/workflow/publish API source compatible，新增或扩展 artifact validation/publish envelope。
2. AI Base 在 `dashboard_query_agent` profile 中增加 workspace artifact creation 和 Metrics connector artifact validation call。
3. E2E script 启动 Dashboard、Grafana、AI Base 后，先 sync context，再在 AI Base chat/workflow 中创建 artifact。
4. 发布前要求 dry-run proof 和 approval；失败时保留 artifact 和 findings 供用户修正。
5. 若需要 rollback，可禁用 AI Base dashboard profile 或不调用 artifact validation/publish；Dashboard 非 AI flows 不受影响。

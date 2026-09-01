## Context

当前系统已经完成 HSD-ES 本地可见 demo：AI Base Chat 可以触发 dry-run proof，并在明确 approve/publish 后调用 Dashboard `publish-demo`，Dashboard 重新验证 render config 并导入本地 Grafana。限制是：Jira `chiplet-2a-jira` 在 fast E2E 下可能没有目标 range 的 aggregate artifact；approval 还是 local demo id；chart authoring 固定在 `open_bug_trend/new_critical_high`；已发布的 AI dashboard 缺少用户可浏览的 history/list。

## Goals / Non-Goals

**Goals:**
- 让 Jira-first prompt 成为可验证的 primary E2E path。
- 在 publish 前暴露 Jira profile 数据 readiness，避免发布 `No data` dashboard。
- 引入可查询 approval state，为后续正式 approval UI 铺路。
- 将 authoring 从固定 demo 变成 catalog/recipe-driven。
- 记录和展示 AI-generated Grafana publish history。

**Non-Goals:**
- 不在本 milestone 实现完整企业审批权限系统。
- 不让 AI Base 拥有 Jira/HSD-ES credentials、metric semantics 或 Grafana JSON authority。
- 不要求一次性支持所有 deferred charts；unsupported charts 必须保留 `needs_metric_recipe`。

## Decisions

1. **Jira readiness first.**
   - 先确保 `chiplet-2a-jira` 能产生目标 range 的 completed aggregate artifact，再把它纳入 Chat publish demo。
   - 如果数据未就绪，Chat 和 Dashboard 都返回 readiness blocker，而不是创建 `No data` 图。

2. **Approval state belongs to Dashboard.**
   - AI Base 可以携带 approval id，但 Dashboard 必须能创建、查询和验证 approval state。
   - local demo 可以有 auto-approved policy，但状态仍要显式记录。

3. **Recipe-driven authoring is constrained by Metrics catalog.**
   - AI Base 不能自由发明 chart id、series 或 field mapping。
   - Dashboard catalog 和 render validator 决定可发布内容。

4. **Publish history is a Dashboard artifact registry.**
   - Grafana 负责展示，Dashboard 负责记录谁发布了什么、基于哪个 profile/range/recipe/proof/approval。

## Risks / Trade-offs

- [Risk] Jira live sync depends on credentials/network. -> Mitigation: tests use deterministic fixture path; live E2E records blocker if sync cannot run.
- [Risk] Approval model may be too small for production. -> Mitigation: scope it as queryable state and keep future policy fields.
- [Risk] Recipe-driven authoring can balloon. -> Mitigation: first support only catalog-advertised chart recipes and reject everything else.
- [Risk] Publish history duplicates audit events. -> Mitigation: history entries reference audit/correlation metadata and serve operator UX; audit remains authoritative.

## Migration Plan

Implement in phases:

1. Commit existing case study docs as baseline.
2. Add Jira publish readiness checks and tests.
3. Add approval state model/API and wire publish demo through it.
4. Generalize AI request parsing and Dashboard validation to catalog recipes.
5. Add publish history API/UI and update runbook/case study.

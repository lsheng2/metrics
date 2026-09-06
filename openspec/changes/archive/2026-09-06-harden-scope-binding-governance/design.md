## Context

当前 scope binding 已经有 explicit/compatibility/configuration_required 等状态，Scope Library 可以逐行 confirm 或选择 profile，Data Health 可以显示绑定健康，Workbench 也已经通过 server-side resolver 以 `scope_id` 为 authority。这个 change 在此基础上补治理闭环：批量迁移、投产前 readiness、审计、Workbench policy 和高密度 UI。

## Goals / Non-Goals

**Goals:**

- 让 operator 可以一次性确认所有安全的 compatibility bindings，并看到 changed/skipped 结果。
- 让 Data Health 提前判断 explicit-only policy 是否可启用，而不是等 runtime 切换后才发现 Workbench 被阻断。
- 让 Workbench 对 compatibility 和 unresolved binding 的提示策略一致，避免 stale provider/profile/chart/evidence/AI 状态。
- 复用现有 audit event 机制记录 binding mutation，避免新增不必要的数据模型。
- 让 Scope Library binding 行保持高密度，适合大量 scopes 的扫描和修复。

**Non-Goals:**

- 不在本阶段实际关闭 compatibility runtime。
- 不修改 Grafana dashboard 或 AI Base app UI。
- 不改变 provider profile registry 本身的 profile 定义或 source population contract。
- 不引入新的前端框架或通用 dock/window 依赖。

## Decisions

1. **readiness 是 projection，不是 runtime flag。**
   explicit-only readiness 将由现有 binding health 聚合派生，返回 `explicit_only_ready`、blocked count 和 impacted rows。替代方案是在 settings 中新增 policy flag；但本阶段目标是投产前可见性，不改变 runtime 行为。

2. **批量确认只处理安全 compatibility rows。**
   bulk confirm 不接受任意 profile/provider 输入，只把 resolver 已安全解析出的 compatibility binding 固化为 explicit。configuration_required、ambiguous、disabled 或缺失 profile/provider 的 rows 必须 skipped。这样避免批量操作扩大误绑定风险。

3. **审计复用 `BugTrendAuditEvent`。**
   binding confirm/save/bulk confirm 写入结构化 payload，包含 old/new snapshot 和 operation metadata。若现有字段能承载 JSON metadata，就不新增 migration；如果验证发现字段不足，再以最小 migration 扩展。

4. **Workbench policy 以 resolver status 为单一入口。**
   compatibility 显示 warning 但不阻断；configuration_required/ambiguous/disabled/missing profile-provider 阻断 provider-backed panes，并清空 stale data。替代方案是在每个 pane 自行判断，但会重复逻辑并再次引入状态漂移。

5. **Scope Library 高密度优先使用现有 Bulma/HTMX。**
   通过 compact form、button group、短 status chip 和二级说明折叠/tooltip 化提高密度；不引入 React/Vue 或新的组件库。

## Risks / Trade-offs

- [Risk] Bulk confirm 误确认错误 compatibility 结果 -> Mitigation: 仅允许 resolver 标记为 compatibility 且带 resolved profile/provider 的 rows，返回 skipped reasons，并写 audit。
- [Risk] Data Health gate 与 runtime 行为口径不一致 -> Mitigation: readiness 从同一个 registry health projection 计算，测试覆盖 status counts 和 impacted rows。
- [Risk] Workbench 仍显示前一个 scope 的 stale pane 内容 -> Mitigation: unresolved binding scenario 明确清空 provider-backed panes，增加 view/template regression tests。
- [Risk] Scope Library 过度压缩导致操作不清楚 -> Mitigation: 保留 primary action inline，policy 解释放在 Data Health 或 help/tooltip，UI screenshot 做真实浏览器检查。

## Migration Plan

1. 先增加 API projection 和 tests，不改变 runtime policy。
2. 增加 Scope Library bulk action、audit 和 Data Health explicit-only gate。
3. 增加 Workbench warning/blocking rendering。
4. 跑 focused tests、OpenSpec validate、Django check、migration dry-run、real stack UI inspection。
5. 若问题出现，可回滚 UI action 和 projection；已有 explicit bindings 与 audit events 保持向后兼容。

## Context

当前系统默认接受 safe compatibility binding，并通过 Data Health 提供 explicit-only readiness。Scope binding mutation 已写入 `BugTrendAuditEvent`，但没有用户可见查询和页面。这个 change 将新增 runtime policy，但默认仍保持兼容模式，避免升级后立即阻断现有环境。

## Goals / Non-Goals

**Goals:**

- 通过配置把 scope binding runtime 分成 `compatibility_allowed` 和 `explicit_only`。
- 在 explicit-only 下，compatibility binding 只可用于 readiness/audit 展示，不可作为 provider-backed runtime authority。
- 提供 operator 可见的 binding audit history。
- 用真实 stack/UI 验证批量确认后 readiness ready，并尝试 full AI chat smoke。

**Non-Goals:**

- 不改变 provider profile registry 的 profile 定义格式。
- 不把 compatibility binding 从数据库或历史 projection 中删除。
- 不修改 Grafana UI 或 AI Base app UI。
- 不把模型 gateway 不可用视为 full AI smoke 通过。

## Decisions

1. **policy 作为 Dashboard runtime config。**
   使用 `METRICS_SCOPE_BINDING_POLICY`，默认 `compatibility_allowed`。这样生产/本地可以渐进启用 explicit-only，而不需要 schema migration。

2. **resolver 输出 policy-aware runtime status。**
   在 explicit-only 下，原本 safe 的 compatibility binding 返回 `configuration_required` 和 blocker。Data Health 仍可展示原始状态和 impacted rows，帮助 operator 知道为什么被挡住。

3. **audit history 复用 `BugTrendAuditEvent`。**
   仅筛选 scope binding event types，并把 `request_summary.before/after` 映射成页面 DTO。无需新表。

4. **UI 放在现有 admin surfaces。**
   Scope Library 显示 policy 和 audit history，Data Health 显示 policy/readiness；不新增独立导航页面，保持高密度。

## Risks / Trade-offs

- [Risk] explicit-only 误开启后阻断用户分析 -> Mitigation: 默认仍为 compatibility_allowed，并在 Data Health 显示 readiness/impact。
- [Risk] audit event payload 形状不完整 -> Mitigation: audit projection 对缺失字段显示空值，并用 tests 覆盖 binding event filtering。
- [Risk] full AI smoke 依赖外部 model gateway -> Mitigation: 脚本失败时记录具体 blocker，不把 unavailable 依赖记为通过。

## Migration Plan

1. 增加 policy config 和 resolver tests。
2. 增加 audit history API/facade/template/tests。
3. 用 Scope Library 批量确认当前 sample scopes，验证 readiness ready。
4. 运行 full stack 和 UI inspection；尝试 `-FullAiChatSmoke` 并记录结果。

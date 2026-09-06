## Overview

本阶段把 scope binding 从“后端 authority + library 可确认”推进到“用户可修复、健康可观测、AI 诊断可解释”。实现仍保持 Django server-rendered/Bulma/HTMX，不引入新前端框架。

## Backend

- 在 `ApiForBugTrend` 增加 `set_scope_provider_binding(scope_id, profile_id)`。
- `ScopeProviderBindingResolver` 增加 explicit save helper，校验 `ProjectProviderProfileRegistry`。
- 复用现有 `BugTrendScopeProviderBinding` 模型，不新增 migration。
- Facade 提供：
  - scope binding rows
  - provider profile choices
  - binding summary counts
  - save/confirm binding operations

## UI

### Scope Library

- Binding 列显示 status/profile/provider/provenance/blocker。
- Actions 列压缩为：
  - Edit / Duplicate / Disable
  - Bind profile select + Save binding
  - Confirm compatibility
- 对 explicit rows 可隐藏 profile selector，保留 compact profile/provider text。

### Data Health

- 增加 Scope Binding Health section：
  - summary counts
  - detail table
  - repair link

### Workbench AI Pane

- `workbench_ai_context` 增加 `scope_binding`。
- AI unavailable/sync warning copy 展示 binding status/profile/provider，并提供 Scope Library 链接。

## Runtime Compatibility Policy

本阶段不关闭 compatibility runtime。改为：

- 明确显示 compatibility provenance。
- Data Health 汇总 compatibility 数量。
- Scope Library 提供 confirm/rebind。

下一阶段再考虑 explicit-only 开关。

## Validation

- Scope Library view tests：编辑/保存 binding、确认 compatibility、未绑定显示 selector。
- Data Health view tests：summary/detail/repair link。
- Workbench AI tests：context 包含 binding，unresolved binding 优先指向 Scope Library。
- Live UI：Scope Library 和 Data Health 截图级检查。

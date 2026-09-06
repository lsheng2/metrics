## Overview

第一版管理入口放在 Scope Library。原因是用户已经在这里管理 saved scope 的生命周期，binding 是 saved scope 的 provider-facing sidecar metadata，放在同一页最少跳转、最低风险。

## UI

Scope Library 表格新增 Binding 列：

- status tag: explicit / compatibility / configuration_required / ambiguous / disabled
- profile id
- provider id
- provenance summary
- blocker summary
- compatibility binding 的 Confirm explicit 按钮

## Backend

- `ApiForBugTrend.list_scope_provider_binding_rows()` 返回 scope-bound DTO。
- `ApiForBugTrend.confirm_scope_provider_binding(scope_id)` 把 resolved compatibility binding 持久化为 explicit。
- `BugTrendFacade.get_scope_library()` 可以继续返回 scope config；新增 `get_scope_library_rows()` 或 equivalent view composition 供 UI 使用。

## Validation

- View test: Scope Library shows binding status/profile/provider/provenance.
- POST test: Confirm explicit updates binding status and redirects back.
- Regression: configuration_required binding shows blocker and has no confirm action.

## Non-goals

- 本阶段不做完整 profile picker/editor。
- 本阶段不删除 compatibility resolver。
- 本阶段不改变 existing scope config save flow。

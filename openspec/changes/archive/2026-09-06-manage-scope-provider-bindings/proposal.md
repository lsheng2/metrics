## Why

显式 scope-provider binding 已经成为 Workbench 的状态 authority，但用户目前还看不到哪些 scope 是 explicit、compatibility 或 configuration_required，也不能把兼容绑定升级为明确绑定。进入产品化阶段后，binding 必须可见、可确认、可审计。

## What Changes

- 在 Scope Library 中显示每个 saved scope 的 provider binding status、profile、provider 和 provenance。
- 为 compatibility binding 提供 `Confirm explicit` 操作，把迁移/兼容推断结果升级为人工确认的 explicit binding。
- 对 configuration_required / ambiguous binding 显示 blocker 信息和下一步入口。
- 增加 view/facade/API 方法和测试，确保管理入口不再隐藏 binding 问题。

## Capabilities

### New Capabilities

- 无。该能力是现有 scope wizard/library 和 provider profile registry 的产品化补强。

### Modified Capabilities

- `provider-scope-wizard`: Scope Library SHALL expose provider binding status and confirmation actions.
- `provider-profile-registry`: Scope binding SHALL be manageable/auditable from Dashboard UI instead of remaining runtime-only resolver state.

## Impact

- UI：Scope Library 表格增加 binding status/profile/provider/provenance/actions。
- API/facade：新增 list binding rows 和 confirm explicit binding 操作。
- 数据：更新 `BugTrendScopeProviderBinding.status` 为 `explicit` 并记录确认 provenance。
- 验证：Scope Library view tests、binding resolver tests、OpenSpec validation。

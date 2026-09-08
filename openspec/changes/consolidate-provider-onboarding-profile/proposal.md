## Why

Provider Profile 现在承担了两种不同职责：一部分是 provider onboarding/connection（Jira、HSD-ES、GitHub 如何接入），另一部分是 scope/source（某个 JQL、HSD-ES saved query、project/product 范围）。这让用户在建立 scope 前必须理解 profile，且容易误以为 profile 只是 provider + name。

当前 `.env/settings` 也会在本地承载 secret；它和 profile config 的差别主要是管理面和泄漏面，而不是“是否落盘”。Profile 可以暂时保存 provider onboarding 所需的本地凭据，后续启用 secret store/vault 时通过 `credential_ref` 迁移。Profile package/export、readiness payload、页面摘要仍必须脱敏，避免 token/password 进入共享文件或诊断输出。

## What Changes

- 将 Provider Profile 的主语义改为 provider-level onboarding/connection profile：每种 provider 默认一个 profile，例如 `jira-default`、`hsdes-default`、`github-default`。
- Profile 主 UI 展示 provider name、base URL、auth mode、temporary local credentials、credential reference、onboarding status 和跨 scope 默认能力；不再把项目 JQL 或 HSD-ES saved query 当作 profile 的主输入。
- Scope 继续表示某个项目/产品/范围的操作视图，并引用一个 provider profile；Jira JQL、HSD-ES saved query id/name、project/product/milestone 等 source/range 信息属于 scope 或 scope binding。
- Scope Library 只展示和管理 saved scopes；未绑定的 provider profiles 不再作为只读行混排到 scope 表格中。Provider profile inventory、lifecycle、connection test、export/import 和 archive/delete 统一归 Provider Setup。
- 保留 legacy source-heavy profiles 的兼容读取能力，避免立即破坏现有 HSD-ES/Jira seed、sync、Grafana、AI flows。
- Profile export/import 继续是 non-secret package：允许 `credential_ref`，但默认必须排除 token/password/secret/credential material。
- UI validation 必须覆盖 Provider Setup inventory、Provider Profile Config editor、Scope Library scope-only rows、Scope Config handoff、desktop/mobile overflow、provider tabs/check/color 和 deprecated/display-only field demotion。

## Capabilities

### Modified Capabilities

- `provider-setup-management`: Provider Profile 从 source-specific config 重构为 provider onboarding/connection profile，source-specific settings 退到 scope 或 advanced/legacy compatibility。
- `provider-profile-registry`: Registry contract exposes connection settings, supports local temporary credentials for runtime, and redacts secrets from exported/readiness payloads.
- `provider-scope-wizard`: Scope Library manages scopes only, while Scope Config references provider profiles and owns project/range/source details.

## Impact

- Affected models/API: `ProviderProfileConfig`, `ProjectProviderProfile`, profile import/export, readiness payloads, Jira/HSD-ES sync command.
- Affected UI: Provider Profile Config editor, Provider Setup list, Scope Library row model, Scope Config provider handoff copy.
- Affected tests: provider profile config/registry, HSD-ES sync command, Scope Library scope-only rendering, Provider Setup browser layout, Scope Config browser layout.
- Non-goal: include raw credentials in exported profile packages, readiness payloads, audit details, or page hidden fields.

## Context

See `proposal.md` - Why. 当前 provider profiles 由 `bug_metrics/provider_profile_configs/*.json` 作为只读 registry 输入，`ProjectProviderProfileRegistry` 暴露 profile contract，Scope Library 只展示 provider profile rows 和 scope binding 操作。Scope Config 已开始 provider-first 展示，但没有独立 Provider Setup 菜单，也没有客户自助 profile create/edit/archive/import/export 流程。

## Goals / Non-Goals

**Goals:**

- 建立独立 Provider Setup 用户流程，面向低上下文用户先选 provider，再完成 source、metadata、mapping、readiness、scope handoff。
- 使用与 Scope Library/Scope Config 一致的 admin-style UI：高密度、清楚分组、help tips、dirty-change guard、危险操作确认、移动端可读。
- 将 Jira 绿色、HSD-ES 蓝色、GitHub 紫色纳入 provider visual language，并允许其他 future provider 通过 template 配置颜色。
- 复用 Scope lifecycle 的 archive/delete/import/export/audit 模式，但把 blast radius 和 validation 换成 profile-specific。
- 保持 provider profile 是 Dashboard/Grafana/AI 的 source/mapping authority，scope 是 calculation/use-case view，binding 是连接。

**Non-Goals:**

- 本 OpenSpec 不实现代码。
- 不在本 change 中实现 HSD-ES live metadata 或 write actions。
- 不把 provider credentials 暴露在 profile package 或普通 UI 中。
- 不让 Scope Config 变成完整 Provider Profile editor；它只消费 Provider Setup handoff。

## Decisions

- 新增 `Provider Setup` 菜单，而不是把 profile builder 塞进 Scope Library。
  - Rationale: Scope Library 是 inventory/binding/lifecycle surface；Provider Setup 是 source/mapping creation wizard。拆开后用户更容易理解 profile vs scope。
  - Alternative considered: 在 Scope Library 表格里 inline edit profile。拒绝，因为字段映射和 metadata workflow 会让行高、状态和错误处理变得混乱。

- Provider Setup 使用 template registry 驱动表单。
  - Rationale: Jira、HSD-ES 和 GitHub 的 source model 不同，但步骤形态一致：provider -> source -> metadata -> mappings -> readiness -> save/handoff。
  - Reuse target: 复用 `ui_web/facades/provider_scope_setup.py` 的 provider template 概念，并上移或泛化为 Provider Setup/Scope Config 共用的 projection。
  - Alternative considered: 每个 provider 一套 view/template。拒绝，因为第三 provider 会复制流程和验证逻辑。

- Provider Setup inventory 与 Provider Profile Config editor 分屏。
  - Rationale: 低上下文用户点击 New Profile/Edit 后，主任务已经从“管理列表”切换到“编辑一个 profile”；保留整张 inventory 会分散焦点并让页面像混合后台。
  - Reuse target: 复用 Scope Config 的 dedicated editor pattern、breadcrumb/back action、dirty-form guard 和 provider tab shell。
  - Alternative considered: 把 editor inline 放在 inventory 下面。拒绝，因为它不符合 New Scope 的工作流，也让 profile actions 与当前编辑表单竞争注意力。

- Profile persistence 使用 managed profile store，JSON registry 保留为 bundled baseline。
  - Rationale: 客户自助创建/编辑需要持久化、生命周期、审计和导入导出；只读 JSON 不适合 UI 写入。
  - Proposed model: DB-backed `ProviderProfileConfig` 或等价 managed store，字段结构保持与 `ProjectProviderProfile` contract 对齐。Registry load order 为 managed enabled profiles + bundled JSON profiles，冲突时必须有显式 precedence/provenance。
  - Alternative considered: UI 直接写 JSON。拒绝，因为 web server 写 repo 文件难以审计、权限复杂，并且不适合部署环境。

- Archive/delete/import/export 复用 Scope Config 模式。
  - Rationale: 用户已经在 Scope Library 看到 Archive、Export JSON、Import、Delete archived 的语义；Provider Setup 应使用同样的 reversible-default 和 protected-delete 心智。
  - Reuse target: 抽取或共享 versioned package helpers、delete impact summary pattern、confirmation token pattern、audit event formatting 和 responsive admin table components。

- Profile readiness 是 enable gate，不是事后说明。
  - Rationale: profile 影响 sync、aggregate、evidence、AI/Grafana；缺字段或 provider capability 时不能让用户启用后才发现失败。
  - Reuse target: `ProviderProfileReadinessService`、provider capability manifest、chart support resolution、Data Health rows。

- Scope handoff 是显式动作。
  - Rationale: 创建 profile 不等于创建 Dashboard calculation scope；用户需要选择“Create Scope from Profile”或“Bind Existing Scope”。
  - Alternative considered: 保存 profile 后自动创建 scope。拒绝，因为 scope 的 lifecycle mappings、bucket granularity 和 enablement 仍需 operator review。

## Reuse Opportunities

- **Provider template registry**: 复用/泛化 Scope Config 现有 provider setup template，作为 Provider Setup 和 Scope Config 的共同 projection source。
- **Scope Library lifecycle UI**: 复用 Archive、Delete archived、Export JSON、Import Scope File、confirmation token、status summary、audit table 的交互模式和 CSS。
- **Package format**: 复用 scope export/import 的 versioned JSON package 思路，但 profile package 必须排除 credentials、provider facts、calculation outputs 和 AI artifacts。
- **Binding resolver**: 复用 existing scope-provider binding resolver，Provider Setup 只触发 explicit bind/create handoff，不重新发明 binding authority。
- **Readiness services**: 复用 provider profile readiness、chart support、sync cache health 和 Data Health projections，避免 Provider Setup 自己判断 chart 可用性。
- **Help-tip / dirty-form / responsive table**: 复用现有 `help_tip.html`、`data-dirty-form`、responsive admin table CSS，保持界面风格一致。

## Risks / Trade-offs

- [Risk] DB managed profiles 与 bundled JSON profiles 产生冲突。 -> Mitigation: profile id conflict must show explicit precedence and import conflict actions; registry response includes provenance.
- [Risk] 用户把 Provider Setup 当成 credential setup。 -> Mitigation: credentials remain separate; UI labels provider profile as source/mapping config and shows credential blockers through readiness only.
- [Risk] HSD-ES 细节未完全确认时被误用。 -> Mitigation: HSD-ES live metadata/write capabilities remain configuration_required until authoritative API checks are recorded.
- [Risk] Provider Setup 过重。 -> Mitigation: progressive disclosure：first provider, then source, then metadata/mapping, then readiness; raw JSON/editor remains behind advanced/export affordance, not primary path.
- [Risk] Shared lifecycle abstraction over-generalizes too early。 -> Mitigation: first extract only package/impact/audit/view helpers proven by Scope and Provider Setup; keep domain validation provider-specific.

## Migration Plan

1. Add OpenSpec contracts and validate them.
2. Introduce provider profile managed-store model/service or equivalent profile store abstraction, preserving existing JSON registry as bundled baseline.
3. Add Provider Setup menu, list page and provider-first editor using shared provider template projection.
4. Implement create/edit/archive/restore/delete/export/import/duplicate with provider-specific validation and audit.
5. Integrate metadata/readiness checks and prevent enable when required source/mapping/capability blockers exist.
6. Add handoff actions to create a scope from profile or bind an existing scope.
7. Refactor common lifecycle/package/audit/UI helpers shared with Scope management where duplication is real.
8. Validate with focused provider setup tests, scope handoff tests, data health/readiness tests, browser UI smoke, Django check, OpenSpec strict validation and whitespace gate.

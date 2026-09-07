## Context

See `proposal.md` - Why. 当前 Scope Config 是 server-rendered Django + Bulma + htmx 页面；metadata partial 通过 `hx-include="closest form"` 读取 draft 表单值，后端 `get_scope_metadata_options` 目前只调用 Jira metadata provider。Provider/profile 绑定 authority 已存在于 Scope Library 和 provider registry 边界，但 Scope Config 没有把它展示出来。

## Goals / Non-Goals

**Goals:**

- 在 Scope Config 页面提供 provider/profile visibility，并把修复 binding 的入口连接到 Scope Library。
- 让新建 scope 的第一步就是 provider pillar 选择，并将 provider profile binding 作为可见的一等输入。
- 为 Jira、HSD-ES 和 future provider 使用可扩展 setup template registry 管理 provider-specific copy 和 detail rows。
- 使用 provider color 作为一致视觉提醒：Jira 绿色、HSD-ES 蓝色、GitHub 紫色，其他 future provider 中性或配置化。
- 在同一页面解释四类 readiness：Save Draft、Enable Scope、Provider Metadata、Dashboard/AI。
- 将 metadata options 分组，并让常见候选值可以一键追加到语义字段。
- 保持当前保存语义：metadata refresh 和 mapping link 都不自动保存。

**Non-Goals:**

- 不新增 HSD-ES metadata adapter。
- 不改变 `JiraScopeConfig` 数据模型或 config hash 语义。
- 不把 Scope Library 的 binding mutation authority 搬到新的 API；第一版只在 Scope Config 暴露可理解入口。
- 不引入 React/Vue/Alpine 或其他前端框架。

## Decisions

- Scope Config 读取 provider binding projection，而不是从表单字段推断 provider。
  - Rationale: 现有 provider registry/binding 已是 Workbench/Grafana/AI 的 authority，页面应该展示该 authority。
  - Alternative considered: 根据 `Name` 或 `JQL` 在模板里猜 provider。拒绝，因为这会延续用户困惑并弱化 explicit binding。

- 新 scope 允许在 Save Draft/Enable Scope 时携带 provider profile，并在 scope 保存成功后创建 explicit binding。
  - Rationale: 用户的心智是先选 provider，再填细节；保存时已有稳定 scope id，可以在同一请求后半段写 binding，并保留 audit。
  - Alternative considered: 仍要求保存后去 Scope Library 绑定。拒绝，因为 provider 是 pillar 选项，隐藏到第二页会继续造成困惑。

- Provider-specific UI 文案和 detail rows 来自 setup template registry。
  - Rationale: Jira、HSD-ES、GitHub 的 source query、metadata 状态和 detail fields 不同，集中注册比在模板中散落 if/else 更可扩展。
  - Alternative considered: 直接在模板写 Jira/HSD-ES 条件。拒绝，因为第三个 provider 会复制 UI 分支并增加维护成本。

- Metadata panel 使用分组加 mapping links，而不是复杂 multi-select 组件。
  - Rationale: 当前栈偏向 semantic HTML、Bulma 和 htmx；link with query params 已经支持把 audit value 带回 editor，不需要新 JS。
  - Alternative considered: 客户端 chip picker。拒绝，因为自定义 JS 会增加状态同步风险。

- Provider-aware metadata 第一版明确 Jira-only。
  - Rationale: 当前 `ApiForScopeMetadata` 只注册 Jira provider，HSD-ES metadata 行为需要 HSD-ES API 文档/adapter 单独设计。
  - Alternative considered: 为 HSD-ES 返回空列表。拒绝，因为空列表会让用户误解为 provider 真实无 metadata。

## Risks / Trade-offs

- [Risk] 页面信息量增加。 -> Mitigation: 使用 compact readiness strip 和 details-like grouped sections，避免 card 套 card。
- [Risk] Mapping link 刷新整页可能打断用户编辑。 -> Mitigation: 保留“不保存”语义，mapping 仅追加 query value；后续可升级为 htmx 局部 append。
- [Risk] New scope 无法立即保存 binding。 -> Mitigation: 明确提示 Save Draft 后绑定，并提供 Scope Library 入口。
- [Risk] 保存 scope 后绑定 profile 失败导致 scope 已保存但 binding 失败。 -> Mitigation: 保留 scope save 成功并返回 provider binding validation error；后续可通过 Scope Library 修复。
- [Risk] HSD-ES 用户仍希望在此页查 metadata。 -> Mitigation: 页面明确说明 provider-owned saved query 走 profile/readiness，不伪装为 JQL metadata。

## Migration Plan

1. 扩展 `BugTrendFacade` 暴露单个 scope 的 binding display context。
2. 增加 provider setup template registry，并由 facade 聚合 profile choices 得到 provider pillars。
3. 扩展 `BugTrendScopeConfigView` context，加入 selected provider、binding、profile choices 和 readiness hint。
4. 更新 Scope Config 模板，增加 provider-first 选择、provider color、provider-specific detail rows、required/readiness strip、metadata dependency copy。
5. 保存 scope 成功后根据提交的 provider profile 写 explicit binding；metadata refresh 仍保持不保存。
6. 更新 metadata partial 为分组展示和 semantic mapping links。
7. 增加 focused tests，覆盖 provider-first 选择、颜色、template copy、new scope binding、必填分层提示、metadata 分组和 mapping links。
8. 运行 focused tests、Django check、OpenSpec strict validate 和 whitespace gate。

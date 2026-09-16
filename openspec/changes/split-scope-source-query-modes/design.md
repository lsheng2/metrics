## Context

See `proposal.md` - Why. 当前 Scope Config 是 server-rendered Django + Bulma + htmx 页面，已有 provider-first panel、metadata refresh partial、scope semantic fields 和 explicit provider binding 保存路径。当前 `jql` 同时承载 source population，metadata refresh 又使用 JQL project、Selected Jira projects 和 bug type values 获取候选项，导致用户容易把 metadata context 当成另一个 runtime filter。

当前 durable sync 只需要一个最终 Jira query 和 field mappings。为了降低迁移风险，本设计保留现有 `jql` 作为 persisted final source query，不把 sync 改成读取临时 UI controls。

## Goals / Non-Goals

**Goals:**

- 让 Scope Config 页面明确呈现两个互斥 source authoring modes：`Custom JQL` 和 `Query Builder`。
- 让 Query Builder 生成 JQL preview，并把生成出来的 JQL 持久化到现有 `jql` 字段，继续作为 sync/calculation 的唯一 source query。
- 让 metadata discovery context 成为独立 section，明确它只服务于候选项刷新，不作为隐藏运行时 filter。
- 让 semantic mapping 与 optional display fields 独立于 source query 呈现，支持用户把截图中的 Program Increment、Epic Link、Affected Products、Environment Found、Security Level、Labels 等作为 display/evidence fields 或 query-builder filters。
- 修复 Jira metadata adapter 对 paged `values` / `options` wrapper 的解析，使 issue type 和 custom field option discovery 返回真实候选值。

**Non-Goals:**

- 不实现 HSD-ES live metadata adapter。
- 不改变 Workbench、Grafana、AI flows 的 scope/provider binding authority。
- 不把 Query Builder 扩展成完整 Jira JQL IDE；第一版支持常用字段与 generic custom field rows，复杂条件仍使用 Custom JQL。
- 不引入 React/Vue/Alpine 或其他前端框架。

## Decisions

- 保留 `jql` 作为最终 runtime source query，新增 `source_mode` 和 builder state。
  - Rationale: 现有 sync、hash、audit、fixture 和 chart freshness 都已经围绕 `jql` 工作；保留它能避免跨模块破坏。
  - Alternative considered: 新增 `source_query` 并逐步废弃 `jql`。拒绝，因为命名迁移会触碰历史 fixtures、命令、tests 和用户认知，收益不足。

- Query Builder 保存的是“生成 JQL 的结构化 state”，而不是只保存渲染后的文本。
  - Rationale: 用户重新打开页面时应看到自己选择的 project、issue type 和 field filters，而不仅是一串生成后的 JQL。
  - Alternative considered: 只保存生成 JQL。拒绝，因为这会让 Query Builder 看起来可用但无法 round-trip。

- Metadata discovery context 不进入 runtime query，也不进入语义 hash，除非它被用户明确加入 Query Builder filters 或 semantic mappings。
  - Rationale: 用户可以为了查 metadata 临时输入 project/type；这不应让旧 calculation run 变 stale，也不应改变 sync 范围。
  - Alternative considered: 把 selected projects 持久化并参与 hash。拒绝，因为它会把“刷新候选项”误变成 source authority。

- Query Builder 第一版使用 server-side text/list controls，而不是客户端 chip picker。
  - Rationale: 项目 UI 栈是 Django templates、Bulma、htmx；用 textareas、selects、checkbox/radio 和 server-side preview 可以覆盖主要使用场景，状态也更可测试。
  - Alternative considered: 自定义 JavaScript multi-select。拒绝，因为会增加 dirty-form、disabled fields 和 htmx partial 状态同步风险。

- Jira field filters 使用 explicit native field id/name 保存。
  - Rationale: `Program Increment` 等 Jira 自定义字段可能同名；保存 `customfield_31601` 这类 native id 比保存 display label 更可靠。
  - Alternative considered: 用 field display name 生成 JQL。拒绝，因为同名字段和 Jira 实例差异会造成查询歧义。

- Metadata adapter 统一 unwrap paged payloads。
  - Rationale: Jira Data Center/current atlassian client 会把 issue types 放在 `values`，custom field options 放在 `options`；当前 adapter 把 wrapper key 误当选项。
  - Alternative considered: 在 UI 层特殊处理。拒绝，因为 API 层应统一输出干净候选项。

## Risks / Trade-offs

- [Risk] 新增持久字段需要 migration。 -> Mitigation: default `source_mode='custom_jql'`，旧 scope 的 `jql` 继续有效；builder state 默认为空。
- [Risk] Query Builder 生成 JQL 可能覆盖用户手写 JQL。 -> Mitigation: save path 只根据 selected `source_mode` 读取对应输入，UI 清楚标注 inactive mode ignored。
- [Risk] Jira custom field JQL 语法在某些字段上需要特殊 operator。 -> Mitigation: 第一版支持 `in`/`=` 的列表值，并把复杂条件明确留给 Custom JQL。
- [Risk] metadata context 不持久化会让用户返回页面后需要重新输入 selected projects。 -> Mitigation: Query Builder selections 会持久化；Custom JQL mode 的 selected projects 保持临时刷新辅助，页面文案说明这一点。
- [Risk] Scope Config 页面信息量增加。 -> Mitigation: 使用 full-width sections、compact headings、segmented source mode control、short helper text 和 Bulma density，不使用嵌套 cards。

## Migration Plan

1. 增加 `source_mode` 和 query builder JSON state 字段，迁移旧 scope 为 `custom_jql` 且保留现有 `jql`。
2. 在 scope config dataclass、normalization、hash、import/export、duplicate 和 save path 中传递 source mode / builder state。
3. 添加 Jira query builder helper，负责从结构化 selections 生成 JQL preview 和 final persisted JQL。
4. 修复 Jira metadata adapter wrapper parsing，并补 regression tests 覆盖 `values` issue types 和 `options` custom field values。
5. 重构 Scope Config context，把 source population、metadata discovery context、semantic mapping、optional display fields 分区输出。
6. 更新 Scope Config template，展示互斥 source mode controls、Custom JQL editor、Query Builder editor、generated JQL preview、metadata context 说明和 optional display fields。
7. 更新 focused view/facade/model tests，覆盖 Custom JQL save、Query Builder save、metadata context 非 runtime filter、round-trip builder selections、stale hash 行为。
8. 运行 focused Django tests、`manage.py check`、migration dry-run/OpenSpec strict validation 和 whitespace checks。

## Open Questions

- 第一版 Query Builder 是否需要把 `Epic Link` 做成专门控件，还是先作为 generic custom field filter 处理。这个选择不改变 source-mode 架构，可在 implementation 中按现有 Jira field metadata 能力选择较小实现。

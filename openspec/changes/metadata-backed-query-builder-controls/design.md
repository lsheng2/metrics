## Context

See `proposal.md` - Why. 当前 Jira Scope Config 已经有互斥 `Custom JQL` / `Query Builder` source mode，`Query Builder` 会从结构化 builder state 生成最终 `jql` 并保存。页面也已有 metadata refresh partial，但发现到的 issue type、component、version、priority、resolution 和 field metadata 只显示为参考列表，没有驱动 Source population 输入控件。

项目 UI 栈是 Django templates、Bulma 和 htmx。实现必须保留 server-rendered 表单和现有 save path，不引入新的客户端状态框架。

## Goals / Non-Goals

**Goals:**

- 在 Query Builder section 中复用 Jira metadata，优先让用户点选支持的 source filter values。
- 保留每个 source filter 的手动 fallback，让 metadata 缺失、权限受限或 Jira 返回不完整时仍可保存正确 JQL。
- 让 htmx metadata refresh 后的 partial 能同步更新 Query Builder controls 和 discovered metadata summary。
- 让 POST handling 合并 metadata-selected values 和 manual values，并继续由 `JiraScopeQueryBuilder` 生成唯一 persisted JQL。
- 覆盖 Custom JQL isolation，避免 metadata-backed controls 变成隐藏 runtime filter。

**Non-Goals:**

- 不新增数据库字段或改变 scope hash authority。
- 不实现 Jira label autocomplete 或异步 custom-field-values picker。
- 不把 Query Builder 扩展成完整 JQL IDE；复杂条件仍由 Custom JQL mode 承担。
- 不改变 HSD-ES provider profile/source ownership 行为。

## Decisions

- Query Builder control view-model 在 facade 中构造。
  - Rationale: Django template 不适合做复杂选中态/候选项合并；facade 已经拥有 source mode context、metadata options 和 POST parsing。
  - Alternative considered: 在 template 中直接遍历 metadata 并判断 selected values。拒绝，因为 Django template 对 list membership 和字段映射表达能力弱，会让 UI 逻辑分散。

- Metadata-backed fields 使用 checkbox multi-select plus manual textarea。
  - Rationale: 这些字段是低到中等数量的枚举值，checkbox 在 Bulma/server-rendered 页面中可读、可测试，并且能和当前 POST shape 共用同一个 field name。
  - Alternative considered: 使用 `<select multiple>`。拒绝，因为多选框在浏览器里可发现性差，移动端交互也更弱。

- Manual fallback 使用独立 `*_manual` POST names，然后 parser 合并。
  - Rationale: 可以区分 metadata-selected values 与额外手填值，同时不破坏现有 `query_builder_issue_types` 等 repeated value POST 兼容性。
  - Alternative considered: checkbox 和 textarea 共用同名字段。拒绝，因为 textarea 内容与 checkbox values 混在 `getlist()` 后更难调试和测试。

- Metadata refresh partial 返回 query builder controls 与 metadata summary 的同一片段。
  - Rationale: htmx target 已经是 `#scope-metadata-options`；在这个 target 内放置 refreshed controls 可以避免整页刷新，同时保留原 Source population 的 no-metadata fallback。
  - Alternative considered: 让 refresh 替换整个 Source population section。拒绝，因为需要携带更多 form state，风险更高。

- Custom field picker 第一版只选择 field id，values 继续手动输入。
  - Rationale: 已有 API 支持按 project/type/field 拉 custom field values，但前端还没有 field-change htmx endpoint；本 change 先消除最容易错的 custom field id 输入，同时保留 values fallback。
  - Alternative considered: 实现每个 custom field row 的动态 allowed-values refresh。推迟，因为它需要更多交互状态和额外 partial endpoint，超出本次可控范围。

## Risks / Trade-offs

- [Risk] Metadata options 很多时 checkbox 列表过长。 -> Mitigation: 使用紧凑 wrapping option group、限制 Source section 的视觉密度，并保留 manual textarea 作为快速输入。
- [Risk] htmx partial 内的新增控件没有绑定 preview listeners。 -> Mitigation: 在 `htmx:afterSwap` 后重新初始化 Query Builder behavior，并让 preview collector 支持 checkbox/select/textarea。
- [Risk] 已有测试使用简单 dict，不具备 `getlist()`。 -> Mitigation: parser 保持 dict/list/string 兼容，并为 manual fallback 添加 facade tests。
- [Risk] Custom field allowed values 未自动加载仍需要手输。 -> Mitigation: UI 明确 values fallback；field id 可以通过 metadata field picker 点选，已显著降低错误率。
- [Risk] Metadata refresh 不触发时 Source section 仍显示旧 textarea。 -> Mitigation: 页面首次渲染没有 metadata 时继续显示 manual-first controls；refresh 后显示 metadata-backed options。

## Migration Plan

1. 添加 facade view-model，把 `ScopeConfigOptions` 和 current builder state 映射为 Query Builder control descriptors。
2. 更新 POST parser，合并 `query_builder_*` metadata selections 与 `query_builder_*_manual` fallback values。
3. 更新 Scope Config template，把 no-metadata fallback 和 refreshed metadata-backed controls 作为同一套 Query Builder UI。
4. 更新 metadata partial，让 htmx refresh 可以渲染 Query Builder controls，同时保留 discovered metadata summary。
5. 更新 JavaScript preview collection，支持 checkbox/select/manual textareas and htmx reinitialization。
6. 增加 focused tests，先验证 RED，再实现到 GREEN。
7. 运行 OpenSpec、Django focused tests、Django checks、migration dry-run、whitespace 和 browser smoke。

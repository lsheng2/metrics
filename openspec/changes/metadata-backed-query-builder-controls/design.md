## Context

See `proposal.md` - Why. 当前 Jira Scope Config 已经有互斥 `Custom JQL` / `Query Builder` source mode，`Query Builder` 会从结构化 builder state 生成最终 `jql` 并保存。页面也已有 metadata refresh partial，但发现到的 issue type、component、version、priority、resolution 和 field metadata 只显示为参考列表，没有驱动 Source population 输入控件。

项目 UI 栈是 Django templates、Bulma 和 htmx。实现必须保留 server-rendered 表单和现有 save path，不引入新的客户端状态框架。

## Goals / Non-Goals

**Goals:**

- 在 Query Builder section 中复用 Jira metadata，优先让用户点选支持的 source filter values。
- 将 Jira 的 Source population 和 Metadata discovery context 合并为一个工作区，让 metadata 只作为字段 picker 和 validation 的后台数据源；不再显示独立的 discovered metadata catalog。
- 保留每个 source filter 的可手写输入，让 metadata 缺失、权限受限或 Jira 返回不完整时仍可保存正确 JQL。
- 让点击每个 picker 的下拉按钮时触发同一批 metadata refresh，并在刷新后打开对应字段的 searchable picker。
- 让 htmx metadata refresh 后的 partial 能同步更新 Query Builder controls、inline metadata status 和 validation result。
- 让 POST handling 合并 metadata-selected values 和 manual values，并继续由 `JiraScopeQueryBuilder` 生成唯一 persisted JQL。
- 提供保存前 metadata validation，检查手写值/选中值是否能在当前 Jira metadata 中找到，同时不保存 scope。
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

- Metadata-backed fields 使用 editable input/textarea plus searchable picker。
  - Rationale: 用户最终是在填写字段值；输入框保持手写能力，旁边的 picker 让 metadata 可选值在同一位置出现。多值字段通过 picker 追加到 textarea，单值字段通过 picker 回填 input。
  - Alternative considered: 保持 checkbox 列表。拒绝，因为选项多时占用空间大，而且和“每个字段旁边下拉搜索”的期望不一致。

- Editable inputs 使用原有 `query_builder_*` POST names。
  - Rationale: picker 追加的值与手写值天然进入同一表单字段；现有 parser 已支持 text/list shape 并会 normalize/dedupe。
  - Alternative considered: 继续使用独立 `*_manual` 字段。拒绝，因为 UI 合并后不再需要暴露“metadata vs manual”两个输入通道。

- Picker refresh 使用 existing metadata endpoint 和 out-of-band swap。
  - Rationale: 每个 picker 按钮都带当前 form payload 调用同一 metadata partial；后端按当前 project/issue type 批量刷新所有相关 metadata，并通过 OOB swap 替换 Query Builder controls。`open_picker` 决定刷新后打开哪个 picker。
  - Alternative considered: 为每个字段新增独立 endpoint。拒绝，因为 Jira metadata 之间有共同的 project/issue-type context，逐字段请求会重复调用 Jira。

- Custom field picker 第一版只选择 field id，values 继续手动输入。
  - Rationale: 已有 API 支持按 project/type/field 拉 custom field values，但前端还没有 field-change htmx endpoint；本 change 先消除最容易错的 custom field id 输入，同时保留 values fallback。
  - Alternative considered: 实现每个 custom field row 的动态 allowed-values refresh。推迟，因为它需要更多交互状态和额外 partial endpoint，超出本次可控范围。

- Validation 是显式的 pre-save action，不强制阻塞 Save Draft。
  - Rationale: Jira metadata 可能受权限、project scope 或 field configuration 限制而不完整；校验应告诉用户哪些值 confirmed、哪些仍是 manual/unconfirmed，而不是把合法但未枚举出的值一律拦下。
  - Alternative considered: 保存时强制拒绝所有未匹配 metadata 的值。拒绝，因为这会破坏手写 fallback 的核心目的。

- Discovered metadata catalog 永久隐藏。
  - Rationale: 用户真正需要的是填写字段值；Custom JQL 用户如果不知道值，可以切到 Query Builder 用 picker 选择并生成 JQL。展示完整 metadata catalog 会制造第二个信息区，增加认知负担。
  - Alternative considered: 仅在 Custom JQL 下展示 metadata catalog。拒绝，因为这仍然让 Custom JQL 和 Query Builder 形成两套找值入口。

## Risks / Trade-offs

- [Risk] Metadata options 很多时 picker 列表过长。 -> Mitigation: picker 内置 type-in search，列表高度固定滚动，输入框仍可快速手写。
- [Risk] htmx partial 内的新增控件没有绑定 preview listeners。 -> Mitigation: 在 `htmx:afterSwap` 后重新初始化 Query Builder behavior，并让 preview collector 支持 checkbox/select/textarea。
- [Risk] 已有测试使用简单 dict，不具备 `getlist()`。 -> Mitigation: parser 保持 dict/list/string 兼容，并为 manual fallback 添加 facade tests。
- [Risk] Custom field allowed values 未自动加载仍需要手输。 -> Mitigation: UI 明确 values fallback；field id 可以通过 metadata field picker 点选，已显著降低错误率。
- [Risk] Metadata refresh 不触发时用户不知道可选项来自哪里。 -> Mitigation: 每个 picker 按钮即是 refresh affordance；没有 metadata 时按钮仍可点并显示 inline loading/status。
- [Risk] Batched refresh 比单字段刷新返回更多数据。 -> Mitigation: 复用缓存；项目列表、优先级、resolution、fields 是通用 metadata，project-scoped components/versions/statuses 随当前 project/issue-type 一次刷新，避免多次 Jira round-trip。

## Migration Plan

1. 添加 facade view-model，把 `ScopeConfigOptions` 和 current builder state 映射为 Query Builder control descriptors。
2. 更新 POST parser，合并 `query_builder_*` metadata selections 与 `query_builder_*_manual` fallback values。
3. 更新 Scope Config template，把 Jira metadata discovery context 合并进 Source population，并移除页面下方独立 Jira metadata section。
4. 更新 metadata partial，让 htmx refresh 可以渲染 Query Builder controls、inline metadata status 和 validation result。
5. 更新 JavaScript picker behavior，支持 searchable option filtering、option append/replace、htmx swap 后重新初始化、picker open state 和 loading state。
6. 增加 focused tests，先验证 RED，再实现到 GREEN。
7. 运行 OpenSpec、Django focused tests、Django checks、migration dry-run、whitespace 和 browser smoke。

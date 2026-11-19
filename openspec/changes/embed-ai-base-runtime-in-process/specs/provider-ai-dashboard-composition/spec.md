# Spec Delta

## ADDED Requirements

### Requirement: Embedded AI runtime operates only through Metrics App tools
嵌入的 AI 运行时 SHALL 只通过 Metrics App 包中的 tool、context provider 和 host action 使用 Metrics 的 catalog、profile、chart recipe、render config 校验、evidence 和发布服务；它 SHALL NOT 修改 Metrics 代码、直接访问 provider，或拥有 Metrics facts、provider 凭据、profile registry 和 chart 语义。`read` tool（`metrics.catalog`、`metrics.chart_workflow`）SHALL NOT 改变 Metrics 或 Grafana 的状态；导入 Grafana 只能经过需要审批的 `external` tool `metrics.publish_chart`。

#### Scenario: AI starts a dashboard edit
- **WHEN** 用户在嵌入聊天中要求创建或调整 Grafana 图表
- **THEN** AI SHALL 先通过 `metrics.catalog` 读取 capability、catalog 和 profile 元数据
- **AND** AI SHALL 产出结构化的草稿意图或 render config，SHALL NOT 产出修改 dashboard 后端代码的补丁

#### Scenario: AI model is not configured
- **WHEN** 嵌入运行时没有配置 AI 模型
- **THEN** Metrics SHALL 仍然支持 provider sync、profile 选择、已批准图表、Grafana 渲染、evidence 和确定性 API，且不依赖 AI 模型

#### Scenario: Model requests a supported chart
- **WHEN** 模型以 profile、chart id、requested series 和 range 调用 `metrics.chart_workflow`
- **THEN** tool SHALL 返回与 operator 工作流页面相同的工作流信封，包括校验状态、render config 预览摘要和发布就绪状态
- **AND** 这次调用 SHALL NOT 写入任何 Metrics 或 Grafana 状态

#### Scenario: Model asks to publish
- **WHEN** 模型调用 `metrics.publish_chart`
- **THEN** 运行时 SHALL 先创建等待人工决定的审批，审批通过之前 SHALL NOT 导入 Grafana

### Requirement: AI-authored chart drafts are validated as tool inputs
AI 生成的 render config 或 Grafana 草稿 SHALL 作为 `metrics.chart_workflow` 或 `metrics.publish_chart` 的参数交给 Metrics 校验，在校验通过并经审批发布之前 SHALL 保持未发布；Metrics SHALL NOT 存储未校验的草稿，SHALL NOT 直接信任 AI 提供的 dashboard JSON。校验 SHALL 覆盖会话 `ContextRef` 边界、profile 引用、chart recipe 或 data-block 引用、series、canonical 与 category 字段、render 形状、datasource 白名单、range 与数量上限、evidence 链接、秘密安全和 provider 原生字面量禁令。AI SHALL NOT 修改 Dashboard 应用代码、provider profile 配置、原生查询或 Metrics 的 chart recipe 代码。

#### Scenario: Draft passes validation
- **WHEN** AI 用一个引用已批准 recipe 或 data block、且 provider 与 profile 都在会话 `ContextRef` 边界内的草稿调用 `metrics.chart_workflow`
- **THEN** Metrics SHALL 返回 `draft_validated`、规范化的 render config 预览、correlation id 和下一步操作
- **AND** 这次校验 SHALL 作为 tool 调用记录在 AI 运行时审计中
- **AND** 之后的发布 SHALL 由 `metrics.publish_chart` 用同样的参数重新生成并校验，而不是引用一份已存储的草稿

#### Scenario: Draft references a profile outside the session boundary
- **WHEN** 草稿引用会话 `ContextRef` 边界之外的 provider 或 profile
- **THEN** Metrics SHALL 以 `ToolError("context_boundary_violation")` 拒绝该草稿（`ToolError` 只携带注册表中的 code，不附 findings），SHALL NOT 读取或写入 Metrics 数据
- **AND** Metrics SHALL NOT 从中生成可导入的 Grafana JSON

#### Scenario: Draft fails validation
- **WHEN** 草稿包含未批准的 datasource、原始 JQL/EQL、provider 原生字段字面量、疑似秘密的值、无界 SQL、不支持的 chart id 或不支持的 profile
- **THEN** Metrics SHALL 返回带字段路径和原因的结构化 findings，SHALL NOT 生成可导入的 Grafana JSON
- **AND** 发布就绪状态 SHALL 保持不可用

#### Scenario: Draft references unsupported semantics
- **WHEN** 草稿引用 Metrics 未批准的 chart id、series、canonical 字段、transform 或 provider 边界
- **THEN** Metrics SHALL 返回结构化 findings 或 `needs_metric_recipe`
- **AND** Metrics SHALL NOT 发布或导入 Grafana dashboard

### Requirement: Operator workflow page shows runtime and publish readiness
`/ai-dashboard/workflow/` 页面 SHALL 让操作者不经过聊天、直接运行与 `metrics.chart_workflow` 相同的工作流，并显示 AI 运行时状态、所选 provider profile、range、chart recipe、请求的 series、校验结果、草稿预览状态、发布就绪状态和下一步操作。AI 运行时未就绪时页面 SHALL 仍然可用。页面 SHALL NOT 显示 gcx、dry-run proof 或 sidecar 握手状态。

#### Scenario: Supported HSD-ES request produces a draft
- **WHEN** 操作者对 profile `nvu-ttl-hsdes`、chart `open_bug_trend`、series `new_critical_high` 运行工作流
- **THEN** 结果 SHALL 是 `draft_validated`，并附带安全的 render config 预览
- **AND** 页面 SHALL NOT 显示 HSD-ES 原生查询文本、凭据或私有路径

#### Scenario: Unsupported HSD-ES semantic is blocked
- **WHEN** 操作者对 profile `nvu-ttl-hsdes`、chart `open_bug_trend`、series `new_critical` 运行工作流
- **THEN** 结果 SHALL 是 `needs_metric_recipe`，并原样保留请求的 series
- **AND** 工作流 SHALL NOT 把它映射为 `new_critical_high`

#### Scenario: Jira profile uses the same workflow
- **WHEN** 操作者对 profile `chiplet-2a-jira`、chart `open_bug_trend`、series `new_critical_high` 运行工作流
- **THEN** 结果 SHALL 使用与 HSD-ES 相同的信封和状态值，并显示 provider `jira` 和下一步操作
- **AND** 页面 SHALL NOT 包含 provider 专属的 UI 分支，SHALL NOT 显示 Jira 凭据

#### Scenario: AI runtime is not ready
- **WHEN** AI pane 的状态是 `not_configured` 或 `not_running`
- **THEN** 页面 SHALL 仍然可以运行 Metrics 本地工作流，并显示运行时状态和对应的下一步操作

### Requirement: Workbench passes context to AI only as a ContextRef
Workbench 向 AI 传递上下文时 SHALL 只传 `ContextRef`，其中只包含标识和选择值：scope binding key、profile、provider、range、chart、bucket/series 和有上限的已选 ticket id。`metrics.workbench` context provider SHALL 在服务端把它解析为已批准的状态和安全摘要。`ContextRef`、iframe URL 和解析结果 SHALL NOT 包含凭据、私有路径、provider 原生秘密或不受限制的查询文本。

#### Scenario: Workbench sends context to AI
- **WHEN** profile、range、chart 或选择变化后，shell 更新 AI pane 的上下文
- **THEN** shell SHALL 只向嵌入聊天发送新的 `ContextRef`
- **AND** context provider SHALL 只解析出安全的 Metrics 上下文字段和有上限的证据摘要
- **AND** 敏感的 provider 配置 SHALL 按现有 AI dashboard 上下文规则省略或脱敏

#### Scenario: AI runtime is not ready
- **WHEN** AI pane 的状态是 `not_configured` 或 `not_running`
- **THEN** AI pane SHALL 显示该状态的诊断信息
- **AND** Dashboard 的图表、证据、设置、发布历史和 Grafana 渲染 SHALL 保持可用

## MODIFIED Requirements

### Requirement: AI workflow envelope is provider neutral
Metrics SHALL expose a workflow envelope for AI dashboard requests that describes profile、range、chart recipe、requested series、validation、draft preview、publish readiness and audit state without embedding provider-native query language.

#### Scenario: Workflow envelope is returned
- **WHEN** a user submits an AI chart request through the dashboard workflow page or `metrics.chart_workflow`
- **THEN** Metrics SHALL return a structured envelope containing profile id, provider id, dashboard uid, chart id, requested series, range mode, range bounds, intent validation result, render config preview summary, publish readiness and safe user-facing guidance

#### Scenario: Provider-native secrets are present in source configuration
- **WHEN** the selected profile contains Jira JQL、HSD-ES saved query metadata、credentials、tokens、private paths or native field mappings
- **THEN** the workflow envelope SHALL omit or redact those values and SHALL expose only approved catalog/profile provenance, canonical metric names and safe artifact references

### Requirement: AI generated chart workflow is preview-first
AI dashboard workflow SHALL treat generated render configs as drafts until validation and publish readiness checks complete.

#### Scenario: Draft render config is valid
- **WHEN** intent validation produces a render config draft and Metrics render-config validation passes
- **THEN** the workflow SHALL show the draft as previewable and eligible for an approval-gated `metrics.publish_chart` call, not as already published

#### Scenario: Draft render config is invalid
- **WHEN** render-config validation fails
- **THEN** the workflow SHALL show structured findings and SHALL NOT expose a publish-ready state

### Requirement: Jira and HSD-ES profiles share the same AI composition surface
Metrics SHALL use the same AI dashboard composition workflow for Jira and HSD-ES profiles, with provider differences handled by profile registry、fact adapters、chart recipes and render config validation rather than separate UI logic.

#### Scenario: Jira first provider uses the workflow
- **WHEN** profile `chiplet-2a-jira` is selected for an AI dashboard request
- **THEN** Metrics SHALL validate the request through the same catalog and chart workflow services used for HSD-ES

#### Scenario: HSD-ES second provider uses the workflow
- **WHEN** profile `nvu-ttl-hsdes` is selected for an AI dashboard request
- **THEN** Metrics SHALL validate the request through the same catalog and chart workflow services used for Jira

### Requirement: Workflow result is the preferred AI composition envelope
Dashboard SHALL expose a single workflow result envelope that combines catalog/profile context, intent validation, render-config validation, publish readiness, correlation id and next-action guidance for AI dashboard composition.

#### Scenario: Supported Jira chart request
- **WHEN** AI requests `open_bug_trend` for `chiplet-2a-jira` with approved series
- **THEN** the workflow result SHALL include `draft_validated`, render validation, publish readiness and Jira provider/profile provenance in one response

#### Scenario: Supported HSD-ES chart request
- **WHEN** AI requests `open_bug_trend` for `nvu-ttl-hsdes` with approved series
- **THEN** the workflow result SHALL include the same envelope shape as Jira with HSD-ES profile/provider provenance

#### Scenario: Unsupported semantic request
- **WHEN** AI requests a series not approved by the Metrics chart recipe
- **THEN** the workflow result SHALL return `needs_metric_recipe`, SHALL keep render validation and publish readiness as `not_checked`, and SHALL NOT fabricate a valid draft

### Requirement: AI composition publish envelope is Metrics-owned
Metrics SHALL own the envelope that converts a validated AI render draft into an imported Grafana dashboard.

#### Scenario: Publish envelope succeeds
- **WHEN** 审批通过的 `metrics.publish_chart` 调用执行，且重新生成的 preview 摘要与审批绑定的摘要一致
- **THEN** Metrics SHALL import only the dashboard JSON that its render config generator produced for the approved preview
- **THEN** the response SHALL include publication status, dashboard uid, dashboard URL, correlation id, tool call id and audit status

#### Scenario: Publish envelope cannot reach Grafana
- **WHEN** Metrics validation passes but Grafana import fails or Grafana runtime is unavailable
- **THEN** Metrics SHALL return a typed failure result that keeps the validation status (a tool result, not a runtime error code)
- **THEN** Metrics SHALL NOT report publication success

### Requirement: AI chart authoring is recipe-driven
AI dashboard composition SHALL derive supported chart authoring options from Metrics catalog and chart recipes instead of fixed demo literals.

#### Scenario: User asks for a supported chart recipe
- **WHEN** user asks for a chart whose requested chart id, series, profile and range can be matched to a Metrics catalog recipe
- **THEN** the workflow SHALL generate a render-config draft from that recipe and preserve the approved chart id, chart version, value fields, category field, evidence capability and provider binding

#### Scenario: User asks for unsupported recipe or series
- **WHEN** user asks for a chart id or series not listed in Metrics catalog
- **THEN** the workflow SHALL return `needs_metric_recipe` or structured validation findings
- **THEN** it SHALL NOT publish, synthesize or rename the unsupported semantic

#### Scenario: Multiple approved chart recipes exist
- **WHEN** the catalog contains multiple supported chart recipes for a selected profile
- **THEN** AI MAY choose among those recipes only by passing an explicit chart id and requested series to `metrics.chart_workflow`
- **THEN** Dashboard SHALL remain the authority that validates the final draft

### Requirement: Publish response includes recipe and provenance metadata
AI dashboard publish responses SHALL expose enough metadata for audit and history views.

#### Scenario: Publish succeeds
- **WHEN** a chart is published to Grafana
- **THEN** the response SHALL include chart id, chart version, provider id, profile id, requested series, range, render visualization, approval id, tool call id, preview digest, dashboard uid, Grafana URL and audit status

### Requirement: AI chart composition can start from canonical data blocks
AI dashboard composition SHALL support future chart drafting from Metrics-published canonical data blocks, not only from pre-existing chart recipes.

#### Scenario: AI asks available lego blocks
- **WHEN** a user asks what data elements can be used to build Grafana charts
- **THEN** AI SHALL answer from Metrics context bundle data-block catalog, including canonical dimensions, measures, grain, allowed transforms and evidence capability

#### Scenario: AI generates a draft artifact
- **WHEN** AI generates Grafana JSON or a render spec from data blocks
- **THEN** 草稿 SHALL 保持为未发布的 tool 参数，直到 `metrics.chart_workflow` 校验了 canonical fields、transforms、会话 `ContextRef` 边界和 Grafana render constraints

### Requirement: AI Base participates as a workbench pane
AI Base dashboard agent experience SHALL be available as a workbench pane or sidebar whose chat session is bound to the current Metrics context through `ContextRef`, without owning Metrics facts, chart semantics, validation, evidence or publication authority.

#### Scenario: User opens AI assistant inside workbench
- **WHEN** 用户打开 AI assistant pane from the unified workbench
- **THEN** the pane's chat session SHALL be bound to a `ContextRef` carrying the current scope binding key, profile id, provider id, range mode, range bounds, active chart id and selected bucket/series when available
- **AND** AI SHALL use Metrics-approved context and tools rather than direct provider credentials or private Dashboard internals
- **AND** the compact pane SHALL NOT render full AI Base App chrome, settings navigation, workspace catalog, or duplicate service status strip

#### Scenario: User resizes or collapses AI assistant
- **WHEN** 用户拖动 AI pane splitter、折叠 AI pane 或从 right rail 恢复 AI pane
- **THEN** Dashboard SHALL treat that as layout state only
- **AND** AI chat session、pending approvals、tool results and active turn context SHALL remain available after restore

#### Scenario: User asks AI about selected chart evidence
- **WHEN** selected chart state includes a validated bucket/series evidence selection
- **THEN** the context provider MAY include deterministic evidence context from Metrics for that selection
- **AND** AI response SHALL preserve provider/profile/run or snapshot provenance and disclose unavailable evidence states

#### Scenario: User asks AI about selected tickets
- **WHEN** user has selected one or more evidence tickets as an explicit working set
- **THEN** `ContextRef` MAY carry the selected ticket ids, and the context provider MAY resolve them into safe summaries
- **AND** AI SHALL distinguish selected tickets from chart bucket/series selection and from evidence list filters
- **AND** the selected ticket ids SHALL be bounded and expose truncation metadata when the UI selection is larger than the handoff limit

#### Scenario: User asks AI to create or publish a chart from workbench
- **WHEN** AI drafts, validates, previews or publishes a chart from workbench context
- **THEN** Metrics SHALL remain the authority for chart recipe validation, draft validation, preview content, approval authorization, Grafana import and audit
- **AND** the AI pane SHALL surface required approval or validation failures without bypassing Metrics App tools

## REMOVED Requirements

### Requirement: AI dashboard composition uses structured Metrics contracts
**Reason**: 原 scenario 以 "AI sidecar" 和 "AI base is absent" 为前提，嵌入运行时后这两个前提不存在。
**Migration**: 并入 "Embedded AI runtime operates only through Metrics App tools"；两个 scenario 的行为由 "AI starts a dashboard edit" 和 "AI model is not configured" 保留。

### Requirement: AI-generated render drafts are validation-gated
**Reason**: 原 scenario 以 workspace key 为边界，workspace 已删除。
**Migration**: 并入 "AI-authored chart drafts are validated as tool inputs"；边界检查改为会话 `ContextRef`，"Draft fails validation" 的拒绝清单原样保留。

### Requirement: Dashboard AI integration is isolated behind an adapter layer
**Reason**: 隔离边界从 adapter 层变为 `ai_host` 模块，由 `embedded-ai-runtime-host` 统一规定；原 scenario 以 "AI Base enabled/unreachable" 为前提。
**Migration**: 模块隔离和新增 AI 行为的归属见 `embedded-ai-runtime-host` 的 "Only the ai_host module imports the AI runtime"；无模型时的可用性见同一能力的 "AI pane reports runtime readiness without blocking the workbench"；`WorkbenchPageQueryState` 到 `ContextRef` 的转换见 "Workbench passes context to AI only as a ContextRef"。

### Requirement: Workbench context handoff is bounded and explicit
**Reason**: 原 scenario "AI Base is absent or disconnected" 以网络连接为前提；上下文交接改为只传 `ContextRef`。
**Migration**: 由 "Workbench passes context to AI only as a ContextRef" 承接，两个 scenario 的行为保留。

### Requirement: AI base and gcx operate as optional clients
**Reason**: AI 运行时不再是外部客户端；gcx 删除。
**Migration**: "不拥有 Metrics facts、provider 凭据、profile registry 和 chart 语义"由 "Embedded AI runtime operates only through Metrics App tools" 承接；Grafana 写入只经过 `metrics.publish_chart`，见 `ai-dashboard-publish-authority`。

### Requirement: Workflow envelope supports dry-run proof handoff
**Reason**: dry-run proof 删除。
**Migration**: 由 `ai-dashboard-publish-authority` 的 "Approved preview digest binds publish content" 承接。

### Requirement: AI-authored chart artifacts are workspace artifacts
**Reason**: 草稿不再作为 AI Base workspace artifact 存储，也不再有 artifact id、version 和 source workspace id。
**Migration**: 由 "AI-authored chart drafts are validated as tool inputs" 承接，"AI 不修改 Dashboard 代码、profile 配置和 recipe"的要求一并迁入。

### Requirement: Dashboard validates AI workspace artifacts before publish
**Reason**: 校验对象从 workspace artifact 改为 tool 参数。
**Migration**: 由 "AI-authored chart drafts are validated as tool inputs" 承接，校验范围不变。

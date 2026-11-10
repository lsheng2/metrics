# Spec Delta

## ADDED Requirements

### Requirement: Approved preview digest binds publish content
`metrics.publish_chart` 的 preview SHALL 是确定性的：相同参数和相同 Metrics 数据 SHALL 产生字节相同的 dashboard JSON。preview 摘要 SHALL 覆盖 dashboard JSON 和发布目标（Grafana 地址和 dashboard uid），并绑定到审批。运行时 SHALL 在执行已批准的调用之前重新运行 preview；摘要与审批绑定的摘要不一致时，审批 SHALL 作废，handler SHALL NOT 被调用。handler SHALL 只导入 `ctx.approval.preview` 中的内容，并在导入之前再次核对它与摘要一致。

#### Scenario: Preview is repeated with unchanged data
- **WHEN** 同一组参数在 Metrics 数据不变时预览两次
- **THEN** 两次的 dashboard JSON SHALL 字节相同，摘要 SHALL 相同

#### Scenario: Data changes between approval and execution
- **WHEN** 审批通过之后、执行之前，一次 sync 改变了该图表在所选 range 内的数据
- **THEN** 重新 preview 得到的摘要 SHALL 与审批不一致
- **AND** 运行时 SHALL 作废该审批、不调用 handler，并在 tool 结果中说明需要重新审批

#### Scenario: Preview content does not match its digest
- **WHEN** handler 收到的 `ctx.approval.preview` 内容与绑定的摘要不一致
- **THEN** handler SHALL 拒绝导入并返回结构化错误，Grafana SHALL NOT 被调用

### Requirement: Approved publish creates a visible Grafana dashboard
已批准且摘要一致的 `metrics.publish_chart` 调用 SHALL 把已批准 preview 中的 dashboard JSON 导入 Grafana，并返回 dashboard uid 和可访问的 Grafana URL。只有导入成功时，Metrics SHALL 报告发布成功并写入发布历史。数据未就绪或语义不受支持时，preview SHALL 失败，运行时 SHALL NOT 创建审批。

#### Scenario: Approved publish succeeds
- **WHEN** 已批准的调用执行，Grafana 导入成功
- **THEN** tool 结果 SHALL 包含 dashboard uid、Grafana URL、approval id、`tool_call_id` 和 preview 摘要
- **AND** Metrics SHALL 写入一条发布历史
- **AND** 该 URL 打开的 dashboard SHALL 渲染所选 range 的数据

#### Scenario: Grafana is unreachable
- **WHEN** 导入时 Grafana 不可达或返回错误
- **THEN** tool 结果 SHALL 是包含校验状态的结构化错误
- **AND** Metrics SHALL NOT 报告发布成功，SHALL NOT 写入成功的发布历史

#### Scenario: Requested semantic is unsupported
- **WHEN** `metrics.publish_chart` 的参数引用不受支持的 series，例如 profile `nvu-ttl-hsdes` 的 `new_critical`
- **THEN** preview SHALL 失败并返回 `needs_metric_recipe`
- **AND** 运行时 SHALL NOT 创建审批，错误 SHALL 作为 tool 结果返回给模型

### Requirement: Jira-first publish is validated end to end in the embedded chat
Jira profile `chiplet-2a-jira` SHALL 是嵌入聊天发布流程的首个端到端验收场景：从 workbench 打开聊天、请求图表、预览、人工批准、导入 Grafana，到发布历史可见，全程只经过 Metrics App tools 和运行时审批。

#### Scenario: Jira chart is published from the embedded chat
- **WHEN** 用户在绑定 `chiplet-2a-jira` 的 workbench 聊天中，请求 range `26WW32`–`26WW35`、series `new_critical_high` 的 `open_bug_trend` 并批准发布
- **THEN** 工作流 SHALL 依次产生 `draft_validated`、pending 审批、approved 审批和成功的发布结果
- **AND** 返回的 Grafana URL SHALL 渲染该 range 的数据
- **AND** 发布历史 SHALL 出现这次发布，包含 approval id、`tool_call_id` 和 preview 摘要

#### Scenario: Jira data is not ready
- **WHEN** 该 profile 在所选 range 内的 sync 数据缺失或过期
- **THEN** preview SHALL 失败，并说明阻塞原因和对应的 sync 操作
- **AND** 运行时 SHALL NOT 请求审批，SHALL NOT 返回会显示 `No data` 的 Grafana URL

## MODIFIED Requirements

### Requirement: Publish authorization is a bound authority object
Dashboard SHALL NOT publish an AI-generated Grafana dashboard from independently supplied approval/proof strings. 发布授权 SHALL 是运行时为 `metrics.publish_chart` 调用创建的持久化审批，绑定 run id、`tool_call_id`、规范化参数摘要和 preview 摘要。tool 参数 SHALL NOT 包含 approval、proof 或 actor 字段；执行者 SHALL 取自审批的 `decided_by`。

#### Scenario: Publish authorization is requested
- **WHEN** 模型调用 `metrics.publish_chart`
- **THEN** 运行时 SHALL 先运行 Metrics 的 preview，得到摘要信息、确定性的 dashboard JSON 和 preview 摘要
- **AND** 运行时 SHALL 创建 pending 状态的审批，绑定 run id、`tool_call_id`、参数摘要、preview 摘要和过期时间
- **AND** 审批界面 SHALL 显示 profile、provider、chart、series、range 和 Grafana 发布目标

#### Scenario: Human approval is granted
- **WHEN** 通过认证且有决定权的用户批准该审批
- **THEN** 运行时 SHALL 只把这一条审批标记为 approved，并记录 `decided_by`
- **AND** 批准 SHALL NOT 改变已绑定的参数、preview 摘要或 range

#### Scenario: Publish is requested
- **WHEN** 已批准的 `metrics.publish_chart` 调用开始执行
- **THEN** 运行时 SHALL 只执行 `tool_call_id` 和参数摘要都与审批一致的调用
- **AND** pending、被拒绝、已过期或不匹配的审批 SHALL 在调用 handler 之前被拒绝
- **AND** handler SHALL 在导入 Grafana 之前重新生成并校验 render config

#### Scenario: Local demo approval prefix is supplied
- **WHEN** 调用方在 tool 参数或聊天文本中提供带本地 demo 前缀的审批 id，或声称已经批准
- **THEN** tool 参数校验 SHALL 拒绝 approval 字段
- **AND** 运行时 SHALL NOT 根据审批 id 前缀或聊天文本创建、批准或执行审批

#### Scenario: Approval is denied or expires
- **WHEN** 用户拒绝审批，或审批在决定之前过期
- **THEN** `metrics.publish_chart` SHALL NOT 执行，tool 结果 SHALL 报告拒绝或过期
- **AND** Grafana SHALL NOT 被调用

#### Scenario: Approved call is executed again
- **WHEN** 同一个 `tool_call_id` 的已批准调用被再次执行，例如服务重启后恢复运行
- **THEN** handler SHALL 以 `tool_call_id` 为幂等键，返回第一次执行记录的结果
- **AND** handler SHALL NOT 再次导入 Grafana 或写入第二条发布历史，审批 SHALL 只被消费一次

### Requirement: Publish history remains auditable
Dashboard SHALL record approved publish transitions with enough metadata to reconstruct the authorization decision. 发布历史 SHALL 保存被批准的规范化 render config，审计 SHALL NOT 依赖 AI 会话是否仍然存在。

#### Scenario: Publish succeeds
- **WHEN** Grafana import succeeds
- **THEN** Dashboard SHALL record publish history with approval id, `tool_call_id`, run id, `decided_by` actor, preview digest, the approved normalized render config, profile/provider, range, chart id, series, dashboard uid, Grafana URL and correlation id

## REMOVED Requirements

### Requirement: Dry-run proof is bound to artifact version
**Reason**: dry-run proof 与 workspace artifact 一起删除。
**Migration**: 发布内容由 "Approved preview digest binds publish content" 绑定：审批绑定 preview 摘要，执行前重新 preview 并比对。

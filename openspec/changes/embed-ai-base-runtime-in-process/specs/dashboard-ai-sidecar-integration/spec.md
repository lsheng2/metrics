# Spec Delta

## REMOVED Requirements

### Requirement: Dashboard sidecar uses AI Base as optional platform
**Reason**: AI Base 改为 Metrics 进程内的运行时，不再是可选的外部 sidecar，也就不存在"未安装、未运行或握手失败"的状态。
**Migration**: 进程组合见 `embedded-ai-runtime-host` 的 "Metrics serves Django and the AI runtime from one composition root"；"没有 AI 时非 AI 功能照常可用"由同一能力的 "AI pane reports runtime readiness without blocking the workbench" 承接（未配置模型的情形）。

### Requirement: Sidecar handshake is identity-checked
**Reason**: 没有 sidecar 端口，也就没有需要校验身份的握手。MDB-0 已经确认，未鉴权握手返回的值不能作为身份证明。
**Migration**: 由 `embedded-ai-runtime-host` 的 "Metrics and the AI runtime share no HTTP integration" 取代。

### Requirement: Dashboard-to-AI request context is bounded
**Reason**: Metrics 不再向 AI Base 发送上下文信封。会话只绑定一个只含 id 的 `ContextRef`，内容由 Metrics 的 context provider 在服务端解析。
**Migration**: 由 `ai-centric-metrics-workspace-composition` 的 "Metrics exposes workspace context bundles" 和 `provider-ai-dashboard-composition` 的 "Workbench context handoff is bounded and explicit" 承接，脱敏要求保留在后者。

### Requirement: AI Base calls Metrics contracts before generating outputs
**Reason**: `/api/ai-dashboard/` 下的 connector HTTP 路由全部删除。
**Migration**: 由 `provider-ai-dashboard-composition` 新增的 "Embedded AI runtime operates only through Metrics App tools" 承接。保留 series 身份、不合成未批准语义的要求仍由同一能力的 "AI cannot own business semantics" 规定。

### Requirement: gcx operations are Metrics-preconditioned
**Reason**: 删除 gcx。Grafana 只由 `metrics.publish_chart` 在审批通过后导入 Metrics 生成的 dashboard JSON。
**Migration**: 由 `ai-dashboard-publish-authority` 的 "Publish authorization is a bound authority object" 承接。

### Requirement: AI Base exposes reusable platform surfaces
**Reason**: 这是对 AI Base 平台本身的要求，不应由 Metrics 规定；Metrics 也不再作为 AI Base 的第四个 profile 被加载。
**Migration**: Metrics 侧的能力声明由 `embedded-ai-runtime-host` 的 "Metrics App package declares the whole AI surface" 承接；运行时的平台契约见本 change 的上游建议文档（v2.1 D1–D12）。

### Requirement: Sidecar results are auditable and replayable
**Reason**: 不再有跨进程的结果信封，运行时事件直接写入 Metrics。
**Migration**: 由 `embedded-ai-runtime-host` 的 "AI runtime audit is written to Metrics" 和 `ai-dashboard-publish-authority` 的 "Publish history remains auditable" 承接。

### Requirement: Dashboard exposes an operator-facing AI sidecar workflow
**Reason**: sidecar readiness、AI Base profile 和 gcx precondition 都不存在了。
**Migration**: 由 `provider-ai-dashboard-composition` 新增的 "Operator workflow page shows runtime and publish readiness" 承接。

### Requirement: Workflow validates supported and unsupported requests explicitly
**Reason**: 并入 operator 工作流页面的统一 requirement，避免同一行为在两个能力中重复规定。
**Migration**: 三个确定性 try-run（HSD-ES 支持的 series、HSD-ES 的 `new_critical` 被拦截、Jira 使用同一信封）由 `provider-ai-dashboard-composition` 的 "Operator workflow page shows runtime and publish readiness" 承接。

### Requirement: gcx precondition is visible before any mutation
**Reason**: 删除 gcx。
**Migration**: 页面改为显示发布就绪状态，见 `provider-ai-dashboard-composition` 的 "Operator workflow page shows runtime and publish readiness"。

### Requirement: AI Base prefers Dashboard workflow operation
**Reason**: `workflow.run` connector 操作及其旧版回退路径一起删除。
**Migration**: 由 `metrics.chart_workflow` tool 承接，见 `provider-ai-dashboard-composition` 的 "Embedded AI runtime operates only through Metrics App tools"。

### Requirement: Dashboard workflow page explains profile-driven Jira and HSD-ES paths
**Reason**: 并入 operator 工作流页面的统一 requirement。
**Migration**: provider、校验状态、发布就绪状态和下一步操作的显示由 `provider-ai-dashboard-composition` 的 "Operator workflow page shows runtime and publish readiness" 承接。

### Requirement: AI Grafana workflow records dry-run proof before mutation
**Reason**: dry-run proof 由调用方提交，执行方无法证明它的真实性。改为审批绑定由 Metrics 生成的 preview 摘要。
**Migration**: 由 `ai-dashboard-publish-authority` 新增的 "Approved preview digest binds publish content" 承接。

### Requirement: Human approval is required after dry-run proof
**Reason**: 审批改由运行时持久化，并绑定 tool 调用参数和 preview 摘要。
**Migration**: 由 `ai-dashboard-publish-authority` 的 "Publish authorization is a bound authority object" 和 `embedded-ai-runtime-host` 的 "Only authenticated humans decide AI approvals" 承接。

### Requirement: AI Base chat can trigger Dashboard chart workflow demo
**Reason**: 删除硬编码的确定性聊天分支。对话测试的确定性改由 testkit 的脚本化模型提供。
**Migration**: 由 `embedded-ai-runtime-host` 的 "Host conformance suite gates the composed runtime" 和 `ai-dashboard-publish-authority` 新增的 "Jira-first publish is validated end to end in the embedded chat" 承接。

### Requirement: Approved AI chart publish demo creates a visible Grafana dashboard
**Reason**: 发布不再接受 approval id 和 dry-run proof id 参数。
**Migration**: 由 `ai-dashboard-publish-authority` 新增的 "Approved publish creates a visible Grafana dashboard" 承接。

### Requirement: Jira-first AI publish flow uses formal approval state
**Reason**: 正式的审批状态改由运行时持久化，Metrics 删除自己的审批表。
**Migration**: 由 `ai-dashboard-publish-authority` 的 "Publish authorization is a bound authority object" 承接。

### Requirement: Jira-first publish is validated end to end from AI Base Chat
**Reason**: 聊天改为嵌入 Metrics 的运行时聊天，验收流程不再经过 dry-run proof。
**Migration**: 由 `ai-dashboard-publish-authority` 新增的 "Jira-first publish is validated end to end in the embedded chat" 承接。

### Requirement: Dashboard can synchronize Metrics context into AI Base workspaces
**Reason**: 删除 workspace 同步，不再复制一份容易过期的状态。
**Migration**: 由 `ai-centric-metrics-workspace-composition` 的 "Metrics exposes workspace context bundles" 承接：context provider 按 `ContextRef` 实时解析。

### Requirement: AI Base chat can produce publishable Dashboard artifacts
**Reason**: 草稿不再作为 AI Base workspace artifact 存储。
**Migration**: 草稿由 `metrics.chart_workflow` 校验，见 `provider-ai-dashboard-composition` 新增的 "AI-authored chart drafts are validated as tool inputs"；发布内容由 preview 摘要绑定，见 `ai-dashboard-publish-authority` 的 "Approved preview digest binds publish content"。

### Requirement: Human-approved publish is end-to-end auditable
**Reason**: 发布前置条件从 dry-run proof 加 approval id 改为运行时审批加 preview 摘要。
**Migration**: 由 `ai-dashboard-publish-authority` 的 "Publish authorization is a bound authority object" 和 "Publish history remains auditable" 承接。

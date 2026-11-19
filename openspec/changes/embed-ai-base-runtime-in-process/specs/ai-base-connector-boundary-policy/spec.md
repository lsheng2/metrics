# Spec Delta

## REMOVED Requirements

### Requirement: Connector model-visible tools are workspace-bound
**Reason**: connector 及其 workspace 绑定一起删除。
**Migration**: Metrics tool 按会话绑定的 `ContextRef` 校验边界，见 `ai-centric-metrics-workspace-composition` 的 "Workspace boundary is provider and project scoped"。

### Requirement: Connector operations declare sensitivity
**Reason**: connector 操作删除。
**Migration**: 每个 Metrics tool 声明 effect；会写入 Grafana 或改变 Metrics 状态的 tool 必须是需要审批的 `external` tool。见 `embedded-ai-runtime-host` 的 "Metrics App package declares the whole AI surface" 和 "Only authenticated humans decide AI approvals"。

### Requirement: Connector transport verifies local sidecar identity
**Reason**: Metrics 与运行时之间不再有 HTTP 传输。
**Migration**: 由 `embedded-ai-runtime-host` 的 "Metrics and the AI runtime share no HTTP integration" 取代。

### Requirement: Loopback connector calls bypass environment proxies
**Reason**: 进程内调用不经过网络，不存在回环 HTTP 客户端。
**Migration**: 无需迁移。运行时访问模型时的网络策略由运行时规定（本 change 的上游建议文档）。

### Requirement: Dashboard connector write routes accept only JSON bodies
**Reason**: connector 写路由全部删除。
**Migration**: 运行时路由的请求完整性检查由运行时实施，并由 `embedded-ai-runtime-host` 的 "Host conformance suite gates the composed runtime" 验证；Django 自身的表单仍由 CSRF 中间件保护。

### Requirement: Dashboard accepts only loopback hosts unless configured
**Reason**: 能力退役；Host 白名单改为 Django 与运行时共用。
**Migration**: 由 `embedded-ai-runtime-host` 的 "One host allowlist protects Django and the AI runtime" 承接。

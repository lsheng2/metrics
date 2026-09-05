## Why

当前系统已经具备 Metrics context bundle 同步、AI Base workspace 绑定、Metrics workflow validation 和 approval/publish 的基础能力，但用户还不能从 AI Base chat 自然地完成“理解 workspace 数据积木、生成 Grafana chart artifact、提交 Dashboard validation、人工批准后发布到 Grafana”的完整闭环。现在需要把前面几轮通用契约和 demo API 串成一个可试用、可审计、不会让 AI 修改 Dashboard 业务代码的端到端能力。

## What Changes

- 让 AI Base `dashboard_query_agent` 能稳定使用 Metrics workspace context 回答 provider boundary、canonical fields、data blocks、Grafana render constraints 相关问题。
- 引入 artifact-first chart authoring 流程：AI 生成 render config / Grafana draft artifact，artifact 存在 AI Base workspace 中，Dashboard 只接收 artifact validation/publish 请求。
- Dashboard 继续作为 Metrics 语义、provider boundary、render validation、precondition、approval 和 Grafana import 的权威方。
- 增强 Dashboard 与 AI Base/gcx 的 E2E 契约：包含 artifact id/version、correlation id、dry-run proof id、approval id、publish history 和清晰失败原因。
- 不允许 AI 直接修改 Dashboard 后端代码、provider query、profile mapping 或未批准的 metric semantics。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `ai-centric-metrics-workspace-composition`: workspace context 不只用于同步，还 SHALL 成为 AI Base chat grounding 和 artifact authoring 的主要上下文来源。
- `provider-ai-dashboard-composition`: chart authoring SHALL 支持从 AI Base workspace artifact 开始，经过 Dashboard validation/precondition/approval/publish 的端到端闭环。
- `dashboard-ai-sidecar-integration`: sidecar workflow SHALL 支持 chat-triggered artifact generation、dry-run proof、human approval 和 Grafana publish visibility。
- `grafana-render-config`: AI-generated render config artifact SHALL 可被版本化、验证，并作为 Grafana JSON 生成输入。

## Impact

- Dashboard app:
  - `bug_metrics/app/api/*` 的 AI composition、render validation、publish/approval API。
  - `ui_web` 的 AI dashboard workflow/API tests。
  - Grafana render config validator/generator 和 publish history。
- AI Base app:
  - `dashboard_query_agent` profile、workspace source context injection、artifact storage/versioning、Metrics connector operations、gcx dry-run/publish flow。
  - Desktop chat/workspace UI 对 workspace context 和生成 artifact 的展示。
- External runtime:
  - Local Grafana 通过 Metrics-owned validated artifact import。
  - `gcx` 只作为受控 Grafana operation tool，不拥有 Metrics 语义或 provider 数据。

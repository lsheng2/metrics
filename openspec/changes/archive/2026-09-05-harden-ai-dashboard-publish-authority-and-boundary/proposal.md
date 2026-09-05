## Why

两轮架构 review 都确认当前 AI-centric dashboard 的总体方向是正确的：AI Base 作为通用 workspace/session/artifact/tool 平台，Metrics Dashboard 作为 provider facts、chart semantics、Grafana render validation 和 publish authority 的所有者。但当前实现仍把 Grafana publish 的 approval、dry-run proof、artifact reference 当成可独立传入的字符串处理，并且部分 connector/tool 路径没有绑定 active workspace boundary。

这个 change 需要把 AI 生成 chart 到 Grafana publish 的关键安全边界升级成架构级 authority：发布必须由不可伪造、可审计、绑定 artifact/version/proof/approval/scope 的授权对象驱动；connector 必须按 workspace/project/profile 边界执行；AI Base generic 平台不得继续硬编码 Dashboard policy。

## What Changes

- Dashboard publish 从 string-based approval/proof 改为 bound publish authorization workflow。
- Dashboard artifact validation SHALL 校验 `workspace_key` 与 artifact 内 profile/provider/project scope 一致。
- AI Base connector runtime SHALL 在 model-visible tool invocation 时绑定 active workspace context，并拒绝跨 provider/profile/project 参数。
- AI Base connector transport SHALL 对本地 Dashboard connector 做 sidecar identity check，并对 loopback HTTP 禁用环境代理。
- AI Base artifact authority policy SHALL 从 Dashboard-specific hardcode 演进为 generic app artifact policy registry。
- AI Base artifact revision SHALL 支持 append-only version history，publish/dry-run/approval 引用 immutable artifact version。
- E2E smoke SHALL 覆盖 dry-run proof、approval、publish authority、publish history；真实 Grafana mutation 可保留为显式可选 live gate。
- 修正 runbook/docs 中 `modelVisibleOperations` 与 internal governed workflow operation 的表述。

## Capabilities

### New Capabilities
- `ai-dashboard-publish-authority`: 定义 Dashboard/AI Base/Grafana publish 的 bound authorization、proof、approval、artifact version 与 audit 语义。
- `ai-base-connector-boundary-policy`: 定义 AI Base connector model-visible tool 的 workspace boundary、identity、proxy 和 operation sensitivity policy。

### Modified Capabilities
- `dashboard-ai-sidecar-integration`: 加强 AI sidecar publish、approval、dry-run、connector invocation 的安全边界。
- `provider-ai-dashboard-composition`: 加强 workspace/profile/provider boundary validation，确保 Metrics validator 不接受跨 workspace/profile artifact。
- `grafana-render-config`: 将 AI publish artifact 与 immutable render config/version/proof 绑定。
- `ai-centric-metrics-workspace-composition`: 明确 workspace context boundary 是 connector/model-visible operation 的执行约束。

## Impact

- Dashboard repo:
  - `bug_metrics/app/api/ai_dashboard_approval.py`
  - `bug_metrics/app/api/ai_context.py`
  - `bug_metrics/app/api/ai_dashboard_composition.py`
  - `bug_metrics/app/api/ai_dashboard_composition_contracts.py`
  - `ui_web/views/ai_dashboard_view.py`
  - `ui_web/tests/test_ai_dashboard_api_surface.py`
  - `scripts/e2e_dashboard_ai_stack.ps1`
  - `docs/validation/dashboard-ai-e2e-runbook.zh.md`
- AI Base repo:
  - `services/app-service/app/services/connectors/*`
  - `services/app-service/app/services/workspace_artifacts.py`
  - `services/app-service/app/services/workspace_catalog.py`
  - `services/app-service/app/routes/dashboard_chat_shortcuts.py`
  - `services/app-service/tests/test_chat_api.py`
  - `services/app-service/tests/test_dashboard_profile_metrics_connector.py`
  - `services/app-service/tests/test_workspace_artifacts.py`
  - `config/dashboard/metrics-connector-operations.json`
- Cross-app contract:
  - publish authorization id / dry-run proof id / artifact ref / artifact version / workspace key / profile-range-series tuple must be validated together.

# Tasks

## 1. Sidecar 握手

- [x] 1.1 删除 `bug_metrics/app/api/ai_sidecar.py` 中的 `instanceToken` 比对和 `_config['instance_token']`。`METRICS_AI_BASE_INSTANCE_TOKEN` 保留，因为在 AIB-2/MDB-2 切换之前 adapter 仍要用它做 binding 认证。验证：`bug_metrics/tests/test_api_ai_sidecar.py` 通过；新增用例证明 token 不一致时探活结果仍为 `ready`，且状态中不含 token。

## 2. Connector 写路由只接受 JSON

- [x] 2.1 新增 `ui_web/views/ai_dashboard_connector_endpoint.py` 中的 `connector_endpoint`，替换 9 个 connector 视图上的 `csrf_exempt`。验证：`ui_web/tests/test_ai_dashboard_api_surface.py` 中，9 个写路由分别以 3 种 CORS 简单请求类型发送，全部返回 415。
- [x] 2.2 伪造的跨站审批决策不生效。验证：`ui_web/tests/test_ai_dashboard_publish_authority.py` 中，以 `text/plain` 发送的决策返回 415，审批仍为 `pending_approval`；其余 connector、sidecar 和 workbench 相关测试通过。
- [x] 2.3 `ALLOWED_HOSTS` 只在 `metrics/settings/defaults.py` 定义，默认值为 `127.0.0.1`、`localhost`、`[::1]`；删除 production 和 development 中的 `['*']`；README 写明如何为其他主机名配置。验证：`metrics/tests/test_defaults_metrics.py` 在清除 `ALLOWED_HOSTS` 且不读取 `.env` 的子进程中，分别加载 production 和 development settings，结果拒绝 `rebind.attacker.example`、接受三个回环地址。

## 3. 规格同步

- [x] 3.1 delta spec 修改 "Sidecar handshake is identity-checked"，并新增 connector JSON-only 和回环 Host 两条 requirement。验证：`openspec validate harden-ai-base-sidecar-and-connector-inputs --strict` 通过。

## Workflow follow-up

- 归档本 change，把三条 requirement 同步到 baseline spec；归档后运行 `openspec validate --specs --strict`。
- 有意不写 design：改动只有一个装饰器、一处删除和一个默认值收紧，决策理由已在 proposal 中说明。

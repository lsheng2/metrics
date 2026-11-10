# Proposal

## Why

对 AI Base 的中立评审（`embed-ai-base-runtime-in-process/upstream-ai-base-runtime-proposal.md` 的 F1、F3、F11）
发现 Dashboard 侧有三处缺陷：现在就能被利用，而且不需要 AI Base 配合就能修复。

- sidecar 探活把 `/health/handshake` 返回的 `instanceToken` 与 `METRICS_AI_BASE_INSTANCE_TOKEN` 比对，并把比对结果
  当作 AI Base 的身份证明。但这个端点不鉴权，会把 token 返回给任何调用方，同机进程可以先读取再冒充。所以这项比对
  证明不了服务端身份，还会让人误以为握手做了认证。
- connector 的 9 个写路由（`/api/ai-dashboard/*` 下的 POST）全部 `csrf_exempt`、不做认证，`json_body` 也不检查
  `Content-Type`。任何网页都能以 `text/plain`、表单或 multipart 这三种 CORS 简单请求直接 POST 到本机 Dashboard，
  完全不经过预检。例如，伪造一次 `publish_approval.decide`，就能把待审批的 Grafana 发布改成 approved。
- `ALLOWED_HOSTS` 默认是通配符，DNS rebinding 之后的页面会被当作同源，连预检这道防线也能绕过。

三项改动都只涉及 Dashboard，并且兼容现有 AI Base：AI Base 的 `HttpxConnectorTransport` 用 `json=` 发送请求，本身
就带 `application/json`，并且通过 `127.0.0.1` 访问。因此本 change 可以先于 AI Base 的 AIB-0 发布。它就是上游建议
中的 MDB-0，拆成独立 change 是为了能单独归档。

## What Changes

- sidecar 握手只用 `serviceId`、profile 和能力摘要来发现配置错误；删除 `instanceToken` 比对，并在 spec 中写明握手
  不是认证。`METRICS_AI_BASE_INSTANCE_TOKEN` 暂时保留：在 AIB-2/MDB-2 同版本切换之前，
  `ui_web/ai_base_workbench_adapter.py` 仍用它完成服务端 binding 认证。切换时它随整个 HTTP 集成一起删除。
- 新增 `connector_endpoint` 装饰器（`ui_web/views/ai_dashboard_connector_endpoint.py`），替换 9 个 connector 视图
  上的 `csrf_exempt`。带请求体的方法只接受 `Content-Type: application/json`，其他类型在视图读取请求体之前就返回
  HTTP 415。CSRF 豁免和 JSON-only 写在同一处，因为 CSRF 豁免的安全前提，正是浏览器发出的跨站请求必须先经过
  CORS 预检。
- 关闭 DNS rebinding：`manage.py` 默认使用 `metrics.settings.production`，而 production 和 development 的
  `ALLOWED_HOSTS` 默认都是 `['*']`。在未启用 BasicAuth 的部署上，浏览器会把 rebinding 之后的页面视为同源，从而
  绕过上面依赖的预检。现在 `ALLOWED_HOSTS` 只在 `metrics/settings/defaults.py` 定义一次，默认值改为
  `127.0.0.1`、`localhost`、`[::1]`；删除 production 和 development 中的通配符覆盖。现有启动脚本和 AI Base 都通过
  `127.0.0.1` 访问；以其他主机名提供服务的部署需要显式设置 `ALLOWED_HOSTS`，README 已写明。
- 残余风险，不在本 change 中处理：同机进程仍然可以直接调用 connector 路由，并在请求体里自报 actor（F11）。
  按已确认的单进程嵌入方向，`embed-ai-base-runtime-in-process`（MDB-2）会删除这些 connector 路由，问题随之消失。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `dashboard-ai-sidecar-integration`：修改 "Sidecar handshake is identity-checked"，去掉 `instanceToken`，并写明
  握手只用于发现配置错误。
- `ai-base-connector-boundary-policy`：新增 "Dashboard connector write routes accept only JSON bodies" 和
  "Dashboard accepts only loopback hosts unless configured"。

## Impact

- 代码：
  - `bug_metrics/app/api/ai_sidecar.py`；
  - 新增 `ui_web/views/ai_dashboard_connector_endpoint.py`；
  - `ui_web/views/ai_dashboard_view.py`、`ui_web/views/ai_dashboard_publish_view.py`；
  - `metrics/settings/defaults.py`、`metrics/settings/production.py`、`metrics/settings/development.py`；
  - `README.md` 的安全配置说明。
- 测试：`bug_metrics/tests/test_api_ai_sidecar.py`、`ui_web/tests/test_ai_dashboard_api_surface.py`、
  `ui_web/tests/test_ai_dashboard_publish_authority.py`、`metrics/tests/test_defaults_metrics.py`。
- 调用方：AI Base 的 connector transport 和 `scripts/e2e_dashboard_ai_stack.ps1` 都已经发送 `application/json`，
  并通过 `127.0.0.1` 访问，无需修改；Dashboard 页面中没有 JS 调用这些路由。
- 设置项：`ALLOWED_HOSTS` 的默认值从 `['*']` 收紧为回环地址，这是有意的行为变化。不涉及数据迁移或依赖变化。

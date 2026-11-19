# ai-base-connector-boundary-policy Specification

## Purpose
Keep AI Base access to Metrics Dashboard connector operations inside the active Metrics workspace and its safety policy: model-visible tools stay bound to the bound workspace context, every operation declares its sensitivity so publish or mutation operations never become model-visible, connector transport verifies the local Dashboard sidecar identity before sending context, loopback calls never travel through environment proxies, connector write routes accept only JSON bodies, and Dashboard accepts only loopback Host headers unless `ALLOWED_HOSTS` is configured.

## Requirements

### Requirement: Connector model-visible tools are workspace-bound
AI Base SHALL enforce the active app workspace boundary before invoking model-visible connector operations.

#### Scenario: Model supplies a matching profile
- **WHEN** a chat session is bound to a Metrics workspace context
- **AND** the model calls a Metrics connector operation with profile/provider/workspace arguments matching the active workspace boundary
- **THEN** AI Base MAY invoke the connector operation

#### Scenario: Model supplies a different profile
- **WHEN** a chat session is bound to one Metrics workspace context
- **AND** the model calls a connector operation with a different provider id, profile id, workspace key or project scope
- **THEN** AI Base SHALL block the operation before sending an HTTP request to Dashboard

#### Scenario: Chat session has no Metrics workspace binding
- **WHEN** the model calls a Metrics connector operation that requires provider/project context
- **THEN** AI Base SHALL block the operation and instruct the user to sync/select a Metrics workspace context first

### Requirement: Connector operations declare sensitivity
AI Base SHALL require connector operation policy metadata before exposing operations as runtime tools.

#### Scenario: Operation can mutate or publish
- **WHEN** a connector operation can publish, mutate, callback, approve or import external resources
- **THEN** it SHALL NOT be model-visible
- **THEN** it SHALL require explicit governed workflow execution and approval policy

#### Scenario: Model-visible operation lacks safe policy
- **WHEN** a connector operation is marked model-visible without declaring read/validate-only sensitivity
- **THEN** AI Base SHALL fail closed and not expose it as a runtime tool

### Requirement: Connector transport verifies local sidecar identity
AI Base SHALL verify configured Dashboard connector identity before sending app context, user prompts, artifact refs or mutation requests.

#### Scenario: Expected Dashboard service responds
- **WHEN** AI Base initializes or first invokes the Dashboard connector
- **THEN** it SHALL verify the expected service id, profile/capability summary and optional instance token before enabling connector calls

#### Scenario: Wrong service responds on the port
- **WHEN** the configured base URL responds but identity does not match the Dashboard connector contract
- **THEN** AI Base SHALL block the connector call

### Requirement: Loopback connector calls bypass environment proxies
AI Base SHALL avoid leaking local connector payloads through environment HTTP proxies.

#### Scenario: Connector base URL is loopback
- **WHEN** connector base URL uses `127.0.0.1`, `localhost` or `[::1]`
- **THEN** AI Base SHALL create HTTP clients with environment proxy trust disabled

### Requirement: Dashboard connector write routes accept only JSON bodies
对 `/api/ai-dashboard/` 下所有 CSRF 豁免的 connector 路由，Dashboard SHALL 拒绝 `Content-Type` 不是 `application/json` 的带请求体请求，并在路由读取请求体或改变任何状态之前返回 HTTP 415。这样，浏览器发出的跨站请求必须先经过 CORS 预检，而 Dashboard 不返回任何 CORS 放行头。

#### Scenario: Cross-site simple request reaches a connector write route
- **WHEN** 发往 connector 写路由的请求使用 `text/plain`、`application/x-www-form-urlencoded` 或 `multipart/form-data`
- **THEN** Dashboard SHALL 返回 HTTP 415
- **AND** Dashboard SHALL NOT 为该请求创建、决策、校验或发布任何内容

#### Scenario: AI Base sends a JSON connector request
- **WHEN** AI Base 以 `Content-Type: application/json` 发送 connector 写请求
- **THEN** Dashboard SHALL 按该路由现有的契约处理请求

### Requirement: Dashboard accepts only loopback hosts unless configured
未显式配置 `ALLOWED_HOSTS` 时，Dashboard SHALL 只接受 Host 为 `127.0.0.1`、`localhost` 或 `[::1]` 的请求，对其他 Host 在进入任何视图之前返回 HTTP 400。否则，DNS rebinding 之后的页面会被浏览器视为同源，可以绕过上一条 requirement 所依赖的 CORS 预检。以其他主机名提供服务的部署 SHALL 通过 `ALLOWED_HOSTS` 环境变量显式列出这些主机名；settings 中 SHALL NOT 使用通配符作为默认值。

#### Scenario: DNS-rebound page calls the dashboard
- **WHEN** 未配置 `ALLOWED_HOSTS`，请求的 Host 是 `rebind.attacker.example`
- **THEN** Dashboard SHALL 返回 HTTP 400，且不执行任何视图

#### Scenario: Local launcher or AI Base calls the dashboard
- **WHEN** 未配置 `ALLOWED_HOSTS`，请求的 Host 是 `127.0.0.1`、`localhost` 或 `[::1]`，可以带端口
- **THEN** Dashboard SHALL 正常处理请求

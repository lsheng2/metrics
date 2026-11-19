# Spec Delta

## ADDED Requirements

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

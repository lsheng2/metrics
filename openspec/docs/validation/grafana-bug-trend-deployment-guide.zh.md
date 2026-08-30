# Grafana Bug Trend Dashboard 部署手册

日期：2026-08-20

## 目标

本文说明如何部署 Metrics Bug Trend dashboard 的 Grafana C-stock runtime。Grafana 只负责渲染 dashboard；Bug Trend 的 Jira scope 语义、计算结果、evidence rows、API allowlist 和验证 gate 仍由 Metrics 拥有。

## 部署形态

| 场景 | 推荐方式 | 说明 |
| --- | --- | --- |
| 本机验证 | Windows PC 本地 Grafana，端口 `3001` | 最快验证 dashboard artifact、datasource plugin 和 Metrics API。 |
| 团队共享 | Linux server、Windows server 或容器化 Grafana | 适合长期运行、统一权限、TLS、备份和运维。 |

## 前置条件

1. Metrics backend 已运行，例如：

```powershell
.venv\Scripts\python.exe manage.py runserver 8002
```

本仓库 demo 也可以使用 VS Code task `Backend: Start Django`。

2. Metrics API 可以访问：

```powershell
curl.exe --noproxy 127.0.0.1 "http://127.0.0.1:8002/api/charts/data/?scope_id=3&begin=2026-06-01&end=2026-08-09&chart_id=default_bug_trend"
```

3. Grafana OSS 已安装。本机验证使用 Grafana `13.2.0` 已通过。

4. 需要安装 Grafana Infinity datasource plugin：`yesoreyeram-infinity-datasource`。本机验证使用 plugin `4.0.0` 已通过。

## Windows 本机验证部署

### 1. 确认 Grafana 安装

```powershell
Get-Service *grafana* -ErrorAction SilentlyContinue | Select-Object Name,DisplayName,Status,StartType
Get-ChildItem "C:\Program Files\GrafanaLabs\grafana\bin" -Filter "grafana*.exe"
```

如果 Grafana service 使用默认端口 `3000`，但该端口已被其他本地 Web UI 占用，可以不要修改系统 service，改用 repo-local Grafana validation instance 跑在 `3001`。

### 2. 安装 Infinity datasource plugin

```powershell
New-Item -ItemType Directory -Force state\grafana\data\plugins
& "C:\Program Files\GrafanaLabs\grafana\bin\grafana.exe" cli `
  --homepath "C:\Program Files\GrafanaLabs\grafana" `
  --pluginsDir "state\grafana\data\plugins" `
  plugins install yesoreyeram-infinity-datasource
```

如果网络受限，可以先离线下载 plugin zip，再用 Grafana CLI 的 `--pluginUrl` 参数安装。

### 3. 创建本地 Grafana 配置

本仓库使用 `state/grafana/grafana.ini` 作为本机验证配置。关键配置如下：

```ini
[server]
http_addr = 127.0.0.1
http_port = 3001
root_url = http://127.0.0.1:3001/

[paths]
data = C:/Users/<user>/.../scrum_dashboard/state/grafana/data
logs = C:/Users/<user>/.../scrum_dashboard/state/grafana/logs
plugins = C:/Users/<user>/.../scrum_dashboard/state/grafana/data/plugins
provisioning = C:/Users/<user>/.../scrum_dashboard/state/grafana/conf/provisioning

[security]
admin_user = admin
admin_password = admin
allow_embedding = true

[auth.anonymous]
enabled = true
org_role = Admin
```

本机验证账号是 `admin` / `admin`。当前配置同时启用了 anonymous Admin，所以浏览器通常不需要登录即可访问 dashboard；如果 Grafana 显示登录页，使用上述账号即可。

注意：`state/grafana/grafana.ini` 中的 `paths` 建议使用绝对路径。Grafana 会以 `--homepath` 为基准解析相对路径，容易误写到 `C:\Program Files\GrafanaLabs\grafana\state\...`。

### 4. 配置 datasource provisioning

创建：

```text
state/grafana/conf/provisioning/datasources/metrics-bug-trend-api.yml
```

内容示例：

```yaml
apiVersion: 1

datasources:
  - name: Metrics Bug Trend API
    uid: metrics-bug-trend-api
    type: yesoreyeram-infinity-datasource
    access: proxy
    url: http://127.0.0.1:8002
    isDefault: false
    jsonData:
      allowedHosts:
        - http://127.0.0.1:8002
      auth_method: none
      global_queries: []
      timeoutInSeconds: 60
    editable: true
```

`uid` 必须是 `metrics-bug-trend-api`，因为 dashboard artifact 和 allowlist 都引用这个 datasource UID。

### 5. 启动 repo-local Grafana

```powershell
& "C:\Program Files\GrafanaLabs\grafana\bin\grafana.exe" server `
  --homepath "C:\Program Files\GrafanaLabs\grafana" `
  --config "state\grafana\grafana.ini"
```

验证健康状态：

```powershell
curl.exe --noproxy 127.0.0.1 "http://127.0.0.1:3001/api/health"
```

期望包含：

```json
{"database":"ok","version":"13.2.0"}
```

使用 VS Code task `E2E: Start Bug Trend` 或 `E2E: Restart Bug Trend` 时，脚本会优先选择 `3001`，如果端口被占用则尝试 `3011`、`3021`、`3031`、`3051`。实际端口和 dashboard URL 会写入：

```text
state/e2e/bug_trend_ports.json
```

示例：

```json
{
  "dashboard_url": "http://127.0.0.1:3001/d/metrics-bug-trend-c-stock/metrics-bug-trend-c-stock-spike?orgId=1&var-scope_id=3&var-begin=2026-06-01&var-end=2026-08-09",
  "django_port": 8002,
  "grafana_port": 3001
}
```

用户入口以 `dashboard_url` 为准。手动打开根页面时使用 `http://127.0.0.1:<grafana_port>/`。

### 6. 验证 datasource 和 plugin

```powershell
curl.exe --noproxy 127.0.0.1 -u admin:admin "http://127.0.0.1:3001/api/datasources/uid/metrics-bug-trend-api"
curl.exe --noproxy 127.0.0.1 -u admin:admin "http://127.0.0.1:3001/api/plugins/yesoreyeram-infinity-datasource/settings"
```

### 7. 导入 dashboard artifact

先验证 artifact 没有绕过 Metrics-owned data surface：

```powershell
.venv\Scripts\python.exe scripts\validate_grafana_artifacts.py --artifact-root ops\grafana --allowlist openspec/docs/current-baseline/grafana-approved-data-surfaces.json
```

导入 dashboard：

```powershell
$dashboard = Get-Content ops\grafana\bug_trend_dashboard.json -Raw | ConvertFrom-Json
$dashboard.templating.list | ForEach-Object {
  if ($_.name -eq 'scope_id') { $_.query = '3'; $_.current.text = '3'; $_.current.value = '3' }
  if ($_.name -eq 'begin') { $_.query = '2026-06-01'; $_.current.text = '2026-06-01'; $_.current.value = '2026-06-01' }
  if ($_.name -eq 'end') { $_.query = '2026-08-09'; $_.current.text = '2026-08-09'; $_.current.value = '2026-08-09' }
}
$payload = @{ dashboard = $dashboard; overwrite = $true; message = 'Import Metrics Bug Trend C-stock dashboard' } | ConvertTo-Json -Depth 100
curl.exe --noproxy 127.0.0.1 -u admin:admin -H "Content-Type: application/json" -X POST "http://127.0.0.1:3001/api/dashboards/db" -d $payload
```

打开：

```text
http://127.0.0.1:3001/d/metrics-bug-trend-c-stock/metrics-bug-trend-c-stock-spike?orgId=1&var-scope_id=3&var-begin=2026-06-01&var-end=2026-08-09
```

通过标准：页面显示 `Bug Trend` panel，不显示 `No data`，并且 panel 有非空 canvas 或 legend。

## 运行验证 gates

```powershell
.venv\Scripts\python.exe scripts\validate_grafana_artifacts.py --artifact-root ops\grafana --allowlist openspec/docs/current-baseline/grafana-approved-data-surfaces.json
.venv\Scripts\python.exe scripts\compare_grafana_bug_trend_parity.py --calculation-run-id <calculation_run_id>
.venv\Scripts\python.exe scripts\check_c0_validation_evidence.py --evidence docs\c0-validation-closure-evidence.md
.venv\Scripts\python.exe manage.py check
```

## 团队/服务器部署建议

1. 使用 Linux server、Windows server 或容器运行 Grafana。
2. Grafana 和 Metrics backend 之间使用稳定 URL，不要依赖开发机 `127.0.0.1`。
3. 为 Grafana 配置 TLS、登录认证和团队权限。
4. 使用 provisioning 管理 datasource 和 dashboard，不手工修改生产 dashboard 的业务 query。
5. 保持 datasource UID 为 `metrics-bug-trend-api`。
6. 所有 dashboard JSON 必须先通过 `scripts/validate_grafana_artifacts.py`。
7. Grafana 不拥有 bug/fixed/critical/high 语义；这些定义仍来自 Metrics scope config、calculation run 和 evidence API。

## 常见问题

### 端口 3000 已被占用

本机验证使用 `3001`。不要为了验证强行覆盖已有 `3000` 服务。

### Dashboard 显示 No data

检查：

1. Metrics backend 是否运行在 `8002`。
2. datasource `metrics-bug-trend-api` 是否存在。
3. Infinity plugin 是否已安装。
4. dashboard target 是否包含 `url_options: {"method": "GET"}`。
5. Grafana datasource proxy 是否能访问 Metrics API：

```powershell
curl.exe --noproxy 127.0.0.1 -u admin:admin "http://127.0.0.1:3001/api/datasources/proxy/uid/metrics-bug-trend-api/api/charts/data/?scope_id=3&begin=2026-06-01&end=2026-08-09&chart_id=default_bug_trend"
```

### 浏览器里看到 Sign in

本机验证可以使用 `admin/admin` 登录。团队部署必须改掉默认密码，并使用公司认可的认证方式。

## 当前已验证版本

| Component | Version / State |
| --- | --- |
| Grafana | `13.2.0` |
| Infinity datasource plugin | `4.0.0` |
| Grafana local port | `3001` |
| Metrics backend | `http://127.0.0.1:8002` |
| Dashboard UID | `metrics-bug-trend-c-stock` |
| Datasource UID | `metrics-bug-trend-api` |

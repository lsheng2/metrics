# Dashboard AI E2E Runbook

## 目的

本 runbook 用于人工验证 Dashboard 与 AI Base 的真实联调链路：

1. Dashboard Django + Grafana 启动。
2. Jira profile `chiplet-2a-jira` 可选 live sync。
3. AI Base `dashboard_query_agent` 启动并连接 Dashboard。
4. Dashboard `workflow.run` 返回 Metrics validation、render validation、gcx precondition。
5. AI Base connector 暴露 `workflow.run`，并保持 dry-run proof / human approval 语义。

## 启动

完整重启，包含 Jira live sync：

```powershell
cd "C:\Users\lsheng2\OneDrive - Intel Corporation\Documents\my_project\scrum_dashboard"
powershell -ExecutionPolicy Bypass -File scripts\e2e_restart_dashboard_ai_stack.ps1 -ForceByPort
```

快速重启，不重新拉 Jira：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\e2e_restart_dashboard_ai_stack.ps1 -ForceByPort -SkipJiraSync
```

只启动：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\e2e_start_dashboard_ai_stack.ps1
```

停止：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\e2e_stop_dashboard_ai_stack.ps1 -ForceByPort
```

## 打开页面

- Dashboard AI Workflow: `http://127.0.0.1:8002/ai-dashboard/workflow/`
- AI Base Dashboard Agent: `http://127.0.0.1:48310/`
- AI Base backend: `http://127.0.0.1:48300/`

Grafana 端口由 Dashboard 启动输出给出，通常是 `3001`，端口占用时会自动选择其他端口。

## Dashboard Workflow 检查

### Jira supported case

在 Dashboard AI Workflow 页面选择：

- Profile: `chiplet-2a-jira`
- Chart: `open_bug_trend`
- Requested Series: `new_critical_high`
- Range Mode: `WW`
- Range Start: `26WW32`
- Range End: `26WW35`
- gcx Operation: `grafana_import`

点击 `Run Metrics Validation`。

预期：

- Provider: `jira`
- Intent Validation: `draft_validated`
- Render Preview: `draft_validated`
- gcx Precondition: `precondition_passed`
- Guidance Status: `ready_for_dry_run`
- Next Action: `gcx_dry_run`

### HSD-ES supported case

选择：

- Profile: `nvu-ttl-hsdes`
- Chart: `open_bug_trend`
- Requested Series: `new_critical_high`

预期：

- Intent Validation: `draft_validated`
- Render Preview: `draft_validated`
- gcx Precondition: `precondition_passed`

### Unsupported semantic case

把 Requested Series 改为：

```text
new_critical
```

预期：

- Intent Validation: `needs_metric_recipe`
- Render Preview: `not_checked`
- gcx Precondition: `not_checked`
- 系统不应把 `new_critical` 静默替换成 `new_critical_high`

## AI Base 检查

打开 `http://127.0.0.1:48310/`，进入 Dashboard Query Agent 页面。

预期 Metrics Connector 显示：

- Connector ID: `metrics-dashboard`
- Model Visible Operations 包含 `workflow.run`
- Workflow Operation: `workflow.run`
- Dry-run Proof: `workflow.run can record dry-run proof`
- Approval Gate: `Human approval required before mutation`

也可以直接检查 backend diagnostics：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:48300/api/runtime/diagnostics/summary" |
    Select-Object -ExpandProperty security |
    ConvertTo-Json -Depth 8
```

预期 connector:

- `available=true`
- `activated=true`
- `executable=true`
- `modelVisibleOperations` 包含 `workflow.run`

## 当前安全边界

- `workflow.run` 可以进入 `ready_for_dry_run`。
- AI Base try-run 可以返回 dry-run proof summary。
- 真实 Grafana import/publish 仍需要 human approval。
- 没有 approval id 时，不应执行真实 mutation。
- Unsupported metric series 必须返回 `needs_metric_recipe`，不能由 AI 自行改写语义。

## 常见问题

### `base_url_missing`

AI Base 没有拿到 Dashboard URL。使用本 runbook 的启动脚本，它会设置：

```text
RCA_DASHBOARD_METRICS_BASE_URL=http://127.0.0.1:8002
DASHBOARD_METRICS_BASE_URL=http://127.0.0.1:8002
```

### Grafana 不是 3001

如果 3001 被占用，脚本会自动选择其他端口。以启动输出为准。

### Jira sync 慢或证书告警

`-SkipJiraSync` 可以跳过 live Jira sync，用现有本地数据做快速 E2E。

证书 warning 不代表本次 sync 必然失败；以命令最终 JSON 的 `status` 为准。

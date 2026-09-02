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
- Model Visible Operations 只包含 read/validate 类操作，例如 `catalog.lookup`、`intent.validate`、`render_config.validate`、`context.lookup`
- Internal Workflow Operation: `workflow.run` 不应 model-visible，只能由受控 workflow/helper 调用
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
- `modelVisibleOperations` 不包含 `workflow.run`、`artifact.validate`、`workflow.publish_demo` 或 callback/mutation 操作

## AI Base Chat Demo

打开 `http://127.0.0.1:48310/`，进入 `Chat` 页面，新建一个 chat session。

输入：

```text
Create a weekly open bug trend chart for chiplet Jira from 26WW32 to 26WW35, only new critical/high.
```

预期 Chat 回复包含：

- `Dashboard chart workflow completed.`
- `Profile: chiplet-2a-jira`
- `Provider: jira`
- `Chart: open_bug_trend`
- `Series: new_critical_high`
- `Intent validation: draft_validated`
- `Render validation: draft_validated`
- `gcx precondition: precondition_passed`
- `Dry-run proof: dryrun_...`
- `Approval: human approval required before Grafana mutation`

这个 demo 是 **受控 chart authoring dry-run**。它证明 AI Base Chat 已经能通过 Dashboard `workflow.run` 走完整验证和 dry-run proof handoff。

## AI Base Chat Publish Authority Check

在同一个 Chat session 继续输入：

```text
Approve and publish a weekly open bug trend chart for NVU HSDES from 26WW32 to 26WW35, only new critical/high.
```

预期 Chat 回复包含：

- `human approval required`
- `dry-run proof`
- 不应声称已经 publish
- 不应返回 `approval_chat_demo_...` 作为可执行 approval
- 不应直接触发 Grafana import

真实 publish 必须走 Dashboard-owned publish authorization：先创建 pending approval，人工 approve 后，publish request 的 provider、workspace key、profile、range、series、artifact ref/version/hash、dry-run proof、operation 和 actor 必须与 approval 记录完全匹配，并且 approval 必须在有效期内。

当 publish authorization 通过时，预期返回：

- `Dashboard chart published to Grafana.`
- `Dashboard: ai-open-bug-trend-demo`
- `URL: http://127.0.0.1:3001/d/ai-open-bug-trend-demo/...`
- `Dry-run proof: dryrun_...`
- `Approval: approval_...`
- `Audit: recorded`

打开回复里的 URL。预期 Grafana 页面能看到 AI 生成的 `Open Bug Trend` chart。Dashboard 会重新执行 Metrics validation、render validation、gcx precondition，然后只导入 Metrics 生成的 Grafana JSON，并记录 publication callback audit。

如果要用 Jira `chiplet-2a-jira` 做同一个 publish demo，需要先运行不带 `-SkipJiraSync` 的完整重启或手动 sync，确保 `26WW32` 到 `26WW35` 有 completed aggregate artifact；否则 Grafana dashboard 会被创建，但 panel 会显示 `No data`。

## 当前安全边界

- `workflow.run` 可以进入 `ready_for_dry_run`。
- AI Base try-run 可以返回 dry-run proof summary。
- 真实 Grafana import/publish 需要 human-approved Dashboard publish authorization；Chat 文本不能自造 approval id。
- 没有 approval id 时，不应执行真实 mutation。
- approval id、dry-run proof id、artifact ref/version/hash、provider/workspace/profile/range/series/operation/actor 必须匹配同一个未过期 authorization tuple。
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

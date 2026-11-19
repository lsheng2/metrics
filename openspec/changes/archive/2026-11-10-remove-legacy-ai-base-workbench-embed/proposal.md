# Proposal

## Why

Workbench AI pane 同时保留了两套 AI Base 嵌入协议：旧的 `embed=workbench`（URL 携带
`source=metrics-workbench`、`workspace_key`、`agent_id`，没有 Dashboard 侧 binding
preflight）和当前的 `embed=app-chat`（app identity + binding key + workspace key + agent key，
instance token 只在服务端 binding 请求中）。旧模式只靠 `METRICS_AI_BASE_EMBED_MODE`
开关存活，默认值早已是 `app-chat`；双轨让 baseline spec 继续描述旧参数，测试也在维护无人使用的
路径。项目处于早期阶段，只为当前契约设计，因此直接删除旧模式。

## What Changes

- **BREAKING** 删除 `embed=workbench` 嵌入模式：AI pane iframe 只生成
  `<frontend>/?embed=app-chat#/chat?...` URL。
- **BREAKING** 删除 `METRICS_AI_BASE_EMBED_MODE` 配置项；unified stack launcher
  不再设置该变量。残留的同名环境变量会被忽略。
- 删除 AI pane payload 中只服务旧 URL 的 `agent_id` 字段。
- baseline spec 的 AI Base 嵌入 scenario 改为描述 app-chat binding 契约。
- 测试只断言 app-chat URL；"未绑定 scope 不泄漏 stale workspace" 的否定断言改为检查
  workspace key 本身，不再依赖旧 URL 参数名。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `unified-metrics-workbench-ui`: requirement "Workbench supports one-window local runtime"
  中两个 AI Base 嵌入 scenario 从 legacy compact embed 参数改为 app-chat binding 契约。

## Impact

- 代码：`ui_web/ai_base_workbench_adapter.py`、`metrics/settings/defaults_metrics.py`、
  `scripts/e2e_dashboard_ai_stack.ps1`。
- 测试：`ui_web/tests/test_ai_base_workbench_adapter.py`、
  `ui_web/tests/test_workbench_ai_host_actions.py`、
  `ui_web/tests/test_workbench_scope_profile_sync.py`、
  `scripts/tests/test_e2e_dashboard_ai_stack_launcher.py`。
- 配置文档：`METRICS_AI_BASE_EMBED_MODE` 从未出现在 `.env.example` 或配置文档中，无需同步。
- 外部系统：AI Base 前端本身支持 `app-chat`，本变更不需要修改 AI Base。
- 不在范围内：`bug_metrics/app/api/ai_sidecar.py` 与 `ui_web/ai_base_workbench_adapter.py`
  的 urllib 直连保持不变；它们由 `embed-ai-base-runtime-in-process`（进程内嵌入 AI Base 运行时）整体删除。

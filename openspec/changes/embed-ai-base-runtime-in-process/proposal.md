# Proposal: embed-ai-base-runtime-in-process（MDB-2）

## Why

Metrics 与 AI Base 一对一部署，运行在同一台机器、同一个 OS 用户下，却通过两个进程和三条 HTTP 通道集成：
AI Base 以 connector 回调 Metrics 的 14 个 `/api/ai-dashboard/*` 路由；Metrics 用 HTTP SDK 向 AI Base 提交
task run；workbench 把 Metrics 上下文推送到 AI Base workspace。这种结构带来以下问题：

- 安全面大：CSRF 豁免的写路由、instance token 与 credential ref、跨源 iframe 与 postMessage，以及 DNS
  rebinding。MDB-0（`harden-ai-base-sidecar-and-connector-inputs`）只是止血。
- 证明不可靠：gcx 的 `dry_run_proof_id` 由调用方提交，执行方没有任何证明；workspace 同步复制了一份状态，容易过期。
- 生产路径不可用：生产 settings 没有 project runtime factory，AI 摘要和报告辅助在生产路径上只能返回
  `RUN_UNAVAILABLE`；`metrics/asgi.py` 和 `metrics/wsgi.py` 的默认 settings 指向空的 `metrics.settings` 包。
- 难以演进：Metrics 专属代码（connector、dashboard 服务、聊天快捷方式）散落在 AI Base 核心，两边都无法单独演进。

v2 上游建议（[upstream-ai-base-runtime-proposal.md](upstream-ai-base-runtime-proposal.md)）确定的终态是：
AI Base 以可嵌入运行时 `ai-base-runtime` 的形式进入 Metrics 进程，不建过渡层。本 change 是其中属于 Metrics 的 MDB-2。

## What Changes

- **BREAKING** `metrics.asgi` 成为唯一的组合根。一个 uvicorn 进程同时托管 Django 和挂载在 `<URL 前缀>/ai`
  的运行时；组合根的 lifespan 负责进入运行时的运行期，并安装 project run 运行时。新增 `manage.py serve`，
  取代 `project_serve` 和 gunicorn：默认绑定回环地址，容器以 `--host 0.0.0.0` 运行，development settings 下拒绝
  非回环绑定。删除 `metrics/wsgi.py` 与 `WSGI_APPLICATION`，Docker 镜像改为单进程、单副本。
- 新增 `ai_host` 模块，它是 Metrics 中唯一导入 `ai_base_runtime` 的地方，负责：组合根装配；宿主 SPI（认证、
  审批授权、审计、`HostConfig`）；Metrics App 包；task-run 端口的实现；AI pane 的状态。
- 新增 Metrics App 包（`app_id=metrics`），包含：
  - agents；
  - `read` tools：`metrics.catalog`、`metrics.chart_workflow`；
  - `external` tool：`metrics.publish_chart`，必须经过审批；
  - context provider：按 `ContextRef` 拉取上下文；
  - host actions：只做 UI 动作。
- **BREAKING** 发布改为由运行时审批 `publish_chart` 调用：
  - Metrics 的 `preview()` 生成将要导入的确切 dashboard JSON 及其内容摘要，审批绑定这个摘要；
  - 执行前重新生成并比较摘要，不一致就不导入；
  - 以 `tool_call_id` 作为幂等键；
  - chart 草稿只存在于对话的 tool 调用中，不另建 artifact 存储；发布结果写入 Metrics 自有的新表
    `AiChartPublication`（`tool_call_id` 唯一，`supersedes` 唯一），`/api/ai-publish-history/` 只读这张表。
- **BREAKING** 删除 gcx，包括 gcx 操作词表、precondition、publication callback 和 `dry_run_proof_id`。
- **BREAKING** 删除 Metrics 与 AI Base 之间的全部 HTTP 集成：
  - 14 个 connector 路由，以及 `connector_endpoint`；
  - sidecar 握手和探活；
  - `ai_base_workbench_adapter.py`；
  - workspace 同步（表单、视图、JS）；
  - `AiGrafanaPublishApprovalService`；
  - `TaskRunClient`、`AiBackendTarget`、`execution_mode`，以及 `run_factories`、`report_factories` 中的工厂；
  - 设置项 `METRICS_AI_SIDECAR_ENABLED`、`METRICS_AI_BASE_*`、`METRICS_PROJECT_AI_*`、`METRICS_PROJECT_RUNTIME_FACTORY`、
    `METRICS_REPORT_ASSIST_FACTORY`；
  - `requirements-ai-task.txt`；
  - launcher 中对 AI Base 进程的管理。
- **BREAKING** project_management 的摘要分析、报告辅助和 project run worker 改为调用 Metrics 自有的同步
  task-run 端口，并删除 AI 路径上的全部 `asyncio.run`。档案改由 Metrics 自有的 `ai_profiles/` 以数据维护
  （`metrics.project_summary`、`metrics.report_authoring`），取代 vendored 的 `ai_bundle/`；准入记录只认一个
  schema 版本，旧格式一律 `RUN_STORAGE_INVALID`，不做兼容读取。
- 运行时状态固定存放在 `METRICS_STATE_DIR/ai-base`，只允许一个写入进程；服务运行期间，CLI 会得到 `RUN_BUSY`。
- AI pane 改为同源 iframe，并加载运行时提供的 `embed-host.js`。scope 变化时只传递 `ContextRef`。
- `ALLOWED_HOSTS` 成为 Django 和运行时共用的唯一 Host 白名单。
- 运行时的会话、tool 和审批事件写入 `ai_host` 自有的只追加审计表；认证失败只输出结构化日志 `ai_auth_failed`。
- `/ai-dashboard/workflow/` 页面保留，改为显示运行时状态、工作流结果和发布就绪状态，不再出现 gcx。

## Capabilities

### New Capabilities

- `embedded-ai-runtime-host`：规定 Metrics 进程如何托管 AI Base 运行时，包括组合根、宿主 SPI、App 包、同步
  task-run 端口、状态目录、单一 Host 白名单、宿主一致性套件和运行时版本准入。

### Modified Capabilities

- `dashboard-ai-sidecar-integration`：全部 requirement 标为 REMOVED，能力退役。
- `ai-base-connector-boundary-policy`：全部 requirement 标为 REMOVED（包括 MDB-0 新增的两条），能力退役。
- `provider-ai-dashboard-composition`：
  - AI 只能通过 App 包的 tool 访问 Metrics；
  - gcx precondition 改为发布就绪；
  - dry-run 交接改为 preview；
  - artifact 改为 tool 调用中的草稿加内容摘要，由 Metrics 在发布历史中保存被批准的内容；
  - AI pane 和适配层统一收敛到 `ai_host`。
- `ai-dashboard-publish-authority`：授权对象改为运行时审批加 preview 摘要，删除 dry-run proof。
- `ai-centric-metrics-workspace-composition`：上下文改由 context provider 按 `ContextRef` 拉取，不再同步到 workspace。
- `unified-metrics-workbench-ui`：本地运行改为单进程；AI pane 的诊断不再涉及 workspace 同步。
- `provider-facts-and-sync`：发布就绪在 `publish_chart` 请求审批之前判定。
- `grafana-render-config`：发布前置条件从 dry-run proof 改为已批准的 preview 摘要。

## Impact

- **前置条件（tasks 第 0 组）**：
  - owner 已于 2026-11-10 签署 Q1–Q9；
  - S0 共装 spike 的全部退出条件通过；
  - AIB-2 发布的 `ai-base-runtime` 提供 v2 D1–D11 中的 SPI，包括 owner 同日接受的五项补充：D4
    `AppPackage.task_profiles`、D5 `ToolContext.context_ref`、D6 preview 摘要绑定、D7 `open_session` 的
    `session_key`、D9 task-run 真实模型执行与准入错误码。
- **前置 change 已归档**：`isolate-dashboard-runtime-instances`、`remove-legacy-ai-base-workbench-embed` 和
  `harden-ai-base-sidecar-and-connector-inputs` 已于 2026-11-10 归档。本 change 的 delta 以归档后的主 spec 为基线，
  并通过 strict 校验。
- **与进行中 change 的冲突（2026-11-11 已由任务 0.4 消除）**：`add-provider-neutral-project-reporting` 中原以 HTTP SDK、
  App 注册和 connector 为前提的内容已改写为"运行时版本准入"和"进程内 task-run 端口"：
  - W4.REPLAN、W5.N1、W5.APP、W5.MIGRATE、W5.CLIENT、W5.CHAT 已改写；
  - `sdk-consumer-integration` delta 已删除，仍有效的规则并入该 change 的 `project-reporting` delta。
- **代码**：
  - `metrics/`：`asgi.py`、`middleware.py`、`settings/*`；删除 `wsgi.py`；
  - 新模块 `ai_host/`：组合根装配、宿主 SPI、App 包、task-run 端口实现、审计表、`serve` 命令；
  - `project_management`：删除 `ai_bundle/` 与 `project_serve`，新增 `ai_profiles/`；`out/ai_task_contract.py` 和
    `out/report_ai_task.py` 改写为同步端口；run_factories、report_factories、runtime、summary_analysis、
    report_assists、project_run_worker、project_run 与准入记录值对象；
  - `bug_metrics`：新表 `AiChartPublication`；`app/api/` 下的 ai_sidecar、ai_dashboard_approval、ai_context、
    ai_dashboard_composition、ai_dashboard_workflow；
  - `ui_web`：urls、views、adapter、service status、context processors、workbench 模板与 JS；
  - `ops/docker/Dockerfile`、`README.md`、`scripts/dashboard_runtime_instance_profile.py`；
  - `scripts/validation/project_*`、`scripts/e2e_dashboard_ai_stack.ps1`。
- **依赖**：
  - 新增精确版本的 `ai-base-runtime`、`uvicorn` 和 `starlette`；
  - 删除 `ai-base-application-sdk`、`requirements-ai-task.txt` 和 `gunicorn`；
  - `portalocker` 升级到 ≥4.4.2。
- **运行方式**：本地与 Docker 都改为 `manage.py serve`，即单进程、单 worker、不 reload；开发和生产使用同一个组合根。
  Docker 只允许单副本，`METRICS_STATE_DIR` 挂载为卷。按 owner 2026-11-10 的决定，非回环绑定不强制 Basic 认证，
  维持现有姿态。
- **状态**：切换时不迁移 `dashboard_query_agent` 独立壳的会话、审批和技能目录（Q8），并删除 archive 中的
  `runtime/operations/`。发布历史改由新表 `AiChartPublication` 记录，旧 `BugTrendAuditEvent` 发布行保留在表中但
  不再列出。数据库、`METRICS_STATE_DIR` 与 archive root 作为一个单元备份和回滚。

# Spec Delta

## Purpose

Embedded AI runtime host 规定 Metrics 进程如何托管 AI Base 运行时：一个 ASGI 组合根同时服务 Django 和运行时；
`ai_host` 模块实现宿主 SPI 和 Metrics App 包；领域服务通过同步端口调用 task run；运行时状态只有一个写入进程；
Django 与运行时共用一个 Host 白名单；宿主一致性套件和版本准入作为升级门禁。Metrics 与运行时之间不存在任何 HTTP 集成。

## ADDED Requirements

### Requirement: Metrics serves Django and the AI runtime from one composition root
`metrics.asgi` SHALL 是 Metrics 唯一的组合根：一个 ASGI 应用把 `<URL 前缀>/ai` 交给 AI Base 运行时，其余路径（包括静态文件）交给 Django。组合根的 lifespan SHALL 在接受第一个请求之前进入运行时的运行期并安装 project run 运行时，关闭时按相反顺序停止。受支持的启动方式 SHALL 只有 `manage.py serve`：只接受回环地址，单 worker，不 reload，Windows 上使用 Proactor 事件循环。

#### Scenario: Operator starts the server
- **WHEN** 操作者运行 `manage.py serve --host 127.0.0.1 --port <port>`
- **THEN** 运行时 SHALL 在第一个请求到达之前进入运行期
- **AND** `<URL 前缀>/ai/` 下的请求 SHALL 由运行时处理，其余请求 SHALL 由 Django 处理
- **AND** project run worker SHALL 已经安装并可以接收运行

#### Scenario: Operator requests a non-loopback bind
- **WHEN** 操作者以 `--host 0.0.0.0` 或其他非回环地址运行 `manage.py serve`
- **THEN** 命令 SHALL 在启动服务之前以错误退出

#### Scenario: URL prefix is configured
- **WHEN** `METRICS_BASE_URL` 是 `/metrics/`
- **THEN** 运行时 SHALL 挂载在 `/metrics/ai`
- **AND** 嵌入页路径和运行时资产地址 SHALL 带有同一个前缀

#### Scenario: Settings module is not set
- **WHEN** 进程启动时没有设置 `DJANGO_SETTINGS_MODULE`
- **THEN** `metrics.asgi` SHALL 使用 `metrics.settings.production`，与 `manage.py` 一致

#### Scenario: Runtime cannot start
- **WHEN** 运行时无法进入运行期，例如状态目录已被其他进程锁定或运行时配置无效
- **THEN** 服务 SHALL 以包含错误码的错误退出
- **AND** 服务 SHALL NOT 在没有运行时的情况下继续提供 Django 页面

#### Scenario: Server shuts down
- **WHEN** 组合根的 lifespan 进入关闭阶段
- **THEN** project run worker SHALL 先停止，运行时随后停止
- **AND** 未完成的运行 SHALL 被取消并标记为中断，状态目录锁 SHALL 被释放

### Requirement: AI runtime requests use the Metrics identity
运行时挂载下的每个请求 SHALL 由 Metrics 宿主的 `authenticate` 确定 principal。`authenticate` 与 Django 的 `BasicAuthMiddleware` 调用同一个纯函数 `check_basic_authorization`，同一请求在两边的认证结果 SHALL 一致。认证失败 SHALL 返回 401。未配置 Basic 用户时，principal SHALL 是匿名的本地操作者。运行时 SHALL NOT 从请求体、tool 参数或 iframe URL 中读取 actor。

#### Scenario: Request carries valid Basic credentials
- **WHEN** 请求携带有效的 Basic 凭据访问 Django 页面或运行时路由
- **THEN** 两边 SHALL 得到同一个 principal，其 id 为该用户名

#### Scenario: Request carries invalid credentials
- **WHEN** 已配置 Basic 用户，请求的凭据缺失或错误
- **THEN** Django 页面和运行时路由 SHALL 都返回 401

#### Scenario: Basic authentication is not configured
- **WHEN** 没有配置 Basic 用户
- **THEN** 运行时 SHALL 得到匿名的本地操作者 principal

### Requirement: Only authenticated humans decide AI approvals
`external` tool 调用 SHALL 先由运行时创建持久化审批，审批通过之前 SHALL NOT 执行。审批 SHALL 只能由通过认证、且 Metrics 宿主的 `can_decide` 返回真的 principal 决定。匿名 principal SHALL 只在 development settings 中被允许决定审批，这项允许 SHALL NOT 能通过环境变量打开。任何 tool、host action 或模型输出 SHALL NOT 产生审批决定。

#### Scenario: Anonymous operator tries to approve in production settings
- **WHEN** 使用 production settings 且未配置 Basic 用户，匿名本地操作者尝试批准一个发布审批
- **THEN** 运行时 SHALL 拒绝该决定，审批 SHALL 保持 pending

#### Scenario: Anonymous operator approves in development settings
- **WHEN** 使用 development settings，匿名本地操作者批准一个审批
- **THEN** 运行时 SHALL 接受该决定，并把本地操作者记录为 `decided_by`

#### Scenario: Model output claims approval
- **WHEN** 模型输出声称用户已经批准，或者请求某个 tool 代为批准
- **THEN** 审批 SHALL 保持 pending，因为不存在任何能产生审批决定的 tool

### Requirement: AI runtime state has a single writer
运行时状态 SHALL 存放在 `METRICS_STATE_DIR/ai-base`，这个路径不能单独配置。同一时间 SHALL 只有一个进程持有该目录的锁。服务进程持有锁时，需要运行时的 CLI（例如 `project_run --execute-local`）SHALL 立即以 `RUN_BUSY` 失败，不等待，也不改用其他目录。Metrics SHALL NOT 为多 worker 部署设计共享状态。

#### Scenario: CLI runs while the server holds the lock
- **WHEN** 服务正在运行，操作者执行 `project_run --execute-local`
- **THEN** 命令 SHALL 立即以 `RUN_BUSY` 失败，并提示通过服务提交运行

#### Scenario: CLI runs while no server is running
- **WHEN** 没有服务进程，操作者执行 `project_run --execute-local`
- **THEN** 命令 SHALL 在自己的进程中启动运行时、获取锁、完成运行，并在退出时释放锁

### Requirement: Only the ai_host module imports the AI runtime
Metrics 中 SHALL 只有 `ai_host` 模块导入 `ai_base_runtime`；组合根 SHALL 通过 `ai_host` 构造运行时。任何 Metrics 代码 SHALL NOT 导入 `ai_base_runtime._internal` 或 AI Base 的 `app.*` 包。`ai_host` SHALL 负责嵌入资产地址、聊天会话、由 `WorkbenchPageQueryState` 构造 `ContextRef` 和 host action 声明；图表、证据、ticket 详情和 PageQueryState 模块 SHALL 在不导入运行时的情况下可用。其他模块 SHALL 通过 `ai_host` 的公共 API，或者通过自己定义、由组合根注入实现的端口使用 AI 能力。自动化导入规则测试 SHALL 强制这一点。

#### Scenario: A module outside ai_host imports the runtime
- **WHEN** `ai_host` 以外的任何 Metrics 模块导入 `ai_base_runtime`
- **THEN** 导入规则测试 SHALL 失败

#### Scenario: project_management needs an AI task run
- **WHEN** project_management 需要启动 AI task run
- **THEN** 它 SHALL 调用自己定义的 task-run 端口，而不是导入 `ai_host` 或运行时

#### Scenario: A change adds AI-assisted behavior
- **WHEN** 一个变更为 Dashboard 增加 AI 聊天、tool、审批、host action 或上下文行为
- **THEN** 该行为 SHALL 放在 `ai_host` 或 Metrics App 包中
- **AND** 测试 SHALL 覆盖受影响的用户工作流在 `ready` 状态和非 `ready` 状态下的行为

### Requirement: Domain services call AI task runs through a synchronous port
project_management 的摘要分析、报告辅助和 project run worker SHALL 通过 project_management 定义的同步 task-run 端口调用 AI；端口由 `ai_host` 基于运行时的 `blocking.task_runs` 实现，由组合根注入。Metrics SHALL NOT 用 `asyncio.run` 调用运行时协程，SHALL NOT 在运行时的事件循环线程上调用 blocking 门面，SHALL NOT 保留 HTTP task-run 客户端、凭据引用或 token 设置。

#### Scenario: Project run worker starts an AI run
- **WHEN** project run worker 线程处理一个需要 AI 的运行
- **THEN** 它 SHALL 通过 task-run 端口启动运行，principal SHALL 来自提交运行的用户
- **AND** 运行结果 SHALL 按 task-run/1 契约记录

#### Scenario: Runtime is not running
- **WHEN** 进程不是经组合根启动的（例如 Django 测试客户端），领域服务调用 task-run 端口
- **THEN** 端口 SHALL 返回结构化的 `RUN_UNAVAILABLE`，SHALL NOT 自行创建事件循环或运行时

### Requirement: Metrics App package declares the whole AI surface
Metrics SHALL 用一个 `AppPackage`（`app_id=metrics`）声明全部 AI 能力：agent、带类型和 effect 的 tool、按 `ContextRef` 解析上下文的 context provider，以及只做 UI 动作的 host action。tool handler SHALL 是 async 函数，通过 `sync_to_async` 在工作线程中调用 Metrics 公共 API，并在该线程中调用 `close_old_connections`。tool 参数 SHALL NOT 包含 actor、审批 id 或证明 id；操作者 SHALL 只取自 `ctx.principal` 或 `ctx.approval.decided_by`。

#### Scenario: Runtime starts with the Metrics package
- **WHEN** 组合根构造运行时
- **THEN** tool 注册表 SHALL 包含 `read` tool `metrics.catalog`、`metrics.chart_workflow` 和 `external` tool `metrics.publish_chart`
- **AND** 运行时 SHALL 拥有 context provider `metrics.workbench` 和 host action `metrics.openChart`、`metrics.openEvidence`

#### Scenario: Tool schema exposes authority fields
- **WHEN** 某个 Metrics tool 的参数模型包含 actor、approval id、proof id 或 workspace key 字段
- **THEN** App 包测试 SHALL 失败

#### Scenario: Embedded chat requests a host action
- **WHEN** iframe 请求执行 `metrics.openChart`
- **THEN** 宿主页面 SHALL 只在 workbench 中切换到该图表，SHALL NOT 改变任何服务端状态

### Requirement: Metrics and the AI runtime share no HTTP integration
Metrics 与运行时之间 SHALL NOT 存在 HTTP 调用、connector 回调路由、App 注册、instance token、credential ref 或 workspace 同步。`/api/ai-dashboard/` 前缀下的全部路由、sidecar 握手与探活，以及设置项 `METRICS_AI_SIDECAR_ENABLED`、`METRICS_AI_BASE_*`、`METRICS_PROJECT_AI_*`、`METRICS_PROJECT_RUNTIME_FACTORY` SHALL 不存在；workbench 使用的发布历史只读 API SHALL 改用 `/api/ai-publish-history/`。grep gate SHALL 阻止这些名称和 `ai_base_application_sdk` 的导入重新出现。

#### Scenario: A former connector route is requested
- **WHEN** 任何客户端请求 `/api/ai-dashboard/workflow/`、`/api/ai-dashboard/identity/` 或该前缀下的其他路径
- **THEN** Metrics SHALL 返回 404

#### Scenario: Workbench reads publish history
- **WHEN** workbench 的 Publish And Audit pane 加载发布历史
- **THEN** 它 SHALL 读取 `/api/ai-publish-history/`，响应字段 SHALL 符合 `grafana-render-config` 的 "AI-generated Grafana dashboards are listed and auditable"

#### Scenario: A change reintroduces an HTTP integration name
- **WHEN** 代码、settings 或脚本中出现上述设置名、connector 路由前缀或 `ai_base_application_sdk` 导入
- **THEN** grep gate SHALL 失败

### Requirement: AI pane reports runtime readiness without blocking the workbench
AI pane SHALL 根据进程内运行时显示三种状态之一：`ready`；`not_configured`，即未配置模型；`not_running`，即进程不是经组合根 lifespan 启动的。非 `ready` 状态 SHALL 说明原因和下一步操作，且 SHALL NOT 影响图表、证据、设置、发布历史和诊断页面。Metrics SHALL NOT 提供启用或禁用 AI 的开关，SHALL NOT 在渲染请求时启动任何进程。

#### Scenario: Model is not configured
- **WHEN** 运行时已进入运行期，但 Metrics settings 中没有模型配置
- **THEN** AI pane SHALL 显示 `not_configured`，并列出缺少的设置项名称，SHALL NOT 显示任何设置值

#### Scenario: Process was not started by the composition root
- **WHEN** 页面由没有经过组合根 lifespan 的进程渲染
- **THEN** AI pane SHALL 显示 `not_running`，并提示使用 `manage.py serve` 启动

#### Scenario: Runtime is ready
- **WHEN** 运行时已进入运行期且模型已配置
- **THEN** AI pane SHALL 渲染同源的嵌入聊天

### Requirement: One host allowlist protects Django and the AI runtime
`ALLOWED_HOSTS` SHALL 是 Django 和运行时共用的唯一 Host 白名单，经 `HostConfig.allowed_hosts` 传给运行时。未显式配置时，它 SHALL 只包含 `127.0.0.1`、`localhost` 和 `[::1]`，settings SHALL NOT 用通配符作为默认值。Host 不在白名单内的请求 SHALL 在进入任何 Django 视图或运行时路由之前得到 HTTP 400，否则 DNS rebinding 之后的页面会被浏览器当作同源。

#### Scenario: DNS-rebound page calls Metrics
- **WHEN** 未配置 `ALLOWED_HOSTS`，请求的 Host 是 `rebind.attacker.example`
- **THEN** Django 路径和 `<URL 前缀>/ai/` 下的路径 SHALL 都返回 HTTP 400，且不执行任何视图或运行时处理

#### Scenario: Loopback host carries a port
- **WHEN** 未配置 `ALLOWED_HOSTS`，请求的 Host 是 `127.0.0.1:8793`、`localhost:8793` 或 `[::1]:8793`
- **THEN** Django 和运行时 SHALL 都正常处理请求

#### Scenario: Deployment lists another host name
- **WHEN** `ALLOWED_HOSTS` 环境变量显式列出 `metrics.example.internal`
- **THEN** Django 和运行时 SHALL 都接受该 Host

### Requirement: Host conformance suite gates the composed runtime
Metrics 测试 SHALL 用运行时 testkit 的宿主一致性套件验证组合后的宿主，覆盖：Host 校验、请求完整性、资源归属、`frame-ancestors`、审批持久化、`os.environ` 与全局 tracer 不变、Proactor 事件循环、slow callback 阈值、`RuntimeBusy`。确定性的对话测试 SHALL 使用 testkit 的脚本化模型，SHALL NOT 依赖真实模型或聊天快捷方式。升级运行时版本 SHALL 以该套件通过为门禁。

#### Scenario: Runtime version is upgraded
- **WHEN** 一个变更修改了固定的 `ai-base-runtime` 版本
- **THEN** 宿主一致性套件和 Metrics 浏览器测试子集 SHALL 在合入之前通过

#### Scenario: Chat-driven publish flow is tested
- **WHEN** 测试覆盖从对话发起的图表工作流和发布
- **THEN** 测试 SHALL 用 testkit 的脚本化模型产生确定的 tool 调用，SHALL NOT 调用真实模型

### Requirement: AI runtime audit is written to Metrics
Metrics 宿主 SHALL 把运行时的会话、tool 调用、审批（请求、决定、消费、过期）和认证失败事件写入 Metrics 的 AI 审计存储，记录 principal、session id、run id、`tool_call_id`、tool 名称、审批 id 和结果状态。审计 SHALL NOT 包含模型凭据、provider token、Basic 密码或其他秘密。

#### Scenario: Publish approval completes its lifecycle
- **WHEN** 一次 `metrics.publish_chart` 调用经历请求审批、批准和执行
- **THEN** AI 审计存储 SHALL 按顺序记录审批请求、决定、消费和 tool 调用结果，每条都带有同一个 `tool_call_id`

#### Scenario: Authentication fails
- **WHEN** 运行时路由上的认证失败
- **THEN** AI 审计存储 SHALL 记录一次认证失败事件，SHALL NOT 记录提交的凭据

### Requirement: Runtime version is pinned and admitted explicitly
Metrics SHALL 在 `requirements.txt` 中固定 `ai-base-runtime` 的精确版本；准入时 SHALL 校验 wheel 摘要、`pip check` 无冲突、宿主一致性套件通过。Metrics SHALL NOT 依赖 Python HTTP SDK `ai-base-application-sdk`，SHALL NOT vendor 运行时的前端资产；嵌入脚本 SHALL 使用运行时 `ui.asset_url` 返回的带内容哈希的地址。

#### Scenario: A new runtime wheel is admitted
- **WHEN** 维护者把固定版本升级到新的 `ai-base-runtime` wheel
- **THEN** 准入检查 SHALL 校验 wheel 摘要与记录一致、`pip check` 无冲突、宿主一致性套件通过，任何一项失败都 SHALL 阻止合入

#### Scenario: Workbench loads the embed script
- **WHEN** workbench 渲染 AI pane
- **THEN** `embed-host.js` 的地址 SHALL 来自运行时的 `ui.asset_url`，Metrics 静态目录中 SHALL NOT 存在该脚本的副本

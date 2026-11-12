# Spec Delta

## Purpose

Embedded AI runtime host 规定 Metrics 进程如何托管 AI Base 运行时：`manage.py serve` 是唯一组合根，以线程化 WSGI
同时服务 Django 和运行时，运行时在同一进程的专用事件循环线程上运行；
`ai_host` 模块实现宿主 SPI 和 Metrics App 包；领域服务通过同步端口调用 task run；运行时状态只有一个写入进程；
Django 与运行时共用一个 Host 白名单；宿主一致性套件和版本准入作为升级门禁。Metrics 与运行时之间不存在任何 HTTP 集成。

## ADDED Requirements

### Requirement: Metrics serves Django and the AI runtime from one composition root
`manage.py serve` SHALL 是 Metrics 唯一的组合根和唯一受支持的启动方式，本地与容器部署相同：单进程，不 reload，默认绑定回环地址。它 SHALL 用一个线程化 WSGI 应用受理全部请求：路径等于挂载路径 `<URL 前缀>/ai` 或以挂载路径加 `/` 开头的请求交给运行时的 WSGI 适配器，其余路径（包括静态文件）交给 Django。Metrics SHALL NOT 保留 `metrics.wsgi`、`metrics.asgi` 或其他组合根，SHALL NOT 用 ASGI server 托管 Django。

#### Scenario: Operator starts the server
- **WHEN** 操作者运行 `manage.py serve --host 127.0.0.1 --port <port>`
- **THEN** 运行时 SHALL 在第一个请求到达之前进入运行期
- **AND** `<URL 前缀>/ai/` 下的请求 SHALL 由运行时处理，其余请求 SHALL 由 Django 处理
- **AND** project run worker SHALL 已经安装并可以接收运行

#### Scenario: Container image starts Metrics
- **WHEN** 使用 production settings 的容器镜像启动
- **THEN** 镜像 SHALL 以 `manage.py serve --host 0.0.0.0 --port 8000` 运行单个进程
- **AND** 镜像 SHALL NOT 包含 gunicorn、`metrics.wsgi` 或 `metrics.asgi`

#### Scenario: Static files sit behind Basic authentication
- **WHEN** 已配置 Basic 用户，请求不带凭据访问静态文件
- **THEN** Metrics SHALL 返回 401，与 Django 页面一致

#### Scenario: Requests are written to the access log
- **WHEN** 请求携带 `Authorization` 或 `Cookie` 头访问 Django 页面或 `<URL 前缀>/ai/` 下的路径
- **THEN** `serve` SHALL 为该请求写一行访问日志，包含方法、路径与状态码
- **AND** 访问日志 SHALL NOT 包含 `Authorization` 与 `Cookie` 的值

#### Scenario: URL prefix is configured
- **WHEN** `METRICS_BASE_URL` 是 `/metrics/`
- **THEN** 运行时 SHALL 挂载在 `/metrics/ai`
- **AND** 嵌入页路径和运行时资产地址 SHALL 带有同一个前缀

#### Scenario: Mount path is requested without a trailing slash
- **WHEN** 请求的路径恰好是 `<URL 前缀>/ai`，Host 合法且认证通过
- **THEN** 运行时适配器 SHALL 返回 308，`Location` 为只含路径的 `<URL 前缀>/ai/`，并保留查询串
- **AND** 已配置 Basic 用户而请求不带凭据时，响应 SHALL 是 401 而不是 308

#### Scenario: Settings module is not set
- **WHEN** 进程启动时没有设置 `DJANGO_SETTINGS_MODULE`
- **THEN** `manage.py serve` SHALL 使用 `metrics.settings.production`

### Requirement: Serve starts and stops the runtime in a fixed order
`serve` SHALL 先绑定端口，再让运行时在同一进程的专用事件循环线程上进入运行期（Windows 上为 Proactor 事件循环）并安装 project run 运行时，然后才受理第一个请求；任一步失败时 SHALL 以 1 退出（清理也失败时以 3 退出），SHALL NOT 处理任何请求。停止时 `serve` SHALL 依次停止受理新请求、结束打开的 AI 流、排空在途请求并在已缓冲的输出写出后关闭连接、停止 project run，最后停止运行时；没有执行中的 project run 时，从停止触发到进程退出的预算为 10 秒，由看门狗按段保证；停止顺序结束后 `serve` SHALL 写出全部输出并立即结束进程，SHALL NOT 等待剩余线程或解释器收尾。运行期内运行时意外结束时，`serve` SHALL 按同一顺序停止并以 1 退出，SHALL NOT 在没有运行时的情况下继续服务。

#### Scenario: Port is already in use
- **WHEN** 操作者运行 `manage.py serve`，目标地址和端口已被其他进程占用，或绑定被拒绝（`EADDRINUSE` 或 `EACCES`）
- **THEN** 命令 SHALL 在 2 秒内输出 `serve bind failed.` 并以 1 退出
- **AND** 命令 SHALL NOT 在绑定之前运行 Django 系统检查或导入 AI Base 运行时，SHALL NOT 启动运行时，SHALL NOT 获取状态目录锁

#### Scenario: Another process binds the serving port
- **WHEN** `serve` 绑定 `127.0.0.1` 并正在运行，另一个进程以默认选项或设置 `SO_REUSEADDR` 后绑定同一地址和端口
- **THEN** 该绑定 SHALL 失败，发往该地址和端口的连接 SHALL 全部由 `serve` 受理

#### Scenario: Runtime cannot start
- **WHEN** 运行时无法进入运行期，例如状态目录已被其他进程锁定、运行时配置无效、启动时限到期且运行时已按时回滚，或绑定之后的 Django 系统检查报告错误（code `system_check_failed`，此时不启动运行时）
- **THEN** 服务 SHALL 以 1 退出，并只输出一行 `serve startup failed (<code>).`
- **AND** 输出与日志 SHALL NOT 包含异常消息或 traceback
- **AND** 服务 SHALL NOT 在没有运行时的情况下继续提供 Django 页面

#### Scenario: Server shuts down
- **WHEN** `serve` 收到 SIGINT、SIGTERM 或 Windows 上的 SIGBREAK，或者 `--stop-file` 指定的文件出现、`--lifetime-seconds` 到期
- **THEN** `serve` SHALL 先停止受理新请求，打开的 AI 流 SHALL 发送终止事件后结束
- **AND** project run worker SHALL 随后停止，运行时最后停止
- **AND** 未完成的运行 SHALL 被取消并标记为中断，状态目录锁 SHALL 被释放，进程 SHALL 以 0 退出
- **AND** 进程退出前 SHALL 写出全部日志与 `project_runtime_stopped` 事件

#### Scenario: Requests arrive while the server stops
- **WHEN** `serve` 已开始停止，已有连接上又到达 Host 合法的页面请求或 `/ai` 请求，不论是否带凭据
- **THEN** 该请求 SHALL 立即得到固定文本的 503 和 `Retry-After`，SHALL NOT 等待停止完成
- **AND** 响应 SHALL NOT 带 hop-by-hop 头

#### Scenario: Server stops while chat streams are open
- **WHEN** 没有执行中的 project run，一条聊天流正在输出、一条处于空闲、另一条的客户端积压了未读的输出并暂停读取时，`serve` 收到停止信号或 `--stop-file` 指定的文件出现
- **THEN** 正在输出与空闲的流 SHALL 在第一段停止开始后 2 秒内发送终止事件后结束
- **AND** 三个客户端 SHALL 都在连接关闭之前收到终止事件，进程 SHALL 在停止触发后 10 秒内以 0 退出

#### Scenario: A client never reads during shutdown
- **WHEN** 没有执行中的 project run，一个流的客户端一直不读取，`serve` 收到停止信号
- **THEN** `serve` SHALL 在关闭连接的时限到期后关闭该连接，进程 SHALL 在停止触发后 10 秒内以 0 退出

#### Scenario: Runtime stops unexpectedly
- **WHEN** 服务运行期间，运行时因内部错误结束
- **THEN** `serve` SHALL 在 1 秒内输出 `serve runtime failed (<code>).`
- **AND** `serve` SHALL 按停止顺序清理后以 1 退出，清理失败时以 3 退出

#### Scenario: Second signal arrives during shutdown
- **WHEN** `serve` 正在停止（包括排空在途请求与关闭连接期间），又收到一次 SIGINT、SIGTERM 或 Windows 上的 SIGBREAK
- **THEN** `serve` SHALL 输出 `serve forced exit.`，并在 1 秒内以退出码 130 退出
- **AND** 被中断的运行 SHALL 在下一次启动时由恢复标记为中断

#### Scenario: Cleanup does not finish cleanly
- **WHEN** 停止后在途请求在排空时限内没有结束、project run 没有全部停下、运行时停止超时，或某一步清理出错；或者启动时限到期后运行时没有按时回滚
- **THEN** `serve` SHALL 输出 `serve cleanup failed.`（有错误码时附带）并以 3 退出，SHALL NOT 等待未结束的线程

#### Scenario: A thread outlives the stop sequence
- **WHEN** 没有执行中的 project run，停止顺序结束时运行时的事件循环线程或 HTTP server 线程仍未结束，例如运行时停止超时
- **THEN** `serve` SHALL 写出全部输出后立即结束进程，SHALL NOT 等待该线程
- **AND** 进程 SHALL 在停止触发后 10 秒内输出 `serve cleanup failed.` 并以 3 退出

### Requirement: Serve bounds shutdown with a two-stage watchdog
`serve` SHALL 在停止开始时（t0，停止触发后至多 0.5 秒）启动看门狗，截止时刻为 t0 + 9.2 秒；停止 project run 时发现执行中的运行，SHALL 放宽到 t0 + 659.2 秒；project run 的停止在时刻 T 返回后，SHALL 改为当前截止时刻与 T + 1.2 秒中的较早者。到期时看门狗 SHALL 从辅助线程写出 `serve cleanup failed.` 并 flush，至多再等 0.1 秒后以 `os._exit(3)` 结束进程。退出码 SHALL 为：干净停止 0；绑定、启动或运行期失败 1；清理失败或看门狗到期 3，与 1 同时出现时取 3；停止期间第二次信号 130。

#### Scenario: A stop step never returns
- **WHEN** 测试缩短看门狗时限，停止顺序中的某一步一直不返回
- **THEN** 看门狗 SHALL 在截止时刻输出 `serve cleanup failed.`，该行 SHALL 已落盘，进程 SHALL 以 3 退出

#### Scenario: A project run is executing when the server stops
- **WHEN** 停止开始时有一个执行中的 project run，测试使用可注入的时钟
- **THEN** 看门狗截止时刻 SHALL 放宽为 t0 + 659.2 秒
- **AND** 该运行在 620 秒内没有停下时，`serve` SHALL 输出 `serve cleanup failed.` 并以 3 退出

#### Scenario: Project runs finish stopping
- **WHEN** 停止顺序中 project run 的停止在时刻 T 返回
- **THEN** 看门狗截止时刻 SHALL 变为原截止时刻与 T + 1.2 秒中的较早者

### Requirement: Serve verifies process state before it exits
`serve` SHALL 在启动最早处包装 `atexit.register` 以记录注册者，并在显式退出之前、`logging.shutdown()` 之前清点：atexit 回调及注册者、`threading._register_atexit` 回调、存活的非 daemon 线程与子进程、`weakref.finalize(atexit=True)` 与日志 handler。清点结果 SHALL 写成一条结构化日志 `serve_exit_inventory`，并与 `ai_host` settings 中的白名单比对。必需的清理 SHALL 在显式退出中显式执行；出现白名单之外的项，或必需的清理失败、超时时，`serve` SHALL 输出 `serve cleanup failed.` 并以 3 退出。

#### Scenario: Server stops cleanly
- **WHEN** 没有执行中的 project run，`serve` 收到停止信号并完成停止顺序
- **THEN** `serve_exit_inventory` 与最后一行输出 SHALL 已落盘，临时目录 SHALL 已清除，SHALL NOT 留下子进程
- **AND** 进程 SHALL 以 0 退出

#### Scenario: An unlisted exit hook is registered
- **WHEN** 运行期间有代码注册了白名单之外的 atexit 回调
- **THEN** `serve_exit_inventory` SHALL 记录该回调及其注册者，`serve` SHALL 输出 `serve cleanup failed.` 并以 3 退出

#### Scenario: A required cleanup fails
- **WHEN** 测试注入一个失败的必需清理
- **THEN** `serve` SHALL 输出 `serve cleanup failed.` 并以 3 退出

### Requirement: AI requests cannot exhaust the page threads
`/ai` 的在途请求 SHALL 按流式请求与其他请求分开限额（4 与 4），服务线程数（14）减去两个上限后 SHALL 至少为页面保留 6 个线程。UI 资产与未认证的请求 SHALL NOT 计入名额。达到各自上限后新到的 `/ai` 请求 SHALL 立即得到 503 和 `Retry-After`，不排队；页面请求 SHALL 始终有可用线程。请求正常结束、出错、被客户端中止或因服务停止而结束时 SHALL 归还名额。空闲的流 SHALL 按心跳间隔（默认 2 秒）发送心跳，客户端断开 SHALL 在心跳间隔加 1 秒内被发现。

#### Scenario: AI requests reach the in-flight limit
- **WHEN** 流以外的 `/ai` 在途请求已达其上限，又有新的短 `/ai` 请求到达
- **THEN** 新请求 SHALL 立即得到 503 和 `Retry-After`
- **AND** 同时到达的 Django 页面请求 SHALL 照常处理

#### Scenario: Open streams fill their limit
- **WHEN** 打开的流已达到流的上限，又有一条新流和一个短的 `/ai` 请求到达
- **THEN** 新流 SHALL 立即得到 503 和 `Retry-After`
- **AND** 短的 `/ai` 请求和同时到达的页面请求 SHALL 照常处理

#### Scenario: Requests return their admission slots
- **WHEN** 占满流上限的流全部被客户端中止，或者 `/ai` 请求出错结束
- **THEN** 这些请求的名额 SHALL 归还，新流 SHALL 在心跳间隔加 1 秒内被接受
- **AND** 在途数与拒绝数 SHALL 可观测，停止完成后在途数 SHALL 为 0

#### Scenario: Client disconnects from an idle stream
- **WHEN** 一条流处于空闲，客户端断开连接
- **THEN** 运行时 SHALL 在心跳间隔加 1 秒内发现断开，取消该流并释放它占用的资源与名额

#### Scenario: AI pane loads with an empty browser cache
- **WHEN** 浏览器缓存为空，用户打开带 AI pane 的工作台
- **THEN** iframe 入口 HTML 引用的 UI 资产 SHALL 全部位于 `/ai` 挂载路径下并返回 200，SHALL NOT 占用 `/ai` 名额
- **AND** 因名额已满被拒的幂等 GET SHALL 由 UI 按 `Retry-After` 重试，AI pane SHALL 加载完成

#### Scenario: Unauthenticated requests arrive in a burst
- **WHEN** 已配置 Basic 用户，超过短请求上限的未认证 `/ai` 请求同时到达
- **THEN** 每个请求 SHALL 得到 401，SHALL NOT 占用名额，SHALL NOT 进入运行时的事件循环
- **AND** 同时到达的已认证短 `/ai` 请求 SHALL 照常处理

#### Scenario: Embedded page navigation finds the limit full
- **WHEN** 短请求名额已满，iframe 导航到嵌入页
- **THEN** 响应 SHALL 是带 `Retry-After` 的 503 HTML 页面，按该间隔自动刷新，名额释放后 SHALL 加载嵌入页

### Requirement: Non-loopback binds guard anonymous access
`serve` 绑定非回环地址时，settings 允许匿名决定审批的情况下 SHALL 拒绝启动；未配置 Basic 用户时 SHALL 照常启动，并输出一条不含凭据的匿名暴露警告。

#### Scenario: Non-loopback bind without Basic users
- **WHEN** 使用 production settings、未配置 Basic 用户，操作者以非回环地址运行 `manage.py serve`
- **THEN** 服务 SHALL 正常启动，并输出一条只包含绑定地址的匿名暴露警告

#### Scenario: Development settings request a non-loopback bind
- **WHEN** 使用允许匿名决定审批的 development settings，操作者以 `--host 0.0.0.0` 或其他非回环地址运行 `manage.py serve`
- **THEN** 命令 SHALL 在启动服务之前以错误退出

### Requirement: AI runtime requests use the Metrics identity
运行时挂载下的每个请求 SHALL 由 Metrics 宿主的 `authenticate` 确定 principal。`authenticate` 与 Django 的 `BasicAuthMiddleware` 调用同一个纯函数 `check_basic_authorization`，同一请求在两边的认证结果 SHALL 一致。`authenticate` SHALL 是普通函数，由运行时的 WSGI 适配器在 WSGI 线程上、准入之前调用。认证失败 SHALL 返回 401。未配置 Basic 用户时，principal SHALL 是匿名的本地操作者。Basic 用户设置 SHALL fail-closed：格式不合法时 settings 加载 SHALL 失败，SHALL NOT 停用认证。运行时 SHALL NOT 从请求体、tool 参数或 iframe URL 中读取 actor。

#### Scenario: Request carries valid Basic credentials
- **WHEN** 请求携带有效的 Basic 凭据访问 Django 页面或运行时路由
- **THEN** 两边 SHALL 得到同一个 principal，其 id 为该用户名

#### Scenario: Request carries invalid credentials
- **WHEN** 已配置 Basic 用户，请求的凭据缺失或错误
- **THEN** Django 页面和运行时路由 SHALL 都返回 401
- **AND** 两边的 401 SHALL 带同一个 `WWW-Authenticate: Basic realm="Restricted"` 质询头

#### Scenario: Basic user setting is malformed
- **WHEN** `METRICS_BASIC_AUTH_USERS` 是 JSON 数组、非对象 JSON、`{}`，或者含空用户名或空密码
- **THEN** settings 加载 SHALL 以错误失败，错误 SHALL 只指出设置项名称，SHALL NOT 包含设置值
- **AND** Metrics SHALL NOT 在认证被停用的状态下启动

#### Scenario: Basic authentication is not configured
- **WHEN** 没有配置 Basic 用户
- **THEN** 运行时 SHALL 得到匿名的本地操作者 principal

### Requirement: Only authenticated humans decide AI approvals
`external` tool 调用 SHALL 先由运行时创建持久化审批，审批通过之前 SHALL NOT 执行。审批 SHALL 只能由通过认证、且 Metrics 宿主的 `can_decide` 返回真的 principal 决定。匿名 principal SHALL 只在 development settings 中被允许决定审批，这项允许经 `HostConfig.allow_anonymous_approval`（默认 `False`）传给运行时，SHALL NOT 能通过环境变量打开。任何 tool、host action 或模型输出 SHALL NOT 产生审批决定。

#### Scenario: Anonymous operator tries to approve in production settings
- **WHEN** 使用 production settings 且未配置 Basic 用户，匿名本地操作者尝试批准一个发布审批
- **THEN** 运行时 SHALL 拒绝该决定，审批 SHALL 保持 pending

#### Scenario: Production deployment has no Basic users
- **WHEN** 使用 production settings 且未配置 Basic 用户，操作者打开 AI pane
- **THEN** AI pane SHALL 提示发布审批需要配置 `METRICS_BASIC_AUTH_USERS`
- **AND** read tool SHALL 照常可用

#### Scenario: Anonymous operator approves in development settings
- **WHEN** 使用 development settings，匿名本地操作者批准一个审批
- **THEN** 运行时 SHALL 接受该决定，并把本地操作者记录为 `decided_by`

#### Scenario: Model output claims approval
- **WHEN** 模型输出声称用户已经批准，或者请求某个 tool 代为批准
- **THEN** 审批 SHALL 保持 pending，因为不存在任何能产生审批决定的 tool

### Requirement: AI runtime state has a single writer
运行时状态 SHALL 存放在 `METRICS_STATE_DIR/ai-base`，这个路径不能单独配置。同一时间 SHALL 只有一个进程持有该目录的锁；该锁 SHALL 是 OS 级文件锁，持有进程以任何方式终止时 SHALL 由操作系统释放。服务进程持有锁时，需要运行时的 CLI（例如 `project_run --execute-local`）SHALL 立即以 `RUN_BUSY` 失败，不等待，也不改用其他目录。CLI 在自己的进程中启动运行时时 SHALL 设启动时限，到期时 SHALL 以 `RUN_UNAVAILABLE` 失败；启动回滚或退出时的停止没有按时完成时，CLI SHALL 照常写出结果，再输出 `project_run cleanup failed.` 并以 3 退出，SHALL NOT 等待未结束的线程。Metrics SHALL NOT 为多 worker 部署设计共享状态。

#### Scenario: CLI runs while the server holds the lock
- **WHEN** 服务正在运行，操作者执行 `project_run --execute-local`
- **THEN** 命令 SHALL 立即以 `RUN_BUSY` 失败，并提示通过服务提交运行

#### Scenario: CLI runs while no server is running
- **WHEN** 没有服务进程，操作者执行 `project_run --execute-local`
- **THEN** 命令 SHALL 在自己的进程中启动运行时、获取锁、完成运行，并在退出时释放锁；启动时限到期时 SHALL 以 `RUN_UNAVAILABLE` 失败，回滚或停止没有按时完成时 SHALL 在写出结果后输出 `project_run cleanup failed.` 并以 3 退出

#### Scenario: Previous server was killed
- **WHEN** 上一个服务进程被强制终止（例如 SIGKILL），没有执行停止顺序
- **THEN** 下一次 `manage.py serve` SHALL 获得锁并正常启动
- **AND** 被中断的运行 SHALL 由恢复标记为中断

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
project_management 的摘要分析、报告辅助和 project run worker SHALL 通过 project_management 定义的同步 task-run 端口调用 AI；端口由 `ai_host` 基于运行时句柄的同步门面 `handle.blocking.task_runs` 实现，由组合根注入。端口 SHALL 原样传递运行时的错误码及其恢复类别，类别 SHALL 按错误码取自 AI Base 的单一注册表，SHALL NOT 由旧的恢复词换算。运行记录 SHALL 归 project_management 所有，只有一个 schema 版本，SHALL NOT 携带 AI 后端绑定或执行模式；其他版本的记录 SHALL 作为无效存储拒绝，SHALL NOT 兼容读取。Metrics SHALL NOT 用 `asyncio.run` 调用运行时协程，SHALL NOT 在运行时的事件循环线程上调用 blocking 门面，SHALL NOT 保留 HTTP task-run 客户端、凭据引用或 token 设置。

#### Scenario: Project run worker starts an AI run
- **WHEN** project run worker 线程处理一个需要 AI 的运行
- **THEN** 它 SHALL 通过 task-run 端口启动运行，principal SHALL 来自提交运行的用户
- **AND** 运行结果 SHALL 写入 project_management 自有的运行记录，包括档案 `id@version`、模型身份和运行时版本

#### Scenario: Runtime rejects admission
- **WHEN** 运行时拒绝一次准入，例如返回 `model_not_configured`
- **THEN** 端口 SHALL 返回同一个错误码及其恢复类别（`model_not_configured` 为 `repair`），SHALL NOT 改写为其他错误码

#### Scenario: Run storage holds a record of another schema version
- **WHEN** 读取到不是当前 schema 版本的准入记录，例如带有 `backend` 或 `execution_mode` 的旧记录
- **THEN** 读取 SHALL 以 `RUN_STORAGE_INVALID` 失败，SHALL NOT 兼容读取

#### Scenario: Runtime is not running
- **WHEN** 进程不是经组合根启动的（例如 Django 测试客户端），领域服务调用 task-run 端口
- **THEN** 端口 SHALL 返回结构化的 `RUN_UNAVAILABLE`，SHALL NOT 自行创建事件循环或运行时

### Requirement: Metrics App package declares the whole AI surface
Metrics SHALL 用一个 `AppPackage`（`app_id=metrics`）声明全部 AI 能力：agent、带类型和 effect 的 tool、task profile、按 `ContextRef` 解析上下文的 context provider，以及只做 UI 动作的 host action。task profile 的 schema 与 instructions SHALL 由 project_management 以数据维护并随 Metrics 版本化，task run 请求 SHALL 引用精确的 `id@version`。

#### Scenario: Runtime starts with the Metrics package
- **WHEN** 组合根构造运行时
- **THEN** tool 注册表 SHALL 包含 `read` tool `metrics.catalog`、`metrics.chart_workflow` 和 `external` tool `metrics.publish_chart`
- **AND** 运行时 SHALL 拥有 context provider `metrics.workbench` 和 host action `metrics.openChart`、`metrics.openEvidence`
- **AND** 运行时 SHALL 拥有 task profile `metrics.project_summary` 和 `metrics.report_authoring`

#### Scenario: App package is checked
- **WHEN** Metrics 测试对 Metrics App 包运行 `check_app_package`
- **THEN** 检查 SHALL 通过，包括 task profile 的 schema 校验和 `metrics.publish_chart` preview 的确定性

#### Scenario: Task run names its profile
- **WHEN** task-run 端口提交一次运行
- **THEN** 请求 SHALL 引用精确的 `id@version`，SHALL NOT 使用 `latest`

#### Scenario: Embedded chat requests a host action
- **WHEN** iframe 请求执行 `metrics.openChart`
- **THEN** 宿主页面 SHALL 只在 workbench 中切换到该图表，SHALL NOT 改变任何服务端状态

### Requirement: Metrics tools call public APIs off the event loop
tool handler、preview 和 context provider SHALL 是 async 函数，通过 `sync_to_async(thread_sensitive=False)` 在工作线程中调用各模块 `app/api/` 的公共 API，并在该线程中于调用前后各执行一次 `close_old_connections`；它们 SHALL NOT 直接访问 ORM 模型。tool 参数 SHALL NOT 包含 actor、审批 id 或证明 id；操作者 SHALL 只取自 `ctx.principal` 或 `ctx.approval.decided_by`。

#### Scenario: Tool handler reads Metrics data
- **WHEN** 运行时调用一个读取 Metrics 数据的 tool handler
- **THEN** 公共 API 调用 SHALL 在工作线程而不是事件循环线程上执行
- **AND** 该线程 SHALL 在调用前后各关闭一次过期的数据库连接

#### Scenario: Tool schema exposes authority fields
- **WHEN** 某个 Metrics tool 的参数模型包含 actor、approval id、proof id 或 workspace key 字段
- **THEN** App 包测试 SHALL 失败

### Requirement: Metrics and the AI runtime share no HTTP integration
Metrics 与运行时之间 SHALL NOT 存在 HTTP 调用、connector 回调路由、App 注册、instance token、credential ref 或 workspace 同步。`/api/ai-dashboard/` 前缀下的全部路由、sidecar 握手与探活，设置项 `METRICS_AI_SIDECAR_ENABLED`、`METRICS_AI_BASE_*`、`METRICS_PROJECT_AI_*`、`METRICS_PROJECT_RUNTIME_FACTORY`、`METRICS_REPORT_ASSIST_FACTORY`，以及 `TaskRunClient`、`AiBackendTarget`、`execution_mode` 和 vendored 的 `ai_bundle` SHALL 不存在；workbench 使用的发布历史只读 API SHALL 改用 `/api/ai-publish-history/`。grep gate SHALL 阻止这些名称和 `ai_base_application_sdk` 的导入重新出现。

#### Scenario: A former connector route is requested
- **WHEN** 任何客户端请求 `/api/ai-dashboard/workflow/`、`/api/ai-dashboard/identity/` 或该前缀下的其他路径
- **THEN** Metrics SHALL 返回 404

#### Scenario: Workbench reads publish history
- **WHEN** workbench 的 Publish And Audit pane 加载发布历史
- **THEN** 它 SHALL 读取 `/api/ai-publish-history/`，响应字段 SHALL 符合 `grafana-render-config` 的 "AI-generated Grafana dashboards are listed and auditable"

#### Scenario: A change reintroduces an HTTP integration name
- **WHEN** 代码、settings 或脚本中出现上述名称、connector 路由前缀或 `ai_base_application_sdk` 导入
- **THEN** grep gate SHALL 失败

### Requirement: AI pane reports runtime readiness without blocking the workbench
AI pane SHALL 根据进程内运行时显示三种状态之一：`ready`；`not_configured`，即未配置模型；`not_running`，即运行时不在运行期，原因是进程不是经 `manage.py serve` 启动的，或者服务已开始停止。"是否已配置模型"SHALL 只由构造运行时配置的同一个函数判定。非 `ready` 状态 SHALL 说明原因和下一步操作，且 SHALL NOT 影响图表、证据、设置、发布历史和诊断页面。页面视图调用运行时 SHALL 有时限（1 秒）和并发上限（2，小于为页面保留的线程数），达到上限时 SHALL 不等待。Metrics SHALL NOT 提供启用或禁用 AI 的开关，SHALL NOT 在渲染请求时启动任何进程。

#### Scenario: Model is not configured
- **WHEN** 运行时已进入运行期，但 Metrics settings 中没有模型配置
- **THEN** AI pane SHALL 显示 `not_configured`，并列出缺少的设置项名称，SHALL NOT 显示任何设置值
- **AND** 此时提交的 task run SHALL 得到 `model_not_configured`

#### Scenario: Process was not started by the composition root
- **WHEN** 页面由不是经 `manage.py serve` 启动的进程渲染，例如 `runserver` 或 Django 测试客户端
- **THEN** AI pane SHALL 显示 `not_running`，并提示使用 `manage.py serve` 启动

#### Scenario: Runtime is ready
- **WHEN** 运行时已进入运行期且模型已配置
- **THEN** AI pane SHALL 渲染同源的嵌入聊天

#### Scenario: Runtime does not answer in time
- **WHEN** 页面渲染 AI pane 时，打开会话的调用超过 1 秒，或者同时进行的调用已达上限
- **THEN** AI pane SHALL 显示可重试的暂不可用状态
- **AND** 页面 SHALL 照常返回 200，因等待运行时增加的时间 SHALL NOT 超过 1 秒，图表与证据 SHALL 正常显示

### Requirement: One host allowlist protects Django and the AI runtime
`ALLOWED_HOSTS` SHALL 是 Django 和运行时共用的唯一 Host 白名单，经 `HostConfig.allowed_hosts` 传给运行时。未显式配置时，它 SHALL 只包含 `127.0.0.1`、`localhost` 和 `[::1]`，settings SHALL NOT 用通配符作为默认值。Host 不在白名单内的请求 SHALL 在进入任何 Django 视图、静态文件或运行时路由之前得到 HTTP 400，否则 DNS rebinding 之后的页面会被浏览器当作同源。静态文件 SHALL NOT 豁免。

#### Scenario: DNS-rebound page calls Metrics
- **WHEN** 未配置 `ALLOWED_HOSTS`，请求的 Host 是 `rebind.attacker.example`
- **THEN** Django 路径、静态文件和 `<URL 前缀>/ai/` 下的路径 SHALL 都返回 HTTP 400，且不执行任何认证、视图或运行时处理

#### Scenario: Loopback host carries a port
- **WHEN** 未配置 `ALLOWED_HOSTS`，请求的 Host 是 `127.0.0.1:8793`、`localhost:8793` 或 `[::1]:8793`
- **THEN** Django 和运行时 SHALL 都正常处理请求

#### Scenario: Deployment lists another host name
- **WHEN** `ALLOWED_HOSTS` 环境变量显式列出 `metrics.example.internal`
- **THEN** Django 和运行时 SHALL 都接受该 Host

### Requirement: Requests pass the host layers in a fixed order
`serve` 的请求 SHALL 按固定顺序处理。L0 由 waitress 在调用应用之前完成：请求行与头部大小、`Content-Length` 语法、chunked 分帧和请求体上限。L1 由 `serve` 的分派完成：先按 Django `get_host()` 的规则对所有路径校验 Host，非法时返回固定文本的 400；Host 合法且已开始停止时返回 503；然后挂载路径交给运行时适配器，其余路径进入 Django 中间件链。适配器 SHALL 依次执行 Host 校验、请求完整性、认证、308、UI 资产、运行时未运行的 503 与准入。

#### Scenario: Invalid host arrives while the server stops
- **WHEN** 已配置 Basic 用户、`serve` 已开始停止，一个不带凭据的请求以不在白名单内的 Host 到达
- **THEN** 响应 SHALL 是 400，SHALL NOT 是 503 或 401

#### Scenario: Django path gets an invalid host without credentials
- **WHEN** 已配置 Basic 用户，经 `serve` 访问 Django 路径的请求 Host 不在白名单内且不带凭据
- **THEN** 响应 SHALL 是 400 而不是 401

#### Scenario: Unauthenticated requests reach the mount path
- **WHEN** 已配置 Basic 用户，不带凭据的请求访问 `<URL 前缀>/ai`、挂载路径下的 UI 资产，或在短请求名额已满时访问 `/ai` 路由
- **THEN** 每个请求 SHALL 得到 401，SHALL NOT 得到 308、200 或 503

### Requirement: The server caps request bodies
`serve` SHALL 显式把 waitress 的 `max_request_body_size` 设为 N + 1 字节，N 取 `request_body_policy(settings, apps).max_request_body_bytes` 与 Django 侧最大合法请求中的较大值，SHALL 在启动任何运行时资源之前计算。waitress 在调用应用之前读完并缓冲请求体，超过 512 KiB 时写入临时文件，因此这个 413 SHALL 是唯一的资源上限，最坏的临时文件占用约为 N 乘以连接上限；适配器的 413 只保证语义与顺序。宿主对非数字 `Content-Length` 返回 400 的分支 SHALL 作为纵深防御保留。

#### Scenario: Declared body exceeds the cap
- **WHEN** 一个不带凭据的请求声明的 `Content-Length` 为 N + 1
- **THEN** waitress SHALL 在读取请求体之前返回 413，响应体 SHALL 含 `(generated by waitress)`，应用 SHALL NOT 被调用

#### Scenario: Chunked body exceeds the cap
- **WHEN** 一个 chunked 请求体累计达到 N + 1 字节
- **THEN** waitress SHALL 返回 413，应用 SHALL NOT 被调用

#### Scenario: Body is exactly at the cap
- **WHEN** 一个请求的请求体恰好为 N 字节
- **THEN** waitress SHALL 调用应用，SHALL NOT 在 L0 返回 413

#### Scenario: Content-Length is not a number
- **WHEN** 请求的 `Content-Length` 不是数字
- **THEN** waitress SHALL 返回 400，应用 SHALL NOT 被调用

### Requirement: Host conformance suite gates the composed runtime
Metrics 测试 SHALL 用运行时 testkit 的宿主一致性套件验证组合后的宿主，检查项见下方场景；Metrics SHALL 在单独的一致性通道中以 ini 选项 `ai_host_modes=blocking_wsgi` 声明托管方式，SHALL NOT 在默认的 pytest 配置中加载该插件。确定性的对话测试 SHALL 使用 testkit 的脚本化模型，SHALL NOT 依赖真实模型或聊天快捷方式。升级运行时版本 SHALL 以该套件通过为门禁。

#### Scenario: Conformance suite runs against the composed host
- **WHEN** Metrics 测试对组合后的宿主运行宿主一致性套件
- **THEN** 套件 SHALL 覆盖 Host 校验、请求完整性、资源归属、`frame-ancestors`、审批持久化、`os.environ` 与全局 tracer 不变、Proactor 事件循环、slow callback 阈值与 `RuntimeBusy`
- **AND** 套件 SHALL 覆盖运行时未运行或进入第一段停止后 `/ai` 返回 503、第一段停止开始后所有打开的流在 `HostConfig.lifecycle.http_close_timeout_seconds`（2 秒）内发送终止事件后结束、第二段停止在 `HostConfig.lifecycle.stop_timeout_seconds` 内返回、在事件循环线程上调用 blocking 门面立即抛 `RuntimeUsageError`、门面等待超时抛 `RuntimeCallTimeout` 并取消循环侧协程、以同一个 `client_run_key` 重试只产生一次运行、运行时结束信号 `handle.ended` 在 1 秒内可见
- **AND** 套件 SHALL 覆盖 WSGI 适配器逐块转发流式响应、空闲流按心跳间隔发送心跳且断开在心跳间隔加 1 秒内被发现、在 WSGI 线程上从 `wsgi.input` 读取有上限的请求体、响应块交接队列有上限并形成背压、客户端断开后释放连接级资源、流与其他 `/ai` 请求分开的在途上限、名额在正常结束、出错、客户端中止与停止后都归还、循环被阻塞时短请求在总时限内得到 503 或 504、适配器按 Host 校验、请求完整性、认证、308、UI 资产、运行时未运行的 503、准入的顺序逐项执行且未认证请求不占名额、UI 资产不经循环与准入（循环被阻塞时仍返回 200）且 URL 跟随挂载路径、导航请求被拒时得到自动刷新的 503 页面
- **AND** 套件 SHALL 覆盖运行时不安装信号处理器、不注册 atexit，以及第二段停止期间宿主的信号处理器在 1 秒内执行
- **AND** 套件 SHALL 在离开 `with context as handle` 块后立即以 `os._exit(0)` 结束运行时所在的子进程，重启后已完成的运行、会话与审批记录 SHALL 完整，状态目录锁 SHALL 可再次获取

#### Scenario: Runtime version is upgraded
- **WHEN** 一个变更修改了固定的 `ai-base-runtime` 版本
- **THEN** 宿主一致性套件和 Metrics 浏览器测试子集 SHALL 在合入之前通过

#### Scenario: Chat-driven publish flow is tested
- **WHEN** 测试覆盖从对话发起的图表工作流和发布
- **THEN** 测试 SHALL 用 testkit 的脚本化模型产生确定的 tool 调用，SHALL NOT 调用真实模型

### Requirement: AI runtime audit is written to Metrics
Metrics 宿主 SHALL 把运行时投递的会话、tool 调用和审批（请求、决定、作废、消费、过期）事件写入 `ai_host` 自有的只追加审计表，记录 `event_id`、事件类别、发生时间、principal、session id、run id、`tool_call_id`、tool 名称、审批 id、结果状态与运行时给出的事件顺序。认证失败 SHALL 只输出一条结构化日志 `ai_auth_failed`，SHALL NOT 写入数据库。Metrics 代码 SHALL 只插入审计记录，SHALL NOT 更新或删除；这些事件 SHALL NOT 写入 bug_metrics 的业务审计 `BugTrendAuditEvent`。审计记录与日志 SHALL NOT 包含模型凭据、provider token、Basic 密码或其他秘密。

#### Scenario: Publish approval completes its lifecycle
- **WHEN** 一次 `metrics.publish_chart` 调用经历请求审批、批准和执行
- **THEN** `ai_host` 审计表 SHALL 依次记录审批请求、决定、消费和 tool 调用结果，顺序以运行时给出的事件顺序为准，每条都带有同一个 `tool_call_id`

#### Scenario: Authentication fails
- **WHEN** 已配置 Basic 用户，运行时路由上的一个请求认证失败
- **THEN** `ai_host` 审计表的行数 SHALL 不变
- **AND** 宿主 SHALL 输出恰好一条 `ai_auth_failed` 日志，记录路径、客户端地址与原因，SHALL NOT 包含提交的凭据

### Requirement: AI runtime audit delivery is idempotent and bounded
运行时至少投递一次审计事件，且不为投递设时限。同一 `event_id` 再次投递时，宿主 SHALL NOT 新增行，SHALL NOT 报错。`record_audit` SHALL 在有界时间内返回或抛错：等待数据库锁超过 SQLite busy timeout 时 SHALL 抛错，由运行时重投。

#### Scenario: Audit event is delivered again
- **WHEN** 运行时再次投递一个已写入的事件（同一 `event_id`）
- **THEN** `ai_host` 审计表 SHALL 仍只有一行该事件
- **AND** `record_audit` SHALL 正常返回

#### Scenario: Audit write meets a held database lock
- **WHEN** 另一连接持有 SQLite 写锁，运行时投递一个审计事件
- **THEN** `record_audit` SHALL 在 busy timeout 到期后抛错，SHALL NOT 挂起，审计表 SHALL NOT 新增该事件
- **AND** 锁释放后运行时再次投递该事件，审计表 SHALL 恰好有一行该事件

### Requirement: Runtime version is pinned and admitted explicitly
Metrics SHALL 在 `requirements.txt` 中固定 `ai-base-runtime` 的精确版本；准入时 SHALL 校验 wheel 摘要、`pip check` 无冲突、宿主一致性套件通过。Metrics SHALL NOT 依赖 Python HTTP SDK `ai-base-application-sdk`，SHALL NOT vendor 运行时的前端资产；嵌入脚本 SHALL 使用运行时句柄 `handle.ui.asset_url` 返回的带内容哈希的地址。

#### Scenario: A new runtime wheel is admitted
- **WHEN** 维护者把固定版本升级到新的 `ai-base-runtime` wheel
- **THEN** 准入检查 SHALL 校验 wheel 摘要与记录一致、`pip check` 无冲突、宿主一致性套件通过，任何一项失败都 SHALL 阻止合入

#### Scenario: Workbench loads the embed script
- **WHEN** workbench 渲染 AI pane
- **THEN** `embed-host.js` 的地址 SHALL 来自运行时句柄的 `handle.ui.asset_url`，Metrics 静态目录中 SHALL NOT 存在该脚本的副本

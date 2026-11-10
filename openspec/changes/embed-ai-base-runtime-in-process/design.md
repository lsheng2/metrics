# Design

## Context

动机与范围见 `proposal.md`（Why / What Changes），行为要求见本变更的 9 个 delta spec；本文只写"怎么做"，按 capability
名引用要求，不重复场景。未加模块前缀的 `app/`、`services/`、`out/`、`management/` 路径均位于 `project_management/` 下。

已定输入（不再讨论）：

- owner 已于 2026-11-10 签署 v2 的 Q1–Q9，并接受 MDB-2 依赖的五项运行时补充：D4 `AppPackage.task_profiles`
  （删除 `pack.py`/`ScopeGrant`）、D5 `ToolContext.context_ref`、D6 审批绑定的预览摘要、D7
  `open_session(..., session_key)`、D9 task-run 真实模型执行与准入错误码（`upstream-ai-base-runtime-proposal.md`）。
- owner 于 2026-11-10 决定保留 Docker 部署：镜像改为单进程 `manage.py serve`，非回环绑定不强制 Basic 认证，
  维持现有的匿名姿态（决策 3、16）。
- 本设计只使用 v2 文档定义的运行时 API（`create_runtime`、`start_blocking`、`runtime.running()`、`runtime.asgi_app()`、
  `runtime.chat`、`runtime.task_runs`、`runtime.blocking`、`runtime.ui.asset_url`、`ai_base_runtime.spi/apps/contracts/testkit`）。
- 发布顺序：AIB-0（AI Base 热修）→ S0 共装 spike → AIB-2 与 MDB-2 同版本发布（v2 §9）。

与设计相关的现状：

- 服务：`project_serve` 是多线程 WSGI 服务（`management/commands/project_serve.py:100-115`，`daemon_threads`），先
  `build_project_runtime()` 与 `start()`，再托管 `StaticFilesHandler(get_internal_wsgi_application())`（`:50`）；停止时
  `runtime.stop(620)`（`:70`）并输出 `project_runtime_stopped` JSON 事件（`:86-93`），验证脚本依赖它的 `--stop-file`、
  `--lifetime-seconds`（`:24-25`，`scripts/validation/project_full_stack.py:156-158,178`）。
- `metrics/asgi.py:14` 默认指向空的 `metrics.settings` 包，而 `manage.py:9` 使用 `metrics.settings.production`；
  `WSGI_APPLICATION` 仍指向 `metrics.wsgi`（`metrics/settings/defaults.py:85`）。
- 生产没有 project run 组合：`METRICS_PROJECT_RUNTIME_FACTORY`（`metrics/settings/defaults_metrics.py:213`）未设置时
  project run 一律 `RUN_UNAVAILABLE`，因此生产从未写出 v1 AI 记录。
- AI 路径用 `asyncio.run` 调用异步客户端：`services/report_assists.py:64,75,105`、`services/project_run_worker.py:196,322`。
- 准入记录 `request.json` 双读 v1/v2 并携带 `backend`、`execution_mode`（`app/domain/run_admission_values.py:73,88,90,118,140-142,190`）。
- `out/ai_task_contract.py`（`AiTaskContract`，`:32`）和 `out/report_ai_task.py`（`AuthoringTaskContract`，`:13`）
  目前是 vendored task pack 的 wire 校验器，不是端口。
- 发布历史由 `BugTrendAuditEvent`（`bug_metrics/models.py:270`）推导（`bug_metrics/app/api/ai_dashboard_approval.py:116-150`）。
- 依赖：`requirements.txt` 固定 Django 6.0.7、whitenoise 6.12.0、gunicorn 26.0.0（`:8`）、portalocker 4.4.1；AI Base
  要求 portalocker ≥4.4.2（v2 D9）。
- Docker：`ops/docker/Dockerfile:27-36` 以 gunicorn 运行 `metrics.wsgi`（5 worker × 10 线程，绑定 `0.0.0.0:8000`），
  README 的 Docker 快速上手（`README.md:100-139`）与生产步骤（`:566`）都以它为准。镜像中 `METRICS_STATE_DIR` 默认为
  `/metrics/state`（`defaults_metrics.py:44`）。

## Goals / Non-Goals

**Goals:**

- 一个 uvicorn 进程、一个组合根 `metrics.asgi` 同时托管 Django 与运行时；`manage.py serve` 是唯一受支持的启动方式。
- 运行时只经新 Django app `ai_host` 进入 Metrics；project_management 只依赖自己定义的同步端口；domain 保持纯 Python。
- project run 与 report assist 经 task-run 端口、以提交用户身份在真实模型上执行，记录只有一个版本。
- 发布审批绑定确定性预览摘要，发布结果写入 Metrics 自有的 `AiChartPublication`。
- 验证只替换外部系统（模型、Jira），组合根与生产完全相同。
- 一次切换完成：HTTP 集成与兼容读取全部删除，数据库、状态目录、archive root 作为一个单元备份和回滚。

**Non-Goals:**

- 多 worker、reload、多进程共享状态目录（v2 §8.9）。
- 任何向后兼容：旧 admission/wire 记录不读取、`runtime/operations/` 不迁移、旧 `BugTrendAuditEvent` 发布行不进入新发布列表。
- 迁移 dashboard_query_agent 的旧会话与外壳状态（Q8）。
- 在 Metrics 中重做运行时已有的能力：审批 UI、会话存储、模型管线、task-run 准入；Metrics 不提供 AI 开关。
- 任何过渡层：HTTP sidecar、connector 路由、BFF、双通道并行（v2 §8.1）。
- AIB-2 自身的设计与 AI Base 仓库的改动。

## Decisions

### 决策 1：`metrics.asgi` 是唯一组合根，`ai_host` 是唯一导入运行时的模块

- **决定**：
  - `metrics/asgi.py` 先 `os.environ.setdefault("DJANGO_SETTINGS_MODULE", "metrics.settings.production")`，调用
    `get_asgi_application()` 完成 `django.setup()`，再导入 `ai_host.wiring.build_application`；除此之外不导入 AI 代码。
  - 新 Django app `ai_host`（加入 `INSTALLED_APPS`）：`wiring.py`（组合根、lifespan、CLI 端口工厂）、`host.py`（宿主 SPI）、
    `package.py`（`METRICS_APP`）、`settings.py`、`state.py`（生命周期对象）、`task_runs.py`、`tools/`、`models.py`（审计表）、
    `management/commands/serve.py`。
  - 外层 Starlette 应用：`Mount(ai_mount_path(), app=runtime.asgi_app())` 在前，`Mount("/", app=django_app)` 在后。
    挂载路径为 `METRICS_BASE_URL + "ai"`（Q7）。静态文件只由中间件链中的 WhiteNoise 提供（`defaults.py:52-55`，位于
    `BasicAuthMiddleware` 之后，与现在的 gunicorn 镜像相同），并设置 `WHITENOISE_USE_FINDERS = True`，让没有运行
    `collectstatic` 的本地进程也能提供静态文件；不再使用 `project_serve.py:50` 的 `StaticFilesHandler` 或其 ASGI 等价物。
    Django 6 已不读取 `STATICFILES_STORAGE`（`defaults.py:147`），实际生效的是不带哈希的 `StaticFilesStorage`，finders 与
    `STATIC_ROOT` 中的文件名一致。
  - 删除 `metrics/wsgi.py` 与 `WSGI_APPLICATION`（`defaults.py:85`）；Docker 与 README 的部署方式见决策 16。
    `runserver` 与 Django test client 仍能渲染页面，此时 AI pane 为 `not_running`。
  - 导入规则测试（import-linter 或等价 gate）：只有 `ai_host` 导入 `ai_base_runtime`；任何模块不导入
    `ai_base_runtime._internal` 或 AI Base 的 `app.*`；`metrics/asgi.py` 只导入 Django 与 `ai_host.wiring`；
    project_management 不导入 `ai_host`；各模块 `app/domain/` 不导入 Django、asgiref 与运行时。
  - 依赖：精确固定 `ai-base-runtime`、`uvicorn`，以及 `ai_host` 直接导入的 `starlette`；删除 `gunicorn`、
    `ai-base-application-sdk` 与 `requirements-ai-task.txt`；portalocker 升到 ≥4.4.2，精确值由 S0 确定。
- **理由**：开发、验证、生产走同一条装配路径；运行时 API 面收敛在一个 app，升级只改一处；边界可由 gate 机器检查
  （见 `embedded-ai-runtime-host`）。Django 的 ASGI handler 只处理 HTTP scope，Starlette 的 `Mount` 不转发 lifespan，
  所以 lifespan 必须由外层应用持有。静态文件只走一条路径：外层的静态处理器会绕过整条中间件链，配置了 Basic 用户的镜像
  会因此公开静态文件。
- **否决的备选**：把运行时挂进 Django URLconf（Django 无法托管子应用的 lifespan）；在 `AppConfig.ready()` 构造运行时
  （migrate、测试、CLI 等所有加载 Django 的进程都会争抢状态目录锁）；保留 WSGI 入口作备用（第二个组合根，永远进不了
    `running()`）；外层用 `ASGIStaticFilesHandler` 提供静态文件（绕过中间件链，见理由）。

### 决策 2：lifespan 与 project run 生命周期（与 v2 §5.1 一致）

- **决定**：`build_application(django_app)` 调用 `create_runtime(build_settings(), host=MetricsHost(), apps=[METRICS_APP])`，
  lifespan 严格按以下顺序：
  1. Windows 上断言当前运行的循环是 Proactor 循环，否则以 Metrics 自有错误码 `EVENT_LOOP_NOT_PROACTOR` 启动失败；
  2. `async with runtime.running()`：获取状态目录锁；`RuntimeBusy` 与无效设置直接向外传播；
  3. `attach(runtime)`，供 `ai_host` 视图、嵌入路径与 AI pane 状态读取；
  4. `port = RuntimeTaskRunPort(runtime.blocking.task_runs)`；
  5. `project_runs = await asyncio.to_thread(build_project_runtime, task_runs=port)`，随后 `install_project_runtime(project_runs)`；
  6. `await asyncio.to_thread(project_runs.start)`，然后 `yield`；
  7. `finally`：`await asyncio.to_thread(project_runs.stop, 620)`，随后立即向 stdout 写一行 `project_runtime_stopped`
     事件（格式同 `project_serve.py:86-93`；`stop` 抛错时按 `RuntimeStopResult(False, None, ())` 输出，同 `:69-75`）
     → `clear_project_runtime(project_runs)` → `detach()` → 离开 `running()`。任一步的异常记入生命周期对象，不跳过后续步骤。
  - `ai_host.state` 中只有一个生命周期对象，保存阶段（starting/running/stopped/failed）、启动或清理的错误码（异常的
    `code` 属性，取法同 `project_serve.py:95-98`）和 `stop` 返回的 `RuntimeStopResult`。启动阶段的异常记录错误码后，
    以只含错误码的异常重新抛出（`from None`）：uvicorn 会把 lifespan 启动失败的 traceback 文本写入日志
    （`lifespan/on.py:115-121`），这样日志不含原异常消息。`serve` 与 AI pane 只读这个对象。
- **理由**：
  - `ProjectRunRuntime.start()`（`project_management/runtime.py:39-43`）调用 `reconcile_interrupted()`
    （`services/project_run_recovery.py:17-29`）扫描运行档案并访问 ORM，放在事件循环上会抛 `SynchronousOnlyOperation`
    并阻塞循环；v2 §5.1 把构造、启动、停止都视为阻塞调用。
  - `stop()` 要等待 worker 线程，而 worker 可能正阻塞在 blocking 门面上，门面的协程需要同一个循环推进；在循环上
    stop 会死锁。先停 worker、后离开 `running()`，worker 的最后一次调用仍有运行中的运行时。
  - 620 秒 = `RunPolicy.timeout_seconds` 600（`app/domain/run_contracts.py:33`）加宽限，等于 `project_serve.py:70`。
  - 停止事件紧接 `stop` 在 lifespan 中输出，而不是在 `serve` 的 `run()` 返回之后：非 PID 1 进程收到 SIGTERM 时，
    uvicorn 重新抛出该信号，`run()` 之后的代码不会执行（决策 3）。
  - Proactor 是 v2 D8 对 Windows 宿主的要求，由一致性套件断言。
- **否决的备选**：在 `AppConfig.ready()` 启动 worker（非服务进程也会启动）；`sync_to_async(thread_sensitive=True)`
  调用 start/stop（排进共享线程，与请求和 tool 调用互相阻塞）；在 lifespan 之外单独启停 project run（无法保证
  "先停 worker、再停运行时"的顺序）。

### 决策 3：`manage.py serve` 取代 `project_serve`

- **决定**：
  - 新命令 `ai_host/management/commands/serve.py`；删除 `project_serve` 及 `project_management/tests/test_project_serve_command.py`。
  - 地址：`--host` 默认 `127.0.0.1`。回环判定为 `host == "localhost"` 或 `ipaddress.ip_address(host).is_loopback`，
    无法解析为 IP 的主机名按非回环处理（取代 `project_serve.py:30` 的固定集合）。非回环绑定（如容器内的 `0.0.0.0`）
    按 owner 决定允许，另有两条规则：settings 允许匿名决定审批（只有 development settings，决策 14）时以
    `CommandError` 拒绝，避免匿名审批暴露到网络；未配置 Basic 用户时输出一条 `serve_anonymous_network_bind`
    警告，只含绑定地址。
  - 运行 `uvicorn.Server(uvicorn.Config("metrics.asgi:application", host=..., port=..., lifespan="on", workers=1,
    reload=False, timeout_graceful_shutdown=10)).run()`；不提供 workers 或 reload 参数。
  - `serve` 捕获 `run()` 抛出的 `SystemExit`（lifespan 或端口绑定失败时 uvicorn 调用 `sys.exit`）与 `KeyboardInterrupt`
    （Ctrl+C 关闭后 uvicorn 重新抛出 SIGINT），然后统一判断：`server.started` 为假且生命周期对象有启动错误码时输出
    `serve startup failed (<code>).`；为假但没有启动错误码（lifespan 已启动、端口绑定失败）时输出 `serve bind failed.`；
    两者都非零退出。
  - 保留 `--stop-file`（绝对路径）与 `--lifetime-seconds`（`project_serve.py:24-25,117-130`）：命令内的监视线程在文件
    出现或到期时设置 `server.should_exit`，走正常 lifespan 关闭。Windows 父进程无法可靠地向子进程发送 Ctrl+C，
    验证脚本依赖这两个参数。
  - `project_runtime_stopped` 事件由 lifespan 输出（决策 2 第 7 步），格式不变，仍由
    `scripts/validation/project_full_stack_identity.py:304` 消费；`serve` 不再输出它。启动成功的情况下，未干净停止
    （`stopped` 为假或 `unresolved` 非空）或生命周期对象有清理错误码时输出 `serve cleanup failed.`（有错误码时附带），
    非零退出；否则退出码为 0。
- **理由**：错误输出只含错误码，沿用 `project_serve.py:95-98` 不泄露细节的约定；保留停止事件让现有验证断言不变。
  以下行为已在 uvicorn 0.54.0 源码中核实，S0 以固定版本复核：
  - lifespan 启动失败时 `Server.startup` 调用 `sys.exit(STARTUP_FAILURE)`（`server.py:116-118`）；端口绑定失败时先执行
    lifespan shutdown 再 `sys.exit`（`:189-192`）；`started` 只在启动成功后置真（`:205`）。0.47.0 在 lifespan 失败时
    只是返回，上面的捕获方式对两种行为都成立。
  - `timeout_graceful_shutdown` 默认 `None`（`config.py:236`）。关闭时先停止监听并通知各连接，再等待所有连接与任务结束
    （`server.py:281-311`），打开的 SSE 或聊天流会让关闭无限等待；设为 10 秒后，超时的任务被取消，lifespan shutdown
    照常执行。
  - `capture_signals`（`:331-349`）在 `run()` 结束前恢复原信号处理器，并重新抛出捕获到的信号。非 PID 1 进程收到 SIGTERM
    时在 lifespan 结束后以该信号退出，`run()` 之后的代码不执行，所以停止事件必须在 lifespan 中输出；SIGINT 则变成
    `KeyboardInterrupt`。Docker 中 exec 形式的 Python 是 PID 1，内核不向它投递默认处理的 SIGTERM，`run()` 正常返回。
  - 连续两次 Ctrl+C 会置 `force_exit`，不再发送 lifespan shutdown（`:310-311,351-356`），按强制终止处理：中断的运行由
    下次 `start()` 的恢复标记出来。
  - Windows 上不使用子进程时，循环工厂是 `ProactorEventLoop`（`loops/asyncio.py:8-10`）。
- **否决的备选**：直接用 `uvicorn` CLI（无法做绑定规则、读错误码、输出停止事件）；`uvicorn.run()`（返回后拿不到
  `Server` 实例判断 `started`）；把 `runserver` 作为支持的方式（不经 lifespan）；一律拒绝非回环绑定（容器无法部署）；
  非回环绑定强制 Basic 认证（owner 选择维持现有姿态）。

### 决策 4：tool handler 为 async，经 `sync_to_async(thread_sensitive=False)` 调用 Metrics 公共 API

- **决定**：
  - Metrics 的 tool、preview、`ContextProvider` 与 `record_audit` 都是 async 函数，只调用各模块 `app/api/` 的公共 API，
    不直接访问 ORM 模型，不在事件循环上做阻塞 I/O。
  - 同步调用统一经 `ai_host` 的 helper `run_sync`：`sync_to_async(..., thread_sensitive=False)`，在工作线程内调用
    前后各执行一次 `close_old_connections()`。
  - 公共 API 的领域错误映射为 `ToolError(<code>)`；其余异常交给运行时以 API 错误返回（v2 D8）。
- **理由**：tool 调用由运行时在 Django 请求处理之外调度，没有 `ThreadSensitiveContext`；`thread_sensitive=True` 会把
  所有调用串到一个共享线程上，并发 tool 调用互相排队，任一调用等待另一个 thread-sensitive 调用就会死锁。Django 连接
  按线程保存，请求信号不会为 tool 调用触发，所以要手动 `close_old_connections()` 来遵守 `CONN_MAX_AGE` 并丢弃失效连接。
  v2 §5.2 的草图已改为同一个 helper。
- **否决的备选**：同步 handler 由运行时放进线程池（v2 未定义该行为）；`thread_sensitive=True`（见上）；在 handler 中
  用 Django async ORM（绕过公共 API，破坏模块边界）。

### 决策 5：`NetworkPolicy` 只管运行时自身的模型出口，Grafana 导入留在 Metrics

- **决定**：
  - `HostConfig` 中的 `NetworkPolicy` 只描述运行时自建 HTTP 客户端访问模型端点的出站配置。运行时客户端显式传入代理并设
    `trust_env=False`（v2 F13 缓解），不受 Metrics 进程环境变量影响；Metrics 现在没有代理设置，因此传入不含代理的策略。
  - Grafana 导入不是运行时出口：`publish_chart` 在 Metrics 进程内调用 bug_metrics 公共 API，复用
    `import_grafana_dashboard_payload`（`bug_metrics/app/api/ai_dashboard_grafana_publish.py:14`，`overwrite: True` 见 `:17`），
    目标来自 `METRICS_AI_GRAFANA_BASE_URL`、`_USERNAME`、`_PASSWORD`（`defaults_metrics.py:157-159`，保留）。
  - Jira 与 Azure 访问继续走 provider 连接与同步（见 `provider-facts-and-sync`），与运行时无关。
- **理由**：运行时只需要和模型通信；Grafana、Jira 凭据与错误码留在 Metrics 自己的配置和代码路径中。一致性套件断言
  `os.environ` 在运行时启动前后不变，Metrics 访问 Jira、Grafana 的代理不会被运行时改写。
- **否决的备选**：把 Grafana 做成运行时的 HTTP tool 或 connector（重新引入 connector 边界，凭据要交给运行时）；
  在 `NetworkPolicy` 中枚举允许的主机（v2 没有定义主机白名单字段）。

### 决策 6：模型设置只来自环境变量，AI pane 三态

- **决定**：
  - `ai_host.settings.build_settings()` 读取 `METRICS_AI_MODEL_BASE_URL`、`METRICS_AI_MODEL_NAME`、`METRICS_AI_MODEL_API_KEY`
    （`SecretStr`）。它们只来自环境变量，不进数据库，不出现在页面或日志中。
  - 三项齐全才在 `HostConfig` 中配置模型。任一缺失时运行时照常进入运行期，task run 准入返回 `model_not_configured`，
    AI pane 显示 `not_configured` 并只列出缺失的变量名。
  - pane 状态由生命周期对象和设置推导：未经 lifespan 启动为 `not_running`，缺模型为 `not_configured`，否则为 `ready`。
    scope binding 未解析的诊断与运行时就绪状态分开显示（见 `unified-metrics-workbench-ui`）。
  - 删除 `METRICS_AI_SIDECAR_ENABLED` 与 `METRICS_AI_BASE_*`（`defaults_metrics.py:149-156`），不提供 AI 开关。
- **理由**：模型凭据与 `METRICS_AI_GRAFANA_PASSWORD` 一样经环境变量注入，沿用现有机密姿态；"模型是否已配置"
  由运行时准入统一判断（v2 D9），Metrics 不重复判断，只把 `model_not_configured` 映射为 `not_configured`。
- **否决的备选**：在设置页保存模型凭据（需要新的机密存储和审计）；缺模型时不启动运行时（`not_configured` 会退化成
  `not_running`，失去可诊断性）；保留启用开关。

### 决策 7：工作台会话键与 `ContextRef`

- **决定**：
  - 嵌入路径来自 `runtime.chat.open_session(principal, app_id="metrics", agent=..., context_ref=...,
    session_key=f"metrics.workbench.{profile_id}")`（D7），运行时按 (principal, app_id, session_key) 复用会话。
  - range、图表或 bucket 变化时，页面局部刷新得到新的 `ai_context_ref`，经 `embed-host.js` 发送 `context-changed`，
    运行时把同一会话重新绑定（进程内等价调用为 `runtime.chat.bind_context`），不新建会话。
  - `ContextRef(kind="metrics.workbench", values=...)` 只含标识：binding key、profile id、provider、range、chart id、
    bucket/series、已选 ticket id。值只能是 str/int/bool 或它们的扁平列表，规范化后不超过
    `RuntimeLimits.max_context_ref_bytes`（4 KiB）。ticket id 最多 50 个，超出数量或字节上限时按选择顺序保留能放入的
    最长前缀，并附带 `ticket_ids_total` 与 `ticket_ids_truncated`，让模型知道列表不完整。`ai_host` 在服务端由
    `WorkbenchPageQueryState` 构造，页面只转发。
  - `WorkbenchContextProvider` 的 `validate(principal, ref)` 检查标识对当前 principal 可见，`resolve(principal, ref)`
    生成安全摘要；tool 再用 `ctx.context_ref`（运行开始时的快照，D5）复核参数，越界抛
    `ToolError("CONTEXT_BOUNDARY_VIOLATION")`。
  - 同源 iframe，`embed-host.js` 地址取自 `runtime.ui.asset_url("embed-host.js")`。审批只在嵌入的运行时 UI 中决定，
    Metrics 不另建审批视图。
- **理由**：一个 profile 对应一个持续的工作台对话；上下文只传标识，数据在服务端按 principal 拉取，越界校验不依赖页面。
- **否决的备选**：按 binding key 建会话（切换范围就丢失对话）；每个 principal 一个会话（不同 profile 的上下文混在一起）；
  不传 session key（每次打开都新建会话）；在 `ContextRef` 中放图表数据或 ticket 正文（超限，也无法校验）。

### 决策 8：发布审批绑定确定性预览，结果写入 `AiChartPublication`

- **决定**：
  - `publish_chart` 声明 `effect="external"` 与 `preview=preview_chart_publication`。preview 只读且确定（同样的参数和
    数据产生同样的字节），返回 `{dashboard, target:{grafana_base_url, uid}}`；运行时用 `canonical_digest` 绑定审批（D6）。
  - uid 由 Metrics 按工作流信封与 profile 渲染配置确定，不取自模型参数；`grafana_base_url` 取自设置。
  - handler 只反序列化 `ctx.approval.preview`，复核 `canonical_digest(...) == ctx.approval.preview_digest`（否则
    `ToolError("PREVIEW_DIGEST_MISMATCH")`），只导入已批准的字节；操作者取 `ctx.approval.decided_by`，幂等键为
    `ctx.tool_call_id`。
  - 新表 `bug_metrics.AiChartPublication`，由 bug_metrics 公共 API 在导入后写入：每次执行一行，状态为 `published` 或
    `failed`（带错误码），字段满足 `grafana-render-config` 与 `ai-dashboard-publish-authority` 的列表和审计要求；
    `tool_call_id` 唯一，重复执行直接返回已存结果；`supersedes` 指向同 uid 的上一条 `published` 行，并加唯一约束，
    防止并发发布让历史分叉。
  - 导入成功、写库前崩溃时，重试以相同字节和 `overwrite: True` 重新导入，结果等价。
  - `/api/ai-publish-history/` 只读 `AiChartPublication`；`ai_dashboard_approval.py:116-150` 的推导逻辑删除，旧
    `BugTrendAuditEvent` 行留在表中但不列出。
- **理由**：摘要把"人批准的内容"和"实际导入的内容"绑定，重新预览不一致时运行时直接使审批失效（D6）；独立的表让
  幂等、取代关系和失败记录都能直接查询，而不是从通用审计事件推导。
- **否决的备选**：handler 重新渲染后导入（批准的与导入的可能不同）；继续由 `BugTrendAuditEvent` 推导（没有唯一约束，
  表达不了取代和幂等）；把旧审计行迁入新表（违背不做兼容的决定）。

### 决策 9：admission 记录只认 v3，旧格式一律无效

- **决定**：
  - `request.json` 只接受 schema v3：去掉 `backend` 与 `execution_mode`，删除 v1/v2 双读
    （`app/domain/run_admission_values.py:73,88,90,118,140-142,190`）；其他版本一律 `RUN_STORAGE_INVALID`
    （错误码见 `app/domain/run_contracts.py:7-21`）。
  - 记录改为保存档案 id/version、`definition_sha256`、模型身份与运行时版本（取自 task-run 结果，D9）。
  - 切换时删除 `<archive>/projects/*/stages/*/runtime/operations/`，否则 `start()` 的恢复扫描会读到旧记录。
  - analysis attempt 与 report assist 的 wire 记录升到 schema v2 并去掉 `backend`（`services/report_assist_wire.py:32,34,45-47,55`、
    `services/summary_journal_reads.py:19-29,38-41,79`）。旧 analysis 信封沿用现有的 `AnalysisError('ANALYSIS_INVALID')`，
    旧 report assist 记录经现有的 `ValueError` 无效路径处理；都不做兼容读取。
- **理由**：不做向后兼容是 owner 决策；生产从未写出 v1 AI 记录（见 Context）；单一版本让 domain 值对象保持简单。
- **否决的备选**：保留双读并标为 legacy（与"无兼容"冲突，死代码长期存在）；写迁移脚本转换旧记录（没有需要保留的
  生产数据）；保留 `operations/` 但在扫描时跳过无效记录（每次启动都报错，并掩盖真正的存储损坏）。

### 决策 10：project_management 定义同步 task-run 端口，`ai_host` 实现并注入

- **决定**：
  - 重写已有的 `out/ai_task_contract.py` 与 `out/report_ai_task.py`，从 wire 校验器改为同步端口协议，入参和返回值都是
    project_management 自有的值类型。
  - `ai_host.task_runs.RuntimeTaskRunPort` 在 `runtime.blocking.task_runs` 上实现端口（`start(principal, request)` 调用
    `task_runs.start(principal, request, timeout=30)`）。服务进程由组合根经 `build_project_runtime(task_runs=port)` 注入，
    该函数移到 `app/api/project_runs.py`；CLI 由 `ai_host` 的 `AppConfig.ready()` 把 `local_task_run_port`（基于
    `start_blocking`）注册为 CLI 端口工厂，project_management 经 `open_local_task_run_port()` 使用。
  - 端口原样传递运行时准入错误码与 `recovery`（`profile_not_declared`、`profile_disabled`、`model_not_configured`、
    `input_schema_invalid`）；运行时未运行为 `RUN_UNAVAILABLE`，`RuntimeBusy` 为 `RUN_BUSY`。
  - 删除 AI 路径上的全部 `asyncio.run`（见 Context）；report assist 也经端口提交。
- **理由**：依赖倒置后 project_management 不导入 `ai_host` 或运行时，可以用假端口单测；blocking 门面只在工作线程调用，
  在循环线程误用会立即抛 `RuntimeUsageError`（D8），不会静默死锁；`asyncio.run` 会创建第二个事件循环，而运行时资源
  绑定在第一个循环上（D8）。
- **否决的备选**：project_management 直接调用运行时（破坏模块边界）；保留 `TaskRunClient` 走 HTTP（v2 §8 否决）；
  在 worker 中 `asyncio.run(runtime.task_runs.start(...))`（D8 禁止）。

### 决策 11：档案与记录归 Metrics 所有，删除 vendored 包与工厂

- **决定**：
  - 删除 `project_management/ai_bundle/`；新增 `project_management/ai_profiles/`，以数据保存 schema 与 instructions，经
    project_management 公共 API 暴露。
  - `ai_host.package` 把它们转换成 `TaskProfile`：`metrics.project_summary` 与 `metrics.report_authoring`，声明在
    `METRICS_APP.task_profiles`（D4）；请求使用精确的 `id@version`，不用 `latest`；Metrics 测试调用 `check_app_package`。
  - 删除 `TaskRunClient`、`AiBackendTarget`（`app/domain/summary_contracts.py:37`）、`execution_mode`、`app/api/run_factories.py`
    的工厂（`:32-45`、`_backend_resolver_from_settings` `:57`、`_client_factory_from_settings` `:85`）、
    `METRICS_PROJECT_RUNTIME_FACTORY`（`defaults_metrics.py:213`）、`METRICS_PROJECT_AI_*`（`:214-216`）、
    `METRICS_REPORT_ASSIST_FACTORY`（只在 `app/api/report_factories.py:154` 读取，从未设置）。grep gate 阻止这些名称回流
    （见 `embedded-ai-runtime-host`）。
  - 删除 `/api/ai-dashboard/` 前缀下的 14 个路由（`ui_web/urls.py:227-240`，connector 回调、sidecar 握手与探活）；
    workbench 的发布历史改读 `/api/ai-publish-history/`（决策 8）。不保留任何 HTTP 回退路径。
- **理由**：档案内容是 Metrics 的业务规格，应随 Metrics 版本化；运行时只负责执行、准入和审计（D4、D9）。工厂和执行模式
  是 sidecar 时代的替换点，现在只有一种组合。
- **否决的备选**：继续 vendor AI Base 的 task pack（版本脱节，且依赖 D4 已删除的 `pack.py`/`ScopeGrant`）；把 schema 放在
  `ai_host` 内（project_management 就无法在不导入 `ai_host` 的前提下校验自己的输入输出）。

### 决策 12：状态目录与单进程锁

- **决定**：运行时状态目录固定为 `METRICS_STATE_DIR/ai-base`（Q8；`METRICS_STATE_DIR` 见 `defaults_metrics.py:44`），
  不可单独配置；`running()` 持有 `state_dir/.runtime.lock`。服务进程持锁时，`project_run --execute-local`（现流程见
  `management/commands/project_run.py:84-98`）经 `start_blocking` 得到 `RuntimeBusy`，映射为 `RUN_BUSY` 并提示通过服务
  提交，不等待、不换目录。进程内的 project run 注册表（`project_management/runtime.py:178-193`）只由组合根安装。
- **理由**：运行时状态与数据库位于同一个可备份的根目录下；锁让单进程前提可检查（D8），避免两个运行时实例同时写审批
  和会话。
- **否决的备选**：独立的 `METRICS_AI_STATE_DIR`（多一个需要备份和对齐的位置）；CLI 等待锁（可能无限期阻塞）；CLI 改用
  临时目录（审批与运行记录分裂）。

### 决策 13：launcher、启动入口与进程审计只认 Metrics 与外部模型端点

- **决定**：
  - `scripts/dashboard_runtime_instance_profile.py` 删除 ai-base backend/frontend 端口与绑定（`:29-30,105-114`）
    以及 `METRICS_AI_BASE_URL`、`METRICS_AI_BASE_FRONTEND_URL` 两行（`:264-265`）；保留外部 LiteLLM 端口 4000
    （`:31,117-120`，launcher 不启动它），把未被读取的 `METRICS_EXTERNAL_LITELLM_URL`（`:266`）改为输出
    `METRICS_AI_MODEL_BASE_URL`；`SCHEMA_VERSION`（`:23`，写入 `:130`）加一，旧 profile 由 `:223-224` 直接拒绝。
  - 所有启动入口改用 `manage.py serve`：`scripts/e2e_dashboard_ai_stack.ps1` 只启动或检测 Metrics 与 Grafana，不启动、
    停止或探测任何 AI Base 进程；`scripts/e2e_bug_trend.services.json`、`scripts/local_start_backend.ps1` 与
    `scripts/validation/project_ui_fixture.py` 的 manifest 命令同样改为 `serve`。
  - 进程与启动日志审计（`scripts/audit_stack_process_inventory.py`、`scripts/audit_stack_boot_logs.py`）按 `serve`
    识别 Metrics 服务，删除 AI Base 的盘点与状态检查。
- **理由**：只剩一个服务进程，launcher 不再分配、探活第二个服务；模型端点仍是外部服务，需要告诉 Metrics 它在哪里。
  启动方式只有 `serve` 一种（决策 3），入口与审计都按它识别，否则审计会把正常的单进程部署报告为缺少 AI Base。
- **否决的备选**：保留 ai-base 端口但不用（死配置误导运维）；兼容读取旧 profile（违背不做兼容）；审计脚本同时识别
  `runserver` 与 `serve`（`runserver` 不经 lifespan，不是支持的启动方式）。

### 决策 14：宿主 SPI 的认证、审批与审计

- **决定**：
  - `authenticate`：从 `BasicAuthMiddleware`（`metrics/middleware.py:10-62`）抽出纯函数 `check_basic_authorization`，
    中间件与 `MetricsHost` 共用；未配置 Basic 用户时返回匿名的 `local_operator`，认证失败返回 `None`（401）。
  - `HostConfig` 中"允许匿名 principal 决定审批"（字段名由 AIB-2 确定，见 Open Questions 4）只在 development settings
    中以常量打开，不读环境变量（Q5）；`can_decide` 返回真，匿名与模型的拒绝由运行时完成。`manage.py` 默认使用 production
    settings（`manage.py:9`），所以发布审批至少需要一个 Basic 用户（`METRICS_BASIC_AUTH_USERS`）；没有时 AI pane 提示
    配置，read tool 照常可用。
  - 审计分两处：`record_audit` 经决策 4 的 helper 把会话、tool 调用与审批事件写入 `ai_host` 自有的只追加审计表，不写
    `BugTrendAuditEvent`；运行时交来的认证失败事件不写数据库，只输出一条结构化日志 `ai_auth_failed`（path、客户端地址、
    原因，不含凭据）。
  - `HostConfig` 的允许 Host 取自 Django `ALLOWED_HOSTS`（默认只有回环，`defaults.py:21`）；挂载路径、状态目录、模型
    凭据与 `NetworkPolicy` 都由 `ai_host.settings` 生成。静态文件由 WhiteNoise 在 `CommonMiddleware` 之前返回，不经
    Host 校验（决策 1，与现状相同）；静态资源公开且不含用户数据，予以豁免。
- **理由**：同一请求在 Django 和运行时两侧的认证结果必须一致（见 `embedded-ai-runtime-host`）；审批权限是安全控制，
  不能被环境变量打开（v2 §8.5）；运行时的会话、tool 和审批事件与 bug_metrics 的业务审计语义不同。认证失败可由未认证
  的请求无限触发，写入数据库会让审计表无限增长，并在 SQLite 上争用写锁；结构化日志足以排查。
- **否决的备选**：运行时自己做认证（与 Django 不一致）；用环境变量开启匿名审批；把运行时审计写进
  `BugTrendAuditEvent`（混淆业务审计，且该表不归 `ai_host`）；认证失败写入审计表（理由见上）。

### 决策 15：验证只替换外部系统，不替换组合

- **决定**：
  - 全栈验证 = `manage.py serve` + 确定性的 OpenAI 兼容假模型服务，后者复用 `scripts/validation/project_full_stack_base.py`
    中 `ExactDynamicVectorExecutor`（`:134`）的向量匹配。
  - Jira 由一个只用于验证的 AppConfig 安装进程内 fixture transport（沿用 `scripts/validation/project_ui_fixture_app.py`
    的模式）：provider 端点必须是 https（`bug_metrics/provider_connections/normalization.py:103-104`），回环 http 假 Jira
    不可行。该 AppConfig 不得导入 `ai_host` 或 `project_management.runtime`；周完成视图的假对象
    （`scripts/validation/project_week_fixture.py:44-45`）移入其中。
  - 删除并行组合：`scripts/validation/project_full_stack_settings.py:76-80`、`project_week_settings.py:12-16`、
    `project_full_stack_fixture.py:108-148`；同步改写 `project_sdk_join*.py`、`profile_report_*.py`、
    `prepare_report_scale.py`、`project_management/tests/test_project_full_stack_*.py` 与 `test_project_week_fixture.py`；
    启动入口与审计脚本的改写见决策 13。
  - 单元与对话测试用 testkit 的脚本化模型和 `RuntimeHarness`；Metrics CI 运行宿主一致性套件、`check_app_package`、
    导入规则与 grep gate（见 `embedded-ai-runtime-host`）。
- **理由**：组合本身是本变更最大的风险，验证必须走生产组合根；不确定性只来自外部系统，替换它们即可得到可重复的结果。
- **否决的备选**：验证 settings 注入假的 project runtime 工厂（正是要删除的并行组合）；放宽 https 规则以使用回环假 Jira
  （削弱生产校验）；对话测试连接真实模型（不确定、不可重复）。

### 决策 16：Docker 镜像以单进程 `serve` 运行

- **决定**：
  - `ops/docker/Dockerfile` 删除 `GUNICORN_*` 环境变量（`:27-34`），`CMD` 改为 exec 形式
    `["python", "manage.py", "serve", "--host", "0.0.0.0", "--port", "8000"]`；`collectstatic` 与 production settings 不变。
  - exec 形式让 Python 成为 PID 1，uvicorn 在主线程捕获 SIGTERM，走正常的 lifespan 关闭（决策 2），`run()` 正常返回
    （决策 3）。Docker 默认 10 秒后发送 SIGKILL；停止预算 660 秒 = 连接排空 10（`timeout_graceful_shutdown`）+
    `project_runs.stop` 620 + 运行时停止与余量 30，所以 README 要求 `docker run --stop-timeout 660`（Compose 用
    `stop_grace_period: 660s`）；被提前杀死时，中断的运行由下次 `start()` 的恢复标记出来，不会静默丢失。
  - 只允许一个副本：`METRICS_STATE_DIR`（镜像内为 `/metrics/state`）挂载为卷，数据库与 `ai-base/` 状态目录随卷持久化；
    第二个副本挂载同一个卷时，`running()` 抛 `RuntimeBusy`，`serve` 以错误码退出（决策 3）。
  - README 的 Docker 快速上手与 "Production Setup"（`README.md:100-139,556-577`）改为上述命令、卷与停止超时，并写明
    单副本、非回环绑定的匿名姿态（决策 3）、production settings 下发布审批至少需要一个 Basic 用户（决策 14），以及配置
    `ALLOWED_HOSTS` 与由反向代理终止 TLS 的建议。
- **理由**：容器与本地使用同一个组合根和同一条启动命令（决策 1、3）；状态目录锁决定了只能有一个进程，这也是 gunicorn
  多 worker 不再可行的原因。
- **否决的备选**：gunicorn 加 uvicorn worker 跑多个 worker（只有第一个 worker 能拿到状态目录锁，其余无法启动）；gunicorn
  加单个 uvicorn worker（多一层进程管理，信号与停止超时另由 gunicorn 决定，启动方式不再唯一）；保留 WSGI 镜像（生产
  没有运行时，AI 不可用，并形成第二个组合根）。

## Risks / Trade-offs

- [运行时阻塞、崩溃或内存泄漏会直接拖垮 Metrics 页面] → `RuntimeLimits` 限制并发、单次运行与 tool 超时、输出大小；
  slow callback 门禁与宿主一致性套件；运行时异常只以 API 错误返回（v2 §6、D8）。
- [两套依赖进入同一个 venv 后冲突] → 单一 requirements；S0 用 `pip check` 验证；`ai-base-runtime`、`uvicorn`、`starlette`
  精确固定。
- [发布耦合：AIB-2 与 MDB-2 必须同版本，回滚也要一起回滚] → 精确版本固定；宿主一致性套件是升级门禁；回滚按
  Migration Plan 整体恢复。
- [blocking 门面误用或 `asyncio.run` 回流导致死锁] → 在循环线程调用门面立即 `RuntimeUsageError`；残留 gate 用 AST 检查
  `services/report_assists.py`、`services/project_run_worker.py` 与 `ai_host/` 中没有 `asyncio.run`；lifespan 中的阻塞调用
  全部经 `asyncio.to_thread`。
- [project run 在 620 秒内没有停下] → `RuntimeStopResult.unresolved` 记录未停止的操作，`serve` 非零退出；下次
  `start()` 的恢复把中断的运行标记出来，不会静默丢失。
- [导入成功、写库前崩溃导致重复导入] → 相同字节加 `overwrite: True` 使重导入等价；`tool_call_id` 唯一约束保证只记一行。
- [preview 不确定导致审批总被判为 invalidated] → `check_app_package` 断言两次 preview 摘要相同；preview 不读取当前时间、
  随机数等易变输入。
- [`thread_sensitive=False` 下多线程并发写 SQLite] → 与现在多线程 `project_serve` 的并发面相同；写入保持短事务；
  `AiChartPublication` 的唯一约束兜住并发发布。
- [工作线程持有失效的数据库连接] → helper 在调用前后执行 `close_old_connections()`。
- [切换时删除 `runtime/operations/`、旧格式被拒，操作不可逆] → 数据库、状态目录、archive root 三者在停机状态下一起备份，
  回滚以文件恢复为准。
- [匿名审批被误开] → 只在 development settings 中以常量打开；一致性套件断言 production settings 下匿名 principal 不能决定。
- [production settings 下没有配置 Basic 用户时，没有人能批准发布] → AI pane 提示配置 `METRICS_BASIC_AUTH_USERS`，read tool
  照常可用；README 与 onboarding 写明这一要求（决策 14）。
- [不认证的部署下，审计表随任何能访问端口的人的使用而增长] → 只记录会话、tool 与审批事件，认证失败只写日志，增长与实际
  使用成正比；`RuntimeLimits` 限制并发；保留与清理策略不在本 change 范围内。
- [关闭时打开的 SSE 或聊天流让停止无限等待] → `timeout_graceful_shutdown=10` 到期后取消连接任务，lifespan 照常关闭；
  0.5 的 S0 与 5.6 的命令测试都验证这一点。
- [WSGI 改 ASGI 后页面变慢] → S0 门槛：主要页面 p95 比 `project_serve` 基线劣化不超过 20%；S0 跑 Metrics 浏览器测试子集。
- [Docker 从 5 worker × 10 线程的 gunicorn 改为单进程，峰值吞吐下降] → Django 6.0.7 的 ASGI handler 为每个请求建立
  `ThreadSensitiveContext`（`django/core/handlers/asgi.py:169`），同步视图仍按请求在各自线程中并发，I/O 等待不受影响，
  只有 CPU 密集的渲染受 GIL 限制；Metrics 是团队内部看板，页面读取本地聚合；S0 在镜像中记录并发数据供 owner 参考，
  不作为退出条件。
- [非回环绑定且未配置 Basic 用户时，能访问该端口的任何人都能匿名使用页面与 AI 对话] → owner 决定维持现有姿态；`serve`
  输出警告；development settings 下拒绝非回环绑定；production settings 下匿名 principal 不能决定审批（Q5）；README
  建议配置 Basic 用户并由反向代理终止 TLS。
- [模型凭据与 Jira PAT 位于同一进程内存] → 与现状等价（两个进程本来以同一 OS 用户运行）；凭据用 `SecretStr`，日志脱敏。
- [`runserver` 仍可启动但没有 AI] → AI pane 明确显示 `not_running` 并提示用 `manage.py serve` 启动；文档只写 `serve`。

## Migration Plan

前置条件：AIB-0 已发布并通过现有 launcher 端到端流程；S0 的全部退出条件通过；AIB-2 wheel 已发布，Metrics 已精确固定其
版本并通过宿主一致性套件。

切换步骤（一次完成，不设并行期）：

1. 给当前部署的提交打 git tag 并保留对应镜像；停止旧 `project_serve`、AI Base sidecar（backend、frontend）与 gunicorn
   容器，确认没有进程再写数据库或 archive。
2. 停机状态下把三者作为一个单元备份，并记录同一个时间戳：
   - SQLite 数据库：`METRICS_SQLITE_DATABASE_PATH`，默认 `METRICS_STATE_DIR/db.sqlite3`（`defaults_metrics.py:46-47`）；
   - 整个 `METRICS_STATE_DIR`（`:44`），其中包括默认的 provider 机密目录（`:135`），切换后还会包含 `ai-base/`；
   - archive root：`METRICS_PROJECT_ARCHIVE_ROOT`（`:201`，默认为空，此时没有 archive 需要备份）。
3. 安装新版本代码与精确固定的依赖（不再安装 `requirements-ai-task.txt` 与 gunicorn；Docker 部署重新构建镜像），运行
   `manage.py migrate`，创建 `AiChartPublication` 与 `ai_host` 审计表。
4. 删除 `<archive>/projects/*/stages/*/runtime/operations/`。
5. 部署环境中删除 `METRICS_AI_SIDECAR_ENABLED`、`METRICS_AI_BASE_*`、`METRICS_PROJECT_AI_*`、`METRICS_PROJECT_RUNTIME_FACTORY`
   与 `GUNICORN_*`，设置 `METRICS_AI_MODEL_BASE_URL`、`_NAME`、`_API_KEY`；用新 `SCHEMA_VERSION` 重新生成 launcher profile。
6. 本地运行 `manage.py serve --host 127.0.0.1 --port <port>`；Docker 以单副本运行新镜像，`METRICS_STATE_DIR` 挂载为卷，
   `--stop-timeout 660`（决策 16）。冒烟检查：
   - `<prefix>/ai/api/health` 报告运行中；AI pane 为 `ready`（未配模型时为预期的 `not_configured`）；
   - Jira-first 工作台正常加载，切换 range 后仍是同一会话；
   - 一次发布审批后 `AiChartPublication` 出现 `published` 行，`/api/ai-publish-history/` 列出它；
   - 服务运行时执行 `project_run --execute-local` 立即得到 `RUN_BUSY`。

数据说明：

- 生产从未写出 v1 AI 记录（没有生产 project run 组合），因此没有数据转换步骤；验证或开发环境中的旧格式记录读取时一律
  `RUN_STORAGE_INVALID`（analysis 记录为 `ANALYSIS_INVALID`），不做兼容。
- 旧 `BugTrendAuditEvent` 发布行保留在表中，但不出现在新发布列表；dashboard_query_agent 的旧状态不迁移（Q8）。

回滚（文件恢复，不做反向迁移）：

1. 停止 `manage.py serve`。
2. 用步骤 2 的同一份备份覆盖恢复数据库、`METRICS_STATE_DIR` 与 archive root；三者必须一起恢复，单独恢复任一项都会让
   数据库与 archive 不一致。
3. 检出步骤 1 的 git tag，重新安装该版本的依赖（Docker 部署使用该 tag 对应的镜像），恢复旧的环境变量与 launcher
   profile，启动旧 `project_serve` 与 sidecar。
4. 切换期间新产生的会话、审批和发布记录随恢复一起丢弃；已导入 Grafana 的 dashboard 不回退，需要时由操作者手动处理。

## Open Questions

以下问题可以在实施期间回答，不改变 spec、方案或任务拆分；Q1–Q9 与 D4/D5/D6/D7/D9 已定，不在此列。

1. S0 结果：任一退出条件不通过就停止 AIB-2，带证据回到 owner 决策；本设计不预置备选方案。
2. AIB-2 的精确版本号、wheel 摘要，以及 S0 确定的 portalocker 精确版本，发布时写入 requirements。
3. AIB-2 的 `session_key` 校验是否与 v2 D7 一致（字符集 `[A-Za-z0-9._:-]`，总长不超过 200）。`metrics.workbench.` 加
   profile id（`[a-z0-9][a-z0-9._-]{0,159}`）最长 178 个字符且只含允许的字符，由 0.6 确认；不一致时回到 v2 修正，
   `ai_host` 不做编码。
4. AIB-2 中 task run 查询与取消的同步方法名（v2 只给出 `task_runs.start(principal, request, timeout=30)`）、
   `HostConfig` 中"允许匿名 principal 决定审批"的字段名，以及 `ctx.approval` 中 preview、preview 摘要与 `decided_by`
   的确切名称，由 0.6 记录。差异只影响 `RuntimeTaskRunPort`、`ai_host.settings` 与发布 tool 内部，project_management
   的端口不变。

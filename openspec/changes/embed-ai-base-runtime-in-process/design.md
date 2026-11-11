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
- owner 于 2026-11-11 根据 S0 结果（`s0-spike-report.md`，C5 不通过）选择方向 1：Django 保持线程化 WSGI；运行时经
  `start_blocking` 运行在自己的专用循环线程上；`/ai` 经运行时的 WSGI 适配器（v2.1 H7）进入同一循环。本文已按方向 1
  改写；标注【待 S0b】的项（HTTP server、静态文件设置、线程数与 `/ai` 在途上限、第一段停止时限、精确版本）由 S0b
  结论填充（tasks 0.5），填充前不得据以实施。本设计依赖上游 v2.1 的 Q10（运行时提供同步宿主托管：`start_blocking`
  句柄、两段式停止、心跳与核心 wheel 中的 WSGI 适配器），由 owner 随 v2.1 定稿签署；Q10 不获签署时回到 owner 重新决策。
- 本设计只使用上游提案 v2.1 定义的运行时 API：`start_blocking` 及其返回的句柄（`runtime.blocking` 同步门面，含
  `chat` 与 `task_runs`；第一段停止；WSGI 适配器，v2.1 H2/H6/H7）、`runtime.ui.asset_url`、
  `ai_base_runtime.spi/apps/contracts/testkit`。句柄方法与适配器配置的最终名称以 AIB-2 的接口回执为准（tasks 0.6，Q4）。
- 发布顺序：AIB-0（AI Base 热修）→ S0 共装 spike（不通过）→ S0b（方向 1）→ 上游提案 v2.1 → AIB-2 与 MDB-2
  同版本发布（v2 §9）。

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

- 一个进程、一个组合根：`manage.py serve` 以线程化 WSGI 托管 Django，运行时在同一进程的专用循环线程上运行，`/ai`
  经运行时的 WSGI 适配器进入；`manage.py serve` 是唯一受支持的启动方式。
- 运行时只经新 Django app `ai_host` 进入 Metrics；project_management 只依赖自己定义的同步端口；domain 保持纯 Python。
- project run 与 report assist 经 task-run 端口、以提交用户身份在真实模型上执行，记录只有一个版本。
- 发布审批绑定确定性预览摘要，发布结果写入 Metrics 自有的 `AiChartPublication`。
- 验证只替换外部系统（模型、Jira），组合根与生产完全相同。
- 一次切换完成：HTTP 集成与兼容读取全部删除，数据库、状态目录、archive root 作为一个单元备份和回滚。

**Non-Goals:**

- 多 worker、reload、多进程共享状态目录（v2 §8.9）。
- 用 ASGI server 托管 Django（S0 C5：主要页面 p95 超过线程化 WSGI 基线 1.2 倍的门槛）。
- 任何向后兼容：旧 admission/wire 记录不读取、`runtime/operations/` 不迁移、旧 `BugTrendAuditEvent` 发布行不进入新发布列表。
- 迁移 dashboard_query_agent 的旧会话与外壳状态（Q8）。
- 在 Metrics 中重做运行时已有的能力：审批 UI、会话存储、模型管线、task-run 准入；Metrics 不提供 AI 开关。
- 任何过渡层：HTTP sidecar、connector 路由、BFF、双通道并行（v2 §8.1）。
- AIB-2 自身的设计与 AI Base 仓库的改动。

## Decisions

### 决策 1：`manage.py serve` 是唯一组合根，`ai_host` 是唯一导入运行时的模块

- **决定**：
  - 组合根是 `ai_host` 的 `serve` 命令与 `wiring.py`：`manage.py` 完成 `django.setup()`（默认
    `metrics.settings.production`，`manage.py:9`）之后，`serve` 构造运行时、WSGI 应用与 HTTP server，并持有整个生命周期
    （决策 2、3）。删除 `metrics/asgi.py`、`metrics/wsgi.py` 与 `WSGI_APPLICATION`（`defaults.py:85`）。`runserver` 与
    Django test client 仍能渲染页面（`WSGI_APPLICATION` 为空时 Django 回退到 `get_wsgi_application()`），此时 AI pane
    为 `not_running`。
  - 新 Django app `ai_host`（加入 `INSTALLED_APPS`）：`wiring.py`（WSGI 分派、生命周期、CLI 端口工厂）、`host.py`（宿主 SPI）、
    `package.py`（`METRICS_APP`）、`settings.py`、`state.py`（生命周期对象）、`task_runs.py`、`tools/`、`models.py`（审计表）、
    `management/commands/serve.py`。
  - `wiring.build_wsgi_application(django_app, ai_app)` 返回一个 WSGI 分派函数，按 `PATH_INFO` 分三路。挂载路径（Q7）为
    `/` 加规范化的 `METRICS_BASE_URL` 再加 `ai`，规范化规则与页面路由前缀相同（`ui_web/urls.py:93` 经
    `ui_web/utils/url_utils.py:4`：去掉首尾 `/`，非空时补一个 `/`）：为空或 `/` 时是 `/ai`，为 `/metrics/` 或 `metrics`
    时是 `/metrics/ai`。
    - 等于挂载路径时返回 308，`Location` 为挂载路径加 `/`，保留查询串；
    - 以挂载路径加 `/` 开头时交给运行时的 WSGI 适配器（v2.1 H7）：`SCRIPT_NAME` 追加挂载路径，`PATH_INFO` 为余下部分，
      请求头、Host、客户端地址与 scheme 原样传递；认证与 Host 校验由运行时经宿主 SPI 完成（决策 14）；
    - 其余交给 Django 的 `get_wsgi_application()`，页面请求路径与现在相同。
  - 静态文件只由中间件链中的 WhiteNoise 提供（`defaults.py:52-55`，位于 `BasicAuthMiddleware` 之后，与现在的 gunicorn
    镜像相同），并设置 `WHITENOISE_USE_FINDERS = True`，让没有运行 `collectstatic` 的本地进程也能提供静态文件；
    `WHITENOISE_AUTOREFRESH`【待 S0b】。不再使用 `project_serve.py:50` 的 `StaticFilesHandler`。Django 6 已不读取
    `STATICFILES_STORAGE`（`defaults.py:147`），实际生效的是不带哈希的 `StaticFilesStorage`，finders 与 `STATIC_ROOT`
    中的文件名一致。
  - HTTP server 为【待 S0b】，必须接受 `serve` 预先绑定的监听 socket（决策 2 第 1 步）。线程数与 `/ai` 在途上限在
    `ai_host.settings` 中显式设置：流式请求与其他 `/ai` 请求分开限额，两者之和小于线程数，页面始终至少保留【待 S0b】
    个线程；超过各自上限的 `/ai` 请求立即得到 503 和 `Retry-After`，不排队（v2.1 H7）。流占满自己的限额时，其他
    `/ai` 请求与页面照常处理。
  - 导入规则测试（import-linter 或等价 gate）：只有 `ai_host` 导入 `ai_base_runtime` 与所选 HTTP server；任何模块不导入
    `ai_base_runtime._internal` 或 AI Base 的 `app.*`；project_management 不导入 `ai_host`；各模块 `app/domain/` 不导入
    Django、asgiref 与运行时。
  - 依赖：精确固定 `ai-base-runtime` 与所选 HTTP server；`uvicorn`、`starlette` 不是 Metrics 的直接依赖；删除 `gunicorn`、
    `ai-base-application-sdk` 与 `requirements-ai-task.txt`；portalocker 升到 4.4.2（S0 确定）。
- **理由**：
  - S0 实测：Django 在 ASGI 下每个请求（包括每个静态资源）都要新建线程上下文与执行器，主要页面 p95 是线程化 WSGI
    基线的 1.82–3.23 倍，不挂运行时的 uvicorn 组合同样超标（`s0-spike-report.md` §2.4）。保持 WSGI，页面请求路径与
    基线相同。
  - 开发、验证、生产走同一条装配路径；运行时 API 面收敛在一个 app，升级只改一处；边界可由 gate 机器检查（见
    `embedded-ai-runtime-host`）。
  - 生命周期由 `serve` 显式控制，不依赖任何 server 的 lifespan 或信号语义；换 server 只影响决策 3 中的启停调用。
  - 静态文件只走一条路径：在中间件链之外提供静态文件会绕过 Basic 认证，配置了 Basic 用户的镜像会因此公开静态文件。
  - WSGI server 的线程池是固定的，每个 `/ai` 在途请求（包括整条流）占用一个线程；在途上限保证页面始终有线程可用。
    流与其他 `/ai` 请求分开限额，长时间打开的流不会挤掉审批、会话列表等短请求。
- **否决的备选**：
  - uvicorn 同时托管 Django ASGI 与运行时（S0 C5 不通过）；uvicorn 托管运行时、Django 经 Starlette `WSGIMiddleware`
    挂入：S0 测过两种静态文件姿态，`composed_wsgi` 的 p95 比值 seq 1.40–2.15、c4 1.85–2.38，`composed_sf_wsgi` seq
    1.25–1.93、c4 1.55–1.73，都是 0/12 达标（`s0-spike-report.md:82,118,122`）；Granian（WSGI 模式在独立的 worker
    进程中运行应用，`serve` 无法在同一进程内控制生命周期）；gunicorn（不支持 Windows，多 worker 与状态目录锁冲突，
    见决策 16）。
  - 由 Django 视图代理 `/ai`：同样需要线程与循环之间的桥接，另加一层 Django 响应处理（流要么被缓冲，要么被改写），
    POST 还要豁免 CSRF。
  - 通用桥接库 a2wsgi 1.10.10：跨线程等待没有上限（`a2wsgi/asgi.py:214` 的 `run_coroutine_threadsafe(...).result()`、
    `:69,230` 的 `SyncEvent.wait()`）；响应生成器的 `yield`（`:248,269,303`）不在 try/finally 中，WSGI `close()` 时
    既不发送 `http.disconnect`，也不取消 ASGI task。S0 测的是 Starlette `WSGIMiddleware`，没有安装 a2wsgi
    （`s0-spike-report.md:127`）。
  - 在 `AppConfig.ready()` 构造运行时（migrate、测试、CLI 等所有加载 Django 的进程都会争抢状态目录锁）；保留
    `metrics/wsgi.py` 作备用入口（第二个组合根，永远不启动运行时）；在中间件链之外提供静态文件（见理由）。

### 决策 2：生命周期与 project run（v2.1 §5.1）

- **决定**：`serve` 的主线程只做生命周期控制，严格按以下顺序：
  1. 按决策 3 的规则检查地址后，由 `ai_host` 自建监听 socket 并交给所选 server（例如 waitress 的 `sockets` 参数）：
     Windows 设置 `SO_EXCLUSIVEADDRUSE`，POSIX 设置 `SO_REUSEADDR`，然后 bind 与 listen；端口被占用时 2 秒内以
     `serve bind failed.` 非零退出，不启动运行时。
  2. `with start_blocking(build_settings(), host=MetricsHost(), apps=[METRICS_APP]) as runtime:`：运行时在自己的专用线程上
     创建事件循环（Windows 上为 Proactor）并进入 `running()`，获取状态目录锁；`RuntimeBusy`、无效设置等启动异常传回
     主线程（v2.1 H6）。
  3. `attach(runtime)`，供 WSGI 分派、`ai_host` 视图与 AI pane 状态读取。
  4. `port = RuntimeTaskRunPort(runtime.blocking.task_runs)`。
  5. `project_runs = build_project_runtime(task_runs=port)`，`install_project_runtime(project_runs)`，`project_runs.start()`，
     都在主线程上直接调用。
  6. 在 `serve-http` 线程中开始受理请求；主线程以不超过 0.5 秒的间隔检查停止事件（决策 3）与运行时的结束事件
     （v2.1 H6）。运行时在运行期意外结束时，生命周期对象进入 `failed` 并记录错误码，`serve` 输出
     `serve runtime failed (<code>).`，执行第 7 步后以非零退出。
  7. 停止，在 `finally` 中按序执行；任一步的异常记入生命周期对象，不跳过后续步骤：
     1. 停止受理新连接；
     2. 运行时第一段停止（v2.1 H2）：新的 `/ai` 请求得到 503，打开的流发送终止事件后结束，时限【待 S0b】；task run 与
        blocking 门面照常工作；
     3. 排空进行中的请求：从第 1 步算起，与第一段停止合计最长 10 秒，到期后关闭剩余连接，然后 join `serve-http` 线程；
     4. `project_runs.stop(620)`，随后立即向 stdout 写一行 `project_runtime_stopped` 事件（格式同
        `project_serve.py:86-93`；`stop` 抛错时按 `RuntimeStopResult(False, None, ())` 输出，同 `:69-75`）；
     5. `clear_project_runtime(project_runs)`，`detach()`；
     6. 离开 `start_blocking`：运行时第二段停止，取消未完成的运行并标记中断，时限 30 秒，结果记入生命周期对象。
  - 第 7 步（包括第 6 步发现运行时结束后的退出路径）中的每一次等待都按不超过 0.5 秒分片：排空后的 join、
    `project_runs.stop` 内的 join、离开 `start_blocking` 时的 join。`ProjectRunRuntime.stop`
    （`project_management/runtime.py:75` 是一次 `join(timeout_seconds)`）改为分片 join，总时限不变。
  - 视图与 WSGI 分派在每个请求开始时从生命周期对象取一次运行时句柄，此后不再读取。`detach()` 之后仍持有旧句柄的
    请求在第二段停止之前照常完成；第二段停止之后门面立即抛运行时未运行的异常（v2.1 H6），视图按 `not_running`
    渲染，不返回 500。server 的工作线程是 daemon 线程，强制退出不等待它们。
  - 第 2–6 步中任一步失败时，已完成的步骤按第 7 步的对应部分逆序清理，然后按决策 3 输出启动失败。
  - `ai_host.state` 中只有一个生命周期对象，保存阶段（starting/running/stopping/stopped/failed）、启动或清理的错误码
    （异常的 `code` 属性，取法同 `project_serve.py:95-98`）、`project_runs.stop` 返回的 `RuntimeStopResult` 与运行时的
    停止结果。`serve` 与 AI pane 只读这个对象。
- **理由**：
  - 先绑定再启动：端口冲突在 2 秒内失败，不获取状态目录锁，也不触发 project run 的恢复扫描。
  - 自建 socket：Windows 上 `SO_REUSEADDR` 的语义是强制绑定已被占用的端口，server 自己设置它时端口被占用也不报错；
    不设置 `SO_EXCLUSIVEADDRUSE` 时，其他进程可以借 `SO_REUSEADDR` 绑定同一端口并截走连接。独占绑定因此不能依赖
    各 server 的默认选项。
  - 分片等待：Windows 上 `Thread.join(timeout)` 的等待可能不被信号打断，处理器要等 join 返回后才执行（CPython 3.13
    的实际行为由 S0b 测量，见 tasks 0.5）。一次长 join 会让第二次信号推迟到 join 返回才生效；分片后最迟一个分片即
    生效，与解释器版本无关。
  - 主线程上没有事件循环：`ProjectRunRuntime.start()`（`project_management/runtime.py:39-43`）中访问 ORM 的
    `reconcile_interrupted()`（`services/project_run_recovery.py:17-29`）与 `stop()` 中的线程等待都可以直接调用；worker
    经 blocking 门面调用运行时，由运行时的循环线程推进，不会死锁。
  - 第一段停止先于排空：每条打开的流占用一个 server 线程，不先结束流，排空就要等到时限。
  - 先停 worker、后完整停止运行时：第一段停止不影响 blocking 门面，worker 的最后一次调用仍有运行中的运行时。
  - 620 秒 = `RunPolicy.timeout_seconds` 600（`app/domain/run_contracts.py:33`）加宽限，等于 `project_serve.py:70`。
  - Proactor 由 `start_blocking` 保证（v2 D8、v2.1 H6）并由宿主一致性套件断言，Metrics 不再自定检查与错误码。
- **否决的备选**：在 `AppConfig.ready()` 启动 worker（非服务进程也会启动）；HTTP server 占用主线程（停止顺序只能放进
  server 的回调或另一个线程，各 server 的回调语义不同，而信号处理器只在主线程执行）；先排空再做第一段停止（见理由）；
  在运行时的循环线程上启停 project run（`start()` 访问 ORM，`stop()` 等待的 worker 正需要这个循环推进）。

### 决策 3：`manage.py serve` 取代 `project_serve`

- **决定**：
  - 新命令 `ai_host/management/commands/serve.py`；删除 `project_serve` 及 `project_management/tests/test_project_serve_command.py`。
  - 地址：`--host` 默认 `127.0.0.1`。回环判定为 `host == "localhost"` 或 `ipaddress.ip_address(host).is_loopback`，
    无法解析为 IP 的主机名按非回环处理（取代 `project_serve.py:30` 的固定集合）。非回环绑定（如容器内的 `0.0.0.0`）
    按 owner 决定允许，另有两条规则：settings 允许匿名决定审批（只有 development settings，决策 14）时以
    `CommandError` 拒绝，避免匿名审批暴露到网络；未配置 Basic 用户时输出一条 `serve_anonymous_network_bind`
    警告，只含绑定地址。
  - 不提供 workers、reload 或线程数参数：单进程、单副本（v2 §8.9），线程数与在途上限只来自 settings（决策 1）。
  - 停止触发：SIGINT（Ctrl+C）、SIGTERM，以及保留的 `--stop-file`（绝对路径）与 `--lifetime-seconds`
    （`project_serve.py:24-25,117-130`）。`serve` 在主线程为 SIGINT、SIGTERM 安装处理器，处理器只设置停止事件；监视线程
    在文件出现或到期时设置同一个事件；主线程按决策 2 第 6 步的间隔检查该事件，然后执行决策 2 第 7 步。停止期间再次
    收到 SIGINT 或 SIGTERM 时输出 `serve forced exit.`，经 `os._exit` 在 1 秒内以非零退出（依赖决策 2 的分片等待），
    中断的运行由下次 `start()` 的恢复标记出来。
  - 输出与退出码，只输出错误码，不输出异常消息或 traceback：
    - 绑定失败：`serve bind failed.`；
    - 运行时或 project run 启动失败：`serve startup failed (<code>).`；
    - 运行时在运行期意外结束：`serve runtime failed (<code>).`（决策 2 第 6 步）；
    - 停止后未干净结束（`stopped` 为假或 `unresolved` 非空、运行时停止超时，或有清理错误码）：`serve cleanup failed.`，
      有错误码时附带；
    - 以上都非零退出；否则退出码为 0。
  - `project_runtime_stopped` 事件格式不变，仍由 `scripts/validation/project_full_stack_identity.py:304` 消费。
  - 所选 HTTP server 必须接受预先绑定的 socket；它的开始受理、停止受理与排空调用【待 S0b】。
- **理由**：
  - 错误输出只含错误码，沿用 `project_serve.py:95-98` 不泄露细节的约定；停止事件与停止参数保留，现有验证断言不变。
  - Windows 父进程无法可靠地向子进程发送 Ctrl+C，验证脚本依赖 `--stop-file` 与 `--lifetime-seconds`。
  - 信号处理器由宿主安装，运行时核心不触碰信号（v2 D2、v2.1 H8）；停止顺序不依赖 server 的信号处理。Docker 中 Python
    是 PID 1，内核不向 PID 1 投递默认处理的 SIGTERM，不安装处理器时 `docker stop` 只能等到 SIGKILL（决策 16）。
- **否决的备选**：把 `runserver` 作为支持的方式（不启动运行时，默认的自动重载会派生子进程）；用 server 自带的命令行
  入口启动（无法做绑定规则、读错误码、控制停止顺序）；一律拒绝非回环绑定（容器无法部署）；非回环绑定强制 Basic 认证
  （owner 选择维持现有姿态）。

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
  - pane 状态由生命周期对象和设置推导：生命周期对象不在 `running` 阶段（未经 `serve` 启动，或已开始停止）为
    `not_running`，缺模型为 `not_configured`，否则为 `ready`。scope binding 未解析的诊断与运行时就绪状态分开显示（见
    `unified-metrics-workbench-ui`）。
  - 删除 `METRICS_AI_SIDECAR_ENABLED` 与 `METRICS_AI_BASE_*`（`defaults_metrics.py:149-156`），不提供 AI 开关。
- **理由**：模型凭据与 `METRICS_AI_GRAFANA_PASSWORD` 一样经环境变量注入，沿用现有机密姿态；"模型是否已配置"
  只由 `ai_host.settings` 中构造 `HostConfig` 的同一个函数判断：pane 的 `not_configured` 由它推导，运行时准入根据同一个
  `HostConfig` 返回 `model_not_configured`（v2 D9），两边不会出现不一致。
- **否决的备选**：在设置页保存模型凭据（需要新的机密存储和审计）；缺模型时不启动运行时（`not_configured` 会退化成
  `not_running`，失去可诊断性）；保留启用开关。

### 决策 7：工作台会话键与 `ContextRef`

- **决定**：
  - 页面视图在 WSGI 线程上经 blocking 门面取得嵌入路径：`runtime.blocking.chat.open_session(principal, app_id="metrics",
    agent=..., context_ref=..., session_key=f"metrics.workbench.{profile_id}")`（D7、v2.1 H6），运行时按
    (principal, app_id, session_key) 复用会话。
  - range、图表或 bucket 变化时，页面局部刷新得到新的 `ai_context_ref`，经 `embed-host.js` 发送 `context-changed`，
    运行时把同一会话重新绑定（进程内等价调用为 `runtime.blocking.chat.bind_context`），不新建会话。
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
  - 页面视图对 `open_session` 的调用设置时限，并先取得一个非阻塞信号量（上限小于页面保留的线程数），时限与上限是
    `ai_host.settings` 中的常量【待 S0b】。超时或信号量已满时 pane 显示"暂时不可用，可重试"，门面报告运行时未运行时
    显示 `not_running`；两种情况页面都照常返回 200。
- **理由**：一个 profile 对应一个持续的工作台对话；上下文只传标识，数据在服务端按 principal 拉取，越界校验不依赖页面。
  pane 嵌在每个 workbench 页面中，门面调用有时限与并发上限，运行时变慢或卡住时不会占满页面线程。
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
    `input_schema_invalid`）；运行时未运行或门面超时（v2.1 H5）为 `RUN_UNAVAILABLE`，`RuntimeBusy` 为 `RUN_BUSY`。
  - 每次 `start` 都带 `client_run_key`，取现有的 `clientRunKey`（attempt id 或 assist id，`out/ai_task_contract.py:102`、
    `services/report_assist_wire.py:21`）；运行时按 (principal, app_id, `client_run_key`) 去重（v2 D9），超时后以同一个
    键重试不会产生第二次运行。
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
  不可单独配置；运行时在 `start_blocking` 进入运行期时获取 `state_dir/.runtime.lock`，停止后释放。该锁是 OS 级文件锁
  （v2.1 D8），持有进程以任何方式终止（包括 SIGKILL）都由操作系统释放。服务进程持锁时，`project_run --execute-local`
  （现流程见 `management/commands/project_run.py:84-98`）经 `start_blocking` 得到 `RuntimeBusy`，映射为 `RUN_BUSY` 并
  提示通过服务提交，不等待、不换目录。进程内的 project run 注册表（`project_management/runtime.py:178-193`）只由组合根
  安装。
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
  `runserver` 与 `serve`（`runserver` 不启动运行时，不是支持的启动方式）。

### 决策 14：宿主 SPI 的认证、审批与审计

- **决定**：
  - `authenticate`：从 `BasicAuthMiddleware`（`metrics/middleware.py:10-62`）抽出纯函数 `check_basic_authorization`，
    中间件与 `MetricsHost` 共用；未配置 Basic 用户时返回匿名的 `local_operator`，认证失败返回 `None`（401）。
  - Basic 用户设置改为 fail-closed：`METRICS_BASIC_AUTH_USERS` 未设置或为空字符串表示未配置；其他取值必须是至少有一个
    条目、键和值都是非空字符串的 JSON 对象，否则 settings 加载时抛 `ImproperlyConfigured`，消息只含变量名。
    `check_basic_authorization` 只把 `None` 视为未配置，非空字典以外的其他值一律拒绝。现状下 JSON 数组、非对象 JSON
    或 `{}` 会让中间件静默停用认证（`metrics/middleware.py:18-31,36-37`）。
  - 401 带 `WWW-Authenticate: Basic realm="Restricted"`（`metrics/middleware.py:59-62`）；运行时路由的 401 使用宿主
    提供的同一质询头（v2.1 D3），浏览器在两边弹出同一个登录框。
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
- **理由**：同一请求在 Django 和运行时两侧的认证结果必须一致（见 `embedded-ai-runtime-host`）；Basic 用户设置写错时
  进程必须启动失败，而不是静默放行全站；审批权限是安全控制，不能被环境变量打开（v2 §8.5）；运行时的会话、tool 和
  审批事件与 bug_metrics 的业务审计语义不同。认证失败可由未认证的请求无限触发，写入数据库会让审计表无限增长，并在
  SQLite 上争用写锁；结构化日志足以排查。
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
  - `ops/docker/Dockerfile` 的基础镜像由 `python:slim`（`:2`，随上游 latest 漂移）改为 `python:3.13-slim`，与 S0/S0b
    验证的 CPython 3.13 同一小版本；删除 `GUNICORN_*` 环境变量（`:27-34`），`CMD` 改为 exec 形式
    `["python", "manage.py", "serve", "--host", "0.0.0.0", "--port", "8000"]`；`collectstatic` 与 production settings 不变。
  - exec 形式让 Python 成为 PID 1。内核不向 PID 1 投递默认处理的信号，`serve` 在主线程安装的 SIGTERM 处理器（决策 3）
    让 `docker stop` 走决策 2 的停止顺序。Docker 默认 10 秒后发送 SIGKILL；进程内停止预算 660 秒 = 第一段停止与排空
    10 + `project_runs.stop` 620 + 运行时第二段停止 30，README 要求 `docker run --stop-timeout 690`（Compose 用
    `stop_grace_period: 690s`），在预算之外留 30 秒给进程退出；被提前杀死时，状态目录锁由操作系统释放（决策 12），
    中断的运行由下次 `start()` 的恢复标记出来，不会静默丢失。
  - 只允许一个副本：`METRICS_STATE_DIR`（镜像内为 `/metrics/state`）挂载为卷，数据库与 `ai-base/` 状态目录随卷持久化；
    第二个副本挂载同一个卷时，`start_blocking` 抛 `RuntimeBusy`，`serve` 输出 `serve startup failed (<code>).` 并以非零
    退出（决策 3）。
  - README 的 Docker 快速上手与 "Production Setup"（`README.md:100-139,556-577`）改为上述命令、卷与停止超时，并写明
    单副本、非回环绑定的匿名姿态（决策 3）、production settings 下发布审批至少需要一个 Basic 用户（决策 14），以及配置
    `ALLOWED_HOSTS` 与由反向代理终止 TLS 的建议。
- **理由**：容器与本地使用同一个组合根和同一条启动命令（决策 1、3）；状态目录锁决定了只能有一个进程，这也是 gunicorn
  多 worker 不再可行的原因；固定 Python 小版本让镜像与验证环境的解释器一致。
- **否决的备选**：gunicorn 多 worker（只有第一个 worker 能拿到状态目录锁，其余无法启动）；gunicorn 单 worker（多一层
  进程管理，信号与停止超时另由 gunicorn 决定，启动方式不再唯一，且 gunicorn 不支持 Windows 本地运行）；保留 gunicorn
  运行 `metrics.wsgi` 的镜像（生产没有运行时，AI 不可用，并形成第二个组合根）；shell 形式的 `CMD`（`/bin/sh` 成为 PID 1，
  不转发 SIGTERM）。

## Risks / Trade-offs

- [运行时阻塞、崩溃或内存泄漏会直接拖垮 Metrics 页面] → `RuntimeLimits` 限制并发、单次运行与 tool 超时、输出大小；
  slow callback 门禁与宿主一致性套件；运行时异常只以 API 错误返回（v2 §6、D8）；运行时在运行期意外结束时 `serve`
  输出 `serve runtime failed (<code>).` 并非零退出，不在没有运行时的情况下继续服务（决策 2）；pane 的门面调用有时限与
  并发上限（决策 7）。
- [两套依赖进入同一个 venv 后冲突] → 单一 requirements；S0 与 S0b 用 `pip check` 验证；`ai-base-runtime` 与所选 HTTP
  server 精确固定。
- [发布耦合：AIB-2 与 MDB-2 必须同版本，回滚也要一起回滚] → 精确版本固定；宿主一致性套件是升级门禁；回滚按
  Migration Plan 整体恢复。
- [blocking 门面误用或 `asyncio.run` 回流导致死锁] → 在循环线程调用门面立即 `RuntimeUsageError`；残留 gate 用 AST 检查
  `services/report_assists.py`、`services/project_run_worker.py` 与 `ai_host/` 中没有 `asyncio.run`；Metrics 只在
  `serve` 主线程、WSGI 线程与 worker 线程上调用门面，运行在循环上的 tool 只经 `run_sync` 调用 Metrics 公共 API（决策 4）。
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
- [关闭时打开的聊天流让停止无限等待] → 运行时第一段停止让打开的流发送终止事件后结束（v2.1 H2），客户端在连接关闭
  之前收到终止事件；第一段停止与排空合计最长 10 秒，到期后关闭剩余连接；第二段停止取消未完成的运行并标记中断；
  0.5 的 S0b（B5）与 5.6 的命令测试都验证这一点。
- [`/ai` 流占满 server 线程，页面没有线程可用] → 每个 `/ai` 在途请求（包括整条流）占用一个 server 线程；流与其他 `/ai`
  请求分开限额，两个上限之和小于线程数，超限立即返回 503 与 `Retry-After`，不排队（决策 1，v2.1 H7）；S0b 的 B9
  验证流占满限额时短请求与页面不受影响；线程数与两个在途上限【待 S0b】。
- [Windows 上其他进程绑定同一端口并截走连接] → `serve` 自建 socket 并设置 `SO_EXCLUSIVEADDRUSE`（决策 2 第 1 步）；
  S0b 的 B1 验证其他进程即使设置 `SO_REUSEADDR` 也无法绑定。
- [Basic 用户设置写错导致全站静默放行] → 设置 fail-closed，格式错误时 settings 加载失败（决策 14）。
- [WSGI 线程与运行时循环之间的流桥接] → 运行时适配器逐块转发、不缓冲（v2.1 H7），请求体在 WSGI 线程上读取并有上限，
  响应块交接队列有上限并对运行时形成背压（H7），跨线程等待都有上限（H5），客户端断开后在心跳间隔内被发现并释放
  连接级资源（H3、H4）；S0b 的 B3、B4 实测缓冲、断开与残留，一致性套件持续断言。
- [停止信号到不了 `serve`] → `serve` 在主线程为 SIGINT、SIGTERM 安装处理器（Docker 中 Python 是 PID 1，内核不投递默认
  处理的信号）；Windows 无法可靠地向子进程发送 Ctrl+C，验证脚本用 `--stop-file` 与 `--lifetime-seconds`；停止期间第二次
  信号在 1 秒内强制退出（决策 3，依赖分片等待）。运行时核心不触碰信号（v2.1 H8）。
- [Docker 从 5 worker × 10 线程的 gunicorn 改为单进程，峰值吞吐下降] → 单进程线程化 WSGI，线程数【待 S0b】；同步视图
  按请求在各自线程中并发，I/O 等待不受影响，只有 CPU 密集的渲染受 GIL 限制；Metrics 是团队内部看板，页面读取本地聚合；
  镜像内的并发数据（S0 的 C7）未测量，只供 owner 参考，不作为退出条件。
- [非回环绑定且未配置 Basic 用户时，能访问该端口的任何人都能匿名使用页面与 AI 对话] → owner 决定维持现有姿态；`serve`
  输出警告；development settings 下拒绝非回环绑定；production settings 下匿名 principal 不能决定审批（Q5）；README
  建议配置 Basic 用户并由反向代理终止 TLS。
- [模型凭据与 Jira PAT 位于同一进程内存] → 与现状等价（两个进程本来以同一 OS 用户运行）；凭据用 `SecretStr`，日志脱敏。
- [`runserver` 仍可启动但没有 AI] → AI pane 明确显示 `not_running` 并提示用 `manage.py serve` 启动；文档只写 `serve`。

## Migration Plan

前置条件：AIB-0 已发布并通过现有 launcher 端到端流程；S0b 的全部退出条件通过（tasks 0.5）；AIB-2 wheel 已发布，Metrics
已精确固定其版本并通过宿主一致性套件。

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
   `--stop-timeout 690`（决策 16）。冒烟检查：
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

1. S0b 结果：任一退出条件不通过，或只有 Django 线程化开发服务器、只有静态文件不经认证的组达标时，停止实施，带证据回到
   owner 决策（tasks 0.5）；本设计不预置其他备选方案。
2. AIB-2 的精确版本号、wheel 摘要，S0 确定的 portalocker 精确版本，以及 S0b 选定的 WSGI server 精确版本，发布时写入
   requirements。
3. AIB-2 的 `session_key` 校验是否与 v2 D7 一致（字符集 `[A-Za-z0-9._:-]`，总长不超过 200）。`metrics.workbench.` 加
   profile id（`[a-z0-9][a-z0-9._-]{0,159}`）最长 178 个字符且只含允许的字符，由 0.6 确认；不一致时回到 v2 修正，
   `ai_host` 不做编码。
4. AIB-2 中 task run 查询与取消的同步方法名（v2 只给出 `task_runs.start(principal, request, timeout=30)`）、
   `start_blocking` 句柄上第一段停止、运行时结束事件与 WSGI 适配器的方法名及其配置项（心跳间隔、结束流时限、流与其他
   `/ai` 请求各自的在途上限、请求体上限、响应块队列上限，v2.1 H2/H3/H6/H7）、门面超时异常的类型、`HostConfig` 中
   "允许匿名 principal 决定审批"的字段名，以及 `ctx.approval` 中 preview、preview 摘要与 `decided_by` 的确切名称，
   由 0.6 记录。差异只影响 `RuntimeTaskRunPort`、`ai_host.settings`、`ai_host.wiring`、`serve` 与发布 tool 内部，
   project_management 的端口不变。

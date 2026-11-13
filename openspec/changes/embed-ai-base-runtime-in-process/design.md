# Design

## Context

动机与范围见 `proposal.md`（Why / What Changes），行为要求见本变更的 9 个 delta spec；本文只写"怎么做"，按 capability
名引用要求，不重复场景。未加模块前缀的 `app/`、`services/`、`out/`、`management/` 路径均位于 `project_management/` 下。

已定输入（不再讨论）：

- owner 已于 2026-11-10 签署 v2 的 Q1–Q9，并接受 MDB-2 依赖的五项运行时补充：D4 `AppPackage.task_profiles`
  （删除 `pack.py`/`ScopeGrant`）、D5 `ToolContext.context_ref`、D6 审批绑定的预览摘要、D7 会话键（W0 冻结为
  `chat.open_session(principal, *, app_id, agent, context_ref=None, session_key=None)`）、D9 task-run 真实模型执行与
  准入错误码（`upstream-ai-base-runtime-proposal.md`）。
- owner 于 2026-11-10 决定保留 Docker 部署：镜像改为单进程 `manage.py serve`，非回环绑定不强制 Basic 认证，
  维持现有的匿名姿态（决策 3、16）。
- owner 于 2026-11-11 根据 S0 结果（`s0-spike-report.md`，C5 不通过）选择方向 1：Django 保持线程化 WSGI；运行时经
  `start_blocking` 运行在自己的专用循环线程上；`/ai` 经运行时的 WSGI 适配器（v2.1 H7）进入同一循环。S0b
  （`s0b-spike-report.md`，2026-11-11）表明方向 1 可行，没有触发停止条件；本文据其结论确定 HTTP server（waitress
  3.0.2）、静态文件设置、线程数与 `/ai` 在途上限、停止机制、心跳与精确版本（决策 1–3、7）。S0b 首轮签核为 NEEDS_FIX
  （`s0b-signoff.md`）：推荐组合没有作为整体运行，第二次信号的强制退出只在合成子进程上测过，spike 的停止总时长没有
  上界。S0b 终测（报告 §3.11）在最终组合（线程 14、上限 4 与 4、资产直出、flush 收尾、显式退出、`serve-http` 线程）
  上补测 M1–M6，全部通过，线程数、在途上限与停止各段时限按终测定稿（决策 1、2）。复签 PASS（附条件，不需要重跑），
  条件已并入决策 1、2、3、14、16，tasks 0.5 逐项通过。
  本设计依赖上游 v2.1 的 Q10（运行时提供同步宿主托管：`start_blocking` 句柄、两段式停止、心跳与核心 wheel 中的 WSGI
  适配器，以及 S0b 新增的 R14–R24），owner 已于 2026-11-11 签署，v2.1 定稿。
- owner 于 2026-11-11 随 Q10 就复签提出的三项作出决定：请求按复签的定序表处理（L0 为 waitress 传输层；L1 为宿主的
  Host 校验、停止中的 503 与两路分派；308 在适配器的认证之后，决策 1）；停止的 10 秒是预算，由两段式看门狗按段保证
  （决策 2、3）；不重跑 M3：判定为"11/11 逐个一致"，代码差异要掩盖由 server 引起的失败就必须恰好补偿它，没有这样的
  机制（复签 C），只需披露代码树。
- owner 于 2026-11-11 就 AI pane 冷加载决定（上游 v2.1 D3、D7、H7）：同步托管时 `MetricsHost.authenticate` 是普通
  函数，由适配器在 WSGI 线程上、准入之前调用，未认证的请求不占名额；UI 资产由适配器在认证之后直接返回，不经循环、
  不计名额，URL 跟随 `root_path`；短请求上限由 2 改为 4，线程数由 12 改为 14；UI 按 `Retry-After` 重试幂等 GET，
  嵌入页导航被拒时自动刷新（决策 1、14）。S0b 首轮测的是旧配置（线程 12、上限 2、资产计入名额），终测在新配置上复测。
- owner 于 2026-11-12 把 AIB-2 规划（v2.1 修订 `5757c9c`，连同 AIB-0 收尾 `44cdfa7`）fast-forward 合入 AI Base main
  并 push，同意上游提案增补 1 的三项 W0 接口输入（Q11）：`start_blocking` 的启动时限到期时有上限地回滚，并抛出带专用
  code 的异常（v2.1 H6，冻结为 `RuntimeStartTimeout`，code `start_timeout`）；导出异常都带稳定的 `code`（D9）；宿主
  一致性套件只运行宿主声明的托管方式，Metrics 只声明 `blocking_wsgi`（D10）。W0 已在 AI Base `fc4db2f` 冻结公开契约
  （AI Base `openspec/changes/extract-embeddable-agent-runtime/design.md`，下称 AIB design，§10、§11），Metrics 已在
  `e3c8a80` 复核接受（`aib2-w0-acceptance.md`），W1–W4 已获授权。本设计据此确定启动时限的处理（决策 2、3、10）与
  一致性套件的范围（tasks 5.10）。
- 本设计只使用 W0 冻结的运行时公开契约（AIB design §11.1，`fc4db2f`）：`start_blocking(settings, host, apps, *,
  start_timeout)` 返回的 `BlockingRuntimeContext`，以及 `with context as handle` 得到的句柄（同步门面
  `handle.blocking`，含 `chat` 与 `task_runs`；第一段停止 `close_http()`、第二段停止 `stop()`、WSGI 适配器
  `wsgi_app()`、结束信号 `ended` 与 `end_code`、停止结果 `stop_result`、`handle.ui.asset_url`，v2.1 H2/H6/H7）、
  `request_body_policy` 与 `ai_base_runtime.spi/apps/contracts/testkit`。名称、签名、配置项与默认值以 AIB design
  §10、§11 为准，tasks 0.6 只在 wheel 交付后核对实现与之一致。
- 发布顺序：AIB-0（AI Base 热修）→ S0 共装 spike（不通过）→ S0b（方向 1 可行，终测 M1–M6 通过，复签 PASS）→ 上游提案
  v2.1 定稿 → AIB-2 规划合入 AI Base main（`5757c9c`）与上游增补 1 → AIB-2 W0 接口冻结（`fc4db2f`）并经 Metrics 复核
  接受（`e3c8a80`）→ AIB-2 W1–W4（已授权）→ AIB-2 与 MDB-2 同版本发布（v2 §9）。

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
  - `wiring.build_wsgi_application(django_app, ai_app)` 返回一个 WSGI 分派函数（L1）。挂载路径（Q7）为
    `/` 加规范化的 `METRICS_BASE_URL` 再加 `ai`，规范化规则与页面路由前缀相同（`ui_web/urls.py:93` 经
    `ui_web/utils/url_utils.py:4`：去掉首尾 `/`，非空时补一个 `/`）：为空或 `/` 时是 `/ai`，为 `/metrics/` 或 `metrics`
    时是 `/metrics/ai`。请求按复签的定序表处理（owner 2026-11-11），任一步拒绝即返回：
    - L0，waitress 传输层，先于应用执行，宿主无法调整：请求行与头部大小、`Content-Length` 语法（400）、chunked 分帧、
      请求体上限（413，`max_request_body_size` 显式配置，决策 3）。waitress 在调用应用之前读完并缓冲请求体，超过
      512 KiB（`inbuf_overflow`）时写入临时文件；`channel.py` 在 `request.completed` 之后才创建 task。这是 AIB-2
      `blocking_wsgi` 的宿主前提（OD-W1-1，`aib2-w1-review.md` 第 3 节）：运行时在 WSGI 线程上按合作式时限分块读取
      已缓冲的请求体，进行中的单次读取不被抢占；更换或升级 WSGI server 时必须保持先缓冲后派发，由宿主一致性套件的前提
      断言验证；
    - L1 第 1 步，Host 校验：对所有路径（包括静态文件）用 `WSGIRequest(environ).get_host()` 判定，与 Django 同一规则、
      同一 `ALLOWED_HOSTS`，非法时返回固定文本的 400（决策 14）；
    - L1 第 2 步，停止中的 503：停止受理之后（决策 2 第 7.1 步），已有连接上的请求不论是否带凭据都得到固定文本的 503 与
      `Retry-After: 2`（与准入同值），不带 hop-by-hop 头；这是先于认证的具名例外；
    - L1 第 3 步，两路分流：路径等于挂载路径或以挂载路径加 `/` 开头时交给运行时的 WSGI 适配器（`handle.wsgi_app()`，
      v2.1 H7）：`SCRIPT_NAME` 追加挂载路径，`PATH_INFO` 为余下部分（挂载路径本身为 `""`），请求头、Host、客户端地址与
      scheme 原样传递；适配器按 v2.1 D3 依次执行 Host 校验（同一白名单）、请求完整性、认证（401）、308（`Location` 为
      `SCRIPT_NAME` 加 `/`，只含路径，保留查询串）、UI 资产、运行时未运行的 503 与准入，然后进入桥。其余路径交给
      Django 的 `get_wsgi_application()`，进入中间件链（`defaults.py:52-63`，`BasicAuthMiddleware` 在最前），页面请求
      路径与现在相同；
    - 行为变化：经 `serve` 的 Django 路径上，非法 Host 且不带凭据的请求由 401 变为 400（`BasicAuthMiddleware` 不调用
      `get_host()`）。Django 测试客户端不经分派，现有测试不受影响。
  - 静态文件只由中间件链中的 WhiteNoise 提供（`defaults.py:52-55`，位于 `BasicAuthMiddleware` 之后，与现在的 gunicorn
    镜像相同），并设置 `WHITENOISE_USE_FINDERS = True`，让没有运行 `collectstatic` 的本地进程也能提供静态文件。
    `defaults.py` 设置 `WHITENOISE_AUTOREFRESH = False`，development 与 production settings 不覆盖（WhiteNoise 默认取
    `DEBUG`）：启动时经 finders 建立索引，启动后新增或修改的静态文件要重启 `serve` 才能正确提供。不再使用
    `project_serve.py:50` 的 `StaticFilesHandler`。Django 6 已不读取 `STATICFILES_STORAGE`（`defaults.py:147`），实际
    生效的是不带哈希的 `StaticFilesStorage`，finders 与 `STATIC_ROOT` 中的文件名一致。
  - HTTP server 为 waitress 3.0.2：`serve` 以 `waitress.create_server(app, sockets=[sock], threads=14,
    channel_request_lookahead=1, max_request_body_size=N + 1)` 接管预先绑定的监听 socket（决策 2 第 1、6 步），启停调用
    与请求体上限见决策 3。线程数与 `/ai`
    在途上限是 `ai_host.settings` 中的常量。线程数取保守值 14 = 流上限 4 + 其他 `/ai` 请求上限 4 + 页面并发 4（C5 的
    c4）+ 余量 2，页面始终至少保留 6 个线程（14 − 4 − 4）。两个上限分开计数，UI 资产与未认证的请求不计入：适配器在
    WSGI 线程上先做 Host 校验、请求完整性与认证（决策 14），资产在认证之后直接返回，不进入循环（v2.1 D7、H7）。超过
    各自上限的 `/ai` 请求立即得到 503 和 `Retry-After`，不排队；嵌入页的导航请求被拒时得到自动刷新的 503 页面；请求
    正常结束、出错、客户端中止或停止时名额都归还（v2.1 H7，R22）；流占满自己的限额时，其他 `/ai` 请求与页面照常
    处理。第一段停止时限 2 秒、停止各段时限（决策 2）、空闲流心跳间隔 2 秒与启动时限 `RUNTIME_START_SECONDS`（决策 2
    第 2 步）也是该模块中的常量。`ai_host.settings` 构造 `HostConfig` 时，`lifecycle` 传入
    `LifecycleLimits(stop_timeout_seconds=1.0, heartbeat_interval_seconds=2.0, http_close_timeout_seconds=2.0)`，
    `http_limits` 传入 `HttpLimits(max_streams=4, max_requests=4)`（AIB design §11.1 `:724-747`，`fc4db2f`）：只有
    `stop_timeout_seconds` 必填、没有默认值（§10 `:662`）；其余四项是可选字段，取值与 §10 的 A 类默认值相同
    （`:659-661`），Metrics 仍显式传入，让线程数 14 与停止预算所依据的取值只有 `ai_host.settings` 一处来源。响应块队列
    的三个上限（16 块、1048576 字节、65536 字节）是 §10 的 B 类冻结值（`:663`），Metrics 不传入，由一致性套件验证。
    这些配置项都不是 `start_blocking`、句柄方法或 `wsgi_app()` 的参数（§2 `:93-97`）；启动时限只经 `start_blocking`
    的必填 keyword-only 参数 `start_timeout` 传入，AI Base 不提供默认值（§3.1 `:231`），取值见 Open Questions 5。
  - 访问日志：waitress 没有内置访问日志，`serve` 用一个 WSGI 中间件包住分派函数，按 Django 的格式为页面与 `/ai`
    请求各写一行，不记录 `Authorization` 与 `Cookie` 请求头。
  - 导入规则测试（import-linter 或等价 gate）：只有 `ai_host` 导入 `ai_base_runtime` 与 `waitress`；任何模块不导入
    `ai_base_runtime._internal` 或 AI Base 的 `app.*`；project_management 不导入 `ai_host`；各模块 `app/domain/` 不导入
    Django、asgiref 与运行时。
  - 依赖：精确固定 `ai-base-runtime`、`waitress==3.0.2` 与 `portalocker==4.4.2`（S0 确定），Django 6.0.7 与
    whitenoise 6.12.0 不变；`uvicorn`、`starlette`、`cheroot`、`a2wsgi` 不是 Metrics 的直接依赖；删除 `gunicorn`、
    `ai-base-application-sdk` 与 `requirements-ai-task.txt`。`ai_host` 使用 waitress 的内部接口（决策 3：
    `trigger.pull_trigger`、`active_channels` 与 `close_when_flushed`、`task_dispatcher` 的 `active_count` 与
    `shutdown`），因此精确固定；升级 waitress 时重跑 S0b 的 B1、B4、B5、B9 子集与宿主一致性套件（含先缓冲后派发的
    前提断言，OD-W1-1）。
- **理由**：
  - S0 实测：Django 在 ASGI 下每个请求（包括每个静态资源）都要新建线程上下文与执行器，主要页面 p95 是线程化 WSGI
    基线的 1.82–3.23 倍，不挂运行时的 uvicorn 组合同样超标（`s0-spike-report.md` §2.4）。保持 WSGI，页面请求路径与
    基线相同。
  - 开发、验证、生产走同一条装配路径；运行时 API 面收敛在一个 app，升级只改一处；边界可由 gate 机器检查（见
    `embedded-ai-runtime-host`）。
  - 生命周期由 `serve` 显式控制，不依赖任何 server 的 lifespan 或信号语义；换 server 只影响决策 3 中的启停调用。
  - 静态文件只走一条路径：在中间件链之外提供静态文件会绕过 Basic 认证，配置了 Basic 用户的镜像会因此公开静态文件。
  - 定序（复签 D，owner 2026-11-11）：Host 校验是 DNS rebinding 的防线，要对所有响应生效，而且成本很低；停止中的 503
    只出现在关闭监听（≤ 0.5 秒）之前已接受的连接上，内容是固定文本；308 放在认证之后，与 Metrics 现状一致（无凭据的
    `/projects` 得到 401，而不是 APPEND_SLASH 的 301），一致性套件只断言一种顺序。L0 由 waitress 在调用应用之前完成，
    宿主只能配置上限，不能调整顺序。
  - WSGI server 的线程池是固定的，每个 `/ai` 在途请求（包括整条流）占用一个线程；在途上限保证页面始终有线程可用。
    流与其他 `/ai` 请求分开限额，长时间打开的流不会挤掉审批、会话列表等短请求。
  - S0b 实测（`s0b-spike-report.md` §1、§4.2、§4.3）：waitress 3.0.2 + WhiteNoise（认证之后、关闭 autorefresh）的 C5
    Phase 2 为 12/12（线程 8，p95 比 seq 0.89–1.04×、c4 0.88–0.96×），开启 autorefresh 时 11/12；分开限额时短请求
    20/20 返回 200，共享一个上限时 20/20 得到 503（B9(b)，线程 8）；4 条流占满流上限时线程 12 为 12/12（B9(c)，c4 home
    1.15×，单次运行）。线程数是保守取值，不是实测下限：线程 8 在 B9(c) 中唯一不达标的是 seq 单元格（单连接，不是
    线程耗尽），同一配置两次运行之间的波动约 0.18。终测 M2 在最终组合（线程 14、上限 4 与 4、资产直出、flush 收尾）
    上复测同一次饱和：未饱和与饱和两组各 12/12，hold 期间 1944 个短请求全部 200（最大 70.78 毫秒），新流 194/194 得到
    503 与 `Retry-After: 2`；M3 浏览器子集 11/11 与 stock 一致（tasks 0.5）。
  - AI pane 冷加载（owner 2026-11-11）：浏览器对同一 origin 约开 6 个连接，AI Base 的入口 HTML 一次引用 7 个资产
    （构建产物共 13 个 JS/CSS 与 30 个字体文件），script 与 stylesheet 遇到 503 不重试。资产计入上限 2 时，冷加载会
    与 API 请求一起被拒，页面直接坏掉；资产不计名额后，上限 4 只需容纳入口 HTML 与启动时的 API 请求，被拒的幂等 GET
    由 UI 按 `Retry-After` 重试。线程数随上限增加 2，页面保留的 6 个线程不变；终测冒烟与 M5 确认资产不占名额，短请求
    名额占满时资产仍返回 200；浏览器冷加载由 7.2 与 10.4 验证。
- **否决的备选**：
  - uvicorn 同时托管 Django ASGI 与运行时（S0 C5 不通过）；uvicorn 托管运行时、Django 经 Starlette `WSGIMiddleware`
    挂入：S0 测过两种静态文件姿态，`composed_wsgi` 的 p95 比值 seq 1.40–2.15、c4 1.85–2.38，`composed_sf_wsgi` seq
    1.25–1.93、c4 1.55–1.73，都是 0/12 达标（`s0-spike-report.md:82,118,122`）；Granian（WSGI 模式在独立的 worker
    进程中运行应用，`serve` 无法在同一进程内控制生命周期）；gunicorn（不支持 Windows，多 worker 与状态目录锁冲突，
    见决策 16）。
  - 其他 WSGI server 与绑定方式（S0b）：cheroot（Windows 上 keep-alive 每个请求约 61 ms，C5 Phase 1 0/12；
    `ThreadPool.stop` 的 `join()` 没有时限）；Django 开发服务器（不是 production server，C5 Phase 2 11/12，不靠 server
    探测时空闲流 3.80 秒才检出断开）；让 waitress 自己绑定（Windows 上它设置 `SO_REUSEADDR`，与以 `SO_REUSEADDR`
    占用同一端口的进程共存，20/20 个连接由占用者应答，B1）。
  - 由 Django 视图代理 `/ai`：同样需要线程与循环之间的桥接，另加一层 Django 响应处理（流要么被缓冲，要么被改写），
    POST 还要豁免 CSRF。
  - 通用桥接库 a2wsgi 1.10.10：跨线程等待没有上限（`a2wsgi/asgi.py:214` 的 `run_coroutine_threadsafe(...).result()`、
    `:69,230` 的 `SyncEvent.wait()`）；响应生成器的 `yield`（`:248,269,303`）不在 try/finally 中，WSGI `close()` 时
    既不发送 `http.disconnect`，也不取消 ASGI task。S0b 实测：20 条中止的流 0 条被检出，循环上遗留 20–30 个 task
    （B4）；停止时排空 10 秒超时，流被截断且没有终止事件（B5）；它声明 `spec_version` "2.5"，Starlette
    `StreamingResponse` 因此不监听 `http.disconnect`（R17）。
  - 在 `AppConfig.ready()` 构造运行时（migrate、测试、CLI 等所有加载 Django 的进程都会争抢状态目录锁）；保留
    `metrics/wsgi.py` 作备用入口（第二个组合根，永远不启动运行时）；在中间件链之外提供静态文件（见理由）；开启
    `WHITENOISE_AUTOREFRESH`（每个请求都检查文件系统，S0b C5 Phase 2 为 11/12，seq home 1.33×）。
  - 其他定序（复签 D）：308 放在认证之前（与 Django 路径的 401 不一致）；停止中的 503 放在 Host 校验之前（停止窗口内
    DNS rebinding 页面也能得到宿主的响应）；静态文件豁免 Host 校验（原决策 14，见决策 14）。

### 决策 2：生命周期与 project run（v2.1 §5.1）

- **决定**：`serve` 的主线程只做生命周期控制，严格按以下顺序：
  1. 按决策 3 的规则检查地址后，主线程自建监听 socket（Windows 设置 `SO_EXCLUSIVEADDRUSE`，POSIX 设置
     `SO_REUSEADDR`）并 bind，此时尚未加载 AI Base、未启动运行时，也未获取状态目录锁；waitress 不自己绑定。bind 失败
     （包括 `EADDRINUSE` 与 `EACCES`，Windows 为 10048 与 10013）时 2 秒内以 `serve bind failed.` 退出，退出码 1。listen 在第
     6 步由 waitress 构造 server 时执行，启动期间的连接被拒绝，不会停在 backlog 中。为满足 2 秒（见理由）：
     - `serve` 设置 `requires_system_checks = []`（先例 `provider_sync/management/commands/provider_credentials.py:24`），
       bind 成功后才调用 `self.check()`。检查有错误时输出 `serve startup failed (system_check_failed).`，经第 7.7 步以 1
       退出，详情由操作者运行 `manage.py check` 查看；`system_check_failed` 是 `ai_host` 自有的 code，不属于 AIB 注册表。
       Django 的 `check()` 有错误时抛 `SystemCheckError`，抛出前不打印；只有 warning 时写 stderr，与现状一致。
     - bind 之前不导入 `ai_base_runtime`：`django.setup()` 与加载命令时导入的模块（`ai_host` 包、`apps.py`、models、
       `serve` 命令模块及其导入的模块）都不导入它；`ready()` 注册的 CLI 端口工厂（决策 10）在被调用时才导入
       `ai_host.wiring`。URLconf 不受此约束：系统检查在 bind 之后，bind 之前不导入 URLconf。
     - bind 之后、启动任何运行时资源之前，以 `settings = build_settings()` 计算 N（决策 3，AIB design §11.1
       `:786-787`），第 2 步复用这个对象。
  2. `context = start_blocking(settings, MetricsHost(), [METRICS_APP], start_timeout=RUNTIME_START_SECONDS)`，
     然后 `with context as handle:`（AIB design §11.1 `:701-703`、`:799-801`，`fc4db2f`；`MetricsHost().config` 是决策 1
     的 `HostConfig`，`:760`），`start_timeout` 取 `RUNTIME_START_SECONDS`（决策 1）：运行时在自己的专用线程上创建
     事件循环（Windows 上为 Proactor）并进入运行期，获取状态目录锁；`RuntimeBusy`（code `runtime_busy`）、
     `RuntimeConfigurationError`（code `configuration_invalid`）、`RuntimeStartupError`（code `startup_failed`）等启动
     异常带稳定的 `code` 原样传回主线程（v2.1 H6、D9，§11.3 `:990-997`）。启动时限到期时运行时按 v2.1 H6（增补 1）
     回滚，最迟在 `RUNTIME_START_SECONDS` + 1.0 秒（`stop_timeout_seconds`，§3.1 `:254`）时抛出 `RuntimeStartTimeout`
     （code `start_timeout`，§3.1 `:264-265`）：回滚已完成时按启动失败输出，以 1 退出；回滚未按时完成时
     （`context.startup_failure.rollback_result` 的 `completed` 为假，§11.2），先按启动失败输出，再记入清理错误码并输出
     清理失败，以 3 退出（决策 3），仍存活的循环线程由第 7.7 步的退出清点记录，`os._exit` 不等待它。
  3. `attach(handle)`，供 WSGI 分派、`ai_host` 视图与 AI pane 状态读取。
  4. `port = RuntimeTaskRunPort(handle.blocking.task_runs)`。
  5. `project_runs = build_project_runtime(task_runs=port)`，`install_project_runtime(project_runs)`，`project_runs.start()`，
     都在主线程上直接调用。
  6. 主线程用第 1 步的 socket 构造 waitress server（决策 3），在 `serve-http` 线程中运行 `server.run()` 开始受理请求。
     主线程不运行 server 循环，只处理信号与停止编排：以不超过 0.5 秒的间隔检查停止事件（决策 3）与运行时的结束信号
     `handle.ended`（v2.1 H6，§11.1 `:808-810`）。运行时在运行期意外结束时，生命周期对象进入 `failed` 并记录
     `handle.end_code`，`serve` 输出 `serve runtime failed (<code>).`，执行第 7 步后以 1 退出（清理也失败时以 3 退出，
     决策 3）。
  7. 停止，在 `finally` 中按序执行；任一步的异常记入生命周期对象，不跳过后续步骤。t0 为主线程开始第 7 步的时刻，不晚于
     停止触发后 0.5 秒（信号处理器最迟在一个等待分片后执行；监视线程以不超过 0.5 秒的间隔检查 stop-file 与时限）。HTTP
     各段的截止时刻与运行时停止时限是 `ai_host.settings` 中的常量，从停止触发到进程实际退出的预算为 10 秒，由两段式
     看门狗按段保证（决策 3），不含第 4 步等待执行中的 project run；下列取值按 S0b 终测 M4 定稿（见理由）：
     1. 停止受理新连接（决策 3）；此后 L1（决策 1）对已有连接上 Host 合法的新请求（页面与 `/ai`，不论是否带凭据）
        立即返回固定文本的 503 与 `Retry-After: 2`；
     2. 运行时第一段停止 `handle.close_http()`（v2.1 H2；不带参数，时限只取 `HostConfig.lifecycle` 的
        `http_close_timeout_seconds` 2.0，返回 `HttpCloseResult`，AIB design §3 `:199`）：新的 `/ai` 请求得到 503，
        打开的流在 t0 + 2 秒之前发送终止事件后结束；task run 与 blocking 门面照常工作；
     3. 排空与收尾（决策 3）：等宿主统计的在途请求归零，截止 t0 + 3 秒；再按 flush 方式关闭连接，截止 t0 + 6.5 秒，到期
        后关闭剩余连接；然后 `server.close()`，`serve-http` 在 `run()` 返回后以 0.5 秒时限关闭 waitress 线程池，主线程
        分片 join `serve-http`，截止 t0 + 7.5 秒。仍有在途请求或 `serve-http` 没有结束时，记入清理错误码后继续；
     4. `project_runs.request_stop()`：在锁内停止受理、清空排队的 run，对排队与执行中的 run 请求取消，返回是否有执行中的
        run；返回真时看门狗截止放宽到 t0 + 659.2 秒（决策 3）。然后 `project_runs.wait_stopped(620)` 按不超过 0.5 秒分片
        join worker，返回 `RuntimeStopResult`；返回时刻记为 T，看门狗截止收紧为 min(当前截止, T + 1.2 秒)。随后立即向
        stdout 写一行 `project_runtime_stopped` 事件（格式同 `project_serve.py:86-93`；任一调用抛错时按
        `RuntimeStopResult(False, None, ())` 输出，同 `:69-75`）。没有执行中的 project run 时，worker 在 `notify_all` 后
        立即退出（`project_management/runtime.py:54-81,120-127`），这一步按 0.5 秒计入预算；有执行中的 run 时最多等待
        620 秒（决策 16）；
     5. `clear_project_runtime(project_runs)`，`detach()`；
     6. 离开 `with context as handle` 块：运行时第二段停止（与 `handle.stop()` 相同，AIB design §11.1 `:820-822`），
        取消未完成的运行并标记中断，关闭循环并 join 循环线程，合计时限 1.0 秒（`HostConfig.lifecycle` 的
        `stop_timeout_seconds`，v2.1 H6、R14），`handle.stop_result` 记入生命周期对象；
     7. 显式退出（owner 于 2026-11-11 决定）：先做退出清点（R24-host，见下），再 `connections.close_all()`，
        `logging.shutdown()`，按决策 3 写出最后一行输出，flush stdout 与 stderr，然后 `os._exit(<退出码>)`；不经
        `sys.exit`，不等待非 daemon 线程、atexit 回调与解释器收尾。这一步与操作系统结束进程合计按 0.5 秒计入预算。
        `close_all()` 只关闭主线程的连接（Django 的连接按线程保存）；请求线程的连接在请求结束时已关闭（`CONN_MAX_AGE`
        为 0），其余线程的连接随进程退出由操作系统释放。这依赖 SQLite 与 `CONN_MAX_AGE` 为 0，改用持久连接或网络数据库
        时要重新评估。除第二次信号与看门狗外，`serve` 的每条退出路径（包括绑定失败、启动失败与运行期失败）都以这一步
        结束；第二次信号与看门狗只写出自己的一行，flush 后 `os._exit`。
  - 退出清点（R24-host，复签 D 第 6 项）：`manage.py` 在导入 Django 之前包装 `atexit.register`，记录每个回调的
    注册者。第 7.7 步在 `logging.shutdown()` 之前清点 `os._exit` 会跳过的收尾：atexit 回调及其注册者、
    `threading._register_atexit` 的回调（如 `concurrent.futures` 的 `_python_exit`）、存活的非 daemon 线程与子进程
    （Windows 上父进程退出不结束子进程）、`weakref.finalize(atexit=True)` 对象（如 `TemporaryDirectory`）与日志
    handler；写一条结构化日志 `serve_exit_inventory`，与 `ai_host.settings` 中的白名单比对。白名单中标为必需的清理在
    本步内显式执行；出现白名单之外的条目，或必需的清理超时、失败时，记入清理错误码，以 3 退出。运行时自己的资源由
    R24 保证（v2.1 H6）。
  - 主线程上的每一次等待都按不超过 0.5 秒分片：第 6 步对停止事件的等待，第 7 步（包括第 6 步发现运行时结束后的退出
    路径）中的排空等待、对 `serve-http` 的 join、`project_runs.wait_stopped` 内的 join 与离开 `with` 块时的 join。
    `ProjectRunRuntime.stop`（`project_management/runtime.py:54-81`，`:75` 是一次 `join(timeout_seconds)`）拆为
    `request_stop()` 与 `wait_stopped(timeout)`，后者分片 join、总时限不变；删除旧 `stop`，调用方测试一并改写（tasks 5.3）。
  - 视图与 WSGI 分派在每个请求开始时从生命周期对象取一次运行时句柄，此后不再读取。`detach()` 之后仍持有旧句柄的
    请求在第二段停止之前照常完成；第二段停止之后门面立即抛 `RuntimeNotRunning`（code `runtime_not_running`，v2.1 H6，
    AIB design §11.1 `:850`），视图按 `not_running` 渲染，不返回 500。server 的工作线程是 daemon 线程；显式退出与强制
    退出都不等待任何线程。
  - 第 2–6 步中任一步失败时，已完成的步骤按第 7 步的对应部分逆序清理，然后按决策 3 输出启动失败，经第 7.7 步退出。
  - `ai_host.state` 中只有一个生命周期对象，保存阶段（starting/running/stopping/stopped/failed）、启动或清理的错误码
    （异常的 `code` 属性，取法同 `project_serve.py:95-98`；AIB-2 导出的每个异常都带稳定的 `code`，取值只来自 AIB design
    §11.3 的单一注册表，v2.1 D9 增补 1，`ai_host` 不解析异常消息；第 1 步的 `system_check_failed` 是 `ai_host` 自有的
    code，与注册表不重名）、`project_runs.wait_stopped` 返回的
    `RuntimeStopResult` 与运行时的停止结果（`handle.stop_result`；启动失败时为
    `context.startup_failure.rollback_result`，§11.2）。`serve` 与 AI pane 只读这个对象。
- **理由**：
  - 先绑定再启动：端口冲突在 2 秒内失败，不获取状态目录锁，也不触发 project run 的恢复扫描（S0b B1：4/4 个占用用例
    0.36–0.43 秒退出，没有创建状态目录与锁）。B1 的原型在 `django.setup()` 之前 bind，不代表真实命令的耗时。本机实测
    （Django 6.0.7，2026-11-12）：`manage.py check` 10 次 2.77–4.06 秒，其中 `django.setup()` 0.54–0.61 秒、系统检查
    1.77–1.96 秒（最慢的 `check_custom_error_handlers` 1.55 秒）。按 Django 默认先跑系统检查时，端口冲突约 3 秒才
    报错；检查移到 bind 之后、bind 之前不导入 AI Base 时，到 bind 为 1.06–1.19 秒（5 次）。由 tasks 5.6 在真实命令上
    验证。
  - 自建 socket：Windows 上 `SO_REUSEADDR` 的语义是强制绑定已被占用的端口，server 自己设置它时端口被占用也不报错；
    不设置 `SO_EXCLUSIVEADDRUSE` 时，其他进程可以借 `SO_REUSEADDR` 绑定同一地址和端口并截走连接。独占绑定因此不能依赖
    各 server 的默认选项（S0b B1：waitress 自己绑定时 20/20 个连接由占用者应答）。
  - 分片等待：Windows 上 `Thread.join(timeout)` 的等待可能不被信号打断，处理器要等 join 返回后才执行。一次长 join
    会让第二次信号推迟到 join 返回才生效；分片后最迟一个分片即生效。S0b 在 CPython 3.13.7 的合成子进程
    （`s0b_sig2.py`）上测得：不分片的 `join(10)` 使第二次信号推迟 8.58–8.61 秒，分片到 0.5 秒后 0.22–0.23 秒以 130
    退出；终测 M1 在组合宿主上 8/8：第二次信号在第一次之后 1.0 秒发出，到进程实际退出 0.07–0.50 秒，退出码 130。
  - 第一段停止 2 秒：S0b B5 中支持终止事件的活动流 ≤ 1.01 秒收到终止事件，不支持的流在 2.0–3.0 秒被取消，排空合计
    2.01–2.52 秒。
  - 停止总预算 10 秒，算到进程实际退出：spike 的各段时限依次叠加（排空截止 t0 + 10 秒，flush 截止
    `max(t0 + 10, now + 2)`，线程池关闭 5 秒，循环收尾最多 5 秒），客户端一直不读取时停止到退出可能超过 10 秒（S0b
    签核第 5 项）。本设计给每段一个截止时刻：触发到 t0 0.5 + HTTP 7.5 + project run 0.5 + 运行时 1.0 + 显式退出 0.5 =
    10 秒。S0b 终测原型从检测到停止起分配 10 秒（关闭剩余连接、join `serve-http`、关闭线程池各 0.5 秒）；本设计从停止
    触发起算，多计 0.5 秒检测时间，把这三项合并为 1 秒。终测 M4 5/5 以 0 退出：没有积压时触发到进程实际退出
    0.09–0.28 秒，慢读者（积压约 8 MB、暂停 3 秒）3.17 秒，一直不读取的客户端在 flush 截止后被关闭，6.69 秒；flush
    截止之后到进程实际退出约 0.06 秒。flush 截止 t0 + 6.5 秒晚于签核补测中慢读者的 EOF（5.95 秒）。10 秒是预算，不是
    硬上限：每段截止由两段式看门狗兜底（决策 3），而持有 GIL 的长 C 调用会挡住看门狗，此时依靠外层的强制结束（启动脚本
    15 秒，Docker `--stop-timeout 690`）。
  - 显式退出：签核补测中，宿主记录退出之后进程还要 0.96–1.16 秒才实际退出（M4 5/5），这段不在 10 秒预算内，也不受
    看门狗约束。终测步骤 A 拆分（5 次）：`threading._shutdown` 0.12–0.19 毫秒，atexit 回调 0.17–0.27 毫秒，模块清理与
    GC 到进程结束 849–915 毫秒；线程都已结束时，这段几乎全是解释器释放对象。运行时的循环线程是非 daemon 线程（v2.1
    H6），它没有按时结束时 `threading._shutdown` 会一直等待。`os._exit` 去掉这段不受控的时间：终测 M4 中
    `close_all()` 与 `logging.shutdown()` 合计约 0.1 毫秒，`os._exit` 到进程实际退出 44–61 毫秒。持久状态不依赖解释器
    收尾：SQLite 中已提交的事务不依赖关闭连接，日志由 `logging.shutdown()` 显式 flush，运行时在离开 `with` 块时
    已写完持久状态并关闭自己的资源（v2.1 H6，R24）；运行时停止超时、仍有线程在写时退出，与进程被杀死时相同，由下次启动的
    恢复处理。步骤 A 只在旧宿主、stop-file 触发、无流且空闲时测得，只记录了 atexit 回调的数量而没有身份：它说明显式退出
    省掉了多少时间，不能证明跳过这些收尾是安全的；安全性由运行时的 R24 与宿主的退出清点（R24-host）保证（复签 B）。
  - 主线程上没有事件循环：`ProjectRunRuntime.start()`（`project_management/runtime.py:39-43`）中访问 ORM 的
    `reconcile_interrupted()`（`services/project_run_recovery.py:17-29`）与 `stop()` 中的线程等待都可以直接调用；worker
    经 blocking 门面调用运行时，由运行时的循环线程推进，不会死锁。
  - 第一段停止先于排空：每条打开的流占用一个 server 线程，不先结束流，排空就要等到时限。
  - 先停 worker、后完整停止运行时：第一段停止不影响 blocking 门面，worker 的最后一次调用仍有运行中的运行时。
  - 620 秒 = `RunPolicy.timeout_seconds` 600（`app/domain/run_contracts.py:33`）加宽限，等于 `project_serve.py:70`。
    拆成 `request_stop` 与 `wait_stopped`：看门狗要在等待之前知道是否有执行中的 run（放宽），并在等待结束时立即收紧。
  - Proactor 由 `start_blocking` 保证（v2 D8、v2.1 H6）并由宿主一致性套件断言，Metrics 不再自定检查与错误码。
- **否决的备选**：在 `AppConfig.ready()` 启动 worker（非服务进程也会启动）；HTTP server 占用主线程（停止顺序只能放进
  server 的回调或另一个线程，各 server 的回调语义不同，而信号处理器只在主线程执行；waitress `run()` 在主线程时，
  处理器还要等 `select` 返回，`asyncore_loop_timeout` 默认 1 秒，第二次信号不能保证 1 秒内生效）；先排空再做第一段
  停止（见理由）；在运行时的循环线程上启停 project run（`start()` 访问 ORM，`stop()` 等待的 worker 正需要这个循环
  推进）。

### 决策 3：`manage.py serve` 取代 `project_serve`

- **决定**：
  - 新命令 `ai_host/management/commands/serve.py`；删除 `project_serve` 及 `project_management/tests/test_project_serve_command.py`。
  - 地址：`--host` 默认 `127.0.0.1`。回环判定为 `host == "localhost"` 或 `ipaddress.ip_address(host).is_loopback`，
    无法解析为 IP 的主机名按非回环处理（取代 `project_serve.py:30` 的固定集合）。非回环绑定（如容器内的 `0.0.0.0`）
    按 owner 决定允许，另有两条规则：settings 允许匿名决定审批（只有 development settings，决策 14）时以
    `CommandError` 拒绝，避免匿名审批暴露到网络；未配置 Basic 用户时输出一条 `serve_anonymous_network_bind`
    警告，只含绑定地址。
  - 不提供 workers、reload 或线程数参数：单进程、单副本（v2 §8.9），线程数与在途上限只来自 settings（决策 1）。
  - 停止触发：SIGINT（Ctrl+C）、SIGTERM、Windows 上的 SIGBREAK（Ctrl+Break 或 `CTRL_BREAK_EVENT`），以及保留的
    `--stop-file`（绝对路径）与 `--lifetime-seconds`（`project_serve.py:24-25,117-130`）。`serve` 在主线程为这些信号
    安装处理器，处理器只设置停止事件；监视线程以不超过 0.5 秒的间隔检查，在文件出现或到期时设置同一个事件；主线程按
    决策 2 第 6 步的间隔检查该事件，然后执行决策 2 第 7 步。停止事件已设置后（无论由哪种触发设置）再收到其中任一信号
    时，处理器写出 `serve forced exit.`，flush 后立即 `os._exit(130)`，1 秒内退出（依赖决策 2 的分片等待与
    `serve-http` 线程布局）；中断的运行由下次 `start()` 的恢复标记出来。
  - 输出与退出码，只输出错误码，不输出异常消息或 traceback：
    - 绑定失败：`serve bind failed.`；
    - 运行时或 project run 启动失败，包括启动时限到期（决策 2 第 2 步）与 bind 之后的系统检查失败（`system_check_failed`，
      决策 2 第 1 步）：`serve startup failed (<code>).`；
    - 运行时在运行期意外结束：`serve runtime failed (<code>).`（决策 2 第 6 步）；
    - 停止后未干净结束（`stopped` 为假或 `unresolved` 非空、运行时停止超时、有清理错误码、第 7.7 步的关闭失败或退出
      清点不通过，或看门狗到期），或启动时限到期后运行时没有按时回滚：`serve cleanup failed.`，有错误码时附带；
    - 退出码：干净停止为 0；绑定、启动或运行期失败为 1；清理失败或看门狗到期为 3（与 1 同时出现时取 3）；停止期间再次
      收到信号时为 `serve forced exit.`，退出码 130。每条路径都在写出并 flush 最后一行后经 `os._exit` 结束进程（决策 2
      第 7.7 步）。
  - `project_runtime_stopped` 事件格式不变，仍由 `scripts/validation/project_full_stack_identity.py:304` 消费。
  - waitress 的启停调用（S0b §4.2，spike 的 server 适配见 `s0b-spike-report.md` §2）：
    - 构造：主线程调用 `create_server(app, sockets=[sock], threads=14, channel_request_lookahead=1,
      max_request_body_size=N + 1)`，不传 `listen`
      （3.0.2 不允许与 `sockets` 同时传入，`adjustments.py:296-297`），也不修改 waitress 的类属性。传入 `sockets` 时
      waitress 以 `bind_socket=False` 构造 server（`server.py:91-101`），`server.socket` 就是预绑定的 socket。
      `Adjustments` 构造时仍按类默认值 `0.0.0.0:8080` 调用一次 `getaddrinfo`（`:146,368`），这是 IP 字面量的解析，不
      访问网络，传入 `sockets` 时结果不用（`server.py:73`）。spike 在构造期间替换类默认值，只是为了通过它自己的网络
      守卫（`s0_common.py:77-80`），实现不照搬；在进程内构造 server 的测试，其网络守卫要放行 IP 字面量的解析（现有的
      `scripts/validation/run_report_authoring_tests.py:21-30` 只放行回环名）。
    - 请求体上限（复签 D）：waitress 以 `>=` 判定超限（`parser.py:154-162,175-180`），所以 `max_request_body_size` 设为
      N + 1，长度为 N 的请求体可以通过。N = max(`request_body_policy(settings, apps).max_request_body_bytes`, Django
      侧最大的合法请求)（N1，AIB design §11.1 `:780-787`、§2 `:108-116`，`fc4db2f`），在启动任何运行时资源之前（决策 2
      第 2 步之前）计算；`request_body_policy` 是纯函数。Django 侧最大的是 `RECOVERY_LIMIT` 1 MiB
      （`project_management/app/domain/report_recovery.py:12`），multipart 为 KB 级。Metrics 不经 settings 放大路由
      上限，运行时侧最大的是 `chat.message` 的 8388608 字节（§10 B 类冻结值，`:664`），所以 N = max(8388608, 1048576)
      = 8388608，`max_request_body_size` = 8388609。L0 在调用应用之前读完请求体，超过 512 KiB 写入临时文件，最坏占用约
      N × `connection_limit`（100）= 838860800 字节，约 800 MiB（见 Risks）。waitress 的 400 与 413 错误页带
      "(generated by waitress)"，测试据此区分拒绝来自 L0 还是适配器。
    - 受理：`serve-http` 线程运行 `server.run()`，主线程只处理信号与停止编排。S0b 改后宿主与终测宿主都用这种布局
      （终测 M1–M6），tasks 5.6 持续验证。
    - 停止受理：经 `server.trigger.pull_trigger(...)` 在 waitress 的 asyncore 循环上关闭监听 dispatcher，已有连接的
      读写不受影响（S0b：终止事件在其后 0.8–1.9 毫秒写出）。停止期间 L1 返回的 503（固定文本、`Retry-After: 2`、先于
      认证，决策 1）不带 `Connection` 等 hop-by-hop 头（PEP 3333；waitress 遇到会抛 `AssertionError`）。
    - 排空：waitress 的工作线程是 daemon 线程（`task.py:61`），所以宿主自己统计在途请求（运行时适配器与 Django 两路），
      计数在响应迭代器的 `close()` 中减少，不在 `__call__` 返回时减少（否则流式响应不计入排空，S0b 中 Django 的
      `StreamingHttpResponse` 在 2.10 秒被截断）。Django 的流式视图（目前没有）必须在停止事件后结束。
    - 收尾（flush）：先等工作线程空闲（`task_dispatcher.active_count` 为 0），再给每个 channel 设
      `close_when_flushed`，直到 channel 数为 0 或到期（决策 2 第 7.3 步）；然后 `server.close()`，`server.run()` 返回后
      由 `serve-http` 线程执行 `task_dispatcher.shutdown(cancel_pending=True, timeout=0.5)`。不用 waitress 默认的关闭
      方式：它对每个 channel 调 `handle_close()`，丢弃未写出的输出缓冲，慢读的客户端收不到终止事件。S0b b5s 在
      stop-file 触发下测得：积压约 8 MB、暂停 3 秒的慢读者，默认关闭时 FAIL；flush 时 3.31 秒收到终止事件，7.08 秒
      以 0 退出。终测 M4 在显式退出的原型上验证了 flush 与 stop-file、SIGINT、`CTRL_BREAK_EVENT` 的组合，以及一直
      不读取的客户端（决策 2 理由）。
  - 看门狗（两段式，owner 于 2026-11-11 决定）：t0 时启动一个 daemon 线程，一直保持到第 7.7 步的 `os._exit`，截止时刻
    由主线程按决策 2 第 7.4 步调整：
    - 初始截止 t0 + 9.2 秒；`project_runs.request_stop()` 返回真（有执行中的 run）时放宽到 t0 + 659.2 秒；
      `wait_stopped` 在 T 返回后改为 min(当前截止, T + 1.2 秒)；
    - 到期时由一个辅助线程写出 `serve cleanup failed.` 并 flush，看门狗最多等 0.1 秒，然后 `os._exit(3)`；
    - 算术：触发到 t0 0.5 + HTTP 7.5 + project run 0.5 + 运行时 1.0 + 显式退出 0.5 = 10；10 − 0.5 − 0.3（看门狗到期到
      进程退出，终测 `os._exit` 到进程退出 44–61 毫秒）= 9.2；有 run 时 0.5 + 659.2 + 0.3 = 660（决策 16）；run 停止后
      1.2 = 运行时 1.0 + 显式退出 0.5 − 0.3。
    它兜住 server、适配器、运行时调用或第 7.7 步卡住的情况，正常停止远早于截止。持有 GIL 的长 C 调用会挡住看门狗，
    此时由外层强制结束兜底（启动入口 15 秒，Docker `--stop-timeout 690`）。
  - 启动入口与停止脚本（tasks 9.7）：一律以 `--stop-file` 启动 `serve`；停止时先写入该文件，等待不少于 15 秒（停止触发
    到进程实际退出的 10 秒预算加余量）仍未退出，才按 PID 强制结束并输出该 PID。执行中的 project run 因此可能被强制
    结束，由下次 `start()` 的恢复标记为中断。
- **理由**：
  - 错误输出只含错误码，沿用 `project_serve.py:95-98` 不泄露细节的约定；停止事件与停止参数保留，现有验证断言不变。
  - Windows 父进程无法可靠地向子进程发送 Ctrl+C，验证脚本依赖 `--stop-file` 与 `--lifetime-seconds`。启动入口也用
    stop-file：`Stop-Process`（`TerminateProcess`）不经停止顺序直接结束进程，不带 `/F` 的 `taskkill` 对没有窗口的
    进程无效，以 `CREATE_NO_WINDOW` 启动的进程与调用方不共享控制台、收不到调用方发出的 `CTRL_BREAK_EVENT`。
  - SIGBREAK：Windows 上其他进程无法投递 SIGTERM（`os.kill` 传入非 CTRL 信号时调用 `TerminateProcess`），能投递的是
    `CTRL_BREAK_EVENT`，前提是子进程以 `CREATE_NEW_PROCESS_GROUP` 启动。S0b B5 的基础矩阵（3 个 server × 3 种触发，
    默认关闭方式，空闲流不要求终止事件）中 stop-file、`CTRL_BREAK_EVENT` 与 SIGINT 共 9/9 次以 0 退出，每次恰好
    一条 `project_runtime_stopped`。
  - flush 收尾与看门狗：S0b 的停止测量覆盖了预绑定、停止受理、排空与 flush（`s0b-spike-report.md` §3.1、§4.2），
    终测 M4 覆盖了 flush 与三种触发的组合；看门狗对应 §4.2 的兜底要求（spike 在 drain + 25 秒后强制退出，B5 中 cheroot ×
    a2wsgi 卡住时实际触发）。单段截止 t0 + 660 秒在没有执行中的 run 时兜不住 10 秒预算（复签 E）；两段式的三个常数都由
    各段预算推出，没有 run 时在预算内退出，有 run 时在 660 秒内退出，run 停止后只留运行时停止与显式退出的时间。到期时的
    写出放在辅助线程中，stdout 管道不再被读取时也挡不住退出；第 7.7 步的各项因此都在看门狗截止之内。
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
  - 失败按 AIB design §11.3 `:1056-1065`（`fc4db2f`）处理：App 把业务失败转成指定的 `ToolError`，或返回类型化的业务
    数据，不新增 code。越界抛 `ToolError("context_boundary_violation")`（决策 7），载荷与摘要不符抛
    `ToolError("preview_digest_mismatch")`（决策 8）。草稿 findings、`needs_metric_recipe`、`binding_unresolved`、会话
    没有 `ContextRef` 与 Grafana 导入失败都以类型化的业务结果返回（tool 或 context provider 的返回值，带状态与
    findings），不是运行时错误；publish preview 中的拒绝见决策 8 与 Open Questions 9。必须中止且没有更具体的 code 时
    抛 `ToolError()`（`tool_failed`，`:1052`）；`ToolError` 只带 code，消息是注册表的固定文本。未预期的异常交给运行时
    净化，failure records 只含注册 code（`:1076-1087`）；映射到哪个 code 未冻结，Metrics 不依赖（Open Questions 8）。
- **理由**：tool 调用由运行时在 Django 请求处理之外调度，没有 `ThreadSensitiveContext`；`thread_sensitive=True` 会把
  所有调用串到一个共享线程上，并发 tool 调用互相排队，任一调用等待另一个 thread-sensitive 调用就会死锁。Django 连接
  按线程保存，请求信号不会为 tool 调用触发，所以要手动 `close_old_connections()` 来遵守 `CONN_MAX_AGE` 并丢弃失效连接。
  v2 §5.2 的草图已改为同一个 helper。`ToolError` 不带调用方消息（AIB design §11.3 `:1056-1061`），模型需要的业务原因
  只能经 tool 的返回值传递。
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
  - `ai_host.settings` 中构造 `HostConfig` 的函数读取 `METRICS_AI_MODEL_BASE_URL`、`METRICS_AI_MODEL_NAME`、
    `METRICS_AI_MODEL_API_KEY`（`SecretStr`）；`build_settings()` 只构造 `RuntimeSettings`，不读模型变量。三项只来自
    环境变量，不进数据库，不出现在页面或日志中。
  - 三项齐全时设置 `HostConfig.model = ModelConfig(provider=..., name=..., base_url=..., api_key=...)`（AIB design
    §11.1 `:724-733`、`:748-749`；`provider` 的来源见 Open Questions 6）。任一缺失时 `HostConfig.model` 为 `None`，
    运行时照常进入运行期，task run 准入返回 `model_not_configured`，AI pane 显示 `not_configured` 并只列出缺失的变量名。
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
  - 页面视图在 WSGI 线程上经 blocking 门面取得嵌入路径：`handle.blocking.chat.open_session(principal, app_id="metrics",
    agent=..., context_ref=..., session_key=f"metrics.workbench.{profile_id}", timeout=...)` 返回 `SessionView`，嵌入
    路径取其 `embed_path`（D7、v2.1 H6，AIB design §11.1 `:826-829`、`:843-845`、`:856-861`，`fc4db2f`）；运行时按
    `(principal.id, app_id, session_key)` 复用会话，同一个键对应不同的 agent 时为冲突。session_key 必须完整匹配
    `[A-Za-z0-9._:-]+`、以 `<app_id>.`（即 `metrics.`）开头、不超过 200 个 ASCII 字符；`None` 新建会话，空串非法；
    运行时不做规范化、截断或大小写折叠，不合法时报 `session_key_invalid`（422，§11.3 `:1023`）。profile id 为
    `[a-z0-9][a-z0-9._-]{0,159}`，`metrics.workbench.{profile_id}` 最长 178 个字符，满足这些规则，`ai_host` 不另做编码。
  - range、图表或 bucket 变化时，页面局部刷新得到新的 `ai_context_ref`，经 `embed-host.js` 发送 `context-changed`，
    运行时把同一会话重新绑定（进程内等价调用为 `handle.blocking.chat.bind_context(principal, session_id, context_ref,
    timeout=...)`，§11.1 `:830-832`），不新建会话。
  - `ContextRef(kind="metrics.workbench", values=...)` 只含标识：binding key、profile id、provider、range、chart id、
    bucket/series、已选 ticket id。值只能是 str/int/bool 或它们的扁平列表，规范化后不超过
    `RuntimeLimits.max_context_ref_bytes`（4 KiB）。ticket id 最多 50 个，超出数量或字节上限时按选择顺序保留能放入的
    最长前缀，并附带 `ticket_ids_total` 与 `ticket_ids_truncated`，让模型知道列表不完整。`ai_host` 在服务端由
    `WorkbenchPageQueryState` 构造，页面只转发。
  - `WorkbenchContextProvider` 的 `validate(principal, ref)` 检查标识对当前 principal 可见，`resolve(principal, ref)`
    生成安全摘要；tool 再用 `ctx.context_ref`（运行开始时的快照，D5）复核参数，越界抛
    `ToolError("context_boundary_violation")`（AIB design §11.3 `:1053`）。
  - 同源 iframe，`embed-host.js` 地址取自 `handle.ui.asset_url("embed-host.js")`（§11.1 `:812`）。审批只在嵌入的运行时
    UI 中决定，Metrics 不另建审批视图。
  - 页面视图对 `chat.open_session` 的调用以门面方法必填的 keyword-only 参数 `timeout` 设置 1 秒时限（§11.1
    `:843-844`），并先取得一个上限为 2 的非阻塞信号量（小于页面保留的 6 个线程，决策 1），两者是 `ai_host.settings`
    中的常量。门面等待超时（`RuntimeCallTimeout`，§11.1 `:851`）或信号量已满时 pane 显示"暂时不可用，可重试"，门面抛
    `RuntimeNotRunning`（`:850`）时显示 `not_running`；两种情况页面都照常返回 200。
- **理由**：一个 profile 对应一个持续的工作台对话；上下文只传标识，数据在服务端按 principal 拉取，越界校验不依赖页面。
  pane 嵌在每个 workbench 页面中，门面调用有时限与并发上限，运行时变慢或卡住时不会占满页面线程。S0b B2 中视图内
  门面调用的 p50 为 0.30–0.49 ms；循环卡住 3 秒时，0.3 秒时限的调用在 0.303 秒返回。取 1 秒时，循环卡住期间页面最多
  慢 1 秒，最多 2 个页面线程在等待。
- **否决的备选**：按 binding key 建会话（切换范围就丢失对话）；每个 principal 一个会话（不同 profile 的上下文混在一起）；
  不传 session key（每次打开都新建会话）；在 `ContextRef` 中放图表数据或 ticket 正文（超限，也无法校验）。

### 决策 8：发布审批绑定确定性预览，结果写入 `AiChartPublication`

- **决定**：
  - `publish_chart` 声明 `effect="external"` 与 `preview=preview_chart_publication`。preview 只读且确定（同样的参数和
    数据产生同样的字节），返回 `{dashboard, target:{grafana_base_url, uid}}`；运行时用 `canonical_digest` 绑定审批（D6）。
  - preview 不能继续时（数据未就绪、`needs_metric_recipe`）的处理依赖上游冻结 preview 的拒绝语义（Open Questions 9）：
    冻结契约中 preview 只能返回内容或抛 `ToolError`。`ai-dashboard-publish-authority` 中"语义不受支持"与"Jira 数据
    未就绪"两个场景暂不改写，按 Open Questions 9 的结论落实。
  - uid 由 Metrics 按工作流信封与 profile 渲染配置确定，不取自模型参数；`grafana_base_url` 取自设置。
  - handler 只反序列化 `ctx.approval.preview`，复核 `canonical_digest(...) == ctx.approval.preview_digest`（否则
    `ToolError("preview_digest_mismatch")`，AIB design §11.3 `:1054`，`fc4db2f`），只导入已批准的字节；操作者取
    `ctx.approval.decided_by`（`Principal`，身份取其 `id`，§11.1 `:762-763`、`:864-868`），幂等键为 `ctx.tool_call_id`。
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
  - `ai_host.task_runs.RuntimeTaskRunPort` 在 `handle.blocking.task_runs` 上实现端口（`start(principal, request)` 调用
    `task_runs.start(principal, request, timeout=30)`，运行时侧的 `request` 为 `RunSubmit`，`timeout` 是门面方法必填的
    keyword-only 参数，AIB design §11.1 `:833`、`:843-848`，`fc4db2f`）。服务进程由组合根经
    `build_project_runtime(task_runs=port)` 注入，该函数移到 `app/api/project_runs.py`；CLI 由 `ai_host` 的
    `AppConfig.ready()` 注册 CLI 端口工厂，工厂被调用时才导入 `ai_host.wiring` 并进入 `local_task_run_port`（基于
    `start_blocking`；决策 2 第 1 步），project_management 经 `open_local_task_run_port()` 使用。
  - 端口原样传递运行时的错误 code（准入时的 `RuntimeOperationError` 与运行结果中的 `RunSnapshot.error.code`）及其恢复
    类别。类别是 AIB design §11.3 注册表的 Retry 列（`:982-985`）：`correct` 需要更正输入；`observe` 用同一个键查询或
    重试，不重新派发；`repair` 需要配置、状态或操作者修复；`fresh` 需要确认清理完成并换用新的运行时；`no` 禁止自动
    重试。准入示例（`:1030-1040`）：correct 为 `profile_not_declared`、`input_schema_invalid`、`input_hash_mismatch`、
    `input_too_large`、`limit_exceeded`、`idempotency_conflict`；repair 为 `profile_disabled`、`model_not_configured`、
    `idempotency_capacity_exhausted`、`unknown_exposure_limited`；observe 为 `admission_limited`。
  - 类别按 code 从注册表取，不由旧词换算：同一个旧词 `stop` 对 `run_not_found` 与 `backend_failed` 是 `observe`
    （`:1041`、`:1051`），对 `profile_disabled` 与 `model_not_configured` 是 `repair`。读取类别的方式未冻结（Open
    Questions 10），冻结前不在 Metrics 中复制注册表；"请求被拒"的判定一并改写（tasks 5.2）。
  - 运行时未运行（`RuntimeNotRunning`，类别 `fresh`）或门面等待超时（`RuntimeCallTimeout`，类别 `observe`，v2.1 H5，
    §11.1 `:850-851`）为 `RUN_UNAVAILABLE`，`RuntimeBusy` 为 `RUN_BUSY`；这几项按异常类型映射。
  - CLI 的启动时限与清理（上游增补 1，Q11）：`local_task_run_port` 以 `start_timeout=RUNTIME_START_SECONDS` 调用
    `start_blocking`，启动时限到期（`RuntimeStartTimeout`，code `start_timeout`）为 `RUN_UNAVAILABLE`。启动回滚或
    退出 `with` 块时的第二段停止没有按时完成时（`context.startup_failure.rollback_result` 或 `handle.stop_result` 的
    `completed` 为假，AIB design §11.2、§11.5），运行时的非 daemon 循环线程可能仍然存活，解释器收尾会一直等它：端口
    工厂以 project_management 自有的错误类型报告清理失败（带错误码），`project_run` 照常写出 JSON 结果或错误，再向
    stderr 写 `project_run cleanup failed.`（有错误码时附带），flush stdout 与 stderr 后 `os._exit(3)`，不等待该线程；
    与退出码 1 同时出现时取 3，与 `serve` 一致（决策 3）。第二段停止未按时完成是原有的缺口，与启动回滚的处理相同，
    一并解决。
  - 每次 `start` 都带 `client_run_key`，取现有的 `clientRunKey`（attempt id 或 assist id，`out/ai_task_contract.py:102`、
    `services/report_assist_wire.py:21`）；运行时按 `(principal.id, app_id, client_run_key)` 去重（v2 D9，AIB design §7
    `:504-505`），超时后以同一个键重试不会产生第二次运行（§11.1 `:854`）。
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
  不可单独配置；运行时在进入 `start_blocking` 返回的 context（`with context as handle`）时获取
  `state_dir/.runtime.lock`，停止后释放。该锁是 OS 级文件锁（v2.1 D8），持有进程以任何方式终止（包括 SIGKILL）都由
  操作系统释放。服务进程持锁时，`project_run --execute-local`（现流程见 `management/commands/project_run.py:84-98`）
  经 `start_blocking` 得到 `RuntimeBusy`（code `runtime_busy`），映射为 `RUN_BUSY` 并提示通过服务提交，不等待、
  不换目录。进程内的 project run 注册表（`project_management/runtime.py:178-193`）只由组合根安装。
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
    `authenticate` 是普通函数（同步托管，v2.1 D3），由运行时的 WSGI 适配器在 WSGI 线程上、准入之前调用：它只解析
    请求头与 settings，不访问数据库，未认证的请求因此不占 `/ai` 名额，也不进入循环（决策 1）。
  - Basic 用户设置改为 fail-closed：`METRICS_BASIC_AUTH_USERS` 未设置或为空字符串表示未配置；其他取值必须是至少有一个
    条目、键和值都是非空字符串的 JSON 对象，否则 settings 加载时抛 `ImproperlyConfigured`，消息只含变量名。
    `check_basic_authorization` 只把 `None` 视为未配置，非空字典以外的其他值一律拒绝。现状下 JSON 数组、非对象 JSON
    或 `{}` 会让中间件静默停用认证（`metrics/middleware.py:18-31,36-37`）。
  - 401 带 `WWW-Authenticate: Basic realm="Restricted"`（`metrics/middleware.py:59-62`）；运行时路由的 401 使用宿主
    提供的同一质询头（v2.1 D3），浏览器在两边弹出同一个登录框。
  - `HostConfig.allow_anonymous_approval`（默认 `False`，运行时唯一的匿名决定策略，AIB design §11.1 `:732`、§2 `:80`，
    `fc4db2f`）只在 development settings 中以常量设为 `True`，不读环境变量（Q5）；`can_decide` 返回真，匿名与模型的
    拒绝由运行时完成。`manage.py` 默认使用 production settings（`manage.py:9`），所以发布审批至少需要一个 Basic 用户
    （`METRICS_BASIC_AUTH_USERS`）；没有时 AI pane 提示配置，read tool 照常可用。
  - 审计分两处：运行时把会话、tool 调用与审批事件经事务性 outbox 至少投递一次（增补 A6，Open Questions 11），
    `record_audit` 经决策 4 的 helper 写入 `ai_host` 自有的只追加审计表，以 `event_id` 为唯一约束，同一事件再次投递时
    不新增行、不报错；不写 `BugTrendAuditEvent`；运行时交来的认证失败事件不写数据库，只输出一条结构化日志
    `ai_auth_failed`（path、客户端地址、原因，不含凭据）。
  - `record_audit` 在有界时间内返回或抛错，这是 A6 的宿主义务，运行时不为 outbox 投递另设时限（owner 2026-11-12 确认）：
    一次投递只做一次插入，插入冲突视为已写入并正常返回（不先查后插）；等锁不超过 SQLite busy timeout（`sqlite3` 默认
    5 秒，`DATABASES` 未覆盖），超时抛错，由运行时退避重投。stop 时被取消的投递之后会再次投递，可能与仍在执行的上一次
    插入并发，唯一约束保证只有一行。
  - `HostConfig.allowed_hosts` 取自 Django `ALLOWED_HOSTS`（默认只有回环，`defaults.py:21`）；挂载路径 `root_path`、
    状态目录 `state_dir`、模型 `model` 与 `network`（`NetworkPolicy`）都由 `ai_host.settings` 生成（§11.1 `:724-733`）。
    L1 对所有路径（包括静态文件）用 Django 的同一规则与 `ALLOWED_HOSTS` 校验 Host（决策 1），挂载路径下的请求再由
    适配器用同一白名单校验一次；静态文件不豁免（复签 D：现状下 WhiteNoise 在 `CommonMiddleware` 之前返回，静态文件
    不经 Host 校验）。
- **理由**：同一请求在 Django 和运行时两侧的认证结果必须一致（见 `embedded-ai-runtime-host`）；Basic 用户设置写错时
  进程必须启动失败，而不是静默放行全站；审批权限是安全控制，不能被环境变量打开（v2 §8.5）；运行时的会话、tool 和
  审批事件与 bug_metrics 的业务审计语义不同。运行时至少投递一次，重复投递时报错会让运行时反复重试同一事件，所以按
  `event_id` 去重并正常返回。运行时不为 outbox 投递设时限：取消只停止等待，不停止写库的工作线程，每次重试都会多占
  一个线程；有界因此由宿主保证，与 `authenticate` 相同（AIB design §2 `:129-130`）。认证失败可由未认证的请求无限触发，
  写入数据库会让审计表无限增长，并在 SQLite 上争用写锁；结构化日志足以排查。
- **否决的备选**：运行时自己做认证（与 Django 不一致）；用环境变量开启匿名审批；把运行时审计写进
  `BugTrendAuditEvent`（混淆业务审计，且该表不归 `ai_host`）；认证失败写入审计表（理由见上）；静态文件豁免 Host 校验
  （Host 校验是 DNS rebinding 的防线，只比较请求头，豁免没有收益，复签 D）。

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
    让 `docker stop` 走决策 2 的停止顺序。Docker 默认 10 秒后发送 SIGKILL；进程内停止预算 660 秒 = 停止触发到进程实际
    退出的各段合计 10（决策 2 第 7 步）+ `project_runs.wait_stopped` 620 + 余量 30。两段式看门狗（决策 3）按段兜底：
    有执行中的 project run 时截止 t0 + 659.2 秒，触发后 660 秒内退出；没有时截止 t0 + 9.2 秒，停止在 10 秒预算内完成。
    README 要求 `docker run --stop-timeout 690`（Compose 用
    `stop_grace_period: 690s`），在进程内停止预算之外再留 30 秒余量；被提前杀死时，
    状态目录锁由操作系统释放（决策 12），中断的运行由下次 `start()` 的恢复标记出来，不会静默丢失。
  - 只允许一个副本：`METRICS_STATE_DIR`（镜像内为 `/metrics/state`）挂载为卷，数据库与 `ai-base/` 状态目录随卷持久化；
    第二个副本挂载同一个卷时，进入 `start_blocking` 返回的 context 时抛 `RuntimeBusy`（code `runtime_busy`），`serve`
    输出 `serve startup failed (<code>).` 并以 1 退出（决策 3）。
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
  输出 `serve runtime failed (<code>).` 并以 1 退出，不在没有运行时的情况下继续服务（决策 2）；pane 的门面调用有时限与
  并发上限（决策 7）。
- [两套依赖进入同一个 venv 后冲突] → 单一 requirements；S0 与 S0b 用 `pip check` 验证；`ai-base-runtime`、`waitress` 与
  `portalocker` 精确固定（决策 1）。
- [`ai_host` 依赖 waitress 的内部接口（`trigger.pull_trigger`、channel 的 `close_when_flushed`、`task_dispatcher`）与
  传入 `sockets` 时不再绑定的行为] → `waitress==3.0.2` 精确固定；5.6 的命令测试覆盖这些调用；升级 waitress 时重跑 S0b
  的 B1、B4、B5、B9 子集与宿主一致性套件（决策 1）。
- [流式响应的未发送输出超过 waitress 的 `outbuf_high_watermark`（默认 16 MB，`adjustments.py:215`）后，写该响应的
  工作线程阻塞到客户端读取或断开（`channel.py:394-415`；一次写出的响应与 WhiteNoise 的文件响应不受影响）] → Metrics
  目前没有 Django 流式视图，聊天流的事件与心跳达不到 16 MB 的积压，S0b、补测与终测只测到约 8 MB；停止时若出现，排空用满
  截止时刻并记入清理错误码，flush 到期后关闭剩余连接（关闭会唤醒阻塞的线程，`channel.py:307-318`），`serve` 仍在
  10 秒预算内以 `serve cleanup failed.` 退出，退出码 3（决策 2 第 7 步）。作为已知限制接受，不调整该值。
- [L0 在调用应用之前读完并缓冲请求体，未认证的请求也能让进程写临时文件] → `max_request_body_size` 显式设为 N + 1
  （决策 3）；超过 512 KiB 才写临时文件，最坏占用约 N × `connection_limit`（100），N = 8388608 字节时为 838860800
  字节，约 800 MiB，位于系统临时目录。需要更紧的上限时由反向代理限制请求体。
- [运行时按合作式时限读取已缓冲的请求体，进行中的单次读取不被抢占（OD-W1-1）] → 读取源只有本机内存或临时文件，慢客户端
  停在 L0，不占 WSGI 线程与运行时名额；本机磁盘读卡死属于整机故障，读取返回之前占住一个 WSGI 线程与一个短请求名额，
  停止时由两段式看门狗兜底（决策 3）。
- [经 `serve` 的 Django 路径上，非法 Host 且不带凭据的请求由 401 变为 400] → 有意的行为变化（决策 1）：Host 校验移到
  L1 最前；Django 测试客户端不经分派，现有测试不受影响；定序矩阵（tasks 5.10）断言新行为。
- [持有 GIL 的长 C 调用挡住看门狗线程] → 看门狗只能兜住释放 GIL 的卡顿；最终上限依靠外层强制结束：启动入口等待
  15 秒后按 PID 结束，Docker `--stop-timeout 690` 后发送 SIGKILL（决策 3、16）。
- [发布耦合：AIB-2 与 MDB-2 必须同版本，回滚也要一起回滚] → 精确版本固定；宿主一致性套件是升级门禁；回滚按
  Migration Plan 整体恢复。
- [blocking 门面误用或 `asyncio.run` 回流导致死锁] → 在循环线程调用门面立即 `RuntimeUsageError`；残留 gate 用 AST 检查
  `services/report_assists.py`、`services/project_run_worker.py` 与 `ai_host/` 中没有 `asyncio.run`；Metrics 只在
  `serve` 主线程、WSGI 线程与 worker 线程上调用门面，运行在循环上的 tool 只经 `run_sync` 调用 Metrics 公共 API（决策 4）。
- [project run 在 620 秒内没有停下] → `RuntimeStopResult.unresolved` 记录未停止的操作，`serve` 以 3 退出，看门狗截止
  t0 + 659.2 秒兜底（决策 3）；下次 `start()` 的恢复把中断的运行标记出来，不会静默丢失。
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
- [关闭时打开的聊天流让停止无限等待] → 运行时第一段停止让打开的流在 t0 + 2 秒之前发送终止事件后结束（v2.1 H2）；收尾
  按 flush 方式等输出缓冲写完，慢读的客户端也在连接关闭之前收到终止事件；HTTP 各段到期后关闭剩余连接，运行时停止有
  时限，从停止触发到进程实际退出的预算为 10 秒，由两段式看门狗按段保证（决策 2 第 7 步、决策 3）；第二段停止取消未完成的运行并标记中断。S0b B5 实测：
  基础矩阵 9/9 次以 0 退出，排空 2.01–2.52 秒；积压约 8 MB 的慢读客户端在 waitress 默认关闭方式下丢失终止事件，flush
  收尾（stop-file 触发）时收到。spike 的停止总时长没有上界；终测 M4 在 10 秒预算与显式退出下 5/5 以 0 退出，一直不读取
  的客户端 6.69 秒退出（决策 2 理由），5.6 的命令测试持续验证。
- [AI Base 真实聊天流的终止事件没有在 S0b 中走通（用同类 Starlette 端点代替，S0b §7 第 2 项）] → AIB-2 按 v2.1 H2
  （R15）实现并由宿主一致性套件断言；10.4 用 AIB-2 wheel 重跑 B5。
- [`/ai` 流占满 server 线程，页面没有线程可用] → 每个 `/ai` 在途请求（包括整条流）占用一个 server 线程；流与其他 `/ai`
  请求分开限额（4 与 4），两者之和小于线程数 14，页面至少保留 6 个线程；UI 资产与未认证的请求不计入名额；超限立即
  返回 503 与 `Retry-After`，不排队（决策 1，v2.1 H7）。S0b B9 首轮实测（线程 8 与 12、上限 2、资产计入名额）：流占满
  限额时，分开限额下短请求 20/20 返回 200，共享一个上限时 20/20 得到 503（(b)，线程 8）。终测 M2 在新配置下同一次饱和
  中页面 12/12，短请求 1944/1944 返回 200 且小于 100 毫秒；10.4 用 AIB-2 wheel 复测。
- [`/ai` 名额泄漏，AI pane 永久得到 503] → 准入在 wheel 的适配器中实现（v2.1 H7，R19）；请求正常结束、出错、客户端
  中止或停止时名额都归还（R22），由宿主一致性套件断言（v2.1 §9 第 4 条）；终测 M5 15/15：中止 4 条流后新流 4/4 在
  0.104–0.147 秒内被接受，服务端异常结束后 0.002–0.031 秒，短请求中止后 0.106 秒恢复；5.6 的命令测试覆盖这四种情况。
- [AI pane 的 iframe 冷加载时，浏览器对同一 origin 约有 6 个并发连接，入口 HTML 一次引用 7 个资产，script 与
  stylesheet 遇到 503 不重试] → owner 决定（2026-11-11）：资产在认证之后由适配器直接返回，不计名额、不进入循环；
  短请求上限 4；UI 按 `Retry-After` 重试幂等 GET，嵌入页导航被拒时自动刷新（决策 1，v2.1 D7、H7）。S0b 的 B7 不访问
  `/ai`，没有覆盖浏览器冷加载（签核第 11 项）；终测冒烟与 M5 确认资产不占名额、短请求名额占满时资产仍返回 200；
  冷加载由 7.2 的浏览器测试与 10.4 验证。
- [线程 14 与上限 4、4 只在 spike 中各运行一次（终测 M2、M3），用的是 spike 的适配器] → 终测 M2 未饱和与饱和两组各
  12/12（seq 0.899–1.093×，c4 0.795–1.015×），M3 11/11；线程 8 在 B9(c) 中唯一不达标的是 seq 单元格（单连接，不是
  线程耗尽），不能说明 8 不够。10.4 用 AIB-2 wheel 在同一组合下重测（tasks 0.5、10.4）。共享机器的噪声可能让单个
  单元格接近门限（S0b §7 第 6 项），10.4 与基线在同一次运行中对比（同 B6）。
- [生产配置（`DEBUG=False`、`collectstatic`、manifest storage）下的页面性能没有测量，C5 只在 `DEBUG=True` 下测得] →
  10.4 在 production settings 下补跑一次 B6。
- [`WHITENOISE_AUTOREFRESH = False` 时，启动后新增或修改的静态文件要重启 `serve` 才能正确提供] → 接受这一代价（开启时
  C5 Phase 2 只有 11/12，决策 1）；开发者文档写明（tasks 5.12）。
- [Windows 上其他进程绑定同一端口并截走连接] → `serve` 自建 socket 并设置 `SO_EXCLUSIVEADDRUSE`（决策 2 第 1 步）。
  S0b B1 在 127.0.0.1 上实测：宿主先独占监听后，另一进程以 `SO_REUSEADDR`、默认与独占方式绑定，分别得到 10013、
  10048、10048，入侵前后各 10 个连接都由宿主应答（探测用 `Host: x`，记为 HTTP 400 `other-400`）；让 waitress 自己
  绑定时，以 `SO_REUSEADDR` 占用端口的进程应答了 20/20 个连接。独占的范围是 127.0.0.1 上的这个端口：另一进程以
  `0.0.0.0` + `SO_REUSEADDR` 绑定同一端口会成功（S0b 补测 (a) 与终测 M6 各 3/3，只 bind 不 listen），按 Windows 的
  绑定规则它得到的是 127.0.0.1 以外的接口，截不走发往 127.0.0.1 的连接；只绑定回环时无法阻止这种绑定，`serve` 也不在
  其他接口上服务。`::1` 同样不在范围内（本地只绑定 127.0.0.1）。终测 M6 在最终宿主上复核：三种绑定各 3 次被拒，期间
  与之后 520 个请求（合法 Host 与凭据）全部由宿主应答 200。
- [端口冲突的表现不唯一] → 10048 与 10013 都按绑定失败处理（决策 2 第 1 步）。S0b 中 8851 出现过一次无法解释的
  exit 4（当时观察为 10013，未留存），重跑通过；通配地址上监听时的共存行为受只用回环的限制没有测，以 Windows 文档
  为准；本机 TCP 动态端口范围
  （1024–15000）覆盖 8840–8859，出站连接可能临时占用 `serve` 的端口。这些情况都输出 `serve bind failed.`，操作者换
  端口重试。
- [POSIX 没有测（SIGTERM、`SO_REUSEADDR` 语义、非 Proactor 循环，S0b §7 第 8 项）] → Docker 部署前由 6.2 在 Linux
  容器中验证 `docker stop` 的停止顺序与端口占用。
- [`serve-http` 线程布局（waitress 不在主线程）只在 spike 宿主上测过] → 终测 M1–M6 都在该布局上运行（第二次信号 8/8
  在 0.07–0.50 秒内以 130 退出）；5.6 的命令测试按设计的布局覆盖受理、停止受理、排空、flush 收尾与第二次信号。
- [运行时适配器只有 spike 质量（约 450 行，只在本机 Windows 上验证）] → 由 AIB-2 核心 wheel 实现并测试（v2.1 H7，
  R19），宿主一致性套件断言；10.4 用 AIB-2 wheel 重跑 S0b 的 B3–B5、B9。
- [门面调用超时不等于提交没有开始（S0b R21）] → `start` 的幂等键用 `client_run_key`（tasks 5.3、5.4，v2.1 H5），超时后
  以同一个键重试 `task_runs.start`，由运行时按键去重，不换新键（AIB design §11.1 `:854`）。
- [Django 的流式响应在停止时被截断（S0b §3.4）] → 宿主在响应迭代器的 `close()` 时才减少在途计数，Django 的流式视图在
  停止事件后结束（决策 3）；5.6 用一个测试用的流式视图验证排空。
- [Basic 用户设置写错导致全站静默放行] → 设置 fail-closed，格式错误时 settings 加载失败（决策 14）。
- [WSGI 线程与运行时循环之间的流桥接] → 运行时适配器逐块转发、不缓冲（v2.1 H7），请求体在 WSGI 线程上读取并有上限，
  响应块交接队列有上限并对运行时形成背压（H7），跨线程等待都有上限（H5），客户端断开后在心跳间隔 + 1 秒内被发现并
  释放连接级资源（H3、H4）；S0b 的 B3、B4 实测缓冲、断开与残留，一致性套件持续断言。
- [停止信号到不了 `serve`] → `serve` 在主线程为 SIGINT、SIGTERM 与 Windows 上的 SIGBREAK 安装处理器（Docker 中 Python
  是 PID 1，内核不投递默认处理的信号；Windows 上其他进程只能投递 `CTRL_BREAK_EVENT`，子进程要以
  `CREATE_NEW_PROCESS_GROUP` 启动）；验证脚本用 `--stop-file` 与 `--lifetime-seconds`；停止期间第二次信号立即以 130
  退出（决策 3，依赖分片等待与 `serve-http` 线程布局，终测 M1 8/8）。运行时核心不触碰信号（v2.1 H8）。
- [Docker 从 5 worker × 10 线程的 gunicorn 改为单进程，峰值吞吐下降] → 单进程线程化 WSGI，线程 14（决策 1）；同步视图
  按请求在各自线程中并发，I/O 等待不受影响，只有 CPU 密集的渲染受 GIL 限制；Metrics 是团队内部看板，页面读取本地聚合；
  镜像内的并发数据（S0 的 C7）未测量，只供 owner 参考，不作为退出条件。
- [非回环绑定且未配置 Basic 用户时，能访问该端口的任何人都能匿名使用页面与 AI 对话] → owner 决定维持现有姿态；`serve`
  输出警告；development settings 下拒绝非回环绑定；production settings 下匿名 principal 不能决定审批（Q5）；README
  建议配置 Basic 用户并由反向代理终止 TLS。
- [模型凭据与 Jira PAT 位于同一进程内存] → 与现状等价（两个进程本来以同一 OS 用户运行）；凭据用 `SecretStr`，日志脱敏。
- [`runserver` 仍可启动但没有 AI] → AI pane 明确显示 `not_running` 并提示用 `manage.py serve` 启动；文档只写 `serve`。

## Migration Plan

前置条件：AIB-0 已发布并通过现有 launcher 端到端流程（tasks 0.3，已满足）；S0b 的退出条件逐项通过，复签 PASS
（tasks 0.5，含终测 M1–M6，已满足）；AIB-2 wheel 已发布，Metrics 已精确固定其版本并通过宿主一致性套件。

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

以下问题可以在实施期间回答，不改变 spec、方案或任务拆分；Q1–Q11、D4/D5/D6/D7/D9 与 W0 冻结的运行时公开契约（AI Base
`fc4db2f` 的 AIB design §10、§11）已定，不在此列。

1. （已关闭）S0b 复签：首轮签核结论为 NEEDS_FIX；终测在最终组合上补测 M1–M6，全部通过；2026-11-11 复签 PASS（附条件，
   不需要重跑），条件已并入决策 1、2、3、14、16 与 tasks 1.2、5.3、5.5、5.6、5.10、7.2、9.7、10.4，tasks 0.5 逐项通过。
2. AIB-2 的精确版本号与 wheel 摘要，发布时写入 requirements（`waitress==3.0.2` 与 `portalocker==4.4.2` 已固定，
   决策 1）。
3. （已关闭）`session_key` 的规则由 W0 冻结（AIB design §11.1 `:856-861`，`fc4db2f`），与 v2 D7 一致：完整匹配
   `[A-Za-z0-9._:-]+`，以 `<app_id>.` 开头，不超过 200 个 ASCII 字符；`None` 新建会话，空串非法；唯一键为
   `(principal.id, app_id, session_key)`；不做规范化、截断或大小写折叠；不合法时报 `session_key_invalid`（§11.3
   `:1023`）。Metrics 的 app_id 为 `metrics`，`metrics.workbench.` 加 profile id（`[a-z0-9][a-z0-9._-]{0,159}`）最长
   178 个字符且只含允许的字符，`ai_host` 不做编码（决策 7）；wheel 交付后由 tasks 0.6 核对实现与之一致。
4. （已关闭）方法名与配置项由 W0 冻结（AIB design §10、§11.1–§11.4，`fc4db2f`），决策 1、2、3、7、8、10、12、14、16
   已按冻结名称改写：
   - 托管入口：`start_blocking(settings, host, apps, *, start_timeout)` 返回 `BlockingRuntimeContext`，以
     `with context as handle` 使用，启动失败经 `context.startup_failure` 读取，其 `rollback_result` 是 `StopResult`
     （§11.1 `:701-703`、`:799-801`，§11.2）；非法 `start_timeout` 报 `RuntimeConfigurationError`（code
     `configuration_invalid`），启动超时为 `RuntimeStartTimeout`（code `start_timeout`）（§11.1 `:852-853`，§11.3
     `:990`、`:996`）。
   - 句柄：`handle.blocking`、`close_http()`、`stop()`、`wsgi_app()`、`ended`、`end_code`、`stop_result`、
     `handle.ui.asset_url`（§11.1 `:804-812`）。
   - 同步门面：`chat.open_session`、`chat.bind_context`、`task_runs.start`、`task_runs.get`、`task_runs.result`、
     `task_runs.cancel`、`approvals.decide`、`diagnostics.snapshot` 共 8 个方法，都带必填的 keyword-only `timeout`，
     非法 timeout 在产生副作用之前抛 `RuntimeUsageError`（code `runtime_usage_invalid`）；task run 的查询与取消为
     `task_runs.get(principal, run_id, *, timeout)` 与 `task_runs.cancel(principal, run_id, *, timeout)`，没有第二套
     名称；未运行时抛 `RuntimeNotRunning`，等待超时抛 `RuntimeCallTimeout`，在循环线程上调用抛 `RuntimeUsageError`
     （§11.1 `:826-851`）。
   - 配置：停止时限、结束流时限与心跳间隔在 `HostConfig.lifecycle`（`LifecycleLimits`，`stop_timeout_seconds` 必填），
     两个在途上限在 `HostConfig.http_limits`（`HttpLimits`），都不是 `start_blocking`、句柄方法或 `wsgi_app` 的参数
     （§11.1 `:724-747`，§2 `:93-97`）；`RuntimeLimits` 的前五个字段必填（`:775-776`）。Metrics 显式传入运行时停止
     时限 1.0 秒、心跳间隔 2 秒、结束流时限 2 秒与在途上限 4、4（两项时限按终测 M4 定稿），后四项与 §10 的 A 类默认值
     相同（`:659-661`）；响应块队列的三个上限是 B 类冻结值（`:663`），Metrics 不传入，由一致性套件验证（决策 1）。
   - 审批：`HostConfig.allow_anonymous_approval`（默认 `False`，`:732`）；`ctx.approval.preview`、
     `ctx.approval.preview_digest`、`ctx.approval.decided_by`、`ctx.approval.decided_at`（`:864-868`）。
   - 请求体上限 N（N1）：取 `request_body_policy(settings, apps).max_request_body_bytes`，在启动任何运行时资源之前
     计算（`:780-787`）；Metrics 不经 settings 放大路由上限，N = max(8388608, 1048576) = 8388608，
     `max_request_body_size` = 8388609（决策 3）。
   - 上游增补 1（Q11）：启动超时的 code 与回滚结果见上；"异常名 → code"对照表是 §11.3 的单一注册表，`ToolError` 只
     接受注册表成员，code 全部小写，未注册的 code 抛 `RuntimeConfigurationError`（§11.3 `:1052-1065`）；一致性套件是
     以 `-p` 显式加载的 pytest 插件 `ai_base_runtime.testkit.pytest_plugin`（§9 `:627-629`，§11.4 `:1100`），宿主以
     ini 选项 `ai_host_modes` 声明托管方式（`:1101-1105`）：Metrics 在单独的一致性通道中以
     `-o ai_host_modes=blocking_wsgi` 设置，根 `pytest.ini` 不加载插件（tasks 5.10）；五个夹具冻结的是名称、作用域与
     返回协议，依赖参数列表不冻结（`:1118-1128`）。

   认证前移、308 在认证之后、资产直接返回、UI 重试与导航 503 自动刷新已由 owner 决定（决策 1、14），W0 只冻结对应的
   方法名与配置项名。差异只影响 `RuntimeTaskRunPort`、`ai_host.settings`、`ai_host.wiring`、`serve` 与发布 tool 内部，
   project_management 的端口不变。wheel 交付后由 tasks 0.6 逐项核对；`RUNTIME_START_SECONDS` 的取值仍开放，见第 5 项。
5. `RUNTIME_START_SECONDS` 的取值：`start_timeout` 是 `start_blocking` 必填的 keyword-only 参数，AI Base 不提供默认值、
   建议值或配置项（AIB design §3.1 `:231`）。取值按 tasks 5.6 实测的启动耗时（空状态目录与已有运行记录的状态目录各
   5 次）留足余量确定，不预设数字；`serve` 与 CLI 端口共用这个常量（决策 1、2、10），超时路径的总预算为该值加
   `stop_timeout_seconds` 1.0 秒（§3.1 `:254`）。
6. `ModelConfig.provider` 的来源与合法取值：`ModelConfig` 必须带 `provider: str`（AIB design §11.1 `:748-749`，
   `fc4db2f`），Metrics 现有的三项模型变量中没有对应项。owner 于 2026-11-12 决定由 `ai_host.settings` 中的常量提供，
   不新增环境变量（决策 6）。冻结契约只给出类型 `str`，合法取值已请求上游冻结（增补 A2；A1–A6 的清单见
   `aib2-w0-acceptance.md` 第 9 节），未知取值应在启动时报 `configuration_invalid`（§11.3 `:990`）；常量的取值在
   上游冻结后确定，wheel 交付后由 tasks 0.6 核对。
7. `RuntimeLimits` 前五项的取值与语义：`max_concurrent_runs`、`max_tool_duration_seconds`、`max_captured_output_bytes`、
   `max_input_tokens` 与 `max_output_tokens` 必填且没有默认值（§11.1 `:711-713`、`:775-776`，§10 `:672`）。owner 于
   2026-11-12 决定暂定值：`max_concurrent_runs` = 4（与 `max_streams` 相同，超出部分按默认的 `max_queued_runs` = 8
   排队）；`max_tool_duration_seconds` = 60（Metrics 的 tool 只读本地持久数据，run 时限默认 600 秒，§10 `:671`）；
   `max_captured_output_bytes` = 65536（与默认的 `max_output_bytes` 及报告辅助的 `MAX_OUTPUT_BYTES` 相同，
   `project_management/app/domain/report_assists.py:15`）；`max_input_tokens` = 65536；`max_output_tokens` = 16384
   （约等于 65536 字节）。冻结契约只给出五项的名称与类型，作用对象、token 计数方式与超限时的 code 都没有定义，注册表
   也没有 tool 时长、捕获输出与输入 token 超限的 code；已请求上游冻结（增补 A5）。冻结后由 tasks 0.6 复核这五个值，
   TaskProfile 可在此基础上收紧。
8. App tool 抛出 `ToolError` 以外的异常时的 code：§11.3 要求异常链保密、failure records 只含注册 code
   （`:1076-1087`），但没有规定映射到哪个 code。建议上游定为 `tool_failed`（`:1052`），`internal_error`（`:989`）
   留给运行时自身的故障；Metrics 不依赖这一映射（决策 4）。已请求上游冻结（增补 A3）。
9. preview 的拒绝语义：冻结契约没有规定 preview 的返回类型（§11.1 `:863-864` 把 tool 接口指向 §5–7，那里也没有
   定义），按现有语义 preview 只能返回内容或抛 `ToolError`，数据未就绪或 `needs_metric_recipe` 时模型只能看到
   `tool_failed`，看不到阻塞原因与对应的 sync 操作。已请求上游冻结 `PreviewReady(content)` 与 `PreviewDeclined(result)`
   （增补 A1，名称以上游为准；类型由 W1.CORE 定义，行为由 W2.APP 与 W2.APPROVAL 实现）：拒绝时不创建审批、不调用
   handler、记一条审计事件（增补 A6）；`result` 与 handler 的返回值走同一条结果路径后返回模型，不带错误 code；执行前重新 preview 时被
   拒绝的，审批作废（`approval_invalidated`，`:1028`）并返回拒绝结果。上游不采纳时的内部方案（不推荐作为终态）：
   chart workflow 先返回 findings 与就绪状态，publish preview 只在竞态下抛 `ToolError()`。决策 8 与
   `ai-dashboard-publish-authority` 的两个场景按结论落实。
10. 恢复类别的读取方式：§11.3 自称唯一的规范注册表，要求引用而不复制（`:954-955`），但没有导出 Retry 列。已请求上游
    在 W1.CORE 冻结（增补 A4）：每个导出异常带由注册表派生的 `retry` 属性，根包导出按 code 查询类别的纯函数，供
    `RunSnapshot`、`ToolResult` 与 `StopResult` 中的 code 使用。冻结前 Metrics 不复制注册表（决策 10）；wheel 交付后
    由 tasks 0.6 核对。
11. 审计事件的结构与投递：宿主 SPI 只有 `record_audit(event: AuditEvent)`（AIB design §2 `:125`），`AuditEvent` 的字段、
    事件类别与认证失败以外事件的投递方式都没有定义；唯一定义的是认证失败事件，可以丢弃（`:132-136`，§10 `:666`）。
    审批事件照此投递，Metrics 的审计表会缺记录且没有任何报错。owner 于 2026-11-12 决定请求上游冻结（增补 A6）：
    `event_id`、类别表、关联 id、结果 code 与可还原的事件顺序；状态转换产生的事件经事务性 outbox 至少投递一次，停止时
    不排空、重启后继续投递；宿主按 `event_id` 幂等。Metrics 据此在审计表上加 `event_id` 唯一约束（决策 14、tasks 2.3），
    是否提供会话事件以上游的类别表为准；wheel 交付后由 tasks 0.6 核对。owner 于同日确认：运行时不为 outbox 投递设单事件
    时限，`record_audit` 有界是宿主义务（决策 14）。

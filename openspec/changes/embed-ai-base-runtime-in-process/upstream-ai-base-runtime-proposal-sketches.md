# AI Base 可嵌入运行时：上游架构建议（v2.1）§5 接口草图

- 本文是 [`upstream-ai-base-runtime-proposal.md`](upstream-ai-base-runtime-proposal.md)（下称正文）的第 5 节。增补 1
  （2026-11-12）把它从正文整节移出，移动本身不改内容，章节号不变；正文和其他文档中的"§5.1"至"§5.4"都指本文。
- 草图只是示意，规范以正文的 D1–D12 为准；状态、证据基线、路径约定与修订记录见正文。

## 5. 接口草图

以下为示意；AI Base 的名称与签名以 AIB design §11（`fc4db2f`）为准，Metrics 侧的名称以 MDB-2 的 design 为准。

### 5.1 Metrics 组合根

`manage.py serve` 是唯一的启动方式，Metrics 不再有 `metrics/asgi.py` 和 `metrics/wsgi.py`。下面的示例已按 `fc4db2f` 的
AIB design §11 改写（W0 冻结，Metrics 在 `e3c8a80` 接受）：`start_blocking(settings, host, apps, *, start_timeout)`
只返回 `BlockingRuntimeContext`，进入 `with context as handle` 时才校验 `start_timeout` 并启动运行时，启动失败经
`context.startup_failure` 读取（§11.1 `:701-703`、`:799-801`，§3.1 `:223-230`，§11.2）；句柄成员为 `blocking`、
`close_http()`、`stop()`、`wsgi_app()`、`ended`、`end_code`、`stop_result` 与 `ui.asset_url`（§11.1 `:804-812`）。
停止时限、结束流时限与心跳间隔在 `HostConfig.lifecycle`，两个在途上限在 `HostConfig.http_limits`，都不是
`start_blocking`、句柄方法或 `wsgi_app()` 的参数（§2 `:93-97`，§11.1 `:724-747`、`:818-819`）；适配器的请求体上限为
`request_body_policy(settings, apps).max_request_body_bytes`（§11.1 `:704-705`、`:780-787`）。
`ai_host.http_server` 封装 `waitress==3.0.2`（S0b 选定），只影响 Metrics；监听 socket 由 `ai_host` 在主线程上自建后交给
server，waitress 不自己绑定（Windows 上设置 `SO_EXCLUSIVEADDRUSE`），其他进程借 `SO_REUSEADDR` 也无法绑定同一地址与
端口（S0b：得到 10013；通配地址上的绑定只得到回环以外的接口，截不走发往回环的连接）。停止各段的时限按 S0b 终测 M4
定稿，请求定序（L0/L1）与两段式看门狗按复签后 owner 2026-11-11 的决定。

```python
# ai_host/management/commands/serve.py (abridged). Before importing Django, manage.py wrapped atexit.register
# to record registrants for the exit inventory (R24-host); it has already run django.setup().
import os
import signal
import sys
import threading

from django.core.management.base import BaseCommand

from ai_host.http_server import bind_server  # neither import loads ai_base_runtime
from ai_host.state import watch_stop_conditions


class Command(BaseCommand):
    requires_system_checks = []  # checks run after bind, so a taken port still fails within 2 s

    def handle(self, *args, host, port, stop_file, lifetime_seconds, **options):
        stop = threading.Event()

        def on_signal(signum, frame):
            if stop.is_set():  # any signal once stopping has begun (signal, stop file or lifetime)
                sys.stderr.write("serve forced exit.\n")
                os._exit(130)
            stop.set()

        # Only the host installs handlers, on the main thread; the runtime core never touches signals (D12 H8).
        signal.signal(signal.SIGINT, on_signal)
        signal.signal(signal.SIGTERM, on_signal)
        if hasattr(signal, "SIGBREAK"):  # Windows: Ctrl+Break, or CTRL_BREAK_EVENT sent by a supervisor
            signal.signal(signal.SIGBREAK, on_signal)
        watch_stop_conditions(stop, stop_file, lifetime_seconds)  # sets the same event from a watcher thread
        # bind_server creates the listening socket itself (SO_EXCLUSIVEADDRUSE on Windows) and hands it to the server.
        # Bind first: a taken port fails within 2 s, before system checks, the state-dir lock and run recovery.
        with bind_server(host, port) as server:
            self.check()  # SystemCheckError -> "serve startup failed (system_check_failed)." (MDB-2 design decision 2)
            from ai_host.wiring import run_composed_host  # imports ai_base_runtime, so only after bind

            run_composed_host(server, stop)  # bind rules, error codes and exit status: MDB-2 design decision 3
```

```python
# ai_host/wiring.py: the only Metrics code that constructs the runtime. serve imports it only after bind and the
# system checks (MDB-2 design decision 2, step 1), because importing it loads ai_base_runtime.
import time
from collections.abc import Iterator
from contextlib import contextmanager

from django.core.wsgi import get_wsgi_application

from ai_base_runtime import request_body_policy, start_blocking
from ai_host.host import MetricsHost  # MetricsHost().config is the HostConfig of MDB-2 design decision 1
from ai_host.http_server import host_allowed, plain_response
from ai_host.package import METRICS_APP
from ai_host.settings import (  # stop deadlines are seconds after t0, finalized by S0b M4 and the re-signoff
    SERVER_THREADS,  # 14: streams 4 + other /ai requests 4 (HostConfig.http_limits) + pages 4 + spare 2
    DRAIN_BY,  # 3.0: requests counted by the host (Django until close()) reach zero
    FLUSH_BY,  # 6.5: flush-mode close, so slow readers still receive the terminal event
    HTTP_STOPPED_BY,  # 7.5: server closed, worker pool shut down (0.5 s), serve-http joined
    PROJECT_RUN_STOP_SECONDS,  # 620: run timeout (600 s) plus grace; returns at once when no run executes
    RUNTIME_START_SECONDS,  # startup only; measured startup time plus margin, fixed by MDB-2 tasks 5.6 (D12 H6)
    WATCHDOG_BY, WATCHDOG_RUNS_BY, WATCHDOG_AFTER_RUNS,  # 9.2, 659.2, and 1.2 after project runs stopped
    DJANGO_MAX_REQUEST_BODY,  # 1048576: RECOVERY_LIMIT, the largest Django request
    ai_mount_path, build_settings,
)
from ai_host.state import attach, detach, lifecycle, start_watchdog
from ai_host.task_runs import RuntimeTaskRunPort
from project_management.app.api.project_runs import (
    build_project_runtime, clear_project_runtime, install_project_runtime,
)


def run_composed_host(server, stop) -> None:
    # Abridged: each stop step records its error in the lifecycle object and never skips the next step;
    # a failed startup step unwinds the completed ones in reverse order.
    settings = build_settings()
    # N1: request_body_policy is pure (no I/O, thread or lock), so N is fixed before any runtime resource starts.
    max_body = max(request_body_policy(settings, [METRICS_APP]).max_request_body_bytes, DJANGO_MAX_REQUEST_BODY)
    # MetricsHost().config.lifecycle holds the stop (1.0), stream-close (2.0) and heartbeat (2.0) times and
    # .http_limits the two in-flight limits (4 and 4); none of them is an argument of start_blocking or the handle.
    context = start_blocking(settings, MetricsHost(), [METRICS_APP], start_timeout=RUNTIME_START_SECONDS)
    # Entering the context checks start_timeout and starts the runtime: RuntimeConfigurationError, RuntimeBusy,
    # RuntimeStartupError and RuntimeStartTimeout are raised here, on the main thread, and
    # context.startup_failure keeps the rollback result (D12 H6).
    with context as handle:
        attach(handle)  # WSGI dispatch, ai_host views and AI pane status
        try:
            # No event loop on this thread: start() reconciles interrupted runs through the ORM,
            # and the worker reaches the runtime through the blocking facade.
            project_runs = build_project_runtime(task_runs=RuntimeTaskRunPort(handle.blocking.task_runs))
            install_project_runtime(project_runs)
            project_runs.start()
            try:
                # waitress run() goes to the serve-http thread; this thread only handles signals and stopping.
                # waitress rejects a body at >= max_request_body_size, so a body of exactly N bytes passes.
                server.serve_in_thread(
                    build_wsgi_application(get_wsgi_application(), handle.wsgi_app()),
                    threads=SERVER_THREADS,
                    max_request_body_size=max_body + 1,
                )
                # Short waits keep SIGINT deliverable on Windows and notice a runtime that ended on its own.
                while not stop.wait(0.5):
                    if handle.ended.is_set():
                        lifecycle.runtime_failure = handle.end_code  # "serve runtime failed (<code>)."
                        break
            finally:
                t0 = time.monotonic()
                watchdog = start_watchdog(t0 + WATCHDOG_BY)  # on expiry: "serve cleanup failed.", os._exit(3)
                server.stop_accepting()  # listener closed, lifecycle.stopping set: L1 answers a plain 503
                # Stage 1 takes no arguments: /ai answers 503, streams end within http_close_timeout_seconds.
                handle.close_http()
                server.drain(until=t0 + DRAIN_BY)  # sliced waits on the host's own in-flight count
                server.close_flushed(flush_until=t0 + FLUSH_BY, stopped_by=t0 + HTTP_STOPPED_BY)
                # Stage 1 keeps the blocking facade working for the worker's last calls.
                if project_runs.request_stop():  # True while a run executes
                    watchdog.set_deadline(t0 + WATCHDOG_RUNS_BY)
                lifecycle.project_stop = project_runs.wait_stopped(PROJECT_RUN_STOP_SECONDS)  # sliced joins
                watchdog.set_deadline(min(watchdog.deadline, time.monotonic() + WATCHDOG_AFTER_RUNS))
                clear_project_runtime(project_runs)
        finally:
            detach()
    # Leaving the with block ran stage 2, as handle.stop(), within stop_timeout_seconds:
    # unfinished runs are cancelled and marked interrupted.
    lifecycle.runtime_stop = handle.stop_result


def build_wsgi_application(django_app, ai_app):
    mount = ai_mount_path()  # "/ai", or "/metrics/ai" when METRICS_BASE_URL is "/metrics/"

    def application(environ, start_response):
        # L1. L0 (waitress) already checked the request line, headers, framing and body size.
        if not host_allowed(environ):  # every path, static files included; same rule as Django's get_host()
            return plain_response(start_response, 400)
        if lifecycle.stopping:  # before authentication; fixed text, Retry-After: 2, no hop-by-hop headers
            return plain_response(start_response, 503, retry_after=2)
        path = environ.get("PATH_INFO", "")
        if path == mount or path.startswith(mount + "/"):
            # The adapter runs D3 in order (308 for the bare mount after authentication) and maps SCRIPT_NAME
            # to root_path; Host, client address, scheme and headers pass unchanged.
            script_name = environ.get("SCRIPT_NAME", "") + mount
            return ai_app({**environ, "SCRIPT_NAME": script_name, "PATH_INFO": path[len(mount):]}, start_response)
        return django_app(environ, start_response)  # BasicAuthMiddleware first, then pages and WhiteNoise

    return application


@contextmanager
def local_task_run_port() -> Iterator[RuntimeTaskRunPort]:
    # AppConfig.ready() registers a factory that imports this module only when called, so loading Django
    # never imports ai_base_runtime (MDB-2 design decision 2, step 1).
    # CLI processes run their own runtime; RuntimeBusy from the state-dir lock becomes RUN_BUSY and
    # RuntimeStartTimeout (code start_timeout) becomes RUN_UNAVAILABLE. A rollback or stop that misses its deadline
    # (completed false in context.startup_failure.rollback_result or handle.stop_result) is reported as a cleanup
    # failure: the CLI writes its JSON first, then exits with os._exit(3) (MDB-2 design decision 10).
    context = start_blocking(build_settings(), MetricsHost(), [METRICS_APP], start_timeout=RUNTIME_START_SECONDS)
    with context as handle:
        yield RuntimeTaskRunPort(handle.blocking.task_runs)
```

- Metrics 中只有 `ai_host` 导入 `ai_base_runtime` 和 `waitress`，由导入规则测试强制
  （`specs/embedded-ai-runtime-host/spec.md:243-248`）；project_management 只认识自己的 task-run 端口，实现由这里注入，
  它不导入 `ai_host`（同一文件 `:250-252`）。
- 请求定序（`:363-376`）：L0 是 waitress 在调用应用之前的传输层检查，L1 是上面的分派；由此经 `serve` 的 Django 路径上
  非法 Host 且不带凭据的请求由 401 变为 400。waitress 在调用应用之前读完并缓冲请求体，资源上限因此是
  `max_request_body_size`，以 `>=` 判定，设为 N + 1；N 取 `request_body_policy(settings, apps).max_request_body_bytes`
  与 Django 侧最大的合法请求（1 MiB）中的较大值，在启动任何运行时资源之前计算（AIB design §11.1 `:780-787`）；Metrics
  不经 settings 放大路由上限，N = 8388608，`max_request_body_size` = 8388609（`:378-395`）。
- 挂载路径随 URL 前缀：`METRICS_BASE_URL=/metrics/` 时为 `/metrics/ai`（`:35-38`）；精确访问挂载路径时，认证通过后 308
  到加 `/` 的路径并保留查询串（`:40-43`）；`/ai` 的流与其他请求分开限额，达到各自上限时立即返回 503，页面照常，名额在
  请求结束、出错、中止或停止时归还；UI 资产与未认证的请求不计入名额，缓存为空时 AI pane 也能加载，导航被拒时得到自动
  刷新的 503 页面（`:139-173`）。
- 先绑定再启动运行时：`serve` 设 `requires_system_checks = []`，bind 之后才运行系统检查、导入 `ai_base_runtime`（MDB-2
  design 决策 2 第 1 步）；端口被占用或绑定被拒绝时 2 秒内输出 `serve bind failed.` 并以 1 退出，不获取状态目录锁
  （`:52-55`）；其他进程以默认方式或借 `SO_REUSEADDR` 都无法绑定同一地址和端口（`:57-59`）。运行时无法进入运行期
  （包括启动时限到期且已按时回滚）时，`serve` 只输出错误码并以 1 退出，不会只提供 Django 页面（`:61-65`）；回滚没有
  按时完成时按清理失败以 3 退出，不等待未结束的线程（`:98-100`）。
  停止顺序见上面的 `finally`；停止期间已有连接上的新请求得到 503（`:74-77`）；正在输出、空闲与读得慢的客户端都在连接
  关闭之前收到终止事件；没有执行中的 project run 时，从停止触发到进程实际退出的预算为 10 秒，客户端一直不读取时也是如此
  （`:67-86`），由两段式看门狗按段保证（`:107-121`，截止与算术见 MDB-2 design 决策 3）。之后 `serve` 先做退出清点
  （R24-host：atexit 回调及其注册者、非 daemon 线程与子进程等与白名单比对，`:123-137`），再写出并 flush 全部输出，经
  `os._exit` 立即退出，不等待剩余线程与解释器收尾（`:72,102-105`，依赖 H6 的持久状态契约）。运行时意外结束以 1 退出，
  清理失败或看门狗到期以 3 退出，停止期间的第二次信号以 130 退出，各有一行固定输出（`:88-100`）。
- project run runtime 的构造、启动和停止都在 `serve` 主线程上直接调用。主线程上没有事件循环：`start()` 扫描运行档案、
  经 ORM 恢复中断的运行（`project_management/services/project_run_recovery.py:17-29`），既不会阻塞运行时的循环，也不会
  触发 `SynchronousOnlyOperation`。停止的宽限期沿用 `project_management/management/commands/project_serve.py:70` 的
  620 秒（没有执行中的 run 时立即返回），有执行中的 run 时看门狗截止放宽为 t0 + 659.2 秒，进程在触发后 660 秒内退出；
  持有 GIL 的长 C 调用会挡住看门狗，最终由外层强制结束：启动入口 15 秒，Docker 的 `--stop-timeout` 与 Compose 的
  `stop_grace_period` 690 秒。
- 静态文件只由 Django 中间件链中的 WhiteNoise 提供，位于 Basic 认证之后；`WHITENOISE_AUTOREFRESH=False`（S0b B6：
  开启时 C5 不达标），启动后新增或修改的静态文件要重启 `serve` 才生效；`/ai` 下的资产由运行时提供（D7）。

### 5.2 宿主 SPI 与 tool

```python
# ai_host/host.py and ai_host/package.py (abridged); only ai_host imports ai_base_runtime.
from asgiref.sync import sync_to_async
from django.db import close_old_connections
from pydantic import BaseModel

from ai_base_runtime.apps import AppPackage, TaskProfile, ToolContext, ToolError, tool
from ai_base_runtime.contracts import canonical_digest
from ai_base_runtime.spi import ApprovalView, AuditEvent, HostRequest, Principal


async def run_sync(fn, /, *args, **kwargs):
    # Runtime callbacks have no ThreadSensitiveContext: use a worker thread and drop stale DB connections.
    def call():
        close_old_connections()
        try:
            return fn(*args, **kwargs)
        finally:
            close_old_connections()

    return await sync_to_async(call, thread_sensitive=False)()


class MetricsHost:
    # Sync hosting: the WSGI adapter calls this on the WSGI thread, before admission (D3, D12 H7).
    def authenticate(self, request: HostRequest) -> Principal | None:
        result = check_basic_authorization(request.headers.get("authorization"))
        if result.auth_disabled:
            return Principal(id="local_operator", display_name="Local operator", anonymous=True)
        return Principal(id=result.username, display_name=result.username) if result.ok else None

    async def can_decide(self, principal: Principal, approval: ApprovalView) -> bool:
        return True  # the runtime rejects anonymous principals unless HostConfig.allow_anonymous_approval

    async def record_audit(self, event: AuditEvent) -> None:
        if is_auth_failure(event):
            log_ai_auth_failed(event)  # structured log only: unauthenticated requests must not grow the audit table
            return
        await run_sync(write_ai_audit_event, event)


class PublishChart(BaseModel):
    profile_id: str
    chart_id: str


class PublishTarget(BaseModel):
    grafana_base_url: str
    uid: str


class ChartPublication(BaseModel):
    dashboard: dict[str, object]  # deterministic Grafana dashboard JSON
    target: PublishTarget


class PublishedChart(BaseModel):
    dashboard_url: str


async def preview_chart_publication(params: PublishChart, ctx: ToolContext) -> ChartPublication:
    require_in_boundary(params, ctx.context_ref)  # ToolError("context_boundary_violation") otherwise
    # Data not ready or needs_metric_recipe: the decline shape depends on MDB-2 design Open Questions 9.
    return await run_sync(render_chart_publication, params)  # same params and data -> same bytes


@tool(effect="external", preview=preview_chart_publication)
async def publish_chart(params: PublishChart, ctx: ToolContext) -> PublishedChart:
    # The runtime has re-run the preview and matched its digest; import only the approved bytes.
    publication = ChartPublication.model_validate_json(ctx.approval.preview)
    if canonical_digest(publication) != ctx.approval.preview_digest:
        raise ToolError("preview_digest_mismatch")
    # The operator comes from the approval, never from model-supplied parameters.
    return await run_sync(
        import_publication_to_grafana,
        publication,
        operator=ctx.approval.decided_by,
        idempotency_key=ctx.tool_call_id,
    )


PROJECT_SUMMARY = TaskProfile(
    id="metrics.project_summary",
    version="1",
    input_schema=ProjectSummaryInput.model_json_schema(),
    output_schema=ProjectSummaryOutput.model_json_schema(),
    instructions=PROJECT_SUMMARY_INSTRUCTIONS,
)

METRICS_APP = AppPackage(
    app_id="metrics",
    agents=[DASHBOARD_QUERY_AGENT, TICKET_TRIAGE_AGENT],
    tools=[catalog, chart_workflow, publish_chart],
    task_profiles=[PROJECT_SUMMARY, REPORT_AUTHORING],
    context_providers={"metrics.workbench": WorkbenchContextProvider()},
    host_actions={"metrics.openChart": OpenChartAction, "metrics.openEvidence": OpenEvidenceAction},
)
```

`check_basic_authorization` 是从 `BasicAuthMiddleware` 中抽出的纯函数，Django 中间件和宿主 SPI 共用，保证两边的
认证结果一致。`preview_chart_publication` 是确定性的只读函数，摘要覆盖 `{dashboard, target:{grafana_base_url, uid}}`；
`PROJECT_SUMMARY` 和 `REPORT_AUTHORING` 取代 vendored 的 `project-reporting.summary@review-1` 和
`project-reporting.authoring`（D4）。

### 5.3 blocking 门面、页面视图与 CLI

```python
# ai_host/task_runs.py: implements project_management's synchronous task-run port.
class RuntimeTaskRunPort:
    def __init__(self, task_runs):
        self._task_runs = task_runs  # handle.blocking.task_runs

    def start(self, principal, request):
        # Worker threads only: on the runtime's loop thread the blocking facade raises RuntimeUsageError.
        return self._task_runs.start(principal, request, timeout=30)  # request: RunSubmit; timeout keyword-only


# ai_host/views.py (abridged): the workbench AI pane partial runs on a WSGI server thread.
PANE_CALLS = threading.BoundedSemaphore(PANE_MAX_CALLS)  # below the threads kept for pages


def ai_pane(request, profile_id):
    handle = attached_handle()  # read once per request: detach() may run concurrently
    status = pane_status(handle)  # lifecycle phase plus the same model check that builds HostConfig
    if status != "ready":
        return render_pane(request, status)
    if not PANE_CALLS.acquire(blocking=False):
        return render_pane(request, "busy")
    try:
        session = handle.blocking.chat.open_session(
            principal_for(request),
            app_id="metrics",
            agent=WORKBENCH_AGENT,
            context_ref=workbench_context_ref(request, profile_id),
            session_key=f"metrics.workbench.{profile_id}",
            timeout=PANE_CALL_SECONDS,
        )
    except RuntimeNotRunning:  # stopping began after the status check; raised at once (D12 H5)
        return render_pane(request, "not_running")
    except RuntimeCallTimeout:  # the facade already cancelled the loop-side call (D12 H5)
        return render_pane(request, "busy")
    finally:
        PANE_CALLS.release()
    return render_pane(request, "ready", embed_path=session.embed_path)


# manage.py project_run --execute-local: a separate process that runs its own runtime through start_blocking.
# ai_host registers local_task_run_port (5.1) as the CLI port factory, so project_management never imports ai_host.
with open_local_task_run_port() as port:  # project_management's own port API
    port.start(principal, request)
# Entering the context raises RuntimeBusy while the server holds the state-dir lock; Metrics maps it to RUN_BUSY.
# RuntimeStartTimeout (code start_timeout) maps to RUN_UNAVAILABLE (D12 H6).
```

`RuntimeNotRunning`、`RuntimeCallTimeout` 与门面方法必填的 keyword-only 参数 `timeout` 是 W0 冻结的名称（D12 H5；AIB
design §11.1 `:843-851`、§11.3 `:993-995`，`fc4db2f`）；`timeout` 非法时门面在产生副作用之前抛 `RuntimeUsageError`
（code `runtime_usage_invalid`）。
pane 对门面的调用有时限（`PANE_CALL_SECONDS` 为 1 秒），并发调用数由非阻塞信号量限制（`PANE_MAX_CALLS` 为 2，少于
为页面保留的 6 个线程），运行时变慢或卡住时不会占满页面线程：循环卡住期间页面最多慢 1 秒，最多 2 个页面线程在等待
（S0b B2：视图内门面调用 p50 0.30–0.49 ms；循环阻塞 3 秒时，0.3 秒时限的调用在 0.303 秒返回）。`busy` 在 pane 中显示
"暂时不可用，可重试"，页面本身照常返回 200。

### 5.4 嵌入页

```html
<iframe id="ai-pane" src="{{ ai_embed_path }}" title="AI assistant"></iframe>
{{ ai_context_ref|json_script:"ai-context-ref" }}
<script type="module">
  import { connectEmbed } from "{{ ai_embed_host_url }}";

  const embed = connectEmbed(document.getElementById("ai-pane"), {
    hostActions: {
      "metrics.openChart": ({ chartId }) => openChart(chartId),
    },
  });
  embed.setTheme(document.documentElement.dataset.theme);
  // ai_host builds the id-only ContextRef on the server; the page only forwards it.
  embed.contextChanged(JSON.parse(document.getElementById("ai-context-ref").textContent));
</script>
```

`ai_embed_path` 是 `handle.blocking.chat.open_session(principal, app_id="metrics", agent=..., context_ref=...,
session_key=f"metrics.workbench.{profile_id}", timeout=...)` 返回的 `SessionView.embed_path`（5.3）；
`ai_embed_host_url` 取自 `handle.ui.asset_url("embed-host.js")`（AIB design §11.1 `:812`、`:856-861`）。
range 或图表变化后，页面局部刷新得到新的 `ai_context_ref`，再发送 `context-changed`，同一个会话重新绑定（D7）。

# MDB-2 0.5 S0 共装 spike 报告

- 入库说明：本文是 spike 报告的提交副本。原型、日志、venv 与 AI Base 源副本只保存在本地被忽略的 `.tmp\s0-coinstall\`，
  不入库；文中的 `logs\`、`s0proj\`、`aibase-src\` 路径相对该目录。owner 于 2026-11-11 根据本报告选择方向 1，后续见
  `tasks.md` 0.5 与 `s0b-spike-report.md`。
- 日期：2026-11-11；角色：Implementation Engineer；一次性 spike，原型与证据只在 `.tmp\s0-coinstall\`，不合入。
- 范围：`openspec/changes/embed-ai-base-runtime-in-process/tasks.md:12`（0.5）与 `upstream-ai-base-runtime-proposal.md` §9 第 2 条（`:793-831`）。
- 环境：Windows + PowerShell 7，CPython 3.13.7，venv `.tmp\s0-coinstall\venv`；AI Base 源（只读）副本 `aibase-src\` 非 editable 安装（dist `report-creator-agent-app-service` 0.1.0）。只用回环端口 8840–8859；合成 settings 与凭据；没有读取任何 `.env`/`.env.local`；没有修改 AI Base 副本与任何受版本控制的文件。
- 清理：本次启动的全部进程（PID 见 `logs\pids.jsonl` 与各结果 JSON）均已退出，端口 8840–8859 无 TCP/UDP 端点，`git status` 无受版本控制文件的改动。
- **总结论：0.5 不通过。** C5 判定组 `composed` 在 6 个页面 × 顺序/c4 两种模式下 p95 比值全部超过 1.20（run 1：1.86–3.23×；run 2 复测：1.82–2.70×）；owner 追加的缓解候选组也没有任何页面达标（最低 1.25×）。按 `tasks.md:12`"任一条件不通过即停止实施，带证据回到 owner 决策"。C1–C4 通过（C4 附发现），C6 通过（stock 与 composed 均 11/11，其中 7 个经过组合服务器），C7 未测量，C8 已确定版本。

## 1. 结论表

| # | 退出条件 | 结论 | 关键证据 | 证据（`.tmp\s0-coinstall\logs\`） |
|---|---|---|---|---|
| 0 | 依赖解析与 `pip check` | PASS | Phase A 只因 portalocker 4.4.1 与 AI Base `>=4.4.2,<5` 冲突（1.1 处理）；Phase B（4.4.2）通过；SDK wheel sha256 `1ab6c7aa…2dd134` 核对一致后 `--no-deps` 安装，`pip check` 输出 "No broken requirements found." | `phaseA.txt` `phaseB.txt` `sdk-install.txt` `pipcheck-after-sdk.txt` `freeze.txt` |
| 1 | 组合与 lifespan | PASS | Django 页面 200、无凭据 401；`/ai/health` 200；AI Base lifespan 进入与退出都执行；`/ai/docs` 引用 `/ai/openapi.json`，`url_for` 带 `/ai` | `c1c2-results.json` `c1c2-server.log` |
| 2 | Proactor 与 blocking 门面 | PASS | `ProactorEventLoop`；同步视图调用成功；loop 线程调用立即 `RuntimeError` | `c1c2-results.json` |
| 3 | 审批持久化（跨进程） | PASS | 新进程恢复后 tool 恰好执行一次；不可恢复时标记 `interrupted` | `c3-results.json` `c3-phases.log` |
| 4 | 打开流时停止 | PASS（附发现） | 宽限期到期后流被取消，lifespan 仍关闭并输出 `project_runtime_stopped`，限时退出 | `c4-results*.json` `c4-*.log` |
| 5 | p95 ≤ 1.20× 基线（含静态资源） | **FAIL** | 判定组两次运行 24/24（页面×模式）超标（1.82–3.23×）；缓解候选组没有任何单元格达标（最低 1.25×） | `c5-results.json` `c5-run.log` `c5r2-results.json` `c5r2-run.log` `c5*-server.log` `c5r2-collectstatic.json` |
| 6 | 浏览器子集 | PASS | 同一子集 11 个测试：stock 11 passed（394.6 s），composed 11 passed（414.6 s），逐项结果一致；其中 7 个经过组合服务器（工作线程中的 uvicorn + Proactor，AI Base lifespan 每类进入、退出）；0 次非回环连接 | `c6-*.log` `c6-*-junit.xml` `c6-*.json` |
| 7 | Docker（只供参考） | NOT MEASURED | "Docker engine on this host is Windows-containers (OSType=windows); the repo image is Linux-only; owner accepted recording it as not measured on 2026-11-11 (reference data only, not a gate)." | `c7-docker.json` |
| 8 | 精确版本 | DONE | 见 §4 | `freeze.txt` |

## 2. 实测数据

### 2.1 C1/C2：组合、事件循环与门面（`s0proj\composition.py`、`s0_facade.py`、`c1c2_check.py`）

- starlette 1.10.0 `Mount.matches` 只匹配 http/websocket（`starlette/routing.py:403-405`），Router 只运行自己的 `lifespan_context`（`:652-661`），挂载的子应用 lifespan 不会自动运行；原型在外层 lifespan 中显式进入 `aibase_app.router.lifespan_context(aibase_app)`。
- 启动顺序：`aibase.loaded`（6.83 s）→ `uvicorn.run` → `aibase.lifespan.entered` → `facade.installed` → `project_runtime.started` → `lifespan.startup.complete`（8.48 s）。关闭：`project_runtime.stop.end` 0.107 s → `aibase.lifespan.exited` 0.108 s → `uvicorn.returned` 0.111 s；输出一行 `{"schema_version":1,"event":"project_runtime_stopped","stopped":true,...}`；stop-file 到进程退出 1.48 s，exit 0。不加载 AI Base 的组合约 4.9 s 就绪。
- `/`、`/projects/`、项目详情、`/bug-trend/`、`/bug-trend/scopes/` 均 200，无凭据 401；`/ai/health` 200；openapi `servers=[{"url":"/ai"}]`，93 个 path；挂载内 `url_for('health')` = `http://127.0.0.1:8841/ai/health`，`root_path=/ai`。`/ai`（无尾斜杠）落到 Django（401）。
- 事件循环：`ProactorEventLoop`（`asyncio.windows_events`，policy `WindowsProactorEventLoopPolicy`，主线程）；来源 uvicorn 0.54.0 `loops/auto.py:7-17`、`loops/asyncio.py:8-11`（win32 → Proactor）、`config.py:72-75`。
- `BlockingTaskRuns`（`run_coroutine_threadsafe(coro, loop).result(timeout)`）：Django 同步视图（线程 `ThreadPoolExecutor-13_0`，无运行中 loop）连续 5 次成功，0.21–0.28 ms，协程在 `MainThread` 的 Proactor loop 上执行；在 loop 线程（异步视图）调用立即 `RuntimeError`（0.013–0.014 ms，消息指向 async API）。对照：不加守卫时阻塞 loop 2011 ms 后才 `TimeoutError`，期间并发 `/ai/health` 耗时 3627 ms。

### 2.2 C3：审批持久化（pydantic-ai 2.66.0，`FunctionModel`，无网络；`s0proj\approval_persist.py`、`c3_driver.py`）

API 以安装源码核对：`pydantic_ai/_deferred.py:30` `DeferredToolRequests`、`:116` `ToolDenied`、`:163` `DeferredToolResults(approvals=...)`、`tools.py:397` `requires_approval`、`messages.py:5188` `ModelMessagesTypeAdapter`、`models/function.py:56` `FunctionModel`、`exceptions.py:302` `UserError`。每步是独立进程（PID 见 `c3-results.json`），消息历史、pending `tool_call_id`、参数摘要与 tool 定义摘要存于 `data\c3\approvals.sqlite3`。

| run | 过程 | 结果 |
|---|---|---|
| A | start → `DeferredToolRequests`（`call-A`），进程结束；新进程 approve 恢复 | `completed`，tool 执行 1 次；再次恢复因状态已 `completed` 被拒，仍为 1 次 |
| A 重放探针 | 用完成后的历史重放 → `UserError`（0 次）；用 pending 前缀重放 → tool **再次执行** | pydantic-ai 本身不保证恰好一次，需要持久化的状态迁移（§3 R12） |
| B | deny（`ToolDenied`） | `completed`，执行 0 次 |
| C | 存储的 tool 定义摘要与当前不一致 | `interrupted` / `TOOL_DEFINITION_CHANGED`，不恢复 |
| D | tool 执行中进程退出 | `interrupted` / `PROCESS_EXIT_DURING_EXECUTION`，不重新执行 |

### 2.3 C4：打开流时停止（`timeout_graceful_shutdown=5`；时间从触发起算；`s0proj\c4_shutdown.py`）

| 场景 | 结果 |
|---|---|
| stop-file（与 `project_serve --stop-file` 相同，设置 `server.should_exit`），sse-starlette 自动 drain | 0.20 s 检测；SSE 0.46 s 协作结束；NDJSON 流（AI Base 同款 `StreamingResponse`）保持到超时，5.33 s 被取消；lifespan 关闭 5.33 s（runtime stop 0.009 s）；`uvicorn.returned` 5.34 s；进程退出 6.30 s，exit 0，有 stop 行 |
| stop-file，关闭 drain（`AppStatus.disable_automatic_graceful_drain()`） | SSE 与 NDJSON 都在 5.32 s 被取消；退出 6.45 s，exit 0，有 stop 行 |
| CTRL_BREAK（`CREATE_NEW_PROCESS_GROUP`） | 0.54.0 处理 SIGBREAK（`server.py:45-50`）；SSE 0.49 s 结束，关闭完成 5.16 s，有 stop 行；之后 `capture_signals` 重新抛出信号（`:332-349`），CRT 默认处理使进程以 exit 3 结束（5.24 s），atexit 不执行 |
| SIGINT 一次 / 两次 | 一次：优雅关闭后重抛为 `KeyboardInterrupt`，exit 0xC000013A。两次：`force_exit`（`:351-354`）跳过等待；本例 exit-stack 清理仍运行，但不保证 |
| lifespan 启动失败（早 / 晚） | `sys.exit(3)`（`:118`）。早失败 11.7 s 退出，无 stop 行；晚失败（runtime 已启动）有 stop 行，exit 3 |
| 端口已被占用 | 先完成全部启动（含 AI Base 与 runtime），绑定失败（10048）后执行 lifespan 关闭与 stop 行，12.15 s 以 exit 3 退出（`:189-192`） |

宿主应对（写入 `serve`）：先自行绑定 socket，失败即以专用错误码退出、不启动 runtime，再 `server.run(sockets=[sock])`；捕获 `SystemExit`/`KeyboardInterrupt` 并区分原因（exit 3 同时表示启动失败与 CTRL_BREAK）；AI Base 的 NDJSON 流需要运行时关闭信号（R10）。

### 2.4 C5：性能（`s0proj\perf.py`）

方法：所有组使用同一 `s0_settings`（DEBUG=True）、同一播种的 file sqlite（`data\metrics\s0.sqlite3`）、同一桩化报告页（`perf_bootstrap.py`；仓库内存档根被 `project_management/storage/paths.py:161-181` 拒绝，两边一致）。基线是真实 `project_serve` 命令（`serve_baseline.py` 调用 `call_command('project_serve', ...)`：ThreadingMixIn `WSGIServer` + `StaticFilesHandler`；runtime 工厂 `s0_runtime.py`）。每个样本 = HTML + `link[href]`/`script[src]`/`img[src]` 引用的全部 `/static/` 资源（61–68 个，0.79–1.59 MB），同一 httpx 连接顺序拉取，无缓存；各组资源数与字节完全一致，正则与 `html.parser` 一致。各组按块交错，预热 10 次，seq 与 c4（4 个并发客户端）；所有组都把每请求一行访问日志写入文件。run 1：4 块 × 50（判定组 n=200），诊断组 4 × 15（n=60）；run 2：4 组 × 4 块 × 40（n=160），测量 27.0 分钟（含启停约 29.8 分钟）。

**判定（门槛不变）**：`composed` = uvicorn 0.54.0 → Starlette 外层（lifespan：AI Base + runtime）→ `Mount('/ai', AI Base)` + `Mount('/', ASGIStaticFilesHandler(Django ASGI))`。

| 模式 | 页面 | run 1 基线 p50/p95 | run 1 `composed` p50/p95 | run 1 比值 | run 2 基线 p50/p95 | run 2 `composed` p50/p95 | run 2 比值 | ≤1.20 |
|---|---|---|---|---|---|---|---|---|
| seq | home | 164/233 | 369/550 | 2.36 | 120/160 | 287/367 | 2.29 | FAIL |
| seq | projects | 166/201 | 362/575 | 2.85 | 165/212 | 312/388 | 1.83 | FAIL |
| seq | project_detail | 176/234 | 339/577 | 2.47 | 147/206 | 299/424 | 2.05 | FAIL |
| seq | stage_reports | 244/306 | 436/652 | 2.13 | 194/226 | 360/436 | 1.93 | FAIL |
| seq | draft_edit | 231/305 | 460/567 | 1.86 | 204/245 | 359/447 | 1.82 | FAIL |
| seq | bug_trend | 158/185 | 352/409 | 2.21 | 125/148 | 294/362 | 2.44 | FAIL |
| c4 | home | 367/439 | 1145/1417 | 3.23 | 299/379 | 847/1011 | 2.67 | FAIL |
| c4 | projects | 392/471 | 1119/1446 | 3.07 | 315/371 | 873/1002 | 2.70 | FAIL |
| c4 | project_detail | 423/555 | 1139/1389 | 2.50 | 344/392 | 906/985 | 2.51 | FAIL |
| c4 | stage_reports | 602/794 | 1256/1689 | 2.13 | 488/572 | 1079/1400 | 2.45 | FAIL |
| c4 | draft_edit | 559/659 | 1289/1681 | 2.55 | 477/570 | 1162/1295 | 2.27 | FAIL |
| c4 | bug_trend | 357/415 | 930/1237 | 2.98 | 338/410 | 897/1016 | 2.48 | FAIL |

**缓解候选（diagnostic, not a 0.5 PASS）**：单元格为 `p50/p95 ×p95 比值 h=仅 HTML 的 p95`（ms）。组定义：`composed_wn` = Django ASGI，静态由 `BasicAuthMiddleware` 之后的 WhiteNoise 提供（决策 1 姿态；DEBUG=True 时 WhiteNoise 开启 autorefresh 与 finders，`whitenoise/middleware.py:40-42,88-90`）；`composed_noai` = 不加载 AI Base；`uvicorn_django` = 无 Starlette、无 AI Base；`composed_wsgi` = `WSGIMiddleware(StaticFilesHandler(Django WSGI))`；`composed_sf_wsgi`/`composed_sf_asgi` = `Mount('/static', StaticFiles(STATIC_ROOT))`（前置复用 `metrics.middleware.BasicAuthMiddleware` 的 ASGI 认证层）+ `Mount('/', WSGIMiddleware(Django WSGI))` / `Mount('/', Django ASGI)`。

run 1（n：`baseline` 200，`composed` 200，`composed_wn` 60，`composed_noai` 60，`uvicorn_django` 60，`composed_wsgi` 60）：

| 模式 | 页面 | `baseline` | `composed` | `composed_wn` | `composed_noai` | `uvicorn_django` | `composed_wsgi` |
|---|---|---|---|---|---|---|---|
| seq | home | 164/233 h22 | 369/550 ×2.36 h35 | 403/579 ×2.49 h33 | 381/646 ×2.77 h38 | 362/567 ×2.43 h36 | 342/389 ×1.67 h23 |
| seq | projects | 166/201 h25 | 362/575 ×2.85 h41 | 403/492 ×2.44 h38 | 333/453 ×2.25 h38 | 333/381 ×1.89 h33 | 315/382 ×1.89 h27 |
| seq | project_detail | 176/234 h35 | 339/577 ×2.47 h55 | 383/511 ×2.19 h48 | 371/572 ×2.44 h64 | 327/396 ×1.69 h43 | 292/327 ×1.40 h30 |
| seq | stage_reports | 244/306 h106 | 436/652 ×2.13 h128 | 440/568 ×1.86 h112 | 412/502 ×1.64 h106 | 430/579 ×1.89 h119 | 398/540 ×1.77 h107 |
| seq | draft_edit | 231/305 h91 | 460/567 ×1.86 h106 | 476/770 ×2.52 h118 | 425/537 ×1.76 h113 | 412/451 ×1.48 h95 | 461/519 ×1.70 h86 |
| seq | bug_trend | 158/185 h32 | 352/409 ×2.21 h43 | 380/453 ×2.45 h40 | 345/594 ×3.21 h58 | 340/1897 ×10.26 h107 | 322/398 ×2.15 h40 |
| c4 | home | 367/439 h33 | 1145/1417 ×3.23 h108 | 1218/1366 ×3.11 h114 | 1008/1147 ×2.61 h83 | 966/1080 ×2.46 h99 | 861/980 ×2.23 h55 |
| c4 | projects | 392/471 h49 | 1119/1446 ×3.07 h115 | 1206/1473 ×3.13 h101 | 1109/2238 ×4.75 h146 | 1150/1598 ×3.39 h130 | 865/1098 ×2.33 h75 |
| c4 | project_detail | 423/555 h85 | 1139/1389 ×2.50 h134 | 1308/1956 ×3.53 h172 | 1064/1668 ×3.01 h176 | 1031/1236 ×2.23 h144 | 977/1270 ×2.29 h294 |
| c4 | stage_reports | 602/794 h248 | 1256/1689 ×2.13 h290 | 1335/1998 ×2.52 h297 | 1257/1599 ×2.01 h338 | 1252/1640 ×2.07 h327 | 1146/1466 ×1.85 h284 |
| c4 | draft_edit | 559/659 h203 | 1289/1681 ×2.55 h278 | 1285/1439 ×2.18 h224 | 1161/1259 ×1.91 h231 | 1103/1496 ×2.27 h309 | 1256/1569 ×2.38 h256 |
| c4 | bug_trend | 357/415 h67 | 930/1237 ×2.98 h128 | 1035/1337 ×3.22 h120 | 906/1099 ×2.65 h110 | 871/1020 ×2.46 h105 | 871/958 ×2.31 h90 |

run 2（n：`baseline` 160，`composed` 160，`composed_sf_wsgi` 160，`composed_sf_asgi` 160）：

| 模式 | 页面 | `baseline` | `composed` | `composed_sf_wsgi` | `composed_sf_asgi` |
|---|---|---|---|---|---|
| seq | home | 120/160 h19 | 287/367 ×2.29 h26 | 201/280 ×1.75 h18 | 200/299 ×1.87 h27 |
| seq | projects | 165/212 h25 | 312/388 ×1.83 h33 | 231/265 ×1.25 h22 | 232/278 ×1.31 h30 |
| seq | project_detail | 147/206 h33 | 299/424 ×2.05 h42 | 219/291 ×1.41 h30 | 242/288 ×1.40 h40 |
| seq | stage_reports | 194/226 h83 | 360/436 ×1.93 h93 | 274/319 ×1.41 h85 | 295/373 ×1.65 h98 |
| seq | draft_edit | 204/245 h77 | 359/447 ×1.82 h85 | 300/351 ×1.43 h76 | 316/391 ×1.59 h95 |
| seq | bug_trend | 125/148 h29 | 294/362 ×2.44 h37 | 231/286 ×1.93 h32 | 224/259 ×1.75 h36 |
| c4 | home | 299/379 h37 | 847/1011 ×2.67 h66 | 542/640 ×1.69 h46 | 578/675 ×1.78 h62 |
| c4 | projects | 315/371 h36 | 873/1002 ×2.70 h82 | 550/615 ×1.66 h47 | 571/692 ×1.87 h93 |
| c4 | project_detail | 344/392 h61 | 906/985 ×2.51 h103 | 575/657 ×1.68 h77 | 629/720 ×1.83 h109 |
| c4 | stage_reports | 488/572 h211 | 1079/1400 ×2.45 h295 | 741/887 ×1.55 h214 | 780/988 ×1.73 h268 |
| c4 | draft_edit | 477/570 h185 | 1162/1295 ×2.27 h234 | 854/978 ×1.72 h208 | 856/988 ×1.73 h226 |
| c4 | bug_trend | 338/410 h67 | 897/1016 ×2.48 h99 | 611/707 ×1.73 h74 | 648/784 ×1.91 h107 |

p95 比值范围：`composed`（run 1）seq 1.86–2.85，c4 2.13–3.23，达标 0/12；`composed_wn`（run 1）seq 1.86–2.52，c4 2.18–3.53，达标 0/12；`composed_noai`（run 1）seq 1.64–3.21，c4 1.91–4.75，达标 0/12；`uvicorn_django`（run 1）seq 1.48–10.26，c4 2.07–3.39，达标 0/12；`composed_wsgi`（run 1）seq 1.40–2.15，c4 1.85–2.38，达标 0/12；`composed`（run 2）seq 1.82–2.44，c4 2.27–2.70，达标 0/12；`composed_sf_wsgi`（run 2）seq 1.25–1.93，c4 1.55–1.73，达标 0/12；`composed_sf_asgi`（run 2）seq 1.31–1.87，c4 1.73–1.91，达标 0/12。

C5 说明：

- **判定**：两次运行判定组 24/24 单元格超标，C5 = FAIL；门槛（≤1.20×，含页面引用的静态资源）与判定组定义均未改动。**缓解候选**：没有任何候选在全部页面与两种模式下达到 ≤1.20×（最好的 `composed_sf_wsgi` 达标 0/12），因此不提出对决策 1 的候选修改。
- **差异来源（代码与数据支持的推断，未做 profiler 归因）**：只看 HTML 的 p95，`composed_sf_wsgi` 与基线相当（seq 0.90–1.11×，c4 1.01–1.30×），经 Django ASGI 的组更高（`composed` seq 1.10–1.35×，c4 1.26–2.26×）；每个样本含 61–68 个静态请求，每请求 p50（run 2）：基线 seq 1.74–2.40 ms / c4 4.61–5.43 ms，`composed` 4.34–4.76 / 13.11–14.47 ms，`StaticFiles` 组 3.02–3.60 / 8.49–10.03 ms。Django ASGI 每请求进入 `ThreadSensitiveContext`（`django/core/handlers/asgi.py:169`），asgiref 为每个 context 新建单线程执行器并在退出时用新线程 join（`asgiref/sync.py:182-208,526-532`）；`ASGIStaticFilesHandler` 另有 `sync_to_async(serve, thread_sensitive=False)` 与 `sync_to_async(list)`（`django/contrib/staticfiles/handlers.py:58-60,103-111`）；Starlette `StaticFiles` 每个文件也经 `anyio.to_thread.run_sync`（`starlette/staticfiles.py:123`）与线程化读文件；基线 ThreadingMixIn `WSGIServer` 在连接线程内直接返回文件，无线程切换。`composed_noai`、`uvicorn_django`（无 Starlette、无 AI Base）同样超标，AI Base 与 Starlette 不是主因。
- 两次运行的绝对值不同（run 2 基线更快），只比较同一次运行内交错测量的比值；`uvicorn_django` seq bug_trend 的 10.26× 来自单块离群（p50 340 ms），不影响结论。所有组 0 失败，所有服务器 exit 0 且各输出 1 行 `project_runtime_stopped`。run 2 launch→ready：基线 4.1 s，带 AI Base 的组 14.1–14.6 s（4 个服务器并行启动）。
- **collectstatic**：`collectstatic_s0.py` 在 S0 settings 下执行 `call_command('collectstatic', interactive=False, clear=True, verbosity=1)`；`STATIC_ROOT = .tmp\s0-coinstall\data\metrics\static-root`；274 个文件，3,524,114 字节，1.02 s；存储为默认 `django.contrib.staticfiles.storage.StaticFilesStorage`（`logs\c5r2-collectstatic.json`）。
- **缓存头**（`/static/img/favicon.svg`，`c5r2-results.json` 的 `sanity_extra`）：`StaticFiles` 返回 `ETag` 与 `Last-Modified`（`starlette/responses.py:339-344`），带 `If-None-Match` 返回 304（`staticfiles.py:191-192,211`）；基线与 `composed`（Django `serve`）只有 `Last-Modified`，没有 `ETag`；所有组都没有 `Cache-Control`。压测客户端不发条件请求，不影响上表。
- **`WSGIMiddleware`**：可用，未安装 a2wsgi；导入时发出（原文）`StarletteDeprecationWarning: starlette.middleware.wsgi is deprecated and will be removed in a future release. Please refer to https://github.com/abersheeran/a2wsgi as a replacement.`（`starlette/middleware/wsgi.py:18-21`；`logs\c5r2-composed_sf_wsgi-server.log` 第 3 行事件 `wsgi_middleware.import`）。
- **认证姿态**：基线与 `composed` 的 `/static/` 无凭据返回 200（`StaticFilesHandler` 绕过中间件）；`composed_sf_*` 的 `/static` 挂载前置 `MetricsBasicAuthASGI`（直接调用 `metrics.middleware.BasicAuthMiddleware`），无凭据 401；所有组页面无凭据 401。

### 2.5 C6：浏览器子集（`s0proj\browser_runner.py`）

方法：runner 按路径导入未改动的 `scripts/validation/run_report_authoring_tests.py`，复用其 `test_settings()` 与只允许回环的 socket 守卫；两种模式跑同一子集（4 个文件、11 个测试，含 authoring 与 daily 文件的全部 6 个用例，都不调用模型）、同一 DEBUG=True。两种模式都把 live server 端口固定到 8856–8859、临时目录放到 `data\c6\<mode>\`：Django 原生 `port = 0` 绑定系统临时端口（`django/test/testcases.py:1803`），超出本次允许的端口范围，所以 `stock` 模式就是"原 runner + 固定端口"。
- `stock`：原生 `LiveServerThread`（`ThreadedWSGIServer` + `StaticFilesHandler`）+ 内存 sqlite。
- `composed`：`LiveServerTestCase.server_thread_class` 换成 `UvicornLiveServerThread`（提供 `host`/`port`/`is_ready`/`error`/`terminate()`），在工作线程中运行 uvicorn 0.54.0（预绑定 socket），服务 C1 的外层应用（AI Base lifespan + `Mount('/ai')` + `Mount('/', ASGIStaticFilesHandler(Django ASGI))`）；DATABASES 换成 file sqlite（带 `TEST.NAME`），因为 Django ASGI 每个请求换线程，无法共享内存库连接；lifespan 不启动 project runtime（daily 用例用 `override_settings` 自装）。

| 项 | `stock` | `composed` |
|---|---|---|
| 结果 | 11 passed，394.6 s，rc 0 | 11 passed（2 warnings），414.6 s，rc 0；逐个测试结果相同 |
| live server | 启动 0.31–0.34 s | 组合 0.009–0.085 s，启动 0.39–0.41 s（两者都含 runner 约 0.3 s 的端口探测）；`ProactorEventLoop`，线程 `s0-uvicorn-live-*`（非主线程）；每类 AI Base lifespan 进入、退出各 1 次；`terminate()` 0.11–0.19 s |
| 探针与计数 | — | 每类 `/ai/health`、`/s0/health` 200；静态请求 752/330/4329，其中 2xx 752/330/4323（8858 上 6 个静态与 4 个页面请求未发出响应头；日志无应用异常，应为浏览器先断开） |
| 退出时 | 0 次非回环连接，无存活线程，临时目录已删除 | 同左；共创建 3 个 AI Base 应用 |

- 两种模式日志中的 401/503 完全相同：20 次 `Service Unavailable` 都是 `.../reports/drafts/<id>/recovery/`，17 次 `Unauthorized` 分布在 reports、drafts、publications、`/projects/language/`，不是组合引入的。
- `test_dashboard_shell_browser.py` 的 4 个用例用 `self.client` 取页面、Playwright `context.route` 回放（`:112-130`），不访问 live server；实际经过组合服务器的是其余 7 个（单项耗时合计 380.5 s → 401.5 s，+5.5%；功能测试，不作性能证据）。
- 组合模式独有的日志：4 条 `ERROR asyncio:base_events.py:1879 Exception in callback _ProactorBasePipeTransport._call_connection_lost()` → `ConnectionResetError: [WinError 10054]`（浏览器重置连接；`stock` 记为 INFO 级 `Broken pipe`），不影响结果。
- 2 个 warning 是 `PytestAssertRewriteWarning`（`anyio`、`logfire`）：runner 在 `pytest.main` 前预加载 AI Base，而两者注册了 pytest11 插件；共装后 `logfire` 的两个插件（`logfire.testing`、`logfire._internal.integrations.pytest`）会被 Metrics 的所有 pytest 运行自动加载。
- AI Base 应用只能启动一次（R11），每个 live server 类都新建 `create_app()`：预加载导入 1.22 s + 首个 `create_app` 0.86 s，之后每类组合 ≤0.085 s。
- 没有 composed 独有的失败，所以未运行只换 file sqlite 的 `stock-filedb` 对照。

## 3. 嵌入隐患 → AIB-2 要求（文件:行号指 AI Base `services/app-service`，以副本 `aibase-src\` 核对）

| # | 隐患（S0 实测） | AI Base 位置 | AIB-2 要求 |
|---|---|---|---|
| R1 | 路径根按包位置推算：wheel 安装后 `SERVICE_ROOT`=site-packages、`WORKSPACE_ROOT`=venv；`env_file` 指向 `site-packages\.env`/`.env.local`；`app_data_dir` 默认落到 `site-packages\.local\app-data`（纯默认导入实测写入 37 项，探针已清理）；`REPO_ROOT=parents[3]` 使纯默认 `import app.main` 抛 `FileNotFoundError <venv>\config\app-profiles.json` | `app/config.py:33-34,65,84`；`app/profile_manifest.py:10-11,125,345,361`；`app/config_rag.py:13,43`；`app/services/workspace_artifact_policies.py:8`；`app/services/workspace_artifacts.py:63`；`app/services/connectors/dashboard_metrics.py:21-24`；`app/services/host_tool_deps.py:13`（按值导入：`host_tool_permission.py:22`、`host_tool_binding.py:14`、`agent_runtime.py:14`）；`app/services/task_runs/pack.py:12` | 所有路径由宿主显式传入（`HostConfig`）；库模式不读 `.env`；包内数据用 `importlib.resources`；未配置数据目录时 fail-closed；永不写包目录；host tool 允许根必须由宿主显式配置（现默认 `parents[4]`，wheel 安装后为 venv 根，`host_tool_permission.py:33`）。S0 原型靠 `s0proj\aibase_embed.py` 在导入 `app.config` 前运行时替换 12 个模块属性（含 4 处 `HOST_WORKTREE_ROOT` 按值副本）与 2 个函数的默认参数（不改文件） |
| R2 | 模块级 `app = create_app()`：导入即按全局环境构造应用；导入 1.66–1.74 s，logger 8→128（`requests`/`urllib3`/`charset_normalizer` 被加 handler），atexit 1→12，模块 140→2027，warning filter 5→11 | `app/main.py:333` | 删除模块级应用；导入无文件、环境、日志副作用；只在宿主调用工厂时构造 |
| R3 | `create_app` 调用 `apply_process_environment`：配置了代理字段就写入或删除 `os.environ` 的 `HTTP(S)_PROXY`/`ALL_PROXY`/`NO_PROXY`（大小写各一份），作用于整个 Metrics 进程 | `app/main.py:92`；`app/config_runtime.py:86-107` | 代理只传给 runtime 自己的 HTTP 客户端，不改 `os.environ`（`tasks.md:55` 一致性项） |
| R4 | `get_settings` 是 `lru_cache` 单例（两次调用得到同一对象） | `app/config.py:575-576` | settings 属于 runtime 实例，不用进程级缓存 |
| R5 | `logfire.configure`、`instrument_httpx`（全局包装 `httpx.HTTPTransport.handle_request` 与 `AsyncHTTPTransport.handle_async_request`，Metrics 自己的 httpx 调用也被包装）、`instrument_pydantic_ai`；全局 tracer provider 变为 logfire `ProxyTracerProvider` | `app/observability.py:40,55,59` | 默认不做全局 instrument；由宿主显式开启且只作用于 runtime 客户端（`tasks.md:55` 要求全局 tracer 不变） |
| R6 | 无条件 `CORSMiddleware(allow_credentials=True)`，origin 为回环端口窗口 | `app/main.py:136-142`；`app/config.py:37-48,147` | 嵌入模式不加 CORS（`/ai` 与页面同源），或完全由宿主配置 |
| R7 | 路由无认证依赖：组合后 `/ai/api/chat/sessions`、`/ai/api/drafts`、`/ai/api/runtime/diagnostics/summary` 等无任何凭据返回 200；`/ai/docs`、`/ai/openapi.json` 公开 | `app/main.py:278-328` | 每个路由经宿主 principal SPI 认证；嵌入模式关闭或保护 docs/openapi |
| R8 | 顶层包名 `app`、`template_runtime` 过于通用（目前与 Metrics 不冲突） | dist `report-creator-agent-app-service` | 以 `ai_base_runtime` 命名空间发布（`design.md:76-78` 的导入规则依赖此名） |
| R9 | 全量 `pydantic-ai` 带入 anthropic 2.7.0、google-genai 3.0.0、mcp 2.3.0、fastmcp-slim 4.1.7 等；模型工厂只用 OpenAI 兼容接口；sse-starlette 未被 AI Base 导入；openai 解析到 3.49.0（AI Base 验证 3.46.0） | `template_runtime/services/pydantic_ai_model_factory.py:25-34` | 依赖 `pydantic-ai-slim[openai]`；`github-copilot-sdk` 等可选能力拆为 extras；随 wheel 发布 constraints/lock |
| R10 | NDJSON `StreamingResponse` 不感知关闭，只能等宽限期到期被取消（C4：5.33 s），客户端收不到终止事件 | `app/routes/chat_stream_route.py:258`；`app/routes/preflight.py:146` | runtime 提供关闭信号；lifespan 关闭开始时流发送终止事件并结束 |
| R11 | lifespan 只负责关闭；21 个服务在 `create_app` 中急切构造 | `app/main.py:105-131,143-255` | 显式、幂等的 `start()`/`stop()`/`running()`，构造移到启动阶段 |
| R12 | 从 pending 前缀重放会再次执行已批准的 tool（C3） | 新能力（D9，`upstream-ai-base-runtime-proposal.md:396-425`） | 执行 tool 前做持久化 CAS（pending→executing→done）；恢复前比对参数与 tool 定义摘要；进程退出时标记 `interrupted` |
| R13 | 在 loop 线程调用阻塞门面会卡住 loop 直到超时（C2 对照） | 新能力（D9） | `runtime.blocking.*` 检测 loop 线程并立即抛 `RuntimeError`（C2 已证明可行） |

未发现：AI Base 自身代码没有 `signal.signal`、`sys.path` 修改、`atexit` 注册或 `threading.Thread`（atexit 增量来自第三方依赖）；`create_app` 与 lifespan 不启动后台 asyncio 任务（`create_task` 只出现在按请求执行的路径，以及未接入 `create_app` 的候选工厂 `app/task_run_candidate.py:50`）；`app/services/workspace_source_imports.py:41` 的 `ThreadPoolExecutor` 按需创建线程，关闭时 `shutdown(wait=False, cancel_futures=True)`（`:49`）不等待进行中的导入（静态检查；AIB-2 的 `stop()` 应等待或取消）；导入探针与 C3 各进程记录到的非回环连接、子进程启动均为 0；工作目录无写入。全部检查结束后 site-packages 相对运行前快照（`logs\site-packages-before.txt`）只新增 112 个 `.pyc`（logfire 68、anyio 30、pytest_django 7、platformdirs 6、_pytest 1），无删除、无改动，无 `.local`、`.env` 或数据文件；仓库内唯一新写入的是被忽略的字节码缓存 `ui_web/tests/__pycache__/test_report_authoring_views.cpython-313.pyc`（`perf_bootstrap.py:28` 导入复用的 fixture 时生成）。没有修改 AI Base 副本的任何文件（运行时替换见 R1）。

## 4. 建议的精确版本

| 包 | 建议固定 | 说明 |
|---|---|---|
| `ai-base-runtime` | 0.6 发布的版本 | 尚未发布（`tasks.md:13`） |
| `uvicorn[standard]` | `0.54.0` | S0 实测；C2/C4 行为按此版本源码核对 |
| `starlette` | `1.10.0` | S0 实测；`ai_host` 直接导入；`starlette.middleware.wsgi` 已弃用（导入即 `StarletteDeprecationWarning`，`middleware/wsgi.py:18-21`） |
| `portalocker` | `4.4.2` | 现为 4.4.1（`requirements.txt:11`）；AI Base 要求 `>=4.4.2,<5` |
| `fastapi` / `pydantic` | `0.162.2` / `2.14.3` | AI Base 传递依赖，S0 实测 |
| `pydantic-ai-slim[openai]` | `2.66.0` | 替代全量 `pydantic-ai`（R9）；C3 API 以此版本核对 |
| `openai` | `3.46.0` | AI Base 验证版本；S0 解析到 3.49.0 且 C1–C4 正常（未调用模型），放宽前需 AI Base 确认 |
| `anyio` / `asgiref` / `httpx` | `4.16.0` / `3.13.0` / `0.28.1` | 线程切换与门面行为依赖这些版本 |
| `sse-starlette` | `3.7.0` | 仅当 Metrics 自己使用时保留；AI Base 未使用 |
| 不变 | `Django==6.0.7`、`whitenoise==6.12.0` | `requirements.txt:3,5` |

另需覆盖全部传递依赖的 constraints/lock 文件（S0 freeze 共 149 个包，`logs\freeze.txt`）；`gunicorn==26.0.0`（`requirements.txt:8`）按 6.2 删除。

## 5. 复现命令（仓库根目录执行；`$py = '.tmp\s0-coinstall\venv\Scripts\python.exe'`）

```powershell
& $py -I .tmp\s0-coinstall\s0proj\seed.py                     # migrate + 播种 data\metrics\s0.sqlite3（logs\seed.txt）
& $py -I .tmp\s0-coinstall\s0proj\probe_import.py --mode sandbox   # 另有 packaged-defaults / default
& $py -I .tmp\s0-coinstall\s0proj\c1c2_check.py               # C1/C2 → logs\c1c2-results.json
& $py -I .tmp\s0-coinstall\s0proj\c3_driver.py                # C3，每步一个新进程 → logs\c3-results.json
& $py -I .tmp\s0-coinstall\s0proj\c4_shutdown.py              # C4 全部场景；也可只传场景名
# C5 run 1（run 1 未记录 argv，按 c5-results.json 的 config 重建）
& $py -I .tmp\s0-coinstall\s0proj\perf.py --arms baseline,composed,composed_wn,composed_noai,uvicorn_django,composed_wsgi --blocks 4 --per-block 50 --diag-per-block 15 --warmup 10 --modes seq,c4 --out c5-results.json
# C5 run 2：collectstatic = call_command('collectstatic', interactive=False, clear=True, verbosity=1)
& $py -I .tmp\s0-coinstall\s0proj\collectstatic_s0.py         # STATIC_ROOT = .tmp\s0-coinstall\data\metrics\static-root
& $py -I .tmp\s0-coinstall\s0proj\perf.py --arms baseline,composed,composed_sf_wsgi,composed_sf_asgi --ports baseline=8842,composed=8843 --blocks 4 --per-block 40 --diag-per-block 40 --warmup 10 --modes seq,c4 --log-prefix c5r2 --out c5r2-results.json
$c6 = 'ui_web/tests/test_dashboard_shell_browser.py', 'ui_web/tests/test_report_query_browser.py', 'ui_web/tests/test_report_authoring_browser.py', 'ui_web/tests/test_report_daily_ui_browser.py'
foreach ($m in 'stock', 'composed') { & $py -I .tmp\s0-coinstall\s0proj\browser_runner.py --mode $m -- @c6 -q --tb=short -p no:cacheprovider -rA "--junitxml=.tmp\s0-coinstall\logs\c6-$m-junit.xml" }   # C6 → logs\c6-<mode>-runner.json
& $py -I .tmp\s0-coinstall\s0proj\report_tables.py mitig c5-results.json c5r2-results.json   # 另有 c5-results.json / c6
```

## 6. 未决风险与和 MDB-2 设计/任务的冲突

1. **C5 不通过，按 `tasks.md:12` 停止实施**（`design.md:416` 把"p95 劣化不超过 20%"作为"WSGI 改 ASGI 后页面变慢"的缓解）。差异来自 uvicorn 下 Django 的请求路径；AI Base 与 Starlette 不是主因（`composed_noai`、`uvicorn_django` 同样超标）。
2. **判定组与决策 1 不一致**：本 spike 规定的判定组使用 `ASGIStaticFilesHandler`；`design.md:71-73` 规定静态只由 `BasicAuthMiddleware` 之后的 WhiteNoise 提供，`:89` 明确否决外层 `ASGIStaticFilesHandler`。判定组与基线的 `/static/` 无凭据即 200（`sanity_extra.unauth_static_status`）。符合决策 1 的 `composed_wn` 同样超标（seq 1.86–2.52×，c4 2.18–3.53×；DEBUG=True 下 WhiteNoise 走开发路径）。
3. **缓解候选与决策 1 的关系**：`composed_sf_*` 需要 `collectstatic` 与外层 `/static` 挂载（自带认证层，无凭据 401），与 `design.md:71-73`（`WHITENOISE_USE_FINDERS=True`，不需要 collectstatic）及 `:87`"静态文件只走一条路径"不一致。两次运行中没有候选在全部页面与两种模式下达到 ≤1.20×（`composed_sf_wsgi` seq 1.25–1.93×、c4 1.55–1.73×；`composed_sf_asgi` seq 1.31–1.87×、c4 1.73–1.91×），因此本报告不提出对决策 1 的候选修改，也不建议放宽门槛；下一步由 owner 决定。
4. **`design.md:417` 的并发推断与数据不符**：c4 下判定组比值（2.13–3.23×）高于顺序模式（1.86–2.85×）。Django ASGI 为每个请求（含每个静态资源）至少新建 2 个线程（`django/core/handlers/asgi.py:169`；`asgiref/sync.py:182-208,526-532`），并发时劣化更大。
5. **5.10 一致性项在现有 AI Base 上必然失败**：`tasks.md:55` 要求 `os.environ` 与全局 tracer 不变，R3、R5 违反；必须进入 0.6（`tasks.md:13`）的 AIB-2 范围。R7（路由无认证）同样使 5.10 的跨栈认证测试无法通过。
6. **`serve` 退出语义**（`design.md:132-133,146-147`）：0.54.0 行号与设计引用一致（`server.py:116-118,189-192,205`）。但端口被占用时会先完整启动 AI Base 与 runtime（约 12 s）再失败，且 exit 3 同时表示启动失败与 CTRL_BREAK；建议预绑定 socket，并为每种失败定义独立退出码。
7. **流关闭**（`design.md:414`）：AI Base NDJSON 流总要等满 `timeout_graceful_shutdown`（设计为 10 s）才被取消，客户端拿不到终止事件（R10）。
8. **`/ai` 无尾斜杠落到 Django**：挂载路径 `METRICS_BASE_URL + "ai"`（`design.md:71`，Q7）需要重定向或精确匹配。
9. **启动成本**：加载 AI Base 使就绪时间从约 4.9 s 增至 8.5 s（6 个服务器并行启动时 16.4 s），影响 `serve` 就绪与每个 LiveServer 测试类。
10. **Docker**：`ops/docker/Dockerfile` 基于未固定标签的 `python:slim`，只能运行 Linux 容器；本机为 Windows 容器引擎，6.2（`tasks.md:62`）的验证与镜像内并发数据都无法在本机完成。
11. **仓库现有问题（不在范围内，仅记录）**：`pytest.ini` 只有 `[tool:pytest]` 节，pytest 9.1.1 对 `pytest.ini` 只读 `[pytest]` 节，这些选项不生效（`_pytest/config/findpaths.py:69-77`）；`metrics/settings/defaults.py:147` 的 `STATICFILES_STORAGE` 在 Django 6 不生效（`design.md:74-75` 已记录）。
12. **浏览器门禁与日志（C6）**：`tasks.md:56`（5.11）要记录的浏览器子集应只计经过组合服务器的用例（`test_dashboard_shell_browser.py` 不访问 live server）；组合服务器下 Proactor 把浏览器重置连接记为 asyncio ERROR（`WinError 10054`），`serve` 的日志配置需要降级或过滤；共装后 `logfire` 的 pytest 插件进入所有 Metrics 测试运行（随 R9 一并处理）；AI Base 应用只能启动一次，每个 LiveServer 测试类都要新建（R11）。

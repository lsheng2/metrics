# MDB-2 0.5 S0b（方向 1）可行性 spike 报告

- 日期：2026-11-11（+08:00）。原 spike 06:46–10:20（约 3 h 34 min）。签核补测（旧配置）11:13–12:32（最后一次测量 M2 于 12:28 结束），之后到 13:45 只做离群诊断与报告修正：M1–M5 完成，M2 的 (b) 子条件 FAIL 后按规则停止，M6 暂停。新配置终测 16:14–18:24：步骤 A 16:29–16:30，宿主 17:00:31 冻结，M1–M6 测量 17:00–17:31，之后只做只读分析、清理复核与报告。角色：Implementation Engineer；一次性 spike，原型与证据只在 `.tmp\s0-coinstall\`（被 git 忽略），不合入。
- 范围：owner 2026-11-11 方向 1——Django 留在多线程 WSGI server（页面路径等同 `project_serve` 基线），AI Base runtime 在宿主拥有的 asyncio loop 线程上运行，`/ai` 经 WSGI 桥接进入同一 loop，`/ai/*` 由宿主认证；C5 门限、基线与测量方法不变。对应 `design.md` 中标注【待 S0b】的项（`:16-19,92,95-96,133,178`）。C3（审批持久化）与拓扑无关，引用 S0；C7 Docker 仍为 NOT MEASURED（owner 已接受）。架构评审补充项已并入：第 1 项 → B5（客户端确认收到终止事件），第 2 项 → B9（AI 饱和不拖慢页面），第 3 项 → B1（Windows 端口复用），第 4 项 → B1（停止中的第二个信号），第 5 项 → B2（loop 阻塞时的门面超时）；原 B9“发现”移到 §4；B0 与 B7 stock 没有重跑。Validation 签核（`.tmp\s0-coinstall\s0b-signoff.md`，判定 NEEDS_FIX）要求的补测分两轮。第一轮用改后的宿主与签核指定的参数（下称“M 参数”，即旧配置）完成 M1–M5（§3.10，证据在 `logs\s0b\rec\`，包括 M2 (b) FAIL），M6 暂停。owner 2026-11-11 决定后，第二轮在冻结的最终宿主上按新配置跑完 M1–M6 全套（新配置终测，§3.11，证据在 `logs\s0b\final\`），推荐组合已作为整体运行。被补测结果取代的说法已直接改写为终测结论；旧配置的结果保留在 §3.10，标注为“旧配置”。
- 环境：同 S0（Windows 11 26200 + PowerShell 7，CPython 3.13.7，venv `.tmp\s0-coinstall\venv`，36 CPU / 98 GB，共享机器）；AI Base 副本 `aibase-src\` 非 editable 安装；Django 6.0.7、whitenoise 6.12.0；本次只新增 waitress、cheroot、a2wsgi 及 cheroot 的 2 个依赖（B0）。只用回环端口 8840–8859（复用 S0 网络守卫）；合成 settings 与凭据（`s0_settings.py`、`s0_common.py`、`seed.py`）；没有读取 `.env`/`.env.local`；没有修改受版本控制的文件与 AI Base 副本；没有调用任何真实模型。
- 清理：
  - 进程（17:50 复核）：`logs\pids.jsonl` 中 371 条 `started` 记录都有对应的结束记录（13:39 时为 304 条，16:14 之后新增 67 条；另有 1 条 `killed`）；16:14 之后非 0 退出的只有 M1 的 8 个宿主（130，符合预期）；venv 中没有 python 进程。记录中的 7 个 PID 目前存在，都已被系统复用给无关进程（Orca 09:39、Zoom 10:18、Antigravity 11:31、msedgewebview2 13:02 与 17:43:50、Code 13:02、另一项目 venv 的 python 17:47:06 创建，都晚于记录的退出时间），没有触碰。
  - 端口与仓库（18:21 复核）：8840–8859 上没有 TCP/UDP 端点；没有命令行含 `s0-coinstall` 的进程。`git status --porcelain` 只列出用户同步的 2 个未跟踪文件（`s0b-signoff.md`、`s0b-spike-report.md`）；17:50 时还列出的 `openspec/changes/embed-ai-base-runtime-in-process/` 下 7 个已修改文件，已由 Metrics 侧在 18:07:55 提交（e1c9cc9）。本 spike 没有触碰这些文件。仓库中 104 个被忽略的 `__pycache__` 目录里，06:46 之后新写入 19 个文件（18:21 复核未变），时间与位置都对应 Metrics 侧的活动：`scripts\`、`scripts\tests\`（16:43–17:06；17:06:22 的 pytest 缓存来自 17:06:15–17:06:39 的 Metrics 侧 pytest）；`ui_web\tests`、`jira_sync\tests`（17:14:43–44，来自 17:14:37–17:14:49 的 Metrics 侧 pytest）；`jira_sync\__pycache__\container.cpython-313.pyc`（17:41:07）。Metrics 侧在终测期间还修改并提交了仓库源文件，见偏差第 10 项。
  - 协调标记 `logs\s0b\HEAVY_RUN_ACTIVE` 已删除（17:31:13）。
  - 依赖：新增的 pip 包只装在 S0 venv 中（B0）。
- 偏差：
  1. 用时超出 3.5 h 预算（见结束时间），超出部分主要是补充项。签核补测预算约 2.5 h：测量 11:13–12:32（约 1 h 19 min），加上离群诊断与报告修正，到 13:45 共约 2 h 32 min。新配置终测预算约 2.5 h：16:14–18:24（约 2 h 10 min，在预算内），其中测量 16:29–17:31。
  2. `s0b_portbind.py` 的早期草稿含 0.0.0.0（通配地址）占用者与入侵者用例，而且运行过，违反“只用回环”规则（端口仍在 8840–8859 内，监听时间为秒级）。这些用例已删除，并加了“只允许 127.0.0.1”的守卫；草稿输出已被覆盖，本报告不使用其结果。
  3. 第 4 项用 `Thread.join(10)` 代替 30 s，以缩短用时；结论不受影响。
  4. `b5s.json` 中 3 个用例（端口 8851）以 exit 4 退出（`b5s.json` 只记录 `server exited early with 4`；当时观察到的 10013 未留存，server 日志已被重跑覆盖）。8851 不在本机排除端口范围内（09:40 查询）。这 3 个用例随后在同一端口重跑（`b5s-rerun.json`），全部 exit 0，表中使用重跑结果。
  5. Phase 1 中 cheroot arm 的样本数见 §3.7。
  6. 签核补测（§3.10，旧配置）：
     - M1：drain 阶段的活动流用 `terminal=0`（模拟不支持终止事件的应用），使第 2 个信号到达时控制线程仍在排空等待；第 2 个信号以宿主 `stop.requested` 为基准 +1.0 s 发出（签核写的是“第 1 个信号后 1.0 s”，两者相差第 1 个信号到 `stop.requested` 的 0.03–0.48 s）。终测中已改正：驱动在第 1 个信号发出后 1.000–1.001 s 发出第 2 个信号（§3.11）。
     - M2：hold 进程在整个测量期间（包括其他 arm 的块）每 1 s 用新连接各发 1 次 `/ai/health` 与 `/ai/s0b/asset.js`，每 5 s 探测 1 次第 5 条流。
     - M3：runner 的 `terminate()` 按宿主停止预算的顺序停止 live server，超出预算时退回长时限 join（本次没有发生，`budget_misses` 为空）。
     - M4：`m4-b5s.json` 记录的 `s0b_sig2.py` hash 是 M1 修改前的版本（M4 只用它发送 CTRL_C）。
     - M5：第 1 次运行因 driver 自身的检查错误判 FAIL（`/ai/s0b/state` 探测本身就是 1 个桥接交换，检查却要求桥在途为 0）；证据改名为 `m5-run1-checkbug-*` 保留，修正检查后重跑 PASS。
     - M6：旧配置阶段没有运行。M2 的 (b) 子条件 FAIL 后，按“FAIL 即停”规则停止；之后 owner 更正了 M6 的期望（`0.0.0.0` + `SO_REUSEADDR` 只 bind，在 Windows 上预期成功，不作为失败条件），并要求 M6 暂停。终测中在最终宿主上运行，PASS（§3.11）。
  7. 事后分析：`s0b_m2_verdict.py`（按签核 M2 的判定项汇总）与 `s0b_m2_outliers.py`（离群短请求诊断）只读取已有证据，没有新的测量。
  8. 配置：§3.10 的 M1–M5 与上一轮补测 (a) 都用 M 参数（旧配置），与新配置的三项差别见 §3.10。新配置的 M1–M6 全套见 §3.11。
  9. 上一轮补测 (a)（11:06）用的是 M1 改动之前的宿主，`a-revbind.json` 没有记录脚本 hash。其余 M 证据都记录了 `script_sha256`（签核第 10 条）；`b6b9-rec.json` 记录在 `config.script_sha256` 中。
  10. 新配置终测（§3.11）：
      - Metrics 侧在测量期间修改并提交了仓库源文件，不是本 spike 所为。工作区 `jira_sync/container.py` 在 17:09:14（M2 进行中）被修改，两个测试文件在 17:13:52 与 17:14:30 被修改，17:43:28/17:43:42 提交为 f3b39e3、d979e55；16:59 另有两个只改 `scripts/` 的提交。M2 的 4 个 arm 在 17:06:16 启动，并在修改之前完成了每个页面的预热；已导入的模块不会重新加载，所以这次运行中各 arm 用的是同一份代码（推断）。M3（17:24–17:31）运行时，工作区中有这些未提交的修改；M3 期间没有写入该模块的 pyc（17:41:07 才写入），无法确定 M3 是否导入了修改后的 `container.py`。M3 的代码树如下（复签 C；只披露，不需要重跑）：
        - stock（06:53–06:59，`b7-stock-junit.xml`）运行在 HEAD 6b3d017 上；候选运行在 7181b6f 加未提交修改上，6b3d017 之后到 7181b6f 的提交只改了 `scripts/`。
        - `jira_sync/container.py` 自 M2 中的那次修改起（文件时间 17:09:14.774，复签记为 09:09:16Z）即为 d979e55 的内容，此后没有再改；所以 M3 宿主如果导入了它，用的就是 d979e55 版本。
        - 6b3d017..d979e55（不含 openspec/docs）只改了 `jira_sync/container.py`、jira_sync 测试与 `scripts/*`，另新增 1 个测试文件。B7 的 4 个测试文件、conftest、pytest.ini、`metrics/settings` 与 ui_web 非测试代码都没有变，B7 的 11 个测试也不在被修改的测试文件中。
        - 对 B7 有影响的只有 `OnDemandJiraScopeMetadataProvider`（Jira client 改为按需创建），M3 的 `network_attempts` 为空。判定是“11/11 逐个一致”；代码差异要掩盖一个由 server 引起的失败，必须恰好补偿它，没有这样的机制。
      - Metrics 侧在终测期间运行过以下进程（复签据会话日志确认，本地时间）。前两个窗口在 `HEAVY_RUN_ACTIVE` 标记写入（17:05:53）之前，其余在标记存在期间。复签认为它们不改变任何判定，不需要重跑；影响与归因见 §3.11。
        - 17:00:56–17:01:00：单进程 pytest，与冒烟重跑重叠。
        - 17:05:06–17:05:19：pytest（3 个 launcher 测试文件，21 项），与 M5 及 M6 的开头重叠。
        - 17:06:15–17:06:39：两次 pytest（其中一次在临时目录副本上做 red 检查，4 项，10.34 s），与 M2 启动、预热与 hold 起点重叠，没有测量块。17:06:22 的仓库 pytest 缓存来自这里，已确认是 Metrics 侧。
        - 17:14:37–17:14:49：pytest（17 项 Django 测试），取代此前通知中的 17:14:30–17:14:55（当时估计）。
        - 17:18:00–17:19:59：三个读文件的短 python 进程，与 M2 的 32 个测量块重叠。
        - 17:24:22–17:25:28 与 17:30:11–17:30:35：M3 期间读 JSON 的短 python 进程。
      - 冻结后新增两个只读分析脚本 `s0b_final_window.py`、`s0b_final_shacheck.py`，不参与测量。分析脚本先在旧证据的改名副本上自测，副本已删除。
      - 步骤 A 用包装器 `s0b_tailwrap.py` 经 `runpy` 运行未修改的旧宿主，用来登记 atexit 时刻。
      - 宿主 `STOP_BUDGET` 中 `os_teardown` 的注释“measured 5-8 ms”有误：那是步骤 A 的观测误差。M4 实测 `os._exit` 到进程退出为 43.8–60.6 ms。
      - M4 用例名沿用旧的 `rec-` 前缀；perf 采样进程没有 ticker（C5 方法不变）。
- **总结论：方向 1 可行；推荐组合已作为整体运行（新配置终测，§3.11），B0–B9 全部 PASS。**
  - 推荐组合：waitress 3.0.2，threads 14，`channel_request_lookahead=1`，宿主以 `SO_EXCLUSIVEADDRUSE` 预绑定 127.0.0.1；WhiteNoise 在 BasicAuth 之后（`WHITENOISE_AUTOREFRESH=False`）；custom 桥；`/ai` 分离准入，流 4 / 短请求 4，超限时 503 + `Retry-After: 2`；`flush` 收尾；显式退出。终测证据都来自同一个宿主 `s0b_host.py`（SHA-256 `e6e1707d…`，`final\sha-verify.json`）。
  - C5：Phase 2（threads 8）`waitress_wn_noauto` 12/12（seq 0.89–1.04×，c4 0.88–0.96×）。终测 M2（同一次运行，n=160）：`rec_t14` 12/12（seq 0.914–1.020×，c4 0.795–0.970×）；4 条流占满的 `rec_t14_sat` 12/12（seq 0.899–1.093×，c4 0.857–1.015×）。
  - B9：在终测 M2 的同一次饱和中，(a) 第 5 条流探测 194/194 立即 503 + `Retry-After: 2`；(b) 1944 个短请求全部 200 且 < 100 ms（max 70.78 ms），其中 972 个 `/ai/health` 经过 loop，972 个资产直出；(c) `rec_t14_sat` 12/12。旧配置 M2 (b) 的 FAIL（2/2092 ≥ 100 ms）保留在 §3.10。
  - 停止：M4 5/5 exit 0，触发到进程实际退出 0.085–6.692 s（≤ 10 s；驱动阻塞等待进程句柄）。M1 第 2 个信号到进程实际退出 0.073–0.502 s，exit 130。显式退出把 `sys.exit` 之后约 0.85–0.92 s 的解释器收尾与进程结束（步骤 A）换成 `os._exit` 之后 43.8–60.6 ms 的进程结束。
  - B0、B2–B4、B8 PASS；B1、B5、B6、B7、B9 由终测确认（§1）。通过 C5 的是 production server，不只是 devserver，所以“询问 owner”的停止条件没有触发。a2wsgi 不满足 B4/B5，cheroot 在 Windows 上不满足 C5；AI Base 需要满足 R14–R24（§4.1）。

## 1. 结论表

| # | 退出条件 | 结论 | 关键证据 | 证据（`.tmp\s0-coinstall\logs\s0b\`） |
|---|---|---|---|---|
| B0 | 依赖 | PASS | 按精确版本安装 waitress 3.0.2、cheroot 11.1.2、a2wsgi 1.10.10（cheroot 带入 jaraco.functools 4.6.0、more-itertools 11.2.1）；`pip check` 输出 "No broken requirements found."；freeze 差异只有这 5 行新增 | `b0-freeze-before.txt` `b0-freeze-after.txt` `b0-freeze-diff.txt` `b0-dryrun.txt` `b0-install.txt` `b0-pipcheck.txt` |
| B1 | 组合与生命周期 | PASS（终测 M1、M6 与冒烟在最终宿主上 PASS，§3.11） | **终测（新配置，最终宿主，§3.11）**：M1 8/8，驱动在第 1 个信号后 1.000–1.001 s 发出第 2 个信号，到进程实际退出 0.073–0.502 s（venv 启动器 0.081–0.508 s），exit 130；M6 中宿主先独占服务，另一进程在 127.0.0.1 上以 `SO_REUSEADDR`、默认、独占方式各绑定 3 次，分别以 10013/10048/10048 失败，`0.0.0.0` + `SO_REUSEADDR` 只 bind 3/3 成功（只记录），520 个请求（合法 Host + 凭据）全部 200，`X-S0b-Pid` 都是宿主；冒烟：`/ai/*` 非法 Host 400、无凭据 401、`/ai` 308。**此前**：3 种 server × 2 种桥全部满足：先预绑定、后启动 runtime；页面、静态、`/ai/health` 有凭据 200、无凭据 401；`/ai` 308 到 `/ai/` 并保留查询串；`root_path=/ai`，`url_for` 与 openapi `servers` 都带 `/ai`；端口被占用时 0.40–0.45 s 以 exit 4 退出，runtime 未启动；stop-file、CTRL_BREAK、SIGINT 都 exit 0，且恰好输出 1 行 `project_runtime_stopped`（旧配置 M4 与终测 M4 都复测了 3 种触发，同样 exit 0、1 行）。**Windows 端口复用（第 3 项）**：原生 waitress、devserver 绑定前设置 `SO_REUSEADDR`；另一进程以 `SO_REUSEADDR` 占用同一 127.0.0.1 端口时，它们仍“绑定成功”，但 20/20 个连接都由占用者应答。cheroot 原生绑定在 3 种占用下都失败。宿主改为自己以 `SO_EXCLUSIVEADDRUSE` 预绑定 127.0.0.1、再把 socket 交给 server 后，4/4 个占用用例在 0.36–0.43 s 内 exit 4（10048），runtime 未启动，state 目录与锁都没有创建。**反向绑定**（宿主先独占监听，`b1-portbind-host.json[4].control`）：另一进程以 127.0.0.1 + `SO_REUSEADDR`、默认、独占方式绑定，分别以 10013/10048/10048 失败；入侵前后各 10 个连接都由宿主应答（HTTP 400：探测用 `Host: x`，记为 `other-400`）。**反向绑定补测 (a)**（11:06，M 参数宿主加 `--state-lock --pid-marker`，端口 8850）：另一进程在 127.0.0.1 上以 `SO_REUSEADDR`、默认、独占方式各绑定 3 次，分别以 10013/10048/10048 失败；`0.0.0.0` + `SO_REUSEADDR`（只 bind、不 listen、立即关闭）3/3 成功，与 Windows 文档一致；每次尝试期间与之后各 20 个请求（合法 Host + 凭据）全部 200，`X-S0b-Pid` 都是宿主。正在服务的地址与端口独占；通配绑定按 Windows 文档可成功，截不走回环连接。**第二个信号（第 4 项）**：合成子进程（`s0b_sig2.py`）不切片时 8.58–8.61 s、切片后 0.22–0.23 s 以 130 退出（含助手发送后 0.2 s 的休眠）；**组合宿主（旧配置 M1）**：排空与 flush 两个阶段 × CTRL_BREAK/CTRL_C × 2 次，8/8 以 130 退出，第 2 个信号到进程退出 0.061–0.084 s（门限 1.0 s；第 2 个信号以 `stop.requested` + 1.0 s 为基准） | `final\m1-sig2-host.json` `final\m1-*-host.log` `final\m6-revbind.json` `final\m6-revbind-server.log` `final\stepB-smoke.json` `b14-*.json` `b1-portinuse-*.json` `b5-*-custom-*.json` `b1-portbind.json` `b1-portbind-host.json` `sig2.json` `rec\m1-sig2-host.json` `rec\m1-*-host.log` `retest-t12\a-revbind.json` `retest-t12\a-revbind-server.log` |
| B2 | Loop 与门面 | PASS | `ProactorEventLoop`，运行在非 daemon 线程 `s0b-ai-runtime-loop`；从 WSGI 请求线程调用门面 20/20 成功（视图内 p50 0.30–0.49 ms）；在 loop 线程上调用时 0.009–0.016 ms 内抛 `RuntimeError`。**loop 阻塞 3 s（第 5 项）**：页面线程上 timeout 0.3 s 的门面调用 0.303 s 抛 `TimeoutError`（客户端 310 ms，门限 0.5 s）；阻塞结束后 pending task 22 → 22，没有遗留；阻塞期间页面照常（p50 128 ms）。但超时调用的第一步已经执行（R21） | `b14-*.json` `b9-admission.json`（`split.stall`） `b9-split-server.log` |
| B3 | 流式（无缓冲） | PASS（两种桥） | 6 个组合的 ASGI SSE、ASGI NDJSON 与 Django SSE：首事件 1.3–3.6 ms，间隔 p95 100.5–109.8 ms，max ≤ 164.9 ms；补充（Starlette `StreamingResponse`）：custom 桥（devserver、waitress）与 waitress × a2wsgi 都 PASS，首事件 1.4–18.3 ms，间隔 p95 108.1–108.8 ms | `b14-*.json` `b35-starlette-*.json` |
| B4 | 客户端断开 | custom PASS ×3；a2wsgi **FAIL** ×3 | custom：活动流检出 p50 93–200 ms，空闲流 14–18 ms，0 遗留；a2wsgi：20 个中止流 0 个被检出，loop 上遗留 20/20/30 个 pending task；补充（Starlette）：custom 桥开启探测时 PASS（活动流 p50 93–111 ms，空闲流 15–16 ms，0 遗留）；关闭探测时，waitress 空闲流 1.80 s PASS，devserver 3.80 s **FAIL**（> 3.0 s）；waitress × a2wsgi 0/10 检出，10 个遗留 task，FAIL | `b14-*.json` `b14-*-server.log` `b35-starlette-*.json` |
| B5 | 打开流时停止 | PASS（终测 M4：新配置，`flush` × stop-file/CTRL_BREAK/CTRL_C，另加慢读与不读，5/5）；a2wsgi **FAIL** ×3 | **终测 M4**（§3.11；显式退出，10 s 预算按进程实际退出计算）：5/5 exit 0，触发到进程实际退出 0.085–6.692 s（启动器 0.092–6.698 s），各 1 行 `project_runtime_stopped`；正常读取的客户端都在连接关闭前收到终止事件（触发后 0.032–0.201 s）；慢读的活动流在 3.097 s 收到完整的终止事件，然后 EOF；不读的活动流在 flush 截止时被关闭，没有收到终止事件（按签核只记录）。**旧配置 M4**（threads 12、分离准入、`flush`，各段停止预算合计最坏 9.5 s）：5/5 exit 0，触发到进程退出 1.12–7.89 s，各 1 行 `project_runtime_stopped`。正常读取的客户端（3 种触发用例的两条流，以及慢读、不读用例中的空闲流）都在连接关闭前收到完整的终止事件（触发后 0.06–0.25 s）；慢读（8 MB，暂停 3 s）3.13 s 收到终止事件；不读（暂停 16 s）在 flush 截止 t0+6.5 s 被关闭，7.8 MB 未写出，没有终止事件（按签核只记录）。基础矩阵（空闲流 `terminal=0`，只证明活动流终止事件与 exit 0）：custom（3 种 server × 3 种触发）活动流 0.01–1.01 s 内收到终止事件并结束，空闲流 2.0–3.0 s 被取消，drain 2.01–2.52 s，exit 0；a2wsgi：drain 10 s 超时，流被截断且没有终止事件；cheroot × a2wsgi 卡住，看门狗在 35.2 s 强制 exit 3。**客户端确认（第 1 项，threads 8，两条流都支持终止事件）**：正常读取 6/6 两条流都在 EOF 前收到终止事件；终止事件在“停止受理”结束后 0.8–1.9 ms 到达，停止受理没有停掉 waitress 的 I/O 路径；慢读时 waitress `close` 收尾丢弃输出缓冲，**FAIL**，`flush` 收尾 PASS（7.08 s exit 0）；停止期间同一连接上的新请求 1.1–62 ms 内得到 503 | `final\m4-b5s.json` `final\rec-*` `rec\m4-b5s.json` `rec\rec-*-flush*` `b5-*.json` `b5-*-server.log` `b5s.json` `b5s-rerun.json` `b5s-*-server.log` |
| B6 | C5：p95 ≤ 1.20×（门限不变） | PASS（`waitress_wn_noauto`；终测 M2 中两个新配置 arm 都是 12/12） | **终测 M2**（§3.11，同一次运行，n=160，与 `baseline` 交错）：`rec_t14`（未饱和）12/12（seq 0.914–1.020×，c4 0.795–0.970×）；`rec_t14_sat`（4 条流占满）12/12（seq 0.899–1.093×，c4 0.857–1.015×）；对照 `waitress_wn_noauto`（threads 8）12/12；两个 rec arm 无凭据请求静态文件得到 401。Phase 2（n=160，threads 8）：`waitress_wn_noauto` 12/12（seq 0.89–1.04×，c4 0.88–0.96×）；`waitress_wn` 11/12（seq home 1.33×）与 `dev_wn` 11/12（seq draft_edit 1.21×）FAIL。Phase 1（n=60）只有 `waitress_wn_noauto` 12/12；cheroot 全部 0/12（keep-alive 每个请求约 61 ms）。**旧配置 M2**（同一次运行，n=160，与 `baseline` 交错）：`rec_t12`（M 参数，未饱和）12/12（seq 0.908–0.946×，c4 0.843–1.069×）；`rec_t12_sat`（M 参数，4 条流占满）12/12（seq 0.807–1.081×，c4 0.772–1.065×）；对照 `waitress_wn_noauto`（threads 8）12/12；两个 rec arm 无凭据请求静态文件得到 401。诊断：loop 上有 2 条 50 ms 流时，（相对同 arm 无流）页面 p95 比为 0.94/0.97 | `b6-phase1.json` `b6-phase2.json` `b6-diag-streams.json` `b6p1-*` `b6p2-*` `b6diag-*` `keepalive.json` `final\b6b9-final.json` `final\m2-final-verdict.json` `final\final-*-server.log` `rec\b6b9-rec.json` `rec\m2-verdict.json` `rec\rec-*-server.log` |
| B7 | 浏览器子集 | PASS（threads 8、旧配置 threads 12、新配置 threads 14 各一次） | **终测 M3**（新配置 threads 14，§3.11）：11/11 passed，逐个与 stock 一致，每次停止 `budget_misses` 都为空。stock 与候选（waitress + wn-noauto + custom 桥，threads 8，runtime loop 线程，AI Base lifespan）都是 11/11 passed，逐个测试结果一致。**旧配置 M3**（M 参数：threads 12、分离准入流 4/短请求 2、`flush`，停止按宿主预算）：11/11 passed，逐个与 stock 一致，`budget_misses` 为空。这 11 个测试不访问 `/ai` | `b7-*.log` `b7-*-junit.xml` `b7-*-runner.json` `rec\b7-candidate-t12*` `final\b7-candidate-t14*` `final\m3-final-compare.json` |
| B8 | 精确版本 | PASS | 见 §5 | `b0-freeze-after.txt` |
| B9 | AI 饱和不拖慢页面（第 2 项） | PASS（终测 M2：(a)(b)(c) 在同一次饱和中全部满足；终测 M5 名额归还 15/15）；旧配置 M2 (b) **FAIL**（保留）；共享准入 (b) **FAIL**；threads 8 (c) **FAIL**（1 个单元格） | **终测 M2**（新配置，§3.11）：hold 进程用 1 条活动流 + 3 条空闲流占满流上限 972 s。(a) 第 5 条流探测 194/194 立即 503 + `Retry-After: 2`（p50/max 2.29/24.37 ms）；(b) 每 1 s 各发 1 次 `/ai/health`（经 loop）与资产请求（直出），1944 个全部 200 且 < 100 ms（`/ai/health` p50/p99/max 5.34/22.77/70.78 ms，资产 2.36/27.54/33.12 ms）；(c) `rec_t14_sat` 12/12。终测 M5：客户端中止或服务端异常结束后名额立即归还；短请求池占满时资产仍 200。**此前**：1 条活动流（100 ms）+ 3 条空闲流占满流上限 4。(a) 共享与分离两种设计下，新的流请求 10/10 立即 503 + `Retry-After: 2`（p50 1.7–2.0 ms）。(b) 共享上限时短请求（`asset.js`、`/ai/health`）也 20/20 得到 503，**FAIL**；分离上限（流 4 / 短请求 2）时 20/20 返回 200（p50 1.9/4.0 ms）。(c) 4 条流占满上限期间的页面 p95（方法同 B6，n=160，静态文件在认证之后；`b9-perf.json` 期间没有发短 `/ai` 请求）：threads 12 为 12/12（seq 0.69–1.05×，c4 0.90–1.15×），PASS；threads 8 为 11/12（seq stage_reports 1.23×），FAIL；未饱和对照 12/12。**旧配置 M2**（M 参数，与 B6 同一次运行；hold 进程在整个测量期间占满流上限，每 1 s 各发 1 次 `/ai/health` 与 `/ai/s0b/asset.js`，每 5 s 探测第 5 条流）：(a) 探测 209/209 立即 503 + `Retry-After: 2`（p50/max 2.45/29.0 ms）；(c) `rec_t12_sat` 12/12；(b) 2092 个短请求全部 200，p50/p95/p99 4.9/26.47/29.59 ms，但 2 个 ≥ 100 ms（`/ai/health` 212.48 ms、`/ai/s0b/asset.js` 157.89 ms），按签核门限（全部 < 100 ms）**FAIL**。这两次与进程级或跨进程的停顿同时发生，原因无法判定（§3.10） | `final\m2-final-verdict.json` `final\final-rec_t14_sat-hold.json` `final\final-rec_t14*-diag.json` `final\m2-window-attrib.json` `final\m5-slots.json` `b9-admission.json` `b9-shared-server.log` `b9-split-server.log` `b9-perf.json` `b9p-*` `rec\m2-verdict.json` `rec\m2-outliers.json` `rec\rec-rec_t12_sat-hold.json` `rec\b6b9-rec.json` |
| 发现 | 原 B9 | DONE | AIB-2 新要求 R14–R24、`serve` 要求、静态文件姿态取舍，见 §4 | — |
| C3 | 审批持久化 | PASS（引用 S0） | 与拓扑无关，本次没有重跑 | `..\c3-results.json` |
| C7 | Docker | NOT MEASURED | 本机 Docker 为 Windows 容器引擎，owner 已接受（引用 S0） | `..\c7-docker.json` |

## 2. 原型（`s0proj\s0b_*.py`）

- `s0b_host.py` 参数：`--port`（只允许 8840–8859）、`--server {devserver,waitress,cheroot}`、`--static {sfh,wn,wn-noauto}`、`--bridge {a2wsgi,custom}`、`--no-aibase`、`--threads`（默认 8）、`--stop-file`、`--perf`、`--drain-seconds 10`、`--terminate-grace 2`、`--disconnect-probe {auto,off}`、`--tag`。补充项新增：`--finish {close,flush}` 与 `--flush-min-seconds 2`（第 1 项）；`--ai-limit-mode {none,shared,split}` 与 `--ai-inflight-limit 4`、`--ai-stream-limit 4`、`--ai-short-limit 2`（第 2 项）；`--state-lock`（绑定成功后才获取 `state_dir/.runtime.lock`，第 3 项）；`--enable-ctrl-c`（以 `CREATE_NEW_PROCESS_GROUP` 启动的进程默认忽略 CTRL_C，该参数重新启用）。上一轮补测 (a) 新增 `--pid-marker`（每个响应带 `X-S0b-Pid`，用来判定由谁应答）。终测宿主新增 `--diag-out`（GC 回调、10 ms ticker、每个请求从进入分派到 `start_response` 的耗时，§3.11）。参数默认值仍是 threads 8、短请求上限 2，所以所有用例都显式传入推荐参数。M 宿主中 `--drain-seconds` 与 `--terminate-grace` 受停止预算封顶（排空截止 t0+3.0 s、宽限 2.0 s），`--flush-min-seconds` 不再使用（flush 截止固定为 t0+6.5 s）。`--urlconf`、`--no-access-log`、`--cheroot-expiration-interval` 只用于诊断。
- 退出码：0 正常；2 参数错误；3 强制退出（看门狗、清理失败，或非 daemon 线程超出预算、runtime 停止失败）；4 端口被占用；5 runtime loop 或 AI Base 启动失败；6 project runtime 启动失败；7 server 构造失败；130 停止过程中收到第二个控制台信号（M1）。看门狗：基础矩阵与补充项为 drain + 25 s；签核补测（M）宿主与终测宿主为 t0 + 10 s，这只是 spike 的测量护栏（`serve` 的进程内看门狗为 660 s，§3.11）。终测宿主的每条退出路径都以显式退出结束：[`--diag-out` 转储] → `django.db.connections.close_all()` → `logging.shutdown()` → `sys.stdout`/`sys.stderr` flush → `os._exit(code)`；清理失败时把 0 改为 3，非 0 的码保持不变，看门狗一直保持到 `os._exit`。更早的宿主以 `sys.exit(0)` 结束，经过解释器收尾。
- 启动顺序（`b14-waitress-custom-server.log`，时间相对进程启动）：`prebind.ok`（0.001 s，127.0.0.1 + `SO_EXCLUSIVEADDRUSE`）→ 安装 SIGINT、SIGBREAK、SIGTERM 处理器与 stop-file 监视线程 → `django.setup`（1.64 s）→ 加载 AI Base（10.67 s，沿用 S0 R1 的路径替换）→ 构造 Django WSGI 应用（12.41 s）→ 新建非 daemon 线程 `s0b-ai-runtime-loop`：在线程内 `asyncio.new_event_loop()`（`ProactorEventLoop`），进入 `aibase_app.router.lifespan_context(aibase_app)`（R11），安装绑定该 loop 的门面后通知主线程就绪（启动异常在时限内传回主线程，exit 5）→ 主线程按 S0 的方式 `start()` project runtime（12.49 s）→ `server.serving`（12.52 s）。M 宿主中 server 的 `run()` 在非 daemon 线程 `serve-http` 上执行，主线程启动它之后只做 ≤ 0.5 s 的切片等待并处理信号（§3.10）。
- 停止：stop-file、CTRL_BREAK、Ctrl+C/SIGINT 都只设置停止事件，由控制线程 `s0b-shutdown-controller` 依次执行：停止受理 → `terminate_all(2 s)` → 排空（桥与 Django 的在途请求都为 0，或到期）→ server 收尾 → join `serve-http` → waitress 工作线程收尾 → `project_runs.stop(...)`，输出与 S0 相同的 `project_runtime_stopped` 行 → 在 loop 上退出 AI Base lifespan → 取消剩余 task，停止并关闭 loop → 带时限 join loop 线程 → exit 0（终测宿主：显式退出 `os._exit(0)`）。M 宿主中每一步都受停止预算约束（排空截止 t0+3.0 s、flush 截止 t0+6.5 s，其余各步 0.5–1.0 s，最坏合计 9.5 s，见 §3.10）；终测宿主再加显式退出 0.2 s 与进程结束 0.3 s，按进程实际退出合计 10 s（§3.11）。基础矩阵与补充项的证据来自改动前的宿主（排空 10 s、flush 至少 2 s、dispatcher 5 s、loop 收尾最多 5 s，没有总上界，签核第 5 条）。没有打开的流时，停止到退出 waitress 0.006 s、devserver 0.49 s（`handle_request` 超时 0.5 s）。
- WSGI 分派：
  - 停止期间所有请求立即返回 503，不阻塞。早期版本在 503 上加了 `Connection: close`；这是 hop-by-hop 头，PEP 3333 不允许 WSGI 应用设置（waitress `task.py:423-427` 直接抛 `AssertionError`），已去掉。
  - `PATH_INFO == '/ai'` 时 308 到 `/ai/`，保留查询串，先于认证。`/ai/` 前缀：宿主 BasicAuth（`metrics.middleware.BasicAuthMiddleware` 语义，无凭据 401）→ runtime 停止中立即 503 → AI 准入 → `SCRIPT_NAME += '/ai'`、`PATH_INFO` 去掉前缀后交给桥。其余请求交给 Django。
  - 终测宿主的 `/ai/*` 固定顺序（§3.11）：停止中 503 → Host 校验（Django `ALLOWED_HOSTS`，非法 400）→ 请求完整性（超过 16 MiB 413）→ `/ai` 308 → BasicAuth（401，不占名额、不调度 loop）→ 资产直出（构建时清单，WSGI 线程上直接返回）→ AI runtime 停止中 503 → 准入 → 桥。更早的宿主没有 Host 校验、完整性检查与资产直出。完整性检查的实际分工（复签 N1）：`Content-Length` 非数字时的 400 由 waitress 解析器在调用应用之前返回，宿主的这一分支在 waitress 下走不到；413 由宿主返回，但 waitress 在调用应用之前已读完并缓冲整个请求体，所以这个上限不限制资源。
- AI 准入（第 2 项）：`shared` 模式下所有 `/ai/*` 共用一个在途上限；`split` 模式下长连接流与短请求各有上限。长连接流指路径匹配 `^/s0b/(sse|ndjson|starlette-ndjson)$` 或以 `/stream` 结尾的请求；`/s0b/state`、`/s0b/loop` 不计数；其余请求（包括代表 UI 资产的 `/ai/s0b/asset.js` 与 `/ai/health`）都按短请求计数并经过 loop。超限时立即返回 503 JSON `{"error":"ai_busy","pool":…,"limit":…}` 和 `Retry-After: 2`。认证先于准入；名额在响应迭代器 `close()` 时释放。终测宿主中资产在准入之前直出，不计名额，也不进 loop。
- 静态文件姿态：`sfh` 把 `StaticFilesHandler` 包在 Django 外（同基线，绕过认证）；`wn` 把 WhiteNoise 中间件放在 `BasicAuthMiddleware` 之后（决策 1），DEBUG 下开启 autorefresh 与 finders；`wn-noauto` 同 `wn`，但 `WHITENOISE_AUTOREFRESH=False`，启动时建立 finders 索引。
- server 适配：
  - devserver：`ThreadingMixIn` + Django `WSGIServer`，`handle_request` 循环同 `project_serve.py:100-113`。
  - waitress：`create_server(app, sockets=[预绑定 socket], threads=N, channel_request_lookahead=1)`（基础矩阵 N=8，M 参数与上一轮补测 (a) 为 12，终测为 14）。停止受理：经 `server.trigger.pull_trigger` 在 asyncore 循环上关闭监听 dispatcher，已有连接继续服务。收尾有两种：`close`（B5 原行为）对所有 channel 调 `handle_close()`，会丢弃尚未写出的输出缓冲；`flush`（第 1 项）先等工作线程写完，再给每个 channel 设 `close_when_flushed`，轮询到 channel 数为 0 或到期（改动前：至少 2 s，受 drain 预算约束；M 宿主：t0+6.5 s）。两种收尾最后都执行 `server.close()` 与 `task_dispatcher.shutdown(cancel_pending=True, timeout=…)`（改动前 5 s，M 宿主 0.5 s）。
  - cheroot：预绑定的 `wsgi.Server` 子类，`numthreads=8`、`shutdown_timeout=5`。它没有“只停止受理”的 API，停止期间由分派返回 503；收尾调用 `server.stop()`。
- 桥 (a) `A2wsgiBridge`：`a2wsgi.ASGIMiddleware(app, loop=runtime_loop)`。
- 桥 (b) `S0bBridge`（`s0b_bridge.py`，约 450 行）：
  - 每个请求用 `run_coroutine_threadsafe` 在 runtime loop 上运行一个 ASGI task。`scope.asgi.spec_version='2.3'`（同 uvicorn），使 Starlette `StreamingResponse` 监听 `http.disconnect`。每个 `http.response.body` 片段立即交给 WSGI 迭代器。
  - 所有跨线程等待都有界（0.1 s 轮询，外加总时限）。WSGI 迭代器被提前 `close()`、写失败或探测到断开时，投递 `http.disconnect`，之后的 `send` 抛 `OSError`；0.5 s 后 task 仍未结束则取消。
  - `terminate_all(grace)` 设置宿主关闭事件：支持该事件的应用发送终止事件后结束，宽限期到期后取消其余 task。
  - 断开探测（`--disconnect-probe auto`）：waitress 用 `environ['waitress.client_disconnected']`（`task.py:568`，需要 `channel_request_lookahead>0`）；devserver 与 cheroot 对 socket 做 `MSG_PEEK`。两者都是 server 特定扩展，不是可移植的 WSGI。
- 测试端点（只在 spike 内；用单调时钟记录开始、每次发送、收到 `http.disconnect` 与 `CancelledError` 的时间）：
  - `/ai/s0b/sse`、`/ai/s0b/ndjson`：参数 `interval_ms`、`count`；`idle=1` 时每 2 s 一个心跳；`terminal=1` 时响应宿主关闭事件，发送终止事件。
  - `/ai/s0b/starlette-ndjson`：与 AI Base 聊天流相同的 `fastapi.responses.StreamingResponse` + `application/x-ndjson`（`app/routes/chat_stream_route.py:258`），生成器不感知宿主，同 R10。
  - 其他：`/ai/s0b/state`（loop 上的 pending task、线程与各流时间戳）；第 2、5 项用的 `/ai/s0b/asset.js?delay_ms=`、`/ai/s0b/stall?seconds=`（在 loop 线程上排入阻塞的 `time.sleep`）、`/s0b/django/facade-timeout/?timeout=`；Django 原生 `StreamingHttpResponse` SSE `/s0b/django/sse/`。
  - AI Base 真实聊天流路由需要配置后端与会话，本次没有使用；最接近的替代是 Starlette 端点（§3.5）。

## 3. 实测数据

本节只保留关键表。以下明细见 `logs\s0b\s0b-report-tables.md`（由 `s0b_report.py` 从原始 JSON 生成；“附表 X”指其中 `<!-- X -->` 一节）：B1、B2、B3、B5 的逐组合表，端口复用矩阵与宿主预绑定，第二个信号，排空期间的 503 探测，loop 阻塞明细，Starlette 端点，keep-alive 微基准，B6 诊断，B7 逐测试结果。

### 3.1 B1/B2：组合、生命周期、loop 与门面（`s0b_checks.py combo`、`portinuse`；附表 `B1_TABLE`、`B1_PORT_TABLE`、`B2_TABLE`）

- 组合与生命周期：6 个组合（3 种 server × 2 种桥）全部 PASS。就绪 10.1–13.3 s；6 个页面、静态资源、`/ai/health` 有凭据 200、无凭据 401；`/ai` 与 `/ai?x=1` 分别 308 到 `/ai/`、`/ai/?x=1`；`root_path=/ai`，`url_for` 得到 `…/ai/health`，openapi `servers=[{"url": "/ai"}]`；启动与停止顺序同 §2；stop-file 停止 1.24–2.47 s，exit 0，1 行 stop。
- 端口被占用（测试先占用端口，再启动宿主）：3 种 server 都以 exit 4 退出，进程启动到退出 0.398–0.451 s，`prebind.failed` 在启动后 0.6–0.8 ms，runtime 未启动。
- 门面：6 个组合都是 `ProactorEventLoop`，运行在线程 `s0b-ai-runtime-loop`。从 WSGI 请求线程调用 20/20 成功，视图内 p50 0.30–0.49 ms，max ≤ 0.82 ms；客户端 p50 1.78–2.25 ms，cheroot 为 60.8–60.9 ms（来自 keep-alive，§3.6）。在 loop 线程上调用时，0.009–0.016 ms 内抛 `RuntimeError`。

#### Windows 端口复用（第 3 项；`s0b_portbind.py matrix`、`host`；附表 `PORTBIND_TABLE`）

占用者与入侵者都在另一个进程中，只绑定 127.0.0.1（端口 8854/8855）；每个用例发 20 个连接，记录由谁应答。本机 TCP 动态端口范围为 1024–15000，包含 8840–8859。
- waitress 与 devserver 在 Windows 上也设置 `SO_REUSEADDR`：waitress 用 `wasyncore.set_reuse_addr()`（`server.py:240`，失败时吞掉 `OSError`，`wasyncore.py:339`），devserver 用 Django `WSGIServer(allow_reuse_address=True)`（`basehttp.py:74,77`）。
  - 另一进程以 `SO_REUSEADDR` 占着端口时，它们照常“启动”，但 20/20 个连接都由占用者应答，端口占用检测不报错。
  - 它们先监听时，带 `SO_REUSEADDR` 的入侵者也能绑定，但连接仍由先监听的一方接收（20/20）。
  - 占用者为默认或独占选项时，它们绑定失败（10013）。
- cheroot 在 Windows 上不设置 `SO_REUSEADDR`（`server.py:2128-2139`，cherrypy/cheroot#114），3 种占用下都绑定失败。但它把错误包装成新的 `OSError('No socket could be created -- (…)')`（`server.py:1846-1858`），没有 `winerror` 属性，调用方只能从消息文本区分 10013 与 10048。
- 带 `SO_REUSEADDR` 的绑定撞上默认或独占的占用者时，返回 10013 WSAEACCES 而不是 10048。在 Windows 上，“端口被占用”可能表现为“权限不足”。

宿主修正：主线程先以 127.0.0.1 + `SO_EXCLUSIVEADDRUSE` 创建并绑定监听 socket，再交给 server（waitress `create_server(..., sockets=[sock])`，cheroot 用预绑定的 `wsgi.Server` 子类）。结果（`--state-lock`；附表 `PBHOST_TABLE`）：
- 被占用：waitress、cheroot 各 2 种占用者（默认、`SO_REUSEADDR`），4/4 个用例在 0.36–0.43 s 内 exit 4（10048），runtime 未启动，没有创建 state 目录与锁。
- 对照（宿主先监听）：3 种入侵者都绑定失败（`SO_REUSEADDR` 10013，默认与独占 10048），入侵前后各 10 个连接都由宿主应答（HTTP 400：探测用 `Host: x`，记为 `other-400`；宿主是唯一成功绑定的监听者），锁一直由宿主持有；同端口的第二个宿主 0.45 s exit 4；共用 state 目录、换端口的第二个宿主因锁被占 exit 5，没有进入 lifespan。用 M 参数、合法 Host 与凭据的反向绑定复测（上一轮补测 (a)）见 §3.10；M6 没有运行。

#### 停止过程中的第二个信号（第 4 项；`s0b_sig2.py`，CPython 3.13.7；附表 `SIG2_TABLE`）

- 方法：第 1 个 CTRL_C 或 CTRL_BREAK 使子进程进入停止等待，1.0 s 后发送第 2 个同类事件，记录第 2 个事件到进程退出的时间（每种 2 次）。结果：不切片的 `Thread.join(10)` 为 8.58–8.61 s，切片 0.5 s 为 0.22–0.23 s，都由处理器 `os._exit(130)` 退出。0.22–0.23 s 包含助手发送后固定的 0.2 s 休眠（组合宿主的 M1 改为从助手在单调时钟上记录的发送时刻计时）。
- 原因：CPython 只在主线程执行 Python 信号处理器。主线程阻塞在不切片的 join 上时，处理器要等 join 返回才运行，延迟约等于 join 的剩余时间。
- waitress 的 `run()` 在主线程上时，处理器同样要等 `select` 返回（`asyncore_loop_timeout=1`）。第 1 项（改动前的宿主）中，stop-file 触发后 0.04–0.06 s 收到停止请求，CTRL_BREAK 为 0.30 s，CTRL_C 为 0.54 s。
- 组合宿主（M1，§3.10）：重复信号改为 `os._exit(130)`，主线程上的等待都切片到 ≤ 0.5 s，waitress `run()` 移到非 daemon 线程 `serve-http`，主线程只做 0.5 s 切片等待。排空与 flush 两个阶段 × CTRL_BREAK/CTRL_C × 2 次，8/8 以 130 退出：第 2 个信号到处理器 0.003–0.021 s，到进程退出 0.061–0.084 s；没有输出 `project_runtime_stopped`。

#### loop 阻塞时的门面超时（第 5 项；`s0b_b9.py admission` 的 split 会话，waitress + wn-noauto + custom 桥；附表 `STALL_TABLE`）

- 门面超时：在 loop 线程上排入 `time.sleep(3)`。阻塞期间，Django 请求线程（`waitress-7`）上 timeout 0.3 s 的门面调用在视图内 0.3032 s 抛 `TimeoutError`，客户端 309.74 ms（门限 timeout + 0.2 s = 0.5 s），PASS。
- 阻塞期间的其他请求：`home` ×3（含 61 个静态资源）全部成功，p50 128.4 ms、max 138.7 ms；Django 路由 `/s0/health` 18 ms 返回 404（`--urlconf s0b` 下没有该路由，只说明请求线程未被阻塞）。`/ai/health` 与 `/ai/s0b/asset.js` 都等到 loop 恢复才返回 200（2.76 s），期间各占 1 个短请求名额与 1 个 WSGI 线程；分离准入限制了被占线程的上限，所以页面不受影响。
- 遗留 task：阻塞前后 loop 上的 pending task 都是 22 个，coroutine 列表相同，没有遗留。
- 超时不等于未开始（R21）：阻塞结束后的下一次门面调用得到 `s0-run-2`。原因是门面超时后调用的 `future.cancel()`，对 `run_coroutine_threadsafe` 而言要等 loop 恢复后经 `call_soon_threadsafe` 送达，而 task 的第一步排在取消之前。所以超时调用的第一步照常执行（生成 `s0-run-1` 并 `queue.put`），取消落在其后的第一个 `await` 上，调用方也收不到回执。

### 3.2 B3：流式延迟（100 ms × 50 个事件；门限：首事件 ≤ 200 ms，间隔 p95 ≤ 150 ms；附表 `B3_TABLE`）

- 6 个组合 × 3 种流（ASGI SSE、ASGI NDJSON、Django 原生 SSE）都收到 50/50 个事件，没有缓冲：首事件 1.3–3.6 ms，间隔 p95 100.5–109.8 ms，max ≤ 164.9 ms（devserver 上的 Django SSE）。
- devserver 的流式响应既没有 `Content-Length` 也不分块（Django `ServerHandler` 对长度未知的响应改为关闭连接），客户端只能靠终止事件区分正常结束与中断。waitress 与 cheroot 使用 chunked。

### 3.3 B4：客户端中止

每个组合：10 个活动流在第 3 个事件后中止，10 个空闲流在首个心跳后 0.2 s 中止；中止 6 s 后读取 loop 状态。

| 组合 | 活动流 检出/n · p50/max ms（门限 1100） | 空闲流 检出/n · p50/max ms（门限 3000） | 检出方式 | 遗留 task | 遗留占用 handler | 线程数变化 | 应用 `finally` 结束原因 | 结论 |
|---|---|---|---|---|---|---|---|---|
| devserver × custom | 10/10 · 199.7/203.4 | 10/10 · 14.1/17.8 | disconnect×20 | 0 | 0 | 0 | http.disconnect×20 | PASS |
| devserver × a2wsgi | 0/10 · —/— | 0/10 · —/— | never×20 | 20 | 0 | 0 | None×20 | FAIL |
| waitress × custom | 10/10 · 92.6/106.8 | 10/10 · 18.2/22.3 | disconnect×19, oserror×1 | 0 | 0 | 0 | http.disconnect×19, send-oserror×1 | PASS |
| waitress × a2wsgi | 0/10 · —/— | 0/10 · —/— | never×20 | 20 | 0 | 0 | None×20 | FAIL |
| cheroot × custom | 10/10 · 108.2/199.4 | 10/10 · 15.5/19.6 | disconnect×19, oserror×1 | 0 | 0 | 0 | http.disconnect×19, send-oserror×1 | PASS |
| cheroot × a2wsgi | 0/10 · —/— | 0/10 · —/— | never×20 | 30 | 0 | 0 | None×20 | FAIL |

a2wsgi 1.10.10 代码核对（`a2wsgi/asgi.py`）与实测一致：
- `__call__` 是生成器，`yield`（`:248`）外没有 try/finally。客户端断开后 WSGI server 调 `close()` 时，既不发送 `http.disconnect`（只在 `:294`，即正常读完响应之后发送），也不取消 task（`:302`）；task 停在 `asgi_send` 的 `send_event.wait()`（`:178`）。
- scope 的 `spec_version` 为 "2.5"（`:98`），因此 Starlette `StreamingResponse` 不监听断开（`starlette/responses.py:270-276`），只依赖 `send` 抛 `OSError`；而 a2wsgi 的 `send` 从不抛出。
- 跨线程等待都没有时限：`__init__` 用 `call_soon_threadsafe` 创建锁（`:165`）；`execute_in_loop` 用不带时限的 `.result()`（`:213-214`）；`SyncEvent.wait()` 是不带时限的 `threading.Event.wait()`；`asgi_done.wait(wait_time=None)`（`:301`）。loop 停止后，请求线程会永久阻塞（见 B5 cheroot）。
- 遗留 task 只有在之后被 GC 销毁时才结束（server 日志中 "Task was destroyed but it is pending!" 分别出现 14/13/10 次）。这时应用的 `finally` 才运行，而且收不到 `http.disconnect` 或 `CancelledError`（`end_reason=None`）。

### 3.4 B5：两条打开的流（活动流 `terminal=1` + 空闲流 `terminal=0`）时停止，drain 预算 10 s（附表 `B5_TABLE`）

- custom（3 种 server × 3 种触发）9/9 PASS：活动流在 0.01–1.01 s 内收到终止事件并干净结束；空闲流不支持终止事件，在 2 s 宽限期后被取消（2.0–3.0 s）；drain 2.01–2.52 s，停止到退出 2.02–2.52 s，exit 0，1 行 stop，0 个遗留 task（脚本 `pass` 不要求空闲流收到终止事件；0.5 B5 的这一子条件见下文 b5s，M 参数下 3 种触发 × `flush` 见 §3.10 M4）。
- a2wsgi 3/3 FAIL：两条流都要等 10 s drain 到期、连接被关闭才结束，没有终止事件，遗留 4–8 个 task。cheroot × a2wsgi 中，server 线程阻塞在 a2wsgi 的无时限等待上，而 cheroot 11.1.2 的 `ThreadPool.stop` 在超时后还会对 worker 做一次无时限 `join()`（`workers/threadpool.py:352-393`），进程卡住，直到看门狗在 35.2 s 强制 exit 3。

#### 客户端确认收到终止事件（第 1 项；`s0b_b5s.py`，custom 桥）

设置：一条活动流（100 ms 间隔）和一条空闲流（每 2 s 一个心跳），两条都支持宿主关闭事件。客户端 `s0b_tail.py` 用原始 socket 增量读取，记录终止事件完整到达的时刻、EOF 时刻和分块终止符。慢读用例中，活动流先写出 8 MB 填充数据，客户端前 3 s 不读；停止时 waitress 的输出缓冲中还有 7.8 MB 未写出。

| 用例 | server · 收尾 · 触发 | stop.requested s | 活动流：终止事件 / EOF s · 结束分界 · 字节 | 空闲流：终止事件 / EOF s | 终止事件晚于停止受理 ms（活动/空闲） | 触发后 0.3 s 新连接 | exit · 退出 s | 结论 |
|---|---|---|---|---|---|---|---|---|
| `b5s-cheroot-stopfile`（重跑） | cheroot · close · stop_file | 0.04 | 0.04 / 0.04 · 块终止符 · 573 | 0.04 / 0.04 | 1.0 / 1.2 | ConnectTimeout | 0 · 0.99 | PASS |
| `b5s-devserver-stopfile`（重跑） | devserver · close · stop_file | 0.04 | 0.31 / 0.31 · 关闭分界 · 725 | 0.31 / 0.31 | 1.2 / 1.9 | 503 | 0 · 1.41 | PASS |
| `b5s-waitress-ctrlbreak` | waitress · close · ctrl_break | 0.30 | 0.31 / 0.31 · 块终止符 · 792 | 0.31 / 0.31 | 0.8 / 1.1 | 503 | 0 · 1.30 | PASS |
| `b5s-waitress-ctrlc` | waitress · close · ctrl_c | 0.54 | 0.55 / 0.55 · 块终止符 · 4390 | 0.55 / 0.55 | 1.4 / 1.8 | 503 | 0 · 1.69 | PASS |
| `b5s-waitress-flush-stopfile` | waitress · flush · stop_file | 0.04 | 0.05 / 0.05 · 块终止符 · 644 | 0.05 / 0.05 | 0.9 / 1.3 | ConnectTimeout | 0 · 1.14 | PASS |
| `b5s-waitress-stopfile` | waitress · close · stop_file | 0.06 | 0.07 / 0.07 · 块终止符 · 644 | 0.07 / 0.07 | 0.9 / 1.6 | ConnectTimeout | 0 · 1.11 | PASS |
| `b5s-slow-cheroot` | cheroot · close · stop_file（慢读） | 0.13 | 3.06 / 3.06 · 块终止符 · 8000661 | 0.18 / 0.18 | 2931.5 / 47.3 | ConnectTimeout | 0 · 1.24 | PASS |
| `b5s-slow-devserver` | devserver · close · stop_file（慢读） | 0.08 | 3.06 / 3.06 · 关闭分界 · 8000736 | 0.37 / 0.37 | 2753.7 / 60.2 | 503 | 0 · 1.34 | PASS |
| `b5s-slow-waitress-close` | waitress · close · stop_file（慢读） | 0.19 | — / 3.05 · **无块终止符** · 197192 | 0.25 / 0.25 | — / 55.6 | ConnectTimeout | 0 · 1.29 | **FAIL** |
| `b5s-slow-waitress-flush` | waitress · flush · stop_file（慢读） | 0.04 | 3.31 / 5.95 · 块终止符 · 8000588 | 0.09 / 0.09 | 3268.3 / 53.9 | ConnectTimeout | 0 · 7.08 | PASS |

- 正常读取（6 个用例：3 种 server 的 stop-file，加上 waitress 的 CTRL_BREAK、CTRL_C 与 `flush` 收尾）：两条流都在 EOF 之前收到完整的终止事件。终止事件在“停止受理”结束后 0.8–1.9 ms 写出：停止受理只关闭监听，已有连接的 I/O（waitress 由 asyncore 线程写出）不受影响。
- 慢读：
  - waitress `close` 收尾时，`handle_close()` 直接丢弃 channel 的输出缓冲。客户端只收到 197,192 字节，没有终止事件，也没有分块终止符；进程仍然 exit 0，所以只能在客户端发现。
  - 改用 `flush` 收尾后，3.31 s 收到终止事件，5.95 s EOF，7.08 s exit 0，在 10 s 预算内。
  - devserver 与 cheroot 的工作线程同步写 socket，写完才返回，所以没有这个问题。
- 触发后 0.3 s 发起的新连接：监听已关闭时表现为连接超时（Windows 会对被拒绝的连接重试 SYN）；监听尚未关闭时（devserver，以及 waitress 的 CTRL 触发用例），连接被受理并立即得到 503。
- 排空期间的 503 探测（附表 `PROBE_TABLE`）：同一 keep-alive 连接上的请求，waitress 1.1–1.5 ms、devserver 1.6–2.6 ms、cheroot 6–62 ms 内得到 503。
- Django 原生流不计入排空：另开一条 Django 原生 `StreamingHttpResponse` SSE 流，宿主的在途统计不包含它（`django_inflight` 只统计 `__call__` 期间），所以排空不会等它。waitress 在 2.10 s 收尾时把它截断（23/100 个事件），devserver 在 3.28 s 截断（24/100）；cheroot 的 `server.stop()` 等工作线程把它发完（100/100），9.80 s 才退出。

### 3.5 补充：Starlette `StreamingResponse`（AI Base 聊天流使用的响应类）经过各桥（`s0b_starlette_check.py`；附表 `SL_TABLE`）

- custom 桥：
  - B3：首事件 14.7–18.3 ms（自写端点为 1.3–3.6 ms，差异原因未分析），间隔 p95 108.1–108.5 ms。
  - B4：开启探测时，活动流 p50 93–111 ms、空闲流 15–16 ms 检出断开，0 遗留。
  - B5：两条流在 2 s 宽限期后被取消，2.12–2.31 s 在 HTTP 层干净结束，但没有终止事件（生成器不感知宿主，R10/R15）。
- 关闭断开探测（`--disconnect-probe off`，只靠写失败发现断开）时，空闲流要等下一次心跳写入：
  - waitress 1.80 s（第 1 次心跳写失败），PASS；
  - devserver 3.80 s（第 1 次心跳写入没有报错，第 2 次才失败），超过 3.0 s 门限，**FAIL**（R16）。
- waitress × a2wsgi：B3 PASS；B4 0/10 检出，10 个遗留 task；B5 drain 10 s 超时，两条流被截断，FAIL（R17、R18）。

### 3.6 keep-alive 微基准（`s0b_keepalive.py`；cheroot 不达标的根因；附表 `KA_TABLE`）

cheroot 11.1.2 在 Windows 上把连接管理的 `select` 超时设为 `min(expiration_interval, 0.05)`（`connections.py:224-234`，源码注释为 "select() does not return when a socket is ready"）。因此 keep-alive 连接上每个后续请求约 61 ms；`expiration_interval` 设为 0.01 或 0.001 时约 15 ms，受 Windows 计时粒度限制。一个有 61 个资源的页面顺序加载，cheroot 约 3.78 s，waitress 与 devserver 约 0.13–0.15 s。新建连接时三种 server 都约 2.7–3.7 ms。

### 3.7 B6：C5 性能（`s0b_perf.py`，原样复用 `perf.py` 的 `sample`/`run_block`/`summarize`）

方法：同 S0。DEBUG=True、同一播种 sqlite、同一组 stub 页面、6 个页面、seq 与 c4 两种模式、交错块（奇数块倒序）、warmup 10、所有 arm 都开访问日志；比值 = 同一次运行中 arm p95 / `baseline` p95。`baseline` 是未改动的 `serve_baseline.py`（`call_command('project_serve')`）。除 `baseline` 外，所有 arm 都加载 AI Base、运行 runtime loop 线程并使用 custom 桥（B3/B4/B5 通过的桥）。单元格格式为 `p50/p95 ×p95 比值 h=仅 HTML 的 p95 r=单个请求 p50`（ms），粗体表示 > 1.20。

偏差：Phase 1 中 cheroot 的 arm 每块只取 2 个样本（`cheroot_wn_ei001` 取 4 个），warmup 2。原因是每个样本约 3.8 s，按原样本数单个 arm 约需 1 h。这些 arm 的比值为 1.84–47×，全部 > 1.20，结论不受样本数影响。

Phase 1 筛选（`b6-phase1.json`；n seq/c4：`baseline` 60/60，`dev_sfh` 60/60，`dev_wn` 60/60，`waitress_sfh` 60/60，`waitress_wn` 60/60，`waitress_wn_noauto` 60/60，`cheroot_sfh` 8/16，`cheroot_wn` 8/16，`cheroot_wn_noauto` 8/16，`cheroot_wn_ei001` 16/16；warmup：`baseline` 10，`dev_sfh` 10，`dev_wn` 10，`waitress_sfh` 10，`waitress_wn` 10，`waitress_wn_noauto` 10，`cheroot_sfh` 2，`cheroot_wn` 2，`cheroot_wn_noauto` 2，`cheroot_wn_ei001` 2；测量 1559.3 s）：

| 模式 | arm | home | projects | project_detail | stage_reports | draft_edit | bug_trend | ≤1.20 |
|---|---|---|---|---|---|---|---|---|
| seq | `baseline` | 123/147 h16 r1.83 | 147/177 h22 r2.14 | 139/168 h29 r1.94 | 192/234 h85 r2.01 | 216/253 h80 r2.26 | 130/168 h30 r1.79 | — |
| seq | `dev_sfh` | 127/183 **×1.25** h18 r1.90 | 143/182 ×1.03 h22 r2.06 | 137/158 ×0.94 h27 r1.90 | 189/220 ×0.94 h79 r1.93 | 203/252 ×1.00 h72 r2.14 | 140/168 ×1.00 h29 r1.90 | 5/6 |
| seq | `dev_wn` | 129/181 **×1.24** h16 r1.94 | 161/206 ×1.17 h24 r2.38 | 144/181 ×1.08 h25 r2.04 | 200/231 ×0.99 h83 r2.13 | 230/263 ×1.04 h77 r2.46 | 149/171 ×1.02 h29 r2.07 | 5/6 |
| seq | `waitress_sfh` | 128/146 ×0.99 h16 r1.89 | 156/187 ×1.06 h22 r2.29 | 146/172 ×1.02 h31 r2.03 | 205/249 ×1.07 h85 r2.16 | 213/276 ×1.09 h80 r2.25 | 149/174 ×1.03 h32 r2.06 | 6/6 |
| seq | `waitress_wn` | 149/170 ×1.16 h18 r2.20 | 165/186 ×1.05 h22 r2.42 | 158/177 ×1.06 h29 r2.24 | 219/251 ×1.08 h85 r2.40 | 221/260 ×1.03 h75 r2.38 | 156/181 ×1.08 h32 r2.18 | 6/6 |
| seq | `waitress_wn_noauto` | 116/131 ×0.89 h14 r1.73 | 138/163 ×0.93 h21 r2.02 | 132/153 ×0.91 h28 r1.84 | 182/216 ×0.92 h83 r1.82 | 191/224 ×0.89 h74 r1.91 | 127/150 ×0.89 h26 r1.75 | 6/6 |
| seq | `cheroot_sfh` | 3730/3791 **×25.84** h72 r60.85 | 3761/3787 **×21.45** h81 r60.69 | 3723/3777 **×22.51** h87 r60.52 | 3841/3909 **×16.74** h128 r60.77 | 4204/4270 **×16.87** h155 r60.37 | 3724/3788 **×22.49** h81 r60.63 | 0/6 |
| seq | `cheroot_wn` | 3730/3786 **×25.81** h74 r60.81 | 3719/3783 **×21.43** h81 r60.48 | 3719/3795 **×22.62** h85 r60.54 | 3844/3908 **×16.74** h147 r60.66 | 4213/4272 **×16.88** h139 r60.65 | 3722/3789 **×22.50** h84 r60.62 | 0/6 |
| seq | `cheroot_wn_noauto` | 3726/3790 **×25.84** h75 r60.79 | 3749/8381 **×47.47** h81 r60.56 | 3726/3783 **×22.55** h94 r60.54 | 3856/3918 **×16.78** h134 r60.81 | 4210/4294 **×16.97** h155 r60.71 | 3728/3790 **×22.50** h81 r60.65 | 0/6 |
| seq | `cheroot_wn_ei001` | 946/954 **×6.50** h25 r15.16 | 949/970 **×5.50** h34 r15.18 | 958/976 **×5.82** h44 r15.18 | 1030/1066 **×4.56** h113 r15.25 | 1109/4587 **×18.13** h96 r15.25 | 960/975 **×5.79** h46 r15.20 | 0/6 |
| c4 | `baseline` | 335/382 h42 r5.15 | 343/387 h49 r5.09 | 362/432 h93 r5.13 | 490/545 h221 r5.01 | 577/696 h221 r5.72 | 353/429 h88 r5.10 | — |
| c4 | `dev_sfh` | 334/376 ×0.98 h42 r5.08 | 338/398 ×1.03 h55 r5.06 | 380/428 ×0.99 h79 r5.26 | 506/835 **×1.53** h225 r5.17 | 576/675 ×0.97 h240 r5.98 | 344/390 ×0.91 h81 r4.78 | 5/6 |
| c4 | `dev_wn` | 376/451 ×1.18 h42 r5.72 | 367/420 ×1.08 h48 r5.51 | 390/468 ×1.08 h86 r5.51 | 560/758 **×1.39** h245 r6.13 | 578/658 ×0.95 h208 r6.12 | 372/410 ×0.96 h67 r5.30 | 5/6 |
| c4 | `waitress_sfh` | 361/414 ×1.08 h42 r5.49 | 349/399 ×1.03 h51 r5.24 | 387/570 **×1.32** h75 r5.38 | 484/637 ×1.17 h240 r5.25 | 547/621 ×0.89 h211 r5.64 | 360/420 ×0.98 h73 r5.04 | 5/6 |
| c4 | `waitress_wn` | 365/420 ×1.10 h40 r5.56 | 390/434 ×1.12 h53 r5.75 | 424/528 **×1.22** h100 r5.99 | 526/723 **×1.33** h216 r5.73 | 575/4422 **×6.36** h254 r6.05 | 389/434 ×1.01 h68 r5.47 | 3/6 |
| c4 | `waitress_wn_noauto` | 290/341 ×0.89 h46 r4.39 | 307/345 ×0.89 h50 r4.51 | 341/375 ×0.87 h80 r4.59 | 457/599 ×1.10 h231 r4.49 | 510/563 ×0.81 h212 r4.97 | 318/370 ×0.86 h72 r4.25 | 6/6 |
| c4 | `cheroot_sfh` | 3727/3800 **×9.94** h70 r60.68 | 3724/3738 **×9.66** h50 r60.46 | 3777/3796 **×8.80** h74 r60.84 | 3982/4102 **×7.52** h336 r60.93 | 4321/4365 **×6.28** h229 r60.81 | 3780/3798 **×8.85** h108 r60.66 | 0/6 |
| c4 | `cheroot_wn` | 3731/3738 **×9.78** h43 r60.64 | 3730/3799 **×9.81** h67 r60.53 | 3777/3805 **×8.82** h87 r60.95 | 3907/3965 **×7.27** h209 r60.46 | 4285/4344 **×6.25** h199 r60.43 | 3786/3797 **×8.85** h83 r60.86 | 0/6 |
| c4 | `cheroot_wn_noauto` | 3733/3791 **×9.92** h73 r60.52 | 3729/3737 **×9.65** h58 r60.40 | 3731/3783 **×8.76** h77 r60.51 | 3914/3978 **×7.30** h210 r60.60 | 4316/4346 **×6.25** h211 r60.75 | 3734/3797 **×8.85** h75 r60.50 | 0/6 |
| c4 | `cheroot_wn_ei001` | 962/991 **×2.59** h52 r15.34 | 986/1007 **×2.60** h58 r15.39 | 1001/1043 **×2.42** h87 r15.29 | 1138/1166 **×2.14** h223 r15.35 | 1248/1278 **×1.84** h215 r15.68 | 988/1023 **×2.39** h91 r15.29 | 0/6 |

p95 比值范围：`dev_sfh` seq 0.94–1.25，c4 0.91–1.53，达标 10/12；`dev_wn` seq 0.99–1.24，c4 0.95–1.39，达标 10/12；`waitress_sfh` seq 0.99–1.09，c4 0.89–1.32，达标 11/12；`waitress_wn` seq 1.03–1.16，c4 1.01–6.36，达标 9/12；`waitress_wn_noauto` seq 0.89–0.93，c4 0.81–1.10，达标 12/12；`cheroot_sfh` seq 16.74–25.84，c4 6.28–9.94，达标 0/12；`cheroot_wn` seq 16.74–25.81，c4 6.25–9.81，达标 0/12；`cheroot_wn_noauto` seq 16.78–47.47，c4 6.25–9.92，达标 0/12；`cheroot_wn_ei001` seq 4.56–18.13，c4 1.84–2.60，达标 0/12。进程：所有 arm exit 0，各 1 行 `project_runtime_stopped`；启动→就绪 s `baseline` 4.9，`dev_sfh` 21.2，`dev_wn` 21.2，`waitress_sfh` 21.2，`waitress_wn` 21.2，`waitress_wn_noauto` 21.7，`cheroot_sfh` 21.7，`cheroot_wn` 21.8，`cheroot_wn_noauto` 21.7，`cheroot_wn_ei001` 21.7。

- Phase 1 只有 `waitress_wn_noauto` 12/12 达标（seq 0.89–0.93×，c4 0.81–1.10×）。其余 arm：
  - `waitress_sfh` 11/12（c4 project_detail 1.32×）；
  - `dev_sfh`、`dev_wn` 各 10/12；
  - `waitress_wn` 9/12，其中 c4 draft_edit 6.36× 来自 p95 4422 ms 的离群样本，p50 575 ms 与基线 577 ms 持平；
  - cheroot 4 个 arm 都是 0/12（keep-alive 问题，§3.6）。
- `wn` 比 `wn-noauto` 慢：autorefresh 时 WhiteNoise 对每个请求重新查找文件（WhiteNoise 文档说明该设置只用于开发）。单个请求 p50：seq `waitress_wn` 2.18–2.42 ms，`waitress_wn_noauto` 1.73–2.02 ms，基线 1.79–2.26 ms。

Phase 2 判定（`b6-phase2.json`；n seq/c4：`baseline` 160/160，`waitress_wn_noauto` 160/160，`waitress_wn` 160/160，`dev_wn` 160/160；warmup：`baseline` 10，`waitress_wn_noauto` 10，`waitress_wn` 10，`dev_wn` 10；测量 1035.7 s）：

| 模式 | arm | home | projects | project_detail | stage_reports | draft_edit | bug_trend | ≤1.20 |
|---|---|---|---|---|---|---|---|---|
| seq | `baseline` | 125/142 h15 r1.88 | 136/165 h22 r1.99 | 132/163 h26 r1.84 | 195/230 h79 r2.06 | 197/236 h75 r2.03 | 130/159 h27 r1.82 | — |
| seq | `waitress_wn_noauto` | 119/136 ×0.96 h16 r1.76 | 127/150 ×0.91 h21 r1.85 | 126/150 ×0.92 h28 r1.75 | 175/205 ×0.89 h77 r1.82 | 179/246 ×1.04 h74 r1.79 | 125/144 ×0.90 h27 r1.71 | 6/6 |
| seq | `waitress_wn` | 153/189 **×1.33** h18 r2.30 | 154/177 ×1.07 h20 r2.26 | 160/188 ×1.15 h28 r2.24 | 213/239 ×1.04 h79 r2.35 | 223/272 ×1.15 h79 r2.39 | 151/181 ×1.13 h29 r2.11 | 5/6 |
| seq | `dev_wn` | 138/162 ×1.14 h16 r2.09 | 147/178 ×1.08 h20 r2.17 | 152/185 ×1.13 h29 r2.13 | 206/242 ×1.05 h79 r2.21 | 215/285 **×1.21** h80 r2.26 | 134/153 ×0.96 h27 r1.87 | 5/6 |
| c4 | `baseline` | 339/386 h35 r5.23 | 355/418 h44 r5.40 | 349/402 h65 r4.99 | 491/586 h207 r5.25 | 532/621 h192 r5.53 | 377/460 h74 r5.36 | — |
| c4 | `waitress_wn_noauto` | 291/339 ×0.88 h39 r4.46 | 314/371 ×0.89 h46 r4.70 | 329/371 ×0.92 h72 r4.65 | 474/564 ×0.96 h216 r4.87 | 492/544 ×0.88 h190 r4.91 | 348/429 ×0.93 h73 r4.82 | 6/6 |
| c4 | `waitress_wn` | 357/407 ×1.05 h32 r5.52 | 382/425 ×1.02 h41 r5.79 | 383/466 ×1.16 h65 r5.57 | 575/683 ×1.17 h226 r6.13 | 567/621 ×1.00 h189 r6.04 | 426/510 ×1.11 h72 r6.10 | 6/6 |
| c4 | `dev_wn` | 360/412 ×1.07 h37 r5.60 | 371/419 ×1.00 h47 r5.63 | 398/445 ×1.11 h73 r5.63 | 513/684 ×1.17 h218 r5.60 | 560/669 ×1.08 h200 r6.07 | 402/436 ×0.95 h71 r5.66 | 6/6 |

p95 比值范围：`waitress_wn_noauto` seq 0.89–1.04，c4 0.88–0.96，达标 12/12；`waitress_wn` seq 1.04–1.33，c4 1.00–1.17，达标 11/12；`dev_wn` seq 0.96–1.21，c4 0.95–1.17，达标 11/12。进程：所有 arm exit 0，各 1 行 `project_runtime_stopped`；启动→就绪 s `baseline` 4.1，`waitress_wn_noauto` 14.6，`waitress_wn` 14.6，`dev_wn` 14.6。

- Phase 2（threads 8）中，`waitress_wn_noauto` 12/12 达标：seq 0.89–1.04×，c4 0.88–0.96×；单个请求 p50 seq 1.71–1.85 ms，低于基线 1.82–2.06 ms。它是唯一同时满足“静态文件在认证之后”和 C5 的 production server 组合。
- `waitress_wn` 11/12（seq home 1.33×）与 `dev_wn` 11/12（seq draft_edit 1.21×），都 FAIL。
- `sfh` arm 静态文件绕过认证，只作诊断，没有进入 Phase 2。
- “只有 devserver 通过”的停止条件没有触发：通过的是 waitress，devserver（`dev_wn`）没有通过。

诊断（不计门限；`waitress_wn_noauto`，seq，4 块 × 20，warmup 10，exit 0；附表 `DIAG_TABLE`）：loop 上同时有 2 条 50 ms NDJSON 流时，`home` p50/p95 为 115/129 ms（无流 113/137），`bug_trend` 为 114/128 ms（无流 113/132），（相对同 arm 无流）p95 比 0.94、0.97，p50 比 1.02、1.01；流事件间隔 p95 ≤ 62.3 ms。runtime loop 上的流没有拖慢页面。M 参数（threads 12、分离准入、`flush`）下的 Phase 2 复测，以及与 B9 (a)(b)(c) 同一次饱和的测量，见 §3.10 M2。

### 3.8 B7：浏览器子集（`s0b_browser_runner.py`，与 S0 C6 相同的 11 个测试）

- 结果：stock 与候选都是 11/11 passed，逐个测试结果一致（附表 `B7_TABLE`）。
- 候选模式：waitress + wn-noauto + custom 桥，threads 8，带 runtime loop 线程与 AI Base lifespan。
  - live server 用自定义 `server_thread_class`。
  - 静态文件由位于 BasicAuth 之后的 WhiteNoise 提供（`AUTOREFRESH=False`、`USE_FINDERS=True`、`MAX_AGE=0`；测试运行器下构建时 `DEBUG=False`），替换了 `StaticLiveServerTestCase` 的 `StaticFilesHandler`。
  - 探测：`/ai/health`、`/ai/openapi.json` 无凭据时 401，`/ai` 308。
- 用时：pytest stock 407.4 s，候选 446.5 s。差异主要来自 `TestReportDailyUiBrowser` 的 2 个测试（+19.9 s、+10.9 s），原因未分析。
- M3（M 参数：threads 12、分离准入流 4/短请求 2、`flush`，live server 按宿主停止预算停止；`rec\b7-candidate-t12-*`）：11/11 passed，逐个测试结果与 stock 一致；pytest 417.9 s。3 个 live server 类分别用端口 8856/8857/8858；探测 `/ai/health`、`/ai/openapi.json` 无凭据 401，`/ai` 308 到 `/ai/`；`ProactorEventLoop`，没有对外网络尝试，退出时没有遗留线程，`budget_misses` 为空。这 11 个测试不访问 `/ai`。

### 3.9 B9：AI 饱和不拖慢页面（第 2 项；`s0b_b9.py admission`、`s0b_perf.py`）

设置：waitress + wn-noauto + custom 桥，`threads 8`，`--perf --urlconf s0b`。用 1 条活动 SSE（100 ms）和 3 条空闲 NDJSON（每 2 s 一个心跳）占满流上限。两种设计：
- 共享：`--ai-limit-mode shared --ai-inflight-limit 4`，端口 8850；
- 分离：`--ai-limit-mode split --ai-stream-limit 4 --ai-short-limit 2`，端口 8851。

| 设计 | (a) 新流请求 ×10：状态 · p50/max ms | (b) `/ai/s0b/asset.js` ×20 | (b) `/ai/health` ×20 | 短请求池突发 | `home` p50 ms（含 61 个资源）未饱和/饱和 | 停止：终止事件 · EOF s · exit | 结论 (a)/(b) |
|---|---|---|---|---|---|---|---|
| shared（--ai-inflight-limit 4） | 503×10 · 1.7/2.0 · Retry-After 2 | 503×20 · 1.1/2.3 · Retry-After 2 | 503×20 · 1.1/1.5 · Retry-After 2 | —（共享池已被流占满） | 160.5/134.7 | 4/4 · 0.10–0.10 · 0 | PASS / **FAIL** |
| split（--ai-stream-limit 4 --ai-short-limit 2） | 503×10 · 2.0/24.6 · Retry-After 2 | 200×20 · 1.9/4.7 | 200×20 · 4.0/5.4 | 2 个慢短请求（1.5 s）占满短池时：第 3 个 asset 503、health 503；Django 路由 `/s0/health` 17 ms 返回 404（未被阻塞，不是页面请求）；释放后 asset 200 | 133.6/133.7 | 4/4 · 0.13–0.14 · 0 | PASS / PASS |

- (a) 两种设计下，第 5 条流请求（SSE 与 NDJSON 路由）都立即得到 503 + `Retry-After: 2`，响应体标明是哪个池（`shared`/`stream`）。无凭据请求仍是 401。
- (b) 共享上限时，流用完名额后短请求也全部 503，所以共享设计不满足 (b)。分离设计下短请求 20/20 返回 200。
  - 短请求池本身被 2 个 1.5 s 慢请求占满时，第 3 个短请求 2.6–2.8 ms 内得到 503；Django 路由 `/s0/health` 17 ms 返回 404（未被阻塞，不是页面请求）；慢请求结束后恢复 200。
  - 分离会话结束时的计数：流拒绝 11、短请求拒绝 2、短请求放行 47。
- 饱和期间 waitress 忙线程为 5（4 条流加 1 个状态请求），loop 上 pending task 为 22。停止时 4 条流都收到终止事件，0.10–0.14 s 后 EOF，exit 0，`project_runtime_stopped` 1 行。
- 结果中 `streams_healthy=false` 来自检查器本身：共享会话的测试窗口短于 2 s，窗口内没有空闲心跳（活动流间隔 p95 109 ms）；分离会话包含第 5 项故意制造的 3 s 阻塞。

(c) 页面 p95：方法同 B6（seq + c4，4 块 × 40，warmup 10，静态在认证之后，与同一次运行中的 `baseline` 比较）。`b9_sat_t8`、`b9_sat_t12`（threads 8/12，分离准入流 4/短请求 2）在测量开始前由 `s0b_b9.py hold` 进程用 4 条流占满流上限，并一直保持到测量结束；`waitress_wn_noauto`（threads 8、无准入、`close`）是未饱和的对照；本次没有 threads 12 加分离准入的未饱和 arm，hold 期间也没有发短 `/ai` 请求。这两点由签核补测 M2 补上（未饱和 arm `rec_t12`；hold 期间每 1 s 发 2 个短 `/ai` 请求，每 5 s 探测第 5 条流），见 §3.10。

B9(c) 饱和（`b9-perf.json`；n seq/c4：`baseline` 160/160，`waitress_wn_noauto` 160/160，`b9_sat_t8` 160/160，`b9_sat_t12` 160/160；warmup：`baseline` 10，`waitress_wn_noauto` 10，`b9_sat_t8` 10，`b9_sat_t12` 10；测量 1080.7 s）：

| 模式 | arm | home | projects | project_detail | stage_reports | draft_edit | bug_trend | ≤1.20 |
|---|---|---|---|---|---|---|---|---|
| seq | `baseline` | 133/162 h16 r2.01 | 160/243 h29 r2.31 | 155/211 h33 r2.15 | 210/238 h89 r2.17 | 240/277 h89 r2.42 | 166/196 h34 r2.29 | — |
| seq | `waitress_wn_noauto` | 130/158 ×0.98 h17 r1.93 | 145/217 ×0.89 h28 r2.09 | 158/193 ×0.91 h36 r2.15 | 212/256 ×1.07 h105 r2.08 | 226/294 ×1.06 h104 r2.19 | 149/184 ×0.94 h33 r2.02 | 6/6 |
| seq | `b9_sat_t8` | 129/148 ×0.92 h17 r1.92 | 136/190 ×0.78 h23 r1.97 | 154/187 ×0.89 h36 r2.09 | 212/293 **×1.23** h112 r2.16 | 226/317 ×1.14 h107 r2.24 | 142/166 ×0.84 h32 r1.94 | 5/6 |
| seq | `b9_sat_t12` | 128/150 ×0.93 h17 r1.93 | 135/168 ×0.69 h21 r1.96 | 142/167 ×0.79 h31 r1.95 | 214/250 ×1.05 h100 r2.13 | 228/261 ×0.94 h89 r2.27 | 137/162 ×0.83 h32 r1.86 | 6/6 |
| c4 | `baseline` | 361/423 h34 r5.61 | 386/449 h54 r5.89 | 420/476 h79 r6.15 | 514/574 h205 r5.75 | 549/633 h204 r5.77 | 374/430 h67 r5.37 | — |
| c4 | `waitress_wn_noauto` | 321/395 ×0.93 h35 r4.90 | 347/395 ×0.88 h44 r5.24 | 384/435 ×0.91 h82 r5.45 | 484/552 ×0.96 h215 r4.98 | 531/644 ×1.02 h214 r5.40 | 332/376 ×0.87 h71 r4.59 | 6/6 |
| c4 | `b9_sat_t8` | 360/466 ×1.10 h40 r5.58 | 357/430 ×0.96 h49 r5.35 | 383/466 ×0.98 h85 r5.42 | 497/548 ×0.95 h215 r5.12 | 553/622 ×0.98 h214 r5.52 | 350/390 ×0.91 h68 r4.91 | 6/6 |
| c4 | `b9_sat_t12` | 363/484 ×1.15 h43 r5.57 | 377/446 ×0.99 h55 r5.64 | 392/455 ×0.95 h81 r5.57 | 508/561 ×0.98 h220 r5.32 | 560/629 ×0.99 h221 r5.65 | 358/388 ×0.90 h66 r5.04 | 6/6 |

p95 比值范围：`waitress_wn_noauto` seq 0.89–1.07，c4 0.87–1.02，达标 12/12；`b9_sat_t8` seq 0.78–1.23，c4 0.91–1.10，达标 11/12；`b9_sat_t12` seq 0.69–1.05，c4 0.90–1.15，达标 12/12。进程：所有 arm exit 0，各 1 行 `project_runtime_stopped`；启动→就绪 s `baseline` 5.6，`waitress_wn_noauto` 18.7，`b9_sat_t8` 18.7，`b9_sat_t12` 18.6。

- `b9_sat_t8` 饱和进程：exit 0，保持 1129.0 s；开始时 4 条流状态 [200, 200, 200, 200]，第 5 条流开始/结束时 503/503；活动流 11292 个事件，间隔 p50/p95/max 105.4/108.5/508.3 ms；空闲流心跳间隔 max 2062.1 ms；中途 EOF/错误 0。
- `b9_sat_t12` 饱和进程：exit 0，保持 1129.0 s；开始时 4 条流状态 [200, 200, 200, 200]，第 5 条流开始/结束时 503/503；活动流 11293 个事件，间隔 p50/p95/max 105.3/108.5/317.1 ms；空闲流心跳间隔 max 2036.2 ms；中途 EOF/错误 0。

- 未饱和对照 `waitress_wn_noauto` 12/12（seq 0.89–1.07×，c4 0.87–1.02×），与 Phase 2 一致。
- 饱和、threads 12：12/12（seq 0.69–1.05×，c4 0.90–1.15×），(c) **PASS**。
- 饱和、threads 8：11/12，(c) **FAIL**（1 个单元格）。
  - 不达标的单元格是 seq stage_reports 1.23×：p95 293 vs 238 ms，p50 212 vs 210 ms 基本不变；c4 为 0.91–1.10×。
  - seq 只用 1 条连接，4 条流占 4 个线程后仍有 4 个空闲线程，不是线程耗尽。同一单元格的对照为 1.07×，更像尾部波动，但没有证明，按门限记为 FAIL。
- 饱和时 c4 home 为 1.10–1.15×（对照 0.93×）：流对页面有可见但在门限内的影响，原因未分析。
- 本次运行的基线比 Phase 2 慢且更离散（seq 基线 p95 162–277 ms，Phase 2 为 142–236 ms），说明共享机器的负载不同；比值只在同一次运行内比较。
- 签核补测 M2（§3.10，旧配置）用 M 参数在同一次饱和中测了 (a)(b)(c)：(a) 第 5 条流探测 209/209 得到 503 + `Retry-After`；(c) 饱和 arm 12/12；(b) 2092 个短 `/ai` 请求全部 200，但 2 个 ≥ 100 ms（212.48 ms、157.89 ms），按签核门限（全部 < 100 ms）**FAIL**，原因无法判定。
- 新配置终测 M2（§3.11）在同一次饱和中再测 (a)(b)(c)，全部 PASS：(a) 194/194 立即 503 + `Retry-After: 2`；(b) 1944 个短请求（972 个 `/ai/health` 经 loop，972 个资产直出）全部 200，max 70.78 ms；(c) `rec_t14_sat` 12/12（seq 0.899–1.093×，c4 0.857–1.015×）。

### 3.10 签核补测（旧配置；2026-11-11；M1–M5 与上一轮补测 (a)；M6 当时未运行，新配置终测见 §3.11）

时间与证据：
- 上一轮补测 (a) 在 11:06 运行；签核补测的测量在 11:13–12:28 进行，M2 判定在 12:32 完成。证据在 `logs\s0b\rec\`；上一轮补测 (a) 的证据在 `logs\s0b\retest-t12\`。
- M 证据 JSON 都记录了所用脚本的 SHA-256：字段为 `script_sha256`，`b6b9-rec.json` 中为 `config.script_sha256`。宿主 `s0b_host.py` 的 hash 是 `f4aa2dcc34860bc63c415b985973d391bb096b11ef27878cc135a1f02b273e3d`。
- 例外 1：`a-revbind.json` 没有记录 hash，它用的是 M1 改动之前的宿主。
- 例外 2：`m4-b5s.json` 中 `s0b_sig2.py` 的 hash 是加入 `--target host` 之前的版本。M4 先于 M1 运行，只用这个脚本发送 CTRL_C。

**配置**

M1–M5 统一使用改后的宿主和 M 参数：`--server waitress --static wn-noauto --bridge custom --threads 12 --ai-limit-mode split --ai-stream-limit 4 --ai-short-limit 2 --finish flush`；需要 CTRL_C 的用例另加 `--enable-ctrl-c`。M 参数是签核时的推荐配置，即旧配置。owner 之后就 `/ai` 准入做出决定，新配置与旧配置有三项差别：

| 项 | M 参数（旧配置，M1–M5 实测） | owner 新决定（§3.11 终测已整体运行） |
|---|---|---|
| 线程数 | 12 | 14 |
| 短请求上限 | 2 | 4（流上限两者都是 4，超限立即 503 + `Retry-After`，不排队） |
| UI 资产（例如 `asset.js`） | 计入短请求名额，经过 loop | 认证之后由适配器直接返回，不计名额，也不进 loop |

- 认证先于准入：spike 宿主本来就是这样（§2“AI 准入”）。未认证请求在 WSGI 线程上得到 401，不占名额，与新决定一致。
- Host 校验：旧配置阶段的宿主在 `/ai/*` 分派中不做 Host 校验，只有 Django 路径会经过 Django 的 `ALLOWED_HOSTS`。终测宿主已实现（非法 Host 400，先于认证，§3.11）。
- 旧配置下没有重跑；新配置的 M2 (b) 在终测中 PASS（§3.11）。旧配置 M2 中两个 ≥ 100 ms 的短请求，一个是 `/ai/health`，一个是 `asset.js`（见下文诊断）。

**宿主改动**

以下改动在 M1–M5 之前完成，M1–M5 都使用改后的宿主。前 4 条对应签核 M1 的宿主改动 1–4，停止预算对应 M4 的预算要求。
- 停止过程中再收到 SIGINT 或 CTRL_BREAK 时，执行 `os._exit(130)`。改动前只记录 `stop.trigger.repeat`。
- 主线程上的所有等待都切片到 ≤ 0.5 s（`wait_sliced`、`join_sliced`）。
- waitress `run()` 移到非 daemon 线程 `serve-http`。主线程启动它之后，只做 0.5 s 的切片等待并处理信号。`asyncore_loop_timeout` 保持 1 s，它只影响 `serve-http` 线程。
- `s0b_sig2.py driver` 增加 `--target host` 模式：以组合宿主为目标，按 QPC 时钟在宿主 `stop.requested` + 1.0 s 时发出第 2 个事件，并由 `Popen.wait()` 线程记录退出时间。
- 停止总预算为 10 s，见 `s0b_host.py` 中的 `STOP_BUDGET`。t0 指收到停止请求的时刻。

| 段 | 预算 | 内容 |
|---|---|---|
| 停止受理 | 0.5 s | 经 `pull_trigger` 关闭监听 dispatcher |
| 终止宽限 | 2.0 s | 设置宿主关闭事件；到 t0 + 2 s 时取消仍未结束的桥 task |
| 排空 | 截止 t0 + 3.0 s | 桥与 Django 的在途请求降为 0 |
| flush | 截止 t0 + 6.5 s | waitress channel 的输出缓冲写完；到期后放弃未写出的数据 |
| server 关闭 | 0.5 s | `server.close()`：关闭剩余 channel 与 trigger，`run()` 返回 |
| join `serve-http` | 0.5 s | — |
| waitress 工作线程 | 0.5 s | `task_dispatcher.shutdown(cancel_pending=True, timeout=0.5)` |
| project runtime | 0.5 s | `project_runs.stop(...)`；`project_serve` 用的是 `runtime.stop(620)` |
| AI runtime | 1.0 s | 在 loop 上退出 AI Base lifespan，取消剩余 task，关闭 executor 与 loop，join loop 线程 |
| 合计 | 10 s | 最坏 6.5 + 4 × 0.5 + 1.0 = 9.5 s；看门狗（daemon 线程）在 t0 + 10 s 执行 `os._exit(3)` |

- 改动前的宿主：排空截止 t0 + 10 s；flush 至少 2 s，截止为 `max(t0 + 10, now + 2)`；dispatcher 收尾 5 s；loop 收尾最多 5 s；没有总上界；看门狗在 drain + 25 s 触发。
- 实测：宿主记录的 stop → `process.exit` 为 0.007–6.553 s（M4、M5）。`process.exit` 之后，进程还要 0.96–1.16 s 才实际退出（M4 5/5）。这段时间包括 `sys.exit(0)` 之后的解释器收尾和驱动的观测；这段不受看门狗约束，也不在 10 s 预算内。M4 中触发到进程退出最长为 7.894 s（不读用例）。步骤 A（§3.11）已把这段拆开：约 0.85–0.92 s 花在 atexit 回调之后的模块清理、GC 与进程结束；终测宿主改为显式退出，`os._exit` 到进程退出为 43.8–60.6 ms。

**M1：第二个信号（B1）**

证据：`rec\m1-sig2-host.json`、`rec\m1-*-host.log`、`rec\m1-sig2-driver.log`。
- 负载为 1 条活动流、1 条空闲流和 1 个慢读者。第 1 个 CTRL_BREAK 或 CTRL_C 发出后 0.029–0.483 s，宿主记录 `stop.requested`。第 2 个同类事件在 `stop.requested` + 1.0 s 时发出。
- 排空阶段：活动流不支持终止事件，第 2 个信号到达时宿主仍处于 `shutdown.terminate_streams`。
- flush 阶段：活动流支持终止事件，已经结束；慢读者使宿主停在 `shutdown.server_finish.begin`。8 次运行的阶段都符合预期。

| 阶段 × 事件（各 2 次） | 端口 | 第 2 个信号 → 处理器 s | 第 2 个信号 → 进程退出 s | 退出码 | stop 行 |
|---|---|---|---|---|---|
| 排空 × CTRL_BREAK | 8847/8848 | 0.008/0.017 | 0.061/0.068 | 130/130 | 0/0 |
| 排空 × CTRL_C | 8849/8851 | 0.005/0.003 | 0.062/0.064 | 130/130 | 0/0 |
| flush × CTRL_BREAK | 8852/8853 | 0.011/0.021 | 0.065/0.083 | 130/130 | 0/0 |
| flush × CTRL_C | 8854/8855 | 0.006/0.005 | 0.061/0.084 | 130/130 | 0/0 |

- 判定条件为第 2 个信号到退出 ≤ 1.0 s 且退出码非 0：8/8 **PASS**。
- 强制退出时没有输出 `project_runtime_stopped`。排空阶段的活动流在客户端表现为 `ConnectionResetError(10054)`；慢读者没有收到终止事件。

**M4：带流停止（B5 加强）**

证据：`rec\m4-b5s.json`、`rec\rec-flush-*`、`rec\rec-slow-flush*`、`rec\rec-noread-flush*`。
- 用例都使用 `flush` 收尾，每个用例有 1 条活动流（100 ms）和 1 条空闲流。
- 慢读与不读用例中，活动流的终止事件带 8 MB 填充；客户端在触发时停止读取，分别停 3 s 与 16 s（`SO_RCVBUF` 32 KiB）。
- 表中时间相对触发时刻。

| 用例 | 端口 | 活动流：终止事件 / EOF s | 空闲流：终止事件 / EOF s | flush | stop → `process.exit` s | 触发 → 进程退出 s |
|---|---|---|---|---|---|---|
| stop-file | 8841 | 0.055 / 0.056 | 0.055 / 0.056 | 无积压 | 0.09 | 1.116 |
| CTRL_BREAK | 8842 | 0.18 / 0.182 | 0.18 / 0.182 | 无积压 | 0.061 | 1.223 |
| CTRL_C | 8843 | 0.249 / 0.25 | 0.249 / 0.25 | 无积压 | 0.057 | 1.304 |
| 慢读（暂停 3 s） | 8844 | 开始 0.097，完整 3.128 / 3.133（共 8,000,586 B） | 0.09 / 0.091 | 等待 3.056 s，7,738,006 B → 0 | 3.113 | 4.114 |
| 不读（暂停 16 s） | 8846 | 只收到 197,192 B，没有完整终止事件，也没有 chunked 结束块 | 0.23 / 0.23 | t0 + 6.439 s 到期，7,803,542 B 未写出 | 6.553 | 7.894 |

- 5/5 在 10 s 内 exit 0，每个用例恰好 1 行 `project_runtime_stopped`，启动顺序与停止顺序都正确。
- 3 个正常读取用例中，两条流的终止事件都在停止受理结束后 0.9–3.9 ms 完整到达客户端（`terminal_end_after_stop_accepting_end_ms`）。慢读用例的活动流在恢复读取后收到完整的终止事件（停止受理结束后 3088.2 ms），然后才 EOF。所以停止受理没有停掉写出已产生数据的 I/O 路径。
- 触发后 0.303–0.537 s 发起的新连接都得到 `ConnectTimeout`。
- 不读用例：到期时丢弃未写出的数据，这是预算内的设计行为。签核的“正常读取的客户端在连接关闭前收到终止事件”不适用于这个用例。
- 判定：**PASS**。

**M5：流名额归还（Metrics 追加）**

证据：`rec\m5-slots.json`，端口 8858，`s0b_m5.py --port 8858 --rounds 5`。
- 客户端中止，共 5 轮。每轮先打开 4 条流（都是 200），第 5 条在 0.6–1.0 ms 内得到 503 + `Retry-After: 2`。然后中止这 4 条流，新流 4/4 在中止后 0.104–0.167 s 内被接受。门限是心跳间隔 + 1 s，即 3 s。
- 服务端异常结束，共 2 轮。每轮 4 条流由服务端异常结束：2 条 `fail_after=3`（200，3 个事件后断开，没有 chunked 结束块），2 条 `fail_after=0`（500）。之后新流 4/4 在 0.002–0.028 s 内被接受，第 5 条仍然 503。
- 短请求池：2 个慢短请求（`asset.js?delay_ms=3000`）占满时，第 3 个在 0.7 ms 内得到 503 + `Retry-After`；中止后 0.105 s，health 恢复 200。
- 结束状态：准入在途 0/0（峰值：流 4、短请求 2）。桥只剩状态探测本身这 1 个在途请求，loop 上的 task 回到基线（`Task-1`、`s0-task-run-worker`）。
- 停止：stop-file 触发后 1.067 s exit 0，1 行 stop，0 个遗留 task。
- 13/13 项检查通过，**PASS**。第 1 次运行因驱动的检查逻辑错误而失败（不是宿主问题），证据保留为 `m5-run1-checkbug-*`。

**M3：B7 浏览器子集（threads 12）**

11/11 passed，逐个测试结果与 stock 一致，**PASS**。详见 §3.8。

**M2：B6 与 B9 (a)(b)(c) 在同一次饱和中**

证据：`rec\b6b9-rec.json`、`rec\m2-verdict.json`、`rec\rec-rec_t12_sat-hold.json`、`rec\rec-*-server.log`。
- 运行参数：`s0b_perf.py run --arms baseline,rec_t12,rec_t12_sat,waitress_wn_noauto --blocks 4 --per-block 40 --warmup 10 --modes seq,c4 --hold-short-interval 1 --hold-probe-interval 5`。
- 端口：`baseline` 8840，`rec_t12` 8856，`rec_t12_sat` 8857，`waitress_wn_noauto` 8845。测量用时 1001.6 s。
- `rec_t12` 与 `rec_t12_sat` 都用 M 参数。`rec_t12_sat` 由 hold 进程在测量开始前用 1 条活动 SSE（100 ms）和 3 条空闲 NDJSON 占满流上限，并保持到测量结束。hold 期间每 1 s 依次发 1 次 `/ai/health` 和 1 次 `/ai/s0b/asset.js`，每次新建连接；每 5 s 探测一次第 5 条流。
- `waitress_wn_noauto`（threads 8、无准入、`close`）用作对照。

| 模式 | arm | home | projects | project_detail | stage_reports | draft_edit | bug_trend |
|---|---|---|---|---|---|---|---|
| seq | `baseline` | 130/153 h15 r1.97 | 141/164 h22 r2.07 | 147/172 h29 r2.03 | 217/249 h95 r2.22 | 206/306 h97 r2.16 | 135/157 h28 r1.85 |
| seq | `rec_t12` | 118/139 ×0.91 h15 r1.76 | 133/155 ×0.95 h23 r1.92 | 138/163 ×0.95 h31 r1.89 | 195/227 ×0.91 h87 r2.00 | 196/283 ×0.92 h97 r1.95 | 121/143 ×0.91 h28 r1.65 |
| seq | `rec_t12_sat` | 119/145 ×0.95 h15 r1.76 | 132/159 ×0.97 h20 r1.90 | 138/186 ×1.08 h34 r1.89 | 194/224 ×0.90 h88 r1.96 | 195/247 ×0.81 h85 r1.94 | 118/143 ×0.91 h27 r1.61 |
| seq | `waitress_wn_noauto` | 119/142 ×0.93 h15 r1.76 | 125/149 ×0.91 h20 r1.82 | 132/162 ×0.94 h29 r1.81 | 182/224 ×0.90 h85 r1.86 | 202/255 ×0.83 h88 r2.01 | 120/140 ×0.89 h26 r1.63 |
| c4 | `baseline` | 321/366 h31 r5.00 | 329/383 h44 r4.98 | 355/403 h65 r5.15 | 519/745 h275 r5.88 | 619/724 h220 r6.62 | 389/487 h78 r5.58 |
| c4 | `rec_t12` | 288/329 ×0.90 h34 r4.44 | 301/360 ×0.94 h43 r4.55 | 335/391 ×0.97 h66 r4.79 | 501/741 ×0.99 h249 r5.13 | 579/774 ×1.07 h252 r5.94 | 332/410 ×0.84 h78 r4.65 |
| c4 | `rec_t12_sat` | 302/389 ×1.06 h32 r4.64 | 311/361 ×0.94 h44 r4.67 | 355/414 ×1.03 h70 r5.00 | 483/575 ×0.77 h220 r4.99 | 563/746 ×1.03 h251 r5.96 | 333/406 ×0.83 h73 r4.67 |
| c4 | `waitress_wn_noauto` | 304/335 ×0.92 h38 r4.66 | 311/352 ×0.92 h47 r4.60 | 350/400 ×0.99 h66 r5.01 | 483/618 ×0.83 h242 r4.88 | 566/690 ×0.95 h235 r5.75 | 355/464 ×0.95 h80 r4.94 |

表中单元格为页面 p50/p95 ms（含引用的静态资源）；×为 p95 比值（相对同一次运行的 `baseline`）；h 为 HTML 单独的 p95；r 为每个请求的 p50 ms。

- p95 比值范围：`rec_t12` seq 0.908–0.946、c4 0.843–1.069，12/12；`rec_t12_sat` seq 0.807–1.081、c4 0.772–1.065，12/12；`waitress_wn_noauto` seq 0.833–0.938、c4 0.829–0.992，12/12。两个 rec arm 无凭据请求静态文件都得到 401。
- 进程：4 个 arm 的进程都 exit 0，各输出 1 行 `project_runtime_stopped`；hold 进程 exit 0。
- hold：保持 1046.1 s；开始时 4 条流都是 200。活动流 10,460 个事件，间隔 p50/p95/max 为 104.8/108.6/286.4 ms；空闲流心跳间隔 max 2022.5 ms；中途没有 EOF 或错误。
- (a) 第 5 条流的探测 209/209 立即得到 503 + `Retry-After: 2`，p50/p95/p99/max 为 2.45/23.03/24.31/29.0 ms；开始与结束时的探测都是 503。
- (b) 短请求 2092 个，全部 200，p50/p95/p99/max 为 4.9/26.47/29.59/212.48 ms，但其中 2 个 ≥ 100 ms：`/ai/health` 212.48 ms、`/ai/s0b/asset.js` 157.89 ms。
- (c) `rec_t12_sat` 12/12。
- 判定：(a)(c) PASS；(b) 不满足签核门限“全部 < 100 ms”，M2 **FAIL**。按规则停止，没有运行 M6。（旧配置；FAIL 记录保留。新配置终测 M2 PASS，§3.11）

**M2 离群短请求诊断（只用已有证据，没有新的测量；`s0b_m2_outliers.py` → `rec\m2-outliers.json`）**

方法：
- hold 进程记录每个短请求的开始时刻与耗时，每次都新建回环连接，所以耗时包含连接建立。服务端访问日志只有写出时刻，没有单个请求的耗时。
- 用服务端日志中同时带 wall 与 mono 时钟的 JSON 行（每个宿主 33–47 条），把访问日志时间换算到 monotonic 时钟：偏移离散 2.4–2.8 ms，用流开始时刻核对，误差为 −1.5 ms。
- 据此拆出两段：pre = 访问日志写出时刻 − 请求开始（到 `start_response` 为止）；post = 下一个请求开始 − 访问日志写出时刻（正文写出、客户端读取与关闭）。
- 正常短请求（< 50 ms）的 pre p50/p99/max：`/ai/health` 为 4.4/21.2/40.1 ms，`asset.js` 为 1.9/26.6/34.4 ms；`/ai/health` 的 post 为 2.5/5.1/18.8 ms。
- 局限：流事件时刻是按发送计划推算的，没有逐事件日志；perf 驱动没有记录逐个页面样本，只有块均值和单元格汇总；GC 与 OS 调度没有埋点。

hold 期间的短请求统计（hold 进程测得，n=2092）：
- 全部：p50/p95/p99/max 4.9/26.47/29.59/212.48 ms。
- `/ai/health`：n=1046，5.68/20.19/31.12/212.48 ms。
- `/ai/s0b/asset.js`：n=1046，3.19/27.17/29.07/157.89 ms。
- ≥ 50 ms 的有 6 个，≥ 100 ms 的有 2 个。

按测量块统计：

| 测量块 | n | p50 ms | max ms | ≥ 100 ms 的个数 |
|---|---|---|---|---|
| c4/`rec_t12` | 206 | — | 157.89 | 1 |
| c4/`rec_t12_sat` | 186 | 7.8 | 212.48 | 1 |
| seq/`baseline` | 328 | — | 79.09 | 0 |
| 块间 | 90 | — | 42.18 | 0 |
| 其余块 | — | — | ≤ 34.65 | 0 |

hold 顺序发送短请求，同一时刻最多 1 个，所以短请求名额（2 个）没有占满，准入不是原因。

| | A：`/ai/health` 212.48 ms | B：`/ai/s0b/asset.js` 157.89 ms |
|---|---|---|
| 时刻 | 12:23:37.293，hold 就绪后 796.1 s | 12:24:59.354，hold 就绪后 878.1 s |
| 当时在测的块（块号从 0 起） | c4/project_detail，`rec_t12_sat` 块 3，即 8857 本身（块长 3.7 s，A 在块内 0.9 s） | c4/stage_reports，`rec_t12` 块 3，在另一进程 8856 上（块长 10.2 s，块内 3.6 s）；8857 上只有 hold 流量 |
| 拆分 | pre 3.6 ms，post 209.8 ms：响应头很快写出，正文写出到客户端读完用了约 210 ms | pre 143.6 ms：写访问日志之前就已经慢了 |
| 与流事件的关系（推算） | 活动流上次发送在 79.9 ms 前，A 的窗口内有 2 次发送；空闲流心跳在 164.9–167.9 ms 前 | 活动流上次发送在 40.9 ms 前，窗口内有 2 次；空闲流心跳在 225.9–228.9 ms 前 |
| 前后约 1 s 的短请求与探测 | −0.99 s health 18.24 ms；−0.97 s asset 3.0 ms、探测 23.8 ms；+0.21 s asset 10.01 ms；+1.01 s health 16.5 ms | −0.03 s health 31.12 ms；+0.96 s health 4.09 ms、asset 2.45 ms；之后 +1.94 s health 67.87 ms（pre 66.3），+2.01 s asset 87.57 ms（pre 86.4） |
| 同一时段的页面请求（没有逐个样本） | 8857 在 ±1 s 内有 1247 行访问日志（21 个 HTML、1221 个静态、4 个短请求、1 个探测）。块内访问日志间隔 p50/p99 为 1/9 ms；唯一的大间隔 213 ms 正好从 A 的访问日志开始，次大的只有 24 ms。块均值 373.6 ms（其他块 346.1–373.7 ms）；该单元格 max 593.04 ms（其他 arm 421.9–457.0 ms） | 8856 从 422811.73 s 到 422813.79 s 共 2060 ms 没有写访问日志，覆盖了 B；之后又有 527 ms 与 1043 ms 的间隔。该块均值 1023.1 ms（其他块 447.5–528.0 ms）；单元格 max 4544.92 ms（其他 arm 652–797 ms） |
| 判断 | 8857 在 c4 负载下约 213 ms 没有写任何访问日志，表现为整个进程停顿。线程没有耗尽：12 个线程，最多 4 个页面连接 + 4 条流 + 1 个短请求。停顿来源（GC、GIL、Windows 调度或其他）没有埋点，**无法判定** | B 在 8857 上变慢时，正在测量的另一进程 8856 也在停顿。8857 当时只有 hold 流量，所以 B 与 8857 上的页面并发无关，是两个进程同时变慢（整机层面）；来源**无法判定** |

其他 ≥ 50 ms 的短请求：
- 79.09 ms（12:17:38.465，pre 77.2 ms）：seq/draft_edit，`baseline` 块 0。当时正在测量的基线进程 8840 与 AI 无关，也停顿了：12:17:35–38 每秒只写出 64/0/0/3 行访问日志；该单元格 max 4864.04 ms；块均值 388.9 ms，其他块为 192.8–214.0 ms。
- 74.32 ms：c4/draft_edit，`rec_t12_sat` 块 1；pre 33.3 ms，post 42.6 ms。
- 67.87 ms 与 87.57 ms：在 B 之后约 2 s，两个请求的时间窗都落在 8856 的 527 ms 访问日志间隔内。

访问日志间隔（每个 arm/模式 24 块；表中为 ≥ 100 ms 与 ≥ 200 ms 的间隔数，括号内为最大值）：

| arm | seq | c4 |
|---|---|---|
| `rec_t12_sat` | 2/1（219 ms） | 27/1（213 ms） |
| `rec_t12` | 4/1（246 ms） | 45/3（2060 ms） |
| `waitress_wn_noauto` | 4/1（210 ms） | 46/0（187 ms） |

≥ 100 ms 的间隔在三个 waitress arm 中都出现，包括没有 AI 负载的 `waitress_wn_noauto`。c4 中 HTML 渲染本身也会造成这种间隔，所以这只是旁证。

结论：两个离群值都与进程级或跨进程的停顿同时发生，与准入、线程耗尽或流事件没有可见关联。现有证据不足以把停顿归因于 GC、静态资源或 Windows 调度，**无法判定**。

**上一轮补测 (a)：反向绑定**

证据：`retest-t12\a-revbind.json`、`retest-t12\a-revbind-server.log`；端口 8850；11:06 运行。
- 宿主：M 参数加 `--state-lock --pid-marker`，宿主版本为 M1 改动之前。宿主先以 127.0.0.1 + `SO_EXCLUSIVEADDRUSE` 预绑定，并正常服务。
- 另一个独立进程尝试绑定同一端口，每种方式 3 次：

| 方式 | 结果（3 次） |
|---|---|
| 127.0.0.1 + `SO_REUSEADDR` | 失败，10013 ×3 |
| 127.0.0.1，不设选项 | 失败，10048 ×3 |
| 127.0.0.1 + `SO_EXCLUSIVEADDRUSE` | 失败，10048 ×3 |
| 0.0.0.0 + `SO_REUSEADDR`（只 bind，不 listen，立即关闭） | 成功 ×3 |

- 请求：开始前、每次尝试期间与之后、结束时各发 20 个请求，`/ai/health` 与 `/s0/django/thread/` 交替，带合法 Host 和凭据，共 520 个。全部 200，`X-S0b-Pid` 都是宿主进程 51956。
- 宿主最后 exit 0，输出 1 行 `project_runtime_stopped`。
- 结论：正在服务的地址与端口独占；通配绑定按 Windows 文档可成功，截不走回环连接。
- `a-revbind.json` 中的 `verdict=false` 是按当时的期望（通配绑定应失败）计算的。按 owner 更正后的 M6 口径，这次数据中 127.0.0.1 上三种方式都失败，请求全部 200 且由宿主应答。但这次运行不是 M6：宿主是 M1 改动之前的版本，也没有记录脚本 hash。

**M6**

旧配置阶段没有运行：M2 的 (b) FAIL 后，按“FAIL 即停”规则停止；之后 owner 更正了 M6 的期望，并要求 M6 暂停。终测中在最终宿主上按新配置运行，PASS（§3.11）。

### 3.11 新配置终测（2026-11-11；最终宿主上的 M1–M6 全套，全部 PASS；推荐组合已作为整体运行）

时间与证据：
- 16:14 收到请求。步骤 A 16:29–16:30（旧宿主）。宿主改完后，17:00:31 冻结 `s0proj\` 下全部 51 个 `.py`（清单 `final\scripts-sha256.json`，冻结前副本 `final\pre-scripts\`）。之后依次运行：冒烟 17:00:49；M1 17:01–17:03；M4 17:03–17:04；M5 17:04:50；M6 17:05:22–17:05:37；M2 17:06:16–17:22:56；M3 17:24:11–17:31。M2、M3 期间写有协调标记 `logs\s0b\HEAVY_RUN_ACTIVE`（17:05:53 写入，17:31:13 删除）。
- 证据在 `logs\s0b\final\`。每个证据 JSON 都在 `script_sha256` 中记录所用脚本（含 `s0b_sig2.py`、`s0b_b5s.py` 等驱动）的最终版本 hash。最终宿主 `s0b_host.py` 的 SHA-256 是 `e6e1707d6476ee0c38b544272ec3c28c986ccbb1f6d1646c82c52d8b05b8dc5b`。
- `s0b_final_shacheck.py` 的核对结果（`final\sha-verify.json`，PASS）：19 个终测 JSON 记录的 hash 都与冻结清单一致，宿主都是 `e6e1707d…`；冻结后磁盘上的脚本没有变化。例外是 `stepA-tail.json`，按设计用旧宿主 `f4aa2dcc…`。冻结后只新增两个只读分析脚本，见 `sha-verify.json` 的 `post_freeze_scripts`。

**owner 决定（2026-11-11）**

1. M2 (b) FAIL：保留 FAIL 记录，旧配置证据（`rec\` 下全部文件）不删除、不覆盖；用新配置重跑，判据不变。
2. 退出尾段约 1 s，采用显式退出：
   - 停止顺序的最后依次执行 `django.db.connections.close_all()`、`logging.shutdown()`、`sys.stdout.flush()`、`sys.stderr.flush()`，然后 `os._exit(code)`。
   - 退出码：干净结束 0；清理失败或看门狗到期 3；第二个信号 130。看门狗一直保持到 `os._exit` 那一刻。
   - 10 s 预算按进程实际退出计算。
   - 上游 SDK 新增契约：`start_blocking` 退出时，runtime 已 flush 并关闭全部持久资源，不依赖 atexit 或解释器收尾（R24）。
3. 执行中的 project run，沿用 design 规则（只记录，不测试）：
   - 10 s 预算不含 `project_runs.stop(620)` 对执行中 run 的等待；`serve` 的进程内看门狗为 660 s，Docker 用 `--stop-timeout 690`。
   - 启动脚本写入 stop-file 后，等待 ≥ 15 s 仍未退出，就按 PID 强制结束；中断的运行由下次启动时的恢复流程标记。
   - spike 中没有执行中的 run，预算中 project runtime 的 0.5 s 段代表这种情况。spike 的看门狗 t0 + 10 s 只是测量护栏，不是 `serve` 的 660 s 看门狗。

**配置**

- 参数：`--server waitress --static wn-noauto --bridge custom --threads 14 --ai-limit-mode split --ai-stream-limit 4 --ai-short-limit 4 --finish flush`，需要 CTRL_C 的用例另加 `--enable-ctrl-c`。
- 14 个线程 = 流 4 + 短请求 4 + 页面 4（c4）+ 余量 2。准入拒绝返回 503 + `Retry-After: 2`，不排队。
- waitress：宿主以 127.0.0.1 + `SO_EXCLUSIVEADDRUSE` 预绑定，调用 `create_server(app, sockets=[sock], threads=14, channel_request_lookahead=1)`；`run()` 在 `serve-http` 线程上，`asyncore_loop_timeout` 保持 1 s。

**步骤 A：旧尾段拆分**

证据：`final\stepA-tail.json`、`final\stepA-run{1..5}-server.log`。

方法：
- 宿主与触发：用当时的宿主（`f4aa2dcc…`，旧配置），stop-file 触发，不开流，端口 8840，跑 5 次，全部 exit 0。
- 宿主侧记时：包装器 `s0b_tailwrap.py` 经 `runpy` 运行未修改的宿主。
  - 包装器启动时先注册一个 atexit 回调。它最先注册，所以最后执行，记 t2。
  - 宿主调用 `sys.exit` 时（t1），包装器再注册一个 `threading._register_atexit` 回调和一个 atexit 回调。后者最后注册，所以最先执行，记 t3。
- 驱动侧记时：驱动 `s0b_tailsplit.py` 在独立线程中用 `WaitForSingleObject(INFINITE)` 阻塞等待解释器进程句柄（不轮询），记录句柄被 signal 的时刻 t4；venv 启动器另用 `Popen.wait` 观测。
- 时钟：QPC（3.13 的 `time.monotonic` 与 `time.perf_counter` 在 Windows 上都基于 QPC，跨进程可比），同时记录 wall clock。

| 段 | min–max ms | p50 ms |
|---|---|---|
| 触发 → `stop.requested`（stop-file 每 0.2 s 轮询） | 17.3–167.7 | 97.7 |
| `stop.requested` → `process.exit` 标记（无流的停止流程） | 5.8–6.7 | 6.5 |
| `process.exit` 标记 → t1（`sys.exit` 前） | 0.089–0.244 | 0.191 |
| t1 → t3：`threading._shutdown`（join 非 daemon 线程） | 0.124–0.188 | 0.174 |
| t3 → t2：各 atexit 回调 | 0.171–0.273 | 0.235 |
| t2 → t4：模块清理、GC 与进程结束 | 848.6–915.1 | 884.2 |
| t4 → 启动器退出 | 6.1–7.5 | 6.4 |
| t1 → t4 合计 | 848.9–915.5 | 884.6 |
| 触发 → 启动器退出 | 878.1–1065.1 | 1010.9 |

- 驱动观测误差：校准用 10 个只打印 `time.monotonic()` 后立即 `os._exit` 的子进程。从子进程打印的时刻到驱动观测到句柄，解释器为 5.2–8.0 ms（p50 6.5），启动器为 10.9–16.9 ms（p50 13.5）。
- 结论：旧尾段几乎全部在最后一个 atexit 回调之后（849–915 ms），即解释器的模块清理、GC 与进程结束；join 非 daemon 线程与 atexit 回调合计不到 0.5 ms。现有埋点不能再细分 t2 → t4。
- 推断：终测宿主中 `os._exit` 到进程退出为 43.8–60.6 ms（M4）。据此，旧尾段中约 0.8 s 是解释器收尾，显式退出可以跳过；但两组数据来自不同宿主，只能作为推断。

**宿主改动（相对 §3.10 的 M 宿主）**

1. 显式退出 `explicit_exit(code)`：`main()` 的每条退出路径都经过它。
   - 顺序：[`--diag-out` 转储] → `close_all()` → `logging.shutdown()` → 输出 `process.exit.final` 行 → stdout/stderr flush → `os._exit(code)`。
   - 清理失败时把 0 改为 3；转储失败只记录，不改退出码。
   - `close_all()` 只关闭调用线程的连接（Django 连接是线程局部的）；请求线程在 `request_finished` 时关闭自己的连接（`CONN_MAX_AGE=0`）。终测中 `db_open_on_main` 都是 0，`errors` 都为空。
2. `/ai/*` 固定顺序：
   1. 停止中，所有路径 503。
   2. Host 校验：Django `HttpRequest.get_host()` / `ALLOWED_HOSTS`，非法 400。
   3. 请求完整性：超过 16 MiB 413（占位上限）。宿主也检查 `Content-Length` 是否为数字（非数字 400），但这一分支在 waitress 下走不到：waitress 解析器在调用应用之前就返回 400。413 由宿主返回，但 waitress 此时已读完并缓冲整个请求体（> 512 KiB 落临时文件），所以不限制资源（复签 N1）。
   4. `/ai` → 308（不需要认证，也不调度 loop 工作）。
   5. BasicAuth：401，不占名额，不调度 loop 工作。
   6. 资产直出。
   7. AI runtime 停止中 503。
   8. 分离准入：超限 503 JSON `{"error":"ai_busy",…}` + `Retry-After: 2`。测试控制路由 `/s0b/state`、`/s0b/loop` 免准入。
   9. 桥：`SCRIPT_NAME += /ai`；名额由包装迭代器在 `close()` 时归还。
3. 资产直出：
   - 构建时固定清单：`/ai/s0b/asset.js`、`/ai/s0b/assets/app.css`。资产前缀下清单外的路径返回 404。
   - 只接受 GET/HEAD，其他方法返回 405 + `Allow: GET, HEAD`。
   - 响应头：`Cache-Control: private, max-age=31536000, immutable`、ETag（内容 SHA-256 前 32 位十六进制）、`X-Content-Type-Options: nosniff`；`If-None-Match` 命中时返回 304。
   - 在认证之后由 WSGI 线程直接返回，不进 loop，不计名额。B7 的 11 个测试不请求任何 `/ai` 资产。
4. 诊断 `--diag-out`（只用于归因，不影响判据）：
   - `gc.callbacks`：记录所有 gen2，以及所有 ≥ 1 ms 的回收。
   - 10 ms ticker 线程：记录 > 50 ms 的停顿。
   - 每个请求从进入分派到 `start_response` 的耗时。
   - 以上在显式退出时转储。
5. 停止预算在 9.5 s 之后增加两段：显式退出 0.2 s、进程结束 0.3 s，按进程实际退出合计 10 s（见本节末的表）。
6. 驱动：
   - `s0b_sig2.py` 在第 1 个信号发出后 1.0 s（驱动时钟）发出第 2 个信号。
   - M1、M4 与冒烟的驱动在独立线程中阻塞等待进程句柄，分别记录解释器与启动器的退出时刻。

**冒烟（`final\stepB-smoke.json`，端口 8841，19 项全部 PASS）**

- 非法 Host 返回 400（带或不带凭据都是）。无凭据请求返回 401，短请求池占满时也是 401。`/ai` 返回 308，`/ai/health` 返回 200。
- 资产：
  - 无凭据 401。
  - 200，带上述三个头；`If-None-Match` 304；HEAD 200；POST 405；`app.css` 200；清单外路径 404。
- 请求完整性：`Content-Length` 非数字时 400，由 waitress 解析器在调用应用之前返回（67 B 的 waitress 错误页），宿主这一分支在 waitress 下走不到；超过 16 MiB 时 413，由宿主返回，但 waitress 此时已读完并缓冲整个请求体（客户端测得 170.16 ms）。
- 准入：短请求池占满（4 个）后，第 5 个短请求得到 503 + `Retry-After: 2`；此时资产仍为 200（1.48 ms）。
- 停止：`stop.requested` 到进程退出 0.051 s；`os._exit` 调用到进程退出 42.14 ms；ticker 最大间隔 18.54 ms。

**M1–M6 结果总表**

| 项 | 判据（签核第二节，按终测要求更正） | 结果 | 证据（`final\`） |
|---|---|---|---|
| M1 第二个信号 | 第 2 个信号在第 1 个之后 1.0 s 发出；从第 2 个信号到进程实际退出 ≤ 1.0 s，退出码 130 | **PASS** 8/8：0.073–0.502 s（启动器 0.081–0.508 s），130，stop 行 0 | `m1-sig2-host.json` `m1-*-host.log` |
| M2 B6 + B9 同一次饱和 | 两个 rec arm 12/12，无凭据请求静态文件得到 401；hold 期间短请求与资产全部 200 且 < 100 ms；新流探测全部 503 + `Retry-After` | **PASS**：`rec_t14` 12/12、`rec_t14_sat` 12/12、401；1944/1944 个 200，max 70.78 ms；194/194 个 503 + `Retry-After: 2` | `b6b9-final.json` `m2-final-verdict.json` |
| M3 B7 浏览器子集 | 11/11，逐个与 stock 一致 | **PASS** | `m3-final-compare.json` `b7-candidate-t14*` |
| M4 带流停止 | 触发到进程实际退出 ≤ 10 s，exit 0；正常读取的客户端在连接关闭前收到终止事件 | **PASS** 5/5：0.085–6.692 s（启动器 0.092–6.698 s） | `m4-b5s.json` `rec-*` |
| M5 名额归还 | 签核 M5 | **PASS** 15/15 | `m5-slots.json` `m5-host.log` |
| M6 反向绑定 | 127.0.0.1 上三种绑定方式都失败；期间与之后的请求全部 200 且由宿主应答；`0.0.0.0` 只记录 | **PASS** | `m6-revbind.json` `m6-revbind-server.log` |

**M1：第二个信号**

负载：1 条活动流、1 条空闲流、1 个慢读者。驱动在第 1 个信号发出后 1.000–1.001 s 发出第 2 个同类信号。

| 阶段 × 事件 | 端口 | 第 1 个信号 → `stop.requested` s | 第 2 个信号 → 处理器 s | 第 2 个信号 → 解释器退出 s | 第 2 个信号 → 启动器退出 s |
|---|---|---|---|---|---|
| 排空 × CTRL_BREAK r0 | 8847 | 0.220 | 0.245 | 0.302 | 0.309 |
| 排空 × CTRL_BREAK r1 | 8848 | 0.014 | 0.029 | 0.073 | 0.081 |
| 排空 × CTRL_C r0 | 8849 | 0.199 | 0.207 | 0.250 | 0.257 |
| 排空 × CTRL_C r1 | 8851 | 0.045 | 0.050 | 0.100 | 0.108 |
| flush × CTRL_BREAK r0 | 8852 | 0.376 | 0.382 | 0.432 | 0.438 |
| flush × CTRL_BREAK r1 | 8853 | 0.231 | 0.237 | 0.291 | 0.297 |
| flush × CTRL_C r0 | 8854 | 0.447 | 0.452 | 0.502 | 0.508 |
| flush × CTRL_C r1 | 8855 | 0.061 | 0.065 | 0.114 | 0.121 |

- 8/8 退出码 130，没有输出 `project_runtime_stopped`。第 2 个信号到达时，宿主所处步骤与设计一致：排空阶段为 `shutdown.terminate_streams`，flush 阶段为 `shutdown.server_finish.begin`。
- 第 2 个信号到处理器的延迟与第 1 个信号到 `stop.requested` 的延迟基本相同（相差 0.004–0.025 s）。原因：两个信号相隔 1.0 s，正好是两个 0.5 s 切片，落在切片中的同一相位。所以最坏延迟由切片长度决定（≤ 0.5 s 加处理器与进程结束时间）。
- 排空阶段被强制退出时，活动流（不支持终止事件）在客户端得到 `ConnectionResetError(10054)`，空闲流已收到终止事件。

**M4：带流停止（B5 加强）**

时间相对触发。“flush 等待”指 flush 步骤的耗时。

| 用例 | 端口 | 触发 → t0 s | 活动流 终止事件 / EOF s | 空闲流 终止事件 / EOF s | flush 等待 | t0 → `os._exit` s | 触发 → 解释器 / 启动器退出 s | `os._exit` → 进程退出 ms |
|---|---|---|---|---|---|---|---|---|
| stop-file | 8841 | 0.160 | 0.162 / 0.163 | 0.163 / 0.163 | 无 | 0.060 | 0.281 / 0.291 | 60.6 |
| CTRL_BREAK | 8842 | 0.028 | 0.032 / 0.034 | 0.033 / 0.034 | 无 | 0.011 | 0.085 / 0.092 | 46.4 |
| CTRL_C | 8843 | 0.094 | 0.118 / 0.119 | 0.118 / 0.120 | 无 | 0.051 | 0.191 / 0.199 | 46.2 |
| 慢读（3 s 后恢复读取） | 8844 | 0.137 | 3.047 开始，3.097 完整 / 3.101（共 8,000,661 B） | 0.201 / 0.201 | 2.874 s，7,803,542 B 写完 | 2.986 | 3.167 / 3.173 | 43.8 |
| 不读（16 s 后才读） | 8846 | 0.136 | 只收到 197,118 B，没有终止事件 / 16.046 | 0.190 / 0.191 | 6.398 s 到截止，7,803,542 B 未写出 | 6.512 | 6.692 / 6.698 | 44.1 |

- 正常读取的客户端都在连接关闭前收到完整的终止事件：三种触发中，两条流在停止受理结束后 0.7–1.8 ms 到达；慢读与不读用例中的空闲流在 52.6–62.2 ms 到达。不读用例的活动流按签核只记录。
- 每个用例输出 1 行 `project_runtime_stopped`，`lingering_non_daemon` 为空，看门狗没有触发。
- 触发后 0.302–0.536 s 发起的新连接都是 `ConnectTimeout`（停止受理之后不再接受连接）。

**M5：名额归还（`final\m5-slots.json`，端口 8857，就绪 10.048 s，15 项检查全部 true）**

- 客户端中止，5 轮：
  - 每轮占满 4 条流后，第 5 条流得到 503 + `Retry-After: 2`（0.7–2.0 ms）。
  - 中止 4 条流后，新流 4/4 在 0.104–0.147 s 内被接受。每轮第 1 次尝试早于名额归还，得到 503。
- 服务端异常，2 轮：每轮 2 条 `fail_after=3`（中途异常）+ 2 条 `fail_after=0`（500）。
  - 新流 4/4 在 0.002–0.031 s 内被接受。
  - 第 5 条流 503（0.9/1.2 ms）。
  - 名额在 0.107/0.108 s 归零。
- 短请求池（上限 4）：
  - 占满后，第 5 个短请求 503 + `Retry-After: 2`（0.7 ms）。
  - 此时资产 200（1.5 ms，三个头都正确），短请求名额仍为 4，说明资产不计名额。
  - 中止后 0.106 s，`/ai/health` 恢复 200；0.524 s 名额归零。
- 结束时：
  - 准入：在途 0/0；峰值 流 4、短请求 4；接受 流 40、短请求 6；拒绝 流 13、短请求 2。
  - 桥：started 67，client_gone 36，cancelled_after_grace 4。
  - loop 上的 task 回到基线（`Task-1`、`s0-task-run-worker`）。
- stop-file 触发，0.145 s 后 exit 0；1 行 stop，剩余 task 0。

**M6：反向绑定（`final\m6-revbind.json`，端口 8850，宿主 pid 94440，就绪 9.566 s）**

宿主先按推荐方式独占服务：新配置加 `--enable-ctrl-c --state-lock --pid-marker`。随后另一个独立进程以 4 种方式尝试绑定同一端口，每种 3 次：

| 方式 | 结果（3 次） | winerror |
|---|---|---|
| 127.0.0.1 + `SO_REUSEADDR` | 失败 ×3 | 10013 ×3 |
| 127.0.0.1，不设选项 | 失败 ×3 | 10048 ×3 |
| 127.0.0.1 + `SO_EXCLUSIVEADDRUSE` | 失败 ×3 | 10048 ×3 |
| `0.0.0.0` + `SO_REUSEADDR`（只 bind，不 listen，立即关闭） | bind 成功 ×3（只记录，按 owner 更正不作为失败条件） | — |

- 请求：开始前、每次尝试期间与之后、结束时各发 20 个，`/ai/health` 与 `/s0/django/thread/` 交替，带合法 Host 和凭据，共 520 个。
  - 全部 200，`X-S0b-Pid` 都是宿主 94440。
  - 期间与之后 p50 2.83 ms，max 28.68 ms。开始前那批 max 568.18 ms，是第一个 Django 请求（冷启动）。
- 宿主 exit 0，1 行 `project_runtime_stopped`，没有错误标记。
- 结论：正在服务的地址与端口独占；通配绑定按 Windows 文档可以成功，但截不走回环连接。

**M2：B6 与 B9 (a)(b)(c) 在同一次饱和中**

方法：
- arm 与端口：
  - `baseline` 8840（`serve_baseline.py`，未改）；
  - `rec_t14` 8858（candidate：新配置）；
  - `rec_t14_sat` 8859（b9：新配置 + hold 进程占满流上限）；
  - `waitress_wn_noauto` 8845（threads 8 对照，同 Phase 2）。
- 测量：4 块 × 40，warmup 10，seq 与 c4，交错测量，包含页面引用的静态资源，静态文件经过认证。测量 930.7 s（约 17:07–17:22）。
- 表中格式：p50/p95 ms，× 为 p95 比值，h 为只算 HTML 的 p95，r 为单请求 p50。

| 模式 | arm | home | projects | project_detail | stage_reports | draft_edit | bug_trend |
|---|---|---|---|---|---|---|---|
| seq | `baseline` | 115/138 h15 r1.74 | 130/152 h20 r1.90 | 140/170 h29 r1.96 | 179/215 h78 r1.87 | 196/248 h81 r2.02 | 127/151 h27 r1.76 |
| seq | `rec_t14` | 117/132 ×0.96 h15 r1.74 | 126/155 ×1.02 h22 r1.81 | 133/171 ×1.01 h31 r1.80 | 174/216 ×1.01 h83 r1.76 | 189/237 ×0.96 h79 r1.87 | 119/138 ×0.91 h27 r1.62 |
| seq | `rec_t14_sat` | 113/133 ×0.96 h16 r1.69 | 132/166 ×1.09 h23 r1.91 | 137/165 ×0.97 h30 r1.88 | 174/215 ×1.00 h79 r1.77 | 191/244 ×0.99 h81 r1.92 | 117/136 ×0.90 h25 r1.59 |
| seq | `waitress_wn_noauto` | 113/138 ×1.00 h16 r1.67 | 128/177 ×1.16 h23 r1.85 | 132/163 ×0.96 h29 r1.81 | 169/203 ×0.95 h75 r1.72 | 191/270 ×1.09 h85 r1.91 | 112/128 ×0.85 h25 r1.54 |
| c4 | `baseline` | 306/347 h34 r4.77 | 348/390 h44 r5.32 | 365/409 h64 r5.31 | 471/528 h205 r5.01 | 510/580 h191 r5.28 | 350/429 h69 r5.13 |
| c4 | `rec_t14` | 278/322 ×0.93 h29 r4.25 | 317/365 ×0.94 h50 r4.79 | 335/397 ×0.97 h66 r4.71 | 460/500 ×0.95 h196 r4.81 | 473/525 ×0.91 h199 r4.63 | 308/341 ×0.79 h65 r4.26 |
| c4 | `rec_t14_sat` | 291/338 ×0.97 h37 r4.47 | 319/371 ×0.95 h46 r4.75 | 357/415 ×1.01 h73 r5.08 | 485/535 ×1.01 h216 r4.98 | 473/527 ×0.91 h192 r4.66 | 321/368 ×0.86 h68 r4.48 |
| c4 | `waitress_wn_noauto` | 276/320 ×0.92 h34 r4.21 | 322/373 ×0.95 h45 r4.85 | 344/388 ×0.95 h70 r4.90 | 478/529 ×1.00 h217 r4.87 | 457/513 ×0.88 h174 r4.64 | 304/365 ×0.85 h64 r4.27 |

- p95 比值范围，三个 arm 都是 12/12：
  - `rec_t14`：seq 0.914–1.020，c4 0.795–0.970；
  - `rec_t14_sat`：seq 0.899–1.093，c4 0.857–1.015；
  - `waitress_wn_noauto`：seq 0.848–1.159，c4 0.851–1.003。
- 无凭据请求静态文件：`baseline` 200，其余三个 arm 401。
- 所有 arm 的进程 exit 0，各 1 行 `project_runtime_stopped`。
- hold 进程：
  - 17:06:32.221–17:22:44.305 保持 972.1 s，exit 0。
  - 开始时 4 条流都是 200。活动流 9720 个事件，间隔 p50/p95/max 105.0/108.5/257.4 ms。
  - 3 条空闲流的心跳间隔 max 2023.1 ms。
  - 中途没有 EOF 或错误。
- (a) 每 5 s 探测一次第 5 条流：194/194 立即得到 503 + `Retry-After: 2`，p50/p95/max 2.29/22.56/24.37 ms；开始与结束时的探测也是 503。宿主的拒绝计数为 196（含开始与结束的探测）。
- (b) 每 1 s 发一次 `/ai/health`（经过 loop），每 1 s 发一次资产请求（直出）。共 1944 个，全部 200，没有 ≥ 100 ms 的请求：
  - 全部：p50/p95/p99/max 4.64/25.72/27.24/70.78 ms；
  - `/ai/health`（972 个）：5.34/18.87/22.77/70.78 ms；
  - 资产（972 个）：2.36/26.44/27.54/33.12 ms。
  - 宿主内从进入分派到 `start_response`：资产 0.10/0.14/0.19/0.46 ms（972 个）；`/ai/health` 2.46/3.74/4.93/47.58 ms（971 个）。
- (c) `rec_t14_sat` 12/12。
- 判定：(a)(b)(c) 全部满足，M2 **PASS**。旧配置的 FAIL 记录保留在 §3.10。

客户端耗时分解（1943 个匹配，1 个未匹配；p50/p95/p99/max ms）：

| 段 | 含义 | p50 | p95 | p99 | max |
|---|---|---|---|---|---|
| client | 客户端测得的总耗时 | 4.64 | 25.72 | 27.14 | 70.78 |
| pre_app | 客户端开始 → 宿主进入分派（连接、waitress 接受、解析、排队到工作线程） | 2.4 | 25.1 | 26.5 | 42.9 |
| post | 宿主 `start_response` 之后 → 客户端读完（响应字节、客户端读取、关闭） | 0.21 | 0.9 | 2.76 | 23.47 |

- p95 的尾部在 pre_app（进入宿主分派之前），不在应用内。

**归因诊断（不作为判据；`final\final-rec_t14{,_sat}-diag.json`、`final\final-rec_t14_sat-hold.json`、`final\m2-window-attrib.json`）**

- 宿主 GC：
  - `rec_t14_sat`：gen0 1109 次（max 2.35 ms），gen1 101 次（max 4.71 ms），gen2 1 次。
    - 这次 gen2 耗时 218.65 ms（17:09:25.670，线程 waitress-9），落在 `rec_t14_sat` seq/projects 第 2 块，ticker 同时记到 223.65 ms 停顿。
    - 它没有与任何短请求重叠：前一个短请求在它开始前 349.9 ms 结束，后一个在它结束后 443.3 ms 开始。
    - 该单元格是这个 arm 比值最高的（1.093×），只是相关。
  - `rec_t14`：gen2 194.6 ms（17:13:26.063，seq/draft_edit 第 0 块），ticker 记到 197.76 ms 停顿。另有 3 次非 GC 停顿：68.95 ms（17:08:51）、56.54 ms（17:17:33，c4/projects）、57.84 ms（17:20:39，c4/draft_edit）。
- ticker（> 50 ms 计为停顿）：
  - `rec_t14_sat` 宿主：92886 次 / 973.3 s，最大间隔 223.65 ms，1 次停顿；
  - `rec_t14` 宿主：最大间隔 197.76 ms，4 次停顿；
  - hold 驱动：93950 次 / 972.3 s，最大间隔 90.57 ms，1 次停顿（17:14:54.760，当时没有在途短请求）。
- ≥ 50 ms 的短请求共 2 个：
  1. 50.96 ms，`/ai/health`，17:06:32.306。这是 hold 的第一个 `/ai/health`，宿主内 47.58 ms，pre_app 2.3 ms，post 1.08 ms。它落在 17:06:15–17:06:39 的 pytest 窗口内（已确认重叠；它同时是 hold 的第一次调用，原因不能单独判定）。
  2. 70.78 ms，`/ai/health`，17:21:24.321，`rec_t14_sat` c4/draft_edit 第 2 块，不在任何已确认的 Metrics 侧窗口内。
     - 宿主内 4.41 ms，pre_app 42.9 ms，post 23.47 ms。
     - 附近没有 GC（最近的是 0.19 s 前的一次 gen1，2.5 ms），宿主与驱动都没有 > 50 ms 的停顿，前后短请求 2.57–16.97 ms。
     - 耗时在宿主分派之前与 `start_response` 之后（连接与 waitress I/O、客户端读取），现有埋点不能再细分，**无法判定**。
- Metrics 侧并发活动与 M2 的重叠（复签据会话日志确认，本地时间；完整列表见偏差第 10 项）：
  - 17:06:15–17:06:39，两次 pytest：与 M2 启动、预热与 hold 起点重叠，没有测量块（M2 的第 1 个测量块从 17:07:13.494 开始）。离群 #1 在这个窗口内（见上）。仓库 `scripts\tests\__pycache__` 中写于 17:06:22.114–.184 的 pytest 缓存来自这里，已确认是 Metrics 侧。
  - 17:14:37–17:14:49，pytest（17 项 Django 测试）：只与 seq/draft_edit 第 2 块中的 `rec_t14_sat` 与 `waitress_wn_noauto` 重叠，没有 baseline 块；若有影响，也只会抬高候选 arm 的比值，属保守方向。两个被监测的宿主都没有 ≥ 20 ms 的 GC，也没有停顿。
  - 17:18:00–17:19:59，三个读文件的短 python 进程：与 32 个测量块重叠（c4 的 projects、project_detail、stage_reports，4 个 arm 交错；c4/project_detail 的 16 块全在窗口内）。复签的敏感性分析认为判定稳健：只有落在 baseline 块上的负载会让比值偏乐观；这些单元格中最接近门限的 rec 比值为 1.015×，要掩盖一个超过 1.2 的真实比值，baseline p95 需要被抬高 ≥ 18.3%；窗口内 baseline 的 p95/p50（1.119–1.122）与块耗时都不支持这种抬高，被监测的宿主与驱动没有 > 50 ms 的停顿，也没有 ≥ 20 ms 的 GC。残余：baseline 进程没有 ticker，也没有逐请求样本，只落在 baseline 块上的亚秒级突发不能严格排除。
  - 离群 #2（17:21:24.321）不在任何已确认窗口内。驱动 ticker 的 90.57 ms 停顿（17:14:54.760）不在已确认的窗口内，原因无法判定。
  - 冒烟重跑、M5、M6 与 M3 的重叠见偏差第 10 项。这些判据是功能性的，或有很大余量（例如 `os._exit` 到退出 42 ms 对 300 ms 预算，名额归还 ≤ 0.147 s 对心跳间隔 + 1 s），负载只会让它们更难通过，复签认为判定稳健。
- `m2-window-attrib.json` 中的窗口是当时的估计：`external_window`（17:14:30–17:14:55，当时估计）与 `in_external_window`（两个离群都为 false）只按这个估计窗口计算，没有包含后来确认的其他窗口；证据已冻结，JSON 没有修改。按估计窗口统计，窗口内 50 个短请求全部 200，p50 4.7 ms，max 27.8 ms；确认窗口 17:14:37–17:14:49 是它的子集，所以其中的短请求也全部 200 且 ≤ 27.8 ms。估计窗口中的 `rec_t14` 第 2 块、`waitress_wn_noauto` 第 3 块与 17:14:54.760 的驱动停顿都不在确认窗口内。
- 仓库修改：M2 期间 `jira_sync/container.py` 被 Metrics 侧修改（17:09:14）。各 arm 在 17:06:16 启动并已完成预热，推断各 arm 用的是同一份代码（偏差第 10 项）。

**M3：B7 浏览器子集（threads 14）**

- 11/11 passed，逐个与 stock 一致（stock 06:53–06:59，HEAD 6b3d017；候选在 7181b6f 加未提交修改上运行，代码树见偏差第 10 项）；pytest 392.3 s，合计 400.3 s；`b7-candidate-t14.err.log` 为空。
- live server 在 8856/8857/8858 上运行，都是 waitress + Proactor loop。无凭据请求 `/ai/health`、`/ai/openapi.json` 得到 401，`/ai` 得到 308。
- 每次停止：drain 0.001 s，`budget_misses` 为空，`leftover_tasks` 为空，`runtime_loop_joined` 为 true。没有残留线程，没有网络或 IPC 尝试，`temp_left_behind` 为 false。

**最终停止预算（按进程实际退出计算；`s0b_host.py` 的 `STOP_BUDGET`）**

实测来自 11 个正常停止的最终宿主：冒烟、M4 ×5、M5、M6，以及 M2 的 3 个宿主 arm。

| 段 | 预算 | 实测 |
|---|---|---|
| 停止受理 | 0.5 s | 0.000–0.001 s |
| 终止宽限（到期取消仍未结束的桥 task） | 2.0 s | 终测中没有走到取消路径 |
| 排空 | 截止 t0 + 3.0 s | t0 → 排空结束 0.001–0.106 s |
| flush | 截止 t0 + 6.5 s | flush 加关闭 0.000–6.404 s（最大值是不读用例，到截止） |
| server 关闭 | 0.5 s | 计入上一行 |
| join `serve-http` | 0.5 s | ≤ 0.001 s |
| waitress 工作线程 | 0.5 s | ≤ 0.002 s |
| project runtime | 0.5 s（无执行中的 run） | ≤ 0.001 s |
| AI runtime | 1.0 s | 0.001–0.003 s |
| 小计：t0 → `os._exit` | 9.5 s | 0.0074–6.5121 s |
| 显式退出 | 0.2 s | 0.073–0.106 ms（无诊断转储）；有转储时 2.49–22.55 ms |
| 进程结束（`os._exit` → 进程句柄 signal） | 0.3 s | 43.8–60.6 ms（M4）；冒烟 42.14 ms |
| 合计：t0 → 进程实际退出 | 10.0 s | M4 触发到解释器退出 0.085–6.692 s；最长为不读用例 |

- t0 是 `stop.requested`。从触发算起还要加上触发延迟：stop-file 每 0.2 s 轮询，M4 中为 0.028–0.160 s。
- 看门狗：daemon 线程在 t0 + 10 s 执行 `os._exit(3)`，终测中没有触发。
  - 走看门狗时，进程实际在约 t0 + 10 s 再加上 `os._exit` 之后的进程结束时间（约 0.05 s）才退出，略超 10 s。
  - 若 `serve` 要把 10 s 作为硬上限，看门狗应提前留出余量（例如 t0 + 9.7 s）。
  - 这是 spike 的测量护栏。`serve` 的进程内看门狗为 660 s，Docker 用 `--stop-timeout 690`，启动脚本 ≥ 15 s 后按 PID 强制结束；10 s 预算不含 `project_runs.stop(620)` 对执行中 run 的等待（owner 决定 3）。
- 第二个信号：判据 ≤ 1.0 s，实测 0.073–0.502 s（解释器）/ 0.081–0.508 s（启动器），由 0.5 s 切片与 `os._exit(130)` 保证。
- 宿主 `STOP_BUDGET` 中 `os_teardown` 的注释“measured 5-8 ms”有误，正确数字以本表为准（偏差第 10 项）。

## 4. 发现

### 4.1 AIB-2 / 上游 v2.1 新要求（S0 R1–R13 之外；对应 `design.md:18-19` 的 Q10）

| # | 发现（S0b 实测） | 要求 |
|---|---|---|
| R14 | 线程托管只能在 loop 线程上手动进入 `aibase_app.router.lifespan_context(aibase_app)`；lifespan 是唯一的启停入口（R11） | runtime 提供不依赖 ASGI lifespan 的启停方式：在宿主 loop 线程上可调用的显式 `start()`/`stop(deadline)`，或直接提供 `start_blocking` 句柄（`design.md:123-125`）。句柄在自己的非 daemon 线程上创建 loop（Windows 上断言 Proactor），启动异常在时限内传回调用线程，停止后取消剩余 task 并 join |
| R15 | 宿主无法让所有打开的流正常结束：只有支持宿主关闭事件的流（spike `terminal=1`）能在 0.01–1.01 s 内发送终止事件，其余只能等宽限期后取消；AI Base 的流不感知关闭（R10）；与聊天流同类的 Starlette 端点在 2 s 宽限期后被取消，2.12–2.31 s 在 HTTP 层干净结束，客户端收不到终止事件，只能从缺少完成事件推断被中断（§3.5） | 第一段停止（v2.1 H2）：新的 `/ai` 请求得到 503；所有打开的流在 ≤ 2 s 内发送终止事件并结束（例如 NDJSON 一行 `{"type":"shutdown"}`）；blocking 门面与 task run 照常工作。第二段停止取消剩余任务并标记中断 |
| R16 | 同步 server 只有在写失败时才知道客户端已断开，可移植的 WSGI 没有断开通知；spike 的快速检出依赖 server 特定探测（waitress `client_disconnected`、`MSG_PEEK`）；关闭探测后只能靠写失败发现断开：空闲流在 waitress 上 1.80 s 检出（第 1 次心跳），在 devserver 上 3.80 s（第 2 次心跳），超过 3.0 s 门限（§3.5） | 空闲流定期发送心跳（≤ 2 s，可配置），使检出时间有上界，且不依赖 server 扩展 |
| R17 | Starlette `StreamingResponse` 在 `spec_version >= 2.4` 时不监听 `http.disconnect`，只依赖 `send` 抛 `OSError`（`responses.py:270-276`）；a2wsgi 声明 "2.5" 且 `send` 不抛错，task 永远挂起（B4） | WSGI 适配器在断开后必须投递 `http.disconnect`，之后 `send` 抛 `OSError`，超时后取消 task。runtime 的流路由把 `http.disconnect`、`CancelledError`、`OSError` 都当作停止信号，释放模型调用、审批等资源，并记录结局 |
| R18 | a2wsgi 的跨线程等待没有时限（`asgi.py:165,213-214,301`），loop 停止后请求线程永久阻塞（B5 cheroot 只能靠看门狗退出） | 适配器与门面中所有跨线程等待都有时限；runtime 停止中或已停止时立即返回 503 或抛出明确错误，不阻塞 |
| R19 | a2wsgi 1.10.10 不满足 B4/B5；spike 自写的桥约 450 行才满足 B3–B5，而且要按 server 做断开探测 | 核心 wheel 提供并测试 WSGI 适配器（v2.1 H7，`design.md:16-19,87`），包含：在途上限与 503 + `Retry-After`、断开语义（R17）、有界等待（R18）、`terminate_all`（R15）。不使用 a2wsgi；断开探测作为可选的 server 钩子 |
| R20 | 每个在途 `/ai` 流在结束前一直占用一个 WSGI 线程（WSGI 同步模型）。诊断中 loop 上有 2 条 50 ms 流时，（相对同 arm 无流）页面 p95 比为 0.94/0.97。M2 中 4 条流占满上限、同时每秒发 2 个短 `/ai` 请求时，threads 12 为 12/12（此前 B9(c) 中 threads 8 为 11/12）；hold 期间 2092 个短请求全部 200，其中 2 个 ≥ 100 ms，与进程级或跨进程的停顿同时出现，原因无法判定（旧配置，§3.10）。终测 M2（threads 14、短请求上限 4、资产直出）中 `rec_t14_sat` 12/12，1944 个短请求全部 200 且 < 100 ms（max 70.78 ms）；宿主内资产 max 0.46 ms、`/ai/health` p99 4.93 ms，客户端尾部在进入宿主分派之前（§3.11） | 适配器暴露在途数并支持配置上限；宿主据此为页面保留线程（`design.md:95-96`）。短请求的尾延迟要单独观测（例如按 `/ai` 路由统计 p99 与 max） |
| R21 | loop 阻塞时，timeout 0.3 s 的门面调用按时抛 `TimeoutError`；但取消要等 loop 恢复后才送达，task 的第一步已经执行（消耗 `s0-run-1` 并入队，§3.1 第 5 项） | 门面写明超时语义：超时不等于未开始。`start` 接受调用方提供的幂等键（或先返回可查询的提交 id），超时后可以查询或去重；runtime 要么保证被取消的提交没有副作用，要么能在之后对账 |
| R22 | 共享在途上限下，流占满名额后，短请求（静态资源、health、小 API）也全部 503（B9 共享设计 FAIL） | 适配器分别限制长连接流与短请求，各自超限时返回 503 + `Retry-After`；路由声明自己是否为流；在途数与拒绝数可观测 |
| R23 | loop 被阻塞时，经桥的短请求会一直等到 loop 恢复（2.76 s），期间各占 1 个 WSGI 线程（§3.1 第 5 项） | runtime 提供 loop 滞后监测（例如心跳 task + 滞后阈值告警），健康检查反映 loop 状态；桥对短请求设总时限，超时返回 503/504；loop 上禁止阻塞调用（开发模式开启 asyncio debug 的慢回调告警） |
| R24 | 旧宿主以 `sys.exit(0)` 结束时，`process.exit` 之后还要 0.85–0.92 s 进程才退出。几乎全部时间在最后一个 atexit 回调之后（模块清理、GC 与进程结束，849–915 ms）；join 非 daemon 线程与 atexit 回调合计不到 0.5 ms（步骤 A，§3.11）。终测宿主改为显式退出，`os._exit` 到进程退出为 43.8–60.6 ms | owner 决定的上游 SDK 契约：`start_blocking` 退出时，runtime 已 flush 并关闭全部持久资源（例如数据库连接、文件与日志 handler），不依赖 atexit 或解释器收尾。这样宿主在它返回后可以直接 `close_all()` → `logging.shutdown()` → flush → `os._exit(code)`。runtime 不把必须完成的工作放在 atexit 中 |

### 4.2 Metrics `serve` 要求（对应 `design.md` 决策 2/3 中的【待 S0b】项）

1. HTTP server：waitress 3.0.2。它是唯一同时满足 C5（Phase 2 12/12；终测 M2 中新配置的两个 arm 也是 12/12）和“静态文件在认证之后”的 production server。B3、B4 PASS。新配置终测（§3.11）中，B5（M4：`flush` × 三种触发，另加慢读与不读）、B7（M3）、B6 与 B9 (a)(b)(c)（M2，同一次饱和）都 PASS。旧配置 M2 中 B9 (b) 有 2/2092 个短请求 ≥ 100 ms，FAIL（§3.10，记录保留）。不选 cheroot：Windows 上 keep-alive 每个请求约 61 ms（Phase 1 0/12），`ThreadPool.stop` 还有无时限 `join()`。devserver 不是 production server，Phase 2 `dev_wn` 11/12，关闭探测后空闲流 3.80 s 才检出断开。
2. 绑定（决策 2 第 1 步）：
   - 主线程先自己创建并绑定监听 socket（默认 127.0.0.1；Windows `SO_EXCLUSIVEADDRUSE`，POSIX `SO_REUSEADDR`），再加载 AI Base、启动 runtime，最后交给 waitress：`create_server(app, sockets=[sock], ...)`。不能让 waitress 自己绑定：它在 Windows 上也设置 `SO_REUSEADDR`，会与 REUSEADDR 占用者“共存”而不报错（§3.1）。预绑定之后，其他进程在 127.0.0.1 上以 `SO_REUSEADDR`、默认、`SO_EXCLUSIVEADDRUSE` 绑定同一端口都失败（10013/10048/10048，各 3/3），尝试期间与之后的请求都由宿主应答；`0.0.0.0` + `SO_REUSEADDR` 只 bind 可以成功（3/3），截不走回环连接。终测 M6 在最终宿主（新配置）上得到同样结果，520 个请求全部由宿主应答（§3.11）；上一轮补测 (a) 结果相同（§3.10）。
   - 10048（WSAEADDRINUSE）与 10013（WSAEACCES）都按“端口被占用”退出；spike 中 4/4 个占用用例 0.36–0.43 s exit 4，S0 的 uvicorn 约 12 s 后才失败。
   - state 目录锁在绑定成功之后才获取：占用用例中没有创建 state 目录与锁；共用 state 目录的第二个实例换端口启动时，因锁被占而 exit 5，没有进入 lifespan（`b1-portbind-host.json`）。
   - waitress 3.0.2 构造 `Adjustments` 时会对类默认值 `listen='0.0.0.0:8080'` 做一次 `getaddrinfo('0.0.0.0', 8080, ...)`（`adjustments.py:146,368`）。这是 IP 字面量解析，不访问网络；传入 `sockets` 时结果不使用（`server.py:73`；socket 以 `bind_socket=False` 包装，`server.py:91-101`）。预绑定时不能改传 `listen`：`listen` 与 `sockets` 同时传入时，waitress 3.0.2 抛 `ValueError`（`adjustments.py:296-297`）。spike 临时替换类默认值，只是因为它自己的回环网络守卫（`s0_common.py:77-80`）拒绝这次查找；推荐组合不修改 waitress 的类属性，测试用的网络守卫应放行 IP 字面量解析。
   - 本机 TCP 动态端口范围为 1024–15000，包含 8840–8859：出站连接可能临时占用 `serve` 的端口，选默认端口与写冲突提示时要考虑。
3. 受理、停止受理、排空与收尾（决策 3，`:178`）：
   - 受理：waitress `server.run()` 在非 daemon 的 `serve-http` 线程上运行，主线程只做 ≤ 0.5 s 的切片等待并处理信号。改后宿主与终测宿主都用这种布局，旧配置 M1–M5 与终测 M1–M6 都在其上运行（§3.10、§3.11）。
   - 停止受理：`server.trigger.pull_trigger(...)` 在 asyncore 循环上关闭监听 dispatcher；已有连接的 I/O 不受影响（M4 的 3 个正常读取用例中，两条流的终止事件在停止受理结束后完整到达客户端：旧配置 0.9–3.9 ms，终测 0.7–1.8 ms；慢读客户端恢复读取后收到完整的 8 MB 终止事件）。之后发起的新连接没有被接受（M4 中触发后约 0.3–0.54 s 发起的新连接都是 `ConnectTimeout`）。
   - 排空：宿主自己统计在途请求（桥 + Django），因为 waitress 与 devserver 的工作线程都是 daemon 线程（`task.py:61`、`basehttp.py:90,275`），不会被等待。Django 的计数要到响应迭代器 `close()` 时才减；spike 在 `__call__` 返回时就减，Django `StreamingHttpResponse` 因此不计入排空，waitress 在 2.10 s 收尾时把它截断（§3.4）。Django 的流视图也要感知宿主停止。
   - 收尾要等输出缓冲写完（`flush`）：先等工作线程写完，再给每个 channel 设 `close_when_flushed`，直到 channel 数为 0 或到期（t0 + 6.5 s）；然后 `server.close()`、`task_dispatcher.shutdown(cancel_pending=True, timeout=0.5)`。到期时仍未写出的数据被丢弃：M4 不读用例到期时 7,803,542 B 未写出，客户端没有收到完整的终止事件。waitress 的 `close` 收尾会立即丢弃未写出的缓冲，慢读客户端收不到终止事件（第 1 项）。
4. 第一段停止时限（决策 2 第 7.2 步）：spike 的宽限期为 2 s。活动流 ≤ 1.01 s 收到终止事件；不支持终止事件的流在 2.0–3.0 s 被取消；drain 合计 2.01–2.52 s（改动前的宿主测得），也在改后排空截止 t0 + 3.0 s 之内。改后宿主与终测宿主都没有单独测取消路径：M1 排空阶段在取消之前就被第二个信号强制退出。数据支持把时限设为 2 s。
5. 触发与退出码：
   - SIGINT、CTRL_BREAK（SIGBREAK，需要 `CREATE_NEW_PROCESS_GROUP`）、stop-file 都只设置停止事件，由同一流程执行停止；正常停止 exit 0，且恰好 1 行 `project_runtime_stopped`（改动前 9/9；改后宿主 M4 5/5、M5 1/1，M2 的 3 个宿主 arm 也是；终测宿主冒烟、M4 5/5、M5、M6 与 M2 的 3 个宿主 arm 也是）。
   - 显式退出（owner 决定，终测宿主已实现）：每条退出路径最后依次执行 `django.db.connections.close_all()`、`logging.shutdown()`、`sys.stdout`/`sys.stderr` flush，然后 `os._exit(code)`；干净结束 0，清理失败或看门狗到期 3，第二个信号 130；看门狗保持到 `os._exit`。它替代了 `sys.exit(0)` 之后 0.85–0.92 s 的解释器收尾与进程结束（步骤 A，§3.11），前提是 runtime 满足 R24。
   - 停止过程中收到第二个 SIGINT/CTRL_BREAK 时强制退出：执行 `os._exit(130)`，不输出 `project_runtime_stopped`。终测 M1 按签核计时（第 2 个信号在第 1 个之后 1.0 s 发出），到进程实际退出 0.073–0.502 s（启动器 0.081–0.508 s），8/8 exit 130（排空与 flush 两个阶段 × CTRL_BREAK/CTRL_C × 各 2 次；§3.11）。旧配置 M1 以 `stop.requested` + 1.0 s 为基准，为 0.061–0.084 s（§3.10）。
   - 主线程上的所有等待（join、排空、`Event.wait`）都要切片到 ≤ 0.5 s：CPython 只在主线程执行信号处理器，合成子进程中不切片的 `join(10)` 使第二个信号延迟 8.58–8.61 s，切片后为 0.22–0.23 s（§3.1）。waitress `run()` 也不能留在主线程：主线程阻塞在 `select` 中时，处理器要等 `asyncore_loop_timeout`（默认 1 s）到期才运行；所以用 `serve-http` 线程布局，或把该值设为 ≤ 0.5。
   - 设计中的 SIGTERM 在 Windows 上无法由其他进程送达：`os.kill` 对 CTRL 事件以外的信号直接 `TerminateProcess`。spike 安装了 SIGTERM 处理器但没有测试；建议增加 SIGBREAK。
   - 看门狗兜底 server 或桥卡住的情况：改后宿主与终测宿主在 t0 + 10 s 执行 `os._exit(3)`（改动前为 drain + 25 s，cheroot × a2wsgi 在改动前实际触发过）；旧配置 M1–M5 与终测中都没有触发。spike 的 t0 + 10 s 只是测量护栏，`serve` 的进程内看门狗为 660 s（第 9 项）。
6. 线程数与在途上限（`design.md:95-96`）：
   - owner 决定（2026-11-11）：
     - `/ai` 用分离准入：长连接流上限 4，短请求上限 4；超限立即返回 503 + `Retry-After: 2`，不排队。threads 14。
     - `/ai/*` 固定顺序：Host 校验（非法 400）→ 请求完整性（能做的就做）→ 认证（401，不占名额，不调度 loop 工作）→ 资产直出或准入 → 路由。按复签 D 第 1、4 项分两层落实：
       - L0，waitress 传输层：先于应用执行，适配器无法改变其顺序。包括请求行与头部大小、`Content-Length` 语法（非数字 400；spike 冒烟中的这个 400 即由 waitress 返回）、chunked 分帧、`max_request_body_size`（413，必须显式配置）。
       - L1，适配器：Host 校验（所有路径，复用 Django `validate_host` 与 `ALLOWED_HOSTS`，非法 400）→ 停止中 503（所有路径，固定文本，带 `Retry-After`）→ 分流。Django 路径进入 Django 中间件链（`BasicAuthMiddleware` 第一）；`/ai*` 依次为按路由的完整性 → BasicAuth 401 → `/ai` 到 `/ai/` 的 308（相对 `Location`）→ 资产直出 → AI runtime 停止中 503 → 准入（503 + `Retry-After`）→ 桥。Host 校验移到最外层后，Django 路径上“非法 Host + 无凭据”的结果由 401 变为 400，这一变化要写进 spec 并加入测试矩阵。
       - 请求体上限由 waitress `max_request_body_size` 实现：判定为 `>=`，要允许恰好 N 字节就设 N+1；适配器另做按路由的上限。16 MiB 是占位值，要按 `/ai` API 契约中最大的合法请求定量。请求体在认证之前就被缓冲，最坏的临时文件占用约为“上限 × waitress `connection_limit`（默认 100）”。宿主的非数字 `Content-Length` 分支可以作为纵深防御保留，但测试要断言 400 与 413 分别来自哪一层。
       - 终测宿主与 L1 的差别：停止中 503 在 Host 校验之前，`/ai` 的 308 在认证之前（风险 13）。
     - AI Base UI 资产在认证之后由适配器直接返回：只返回构建时固定清单中的资产，只接受 GET/HEAD；响应头为 `Cache-Control: private, max-age=31536000, immutable`、ETag、`X-Content-Type-Options: nosniff`；清单外路径 404。资产不经过 loop，不计入准入。
     - 这个组合已在终测中作为整体运行（§3.11）：M2 中 4 条流占满时 12/12；hold 期间 1944 个短请求全部 200 且 < 100 ms（`/ai/health` 经过 loop，资产直出）；冒烟与 M5 确认资产不占名额，未认证请求在短请求池占满时也是 401。
   - 旧配置（threads 12、短请求上限 2、UI 资产计入短请求名额并经过 loop；认证同样先于准入；没有 Host 校验）的 M2 中，2/2092 个短请求 ≥ 100 ms（B9 (b) FAIL，原因无法判定；§3.10）。
   - 共享上限会让短请求也得到 503（B9 共享设计 FAIL），所以流与短请求分开限制。
   - 线程预算按 `threads ≥ 流上限 + 短请求上限 + 页面并发 + 余量`：M 参数为 4 + 2 + 4（c4）+ 2 = 12，owner 新决定按同一公式为 4 + 4 + 4 + 2 = 14（终测已运行）。threads 8 饱和时不合格的是 1 个 seq 单元格（1.23×），不是线程耗尽，不能证明 8 不够。未饱和时，threads 8 在 Phase 2、旧配置 M2 与终测 M2 中都是 12/12。
7. 访问日志：waitress 没有内置访问日志（spike 用 WSGI 中间件按 Django 格式写出），`serve` 需要自己提供。
8. 停止期间的新请求：立即返回 503，不阻塞。不设 `Connection: close` 等 hop-by-hop 头（PEP 3333 禁止，waitress 会抛 `AssertionError`）；同一 keep-alive 连接上的请求 1.1–62 ms 内得到 503。
9. 停止预算（owner 决定：10 s，按进程实际退出计算）：从 t0（收到停止请求）到进程实际退出，各段见 §3.11 末的表（`s0b_host.py` 的 `STOP_BUDGET`）。
   - 各段预算：
     - 停止受理 0.5 s；
     - 终止宽限 2.0 s（到 t0 + 2 s 取消仍未结束的流）；
     - 排空截止 t0 + 3.0 s；flush 截止 t0 + 6.5 s；
     - server 关闭、join `serve-http`、waitress 工作线程、project runtime 各 0.5 s；AI runtime 1.0 s（到 `os._exit` 最坏 9.5 s）；
     - 显式退出 0.2 s；进程结束 0.3 s。
   - 终测实测：t0 → `os._exit` 0.0074–6.5121 s；`os._exit` → 进程退出 43.8–60.6 ms；M4 触发到解释器进程退出 0.085–6.692 s（启动器 0.092–6.698 s），最长为不读用例。
   - 改动前与旧配置的宿主以 `sys.exit(0)` 结束，`process.exit` 之后还有 0.85–0.92 s 的解释器收尾与进程结束（步骤 A），不在预算与看门狗之内。显式退出消除了这一段。
   - 执行中的 project run（owner 决定，没有测试）：
     - 10 s 预算不含 `project_runs.stop(620)` 对执行中 run 的等待。
     - 进程内看门狗 660 s，Docker `--stop-timeout 690`。
     - 启动脚本写入 stop-file 后，≥ 15 s 仍未退出就按 PID 强制结束；中断的运行由下次启动时的恢复流程标记。
     - spike 的 0.5 s 段只代表“没有执行中的 run”。
   - 看门狗要一直保持到 `os._exit`。spike 的 t0 + 10 s 看门狗只是测量护栏，走到时进程实际在 t0 + 10 s 再加约 0.05 s 后退出。如果要把 10 s 当作硬上限，看门狗应留出进程结束的时间（例如 t0 + 9.7 s）。
10. 名额归还（签核 M5）：流因客户端中止或服务端异常而结束后，要立即归还准入名额；名额在响应迭代器 `close()` 时归还。
    - 终测 M5（短请求上限 4，§3.11）：
      - 客户端中止 4 条流后，新流 4/4 在 0.104–0.147 s 内被接受；服务端异常结束后为 0.002–0.031 s。
      - 短请求池中止后 0.106 s 恢复 200；短请求池占满时资产仍为 200，且不占名额。
      - 结束时准入在途 0/0，loop 上的 task 回到基线。
    - 旧配置 M5：分别为 0.104–0.167 s、0.002–0.028 s、0.105 s（§3.10）。
    - 流正常结束时的归还没有单独计时。

### 4.3 静态文件姿态取舍

| 姿态 | 认证 | C5 | 代价 |
|---|---|---|---|
| `sfh`：`StaticFilesHandler` 包在 Django 外（同基线） | 绕过 | 只在 Phase 1 测：`dev_sfh` 10/12，`waitress_sfh` 11/12 | 静态文件不经认证；与 runserver 相同的开发用 handler |
| `wn`：WhiteNoise 在 `BasicAuthMiddleware` 之后，DEBUG 默认 autorefresh | 在认证之后 | Phase 2：`waitress_wn` 11/12，`dev_wn` 11/12，FAIL | 每个请求都重新检查文件系统，单个请求 p50 约多 0.4 ms；WhiteNoise 文档说明 autorefresh 只用于开发 |
| `wn-noauto`：同 `wn`，`WHITENOISE_AUTOREFRESH=False` | 在认证之后 | Phase 2：`waitress_wn_noauto` 12/12，PASS | 启动时通过 finders 建立索引，启动后新增或修改的静态文件要重启才能正确提供 |

- 后两种姿态下，每页 61–68 个静态请求都经过 BasicAuth 与 Django 中间件，这部分开销已计入 B6 的页面 p95。
- 生产配置（`DEBUG=False`、`collectstatic`、manifest storage、WhiteNoise 压缩）下的性能没有测量。

## 5. 精确版本（B8）

| 包 | 版本 | 说明 |
|---|---|---|
| `waitress` | `3.0.2` | 推荐：唯一通过 C5 且静态文件在认证之后的 production server；需要预绑定 socket、`run()` 放在 `serve-http` 线程、`flush` 收尾、`channel_request_lookahead=1`（断开探测） |
| `cheroot` | `11.1.2` | 不推荐：Windows 上 keep-alive 每个请求约 61 ms，停止时有无时限 join |
| `jaraco.functools` / `more-itertools` | `4.6.0` / `11.2.1` | 只是 cheroot 的依赖；不选 cheroot 时不需要 |
| `a2wsgi` | `1.10.10` | 不推荐：B4/B5 FAIL（R17–R19） |
| 不变 | `Django==6.0.7`、`whitenoise==6.12.0`、`starlette==1.10.0`、`fastapi==0.162.2` | 同 S0 §4 |

推荐组合（owner 2026-11-11 改定；终测宿主 `s0b_host.py` SHA-256 `e6e1707d…`）：
- waitress 3.0.2，threads 14；`wn-noauto`（WhiteNoise 在 BasicAuth 之后，`WHITENOISE_AUTOREFRESH=False`）；custom 桥（由 AIB-2 核心 wheel 提供，R19）。
- `/ai` 分离准入：流 4 / 短请求 4，超限立即 503 + `Retry-After: 2`，不排队。`/ai/*` 固定顺序：Host 校验（400）→ 请求完整性 → 认证（401，不占名额）→ 资产直出或准入 → 路由（L0 waitress / L1 适配器的分层与请求体上限见 §4.2 第 6 项）。AI Base UI 资产在认证之后按构建时清单直出（GET/HEAD，`Cache-Control: private, max-age=31536000, immutable`、ETag、`nosniff`，清单外 404），不经过 loop，不计入准入。
- 宿主以 127.0.0.1 + `SO_EXCLUSIVEADDRUSE` 预绑定，调用 `create_server(app, sockets=[sock], threads=14, channel_request_lookahead=1)`，`run()` 在非 daemon 的 `serve-http` 线程上；`flush` 收尾；主线程上的等待切片 ≤ 0.5 s；停止中收到第二个信号时 `os._exit(130)`；显式退出（`close_all()` → `logging.shutdown()` → flush → `os._exit`）；停止总预算 10 s，按进程实际退出计算（各段见 §4.2 第 9 项）。执行中的 project run 不在 10 s 内：`serve` 看门狗 660 s，Docker `--stop-timeout 690`。

推荐组合已作为整体运行（新配置终测，§3.11）：冒烟 19/19，M1–M6 全部 PASS，所有终测证据来自同一个宿主 SHA。旧配置（threads 12、短请求上限 2、UI 资产计入短请求名额并经过 loop）的结果保留在 §3.10。

## 6. 复现命令（在仓库根目录执行；`$py = '.tmp\s0-coinstall\venv\Scripts\python.exe'`）

```powershell
& $py -m pip install waitress==3.0.2 cheroot==11.1.2 a2wsgi==1.10.10; & $py -m pip check   # B0
$p = 8850; foreach ($s in 'devserver','waitress','cheroot') { foreach ($b in 'custom','a2wsgi') {
  & $py -I .tmp\s0-coinstall\s0proj\s0b_checks.py combo --port $p --server $s --bridge $b --name "b14-$s-$b"; $p++ } }   # B1–B4
foreach ($s in 'devserver','waitress','cheroot') { & $py -I .tmp\s0-coinstall\s0proj\s0b_checks.py portinuse --port 8850 --server $s --name "b1-portinuse-$s" }
foreach ($s in 'devserver','waitress','cheroot') { foreach ($t in 'stop_file','ctrl_break','sigint') {
  & $py -I .tmp\s0-coinstall\s0proj\s0b_checks.py b5 --port 8850 --server $s --bridge custom --trigger $t --name "b5-$s-custom-$t" } }
foreach ($s in 'devserver','waitress','cheroot') { & $py -I .tmp\s0-coinstall\s0proj\s0b_checks.py b5 --port 8850 --server $s --bridge a2wsgi --trigger stop_file --name "b5-$s-a2wsgi-stop_file" }
& $py -I .tmp\s0-coinstall\s0proj\s0b_keepalive.py                                   # logs\s0b\keepalive.json
& $py -I .tmp\s0-coinstall\s0proj\s0b_perf.py run --arms baseline,dev_sfh,dev_wn,waitress_sfh,waitress_wn,waitress_wn_noauto,cheroot_sfh,cheroot_wn,cheroot_wn_noauto,cheroot_wn_ei001 --blocks 4 --per-block 15 --warmup 10 --per-block-overrides cheroot_sfh=2,cheroot_wn=2,cheroot_wn_noauto=2,cheroot_wn_ei001=4 --warmup-overrides cheroot_sfh=2,cheroot_wn=2,cheroot_wn_noauto=2,cheroot_wn_ei001=2 --modes seq,c4 --out b6-phase1.json --log-prefix b6p1
& $py -I .tmp\s0-coinstall\s0proj\s0b_perf.py run --arms baseline,waitress_wn_noauto,waitress_wn,dev_wn --blocks 4 --per-block 40 --warmup 10 --modes seq,c4 --out b6-phase2.json --log-prefix b6p2
& $py -I .tmp\s0-coinstall\s0proj\s0b_perf.py diag --arm waitress_wn_noauto --blocks 4 --per-block 20 --warmup 10 --out b6-diag-streams.json --log-prefix b6diag
foreach ($v in 'devserver custom auto','devserver custom off','waitress custom auto','waitress custom off','waitress a2wsgi auto') { $s, $b, $o = $v -split ' '
  & $py -I .tmp\s0-coinstall\s0proj\s0b_starlette_check.py --port 8853 --server $s --bridge $b --probe $o }   # §3.5
$t = 'ui_web/tests/test_dashboard_shell_browser.py','ui_web/tests/test_report_query_browser.py','ui_web/tests/test_report_authoring_browser.py','ui_web/tests/test_report_daily_ui_browser.py','-q','--tb=short','-p','no:cacheprovider','-rA'
& $py -I .tmp\s0-coinstall\s0proj\s0b_browser_runner.py --mode stock $t --junitxml=.tmp\s0-coinstall\logs\s0b\b7-stock-junit.xml   # B7
& $py -I .tmp\s0-coinstall\s0proj\s0b_browser_runner.py --mode candidate --static wn-noauto $t --junitxml=.tmp\s0-coinstall\logs\s0b\b7-candidate-junit.xml
& $py -I .tmp\s0-coinstall\s0proj\s0b_b5s.py --out b5s.json                         # 第 1 项；8851 的 3 个用例随后用下一行重跑
& $py -I .tmp\s0-coinstall\s0proj\s0b_b5s.py --cases b5s-devserver-503probe,b5s-devserver-stopfile,b5s-cheroot-stopfile --out b5s-rerun.json
& $py -I .tmp\s0-coinstall\s0proj\s0b_portbind.py matrix; & $py -I .tmp\s0-coinstall\s0proj\s0b_portbind.py host   # 第 3 项
& $py -I .tmp\s0-coinstall\s0proj\s0b_sig2.py driver --events break,c --reps 2 --hold 10 --slice 0.5 --out sig2.json   # 第 4 项
& $py -I .tmp\s0-coinstall\s0proj\s0b_b9.py admission --port 8850 --out b9-admission.json   # 第 2 项 (a)(b) 与第 5 项
& $py -I .tmp\s0-coinstall\s0proj\s0b_perf.py run --arms baseline,waitress_wn_noauto,b9_sat_t8,b9_sat_t12 --blocks 4 --per-block 40 --warmup 10 --modes seq,c4 --out b9-perf.json --log-prefix b9p   # 第 2 项 (c)
# 签核补测（§3.10）：宿主参数由驱动按 M 参数生成；证据都在 logs\s0b\rec，各 JSON 记录脚本 SHA-256
$rec = '.tmp\s0-coinstall\logs\s0b\rec'
& $py -I .tmp\s0-coinstall\s0proj\s0b_sig2.py driver --target host --events break,c --reps 2 --phases drain,flush --ports 8847,8848,8849,8851,8852,8853,8854,8855 --out-dir $rec --out m1-sig2-host.json   # M1
& $py -I .tmp\s0-coinstall\s0proj\s0b_b5s.py --cases rec-flush-stopfile,rec-flush-ctrlbreak,rec-flush-ctrlc,rec-slow-flush,rec-noread-flush --sequential --out-dir $rec --out m4-b5s.json   # M4
& $py -I .tmp\s0-coinstall\s0proj\s0b_m5.py --port 8858 --rounds 5                     # M5 → m5-slots.json
& $py -I .tmp\s0-coinstall\s0proj\s0b_browser_runner.py --mode candidate --server waitress --static wn-noauto --bridge custom --threads 12 --ai-limit-mode split --ai-stream-limit 4 --ai-short-limit 2 --finish flush --tag t12 --out-dir $rec $t --junitxml=$rec\b7-candidate-t12-junit.xml   # M3
& $py -I .tmp\s0-coinstall\s0proj\s0b_perf.py run --arms baseline,rec_t12,rec_t12_sat,waitress_wn_noauto --blocks 4 --per-block 40 --warmup 10 --modes seq,c4 --out b6b9-rec.json --log-prefix rec --log-dir (Resolve-Path $rec) --hold-short-interval 1 --hold-probe-interval 5   # M2
& $py -I .tmp\s0-coinstall\s0proj\s0b_m2_verdict.py; & $py -I .tmp\s0-coinstall\s0proj\s0b_m2_outliers.py   # M2 判定 → m2-verdict.json；离群诊断 → m2-outliers.json
& $py -I .tmp\s0-coinstall\s0proj\s0b_revbind.py run --port 8850 --reps 3 --out-dir .tmp\s0-coinstall\logs\s0b\retest-t12   # 上一轮补测 (a)（M1 改动之前的宿主）
# 新配置终测（§3.11）：步骤 A 用旧宿主 f4aa2dcc…（在步骤 B 改宿主之前运行）；其余都用冻结后的宿主 e6e1707d…；证据都在 logs\s0b\final，各 JSON 记录脚本 SHA-256
$fin = '.tmp\s0-coinstall\logs\s0b\final'
& $py -I .tmp\s0-coinstall\s0proj\s0b_tailsplit.py --runs 5 --port 8840               # 步骤 A → stepA-tail.json
& $py -I .tmp\s0-coinstall\s0proj\s0b_final_smoke.py --port 8841 --out-dir $fin       # 冒烟 → stepB-smoke.json
& $py -I .tmp\s0-coinstall\s0proj\s0b_sig2.py driver --target host --events break,c --reps 2 --phases drain,flush --ports 8847,8848,8849,8851,8852,8853,8854,8855 --out-dir $fin --out m1-sig2-host.json   # M1（第 2 个信号在第 1 个发出后 1.0 s）
& $py -I .tmp\s0-coinstall\s0proj\s0b_b5s.py --cases rec-flush-stopfile,rec-flush-ctrlbreak,rec-flush-ctrlc,rec-slow-flush,rec-noread-flush --sequential --out-dir $fin --out m4-b5s.json   # M4
& $py -I .tmp\s0-coinstall\s0proj\s0b_m5.py --port 8857 --rounds 5 --out-dir $fin     # M5 → m5-slots.json
& $py -I .tmp\s0-coinstall\s0proj\s0b_revbind.py run --port 8850 --reps 3 --name m6-revbind --out-dir $fin   # M6
& $py -I .tmp\s0-coinstall\s0proj\s0b_perf.py run --arms baseline,rec_t14,rec_t14_sat,waitress_wn_noauto --blocks 4 --per-block 40 --warmup 10 --modes seq,c4 --out b6b9-final.json --log-prefix final --log-dir (Resolve-Path $fin) --hold-short-interval 1 --hold-probe-interval 5   # M2（实际从 s0proj 目录运行，--log-dir ..\logs\s0b\final）
& $py -I .tmp\s0-coinstall\s0proj\s0b_browser_runner.py --mode candidate --server waitress --static wn-noauto --bridge custom --threads 14 --ai-limit-mode split --ai-stream-limit 4 --ai-short-limit 4 --finish flush --tag t14 --out-dir $fin $t --junitxml=$fin\b7-candidate-t14-junit.xml   # M3
& $py -I .tmp\s0-coinstall\s0proj\s0b_final_verdicts.py m2; & $py -I .tmp\s0-coinstall\s0proj\s0b_final_verdicts.py m3   # → m2-final-verdict.json、m3-final-compare.json
& $py -I .tmp\s0-coinstall\s0proj\s0b_final_window.py; & $py -I .tmp\s0-coinstall\s0proj\s0b_final_shacheck.py   # 冻结之后新增的只读分析 → m2-window-attrib.json、sha-verify.json
& $py -I .tmp\s0-coinstall\s0proj\s0b_report.py --fill                               # 由原始 JSON 生成原报告中的表格；它会改写本报告，而补测与终测各节为手写，不要重跑
```

## 7. 未决风险

1. custom 桥只有 spike 质量（约 450 行），只在本机 Windows、3 种 server 上验证过。快速断开检出依赖 server 特定探测；关闭探测后 devserver 上空闲流要 3.80 s 才检出。需要由 AIB-2 核心 wheel 实现并测试（R16、R19）。
2. AI Base 真实聊天流路由没有走通（需要后端与会话配置，且不得调用真实模型），用同类 Starlette 端点代替。终止事件（R10、R15）要等 AI Base 改动后再验证。
3. 停止预算按进程实际退出计算（owner 决定 2）：终测中触发到解释器进程退出最长 6.692 s（M4 不读用例）。
   - 走看门狗时会略超 10 s（约 0.05 s；终测中没有触发）。终止宽限到期取消流的路径在终测宿主上没有走到。
   - 显式退出跳过 atexit 与解释器收尾，正确性依赖 R24（`start_blocking` 退出时已 flush 并关闭全部持久资源）。spike 只检查了退出码、`project_runtime_stopped` 行与停止各步的时刻，没有逐项检查 AI Base 的持久资源。
   - 执行中的 project run 按 owner 决定 3 不计入 10 s（620 / 660 / 690 s，启动脚本 ≥ 15 s 后按 PID 强制结束，下次启动时由恢复流程标记）；spike 中没有执行中的 run，没有测。
4. 生产配置（`DEBUG=False`、`collectstatic`、manifest storage）下的性能没有测量；C5 只在 DEBUG=True 下测得。
5. 推荐组合已在终测中作为整体运行（§3.11），但每项只运行了一次。threads 8 饱和时 1 个单元格为 1.23×，原因没有证实。
6. 共享机器噪声：B9(c) 那次运行的 seq 基线 p95 为 162–277 ms，高于 Phase 2 的 142–236 ms。同一配置 `waitress_wn_noauto` 的最大比值在 Phase 2 为 1.04×，在 B9(c) 为 1.07×；threads 8 饱和时有一个单元格到 1.23×。M2 中三个 waitress arm（包括没有 AI 负载的对照 arm）都有 ≥ 100 ms 的访问日志间隔，最长 2060 ms；基线进程 8840 在 12:17:36–37 约 2 s 没有写出访问日志（该单元格 max 4864 ms）。单个单元格的尾部波动可能接近门限。终测期间，Metrics 侧运行过 pytest 与读文件的短 python 进程（复签据会话日志确认的窗口见偏差第 10 项），并修改了仓库文件（17:09–17:14）。离群 #1（50.96 ms）落在 17:06:15–17:06:39 的 pytest 窗口内（已确认重叠；它同时是 hold 的第一次调用，原因不能单独判定）；离群 #2（70.78 ms，17:21:24.321）不在任何已确认窗口内；驱动 ticker 的 90.57 ms 停顿不在已确认的窗口内，原因无法判定。复签认为这些活动不改变任何判定；残余是 baseline 进程没有 ticker 与逐请求样本，只落在 baseline 块上的亚秒级突发不能严格排除（§3.11）。
7. 端口：8851 上出现过一次无法解释的 exit 4（当时观察为 10013，未留存）。终测 M6 中，宿主独占 127.0.0.1 时，另一进程在 127.0.0.1 上用 `SO_REUSEADDR`、默认选项、`SO_EXCLUSIVEADDRUSE` 绑定，分别得到 10013、10048、10048（各 3 次）。用 `0.0.0.0` + `SO_REUSEADDR` 只 bind 则 3/3 成功；按 Windows 文档，它得到的是 127.0.0.1 以外的接口，发往 127.0.0.1 的请求全部由宿主应答（§3.11）。`::` 与在通配地址上 listen 受“只用回环”规则限制，没有测。本机动态端口范围覆盖 8840–8859。
8. POSIX 没有测：SIGTERM（Windows 上无法由其他进程送达）、POSIX 的 `SO_REUSEADDR` 语义、非 Proactor loop。
9. 超时不等于未开始（R21）：门面超时后，提交可能已经产生副作用；本次只确认了现象，幂等键或对账方案需要设计。
10. Django 原生流在停止时会被截断（§3.4）；改为在迭代器 `close()` 时减计数后，需要重新验证排空。
11. 短请求尾延迟：B9 (b) 的门限（全部 < 100 ms）对单次停顿敏感。
    - 旧配置 M2 中 2/2092 个 ≥ 100 ms，原因无法判定（§3.10）。
    - 终测 M2 中 1944 个全部 < 100 ms。最大 70.78 ms，不在已确认的 Metrics 侧窗口内，原因无法判定；其次 50.96 ms，落在 17:06:15–17:06:39 的 pytest 窗口内，同时是 hold 的第一次调用，原因不能单独判定。
    - 宿主的两次 gen2 GC（218.65 ms、194.6 ms）都没有与短请求重叠；若与短请求重叠，该请求会超过 100 ms（推断）。
12. flush 截止时丢弃数据：不读或极慢的客户端在 t0 + 6.5 s 时丢失未写出的数据，收不到终止事件（M4 不读用例 7,803,542 B）。
13. 终测宿主中有两种响应先于认证返回：停止排空时对所有路径返回的 503（固定文本，也先于 Host 校验），以及 `/ai`（无斜杠）的 308。两者都不含 AI 内容，但与 owner 固定顺序（Host → 完整性 → 认证 → … → 路由）不完全一致。另外，请求体上限 16 MiB 是 spike 的占位值。`serve` 实现时需要确认这几点。waitress 在调用应用之前已读完并缓冲请求体（> 512 KiB 落临时文件），应用层 413 不限制资源；真正的上限要配置 waitress `max_request_body_size`（默认 1 GiB，判定为 `>=`），终测宿主没有配置（复签 N1；分层见 §4.2 第 6 项）。

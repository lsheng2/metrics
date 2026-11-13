# AIB-2 W1 复核记录

日期：2026-11-13。结论：AIB-2 按授权提示词第 4 节第 2 条停在 W1.HOST（HEAD `ac061ee`），阻塞成立。design §4 第 5 步要求
WSGI 线程读取请求体时受短请求总时限约束，而 Waitress 把较大的请求体写入临时文件，同一线程上的文件读取无法抢占；回执列出的
四个方案都要 owner 取舍。同一检查点还有两处需要 owner 决定：正向资产断言在 W1 没有资产生产者；ASGI 模式下"loop 卡死仍在
时限内返回 504"无法实现。owner 于 2026-11-13 作出三项决定（第 3 节），W1.HOST 据此恢复。回执另有六项与决定无关的缺陷
（第 2.4 节），须在 HOST 终审之前修复。

第二轮（第 6–9 节）：AIB-2 提交决策记录 D/E 后，按决定提示词第 7 节第 1 条再次停在 W1.HOST（`069ce23`），理由是
DiagnosticsSnapshot 没有公开的 loop lag 等观测字段。复核认定这是 W0 遗漏：W0 只冻结了类型名，字段从未定义，而 design §8、
§4 第 7 步与三份 spec 早已要求这些观测。owner 同日作出 OD-W1-4（第 7 节）；复核另记两项缺陷 W1-F7、W1-F8（第 7.3 节）。

本记录是 `tasks.md` 0.6 的进展证据，0.6 仍不勾选。之后各轮 W1 复核续写在本文件。

## 1. 被复核的提交

- AI Base worktree：`C:/Users/lsheng2/orca/workspaces/Report_creater_agent/extract-embeddable-agent-runtime`，分支
  `codex/extract-embeddable-agent-runtime`，W0 r2 基线 `fc4db2f22bf49ebaddaa582b2b3d885189c317aa`。
- 授权：`handoff-prompt-aib2-w1-w4.md`，引用 Metrics `d48943a27d701fc5bc96911196536a4d076c2b9c`（`aib2-w0-acceptance.md`
  第 7、9 节）。
- 阻塞快照：HEAD `ac061ee59b62b92f64c91d3283ea10dfbcc3c76c`，回执 `openspec/changes/extract-embeddable-agent-runtime/w1-receipt.md`。
- 复核方式：Metrics 只读，没有在 AI Base 侧运行测试。读取了回执与证据（`evidence/w1/host-fix-testkit-blocked.md`、
  `host-fix-lifecycle-c84c8c8-review.md`、`blocked-source-summary.json`）、design、validation-matrix、两份 spec delta、
  tasks.md、`plan.json`、`check-planning.ps1` 与相关源码，以及 AI Base venv 中 waitress 3.0.2 的源码。复核前后
  `git status --porcelain` 都为空。
- 主 checkout `D:\AIGC\Report_creater_agent`：回执（:184-186）说明 controller 与 reviewer 曾因路径错误短暂改动主
  checkout，误改的文件已移除或移走。只读核对：主 checkout 在 `main` 的 `5757c9c`，没有 stash，唯一的未跟踪内容是
  2026-11-09 生成的 `services/app-service/report_creator_agent_app_service.egg-info/`，早于 W1，没有 W1 期间的残留。
- 下文 AI Base 文件的行号以 `ac061ee` 为准，waitress 的行号以 3.0.2 为准。

## 2. 回执摘要与核对

### 2.1 状态

- 节点（`plan.json`）：8 个 complete（PLAN、PLAN.R、GATE.MAIN、GATE.V21、W0.FREEZE、GATE.W0R、W1.VA `69185bd`、
  W1.CORE `dfe711a` 与收尾 `0dab2d2`）；W1.HOST 为 in_progress，处于阻塞；其余 23 个 pending。
- G1–G6：`deb2fb7` 一次修复，只读核对全部闭环。G1 失效的 `#12-…` 锚点改为 `#13-archived-standalone-requirement-disposition`；
  G2 检查本地锚点，并有 RED 用例；
  G3 的 README 与 inventory 改指 design §10、§11；G4 由 W4.REMOVE 发布到 docs/common、W4.QUAL 切换 V01；G5 删除旧恢复词，
  改指注册表 Retry 列；G6 改为 "before starting the runtime or server (the listening socket may already be bound)"。
- controller 全量源码回归：212 passed、8 failed、3 skipped，用时 134.25 s。HOST 还没有已安装 wheel 上的资格结果。
- 漂移检查：CORE 已安装 wheel 上 checked 495、matched 437、pending 58、additions 4，没有失败；最新 HOST 预检为 531、523、
  7、48，因 ai_logs 见证失败判 FAIL。design §10、§11 原有的 647 行保持原顺序，这一段现共 980 行（含新增）。
- 没有发布 W1 dev wheel。`4badf64` 的候选 wheel（SHA-256
  `51902599e87ed37c39c4882f549f03796a7273cf0e1e19e5a51262b0f292ff54`）早于阻塞修复，回执 :203-204 明确不能用作 W1 冒烟或
  发布交接。

### 2.2 八个失败

三个包装测试（`test_host_consistency_suite.py:127`，`assert_outcomes(passed=required + 1)`，加 1 是包来源检查）的 required
分别为 13、14、27：15 个必需的断言族在两种托管方式下共 27 个适用用例（asgi 13、blocking_wsgi 14）。包装测试失败时只给
计数。证据只列出 worker 较早一次复现中的 4 个失败用例（`host-fix-testkit-blocked.md:46-53`），controller 终跑的 asgi
包装少 2 个通过、双模式少 5 个，因此有 1 个 asgi 用例没有归因。

| # | 用例 | 直接原因 | 处理 |
| --- | --- | --- | --- |
| 1 | `test_shipped_suite_runs_against_public_runtime_hosts[asgi]`（12/14） | manifest；另 1 个 asgi 用例未归因 | OD-W1-2；W1-F4 |
| 2 | 同上 `[blocking_wsgi]`（13/15） | manifest；`loop_lag_assets` | OD-W1-2 |
| 3 | 同上 `[asgi blocking_wsgi]`（23/28） | manifest ×2；`loop_lag_assets`；`w1_short_timeout[blocking_wsgi]` 的 504 竞态；另 1 个未归因（按第 1 行推断为同一 asgi 用例） | OD-W1-2；W1-F1；W1-F4 |
| 4–5 | `test_real_runtime_negative_controls[asset_cache-w1_manifest_asset_boundaries-invalid asset cache policy-asgi]` 与 `…-blocking_wsgi]` | 变异执行之前就因资产缺失失败 | OD-W1-2 |
| 6–7 | V01 的 `test_preliminary_host_complete_definition_surface_matches_design_now`、`test_logs_iterator_contract_uses_real_pytest_lifecycle_not_iterator_value` | `fixture ai_logs lifecycle pytest/finalization incomplete`，源于 1–3 | OD-W1-2；W1-F5 |
| 8 | `test_wsgi_adapter.py::test_actual_waitress_supports_memory_and_spilled_bodies[True]` | BytesIO 白名单草案（`_internal/http/bodies.py:55-58`）让 spill 路径返回 500 | OD-W1-1 |

### 2.3 核对结论

1. **阻塞成立。**
   - design §4 第 5 步（:369-373）要求在 WSGI 线程上读取请求体，并写明读取使用剩余的短请求时限（"slow input cannot wait
     forever"）；第 7 步（:378）规定短请求只有一个总时限；spec `synchronous-runtime-host` :143 要求所有 `wsgi.input` 读取
     都在 WSGI 线程上。
   - 请求体超过 `inbuf_overflow`（默认 524288，`adjustments.py:220`）时，Waitress 把它写入 `TemporaryFile`
     （`buffers.py:115-117`），同一线程上的文件读取不能被抢占。
   - 同步的 `read` 接口没有时限或取消参数（回执 :21-24），读取前后检查时钟也无法打断已阻塞在系统调用中的读取。
   - BytesIO 白名单把合法的 spill 请求变成 500，不能接受。回执列出的四个方案（:34-46）都改变契约或 I/O 拓扑，按授权
     第 4 节第 1、5 条须由 owner 决定：1 合作式时限加宿主进程看门狗；2 保留硬时限，另设明确归属的 I/O 边界或可取消的
     读取器；3 只支持纯内存缓冲；4 维持现契约并继续阻塞（回执的建议）。
2. **慢客户端到不了应用层。**
   - Waitress 在 `channel.py:224` 判断 `request.completed` 之后才在 :236 调用 `add_task`；chunked 请求也是完整接收后才派发。
   - `task.py:553` 把已缓冲的 body 流作为 `wsgi.input`，:555 设置 `wsgi.input_terminated`。
   - 所以应用读到的 `wsgi.input` 只来自本机内存或本机临时文件。慢客户端只占 server 的 channel（受 `channel_timeout` = 120、
     `connection_limit` = 100 约束），不占 WSGI 线程，也不占运行时名额。剩下的只有本机磁盘读卡死，属于整机故障。
   - Metrics design 决策 1 的 L0 已记录这一事实。这是 OD-W1-1 的依据。
3. **资产生产者排在 W3。** W1.HOST 拥有资产的消费方（`ui.asset_url` 与资产直出），W3.UI 拥有
   `packages/runtime/src/ai_base_runtime/assets/`（tasks.md :151）；资产加载器固定读取包内的 `assets/manifest.json`
   （`_internal/http/assets.py:68-70`）。W1 没有资产，正向资产断言在 W1 不可能通过。漂移检查（validation-matrix :443-448）
   已有"负责节点未完成即计 pending"的机制，一致性套件没有对应机制。回执没有伪造资产，也没有 skip，处理正确。这是 OD-W1-2
   的依据。
4. **ASGI 下"loop 卡死也在时限内返回 504"无法实现。** design §4 第 7 步（:377-381）与 V14（validation-matrix :155）不区分
   托管方式。asgi 模式下 server 与运行时共用一个 loop，loop 完全卡死时没有代码能在时限内执行（testkit 报告 Gap 5，
   `host-fix-testkit-blocked.md:170-174`）；blocking_wsgi 下 WSGI 线程独立于 loop，可以做到。这是 OD-W1-3 的依据。
5. **注册表不用改。** §11.3 的 `http_request_timeout`（:1304，"Total short HTTP/body-reading deadline expired"，504）与
   `internal_error`（:1272，500）已覆盖三项决定涉及的全部结果；§10 也不新增取值。

### 2.4 与决定无关的缺陷

| 编号 | 缺陷 | 位置与证据 | 修复要求 |
| --- | --- | --- | --- |
| W1-F1 | 504 竞态：loop 一侧到截止时刻发出 504（`_internal/http/app.py:271-273`），WSGI 一侧在最后一次有界等待中取到这条响应开始（`bridge.py:150-152`）并调用 `start_response`；迭代响应体时 `_next_message` 再次检查同一截止时刻，把 `TimeoutError("HTTP request deadline expired")` 抛给 Waitress，Waitress 把响应换成 500 | `_internal/wsgi_support/bridge.py`（`wait_start` :94、`__iter__` :107、`_next_message` :143-149）；回执 :173-174；`host-fix-testkit-blocked.md:48-50`（`w1_short_timeout[blocking_wsgi]`） | 每个请求只交付一个完整响应；504 一旦开始就完整交付，不再检查时限；内部 `TimeoutError` 不传给 server。屏障测试修复前 RED、修复后 GREEN |
| W1-F2 | 复核 P1：调用方在 `start_runtime()` 返回之前中断时（`future is None`），`blocking.py:132` 取 `clean_stop_result()`，:140 丢弃 `worker.close_loop()` 的返回值，:141-146 再次发布"干净"的 `StartupFailure` | `evidence/w1/host-fix-lifecycle-c84c8c8-review.md:12-14` | 合并 `close_loop` 的结果；join 超时时发布不完整的 `StopResult`（含 `runtime_loop`、`loop_join_timeout`、`stop_timeout`）。测试在 `start_runtime()` 返回之前中断，并强制 `close_loop` 超时 |
| W1-F3 | 复核 P2：调用方在截止前已观察到就绪，`blocking.py:97` 的 `worker.commit_running(start_deadline)` 却因调度延迟超时（`blocking_support/worker.py:48-49`），异常被 `blocking.py:67-70` 捕获，经 `startup_reason_code`（`lifecycle_startup.py:40`）改判为 `startup_failed` | 同上 :33-38 | commit 之前显式完成判定：判为过期时按超时回滚并抛 `RuntimeStartTimeout`；判为就绪时，commit 不能因调度慢把结果改成 `startup_failed`（从构造上排除，或映射到已判定的结果并附真实的回滚记录）。屏障测试：截止前已观察到就绪，但 `_commit_running` 被拖过截止 |
| W1-F4 | 1 个 asgi 用例未归因；一次全量快照观察到 ASGI teardown 问题 | 第 2.2 节；回执 :177-178 | 按根因修复，不放宽断言 |
| W1-F5 | V01 的 ai_logs 生命周期见证失败 | 回执 :130 | 源于失败 1–3。OD-W1-2 之后，pending 用例也必须走完完整的夹具生命周期，见证本身不放宽 |
| W1-F6 | testkit 报告 Gap 4：helper 不能证明 FD、task、queue 的基线与响应缓冲上限 | `host-fix-testkit-blocked.md:165-169` | V12、V13 的既有义务，W1.R 之前补齐。Gap 4 中"阻塞的临时文件读取被取消或 join"一项在 OD-W1-1 下不再适用（不设读线程） |

另有两个开放项：

- lifecycle 与 blocking 中的 stage placeholder 和 import-unavailable 路径还没有被确认为最终 API 行为（回执 Deviations）。
  W1.R 之前逐一定性：属于后续节点的，列出负责节点；属于 W1 公开表面的，实现为最终行为。V01 的签名比对不能靠
  placeholder 通过。
- A6 的类别表（AI Base design :896-905）只定义审批、tool 与认证失败三类事件；按 design :859-861，session 与 run 事件在
  W1.CORE 省略，生产者属于 W2，类别届时追加。Metrics tasks 2.3 要记录会话事件，W2 回执须列出新增的类别与投递方式。

## 3. owner 决定（2026-11-13）

三项决定都不改 design §10、§11 的原有内容，不新增 §10 取值、公开 API、配置项或 code。

### OD-W1-1：WSGI 请求体按合作式时限读取

- 宿主前提：`blocking_wsgi` 的 server 在调用应用之前已完整接收并缓冲请求体（包括 chunked）。
- 读取：在 WSGI 线程上分块读取，块大小是私有常量；首次读取之前、每两块之间与派发之前，都检查同一个绝对截止时刻。到期时
  返回 504 `http_request_timeout`，不调用 handler，名额只释放一次。
- 进行中的单次读取不抢占：越过截止时刻的读取完成后返回 504，不能返回 200 或 500。
- 删除类型白名单，改为按行为校验：`read` 必须返回 `bytes`，长度不超过请求的长度；违反时返回 500 `internal_error`，不调用
  handler。已有的长度与截断处理不变。ASGI 的请求体读取保持硬时限。
- 不新增配置、API、code、watchdog、读线程或 observer timeout；短请求时限仍是 1.0 秒。
- 理由（对照回执 :34-46 的四个方案）：
  - 方案 2 的硬时限要另设读线程：超时返回时读取仍在进行，按回执 :41 不能当作已结束，线程与资源都要纳入 R24 清点；
  - 方案 3 要把 `inbuf_overflow` 提到 N+1，放大内存成本，并放弃现有的临时文件路径；
  - 方案 4 维持现契约继续阻塞，但同步文件读取没有时限或取消参数（回执 :21-24），同一线程上不存在合规的读取方式；
  - 采用方案 1，但不设运行时 watchdog：慢客户端到不了应用层（第 2.3 节第 2 条），剩下的本机磁盘读卡死属于整机故障，
    由宿主的停止看门狗兜底（Metrics 决策 3 的两段式看门狗）。
- 验收：
  - 真实 Waitress 下，内存路径与 `inbuf_overflow=1` 的 spill 路径都返回 200；超过上限时两条路径都在 handler 之前返回 413。
  - 注入的 `wsgi.input`：块间到期、首次读取之前到期（`read` 调用 0 次）、单次读取越过截止，都返回 504；返回非 `bytes` 或
    超长时返回 500。
  - 随 wheel 发布的一致性套件新增 `blocking_wsgi` 前提断言：客户端只发送部分请求体并超过时限，其间 handler 未被调用、
    在途数为 0；补齐请求体后返回 200。
  - ASGI 慢请求体在时限内返回 504（已有用例未覆盖时补上）。
- spec：在 `synchronous-runtime-host` 的 "Core WSGI bridging is bounded and preserves request meaning" 正文中写明宿主前提，
  并新增两个场景：已缓冲请求体的合作式读取；慢客户端期间不调用 adapter、不占名额。

### OD-W1-2：依赖资产生产者的验收改排到 W3

- validation-matrix 新建"生产者依赖断言"表，作为唯一数据源。列为：用例、生产者节点（W3.UI）、精确的 pending 诊断、
  清零关口（W3.R）。
- 登记的用例：`w1_manifest_asset_boundaries` 拆分后的正向部分（两种托管方式）；`w1_wsgi_loop_lag_assets[blocking_wsgi]`；
  两个 `asset_cache` 负向对照。
- 判定沿用 V01 读取节点状态的机制：
  - W3.UI 未完成时，登记用例必须以登记的诊断失败，计为 pending；通过、因其他原因失败或没有被选中，都判失败；
  - W3.UI 完成后，登记用例必须全部通过，pending 为 0。
- 适用于三个包装测试、两个负向对照与 V01 的两个见证。见证不放宽，pending 用例同样要走完完整的夹具生命周期。
- 包装测试失败时必须列出内层用例名，不能只给计数。
- 诊断文本只陈述事实：删去 "parent must package a labeled component fixture or provide the W3 asset producer" 这类建议
  （`testkit/host_support/_asset_assertions.py:19-20`），也不写 W1、W3 等节点名。
- 不依赖真实资产的拒绝类断言在 W1 就必须在两种托管方式下通过：401；traversal、编码绕过与未列出的路径返回 404；不支持的
  方法。目前与正向检查放在同一个 AssertionSpec 中的，要拆开。
- 正向行为在 W1 由 AI Base 仓库内的组件测试验收：以私有方式注入临时资源，不进入随 wheel 发布的 testkit。
- 禁止：skip 或 xfail；按资产是否存在切换适用性；在可移植夹具中覆盖私有 loader；伪造资产；inline fallback；新增公开的
  资产来源设置。
- 有 pending 的 wheel 不构成认证。
- tasks.md：W3.UI 负责产出满足登记表的资产；W3.R 在已安装的 wheel 上让两种托管方式全部通过，残留任何 pending 即判失败；
  W1.R 与 W2.R 允许 pending，但必须逐项列出。

### OD-W1-3：澄清 ASGI loop 卡死的语义

- 改写 design §4 第 7 步，按托管方式区分：
  - `blocking_wsgi`：WSGI 线程到截止时刻就停止等待，返回 504（运行时已不可用时返回 503）；loop 一侧的取消可能稍后送达；
  - `asgi`：server 与运行时共用一个 loop。loop 恢复之后、响应开始之前检查截止时刻，已过期的短请求返回 504，不返回迟到的
    成功；lag 快照记录这次卡顿（不小于阈值）。V02 的 100 ms slow-callback 门禁（validation-matrix :259-261）起预防作用。
- "loop 硬卡死且在时限内返回 504"只适用于 `blocking_wsgi`；它与 `asgi` 的组合按 V15 报告为不适用，写明 SKIP 原因。
  `asgi` 新增"卡顿后迟到返回 504，且 lag 被记录"的断言。V14 同步改写。
- spec：在 `embedded-agent-runtime` 新增 ADDED requirement（例如 "Short requests have one total deadline in both hosting
  modes"），覆盖 ASGI 慢请求体返回 504、卡顿后迟到返回 504、硬卡死不适用；validation-matrix 的 R23 行加入该 requirement。
  AI Base 可以调整放置位置，但须在回执中说明。

## 4. 对 Metrics 的影响

- 配置不变：线程 14，在途上限 4 与 4，短请求时限 1.0 秒，`max_request_body_size` = 8388609；`inbuf_overflow` 保持 waitress
  默认值。
- Waitress 3.0.2 满足 OD-W1-1 的宿主前提（第 2.3 节第 2 条）。更换或升级 WSGI server 时，除重跑 S0b 的 B1、B4、B5、B9 子集
  外，还要重跑宿主一致性套件（含先缓冲后派发的前提断言）。design 决策 1 与风险一节、spec 的一致性套件场景、tasks 0.6、1.1
  与 5.10 已同步。
- OD-W1-3 不影响 Metrics：Metrics 只声明 `blocking_wsgi`。
- W1、W2 的 dev wheel 冒烟中出现登记的 pending 诊断属于预期。W3.R 之前的任何 wheel 都不能作为 0.6 的认证证据。
- Metrics tasks 2.3 的会话审计事件依赖 W2 追加的 session 类别（第 2.4 节）。

## 5. 转交

上述决定由 owner 以 `handoff-prompt-aib2-w1-host-decision.md` 转交 AI Base，提示词引用的 `metrics_commit` 是写入本记录的
提交。AI Base 先单独提交"owner 决策记录"（只改 change 目录），再恢复 W1.HOST。原授权的停止条件、回报格式与范围仍然有效。

## 6. 第二轮：D/E 与再次停止（2026-11-13）

- 提交：D `bcf1fc690c99416ae792e7d8e3687bba327daf4d`（记录 OD-W1-1/2/3 的规划提交）、E
  `80c4de514702590709c3f55dc08e00567896867a`（证据提交）、停点 `069ce23432b4bc6f36d9eaf6fbeaa1917f838435`（"docs(common):
  record W1 diagnostic contract hold"）。AI Base 回报：D 的独立复核 P0–P3 为零；E 之后全量复跑通过，含 58 个负例与 9 个额外
  GREEN 用例。
- Metrics 只读复核：`check-planning.ps1` 退出码 0（32 个节点、28 份文档、40 个链接、118 个 changed paths）；
  `openspec validate --strict` 通过；复核前后 worktree 的 `git status --porcelain` 都为空；主 checkout 仍在 `main` 的
  `5757c9c`，唯一的未跟踪内容仍是第 1 节所列 egg-info。没有在 AI Base 侧运行产品测试。
- 节点：8 个 complete，W1.HOST 为 in_progress（停点），其余 23 个 pending。D/E 没有改产品代码，W1-F1…F6 全部 Open。
- 停止理由：W1.HOST 须满足 OD-W1-3 的"lag 快照记录卡顿"与 V14 的观测义务，而 DiagnosticsSnapshot 没有公开的 lag 等观测
  字段。决定提示词第 7 节第 1 条不允许用原授权 3.1 的公开新增落实三项决定，AI Base 据此停下，请 owner 指定已有观测接口或
  授权只读诊断字段与 §11 增补。停下是正确的。

## 7. OD-W1-4：诊断快照字段（owner 决定，2026-11-13）

### 7.1 定性：W0 遗漏，不是修改冻结契约

- W0（`fc4db2f`）冻结了观测义务与入口，没有冻结字段：
  - design :371、:373 要求短请求 p99/max 延迟与可观测的 loop-tick/lag 快照；:584 规定 `GET /ai/api/diagnostics` 与
    `runtime.diagnostics.snapshot(principal)` 提供 lifecycle、loop lag、在途与拒绝数、dropped-auth-audit 数，以及脱敏的
    依赖与模型可用性；:1334 把诊断改由这两个入口提供；
  - spec `synchronous-runtime-host` :189 要求在途数、拒绝数、短请求尾延迟与 loop lag 可观测；
    `standalone-app-service-security` :41-43 要求 Metrics 能取得 loop lag、在途与拒绝数和 dropped-auth-audit 数；
  - §11 中 `DiagnosticsSnapshot` 只作为 :840 的返回类型出现，没有字段声明。
- 现有 4 个字段是 W1.CORE A6 追加的（`069ce23` design :901-904）：3 个 audit outbox 字段与 `dropped_auth_audit_count`。
- 因此"冻结的 DiagnosticsSnapshot 只有四个审计字段"的前提不成立：字段从未冻结，而冻结的义务所需的字段缺失。补齐字段属于
  原授权 3.1 的增补（新增公开表面，在 §11 对应小节登记，标注节点与理由），不改 §10、§11 的原有内容。owner 以本决定授权该
  增补；决定提示词第 7 节第 1 条对本决定范围内的增补不适用，超出本决定的公开新增仍须停下。
- Metrics 自查：W0 接受记录（`e3c8a80`、`85dfa53`、`d48943a`）没有检查只作为返回类型出现在 §11 的类型是否有字段声明，
  漏看了这一项。之后复核冻结时，把"返回类型有字段声明或负责节点"列为检查项。

### 7.2 决定内容

总则：

- 只增补：W1.CORE 的 4 个字段不改；不改 §10；不新增配置项或 code；不新增 lifecycle 枚举或表示 HTTP 已关闭的字段。
- 新字段是 keyword-only、带默认值，排在 4 个字段之后。
- §11 只保留一处 `DiagnosticsSnapshot` 声明：移到新块 `# ai_base_runtime.spi, W1.HOST OD-W1-4 additions`，列出全部
  13 个字段，块前说明前 4 个来自 W1.CORE A6、后 9 个来自 OD-W1-4。不能保留两处：`contract_authority.py:363` 按 target
  写入，后一处会静默覆盖前一处。用 authority 解析确认 `diagnostics_fields` 为 13 个、`additions` 包含
  `DiagnosticsSnapshot`。
- 回执 Additions 表（`w1-receipt.md` :151）登记这次增补；W1.R 复核，W1.REPLAN 归类。

9 个新字段：

| 字段 | 类型与默认值 | 语义 |
| --- | --- | --- |
| `running_since` | `datetime \| None = None` | 进入 RUNNING 的 UTC 时刻，取自 `HostConfig.clock.utc_now()`（与 `AuditEvent.occurred_at` 用同一个 Clock）；运行时产出的快照必须设置 |
| `loop_lag_seconds` | `float = 0.0` | 最近一次完成的探针测得的 max(0, 实际唤醒 − 计划唤醒)，用 loop 的单调时钟；首次完成前为 0.0 |
| `loop_lag_max_seconds` | `float = 0.0` | 自 `running_since` 起的峰值，不重置 |
| `loop_stall_count` | `int = 0` | lag 不小于 `loop_lag_threshold_seconds` 的探针次数 |
| `stream_in_flight_count`、`short_in_flight_count` | `int = 0` | 当前在途数 |
| `stream_rejected_count`、`short_rejected_count` | `int = 0` | 累计值，只计 `http_admission_limited`（503 加 `Retry-After`）。准入之前的拒绝（400、401、308、资产，以及停止中或未运行的 503）不计；导航请求计入它实际所属的类别 |
| `short_request_latency_max_seconds` | `float = 0.0` | short 类名额从取得到归还的最长时长，是响应延迟的上界；单调时钟，覆盖所有结局，可在 `AdmissionLease` 内实现 |

- 校验：int 用 `type(x) is int` 且不小于 0；float 用 `type(x) is float`、有限且不小于 0；datetime 沿用 `_utc`。
- 探针：运行时自有的 asyncio task，不新增线程；按 `loop_probe_interval_seconds` 运行，随 lifecycle 启动，纳入 R24 停止
  清点（取消并等待）。卡顿 D 秒时，下一次探针测得的 lag 不小于 D 减 interval，所以测试的卡顿时长须不小于阈值加 interval
  再加余量（默认值下至少 0.15 秒，建议约 0.3 秒）。
- 可用性：快照由 `DiagnosticsFacade` 组装，只在 RUNNING 与 HTTP_CLOSED 时可用，其他状态抛 `RuntimeNotRunning`。async 门面
  补上状态检查（现在只检查 outbox 与 store，`_internal/lifecycle_stop.py:380-381`）；blocking 门面已按同一规则执行。
- HTTP 路由 `GET <root_path>/api/diagnostics`（design :610）：
  - 运行时自有路由，先于 App 路由解析；按 short 类准入；遵守 D3 顺序（401 先于 503）；认证与其他运行时路由相同，不新增
    角色模型；
  - 响应是 JSON 对象，键恰好是全部快照字段的 camelCase；时间为 ISO 8601 UTC 或 null；不含 secret、cookie、bridge key
    或 token；
  - `close_http()` 之后返回 503；HTTP 投影的 `shortInFlightCount` 包含诊断请求本身。
- 依赖与模型可用性不在本决定内：由引入依赖或模型的节点按 3.1 补齐，W1.REPLAN 指定负责节点。design §8 改为列出实际字段，
  "lifecycle" 由 `running_since` 与上述可用性规则表达。
- 不变式：
  - I1：`close_http()` 以 `completed=True` 返回后，`stream_in_flight_count` 为 0。`close_http` 的完成必须包含名额归还，
    做不到时返回 `completed=False`。第一段停止不等待短请求，I1 不覆盖 short 类。
  - I2：所有已准入的请求结束、loop 侧清理完成后，两类在途数在有界等待内（轮询，超时即失败）回到 0；运行期间 rejected
    计数不递减。
- 断言方式：
  - 只经公开门面或 HTTP 观测。lag 用保留值（`loop_stall_count` 的差值，`loop_lag_max_seconds` 不小于配置的阈值），不用
    `loop_lag_seconds` 的瞬时值；不用私有 hook，不由 App 自行测量。
  - `asgi`：卡顿越过截止时刻，迟到返回 504，后一次快照的 `loop_stall_count` 大于前一次，且 `loop_lag_max_seconds` 不小于
    阈值。
  - `blocking_wsgi`：在 `w1_wsgi_loop_lag` 中，卡顿解除后经 `handle.blocking.diagnostics.snapshot(principal, timeout=…)`
    或 HTTP 校验同样的结果。
  - 门面与 HTTP 一致（`test_admission_limits.py`）：键集合与 camelCase 映射完全相等，`runningSince` 相等；累计值与峰值
    （两类 rejected、`loop_stall_count`、两个 max、`dropped_auth_audit_count`）满足"前一次门面 ≤ HTTP ≤ 后一次门面"；
    静止时 HTTP 的 `shortInFlightCount` 不小于 1，`streamInFlightCount` 与门面相等；瞬时值（`loop_lag_seconds` 与 3 个
    audit outbox 字段）只校验类型与范围。诊断请求本身占一个 short 名额，两次读取之间计数也可能变化，所以不要求逐项相等。
  - V14、V15 写明观测面；validation-matrix §7.7 为新断言补适用性行。
- 尾延迟取 max，不取 p99：p99 需要窗口大小等新的 §10 取值；S0b R20（`s0b-spike-report.md:831`）只把 p99 当作例子；max
  足以发现卡顿与超时。design §4 第 7 步的 "short-request p99/max latency"（`069ce23` :392-393）收窄为 max，spec
  `synchronous-runtime-host` :205 与 V14 的 "tail latency" 同步改为 max。

### 7.3 新发现的缺陷

| 编号 | 缺陷 | 位置与证据 | 修复要求 |
| --- | --- | --- | --- |
| W1-F7 | `dropped_auth_audit_count` 在快照中恒为 0 | HttpState 的真实计数（`_internal/http/state.py:79`，`_internal/http/security.py:104`、`:117`、`:127`、`:143`、`:145` 递增）没有进入快照；`_internal/observability/__init__.py:118-122` 只构造 3 个 outbox 字段 | 快照投影 HttpState 的真实计数。测试：`blocking_wsgi` 下发一次认证失败请求（WSGI 下每次认证失败都计为丢弃，符合 V04）；`asgi` 下让宿主的 `record_audit` 失败或超时，或耗尽队列容量；断言快照的差值等于丢弃次数 |
| W1-F8 | App 路由没有命名空间：`find_route` 直接用 `route.path` 匹配相对 root 的请求路径，App 可以声明 `/api/diagnostics` 这类路径，与运行时路由冲突 | `_internal/http/requests.py:51-58`、`_internal/http/app.py:207`；design §5（:440-442，W0 `fc4db2f` :416）规定 App 的可选路由在 `/ai/apps/{app_id}/` 下；spec `embedded-agent-runtime` :146-148 要求 namespaced；Metrics 上游提案 D4（`upstream-ai-base-runtime-proposal.md:220`）相同 | App 路由只在 `<root_path>/apps/{app_id}` 加 `AppRoute.path` 下解析：`AppRoute.path` 相对 App 命名空间，由运行时挂载（与 tool 名自动加前缀同理）；运行时 `/api/...` 路由不会被 App 遮蔽。改 `find_route` 与 testkit 中 probe、baseline App 的路由请求（现为 `/api/conformance/...`、`/api/echo`），design §5 写明挂载规则。RED：App 声明 `GET /api/diagnostics` 时只能经 `/apps/<id>/api/diagnostics` 访问，`<root_path>/api/diagnostics` 仍返回运行时诊断。发现 W0 冻结了其他路由语义时停下回报 |

## 8. 对 Metrics 的影响（第二轮）

- 配置不变：OD-W1-4 不新增配置项；`loop_lag_threshold_seconds`（0.1）与 `loop_probe_interval_seconds`（0.05）是 B 类冻结
  值，Metrics 不传入。
- 5.10 中在途数、拒绝数与卡顿记录经 `handle.blocking.diagnostics.snapshot(principal, timeout=…)` 观测，并验证 I1、I2。
  spec `embedded-ai-runtime-host` 的名额归还场景与一致性套件场景、tasks 5.10 与 0.6、design 同步门面一条已同步。
- Metrics 生产代码不读取快照：AI pane 状态由 Metrics 的生命周期对象与设置推导（design 决策 6），快照只用于测试。
- Metrics App 包（`app_id=metrics`）不声明 App 路由（spec `embedded-ai-runtime-host` 的 "Metrics App package declares
  the whole AI surface"），W1-F8 不影响 Metrics。运行时诊断在 Metrics 下的路径为 `<root_path>/api/diagnostics`（默认
  `/ai/api/diagnostics`）。

## 9. 转交（第二轮）

OD-W1-4、W1-F7 与 W1-F8 由 owner 以 `handoff-prompt-aib2-w1-diagnostics-decision.md` 转交 AI Base，提示词引用的
`metrics_commit` 是写入第 6–9 节的提交。AI Base 先提交规划 D2（只改 change 目录，含 plan.json 记录与 checker 规则）与
证据 E2，再恢复 W1.HOST。原授权与 `handoff-prompt-aib2-w1-host-decision.md` 的其他内容仍然有效。

# S0b 签核意见（Validation Engineer，2026-11-11）

- 入库说明：本文是 S0b 签核意见的提交副本，原件在本地被忽略的 `.tmp\s0-coinstall\s0b-signoff.md`。文中的脚本行号
  （`s0b_host.py`、`s0b_perf.py` 等）与证据文件都在 `.tmp\s0-coinstall\` 下，不入库。"三、报告修正"中的行号指
  S0b 报告修正前的版本。正文保持签核时的原文，事后发现的错误以"更正"标注，不删除原文。复签与复签勘误
  （原件 :119-365）已追加到本文末尾；勘误中的":NNN"指原件行号，本副本的对应行号加 5，"L"指入库的 994 行版报告。

判定：**NEEDS_FIX**。报告中没有凭据泄露，可以提交，但必须先改正过度声明。0.5 要求推荐组合"逐项通过"；严格关闭需要完成补测 M1–M4。Metrics 另外要求补测 M5。

## 一、发现（按严重度）

1. **[高] B1 第二次信号：组合宿主既没实现也没测。**
   - `sig2.json` 来自合成子进程 `s0b_sig2.py`。
   - `s0b_host.py:62-65` 的 `request_stop` 遇到重复信号时，只记录 `stop.trigger.repeat` 后返回，不会强制退出。
   - 主线程上的等待没有切片：`:822` `controller_done.wait(drain+10)`、`:231` `thread.join(timeout)`、`:449` `_finished.wait(watchdog)`。
   - waitress `run()` 在主线程上时，处理器要等 `select`（`asyncore_loop_timeout=1`）返回，实测 0.30/0.54 s（第 91 行）。所以 1 s 上限取决于 `serve-http` 线程布局，或者把 loop timeout 调短。
2. **[中] B5 混用了两组证据。** 基础矩阵中空闲流 `terminal=0`（`terminal_received=false`，约 2 s 被取消，但仍判 `pass=true`）。
   - 真正满足 0.5 B5 的只有 b5s：
     - `b5s-waitress-flush-stopfile`：1.141 s；
     - `b5s-slow-waitress-flush`：终止事件 3.308 s，EOF 5.947 s，exit 7.077 s。
   - `flush` 只和 stop-file 组合测过；CTRL_BREAK、CTRL_C 只在 `close` 下测过。
3. **[中] 推荐组合从未作为一个整体运行。**
   - B6 Phase 2 判定 arm、b9 的"未饱和对照"、B7（`s0b_browser_runner.py:54`）、B5s、B9(a)(b) 都是 threads 8、无准入、`close`。
   - 唯一的 threads 12 数据是 `b9_sat_t12`。
4. **[中] B9 的 (b) 和 (c) 不是在同一次饱和中测的。**
   - (c) 期间没有发出短 `/ai` 请求：`s0b_b9.py hold` 只有 `--port/--stop-file/--streams/--max-seconds/--out` 这几个参数。
   - (b) 只在 `b9-admission.json` 的 split 会话中测过（threads 8）。
5. **[中] 停止总预算没有上界。**
   - 依次叠加：drain 截止 t0+10 s（`:615`）；flush 截止 `max(t0+10, now+2)`（`:625`）；`task_dispatcher.shutdown(timeout=5)`（`:554`）；loop 收尾（`:219`，最多 5 s，再加 join）。
   - 客户端一直不读时，stop→exit 可能超过 10 s。
6. **[低] threads 12 是保守取值，不能说"需要"。**
   - threads 8 唯一失败的是 seq 单元格（单连接，不是线程耗尽）。
   - 同一配置跨两次运行的波动约 0.18。
   - threads 12 下 c4 home 为 1.146，只有一次运行。
7. **[低] 第 85 行的"由宿主应答"实际是 HTTP 400。** `who_answers` 发送 `Host: x`（`s0b_portbind.py:167,176`），证据记为 `other-400`。
8. **[低] 第 96、250 行的"Django 正常"实际是 `/s0/health` 返回 404**（`--urlconf s0b`）。这只说明线程没有被阻塞。
9. **[低] b5s 中 8851 端口的 10013 没有留存证据。** 只有 `RuntimeError('server exited early with 4')`。
10. **[低] JSON 中没有脚本 hash。** `s0b_host.py` 最后修改于 09:21、`s0b_perf.py` 于 09:31，都晚于多项证据的生成时间。
11. **[残余] B7 不覆盖 `/ai`。**
    - 短请求上限 2 与浏览器约 6 个并发连接之间的关系没有测。
    - 流被客户端中止后名额是否归还，也没有测。

已有证据（不用补测）：
- B1 反向绑定：`b1-portbind-host.json[4].control`。宿主先独占监听；另一进程分别以 `SO_REUSEADDR`、默认、独占方式绑定，结果为 10013/10048/10048；入侵前后各 10 个连接都由宿主应答，记为 `other-400`。
- `::1` 没有测。

## 二、补测规格

- **M1（必需，B1 第二次信号）**
  - 宿主改动：
    1. spike 宿主收到重复信号时执行 `os._exit(130)`；
    2. 把 `:822/:231/:449` 的等待切片到 ≤ 0.5 s；
    3. 把 waitress `run()` 移到 `serve-http` 线程，或把 `asyncore_loop_timeout` 设为 ≤ 0.5；
    4. 给 `s0b_sig2.py driver` 增加以组合宿主为目标的模式。
  - 宿主参数：`--server waitress --static wn-noauto --bridge custom --threads 12 --ai-limit-mode split --ai-stream-limit 4 --ai-short-limit 2 --finish flush --enable-ctrl-c`。
  - 负载：1 条活动流 + 1 条空闲流 + 1 个慢读者。
  - 方法：`--events break,c --reps 2`；第 1 个信号后 1.0 s 发第 2 个；drain 阶段和 flush 阶段各测一组。
  - 判定：第 2 个信号到退出 ≤ 1.0 s，退出码非 0。
- **M2（B6 与 B9 (a)(b)(c) 在同一次饱和中）**
  - 在 `s0b_perf.py` 的 ARMS 中新增：
    - `rec_t12`：端口 8856，`host('waitress','wn-noauto','--threads','12',*B9_LIMITS,'--finish','flush')`，role 为 `candidate`；
    - `rec_t12_sat`：端口 8857，参数相同，role 为 `b9`。
  - `s0b_b9.py hold` 增加：每 1 s 发一次短 `/ai` 请求（`/ai/health`、`/ai/s0b/asset.js`），并周期性探测第 5 条流。
  - 运行：`s0b_perf.py run --arms baseline,rec_t12,rec_t12_sat,waitress_wn_noauto --blocks 4 --per-block 40 --warmup 10 --modes seq,c4 --out b6b9-rec.json --log-prefix rec`，约 18–20 min。
  - 判定：
    - 两个 rec arm 都 12/12，`unauth_static` 为 401；
    - hold 期间的短请求全部 200 且 < 100 ms；
    - 新流探测全部 503 并带 `Retry-After`。
- **M3（B7 在 threads 12 下）**
  - 运行：`s0b_browser_runner.py --mode candidate --static wn-noauto --threads 12 ... --junitxml=...\b7-candidate-t12-junit.xml`，约 450 s。
  - 判定：11/11，逐个与 stock 一致。
- **M4（B5、B1 各触发 × `flush`，10 s 预算）**
  - 在 `s0b_b5s.py` 的 CASES 中新增：
    - `rec-flush-{stopfile,ctrlbreak,ctrlc}`，正常读取；
    - `rec-slow-flush`，8 MB，暂停 3 s；
    - `rec-noread-flush`，暂停 ≥ 15 s。
  - `run_case` 透传 threads 12 和分离准入参数。
  - 跑 noread 之前，先把 drain、flush、dispatcher、loop 收尾的时限合计压到 ≤ 10 s，并在报告中写出各段预算。
  - 判定：
    - 所有用例都在 10 s 内以 0 退出；
    - 正常读取的客户端在连接关闭前收到终止事件。
- **M5（Metrics 追加，流名额归还）**
  - 方法：中止 4 条流（客户端断开），之后新流应在心跳间隔 + 1 s 内被接受（200）；服务端异常结束的流，名额也要归还。
  - 判定：名额全部归还，没有残留计数。
- **M6（Metrics 追加，反向绑定补强，开销很小）**
  - 用 M1 的宿主配置。
  - 对照请求改用合法 Host + 凭据，期望 200，并带宿主 pid 标记。
  - 再加一次 `0.0.0.0` + `SO_REUSEADDR` 尝试：只 bind，不 listen，立即关闭，期望失败。
  - 更正（2026-11-11）：上一句的期望有误。按 Windows 的绑定规则（Microsoft Learn "Using SO_REUSEADDR and
    SO_EXCLUSIVEADDRUSE"），第一个 socket 以 `SO_EXCLUSIVEADDRUSE` 绑定特定地址后，另一个 socket 绑定通配地址会成功，
    得到的是该地址以外的接口，截不走发往 127.0.0.1 的连接；S0b 补测 (a) 实测 3/3 成功。独占的范围是正在服务的
    地址与端口。M6 的通配地址尝试只记录结果，不作为失败条件。

## 三、报告修正（按行号）

- **L14**："因 bind 时一次无法解释的 WSAEACCES 10013 以 exit 4 退出" → "以 exit 4 退出（`b5s.json` 只记录 `server exited early with 4`；当时观察到的 10013 未留存，server 日志已被重跑覆盖）"。
- **L16**："并通过 B1–B5、B7；B9 还需要分离准入与 threads 12。" → "B0、B2–B4、B6、B8 通过；B1 中'停止期间第二次信号 1 秒内非零退出'只在合成子进程上证明了机制，组合宿主未实现、未测；B5 在 waitress `flush` + stop-file 下通过；B7 在 threads 8 下通过；B9 需要分离准入，(a)(b) 在 threads 8、(c) 在 threads 12 下分别测得，threads 12 是保守取值；推荐组合作为整体没有运行过。"
- **L23（B1 行）**：
  - 结论改为"PASS（第二信号子条件除外：未验证）"。
  - 在"都没有创建。"之后插入反向绑定的证据（见第一节"已有证据"）。
  - 第二信号一句改为："合成子进程（`s0b_sig2.py`）不切片时 8.58–8.61 s、切片后 0.22–0.23 s 以 130 退出；组合宿主对重复信号只记录 `stop.trigger.repeat`（`s0b_host.py:62-65`），主线程等待未切片（`:822`），未验证。"
- **L27（B5 行）**：
  - 结论改为"PASS（0.5 定义由 b5s 证明：waitress `flush` + stop-file；`flush` × CTRL_* 未测）；a2wsgi FAIL ×3"。
  - 首句前加："基础矩阵（空闲流 `terminal=0`，只证明活动流终止事件与 exit 0）："。
- **L29**：句末加"；未在 threads 12、分离准入、`flush` 下运行；这 11 个测试不访问 `/ai`"。
- **L31**：
  - 结论改为"(a)(c) PASS（分离准入；(a) 在 threads 8 下 n=10，在 threads 12 下 n=2；(c) 在 threads 12 下）；(b) 只在 threads 8 的独立会话中 PASS；共享准入 (b) FAIL；threads 8 (c) 有 1 个 seq 单元格 FAIL"。
  - 证据中注明"(c) 期间没有发短 `/ai` 请求"。
- **L85**："10/10 个连接由宿主应答" → "入侵前后各 10 个连接都由宿主应答（HTTP 400：探测用 `Host: x`，记为 `other-400`；宿主是唯一成功绑定的监听者），锁一直由宿主持有"。
- **L96**："Django 路由 18 ms" → "Django 路由 `/s0/health` 18 ms 返回 404（`--urlconf s0b` 下没有该路由，只说明请求线程未被阻塞）"。
- **L126**：句末加"（脚本 `pass` 不要求空闲流收到终止事件；0.5 B5 的这一子条件见下文 b5s）"。
- **L250**："Django 页面照常" → "Django 路由 `/s0/health` 17 ms 返回 404（未被阻塞，不是页面请求）"。
- **L259**："`waitress_wn_noauto` 是未饱和的对照" → "`waitress_wn_noauto`（threads 8、无准入、`close`）是未饱和的对照；没有 threads 12 加分离准入的未饱和 arm；hold 期间没有发短 `/ai` 请求"。
- **L306**："B3–B5（custom 桥、`flush` 收尾）、B7、B9（threads 12）都 PASS" → "B3、B4 PASS；B5 在 `flush` + stop-file 下 PASS；B7 在 threads 8 下 PASS；B9 (a)(b) 在 threads 8、(c) 在 threads 12 下 PASS"。
- **L318**：句末加"整体停止预算未定：drain 截止 t0+10 s（`:615`），flush 截止 `max(t0+10, now+2)`（`:625`），之后还有 dispatcher 收尾 5 s（`:554`）和 loop 收尾（`:219`）。客户端不读取时 stop→exit 可能超过 10 s，需要压缩到 10 s 内并补测。"
- **L321**："（spike 为 `os._exit(130)`）" → "（只有 `s0b_sig2.py` 合成子进程如此；组合宿主未实现。waitress `run()` 在主线程时处理器还要等 `select`，最长约 1 s，所以 1 s 上限依赖 `serve-http` 线程布局）"。
- **L326**：第二句改为"流占满时 threads 12 为 12/12（c4 home 1.15×，单次运行）；threads 8 失败的是 seq 单元格，不是线程耗尽，不能证明 8 不够；12 是保守取值。Phase 2、B7、B5s、B9 (a)(b) 都用 threads 8。"
- **L351**：末句改为"该组合作为整体没有运行过：threads 12 只在 B9(c) 饱和场景（`close` 收尾）测过；`flush` 只与 stop-file 组合测过；第二信号强制退出与停止等待切片在宿主中未实现。"
- **L389**："出现过一次无法解释的 10013" → "出现过一次无法解释的 exit 4（当时观察为 10013，未留存）"。
- **L28（可选）**："页面 p95 比为 0.94/0.97" → "（相对同 arm 无流）页面 p95 比为 0.94/0.97"。

补测完成后，以上修正中凡是被补测结果取代的部分，都改为写补测的结论。

## 复签（2026-11-11）

复签人：Validation Engineer（原签核作者）。方式：只读。没有启动宿主、服务器或浏览器，没有运行 pytest；读取了终测报告（981 行）、`logs\s0b\final\` 下的判定 JSON 与日志、最终 `s0b_host.py`、waitress 3.0.2 源码（`.tmp\s0-coinstall\venv`）与 git 记录。时刻标 Z 的为 UTC，本地为 UTC+8。

### 总结论：PASS

- 推荐组合（waitress 3.0.2，threads 14，分离准入流 4 / 短请求 4，`flush`，wn-noauto，custom 桥，`SO_EXCLUSIVEADDRUSE` 预绑定，显式退出）作为整体运行，0.5 的 B0–B9（含 B1、B4、B5、B6、B9 各子条件）都有证据；终测证据都来自冻结的宿主 `e6e1707d…`。
- 原签核发现 1–11 全部关闭（第 11 条留有残余）；M1–M6 都满足判据。
- Metrics 侧的并发活动不改变任何判定，不需要重跑（C）。
- 条件：报告入库前完成本节"报告修正"（只改披露与归因，不改判定）；Metrics 文档落实本节末的条目。

### A. 逐项核对

SHA 独立复算 PASS：
- `final\scripts-sha256.json` 中 51 个文件与磁盘一致。
- 冻结后只新增两个只读分析脚本（`s0b_final_shacheck.py`、`s0b_final_window.py`）。
- 19 个终测 JSON 记录的宿主都是 `e6e1707d…`（57436 B）。
- 步骤 A 记录的是旧宿主 `f4aa2dcc…`（= `final\pre-scripts\s0b_host.py`），报告已注明。
- 3 个 diag JSON 没有 `script_sha256` 键，`sha-verify.json` 按 maps=1 计数，只是口径差异。

§1 与 §3.11 中下表引用的关键数字，与 `final\` 下的判定 JSON 一致，没有发现矛盾。B9 (a) 的 194 次探测与宿主拒绝计数 196 相差的 2 次，是起止两次探测。

| 项 | 判定 | 证据 |
|---|---|---|
| 1 第二信号 | PASS | 宿主已实现重复信号 `os._exit(130)`、`WAIT_SLICE_S=0.5`、`run()` 在 `serve-http` 线程；`m1-sig2-host.json` 8/8 exit 130，第 2 个信号到解释器退出 0.073–0.502 s（启动器 0.081–0.508 s），排空与 flush 两阶段 × CTRL_BREAK/CTRL_C × 2 |
| 2 B5 证据混用 | PASS | `m4-b5s.json` 5/5 exit 0；`flush` × stopfile/ctrlbreak/ctrlc 触发到退出 0.281/0.085/0.191 s，正常读者在停止受理结束后 0.7–1.8 ms 收到终止事件；慢读 3.097 s 收完终止事件；不读 6.692 s（flush 截止，丢弃 7,803,542 B，风险 12 已披露） |
| 3 组合未整体运行 | PASS | 冒烟与 M1–M6 都在 `e6e1707d…` 上用同一配置运行 |
| 4 B9 (b)(c) 不同时 | PASS | `b6b9-final.json`：一次 hold（09:06:32.221Z–09:22:44.305Z，972.1 s）覆盖全部 192 个测量块（09:07:13.494Z–09:22:44.175Z）；(a) 194/194 为 503 + `Retry-After: 2`；(b) 1944/1944 为 200，max 70.78 ms；(c) `rec_t14_sat` 12/12 |
| 5 停止预算无上界 | PASS | `STOP_BUDGET` 合计 10.0 s（到 `os._exit` 9.5 s）；不读用例 `stop_to_os_exit` 6.5121 s；看门狗未触发。残余：终止宽限到期取消的路径没有走到（:789），转 E |
| 6 threads 12 只是保守取值 | PASS | §4.2 第 6 项改为公式 4+4+4+2=14（owner 决定），并写明"不能证明 8 不够" |
| 7 400 被写成"由宿主应答" | PASS | :109 已改；M6 用合法 Host + 凭据，520/520 为 200 且带宿主 pid 标记 |
| 8 404 被写成"Django 正常" | PASS | :121、:276、:280 已改 |
| 9 8851 的 10013 无证据 | PASS | 风险 7（:972）已改为"exit 4（当时观察为 10013，未留存）"。原因仍未知，可能与动态端口范围 1024–15000（:836）或其中的系统保留段有关，未证实 |
| 10 证据无脚本 hash | PASS | 见上方 SHA |
| 11 B7 不覆盖 `/ai` | PASS（残余） | 短请求上限 4；资产在认证之后直出、不占名额（冒烟、M5）；M5 名额归还 15/15。残余：浏览器级 `/ai` 未测；短请求上限 4 小于浏览器每源约 6 个连接，UI 必须处理 503 + `Retry-After` |
| M1 | PASS | 同第 1 条；参数按 owner 新配置 threads 14 / 短请求 4，取代规格中的 12/2 |
| M2 | PASS | `m2-final-verdict.json`：`rec_t14` 12/12（seq 0.914–1.020×，c4 0.795–0.970×）；`rec_t14_sat` 12/12（seq 0.899–1.093×，c4 0.857–1.015×）；rec arm 无凭据静态 401（baseline 200），无凭据页面 401，`If-None-Match` 304；每页 61–68 个资产 |
| M3 | PASS（须披露代码树） | `m3-final-compare.json` 11/11，逐个与 stock 一致；threads 14；`network_attempts` 为空。代码树见 C |
| M4 | PASS | 同第 2 条；`os._exit` 到退出 43.8–60.61 ms；触发后 0.302–0.536 s 发起的新连接都是 `ConnectTimeout` |
| M5 | PASS | `m5-slots.json` 15/15：客户端中止后 0.104–0.147 s、服务端异常后 0.002–0.031 s 可再建流（判据：心跳间隔 + 1 s）；最终准入在途（stream/short/shared）均为 0，exit 0 |
| M6 | PASS | `m6-revbind.json`：监听 socket `SO_EXCLUSIVEADDRUSE`=1；127.0.0.1 上 reuseaddr/default/exclusive 分别 10013×3/10048×3/10048×3；`0.0.0.0` + `SO_REUSEADDR` 只 bind 3/3 成功，按更正只记录。残余：通配地址上真正 listen 的入侵者、`::` 没有测 |

冒烟（`stepB-smoke.json`）19/19：`stop.requested` 到退出 0.051 s；`os._exit` 到退出 42.14 ms；ticker 最大 18.54 ms；`db_open_on_main` 0。

新发现（不改变 0.5 判定，但影响 `serve` 设计）：

- **N1 [中] 请求完整性归因有误，16 MiB 上限没有限制资源。**
  - waitress 在调用应用之前就读完并缓冲整个请求体：`channel.py` 在 `request.completed` 之后才创建 task，超过 `inbuf_overflow`（512 KiB）落到临时文件。
  - 冒烟 `bad_content_length_400` 的 67 B 响应体是 waitress 的错误页（`parser.py:324-325`，`utilities.py:263-268`：Bad Request + Content-Length is invalid + (generated by waitress)，11+4+25+27 B）。宿主 `_integrity` 的非数字分支在 waitress 下走不到。
  - `body_over_cap_413` 的 22 B 响应来自宿主，但此时 16 MiB + 1 B 已上传完（170.16 ms）。
  - 宿主没有设置 `max_request_body_size`，waitress 默认 1 GiB（`parser.py:154-160`，判定为 `>=`；chunked 见 `:175-179`）。
- **N2 [低]** 干扰窗口与离群归因的文字已过时，见 C。
- **N3 [低]** `m2-window-attrib.json` 的 `external_window`（17:14:30–17:14:55）与 `in_external_window` 是按当时估计的窗口算的。证据已冻结，不改 JSON，在报告中注明即可。

### B. 步骤 A 能否作为显式退出的依据

结论：方法有效，但只能说明"旧尾段由什么构成、显式退出省掉多少时间"，不能单独证明"跳过 atexit 是安全的"。

- 有效：
  - 包装器经 `runpy` 运行未修改的宿主。最先注册的 atexit 回调最后执行（t2），t1 时注册的回调最先执行（t3），所以能把 `threading._shutdown`、atexit 回调与之后的收尾分开。
  - 驱动用 `WaitForSingleObject` 阻塞等待进程句柄（t4），用 QPC 计时，并做了校准。
  - t1→t3 0.124–0.188 ms，t3→t2 0.171–0.273 ms，t2→t4 848.6–915.1 ms。效应量远大于波动，n=5 足以确定量级。
- 局限：
  1. 跨宿主：在旧宿主 `f4aa2dcc…` 上测，终测宿主总走显式退出，无法同条件复测（:579 已标为推断）。
  2. 条件窄：stop-file 触发、无流、空闲宿主。
  3. t2→t4 混合了解释器收尾与进程结束；扣除 M4 的 43.8–60.6 ms 后约 0.79–0.87 s，同样是推断。
  4. 只记录了数量（atexit 14、threading atexit 2、2973 个模块），没有记录回调身份。"耗时 < 0.5 ms"不等于"可以省略"。
  5. 生产 `serve` 的进程组成不同（provider sync、线程池、真实 AI 后端、遥测等）。
- 因此显式退出的正确性要靠 R24 加宿主侧清点（D 第 6 项）。

### C. Metrics 侧干扰：判定不受影响，不需要重跑

- 并发的 Metrics 测试只绑定临时端口（`bind(('127.0.0.1', 0))`），只结束自己启动的子进程，没有访问 S0b 的端口或进程。
- 本机动态端口 1024–15000 覆盖 8840–8859（:836）。即使撞上端口，结果也只会是 S0b 宿主预绑定失败（exit 4）或 Metrics 测试报错，不会出现假 PASS。终测宿主都正常启动，M6 的请求都带宿主 pid 标记。
- 剩下的只是 CPU 与磁盘负载，本机有 36 个逻辑 CPU（`config.cpu_count`）。负载只会让功能判定与绝对门限更难通过；只有落在 baseline 块上的负载会让 C5 比值偏乐观。

| 步骤 | 与 Metrics 进程的重叠 | 影响 |
|---|---|---|
| 冒烟重跑 09:00:45–09:01:03Z | pytest 09:00:56–09:01:00Z | 功能或绝对时限判据，余量大（例如 `os._exit` 到退出 42 ms，预算 300 ms），稳健 |
| M5 09:04:45–09:05:12Z | pytest 09:05:06–09:05:19Z | 名额归还 ≤ 0.147 s，判据为心跳间隔 + 1 s，稳健 |
| M6 09:05:18–09:05:39Z | 同一次 pytest，重叠 ≤ 1 s | 绑定语义是确定性的，稳健 |
| M2 W1 09:06:15–09:06:39Z | 宿主启动、预热、hold 起点；没有测量块 | 离群 #1（50.96 ms，09:06:32.306Z，hold 的第一次 `/ai/health`）落在 W1 内；它 < 100 ms，(b) 判定不变 |
| M2 W2 09:14:37–09:14:49Z | 只有 seq/draft_edit 第 2 块中的 `rec_t14_sat` 与 `waitress_wn_noauto`，没有 baseline 块 | 只会抬高候选 arm 的比值，属保守方向。驱动 ticker 的 90.57 ms 停顿（09:14:54.760Z）在确认窗口之外，原因无法判定 |
| M2 W3 09:18:00–09:19:59Z | 32 块：c4 的 projects 第 3 块、project_detail 第 0–3 块、stage_reports 第 0–2 块，4 个 arm 交错 | 见下文，稳健 |
| M3 | 读 JSON 的短 python 进程 | pass/fail 判定，负载只会造成失败，稳健；代码树见下文 |
| 步骤 A、M1、M4 | 只有轻量命令 | 无影响 |

W3 敏感性：
- W3 涉及的 rec 单元格中，最接近门限的是 `rec_t14_sat` 的 c4/project_detail 与 c4/stage_reports，比值都是 1.015（全部 rec 单元格中最高的是 `rec_t14_sat` seq/projects 的 1.093，不在 W1–W3 内）。要越过 1.2，baseline p95 需要被抬高 ≥ 18.3%，即 160 个样本中至少 8 个被拖慢。
- 证据不支持这种抬高：
  - W3 内三个单元格 baseline 的 p95/p50 为 1.119–1.122，是 c4 六个单元格中最低的（其余为 1.134–1.228）。如果尾部被抬高，这个比值会上升。
  - 块耗时正常：c4/projects 中 baseline 的 W3 块（3.39 s）是该单元格最短的；c4/stage_reports 中 baseline 的 W3 块比 W3 外的块长 0.6–3.0%，在块间波动范围内（`rec_t14_sat` 两个 W3 外的块就相差 4.8%）。
  - c4/project_detail 的 16 块全在 W3 内交错测量，持续负载在分子与分母上抵消。
  - W3 内被监测的 `rec_t14`、`rec_t14_sat` 宿主与驱动没有 > 50 ms 的停顿，也没有 ≥ 20 ms 的 GC。
  - baseline 进程（pid 13176）全程是同一个进程，没有自动重载，exit 0。
- 残余：baseline 没有 ticker，也没有逐请求样本，所以"只落在 baseline 块上的亚秒级突发"不能严格排除。若只有少数样本被拖慢（p50 基本不变），由于真实 p95 ≥ p50，p95 最多被抬高约 p95/p50 − 1 ≈ 12%，不足 18.3%（推断）。

M3 的代码树：
- stock 在 HEAD 6b3d017（`b7-stock-junit.xml`，本地 06:53）。
- 候选在 7181b6f 加未提交修改上运行。`jira_sync/container.py` 在 09:09:16Z 改为 d979e55 的内容，此后没有再改，所以 M3 宿主如果导入了它，用的就是 d979e55 版本。
- 6b3d017..d979e55（不含 openspec/docs）只改了 `jira_sync/container.py`、jira_sync 测试与 `scripts/*`，另新增 1 个测试文件。B7 的 4 个测试文件、conftest、pytest.ini、`metrics/settings` 与 ui_web 非测试代码都没有变。
- 对 B7 有影响的只有 `OnDemandJiraScopeMetadataProvider`：它把 Jira client 改为按需创建。M3 的 `network_attempts` 为空。
- 判定是"11/11 逐个一致"。代码差异要掩盖一个由 server 引起的失败，必须恰好补偿它，没有这样的机制。所以不重跑，只需披露。
- M2 的 4 个 arm 在 09:09:16Z 之前已完成全部页面的预热，用的是同一份代码，arm 之间没有混杂。

必须的重跑：无。

可选的整洁性重跑（只在 owner 要求 B7 证据出自单一代码树时才做）：
- 内容：M3 stock 与候选在同一个冻结提交上背靠背运行，命令同报告 §6。
- 条件：
  1. `HEAVY_RUN_ACTIVE` 在第一个进程启动前写入，最后一个判定 JSON 写出后才删除；
  2. 全程 Metrics 侧零进程（不跑 pytest 和 python，不做 git 写操作），用开始、结束与每分钟的进程快照证明；
  3. 开始与结束时记录 `git rev-parse HEAD` 与 `git status --porcelain` 的 hash，有任何变化即作废；
  4. 驱动记录整机 CPU 采样。
- M2 不建议重跑：结论对干扰稳健，重跑仍处在同样的共享机器噪声中。

### D. 风险 13 与 R24

建议 design 与 host spec 用同一张定序表（两处文字一致），并配按序断言的测试矩阵。

1. 分两层：
   - L0，waitress 传输层：先于应用执行，不可调整。包括请求行与头部大小、`Content-Length` 语法（400）、chunked 分帧、`max_request_body_size`（413，必须显式配置）。
   - L1，适配器：
     1. Host 校验：所有路径，复用 Django `validate_host` 与 `ALLOWED_HOSTS`，非法时 400；
     2. 停止中 503：所有路径，固定文本，带 `Retry-After`；
     3. 分流：
        - Django 路径进入 Django 中间件链（`metrics/settings/defaults.py:52-63`，`BasicAuthMiddleware` 第一）；
        - `/ai*`：按路由的完整性 → BasicAuth 401 → `/ai` 到 `/ai/` 的 308（相对 `Location`）→ 资产直出 → AI runtime 停止中 503 → 准入（503 + `Retry-After`）→ 桥。
   - 注意：Host 校验移到最外层后，Django 路径上"非法 Host + 无凭据"的结果由 401 变为 400（`BasicAuthMiddleware` 不调用 `get_host()`，现在先返回 401）。按 `HTTP_HOST`/`DisallowedHost` 检索，Metrics 应用测试中没有断言这一组合；这一行为变化要写进 spec，并加入测试矩阵。
2. 停止中的 503 放在 Host 校验之后、认证之前，作为具名例外写明：
   - 放在认证之前，是为了停止时不进入 Django。它只出现在停止受理完成（≤ 0.5 s 关闭监听）之前已接受的连接上，内容是固定文本，不含数据。
   - 放在 Host 校验之后，是因为 Host 校验只比较请求头，成本很低；放在最外层可以让防 DNS rebinding 覆盖所有路径，也与 owner 顺序一致。
   - 按 PEP 3333 不设 hop-by-hop 头（§4.2 第 8 项）。
3. `/ai` 的 308 移到认证之后。这与 Metrics 现状一致：`BasicAuthMiddleware` 先于 `CommonMiddleware`，所以无凭据的 `/projects` 得到 401，而不是 APPEND_SLASH 的 301。如果保留认证前的 308，就作为第二个具名例外，要求相对 `Location` 与固定响应体。
4. 请求体上限：
   - 由 waitress `max_request_body_size` 实现。判定为 `>=`，要允许恰好 N 字节就设 N+1。适配器另做按路由的上限。
   - 16 MiB 按 `/ai` API 契约中最大的合法请求定量之前，标为占位值。
   - 写明认证之前会先缓冲：最坏的临时文件占用约为"上限 × waitress `connection_limit`（默认 100）"。
   - 宿主的非数字 `Content-Length` 分支可以作为纵深防御保留，但测试要断言 400 与 413 分别来自哪一层。
5. 测试矩阵至少包括：
   - 非法 Host × 无凭据 × 停止中；
   - 无凭据 `/ai`（401；保留例外时为 308）；
   - 无凭据 + 超限 `Content-Length` → 413，请求体没有被读取；
   - chunked 超限 → 413；
   - 无凭据请求资产 → 401；
   - 短请求池占满时无凭据请求 → 401。
6. R24 作为上游契约是必要的，但不充分：显式退出跳过的是整个进程的 atexit 与解释器收尾。
   - host spec 增加宿主侧要求（可记为 R24-host）：在 `explicit_exit` 时记录以下各项并断言白名单：
     - atexit 回调：数量，以及在启动最早处包装 `atexit.register` 记录的注册者；
     - `threading._register_atexit` 回调，例如 `concurrent.futures` 的 `_python_exit`；
     - 存活的非 daemon 线程；
     - 存活的子进程（Windows 上父进程退出不会结束子进程）；
     - `weakref.finalize(atexit=True)` 资源，例如 `TemporaryDirectory`；
     - 日志 handler。
   - 必需的清理在显式退出预算内显式执行，超时或失败则 exit 3。
   - 写明 `connections.close_all()` 只关闭调用线程的连接；这依赖 SQLite 与默认的 `CONN_MAX_AGE=0`（请求线程在 `request_finished` 时关闭连接），改用持久连接时要重新评估。
   - 测试：停止后最后一行日志已落盘、临时目录已清除、没有子进程、exit 0；注入清理失败时 exit 3。

### E. 看门狗

结论：有条件接受。660 s 只作为最外层兜底；10 s 是"没有执行中的 run"时的设计预算，由各段时限保证，不是硬上限。报告 :803-806 的表述正确：spike 的 t0 + 10 s 只是测量护栏。

条件：
1. 文档不写"10 s 硬上限"。写明外层上限：进程内看门狗 660 s，启动脚本 ≥ 15 s 后按 PID 强制结束，Docker `--stop-timeout 690`。执行中的 run 不计入 10 s（owner 决定 3）。
2. "各段时限"必须覆盖 t0 到 `os._exit` 的每一段。
   - spike 的 `explicit_exit` 中，诊断转储、`close_all()`、`logging.shutdown()`、stdout/stderr flush 都在主线程上内联执行，没有单独时限，靠 t0 + 10 s 看门狗兜底（`STOP_BUDGET` 中 `explicit_exit` 的注释即如此；实测 0.07–22.55 ms）。
   - 如果只靠 660 s 兜底，一次阻塞的 flush（例如管道读端停止读取）、日志 handler I/O 或网络数据库连接的关闭，都会让 Docker 上的退出拖到 660 s。
   - 要么把这些步骤放到辅助线程中，并按剩余预算 join；要么在文档中写明它们依赖外部强制结束。
3. 建议采用两段式看门狗：
   - 没有执行中的 run 时，以及 `project_runs.stop` 返回之后，设为 t0 + 剩余预算（约 9.7 s，为进程结束留 0.3 s）；
   - 只在等待执行中的 run 时放宽到 660 s。
   - 这样，没有 run 时"10 s 内退出"就由机制保证。
   - 注意：持有 GIL 的长 C 调用也会挡住看门狗线程，所以最终的硬上限只能依靠外部强制结束。
4. Metrics 实现必须补的测试（spike 没有覆盖，或者只在 spike 代码上测过）：
   - 注入卡住的段，看门狗 exit 3（可以把看门狗时限调小）；
   - 终止宽限到期后取消不支持终止事件的流（:789、§4.2 第 4 项）；
   - 停止执行中的 run（620/660 s，用假 run 与可注入时钟）；
   - 生产宿主上第二个信号 exit 130；
   - 清理失败 exit 3。

### 报告修正（行号按 981 行版本；只改文字，不改判定）

- **:28–29、:766–777、:971**：按会话日志改写 Metrics 侧窗口（本地时间）：
  - 17:00:56–17:01:00 单进程 pytest，与冒烟重跑重叠；
  - 17:05:06–17:05:19 pytest（3 个 launcher 测试文件，21 项），与 M5 及 M6 的开头重叠；
  - 17:06:15–17:06:39 两次 pytest（另一次是在临时目录副本上的 red 检查，4 项，10.34 s），与 M2 启动、预热与 hold 起点重叠，没有测量块；
  - 17:14:37–17:14:49 pytest（17 项 Django 测试），替换原来的 17:14:30–17:14:55；
  - 17:18:00–17:19:59 三个读文件的短 python 进程，与 32 个测量块重叠；
  - M3 期间，17:24:22–17:25:28 与 17:30:11–17:30:35 有读 JSON 的短 python 进程；
  - "17:06:22 可能还有一次"改为"已确认是 Metrics 侧"；
  - 离群 #1 改为"落在 17:06:15–17:06:39 的 pytest 窗口内（已确认重叠；它同时是 hold 的第一次调用，原因不能单独判定）"；
  - 补充：离群 #2（17:21:24.321，70.78 ms）不在任何已确认窗口内；
  - 驱动 ticker 的 90.57 ms 停顿改为"不在已确认的窗口内，原因无法判定"；
  - 注明 `m2-window-attrib.json` 的窗口是当时的估计。
- **:28**：在"无法确定 M3 是否导入了修改后的 `container.py`"之后补上 C 中关于代码树的表述。
- **:68、:582、:610、:853**：改正完整性归因。例如 :610 改为"`Content-Length` 非数字时 400，由 waitress 解析器在调用应用之前返回（67 B 的 waitress 错误页），宿主这一分支在 waitress 下走不到；超过 16 MiB 时 413，由宿主返回，但 waitress 此时已读完并缓冲整个请求体（170 ms）"。:853 改为 D 第 1、4 项的分层表述。
- **:981**：句末加"waitress 在调用应用之前已读完并缓冲请求体（> 512 KiB 落临时文件），应用层 413 不限制资源；真正的上限要配置 waitress `max_request_body_size`（默认 1 GiB，判定为 `>=`），终测宿主没有配置。"
- **:38（可选）**："约 0.85–0.92 s 的解释器收尾" → "约 0.85–0.92 s 的解释器收尾与进程结束"。
- 提交安全：扫描了 981 行报告，查找 Authorization 值、`Basic` 后接 base64，以及 password/token/api_key/secret 赋值，没有命中。

### Metrics 文档必须反映的条目

1. 统一的定序表（L0 waitress / L1 适配器）。停止中 503（以及若保留的认证前 308）写为具名例外，并配按序测试矩阵（D 第 1–3、5 项）。
2. 请求体上限由 waitress `max_request_body_size` 实现（N+1）；16 MiB 标为待定量的占位值；按路由的上限放在适配器（D 第 4 项）。
3. 在 R24 之外加 R24-host：退出清点与白名单测试；写明 `close_all()` 只关闭调用线程的连接，依赖 `CONN_MAX_AGE=0`（D 第 6 项）。
4. 停止预算：10 s 写为预算，外层上限为 660 / ≥ 15 / 690 s；`explicit_exit` 的各步要有时限，否则写明依赖外部强制结束；建议两段式看门狗（E）。
5. 补测 spike 没有覆盖的路径：看门狗 exit 3、终止宽限取消、执行中 run 的停止、生产宿主第二个信号 exit 130、清理失败 exit 3（E 第 4 项）。
6. UI 处理 `/ai` 短请求的 503 + `Retry-After`；`/ai` UI 落地时补浏览器级测试（发现 11 的残余）。
7. 报告修正落实后再入库。Metrics 侧在 `HEAVY_RUN_ACTIVE` 期间不运行进程：本次 W1–W3 与 M3 期间，标记存在时仍有 Metrics 进程。
8. 入库副本：
   - `openspec/changes/embed-ai-base-runtime-in-process/s0b-signoff.md` 是本文在第 1 行之后插入 5 行入库说明的副本（LF 换行），要把本节同样追加过去（保持 LF）；
   - 该目录下的 `s0b-spike-report.md`（68071 B，02:21Z）是旧版，要换成修正后的终测报告（现为 150221 B）。

### 复签勘误（2026-11-11）

本节更正上文复签的文字，并补记一处评估，不改判定：总结论仍为 PASS，必须的重跑仍为无。":NNN" 指本文件行号，"L" 指 994 行版报告。

1. `jira_sync/container.py` 的修改时间（:218、:222）
   - "09:09:16Z" 改为 "09:09:14.774Z"。后者是文件时间（LastWriteTimeUtc，本地 17:09:14.774，报告 L30 采用）；09:09:16Z 是会话事件日志的时间，约晚 1.2 s。内容何时改变，以文件时间为准。
   - 先后关系不变：M2 第一个测量块 09:07:13.5Z 开始，预热在此之前；M3 09:24:07Z 开始；两个时间之间没有宿主启动。:218、:222 的结论不变。报告 L30 如实记录了勘误前的复签文字，可以不改。
   - 补记（上文没有评估）：按 `b6b9-final.json` 的 `block_times`，这次写入落在 seq/projects 第 2 块的 `baseline` 块（09:09:10.990–09:09:16.529Z）内。两个测试文件的最终写入（文件时间 09:13:52.745Z、09:14:30.029Z）落在候选块上（seq/draft_edit 第 1 块 `waitress_wn_noauto`、第 2 块 `rec_t14`），属保守方向。:207 说 `rec_t14_sat` seq/projects 的 1.093"不在 W1–W3 内"，这仍成立，但这个单元格的 baseline 块上有这次写入。评估：
     - 单次文件写入不是进程负载，只持续毫秒级，最多碰到 1–2 个顺序页面请求（每个约 130 ms）（推断）。
     - 要越过 1.2，`rec_t14_sat`（1.093）需要 baseline p95 被抬高 ≥ 9.8%，`rec_t14`（1.020）需要 ≥ 17.7%。
     - 这个 baseline 块 5.54 s，是 4 块中最长的（其余 5.02–5.31 s，极差 10.2%）；没有任何已知重叠的 seq 单元格，baseline 极差也在这个范围（home 12.0%、project_detail 12.6%、bug_trend 10.2%）。
     - 该单元格 baseline 的 p95/p50 为 1.170，所以 p95/p50 上界（约 17%）在这里排除不了 9.8%。残余与 W3 相同：baseline 没有逐请求样本。
     - threads 8 对照 `waitress_wn_noauto` 在该单元格为 1.159，越过 1.2 只需 3.5%。它不是推荐组合的判定依据，本勘误不为它的终测 12/12 作稳健性结论。
     - 判定不变。

2. C 表 M2 W3 行（:202）的块集合
   - 原文"c4 的 projects 第 3 块、project_detail 第 0–3 块、stage_reports 第 0–2 块，4 个 arm 交错"是把同一块号的 4 个 arm 按整轮的开始时间归属得到的。总数同为 32，但集合不对。
   - 按 `block_times` 逐个 arm 块计算，结果与 S0b agent 一致。窗口按 09:18:00–09:20:00Z 计算（会话日志只到分钟）；时钟映射取 `m2-window-attrib.json` 的 `clock_mapping`（wall − mono 中位数 1793948287.337 s，n = 49，极差 3 ms），与 `external_window` 一致：
     - c4/projects 7 块：第 2 块的 `rec_t14`（部分在内，09:17:59.138–09:18:02.266Z，约 72%）、`rec_t14_sat`、`waitress_wn_noauto`，以及第 3 块的 4 个 arm。`baseline` 第 2 块在 09:17:59.138Z 结束，不在窗口内。
     - c4/project_detail 16 块：第 0–3 块的 4 个 arm，全部在内（09:18:21.260–09:19:17.922Z）。
     - c4/stage_reports 9 块：第 0–1 块的 4 个 arm，以及第 2 块的 `baseline`（部分在内，09:19:55.779–09:20:00.625Z，约 87%）。候选的第 2 块从 09:20:00.625Z 开始，不在窗口内。
     - 合计 32 块：30 块完全在内，2 块部分在内。
   - 两种算法下，baseline 的 W3 块相同（projects 第 3 块、project_detail 第 0–3 块、stage_reports 第 0–2 块）。不同的只有候选块：projects 多出 3 个候选的第 2 块，stage_reports 少了 3 个候选的第 2 块。
   - 对 W3 敏感性（:206–214）的影响：
     - "baseline p95 需要被抬高 ≥ 18.3%"不变。它由单元格级 p95 算出：`rec_t14_sat` 的 c4/project_detail（414.78/408.78）与 c4/stage_reports（535.28/527.51）都是 1.0147，1.2/1.0147 = 1.183。这与块归属无关，W3 涉及的仍是这三个单元格。它假设候选没有被抬高，本来就是最坏情况，所以候选块的增减不影响它。
     - :209、:210、:214 的证据不变，因为它们只用 baseline 的 W3 块。:210 的"`rec_t14_sat` 两个 W3 外的块相差 4.8%"本来就是按逐块集合算的（第 2 块 5.047 s，第 3 块 4.815 s）；按 :202 的旧写法，它只有 1 个 W3 外的块。
     - "持续负载在分子与分母上抵消"（:211）不变。它只针对 c4/project_detail，该单元格的 16 块在两种算法下都全部在内。
     - 这一抵消不能推广到 c4/stage_reports。那里 baseline 约有 2.9 块在 W3 内（第 0、1 块与第 2 块的约 87%），每个候选只有 2 块，属偏乐观方向。该单元格的稳健性靠 :209、:210、:214，不靠抵消。若把 baseline W3 块最多 3.0% 的耗时增加全部视为整体平移，再加上尾部上界，p95 最多被抬高约 1.121 × 1.030 − 1 ≈ 15.5%，仍不足 18.3%（推断）。
     - c4/projects 中，候选在 W3 内的块多于 baseline（候选为第 2、3 块，其中 `rec_t14` 第 2 块部分在内；baseline 只有第 3 块），属保守方向。
   - 报告 L779 只列单元格，不列块号，两种算法下都正确，不需要改。

3. "Metrics 文档必须反映的条目"第 7、8 项（:327–330）
   - 第 7 项的入库前提已满足：复签"报告修正"（:299–317）已在修正后的报告中逐条落实，判定列与总结论未变。核对的版本为 994 行、156915 B、CRLF、无 BOM，SHA-256 `75f51d8a1cdecbe673f34c994fb9e52a7e5babc2743a455c2afeda264cf922ed`。
   - 第 8 项的"（现为 150221 B）"已过时，以上面的版本为准；入库前先核对 `.tmp` 原件的 SHA-256。本勘误要和复签一起追加到入库的 `s0b-signoff.md` 副本（保持 LF）。

# AIB-2 W0 复核与接受记录

日期：2026-11-12。结论：AIB-2 W0.FREEZE 第二轮交付（r2，HEAD `fc4db2f`）**接受**，GATE.W0R 可以开放。第一轮（r1）复核提出的 F1–F5 已全部闭环；冻结的名称、签名、66 个 code 与 design 第 10 节取值在 r2 中没有变化。另有四项 P3（G1–G4），不涉及冻结契约，owner 决定并入开闸提交（第 6、7 节）。接受之后，Metrics 改写 MDB-2 时又发现两项 P3（G5、G6）与五处需要上游补充的契约语义（A1–A5），核对授权提示词时再发现一处（A6），owner 决定一并转交（第 9 节）。

本记录是 `tasks.md` 0.6"W0 复核关口"的证据。0.6 本身仍未勾选：wheel、宿主一致性套件、精确版本与摘要要等 AIB-2 交付后记录。

## 1. 被复核的提交

- AI Base worktree：`C:/Users/lsheng2/orca/workspaces/Report_creater_agent/extract-embeddable-agent-runtime`，分支 `codex/extract-embeddable-agent-runtime`，起点为 AI Base main `5757c9c49fc7d71477aa12b5fb431eb80ec47ba0`。
- r1：内容提交 `e96f37db636a7c6b7d749d631d0ec942569f2ffc`，证据提交 `899619a9502ffdc7ff753ba54b32a7e8da69070f`。Metrics 复核结论为有条件通过，提出 F1–F5，修订要求由 owner 以 `handoff-prompt-aib2-w0-amend.md` 转交。
- r2：移动提交 `00f00faa0e6a29030959e97860d0d7079f57ae1c`、修订提交 `3da71981f69d3a8420b6e8d77a8f219e63e1ab73`、证据提交 `fc4db2f22bf49ebaddaa582b2b3d885189c317aa`。
  - 三个提交线性，共改 9 个文件，都在 W0.FREEZE 的 owner paths 内；
  - `plan.json`、两个 checker 脚本、`planning-review.md`、`w0-checker-worklog.md`、`migration-inventory.md` 与 `proposal.md` 未改动。
- 复核方式：Metrics 只读，对 `899619a..fc4db2f` 做增量复核；运行前后 `git status --porcelain` 都为空。
- 下文 AI Base 文件的行号都以 `fc4db2f` 为准。

## 2. 重跑结果

| 检查 | 结果 | 与回执 §12 |
| --- | --- | --- |
| `openspec validate --all --strict --no-interactive` | 11/11 通过 | 一致 |
| `check-planning.ps1` | PASS：nodes 32、ownerRows 32、contracts 10、retiredCapabilities 7、retiredRequirements 53、deltaSpecs 10、documents 19、links 35、changedPaths 27、implementationAuthorized true | 一致 |
| `git diff --check 5757c9c HEAD`、`git diff --check 899619a HEAD` | 都通过 | 一致 |
| `test-planning.ps1 -NoEvidence` | PASS：invalidCases 36、gateCases 20、deltaCases 8、ownershipCases 4、pathCases 3、documentationCases 1、w0AllowanceGreen true、extraGreenCases 5；用时 306 s | 一致 |

links 由 30 增至 35：回执新增 6 条指向 design 的链接；design 原来指向回执的 1 条链接改为文件内锚点，checker 不计文件内锚点，净增 5（回执 :304）。

## 3. F1 的逐字移动

- 用脚本逐节比对 r1 回执的 §1、§2、§3、§4、§6、§7 与 `00f00fa` 中的 design §11.1–11.6，全部逐字相同。
- 移动提交在 §11 之外只把原 §11、§12 重新编号为 §12、§13，并把 `tasks.md:50` 的 "Design section 11" 改为 "Design section 12"。
- 修订提交对 §11 的改动只有 F2–F5 的修订，以及 11.5 中 "section 3 codes" 改为 "section 11.3 codes"；签名代码块与 66 个 code 都没有变化。

## 4. F1–F5 闭环

| 编号 | 闭环位置 | 结论 |
| --- | --- | --- |
| F1 | 冻结契约移入 design §11（:686）；回执头部（:6-9）写明 GATE.W0R 通过前可修订、通过后不可变，§1–4、§6、§7 只留摘要与链接；design :7-8、:102、:216、:259、:326、:629 改指 §11.x；spec delta `embedded-agent-runtime` :236 与 `synchronous-runtime-host` :32 改为 "single runtime code registry"；W4 发布义务写入 `tasks.md:219-221` 与 validation-matrix :163-164 | 闭环；发布义务的归属有误，见 G4 |
| F2 | design §11.4 夹具表（:1118-1128）只冻结名称、作用域与返回协议，依赖参数不受限（:1130-1136），插件不内省签名（:1138-1142）；V15 新增 3 条用例（:226-234） | 闭环 |
| F3 | design :1216-1222：`ai_clock_and_limits` 创建每个测试独立的 `state_dir` 并负责清理，`HostFactory` 原样使用；V10 第 5 条增加"同一 config 调用两次"（:199-203） | 闭环 |
| F4 | design :843-853：八个 facade 方法的 `timeout` 非法时，在任何副作用之前抛 `RuntimeUsageError`/`runtime_usage_invalid`；`start_timeout` 仍为 `configuration_invalid`；注册表 :993 扩展了该 code 的含义；V09 新增用例（:182-186） | 闭环 |
| F5 | validation-matrix V15（:143）恢复独立壳 lane 的判据；§4 新增 standalone shell lane（:268-269）；V01（:129）拒绝 core 依赖 uvicorn，V05（:133）拒绝宿主自称的 308 | 闭环 |

## 5. 0.6"W0 复核关口"逐项确认

| 项 | 要求（上游增补 1） | 位置 | 结论 |
| --- | --- | --- | --- |
| H6 | 启动时限到期时有上限地回滚，复用停止时限，最坏耗时为两者之和；抛出带专用 code 的异常，写明状态目录锁是否已释放、循环线程是否已结束；回滚未按时完成时附带与 `StopResult` 同形的结果；spec 有场景，V10 有用例 | design §3.1（:221-265，总预算 `start_timeout + stop_timeout_seconds` 见 :254）；§11.2（:878-951）的 `StartupFailure(reason_code, state_lock_released, loop_thread_joined, rollback_result: StopResult)`（:886-891）；`RuntimeStartTimeout`/`start_timeout`（:264-265，注册表 :996）；spec `synchronous-runtime-host` 的 "Startup failure has one bounded rollback outcome"（:27-77，8 个场景）；validation-matrix V10 表格行（:138）与 W0 附加用例 1–10（:188-217） | 满足。`rollback_result` 始终存在，类型就是 `StopResult`（§11.5，:1276），比增补 1 的要求更严 |
| D9 | 导出的每个异常都带与 HTTP 错误信封同一套的稳定 code；code 与消息不含 secret；"异常名 → code"对照表冻结 | design §11.3（:952）为单一注册表，66 个小写 code，含异常类、HTTP 状态与结果字段的归属；V01 双向比对注册表，并用合成的 secret 哨兵检查格式化输出（validation-matrix :153-164） | 满足 |
| D10 | 宿主声明托管方式的机制与夹具签名（包括套件 App 包、上限与时钟的注入）已冻结；未声明的方式报告为不适用，不计为通过 | design §11.4（:1098）：ini 选项 `ai_host_modes`（:1101-1105）与不适用的报告文字（:1110-1111）；五个夹具的名称、作用域与返回协议（:1118-1128）；`HostFactory(*, settings, config, apps, start_timeout)`（:1146-1150）；spec `embedded-agent-runtime` :264-284；V15（:143、:219-241） | 满足。F2 之后冻结的是夹具名称、作用域与返回协议，参数列表不冻结 |
| 证据 | 规划证据在 W0 的 HEAD 上重新生成，计数与重跑结果一致 | 回执 §12 的 r2 证据；本记录第 2 节 | 满足 |

## 6. 遗留问题（P3）

四项都不涉及冻结的名称、签名、code 或取值。

| 编号 | 位置 | 问题 | 成因 |
| --- | --- | --- | --- |
| G1 | `planning-review.md:252` | 链接 `[Design section 12](design.md#12-archived-standalone-requirement-disposition)` 的锚点失效，该节现为 §13。扫描本 change 目录、`docs/README.md` 与 `docs/common/`（79 个 md 文件、466 条相对链接，其中 22 条带锚点），只有这一处断链；全仓另有 30 处历史断链，都在 `docs/archive`、`docs/reviews`、已归档的 change 与跨仓库链接中，与 r2 无关 | r2 重新编号时遗漏 |
| G2 | `check-planning.ps1:497-508` | 链接检查去掉 `#fragment` 后只判断文件是否存在，不校验锚点，因此没有发现 G1 | checker 的能力缺口 |
| G3 | `docs/README.md:3`；`migration-inventory.md:6` | 前者把回执标为"W0 回执及 code 注册表"；后者写 "Value/API authority remains design section 10 and the W0 freeze receipt"。F1 之后，取值的权威是 design §10，API、code 与夹具的权威是 design §11 | Metrics 修订提示词的许可路径不含 `docs/README.md`；F1 的引用更新清单漏了 `migration-inventory.md` |
| G4 | `tasks.md:219-221`；`validation-matrix.md:163-164` | 把"V01 改为对照发布版本"交给 W4.REMOVE，但 V01 的测试文件不在 W4.REMOVE 的 owner paths 内（由 W1.CORE 拥有，W4.PACK、W4.QUAL 经 `packages/runtime/` 与 `packages/runtime/tests/` 覆盖） | Metrics 修订提示词 F1 第 5 条的表述。应拆为：W4.REMOVE 负责发布到 `docs/common`；W4.QUAL 负责把 V01 切到发布版本，并在 CLOSE.R 之前确认规范注册表没有只留在 change 中 |

## 7. owner 决定（2026-11-12）

1. 开放 GATE.W0R。
2. 授权实施 W1–W4 的 21 个内部节点：W1.VA、W1.CORE、W1.HOST、W1.R、W1.REPLAN、W2.VA、W2.APP、W2.APPROVAL、W2.RUN、W2.R、W2.REPLAN、W3.VA、W3.UI、W3.APPS、W3.SHELL、W3.R、W3.REPLAN、W4.VA、W4.REMOVE、W4.PACK、W4.QUAL。
   - 外部门禁 GATE.DATA、GATE.LIVE、METRICS.READY 仍要 owner 另行批准；CLOSE.R 与 DELIVERY 不在本次授权内。
   - 按 DAG 依赖，没有 GATE.DATA 时 W4.REMOVE 及其后继不能开始，所以本次实际推进到 W4.VA 为止。
3. G1–G6 并入开闸（G5、G6 见第 9 节）：AI Base 先单独提交六项修复，再提交开闸记录。Metrics 在 W1 回执中复核这六项。
4. 环境：允许创建任务自有的 Python 3.13 venv，从 PyPI 安装 design §9 的核心依赖与测试依赖；允许测试自行启停只绑定 127.0.0.1、端口 0 的环回服务器，不使用固定端口，不留常驻服务。
5. Linux：W1 只在 Windows 上证明端到端切片；Linux 切片延后到 W4.QUAL，由 W1.REPLAN 修改计划。W4.QUAL 的原生 Linux lane 需要 owner 提供环境，缺失时是 open gate，不能算作通过。
6. 不变：GATE.LIVE 之前只用 scripted model，不调用真实模型；GATE.DATA 之前不删除任何数据；不 push，不合入 main。
7. 波次之间不设 Metrics 闸门。Metrics 复核每个波次的回执；有异议时经 owner 转达，AI Base 在下一个节点边界暂停。

上述决定与第 9 节的增补由 owner 以 `handoff-prompt-aib2-w1-w4.md` 转交 AI Base。开闸记录引用的 Metrics 提交见第 9 节末段。

## 8. 对 Metrics 的影响

- 0.6 不勾选，要等 AIB-2 交付 wheel、精确版本与摘要，以及两种托管方式的宿主一致性结果。
- 0.6 要求在 wheel 中确认的名称，W0 已经冻结（design §11.1，:688-877）。Metrics 先按冻结名称改写 design 与 spec，wheel 交付后再逐项核对：
  - design Open Questions 4（task run 查询、取消的同步方法）：`handle.blocking.task_runs.get(principal, run_id, *, timeout)` 与 `handle.blocking.task_runs.cancel(principal, run_id, *, timeout)`，没有第二套查询或取消的名称；
  - "允许匿名 principal 决定审批"的字段：`HostConfig.allow_anonymous_approval: bool = False`；
  - 4.2 使用的审批访问器：`ctx.approval.preview`、`ctx.approval.preview_digest`、`ctx.approval.decided_by`、`ctx.approval.decided_at`；
  - `start_blocking(settings, host, apps, *, start_timeout)` 返回 `BlockingRuntimeContext`，以 `with context as handle` 使用，启动失败经 `context.startup_failure` 读取；句柄提供 `close_http()`、`stop()`、`wsgi_app()`、`ended`、`end_code` 与 `stop_result`；
  - 未运行时抛 `RuntimeNotRunning`，门面等待超时抛 `RuntimeCallTimeout`，在循环线程上调用或 `timeout` 非法时抛 `RuntimeUsageError`；
  - 1.2 的 N 取自 `request_body_policy(settings, apps).max_request_body_bytes`（:780-787），在启动任何运行时资源之前计算。按 §10 的 B 值，Metrics 不经 settings 放大路由上限时，公开最大值为 `chat.message` 的 8388608 字节，N = max(8388608, 1048576) = 8388608，替换 16 MiB 占位；
  - `RuntimeLimits` 的前五个字段与 `LifecycleLimits.stop_timeout_seconds` 必填；
  - 一致性套件：Metrics 在 pytest ini 中声明 `ai_host_modes = blocking_wsgi`；五个夹具可以依赖 `transactional_db`、`live_server`、`tmp_path` 等；`state_dir` 由 `ai_clock_and_limits` 创建；
  - `ToolError` 只接受注册表成员，且都是小写（:1056-1065）；传入未注册的 code 会抛 `RuntimeConfigurationError`。Metrics design :458、:478、tasks 4.2 与 sketches :264、:273 中的 `CONTEXT_BOUNDARY_VIOLATION`、`PREVIEW_DIGEST_MISMATCH` 应改为 `context_boundary_violation`（:1053）与 `preview_digest_mismatch`（:1054）；
  - design Open Questions 3（`session_key`）：:856-861 冻结为完整匹配 `[A-Za-z0-9._:-]+`、以 `<app_id>.` 开头、不超过 200 个 ASCII 字符；`None` 新建会话，空串非法；唯一键为 `(principal.id, app_id, session_key)`；不做规范化、截断或大小写折叠。Metrics 的 app_id 为 `metrics`，`metrics.workbench.{profile_id}` 最长 178 个字符，符合要求；
  - 0.6 要求记录的配置项与默认值，唯一来源是 design §10（:651-685）：心跳间隔、结束流时限与两个在途上限是 A 类运行时默认值（2.0、2.0、4、4），与 Metrics 的取值相同；`stop_timeout_seconds` 没有默认值，由宿主提供（Metrics 为 1.0）；响应块队列的三个上限是 B 类冻结值。心跳与终止事件的 schema 见 §11.6（:1279-1297）。
- 每个波次的 REPLAN 提供开发版 wheel（路径、SHA-256 与依赖快照）。Metrics 用它并行做 `blocking_wsgi` 消费方冒烟，不阻塞 AI Base；冒烟结果不作为 0.6 或 METRICS.READY 的证据。

## 9. 接受后的增补（2026-11-12）

Metrics 按冻结契约改写 MDB-2（提交 `860fbda`）时，又发现两项 P3，以及冻结契约中五处没有定义、宿主无法自行补足的语义（A1–A5）；核对授权提示词时又发现第六处（A6）。owner 于 2026-11-12 决定全部随本次 W1–W4 授权转交：

- G5、G6 与 G1–G4 一起在开闸前修复（第 7 节第 3 条）。两处都在 design §10、§11 之外，修复只让正文与冻结契约一致。
- A1–A6 都是新增，不改动冻结条目，按授权提示词 3.1 的新增规则处理：在引入它的节点内追加到 design §11 的对应小节，标注节点和理由；冻结时已有的条目与已有 code 的含义都不改动。名称由 AI Base 决定，语义按下表。六项都是通用能力，不为 Metrics 设专用分支（design :1065）。

| 编号 | 位置 | 问题 |
| --- | --- | --- |
| G5 | design §7 :500-502 | admission 的拒绝顺序仍附带旧恢复词：`profile_not_declared/correct_request`、`profile_disabled/stop`、`model_not_configured/stop`、`input_schema_invalid/correct_request`。这些词不是注册表 Retry 列的取值（定义见 :982-985）；注册表（:1030-1033）中这四个 code 的 Retry 分别是 correct、repair、repair、correct |
| G6 | design §2 :114-115 | 写 Metrics 在 "binding/starting" 之前计算 N；§11.1（:786-787）只要求在启动任何运行时、线程、锁或服务器之前计算。Metrics 的顺序是绑定端口、计算 N、启动运行时、构造 waitress |

| 编号 | 冻结契约的缺口 | 请求冻结的语义 | Metrics 的依据（本 change 的 design.md） |
| --- | --- | --- | --- |
| A1 | preview 钩子的签名与返回类型没有定义：§11.1（:863-864）把 tool 接口指向 §5–7，那里也没有定义。数据未就绪时 preview 只能抛 `ToolError`，模型只看到 `tool_failed`，看不到阻塞原因 | preview 返回"就绪（内容）"或"拒绝（结果）"之一，就绪内容经 `canonical_json`（§6 :453-455）成为 `ToolApproval.preview`。拒绝时不创建审批、不调用 handler，记一条审计事件（A6）；拒绝结果与 handler 的返回值走同一条结果路径，作为普通 tool 结果返回模型，不带错误 code，在这条路径上失败时 code 与 handler 返回值失败时相同。执行前重新 preview（§6 :468-470）被拒绝时，不调用 handler，审批作废并记 `approval_invalidated`（:1028），本次调用返回拒绝结果 | Open Questions 9 |
| A2 | `ModelConfig.provider` 只有类型 `str`（:748-749），没有合法取值 | 以公开常量给出合法取值，写明每个取值对 `base_url`、`api_key` 的要求；未知取值在启动任何运行时资源之前以 `configuration_invalid`（:990）失败；依赖可选依赖（extras）的取值，写明缺少该依赖时的 code | Open Questions 6 |
| A3 | App handler 或 preview 抛出 `ToolError` 以外的异常时，ToolResult 用哪个 code 没有规定；§11.3（:1076-1087）只要求异常链保密 | `ToolError` 以外的 `Exception` 子类记为 `tool_failed`（:1052），preview 失败时不调用 handler；取消与截止沿用既有 code；非 `Exception` 的 `BaseException` 不在此列；`internal_error`（:989）只用于运行时自身的故障；异常文本与异常链不进入结果与记录 | Open Questions 8 |
| A4 | 注册表的 Retry 列（类别定义见 :982-985）没有导出，宿主只能复制注册表 | 每个导出异常带由注册表派生的恢复类别属性，取值与 Retry 列的字符串相同；根包导出按 code 查询恢复类别的纯函数，可用于 `RunSnapshot`、`ToolResult` 与 `StopResult` 中的 code；二者纳入 V01 的双向比对 | Open Questions 10 |
| A5 | `RuntimeLimits` 前五项必填（§10 :672、§11.1 :711-713），但只有名称与类型。与限额相关的现有 code（`input_too_large` :1035、`admission_limited` :1040、`output_limit_exceeded` :1047、`deadline_exceeded` :1048）都不覆盖 tool 时长、捕获输出与输入 token | 逐项写明作用对象（每次模型调用、每个 run 或每次 tool 调用）、计数方式（token 计数不引入 design §9 以外的依赖）、执行点、超限 code（含义已覆盖的复用已有 code，其余追加到注册表末尾），与 `max_input_bytes`、`max_output_bytes`、`max_run_duration_seconds`、`max_queued_runs` 的区别，以及 TaskProfile 如何收紧 | Open Questions 7 |
| A6 | 宿主 SPI 只给出 `record_audit(event: AuditEvent)`（§2 :125，§11.1 :761）。§6 :480 要求审计审批的请求、决定、作废、消费、过期与结果，migration-inventory :477 把审计事件契约划归运行时，但 §11 没有定义 `AuditEvent` 的字段与事件类别，也没有规定认证失败以外事件的投递方式。唯一定义了投递方式的是认证失败事件（:132-136，§10 :666）：可以丢弃，单事件时限 0.05 秒。审批事件照此投递，宿主的审计表会缺记录且没有任何报错 | `AuditEvent` 带 `event_id`（重投时不变）、`kind`（§11 中的类别表，至少覆盖 :480 列出的事件、A1 的拒绝与认证失败）、发生时间、principal，以及 app、session、run、tool 调用、审批的 id 和结果 code；同一审批、tool 调用或 run 的事件能还原发生顺序；不含秘密、异常文本、tool 参数与 preview 内容。状态转换产生的事件采用事务性 outbox：与转换在同一个持久化事务中写入，异步投递给 `record_audit`，至少一次、失败重试、不丢弃，操作结果不依赖投递；停止时不排空，重启后继续投递。只有认证失败事件保留 :132-136 的可丢弃语义，未认证的请求不触发持久化写入。宿主按 `event_id` 幂等 | Open Questions 11 |

AI Base 开闸记录中，`w0_review` 的 `metrics_commit` 是写入本记录第 1–8 节的提交 `e3c8a8027019d2dde0e491e1ea92cad720550112`；`w1_w4_authorization` 的 `metrics_commit` 是最后修改本节的提交（写入 A6 的提交），全长 SHA 由授权提示词给出。

# Tasks

## Windows Closure Execution Frontier

**当前状态（2026-11-20）**：Windows Dashboard MDB-2 合成数据功能验收已通过。
正式回执为 [`windows-functional-acceptance.json`](evidence/windows-functional-acceptance.json)；
验证源码 `ff09d6ff97dd62e56fb3bfc44914c5c08582a144`，候选仍为 dev4。
114/114 功能证据键、七组完整模块门禁和独立 FUNC.R 均通过；性能为 `NOT_RUN`。
此前完整通过的五组按同源码、制品、环境、命令和报告哈希复用，项目管理 971 项与
脚本 548 项完整重跑通过。原 3600 秒整组超时仍是失败记录；续跑只把项目整组
外层上限设为 7200 秒，未改变单测、生产停止预算或任何断言。
原任务 0.6、6.2、6.3、9.5、10.2、10.3、10.4 保持开放，分别保留 AIB 全局交付、
Linux/镜像、全平台残留门禁及性能义务；其 Windows 功能部分由本回执覆盖。
下一阶段为 W3.REPLAN 和独立性能阶段，未执行其它 App、真实数据或发布操作。
本次收尾提交仅记录文档和回执，其 HEAD 与被测源码 SHA 分开报告。

以下执行授权和过程检查点保留各自的时间、源码与证据范围，不表示当前仍未签收。

**执行授权（2026-11-19，功能验收收尾）**：owner 已批准主线切回功能验收，要求持续执行到
本 topic 的 Windows Dashboard 功能项全部验证通过。沿用本 change 与 114 个功能证据键，
不新建账本，不扩大到其它 Dashboard 产品计划、Linux 或其它 App。
先处置停止/失败恢复可靠性，再固定候选与证据、完成原生/联合/全量模块门禁、
独立 FUNC.R 和正式 FUNC.ACCEPT。停止/取消/持久化/清理约束不后移、不放宽。
正式输入只绑定干净提交；旧失败与旧成功均保留，诊断 PASS 不升级为正式回执。
复用既有 worktree 和安装版候选；协调者独占执行，独立审查不并行改源码。
性能阶段、发布、主线合入和 worktree 删除仍不属于本次执行范围。

全模块收敛检查（尚非最终资格）：metrics 19、bug_metrics 250、jira_sync 32 项通过。
pytest 的通过子测试被计入 JUnit 汇总但不生成独立 testcase；新增执行清单与派生报告
核验保留原 XML、逐项校验实际执行，91 项相关检查及真实模块回放通过。
UI 的大量后续错误源于共享浏览器 fixture 关闭异常后未释放 Playwright；现统一
异常安全清理，17 项反例、32 项相关 UI 回归和实际 driver 故障恢复均通过。
旧 backend 测试入口与旧模块命令写法已改为当前接口，未添加兼容层。
project_management 的 33 项失败集中于旧测试夹具，受影响 72 项已通过；
scripts 的旧文件豁免已移除，SLE 晚退出/身份重查竞态经 RED/GREEN 修复，
保留非零退出的异常判断和 PID 重用防护，59 项消费者回归及真实强制停止通过。
完整资格必须在这些修订的新冻结基线上重跑，不把本轮收敛结果提升为 FUNC.ACCEPT。

`0ab6412` 原生/一致性/恢复、W2.R、迁移/回滚及 49 项业务映射均通过，114 条
证据绑定完成；首次最终 qualifier 的 `ai_host` 全量为 259 passed / 2 failed。
发布失败已定位到 Django SQLite 的读事务升级与审计写入冲突；真实文件数据库
确定性 RED 后，保留应用级发布锁、将历史读取移至写事务之前，10 项发布回归与
独立 6 项发布 owner 检查通过。报告失败来自验收器深目录使 Git 元数据路径过长；
已撤回会改变存档格式的提议，改用 owned root 内的短 `qt` 测试目录，40 项
资格检查回归及原报告恢复用例通过。旧失败完整保留，最终资格仍须新基线重跑。

`d1f8448` 已重新通过原生 56 项、完整一致性 74 项、恢复/观测 39 项、W2.R
1/1 clean pass 与迁移/回滚。随后映射运行 `b4c6da8c-aa8f-4c58-86ac-3aaa1341ea83`
前 40 项通过，但真实仓库边界扫描发现失败恢复测试为记录文件身份而导入私有模块。
现改为从实际 store 对象的类取得源文件身份，不改变故障注入或产品代码；边界、
退役路径及真实失败恢复等 54 项通过。正式回执仍保留其原源码范围，功能验收未签收。

当前检查点：`244c027` 原生 56 项、完整一致性 74 项、恢复/观测 39 项以及同版
迁移/回滚均通过，W2.R 原始回执达到 1/1 clean pass。但随后映射运行
`883e0385-f83a-4e0d-a81a-6fc3c20a27cc` 为 24 passed / 1 failed：
聊天会话请求 504，退出时首次导入 `serve_exit` 阻塞在文件系统查询，看门狗退出 3。
两者不归为同一已证实根因。原预算定向诊断通过，但不作正式验收。
退出模块现移到命令加载阶段；阻止晚期导入的 3 项 RED 及 75 项 GREEN 已记录。
该源码修订须重新冻结与原生/联合验证；最终功能验收仍未签收。

本轮进展：`314441b` 的正式原生回执已通过全部 6 组/56 项，零失败、错误或跳过。
独立复核区分了正常退出恢复与失败收尾恢复；新增 test-only 原生证明已通过，
包括真实 incomplete StopResult/exit3 后恢复、幂等及测试超时清理反例。
产品源码、wheel 和预算未改。新测试快照仍需复核并重新冻结，不将旧原生回执改写为新版本。
证据与后续正式回执见 `evidence/windows-functional-closeout.md`；FUNC.ACCEPT 仍未签收。
冻结验收期间不修改台账，逐节点保留生产者/复核回执，结束后回填同一台账，避免源指纹失效。
`30faf9e` 的后续冻结尝试在信号组盘点进程时出现 WinError 5（发出停止信号之前），
并未形成完整 PASS。现已补显式宿主 PID 子树盘点、保留范围内错误及 PID 诊断；
另用持有读句柄的反例确认测试观测文件的 replace 冲突，改为不可变快照协议。
相关定向检查与恢复用例已通过，组合回归及新基线正式验收继续；未放宽任何运行时限。
后续已明确正式执行的 TEMP/TMP 位于 D；`4d4e00f` 在该记录环境下完成原生 56 项。
补充执行发现 pytest 基目录父路径未创建，最终汇总器亦有同类缺口；RED、39 项回归和
实际子进程门禁冒烟已验证最小修复。下一次干净输入冻结后继续完整一致性和最终资格流程。

**当前执行（2026-11-19，无人值守诊断）**：owner 请求复用 UAC，避免守候 PC。
临时受限管理员助手已启动并通过请求/回执验证，只运行固定采集工具；测试仍用普通令牌，
不安装服务、计划任务或修改安全策略。新采集已经复用该授权完成，无需再次确认。
旧三例 Minifilter 跟踪报告丢失 8,909 个事件，提取也被截断，不作因果判据。
原预算无采样对照与无 Minifilter 的内核跟踪各通过 3 项；SDK stop 为 45-123 ms，
新内核跟踪零事件/缓冲丢失；修正导出器的 raw/converted 时间语义后，可关联 PID/线程/I/O。
完整顺序无采样 B5 也通过 12 项（165.58s），但没有解释旧失败，不能关闭 W2.CERTIFY。
131 个包文件哈希一致；助手与采集/分析工具已安全退出，不修改 KPI。
下一诊断应针对失败路径的队列提交/开始/结束及关闭阶段边界，不盲目重跑相同成功样本。
最新证据见 `evidence/windows-external-diagnostics.md`；此前 UAC 等待记录仅为历史。

**当前执行（2026-11-18，外部诊断）**：owner 已授权系统性能分析权限并确认 UAC。
专用提升权限子进程已验证 WPR 启停；主会话仍是普通令牌，不能把旧权限失败当作持续阻塞。
本轮采用 py-spy 外部采样、受控轻量 ETW 与独立 KPI/架构核对，先定位根因再决定修复或预算。
全量工具冒烟的 5.49 GB 跟踪及高频 native 采样滞后只作为工具成本证据，不用于应用 KPI。
只运行 Windows 合成场景，原验收仍未关闭，不改变候选 wheel、生产配置或真实数据。

外部诊断检查点：50 Hz py-spy 下复现收尾失败，但有采样错误和滞后；同驱动无采样对照通过。
内存模式 ETW 对照也通过，生成 465,567,744 字节跟踪；其初始化/归属关联不足，不能由
“events lost=0”推出证据完整。已准备有界文件模式与 Minifilter 采集，新的三例请求停在
UAC 确认且未启动测试，等待调用方已撤回，旧目录有禁止迟到启动的标记。
详见 `evidence/windows-external-diagnostics.md`。根因仍未确认，不重设 KPI、不宣称架构无缺陷；
该轮 UAC 等待已由上方 2026-11-19 的临时会话取代。

**当前指令（2026-11-18，根因优先）**：owner 要求先深入定位真实根因，再评估实际延时，
最后决定是否调整 KPI；不再把时间预算重规划作为继续诊断的前置批准。
本轮只做 Windows 合成场景诊断：记录关闭链路的墙钟/线程 CPU、文件与数据库 I/O，
并与不含宿主的独立原语实验对照。独立 agent 只读核对存储关闭顺序，主 agent 独占执行实验。
所有新证据在 D 盘独立目录；保留旧失败，不改生产预算、候选 wheel 字节或验收结论。
每个子进程由诊断驱动持有，单次执行有外层安全上限；两次等价失败后必须更换假设或观测。
当前 W2.CERTIFY、W2.R 与最终功能验收继续保持未通过；本轮诊断不是性能 KPI 测试。

诊断检查点：原预算完整 B5 再现了另一处停止失败（真实聊天 lifetime，SQLite commit
处的栈快照）；原不读客户端用例此次通过，不能合并为同一个已证实根因。
修正并排除探针自身的关闭后属性读取错误后，放宽观察窗口的完整 12 项自然完成，
SDK 收尾为 33-71 ms，但它们不是冻结预算的认证证据，也没有解释旧失败。
131 个安装包文件哈希仍匹配；生产预算/KPI 不变。Windows 内核 I/O 跟踪被权限策略拒绝，
尚未获得区分锁、调度与底层 I/O 的最终证据。详见
`evidence/windows-root-cause-diagnostics.md`；当前不是必须修改 timeout，而是根因仍待定位。

**当前阻塞（2026-11-18）**：代码基线 `c9bb950` 的分进程映射检查完整通过 120 项，
但最新原生 B5 为 11 passed / 1 failed，不能关闭 Windows 功能验收。
`CTRL_BREAK_EVENT` 非读取客户端用例在收尾时返回 3；HTTP close 已完成，但
server close/join 超时，随后 SDK stop 未在 1.0s 内完成；诊断栈分别停在
Waitress 输出临时文件 close 与 SQLite connection.close，尚不足以确定根因。
停止结果报告 `runtime_store/state_lock` 未关闭及持久化收尾未确认。
诊断栈和原始失败保存在 `evidence/windows-w2-resume.json` 的 `current_stop_blocker`。
未归因为磁盘、杀软或外部负载，也未把较早的未知 watchdog 失败归为同一根因。
本次相关进程已退出；未改 wheel、阶段预算、10s 总停止上限或持久化要求。
当前按上方 owner 新指令先定位根因，不以批准时间预算重规划作为诊断前置条件；
不得以映射/浏览器用例通过替代失败的原生证明。最终全量 qualifier、FUNC.R、
FUNC.ACCEPT、性能和发布均未完成。下方成功记录保留其原始源码范围。

当前执行更新（2026-11-18）：owner 已批准 B5 拆成两项证明并要求继续。
`B5-r1` 要求真实 AIB 聊天关闭/身份证明与同一安装版适配器、实际 serve 的
active/idle/约 8 MiB 慢读及不读背压证明同时通过；原时限、配额和清理门槛不变。
批准记录见 `evidence/windows-b5-owner-decision.md`。原任务正文及历史 census/摘要保留，
5.6/10.4 的聊天积压来源要求以 B5-r1 为准；批准不等于测试通过。

执行恢复（2026-11-18）：owner 告知已释放磁盘空间，要求继续使用 D 盘并恢复被中断的测试。
不再搬移到 C 盘，不删除原失败目录；先减少单测夹具重复写入，再在新的 D 盘运行目录重跑。
恢复结果：原中断回归已完整通过 52 项，全部 10 种拒绝场景仍执行，大夹具仅生成一次并
逐次恢复原字节；新运行目录总文件量 127,384,558 字节。随后加入候选环境前后指纹及
命令绑定，含迁移相邻消费者的 100 项回归通过；实际 83 包环境与冻结指纹一致。
B5/断开原始记录的语义回放通过。仍待冻结源码的完整原生 CLI、W2.R 与 W3 联合验收。

重启后恢复（2026-11-18）：已核实实际执行目录为 Dashboard `moonfish`，
源码基线 `3dae4be`。上次完整原生运行 `2c16c4cf-df90-4a18-afcb-aa189cad4345`
在 20 次断开均释放后因最终阶段看门狗退出 3，原始日志保留，尚无根因结论。
同一冻结源码单项复测与增加测试诊断后的单项复测均通过；这不替代完整冻结验收，
也不把重启视为修复。诊断仅记录 runtime 停止、退出清点及超时线程栈，不改产品代码、
候选 wheel 或既定时限。独立契约核对确认空闲 project 返回后仍适用 T+1.2s；
它不是 W2.R 签核。后续继续完整原生验收及独立复核，W3 和性能阶段仍未开始。

随后 `d39f914` 的完整原生 CLI 生成 PASS 回执（6 组 56 项，零跳过），
完整 blocking_wsgi 一致性组通过 70 项；两组存在交集，不相加。
独立 W2.R 首轮报告 W2-P1-1：原生回执按输入文件身份绑定，无法被后生成的汇总输入消费。
真实回执回放与端到端 RED 均复现；现沿用迁移验收器的生产输入解析/哈希及关键字段比较，
124 项定向 GREEN 通过。宿主、wheel 和时限未改。原始失败与所有运行目录仍保留；
修复后的冻结原生回执、真实汇总消费和独立复核尚待完成，W2.R 不计 PASS。

最新检查点（2026-11-18）：`3223191` 已完成修复后原生 56 项及 B1/B4/B5
真实汇总消费；独立 W2.R 达到 1/1 clean pass（2 次复核，1 个 P1 已关闭），
W2.REPLAN 为 continue。W3 首轮冻结及合成迁移/回滚均在此 SHA 通过：
9 个 HTTP 检查为 200，新旧版本各保留 1 份发布，原始 94 个文件哈希不变，正常停止。
联合用例首轮 3 passed / 1 failed；发布的业务及 Grafana 断言均通过，但测试入口
在退出观测前导入 `unittest.mock`，导致 `exit_capture_incomplete`。
6 个入口的轻量 RED 仅此入口失败；延后该导入后 21 项退出回归及真实发布复测通过，
Dashboard/Grafana 均退出 0、无 force。实际仓库静态 gate 的 JUnit 见证及反例共 46 项通过。
本次仅测试/验收文档改动；仍需修复后输入再冻结、全量模块门禁、精确的 114 条
functional 证据绑定及 FUNC.R。W3 首轮回执保留，不把它冒充后续修订的最终回执。

`edc59c3` 上四项联合用例已整体通过，核心合同 115 项、静态见证 46 项通过。
正式原生刷新在 signal 组出现 14 passed / 2 failed，其它已执行组通过；
未生成完整 PASS 回执。原始目录为 `conformance-runs/527ed8d4-bbaf-4b64-a3de-3e8d7a9686fc`。
两个观测缺陷分别是 lifetime 已进入 flush 后仍等 HTTP，以及 phase 文件存在但内容未写完。
保持旧逻辑抽取后，确定性 RED 为 5 failed / 5 passed；修复后 11 项 GREEN、
原始两个 Windows 失败用例均通过。仅调整测试观测，所有实际停止/信号时限不变，
正常 lifetime 和其它首个停止触发仍要求 HTTP 就绪；独立复核与最终刷新继续。

`3ecdb07` 的原生 56 项及同版迁移/回滚刷新均已通过。逐条证据核对仍发现少量
缺失断言，因此在最终资格输入前一次补齐了边界/环境一致性用例及冷资产观察。
完整九文件一致性与原需求 census 共 75 项通过，冷启动资产浏览器用例通过；
包括真实满额短请求下的 401、同源导航 503 自动刷新为 200、嵌入 CSP、关闭后 503、
环境哈希/全局 tracer/信号/退出归属保持、Windows Proactor 与慢回调诊断。
独立 Validation Engineer 确认原 5.10 的“未运行”不是“启动前 WSGI 句柄”；
仅修正 census 的过强英文描述，保留全部 114 个功能证据键及原始需求摘要。
不为 Metrics 添加 ASGI/异步认证兼容层，不计入那个无效探针。
绿色报告合并保留全部原始 testcase 并记录输入哈希；失败、skip、重复 ID 均被拒绝。
这不是新增测试次数，也不能代替最终全量模块门禁、功能审查或原生回执。

`8baab7d` 原生回执再次完整通过。首次按映射合并执行的 120 项中 118 passed /
2 failed：Grafana 启动轮询收到请求行回显导致 `BadStatusLine` 未处理；SDK 全进程
句柄基线在混合 GUI/业务进程中未稳定，不能作泄漏结论。原目录
`mapped-proof-runs/ef2b2126-1fe9-40dc-bab4-17e0dec79082` 保留。
HTTP 协议错误家族经 RED 复现后纳入有界启动轮询；通用 SLE 探针同样返回不可达，
没有应用专用分支、额外超时或所有权放行。145 项生命周期/消费者回归、22 项独立
testkit、真实发布复测通过；独立 scoped review 无 P0-P3。映射执行分为独立一致性
进程和普通用例进程，仍要求全部 case 执行，未修改 SDK 资源基线/泄漏阈值。
性能专用基线 helper 的同类轮询留在已延期 PERF.PROBE 范围处理。

此前阻塞记录：B5 12 项、20 次断开、70 项组合一致性和 103 项宿主回归已通过。
原生验收器正在集成；补出的退出码/非有限时长反例已修复，但最新 61 项回归有
59 passed、2 项在写合成夹具时发生 `OSError: [Errno 28] No space left on device`。
`D:/AIGC/artifacts/mdb2-windows-20261117/nv-green1` 是本轮新建的重复合成单测目录，
实测 456,928,257 字节；未删除其中任何证据。原压缩清理提议已由上方“D 盘继续使用”
决定替代，同时改进单测的大数据重复生成，再重跑。阻塞时没有存活的本轮原生测试进程或
运行中的 subagent；尚未提交、冻结、签核 W2.R 或进入 W3。未做磁盘空闲量准入检查。

执行授权更新（2026-11-17）：owner 已明确确认 `8bb83d4` 的计划，并要求连续执行到最终
check out，真实阻塞时询问。`PLAN.R` 已达到 1/1 PASS，`OWNER.RESUME` 已满足。
W1 实现已提交为 `b3fbada10af11230a2d7ecb32995f5e14302cf42`。
独立 W1.R 达到 1/1 clean pass，W1-P1-1 已关闭；W1.REPLAN 的文档再冻结已通过，
W2.VA 独立签核通过，进入 W2.HOST 的负例先行实施；W2.CERTIFY 尚未开始。
Owner 最新排序决定：先关闭全部功能开口，再单独制定性能 KPI、Probe、优化及性能验收。
新增 FUNC.ACCEPT 功能里程碑；V8 性能阶段后移，不降低停止、取消、泄漏及数据完整性门槛。
排序修订经独立 review 后继续既有授权；原 10.4 仅在功能与性能两部分都通过后关闭。
以下原“只编写计划”说明保留为计划创建时的历史。
发布、main 合入、push、worktree 删除及真实用户数据操作仍按计划的独立授权边界执行。

2026-11-17：按 owner 要求细化 Windows 收尾计划并独立审查。本轮只编写计划，
未授权恢复产品实施。执行前须满足独立 `PLAN.R` 和 owner 后续明确批准/恢复。
本文件是唯一进度账本；以下节点组织原有任务，不替代或自动勾选第 0-10 组。

计划入口：[总览](windows-close-plan.md)、
[逐步操作](windows-close-steps.md)、
[验收矩阵及原任务映射](windows-close-validation.md)、
[后置性能阶段](windows-performance-phase.md)、
[结构 DAG](windows-close-dag.json)。
JSON 只存结构，不存第二份完成状态。Windows 里程碑不等于整个 MDB-2/AIB 发布；
Linux、其它 App、真实用户数据和未批准的发布动作保持各自门禁。

- [x] WIN.RECONCILE - 对齐原任务/验收条款、可复用证据和可执行的新旧版本材料。证据：`evidence/windows-coverage.json` 枚举 60 个原任务及 63 条 5.10/10.4 条款；19 个既有附件哈希核对通过；`evidence/windows-release-inputs.json` 固定新 wheel 和旧源码/SDK/环境，旧版实际启动、认证读取及正常停止通过。一次 ABI 不匹配的失败原样保留；这不代表 W3 升级回滚演练已完成。
- [x] W1.VA - 签核安装、Windows 启停所有权及残留 gate 的验证设计。独立 Validation Engineer 签核见 `evidence/windows-w1-validation.md`；包括直接 wheel 安装、pytest/asyncio 依赖对齐、新环境隔离、外部进程不误杀和三类残留 gate 反例。
- [x] W1.INSTALL - 固定依赖和制品来源，完成干净 Windows 安装与 wheel 准入。`windows-release-inputs.json` 绑定 r4 回执、82 个 wheel 与约束哈希；全新 `windows-venv-r4` 的 27 项输入/隔离检查及 15 项准入/包/真实 serve 测试通过，正常退出 0、无 force、端口释放。缺 wheel 的离线安装被拒；源码清单及哈希前后一致。r1 代理超时、r2 缺 Windows 二进制依赖及 r3 下载缓存越界的记录保留，r3 不算最终安装验收。文件大小和空白检查通过；独立整批 review 在 W1.R。
- [x] W1.LAUNCH - 包含 VS Code 和跨工作树入口的实现验证完成；`evidence/windows-w1-launch.json` 与 `windows-w1-review-fix.json` 绑定原生入口、44 项家族补验和真实编辑器停止回执。
- [x] W1.RETIRE - 当前 Windows 边界/残留 gate、58 项检查和默认 smoke 通过；编辑器任务与退役文件存在性已纳入检查。Linux 定义仍延期，不关闭原全平台条款。
- [x] W1.R - 两次独立审查，1 个 P1 修复后达到 1/1 clean pass；范围绑定代码提交 `b3fbada`，见 `evidence/windows-w1-review.json`。
- [x] W1.REPLAN - W2=amend、W3=continue；基线适配要求已写入 steps/validation，五项 S0b 源码哈希未变，18 节点/20 依赖及严格 OpenSpec 检查通过。结构化回执在 `evidence/windows-w1-review.json`；W2.VA 仍须独立签核。
- [x] W2.VA - 独立 Validation Engineer 签核完整 Windows 生命周期、测量、状态演练和汇总检查设计；批准保留真实空闲 ProjectRunRuntime 的 S0b 测试基线适配。原始回执及授权澄清见 `evidence/windows-w2-validation.md`，无新增 owner 决策阻塞。
- [x] W2.HOST - 生命周期实现、原生证明夹具、迁移及验收工具完成；早期回归见 `evidence/windows-w2-resume.json`，最终冻结证明见下方 W2.CERTIFY 和正式功能回执。
- [x] W2.CERTIFY - `ff09d6f` 原生 56 项、完整一致性 74 项及恢复/观测 39 项通过；计数有重叠，不求和。历史 I/O 失败保留，不因本次 PASS 改写归因。
- [x] W2.R - `ff09d6f` 独立 W2 gate 达到 1/1 clean pass，原生生产者/消费者证据绑定通过；精确路径和哈希见 `evidence/windows-functional-acceptance.json` 的 W2.R 引用。
- [x] W2.REPLAN - W2 签核在 `ff09d6f` 判定 continue，随后进入 W3；未改变 wheel 或生产预算，性能判定仍后置。
- [x] W3.FREEZE - 固定 Dashboard `ff09d6f`、AIB `d589ac8`、dev4 wheel、依赖、fixture 及实际环境；回执记录前后干净源码与指纹。
- [x] W3.REHEARSE - 同源码 Windows 合成状态副本的新旧版本切换、语义读取及回滚通过；不关闭原 10.3 的镜像条款。
- [x] W3.JOIN - 完成联合业务映射和七组完整功能模块门禁；同源码续跑明确区分复用与新执行，114/114 功能证据键全部有效。
- [x] FUNC.R - 独立 authority-boundary review 达到 1/1 clean pass；两次 counted review 中一项 P1 已闭环，最终 P0-P3 为零，性能及全局排除范围已核对。
- [x] FUNC.ACCEPT - `evidence/windows-functional-acceptance.json` 已生成；Windows Dashboard MDB-2 功能为 PASS，性能为 NOT_RUN，原 10.4 及其它混合范围父任务保持开放。
- [ ] W3.REPLAN - 以已验收功能基线再冻结后置性能阶段。
- [ ] PERF.KPI - 单独冻结 KPI、负载、基线、采样方法和判定规则。
- [ ] PERF.PROBE - 完成保留的性能工具，独立采集诊断基线，不宣称正式验收。
- [ ] PERF.OPTIMIZE - 按实测瓶颈优化；已达标则记录无需优化，改变行为须功能补验。
- [ ] PERF.CERTIFY - 独占窗口完成正式性能验收，并确认受影响功能再次通过。
- [ ] CLOSE.R - 独立核对功能与性能联合矩阵、证据与后置边界。
- [ ] WIN.ACCEPT - 写入四目标 Windows 里程碑回执，逐条收账而非归档整个项目。
- [ ] DELIVERY - 仅在 owner 明确指定发布动作后执行，保留其它 WIP。

W2.HOST 检查点（未完成节点）：生命周期状态、失效运行时检测、非回环绑定规则、
响应迭代器关闭计数、绝对停止预算、Waitress 线程内 dispatcher 收尾、两阶段 watchdog、
退出清点与显式退出已实现。104 项定向检查通过，既有一致性组 52 passed /
1 ASGI 不适用；真实 Windows stop-file 后第二次 CTRL_BREAK_EVENT 的受控停止场景通过。
证据位于 `D:/AIGC/artifacts/mdb2-windows-20261117/w2-host-focused-r1.xml`、
`w2-conformance-existing-r1.xml`、`w2-native-signal-r1.xml`。这些组有重叠，不相加。
原生正常启动/页面/资产/停止切片为 `w2-native-host-r3`，早先两次失败原样保留。
独立只读资源所有权分析已完成；不是 W2.R 的 counted PASS。
联合验收包装器的 `finally` 退出回执被显式退出绕过，4 个反例复现后改为观察实际
`os._exit`；4 项退出码回执与既有孤立 check 入口测试通过。该验证消费者已加入
W2.HOST owner paths，不增加产品 hook。
仍须补齐完整 V6/V7 场景、其它原生信号/流停止矩阵、功能验收工具及其负例，
再进行 W2.CERTIFY / W2.R；未开始 V8 性能测量、W3 冻结或最终联合验收。
本节点未勾选，当前代码尚未提交，HEAD 仍为 `1dbdd338efaa31f8df1d2f8d9a55a6218c35536e`。

W2 后续检查点：新的真实 served 摘要/报告辅助切片、重复请求、重启恢复均通过，
模型调用仍为两次，两个服务两次停止都为 normal。运行根为
`D:/AIGC/artifacts/mdb2-windows-20261117/w2-served-join/4f770681-651d-4024-a537-a4f25dabb23a`；
最终 stop 回执位于其 `evidence/stop/f761eaf2-516c-4958-808d-bd860d73b592/`。
验收器初稿经协调者集成检查修复了 JUnit 假绿、App/AIB 提交混淆、fixture 摘要语义、
全局 ROOT 污染和缺失需求摘要策略可绕过等问题。当前 26 项 qualifier 检查 +
28 项安装器受影响检查通过；实际 60 条原始需求（含 PUB 两项）的摘要/完整 census
重算也通过。该结果不是独立 W2.R PASS。原生/迁移回执的 producer-owned 语义校验器
仍未实现，验收器对这些 kind 明确拒绝，不具备最终验收能力。
实施 agent 已交回并关闭，协调者接回唯一生产写入；没有运行中的本次测试服务。

排序修订检查点：已有性能 WIP 保留，不是功能收尾前置。混合 B9 条款拆为功能行为
与性能时延两个 aspect，停止/取消/泄漏约束及原生验证不后移。原始需求及
windows-coverage.json 的历史摘要不改写；qualifier 需实现显式 functional/full profile、
完整 census 校验及精确测试路径分流，完成前不得声称功能验收器已经可用。

W2 功能推进：排序修订已提交 `4192656`。functional/full 分流、canonical census 校验、
性能 JUnit 冒充原生测量的拒绝、精确测试分流已实现，66 项定向检查和 35 项功能一致性
检查通过（`evidence/windows-functional-first-progress.json`）；原生/迁移语义验收器仍未完备。
新增原生正常停止及 drain/flush 第二信号矩阵 16 项通过。旧版夹具已补出包含两次修订的
真实落盘报告，实际旧版 HTTP 页面返回 200 且发布记录可见，随后正常停止、模型调用为 0；
见 `evidence/windows-w2-functional-native.json`。初次夹具作者配置不一致和原生测试观察方式
错误的失败样本均保留。迁移工具须验证完整成员集、实际写入进程已停止，并重绑定复制件的
归档根标记与 Git hooks 路径；当前仍在 W2.HOST，未进行 W3 最终演练或 V8 性能验收。
迁移基础已补齐上述保护及快照 ID/目标根防越界，23 项迁移检查与 38 项验收器检查通过。
开发级往返探测已完成：旧版保留数据生成 94 文件快照，新副本迁移/启动/读回/重启/再次读回/
正常停止，独立旧版恢复副本启动/读回/正常停止；两份副本各 6 个发布文件摘要与原件一致，
原快照 94 文件未改动。见 `evidence/windows-w2-migration-development.json`。这不是冻结版本的
W3 回执；仍须完成 CLI 编排、冻结输入准入、producer-owned 语义校验器及剩余宿主功能场景，
再进入 W2.CERTIFY/R。代码保持未提交，未执行性能基准或发布动作。
迁移 CLI 及其语义回放已接入总验收器，仅可覆盖 Windows 的 10.3；当前 133 项定向检查
通过，真实 CLI 对脏源码按预期拒绝且不生成验收输出。三个实际解释器的有序包/导入指纹已
采集，旧 SDK 遮蔽及旧 Base 既有遥测依赖冲突被如实记录，新候选清洁安装门槛未放宽。
按正式目录布局的开发验证完成会话创建/重启保持/同键重开、保留报告读取、RUN_BUSY 与
正常停止；额外嵌套开发路径导致 Git 无法识别仓库的失败样本保留。仍未运行冻结源码的
完整 CLI 正向验收，W2.R 尚未签核；余下五组宿主证明见 `.tmp/mdb2-windows-w2/functional-coverage-reconciliation.md`。
本轮回执：`evidence/windows-w2-migration-cli.json`；正式源码冻结及联合验收状态仍未勾选。
后续功能检查点：实际适配器/服务请求顺序矩阵已补齐，组合一致性组 58 passed；
修复已结束循环被重复提交 HTTP 清理及启动超时信息被清理失败覆盖两项缺陷，原生故障/
相邻清理组 40 passed。上下文退出后立即 os._exit 的跨进程恢复通过：任务结果、会话、
审批及历史均保留，重新开锁且没有重复模型调用。对应 XML 为
`w2-order-runtime-combined-r4.xml`、`w2-native-failures-green-r3.xml`、
`w2-hard-exit-recovery-r2.xml`，均在现有外部 artifact root。真实内部循环故障的额外
子场景、20 次断开、B5 与 conformance driver/最终签核仍未关闭；B5-r1 已获批准，继续实施。
该检查点源码和测试摘要见 `evidence/windows-w2-native-faults.json`，不作为整个宿主或 W3 通过回执。

B5-r1 批准后的开发证明：真实聊天 5 种停止触发、受控 active/idle/约 8 MiB 慢读
5 种触发及不读 2 种触发，共 12 项通过，均正常退出且清理完成；停止耗时分别约
0.17–0.32 秒、3.20–3.24 秒、6.67–6.87 秒。另补独立的 WSGI 队列生产者背压证明，
该测试与 21 项注入 SDK 断言共 22 passed。真实内部循环故障已与公开 stop 场景分开，
原生故障文件 4 passed。证据与失败夹具修复记录见 `evidence/windows-w2-b5-progress.json`。
20 次原生断开证明也已通过：最慢回收 2.04 秒，流名额归零，任务和线程回到基线，
正常退出且未 force。7 个显式一致性文件与 SDK 注入断言合跑 70 passed，未把 ASGI
不适用行当作通过。60 个原任务摘要和 63 条 canonical census 校验仍通过。
这些是脏源码上的定向证明，不是冻结验收；原生语义验收器、W2.CERTIFY/R 和 W3 仍开放。

W1.LAUNCH 执行分工：Implementation Engineer 已交回代码并停止写入，
协调者接回唯一生产写入，补齐停止身份/退出码门禁后继续后续节点。
独立 Architect Planner Reviewer 提前准备 W1.R 的审查矩阵，不提前签核未完成节点。
本批在 W1.R 后统一提交；当前未提交是按此审查边界保留，不代表部署或发布。

W1.LAUNCH 集成细化：发现三个既有 `e2e_start/stop/restart_bug_trend.ps1`
转发入口属于同一启动接口的消费者，已补入 DAG 的 owner paths。已要求本地后端入口
保持 backend-only，避免附带迁移/示例数据/Grafana 写入；解释器必须明确选择，缺失时
拒绝执行，不能回退旧 `.venv` 或 PATH Python。参数转发测试不代替真实 SLE/serve
启停、外部 listener 保护和异常清理证明。安装器针对真实旧 SDK 名称的拒绝检查
也由同一 writer 补齐，再进入 W1.R；r4 已安装环境本身没有该旧包。

W1.LAUNCH 历史一小时检查点（修复前）：实施回执记录 106 项聚焦检查和 141 项受影响回归通过，
但原生用例直接构造 SLE spec，未穿过实际 PowerShell/生产 service JSON；
因此本节点仍未勾选。下一步缩小为真实本地脚本的指定端口启动、停止、再启动切片，
先验证旧 stop-file、端口优先级、真实退出码和无残留，再扩展其余 E2E 入口。
不在每次修正后重复全量 141 项。首轮失败的原生子进程日志已被 pytest 临时目录
轮换，无法补造；已有命令日志及最终日志保留，后续从运行开始使用持久的独立日志目录。
剩余大于 400 行的 stack 脚本和旧审计接口须在同节点完成，不依赖历史大小豁免收尾。

历史交接检查点（最终修复前）：真实入口组曾达 120 项通过，受影响组 144 项通过，并保留 JUnit 与运行日志。
交接核对仍发现两个应在 W1.R 前修正的问题：控制停止 helper 允许空的预期身份；
停止结果记录的是外层成功/进程消失，未保留服务实际退出码。协调者先用负例修正，
不把这些尚缺的证据当作 W1.LAUNCH 已验收。

当前结果：上述缺口已修复。保留进程句柄解决了 Grafana 退出码已就绪、句柄尚未结束时的
过早读取；不增加配置宽限，不把未知值置为 0。真实入口最终 7/7、受影响组 163/163，
四组源码指纹一致、原生测试拥有的进程均已退出。该结果取代上面的历史待修说明；
W1.RETIRE 和 W1.R 仍未完成。

W1.RETIRE 后续结果：当前 Windows 残留检查已通过；默认 smoke 已不再跳过，
其实际启动、页面检查和正常停止通过。生成的 UI fixture 命令已用 PowerShell parser
验证，保留路径中的字面字符。现进入独立 W1.R，尚未开始 W2，尚未提交或发布本批。

W1.R 第一轮：独立 Architect Planner Reviewer 返回 FAIL（P1=1），门禁已记录。
W1-P1-1 的类扩展覆盖 VS Code 任务、三个旧 stack 包装、跨工作树停止和对应检查器；
不只修复一个参数。拟退役无独立职责的包装，让任务调用同一主入口；跨工作树工具
只调当前代码的已登记所有权路径。完整记录在 `.tmp/mdb2-windows-w1/review-state.json`，
W2/W3 重规划结论暂为 amend，须修复复核后再冻结。

W1-P1-1 修复验证：三个冗余包装已退役，编辑器任务直连主入口并传播绑定/执行失败，
跨工作树停止使用当前代码且不按端口取停止权限；残留 gate 纳入编辑器任务和退役文件存在性。
44 项定向检查及真实 VS Code 停止切片通过，回执为 `evidence/windows-w1-review-fix.json`。
当前仅是实现验证完成，等待新的独立 W1.R；未把本地验证转换成 review PASS。

最终 W1.R：新的独立 reviewer 未发现 P0-P3，门禁记录 complete / 1 clean pass。
W1-P1-1 的历史待复核说明由本条取代。代码按审查时的完整暂存树提交，未 push。
W1.REPLAN 结论为 W2=amend、W3=continue：W2.VA 必须明确批准 S0b 基线的保真适配；
不能保真则交 owner 决定，不能用降低阈值、跳过或旧接口恢复代替。

## Original Requirements And Evidence

决策编号指 `design.md` 的"决策 N"；未加模块前缀的 `app/`、`services/`、`out/`、`management/` 路径位于 `project_management/` 下。
第 1 组起的任务原要求在第 0 组全部完成之后开始。owner 于 2026-11-16 明确改为 Dashboard 优先：先锁定 AIB 候选 wheel、版本、SHA256 和实际消费的能力，再完成 MDB-2 迁移和双方联合验收，Dashboard 达到该里程碑后才恢复其他 App 的新增实施。该授权只调整实施顺序，不把候选 wheel 当作 0.6 的最终认证，不降低第 10 组的验收要求。7.6、9.6、9.8、9.9 与 9.10 的既有 AIB-0 修复回执保持不变。

### 2026-11-16 Dashboard 优先实施边界

2026-11-17 owner 补充：当前优先完成 Windows 环境，不执行 Linux、WSL 或 Linux
容器测试。Linux 接口和环境定义保留，其验证后移，不作为本轮 Windows 交付的阻塞条件；
相关跨平台任务仍未验收，不因延期而标为通过。

- 本文件仍是 MDB-2 唯一任务账本，不另建一个重复的迁移计划。当前基线为 Metrics `ee7bfb0e734e1123ba5c611997fedd6052f50049`，该工作树在本次调整前干净；AIB 基线为 `1ba21d258f42d8238557622fe97cefbe286079dc`，已有未提交工作必须单独记录并保留。
- 开始第 1 组之前，候选记录必须固定 wheel 文件名、精确版本、SHA256、构建源身份、依赖约束和 Dashboard 必需的 SPI/UI 能力。不得把旧 wheel、可变源码路径、editable 安装或同名但不同字节的包当作该候选。任何候选替换都产生新记录，不覆盖旧证据。
- Dashboard 必需能力为 `blocking_wsgi` 宿主、唯一宿主认证与 App 绑定、同源嵌入 UI、会话及 ContextRef、tools/preview/审批/审计、host actions，以及摘要和报告辅助的 task-run 端口。SoC 专属工作流、RCA 产品页面和通用 RAG/Skills/Style 不因此变成 Dashboard 联调的前置条件；其未验收状态必须继续如实记录。
- 先用实际候选 wheel 和真实 Django/运行时装配完成一个有界的启动、页面、同源 AI 入口与停止切片，再扩展第 2–9 组。原型桥、替代业务服务或只通过结构检查的假宿主不能作为这个切片的证据。
- 所有持久化、迁移和发布验证使用新建的测试数据或明确受控副本；不迁移或删除用户数据，不读取真实凭据，不调用真实模型或企业 provider，不切换既有服务。Grafana 发布验证只针对该验收拥有的本地测试实例。
- 第 10 组联合验收绑定双方提交、候选 wheel 和测试/环境指纹，覆盖页面、会话保持、上下文切换、审批后发布、重复请求、失败恢复、正常停止及无残留进程。迁移后的消费路径删除对应旧 SDK/sidecar，不保留兼容开关或 fallback。
- 0.6、AIB `METRICS.READY`、原生 Linux/真实模型资格和正式发布仍由各自证据关闭；本次顺序调整本身不关闭任何一项。当前所有未勾选任务保持未完成。

2026-11-16 实施进展：候选 `0.1.0` 已固定为 AIB 源提交 `e8e01d4` 的 wheel，
SHA256 为 `c9101064cdae5aa74246d2a507c706e0791e1d9499b771593a91312bab429216`，
消费端记录在 `ai_host/runtime_artifact.json`。最初宿主原型及其兼容投影未获接受。
现已新增 project_management 自有 typed 运行值、直接使用公共 blocking 门面的端口，以及
`metrics.project_summary@1`、`metrics.report_authoring@1` 自有档案数据；相关单测
32 项通过，摘要 schema 转换的 46 个正负样本保持原有判定。

真实 scripted-model 摘要任务经新端口完成 start/get/result，输出和摘要匹配且模型请求恰好一次。
配置模型的五次空状态、五次含已完成运行的状态测量，加上首次真实档案运行，最大启动值为
12.012899 秒；据此选择 `RUNTIME_START_SECONDS=20.0`，证据见
`evidence/configured-startup-20261116.json`。配置模型的实际 `serve` smoke 已返回首页、
Runtime 页面和页面资源 200，并以 0 退出。上述均不是实际 provider 或完整 Dashboard 验收。

业务摘要/报告服务、旧 wire 校验器和持久化格式仍未迁完；旧兼容投影文件也尚待随调用方移除。
完整审计、project runtime 接线、停止异常路径、AI pane、审批发布及第 10 组联合验收仍开放。
本段不勾选任何尚未满足完整退出条件的任务。

后续进展：摘要执行服务已改为同步 typed 端口，分析请求/观察使用新版记录与严格 reader，
不重建旧 HTTP wire 字段。真实 Git 归档的两项测试通过，覆盖原请求保留、重载、重复接受、
身份及源数据冲突；另有一项真实归档 + 固定运行时 + scripted-model 联合测试通过，
同一摘要重复读取/接受不增加模型请求。当前聚焦组合 62 项通过，文件大小与空白检查通过。
报告辅助服务、项目 worker、运行请求记录、实际工厂注入及其余旧接口仍需迁移；
取消确认字段也须传播到剩余消费者。历史业务数据未被迁移或删除，旧 active wire 的拒绝
不等于允许丢弃历史业务记录。上述只是摘要路径的进展，不关闭整个 5.2 或联合验收。

## 0. 前置条件与外部门禁

2026-11-16 后续候选与任务边界进展：当前消费候选替换为 `0.1.1.dev1`，源提交
`4acc902b2820fd3884502223fac3a7f3339a6935`，wheel SHA256
`4bf24df5927cdcd36f9675948967c3894a4c66e252db5b9b8dffda9223e2b6b6`。
旧候选记录原样保留于 `evidence/runtime-artifact-e8e01d4.json`；当前准入记录仍为
`ai_host/runtime_artifact.json`。新候选增加只读 `task_runs.lookup`，不引入 start fallback。
最终安装包的准入及摘要/报告归档联调共 8 项通过；本地端口重开、状态锁与线程清理
另有 1 项通过。上述使用合成数据及 scripted model，不调用真实 provider/model。

联调发现并修复了应用 UTF-8 JSON 与 SDK 转义 JSON 的哈希差异：应用保留来源哈希，
适配器使用 SDK 公开规范化函数，观察记录同时保留来源及运行时哈希，输出保留 SDK
原始摘要。worker 已切换同步 typed 调用；准入 schema 3、宿主主体、档案绑定、
共享取消预算和 CLI 本地上下文已落地；任务边界的增量复核单独记录，不替代完整里程碑验收。
旧 `project_serve` 命令及其替身测试已删除，关闭断言迁到 `ai_host/tests/test_serve_lifecycle.py`；
`ProjectRunRuntime.stop` 别名已移除，取消在 `request_stop()` 中记录，等待以 0.5 秒分片。
最终宿主组 23 项通过，包含真实 `serve` 的隔离数据库、页面/资产、正常停止和端口释放，
以及启动回滚失败与强制退出；正常进程证据见 `evidence/host-process-20261116-final.json`。
早期测试的归档目录和被动地址解析守卫失败单独保留，未改为成功证据。
后续测试调用方同步：手工准备/日历、CLI refresh 与取消测试不再依赖旧 SDK 构造器、
旧工厂设置或旧 task pack；共享准备回归 18 项、取消回归 21 项及两个真实浏览器场景通过。
前端资产、CSS 与 152 组对比度检查通过。以上仍是任务边界检查点，不是完整 Dashboard 验收。
完整 AI pane/context/tools/审批发布、旧接口和启动脚本清理、第 10 组联合验收
尚未完成。本段不关闭 0.6、5.2 或其他尚未满足完整退出条件的任务。

- [x] 0.1 owner 签署 v2 的 Q1–Q9、五项运行时补充 D4/D5/D6/D7/D9，以及 Docker 部署姿态（单进程 `manage.py serve`，非回环绑定不强制 Basic 认证）。验证：`design.md` "已定输入"与 `proposal.md` Impact 记录了 2026-11-10 的签署范围。
- [x] 0.2 归档前置 change `isolate-dashboard-runtime-instances`、`remove-legacy-ai-base-workbench-embed`、`harden-ai-base-sidecar-and-connector-inputs`，并同步主 spec。验证：commit `3d5d224`；`openspec validate --specs --strict` 与 `openspec validate embed-ai-base-runtime-in-process --strict` 通过。
- [x] 0.3 AI Base 发布 AIB-0：Host 校验、health 与 diagnostics 不含 token、删除 workspace-context sync 路由、拒绝 `browser_origin`。验证：v2 §9 第 1 条的五项验收全部通过，其中 Metrics 现有 launcher 端到端流程 `scripts/e2e_dashboard_ai_stack.ps1` 在 AIB-0 版本上通过。证据（2026-11-11）：Metrics 在 AIB-0 交付的 `c13418f` 上完成第五项验收，run3 通过（`aib0-acceptance.md`）；同时发现 AI Base 侧 AIB-F1（启动脚本把 instance credential 输出到控制台）与 AIB-F2（该凭据经 `-EncodedCommand` 出现在 backend 子进程命令行上），owner 决定两项在 AIB-0 合入 main 前同轮修复；Metrics 侧的 F-a、F-b 由 7.6 与 9.6 处理。AI Base 交付修复后的 HEAD `85f4ea9`，Metrics 按回执第 8 节在该 HEAD 上重新验收通过，AIB-F1、AIB-F2 已证实修复（回执第 9 节）；重新验收另发现 Metrics 侧的 F-d、F-e、F-f，由 9.8、9.9 与 9.10 处理。owner 于 2026-11-11 把 `85f4ea9` fast-forward 合入 AI Base main 并 push 到 origin（`3c3f8b4..85f4ea9`），合入的就是重新验收的 HEAD（回执第 10 节）。AI Base 的 AIB-0 收尾提交 `44cdfa7`（关闭并归档 AIB-0 change、同步三份主 spec，只改 openspec 与文档，按回执第 10 节不需要重新验收）于 2026-11-12 随 AIB-2 规划一起 fast-forward 合入 AI Base main 并 push（`85f4ea9..5757c9c`，回执第 10 节）。
- [x] 0.4 改写 `add-provider-neutral-project-reporting`：W4.REPLAN、W5.N1、W5.APP、W5.MIGRATE、W5.CLIENT、W5.CHAT 与 `sdk-consumer-integration` delta 改为"运行时版本准入"和"进程内 task-run 端口"。验证：`openspec validate add-provider-neutral-project-reporting --strict` 通过；逐条复核这六项任务与该 delta，没有任何未完成任务或 requirement 仍以 HTTP SDK、App 注册或 connector 为前提。证据（2026-11-11）：该 change、本 change 与 `openspec validate --specs --strict` 均通过；`sdk-consumer-integration` delta 已删除，仍有效的规则并入 `project-reporting` delta 的 "Runtime results do not replace application authority"；tasks、design、proposal、`application-integration.md`、`integration-execution.md` 与 report-authoring 现行契约已定点改为端口与 profile 术语；已完成节点的回执和 packet 作为历史证据保留，由该 change tasks 入口的"与 MDB-2 冲突时以 MDB-2 为准"统一覆盖。
- [x] 0.5 在 Metrics 临时分支完成共装 spike（不合入）。S0（uvicorn 组合）已完成，结论 FAIL（`s0-spike-report.md`）：依赖、组合、审批持久化、Proactor 与 blocking 门面、带流停止都通过；C5 不通过，主要页面 p95 是 `project_serve` 基线的 1.82–3.23 倍（门槛 1.2 倍），成本来自 Django 在 ASGI 下的请求路径，不挂 AI Base 的 uvicorn 组合同样超标。owner 于 2026-11-11 选择方向 1，门槛不放宽：Django 保持线程化 WSGI；运行时经 `start_blocking` 运行在 `ai_host` 的专用循环线程上；Django 经 blocking 门面调用运行时；`/ai` 经 WSGI 适配器桥接到同一循环；决策 1、2、3、16 已按方向 1 改写。验证：`s0-spike-report.md` 与 `s0b-spike-report.md` 已提交，S0b 逐项通过以下退出条件：B0 依赖与 `pip check`；B1 组合与生命周期（`/ai` 以 308 重定向到 `/ai/`，`/ai/*` 无凭据返回 401，`root_path` 正确，端口被占用时 2 秒内失败且不启动运行时，其他进程设置 `SO_REUSEADDR` 后也无法绑定正在服务的地址与端口，每种停止触发都以 0 退出，停止期间第二次信号 1 秒内非零退出）；B2 循环为 Proactor，在循环线程上调用门面立即报错；B3 流不被缓冲（事件间隔 100 ms 时首事件不超过 200 ms，到达间隔 p95 不超过 150 ms）；B4 断开在心跳间隔加 1 秒内被发现，20 次断开后没有残留的 task 与线程；B5 一条活跃流和一条空闲流打开时停止，两条流的客户端在连接关闭之前收到终止事件，10 秒内以 0 退出；B6 C5 门槛不变（主要页面 p95 不超过基线的 1.2 倍，测量包含页面引用的静态资源），判定组的静态文件必须经过认证；B7 浏览器子集结果与 stock 一致；B8 记录 WSGI server 与依赖的精确版本；B9 AI 饱和不饿死页面：流达到上限时新流立即得到 503 与 `Retry-After`，短的 `/ai` 请求仍返回 200，同时测量的主要页面 p95 不超过基线的 1.2 倍。只有 Django 线程化开发服务器达标、只有静态文件不经认证的组达标，或者全部不达标时，停止实施，带证据回到 owner。镜像内的并发数据（C7）未测量，只供参考，不作为门槛。S0b 复签通过后，design 与上游提案 v2.1 中依赖终测的取值已按终测结果定稿，owner 已签署 Q10。证据（2026-11-11）：S0b 已完成（`s0b-spike-report.md`），方向 1 可行，未触发停止条件；design 与上游提案已按其结论填写，上游提案先为 v2.1 草案，复签与 Q10 签署后定稿（见本项末尾）。S0b 首轮签核结论为 NEEDS_FIX（`s0b-signoff.md`）：推荐组合（waitress 3.0.2、threads 12、分开限额、flush 收尾）没有作为整体运行；组合宿主没有实现、也没有测停止期间第二次信号的强制退出；B5 只在 waitress flush + stop-file 下满足；B9 的 (b)(c) 不在同一次饱和中测得；停止总时长没有上界。owner 于 2026-11-11 决定 AI pane 冷加载方案 A（线程 14、短请求上限 4、UI 资产在认证后由适配器直出且不计名额，design 背景与决策 1）与停止后显式退出（决策 2、3）。终测（报告 §3.11）在最终组合宿主（waitress 3.0.2、threads 14、分开限额 4 与 4、资产直出、flush 收尾、显式退出）上补测 M1–M6，全部通过：冒烟 19/19；M1 第二次信号 8/8 在 0.07–0.50 秒内以 130 退出；M2 中 B6 与 B9 (a)(b)(c) 在同一次运行中测得，未饱和与饱和两组各 12/12，hold 期间 1944 个短请求全部 200（最大 70.78 ms），第 5 条流 194/194 得到 503 与 `Retry-After: 2`；M3 浏览器子集 11/11；M4 三种触发与慢读、不读 5/5 以 0 退出，触发到进程实际退出最长 6.69 秒；M5 名额归还 15/15；M6 三种反向绑定各 3 次被拒，520 个请求全部由宿主应答 200。复签（2026-11-11，`s0b-signoff.md` 的复签节与勘误）结论 PASS（附条件，不需要重跑）：B0–B9 都有证据（终测证据都出自冻结宿主 `e6e1707d…`），首轮发现 1–11 全部关闭（第 11 条的残余转 7.2）；Metrics 侧的并发活动不改变任何判定，M3 的代码树差异只需披露；条件是报告按复签修正披露与归因（已完成：入库的是 994 行修正版，原件 SHA-256 `75f51d8a1cdecbe673f34c994fb9e52a7e5babc2743a455c2afeda264cf922ed`，入库时只把 CRLF 转为 LF），以及 Metrics 文档落实复签列出的 8 项条目。owner 同日签署 Q10，并决定定序表、两段式看门狗与不重跑 M3；条目已并入 design 决策 1、2、3、14、16 与本文 1.2、5.3、5.5、5.6、5.10、7.2、9.7、10.4，上游提案 v2.1 定稿；报告与复签的入库副本随本项提交。
- [ ] 0.6 AI Base 发布 AIB-2 的 `ai-base-runtime` wheel，提供 v2.1 D1–D12 中本 change 使用的 SPI。验证：AI Base 以独立壳（`asgi`）和 `start_blocking` + `handle.wsgi_app()`（`blocking_wsgi`）两种托管方式通过宿主一致性套件（v2.1 §9 第 4 条）；记录精确版本与 wheel 摘要；确认 wheel 实现与 W0 冻结的公开契约一致（AIB design §10、§11，`fc4db2f`；design Open Questions 3、4 已关闭）：`session_key` 按 §11.1 `:856-861` 校验（完整匹配 `[A-Za-z0-9._:-]+`，以 `<app_id>.` 开头，不超过 200 个 ASCII 字符，不合法时为 `session_key_invalid`）；`HostConfig.allow_anonymous_approval`（默认 `False`）与 4.2 使用的 `ctx.approval.preview`、`ctx.approval.preview_digest`、`ctx.approval.decided_by`、`ctx.approval.decided_at`；`start_blocking(settings, host, apps, *, start_timeout)` 返回 `BlockingRuntimeContext`，以 `with context as handle` 使用，启动失败经 `context.startup_failure` 读取；句柄的 `blocking`、`close_http()`、`stop()`、`wsgi_app()`、`ended`、`end_code`、`stop_result` 与 `ui.asset_url`；同步门面的 8 个方法（包括 `task_runs.get` 与 `task_runs.cancel`）都带必填的 keyword-only `timeout`；`HostConfig.lifecycle`（`LifecycleLimits`，`stop_timeout_seconds` 必填）与 `HostConfig.http_limits`（`HttpLimits`）的字段及 §10 的 A 类默认值；`request_body_policy(settings, apps).max_request_body_bytes`（据此确定 1.2 的 N = 8388608，N1）；响应块队列的 B 类冻结值；§11.6 的心跳与终止事件 schema；`RuntimeNotRunning`、`RuntimeCallTimeout`、`RuntimeUsageError`、`RuntimeStartTimeout` 及其在 §11.3 注册表中的 code；结论写入 `design.md`。W0 复核关口（owner 2026-11-12，Q11）：AIB-2 的 W0.FREEZE 回执经 Metrics 复核通过后才进入 W1，复核按上游增补 1 逐项确认：启动时限到期时有上限地回滚（复用停止时限，最坏耗时为两者之和），抛出带专用 code 的异常并写明状态目录锁是否已释放、循环线程是否已结束，回滚未按时完成时附带与 `StopResult` 同形的结果，AIB-2 spec 有对应场景、V10 有对应用例（H6）；导出的每个异常都带与 HTTP 错误信封同一套的稳定 `code`，code 与消息不含 secret，"异常名 → code"对照表已冻结（D9）；宿主声明托管方式的机制与夹具签名（包括如何注入套件自带的 App 包、上限与时钟）已冻结，未声明的方式报告为不适用、不计为通过（D10）；规划证据在 W0 的 HEAD 上重新生成（check-planning、test-planning 与 `openspec validate`），计数与重跑结果一致。进展（2026-11-12）：AIB-2 规划（v2.1 修订 `5757c9c`）已合入 AI Base main 并 push，owner 已授权从 W0.FREEZE 开始实施（main 上的 `plan.json` 仍记 `implementation_authorized=false`，由实施分支改为 true）；Metrics 核对规划回执的四项发现中，三项接口问题作为增补 1 的 W0 输入，第四项（已提交的 `planning-check-tests.md` 记 links 18，在 `5757c9c` 上重跑为 19，证据生成于最后一次编辑之前）由重新生成证据解决；R24 的空闲停止耗时（预算 770 ms、余量 230 ms）在规划中是估计值，以实施后的实测为准。W0 复核（2026-11-12）：W0.FREEZE 首轮交付（`899619a`）有条件通过，提出 F1–F5；第二轮（`fc4db2f`）经增量复核接受，H6、D9、D10 与规划证据逐项满足，GATE.W0R 开放，四项 P3（G1–G4）并入开闸提交（`aib2-w0-acceptance.md`）。接受之后增补两项 P3（G5、G6）与六项契约新增请求（A1–A6：preview 拒绝语义、`ModelConfig.provider` 合法取值、非 `ToolError` 异常的 code、恢复类别的导出、`RuntimeLimits` 前五项的语义、审计事件的结构与投递），随 W1–W4 授权转交（接受记录第 9 节）；wheel 交付后按 design Open Questions 6–11 逐项核对，据此确定 `provider` 常量的取值，并复核 `RuntimeLimits` 前五项的暂定值。owner 授权 W1–W4 的 21 个内部节点；GATE.DATA、GATE.LIVE 与 METRICS.READY 另行批准，因此本轮实际推进到 W4.VA。Linux 切片延后到 W4.QUAL，原生 Linux 环境由 owner 提供。0.6 要求记录的名称、配置项、默认值与 schema 已由 W0 冻结（AIB design §10、§11，接受记录第 8 节），本 change 的 design、spec 与 tasks 已按冻结名称改写；wheel、精确版本、摘要与两种托管方式的一致性结果仍待 AIB-2 交付。W1 复核（2026-11-13）：AIB-2 按授权第 4 节第 2 条停在 W1.HOST（`ac061ee`）。owner 作出三项决定：WSGI 请求体按合作式时限读取，宿主前提是 server 在调用应用之前完整缓冲请求体（OD-W1-1）；依赖资产生产者的正向断言改排到 W3，W3.UI 完成之前以登记的诊断计为 pending（OD-W1-2）；loop 硬卡死仍在时限内返回 504 只适用于 `blocking_wsgi`（OD-W1-3）。三项决定不改 AIB design §10、§11，不新增取值、公开 API、配置项或 code；Metrics 的配置与 1.2 的 N 不变。W3.R 之前的 wheel 都带 pending，不作为本项的认证证据。回执中与决定无关的六项缺陷（W1-F1 至 W1-F6）须在 HOST 终审之前修复。决定经 `handoff-prompt-aib2-w1-host-decision.md` 转交后 W1.HOST 恢复（`aib2-w1-review.md`）。W1 复核续（2026-11-13）：D/E（`bcf1fc6`、`80c4de5`）之后 AIB-2 再次停在 W1.HOST（`069ce23`），理由是 DiagnosticsSnapshot 没有 loop lag 等观测字段；复核认定为 W0 遗漏：W0 冻结了观测义务、HTTP 与门面入口和类型名，没有冻结字段。owner 作出 OD-W1-4：按原授权 3.1 增补 9 个观测字段（进入 RUNNING 的时刻、loop lag 当前值与峰值、卡顿次数、两类在途数与拒绝数、短请求名额的最长占用时长），尾延迟只取 max，`GET <root_path>/api/diagnostics` 与门面同源，不新增配置项或 code。复核另记两项缺陷：快照没有投影 dropped-auth-audit 计数（W1-F7）；App 路由没有挂在 `apps/{app_id}` 命名空间下（W1-F8）。Metrics 配置不变，5.10 经快照观测；决定经 `handoff-prompt-aib2-w1-diagnostics-decision.md` 转交（`aib2-w1-review.md` 第 6–9 节）。

## 1. 依赖、`ai_host` 骨架与导入规则（决策 1、4、6、12）

- [x] 1.1 在 `requirements.txt` 中精确固定 `ai-base-runtime`（0.6 的版本）与 `waitress==3.0.2`，`portalocker` 升到 `4.4.2`；Django 6.0.7 与 whitenoise 6.12.0 不变；`uvicorn`、`starlette`、`cheroot` 与 `a2wsgi` 不作为直接依赖；`gunicorn`、`ai-base-application-sdk` 与 `requirements-ai-task.txt` 分别在 6.2 与 5.7 随其使用方一起删除。`ai_host` 使用 waitress 的内部接口（决策 3），升级 waitress 前要重跑 S0b 的 B1、B4、B5、B9 子集与宿主一致性套件（决策 1）。验证：新 venv 中 `pip install -r requirements.txt` 成功、`pip check` 无冲突，下载的 wheel 摘要与 0.6 记录一致；`requirements.txt` 中 `ai-base-runtime`、`waitress` 与 `portalocker` 都以 `==` 固定，不含 `uvicorn`、`starlette`、`cheroot` 与 `a2wsgi`。
- [x] 1.2 新建 Django app `ai_host` 并加入 `INSTALLED_APPS`；实现 `ai_host.settings`（构造 `HostConfig` 的函数读取 `METRICS_AI_MODEL_BASE_URL`、`_NAME`、`_API_KEY` 三项只读环境变量，API key 为 `SecretStr`，三项齐全时设置 `HostConfig.model = ModelConfig(provider=..., name=..., base_url=..., api_key=...)`（`provider` 取 `ai_host.settings` 中的常量，取值见 design Open Questions 6）；`build_settings()` 只构造 `RuntimeSettings`，不读模型变量，`RuntimeLimits` 前五项取 design Open Questions 7 的暂定值（4、60、65536、65536、16384）；状态目录固定为 `METRICS_STATE_DIR/ai-base`；挂载路径按决策 1 由规范化的 `METRICS_BASE_URL` 得出；以下取值是常量（决策 1、2、7）：server 线程数 14，流与其他 `/ai` 请求各自的在途上限 4 与 4（`HostConfig.http_limits` 的 `max_streams` 与 `max_requests`；UI 资产与未认证的请求不计入），AI pane 门面调用的时限 1 秒与信号量上限 2，空闲流心跳间隔 2 秒与结束流时限 2 秒（`HostConfig.lifecycle` 的 `heartbeat_interval_seconds` 与 `http_close_timeout_seconds`），启动时限 `RUNTIME_START_SECONDS`（经 `start_blocking` 必填的 keyword-only 参数 `start_timeout` 传入，取值见 design Open Questions 5），停止各段的截止时刻（结束流 t0 + 2、排空 t0 + 3、flush t0 + 6.5、HTTP 停止 t0 + 7.5 秒）、project run 停止按 0.5 秒计、运行时停止时限 1.0 秒（`HostConfig.lifecycle.stop_timeout_seconds`，必填）与显式退出 0.5 秒（按 S0b 终测 M4 定稿），两段式看门狗截止 t0 + 9.2 秒、有执行中的 run 时 t0 + 659.2 秒、`wait_stopped` 在 T 返回后 T + 1.2 秒（决策 3），请求体上限 `max_request_body_size` = N + 1 = 8388609（N = max(`request_body_policy(settings, apps).max_request_body_bytes`, `RECOVERY_LIMIT`) = 8388608，在启动任何运行时资源之前计算，决策 3、N1），以及退出清点白名单（R24-host，决策 2，每项记录注册者并标明是否为必需的清理）；模型是否已配置只由构造 `HostConfig` 的同一个函数判定，pane 状态复用该函数；允许 Host 取自 `ALLOWED_HOSTS`，经 `HostConfig.allowed_hosts` 传入；`NetworkPolicy` 不含代理且 `trust_env=False`）与 `ai_host.state` 生命周期对象；在 `.env.example` 中说明三项模型变量。验证：`ai_host/tests` 覆盖三项齐全时 `HostConfig.model` 为对应的 `ModelConfig`、任一缺失时只报告缺失的变量名、`METRICS_BASE_URL` 为空、`/`、`/metrics/`、`metrics` 时挂载路径分别为 `/ai`、`/ai`、`/metrics/ai`、`/metrics/ai` 且与 `ui_web` 页面路由的前缀一致、线程数减去两个 `/ai` 在途上限后至少保留 6 个页面线程（页面并发 4 加余量 2）、pane 信号量上限小于页面保留的线程数、停止各段的截止时刻严格递增，且检测 0.5 秒、HTTP 停止截止、project run 0.5 秒、运行时停止时限与显式退出 0.5 秒之和不超过 10 秒、看门狗的三个常数由同一组常量推出（10 − 0.5 − 0.3 = 9.2、0.5 + 659.2 + 0.3 = 660、1.0 + 0.5 − 0.3 = 1.2，0.3 是看门狗到期到进程退出的预留）、`max_request_body_size` 等于 N + 1 且 N 不小于 `RECOVERY_LIMIT`、缺模型时 `HostConfig` 不含模型且 pane 由同一函数判定为 `not_configured`、状态目录不能单独配置、`repr` 与日志不含 API key；`manage.py check` 通过。
- [x] 1.3 实现 `ai_host` helper `run_sync`：`sync_to_async(..., thread_sensitive=False)`，在工作线程内调用前后各执行一次 `close_old_connections()`。验证：单测断言调用不在事件循环线程上执行、两个并发调用不排队等待同一线程、调用前后各关闭一次过期连接。
- [x] 1.4 增加导入规则 gate（import-linter 或等价测试）：只有 `ai_host` 导入 `ai_base_runtime` 与 `waitress`；任何模块不导入 `ai_base_runtime._internal` 或 AI Base 的 `app.*`；project_management 不导入 `ai_host`；各模块 `app/domain/` 不导入 Django、asgiref 与运行时。验证：逐类植入违规时 gate 失败，当前树上通过；gate 命令写入 `.github/ai-governance/repo-context.md` 的验证命令。

## 2. 宿主 SPI：认证、审批与审计（决策 4、14）

- [x] 2.1 从 `metrics/middleware.py` 的 `BasicAuthMiddleware` 抽出纯函数 `check_basic_authorization`，中间件与 `MetricsHost.authenticate` 共用；`authenticate` 是普通函数，由运行时的 WSGI 适配器在 WSGI 线程上、准入之前调用（v2.1 D3、H7）；未配置 Basic 用户时返回匿名 `local_operator`，认证失败返回 `None`。`METRICS_BASIC_AUTH_USERS` 改为 fail-closed（决策 14）：settings 加载时未设置或空字符串为未配置，其他取值必须是至少有一个条目、键和值都是非空字符串的 JSON 对象，否则抛只含变量名的 `ImproperlyConfigured`；`check_basic_authorization` 只把 `None` 视为未配置，非空字典以外的值一律拒绝；运行时路由的 401 使用同一个 `WWW-Authenticate` 质询头（v2.1 D3）；README 的 Basic 认证说明写明格式错误时启动失败。验证：同一组请求头分别经中间件与 `authenticate`，有效凭据得到同一 principal，缺失或错误凭据两边都拒绝且带同一质询头，未配置时得到匿名本地操作者；在不读取 `.env` 的子进程中以 JSON 数组、非对象 JSON、`{}`、空用户名或空密码加载 settings 都失败，错误只含变量名；settings 中的值为列表、字符串或 `{}` 时请求一律得到 401；现有中间件测试（`ui_web/tests/test_project_access.py`）不改断言即通过。
- [x] 2.2 实现审批授权：`HostConfig.allow_anonymous_approval`（允许匿名 principal 决定审批，默认 `False`）只在 development settings 中以常量打开，不读环境变量；`can_decide` 返回真。验证：在不读取 `.env` 的子进程中分别加载 production 与 development settings，只有 development 允许；设置任何同名环境变量都不改变结果。
- [x] 2.3 新增 `ai_host` 只追加审计模型与迁移；`record_audit` 经 `run_sync` 把会话、tool 调用（含 preview 拒绝）与审批（请求、决定、作废、消费、过期）事件写入审计表，字段含 `event_id`（唯一约束）、事件类别、发生时间、principal、session id、run id、`tool_call_id`、tool 名称、审批 id、结果状态与运行时给出的事件顺序；运行时至少投递一次（增补 A6），同一 `event_id` 再次投递时不新增行、不报错；`record_audit` 在有界时间内返回或抛错（A6 宿主义务，运行时不另设时限）：一次投递只做一次插入，以 `event_id` 唯一约束去重（插入冲突视为已写入并正常返回，不先查后插），等锁不超过 SQLite busy timeout（`sqlite3` 默认 5 秒，`DATABASES` 未覆盖），超时抛错由运行时退避重投；stop 时被取消的投递之后会再次投递；可能与认证失败事件的 `record_audit` 并发；字段与类别以 A6 冻结的 `AuditEvent` 为准，wheel 交付后由 0.6 核对；认证失败事件不写数据库，只输出一条结构化日志 `ai_auth_failed`（path、客户端地址与原因）。验证：`manage.py makemigrations --check` 无遗漏；单测断言字段完整、同一事件投递两次只有一行且 `record_audit` 正常返回、另一连接持有写锁时 `record_audit` 在 busy timeout 到期后抛错而不挂起且审计表不新增该事件、锁释放后再次投递恰好写入一行、更新或删除审计行被拒绝、审计行与日志中不含 API key、Basic 密码、`Authorization` 头或 provider token，且不写 `BugTrendAuditEvent`；认证失败时审计表行数不变，并恰好输出一条 `ai_auth_failed`。

## 3. 发布记录 `AiChartPublication`（决策 8）

- [x] 3.1 新增 `bug_metrics.AiChartPublication` 模型与迁移：每次执行一行，状态为 `published` 或 `failed`（带错误码）；`tool_call_id` 唯一；`supersedes` 指向同 uid 的上一条 `published` 行并加唯一约束；字段满足 `grafana-render-config` 与 `ai-dashboard-publish-authority` 的列表与审计要求。验证：模型测试覆盖重复 `tool_call_id` 被拒绝、两行不能取代同一行；`makemigrations --check` 通过。
- [x] 3.2 在 bug_metrics 公共 API 中实现确定性的发布 preview（返回 `{dashboard, target:{grafana_base_url, uid}}`，uid 由工作流信封与 profile 渲染配置确定，不读当前时间或随机数）和"导入已批准字节并写入 `AiChartPublication`"（复用 `import_grafana_dashboard_payload`，`overwrite: True`；`tool_call_id` 重复时返回已存结果）。验证：同一参数两次 preview 字节相同；同一数据以不同行顺序读出时 preview 字节相同；数据变化后摘要不同；Grafana 不可达时写入 `failed` 行且不报告成功；导入成功、写库前失败后重试得到同一结果；`nvu-ttl-hsdes` 的 `new_critical` 预览返回 `needs_metric_recipe`。
- [x] 3.3 发布历史改读 `AiChartPublication`：新增只读路由 `/api/ai-publish-history/`，同一 uid 的取代链中最新的 `published` 行标记 latest，被取代的行仍列出；`bug_metrics/app/api/ai_context.py:270-271`、`bug_metrics/app/api/ai_dashboard_api.py:73-74` 与 `ui_web/facades/bug_trend_ai_facade.py:61-62` 的历史调用链改接新查询；删除 `bug_metrics/app/api/ai_dashboard_approval.py:131-177` 由 `BugTrendAuditEvent` 推导历史的逻辑、`ui_web/urls.py:238` 的 `api/ai-dashboard/publish-history/` 路由与 `AiDashboardPublishHistoryApiView`（`ui_web/views/ai_dashboard_publish_view.py:117`）；`ui_web/workbench_registry.py:86`、`ui_web/views/ai_dashboard_view.py:249` 与 `ui_web/templates/ai_dashboard_workflow.html:218,233` 改指新路由。验证：视图测试断言响应字段符合 `grafana-render-config` 的 "AI-generated Grafana dashboards are listed and auditable"，发布被取代后最新行标记 latest 且先前的行仍列出，旧 `BugTrendAuditEvent` 发布行不出现，旧路由返回 404；`ui_web/tests/test_ai_dashboard_publish_authority.py:366` 起的历史用例改为断言新路由；workbench 的发布历史视图与浏览器用例通过。

## 4. Metrics App 包：tools、context provider 与 host actions（决策 4、7、8）

- [x] 4.1 实现 `read` tool `metrics.catalog` 与 `metrics.chart_workflow`：async handler 经 `run_sync` 只调用各模块 `app/api/` 公共 API，失败按 design 决策 4 处理（只用注册表中指定的 `ToolError`，其余以类型化的业务结果返回）；工作流信封删除 gcx 与 dry-run 交接，草稿作为 tool 输入校验（`provider-ai-dashboard-composition`）。验证：用 testkit `RuntimeHarness` 与脚本化模型调用两个 tool，覆盖 Jira 与 HSD-ES profile 共用同一组合面、草稿校验失败返回带字段路径与原因的 findings（类型化结果，不是运行时错误）；参数模型含 actor、approval id、proof id 或 workspace key 字段时 App 包测试失败。
- [x] 4.2 实现 `external` tool `metrics.publish_chart`：`preview` 使用 3.2；handler 只反序列化 `ctx.approval.preview`，核对 `canonical_digest(...) == ctx.approval.preview_digest`（否则 `ToolError("preview_digest_mismatch")`），操作者取 `ctx.approval.decided_by`（`Principal`，身份取其 `id`），幂等键为 `ctx.tool_call_id`；发布就绪在请求审批之前判定（`provider-facts-and-sync`）。验证：harness 测试覆盖批准后导入并写入 `published` 行；审批被拒绝或过期时不调用 handler 与 Grafana，tool 结果说明原因；审批与执行之间数据变化时审批作废且不调用 handler；preview 内容与摘要不一致时拒绝导入且不调用 Grafana；数据未就绪或语义不受支持时不创建审批（拒绝的形状依赖 design Open Questions 9）；harness 重启后重放同一 `tool_call_id` 只有一行发布记录、审批只消费一次；聊天中模型声称已获批准或给出 `demo` 前缀的 approval id 时，审批保持 pending 且不调用 handler。
- [x] 4.3 实现 `WorkbenchContextProvider`：`validate` 检查标识对当前 principal 可见；`resolve` 把 `bug_metrics/app/api/ai_context.py` 的上下文包改为每次按 `ContextRef` 生成（字段 `context_ref`、`bundle_version`、`boundary`、`files`），不再推送到 workspace；binding 无法解析时返回 `binding_unresolved` 与 Scope Library 修复入口。tool 按 `ctx.context_ref` 解析出的边界复核参数，越界抛 `ToolError("context_boundary_violation")`。验证：单测覆盖 HSD-ES 与 Jira 两种 bundle 形状、越界调用不读写 Metrics 数据、没有 `ContextRef` 的会话调用需要 scope 的 tool 时返回提示从 workbench scope 打开聊天的类型化结果（不是运行时错误），且不默认任何 profile。
- [x] 4.4 由 `WorkbenchPageQueryState` 在服务端构造 `ContextRef(kind="metrics.workbench")`：只含 binding key、profile、provider、range、chart、bucket/series 与已选 ticket id；值只能是 str/int/bool 或它们的扁平列表；规范化后不超过 4 KiB；ticket id 最多 50 个，超出数量或字节上限时按选择顺序保留能放入的最长前缀，并写入 `ticket_ids_total`（int）与 `ticket_ids_truncated`（bool）。验证：单测覆盖 51 个已选 ticket 时保留前 50 个并带截断元数据；50 个 80 字符的 id 加其他字段的最大取值时，结果是不超过 4 KiB 的最长前缀且元数据正确；结果不含凭据、私有路径或查询文本。2026-11-16：17 项 context 正负样本通过；真实页面 Ask AI 经服务端绑定已选 ID，不再发送票据正文的私有 iframe 消息。
- [x] 4.5 声明 host action `metrics.openChart`、`metrics.openEvidence`（只做 UI 动作），并在 Metrics 测试中对 `METRICS_APP` 运行 `check_app_package`。验证：`check_app_package` 通过，含 `metrics.publish_chart` preview 两次摘要相同；注册表包含 4.1、4.2 的三个 tool、context provider `metrics.workbench` 与两个 host action。

## 5. 组合根、`serve` 与 task-run 端口切换（决策 1、2、3、9、10、11、12、15）

组内按编号执行，作为一个单元验证：5.7 删除 sidecar 时代的组合之后，全栈验证在 5.9 恢复；5.8 在旧写入方删除之后再切换准入记录格式。

- [x] 5.1 新增 `project_management/ai_profiles/`，以数据保存 `metrics.project_summary` 与 `metrics.report_authoring` 的 schema 与 instructions，并经 project_management 公共 API 暴露；`ai_host.package` 把它们转换为 `TaskProfile` 并声明在 `METRICS_APP.task_profiles`。验证：`check_app_package` 通过，含两个 profile 的 schema 校验；profile 版本是精确值。
- [x] 5.2 把 `out/ai_task_contract.py` 与 `out/report_ai_task.py` 改写为同步 task-run 端口协议（入参与返回值是 project_management 自有值类型，请求引用精确 `id@version`，不用 `latest`）；摘要分析、报告辅助与 project run worker 改为调用端口，删除 AI 路径上的全部 `asyncio.run`（`services/report_assists.py:64,75,105`、`services/project_run_worker.py:196,322`）；运行时的错误码及其恢复类别按 design 决策 10 传递（类别按错误码取自 AIB 注册表的 Retry 列，不由旧的恢复词换算），据此改写"请求被拒"的判定（`services/summary_analysis.py:64-68`、`services/report_assists.py:226`、`app/domain/task_run_observations.py:24`）与使用旧恢复词的测试夹具（`tests/project_run_fixtures.py:199`、`tests/test_report_assist_recovery.py:43`、`tests/test_summary_analysis.py:155-168`、`tests/test_summary_attempt_admission.py:44,54`、`tests/test_summary_delta_journal.py:73,101`、`tests/test_analysis_cancellation.py:193`、`tests/test_project_run_cancellation.py:319`）。验证：假端口单测覆盖三条路径；运行时的错误码与恢复类别原样返回，夹具中的类别与注册表一致（`run_not_found` 与 `backend_failed` 为 `observe`，`profile_disabled` 与 `model_not_configured` 为 `repair`）；端口未安装时返回 `RUN_UNAVAILABLE`；这两个文件中不再有 `asyncio.run`。
- [x] 5.3 把 `build_project_runtime` 移到 `app/api/project_runs.py` 并接收 `task_runs=port`；提供 CLI 端口工厂注册点与 `open_local_task_run_port()`；`project_run --execute-local` 遇到 `RuntimeBusy` 时以 `RUN_BUSY` 立即失败并提示通过服务提交；端口工厂以 project_management 自有的错误类型报告清理失败（带错误码，决策 10）时，`project_run` 照常写出 JSON 结果或错误，再向 stderr 写 `project_run cleanup failed.`（有错误码时附带），flush stdout 与 stderr 后 `os._exit(3)`，不等待剩余线程，与退出码 1 同时出现时取 3；端口请求带 `client_run_key`（现有 `clientRunKey`）；`ProjectRunRuntime.stop`（`project_management/runtime.py:54-81`，`:75` 是一次 `join(timeout_seconds)`）拆为两段（决策 2 第 7.4 步）：`request_stop()` 在锁内停止受理、清空排队的 run、对排队与执行中的 run 请求取消，返回是否有执行中的 run；`wait_stopped(timeout)` 按不超过 0.5 秒分片 join worker，总时限不变，返回 `RuntimeStopResult`；删除旧 `stop`，不保留别名，调用方改用两段调用（`project_management/tests/test_project_runtime.py:157,175,177,185,193,226,261` 与 `ui_web/tests/test_report_daily_ui_browser.py:491`；`project_serve.py:70` 随 5.6 删除）。验证：project_management 单测覆盖未注册工厂时返回 `RUN_UNAVAILABLE`、`RuntimeBusy` 映射为 `RUN_BUSY`、端口工厂报告清理失败时先写出 JSON 结果或错误、再向 stderr 写 `project_run cleanup failed.` 并以 3 退出（运行失败时也取 3；在子进程中运行或注入退出函数，不在 pytest 进程内调用 `os._exit`）、提交给端口的请求引用精确的档案 `id@version` 并带 `client_run_key`、同一 attempt 重试时键不变、`request_stop()` 在有执行中的 run 时返回真且空闲时返回假、`wait_stopped` 每次 join 不超过 0.5 秒且总等待不超过时限、`ProjectRunRuntime` 不再有 `stop`；改写后的调用方测试通过。
- [x] 5.4 在 `ai_host.task_runs` 实现 `RuntimeTaskRunPort`（基于 `handle.blocking.task_runs`，`task_runs.start(principal, request, timeout=30)`，`request` 为 `RunSubmit`，`timeout` 是门面方法必填的 keyword-only 参数；门面抛 `RuntimeNotRunning` 或等待超时抛 `RuntimeCallTimeout` 时映射为 `RUN_UNAVAILABLE`）与基于 `start_blocking` 的 `local_task_run_port`（`context = start_blocking(..., start_timeout=RUNTIME_START_SECONDS)` 后以 `with context as handle` 进入运行期，启动超时 `RuntimeStartTimeout`（code `start_timeout`）为 `RUN_UNAVAILABLE`；启动回滚没有按时完成（`context.startup_failure.rollback_result` 的 `completed` 为假）或离开 `with` 块时的第二段停止没有按时完成（`handle.stop_result` 的 `completed` 为假）时以 5.3 的错误类型报告清理失败，决策 10），由 `ai_host` 的 `AppConfig.ready()` 注册为 CLI 端口工厂（工厂被调用时才导入 `ai_host.wiring`，决策 2 第 1 步）。验证：testkit 脚本化模型下端口以提交用户的 principal 启动运行；门面等待超时（`RuntimeCallTimeout`）时返回 `RUN_UNAVAILABLE`，以同一个 `client_run_key` 重试只产生一次运行；在事件循环线程上调用门面立即抛 `RuntimeUsageError`；没有服务进程时 CLI 端口在自身进程中完成运行，退出时释放状态目录锁；注入启动时限到期且回滚按时完成时 `project_run --execute-local` 得到 `RUN_UNAVAILABLE` 并以 1 退出，状态目录锁已释放；注入回滚没有按时完成时，子进程中的 `project_run` 写出 JSON 错误与 `project_run cleanup failed.`（附错误码）并以 3 退出，不等待仍存活的循环线程。
- [x] 5.5 实现组合根（决策 1、2）：删除 `metrics/asgi.py`；`ai_host.wiring.build_wsgi_application(django_app, ai_app)` 按决策 1 的 L1 定序处理请求：先对所有路径（包括静态文件）用 `WSGIRequest(environ).get_host()` 做 Host 校验，非法时返回固定文本的 400；停止受理之后，Host 合法的请求不论是否带凭据都得到固定文本的 503 与 `Retry-After: 2`，不带 hop-by-hop 头；然后分两路：挂载路径本身与 `<mount>/` 前缀交给运行时的 WSGI 适配器（`handle.wsgi_app()`），`SCRIPT_NAME` 追加挂载路径，挂载路径本身的 `PATH_INFO` 为 `""`（308 由适配器在认证之后返回），其余交给 Django；`ai_host.wiring` 的生命周期编排严格按决策 2 的顺序（`context = start_blocking(..., start_timeout=RUNTIME_START_SECONDS)` 并以 `with context as handle` 进入运行期、`attach(handle)`、端口、在主线程构造与启动 project run、`serve-http` 线程开始受理；`finally` 中停止受理、第一段停止（`handle.close_http()`）、排空、flush 收尾并关闭 server、`request_stop()` 与 `wait_stopped(620)` 后立即输出 `project_runtime_stopped`、`clear`、`detach`、第二段停止（离开 `with` 块，等同 `handle.stop()`）），`request_stop()` 返回真时把看门狗截止放宽到 t0 + 659.2 秒，`wait_stopped` 在 T 返回后收紧为 min(当前截止, T + 1.2 秒)（看门狗见 5.6），停止各段按 1.2 的截止时刻推进，到期后继续下一段：排空到期仍有在途请求或 `serve-http` 到截止时刻仍未结束时记入清理错误码，flush 到期时只关闭剩余连接、不记清理错误码，第 2–6 步失败时逆序清理已完成的步骤；主线程以不超过 0.5 秒的间隔检查停止事件与运行时结束信号 `handle.ended`，第 7 步的等待全部分片；视图与分派每个请求只取一次运行时句柄；分派为页面与 `/ai` 两路统计在途请求，计数在响应迭代器的 `close()` 中减少（决策 3）；`defaults.py` 设置 `WHITENOISE_USE_FINDERS = True` 与 `WHITENOISE_AUTOREFRESH = False`，development 与 production settings 不覆盖（启动后新增或修改的静态文件要重启 `serve`，决策 1）。验证：WSGI 测试覆盖非法 Host 对页面、静态文件与 `<prefix>/ai/` 都得到 L1 的固定文本 400、停止受理后带与不带凭据的请求都得到 L1 的 503 与 `Retry-After: 2` 且不带 hop-by-hop 头、`<prefix>/ai` 与 `<prefix>/ai/` 都交给适配器且 `SCRIPT_NAME` 与 `PATH_INFO` 正确（挂载路径本身的 `PATH_INFO` 为 `""`）、带凭据的 `<prefix>/ai` 由适配器 308 到 `<prefix>/ai/` 且保留查询串、其余路径与静态文件由 Django 处理、未运行 `collectstatic` 时静态文件可用、配置 Basic 用户时未认证的静态文件请求得到 401、`/metrics/` 前缀挂载在 `/metrics/ai`、development 与 production settings 下 `WHITENOISE_AUTOREFRESH` 都为 `False`、Django 与 `/ai` 的流式响应在迭代期间计入在途数并在 `close()` 之后归零；生命周期测试（testkit 运行时）覆盖正常启动后阶段为 `running`，停止时第一段停止先于排空、worker 停止先于第二段停止，排空用满截止时刻时记入清理错误码并仍执行后续各段，flush 到期时关闭剩余连接且不记清理错误码，`request_stop` 或 `wait_stopped` 抛错时仍按 `RuntimeStopResult(False, None, ())` 输出停止事件，第 2–6 步中任一步失败时已完成的步骤逆序清理且阶段为 `failed`，状态目录被占用时以 `RuntimeBusy` 的 code `runtime_busy` 启动失败且不受理请求，启动时限到期且回滚按时完成时以 `RuntimeStartTimeout` 的 code `start_timeout` 启动失败、阶段为 `failed` 且不受理请求，回滚没有按时完成时生命周期对象另记清理错误码与 `context.startup_failure.rollback_result`，运行时意外结束后 1 秒内阶段为 `failed` 并执行第 7 步，`detach()` 之后仍持有旧句柄的视图在第二段停止之后按 `not_running` 渲染且不返回 500，生命周期对象记录阶段、错误码与两个停止结果（project run 的 `RuntimeStopResult` 与运行时的 `handle.stop_result`）。
- [x] 5.6 新增 `ai_host/management/commands/serve.py`（决策 2、3）：`--host` 默认 `127.0.0.1`，回环判定按决策 3；development settings 下拒绝非回环绑定；未配置 Basic 用户的非回环绑定输出只含绑定地址的 `serve_anonymous_network_bind` 警告；主线程在加载 AI Base、启动运行时与获取状态目录锁之前自建并绑定监听 socket（Windows `SO_EXCLUSIVEADDRUSE`，POSIX `SO_REUSEADDR`），`EADDRINUSE` 与 `EACCES`（Windows 为 10048 与 10013）都输出 `serve bind failed.` 并以 1 退出；命令设置 `requires_system_checks = []`，bind 成功后才调用 `self.check()`，检查有错误时输出 `serve startup failed (system_check_failed).` 并经决策 2 第 7.7 步以 1 退出；bind 之前不导入 `ai_base_runtime`（`ready()` 注册的 CLI 端口工厂在被调用时才导入 `ai_host.wiring`）；bind 之后以同一个 `settings = build_settings()` 计算 N 并传给 `start_blocking`（决策 2 第 1 步）；以 `waitress.create_server(app, sockets=[sock], threads=14, channel_request_lookahead=1, max_request_body_size=N + 1)`（N 见 1.2）接管该 socket，不传 `listen`、不修改 waitress 的类属性（决策 3），waitress 不自己绑定；`serve-http` 线程运行 `server.run()`，主线程只处理信号与停止编排，主线程上的每次等待都按不超过 0.5 秒分片；主线程为 SIGINT、SIGTERM 与 Windows 上的 SIGBREAK 安装只设置停止事件的处理器，`--stop-file` 与 `--lifetime-seconds` 由监视线程设置同一事件，停止事件已设置后再收到信号时写出 `serve forced exit.`，flush 后 `os._exit(130)`；停止按决策 3：经 `server.trigger.pull_trigger` 关闭监听，此后 L1（5.5）对已有连接上的新请求返回固定文本的 503 与 `Retry-After: 2`，排空等宿主统计的在途数归零，flush 收尾（`close_when_flushed`，然后 `server.close()` 与 `task_dispatcher.shutdown(cancel_pending=True, timeout=0.5)`），不用 waitress 默认的关闭方式；两段式看门狗（决策 3）是 t0 时启动的 daemon 线程，一直保持到 `os._exit`，截止按 1.2 的常量与 5.5 的调整推进，到期时由辅助线程写出 `serve cleanup failed.` 并 flush，看门狗最多等 0.1 秒后 `os._exit(3)`；除第二次信号与看门狗外，每条退出路径都按决策 2 第 7.7 步显式退出（退出清点、`connections.close_all()`、`logging.shutdown()`、写出最后一行并 flush stdout 与 stderr，然后 `os._exit(<退出码>)`，不经 `sys.exit`，不等待剩余线程）；退出清点按 R24-host：`manage.py` 在导入 Django 之前包装 `atexit.register` 记录注册者，第 7.7 步在 `logging.shutdown()` 之前清点 atexit 回调、`threading._register_atexit` 回调、存活的非 daemon 线程与子进程、`weakref.finalize(atexit=True)` 对象与日志 handler，写一条 `serve_exit_inventory` 日志并与 1.2 的白名单比对，必需的清理在本步内显式执行；白名单之外的条目、必需清理超时或失败与第 7.7 步的关闭失败都记入清理错误码；访问日志中间件为每个请求写一行，不记录 `Authorization` 与 `Cookie` 请求头；按生命周期对象输出 `serve bind failed.`、`serve startup failed (<code>).`、`serve runtime failed (<code>).` 或 `serve cleanup failed.` 并决定退出码：干净停止 0，绑定、启动或运行期失败 1，清理失败或看门狗到期 3（与 1 同时出现时取 3），第二次信号 130；删除 `project_serve` 及 `test_project_serve_command.py`。验证：命令测试覆盖上述绑定规则；端口被占用时 2 秒内输出 `serve bind failed.` 并以 1 退出，没有启动运行时，也没有获取状态目录锁，该计时在真实的 `manage.py serve` 子进程上测量（含解释器启动与 `django.setup()`），且 bind 失败的子进程没有导入 `ai_base_runtime`（如以 `-X importtime` 运行并检查 stderr）；注入一个系统检查错误时输出 `serve startup failed (system_check_failed).` 并以 1 退出，没有启动运行时，也没有获取状态目录锁；注入 10048 与 10013 的绑定错误都输出 `serve bind failed.`；在只放行回环名与 IP 字面量解析的网络守卫下构造 server 成功，`server.socket` 就是预绑定的 socket；服务运行期间，另一进程在 127.0.0.1 的同一端口上以 `SO_REUSEADDR` 或默认方式绑定都失败（Windows 上分别为 10013 与 10048），此后发往 127.0.0.1 的连接仍由 `serve` 应答（合法 Host 与凭据返回 200）；运行时意外结束（`handle.ended` 置位，code 取 `handle.end_code`）时 1 秒内输出 `serve runtime failed (<code>).` 并以 1 退出；运行时启动失败时只输出错误码并以 1 退出，输出与日志不含原异常消息；注入启动时限到期（`RuntimeStartTimeout`）且回滚按时完成时输出 `serve startup failed (start_timeout).` 并以 1 退出；注入回滚没有按时完成（`context.startup_failure.rollback_result` 的 `completed` 为假）时先输出 `serve startup failed (start_timeout).`、再输出 `serve cleanup failed.`，以 3 退出，进程不等待仍存活的循环线程；实测进入 `start_blocking` 返回的上下文（`with context as handle`）的启动耗时（空状态目录与已有运行记录的状态目录各 5 次），记录实测值与据此确定的 `RUNTIME_START_SECONDS`（design Open Questions 5）；stop-file、lifetime、SIGINT、SIGTERM（在测试进程内以 `signal.raise_signal` 触发）与 Windows 上的 `CTRL_BREAK_EVENT`（子进程以 `CREATE_NEW_PROCESS_GROUP` 启动）各触发一次正常停止，输出停止事件并以 0 退出；一条活跃流、一条空闲流与一个积压约 8 MB 并暂停读取 3 秒的慢读客户端打开时，分别以 stop-file、SIGINT 与 `CTRL_BREAK_EVENT` 触发停止，三个客户端都在连接关闭之前收到终止事件，从触发到进程实际退出不超过 10 秒、退出码为 0，并仍输出停止事件；一个一直不读取的客户端打开时也在 10 秒内以 0 退出；正常停止后子进程的日志与 `project_runtime_stopped` 事件完整写出；注入运行时停止超时（`handle.stop_result` 的 `timed_out` 为真）、使运行时循环线程在停止顺序结束后仍未结束时，进程不等待该线程，在 10 秒内输出 `serve cleanup failed.` 并以 3 退出；停止期间已有连接上的新请求立即得到 L1 的 503 与 `Retry-After: 2`，响应不带 hop-by-hop 头；测试用的 Django 流式视图在停止事件后结束，客户端收到完整响应，排空等到其 `close()`；流在正常结束、出错、客户端中止与停止后都归还名额，客户端中止 4 条流后新流在心跳间隔 + 1 秒内被接受；访问日志含方法、路径与状态码，不含 `Authorization` 与 `Cookie` 的值；S0b 没有覆盖或只在 spike 代码上测过的路径（复签 E 第 4 项）：注入卡住的段（测试中注入较短的看门狗截止）时，即使 stdout 管道不再被读取，进程也在截止后 1 秒内输出 `serve cleanup failed.` 并以 3 退出；终止宽限到期后，不支持终止事件的流被取消，停止仍在 10 秒预算内完成；有执行中的假 run 时（可注入时钟）看门狗截止放宽到 t0 + 659.2 秒，`wait_stopped(620)` 到期时以 3 退出，run 在 T 结束时截止收紧为 T + 1.2 秒并以 0 退出；排空阶段与 flush 阶段各发一次第二次信号，都在 1 秒内输出 `serve forced exit.` 并以 130 退出；注入第 7.7 步的关闭失败或必需清理失败时以 3 退出；退出清点（R24-host）在正常停止后最后一行日志已落盘、`serve_exit_inventory` 中没有白名单之外的条目、临时目录已清除、没有存活的子进程、退出码为 0，注入一个白名单之外的 atexit 回调或非 daemon 线程时以 3 退出；所有走到第 7.7 步或强制退出的测试都在子进程中运行 `serve`，或在测试进程内注入退出函数，不在 pytest 进程内调用 `os._exit`；服务运行期间 `project_run --execute-local` 立即得到 `RUN_BUSY`。
- [x] 5.7 删除 sidecar 时代的 project run 组合：`TaskRunClient`、`AiBackendTarget`、`execution_mode`、`app/api/run_factories.py` 与 `app/api/report_factories.py` 中的工厂、`METRICS_PROJECT_RUNTIME_FACTORY`、`METRICS_PROJECT_AI_*`、`METRICS_REPORT_ASSIST_FACTORY`、`ai_bundle/`（连同 `.gitattributes:3-4`）、`ai-base-application-sdk` 与 `requirements-ai-task.txt`；删除或改写依赖它们的测试（包括直接导入 `TaskRunClient` 的 `project_management/tests/test_sdk_020_compatibility.py`）与 `ui_web/templates/projects/reports/run_status_fragment.html`，并删除只用于准入 SDK wheel 与 `ai_bundle` 契约包的 `scripts/validation/run_project_sdk_preintegration.py`；`.env.example:188-193` 改为说明 `manage.py serve`；`docs/development/reporting-delivery.md` 中的 SDK 环境说明（`:14-25,122-127,282`）改为 `ai_base_runtime` 的环境检查与嵌入运行时下的测试入口。验证：`project_management` 与 `ui_web` 中受影响的测试（显式路径）通过；`project_management/`、`bug_metrics/`、`ui_web/`、`metrics/`、`requirements*.txt`、`.env.example` 与 `.gitattributes` 中 grep 这些名称无结果（`scripts/validation` 中其余引用由 5.9 清除，最终由 9.5(a) 把关）。
- [x] 5.8 准入记录 `request.json` 只接受 schema v3：去掉 `backend` 与 `execution_mode`，删除 v1/v2 双读（`app/domain/run_admission_values.py`），其他版本一律 `RUN_STORAGE_INVALID`；记录保存档案 id/version、`definition_sha256`、模型身份与运行时版本。analysis attempt 与 report assist 的 wire 记录升到 v2 并去掉 `backend`（`services/report_assist_wire.py`、`services/summary_journal_reads.py`），旧 analysis 信封走 `ANALYSIS_INVALID`，旧 report assist 记录走现有的无效路径。验证：domain 与 service 单测覆盖 v3 往返、带 `backend` 或 `execution_mode` 的记录被拒、旧 analysis 信封得到 `ANALYSIS_INVALID`；经 5.3 的端口完成的 project run 写出的记录含档案 `id@version`、模型身份与运行时版本。
- [x] 5.9 按决策 15 改写验证组合：新增确定性的 OpenAI 兼容假模型服务（复用 `ExactDynamicVectorExecutor` 的向量匹配）和只用于验证的 Jira fixture AppConfig（不导入 `ai_host` 或 `project_management.runtime`，周完成视图的假对象移入其中）；删除 `project_full_stack_settings.py:76-80`、`project_week_settings.py:12-16`、`project_full_stack_fixture.py:108-148` 的并行组合；改写 `project_sdk_join*.py`、`profile_report_*.py`、`prepare_report_scale.py`、`test_project_full_stack_*.py` 与 `test_project_week_fixture.py`，并清除 `project_full_stack.py`、`project_full_stack_base.py`、`project_full_stack_identity.py`、`project_summary_base_fixture.py`、`project_summary_support.py` 与 `report_read_identity.py` 中的 `execution_mode` 与 `ai_base_application_sdk` 引用。验证：全栈验证以 `scripts.validation.project_full_stack_settings` 经 `manage.py serve` 加假模型完成一次 project run 与一次 report assist，提交者 principal 为合成 Basic 用户 `SYNTHETIC_ALICE`，`project_runtime_stopped` 断言不变；相关 `scripts/tests` 与 `project_management/tests` 通过；`scripts/validation` 与 `scripts/tests` 中 grep 5.7 列出的名称无结果。
- [x] 5.10 接入运行时 testkit 的宿主一致性套件（以 `-p` 显式加载的 pytest 插件 `ai_base_runtime.testkit.pytest_plugin`；Metrics 在单独的一致性通道中运行，命令形如 `pytest -p ai_base_runtime.testkit.pytest_plugin -o ai_host_modes=blocking_wsgi -p <ai_host 一致性夹具模块>`；根 `pytest.ini` 与 addopts 不加载插件，也不声明 `ai_host_modes`：根配置已生效并含 `filterwarnings = error`，未加载插件时未知的 ini 选项不论写在 `pytest.ini` 里还是经 `-o` 传入，都会触发 `PytestConfigWarning` 并以 INTERNALERROR 退出；一致性通道以 `-p` 加载插件，`ai_host_modes` 在那里是已声明的选项，该通道同样执行根配置的警告策略；夹具模块不以 `test_*.py` 命名，最终命令在 wheel 交付后由 0.6 确定并写入 `.github/ai-governance/repo-context.md`；提供 `ai_host_factory`、`ai_server_factory`、`ai_credentials`、`ai_clock_and_limits`、`ai_logs` 五个夹具（冻结的是名称、作用域与返回协议）；夹具可以依赖 `transactional_db`、`live_server`、`tmp_path` 等，`state_dir` 由 `ai_clock_and_limits` 创建；AIB design §11.4，上游增补 1 D10），并补充组合根的跨栈测试：同一请求在 Django 与运行时得到同一 principal、错误凭据两边都返回 401 且带同一 `WWW-Authenticate` 质询头；Host 为 `rebind.attacker.example` 时 Django 与 `<prefix>/ai/` 都返回 400 且不执行视图；`127.0.0.1:8793`、`localhost:8793`、`[::1]:8793` 与显式配置的 Host 正常处理；production settings 下匿名 principal 不能决定审批；运行时路由认证失败时输出一条 `ai_auth_failed` 日志且审计表行数不变；超过短请求上限的未认证 `/ai` 请求同时到达时都得到 401、不占名额，同时到达的已认证短请求照常处理；按决策 1 的定序表逐项断言拒绝来自哪一层（复签 D 第 5 项；waitress 的错误页带 "(generated by waitress)"，宿主与适配器的不带）：非法 Host × 带或不带凭据 × 运行中或停止中的 8 种组合，非法 Host 一律得到 L1 的 400，Host 合法时停止中一律得到 L1 的 503 与 `Retry-After: 2`，运行中不带凭据得到 401；经 `serve` 的 Django 路径上非法 Host 且不带凭据得到 400（原为 401）；不带凭据的 `<prefix>/ai` 得到 401，带凭据时得到 308；不带凭据且 `Content-Length` 超过 N 的请求在发送请求体之前就得到 L0 的 413，长度恰为 N 的请求体通过 L0；chunked 请求体超过 N 时得到 L0 的 413；非数字 `Content-Length` 得到 L0 的 400；不带凭据请求 UI 资产得到 401；短请求名额占满时不带凭据的请求得到 401。验证：普通 pytest 运行不加载插件，也不收集一致性测试；一致性套件在 `blocking_wsgi` 下的全部项（Host 校验、请求完整性、资源归属、`frame-ancestors`、审批持久化、`os.environ` 与全局 tracer 不变、Proactor、slow callback、`RuntimeBusy`，v2.1 新增的未运行、停止中与第一段停止后返回 503、第一段停止中所有打开的流在时限内发送终止事件、第二段停止在 `stop_timeout_seconds` 内返回、空闲流心跳与断开在心跳间隔 + 1 秒内被发现、WSGI 适配器逐块转发、断开释放、流与其他 `/ai` 请求分开的在途上限、名额在正常结束、出错、客户端中止与停止后都归还，两类在途数与拒绝数经 `handle.blocking.diagnostics.snapshot` 可观测，已准入的请求全部结束后两类在途数在有界等待内回到 0，`close_http()` 以 `completed=True` 返回后流的在途数为 0（OD-W1-4 的 I1、I2）、请求体在 WSGI 线程上读取并有上限、请求体接收完毕之前 server 不调用应用且不占名额（OD-W1-1 的前提断言）、响应块队列有上限并形成背压、门面等待超时抛 `RuntimeCallTimeout` 并取消循环侧协程、以同一个 `client_run_key` 重试只产生一次运行、循环被阻塞时短请求在总时限内得到 503 或 504 且卡顿解除后快照记录这次卡顿（`loop_stall_count` 增加，`loop_lag_max_seconds` 不小于阈值）、按 v2.1 D3 的顺序（Host 校验、请求完整性、认证、308、UI 资产、未运行的 503、准入）逐项拒绝且未认证请求不占名额、UI 资产不经循环与准入（循环被阻塞时仍返回 200，清单外的路径返回 404）且 URL 跟随挂载路径、导航请求被拒时得到自动刷新的 503 页面、运行时结束信号 `handle.ended` 1 秒内可见、信号处理器与 atexit 不变、第二段停止期间宿主信号处理器 1 秒内执行、离开 `with context as handle` 块后立即 `os._exit(0)` 时重启后已完成的运行、会话与审批记录完整且状态目录锁可再次获取，以及增补 1 新增的导出异常带 §11.3 注册表中的稳定 code、启动时限到期时有上限地回滚并抛 `RuntimeStartTimeout`（code `start_timeout`））与上述测试通过；`asgi` 托管方式的项报告为 SKIP（`not applicable: host did not declare asgi`），不计入通过数；套件的 pytest 终端或 JUnit 输出（含 assertion id、托管方式与 SKIP 原因）连同 wheel、OS 与 Python 来源随验证证据归档（§11.4）。
- [x] 5.11 新增运行时版本准入检查：校验已安装 wheel 的摘要与记录一致、`pip check` 无冲突，并运行宿主一致性套件与记录在案的 Metrics 浏览器测试子集，任一失败即非零退出。验证：把记录的摘要改错时检查失败，恢复后通过；检查命令与浏览器测试子集写入 `repo-context.md`。
- [x] 5.12 更新开发契约与人读文档：`AI_CONTRACT.md` §3 中 installed SDK 与 HTTP 提交的表述（`:58-62`）改为嵌入运行时、同步 task-run 端口、`ai_host` 是 AI 行为的唯一落点、运行时版本准入；`repo-context.md` 加入 `ai_host` 模块边界与 `manage.py serve`（写明启动后新增或修改的静态文件要重启 `serve` 才生效）；改写 `openspec/docs/current-baseline/project-reporting.md` 中所有描述 AI 执行的段落（`:33,53,91-94,476,501,542,564,570-571,585,606,633-636,644-662,673,683-685`），改为嵌入运行时、同步端口与 `manage.py serve`；删除只描述 HTTP SDK 0.2 接入状态的 `openspec/docs/current-baseline/sdk-020-integration.md`。验证：这些文档不再以 `TaskRunClient`、HTTP SDK、installed SDK 或 `project_serve` 作为现行用法；`repo-context.md` 写明静态文件变更后要重启 `serve`；文档中的命令按原样运行成功。

## 6. 部署：删除 `metrics.wsgi` 与 gunicorn，Docker 单进程（决策 1、16）

- [x] 6.1 删除 `metrics/wsgi.py` 与 `WSGI_APPLICATION`（`metrics/settings/defaults.py:85`；`metrics/asgi.py` 已由 5.5 删除）。验证：settings 测试断言没有 `WSGI_APPLICATION`；`manage.py check` 通过；仓库中 grep 不到 `metrics.wsgi` 与 `metrics.asgi`。
- [ ] 6.2 `ops/docker/Dockerfile` 的基础镜像改为 `python:3.13-slim`，删除 `GUNICORN_*`，`CMD` 改为 exec 形式 `["python", "manage.py", "serve", "--host", "0.0.0.0", "--port", "8000"]`；从 `requirements.txt` 删除 `gunicorn`。验证：`docker build` 成功，镜像内 `python --version` 为 3.13.x；以挂载卷和 `--stop-timeout 690` 运行容器后 `<prefix>/ai/api/health` 报告运行中、首页可访问、日志出现 `serve_anonymous_network_bind` 警告；保持一个聊天流打开、没有执行中的 project run 时执行 `docker stop`，聊天流的客户端在连接关闭之前收到终止事件，日志出现干净的 `project_runtime_stopped` 事件，容器在 10 秒内以 0 退出；服务运行期间，容器内另一进程以 `SO_REUSEADDR` 绑定同一端口失败；挂载同一卷的第二个容器输出 `serve startup failed (<code>).` 并以 1 退出；`docker kill` 之后以同一个卷重新启动容器，`serve` 正常获得状态目录锁并启动。
- [ ] 6.3 改写 README：`:18` 的 installed-SDK 表述改为嵌入运行时；Docker 快速上手与 "Production Setup"（`:100-139,556-577`）使用 `manage.py serve`、`--stop-timeout 690`（Compose 用 `stop_grace_period: 690s`）、单副本与挂载卷；本地启动（`:199-205`）改为 `manage.py serve`；"Unified Metrics Workbench Demo"（`:211-227`）删除 launcher 启动 AI Base、AI Base 诊断与 legacy 回滚的说明；写明非回环绑定的匿名姿态，以及 production settings 下发布审批至少需要一个 Basic 用户（`METRICS_BASIC_AUTH_USERS`），并建议配置 `ALLOWED_HOSTS` 与由反向代理终止 TLS。验证：README 中 grep 不到 `gunicorn`、`project_serve`、`metrics.wsgi`、`runserver`、`sidecar` 与 installed-SDK；文档命令与 6.2 实际运行的命令一致。

## 7. 工作台 AI pane 与工作流页面（决策 6、7、14）

- [x] 7.1 AI pane 改为三态（`ready`、`not_configured`、`not_running`），由生命周期对象与设置推导：`ready` 时渲染同源 iframe，`embed-host.js` 取自 `handle.ui.asset_url("embed-host.js")`，会话经 `handle.blocking.chat.open_session(principal, app_id="metrics", agent=..., context_ref=..., session_key=f"metrics.workbench.{profile_id}", timeout=...)` 打开或恢复（AIB design §11.1 `:856-861`：唯一键为 `(principal.id, app_id, session_key)`；`session_key` 完整匹配 `[A-Za-z0-9._:-]+`，以 `metrics.` 开头，不超过 200 个 ASCII 字符，不做规范化、截断或大小写折叠；profile id 为 `[a-z0-9][a-z0-9._-]{0,159}`，键最长 178 个字符，`ai_host` 不做编码），以门面方法必填的 keyword-only `timeout` 设置时限并先取得非阻塞信号量（1.2 的常量），等待超时（`RuntimeCallTimeout`）或信号量已满时显示"暂时不可用，可重试"且页面返回 200，门面抛 `RuntimeNotRunning` 时显示 `not_running`；`not_configured` 只列出缺失的变量名；`not_running` 提示用 `manage.py serve` 启动；scope binding 未解析时只显示 Scope Library 修复入口；principal 为匿名且 settings 不允许匿名决定审批（`HostConfig.allow_anonymous_approval` 为 `False`）时，pane 提示发布审批需要配置 Basic 用户（`METRICS_BASIC_AUTH_USERS`），read tool 照常可用。删除 `ui_web/ai_base_workbench_adapter.py` 及其测试，以及 sidecar 状态在 UI 链路上的全部残留：`ui_web/workbench_service_status.py:35-92`、`ui_web/context_processors.py:44-67`、`ui_web/views/workbench_view.py:31,42,49-54,194-247`、`ui_web/templates/workbench.html:202-203`、`ui_web/data/data_health_data.py:12`、`ui_web/facades/data_health_facade.py:15,22`、`ui_web/templates/data_health.html:8-9,35-62`、`ui_web/facades/bug_trend_ai_facade.py:28-29`、`bug_metrics/app/api/ai_dashboard_api.py:35-36,46`、`bug_metrics/app/api/__init__.py:22,72`、`bug_metrics/app/api/ai_dashboard_composition_contracts.py:71` 的 `ai_sidecar` actor、`ui_web/templates/partials/bug_trend_scope_lifecycle_guide.html:52` 与 `ui_web/locale/zh_Hans/LC_MESSAGES/django.po:1670-1671`，同步改写 `test_workbench_views.py`、`test_data_health_views.py`、`test_workbench_chart_views.py`、`test_workbench_high_density_browser.py` 与 `bug_metrics/tests/test_ai_sidecar_contract_fixtures.py`。验证：视图测试覆盖三态、门面等待超时（`RuntimeCallTimeout`）与信号量已满时 pane 显示可重试状态且页面返回 200、binding 未解析时不渲染聊天、匿名且不允许匿名审批时显示 Basic 用户提示、160 字符且含连字符的 profile id 得到合法的 `session_key`（178 个字符）、iframe URL 与页面不含 token、credential ref 或 actor；非 `ready` 时图表、证据、设置、发布历史与诊断页面正常；Metrics 静态目录中没有 `embed-host.js` 副本。
- [x] 7.2 scope、range、图表或 bucket 变化时，局部刷新返回新的 `ai_context_ref`，页面经 `embed-host.js` 发送 `context-changed`，同一会话重新绑定；binding 未解析时不发送之前 scope 的 `ContextRef`；亮暗主题经 `embed-host.js` 同步给 iframe；折叠与恢复 AI pane 只切换显示，不重新加载 iframe。删除 workspace 同步的表单、视图与 JS。验证：浏览器测试覆盖切换 range 后仍是同一会话且 iframe 收到新 `ContextRef`、亮暗主题同步、binding 未解析时 iframe 不收到消息、折叠再恢复后 iframe 未重新加载且会话、待处理审批与进行中的回合都保留；AI pane 在浏览器缓存为空时首次加载与切换 range 期间，iframe 内的 UI 资产都返回 200 且不占名额，没有请求最终以 503 失败（被拒的幂等 GET 按 `Retry-After` 重试后成功）；短请求名额被占满时重新加载 iframe，显示按 `Retry-After` 自动刷新的 503 页面，名额释放后加载嵌入页；同一 principal 重新打开同一 profile 时恢复同一会话。这些浏览器测试关闭 S0b 复签发现 11 的残余（浏览器级 `/ai` 未测，短请求上限 4 小于浏览器每源约 6 个连接）；停止中 L1 返回的 503 与准入的 503 同为 `Retry-After: 2`，UI 按同一规则处理，分派层的断言见 5.10。
- [x] 7.3 宿主页面处理 host action `metrics.openChart`、`metrics.openEvidence`：只在 workbench 中切换视图，不改变服务端状态；`ui_web/static/js/workbench-state.js:80,114,242` 的旧 `ai-base.host-action` 消息处理改为经 `embed-host.js` 的 `ai-base.embed/1` 协议接收。验证：浏览器测试模拟 iframe 请求两个 action，页面切换到目标图表或证据，且没有发出任何写请求；`ui_web/tests/workbench_browser_test_support.py:371,408` 与 `test_workbench_ai_host_actions.py` 改用新协议，旧消息格式不再被处理。2026-11-16：新逻辑位于 `workbench-ai.js`，真实 `serve` 浏览器用例验证两种 action、GET-only 导航、旧消息拒绝及 iframe 保持；不包含业务数据或发布变更。
- [x] 7.4 `/ai-dashboard/workflow/` 页面改为显示运行时状态、工作流结果与发布就绪状态，删除 sidecar 状态卡片与 gcx、dry-run proof 文案（`ui_web/views/ai_dashboard_view.py:245`、`ui_web/templates/ai_dashboard_workflow.html:15-39`）。验证：视图测试覆盖 Jira 与 HSD-ES profile 的就绪与阻塞说明，页面不含 gcx 与 sidecar；7.1–7.4 的页面通过 `AI_CONTRACT.md` §7 的前端门禁与 `frontend-design-requirements.md` 的 Definition of Done（含亮暗模式）。
- [x] 7.5 改写 `docs/onboarding/metrics-dashboard-new-user-onboarding.zh.md` 中的 AI Sidecar Health、gcx precondition 与故障排查行，改为 AI pane 三态、发布就绪与审批。验证：该文档不再出现 sidecar 与 gcx，描述的页面元素与 7.1–7.4 的实现一致。
- [x] 7.6 没有 Jira 配置时，读本地 durable 数据的页面与图表 API 可用（AIB-0 验收的 F-a）：`jira_sync` 的 `scope_metadata_api`（`jira_sync/container.py:15-16`）在每次取用时立即调用 `create_jira_client(settings)`，`ui_web` 构造 `BugTrendFacade`（`ui_web/container.py:108-114`）时因此失败，`/api/charts/data/` 返回 500（缺地址时为 `PROVIDER_ENDPOINT_INVALID`，token 为空时为 `PROVIDER_CREDENTIAL_INVALID`）；改为第一次需要 Jira scope 元数据时才创建 client，需要 Jira 的操作的错误行为不变。验证：在不读取 `.env`、没有任何 Jira 变量的 settings 下，bug trend 页面、workbench 页面与 `/api/charts/data/` 读本地数据都返回 200，且没有创建 Jira client（spec `provider-facts-and-sync` 的"Provider 未配置时渲染本地数据"）；需要 Jira scope 元数据的现有用例不变；`jira_sync` 与 `ui_web` 受影响的测试（显式路径）通过。证据（2026-11-11）：commit `d979e55`。`jira_sync/container.py` 新增 `OnDemandJiraScopeMetadataProvider`，`scope_metadata_api` 改用它，第一次请求 scope 元数据时才创建 Jira client。新增 `ui_web/tests/test_bug_trend_without_provider_settings.py`：三个 Jira 设置为 None 时，bug trend 页面、workbench 页面与 `/api/charts/data/` 都返回 200，图表 API 的 `calculation_run_id` 是本地的运行，`create_jira_client` 调用 0 次。`jira_sync/tests/test_api_scope_metadata.py` 新增 `test_shouldReportMissingJiraSettingsOnlyWhenMetadataIsRequested`：取用 API 时不创建 client，请求元数据时创建 1 次并抛出 `PROVIDER_ENDPOINT_INVALID`。把 `container.py` 换回修复前的版本后，这两个测试都因 `ConnectionError: Provider endpoint is invalid` 失败。`jira_sync/tests` 全部、`ui_web` 受影响的 15 个测试文件与 9.6 的 2 个脚本测试文件共 177 项通过。本机运行 launcher 时也验证了这三个地址（见 9.6）。

## 8. 删除 HTTP 集成与 gcx（决策 11）

- [x] 8.1 删除 `/api/ai-dashboard/` 前缀下其余 13 个路由及其视图（`ui_web/urls.py:227-240`，含 `ai_dashboard_connector_endpoint.py` 的 `connector_endpoint`、`ai_dashboard_publish_view.py`，以及 `ui_web/views/ai_dashboard_view.py:121` 以 `ai_sidecar` 为默认 actor 的 artifact 校验视图）、sidecar 握手与探活（`bug_metrics/app/api/ai_sidecar.py`）、`AiGrafanaPublishApprovalService`、gcx 操作词表、precondition、publication callback 与 `dry_run_proof_id`，以及设置项 `METRICS_AI_SIDECAR_ENABLED` 与 `METRICS_AI_BASE_*`（`metrics/settings/defaults_metrics.py:149-156`）；同时删除对应测试，以及 `ui_web/tests/test_ai_dashboard_api_surface.py` 与 `ai_dashboard_publish_test_support.py` 中依赖这些路由的部分，清理模板与 JS 中残留的 sidecar 和 workspace 同步引用。验证：请求 `/api/ai-dashboard/workflow/`、`/api/ai-dashboard/identity/` 等前缀下的路径返回 404；`bug_metrics` 与 `ui_web` 测试（显式路径）通过。
- [x] 8.2 改写 `openspec/docs/current-baseline/grafana-jira-fact-table-architecture.md` 的 AI Base 章节（`:521` 起的复用说明、集成边界、可行性评估与跨仓接口草图），改为进程内 Metrics App 包的边界：tool、context provider、审批与发布记录。验证：该文档不再描述跨仓 HTTP 接口、connector 或 `app-profiles.json` 注册，内容与 `embedded-ai-runtime-host` 及第 4 组实现一致。

## 9. 启动入口、审计脚本与残留 gate（决策 13）

- [x] 9.1 `scripts/dashboard_runtime_instance_profile.py` 删除 ai-base backend、frontend 端口与绑定（`:29-30,105-114`）以及 `METRICS_AI_BASE_URL`、`METRICS_AI_BASE_FRONTEND_URL`（`:264-265`），把 `METRICS_EXTERNAL_LITELLM_URL`（`:266`）改为输出 `METRICS_AI_MODEL_BASE_URL`，`SCHEMA_VERSION` 加一；同步改写 `docs/architecture/local-runtime-instance-isolation.md`（`:30,58-59`），外部服务只保留模型网关。验证：profile 测试覆盖旧 `SCHEMA_VERSION` 的 profile 被拒绝、新 profile 不含 ai-base 端口；该文档不再列出 AI Base backend 与 frontend。
- [x] 9.2 改写 `scripts/e2e_dashboard_ai_stack.ps1`：只用 `manage.py serve` 启动或检测 Metrics（`:518` 按 `runserver` 匹配进程的逻辑改为匹配 `serve`），并启动或检测 Grafana，打开一个 workbench URL；不启动、停止或探测任何 AI Base 进程；冒烟通过后不清理当前 Metrics 与 Grafana 进程树。验证：`scripts/tests/test_e2e_dashboard_ai_stack_launcher.py` 通过；本机在 Orca worktree 中运行脚本，不设置 Jira 环境变量、不手动复制 Grafana 插件（7.6、9.6），workbench 打开，图表 API 返回 200，AI pane 状态与模型配置一致。
- [x] 9.3 其余启动入口与进程审计改用 `serve`：`scripts/e2e_bug_trend.services.json:7`、`scripts/local_start_backend.ps1:32` 与 `scripts/validation/project_ui_fixture.py:148-153` 的 manifest `commands.runserver` 改为 `manage.py serve`；`scripts/audit_stack_process_inventory.py` 的 `is_dashboard_runserver`（`:261-266`）改为识别 `serve` 进程，删除 `--ai-base-workspace`、`--ai-base-state`（`:78,80`）与 ai_base 盘点（`:183,198,252-257,281-293,352`）；`scripts/audit_stack_boot_logs.py` 删除 `--require-ai-base-state`（`:101`）与 ai_base 检查（`:54-70,94-96,108-157,277`）。验证：同步改写的 `scripts/tests/test_stack_process_inventory_audit.py`、`test_stack_boot_log_audit.py` 与 `test_service_lifecycle_platform_ops.py` 通过；对本机一个真实的 `manage.py serve` 进程树运行两个审计脚本，结果识别出 Metrics 服务且不报告 AI Base 缺失。
- [x] 9.4 改写 `docs/validation/dashboard-ai-e2e-runbook.zh.md` 为单进程流程；在 `docs/case_study/ai-base-chat-to-grafana-approved-publish.zh.md` 开头注明其中的 sidecar、connector 与 gcx 流程已由本 change 取代，并链接新 runbook。验证：runbook 中的命令按原样运行成功；两份文档都不再把 sidecar 流程描述为现行做法。
- [ ] 9.5 增加残留 gate（脚本或测试，命令写入 `repo-context.md`），分三类检查：(a) 代码、settings、模板、静态 JS 与脚本（测试文件除外）中不出现 `ai_base_application_sdk`、`/api/ai-dashboard/`、`connector_endpoint`、`TaskRunClient`、`AiBackendTarget`、`execution_mode`、`ai_bundle`、`METRICS_AI_SIDECAR_ENABLED`、`METRICS_AI_BASE_`、`METRICS_PROJECT_AI_`、`METRICS_PROJECT_RUNTIME_FACTORY`、`METRICS_REPORT_ASSIST_FACTORY`、`dry_run_proof_id`、`ai-base.host-action`、`frontend_url`、`project_serve`、`metrics.wsgi`、`metrics.asgi` 与 `uvicorn`；(b) 用 AST 检查 `services/report_assists.py`、`services/project_run_worker.py` 与 `ai_host/` 中没有 `asyncio.run` 调用，其他模块的 `asyncio.run` 不在检查范围内；(c) `README.md`、`AI_CONTRACT.md`、`.github/`、`docs/`（`docs/case_study/` 除外）与 `openspec/docs/current-baseline/` 中不出现 `sidecar`、`project_serve`、`gunicorn`、`metrics.wsgi`、`metrics.asgi`、`TaskRunClient`、`ai_base_application_sdk` 与 installed SDK。验证：三类检查各植入一处违规时 gate 失败，当前树上通过。
- [x] 9.6 Grafana 共享插件缓存在 Orca worktree 布局下可用（AIB-0 验收的 F-b）：`scripts/e2e_grafana_runtime.py` 的 `shared_worktree_grafana_plugins_path`（`:143-146`）只识别 `<repo>\.worktrees\<name>`，改为经 `git rev-parse --git-common-dir` 找到主 checkout，使用其 `state\grafana\data\plugins`；`GRAFANA_PLUGINS_PATH`、`GF_PATHS_PLUGINS` 与本地插件目录的优先顺序（`:130-140`）不变。验证：单测覆盖 `.worktrees` 布局、主 checkout 在其他目录的 worktree 布局、主 checkout 本身与不在 git 仓库中四种情况；本机在 Orca worktree 中运行 launcher，不复制插件时 `/api/plugins/yesoreyeram-infinity-datasource/settings` 返回 200。证据（2026-11-11）：commit `f3b39e3`。新增 `main_checkout_path`，经 `git rev-parse --path-format=absolute --git-common-dir` 定位主 checkout；主 checkout 本身与不在 git 中的目录没有共享缓存。新增 `scripts/tests/test_e2e_grafana_runtime.py` 覆盖上述四种情况，删除 `test_e2e_bug_trend_launcher.py` 中按 `.worktrees` 目录名构造路径的旧测试；随 7.6 的 177 项一起通过。本机在 Orca worktree（主 checkout 为 `D:\AIGC\scrum_dashboard`）中、没有本地插件副本、没有 `.env` 与 Jira 变量时运行 `scripts/e2e_bug_trend.py start --open-entrypoint none`：生成的 Grafana 配置中 `plugins` 指向主 checkout 的 `state/grafana/data/plugins`；该地址返回 200（Infinity 4.0.0），数据源健康检查返回 OK；bug trend 页面、workbench 页面与 `/api/charts/data/` 都返回 200。运行 `stop` 后两个服务都已结束，端口没有监听，没有残留进程。两个服务都是在 5 秒正常停止等待后被强制结束，这是 `runserver` 收不到停止信号的现状，由 9.7 处理。
- [x] 9.7 启动入口与停止脚本正常停止 `serve`（决策 2 第 7 步、决策 3）：Windows 上 `Stop-Process` 与 `TerminateProcess` 直接结束进程，`taskkill` 不带 `/F` 对没有窗口的进程无效，以 `CREATE_NO_WINDOW` 启动的进程与调用方不共享控制台、收不到调用方发出的 `CTRL_BREAK_EVENT`，因此停止 `serve` 一律先写入它的 `--stop-file`，等待不少于 15 秒（10 秒停止预算加余量）仍未退出才按 PID 强制结束，并输出被强制结束的 PID。10 秒是预算，由进程内两段式看门狗按段保证（决策 3）；持有 GIL 的长 C 调用会挡住看门狗，此时由这里的强制结束兜底；有执行中的 project run 时看门狗放宽到 t0 + 659.2 秒，启动入口仍在 15 秒后强制结束，Docker 由 `--stop-timeout 690` 覆盖（6.2）。`scripts/e2e_bug_trend.services.json` 的 `django` 服务以 `--stop-file` 启动 `serve`，`stop_command` 写入该文件，`graceful_timeout_seconds` 不小于 15；`scripts/e2e_bug_trend.py` 的停止按各服务自己的等待时间执行（`:146` 现在统一用 5 秒；如需改 `service_lifecycle_engine`，按其 `AGENTS.md` 保持通用）；`scripts/local_start_backend.ps1` 以 `--stop-file` 启动，`local_stop_backend.ps1` 与 `e2e_dashboard_ai_stack.ps1` 停止残留进程的逻辑（`Stop-StaleDashboardDemoProcesses`、`Stop-ProcessTrees`）对 `serve` 进程从其命令行取得 `--stop-file` 并写入。执行中的 project run 超过等待时间时被强制结束，由下次启动的恢复标记为中断。验证：launcher 与生命周期测试覆盖写入 stop-file 后 `serve` 以 0 退出并输出 `project_runtime_stopped`、15 秒内未退出时才强制结束；本机启动一次 `serve` 后分别运行 `scripts/e2e_bug_trend.py stop` 与 `local_stop_backend.ps1`，日志都出现干净的 `project_runtime_stopped`，没有强制结束。
- [x] 9.8 规划好的端口在启动前或启动中被外部进程占用时，换端口启动（AIB-0 重新验收的 F-d）：`scripts/service_lifecycle_engine/engine.py` 的 `restart_services` 在 `resolve_plan` 中一次选定所有服务的端口，然后依次启动；前面的服务启动期间，后面服务的端口可能被外部进程占用，而 `wait_ready`（`:236-252`）在进程就绪前退出时直接失败。改为：启动每个服务前重新检查它的端口，已被占用就为该服务重新选端口；服务在就绪前退出、且此时它的端口有其他进程监听时，把该端口记为本次不可用，换下一个候选端口重试，每个候选端口最多试一次；端口变化后重新调用 `before_start`，用新端口重新生成依赖端口的配置（例如 Grafana 配置文件），已经启动的服务不变；`restart_services` 返回实际使用的端口。engine 保持通用（遵守其 `AGENTS.md`）。验证：engine 测试覆盖以下情况：启动前端口已被占用时换端口；进程因端口被占用在就绪前退出时换端口重试，并重新调用 `before_start`；进程因其他原因在就绪前退出时不重试；候选端口用尽时报错。`scripts/tests` 中的生命周期测试与 E2E launcher 测试（显式路径）通过。证据（2026-11-11）：commit `7181b6f`。端口规划与启动循环移入新的 `LifecycleStartingMixin`（`scripts/service_lifecycle_engine/starting.py`）：启动前端口被占用时以 `occupied_before_start` 重选；服务就绪前退出且端口被其他进程监听时，以 `occupied_after_exit` 拒绝该端口并重试；每次换端口都发出 `port_reresolved` 事件，并用新端口重新调用 `before_start`，替换尚未启动的服务的 spec；`RestartResult.port_plan` 是实际使用的端口。`wait_ready` 在启动的进程以非 0 退出时立即抛出 `ServiceExitedBeforeReadyError`（`__init__` 已导出）。`e2e_bug_trend.py` 与 `e2e_provider_parity.py` 的 `before_start` 本来就按传入的端口重写 Grafana 配置，并读取 `port_plan`，因此不需要修改。新增 `test_service_lifecycle_port_replan.py`，覆盖上述四种情况。`scripts/tests` 下 13 个生命周期测试文件、3 个 E2E launcher 测试文件与 2 个审计测试文件共 175 项通过。在临时副本中把 `engine.py` 与 `provenance.py` 换回修复前的版本后，9 个新增或改写的测试全部失败。
- [x] 9.9 启动审计脚本在非 UTF-8 输出编码下正常报告（AIB-0 重新验收的 F-e）：`scripts/audit_stack_boot_logs.py` 的 `print_findings`（`:249`）原样输出日志行，输出编码为 cp1252 时遇到 `✗` 等字符抛 `UnicodeEncodeError`，launcher 只报告审计本身失败，掩盖了原来的启动失败；`scripts/audit_stack_process_inventory.py` 原样输出进程命令行，有同样的问题。两个脚本作为入口运行时，无法编码的字符改为转义输出，审计结论与退出码不变。验证：以 `PYTHONIOENCODING=cp1252` 运行两个脚本，输入分别是含 `✗` 的日志行与进程命令行，输出包含转义后的字符，没有异常，退出码与审计结论一致；`scripts/tests/test_stack_boot_log_audit.py` 与 `test_stack_process_inventory_audit.py` 通过。证据（2026-11-11）：commit `2157ec3`。两个脚本作为入口运行时先执行 `sys.stdout.reconfigure(errors="backslashreplace")`。两个测试文件各新增一个子进程测试（`PYTHONIOENCODING=cp1252`、`PYTHONUTF8=0`），输入含 `✗` 时输出 `\u2717`，退出码与审计结论不变；修复前这两个测试都因 `UnicodeEncodeError` 失败。随 9.8 的 175 项一起通过。
- [x] 9.10 启动失败时不得把外部进程记为服务的监听者，停止服务时不得结束外部进程（AIB-0 重新验收的 F-f）：`provenance.resolve_owned_listener` 有一条启发式规则："wrapper 已退出且端口只有一个监听者时，认定该监听者为服务进程"。run1 中 Grafana 因 F-d 在就绪前退出，ABORTED 记录据此把 3001 上本机 VS Code 的 utility 进程（PID 28512）记为 `listener_pid`，capability 为 `owned_listener`；teardown 的 `stop_service` 经 `_running_owned_listener_pid` 把它当作自有进程结束了（详见 `aib0-acceptance.md` 第 9 节）。改为：只有 wrapper 自身在监听，或监听者属于 wrapper 的进程组（`owned_listener_pids`）时，才认定为服务的监听者；启动的进程以非 0 退出时，即使端口上的端点可达，也判定启动失败（9.8 的 `ServiceExitedBeforeReadyError`），不再借外部端点认定就绪。验证：provenance 测试覆盖 wrapper 已退出、端口只有一个外部监听者时不认定监听者；生命周期测试覆盖启动失败后 ABORTED 记录的 `listener_pid` 为空，随后 `stop_service` 不结束任何进程；进程以非 0 退出而 health 可达时 `wait_ready` 报错且不探测端点。证据（2026-11-11）：commit `7181b6f`。`test_service_lifecycle_provenance.py` 新增 `test_shouldNotAdoptSoleListenerWhenWrapperExitedWithoutOwnershipEvidence`；`test_service_lifecycle_port_replan.py` 的 F-f 回归测试断言 ABORTED 记录的 `listener_pid` 为 None、`stop_service` 返回 `not_running` 且没有结束任何进程；`test_service_lifecycle_process.py` 新增 `test_waitReadyShouldRejectHealthyEndpointWhenStartedProcessFails`。三项测试都在 9.8 的红灯验证中失败、修复后通过。已知剩余风险：自有进程尚未退出时，外部服务若在同一端口对 health 路径返回 2xx，仍可能被认定就绪并经"端点可达且只有一个监听者"的路径收养；PID 复用也会造成同类误判。根治需要用进程树或身份端点证明监听者归属，不在本 change 范围内。

## 10. 集成验收

- [x] 10.1 Jira-first 端到端发布：使用 production settings，测试进程经环境变量配置一个合成 Basic 用户（凭据只在测试进程中生成，不提交），该用户在绑定 `chiplet-2a-jira` 的 workbench 嵌入聊天中，由 5.9 的确定性假模型产生 tool 调用，请求 range `26WW32`–`26WW35`、series `new_critical_high` 的 `open_bug_trend`，并由该用户批准后导入本地 Grafana。验证：依次出现 `draft_validated`、pending 审批、approved 审批与成功结果，`decided_by` 为该合成用户；Grafana URL 渲染该 range 的数据；`/api/ai-publish-history/` 列出这次发布并带 approval id、`tool_call_id` 与 preview 摘要；`ai_host` 审计表依次记录审批请求、决定、消费与 tool 结果（顺序以运行时给出的事件顺序为准）；数据缺失时不请求审批。
- [ ] 10.2 全量门禁：5.11 的运行时准入检查、`check_app_package`、导入规则（1.4）、残留 gate（9.5）、受影响模块的测试（显式路径：`ai_host`、`metrics`、`bug_metrics`、`jira_sync`、`ui_web`、`project_management`、`scripts/tests`）、`python scripts/check_file_size_limits.py --include-untracked`、`python scripts/check_diff_whitespace.py --include-untracked` 与 `openspec validate embed-ai-base-runtime-in-process --strict`。验证：全部通过，并按 `.github/ai-governance/closure-verification-policy.md` 记录证据。
- [ ] 10.3 在状态副本上演练 design 的 Migration Plan：切换前给当前提交打 git tag 并保留对应镜像；停机备份数据库、`METRICS_STATE_DIR` 与 archive root（同一时间戳）→ 安装新版本并 `migrate` → 删除 `runtime/operations/` → 更新环境变量与 launcher profile → `manage.py serve` 冒烟（health、AI pane、同一会话、发布行、`RUN_BUSY`），Docker 部署以 `--stop-timeout 690` 运行；随后按回滚步骤恢复备份，并以该 tag 的代码与镜像启动旧版本。验证：演练记录列出每个冒烟项与回滚结果；旧格式记录读取为 `RUN_STORAGE_INVALID`。
- [ ] 10.4 用 AIB-2 wheel 与 `serve` 的推荐组合（`waitress==3.0.2`、threads 14、流与其他 `/ai` 请求分开限额 4 与 4、UI 资产在认证后由适配器直出且不计名额、`WHITENOISE_AUTOREFRESH = False`、flush 收尾）复测 S0b 的 B1 第二次信号、B3、B4、B5、B6、B7、B9 与终测 M5 的名额归还（S0b 与终测使用的是 spike 中的适配器，不是 AIB-2 的 WSGI 适配器），B5 的流用 AIB-2 的聊天流（5.9 的确定性假模型）；B6 另在 production settings 下（`DEBUG=False`，先运行 `collectstatic`）跑一次；浏览器缓存为空时 AI pane 首次加载，UI 资产全部返回 200 且不占名额，没有请求最终以 503 失败；循环被阻塞时资产仍返回 200。门槛与 0.5 相同，B9 另按终测 M2 的判据（hold 期间的短 `/ai` 请求全部 200 且小于 100 ms），作为本 change 的关闭条件；5.10 的定序矩阵在 AIB-2 的适配器上同样复测。复测按 S0b 复签 C 的条件隔离：`HEAVY_RUN_ACTIVE` 在第一个进程启动前写入、最后一个判定 JSON 写出后删除，其间 Metrics 侧不运行其他进程（不跑 pytest 与 python，不做 git 写操作），以开始、结束与每分钟的进程快照证明；开始与结束时记录 `git rev-parse HEAD` 与 `git status --porcelain` 的 hash，有变化即作废；驱动记录整机 CPU 采样。验证：复测报告与 `s0b-spike-report.md` 并列提交，各项全部通过；任一项不通过时不归档本 change，带证据回到 owner。

## Workflow follow-up

2026-11-16 continuation packet: implementing 4.3/4.4 and 7.1-7.3 against Metrics
`f63d1084401bb12e6b1e04222708bc06c894f89f` and the unchanged `0.1.1.dev1`
candidate. Owner paths are `ai_host/`, the Workbench view/state/template/scripts
and their tests, the bug_metrics public context API, and the corresponding
current guides. The parent remains the only production writer; an isolated
`gpt-5.5`/`xhigh` reviewer prepares the authority/consumer coverage.
The installed embed contract accepts `context-changed(sessionId)` notifications,
not a ContextRef payload. The server must call `chat.bind_context` before sending
that notification: keyed `open_session` restores the old binding. Tests must
disconfirm stale binding, unknown/disabled scope, mismatched profile/provider,
oversized selections, principal crossover and iframe reload during htmx swaps.
Existing architecture-review PASS covers the preceding task-run packet only.
Publication, full legacy cleanup and section 10 remain open.

Packet observations: the focused host/context set passed 56 tests. The real
`serve` browser scenario passed with a scripted-model reply, exactly one model
request, stable iframe/session identity across range change and collapse,
theme propagation, same-profile restoration and UI-only `metrics.openChart` /
`metrics.openEvidence` actions. An earlier page/asset-only pass missed a
`ready -> context-changed -> ready` notification loop; the added real-message
check reproduced it, and the host now notifies only after a changed context,
never in response to child `ready`. UI view/catalog checks passed 22 tests and
the asset/style/152-pair contrast gate passed. An early manual-preview cleanup
assertion failed after the notification storm; its cause was not established
and it is not counted as normal-stop evidence. Full active-flow stop coverage
remains under 5.6/10.4. Independent review and final visual QA of this packet
are recorded separately; no unchecked parent task is closed by this note.

The final consumer candidate is now `0.1.1.dev2` from AIB
`e155d4cac70dde13fbd6bdbcca08141218b883e6`, SHA256
`47b4d56c1164092d715792be564b883e56857c7e90baaa1498b0863f2ccbaa55`.
Its runtime core is byte-identical to the prior candidate; only shared UI
accessibility assets and version metadata changed. The prior record remains in
`evidence/runtime-artifact-4acc902.json`. The bounded packet's test and visual
results are recorded in `evidence/workbench-packet-20261116.json`. 4.4 and 7.3
have met their implementation checks; 4.3/4.5, 7.1/7.2, publication, full legacy
cleanup and joint acceptance remain open wherever their wider criteria are unmet.

### Publication Packet Refreeze

Baseline: Metrics `1704fc5e6d57a49e9dddb4640b637dddccc57fc7`; AIB
`e155d4cac70dde13fbd6bdbcca08141218b883e6`. `profile_source=repo-local`;
`agent_routing_mode=multiagent-configured`. One production writer per repository.
The remaining publication wave is classified `amend`: handler-side approval
identity was missing from the public snapshot, and the delta's handler re-render
sentence conflicted with decision 8. Independent read-only preflight accepted an
additive SDK accessor under authorization 3.1, not a constructor change; it also
required the approved render config and data fingerprint to join preview bytes.

- [x] PUB.CORRELATION - Register and implement the AIB W3.UI read-only
  `ToolApproval.approval_id`; preserve the frozen constructor, fail detached reads
  with existing `RuntimeUsageError`, and test approved/recovered/installed paths.
  AIB `0e8b29fc534cf220c1f94ebee56f635017decfe2` supplies candidate
  `0.1.1.dev3`, SHA256
  `8fd1559bbe015e205e82d7dc9be32e48456d6ba8b8f4923cb1592a7fb375d844`.
  The prior installed AIB formal lane recorded 180 passing tests. On 2026-11-17,
  Metrics independently rechecked the wheel hash and its six admission tests.
  The real browser join propagated the exact runtime approval id into publication
  and audit rows; it does not close the wider publication gate below.
- [x] PUB.REFREEZE - Recheck the amended decision 8 and publication delta before
  product implementation; keep the existing 3.1-3.3 and 4.1-4.2 tasks authoritative.
  Independent scoped recheck returned PASS after both OpenSpec strict validators
  passed; the preflight found no remaining owner decision.

Dependency order: PUB.REFREEZE -> PUB.CORRELATION; 3.1 -> 3.2;
4.1 and 3.2 -> 4.2; 3.1/3.2/4.2 -> 3.3 and the joined publication slice.
Owner paths are `ai_host/`, `bug_metrics/app/api/`, publication model/migration
files under `bug_metrics/`, their focused tests, the workflow/history UI consumers,
and current docs. SDK correlation remains owned by AIB, not by an App journal.
The next implementation uses a fresh candidate and an isolated local Grafana
instance. Repeated tool calls, changed data with unchanged URLs, wrong digest,
denied/expired approval, import failure and same-target supersession are required
negative/transition checks. No live provider/model, user database or existing
Grafana service is part of this packet.

Refreeze evidence: `refreeze_actions=[{"action":"amend","reason":"Expose runtime-issued
approval correlation without changing frozen signatures; bind stable publication
provenance to preview bytes."}]`; `updated_artifacts=[design.md,
specs/ai-dashboard-publish-authority/spec.md,tasks.md]`; AIB registers the matching
addition in its design 11.1, embedded-agent-runtime delta and canonical API plan.
`rerun_gates=[openspec validate embed-ai-base-runtime-in-process --strict --no-interactive,
openspec validate extract-embeddable-agent-runtime --strict --no-interactive,
independent publication preflight]`; `post_refreeze_preflight_result=PASS`.

| Contract | Authority / Producer | Consumers | Required Disconfirming Checks |
| --- | --- | --- | --- |
| INV-PUB-ID | AIB persisted approval -> runtime-issued ToolApproval.approval_id | publish handler, AiChartPublication, history result | detached access fails; restart keeps exact id; model/audit/private-store ids are not used |
| INV-PUB-PREVIEW | Metrics validated render config and stable data fingerprint | runtime re-preview, approved-byte handler, publication history | unchanged data is byte-stable; changed data with unchanged URLs invalidates; digest mismatch cannot import |
| INV-PUB-EFFECT | Metrics publication service and unique tool_call_id / supersession constraints | external tool, Grafana import, history API/UI | duplicate call does not re-import; failed import is not published; same-target concurrent history cannot branch |

All three contracts are high risk. Public API, service, UI, audit, schema,
external artifact, docs and test-fixture surfaces apply. Background scheduling
and CLI publication are not added; cache/search ownership stays with existing
Metrics data APIs. User-data migration and external provider/model qualification
remain separately gated.

2026-11-17 publication continuation: the parent owns isolated joint-test fixtures,
candidate evidence and this ledger; the implementation agent is the sole
production writer for legacy API/UI retirement and publication fixes. The r3
browser run completed the real chat -> catalog -> workflow -> pending approval ->
human approval -> Grafana import/history path and normal owned-service cleanup,
but failed because its audit-reader fixture did not close a SQLite connection.
The fixture now explicitly closes it; this failed suite is not acceptance.
The r4 run additionally opened the real Grafana page and found that generated
timeseries columns lack a time-typed field. Its failed evidence is retained at
`D:\AIGC\temp\mdb2-publication-join-20261117-r4`.
Independent negative tests also reproduced operator/tool readiness disagreement,
cross-profile operator drafts and malformed boundary inputs. These product
failures must be fixed and the joined run repeated before 3.2/4.2/10.1 close.

Subsequent observations: the generated Grafana time column, operator boundary,
readiness and malformed-input defects are fixed. The publication history is now
an actual Workbench disclosure with a region-only refresh, not just a registry
entry. A real Waitress keepalive test reproduced `server_thread_alive`; bounded
channel flush/close now fixes it. A broad run initially exposed five lifecycle
fixture failures because admission removed the global runtime module; admission
is now tested in an isolated subprocess and the paired 21 tests pass.
The complete selected regression run passed 426 tests
(`.tmp/mdb2-publication-review/focused-final-r2.xml`). Final browser QA passed all
12 route/theme/viewport combinations, and the frontend asset/CSS/152-pair
contrast gate passed. Earlier nested-interactive failures are retained under
`.tmp/mdb2-publication-review/qa-before-history-fix`; final QA is under `qa-final`.
The manual synthetic browser publication also passed, with both owned services
exiting normally (zero, no force) under
`D:\AIGC\temp\mdb2-publication-visual-20261117-701sqzwp`.

The wider automated join is still RED: r7 passed the actual chart, approval,
range-switch, history and duplicate-request assertions, then returned
`http_close_incomplete` / `stream_write_failed` at runtime shutdown. The runtime
reported one ended stream, no unfinished streams and one undelivered stream.
This is not ignored or counted as normal stop. An independent AIB-side diagnosis
is investigating the transport/disconnect contract before a new candidate or
App fix is chosen. No 10.1/10.4 or whole-topic closure is claimed.

Final publication validation (2026-11-17): independent AIB reproduction isolated
the shutdown error to historical disconnect accounting. AIB `d589ac8e6572a903edc3846e7d78195e85858868`
fixes the existing HTTP-close marker without changing public signatures. The
new `0.1.1.dev4` wheel has SHA256
`b332f338f77bf2e966de7495eea6b5968606eb670287588d97a3a4d82905ec94`;
its only changed package source is `_internal/http/state.py`, and the dev3
record remains in `evidence/runtime-artifact-0e8b29f.json`. Clean source and
installed transport groups each passed 52 tests; the installed approval/App
group passed 180 (an earlier missing formal-probe environment variable failure
is retained separately). Dashboard's affected dev4 group passed 40, and the
six runtime publication/profile tests passed, including Jira and HSD-ES refusal
before approval. R8 and final R9 each passed the real joined browser scenario;
R9 also verifies Basic authentication through production environment parsing.
Grafana returned the four expected timestamps and values `[1, 0, 0, 0]`.
Both owned services exited zero without force and released their ports.

The checked items 3.1-3.3, 4.1-4.2, 7.4-7.5 and 10.1 are supported by this
publication packet. The preceding r7 RED note is historical, not the current
result. UI evidence is reused because the dev4 wheel leaves every shared UI
asset unchanged; final Dashboard UI source passed the 12-case QA matrix.
Global settings/launcher/dependency retirement, remaining lifecycle invariants,
10.2-10.4, final AIB qualification and whole-topic closure remain open.
The durable packet receipt is
[`evidence/publication-packet-20261117.json`](evidence/publication-packet-20261117.json);
it records the wheel/source identity, validation files and hashes, runtime audit
correlation, owned stop results, and the code/test fingerprint without trying
to embed this commit's own SHA.

Review-driven truth sync: current onboarding no longer duplicates the old AI
startup/chat/publication procedure; it links the single current runbook instead.
The original case-study body is preserved under an explicit historical notice.
The active Grafana import message now names an approved publication, not a demo.
The final code was rechecked by real browser run R10 (passed, including normal
owned-service exit); the packet receipt points to that run. The remaining
global retirement and qualification tasks above stay open.

### SDK Retirement And Host Qualification Continuation

The reviewed publication packet is committed as Metrics
`10c9fa9e806a8ce529a4b3628d122abea33142a9`, paired with AIB
`d589ac8e6572a903edc3846e7d78195e85858868`. Neither branch was pushed.
Its planning-artifact review gate reached one clean pass with no open findings.

The next production writer is completing 5.7-5.9 and the remaining obsolete
settings in 8.1. Existing sync task-run factories and schema-v3 readers are
reused; retired DTOs and validation compositions are removed or migrated, not
kept as compatibility paths. Historical business data is not modified.

The coordinator is independently building the explicit-only 5.10 consumer lane
under `ai_host/tests/conformance_*.py`. The installed SDK's 21 registered
`blocking_wsgi` assertions passed; the one ASGI non-applicability record is a
skip, not a pass (`.tmp/mdb2-host-conformance-r2.xml`). The expanded lane added
shared Django/runtime identity and invalid-Host checks: 26 passed, one failed,
one non-applicable skip in r3. The remaining failure is authentication-failure
observability; the current WSGI SDK branch drops that callback, so the required
`ai_auth_failed` log is absent. Its owner/contract is being checked before a fix.
These results do not close the larger 5.10 matrix, 10.2-10.4, or the topic.

The authentication observation gap is now fixed without changing the pinned
SDK: the Metrics runtime-response boundary logs an actual 401 once, while
`record_audit(authentication_failed)` never inserts a database row. Independent
contract review confirmed this preserves the frozen WSGI no-loop-scheduling
rule and adds no SPI, worker or compatibility journal. Current missing, wrong
and duplicate credential checks, direct callback checks and shipped assertions
pass together: 30 passed, one ASGI non-applicable skip in
`.tmp/mdb2-host-conformance-r6.xml`. Separate L1 rejection-order and real CLI
occupied-port checks passed 19 cases (`.tmp/mdb2-host-order-r1.xml`).
Runtime admission metadata is still being tightened before the retirement core
is marked complete; unavailable identities must not become fabricated values.
The extended lane now also covers L0 invalid/oversized Content-Length rejection
before authentication and delivery of an exact-limit body to authentication:
33 passed, one ASGI non-applicable skip in `.tmp/mdb2-host-conformance-r7.xml`.

Continuation verification: the explicit combined consumer lane passed 52 tests
with one ASGI non-applicable skip (`.tmp/mdb2-retirement-conformance-r1.xml`);
host, append-only audit, task port, serve lifecycle and project-runtime regression
passed 78 (`.tmp/mdb2-retirement-host-r1.xml`). These overlap prior groups and
must not be added to earlier totals. The current command is recorded in
`.github/ai-governance/repo-context.md`, without changing root pytest discovery.

The real served runtime join preserved its completed project run and report
assist across two consecutive read-only recoveries, with model dispatch count
remaining two. Both owned services then stopped normally, without force:
`D:\AIGC\scrum_dashboard_validation\mdb2-runtime-join\a220a7d8-9100-4af8-bb0a-2b5553e78430`.
The final stop receipt is under `evidence/stop/0f6bae17-9639-4c54-b223-6b1a207b5312/`.
An earlier repeated recovery failed on a fixed evidence filename; that evidence
is retained. Two failing regression cases reproduced the collision and misleading
success receipt, then the four-case receipt group passed after the fix.

Independent preflight also identified the full-week completion reader and model
observation path as missed consumers of the deleted composition. Both had
meaningful failing tests, then the four-case week-consumer/UI-scope group passed
after moving the reference reader into the dedicated validation AppConfig and
using the current model observations. This is bounded consumer coverage, not a
new full-week browser qualification. The final boundary group passed 23 tests,
final fixture group passed 23, broad validation/read group passed 58, and
installed-runtime/typed/archive consumers passed 35. Counts overlap.
The final fresh served join, schema-3 identity, normal restart/reopen/stop and
source fingerprints are bound in
[`evidence/retirement-packet-20261117.json`](evidence/retirement-packet-20261117.json).
That evidence closes 5.8; 5.7/5.9 retain their wider removal checks until the
remaining launcher and regression consumers are reconciled. The counted
independent review is recorded at `.tmp/mdb2-retirement-review/state.json`.

- 与 AIB-2 同版本发布；生产切换按 `design.md` 的 Migration Plan 执行，回滚时数据库、`METRICS_STATE_DIR` 与 archive root 一起恢复，代码与镜像回到切换前的 git tag。
- 实施完成并通过评审后归档本 change：同步 9 个 delta 到主 spec（`dashboard-ai-sidecar-integration` 与 `ai-base-connector-boundary-policy` 两个能力退役），再运行 `openspec validate --specs --strict`。

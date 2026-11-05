# Dashboard / AI Base 执行 Handoff

日期：2026-11-01。类型：跨仓执行约定与规格就绪核对。
这份文件只维护双方责任、输入输出、依赖、联合验收和交付方式，不维护第二份任务勾选状态。
基座协议继续以FZ-01冻结的task-run/1为准，本文件不重开协议设计。

## 2026-11-05 Current SDK Integration Boundary

当前选择Base已交付Python SDK0.2.0a1及未改写a2 pack；完整hash/API/测试和停止条件见
[SDK 0.2 integration](sdk-020-integration.md)，后续各步见
[post-integration execution](sdk-020-post-integration.md)。
本轮用户授权Dashboard补spec、scoped commit/push、执行集成点前迁移与隔离验证，
然后在`IP-SDK020-READY`等待；这不是启动Base HTTP、DAILY/ASSIST/整周JOIN的授权。

Base owner已完成本批公共SDK制品，继续拥有SDK/API缺陷修复及版本交付。
Dashboard owner负责依赖与AiTaskContract精确组合门禁、受影响业务消费者和后续联合fixture。
双方只修改自己的仓库。Base不等待Dashboard编辑器，Dashboard不等待后置loader/events/TestKit。
SDK接收成功不等于Base HTTP联合验证；联合成功也不等于完整作者层或真实模型资格。
本节以下的早期就绪状态/催办文本保留历史，不覆盖当前tasks或重新授权旧执行指令。

2026-11-03最新作者层需求见[Report Authoring V2](report-authoring-v2.md)：
WYSIWYG-only、`#ID`唯一触发、用户版本模板、显式AI填写及错误策略。
后续确认的逐票/状态/AR/人工格式继承/稳定行序及跨周、每日触发统一见
[报告连续性](report-continuity.md)。HISTORY/DAILY归Dashboard，基座仅负责既有Task执行；
新增note不改原RunResult，来源/分析/正式报告基线分别推进，W7定时默认关闭。
一个作者层协调者可统一实施，不再要求用户另请编辑器Agent；
本次仅设计，不恢复任何产品运行。模板渲染/人工编辑/工单补全不调用模型；
显式AI填写是独立authoring profile的任务，必须有其自身注册/授权/资格，不能借summary@review-1运行。
复用task-run/1与SDK；公共协议若真有缺口仍由基座维护方冻结，不在Dashboard伪造能力。

2026-11-02报告侧新增需求见[HTML模板与人工定稿](html-report-authoring.md)：
Dashboard负责模板、原始摘要投影、草稿/人工注释、邮件HTML复制和人工确认的数据Git提交。
这些动作不调用模型，不回写RunResult，也不向模型隐式加入人工编辑。
基座无需为此修改task-run/1或等待我们的编辑器；既有后端资格工作可独立继续。
若未来模板要求新的推理内容，再按单独应用profile/分析策略处理，不把排版伪装成AI需求。
后续用户已要求连续实现到手动full-stack，应用侧精确入口为
[manual-full-stack](manual-full-stack.md)。2026-11-02再次只读核对基座tasks：
已交付范围仍为BASE-B.CANCEL-INTENT/a2 synthetic-only，未看到真实provider资格。
应用真实切换仍需基座提供匹配的qualified单backend、部署/凭据注入办法和版本化制品；
这不阻塞实际应用+SDK+HTTP+Git的合成full-stack，不要求基座替应用实现报表或编辑器。

## 1. 谁写哪份 OpenSpec

| 内容 | 唯一编写/维护方 | 权威入口 |
| --- | --- | --- |
| 公共Run API、基座内部实施、SDK、BASE-B测试 | AI Base Agent | `D:/AIGC/Report_creater_agent/openspec/changes/define-app-scoped-task-run-contract/`，若拆新change须明确引用FZ-01 |
| Project/Stage、provider、archive/delta、业务attempt、接受/发布、Dashboard消费者测试 | Dashboard Agent | 本目录[design](design.md)、[spec](specs/project-reporting/spec.md)、[tasks](tasks.md)及技术附录 |
| 跨仓分工/依赖与联合用例 | Dashboard维护本handoff，双方确认自己的交付 | 本文件；协议字段不在此复制成第二份authority |
| 模型/来源/用户数据的真实资格 | 各owner执行，联合核对匹配版本 | 各仓tasks的真实命令、结果和授权记录；不得互相代签 |

**推荐分别写自己的实施规格。** 我方把共享边界及对基座的验收要求写清；
基座最了解自己的worker/store/auth/backend，应自己定义准确内部API、文件闭包和故障注入。
不由一个Agent代写两仓全部实现，也不允许两个Agent修改同一个任务清单或互相复制运行器。

## 2. 实际就绪程度

| 范围 | 当前证据 | 是否可直接照此执行 |
| --- | --- | --- |
| 公共task-run/1边界 | FZ-01及CF-A/B已冻结 | 可以作为实施依据，不等于运行资格 |
| BASE-A | 基座proposal/design/spec/tasks及46/515记录；0.1.0a1 pack/wheel已交付 | 已有实现；本方C0.N1已通过安装SDK的12例MockTransport验证，非服务联调 |
| BASE-B.CANCEL-INTENT | 2026-11-02核对基座delivery/tasks；a2 wheel/manifest及21个pack hash匹配 | 基座已交付合成取消/安装/loopback资格；完整BASE-B仍未完成 |
| Dashboard W1 | 代码及验证存在，W1.R已通过隔离候选独立评审 | 进入W1.REPLAN/W2，不等于整个项目完成 |
| Dashboard C0 | [sdk-intake-plan](sdk-intake-plan.md)、实际12例脚本和receipt | C0.N1/C0.R已完成，仍只证明安装SDK的合成行为 |
| Dashboard W2 | 已实现双语项目/阶段表单，桌面Ego验证和W2.R完成 | 已完成，不等待BASE-B |
| Dashboard W3 已交付部分 | 连接/凭据、Git归档、Jira网关、诊断CLI和内部采集链路已通过各自独立评审 | 当前细化W3.LISTS；仅合成资格，不是实时报告上线 |
| Dashboard W3 剩余及 W4-W7 | 已有能力/模块/迁移/用例族 | 后续各叶任务仍先冻结准确API/用例，不能称全部波次均已implementation-ready |

基座后续交付authority为
`D:/AIGC/Report_creater_agent/openspec/changes/define-app-scoped-task-run-contract/base-b-cancel-intent-delivery.json`。
早期未收到BASE-B计划的记录由这份新交付替代，不需重开FZ-01。
就绪按能力包判断，不要求整个BASE-B或所有远期应用波次先完成。

## 3. 分模块与数据交接

| 交接 | Producer / owner | Consumer / owner | 必须交付 / 拒绝条件 |
| --- | --- | --- | --- |
| 基座合同与SDK | 基座DTO/pack/Python SDK | Dashboard C0、W5.APP/CLIENT | 包版本、manifest/hash、操作集、qualification；不能用源码路径或漂移的临时wheel替代安装包 |
| 任务输入 | Dashboard W4/W5.INPUT | 基座compiler/RunSubmit | 固定scope/profile、原content/inputSha256、logical hash、原deadline/limits；缺requiredParts不得发strict完整摘要 |
| attempt -> Run | Dashboard W5.CLIENT | 基座submit/by-key/result | POST前持久exact payload/key/store；丢回包只查原key，不换库/续期/新key |
| Run -> 本地候选 | 基座RunResult | Dashboard W5.ACCEPT | 原content/hash及身份/版本/receipt；应用验证后绑定input_hash，原content不得改写 |
| 取消/unknown/恢复 | 基座BASE-B | Dashboard W5.CLIENT/W7.RUN | 真实操作及SDK方法、持久状态、故障用例、风险账；BASE-A不存在的能力不得由应用自行冒充 |
| accepted -> 报告 | Dashboard W5.ACCEPT/W6 | Dashboard CLI/Web | evidence/owner/CAS及发布字节；模型成功不是业务接受或发布批准 |
| provider访问 | Dashboard W3 | Dashboard capture/delta | Jira/HSD endpoint/principal/coverage；基座不持有PAT、不读取Jira数据库 |

基座改动限其repo；Dashboard限其repo，旧chiplet源码只作固定版本port来源。
真实公共API变更由基座提出版本化delta，Dashboard回答消费者影响；不能静默改变0.1.0a1已交付bytes。
业务工作不等待BASE-B整体完成，基座也不等待Dashboard UI/原文采集完成。

## 4. 依赖与汇合

2026-11-02用户明确要求尽早/提前联调。应用侧新增
[W5.JOIN精确切片](early-ai-integration.md)：复用已完成的catalog/capture/archive，
先验证首次完整摘要、持久attempt、结果接受与无变化复用，不等待名单/附件/完整delta。
这不是取消剩余功能，也不是将C0当作W5。

```text
已交付BASE-A -> Dashboard C0.PLAN.R -> C0.N1 -> C0.R
已交付BASE-A -> 基座BASE-B首个计划/验证签核 -> 基座分批实现/发布

Dashboard原业务链：W1.R -> W1.REPLAN -> W2 -> W3 -> W4
提前汇合：C0.R + 已完成catalog/capture/archive -> W5.JOIN -> 首次业务合成联调
C0.R + W4业务证据 + 实际SDK/pack -> W4.REPLAN -> W5 -> W6/W7

基座BASE-B相应能力 + Dashboard attempt/接受/运行服务 -> 联合可靠性验收
双方真实资格及获准来源 -> 真实手动报告验收
```

C0.R只是消费端SDK验证，不把W4/W5/W7全部绕过去。
W4.REPLAN负责冻结应用最小持久attempt API及W7复用方式，基座不反向依赖该内部实现。
跨仓只对要启用的能力设置汇合门禁，不将所有可选功能/所有backend组成笛卡尔积。

### 什么时候真正需要等待对方

| 时点 | Dashboard必须具备 | 基座必须具备 | 等待规则 |
| --- | --- | --- | --- |
| 当前本地工作 | C0.R、W1.R/W1.REPLAN及随后W2-W4 | 已交付的固定BASE-A pack即可 | 不等BASE-B，不等对方UI/其他应用重构 |
| 首次合成业务联调 | 固定输入、持久attempt、结果校验/CAS的应用实现 | 可启动的专属synthetic candidate、匹配SDK/pack及测试身份 | 两侧实际入口都存在才联合跑；BASE-A已有基本协议，不需要等BASE-B全部完成 |
| 取消/unknown/原生恢复联调 | 对应客户端处理与应用状态恢复 | 对应BASE-B端点、SDK方法、恢复实现及能力证据 | 按能力等待，不靠应用伪实现缺失的基座能力 |
| 真实手动报告 | 真实来源授权、完整或诚实partial采集、发布/部署前置 | qualified单backend及真实运行授权 | 双方匹配版本和授权同时满足；不以合成或文档签字代替 |

等待某一能力期间继续没有该依赖的本地模块/测试；如果后续动作确实都依赖未交付能力，
明确报告所缺版本/端点/证据，不重复全量测试或重开已冻结设计。

## 5. 基座须补齐的 BASE-B 实施包

以下B-P编号是本handoff的**交付要求**，不是替基座创建实施节点/状态；基座应映射到自己的task IDs。
可沿当前change扩展或拆有明确依赖的新change，不改写冻结design bytes。

| 包 | 需明确的边界与API | 最低验证用例 / 退出条件 |
| --- | --- | --- |
| B-P1 取消与unknown | RunStore/worker/backend取消意图、CAS、dispatch knowledge、receipt revision；cancel/get/events及SDK支持面 | cancel对queued/running/terminal；成功/取消/到期竞争；may-have-dispatched零自动重派；usage补记不复活终态 |
| B-P2 重启/恢复 | 实际进程owner、writer/claim fence、storeId、启动恢复、原deadline与exact payload；确定可观察的崩溃边界 | 受理后回包前、intent前后、结果落盘前后崩溃；重启不换store、不重复dispatch；旧进程/错库拒绝 |
| B-P3 限额/留存 | 真实queue/reservation/unknown exposure、结果与观察窗口、tombstone转换/容量；已有key与新准入分支 | 原key+过期deadline+满配额仍重放；410/409；未决unknown不得清账/GC；容量满拒绝新key |
| B-P4 单backend资格 | 固定adapter/model/gateway/limit组合、tool/history隔离、输出schema、实际可观察计数 | 合成请求捕获先行；只按授权运行真实backend；计数/费用未知不假报0，不支持能力明确拒绝 |
| B-P5 版本化交付 | 新SDK方法签名、generated schemas、安装包、manifest、capability矩阵及受影响消费者闭包 | 真正从包安装；无server依赖；BASE-A消费者回归及真实breaking适配；不可只写“已支持” |

每个基座叶任务必须在编码前列明：
owner_paths、depends_on、提供/消费的精确函数/DTO、状态/异常/副作用、
关键事务与锁/CAS、测试node ID及fixture、命令/预计层级、成功和失败退出条件。
发现内部API未定先在该包局部设计，不再次泛评FZ-01。
B-P1/B-P2/B-P3的内部先后依赖由基座依据实际共享store/worker代码决定；不得假定它们可盲目并行写同一文件。
请优先交付第一个合成能力包；真实环境缺权限不阻塞无依赖的合成实现。

## 6. 双方共同的 validation strategy

| 层级 | 主责 | 证明什么 | 不证明什么 |
| --- | --- | --- | --- |
| L0 静态/包/版本 | 各自产物owner；Dashboard做C0接收 | schema闭包、版本/hash、安装导入、操作集、文档 | 业务正确性/真实运行 |
| L1 单元/内存transport | 各自模块owner | 输入/输出拒绝、typed错误、scope/store绑定、无隐式retry；业务纯函数反例 | SQLite事务/进程恢复 |
| L2 临时真实存储/API | 基座Run；Dashboard accepted/archive | CAS/唯一提交/并发/写失败/重提，使用实际store而非全部mock | native crash或远端已取消 |
| L3 专属原生恢复/部署 | 基座生命周期；Dashboard应用集成 | 进程退出/重启/版本组合/隔离安装，合成上游 | 收费provider资格 |
| L4 明确获准live | 对应外部adapter owner | 指定来源、backend、身份和限额下的真实能力 | 全模型/全工单或全环境 |

双方沿同一冻结合同各测自己的责任，不复跑对方515项作为每次进件默认动作。
联合用例只在两侧相应能力实际到货后执行；不把将来的mock替身称为已集成。

| 联合用例 | 基座责任 | Dashboard责任 | 共同判据 |
| --- | --- | --- | --- |
| J01 submit回包丢失 | 保留同key/run/结果，不重复dispatch | 持久原attempt，按key恢复 | 唯一计算及唯一业务接受 |
| J02 stale结果 | 原结果可重取且身份完整 | 拒绝旧target/profile/base-summary CAS | accepted/publication不前进 |
| J03 cancel/timeout | 终态裁决、停止证据与usage分离 | 不将取消当退款，不接收迟到业务结果 | 终态不复活、不盲重跑 |
| J04 进程/版本恢复 | 原storeId/fence/unknown继续有效 | 原payload/key/store继续有效 | 错库拒绝，唯一执行不丢失 |
| J05 partial/no-work | 不伪称缺材料的完整执行 | 缺coverage保留pending；有效无变化零模型调用 | 不丢历史、不推进错误水位 |
| J06 result过期/未知费用 | 结果410不切断允许的receipt观察；tombstone防重放 | 正确展示过期/unknown，不自动新key | 不把过期当“从未执行” |

## 7. 每次交付给对方什么

W5.JOIN已实际跑通首次应用业务合成闭环，CORE与最终验证入口的独立评审已完成。
正式应用方回执为[w5-join-delivery.json](w5-join-delivery.json)。
当前回执位于Dashboard `.tmp/task-run-w5/runs/0221de2b-4577-43d6-823c-72edfba648a9/`，
包含原始业务回执、独立artifact核对和正常停服记录。
跨应用发现与基座下一步建议见[w5-base-feedback](w5-base-feedback.md)。
这不是原默认占位fixture smoke，不是完整W5或真实模型资格。

给基座Agent的下一条消息可以直接使用：

```text
Dashboard已经完成W5.JOIN首次业务合成联调，独立评审无剩余问题。
请读取 D:/AIGC/scrum_dashboard/openspec/changes/add-provider-neutral-project-reporting/w5-join-delivery.json
和同目录 w5-base-feedback.md、execution-handoff.md。
请中立核对交接边界并优先处理a2 RunSubmit schema未表达UTC毫秒格式约束的问题；
在你方OpenSpec记录修正和新版本制品，不改写冻结a1/a2 bytes，不重开FZ-01。
同时评估官方合成launcher接收显式fixture-pack和自包含runtime交付，以减少各应用重复装配。
请返回确认、你方任务ID、接口/制品计划及后续真正需要双方等待的联调点。
本回执不宣称真实模型、取消/unknown全部能力、原生恢复或正式部署已经通过。
```

统一短回执：`change/task IDs`、完成/待实现/待资格的区分、源码commit或固定快照、
wheel/pack/version/hash、操作及qualification矩阵、实际API变化、测试命令/结果、
失败/未运行项、接收方下一最小动作。不附原文/secret，不把派发任务等于完成。
每仓只有自己的tasks勾选完成；本handoff只链接回执，不同步一份可漂移的百分比。

当前可交付：本handoff、Dashboard C0验证及W1/W2项目目录和双语桌面工作流的隔离候选评审回执。
当前不能宣称：基座BASE-B整体完成、Dashboard W3-W7全部可直接编码、双方业务运行全部打通。

### a2 后续交付接收

2026-11-02本方只读核验a2 manifest
`e7386f82d2bf3963feccc28cfbfda732b9eddb829831d5ba660b50554e5f81c4`、
wheel `32e54c5f443e39daa55190c4de142ac6c12478204d8fba6bf9909149c3b365f9`及21个pack文件。
新增cancel；qualification仍为synthetic_only。原a1消费环境/证据保留，不静默升级。
基座回执记录574项非live和5项安装/loopback验证；本方没有重跑或据此勾选应用业务。
W4.REPLAN将选择实际SDK/pack版本。

专属launcher已交付，但仅接受已发布的profile输入向量，不是任意业务摘要服务。
本方到W5汇合时须提供由真实应用输入/attempt/接受接口生成的合成向量与身份，
核对能否直接使用已发布向量，或由基座显式注册匹配的新合成fixture。
不能为适配固定fixture而改写源hash、伪造project/stage身份或跳过应用接受。
这项输入适配是联调准备，不是要求更改冻结公共API或调用真实模型。

已核对：默认review向量的占位ID/规则hash不适用于本应用实际UUID与归档hash。
基座现有`create_task_run_candidate(..., profiles, grants, backend)`支持显式
合成装配。W5.JOIN计划使用该未修改的factory和固定a2 profile，登记应用生成
的专用向量及实际scope；该fixture由Dashboard的联合测试负责，不冒称默认
launcher已覆盖它。若该factory边界不可用，再请基座交付版本化fixture登记入口。
基座不需等待我们的名单/附件功能；也请继续推进自己的后续能力，勿重开FZ-01。

## 8. 发给基座 Agent

```text
请在 D:/AIGC/Report_creater_agent 完成首个BASE-B工作包的编码前准备，持续推进到CODE_READY。
本轮终点是可以直接开始该包编码，不是完成全部BASE-B，也不开始真实模型/正式部署。

先读取跨仓执行handoff：
D:/AIGC/scrum_dashboard/openspec/changes/add-provider-neutral-project-reporting/execution-handoff.md
以及你方FZ-01、冻结design、BASE-A实际代码/SDK/pack和当前tasks。

你负责基座内部实施规格，我负责Dashboard规格；不互改仓库。
FZ-01不重开。按第5节B-P1至B-P5识别依赖，选择最近一个可独立验收的合成工作包，
例如取消/unknown的最小纵向切片；不要把整个BASE-B混成一个巨型节点。

请实际完成以下准备，而不是只返回建议：
1. 选择明确task ID、用户可观察结果、owner_paths和不涉及的文件；记录真实HEAD/dirty与BASE-A版本。
2. 在自己的唯一OpenSpec中补proposal/spec/design/tasks所需内容，明确与现有change的关系。
3. 固定这一包的内部函数签名/DTO、producer/consumer、状态转移、错误及取消/重试/恢复、
   事务/claim/CAS、持久化前后、资源清理和SDK扩展。关键处不能留给编码时猜。
4. 每个叶任务列出depends_on、准确文件、步骤、测试node和完成条件；不依赖Dashboard尚未实现的内部模块。
5. 给出分层validation和具体test cases：输入/初始状态、操作、预期输出/持久状态、
   副作用计数、失败判据。必须包含正常路径、错误路径、竞争/重放和相应恢复边界。
6. 列出可执行测试命令、专属临时数据、合成身份/上游、环境准备和有界收尾方法。
   缺真实provider权限不应阻塞合成包；但不能把synthetic算作真实资格。
7. 做一次独立的计划/验证审查。修复阻断项并做必要定向复核，确认无关键API/用例/依赖缺口。
   不重复审整个FZ-01，也不默认运行全量或live测试。
8. 一旦满足本handoff第9节的CODE_READY条件，就停止扩大准备范围并返回。

最终请返回：
CODE_READY: yes/no（针对准确工作包，不是整个产品）
工作包ID、spec/design/tasks/测试矩阵绝对路径、已固定接口、准备检查证据、
第一步编码动作和第一条RED测试命令，以及仅影响后续阶段的剩余限制。
若仍为no，请给出唯一必要阻断、所需输入和不受影响可先做的工作，不以笼统“还需讨论”收尾。

可以创建/修改本仓设计文档并做无业务副作用的环境探针；本轮不配置真实凭据、
不启动正式服务、不迁移业务数据、不调用收费模型、不修改Dashboard。
不需要等两仓所有远期规格都完成，目标是你方下一包确实可以开工。
```

## 9. CODE_READY 的共同定义

就绪按**指定工作包**判断，不对整个未来项目作一个笼统布尔结论。
以下都是实施前的准入，不等于实现测试已经通过：

| 条件 | 必须有的证据 |
| --- | --- |
| 明确范围 | task ID、唯一owner、准确文件边界、可观察退出结果和非目标 |
| 接口无关键空白 | 上下游、输入输出、状态/错误、持久化/副作用、失败恢复；不依赖假接口 |
| 依赖可用或已隔离 | 固定包/源码版本与环境；缺远期资格不阻挡当前合成任务，当前必要依赖不能假报可用 |
| 验证可执行 | 正常/拒绝/竞争/恢复用例、输入与预期、准确命令、测试身份/数据、时间上限及收尾 |
| 单一执行清单 | OpenSpec tasks承接该包与依赖，没有两份状态或未注明owner的跨仓动作 |
| 审查已收敛 | 对该包的独立计划/验证审查无未关闭阻断；不用追加无关完整评审制造等待 |
| 第一动作确定 | 明确先写哪个文件/测试及预期结果；新增行为须能观察原缺口的RED，验证既有能力可首次即绿，不人为制造失败 |

Dashboard C0、W1/W2、W3连接/归档/网关/CLI/内部采集及对应评审已完成；
下一包W3.LISTS仍在接口和验证设计收敛，不能提前宣布整包可编码。
不能由这些完成状态推导后续业务波次或真实AI接线也已完成。
基座CODE_READY须由其实际准备和回执证明，Dashboard不能代它标记完成。
编码前准备已支持本轮C0.N1开发验证；其他工作仍按指定阶段的依赖和审查门禁执行，
不由C0通过推导真实产品部署或外部调用已获准。

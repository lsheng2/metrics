# AI Base Review 与增强 Handoff

日期：2026-11-01。交付状态：FZ-01已登记，BASE-A合成pack/SDK已交付；并行执行分工见integration-execution。
目标工作区：`D:/AIGC/Report_creater_agent`。
这是任务委托和验收要求，不是基座canonical API或第二份实施清单。
Dashboard进度仍归[tasks](tasks.md)，基座实施由接收方在自己的OpenSpec管理。
**当前执行入口为[execution-handoff](execution-handoff.md)**：明确双方分别编写实施规格、
BASE-B补齐要求、C0详细计划、共享依赖和联合用例。FZ-01及CF均已收敛，不再重复征询。
第1节保留原委托背景，具体执行范围和副作用边界以既有分工、各仓tasks和授权为准。

## 0. 先理解业务背景与合作目的

### 我们要做什么App

这不是一个新的通用聊天窗口，也不只是把Jira数据画成图。
用户每天主持项目站会，需要在明确的项目阶段范围内看所有工单，持续回答：
“这是什么问题、发生了什么变化、现在卡在哪里、下一步找谁做什么、判断依据是什么”。
目标是**带来源证据、历史记忆和增量分析的项目进展管理与报告App**，减少每天手工逐票阅读。
报告要区分当前assignee、明确被指派的下一行动人和模型建议的负责人，不能虚构指派或验证结论。

最初实例是Chiplet的CRC阶段/Jira缺陷清单，随后用户明确：Chiplet仅是项目实例，
任何用户都应能创建自己的Project/Stage并选择Jira或HSD-ES范围。
阶段内绑定一条批准后不可变的范围规则；规则改变新建Stage，不能覆盖旧历史。
范围选择与报告分析分开：UI/tag/saved query/名单等来源形式由应用provider adapter解析，
不能要求模型每次浏览Dashboard再猜应该分析哪些工单。

### 为什么从旧项目转向Dashboard和AI Base

| 演进 | 原因与当前决定 |
| --- | --- |
| 旧`D:/AIGC/chiplet_programmgr` | 已积累采集、差分、证据、归档、报告及本机Codex执行相关实现；原T12整体交付未闭环，不能直接当完整产品搬迁 |
| 转入`D:/AIGC/scrum_dashboard` | 用户选择复用现有scope/provider设置、指标与工作台，在Django模块化单体中新增通用`project_management`，不维护另一个Chiplet专属UI/产品 |
| 接入`D:/AIGC/Report_creater_agent` | 将可复用的AI执行/SDK能力交由公共基座演进；应用保留采集、累计delta、历史与业务接受，不再在各应用重复扩建模型执行基础设施 |
| 允许协调式breaking changes | 应用均处于早期，用户接受同步更新其他APP，要求专门变更记录和Agent迁移包，优先获得合理的公共架构 |

旧实现经历过长期运行/进程生命周期、恢复和验证收口工作，因此希望减少重复基础设施和协调成本。
但基座目前也有待实现能力：接入是共同演进，不是“换SDK即可解决全部问题”。
减少后续维护成本是目标，不是已经测得的提速；本请求不要求基座重写业务App或复制旧keeper。
旧代码的复用/重写清单由Dashboard的[migration-catalog](migration-catalog.md)管理。

### 用户工作流与模型参与位置

以下是目标工作流，不代表当前完整上线：

1. 用户创建Project/Stage，选定provider连接和范围规则，应用冻结来源定义。
2. 用户手动触发本轮；未来可由定时触发调用同一应用服务，但当前不自动启用调度。
3. 应用枚举范围和检查更新时间等轻量标记，按需要读取详情、评论及可访问历史，保留原始材料和coverage。
   Closed/Fixed也检查更新；移出范围、无权限、缺页均不能算关闭或采集完整。
4. 应用脚本比较快照/哈希、生成累计delta；模型不负责决定范围、抓取Jira或计算差异。
   基线是“上一次成功接受的摘要”，不是上次采集；可访问原文先归档，无变化且摘要仍有效时零AI调用。
5. 仅把必要的“旧摘要 + 累计原始delta + 所需证据”交给AI Base Task，返回带证据的结构化候选。
   首次或无法建立可靠delta时，对受影响工单准备完整材料，必要时有界分块，不能静默截断。
6. 应用校验来源/owner/引文/coverage/目标版本，接受候选并推进摘要水位；模型失败不推进水位。
7. 应用生成英文Markdown/Excel及完整在途行动清单；没有变化的阻塞项仍可见。
   保存每轮采集、差分、摘要和发布记录，支持回查；UI支持英文/简体中文，翻译将是独立展示层。

原始工单语言保持原文。初期tracker只读、本机单用户、桌面Chrome/Ego功能优先；
UI仍由Dashboard的Django/Bulma/htmx承担，不要求改成基座React/Tauri界面。
应用配额和每轮时间/输入/输出上限用于有界执行；不允许为节省token丢弃未处理内容。
Jira/HSD实际支持哪些评论/历史必须由adapter证明；源端不提供的历史不能被摘要或基座伪造。

一个合成例子说明为什么需要这些接口：Alpha/Release-1中某工单已有成功摘要S1；
随后新增不同comment ID的B、C。应用保存B、C，以S1+B+C为输入，而不是重送全部旧评论。
如果模型失败，下一轮新增D后应提交S1+B+C+D，不能从失败那次采集起算而丢掉B、C。
如果只是SDK收到结果前连接断开，应按原clientRunKey查询已派发run，不能默认再付费生成一次。
这些规则由应用累计delta和基座durable Run各自负责，不混成同一个“更新时间水位”。

### 业务需要如何映射到基座API

下表的操作名是待review的责任标签，精确协议仍由基座冻结；不是已经上线的接口。

| 业务需要 | 应用负责 | 基座增强及验收方向 |
| --- | --- | --- |
| 项目/阶段/来源隔离 | 范围、用户权限、provider与credential选择 | E4/E5：应用注册、opaque scope、版本化profile、对象授权；不理解Jira业务规则 |
| 不丢材料且节省token | 原文归档、accepted基线、delta与必要证据选择、no-work复用 | E1/E2/E4：显式输入、inputs/seal、完整性manifest和Task策略；strict模式无隐式Chat历史/tools |
| 长任务不依赖网页会话 | 持久业务operation、每工单/片段attempt与候选映射 | E3/E6：submit/get/byClientKey/events/result/cancel，断线查询、幂等和真实取消语义 |
| 解释问题、状态与下一行动 | 提供领域prompt/schema，校验引用/责任人/结果接受 | E2/E7：结构化结果、来源版本/输入hash、真实执行回执；不能把mock算成功 |
| 每日持续运行但费用可控 | 业务配额、分批/续跑、报告完整/partial判定 | E3/E5/E7：有界队列、预算/attempt/usage、unknown记录；不可隐式retry或误报0费用 |
| 可历史追溯和可靠发布 | Git原文、业务索引、摘要接受、报告发布/备份 | E2/E3：运行/结果/artifact身份、下载与留存边界；基座run成功不代替应用发布 |
| 接入现有工作台且服务多App | Dashboard旧交互和新报告分别适配 | E6及API-01至06：可安装SDK、版本协商、fake pack、breaking记录与逐应用迁移，不做私有后门 |

### 对其他应用的影响与完成边界

RCA的草稿/ReportTask/评审、SoC流水线及外部GUI事件、Sample的领域中立与profile隔离、
内置Dashboard和外部Dashboard的binding/context/host-action都属于review对象。
它们的API可以变化；业务接受、权限、来源和真实费用保证不能被当兼容负担删除。
具体调用点、共享资源/DB/启动/升级影响及测试入口见
[增强请求第5至6节](ai-base-enhancement-request.md)；
逐API候选、版本记录和应用迁移责任见[API演进记录](ai-api-evolution.md)。
本handoff第5节规定每个应用Agent应收到什么，不把“已发送文档”当“应用已适配”。

当前Dashboard在本次核对的tasks中是W1项目/阶段目录和本机CLI已实现并验证、W1.R未关闭；
完整采集/AI/发布仍待后续实施。**基座应review并增强公共执行层，不是接管旧T12或宣称项目管理App已交付。**
最新状态始终读取[当前说明](../../docs/current-baseline/project-reporting.md)和[tasks](tasks.md)；
本节是交接背景，不另维护进度。后文定义基座要返回的合同、实现包与迁移证据。

## 1. 原始增强委托参考（本轮不执行）

```text
请在 D:/AIGC/Report_creater_agent 工作，先独立review，再设计并增强AI Base和SDK。

业务背景：我们在scrum_dashboard内建设通用项目管理/每日站会报告App。
用户定义Project/Stage和Jira或HSD-ES范围，应用采集并归档原文、比较变化，
仅对需要更新的工单用“旧成功摘要+累计delta+必要证据”调用AI，再校验候选、生成报告。
需要解释问题、当前状态、阻塞、下一行动和负责人；不是新聊天壳，也不是让模型直接管理Jira。
Chiplet仅是初始实例。请先读本文第0节，理解为什么从旧独立实现转向Dashboard+公共AI基座。

用户最新决定：所有相关应用处于早期开发。优先形成合理、通用的架构，允许breaking API changes，
也允许修改同仓应用及要求外部应用同步适配。不要为了保留旧API维护永久兼容层。
每项破坏性变更必须有版本化记录、旧新接口示例、逐应用迁移说明和验证要求。
无需仅因其他APP要改代码再次询问；权限、数据删除、真实收费调用和正式部署仍按本工作区授权。

先读取：
1. 本仓AI执行入口/契约、当前OpenSpec，以及实际代码和测试，不把旧研究当当前实现。
2. D:/AIGC/scrum_dashboard/openspec/changes/add-provider-neutral-project-reporting/ai-api-evolution.md
3. 同目录 ai-base-enhancement-request.md
4. 同目录 ai-base-review-handoff.md 的完整内容。
核对Dashboard消费端是本次review的必需部分；进行该步骤时必须读取
application-integration.md 和 integration-execution.md，不必为其他模块加载无关历史。

独立评估E1-E9及API-01至06，对每项给出accept/modify/reject/defer和源码依据。
必须从RCA、SoC、Sample、内置Dashboard、外部Dashboard及实际发现的其他消费者出发，
而不是只为项目日报设计。审查公开SDK调用、服务端直接runtime调用、CLI、回调和持久数据。
可以改变当前建议的类名、endpoint、DTO、同步/异步和模块边界；冻结你认为更合理的一套合同。
不能改变的是权限/证据完整性/真实usage/不确定派发不盲重试/业务结果接受等安全与正确性要求。

目标：独立于Chat会话的Task/Run；明确输入和完整性；结构化结果及artifact；
持久幂等、查询、取消、恢复、usage与能力声明；可供多应用使用的版本化profile和TS/Python SDK。
Chat与Task可共享合理的execution core，但严格任务不能隐式使用Chat历史/工具/开发skills。
应用保有业务数据、领域编排和接受/发布权；基座不硬编码Jira、Chiplet、英文、Git或Windows。

按本文工作顺序：review与consumer census -> 冻结合同和迁移包 -> fake双schema纵向闭环 ->
可靠执行与目标SDK/同仓消费者 -> 外部应用handoff -> 匹配版本资格及发布。
在本仓OpenSpec中先定义每个叶任务的文件边界、精确API、依赖、负向用例和退出条件再编码。
已有授权范围内推进实现，不停在泛泛建议；真实后端/正式部署缺授权时单列，不阻塞合成工作。
不要为每个小步骤再造一套计划、review轮次或完整回归。

交付必须包含：review结果、唯一OpenSpec、canonical API/schema、版本化变更/迁移记录、
可安装SDK和fake conformance pack、各应用迁移handoff、实际验证证据、已知限制。
尤其说明RCA草稿/ReportTask如何接受结果，SoC异步/GUI事件如何迁移，Sample如何保持领域中立，
以及Dashboard旧Chat和新Task分别如何接入。mock/stub不能算真实模型能力。
不得声称外部应用已经适配；提供它们的任务包并等待实际回执。

你可以修改本仓及同仓应用，保留他人dirty changes。外部仓库本任务只读并输出handoff；
不复制凭据/工单原文，不自动调用真实模型、启用正式调度或清理用户历史。
用中文交付说明；协议/SDK字段和代码遵循本仓规范，业务语言策略按应用配置。
```

## 2. Review 输入与当前证据

上一轮只读快照：AI Base HEAD `2332d549ab69a7e927865acd0e3db2a19295c609`。
实际checkout可能更新，先记录真实HEAD/dirty及版本；旧图索引当时不新鲜，
不能根据旧索引的空结果断言不存在消费者。按本仓检索规则检查来源和coverage，必要时读源码。
本次没有重新执行基座测试，也未证明下面所有能力已实现或所有路径已列全。

| 必查范围 | 本仓已知入口/证据 | Review要回答的问题 |
| --- | --- | --- |
| Run规格与runtime | `docs/common/AI-Base-Run-Interface-Spec.md`、`services/app-service/template_runtime/services/agent_runtime.py`、`app/cli.py` | 草案与实现差距；哪些责任应共用，哪些应拆出 |
| 公开SDK与装配 | `packages/application-sdk/src/index.ts`、`services/app-service/app/main.py`、`app/services/extension_startup.py` | SDK/server是否耦合，怎样安装注册，哪些lane实际可用 |
| RCA | `apps/desktop/src/profiles/reportCreator/workflow/RCAWorkflowPage.tsx`、`services/app-service/app/services/review_agent_service.py` | Chat副作用、review直调runtime、truncation/mock策略如何迁移 |
| 交互/Sample | `apps/desktop/src/components/chat/WorkflowChatPanel.tsx`、`services/app-service/tests/test_draft_runtime_api.py` | session/stream/审批和profile隔离，不以Task策略替代全部Chat |
| SoC | `services/app-service/app/routes/soc_sessions.py`、`app/services/soc/pipeline/orchestrator.py`、`extraction_agent.py` | 当前stub与真实路径，session/pipeline/run边界，外部GUI契约 |
| Dashboard | 本仓Dashboard profile/connector及外部`D:/AIGC/scrum_dashboard/ui_web/ai_base_workbench_adapter.py` | binding/context/host action如何共同升级，task不能绕过批准 |

表内简写的`app/...`位于`services/app-service/`，`extraction_agent.py`位于上述pipeline目录。
外部GUI精确仓库/路径请从本仓`docs/common/Dual-Repo-Co-Development-Governance-Manual.md`
和实际调用证据定位；未知就记录counterpart-required，不假设GUI已更新。

Review先简述你理解的项目管理工作流、应用/基座边界和其他应用影响，再交付逐项表：
候选ID、观察到的问题、accept/modify/reject/defer、替代方案、
受影响消费者、可复用内容、新增工作、证据缺口。复杂性应与真实多应用需求相称。
允许合并/删除错误抽象；不要求机械实现全部建议。

## 3. 先冻结的合同

在基座自己的OpenSpec/API reference中冻结下表，形成可执行schema/fixture。
本文列责任不冒充精确签名；HTTP路径/字段/大小/状态必须由该合同给出，不能留给各应用猜测。

| 合同 | 必须固定的内容 | 最小反例 |
| --- | --- | --- |
| Application/scope | 认证主体、opaque scope、delegated actor信任、每对象授权、版本握手 | 有效app身份仍不能读取/取消另一app或scope对象 |
| Profile/input | schema revision、prompt hash、装载策略、inline/blob、seal、大小/token上限、require_all/检索语义 | 超限/缺输入/不支持策略派发前拒绝；不能静默截断或加载历史 |
| Run/attempt | submit/query/client key、内容fingerprint、durable acceptance、唯一claim、事件分页 | 同key同内容返回原run，异内容冲突；POST回复丢失不重复派发 |
| Result/artifact | schema验证、source/logical/effective input绑定、原bytes/hash、授权下载、retention/ACK | 无效schema/错误归属不成功；run成功不触发应用发布 |
| Cancel/recovery | 唯一终态裁决、deadline、provider停止能力与unknown、在途升级 | 取消与完成竞争不复活；可能已派发但无结果时不自动重发 |
| Resource/usage | app/lane准入、attempt预算、reservation、known/unknown费用、回收pins | SDK隐藏retry被检测；worker退出不抹除未知费用/材料 |
| SDK/version | TS/Python安装包、typed errors、支持组合、旧版拒绝、CLI作用域 | 不支持版本在业务/模型副作用前失败；无server源码目录也能导入SDK |

对外协议只有一个权威；旧Run草案被采用/替换时标出supersession。
每个改变旧调用的合同必须关联API change ID和具体消费者，不允许只发布新版SDK而不交代迁移。

## 4. 工作顺序与退出条件

下面是handoff顺序，不是另一份可独立勾选的任务清单。
接收方在本仓唯一tasks中拆叶任务，采用本仓profile/routing/门禁；Dashboard不替它维护完成状态。

| 顺序 / 对应交付组 | 边界与输出 | 依赖和退出条件 |
| --- | --- | --- |
| Review/freeze，BASE-A准备 | review决定、consumer census、目标API、API change log、migration guide | 每个高风险消费者有反例；旧新差异、owner和版本策略明确，独立设计review后开始相应编码 |
| BASE-A | 最小输入->Run->Result、fake backend、最小客户端 | 文档提取与项目简报两个不同schema通过；零真实模型调用；应用可据此并行适配 |
| BASE-B | 幂等/取消/恢复/权限/费用、backend能力及有界资源 | 先合成故障和专属服务；真实backend资格只按授权，unsupported诚实暴露 |
| BASE-C | 打包SDK、同仓消费者迁移、按需CLI、逐应用handoff | 安装包及新合同测试通过；本仓实际保留且受影响的调用点已迁移；记录外部待办 |
| 应用接续与部署 | 各应用Agent适配、版本回执、匹配部署验收 | 外部应用可并行，未更新不阻塞隔离基座开发，但不接入不支持版本或假报全平台通过 |
| BASE-D可选 | 新工具/多模态/工作流等明确需求 | 另有消费者和验收才实施，不拖住首批 |

每一实现波次后按实际证据refreeze下一波，新增接口差异同步change log和应用包。
测试先直接反例、再受影响消费者、最后打包/原生资格；不把所有应用所有模型做笛卡尔积。
原协议测试可按API变更记录替换，业务保证不得因删除旧测试而丢失。

## 5. 给其他应用Agent的迁移包

基座在本仓现有文档布局下指定canonical路径，并在返回清单中给出实际路径。
可采用 `docs/common/AI-Base-API-Change-Log.md`、
`docs/common/AI-Base-Application-Migration-Guide.md`，
以及 `docs/handoffs/ai-base/<contract-version>/<application>.md`；
这些是建议产物名，若已有同类权威文档就复用，不再复制第二份。

每个应用包必须能脱离本聊天执行，包含：

1. 目标repo、已核对HEAD、修改owner_paths、不可碰的dirty路径。
2. 适用API change IDs、目标contract/service/SDK/profile版本与可安装包位置/hash。
3. 每个旧调用的path/symbol和精确替换代码/JSON、错误与事件处理、新生产调用入口。
4. config/app ID/binding/data映射；迁移前置、备份/检查点、失败续做及回滚限制。
5. 领域接受职责：RCA草稿/评审、SoC patch/signoff、Dashboard报告/host action不能被Run成功代替。
6. 具体测试node、golden输入/输出、拒绝用例、fake服务启动方法、预期结果和实际证据格式。
7. 可安全暂停的位置、激活前置和返回基座的应用回执；不得把文档送达当应用通过。

基座Agent拥有同仓RCA/SoC/Sample/内置Dashboard代码的实现计划；其他repo由对应Agent实施。
Dashboard返回任务映射：旧Chat adapter受API-02/05影响，新W5.APP/INPUT/CLIENT/ACCEPT受
profile/input/run/result影响，W7受服务版本和恢复影响。不得只交新任务SDK而遗漏旧交互消费者。

## 6. 必须返回给用户与Dashboard的结果

| 返回项 | 内容 |
| --- | --- |
| 业务理解与映射 | 本文第0节工作流如何由应用+基座协作实现；逐业务需要对应的合同，不能只返回技术API列表 |
| Review | E1-E9/API-01至06决定、理由、关键风险、被替换设计 |
| 权威入口 | OpenSpec/proposal/design/tasks及current API/reference实际路径 |
| Breaking记录 | canonical change log、旧新示例、版本矩阵、数据升级与弃用/删除计划 |
| Contract pack | OpenAPI/JSON schema、golden vectors、fake backend/consumer、profile与prompt装载说明 |
| 代码与包 | 实际commit/build、SDK包及hash、配置方式，区分源码和可安装产物 |
| 应用handoff | 每应用修改清单和测试入口；未知消费者/外部GUI缺口明确记录 |
| 证据 | 合成、打包、原生、真实backend分别结果；支持/拒绝组合，不把mock当live |
| 下一步 | Dashboard应消费的版本、最小接入步骤、剩余等待及阻断，分开实现工作量与外部等待 |

当前用户要求是review并增强，不是只回答“可行”。接收方应在授权内推进，
但不能跳过合同冻结、伪造应用回执、调用未获准真实模型或从其他仓拷贝secret。

# Integration Leaf Packets

本附录细化tasks.md的W3-W7，不维护第二份勾选/完成状态。
当前跨仓执行与验收handoff统一在[execution-handoff](execution-handoff.md)，
C0准确任务/用例在[sdk-intake-plan](sdk-intake-plan.md)。下方BASE-A章节保留交付证据和背景，
不作为另一份独立可更新的分工或任务状态。
适用规范：[应用接入包](application-integration.md)、[Provider访问](provider-access.md)、
[移植目录](migration-catalog.md)。所有新路径为拟实施目标，不是已存在模块。
执行前仍须完成前波REPLAN及对应验证架构签核，尤其不能跳过W1.R/W2。
2026-11-02新增HTML报告authoring切片的精确边界见
[html-report-authoring](html-report-authoring.md)与[html-report-validation](html-report-validation.md)。
它在已接受摘要上交付模板/人工编辑/复制/确认Git，不自动放行W7采集运行，
不以首个HTML切片关闭完整W4-W7；唯一任务仍为tasks.md。

## 1. 依赖与文件边界

每行的目标目录均相对Dashboard根；旧库只读，source closure的准确blob在该叶任务首步冻结。

| 叶任务 | depends_on | 提供方/消费者与文件owner | 第一反例与退出判据 |
| --- | --- | --- | --- |
| W3.CREDENTIALS | W2.REPLAN | `bug_metrics/app/api/provider_connections.py`、必要secret引用reader；`provider_sync/management/commands/provider_credentials.py`；现有connection helper兼容层 | 错endpoint的settings token不可发出；预览零写、冲突/失败引用不变；ACCESS-01/02/06，所有受影响连接消费者接通才完成 |
| W3.ARCHIVE | W3.CREDENTIALS | `project_management/app/domain/captures.py`、`app/spi/archive.py`、`out/capture_archive.py`、`storage/`；供后续capture和delta使用 | 写失败不提交完整capture，partial原文可追溯；MIG-08/10目标测试，真实Git小样本+新stage身份/配额 |
| W3.GATEWAY | W3.ARCHIVE | `provider_sync/app/api/{access,access_contracts}.py`、`provider_sync/out/{jira_capture,connection}.py`；project capture服务消费 | 错owner/stage/同key不同site拒绝；HSD不走Jira默认；ACCESS-01/04/05/07 |
| W3.CLI | W3.GATEWAY | `provider_sync/management/commands/provider_access.py`、旧sync两命令及受影响metadata/task调用者；所有路径消费同一service | status/item不发网，legacy输出兼容；capture/operation公开能力只属W7，W3入口若存在只能CAPABILITY_UNAVAILABLE且零ID/零写/零上游；ACCESS-03/06 |
| W3.CAPTURE | W3.CLI | `project_management/services/capture.py`、`provider_sync/out/jira_capture.py`；W3.archive是唯一raw写owner | 完整成员/逐部分coverage、一致性漂移、closed更新、拒绝身份fallback；无UI请求线程持锁等完整抓取；合成API闭环 |
| W3.LISTS | W3.CAPTURE | `project_management/out/spreadsheet_source.py`、`app/domain/scope_inputs.py`、专属CLI/未来UI适配 | 公式/超限/错误ID不产生批准范围；Jira key与HSD ID分策略；MIG-05及目标名单测试 |
| W3.DEPENDENCIES | W3.LISTS | `project_management/services/dependency_capture.py`、`app/domain/input_grants.py`、provider port | 未授权主范围外工单零GET；撤权旧摘要不可再输入；依赖变化使相应summary失效；不是复制不存在的F2 |
| W3.ATTACHMENTS | W3.DEPENDENCIES | `project_management/services/attachment_capture.py`、`provider_sync/out/attachment_transport.py`、archive objects | 默认只metadata；流中断/字节超限/重定向/撤权保留partial且不成功；原包无自动解压；不是复制不存在的F3 |
| W3.HSD | W3.ATTACHMENTS | 现有`provider_sync/app/api/hsdes.py`及新HSD capture适配、`project_management`coverage消费者 | saved query/身份变更可见；事实/评论/历史覆盖分别表达；不支持的完整报告拒绝或明示partial，合成consumer与对应正式资料证据 |
| W4.INDEX | W3.REPLAN | `project_management/storage/{source_versions,index,index_acceptance}.py`，复用W3 archive；capture/analysis/publication消费者 | 可重建索引不改Git历史、旧hash不覆写、缺链拒绝；MIG-08/09对应目标集成 |
| W4.DELTA | W4.INDEX | `project_management/app/domain/{delta,delta_contracts,delta_observation}.py`；输入准备/复用判定消费 | A、B、C已采集版本均保留，delta从accepted不是last fetched，缺链/失权拒绝；MIG-01 |
| W4.EVIDENCE | W4.DELTA | `project_management/app/domain/{evidence,summary_ownership}.py`及schemas | JSON pointer/记录ID/site/principal/hash都匹配；否定/建议不成已确认负责人；MIG-02 |
| W4.IMPORT | W4.EVIDENCE | `project_management/history_import/`、历史CLI与查询；read-only donor source closure | 导入目标自包含、源离线可读、重复提交幂等、非英文旧summary保留非权威状态；MIG-11 |
| W5.APP | W4.REPLAN及基座schema/loader contract pack | `ai_bundle/strict-summary/`、独立disabled `interactive-assistant/`、`management/commands/ai_integration.py` | pack缺失CONTRACT_PACK_MISSING且不注册stub；strict manifest不允许工具lane；APP-01/05/07 |
| W5.MIGRATE | W4.REPLAN及基座API change log/目标pack | `ui_web/ai_base_workbench_adapter.py`、现有adapter/host-action测试及W4.REPLAN冻结的实际SDK消费者闭包 | 按API-02/05等实际采纳ID替换旧调用；APP-09：版本失配零模型/发布，历史归属和批准仍受保护；不得混入可选W5.CHAT |
| W5.INPUT | W5.APP | `project_management/app/domain/analysis_input.py`、`analysis_chunks.py`、可选codec | 旧摘要+累计delta+必要证据完整，无隐式历史；分块可重建、不能引用未提供片段；MIG-03/04，APP-02 |
| W5.CLIENT | W5.INPUT及基座Task/Run可执行契约 | `project_management/out/ai_base_tasks.py`、业务attempt映射与budget consumer | 丢POST响应按原clientRunKey查询；unknown不退费、不重新派发；APP-03/04 |
| W5.ACCEPT | W5.CLIENT | `project_management/services/summary_acceptance.py`、W4 accepted CAS、no-work路径 | wrong evidence/owner/stale source/缺requiredParts拒绝；partial不推进完整accepted；no-change零基座调用；APP-04及MIG-02/09 |
| W5.CHAT | W5.APP + W2授权只读查询 | 可选ai_bundle skill/connector/host actions、`ui_web`专属只读handler | APP-06/08；默认disabled；无权报告、过期ACK、模型写操作拒绝；不阻塞未启用Chat的首版 |
| W6.RENDER | W5.REPLAN | `project_management/reporting/`、HTML模板registry/renderer、Markdown/Excel | HTML首选；模板零模型调用，安全literal/链接和有界输出；MIG-12，HTML精确切片在同目录附录 |
| W6.PUBLISH | W6.RENDER | report draft/publication服务、单一archive writer、`ui_web`编辑/复制/下载 | 草稿不推进发布，人工确认才提交；原稿/编辑/最终字节保留，失败不前进；全部在途行动保留 |
| W7.RUN | W6.REPLAN | `project_management/services/operations.py`、owned worker适配、provider_access capture/operation、项目run CLI | 只维护一个业务operation authority，不另加AI Base第二费用真相；原deadline/cancel/unknown、正常收尾；MIG-14 |
| W7.DEPLOY | W7.RUN | 新安装路径/owner/health/移植元数据、Dashboard lifecycle adapter | old keeper不热替换、不双owner；新用户指定数据根与Git；必要冷恢复单独现场资格；MIG-15 |
| W7.PROTECTION | W7.DEPLOY | `project_management`backup/retention/remote/schedule接口与兼容配置 | 历史无损、实际I/O失败与占用配额，数据remote不继承代码origin；正式激活独立；MIG-16/17 |

W3.R依赖W3.HSD及前序全部必需叶任务；W4.R依赖W4.IMPORT；W5.R依赖W5.ACCEPT与W5.MIGRATE；
W6.R依赖W6.PUBLISH；CLOSE.R依赖W7.PROTECTION及原各波review/refreeze。
W5.CHAT若disabled，记录未启用原因而非勾选已实现；一旦请求启用必须独立review。
W6.HTML.*是用户批准的窄authoring lane，依赖W5.JOIN及既有catalog/capture/archive，
不等待所有未来W3功能；完整跨天差分仍依赖W4.DELTA/EVIDENCE，公开运行仍依赖W7.RUN。

## 2. 通用移植步骤

对每个MIG引用的叶任务按以下顺序执行：

1. 读取固定源commit对应的准确文件/资源/直接依赖与代表测试，生成该叶任务source->target映射。
2. 在新命名空间先写保留语义反例：使用两个任意项目、Jira/HSD合成输入及不同身份。
3. 运行目标测试确认RED，再移植最小完整算法/依赖集；不是全部导入旧包让测试“找到模块”。
4. 调整provider特有字段/URL/ID、项目/阶段映射、schema loader、Python依赖和权限入口。
5. 跑目标测试GREEN，接真实公共API/CLI消费者，再跑受影响旧Dashboard消费者。
6. 涉及历史/预算/网络时补真实小型存储/合成transport边界，稳定后才原生/实模。
7. 记录本轮来源、实际测试、未证明部分；需要新shared能力时先更新本change及基座对应合同。

证据优先复用的是未变的语义与样例，不把旧库测试数字直接计入新库已通过。
没有source closure、明确消费者或refreeze结果，就不能把叶任务写成“直接copy即可完成”。

## 3. 验证命令与层级

以下是叶任务文件创建后的命令模板，**当前不应执行缺失模块的命令或记作已通过**：

```powershell
$python = Join-Path (Get-Location) '.venv/Scripts/python.exe'
& $python -m pytest provider_sync/tests/test_provider_connections.py provider_sync/tests/test_provider_credentials_adoption.py -q
& $python -m pytest provider_sync/tests/test_provider_access_command.py provider_sync/tests/test_provider_access_consumers.py -q
& $python -m pytest project_management/tests/test_capture_archive.py project_management/tests/test_cumulative_delta.py -q
& $python -m pytest project_management/tests/ai_contracts -q
& $python -m pytest project_management/tests/test_report_publication.py -q
```

具体test node通过前波REPLAN冻结，与application-integration/provider-access测试表保持一致。
当前实际可用检查仍是W1 tests、OpenSpec/链接/大小/空白；不为本轮补充文档跑产品或真实模型。
Tier1直接反例，Tier2受影响模块/消费者，Tier3规格/安装资源，Tier4必要原生/浏览器/实模资格。
不能用collect-only/全部skip/空选择关门禁，也不为一个字段修复重跑所有项目全套UI。

## 4. 传播与消费者补充

| 新authority | Producer | 具体consumers | 反例/非目标 |
| --- | --- | --- | --- |
| PM-CONNECTION | provider_connections + adoption | provider_access、旧sync两命令、profile connection test、metadata adapter、受影响tasks Jira repo | ACCESS-01/02/06；不默认改未涉及的Azure/PR身份；逐调用者记录迁移状态 |
| PM-AI-PACK | ai_bundle manifest/prompt/schema | ai_integration doctor、AI Base loader、Task SDK、summary validator、可选Chat工具 | APP-01..08按启用范围；不注册开发skills |
| PM-AI-VERSION | 基座版本化合同/SDK及应用注册映射 | W5.MIGRATE现有workbench adapter/host actions、W5.CLIENT、ai_integration doctor | APP-09；不支持组合拒绝副作用，已有消费者迁移不归可选新助手 |
| PM-PORT | pinned source/target closure | 新domain/storage/service、目标tests、安装资源和当前手册 | 所有MIG有消费者/拒绝边界；不移旧运行状态/secret |
| PM-CAPTURE | provider gateway + archive | delta/index、metrics投影、report source refs、partial-health | 失权/缺页不完整；旧图表cache不成完整source；无scope外隐式扩展 |

Consumer universe的新增落点：公共API/CLI/内部服务/缓存身份/存储schema/审计/导出/安装资源/
测试fixtures/操作文档全部适用；后台capture控制只在W7，新增UI控件在W2/W6/可选Chat；
已有workbench协议消费者升级在W5.MIGRATE，不是新增UI功能。
正式调度与异机备份只保留能力和触发条件，未激活不等于无测试义务。

## 5. 本次完成的只是就绪文档

本轮补齐未来叶任务并不重新关闭W1评审、进行secret采用、注册skill或迁移模块。

## API Evolution Intake

2026-11-01 API-EVO-01取代AI Base接入的默认向后兼容约束，见[演进记录](ai-api-evolution.md)。
W4.REPLAN先核对基座目标版本、API change IDs、实际Dashboard调用闭包和替代测试；
关键目标签名未冻结时不得派发对应W5叶任务。W5.MIGRATE与新任务适配可在文件边界独立时并行。
W5.R要求受影响已有消费者与新任务均完成目标合同验证；未受影响必须以明确census结果说明，
不要求制造无必要的代码变化。W5.REPLAN再检查应用回执和后续发布/运行依赖。
通用API的精确规格与基座任务状态不在本文件重复维护。
下一步仍是tasks当前执行入口；本附录不能被当作一次性并行实施所有模块的授权。

## BASE-A Delivery And Parallel Work

2026-11-01基座交付BASE-A.1/.2/.R后，**双方可以立即并行开展非live开发，不再等待BASE-B整体完成**。
本节是既有DAG的跨仓依赖视图，不另建任务状态，不改变W1至W7的应用内部前置。
基座的BASE-A完成不能直接勾选Dashboard的W5或运行资格。

### 已核验的交付

| 产物 | 位置/固定版本 | 本方本轮核验 |
| --- | --- | --- |
| Contract pack | `D:/AIGC/Report_creater_agent/packages/task-run-contract/manifest.json`；0.1.0a1 | 19个文件hash与manifest一致；FZ-01设计版本匹配；qualification=synthetic_only |
| Manifest SHA-256 | `08f081745ce956df13474de15063ec66849aef7a0454b3f0bd8fb4c56ee9bbca` | 按原bytes计算，不能只依赖尚未提交的仓库HEAD |
| Python wheel | `D:/AIGC/Report_creater_agent/.tmp-validation/task-run-base-a/wheels/ai_base_application_sdk-0.1.0a1-py3-none-any.whl` | zip CRC、包内两份Python源码与当前SDK源码字节一致 |
| Wheel SHA-256 | `de223668e49dc9ed145f6ec3bc5084d453a5611cee5f4f41987dd70a4474179f` | 与基座回执一致；Requires-Python>=3.12，依赖httpx>=0.28,<1 |
| 当前操作 | `TaskRunClient.submit(request)`、`get_by_client_key(scope_key, client_run_key)`、`get_result(scope_key, run_id)` | 已读实际公开client；只消费task-run/1 HTTP，不导入服务端模型/runtime |
| 不具备资格 | provider执行、cancel、unknown reconciliation、原生崩溃恢复、physical GC | manifest明确notQualified；不能用BASE-A替代BASE-B或正式运行 |

基座记录的46项专项、515项非live回归和隔离安装结果由其tasks持有；本方没有重复执行。
首次接收时在Dashboard主环境因`httpx`缺失而停止，未发请求。
后续编码准备已在`.tmp/task-run-c0/venv`独立安装SDK/httpx并完成有界MockTransport探针；
从installed wheel调用submit/by-key/result及typed timeout通过，未导入基座源码或发起真实连接。
下一动作是按已审C0计划编写正式12例验证脚本，不再重复环境准备。
准备探针不等于C0.R、产品接受或BASE-B资格；主环境仍未修改。

### 两个仓库的写入边界

准确owner与数据交接见execution-handoff第1/3节；两个仓库分别维护自己的OpenSpec。
基座推进BASE-B局部计划/实施，Dashboard推进C0和原业务链；双方不等待对方所有模块完成。

双方不同时改对方仓库，也不复制另一方的worker、预算或Run状态机。
Dashboard只做业务attempt/accepted水位/发布；基座只拥有AI执行事实。
基座freeze.json的原executionScope仅为BASE-A；本节BASE-B是建议用户转交的新阶段任务，
不冒称对方已经启动或自动继承未授予的权限。正式执行仍按各仓任务及用户指令推进。
本次不扩大到重写RCA/SoC；实际受共享接口改动影响的消费者仍由基座按既有清单处理。
双方可以同一时间编码；每个仓库内部仍是一名协调写入者，独立review按风险和真实差异选择。

### 汇合点

依赖图、逐层验证和J01-J06联合用例统一在execution-handoff第4/6节。
原C0-C3汇合含义不取消；C0现细化为可执行开发资格节点，后续联合/真实验收须两侧对应能力到货。

BASE-A的`outputSchemaSha256`是runtime规范化schema hash；
`sourceFixtureHashes`是原应用文件字节hash。应用要按manifest/profile校验对应字段，不能混用。
提交前持久attempt及exactSubmitPayload属于Dashboard；新版本不自动切换runStoreId或重置client key。

### 当前要处理的本地方向

W1的实现/专项已存在，但正式W1.R仍待完成；本轮全工作树大小门禁仍报原两文件
`ui_web/tests/bug_trend_scope_config_test_support.py` 650>600、
`ui_web/tests/test_bug_trend_scope_config_views.py` 624>600。
这是本仓其他改动的既存卫生问题，不是AI Base接入阻断。下一步明确其owner与门禁处理，
按既定规则完成W1有边界评审；不修改他人dirty文件、不静默豁免、不把全库说成绿色。
基座BASE-B和独立SDK进件不需要等待该应用评审；W2等业务波次仍须自己的前置通过。

### 固定交付与反馈节奏

目前基座改动尚未提交，wheel在临时验证目录。先以此处hash固定消费版本；
请基座按本仓授权提供scoped commit或可重建的固定快照及稳定产物位置。
这不是重新审批FZ-01的前置，也不要求等待remote push才能开始开发。
不要覆盖已交付0.1.0a1的bytes；BASE-B交付新包版本/manifest/资格声明并附实际API差异。
只处理真实差异，不为新增能力再次评审整个task-run/1；每次交付返回节点、产物hash、测试范围和限制。
不抢占对方服务/端口，不迁移真实数据，不因“并行”取得额外live授权。

### 可转交基座Agent

使用execution-handoff第8节；不再复制一份可漂移的任务委托。

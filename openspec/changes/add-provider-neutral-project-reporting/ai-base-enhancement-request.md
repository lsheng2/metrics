# AI Base / SDK 公共能力增强请求

> 2026-11-11起已被[MDB-2](../embed-ai-base-runtime-in-process/proposal.md)取代：本文件仅为历史证据，不定义剩余工作。

日期：2026-11-01。状态：首批task-run/1边界已获我方设计冻结确认，扩展项仍分波，未实施。
接收方：`D:/AIGC/Report_creater_agent` 的基座维护者。
本文件是跨仓请求，不是Dashboard仓库中的第二份基座canonical规格或基座任务清单。
应用侧交付见[应用接入包](application-integration.md)，状态仍在[tasks](tasks.md)。
最新用户决定见[API演进与迁移记录](ai-api-evolution.md)：允许协调式breaking changes，
取代此前默认保留旧API的约束。独立交接入口为[基座review与增强handoff](ai-base-review-handoff.md)。
基座独立评审及CF修订已返回，当前以[应用方回复第10节](ai-base-review-response.md)的FZ-01
绑定最终设计和schema；请基座登记冻结后推进BASE-A，不再重复首批边界审批。
后续BASE-A已登记并交付synthetic-only pack/SDK，当前执行状态及BASE-B/应用并行分工
以[integration-execution](integration-execution.md)的交付章节为准，不重复本文件早期催办。

## 1. 结论与中立原则

**需要独立增强；建议在AI Base内增加可供多应用使用的Task/Run能力并升级SDK，而不是新增Dashboard专用后端。**
独立增强指独立的规格、模块、版本与验收，不要求另建一个基座、仓库、常驻服务或消息平台。
优先复用有价值的FastAPI、runtime、backend、鉴权和存储，在原仓建立有边界的OpenSpec change。
现有模块拆分和API不是不可改变的前提；SDK和同仓/外部应用都可以按目标合同同步调整。

公共能力进入基座应满足：

1. 接口使用通用概念：application、execution scope、task profile、input、run、result、artifact、policy。
2. 不要求应用创建Jira工单、Project/Stage、ReportTask或SoC项目才能调用一次AI任务。
3. 至少用两种不同对象/schema的消费者验证，例如JSON文档提取与简报生成，不只是改两个项目名字。
4. 基座负责执行与通用策略，应用负责领域真相、业务权限和结果接受。
5. 任何应用都可以保留自己的UI、数据库、业务编排和发布节奏，不强迫全部迁入React/Tauri或同库。
6. 声明“不支持”是合法的能力结果；不能为适配某应用偷偷降低权限或强制所有backend宣称同等能力。

早期开发采用目标架构优先，而非旧调用零修改。旧独立部署可保留，新版本可明确拒绝旧协议；
不需要让所有应用使用全部Run功能，但受公共API变更影响的应用必须列入迁移包。
对需要“后台计算、断线查询、完整输入、结构化结果”的应用，下面的公共增强才是接入前提。

## 2. 当前实现与真正新增项

上一轮只读核验AI Base HEAD为 `2332d549ab69a7e927865acd0e3db2a19295c609`，当时工作树干净。
这是用户指定检出的快照，不代表其他worktree或remote。没有运行新模型/服务/产品测试。
graph索引过旧且coverage不可用，以下事实由当前文件读取核验：

| 能力 | 当前代码证据 | 本次建议 |
| --- | --- | --- |
| 应用Chat SDK | 私有0.1.0 TS包已有绑定、context、消息、host action | 重整为同一公共SDK；可改变旧方法，提供版本化差异与消费者迁移 |
| 应用注册、身份与workspace/session映射 | 现有app-chat服务及注册规格 | 扩展到Run/Input/Artifact，不强制后台任务依赖Chat session |
| backend统一入口 | AgentRuntimeService已有chat/stream与backend registry | 增加task执行port，共用底层transport/模型路由 |
| 出站CLI工具 | extension startup装配CLI registry | 不把它误当入站durable Run/job；按需要扩展lane，不一次实现所有类型 |
| 对外Run CLI/API | Run Interface是Draft，实际CLI只有serve/probe | review后收敛为单一Run合同；可替换原草案及路径，不并存私有协议 |
| 完整输入运输 | 当前Chat message上限12k字符，文件grounding使用3源/12k字符预览 | 新Task采用显式输入及完整性模式，不全局取消Chat限制 |
| 错误与SDK | TS wrapper在非成功HTTP状态主要抛路径/状态文本 | 统一typed error、run关联、重试语义，版本化替换旧异常处理 |

这些差异表明需要实质新增能力，但不支持“所有基础设施推倒重写”的结论。

## 3. 结构与责任边界

```text
Application-owned UI / workflow / source data
              |
       Application SDK / HTTP / CLI
              |
AI Base public application facade
  app authentication + scope authorization + capabilities
              |
      +-------+-------------------------+
      |                                 |
 Chat facade                       Task facade
 session/context/approval           explicit input + profile revision
      |                                 |
      |                      Run coordinator + durable stores
      |                                 |
      +---- shared runtime / policy / backend adapters
                                        |
                                 approved model service
                                        |
                            result + execution receipt
                                        |
Application domain validation -> acceptance / publishing
```

运行中引用的输入/profile/result是固定版本。Chat/Task共用下层，不意味着共用隐式历史或相同工具权限。
图示为职责边界，不冻结旧方法或要求所有Chat都经过重型持久Run；具体公共execution core由基座review。
平台返回run succeeded不等于报告发布、工单结案、patch应用或图表发布成功。
基座正式合同还应明确delegated actor/audit subject的归属：可保留应用提供的非secret审计关联，
但未经独立验证的actor字符串只作来源声明，不成为授权凭证；不能从有效app token推断最终用户权限。

| 事实或操作 | 基座公共责任 | 应用责任 |
| --- | --- | --- |
| 身份/授权 | 认证sourceAppId，检查注册scope与对象归属，每个run/input/artifact操作重验 | 验证实际用户，确认其可访问源数据和业务操作；不把一个应用token当所有用户通行证 |
| Prompt/schema | 支持注册、版本、allowlist、校验与执行策略 | 提供领域prompt/schema及其版本，定义内容质量/证据要求 |
| 输入来源 | 有界保存、hash、编译manifest、授权与DLP策略 | 获取获准原文，决定所需内容、delta、coverage与必要背景 |
| 运行生命周期 | 受理/派发/取消/结果查询/崩溃恢复及不确定性 | 管理整轮业务操作，将平台run关联到本地attempt，决定何时接受结果 |
| 资源/费用 | 平台并发、队列、实际请求、usage及未知费用账 | 业务预算、项目配额、按回执幂等记账，不与平台账相加为两次费用 |
| 原文历史/发布 | 运行结果按平台留存政策保存，返回可下载对象 | 原文Git或业务DB、合法留存、业务CAS、报告/图表/patch发布及备份 |
| 外部工具 | 通用受控执行、审批协议与注册机制 | Jira/HSD等adapter、凭据引用、业务授权及tool参数限制 |

## 4. 公共增强目录

E编号为建议能力标识，不是在Dashboard中新增可勾选的基座任务。
“首批必需”针对任务型执行等级；公共API变化涉及哪些旧应用，就明确哪些应用需要迁移。

| ID / 优先级 | 基座需增强的部分 | 公共接口/模块责任 | 多应用价值与最低验收 |
| --- | --- | --- | --- |
| E1 首批必需 | Task与Chat解耦 | `TaskExecutionPort`；输入为profile revision+显式材料，输出backend-neutral结果 | 无session也能处理文档/报告任务；不伪造ChatMessage或加载Chat历史 |
| E2 首批必需 | 输入manifest与结构化结果 | InputRef、编译证明、OutputSchemaRef、Result/ArtifactRef | 提取、分类、简报均能验证输入/输出；超限明确拒绝，require_all不得截断 |
| E3 首批必需 | 持久Run与可恢复查询 | submit/get/by-client-key/events/result/cancel，共用RunStore | CLI/GUI断线后取回同一结果；同key冲突不重复派发；崩溃未知不盲重发 |
| E4 首批必需 | 版本化执行配置与能力 | ExecutionProfile/TaskProfile registry、BackendCapabilities、effective policy receipt | 同一基座支持不同schema/语言/模型/tool策略；不支持的组合在派发前拒绝 |
| E5 扩展现有基础，首批必需 | 对象级隔离、凭据与资源策略 | 复用AppRequestAuthenticator，扩run/input/artifact授权和配额 | 两应用互相不能取对象；查询不暴露secret；共享服务不被普通consumer取消/停止 |
| E6 HTTP/Python先行 | SDK/CLI与版本协商 | 独立Python client、typed errors、OpenAPI/schema pack；TS按真实消费者、CLI后置 | 先证明安装包与fake消费；以后其他语言共用golden；SDK不依赖服务端app、不直调provider |
| E7 与首批一起交付 | 通用运行诊断与验收包 | request/run/correlation、usage certainty、capability evidence、合成backend | 模型失败、格式错误、调用未开始/未知可区分；本地fake即可验证接入 |
| E8 按需增强 | 应用扩展装载与能力分区 | 不同manifest/lane的schema与实际registry | 可选skill/connector/CLI只装配到获准agent；不污染严格任务或其他应用 |
| E9 后续 | 更复杂工具任务/交互等待/多模态/工作流 | 在同一Run体系增加明确capability和adapter | 第二种真实需求出现时再扩，不为当前接入先造全能DAG引擎或插件市场 |

E8若仅用于装载TaskProfile/prompt/schema，所需最小loader随E4交付；
这里的“按需”只指工具、MCP、skill等额外lane，并非允许没有profile装载路径。

### 4.1 最小接口，不再另造一套状态协议

以现有Run Interface草案为review输入，完善以下责任；精确操作名/字段/大小/状态在基座OpenSpec冻结：

- `applications/capabilities`：已注册应用可用的contract版本、task profiles、输入形式和backend能力。
- 输入seal：首批有界inline在submit原子固定；独立`inputs.create/seal`运输API按实际大对象需求后置。
- `runs.submit`：应用身份、scope key、稳定clientRunKey、profile revision、inputs、output contract、期限和预算上界。
- `runs.get/byClientKey/events/result`：认证只读与有界分页，断线不隐式取消。
- `runs.cancel`：持久取消意图；远端provider是否停止/仍未知独立报告。
- result bytes/hash：首批可通过授权result返回小型结果；通用`artifacts.read`按需后置，不接受任意路径/URL。

新增Task不要求Chat workspace/session；scope是应用注册的opaque key。
基座提供精确或结构化segment匹配策略，不理解其中“stage”“release”或“ip”是什么意思。
普通输入不包含token/原生backend对象，公开错误不泄露原provider异常。

### 4.2 持久化、幂等与未知状态

请求唯一键由已认证app identity与clientRunKey共同限定；同key/同内容返回原run，
同key不同内容冲突。记录输入/profile快照、deadline、attempt、平台reservation和事件。
受理必须持久化成功才回复accepted，worker通过唯一claim/fence派发。

跨网络不能保证provider exactly-once。可能已派发但无结果时，不自动重发；
provider不支持查询/幂等/取消时公开unsupported/unknown，应用不能把unknown费用写成0。
本地worker slot、provider未知调用债、输入/result存储pins分别核算，
防止远端未知永久占本地worker，或本地退出就清掉真实费用/唯一材料。

cancel/result/deadline通过单一CAS裁决；终态不因晚到结果复活。生命周期状态与usage补记分离。
日志/事件可分页和限额，但幂等键回收必须保留tombstone或到期拒绝规则，不能回收后重跑旧请求。
执行回执只描述平台观察到的事实，hash不证明提供方可信或内容语义正确。

## 5. 避免把本应用偏好变成全局规定

| 当前应用的要求 | 中立的基座能力 | 不应做的设计 |
| --- | --- | --- |
| 日报只读、无工具 | 每profile可配置并验证`toolPolicy=none`；其他profile可受控工具 | 全局禁止所有应用tools，或只用prompt劝模型不要调用 |
| 英文权威报告 | 任务语言作为profile/应用约束，原文保持Unicode | 强制RCA/SoC/其他应用全部输出英文 |
| 完整评论及累计delta | `completeness=require_all`和输入manifest，应用提供材料 | 基座理解Jira comment ID或负责每日delta基线 |
| 不使用旧Chat历史 | `contextMode=explicit_only`；检索/对话另选模式且可审计 | 全局移除RAG、memory或会话功能 |
| 首批每run一次provider尝试 | 可声明max attempts且统计全部尝试；严格模式拒绝隐式retry | 所有应用永不重试，或把底层多次请求算一次 |
| Git不可变归档 | 平台Run对象完整性、应用ACK与留存协商 | 强迫基座每个run建Git仓库或替代所有应用的历史DB |
| 可确定的本机运行边界 | 能力描述与合格环境、共享/专属部署策略 | 必须复制chiplet keeper、必须Windows、或只看PID存活判断归属 |
| Jira/HSD访问统一CLI | 通用受控connector/CLI注册与secret ref机制 | 基座内置本项目范围或直接持有并公开应用PAT |
| 手动触发、桌面Chrome优先 | API不依赖特定UI；调度作为外部调用者 | 禁止其他应用调度/手机UI，或强制所有应用换React |

检索模式可以使用节选，但必须明确标注选择/截断及来源版本；不能在require_all请求中静默切换到检索。
平台强制DLP/权限策略优先于应用需求；发生材料变换需回执并由应用按profile接受或拒绝，
不能为保持原文而绕过秘密保护。

### 5.1 现有应用的实际影响

2026-11-01追加核对以下消费者的当前源码；这是有界影响分析，不是所有应用的完整运行验收。
**既要评估影响，也允许改变API后让应用同步迁移。** 下表保留业务保证，不冻结旧调用形式。
具体破坏性差异进入API演进记录；没有应用迁移证据，不能宣称新版本支持它。

| 消费者及当前调用 | 采用新能力的价值 | 应保持的业务保证 | 允许的重构及迁移风险 |
| --- | --- | --- | --- |
| RCA草稿：`RCAWorkflowPage.handleGenerateDraft`调用Chat并要求返回`draftId`，再查关联`reportTaskId` | 长报告生成可独立查询、恢复，并验证输入完整性 | 草稿/ReportTask关联、修订与导出可追踪，业务批准独立 | 可拆出计算和业务接受API、修改UI调用；重复取结果不能重复建草稿，Run成功不能自动finalize |
| RCA评审：`ReviewAgentService.run_review`直接调用`run_chat_turn`，不是TS SDK入口 | 可按schema校验评审结果并留存运行来源 | 评审关联/verdict和实际来源可追踪；不能漏测服务端直接消费者 | 当前有截断和mock fallback；允许移除并调整响应，但新合同必须准确表达provenance，不能伪称require_all或真实成功 |
| RCA交互及Sample：session激活、stream、sources/drafts、按profile启用的skills/RAG | 可增加一次性任务并简化公共SDK | 交互上下文/审批正确、Sample领域中立、语言策略明确 | 可以更新Chat/stream协议与客户端；不能把strict Task的无历史、无工具、英文要求变成全部应用策略 |
| SoC：`PipelineOrchestrator`编排四阶段，`trigger_analyze`等待结果并发`analysis_complete`回调 | 将来让需要模型的阶段复用执行、结果和usage契约 | 阶段结果、失败、patch/signoff关联准确，GUI能跟踪完成 | 可以改为异步Run、事件或轮询；定义新状态/返回与GUI迁移包，不要求保留旧同步接口 |
| 外部Dashboard：Django adapter解析app-chat binding、同步context并承接host actions | 报告任务采用Task，问答/图表仍有明确交互模式 | 历史归属、context绑定、浏览器凭据隐藏及host-action批准 | 身份/binding/SDK可重新统一，须映射迁移；Run成功不是图表/报告发布批准 |

SoC有一项需要收窄此前“共用AI runtime”的表述：本次读取的ExtractionAgent明确为Phase 2 stub，
按RTL AST/占位逻辑产生结果，报告0 token；这条`run`未调用模型。
不能据此说所有SoC能力都是stub，也不能把未来Task接入称为已有真实LLM流水线的无缝替换。
SoC外部GUI仓库本轮未核验，跨仓回调兼容仍为counterpart-required。
RCA现有mock/truncation是观察到的兼容差异，不是建议把它们推广为平台默认或正式质量保证。

### 5.2 未采用新API的应用也可能受影响

先区分部署：同代码、不同profile/数据目录/进程，不等于所有应用共享一个server。
前者主要受包版本、配置/迁移及主机或共同模型网关资源影响；后者还受同一队列、连接池、
数据库锁和worker调度影响。部署清单须记录实际共享关系，不能仅凭profile隔离测试推出运行资源隔离。

| 共享变化 | 潜在影响，不代表已观察到故障 | 基座设计/发布要求 |
| --- | --- | --- |
| 启动装配与依赖 | 轻量Sample/Chat被迫初始化不需要的后台活动 | 按能力装配；统一核心依赖可改变并记录安装迁移，可选能力禁用不启动其worker |
| runtime/model路由/默认策略 | prompt、语言、tools、RAG、重试、token上限或stream行为漂移 | 可显式改变并版本化；profile旧新映射、权限和输入provenance均须验证 |
| 并发与平台额度 | 批量摘要占满worker或模型额度，交互请求排队变长 | 有界队列和可配置的app/lane准入、公平性；共享网关额度单列，不能声称本地隔离消除了远端争用 |
| DB/schema/归档和GC | 新写入加重锁等待，回收误删其他应用或仍在使用的结果 | 命名空间/对象授权独立；明确migration、pins及留存所有者，不共用应用业务表或改写旧历史 |
| SDK构建和异常 | 新exports/错误类型使旧调用失配 | 可以破坏旧签名；发布新包与逐调用点迁移，测试目标版本，拒绝不支持组合 |
| 鉴权与能力发现 | 新对象漏授权或失配客户端继续副作用 | 每对象检查app/scope；版本不支持则拒绝，不能凭Run访问权限推导GUI发布/业务写权限 |
| 升级、取消与回滚 | 升级中断旧stream，重派不确定任务，旧版误读新版持久记录 | 有界drain/停止准入、在途处理及兼容读写规则；无法安全降级时禁用新lane而非盲目回滚DB或重发 |

以上控制优先复用现有装配、鉴权、配置和部署机制，不要求为此新增微服务或通用调度平台。
性能门槛用同配置的基线与代表性并发负载校准，不预设无依据的零开销或固定延迟数字。

## 6. 保持通用性的验证组合

基座首批使用Sample/fake、一个文档提取任务、一个简报任务，schema与领域对象不同。
Dashboard/SoC/RCA按影响选择保留合同回归或新版迁移测试，不要求所有功能先迁成Task。
新strict Task不能用旧Chat绿色冒充；有意改变的API更新断言并记录映射，不把所有旧断言继续绿色当目标。

| 验收 | 必须观察的结果 |
| --- | --- |
| 不同应用但相同clientRunKey | namespace隔离；不能碰撞、读取、取消对方run/input/artifact |
| 长文本和多个输入 | require_all完整可重建或明确拒绝；检索模式的partial标识保留 |
| task profile变更 | 新revision不影响已接受run；运行时撤权阻止后续访问/派发，不覆写旧记录 |
| 回复丢失与worker重启 | 同key查询原结果；可能已派发保持unknown，不增加隐式provider调用 |
| 取消/成功/到期竞争 | 唯一终态裁决；观察中止不等远端停止；usage未知不显示0 |
| 结构化输出错误 | 未通过schema不标task成功，不自动付费“修复JSON”除非明确策略及额度许可 |
| 只读角色与发布动作 | API/token有效也不能代替应用业务批准；没有runtime capability则工具不暴露 |
| Python/TS客户端及CLI | 共用schema/error/golden vectors；同逻辑字段同含义，CLI等待超时仍返回run关联 |
| 服务端版本升级 | 目标Chat/host action调用与迁移记录一致；未支持旧版本或必需能力明确拒绝 |
| 源码到分发产物 | SDK从构建包导入、prompt/schema引用在安装后解析，不以源码目录偶然存在为通过 |

格式测试不调用真实模型。原生重启用专属测试服务，不重启用户整机；
少量真实backend资格另授权，不能因“通用”扩成所有模型/所有应用的笛卡尔积。

### 6.1 现有消费者回归与发布门槛

以下文件是已定位的复用起点，**本轮未运行**；并非表中新增情形都已被这些测试覆盖。
基座维护者在自己的OpenSpec中冻结具体test node、需新增反例、服务/SDK版本和执行结果。
基座负责公共合同和迁移交付；应用负责自身适配与领域接受；GUI等另一仓缺席时不得宣称跨仓通过。

| 验证层 / owner | 复用测试起点 | 必须证明的边界或新增反例 |
| --- | --- | --- |
| 静态/装配 / 基座 | `test_import_boundaries.py`、`test_profile_manifest_consistency.py` | runtime不反向依赖业务app；目标profile/依赖可装配，禁用能力不启动无关worker |
| Chat/runtime契约 / 基座 | `test_chat_api.py`、`test_agent_backend_contracts.py`、`test_rag_chat_augmentation.py` | 新stream/历史/工具合同及迁移断言；strict Task无隐式历史/工具，不把mock或截断算严格成功 |
| RCA业务 / RCA维护者 | `test_draft_runtime_api.py`、`test_rca_workflow_api.py`、`test_rca_v03_workflow.py` | 草稿->ReportTask->review->finalize/export关联；结果重复读取不重复建业务对象；fallback/truncation显式可见 |
| Sample隔离 / 基座 | `test_draft_runtime_api.py`的Sample profile及共享base root隔离场景 | 不加载RCA专属路由/服务，旧数据可读；新Run/Input/Artifact隔离须另加双app反例 |
| SoC契约 / SoC与GUI维护者 | `test_soc_routes.py`及GUI counterpart测试 | 新响应/事件与GUI匹配、失败不发成功、项目地址和patch/signoff正确；fake不算真实模型资格 |
| Dashboard迁移 / 双仓维护者 | 基座`test_app_chat_bindings.py`；Dashboard `test_ai_base_workbench_adapter.py`、`test_workbench_ai_host_actions.py` | binding/context迁移后历史归属和批准正确；strict Task不能经Chat绕过校验，浏览器无凭据 |
| SDK分发 / 基座 | `test_application_sdk_contract.py`及新增TS/Python安装包consumer fixture | 新版Chat/Task客户端构建；两种Task schema同contract pack；未支持旧版本明确拒绝 |
| 运行资源/升级 / 基座 | 新增专属服务fake workload及migration fixture | Task拥塞时Chat按校准策略服务；禁用Task无后台活动；有界drain、未知派发不重跑、旧数据保留及回滚边界 |

成本控制：先跑静态/合成契约，再跑受影响应用业务测试；稳定候选才进行专属服务混合负载/
升级验证。改动公共runtime/auth/schema会扩大消费者集合，但文档或应用局部变更不触发全平台重验。
可先在隔离候选直接实现新合同并移除旧入口，再让各应用按migration pack更新；
是否保留短期兼容层由实际部署决定，不默认新增兼容负担。
不双发真实模型做shadow；基座开发不等待全部外部应用，但失配应用不得连接共享新服务继续执行。
发布清单分别给出目标合同资格、保留功能回归、应用迁移、外部GUI资格，不能合并成一个“全绿”。

## 7. 独立增强的交付分组

| 交付组 | 首批范围 | 与应用的接续条件 |
| --- | --- | --- |
| BASE-A 契约与fake纵向闭环 | E1-E5的最小语义、schema、fake backend、输入->Run->Result、SDK最小客户端 | 提供已通过合成验证的contract pack；应用可并行适配，但不得真实调用 |
| BASE-B 可靠执行等级 | E3/E5/E7故障/预算/权限、一个实际backend的E4能力证明、固定服务构建 | 应用验证自身input/candidate边界后才允许切换真实后端 |
| BASE-C SDK与迁移发布 | E6实际需要的客户端和迁移；TS按breaking闭包、CLI后置；API change log与应用回执 | 可安装包、版本范围、限制和实际consumer测试，不强迫无影响业务Task化 |
| BASE-D 可选扩展 | E8额外lane、E9新需求 | 独立profile/能力门禁，不阻塞不使用这些功能的应用 |

分组是同一基座能力的交付切片，不要求四个独立服务。
最小HTTP+Python接入不必等CLI、所有widgets或所有现有应用迁移完；
但要使用哪个能力，就必须具备它对应的版本和验证，不以分阶段为由假报完整性。
服务/SDK升级应使用既有配置、发布和迁移工具，优先SQLite/local worker，不默认引入Redis/Celery/Kafka。

本次不追加一份未经测量的总工时。已有粗估仅作背景；基座维护者先核对实现差异，
把BASE-A/B/C实际缺口、可复用项、应用适配与等待分别估算，避免两侧重复计算同一基础设施。

## 8. 给基座维护者的交接入口

提示词只维护在[AI Base review与增强handoff](ai-base-review-handoff.md)，取代本节旧版兼容优先提示。
先按[API-EVO-01](ai-api-evolution.md)review，允许重整API和同仓应用，再交付版本化合同与外部应用迁移包。
Dashboard维护者只记录依赖和consumer验收；基座OpenSpec维护自己的实施清单。

## 9. 接口权威与证据入口

基座采纳后，其OpenSpec和 `docs/common` 成为generic协议权威，本文仅作需求来源/讨论记录。
旧项目中的详细[Run契约建议](../../../../chiplet_programmgr/docs/research/2026-11-01-ai-base-run-contract.md)
是可参考的严格任务设计输入，不是要求所有应用遵守的既成API，尤其不固定状态拼写/内部表结构。
跨仓差异应回传contract版本、API change log与逐应用迁移包，再更新adapter，不用临时shim伪装新能力。

本次读取的基座文件：

- [Run Interface](../../../../Report_creater_agent/docs/common/AI-Base-Run-Interface-Spec.md)、
  [实际CLI](../../../../Report_creater_agent/services/app-service/app/cli.py)。
- [SDK包](../../../../Report_creater_agent/packages/application-sdk/package.json)、
  [SDK入口](../../../../Report_creater_agent/packages/application-sdk/src/index.ts)。
- [Runtime](../../../../Report_creater_agent/services/app-service/template_runtime/services/agent_runtime.py)、
  [路由装配](../../../../Report_creater_agent/services/app-service/app/main.py)。
- [Chat输入](../../../../Report_creater_agent/services/app-service/app/services/chat_source_context.py)、
  [消息schema](../../../../Report_creater_agent/services/app-service/app/schemas.py)、
  [扩展装载](../../../../Report_creater_agent/services/app-service/app/services/extension_startup.py)。
- [RCA生成/评审调用](../../../../Report_creater_agent/apps/desktop/src/profiles/reportCreator/workflow/RCAWorkflowPage.tsx)、
  [交互Chat](../../../../Report_creater_agent/apps/desktop/src/components/chat/WorkflowChatPanel.tsx)、
  [服务端评审](../../../../Report_creater_agent/services/app-service/app/services/review_agent_service.py)。
- [SoC流水线](../../../../Report_creater_agent/services/app-service/app/services/soc/pipeline/orchestrator.py)、
  [提取阶段](../../../../Report_creater_agent/services/app-service/app/services/soc/pipeline/extraction_agent.py)、
  [SoC路由](../../../../Report_creater_agent/services/app-service/app/routes/soc_sessions.py)、
  [跨仓GUI治理](../../../../Report_creater_agent/docs/common/Dual-Repo-Co-Development-Governance-Manual.md)。
- [Sample/RCA数据与流程测试](../../../../Report_creater_agent/services/app-service/tests/test_draft_runtime_api.py)、
  [SoC契约测试](../../../../Report_creater_agent/services/app-service/tests/test_soc_routes.py)、
  [共享backend测试](../../../../Report_creater_agent/services/app-service/tests/test_agent_backend_contracts.py)、
  [Dashboard现有adapter](../../../ui_web/ai_base_workbench_adapter.py)。

这份文档只证明增强边界已经整理，不证明平台已升级、迁移提速或任何真实模型资格通过。

## 10. 核验边界

当前API-EVO-01为用户批准方向；首批接口及CF-A/B在FZ-01绑定版本获我方冻结确认。
本次仅改文档与交接材料；基座未修改，未操作凭据、运行产品测试/服务/真实模型。
当前文档检查与独立审查结果见tasks的对应amendment，不代表实现或多应用运行资格。

### 历史审查回执

API-EVO-01之前的中立性审查（GPT-5.5/xhigh）无P0/P1/P2，提出的delegated actor信任等级
已纳入合同责任。当轮OpenSpec/空白通过，10份文档28个相对目标可解析。
随后消费者分析轮OpenSpec/空白通过，9份文档29个相对目标及13份测试文件存在性通过，
但未执行消费者回归、资源量测或GUI联调；不能推出“旧应用无影响”。
全工作树大小门禁当时因另一变更两份scope测试超限失败，本次未改动或豁免。
这些历史回执不覆盖当前API演进改写，也不算目标接口的验收。

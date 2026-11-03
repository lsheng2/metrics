# Application Integration Pack

2026-11-01补充。状态：待实施契约；本文件不宣称新增CLI/SDK/skill已可运行。
任务状态唯一在tasks.md；基座通用Run API由AI Base仓库拥有，本文件只拥有Dashboard应用接入要求。
基座需独立完善的公共能力与多应用中立边界，见[AI Base增强请求](ai-base-enhancement-request.md)。
本文件的英文摘要、无工具、requiredParts是本应用profile选择，不是所有基座应用的全局默认要求。
按[API-EVO-01](ai-api-evolution.md)，这里的SDK/注册/命名建议可以随基座目标合同重新设计；
应用负责同步适配并记录旧新差异，不以保持旧调用不变限制公共API。
最新应用方收敛建议见[独立评审回复](ai-base-review-response.md)：HTTP/Python与有界inline先行，
task-run/1最终版本已获应用方冻结确认，精确hash及执行交接见回复第10节FZ-01。
strict schema本地闭包、服务账号及operator scope、runStoreId恢复锚、分期留存与CF-A/B
均已达成语义一致且基座已登记冻结，不再重复CF审批。
BASE-A现已交付0.1.0a1 pack/Python wheel并通过本方哈希接收；仅支持合成submit/by-key/result。
本方C0专属环境已安装SDK/httpx并完成禁网准备探针，主环境未变，正式应用接线尚未完成。
并行分工及C0-C3汇合点见[integration-execution](integration-execution.md)；
不能把BASE-A当作取消、unknown、原生恢复或实模资格。

## 1. 两条入口，不是每个应用都必须开放工具

| 入口 | 应用必须提供 | 模型可否调用业务CLI |
| --- | --- | --- |
| 权威站会/项目摘要 | 应用注册、TaskProfile、prompt、input/output schema、明确输入和验收器 | 首批禁止。采集、差分、统计、发布由脚本执行；模型只返回候选 |
| 可选交互助手 | ChatBinding、上下文投影、只读connector/host action；按需skill | 仅通过基座支持的受控工具lane，且命令本身执行授权；不是任意shell |

采用SDK不要求把业务逻辑写成skill。CLI是人/脚本/自动化的稳定入口；
skill是使用说明与能力选择；prompt是AI推理约束；真正权限在应用服务与基座执行层。
不得把技能目录存在、manifest注册成功或JSON schema存在当作runtime已能执行。

## 2. 应用需要交付的文件

以下目标都在Dashboard仓库，不再在旧项目里维护第二份新应用运行配置。
目标文件在W5.APP等叶任务实施；本轮只确定清单，不创建没有消费者的空壳。

`ai_bundle`分为两个独立manifest/lane：
`strict-summary/`只允许registration/task-profile/prompt/schema及package-manifest，
禁止skills、CLI tools、MCP、host actions、Chat history被其loader扫描或激活；
`interactive-assistant/`单独默认`enabled=false`，APP-06至08通过且显式启用后才注册执行能力。
下面表内strict文件归入前者，chat/connector/host-action/skill/cli-tools文件归入后者；
不能只在一个大manifest里写一句“不要使用工具”来代替装载隔离。

| 产物 / 建议目标 | 提供方 -> 消费者 | 必须包含 / 验收 |
| --- | --- | --- |
| `project_management/ai_bundle/strict-summary/application-registration.json` | 应用 -> AI Base注册服务 | 新任务namespace、credentialRef、允许的key/context/profile；无secret，无Chiplet实例 |
| `project_management/ai_bundle/strict-summary/task-profile.json` | 应用业务owner -> 基座版本化TaskProfile | summary任务、prompt/schema hash、英文输出、explicit_only、no history/tools、单次provider派发 |
| `project_management/ai_bundle/strict-summary/prompts/project-summary.md` | 应用 -> 基座task compiler | 旧摘要+累计delta+必要证据；不虚构负责人/验证；原文当数据；候选不是已接受报告 |
| `project_management/ai_bundle/strict-summary/schemas/{analysis-input,summary-output,partial-output}.json` | 应用 -> 输入编译/结果校验/测试 | WorkItem身份、baseline/target、policy/input hash、coverage、引文与owner_basis；未知字段拒绝 |
| `project_management/out/ai_base_tasks.py` | 应用summary service -> 基座SDK | submit/get/result/cancel/usage与稳定clientRunKey；错误未知不自动重发 |
| `project_management/ai_bundle/{strict-summary,interactive-assistant}/package-manifest.json` | 应用构建 -> 本地doctor/基座装载 | 各自精确文件allowlist/hash、schema/SDK版本、来源版本、注册能力；禁止跨lane自动发现 |
| `project_management/ai_bundle/interactive-assistant/chat-binding.json` | 应用 -> 已有app-chat | 可选只读项目助手；与权威task不同agent/session/policy，不混入历史聊天 |
| `project_management/ai_bundle/interactive-assistant/connectors/project-read.json` | 应用 -> 基座connector注册 | 仅已授权项目的summary/evidence/report查询；请求上下文由服务端注入 |
| `project_management/ai_bundle/interactive-assistant/host-actions.json` | 应用 -> 基座/Workbench | `projectReporting.openItem/openReport`等只读UI动作，版本/有效期/幂等，不能表示发布批准 |
| `project_management/ai_bundle/interactive-assistant/skills/project-report-assistant/SKILL.md` | 应用 -> 可选Chat agent | 只解释字段/引用/coverage与只读工具；不注册开发skills，不获取token、不执行写入 |
| `project_management/ai_bundle/interactive-assistant/cli-tools.json` | 应用 -> 基座Standard CLI runner | 仅当部署选CLI而非HTTP connector时创建；固定argv、可信exe、输出上限；两者不是同时必需 |
| `project_management/management/commands/ai_integration.py` | 运维 -> 本地bundle validator | inspect/validate默认离线；显式verify检查基座identity/version/capability，不调用模型 |
| `project_management/tests/ai_contracts/` | 应用+基座fixture -> conformance测试 | typed请求、错误、scope越界、输入完整、usage未知、零调用复用、candidate拒绝 |

Schema dialect、基座注册字段和SDK精确版本以基座正式交付的contract pack为准。
旧Run接口草案只能作为输入：`task-profile.json`在schema与loader未落实前不得标可注册。
当前基座 `extension_startup.py`直接装配CLI bundle，其他lane可能需要自己的注册装配；
不能通过在capabilityLanes里填一个名字假设通用loader已经存在。
缺少正式contract pack时，W5.APP readiness返回`blocked/CONTRACT_PACK_MISSING`；
允许保留proposal/schema草案，但不能生成被当作正式包的stub manifest、注册或报告“disabled但已集成成功”。

### Namespace与身份

经独立评审，应用方默认选择同产品 `sourceAppId=metrics-dashboard`、
`taskProfileKey=project-reporting.summary`，
scope key为 `projects.<project-uuid>.stages.<stage-uuid>`；样例Alpha/Chiplet不进入生产默认值。
新的Task profile/scope仍是注册候选，未注册前不能调用；不要自动改已有Dashboard Chat的
`metrics-dashboard/metrics.dashboardQuery`而不记录历史映射。
允许基座review后统一产品身份或重命名能力；不要求永久保留两个sourceAppId或旧名称。
采用改变时须有app/binding/scope映射、凭据授权复核、数据迁移及不支持版本的拒绝规则。
目标服务可以不兼容旧注册；不能因重命名让历史对象失去归属或让新身份越权。

凭据严格分开：用户owner/session、应用调用AI Base的token、tracker凭据、模型provider凭据。
tracker token不进入task输入/skill/CLI argv；模型凭据留在AI Base。
`metrics-dashboard`不是自动取得所有Project访问权限的账号，应用仍验证用户及stage来源范围。

## 3. 必须落到接口的行为

`AiSummaryPort.analyze(prepared, budget, execution_context) -> AnalysisOutcome`：

- 输入包含固定stage/rule/provider/site/principal，旧成功summary、累计delta、需要的原文引用及coverage。
- 发起前持久记录本地attempt与clientRunKey。POST回复丢失后查询原run，不换key。
- 结果关联应用logical input hash与基座effective input hash，两者不是同一个hash。
- 按已确认CF-A，由应用核验RunResult/attempt后补入本地候选input_hash，原始模型输出不生成该hash；
  平台原content和output hash原样保留。profile/schema采用FZ-01绑定版本，后续语义变化另行版本化。
- 基座返回succeeded只表示结构化计算成功；应用证据/owner/language/CAS校验后才接受。
- no_work路径不启动基座，不仅是基座内部缓存命中；无变化行动仍可出现在报告。
- usage未知保持unknown；fragment/merge各次派发分别计数，SDK/模型不隐藏重试。
- 超长输入先由应用无损分块；每个基座strict task仍只允许一次自动provider派发。
- 取消语义、迟到结果和API版本匹配沿基座正式Run合同；本地摘要水位不能由UI或skill改写。
- 接受前检查profile声明的requiredParts，规则见provider-access第7节；缺必需部分不推进accepted水位，
  partial发布不得称complete daily summary，现有旧summary保持原绑定/过期状态。

## 4. 应用接入验收

| ID | 实际要否定的错误 | 目标测试 |
| --- | --- | --- |
| APP-01 | bundle缺文件/版本不匹配或contract pack缺失仍可注册 | `test_ai_bundle.py`：CONTRACT_PACK_MISSING不注册，strict manifest出现工具lane即拒绝 |
| APP-02 | 把开发skill/Chat历史/工具放进权威任务 | `test_ai_input_contract.py`：capture实际请求，无隐式来源，>12k文本完整 |
| APP-03 | 重提任务产生额外费用、unknown当0 | `test_ai_task_recovery.py`：丢回复、重启、usage补记和deadline |
| APP-04 | 错stage/site/输入hash或缺requiredParts结果被接受 | `test_summary_acceptance.py`：跨项目/来源/过期基线/partial必需coverage拒绝推进accepted |
| APP-05 | raw token/secret/private path进入包或模型 | `test_ai_bundle.py`和`test_ai_input_contract.py`合成secret canary |
| APP-06 | 点击打开工单被解释为修改/发布批准 | `test_project_host_actions.py`：错误origin、过期、重复ACK拒绝 |
| APP-07 | skill说明存在但工具入口缺失仍报支持 | `test_ai_bundle_consumers.py`：实际注册/命令schema/消费者闭环 |
| APP-08 | 身份正确但项目无权限仍能查报告 | `test_project_read_connector.py`：服务端owner/stage/artifact检查 |
| APP-09 | 基座/SDK/binding版本已变而旧调用仍被错误接受 | `test_ai_contract_version.py`及现有workbench adapter/host-action测试：支持组合执行，未支持组合在模型/发布前拒绝；原领域断言迁移 |

新增测试路径在 `project_management/tests/`（ai_contracts归类由W5 refreeze定版）；
已有workbench消费者测试位于`ui_web/tests/`。
APP-01至05属于权威摘要首批必需；可选Chat/skill/host action的APP-06至08在启用前完成，
不以可选交互拖延权威日报。未实现功能保持disabled，不发明空的通过回执。
APP-09属于基座版本切换时的必需准入，含已有Dashboard交互消费者；
它不属于可选新助手W5.CHAT，不能因为新助手未启用而跳过旧工作台迁移。

## 5. 与基座Copilot的交接

基座交付generic Run/SDK/capabilities/profile loader；Dashboard交付本应用schema/prompt、业务验收、
应用注册和合成consumer。双方交换固定contract pack，不各造一套clientRunKey/错误/取消协议。
基座CLI `ai-base job`不是Jira CLI，也不能直接发布项目报告。
上线顺序：离线pack -> fake AI service -> 固定安装/无真实模型 -> 获准真实后端资格 -> 单项目手动闭环。
项目UI/语言选择、Chat成功或CLI连接成功均不能跳过最后的接受/发布验收。
完整委托见[基座review handoff](ai-base-review-handoff.md)；基座回传API change log和每应用迁移包。
W4.REPLAN接收并冻结版本/consumer闭包；W5.MIGRATE处理已有AI工作台的受影响调用，
W5.APP/INPUT/CLIENT/ACCEPT处理新任务。没有消费者回执不称已接入新基座。

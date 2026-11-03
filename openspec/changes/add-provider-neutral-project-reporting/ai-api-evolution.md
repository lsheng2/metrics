# AI API 演进与跨应用迁移记录

日期：2026-11-01。决策 `API-EVO-01`：accepted，用户已明确批准。
范围：AI Base、SDK及其应用接入协议的设计与后续协调迁移。
具体目标API尚待基座review/freeze；本文件不是已发布接口，也不代表迁移已执行。
实施状态仍归[tasks](tasks.md)及基座自己的OpenSpec，本文不另建执行清单。

## 1. 决策与替代关系

所有相关应用都处于开发早期，**优先形成清晰、通用的目标架构，允许协调式breaking changes**。
可以修改或移除endpoint、SDK方法、DTO、错误类型、事件、注册方式、同步/异步调用及内部模块。
不再要求“仅增量添加接口”“旧应用零修改”“旧Chat方法永久可用”。
本决策取代上一轮增强请求中的默认向后兼容、保留旧同步响应和仅opt-in新增接口约束；
既有Git记录及旧研究保留为历史，不能继续用这些旧约束否决合理的新API。

采用协调式重构，而不是全盘重写，也不是永久维护新旧两套实现：

| 选择 | 当前决定 |
| --- | --- |
| 永久兼容所有旧API | 不作为默认目标；不能为此持续扩大adapter和分叉 |
| 不核对消费者就全盘重写 | 不采用；会丢失领域行为和增加无依据的工作量 |
| 基座review后冻结目标合同，逐应用迁移 | 采用；破坏性差异可接受，但必须可交接、可验证、有版本记录 |

兼容层只在明确需要滚动升级或过渡时使用，记录owner、适用版本、删除条件和测试。
不需要兼容层时可直接替换；无需仅因为“其他APP要改代码”再次询问用户。
这不是删除用户数据、放宽安全边界、启用正式任务或无限真实模型调用的授权。
无关Provider CLI/W1接口不因本决策自动重写；涉及它们时须单列影响。

## 2. 可变化的形式与必须保持的保证

| 可重新设计 | 仍须证明的结果 |
| --- | --- |
| Chat/Task facade、公共execution core、SDK目录与方法名 | 交互历史/工具与严格任务显式输入隔离；不因复用core泄漏上下文 |
| RCA生成/评审API及Draft/ReportTask建立位置 | 草稿、修订、任务关联可追踪；重复取结果不重复发布，模型成功不是业务批准 |
| SoC同步转异步、callback改事件或轮询 | GUI能得到终态/失败/patch状态；分析结果不能自动等同signoff |
| app ID、binding、scope和profile schema | 身份迁移有映射，历史归属不丢失，不能跨app/scope读取或取消 |
| 统一错误/取消/usage/能力协商 | 不确定派发不能盲重发，费用未知不算0，取消意图不伪称远端已停止 |
| 存储schema、配置、输入/产物运输 | 保留已捕获历史和来源；有界迁移，写失败不假报成功，不重算原文来改hash |

权限、凭据隔离、完整性、人工批准和业务水位不是“旧API兼容负担”。
RCA mock fallback可移除或限制到显式demo模式；不能在新真实执行合同中冒充模型成功。
SoC stub仍是stub，迁入新API不自动获得真实模型资格。
语言、工具、检索和留存是明确的profile/应用策略，不硬编码为Dashboard全局偏好。

## 3. 唯一记录与必填字段

基座维护者将下面的候选ID导入基座OpenSpec，并指定一份canonical API change log/migration guide。
采纳后Dashboard只记录所消费的版本、对应ID与本地迁移证据，不维护另一份通用协议副本。
拒绝/合并候选也要有理由和替代ID；后续变更追加记录，不覆盖已发布版本的含义。

每条正式记录必须包含：

| 字段 | 内容与完成判据 |
| --- | --- |
| Identity | change ID、decision、理由、owner角色、源码baseline commit |
| Old -> new | 精确HTTP方法/path/状态/DTO、SDK签名、事件或CLI协议；删除/新增分别列明 |
| Semantics | 默认值、分页/上限、鉴权、scope、重试/幂等、取消/到期、usage和业务副作用差异 |
| Versions | contract version、服务build、SDK包版本/hash、profile/schema revisions及支持组合 |
| Consumers | 具体repo/path/symbol、应用owner、调用类型；包含服务端直接调用，不只浏览器SDK |
| Migration | 逐调用点改法、旧新JSON/代码示例、配置映射、数据/身份迁移及不可逆步骤 |
| Validation | 不变业务保证、已变API的替代断言、拒绝旧/错误版本的反例、实际test node与结果 |
| Rollout | 独立部署还是共享实例、部署顺序、在途处理、暂停准入、回滚或向前修复方案 |
| Receipt | 文档/包交付、应用采纳与运行验证分别记录；未更新应用标记counterpart-required |

精确目标字段未冻结的记录不能称为“可直接编码的API”。
可以先完成基座设计/合成实现；应用Agent收到目标schema、示例和fake pack后再改调用方，
避免各自猜接口。单纯“已通知其他Agent”不等于迁移完成。

## 4. 初始候选登记

以下均为**proposed，待基座review**，不是要求全部实施，也不是额外任务状态。
路径基于上一轮核验的AI Base `2332d549ab69a7e927865acd0e3db2a19295c609`；
基座Agent应先核对自己的真实checkout，不能用该快照替代当前源码。

| ID | 旧入口/问题 | 建议review的目标差异 | 已知消费者与迁移重点 | 否定错误的检查 |
| --- | --- | --- | --- | --- |
| API-01 | `template_runtime/services/agent_runtime.py`面向chat/stream；Run草案未落地 | 明确公共execution port与Task/Chat facade；可调整现有runtime签名，不强求每次对话走重型持久任务 | `app/services/review_agent_service.py`、`apps/desktop/src/components/chat/WorkflowChatPanel.tsx`、Dashboard新W5 client | strict请求不带Chat历史/tools；服务端直接消费者也适配 |
| API-02 | `packages/application-sdk/src/index.ts`绑定/context/message入口及文本异常 | 同一SDK合同下重整注册、typed error、version/capability、Run/Input/Artifact | 基座TS客户端；Dashboard `ui_web/ai_base_workbench_adapter.py`及W5 Python客户端 | 支持组合正常，旧/未知不支持组合在副作用前拒绝；不要求所有旧签名继续可用 |
| API-03 | RCA `RCAWorkflowPage.tsx`通过Chat创建草稿并查ReportTask；review直接调runtime | 把AI计算与Draft/Review业务接受显式分开，允许新应用API替换旧Chat副作用 | RCA生成/评审/finalize及相关测试 | Run成功不自动finalize；重复拉取不重复Draft；mock/truncated来源不能算严格成功 |
| API-04 | `app/routes/soc_sessions.py`等待pipeline并回调GUI | 评估异步run关联、状态查询/事件和业务session边界；可改同步响应/callback | `app/services/soc/pipeline/orchestrator.py`及外部GUI消费者；GUI路径由SoC owner核对 | 失败不发成功、错project回调拒绝、GUI可恢复查询；stub不算模型资格 |
| API-05 | app-chat注册、profile、`metrics-dashboard`与候选`project-reporting`身份分离 | 评估单产品身份+能力profile或明确多个身份；可统一ID/命名，不要求保留旧名称 | 基座app-chat服务、Dashboard adapter及`ai_bundle`、Sample/RCA profile | 迁移后历史归属可追踪、旧凭据/绑定不能扩大权限、未声明版本拒绝 |
| API-06 | 输入预览/截断、执行错误及usage分散在旧调用中 | 统一输入manifest、完整性/provenance、结构化结果和真实执行回执 | RCA review、Sample任务样例、SoC未来模型阶段、Dashboard W5.INPUT/ACCEPT | require_all不截断；模型错误不能mock成成功；unknown不退款、不盲重发 |

其他现有应用及同仓内置Dashboard profile也由基座Agent作consumer census。
上表是已知起点而非完整清单；基座不得用“未列在表中”跳过实际发现的调用者。

## 5. 跨仓传播与交付边界

基座合同冻结 -> schema/golden/fake pack -> 各应用适配可并行 -> 版本化发布 -> 对应部署组合验收。
BASE-A/B/C仍是基座能力分组，不新增另一套打勾清单。

| 生产者 | 消费者 | 交付及拒绝条件 |
| --- | --- | --- |
| 基座API change log + pack | RCA/Sample/SoC同仓模块 | 基座Agent可按其OpenSpec同步修改；不得在同一交付中留下失配调用并称整个基座通过 |
| 基座SDK/schema及API-02/05 | Dashboard `ui_web/ai_base_workbench_adapter.py`、`project_management/out/ai_base_tasks.py` | Dashboard Agent按目标版本更新旧交互和新任务；版本不匹配阻止AI调用，不阻止离线项目/历史读取 |
| 基座SoC API/事件及API-04 | 外部GUI Agent | 交付精确响应/事件、状态图、前后示例、fake服务和失败恢复用例；未收到应用回执不能称GUI已适配 |
| 各应用迁移回执 | 基座发布清单 | app commit/build、SDK/contract、通过测试、未决事项；未迁移者明确禁用不兼容入口或固定旧独立部署 |

外部应用尚未迁移不阻止基座在隔离候选上开发和验证。也不要求新基座服务继续接纳旧调用。
但共享实例不能未经版本检查把旧客户端导向新协议；不能以“记录过breaking”代替运行准入。
独立部署可分批升级；共享实例需匹配版本组合或明确拒绝未迁移应用。
数据升级先保留可恢复副本/检查点；旧二进制不能安全读新数据时不得强行回滚。
app ID/API版本迁移须保留原clientRunKey与run/attempt、输入revision、reservation/usage、
未知派发和tombstone的可追踪映射；不能用新namespace重置幂等账后重复调用模型。
兼容层若存在，应用回执和部署切换后按已记录条件删除，检查生产调用点不再引用旧入口。

## 6. 测试如何随破坏性变更更新

1. 未变化合同继续原回归；不为重构重写其预期。
2. 有意改变的API为旧断言建立“change ID -> 新测试”映射，允许旧测试被替换，不要求新服务通过旧协议测试。
3. 独立保留或重建业务/权限/证据/成本保证的反例；不能只删旧测试而遗漏行为。
4. 不支持版本验证零模型派发、零业务发布/水位推进；错误回应可使用安全的基础版本拒绝协议。
5. 若宣称支持滚动升级，就测试所声明的旧新组合；不宣称支持的组合只验证明确拒绝，
   不扩展成所有历史版本/所有应用的全量矩阵。
6. 合成契约与打包先行，受影响应用工作流随后，少量真实backend资格独立授权。

本决策记录已获批准；具体API、代码、迁移与性能效果仍需后续基座review及双方验收。

# Application Integration Pack

2026-11-11改写。状态：待实施契约。当前AI接入架构以
[MDB-2](../embed-ai-base-runtime-in-process/proposal.md)为准：AI Base作为`ai-base-runtime`在Metrics进程内运行，
Metrics经project_management的同步task-run端口，以`project_management/ai_profiles/`中精确`id@version`的profile调用。
本文件只拥有Dashboard应用接入要求；准入、执行、审计、审批、会话与tool授权由运行时拥有；任务状态唯一在tasks.md。
此前的SDK/HTTP、应用注册、connector、host action、contract pack、`ai_integration` doctor及BASE-A/C0内容
已被取代，只在git历史与[execution-handoff](execution-handoff.md)等历史附录中作为证据，不定义剩余工作。
英文摘要、无工具、requiredParts是本应用的profile选择，不是所有AI Base应用的全局默认要求。

## 1. 两条入口，不是每个应用都必须开放工具

| 入口 | 应用必须提供 | 模型可否调用业务能力 |
| --- | --- | --- |
| 权威站会/项目摘要 | `ai_profiles`中的profile数据（instructions、input/output schema、policy）、明确输入和验收器 | 禁止：profile不声明tool。采集、差分、统计、发布由应用代码执行；模型只返回候选 |
| 可选项目助手 | 独立助手profile与Metrics App read tool，默认disabled | 只经运行时tool授权调用Project公共API，并以认证principal校验；不是任意shell、connector或host action |

业务逻辑不写成skill。CLI是人/脚本/自动化的稳定入口；profile instructions是AI推理约束；
真正权限在应用服务与运行时tool授权。profile文件或schema存在不代表运行时已能执行。

## 2. 应用需要交付的文件

目标都在Dashboard仓库，由MDB-2 5.1至5.4建立，W5.APP/INPUT/CLIENT/ACCEPT在其上演进；不创建没有消费者的空壳。

| 产物 / 目标 | 提供方 -> 消费者 | 必须包含 / 验收 |
| --- | --- | --- |
| `project_management/ai_profiles/`中的`metrics.project_summary` | 业务owner -> project_management公共API -> `ai_host.package` | 英文输出、instructions、input/output schema、policy；不声明tool；精确版本，内容变化即升级 |
| `project_management/ai_profiles/`中的`metrics.report_authoring` | 同上 -> report assist | 独立于summary的profile；不可用时返回`REPORT_AI_UNAVAILABLE`，人工编辑不受影响 |
| summary instructions | 应用 -> 运行时 | 旧摘要+累计delta+必要证据；不虚构负责人/验证；原文当数据；候选不是已接受报告 |
| summary input/output schema | 应用 -> 输入编译/结果校验/测试 | WorkItem身份、baseline/target、policy/input hash、coverage、引文与owner_basis；未知字段拒绝 |
| `ai_host/package.py`（`METRICS_APP.task_profiles`） | ai_host -> 运行时准入 | 把profile数据转为`TaskProfile`；`check_app_package`通过，含schema校验 |
| `project_management/out/ai_task_contract.py`、`out/report_ai_task.py` | project_management -> 端口实现 | 同步端口协议，入参/返回为project_management值类型；请求引用精确`id@version`，不用`latest` |
| `ai_host/task_runs.py`（`RuntimeTaskRunPort`、`local_task_run_port`） | ai_host -> project_management | `start(principal, request, timeout=30)`；CLI经`open_local_task_run_port()`在自身进程运行 |
| 可选助手profile与read tool | 应用 -> 运行时tool授权 | 默认disabled；只读已授权项目的summary/evidence/report；上下文由服务端注入 |
| `project_management/tests/ai_contracts/` | 应用 -> conformance测试 | 准入错误、scope越界、输入完整、usage未知、零调用复用、候选拒绝 |

### Namespace与身份

运行时App id为`metrics`；项目任务的scope与`context_ref`使用`projects.<project-uuid>.stages.<stage-uuid>`；
样例Alpha/Chiplet不进入生产默认值。幂等命名空间为(principal, app_id, `client_run_key`)。
凭据严格分开：用户owner/session、tracker凭据、模型provider凭据；进程内运行时没有应用调用token。
tracker token不进入task输入、instructions或CLI argv；模型凭据只在运行时配置中。
principal是提交的认证用户，不自动取得所有Project访问权限；应用仍验证用户及stage来源范围。

## 3. 必须落到接口的行为

`AiSummaryPort.analyze(prepared, budget, execution_context) -> AnalysisOutcome`语义保留，提交改为端口`start`：

- 输入包含固定stage/rule/provider/site/principal，旧成功summary、累计delta、需要的原文引用及coverage。
- 启动前持久记录本地attempt与`client_run_key`；结果未知时按原key查询，不换key、不续期deadline。
- 结果同时关联应用logical input hash与运行审计的`definition_sha256`、模型身份和运行时版本，二者不可混用。
- 端口返回完整结果只表示结构化计算成功；应用证据/owner/language/CAS校验后才接受。
- no_work路径不调用运行时；无变化行动仍可出现在报告。
- usage未知保持unknown；fragment/merge各次运行分别计数，运行时不隐藏重试。
- 超长输入先由应用无损分块；每个strict task只派发一次模型调用。
- 端口原样传递准入错误码与`recovery`（`profile_not_declared`、`profile_disabled`、`model_not_configured`、
  `input_schema_invalid`）；运行时未运行为`RUN_UNAVAILABLE`，`RuntimeBusy`为`RUN_BUSY`。
- 取消与迟到结果沿运行时task-run语义；本地摘要水位不能由UI或助手改写。
- 接受前检查profile声明的requiredParts，规则见provider-access第7节；缺必需部分不推进accepted水位，
  partial发布不得称complete daily summary，现有旧summary保持原绑定/过期状态。

## 4. 应用接入验收

| ID | 实际要否定的错误 | 目标测试 |
| --- | --- | --- |
| APP-01 | 未声明/禁用profile、schema不合或版本不精确仍可运行 | `check_app_package`与profile准入测试：模型调用前拒绝；strict summary声明tool即失败 |
| APP-02 | 把Chat历史/工具/隐式来源放进权威任务 | `test_ai_input_contract.py`：capture实际请求，无隐式来源，>12k文本完整 |
| APP-03 | 重提任务产生额外费用、unknown当0 | `test_ai_task_recovery.py`：结果未知按原`client_run_key`查询、重启、usage补记和deadline |
| APP-04 | 错stage/site/输入hash或缺requiredParts结果被接受 | `test_summary_acceptance.py`：跨项目/来源/过期基线/partial必需coverage拒绝推进accepted |
| APP-05 | raw token/secret/private path进入profile或模型输入 | profile数据与`test_ai_input_contract.py`合成secret canary |
| APP-06 | 只读助手的调用被当作修改或发布批准 | 助手read tool测试：模型请求写操作或审批时拒绝 |
| APP-07 | profile声明的tool缺少实现或消费者仍报支持 | `check_app_package`与tool消费者闭环测试 |
| APP-08 | 身份正确但项目无权限仍能查报告 | read tool测试：服务端owner/stage/artifact检查 |
| APP-09 | 运行时版本已变而旧调用仍被错误接受 | 运行时版本准入（MDB-2 5.11）与受影响消费者测试：未准入版本在模型/发布前拒绝；原领域断言迁移 |

新增测试路径在`project_management/tests/`；已有工作台消费者测试位于`ui_web/tests/`与MDB-2新增的`ai_host/tests/`。
APP-01至05属于权威摘要首批必需；可选助手的APP-06至08在启用前完成，不以可选交互拖延权威日报。
未实现功能保持disabled，不发明空的通过回执。APP-09属于运行时升级时的必需准入，含已有工作台消费者；
它不属于可选新助手W5.CHAT，不能因新助手未启用而跳过。

## 5. 分工与上线顺序

运行时由AI Base以`ai-base-runtime` wheel交付；Metrics交付profile数据、业务验收、端口消费者与宿主组合，
细节见[MDB-2 design](../embed-ai-base-runtime-in-process/design.md)。
上线顺序：profile与`check_app_package` -> testkit脚本化模型 -> 已准入运行时版本且无真实模型 ->
获准的真实模型资格 -> 单项目手动闭环。项目UI/语言选择或助手成功均不能跳过最后的接受/发布验收；
没有消费者回执不称已接入。

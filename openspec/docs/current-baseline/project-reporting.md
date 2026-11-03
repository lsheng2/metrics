# 项目管理与报告

## 当前状态

Dashboard是后续项目管理与报告的产品入口。`project_management`是通用业务模块；
Chiplet不是生产代码中的固定项目。用户可以创建任意命名项目，并为阶段选择Jira scope或HSD-ES profile。

当前代码包含持久项目/阶段目录、本机CLI、经过认证的双语桌面表单、
连接/凭据服务、Jira内部采集与Git归档，以及已跑通合成业务链路的严格摘要接入切片。
各个已经通过的独立评审、实际候选、桌面验证和后续实施状态见
[唯一任务清单](../../changes/add-provider-neutral-project-reporting/tasks.md)。
采集到HTML下载、显式Git定稿、重启与无变化复用已通过本机合成全栈验证。
完整provider覆盖、累计delta、富文本集成和正式运行仍待后续交付。
内部合成能力不等于真实来源或真实模型已经上线。

### 已验证的演示

2026-11-03验收使用真实Django/worker、Git、安装SDK和Base HTTP，
Jira响应与模型输出为明确登记的合成内容。1次Base派发产生1份已接受摘要；
重启后再次采集相同内容返回`no_work`，没有新分析尝试或Base Run。
浏览器状态自动刷新并在终态停止，旧报告的HTML/文本下载与原Git字节一致。
三条完整评论、原始Base结果和六份旧数据指纹均保留。
详见[交付回执](../../changes/add-provider-neutral-project-reporting/manual-workflow-delivery.json)。

本轮两个服务均已正常停止，独立HTML示例保存在下方数据根的
`evidence/report.html`。需要再次打开应用时，从本仓执行：

```powershell
$run = 'D:\AIGC\scrum_dashboard_validation\full-stack\7b1f3cc9-7fb4-4bf3-acdc-f4dbb5c4b510'
& .\.venv\Scripts\python.exe -B scripts\validation\project_full_stack.py start --run-dir $run --lifetime-seconds 1800
```

使用命令成功返回的URL。本次地址为
`http://127.0.0.1:8127/projects/20184354-86f2-4156-9e52-6a3dc311ebef/stages/2bafe7f9-0441-461d-992d-2a6176696f95/reports/`。
合成账号为`SYNTHETIC_ALICE`，密码为`SYNTHETIC_ALICE_PASSWORD`；
它们不是公司凭据。演示应用会话限时1800秒。正常退出：

```powershell
& .\.venv\Scripts\python.exe -B scripts\validation\project_full_stack.py stop --run-dir $run
```

这些命令复用已验证的本机输入、原store与数据根，不是正式安装器。
旧项目配置Demo、真实数据库和正式定时任务没有在本轮迁移或启用。

## 产品目标与分工

目标是帮助每日站会持续了解指定阶段内的每个工单：问题是什么、最新状态/阻塞、
下一行动与负责人及其来源证据，而不是只提供图表或聊天。
应用负责范围、采集、原文历史、累计delta、候选校验和报告；AI Base负责受控AI计算。
未变化且摘要有效时不调用模型，有变化时以最后成功接受摘要为基线，避免重复总结旧历史。
完整业务背景、从旧独立实现转向Dashboard/基座的原因和API需求映射，
见[基座handoff第0节](../../changes/add-provider-neutral-project-reporting/ai-base-review-handoff.md)。
这些是后续交付目标，不扩大上文W1的已实现范围。

## 数据与范围

- Project是用户业务容器；Provider Profile是连接/来源/映射配置，两者不同。
- 一个Project可以有多个Stage；每个Stage保存一份不可变来源定义。
- Jira Stage要求已启用scope与显式profile绑定，不接受相似名称或兼容推断。
- HSD-ES Stage使用自己的saved-query profile，不要求伪造一个Jira scope。
- Stage保存来源endpoint、query/reference和版本hash，不保存profile凭据。
- Dashboard范围编辑后，旧Stage保持不变，查询显示`source_changed`；采用新规则须新建Stage key。
- 来源归档/删除后Stage显示`unavailable`，不会级联删除项目和阶段。
- 这只是本地来源配置快照，不是已完成的成员枚举/评论抓取或运行许可。
- HSD-ES saved query的远端定义仍要在采集阶段按授权复核；本地hash不能证明远端从未变化。

## 本机CLI

从Dashboard根使用本项目`.venv/Scripts/python.exe`。
安装时需要应用新migration；本次开发验证仅使用测试数据库，未迁移用户已有`db.sqlite3`。
正式迁移前应完成正常数据库备份/部署确认，不能将测试库通过当正式数据已升级。

```powershell
$python = Join-Path (Get-Location) '.venv/Scripts/python.exe'
& $python manage.py project_catalog --help
& $python manage.py project_catalog create --key alpha --name "Alpha Project"
& $python manage.py project_catalog list --limit 50 --offset 0
```

`show <project-uuid>`、`archive <project-uuid>`使用create/list返回的UUID。
`add-stage <project-uuid> --key release-1 --name "Release 1" --profile-id <configured-profile>`
创建阶段；Jira额外提供`--scope-id <positive-id>`，HSD-ES不提供scope-id。
这些占位符是操作说明，不是可直接执行的实例。没有预置Chiplet或默认Jira范围。

同key/name重复create返回原项目。Stage的key/name/selection/descriptor完全相同时重复请求返回原阶段；
不同定义返回`STAGE_RULE_IMMUTABLE`。重复archive不产生新审计事件。
归档后仍可查询，不能新增Stage；目前没有编辑Stage、硬删除或恢复归档命令。

success输出JSON：`schema_version=1`、`result`和`error=null`。
业务错误以Django标准`CommandError:`前缀后的安全JSON输出到stderr并非零退出。
参数解析错误沿用Django argparse；数据库/程序内部异常不是业务成功。

## 权限边界

W1 CLI固定使用可信的`local_operator`，不接受`--actor`、token、原始descriptor或HTTP调用。
公共Python API要求传入由可信调用层提供的ProjectActor，并按owner隔离Project。
ProjectActor本身不是认证凭证；浏览器不能提交任意subject。
项目页面使用既有Basic Auth成功验证的账号，默认owner为`basic:<username>`。
未配置或未通过认证的请求不能访问项目页面，即使旧Dashboard页面允许匿名访问。
所有写入保留Django CSRF校验；其他owner的项目返回404，不泄露项目内容。

`METRICS_PROJECT_LOCAL_OPERATOR_USERNAME`默认留空。操作员显式配置某个精确账号名后，
只有该已验证账号映射到`local_operator`并能访问CLI创建的项目；不自动选择首个账号。
更改映射会改变访问关系，但不重写旧项目owner或历史。

创建、查询和归档项目只读本地source配置，不发起Jira/HSD/模型网络调用。
API每次返回来源状态而不自动重新抓取或修改已冻结记录。

## 桌面项目页面

入口为`/projects/`，部署了路径前缀时沿用该前缀。现有Scope Library和Provider Setup
仍负责来源配置；项目页面不创建第二套连接设置，也不自动测试真实上游。

1. 使用已配置的Dashboard账号进入Projects，创建项目key和名称。
2. 在详情页填写阶段key/名称，选择已明确绑定的Jira scope或HSD-ES profile。
3. 预览来源endpoint、查询和定义hash，确认后创建不可变阶段。
4. 来源变化、禁用或删除不会覆盖阶段；详情页显示当前来源状态。
5. 归档需要显式确认；归档后历史阶段仍可读，新增阶段被拒绝。

预览保存在服务器的Django DB session中，绑定owner/project，最多有效600秒。
确认时重新检查来源hash；来源漂移、过期、错误项目或身份均不能创建阶段。
本功能拒绝signed-cookie session等未支持的后端，不把浏览器保存的内容当批准记录。
切换语言不会确认阶段；从确认页返回项目详情时保留有效的服务器端草稿。

English/简体中文来自Django gettext静态资源。语言选择、页面`lang`、表单及来源状态标签
一致；项目名称、阶段key、查询、hash和业务记录不翻译、不重算。
现有其他Dashboard页面尚未宣称全部本地化。LLM翻译仍是未来独立展示层。
阶段工作台已接入报告编辑、显式定稿和手动运行控件；运行按钮需要显式启动的受信runtime。
打开页面不启动采集或模型。

### HTML报告工作台

2026-11-03用户明确要求直接编辑富文本。当前页面的文本框加预览只是过渡实现，
不满足所见即所得要求；独立编辑器Agent负责接入开源组件。本轮先收尾采集、
分析、已保存HTML下载和显式Git定稿，不继续扩展旧编辑器测试。
富文本、复制交互和Outlook的联合验收等组件交付后再做，
接口及交接清单见[编辑器handoff](../../changes/add-provider-neutral-project-reporting/rich-text-editor-handoff.md)。

报告以可复制到邮件正文的HTML为主，提供每日站会和按日横向对比模板。
已有的阶段工作台列出真实归档采集、草稿和定稿记录，可从已保存来源创建草稿，
编辑会议注释和叙述字段，保存后预览、复制或下载。最后由用户明确选择是否定稿
并提交独立数据Git。实际Ego桌面已完成运行、下载和显式定稿；
编辑、复制与Outlook验收等待富文本组件。旧的项目/阶段配置Demo不会自动升级到这些源码。

列表每页20条并保留采集游标；过多记录明确拒绝，不把截断结果或Git故障显示为空列表。
保存支持多条注释，未显式删除的旧注释会保留。Copy与Finalize仅作用于精确已保存修订，
有未保存修改时禁用；切换界面语言不会悄悄丢弃或保存这些修改。
定稿确认显示实际注册的数据archive UUID、项目和阶段，不暴露路径或让用户输入remote。
中断定稿使用原命令恢复；已定稿版本只能创建关联新修订，旧版本继续可下载。

模板只决定展示，不改变范围或触发模型。生成的业务内容保持英文，原文和人工注释
按原语言保留并标明来源。人工修改不覆盖Jira事实、已接受摘要或模型原content/hash。
草稿保存不提交最终报告；复制不等于发送邮件或发布，未提交草稿不替代上次正式站会基线。
定稿保留原始快照、模板版本、人工修改和最终HTML字节；再次修改产生新版本，不覆盖旧版。
原始采集与摘要仍按原有规则及时归档，不等人工定稿。不会自动push到remote。

复制目标是带格式的完整正文，而不是HTML源码。App提供编辑控件，导出的邮件HTML
不含编辑脚本/控件，使用独立样式和静态表格。用户已通过2026-11-02截图确认验收目标：
Windows Outlook `1.2026.1020.100`，Client `20261023003.06`，
WebView2 `156.0.4314.50 (Stable)`。版本信息已明确，但实际粘贴验收尚未执行；
不能仅凭截图或Chrome剪贴板成功承诺Outlook格式保真。执行时记录实际版本及HTML撰写模式，
不保存Session ID，也不扩大为所有邮件客户端的测试矩阵。
详细API、存储/恢复和实施边界见
[HTML报告设计](../../changes/add-provider-neutral-project-reporting/html-report-authoring.md)，
测试场景见[HTML报告验收](../../changes/add-provider-neutral-project-reporting/html-report-validation.md)。
Markdown/Excel原有需求保留；离线HTML修改回导和通用模板编辑器不在首个Demo范围。

### 内部报告数据读取

报告源查询已完成专项验证与独立代码评审；其范围和证据记录在当前任务入口。
内部入口是`project_management.app.api.reports.ReportSourceReader`及
`CaptureArchiveService.read_report_material`，只读取固定Git提交中的完整成员范围、
当前事实和经过重新核验的已接受摘要，不创建草稿或发起模型调用。
详情/摘要未齐的成员保留为pending；不完整成员枚举拒绝生成貌似完整的清单。
来源hash与coverage分开检查，原摘要时间和RunResult hash保持不变。

目前该查询只支持最新capture的初始报告投影；跨天基线、历史publication选择由后续
报告/增量接口逐步接入，不能把初始投影当作完整多日增量。
该读取接口已用于上文的合成全栈验收，不代表多日或真实来源资格。
精确边界与来源见[源码查询实施包](../../changes/add-provider-neutral-project-reporting/html-source-packet.md)。

内部`ReportRenderer`现已提供`daily-standup/1`与`weekly-timeline/1`模板、
独立HTML正文/文件和纯文本输出。源字段、人工编辑显示和模板依赖哈希已通过专项与
独立评审，渲染不调用Jira/模型或写Git。周视图只展示传入的已验证日期资料，
不会制造历史；资料缺失有明确状态。模板已接入编辑页面和定稿流程，
合成单日下载/定稿已验收，实际Outlook粘贴仍待编辑器联调。

内部`ReportDraftService`现提供create/get/save/render：草稿存在独立数据目录的runtime，
每次保存保留修订和服务端作者/时间，命令重放保持原修订；重复/过期窗口不能覆盖新编辑。
保存不提交Git，渲染携带实际revision_hash。中断修订可从完整意图恢复，历史修订会验证
原命令/哈希链。该服务已通过专项与独立评审，并已接入用户编辑页面；
新采集/分析的手动运行入口已通过合成服务闭环，富文本前端独立交付。

内部定稿接口现已支持`finalize_and_commit`、`resume_finalization`、
`get_publication`和`read_artifact(format="html"|"plain_text")`。
显式定稿先保留完整六文件字节及原命令/修订绑定，再通过原有stage Git写入器提交；
查询失败不当作“未提交”，旧窗口修订与来源变化拒绝，提交恢复不重新渲染或调用模型。
原稿、各次人工修订和最终文件保留，公开下载仅返回HTML/纯文本原字节。
这些API和对应Web路由已通过专项、独立复查及合成浏览器下载/定稿验证；
它们不代表Outlook或真实模型资格。

### 内部取消接口

`SummaryAnalysisService.cancel`先将取消意图写入原attempt归档，再查询原key或取消
已核验的原run。尚未派发时不创建SDK客户端。取消意图与派发/接受共享原有写锁，
能阻止新派发和迟到结果接受；已经接受的历史摘要不被撤销。
正常观察上限仍为16，取消有独立保留槽，控制网络调用共用10秒预算。
远端停止无法确认时保持unknown，不假称退款或进程已经停止，也不换新key重派。
保存的取消回执绑定独立核验的run ID，不能以响应自身的ID作为校验依据。
采集支持逐页检查取消并保留已捕获的部分原文。以上为内部服务能力，
不代表网页运行入口、原生崩溃恢复或真实后端取消资格已经完成。

### 内部手动运行器

`project_management.app.api.project_runs`提供`ProjectRunService`和
`ProjectRunWorker`。运行器、宿主线程、CLI和网页入口已通过专项测试及独立代码复核，
但不能将这些服务测试当成浏览器到实际Base HTTP的验收。

一次手动运行保存原请求、项目/阶段/操作者、后端身份、截止时间和采集预算。
同一命令重放使用原操作，不重新分配capture/attempt或延长期限。事件日志在独立
数据目录的`runtime/operations`中，完整准入记录hash与逐次事件链分别核验。
状态文件缺失可只读投影，损坏记录、非法状态变化和过期推理明确拒绝。
实际archive配额始终有效；状态事件、投影和active标记先做联合准入。

Worker调用既有采集、分析和草稿服务。无变化来源复用原接受摘要；未覆盖成员保持pending，
不因缺数据判为关闭，也不因模型unknown换新key重试。取消与分析准备/派发/接受共享
归档写锁下的检查，远端取消使用原SDK边界和共享控制预算。恢复保留逐票的attempt及
已接受摘要；终态只能重放，不能继续增加修订。
运行只产生明确版本的草稿，不自动定稿、发送邮件、push或启用定时。

### 显式宿主

`project_serve --host 127.0.0.1 --port <port>`显式安装并启动一个串行worker。
普通`runserver`、模块导入和页面GET都不会启动它。原生运行结束会输出结构化
`project_runtime_stopped`记录；启动/服务/清理失败、worker未退出或有未决工作均返回非零。
`project_run`提供status以及显式本地执行的start/cancel/resume命令，复用同一套业务服务。

启动恢复先有界读取持久操作，再按执行锁和原修订处理；它不会自动重派推理。
新建阶段的页面可在尚无archive时显示Run，而不通过GET创建目录或Git。
状态轮询更新状态、逐票结果、草稿链接及取消/恢复控件，终态停止轮询。
运行状态页使用本地专用脚本，不依赖旧页面仅有的HTMX fallback自动解释定时属性。
每次仅一个只读请求；读取失败保留最后观察值并显示不可用提示，不自动重交任务。
原运行产出的修订链接与最新编辑器分开；较新的定稿不会把旧草稿误标为final。

默认`METRICS_PROJECT_RUN_ENABLED=false`。当前a2只具备synthetic资格，
普通设置即使开启也不能激活真实provider/model；验证环境使用显式受信
`METRICS_PROJECT_RUNTIME_FACTORY`。不能靠改execution_mode或填写token升级资格。
浏览历史运行不依赖AI端点可用，也不创建provider/SDK客户端。
可重复的合成启动/停止命令与实际结果见本文开头的已验证演示。

部署需要既有Django session表和project_management migration。本次只迁移专属合成测试库，
未升级用户已有数据库；正式数据备份、部署和手动报告仍属于后续步骤。

## 当前模块

| 位置 | 职责 |
| --- | --- |
| `project_management/app/api` | 公共Project API |
| `app/domain` | 通用DTO、校验、项目操作与来源漂移判断 |
| `app/spi` | source catalog和repository协议 |
| `out/dashboard_scope_catalog.py` | 消费现有bug_metrics公共API，翻译Jira/HSD来源定义 |
| `out/orm_repository.py` | owner过滤、事务、唯一键和原子审计 |
| `models.py`、`migrations` | Project、Stage、Audit，外部来源无级联外键 |
| `management/commands/project_catalog.py` | 真实本机调用入口 |
| `ui_web/project_access.py` | 已验证HTTP身份到ProjectActor映射 |
| `ui_web/facades/project_management.py`及项目views/forms | 只调用公共Project API的桌面工作流 |
| `ui_web/templates/projects`、`ui_web/locale` | 双语界面与可分发的静态gettext资源 |

本地Stage不是AI Base workspace/chat session。后续strict Task API与交互Chat分开；
AI候选由业务接受服务校验证据/owner/英文后再发布，不能把模型成功当报告成功。

## 验证与限制

W1测试覆盖 arbitrary projects、owner隔离、归档、同key幂等、source漂移、HSD/Jira选择、
secret canary、写失败、CLI及来源删除后的历史读取。测试数据为合成例子，不读取企业工单。
最终执行结果和未决门禁以tasks中的当前入口为准。
W2验证包含CSRF、owner隔离、预览失效、错误输入、locale和专属测试库守卫。
Ego桌面验证保留在本地`.tmp/project-reporting-w2/browser/`，不将合成UI结果当真实来源或报告资格。
相关方案见[design](../../changes/add-provider-neutral-project-reporting/design.md)和
[capability delta](../../changes/add-provider-neutral-project-reporting/specs/project-reporting/spec.md)。

## 后续接入与移植

统一 `provider_access` 的诊断入口和内部采集API已经实现；
默认生产配置中的capture/operation仍未启用，专属演示runtime只运行合成白名单。
当前边界见[Provider采集](provider-capture.md)和[Git归档](capture-archives.md)。
首次完整输入与无变化复用已贯通，累计delta和正式资格仍未完成。
连接解析与本机`provider_credentials`采用代码已实现，完整门禁状态见任务清单；
操作与限制见[Provider连接与凭据](provider-credentials.md)，尚未采用用户真实凭据。
详细设计现在已补入同一OpenSpec：

- [应用AI接入包](../../changes/add-provider-neutral-project-reporting/application-integration.md)：哪些CLI/prompt/schema必须有，哪些skill/connector只是可选交互。
- [Provider访问与凭据](../../changes/add-provider-neutral-project-reporting/provider-access.md)：复用Dashboard设置、显式站点绑定和受保护旧PAT采用，默认不复制token。
- [旧实现移植清单](../../changes/add-provider-neutral-project-reporting/migration-catalog.md)：MIG-01至19的来源、目标、测试及不能直接搬的依赖。
- [叶任务与验收](../../changes/add-provider-neutral-project-reporting/integration-execution.md)：W3-W7的API消费者、依赖、拒绝路径和原生资格。
- [基座公共增强请求](../../changes/add-provider-neutral-project-reporting/ai-base-enhancement-request.md)：基座/SDK需独立完善的中立能力、RCA/SoC/Sample/Dashboard实际消费者影响、回归门槛及可转交提示词；尚未实施。
- [API演进与迁移记录](../../changes/add-provider-neutral-project-reporting/ai-api-evolution.md)：用户批准的API-EVO-01、breaking change记录格式及逐应用迁移要求。
- [AI Base review与增强handoff](../../changes/add-provider-neutral-project-reporting/ai-base-review-handoff.md)：项目背景、日常流程、转向原因、业务到API映射，以及提示词、其他应用影响和返回产物。
- [设计冻结回执与接入材料](../../changes/add-provider-neutral-project-reporting/ai-base-review-response.md)：第10节FZ-01绑定task-run/1精确设计及schema版本；BASE-A实现包已交付，资格边界见下文。

基座最终`task-run/1`设计已获应用方冻结确认，基座已登记FZ-01并交付BASE-A；双方CF语义一致。
边界包括逐app签名service-account、operator精确scope、持久runStoreId、分期留存、
应用绑定input_hash，以及已有key重放先于新准入；新Stage创建不等于获得AI权限。
Dashboard端正式模型profile仍未注册或部署；冻结回执不等于生产资格。

基座已交付a2 contract pack和Python wheel；Dashboard的可选开发依赖为
`requirements-ai-task.txt`，当前安装SDK为0.1.0a2。其21文件pack按固定hash保留，
不静默升级旧C0/a1环境。这不是provider、远程abort、unknown或原生恢复资格。
双方可按[并行交付与汇合点](../../changes/add-provider-neutral-project-reporting/integration-execution.md)
分别推进BASE-B与应用业务，无需互相等待整阶段完成；后续业务波次仍按本地评审和依赖推进。
当前跨仓执行入口为[execution-handoff](../../changes/add-provider-neutral-project-reporting/execution-handoff.md)，
双方各写本仓OpenSpec；不是由Dashboard代写基座内部实现。
[C0 SDK进件计划](../../changes/add-provider-neutral-project-reporting/sdk-intake-plan.md)已细化环境、
接口、12个验证用例和退出条件。C0.N1已落地为
[可运行验证脚本](../../../scripts/validation/test_task_run_sdk_intake.py)，12例全部通过；
C0.R、W1.R和W2.R已通过隔离候选的独立评审；新的业务接线由W5.JOIN单独验证。
这些是已安装SDK的MockTransport测试，不是基座服务或项目报告验收。
BASE-B及Dashboard后续波次仍须各owner按包达到就绪标准，具体等待点见execution-handoff第4节。

用户于2026-11-01批准早期协调式API重构，取代此前默认向后兼容策略。
基座可修改SDK、Chat/Task、身份注册以及SoC同步/回调形式，应用按版本化迁移包更新，
不要求永久保留旧接口。但RCA草稿/任务关联、SoC patch/signoff、Dashboard批准与历史归属
仍须按目标合同验证，不能以“允许breaking”为由删除业务保证。
本应用已完成C0.N1安装SDK验证，生产AI资格及既有工作台迁移尚未完成。未支持的旧版本应明确拒绝，
不能静默fallback；已有工作台的受影响调用由W5.MIGRATE处理，不属于可选新助手。
英文、无工具、完整输入等严格报告策略仍是本应用profile，不强加给其他应用。

同一Jira URL不代表两个凭据视野相同；UI/worker/CLI将共用ProviderAccessService，
不直连Jira数据库，不在认证失败后试另一个token。权威摘要模型无需直接访问Jira或调用CLI。
上述设计不是已实现行为；旧库源码/测试、凭据、运行历史和进程接管按四种不同边界分别迁移。

## 严格摘要切片

内部入口为 `project_management.app.api.summary_analysis.SummaryAnalysisService`。
`prepare`只读获准归档并持久化原始attempt；`advance`通过已安装Task SDK推进一次观察，
不会在丢回包后自动换key或重新POST。输入、派发声明、观察及accepted summary共用原有
Git归档、锁和空间占用配额，不另建一份attempt数据库。

当前切片只支持首次完整单capture输入与完整无变化复用。原始source hash不包含coverage，
所以每个保留版本都须另查完整性；partial/access-lost或中间A→B→A不能算无变化。
超长/多版本/未支持附件与依赖不会静默裁剪，完整累计delta仍属后续W4/W5工作。
已验证的联合场景使用真实应用目录/归档/API、安装a2 SDK和专属Base HTTP服务：
1次合成执行产生1份accepted summary，重建应用服务后无变化复用不增加执行。
这不是收费模型解读质量资格；测试executor只返回明确登记的合成结果。

接受前校验Base原snapshot/result的身份、scope、grant/限额策略、期限、profile及hash，
再核对引用、引文、未确认负责人和源版本CAS。模型不生成本地input_hash，平台原content/hash
不改写。review-1的blockers/limitations是引用ID；历史字段值只作上下文，不能单独证明
当前明确下一负责人。当前基本文字检查也不等于已完成真实模型语言/内容质量资格。

联合验证使用显式的独立D盘数据根；代码、来源Git、模型运行库和验证回执分离。
`--resume-source`只复用尚无attempt的合成采集检查点，不代表已实现原生Run冷恢复。
精确接口、命令、源码移植范围和资格边界见
[W5.JOIN实施包](../../changes/add-provider-neutral-project-reporting/early-ai-integration.md)。
手动Run按钮现已消费该切片并通过合成验证；定时任务、真实凭据采用及自动发布未启用。

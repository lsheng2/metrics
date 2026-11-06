# 项目管理与报告

## 当前状态

Dashboard是后续项目管理与报告的产品入口。`project_management`是通用业务模块；
Chiplet不是生产代码中的固定项目。用户可以创建任意命名项目，并为阶段选择Jira scope或HSD-ES profile。

当前代码包含持久项目/阶段目录、本机CLI、经过认证的双语桌面表单、
连接/凭据服务、Jira内部采集与Git归档，以及已跑通合成业务链路的严格摘要接入切片。
各个已经通过的独立评审、实际候选、桌面验证和后续实施状态见
[唯一任务清单](../../changes/add-provider-neutral-project-reporting/tasks.md)。
采集到HTML下载、显式Git定稿、重启与无变化复用已通过本机合成全栈验证。
富文本日常编辑、有界累计delta和显式AI辅助已通过限定本机合成资格；
已保存报告支持派生Markdown/Excel导出；整周/跨周及未定稿gap操作闭环已通过合成验收。
新精简模板与独立审计附件已实现并完成限定验证；
已观察到的交互延迟、完整provider覆盖和正式运行仍未完成。
内部合成能力不等于真实来源或真实模型已经上线。

### 报告读取性能

2026-11-06本机诊断发现：语言切换POST只用0.005秒，返回工作台的GET用39.602秒。
另一轮profile显示169次串行Git进程累计约27.9秒，草稿、定稿与采集列表重复读取并验证
归档。它不是AI翻译耗时，也不能据此推定是代理、安全软件或磁盘故障。

当前实现采用模块内查询/命令分离、请求级固定Git快照、原生批量对象读取和同packet
完整校验复用。草稿与操作记录的本地独立读取最多四个并发任务，Git调用保持串行。
没有跨请求TTL权限缓存、持久索引或AI Base接口修改，原数据Git仍为发布权威。

工作台定稿行只提供实际显示的manifest和commit，不计算隐藏的checkout诊断；
可见采集状态和旧公开publication接口仍按原语义核验工作树。准备、预览、重新准备和
Save成功路径不预加载无关历史；失败页保留原命令、日期、基线和未应用输入。
Save依然不是Finalize，旧页面的缓存不能绕过锁内revision/hash检查。

2026-11-07隔离合成数据的正式20样本：S0工作台p95 2.876s、首请求3.860s，
基线预览p95 2.573s；100份报告、每稿5修订和3票的S1页20为p95 4.105s。
连续20次Save到修订43为p95 1.839s。这是本机限定证据，不是生产SLA。
实际浏览器已验证人工note/颜色/加粗/高亮保存重开、复制、HTML下载和手机布局；
最终10次Ego语言往返因原任务页已消失仍待重新授权，不能据此宣布完整性能包关闭。
当前状态与剩余门槛见[执行计划](../../changes/add-provider-neutral-project-reporting/performance-execution.md)
和[任务](../../changes/add-provider-neutral-project-reporting/tasks.md)。

### 已验证的演示

2026-11-06验收使用真实Django/worker、Git、安装SDK0.2.0a1和Base HTTP，
Jira响应与模型输出均为明确的合成内容。首日三次派发产生三份已接受摘要，
随后六个会议日期均复用；编辑、补全、保存和导出不产生新的模型调用。
模板、逐日颜色/正文、保存冲突、正常重启、跨周seed和未定稿gap均有实际证据，
最终重读七份发布的42个原文件hash一致。详见
[整周交付回执](../../changes/add-provider-neutral-project-reporting/week-delivery.md)。
原单票演示仍作为[历史证据](../../changes/add-provider-neutral-project-reporting/manual-workflow-delivery.json)保留，
不再用旧`.venv`启动迁移后的报告代码。

资格测试服务已正常停止。HTML位于下方数据根的
`evidence/canonical/20261030/report.html`和`evidence/canonical/20261102/report.html`。
再次打开隔离合成应用时，从本仓执行：

```powershell
$run = 'D:\AIGC\scrum_dashboard_validation\full-stack\aa2fb399-4557-4342-b725-8de2dab91aba'
$reportingPython = Join-Path (Get-Location) '.tmp/sdk-020-join-20261105/app-venv/Scripts/python.exe'
& $reportingPython -I scripts/validation/project_full_stack.py start --run-dir $run --lifetime-seconds 1800
```

使用命令成功返回的URL。本次地址为
`http://127.0.0.1:8127/projects/3bc2224e-a6ce-4f85-be43-3c63223a9125/stages/2e4ffd3f-4fb7-46f0-84ea-2b194bfa34d9/reports/`。
合成账号为`SYNTHETIC_ALICE`，密码为`SYNTHETIC_ALICE_PASSWORD`；
它们不是公司凭据。演示应用会话限时1800秒。正常退出：

```powershell
& $reportingPython -I scripts/validation/project_full_stack.py stop --run-dir $run
```

这些命令复用已验证的本机输入、原store与数据根，不是正式安装器。
旧项目配置Demo、真实数据库和正式定时任务没有在本轮迁移或启用。
旧模板继续保留原始摘要与详细审计表。新建模板时优先选择“精简每日站会”或
“精简每周站会”，正文使用有效notes与AR，完整审计通过独立附件获取。
请求耗时也尚未完成优化，不能把功能通过等同于日常使用性能已经合格。

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

2026-11-04作者层已用Milkdown替代过渡textarea编辑，报告叙述与备注在正文就地修改，
工单事实保持只读；不要求用户另找编辑器Agent。
富文本、保存恢复、浏览器复制与整周作者工作流已有合成验收；Outlook接收端仍未验证，
接口及交接清单见[编辑器handoff](../../changes/add-provider-neutral-project-reporting/rich-text-editor-handoff.md)。

报告以可复制到邮件正文的HTML为主，提供每日站会和按日横向对比模板。
已有的阶段工作台列出真实归档采集、草稿和定稿记录，可从已保存来源创建草稿，
编辑会议注释和叙述字段，保存后预览、复制或下载。最后由用户明确选择是否定稿
并提交独立数据Git。实际Ego桌面已完成运行、下载和显式定稿；
新作者层和浏览器复制有独立验证；Outlook粘贴不由浏览器证据代替。
旧的项目/阶段配置Demo不会自动升级到这些源码。

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
已保存报告支持Markdown/Excel派生导出；Excel是文本表格，颜色以HTML/JSON为准。
离线HTML修改回导仍不在当前范围。

#### 最新作者层设计与当前差距

2026-11-03用户进一步确认：只需要所见即所得，不需要Markdown源码模式；
仅输入`#ID`自动补全，无裸ID/URL/快捷键/按钮触发；并要求用户能自由创建报告模板，
由人工或显式AI填写。完整提案见
[Report Authoring V2](../../changes/add-provider-neutral-project-reporting/report-authoring-v2.md)，
[接口与版本](../../changes/add-provider-neutral-project-reporting/report-authoring-contracts.md)、
[错误矩阵](../../changes/add-provider-neutral-project-reporting/report-completion.md)。

当前支持内置daily/weekly模板，以及项目内可视化用户模板库。
业务层管理不可变模板版本、可填槽和受保护数据区；用户不编写Django/Jinja或Markdown源码。
旧`ReportEdit.text`继续按纯文本解释，新作者草稿使用中立富文本fragment。
取消源码UI不取消Markdown导出，HTML仍是邮件主产物。2026-11-03用户已授权在main实施作者层。
schema2 standalone后端已通过专项测试、独立评审及真实临时Git闭环；
模板库人工填写、固定富文本预览和连续性矩阵页面已通过专项HTTP/桌面Chrome及独立评审。
每日准备已接入页面、CLI和原运行器，并完成两天组合验证与限定独立评审；
显式AI填写已通过限定合成资格，详见
[交付回执](../../changes/add-provider-neutral-project-reporting/assist-delivery.md)；完整工作周也已完成独立合成验收。
编辑器现已接入固定Milkdown7.23.0，正文中的叙述/备注可就地编辑，来源事实保持只读。
颜色、高亮、格式链接、任务/表格/代码块、原生撤销和保存重开已通过专项桌面Chrome测试。
网络结果不确定时重试原保存命令，较新的本地输入继续保留；离页/语言切换须明确处理
未保存内容。作者层、`#ID`补全、模板与连续性编辑流程已独立复查，整周JOIN结果见本文开头。
补全只接受正文中明确输入的`#ID`，按Stage的provider和已固定完整成员范围查询；
三种候选为链接ID、加title、再加`@owner`。方向键/Enter、Esc、IME和原生撤销有专项测试。
默认真实读取关闭；生产补全工厂目前接入Jira reader，HSDES正式reader与现场资格仍待补齐。
Jira也必须单独配置经验证的资格。范围外不发上游请求，
权限/身份/时间/额度/旧响应失败不改正文。补全是单票只读，不调用AI或改变来源快照。

Projects -> Report templates提供空白、daily/weekly起始模板、复制、版本保存和归档。
模板设计器可添加固定富文本、填写槽和受控来源块；不能提交任意HTML/CSS或执行代码。
缺少必需来源块的模板可保存为未就绪版本，但不能用于创建报告。
报告固定完整模板快照，后续模板改版/归档不会改动旧报告；归档后禁止新选择。
必填槽可暂时清空保存，但未填完不能Finalize。模板保存失败或版本冲突保留本地内容；
响应丢失重试原请求，保存期间新增的本地内容仍保持未保存状态。

公共`create_authored`可明确选择内置daily/weekly version2或精确用户模板revision/hash，
`save_authored`保存中立富文本、服务端作者时间和revision/hash-CAS。
历史version1模板字节/hash不变，旧草稿首次显式作者保存才升级为version2；
旧保存接口不能把新草稿降回纯文本。空正文和仅颜色修改均保留为修订。
schema2仍使用原六文件定稿和Git writer；恢复前校验完整packet及选中修订hash，
读取历史原文件不重新渲染。后端现在也支持经服务器prepared seed创建的连续日报；
普通浏览器不能上传历史context。补全收据按当前scope proof/身份和唯一引用link验证，
AI收据在Save时核验独立authoring候选，不复用summary结果冒充作者填写。

#### 连续性编辑

用户随后确认的具体报告形态见
[报告连续性架构](../../changes/add-provider-neutral-project-reporting/report-continuity.md)。
连续性后端已通过三日/跨周临时Git链、重复保存、基线冲突、纠错和周视图专项验证及
独立复查。矩阵页面支持当前日note/AR/常驻备注编辑、手动分组与移行、显式系列/周报选择、
只读历史和关联纠错，并通过合成桌面验证。DAILY按钮已有人工和刷新浏览器链证据，
两天实际生成/编辑/补全继承/颜色/归档/同日重放链、整周及跨周合成验收已通过；
这些合成资格不是正式provider/model或无人值守运行资格。

- 一票一行，AR/AR?独立，日期后的`ww45.1(Fixed):`状态只来自当次Jira/HSDES快照。
  人工/AI叙述不改状态，历史无状态快照时不倒填。
- 模板管理组序/初始顺序，同系列已有票位置稳定、新票追加；状态变化不自动挪行。
- 同周累积notes；继承用户已定稿的有效正文、删除结果、文字颜色、高亮与链接，
  不重放原AI文本。fragment v2保存、服务层继承及浏览器整周保真已有对应证据。
- 换周默认带每票最近一次确认更新、全部未结束AR/未确认建议和常驻备注。
  原日期/状态/格式保留，新周另加新note；完整旧周可读，不把精简展示当成删除。
- Source capture、accepted summary、正式作者报告是三种基线，不能由同一last-run代替。
  只有用户明确Finalize且数据Git确认后，才推进下一日报的editorial baseline。
- 默认通过“生成今日草稿”按钮选择日期、模板和基线。Save只保存，切周/GET只读取。
  前日未定稿先提示处理；明确选择旧正式基线继续时记录gap，不丢原稿。
- 定时准备是W7的延后资格，默认关闭；启用后调用同一准备服务和同日去重，
  不自动定稿、发送或回写工单。停机错过不补造日报。

#### 停会与恢复

阶段报告工作台的“会议日历”支持选择一个日期或连续日期范围，标记停会或撤销停会。
日历区分“未记录”“已停会”和“已有报告任务”；没有日报不等于会议已经取消。
日期按系列时区解释，范围包含明确选中的全部日期，不推测哪些日期是工作日。

停会仅记录人工确认的会议安排，不采集工单、不调用AI、不创建空日报或提交数据Git，
也不推进source、accepted summary或editorial基线。撤销停会只恢复生成资格，不补造会议。
已有准备意图、草稿或定稿的日期不能直接覆盖成停会；整个日期范围拒绝，其他日期不变。
未定稿草稿继续通过原来的gap确认处理，不能借停会丢弃人工内容。

恢复时选择真实会议日期及来源，沿用最近一次实际定稿，不要求它是昨天或上周五。
同周保持累计notes；跨一周或多周仍携带最近有效note、未结束AR和启用跨周保留的常驻备注，
原日期、来源状态、删除结果、颜色和链接不变。中间没有会议的日期不产生虚构更新。
最新ticket状态只来自本次明确选择的source capture；长空档不能用旧值冒充新采集。

恢复后的草稿会冻结“Standups skipped”说明，HTML、纯文本、Markdown/Excel和审计文件
都使用同一份快照。后来撤销停会不会反写既有草稿或定稿。整个空周可从会议日历查看，
但生成weekly view仍需选择真实daily publications，不创建虚构的空周报告。

停会记录按命令幂等及日历/系列版本CAS保存；冲突保留输入，需刷新后再提交。
单次最多62天，查询和冻结窗口最多366天，原因最多240字符，每系列最多1,000条变更。
数据库migration `0004_report_meeting_changes`与报告源码一起部署；开发测试仅使用隔离数据库。
接口、并发准入和验收范围见[停会实施包](../../changes/add-provider-neutral-project-reporting/meeting-skips.md)。

#### 手动准备入口

Stage Reports顶部选择报告系列、会议日期和兼容模板版本，先Preview baseline，再选择
Saved capture或Refresh source。采集选项显示UTC截止时间和短ID，来源表保留完整ID与时间。
这些信息通过只读`list_capture_metadata`查询原manifest，旧`list_captures`回执与归档字节不变。
默认Manual only；具备运行和分析能力时可以显式选Changed items。界面禁用不可用的新选择，
服务端在识别已有请求之后检查新工作能力，不因短暂离线阻断既有请求的安全重放。

首次预览不会初始化stage归档。首次明确生成并通过权限、系列、基线和能力校验后，
应用才初始化已配置的数据归档并保留准备意图，再交由原worker采集；没有新的后台队列。
同一会议再次生成返回原工作和实际选择，不创建第二次采集/推理；不同选择明确列为未应用。
未定稿的前序草稿有可打开的链接，必须先定稿或逐项确认跳过，原稿不会被删除。

准备详情显示当前运行/草稿修订、原始及替换关系。对非finalizing且已结束的准备，可以显式
重建为另一个候选；旧人工文字、空值、颜色和链接按已核验规则继承，不匹配内容会提示核对，
不能默认为无损成功。重建仍受该准备绑定的系列策略及兼容模板限制，不自动改绑策略。
已定稿报告只允许关联纠错，不能把历史纠错说成新来源刷新；从已发布页面进入该操作。
定稿同时检查已保存的revision、准备内容绑定、当前有效准备和正式baseline；
刷新准备的内容hash与完整存档hash分别核验，不要求这两个不同含义的值相等。
已被替代的草稿仍保留可读，但不能冒充当前准备完成定稿。

CLI使用同一准备服务。`project_run preview`返回系列策略hash和正式baseline引用，
`prepare`要求显式`--expected-series-policy-hash`，非初始基线还要提供其publication ID、
manifest hash和commit。`--source-mode saved_capture --analysis-mode manual_only`不依赖
Base运行；`--source-mode refresh --execute-local`使用已配置的同一worker同步执行。
`reprepare`要求原准备ID及精确operation/draft修订。`start/status/cancel/resume`保持原格式；
CLI身份仍为可信`local_operator`，不允许通过参数伪造浏览器用户。

```powershell
$reportingPython = Join-Path (Get-Location) '.tmp/sdk-020-join-20261105/app-venv/Scripts/python.exe'
& $reportingPython manage.py project_run preview $ProjectId $StageId --series-id $SeriesId --meeting-date 2026-10-26 --template-id $TemplateId --template-revision 1 --template-revision-hash $TemplateHash
```

以上运行命令只用于已明确配置的环境，不是测试入口；开发验证必须使用
[隔离、no-dotenv验证方式](../../../docs/development/reporting-delivery.md)。
上例是显式会议日期，不会改变系统时钟、工单时间或执行deadline；来源截止时间独立记录，
不能把当前采集冒充该历史日期的真实来源。本轮验证只使用隔离合成数据，没有执行生产数据库
迁移、正式调度、真实来源/付费模型调用或发送。

用户编辑和`#ID`补全属于草稿富文本界面。HTML预览尚可回草稿修改；
最终HTML是静态只读归档，纠错创建关联新草稿，不原地覆盖。
Markdown/plain不承担颜色恢复，Excel按受验证能力导出；JSON/HTML保留完整格式。
格式/历史/保存不完整时明确失败，不能用静默降纯文本制造成功。

#### 下载和导出

**精简正文与完整审计。** 模板库的“精简每日站会 / Concise daily standup”和
“精简每周站会 / Concise weekly standup”是新建报告的首选。
每张票一行，正文列为Ticket、Updates、AR；Updates按原日期累计有效人工/已接受内容，
状态前缀来自provider，未结束AR与常驻备注保留，显式空白不恢复原AI句子。
简短coverage仍显示partial/pending和已知限制，不因精简隐藏未处理票。
用户可添加固定内容或填写槽；编辑器Save会保留精简呈现版本。

旧模板不自动升级，旧HTML不重新渲染。新模板使用schema2的
`presentation_profile="standup/1"`和`template-document/2`；
未设置profile的旧版本继续使用`template-document/1`及原hash规则。
切换报告系列默认模板须显式保存新系列策略版本，不能只改本地模板选择。

定稿页面的导出菜单增加“完整审计附件（ZIP）”。它包含该次定稿的六个原始文件、
可读`audit.html`和`audit-manifest.json`校验清单。附件独立于精简正文，不调用模型、
来源、Save或Finalize，不修改Git历史；同一原稿重复下载的字节稳定。
正文HTML/plain/Markdown/Excel和复制仍基于保存/定稿版本。草稿不提供审计ZIP，
因为尚未形成不可变publication；有未保存修改时仍禁止复制/定稿与草稿导出。
附件缺失、损坏、无权限或超过32 MiB上限会明确失败，不返回截断包。

实现接口和版本边界见[呈现设计](../../changes/add-provider-neutral-project-reporting/standup-presentation.md)，
实际资格与限制见[呈现交付](../../changes/add-provider-neutral-project-reporting/presentation-delivery.md)。

HTML和纯文本下载读取已保存修订；已发布报告读取原六文件中的原始字节。
新的“导出”控件提供Markdown和Excel文本表格。它们是有明确来源hash及
`report-derived/1`版本的派生文件，不添加或改写旧publication，也不调用模型或刷新工单。
已发布导出只转换已验证的原HTML，不调用新模板renderer重建历史。

Markdown保留工单行、链接、文字格式及单元格内逐日换行，不承诺颜色/高亮。
Excel保留表格行列、单元格换行、完整报告文字和Links清单；单元格单一链接可点击。
Excel首版不保留富文本颜色/高亮/混合字形，Information页和导出描述明确标注，
不能用它恢复原编辑器内容。公式形状的文字保持字符串，数字型ticket ID不变成数值。

源HTML最多16MiB，派生文件最多32MiB，最多64表、100000单元格/文本行。
Excel单元格超过32767个UTF-16单元或包含XML非法控制字符时拒绝，绝不截断。
Markdown嵌套表及不支持结构明确失败；原HTML仍可下载。
未保存、保存中或保存结果未确认时新导出控件不可用，成功保存后使用确认的修订。
这不改变原HTML下载的回退用途。库缺失只影响新导出，手工编辑和原下载继续可用。

实际接口和资格见[导出合同](../../changes/add-provider-neutral-project-reporting/export-execution.md)
及[交付回执](../../changes/add-provider-neutral-project-reporting/export-delivery.md)。
浏览器Clipboard API的HTML/纯文本读回已验证，不等于Outlook接收端已通过。

已完成的端到端验收覆盖人工增删/着色/补全、保存重开、定稿和新周继承；
独立ASSIST样例覆盖AI候选采纳、人工改动和翌日来源保留。
完整RA67合成工作周每天source内容固定、人工note/颜色不同，已保留每日截图、
原报告/hash与调用计数。确切范围见本文开头和整周交付回执，不代表真实来源已经上线。
合成开发验证不启用正式调度、读取新真实工单或调用付费模型。

“不在scope”的默认含义是“不在该报告pinned capture的完整成员快照中”；
缺少完整性证明时提示未确认而不是范围外，不查询全站来区分错ID和别的项目工单。
已知成员上游404统一提示不存在或当前账号无权访问，owner未指派只禁用第三种格式。
新查询不修改来源快照；最新字段附独立观察时间。Jira由Stage scope/profile路由，
HSDES直接由Stage的saved-query profile路由，不伪造Jira scope。

AI填写是单独的候选操作，不是模板渲染或生成报告的默认副作用。
手工编辑不依赖Base；候选先审阅再保存，继续沿原显式定稿/Git/权限边界。
独立`project-reporting.authoring@1`使用SDK0.2.0a1和原a2的`task-run/1` wire；
不改变summary@review-1或把合成资格当成正式模型资格。实际接口和限定证据见
[ASSIST合同](../../changes/add-provider-neutral-project-reporting/assist-execution.md)。
原模板设计器backlog只提升为受控block/slot模板库；任意脚本/CSS/像素布局引擎仍非本次范围。

#### 显式AI辅助

先保存草稿并选择当前可编辑正文，再打开AI assist，填写要求并显式Generate。
浮窗显示候选，Apply只做一次可撤销的本地替换；Save才接受来源，Finalize才推进正式日报基线。
此按钮与`#ID`只读补全是不同操作；编辑、模板、补全、保存和渲染不请求模型。
模板`ai_optional`槽、当前日note及允许的叙述/备注目标可申请候选；
历史note、固定来源数据、源状态、行序和AR跟踪状态不可由AI改写。

- 生成期间改文字、颜色或选择位置会使旧候选不可覆盖当前目标。原文不会因失败而丢失。
- 未保存的修改必须先保存；AI不可用或profile缺失时，手工编辑和保存仍可使用。
- 关闭浮窗/刷新页面不取消运行。重开可以读取原候选或按原key查询未确认请求，不自动重新生成。
- Reject / cancel先记录本地拒绝；晚到结果不能应用。未确认远端结束时仍显示原请求状态。
- 到原期限或观察次数上限，停止自动观察，不重置key、deadline或费用。
  未确认执行结束前不建立竞争请求；仍可继续手工编辑。
- Apply后尚未保存就手改时，临时AI凭证被清除，按人工内容保存。已保存的AI内容再被人工修改，
  则保留其AI来源引用并标注人工修改；归档和翌日继承使用最终有效富文本，不重放原候选。

默认没有运行资格，不会创建Base客户端。运维须在Django settings中显式设置
`METRICS_REPORT_ASSIST_FACTORY`为服务端callable或导入路径，接口为
`factory(*, draft_service, contract) -> ReportAssistService`。该factory提供经过资格验证的
backend/grant与SDK client factory；浏览器不能提交endpoint、token或profile。
普通`.env`键不会自动注册此factory，也不会因已有summary grant而自动授权authoring。
缺失/损坏的authoring bundle只阻断AI，不阻断人工草稿。

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
首次完整输入、无变化复用及有界累计delta已贯通，完整大输入/来源能力与正式资格仍未完成。
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
`requirements-ai-task.txt`，当前报告验证选择SDK0.2.0a1及原a2的21文件pack。
保留主`.venv`仍是旧SDK0.1.0a2，不用于迁移后的报告验证。选择的环境和SDK接入资格
见[验证指南](../../../docs/development/reporting-delivery.md)，不等于真实provider/model已启用。
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

当前切片支持首次完整输入、100版本/64证据/65536字节以内的累计delta与无变化复用。
累计输入从最后已接受摘要到目标采集保留中间版本，新增后删除或变更后恢复也不丢失；
接受版本递增，报告读取重新核验同一输入与前序接受记录。原始source hash不包含coverage，
所以每个保留版本都须另查完整性；partial/access-lost或中间A→B→A不能算无变化。
超长/超限多版本/未支持附件与依赖不会静默裁剪；完整索引、导入及大输入仍属后续W4/W5工作。
旧已接受尝试不阻断新输入；未决提交保留原key/deadline/预算，已验证终态才允许不同输入。
有界增量的SDK0.2真实本地HTTP与报告读取证据见
[delta-core](../../changes/add-provider-neutral-project-reporting/delta-core.md)。
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

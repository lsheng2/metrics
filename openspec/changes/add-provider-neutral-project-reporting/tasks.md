# Provider-Neutral Project Reporting Execution Plan

> For agentic workers: execute this OpenSpec tasks file with Superpowers TDD and bounded validation.
> Do not execute parent summaries as one giant task.

Goal: user-defined projects/stages for Jira and HSD-ES, followed by generic project reporting.
Architecture: Dashboard host, project_management business owner, existing provider APIs, shared AI Base.
Tech stack: current Python3.13/Django6.0.7, Bulma/htmx, ORM/SQLite, pytest.
Spec: specs/project-reporting/spec.md and design.md.
profile_source: repo-local (.github/skills/lsheng2-dag-based-planning/templates/project-profile.md).
agent_routing_mode: multiagent-configured. Coordinator owns plan/integration; one implementation
agent owns the active source packet; independent reviews cover completed behavior boundaries.
Debugger skipped unless a distinct failure needs diagnosis. No parallel source writers.
Task path overrides older profile default openspec/docs: this change's status is maintained only here.
Current cross-repo execution entry: execution-handoff.md. The C0 packet is sdk-intake-plan.md;
base and Dashboard keep separate canonical implementation ledgers.

## Current Execution

2026-11-05用户已明确恢复一个有界窗口：补齐SDK新计划及集成后spec，
先做scoped commit/push，再执行集成点前工作，停在`IP-SDK020-READY`。
本轮唯一实施协调者在Dashboard `main`；Base仓库只读，不恢复旧chiplet T12。

当前节点为`SDK020.PLAN.R`，随后`ARTIFACT -> APP -> PRE -> REPLAN`。
精确API/版本/拒绝路径/命令在[sdk-020-integration.md](sdk-020-integration.md)；
集成后的真实HTTP、DAILY、ASSIST、周模拟与出口在
[sdk-020-post-integration.md](sdk-020-post-integration.md)。
只按既有accepted scope做补充，不重开SDK中立性讨论或FZ-01。

停止点前使用独立`SDK 0.2.0a1`安装target和短命隔离测试进程，原a2 pack不变。
证据根`.tmp/sdk-020-preintegration-20261105/`。不升级主`.venv`，
不启动Base HTTP/联合业务流程，不触碰既有8017服务。
已有作者层实现是未提交WIP，原Scope/config/main.css等改动不纳入本批代码提交。
本轮规格提交不表示这些未提交代码已发布；历史限定验证只按有效依赖复用。
达到停止点后记录实际测试/制品/源码身份并等待用户明确释放，不执行`SDK020.JOIN`。

## Earlier Pause Checkpoint

2026-11-05 10:28 +08:00，用户明确要求安全暂停并做执行复盘。
此前“执行到底”和完整工作周测试授权暂停适用；本轮只读取证据、维护暂停状态和复盘，
不恢复源码实施、产品测试、服务启动或外部调用。恢复须以用户新的明确指令为准。

冻结位置：Dashboard `main`，HEAD `5d83933dc3d3c4f1673ec680c5ee2d03da8f9aed`；
作者层改动仍未commit/push，其他Scope/config/main.css改动保持不动。
唯一证据根`.tmp/authoring-main-20261103/`，本文件仍是唯一任务状态。

已关闭CONTENT、EDIT、REFERENCES、TEMPLATES、HISTORY的限定合成资格。
DAILY后端与C界面已有分组验证；最后独立评审
`daily-ui-review/r1/review.md`在冻结39路径内未发现P0-P3问题。
暂停复盘只读核对这39个工作树文件与manifest一致，没有重新执行测试。
该评审不覆盖整周、ASSIST、继承reference的完整每日浏览器链或外部资格；
DAILY总节点保持未勾选，ASSIST与完整JOIN尚未实施/执行。

安全收尾：协调者测试会话均已退出；最后只读reviewer确认无活动会话并已关闭。
当前goal工具无活动目标。本轮无所属测试进程；11月2日已存在的8017服务
（PID83404/50700）不属于本轮，未停止，不宣称全机无服务。

复盘与下一阶段建议：
[2026-11-05作者层执行复盘](../../../../chiplet_programmgr/docs/development/2026-11-05-report-authoring-postmortem.md)。
恢复后先复用已冻结证据核对DAILY尚缺的消费者，不重开已关闭的全包评审；
后续仍欠ASSIST、导出/复制、2026-10-26..30及11-02整周JOIN、最终R/REPLAN。
这些是暂停交接和建议，不是新执行授权或另一套任务清单。

## Last Pre-Pause Checkpoint (Historical)

2026-11-05，继续用户已授权的作者层实施及完整合成工作周测试，直接Dashboard `main`。
代码HEAD仍为`5d83933`，本轮未commit/push；他人Scope/config/main.css改动保留。
所有子代理固定GPT-5.5/xhigh，一名生产writer。证据根`.tmp/authoring-main-20261103/`。

已关闭叶：CONTENT、EDIT、REFERENCES、TEMPLATES、HISTORY（各自限定合成资格）。
HISTORY最终来源：`history-core-review/fix3/review.md`、
`history-persistence-review/{fix4,matrix-final}/review.md`、`history-ui-review/final/review.md`。
编辑器固定Milkdown7.23.0，本地bundle`f537a725...`；最后B2修复20browser126.40s、
Node10及最终直接反例通过。完整周JOIN仍没有执行，不能把这些结果称为全功能验收。

DAILY A与worker首切片已独立通过：
`daily-core-review/final/review.md`、`daily-worker-review/fix1/review.md`。
reprepare journal/active authority通过`daily-reprepare-review/journal-final/review.md`；
旧内部prepared兼容，受控binding缺失/降级/失活、事件链CAS及采集后检查均有直接证据。

preservation业务与最后schema边界已关闭，最终依据
`daily-preservation-review/schema-enums-final/review.md`；报告为`daily-preservation-report.md`。
协调者修正缺字段fixture及两个enum类型守卫：RED8失败/60通过1.52s，GREEN68通过1.03s；
两文件配置size与whitespace通过。旧schema-final错误归属的review保留，不再作为未决项。
当前唯一生产writer为协调者，接续`daily-ui-brief.md`已有WIP。
Gibbs最后session94157已结束；owner与空capture测试构造已修。
首条Chrome真实已存capture/纯人工流程通过152.65s：生成、红色note、Save/reopen、
Finalize后才推进次日baseline，SDK client创建为0。修复实际空note hash被模板输出为
字符串None的问题，原失败与HTTP响应均保留；表单8反例和只读准备API2用例也通过。
当前补pending gap/保留错误输入、详情与reprepare、稳定runtime接线、CLI/JSON/locale；
尚未独立review DAILY，不把首链通过当作整个DAILY完成。
08:28后检查：pending/详情10tests178.68s、runtime去重2tests20.99s、
CLI/首次只读3tests94.02s、注册worker的真实Chrome刷新链155.04s已通过。
已定稿manual关联纠错与离线saved-capture重建2tests179.20s通过；
UI重放优先级/损坏记录等25tests91.93s通过。原失败均保留。
继续DAILY收口：模式切换/未资格AI禁用、changed_items重建、首次无archive的完整准备、
严格JSON/CSRF/locale、最终浏览器与独立review。新增反例先行，暂不派发ASSIST/JOIN。
当前最后RED：mode controls、changed-items reprepare、control schema bool/float；
不把已有局部绿色当作这些新增边界完成。无活动子代理。
基线保留于`daily-ui-base/`，全部结果沿`daily-ui-report.md`。
JOIN依赖只读核验通过：固定Base844文件、SDK0.1.0a2原wheel；
未启动服务/模型。无并行源码writer，DAILY尚未勾选。
随后ASSIST、JOIN、最终R/REPLAN；保留数据/真实资格不自动扩大。
各brief是本tasks子步骤说明，不维护独立完成状态。

JOIN必须执行2026-10-26..30和11-02换周；同源三票、逐日不同人工note/颜色，
真实app/ORM/编辑器/数据Git、首日installedSDK+localBaseHTTP synthetic executor，
后续无变化零新AI调用，保存/重开/定稿/正常重启及逐日证据，详见validation第7节。
模拟日期不修改系统时钟或真实票据时间。真实provider/paidmodel、生产DB迁移、
正式调度和发送未启用；Outlook/live资格另列。无新正式常驻服务。
测试只用无dotenv隔离入口`scripts/validation/run_report_authoring_tests.py`和显式路径；
现存8017 runserver不属于本任务测试，不控制；ownedpytest按原session有界收尾。

## Earlier Authoring Execution

2026-11-04：用户已授权直接在main完成作者层实施与测试；工作树基线5d83933，
保留其他agent的Scope/config dirty文件；本轮尚未commit/push。
CONTENT/EDIT/REFERENCES已完成各自合成资格，不代表整个作者流程通过。
证据根`.tmp/authoring-main-20261103/`，当前子代理固定GPT-5.5/xhigh。
REFERENCES最终依据为`references-backend-review/fix3/review.md`与
`references-capture-review/review.md`；旧UI发现和失败截图保留，不是当前未决清单。
最后completion10browser70.57s、runtime5browser29.60s及Node9通过。

TEMPLATES的standalone主链已通过合成资格，后续intake新发现固定content预览丢格式，
总节点重新打开，修复明确归入HISTORY B的pinned body消费者接线；core不依赖该显示路径。
A/B依据`templates-library-review/fix2/review.md`、`templates-render-review/fix1/review.md`；
C依据`templates-ui-review/fix2/review.md`最终PASS，原8项及保存/销毁竞态已关闭。
最后browser5tests47.06s、受影响20tests11.75s（含共享locale）及Node10通过。
独立追加的paint浏览器反例1test8.63s确认readonly表格不覆盖子节点人工颜色；
原CSS疑点经schema/renderer复核撤回，未为该疑点改变生产CSS。
源码/截图证据见`templates-ui-report.md`和`template-report-fix2-contrast-desktop.png`；
原失败截图保留。协调者26路径物理size检查15个适用源码PASS。

HISTORY A core已通过独立复查，最终`history-core-review/fix3/review.md`，
直接33tests3.46s、前fix2受影响55tests4.69s；完整证据`history-core-report.md`。
错误baseline、日期重放、summary身份、AR去重/关联、跨周和seed引用问题均已闭环；
来源fixture旧协议修复后13tests42.21s通过，原失败仍保留。
HISTORY B1后端已通过限定独立复查，最终证据为
`history-persistence-review/fix4/review.md`及`matrix-final/review.md`。
三日/跨周真实临时Git、旧六文件不变、恢复CAS、同/旧日纠错、周视图精确选版及
AR后日解决保留均有证据，完整命令/失败/候选见`history-persistence-report.md`。
最后action merge经无dotenv入口4tests67.28s，matrix/renderer7tests0.61s，
协调者对应5文件sizePASS；未以早期historical_export豁免版本作为通过结论。
原失败和每轮frozen diff仍保留，普通daily来源/归属/基线保护未关闭。

B2已通过独立review，最终`history-ui-review/final/review.md`，
原period语义/显式series/子editor销毁及fallback标签问题关闭。
20browser126.40s、continuity completion2tests57.03s、Node10及最终两条直接test通过；
完整证据`history-ui-report.md`，后续模板richpreview重开项也关闭。
DAILY A已通过独立review，最终`daily-core-review/final/review.md`；
前两轮剩余问题已修复，最终route reverse/resolve+终态重放2tests44.56s，
直接service/store/link19tests156.91s、受影响76tests177.39s及原run9tests证据保留。
当前窗口：DAILY B后端，按`daily-worker-brief.md`接原worker版本化刷新/reprepare，
先public service/worker，再HTTP/CLI/按钮。每个子包仍只维护本DAILY一个节点。
22:35约60分钟检查：Popper为唯一writer，run_daily_values/project_run_daily_worker/
report_preparation_worker等WIP已落地，但未收到实际firstchain绿色；不宣称接口已验收。
协调者已要求先真实UserTemplate publicprepare->manual refresh worker->oneauthoreddraft，
避免只用旧builtin测试模板放行新协议；UI/ASSIST/JOIN不启动。继续该最小边界并取具体结果，
不为等待另派并行writer。原源码基线`daily-worker-base/`保留。
后续worker首切片通过`daily-worker-review/fix1/review.md`：original/effective绑定、
采集后取消及request/seed/draftselection/draft恢复验证已闭环，16pathsizePASS。
store7tests0.61s、cancel29.98s、11recovery152.29s、9compat/public55.94s；
完整report为`daily-worker-report.md`。Popper/Parfit已关闭，源码无常驻服务。
当前转`daily-reprepare-brief.md`补终态重建/active slot替换，不把已定稿同选项shell当完整重建。
UI/CLI/继承reference可编辑资格、ASSIST/JOIN仍未执行。
2026-11-05当前：Epicurus唯一writer，reprepare首链5tests282.86s仅部分证据；
Hume在`daily-reprepare-review/review.md`指出adopted-intent不同请求误绑定等P0/P1。
随后journal/admission直接18tests272.32s，但parent CAS/故障位置和source超限未闭环，
不能冻结为完成。当前按`daily-reprepare-fix.md`先收口journal/active authority，
新server-only prepared authority和draft immutable binding已写入continuity同设计；
旧internal prepared流程须兼容，受控missing/corrupt/downgrade必须拒绝。
不使用扫描全部seed或missingintent放行。完整人工preservation仍待后续子包。
原framework服务8017是已存在非本次测试进程，不控制/停止；ownedpytest均按原session收尾。
reprepare journal/authority已由`daily-reprepare-review/journal-final/review.md`闭环，
event-chain parentCAS和capture后active checkpoints4tests103.76s、16受影响128.40s；
对应5文件size通过。原writer/reviewer关闭。
当前`daily-preservation-brief.md`仅做完整人工内容/refresh后续保存保留与dispatch恢复，
不再重开已关闭journal；DAILY UI/CLI与ASSIST/JOIN仍未开始。未最终验收reprepare或DAILY。
仍一名生产writer；未启动ASSIST/JOIN，不把历史编辑验收当每日生成或整周完成。
原main无commit/push。
DAILY A完整初稿/修复报告分别`daily-core-report.md`、`daily-core-fix-report.md`、
`daily-core-fix2-report.md`。A通过不代表刷新/手动按钮/整周已实现或live资格已获准。
15:44 B2 checkpoint：Rawls为唯一writer；连续模板->series隔离browser通过，
colored current note保存/重开15.61s，visible persistent/action/move原子保存12.29s，
精确证据`history-ui-report.md`。首次matrix截图发现ticket/prefix/AR低对比和当日note重复，
当前定点修display消费者；原截图`history-ui-colored-matrix-reopen.png`保留。
历史readonly、period/linked入口、系列policy/locale/反例仍待完成，未勾总节点。
Base固定副本844files与installedSDK批准wheel已只读复核；未启动Base或模型。
16:02 B2截图intake：虽然已有DOM绿色，matrix ticket/AR仍白字白底且current前缀缺失。
根因是contrast测试只查一层透明背景、缺元素时返回7冒充通过；当前暂停扩展其他UI，
先修实际背景递归/必需前缀断言和局部样式，不放宽阈值。旧截图文件被writer覆盖，
不能继续声称该文件保存首次失败；首次图仍在工具对话，后续截图必须独立文件名。
period/linked页面已有窄测试，但尚无最终B2review。编码未停整任务，只收窄当前交付问题。
17:32更新：必需prefix+实际背景contrast已修并由协调者查看新截图
`history-ui-colored-matrix-contrast-fixed.png`确认票号/来源前缀可见、无当日重复body。
12页面测试拆分后92.38s通过；fixed template rich preview9.20s，
currentnote真实#endpoint/receipt/save14.75s及history/weekly前置拒绝已通过。
既有persistent编辑/清空/carry、report-level新增与AR正文已获可见控件证据；
Chinese labels/stale policy10.89s通过。Rawls继续B2剩余weekly选择创建、policy/lifecycle/
打包门禁；未做最终独立review，HISTORY/TEMPLATES总节点仍未勾。
后续DAILY还须覆盖继承persistent中的#link再次编辑，不以只读历史保存替代可编辑保真。
DAILY/ASSIST/JOIN仍未实施。DAILY worker版本化readiness已准备；
全部沿本文件原节点，无第二任务状态。
ASSIST的独立就绪复核见`assist-readiness.md`，仅证明独立profile/SDK/存储边界可实施，
不是AI功能已经通过；已核对固定Base副本的profiles/grants注入签名。
09:04阶段检查：本恢复窗口关闭C保存/销毁反例与下游readiness，未执行整周。
颜色疑点用一次实际保存/渲染反例裁决，不换编辑器或重跑全栈。
恢复核对发现模板C只提供standalone v1 starter；HISTORY集成负责新增可视化v2
连续日报/周报starter和matrix选项，使用户能直接创建合法series，不要求raw JSON。
这是既定v2模板消费者接线，不更改旧模板版本或hash。

JOIN必须执行validation第7节的完整合成周（2026-10-26..30及11-02换周）：
同源三票、每日不同人工note/颜色、保存重开/定稿/周中正常重启、逐日证据。
首日走已安装SDK/真实本地BaseHTTP与synthetic executor；后续无变化不新增AI调用。
尚未执行，不预报通过。真provider/model及Outlook资格与合成JOIN分别报告。
真实provider/model、生产DB迁移、正式调度和发送均未启用；合成检验不扩授权。
协调者8137演示进程已验证归属并停止；测试server按用例创建/关闭，无正式常驻服务。
已落地无dotenv入口`scripts/validation/run_report_authoring_tests.py`配显式目标。
原用户Scope两个超限文件仍未动；每个任务实际改动集合单独门禁。

## Earlier Authoring Checkpoints

2026-11-03用户已明确批准从规格进入实施，并直接在本地main执行。
本地main已从dce92c9快进至已集成基线5d83933，29个原dirty路径保持不变，
未推送origin/main。下方“仅文档/未恢复”描述是此前窗口历史，不覆盖本次实施授权。
本窗口使用原W6.AUTHOR ledger；CONTENT后端由一名实现者写入，
协调者负责组件资格/文档与后续集成，子代理均GPT-5.5/xhigh。
真实provider/model、生产DB迁移、调度激活和发送仍按独立授权执行。
当前最小动作：CONTENT已关闭，进入EDIT真实富文本页面。19:07起的首个约60分钟检查点
选择先收口后端，修复两轮后Ohm的`content-review-r3/review.md`确认最后问题关闭。
修复1受影响67tests/166.37s，修复2所选10tests/10.61s；
协调者新增实际Git schema2闭环1test/67.26s、物理size23文件PASS。
证据位于`.tmp/authoring-main-20261103/`；没有provider/model调用或生产迁移。
EDIT由Kant单写入；后续正文就地编辑和浏览器保存200/颜色重开/409保留输入已获得窄证据，
但Noether的`edit-review-r1/review.md`确认JSON脚本嵌入、action丢失、多段paste、
保存中编辑/离页保护、未聚焦格式及打包/locale/维护测试缺口。
当前执行`edit-fix-r1.md`，先处理数据与安全反例再完善adapter，不勾EDIT或派发REFERENCES。
协调者实际size显示两个Python文件418/411，需职责拆分而非沿用报告的非空行计数。
原浏览器失败记录与窄绿色分别保留，不以旧测试代表新修复/全功能验收。
EDIT fix1的safe JSON/action保留/多段paste/预聚焦格式/打包locale已获得复查支持，
16tests/3subtests含2条维护浏览器链通过；James在`edit-review-r2/review.md`确认其余缺口。
当前fix2只关闭uncertain-save局部B、inline替换/paint、pending mount、task/table与实际size，
并补相应维护浏览器反例。原型运行器已停止；不因已有窄绿色推进下一叶。
后续检查发现原writer报告与未改动的源码不符，已停止并保留全部WIP，不再等价续跑大包。
EDIT内部按两份串行子包收口：`edit-lifecycle-brief.md`与`edit-runtime-brief.md`，
仍只有本节点一个状态。Goodall完成生命周期4条真实browser反例31.13s，
受影响16tests/3subtests26.84s，Node6及metadata consumer通过；
独立Lagrange已在`edit-lifecycle-review/final/review.md`关闭最后语言确认问题，
生命周期5条browser36.02s、相关Node通过。2026-11-04继续原授权，Dalton单写入
`edit-runtime-brief.md`原生编辑器子包；不把午夜或用户追加整周验收误作新业务运行。
生命周期通过不代表EDIT全部关闭，native inline/paint/history/controls仍须实际验证。
2026-11-04 EDIT关闭：Dalton原生runtime4browser22.09s通过，
Erdos在`edit-runtime-review/final/review.md`关闭hardbreak最后问题；生命周期5browser
及受影响Node/HTTP/浏览器证据见同目录reports。协调者actualsize13文件PASS。
native history为唯一undo authority，原adapter临时snapshot undo已移除；bundle固定
`6b99202919a6a4b407dd7893392edca88e92b6facbb660f52af016ee7c4bffcd`。
保留两项非阻断后续检查：工具栏state-disabled、CommonMark输入规则的未覆盖边界，
在JOIN/REFERENCES受影响时验证；不宣称所有RA或整周已通过。
当前下一叶REFERENCES，单写入者消费已复核receipt/admission契约；无真实资格自动启用。
REFERENCES首候选52tests/9subtests94.59s为部分证据；Lovelace复核发现8组缺口，
位于`references-review-r1/review.md`。Mencius先按`references-backend-fix.md`修后端
锁/额度/成员证明/当前Jira身份/严格HTTP/publicAPI，再按独立UI子包修定位与事件。
不勾REFERENCES；当前reported10文件size漏掉原report_sources410，已要求全触及集合验证。
Ruling: Jira重命名返回新current_key合法，但stable_id必须与scope成员精确相同，
不能因为key相同就接受另一个stable_id；这是原canonical current_key语义，不要求旧key永久不变。
代价是旧ID不再匹配时需当前scope别名处理，不扩大来源访问或隐式换票。
协调者干净合成草稿Chrome检查`clean-editor.json/png`确认16区域、无textarea/横向溢出、
来源Fixed/In Analysis、复制payload就绪；同时发现本地Iconoir缺glyph和白底标题低对比，
由REFERENCES当前单writer做定点资产/可读性修复，不改用户dirty main.css，不扩全局美化。
Ego24完成DOM检查后关闭；其截图超时单列不冒充截图通过，也未自动升级Ego0.6.2.5。
当前只读演示helper端口8137，launcher56128/child32744归协调者，
后续代码变化需按同候选正常重启；它不是JOIN或整周资格。
后续REFERENCES候选演进前已核对上述两进程command并停止，避免继续展示旧导入组合；
不是产品停止/恢复资格测试，未删除任何演示数据。新UI浏览器验收用独立测试server。
REFERENCES backendfix1的15tests37.17s及14tests/9subtests3.78s已记录，
Hegel在`references-backend-review/`复核冻结源码；Mencius仅写不相交的UI子包，
不得改待review后端。UI工作要求见`references-ui-fix.md`，仍未勾本节点。
REFERENCES backend闭环：Hegel在`references-backend-review/fix3/review.md`确认PASS。
fix2的27tests/4subtests89.34s及fix3固定membership5tests/2subtests107.88s为对应证据；
原准入hash/限额、同commit pages/object、currentprincipal、非draft拒绝及旧receipt校验已修。
UI仍有3条失败见`references-ui-report.md`，Mencius继续仅UI收口；
不要将backend通过当作浮窗/整个REFERENCES完成。
后续UI5browser41.67s通过，Mendel复查关闭原定位/销毁，指出Esc/caret重查、
same-text重新capture、过长ID静默丢弃、options集合校验、locale和旧请求abort缺口。
当前writer仅修此6组UI，backend维持已审冻结。记录在`references-ui-review/review.md`；
没有勾REFERENCES，尚未开始TEMPLATES产品代码。
可复用无dotenv测试入口已纳入`scripts/validation/run_report_authoring_tests.py`；
协调者实际size7文件PASS，原用户Scope两个超限文件仍未动。

2026-11-03最新要求：只保留WYSIWYG，`#ID`为唯一工单补全触发；
用户可创建模板并人工或显式AI填写，需要错误/架构/API/执行细节。
本窗口只整理OpenSpec，不实施、测试产品或重新启动已停止服务。
统一设计见[Report Authoring V2](report-authoring-v2.md)，唯一新执行清单是
[W6.AUTHOR](#w6-authoring-v2)。不再依赖用户另请一个编辑器Agent；
一个协调者可依明确文件边界统一交付，独立review仍保留。
W6.HTML.UI/R和新作者功能继续未完成；保留既有后台/非编辑工作流证据，
旧绿色不代表schema2、用户模板、工单补全或AI填写已验收。
后续确认的逐票/AR/来源状态前缀、稳定顺序、人工颜色保留与跨日累计，
以及跨周seed/未结束AR、手动每日准备/默认禁用定时，已细化为
[report continuity](report-continuity.md)。新增HISTORY/DAILY叶和RA41-72；
只有规格更新，无产品节点完成。W7.SCHEDULE是延后资格，不默认启用。

Current workflow window is complete at a safe handoff. W7.E2E.QUALIFY is closed
only for the user-approved non-editor synthetic workflow. No broader W3-W7
wave starts from this receipt. The next authoring work is the proposed W6.AUTHOR
lane, not an automatic continuation of that workflow or a second agent dependency.
Authoritative outcome: [manual-workflow-delivery](manual-workflow-delivery.json).
Run7b1f3cc9-7fb4-4bf3-acdc-f4dbb5c4b510 retains its original store and all failures.
Actual capture/SDK/Base HTTP/accepted summary/HTML download/browser-confirmed
Git publication passed. After normal stop/restart, a fresh capture returned
no_work with the original summary bytes, no new attempt and no new Base Run.
Actual desktop auto-refresh reached draft_ready and stopped polling.
Original HTML/plain downloads and6old data fingerprints remained identical.
Final stop0632f195-3035-4a82-82d7-a3c795b960b6 is normal for both services.
Both subagents used by this execution are closed; the standalone report is kept in the
browser for inspection. The qualification run made no real provider/model calls,
sent no email and did not publish code or enable official scheduling.
The user's subsequent scoped code commit/push is a separate source-publication
operation, preserving unrelated Scope Config/CSS and model-preference changes.
Editor/clipboard/Outlook acceptance remains open.
The dated paragraphs below retain earlier checkpoints, not current next actions.

2026-11-02 user explicitly resumed continuous execution through an end-to-end
full-stack flow, after confirming Outlook and HTML/report requirements.
Current window: W7.E2E.QUALIFY launcher implementation, then actual full-stack run.
QUALIFY first9file asset fix passed Turing's scoped review;15tests59.19s,
actualsize9PASS. Prepared root is
D:/AIGC/scrum_dashboard_validation/full-stack/7b1f3cc9-7fb4-4bf3-acdc-f4dbb5c4b510.
Six old W2/W5 fingerprints are retained in its evidence/preserved-data-before.json.
First actual start failed before app/model dispatch: SLE had registered wrapper
provenance but no listener PID; Base used a distinct Python worker PID.
Automatic cleanup stopped the new Base; both recorded PIDs were then absent,
Base exit0 and dispatch0. Do not rerun equivalent starts.
Darwin now fixes live W5-strength worker proof and matching exit receipt
handling, with null-listener/parent/command tests before scoped recheck.
Evidence: qualify-review-r1/native-start-01.md and the preserved failure receipt.
HOST is closed after Anscombe's round3 recheck. Final37HOST/UI/language tests
30.63s cover round1; test split18runtime/command tests20.34s and HX sequence
1test6.69s cover final changes. Coordinator's actual size25PASS uses physical
line counts, not the implementer's earlier nonblank counts.
All dynamic run content is inside one polling fragment. Command failures and
unresolved drain exit nonzero with the structured stop observation.
Evidence: host-implementation.md and host-review-r1/round3-review.md.
No actual server/provider/model/browser business flow has run in this wave yet.
W7.E2E.RUN is closed after Hume's scoped round2 review: original five findings
and new terminal-idempotence finding addressed. RUN25tests50.06s and
affected44tests/1deselected50.92s cover round1; shared control-window19tests/
1deselected18.69s and terminal-counterexample5tests19.68s cover final changes.
Size18 passed, then changed4 passed. This is not HOST or actual BaseHTTP/browser
qualification. Evidence: run-implementation.md and run-review-r1/round2-review.md.
Ramanujan closed the HOST additions readiness check: exact startup discovery,
no-create absent-stage read, long SLE stop test and correct historical revision
link/edition behavior. Evidence: .tmp/html-reports/host-additions-review.md.
QUALIFY exact CLI/fixture/environment/receipt contract is in
full-stack-qualification-packet.md. Popper closed its three source-specific
readiness findings (app-only restart, true environment allowlist, strict source
request guard). Evidence: .tmp/html-reports/qualification-plan-review.md.
QUALIFY implementation still waits for HOST's actual source gate.
HOST first candidate18runtime/UI tests23.69s and15report/language tests8.98s
passed, size24PASS. Anscombe found3Important gaps in abnormal command exit,
locked/shared-bounded startup discovery and htmx fragment shape. Noether owns
one scoped repair plus the named command/corruption/fragment counterexamples.
Evidence: host-implementation.md and host-review-r1/review.md.
Environment only: Ego task16 disappeared; authorized recovery made task17.
Fresh blank-page viewport capture also timed out15.051s; alternative CUA has
no native pipe/browser host. No screenshots or Outlook paste are qualified.
Evidence: .tmp/html-reports/browser/capture-preflight.md and outlook-control-preflight.md.

The following RUN checkpoint notes explain that completed fix wave:
RUN first candidate:19tests29.43s after record-validator split; actual13file
size gatePASS. Hume found2Critical/3Important issues in cancellation, remote
reconciliation, resume progress, combined admission and derived-selection locks.
Lagrange owns one fix batch from run-review-r1/review.md. The atomic operation
cancel callback and item-progress invariants are now explicit in manual-run-packet.
No HOST implementation or full-stack/native validation starts before that gate.
2026-11-03 08:44+08 checkpoint:60.2minutes since the RUN source window began.
Decision: continue the bounded five-finding repair, not widen validation; the
candidate produced new functional evidence but is not reliable yet. The measured
three-file suite is29.43seconds; no claim about unmeasured total/wasted time.
The next HOST-only readiness check covers startup reconciliation and a genuinely
new stage with no archive, so its first Run is reachable without preseeded data.
SOURCE/RENDER/EDIT/FINALIZE remain closed. UI source and scoped code review are
closed; its checkbox still waits for actual desktop/clipboard behavior.
Linnaeus closed all four UI findings plus the bounded Git helper correction.
The28file fix-manifest matches the main checkout. Latest UI/list17tests+3subtests
33.48s, language7tests+20subtests3.10s, directGit2tests21.44s; JS/check/size19PASS.
Evidence: .tmp/html-reports/ui-implementation.md and ui-review-r1/fix-review.md.
Duplicate single-edit controls remain one nonblocking minor; no cosmetic wave.

W7.E2E.CANCEL is closed. Peirce's cancellation9tests27.41s, capture2tests21.52s
and affected15tests+28subtests0.84s cover the initial implementation.
Avicenna closed the retained run-ID binding fix; new counterexamples2tests0.52s
and fast consumers5tests0.56s passed. CN08 damaged-intent-hash1test0.42s then
verified the existing reader without implementation changes or real-Git rerun.
Evidence: cancel-implementation.md and cancel-review-r1/{review,fix-review}.md.
RUN/HOST exact packets are manual-run-packet.md and manual-host-packet.md.
Plato independently returned CODE_READY for both with no design blocker;
CANCEL dependency is now satisfied. Evidence: .tmp/html-reports/manual-plan-review.md.
Ego old task15 is absent, including name lookup; authorized replacement task16
uses the same goal name. No old demo/browser page was modified or screenshot
qualification inferred from that recovery.

### Earlier HTML Checkpoints

The following entries retain prior stage evidence; the Current Execution
paragraph above is the current next action, not these earlier writer statuses.
SOURCE entry is now CODE_READY: Gauss independently checked the exact packet
against current archive/acceptance helpers. His initial verdict confused missing
implementation with design readiness; a limited design-only recheck found no
load-bearing gap. Fixed safe English errors are implementer-owned wording, not
an open contract. Baseline10tests+11subtests passed0.83s.
One implementation writer now owns UI, coordinator owns docs/integration.
UI first candidate43tests+23subtests passed147.79s and JS state test passed.
Coordinator intake found single-edit form could drop other saved notes and
capture page overflow became false no-data; same writer fixes these plus
resume/revision entry, strict clipboard hash checks and error/locale guards.
Do not mark UI complete or re-run the long combined regression after every edit.
FINALIZE closure: Russell independent review closed resume fingerprint binding,
clean absence vs Git failure and pre-write combined growth admission.
Final edge10tests7.65s, changed repository realGit1test76.22s; prior scoped
publication6tests/neighbor26tests evidence retained separately.
Exact packets/history/HTML/plain bytes committed through existing writer,
same-source baseline checks intermediate chain and originals remain readable.
Evidence: `.tmp/html-reports/finalize-implementation.md`, finalize-review-r1.
The per-file limits pass;668lines total across several modules is not a per-file
violation. No live/provider/production-data Git publication implied.
EDIT closure: original eleven draft tests passed54.19s; final scoped recovery
4tests0.92s, fastdraft12tests5.81s and affectedrenderer40tests0.70s.
Galileo independently closed missing-current create replay and revision_hash
render binding. Source/summary/Git unchanged on Save, historical revisions
verified against complete command intents. Evidence:
`.tmp/html-reports/edit-implementation.md` and `edit-review-r1/fix.diff`.
RENDER first candidate26fast tests passed0.65s, but coordinator intake found
actual SOURCE field mismatches (owner_id vs invented owner_display, json_pointer
vs pointer) and missing mandatory weekly sections. It is not accepted as complete.
Same writer fixes these with exact producer-shaped fixtures and shared template
sections, no SOURCE rewrite or real Git/Base rerun.
RENDER revised31tests passed0.71s with explicit no-dotenv synthetic settings.
Pauli independent review found template registry self-hash not package-bound,
plain-text metadata omissions, no-publication day coverage loss, empty-host URL
and invalid-edit error typing, plus evidence-row/mutation coverage gaps.
Same writer fixing one batch; no closed RENDER checkbox yet.
RENDER closure supersedes the initial candidate:38fast tests0.71s with explicit
synthetic settings;14Python file sizePASS. Pauli closed six findings and the
follow-up per-day event association correction. Final code includes a shared
body template bound in each template hash and separate identified day events,
not copying another ticket's events into a row. No model/provider/Git writes.
Evidence: `.tmp/html-reports/renderer-implementation.md` final addenda and
`.tmp/html-reports/renderer-review-r1/` scoped review diffs.
Ego task15 loaded generated daily HTML; DOM has all5headings/29rows, width within
1440viewport and0active script/form/iframe/image elements. CaptureScreenshot
timed out with default, viewport-only and fromSurface=false, so visual screenshot
qualification is still open. Do not repeat equivalent screenshot attempts or
mistake DOM evidence for full visual/Outlook qualification.
SOURCE candidate report: `.tmp/html-reports/source-implementation.md`, correction
addendum8SOURCEtests+4subtests and10affected-consumer tests+11subtests.
Cost correction preserved required branches using memory repository SPI rather
than more real-Git setups; initial4-case candidate was not accepted as complete.
Independent implementation review uses `.tmp/html-reports/source-review-r1/`
10-file diff/manifest, not whole dirty-worktree or release qualification.
SOURCE closure: Hypatia rechecked three findings (missing exact refusal/drift
tests, overly broad pinned facade, missing public service export) and found
them addressed. Final fast12tests+4subtests0.95s, actual pinned-facade Git1test
38.70s, affected10tests+11subtests0.65s. Final11file size gatePASS;
test helper split fixed physical633line failure without removing cases.
Current DTO/API SHA256: report_contracts6c983e9741e8ae8ad211a391470e3020866da80aec3c6e01522079f4b226a1e9,
reports API157be1762ea6110e2bbfd2e7357e97b0227a9c4a7764db13d1489d4913e8aa40.
RENDER/EDIT/FINALIZE packet design review by Aquinas is CODE_READY after fixing
create-replay-before-source ordering and naming the existing atomic current-head
writer. Manual/full-stack and UI review by Hegel identified five contract gaps
and a follow-up public revision_hash mismatch; corrected in the respective
packets. These are pre-code design results, not implementation/test closure.
The previous W5.JOIN goal remains complete; this is a new authorized goal.
Working directory stays D:/AIGC/scrum_dashboard on mvp/intel-jira-connectivity.
Ruling: preserve this user-selected dirty checkout, use scoped source ownership
and immutable review artifacts, not a new worktree or second progress ledger.
The cost of a missed shared change is scoped revalidation; no user work is reset.
All subagents remain GPT-5.5/xhigh. SDD workflow uses this tasks file and linked
leaf packets instead of its default duplicate .superpowers progress ledger.
The execution end point includes actual application/SDK/HTTP/storage and browser
flow; synthetic provider/model qualification and real qualification are separate.
Public manual run is not implied by completing the prepared-report editor.
External prerequisite refreshed read-only: Base task ledger still qualifies
a2/CANCEL-INTENT synthetic only, not live provider/model. Continue local
full-stack implementation without pretending that missing qualification passed.
Full-stack exit and run/worker boundaries are in
[manual-full-stack](manual-full-stack.md); this adds named FS01-FS10 cases without
another task-state ledger. W7 exact constructor/settings entry is finalized
against completed HTML public services before its implementation.

### Earlier W5 Checkpoint

The following W5 completion and docs-only notes describe earlier user requests.
They do not override the later continuous full-stack authorization above.

2026-11-01 user explicitly resumed work in Dashboard with provider-neutral scope.
Baseline HEAD: 12f7ac285d1bba7f125b947a11a3deaa2fd5d330.
Existing dirty paths: metadata-backed-query-builder-controls/{design,tasks,specs/provider-scope-wizard/spec}.md;
ui_web/static/css/main.css; bug_trend_scope_config.html; partials/bug_trend_scope_metadata{,_hints}.html;
ui_web/views/bug_trend_scope_views.py and four existing scope configuration/metadata/query-builder test files.
These are outside this wave and must not be reverted, staged or edited.

Current: W1, C0, W2, W3.CREDENTIALS, W3.ARCHIVE and W3.GATEWAY/CLI/CAPTURE are closed
for their byte-bound owned candidates.
W3.LISTS.A/B and W5.JOIN.CORE/LOOPBACK are now implemented and verified.
W5.JOIN.R is now closed. The user's goal to reach the first genuine business join
is achieved; return this checkpoint without starting another wave.
Cross-repo receipt: w5-join-delivery.json; counterpart feedback: w5-base-feedback.md.
W3.LISTS.C/D and other W3-W7 work remain required, but are not
part of the user's current goal to reach the first genuine business integration join.

2026-11-02 subsequent user requirement: templated daily/weekly reports with HTML
as primary output, formatted email copy, manual notes/edits and user-controlled
final data-Git commit. The design and test matrix are now documented in
html-report-authoring.md / html-report-validation.md; this is not implemented UI.
This docs-only window does not restart the completed W5 goal or perform live
calls, edit the running W2 demo, commit business data or push a repository.
The next report slice is W6.HTML below; preserve all remaining original tasks.
Docs-only checks: strict OpenSpec PASS;10documents/57relative file links,
32unique HT cases and7unique HTML leaves, fences/whitespace PASS.
Independent GPT-5.5/xhigh reviewer Ohm identified two design gaps: durable
pre-Git payload retention and manifest/receipt separation. Both were corrected;
limited recheck found no remaining material issue in those changes.
The size checker selected0files because current rules do not match
openspec/**/*.md; this is not a size-gate PASS and no exemption was added.
No HT product case ran. W6.HTML.PLAN.R remains open for exact source closure,
source-adapter fixture/API mapping and next-leaf readiness; reuse this unchanged
design review rather than repeating it. The user subsequently confirmed Windows
Outlook and supplied its About screenshot: Outlook1.2026.1020.100,
client20261023003.06, WebView2 156.0.4314.50 Stable.
The target environment is recorded in html-report-validation.md; HT30 still
requires actual paste verification after implementation, not further client
identification. No Session ID is retained and no Outlook draft was accessed.

### W5 Current Evidence

The actual application -> installed a2 -> Base loopback -> accepted Git flow passed
in96.829s. Receipt: `.tmp/task-run-w5/runs/0221de2b-4577-43d6-823c-72edfba648a9/receipt.json`.
One Base Run, one accepted revision, service reconstruction/no-work and normal
launcher+worker exit are verified. artifact-verification.json independently compares
Base result_json with the accepted Git record, preserves original content/hash,
and confirms all3comments plus13061characters of raw text.
Final CORE fast tests27passed43subtests3.86s; native journal2passed135.24s.
Final combined fast selection after all harness corrections:30passed43subtests5.93s.
Einstein independently signed off the CORE including the UTC-millisecond wire fix.
His final harness review found two guards to strengthen: pin the full Base archive,
reject unregistered resources, and block connect_ex in the import probe.
Those corrections have10passed4subtests4.24s and an actual Base import-only PASS;
844files match the pinned full commit+delivery overlay. Einstein's limited recheck
found no remaining P0-P3 findings and marked the harness ready; the agent is closed.
The earlier immutable failed attempts/data are retained; the rejected deadline
experiment created0BaseRuns and no executor call. No old payload/key was rewritten.
No real Jira/HSD/model call, production DB migration, schedule, commit or push.

### Earlier Capture Evidence

The coordinator owns source/design. All subagents and required commands from the gateway packet ended.
Current gateway candidate: review-05 manifest-r3,208files and54changes against the accepted
archive snapshot. Gate .tmp/project-reporting-review-05/.tmp/review/gateway-gate.json is complete1/1.
First counted review identified one packaging P1: provider-capture-source.json was omitted from
the inherited snapshot manifest. R3 adds that file, preserves all207 prior hashes, verifies14
donor blobs/4runtime resources and89internal links across21documents.23external historical
design references are explicitly origin-bound, not runtime package dependencies.
Ramanujan `01a199e4-d256-75e0-aa53-add8ef9b33df` returned no P0-P3 findings.
Two counted reviews (1FAIL/1PASS), one P1 finding and one closure; report elapsed17m55s.
The six gate process artifacts are separate from the208source snapshot files.170runtime/config/test
files match the main checkout. Final full candidate size157PASS, whitespacePASS and Django checkPASS.
No provider/model/Git behavior test was rerun for the packaging-only change.
Archive evidence: `.tmp/project-reporting-w3/archive-implementation-report.md`.
Full31tests+3subtests passed304.86s; later scoped RED/GREEN fixes cover review findings.
Latest common UUID/input-boundary4tests+50subtests passed4.59s.
Final review-04 manifest-r6 freezes170files; whole-candidate size126PASS and whitespacePASS.
Carson `01a19979-8ca4-73f3-980a-4cef68cf16a2` returned no P0-P3 findings.
Gate `.tmp/project-reporting-review-04/.tmp/review/archive-gate.json` is complete1/1,
pending_issue_count=0. Six counted reviews (5FAIL/1PASS), nine findings fixed and nine closures;
recorded process elapsed1h13m5s. Final immutable transcript is archive-review-6.txt.
Later task/docs changes do not alter that reviewed runtime candidate or reopen unaffected tests.
Provider-capture.md implementation now includes the pinned Node22.18.0 parser and14source-blob
mapping; four copied resources retain exact bytes through Git autocrlf handling.
Source repositories for API/capture tests are synthetic temporary roots only; no model/provider call.
No real tracker/model calls, default database migration, code commit or push.
Current delivery includes local project/stage catalog, bilingual desktop setup, safe provider diagnostics
and the internal synthetic-qualified Jira capture/archive API. Public capture/operation remain disabled
until W7. Remaining W3 leaves and the report application are not complete or live-qualified.
AI counterpart: BASE-A/a1 preserved; BASE-B.CANCEL-INTENT/a2 and dedicated loopback launcher now delivered.
Initial intake verified a2 wheel/manifest and21 content hashes without inferring
business integration. The later actual W5 evidence above is the current boundary.
Exact receipt/fixture-only input restriction is in execution-handoff.md section7.
Dashboard C0 now has an owned prepared environment and verified installed-SDK probe;
the earlier missing-httpx prerequisite was resolved there. W5 later installed its
optional a2/httpx/jsonschema dependencies in the main environment, leaving C0/a1 unchanged.
C0.N1 is implemented: the formal 12-case installed-SDK suite passes with exact call counts and no real connections.
W1.REPLAN and the first W2.REPLAN packet are complete; W3.CREDENTIALS has no BASE-B dependency.
Dashboard's local business chain remains the critical path to W5; a2 availability does not close W5.
PLAN.R/W1.VA: Dalton (GPT-5.5/xhigh) signed off W1 with no P0/P1/P2 plan findings.
Gate scope is feature plus audit/ownership hygiene, not Jira/Grafana MVP or release closure.
Baseline affected scope/binding suite: 34 passed in 2.11s; Python3.13.7/Django6.0.7.
Product work stays in user-selected checkout on mvp/intel-jira-connectivity; no branch switch.
Owned detached worktrees under .tmp are immutable review snapshots, not a product workspace migration.
2026-11-01 user also authorized refreshing both indexes for this workspace.
Index result: codebase-memory new D-AIGC-scrum_dashboard index succeeded; zvec's copied manifest
incorrectly targeted old OneDrive root (two zero-file attempts). Corrected rootPaths to this checkout,
rebuilt using local/potion-code-16m-v2: 829 files, semantic query resolves ProjectManagementService.
No index credentials/global config or other project index changed.

Goal boundary: the first genuine AI Base business integration join through
early-ai-integration.md is now achieved. C0 or the peer's default fixture alone
would not satisfy it. The later full W3-W7 requirements remain open.
Current window: W3.LISTS.A and B source checkpoints complete; Epicurus independently
closed B after the safe error-category correction. W5.JOIN.PLAN is CODE_READY:
Kuhn closed event-ID, grant/limit binding and command-precision gaps on recheck.
The full W3.LISTS workflow is not complete.
Copernicus independently reviewed the A interface and validation packet. Its two source-map/test
entry mismatches were corrected; limited recheck returned CODE_READY for A only.
Installed openpyxl3.1.5 and et-xmlfile2.0.0 from owned wheels; pip check passed.
Ported two pinned donor parser modules into project_management/out/spreadsheet{,_archive}.py,
with pure bounds/provider syntax and public app/api/spreadsheet.py. No source/DB/credential lookup.
Initial RED: missing public parser API; final focused parser/archive/catalog selection41passed,
38subtests in3.75s; seven owned Python files passed size gate. Cancellation verifies real workbook
and iterator closure, not only exception propagation. No independent complete-list behavior review yet.
B is CODE_READY and implemented; C/D remain draft. Coordinator corrected volatile approval hashes, old HSD selection layout,
project-bound list reads, stage-less request context, known population versus current observations,
metadata/artifact separation and compact descriptor. Remaining DTO/validation/source-map consistency
and plan signoff are required before C/D implementations.
B evidence: .tmp/project-reporting-w3/list-identity-implementation.md.
Shared session/list/reader/Jira selection38passed46subtests20.01s and real temporary
Git consumer1passed32.85s. Independent B review found one connection-error typing
P2; new RED test confirmed it, safe allowlist fix25passed44subtests1.57s.
Limited independent B fix review found no remaining issues; its new node passed
1test+5subtests1.01s. Both review agents are closed. No full dirty-worktree/release claim.
Gateway evidence: .tmp/project-reporting-w3/gateway-implementation-report.md.
Final r0 quick35tests+42subtests passed36.91s; real-Git9tests passed220.86s including500members/
1detail/499pending. Two narrow r1 corrections had23tests+19subtests passed22.22s and targeted
3tests+2subtests passed7.95s. r2online CLI2tests+2subtests passed2.08s; r3was packaging-only.
No public capture runtime, real provider, model or deployment was activated. No commit/push performed.
Codebase-memory refreshed successfully at generation2026-11-02T01:12:27Z;25changed source paths
reported metadata_match. Zvec queries return fresh local evidence. No other project index was changed.
Ruling: use the owned detached review worktree `.tmp/project-reporting-review-01/` at the
recorded HEAD plus exact owned W1/C0 files. Run the unmodified whole-worktree hygiene gates there;
compare all reviewed implementation bytes back to the main checkout before accepting evidence.
The two unrelated over-limit scope tests stay untouched in the main checkout and remain known WIP.
This qualifies the selected candidate, not the combined dirty checkout or a release.
Native worktree creation is bound to the conversation's donor repo, so the explicit Dashboard
Git worktree command was used. Product edits continue in the user-selected Dashboard directory.
Reviewer config now records the user's requested tool model ID `gpt-5.5`; xhigh is explicit on spawn.
No credentials/provider calls, production migrations, permanent services or review cap changes.

W1.R/C0.R closure: independent GPT-5.5/xhigh reviewer Schrodinger found no P0-P3 issues.
One counted pass, one PASS, zero FAIL/findings/fix rounds; planning-artifact coverage.
Gate `.tmp/project-reporting-review-01/.tmp/review/w1-c0-gate.json` reports complete, 1/1.
The review process report lists four process artifacts, separate from the 58 owned snapshot files.
Candidate whole-worktree size gate checked34 PASS; whitespace PASS; 66 tests plus4 subtests
passed in15.86s; Django check and migration dry-run passed. All31 reviewed Python files match
the main checkout hashes. W2-only design additions and this ledger update do not claim to be
part of that immutable review; W1 implementation is unchanged and C0 remains synthetic-only.
Flow: initialized -> independent review PASS(P0-P3=0) -> gate complete.
Neither the combined dirty checkout nor old T12 nor live/report execution is qualified by this closure.

2026-11-02 execution checkpoint (goal elapsed3798s): W2 source and focused tests exist;
initial 9 identity/preview tests, 13 route/language tests +8 subtests and70 affected tests +4 subtests passed.
Parent pre-browser intake found unsafe ambient-settings/flush selection in the new fixture helper,
manual language redirect validation, Unicode preview comparison and missing UI failure/state handling.
W2 remains open. Implementation Engineer Plato is fixing these as one scoped batch with new RED tests;
no browser server or expensive end-to-end run has been started on that candidate.
Decision: finish those negative cases, then one same-candidate desktop workflow and independent W2.R.
W3.CREDENTIALS draft/source-closure preparation ran in parallel; it is not W2.REPLAN or code approval.
Pinned pywin32312 cp313/win_amd64 wheel is available locally (not installed in main environment).
Installed atlassian-python-api5.0.3 accepted an injected requests.Session and explicit retry disable
in a constructor probe guarded against network; send count0. This resolves factory availability,
not credential-safe redirect or full transport qualification.

Earlier W1 evidence before isolated review:
- RED project_catalog/scope_catalog missing module, then behavior GREEN.
- CLI RED 4 failures for unknown command; after implementation current combined suite 66 passed,
  4 subtests passed in 11.58s, including isolated CLI subprocess DB persistence.
- `makemigrations project_management --check --dry-run`: no drift; `manage.py check`: no issues.
- Scoped size check of all new module Python plus changed settings/governance: 32 files PASS;
  changed-worktree whitespace PASS; OpenSpec strict validation PASS.
- Whole-worktree size FAIL solely on pre-existing `ui_web/tests/bug_trend_scope_config_test_support.py`
  (650>600) and `ui_web/tests/test_bug_trend_scope_config_views.py` (624>600).
  These paths are outside W1. Do not modify/ignore/revert them to manufacture a pass.
- PLAN.R/W1.VA passed; no counted exact-pass implementation review has run because its declared
  whole-worktree hygiene prerequisite is red. Do not report W1.R, release or complete topic closure.

### W2 Closure And W3 Entry

2026-11-02: W2 source, negative routes and Ego desktop workflow are complete.
Candidate `.tmp/project-reporting-review-02/`: full size53 PASS, whitespace PASS,
39 focused tests+17 subtests passed in17.45s. Final route/test fix21+20 passed in3.54s.
U11 unaffected core/provider suite70+4 passed; narrow locale/fixture changes validated separately.
Real Ego(Chrome156) desktop1440x900 evidence is in `.tmp/project-reporting-w2/browser/`:
create/error focus, Jira/HSD previews+confirm, en/zh labels+lang+selection, language-only DB
comparison, archive/history, other-owner404/own200 and draft-preserving language navigation.
All owned server sessions exited and port8017 listener absence confirmed.

W2.R gate `.tmp/project-reporting-review-02/.tmp/review/w2-gate.json` is complete1/1.
Three counted reviews:2 FAIL then1 PASS;3 finding events/3 closures, P0=0/P1=0/P2=2/P3=1.
The tool reports2 unique IDs because the second reviewer reused W2-P2-1 for a different evidence
finding; all three actual findings are preserved in separate immutable transcripts. Process elapsed25m30s.
Eight gate process artifacts are distinct from88 copied snapshot files and60 runtime/config files
verified against main. Final planning-only W3 docs are explicitly excluded from the W2 current-runtime
binding in `.tmp/project-reporting-review-02-binding.json`. No whole dirty-checkout/release claim.
Lessons applied: independent refusal fixtures must start from otherwise valid state; review snapshot
and current runtime identity are separate; later docs changes do not trigger redundant browser runs.

W2.REPLAN: refine only the next executable dependency, W3.CREDENTIALS.A/B/C.
refreeze_actions: amend with provider-foundation.md exact resolver/transport/trust/store/adoption/CAS
APIs, mandatory Windows protection, concrete PC/PA matrix and source blob mapping.
Independent reviewer Nietzsche identified3 design gaps; all fixed, limited recheck no blockers.
updated_artifacts: provider-foundation.md, provider-foundation-source.json, design.md,
provider-access.md, tasks.md. rerun_gates: W2.R, W2.REPLAN, strict OpenSpec PASS.
post_refreeze_preflight_result: explicit producer/consumer/file/SPI/negative-case/serial A->B->C
check PASS. W3 remainder and W4-W7 continue; none superseded/retired.
The original broad W2.REPLAN label is narrowed to actual next-packet freeze, not a claim all future
raw-storage/capture APIs are settled. W3.ARCHIVE and later leaf code cannot start until their own
exact packet and validation design are reviewed; this rolling refinement is mandatory, not omission.

### Provider Foundation Progress

W3.CREDENTIALS.A/B source checkpoints complete, not the full credential leaf or public deployment.
Mencius implemented resolver/opaque handle and requests/HSD boundaries, then migrated actual sync,
metadata/helper, Current Tasks and profile probe consumers.
Parent intake exposed source classification/default fallback/actual factory mismatches; expanded
RED cases fixed them before the consumer checkpoint.
Final A+B focused49 passed+19subtests in2.88s; named existing consumers70 passed in3.22s.
Explicitly enumerated25 source/test files pass size and whitespace; Django synthetic settings check passes.
Actual atlassian client construction now tests timeout= and PAT without email, not only fake kwargs.
Reports: `.tmp/project-reporting-w3/credentials-{a,b}-report.md`.
C is still pending: native protected store/adoption/ref CAS/editor race/CLI, and whole-leaf independent review.
Missing protected capability still refuses instead of reading another credential; no real token migrated.
Later C implementation: coordinator took over after repeated core boundary mismatch; no accepted
C completion was claimed from child green tests. Added independent database-window/path/DACL/
public DTO/CLI cases, removed secret memory cache, preserved JSON key order in exact SQLite CAS,
protected every newly created directory, used same-handle reads for all secret metadata and atomically
saved profile+audit. Final credential candidate77passed28subtests19.78s; affectedconsumer70passed3.33s.
One independent review found typed errors escaping legacy sync result handlers; RED4failures reproduced,
fix34tests+2subtests passed2.80s. That transcript combined severity counts on one line and was rejected
by the gate; it remains an uncounted actual review/finding, not fabricated PASS. A fresh independent
review is running on manifest-r1 with89file full-hygiene PASS and separate severity lines.
Evidence: `.tmp/project-reporting-w3/coordinator-c-fixes.md` and immutable review-03 transcripts.
No real token adopted, source credentials read, server started or paid model invoked.
Credential leaf final closure: Hilbert independent review PASS; exact gate review-03 complete1/1.
Two counted reviews (1FAIL/1PASS), one recorded P1 finding fixed; earlier malformed-count transcript
is preserved separately with its real typed-error finding/fix and is not counted. Process21m11s,
6 gate artifacts versus134 snapshotfiles; full candidate size92PASS/whitespacePASS.
Final combined credentials84passed36subtests19.44s, after pure TLS helper/test-file split affected
48passed25subtests4.27s; precise local-profile UI calls32passed6subtests3.04s.
One attempted older full Provider Setup suite hit missing Playwright headless-shell then contaminated
that process's async context:20fail/32pass/2errors. Process exited; no product failure inferred from
the cascaded errors. Its visual checks remain an explicit environment gap, not silently skipped/green.
Affected API/form behavior separately passed in fresh processes; existing visual assertions preserved
in test_provider_setup_connections.py after splitting the previously624-line test file.
Existing unrelated Scope Config files remain untouched. Credentials current guide is
openspec/docs/current-baseline/provider-credentials.md. No actual user credential was adopted.

W3.ARCHIVE entry: full credential prerequisite now satisfied; capture-archive.md independent plan/
validation signoff and41-source-blob mapping remain current. Next writer implements the exact
raw-page/Git/root+stage budget boundary and AR01-24 local tests; no live capture or model.
The next W3.ARCHIVE packet is capture-archive.md; Arendt independently reviewed its precise APIs,
Project authorization, endpoint/principal ownership, budget math and shared append owner. Five entry
gaps fixed and limited recheck passed; implementation still waits for full W3.CREDENTIALS.
41 donor source/test/resource blob IDs verified in capture-archive-source.json; no donor runtime copied.
Provider documentation only: refreshed Jira10.3 OpenAPI and HSD Swagger through official sources.
HSD includes whoAmI/children/history; old facts-only fallback is not evidence those endpoints are absent.
Actual response/auth/row-pagination qualification remains W3.GATEWAY/HSD, not assumed from docs.

## Contract Registry And Propagation

| ID / risk | Owner / authority | Producer -> consumers | Negative check |
| --- | --- | --- | --- |
| PM-IDENTITY high | project_management Project owner/key | domain/validation.py -> app/api, CLI, repository | other actor cannot list/get/archive/add-stage; invalid key rejected |
| PM-SCOPE high | immutable Stage descriptor/hash | out/dashboard_scope_catalog.py -> app/api/service -> repository -> show | mismatching/inferred binding, changed query/endpoint, disabled source, unknown provider rejected |
| PM-HISTORY high | preserved stage/project | models/repository -> archive/show -> future reports | scope deletion cannot cascade; archive blocks writes but preserves reads |
| PM-CLI high | trusted local operation | management/commands/project_catalog.py -> public API | no actor/credential/raw descriptor input; nonzero safe domain errors |
| PM-PROVIDER high | same generic DTO | Jira/HSD translators -> Stage -> future capture | HSD no Jira scope; fake source/history cannot claim live or complete |
| PM-REPORT high | capture/accept/publication | W3 capture -> W4 delta -> W5 candidate -> W6 publication | no-change zero AI, partial coverage/policy drift/invalid evidence cannot advance success |
| PM-CONNECTION high | profile/endpoint/auth/credential source | bug_metrics/app/api/provider_connections.py -> provider_access CLI, existing sync/metadata/task clients | ACCESS-01/02/06: endpoint mismatch, missing reference, failed auth cannot fallback |
| PM-AI-PACK high | task prompt/schema/policy/loader versions | project_management/ai_bundle -> AI Base loader/client/doctor -> candidate acceptance | APP-01/02/04: invalid hash, hidden history/tools, wrong-stage result refused |
| PM-AI-VERSION high | base canonical contract/SDK and app migration map | base release pack -> existing ui_web workbench, W5 Task client, ai_integration doctor | APP-09: unsupported version fails before model/publication; changed identity preserves ownership and approvals |
| PM-SDK-INTAKE high | delivered wheel/pack hashes and qualification | base artifacts -> C0 copied/installed consumer -> C0.R/W4.REPLAN | C0-01..12: valid and invalid responses, no source import/retry/network/synthetic-to-provider upgrade |
| PM-PORT high | pinned donor source/resources/behavior | migration-catalog.md + leaf source closure -> actual destination API/tests | target runtime/import/provider negative cases; donor-only green is insufficient |
| PM-EDIT-V2 / PM-TEMPLATE-V1 / PM-COMPLETION / PM-AI-DRAFT / PM-PUBLICATION-V2 high | 本轮作者层新增契约，不覆盖旧W1 authority | [authoring validation](report-authoring-validation.md)提供精确producer/consumer/反例；仅W6.AUTHOR消费 | RA01-40，不能继承旧HTML绿色 |
| PM-PAINT-V2 / PM-CONTINUITY / PM-PREPARE high | 用户有效富文本、raw状态、系列基线/周周期/稳定行序和准备幂等 | 同附录的保存/renderer/归档/翌日/CLI/UI消费者；HISTORY/DAILY加入原lane | RA41-69，旧样张检查非生产资格 |
| PM-SCHEDULE high, deferred | 显式启用的调度adapter | W7.SCHEDULE -> 同一preparation API/journal，不直接finalize | RA70-72，须独立配置/授权/环境 |

Owner paths W1: project_management/**, metrics/settings/defaults.py (app registration only),
README.md, openspec/changes/add-provider-neutral-project-reporting/**,
openspec/docs/current-baseline/project-reporting.md,
.github/ai-governance/repo-context.md, .github/skills/lsheng2-dag-based-planning/templates/project-profile.md.
Non-goals: dirty UI paths, bug_metrics ORM/schema mutations, old chiplet/AI Base repos and runtime data.

## Consumer Universe

| Category | Decision / exact consumer |
| --- | --- |
| public API | applies: project_management/app/api/__init__.py |
| internal service/facade | applies: project_management/app/domain/service.py, out/orm_repository.py |
| UI route/template | deferred-with-trigger W2: ui_web/views/project_management_views.py etc. No W1 UI |
| export/report | deferred-with-trigger W6: project_management/reporting; W1 JSON CLI is not report |
| audit/log/event | applies: ProjectAuditEvent and repository atomic writes |
| validation script | applies: existing size/whitespace checks; no new framework |
| migration/schema | applies: project_management/models.py and migrations/0001_initial.py |
| background job/scheduler | deferred-with-trigger W7; no W1 worker/model calls |
| cache/index/search | not-applies W1: direct bounded ORM queries, no cache truth |
| external artifact | deferred-with-trigger publication; no config/raw-data export in W1 |
| CLI/admin | applies: project_catalog local command; no Django admin registration |
| docs/operator | applies: current-baseline/project-reporting.md and README navigation |
| test double | applies: tests/fakes.py ScopeCatalog + real ORM; production API remains real |

## DAG And Ledger

W3-W7 parent N1 rows are summaries; dispatch the amended leaves below instead.
`integration-execution.md` gives each leaf owner paths, exact consumers, tests and dependencies.
No current phase is marked complete by this planning amendment.
MIG-01..19是能力族索引，不是完整文件闭包。每个W3-W7 REPLAN/叶任务实施前须固定源commit并
产出准确source/resource/test闭包及目标消费者映射；没有闭包不能标“直接搬完”。
W3不激活provider_access capture/operation；这两个公开运行能力只属于W7.RUN。

```text
BASE-A.R -> C0.PLAN.R -> C0.N1 -> C0.R
C0.R supplies verified SDK evidence to W4.REPLAN; it does not bypass the business chain below.

C0.R + W1/W2 + W3.ARCHIVE + W3.GATEWAY/CAPTURE
 -> W5.JOIN.PLAN -> W5.JOIN.CORE -> W5.JOIN.LOOPBACK -> W5.JOIN.R
This early slice refines only its necessary APIs, not full W4/W5 completion.

PLAN.R + W1.VA -> W1.N1 -> W1.R -> W1.REPLAN
 -> W2.N1 -> W2.R -> W2.REPLAN
 -> W3.N1 -> W3.R -> W3.REPLAN
 -> W4.N1 -> W4.R -> W4.REPLAN
 -> W5.N1 -> W5.R -> W5.REPLAN
 -> W6.N1 -> W6.R -> W6.REPLAN
 -> W7.N1 -> CLOSE.R
```

- [x] PLAN.R Independent contract/module/scope plan review.
- [x] W1.VA Validate W1 negative cases and isolation before implementation.
- [x] W1.N1 Implement durable project/stage/owner API + local CLI with source catalog adapters.
- [x] C0.PLAN.R Review the SDK intake packet and cross-repo dependencies.
- [x] C0.N1 Install pinned SDK in owned isolated environment and execute C0-01..12 without server/provider access.
- [x] C0.R Review C0 artifact/command evidence; feed it to W4.REPLAN, not a W5 completion claim.
- [x] W1.R Review actual diff, focused tests, commands and truth sync.
- [x] W1.REPLAN Reassess UI identity, source adapter requirements and next exact test selection.
- [x] W2.N1 Add authenticated desktop Projects/stages UI and existing Scope Library navigation, en/zh.
- [x] W2.R Verify public API/HTML/CSRF/ownership, Chrome/Ego flow.
- [x] W2.REPLAN Freeze the next provider-foundation packet; require exact leaf APIs before remaining W3 capture/storage implementation.
- [ ] W3.N1 Add bounded provider-neutral capture; Jira complete comments, HSD honest coverage.
- [x] W3.CREDENTIALS Freeze endpoint-bound connection resolver and protected credential adoption.
- [x] W3.CREDENTIALS.A Implement neutral resolver/opaque factory/request policy and protected-store SPI.
- [x] W3.CREDENTIALS.B Migrate each current Jira/HSD/metadata/task/probe consumer without changing its business output.
- [x] W3.CREDENTIALS.C Implement protected preview/apply/CAS, native file tests and safe local credential CLI.
- [x] W3.ARCHIVE Port capture/object/admission minimum before collection.
- [x] W3.GATEWAY Implement shared provider read API, Jira capture adapter and explicit unqualified-provider refusal; HSD-specific capture remains W3.HSD.
- [x] W3.CLI Add provider_access and delegate affected legacy entry points.
- [x] W3.CAPTURE Connect bounded stable membership/current comments/history to capture archive.
- [ ] W3.LISTS Port safe spreadsheet/frozen-list selection with provider-specific ID resolution.
- [x] W3.LISTS.A Port the bounded workbook parser and two-provider syntax rules, with no I/O beyond supplied bytes.
- [x] W3.LISTS.B Add pre-stage request context and ID resolution, preserving existing capture guards.
- [ ] W3.LISTS.C Add immutable list approval/replay/storage and actor/project-bound catalog integration.
- [ ] W3.LISTS.D Connect trusted CLI and fixed-population capture, then review the complete list workflow.
- [x] W5.JOIN.PLAN Review early-ai-integration.md exact APIs, fixture boundary and EJ01-EJ12.
- [x] W5.JOIN.CORE Implement baseline input, shared durable attempt and guarded acceptance with focused tests.
- [x] W5.JOIN.LOOPBACK Run the first actual application -> installed a2 -> synthetic Base -> accepted Git record.
- [x] W5.JOIN.R Review the bounded joined slice and publish the cross-repo receipt; keep remaining waves open.
- [ ] W3.DEPENDENCIES Implement explicit external-dependency grants/source chains; donor F2 is not complete.
- [ ] W3.ATTACHMENTS Implement authorized attachment body capture; donor F3 is not complete.
- [ ] W3.HSD Validate HSD-ES-specific identity/query/part coverage, not Jira equivalence.
- [ ] W3.R Verify capture/pagination/permission/failure sources with synthetic transport.
- [ ] W3.REPLAN Freeze archival/delta compatibility and legacy import.
- [ ] W4.N1 Port generic archival/delta/evidence semantics, not Chiplet names/config.
- [ ] W4.INDEX Extend W3 archive with source-version index and reconstructable state.
- [ ] W4.DELTA Port accepted-baseline cumulative delta and unchanged detection.
- [ ] W4.EVIDENCE Port provider-neutral identity, reference and quote validation.
- [ ] W4.IMPORT Port source-closed historical import and protect original hashes/bytes.
- [ ] W4.R Verify retained versions, baseline and incomplete/revoked source behavior.
- [ ] W4.REPLAN Freeze AI Base fixed contract pack and consumer mapping.
- [ ] W5.N1 Add strict task client, candidate acceptance and no-change reuse.
- [ ] W5.APP Deliver app registration/task profile/prompt/schema/manifest and offline doctor.
- [ ] W5.MIGRATE Update existing AI workbench consumers affected by the selected breaking contract; APP-09 is not optional W5.CHAT.
- [ ] W5.INPUT Port full input preparation and bounded fragments; optional lossless wire codec.
- [ ] W5.CLIENT Integrate fixed AI Base Task SDK and attempt/usage recovery.
- [ ] W5.ACCEPT Wire original semantic/evidence/CAS acceptance and no-call reuse.
- [ ] W5.CHAT Optional assistant skill/connector/host actions; disabled unless separately enabled and qualified.
- [ ] W5.R Verify usage/unknown/identity/evidence; qualified backend separately authorized.
- [ ] W5.REPLAN Freeze publication formats and expected business reports.
- [ ] W6.N1 Deliver HTML-first templated reports plus required English Markdown/Excel and complete pending/action list.
- [ ] W6.RENDER Port generic report DTO/renderers and provider-specific safe source links; include the HTML projection without new model calls.
- [ ] W6.PUBLISH Add drafts/human edits and explicitly confirmed immutable publication, authenticated original-byte downloads and coverage.
- [x] W6.HTML.PLAN.R Review parent HTML design and freeze SOURCE source/DTO/validation entry; later leaf mappings refined before their code.
- [x] W6.HTML.SOURCE Expose an owner-checked pinned report source query over real capture/accepted records.
- [x] W6.HTML.RENDER Implement versioned daily/weekly HTML projections, self-contained email fragment and safe plain fallback.
- [x] W6.HTML.EDIT Persist revisioned local drafts and attributable human edits without model/source changes or Git publication.
- [x] W6.HTML.FINALIZE Confirm exact draft revision into existing data Git with original-byte recovery/download.
- [ ] W6.HTML.UI Summary: consume W6.AUTHOR.EDIT/JOIN for existing authoring acceptance; current textarea is transitional, no separate user-provided Agent prerequisite.
- [ ] W6.HTML.R Review the bounded authoring slice and actual desktop/copy/Git evidence; email-client qualification reported separately if unavailable.
- [ ] SDK020.PLAN.R Freeze the selected SDK/pack contract, pre-IP work and post-IP APIs/fixtures; review and publish scoped specifications before implementation.
- [ ] SDK020.ARTIFACT Verify final owner receipt/wheel/pack; install SDK into an owned separate target without changing the main environment.
- [ ] SDK020.APP Update the exact dependency/runtime version pair with real installed-SDK RED/GREEN tests; preserve all application validators.
- [ ] SDK020.PRE Run the explicit no-socket consumer selection and record source-bound readiness plus protected-WIP integrity.
- [ ] SDK020.REPLAN Confirm next joined packet is reachable, classify retained evidence, record IP-SDK020-READY and stop for the user.
- [ ] SDK020.JOIN After explicit release of IP, execute the new-SDK real local HTTP consumer cases J020-01..06.
- [ ] SDK020.JOIN.R Review the joined candidate, source/acceptance evidence and owned cleanup.
- [ ] SDK020.JOIN.REPLAN Refreeze DAILY/ASSIST prerequisites and affected evidence before continuing authoring execution.
- [x] W6.AUTHOR.PLAN.R Review Authoring V2 scope/error policy, template selection and schema migration before implementation. User approved; bounded first-CONTENT review recorded below.
- [x] W6.AUTHOR.VA Freeze RA01-72, source consumer inventory and exact validation commands; RA70-72 deferred to W7.SCHEDULE. First CONTENT slice qualified to start, not product pass.
- [x] W6.AUTHOR.CONTENT Add schema2 fragment persistence, safe rendering and old-revision compatibility. Standalone backend qualified; nonempty reference/Assist receipts remain fail-closed until their owning leaves.
- [x] W6.AUTHOR.EDIT Integrate one WYSIWYG component and the shared editor adapter; no source mode. Scoped lifecycle/native-runtime review closed; whole-flow JOIN remains separate.
- [x] W6.AUTHOR.REFERENCES Implement #ID query, Stage routing, membership/permission/freshness and three-format popup. Backend and UI scoped reviews closed; live Jira/HSDES qualifications remain separate and disabled.
- [x] W6.AUTHOR.TEMPLATES Add user template library, version-CAS, visual block/slot editing and pinned draft creation. Fixed-content rich preview follow-up closed by B2 browser/review.
- [x] W6.AUTHOR.HISTORY Add effective rich-text daily history, source-status prefixes, stable row order and weekly carry-forward. Core/B1/B2 scoped synthetic qualification closed; daily trigger and whole-week JOIN remain separate.
- [ ] W6.AUTHOR.DAILY Add manual daily preparation, editorial baseline selection/CAS, pending-draft handling and same-day idempotency.
- [ ] W6.AUTHOR.DAILY.REPLAN Bind the qualified DAILY consumer to ASSIST target/profile/save boundaries without reopening unaffected history.
- [ ] W6.AUTHOR.ASSIST Add explicit AI candidates using a separately qualified authoring profile.
- [ ] W6.AUTHOR.ASSIST.REPLAN Verify authoring-profile HTTP qualification and provenance consumers before the final week.
- [ ] W6.AUTHOR.JOIN Validate actual authoring/save/copy/finalization; separate live-provider and Outlook qualification.
- [ ] W6.AUTHOR.R Review exact candidate, changed consumers and docs; no unresolved correctness/security issue.
- [ ] W6.AUTHOR.REPLAN Refreeze remaining W6/W7 work; document completion does not resume implementation.
- [ ] W6.R Verify stable bytes, source links, language independence and failure atomicity.
- [ ] W6.REPLAN Freeze manual operation lifecycle/deployment/rollback and migration scope.
- [ ] W7.N1 Integrate manual trigger/status/cancel and isolated deployment; reserve scheduling.
- [ ] W7.RUN Wire one owned manual operation log/worker, expose capture/status/cancel through shared service.
- [x] W7.E2E.CANCEL Add durable analysis cancellation and per-page capture cancellation using installed a2 SDK.
- [x] W7.E2E.RUN Implement manual operation persistence, exact original identities and one serial worker over existing public capture/analysis/report services.
- [x] W7.E2E.HOST Add explicit project_serve/runtime assembly and authenticated stage run/status/cancel/resume controls.
- [x] W7.E2E.QUALIFY Run same-candidate synthetic full-stack browser -> actual SDK/Base HTTP -> saved HTML/download -> confirmed Git and unchanged repeat; editor/copy integration is deferred under the 2026-11-03 user split. Evidence: manual-workflow-delivery.json.
- [ ] W7.DEPLOY Verify new installation paths, identity, legacy coexistence and required recovery.
- [ ] W7.PROTECTION Port backup/retention/remote/scheduling contracts with explicit inactive activation gates.
- [ ] W7.SCHEDULE Qualify the optional disabled-by-default scheduler over the same daily preparation API; no automatic finalization.
- [ ] CLOSE.R Full matched-candidate integration, required live qualifications and unresolved issues.

## W6 Authoring V2

Goal：用户在同一报告界面使用自建模板、富文本、`#ID`和AI候选，保存可恢复修订并显式定稿。
Spec：[delta](specs/report-authoring/spec.md)、[design](report-authoring-v2.md)、
[contracts](report-authoring-contracts.md)、[completion](report-completion.md)、
[continuity](report-continuity.md)、[validation](report-authoring-validation.md)。
profile_source：repo-local；agent_routing_mode：single-agent实施协调，独立Architect Planner Reviewer。
使用writing-plans/TDD；不复制另一份勾选ledger。Implementation Engineer由同一协调者兼任，
Validation Engineer只在VA有独立验证风险时派发，Debugger当前跳过（不是故障实施请求）。
子代理继续显式GPT-5.5/xhigh，不要求用户另行安排开发者。

### Scope And Preflight

- 2026-11-03执行授权更新：直接main，baseline5d83933；用户工作树不stash/重置/自动暂存。
  Mill（GPT-5.5/xhigh）复核PLAN.R+VA为PASS_WITH_FOLLOWUP：未发现阻断首CONTENT切片的
  新架构缺口；必须先RED，显式选择project_management/provider_sync路径，
  schema2 UI/真实editor/live/Outlook不能冒领旧schema1绿色。
  原源码默认pytest路径不含project_management/provider_sync，禁止仅跑默认pytest宣称覆盖。
  合成执行器见`.tmp/authoring-main-20261103/run-tests.py`，不加载.env或用户数据库。
  每个后续叶开工前复核本叶确切边界，新增缺口回此计划修订而非跳过。
- Ruling: 用户明确指定main，替代SDD默认隔离worktree；任务状态只在本文件维护，
  `.tmp/authoring-main-20261103/`只存brief/证据，不能成为第二套完成ledger。
  保留原权限/归属/旧字节守卫，直接main的代价是需要精确范围review，不能混提交他人改动。
- 组件前置探针：固定npm vditor4.0.1 sha512-CyajvPNE8fjCgEAzAaSxVEEWwQMJ5FTIVkNn3k+5IRaldqGwPRr8Dx2QLALHGCby8L/AJ6pQXjXiSPUGhHGmDw==
  的public html2md/setValue/getHTML在Chrome合成输入中丢foreground/background。
  原始结果在`.tmp/authoring-main-20261103/vditor-qualification.json`；不得用于真实编辑器保真。
  按既定备选评估Milkdown公开schema接口，不改核心fork或降级颜色需求。
- Ruling: 固定采用`@milkdown/kit@7.23.0`的公开schema/JSON与transaction接口；
  本地Chrome156.0.8078.74禁网络探针通过paint、格式link、undo、输入及destroy/remount。
  `.tmp/authoring-main-20261103/milkdown-qualification.json`和PNG为能力证据；
  npm integrity=`sha512-WNu4cZXY33l224gLuyRWaQdPDotsPJ3yBn0+FGobaqH6aEt8G/QxIC1MIUV8Uxj07lMP6aIfaW4ilNLTjAMCmw==`。
  public JSON映射满足格式保留，避免Vditor已观察到的丢失；判断错误的代价是重做adapter，
  不改变中立fragment/存储契约。实际UI/save/reopen/paste/clipboard资格仍由EDIT/JOIN完成。
- 同一组件探针补充通过h3、quote、task/ordered list、code、hardbreak、header-only table
  和reference_id公开属性扩展。UI隔离执行器`run-ui-tests.py`的原生产route首个测试
  1passed/5.05s，只证明测试装配可用；不计新作者页面验收。
- CONTENT首候选18文件已冻结到`.tmp/authoring-main-20261103/content-review-r1/`供独立review。
  实现者报告新测试10passed/8.20s、指定回归33passed/164.06s；协调者物理size17文件PASS。
  尚未勾CONTENT：必须关闭兼容/精确schema/恢复问题，不能以报告中的绿色代替review。
- Ruling: 额外publication_edges失败不能因“optional”被忽略。现有race fixture仅改HEAD，
  与`html-draft-packet.md`允许无关Git append的语义规则冲突；修为真实source变化反例，
  并保留head-only成功用例。代价是补齐测试而非改变生产source校验；旧失败记录仍保留。
- CONTENT review1：Dirac确认3项Important，旧模板原地改动破坏旧草稿、schema2 edits字段偏离契约、
  损坏packet在完整校验前append。原实现者按`content-fix-r1.md`统一修复；不勾CONTENT。
- Ruling: rich模板使用独立版本（允许builtin version2），保留version1原模板字节/hash。
  schema1首次save_authored是显式升级点，可绑定已知作者模板后继；create仍要求精确版本。
  代价是维护必要的旧模板资源，不开放任意registry/忽略hash，不改变现有已归档字节。

- 本轮设计baseline为HEAD `12f7ac285d1bba7f125b947a11a3deaa2fd5d330` 加现有dirty工作树。
  `project_management/`、Provider基础服务、report UI与本change均有未提交文件；
  不把它们全部当本轮新写或自动暂存。其他Scope UI、credentials、runtime、AI Base源码不修改。
- 新接口的源码/fixture/环境资格分开。现有W6.HTML和W7合成回执只按依赖复用。
- 原固定Vditor4.0.1候选已被上述Milkdown资格决定替代；只WYSIWYG，`#ID`唯一触发，
  无源码模式/裸ID/URL/hotkey/button补全，无全站React/Vue迁移。
- 对source事实/slot结构和额度采用contracts数值；网络/AI不在render/save锁内。
- HTML-first/emailcopy、原Markdown/Excel、双语、owner/CSRF/原Git writer都保留。
- 先人工模板闭环，再AI；未合格provider/profile明确unsupported，不以fake取代live验收。
- 本次连续性文档核对HEAD为`5d83933dc3d3c4f1673ec680c5ee2d03da8f9aed`。
  原作者层docs、Scope UI和`.github/skills/lsheng2-coding/config.json`仍有dirty改动；
  本窗口只写本change/当前guide/README，不修改他方源码，不自动commit/push。
- fragment v2增加受限RGB/高亮/链接内格式；同周累计、周seed、来源状态、独立票行和AR契约
  不从Markdown或原AI文本恢复。真正组件保真是EDIT的前置验证，不能静默降级。
- source/analysis/editorial基线分开；手动准备与Save不定稿；W7.SCHEDULE未启用。

本lane是一个实现wave，各叶串行交付并独立验证；若任一叶发现需要扩大authority或换组件，
回到PLAN.R重定范围，不循环局部修补。下一大波必须经过末尾REPLAN。

| Node | depends_on | Deliverable / readiness |
| --- | --- | --- |
| W6.AUTHOR.PLAN.R | 已有W6.HTML.EDIT/FINALIZE、已确认功能方向 | 边界与错误策略获准；设计review不是产品通过 |
| W6.AUTHOR.VA | W6.AUTHOR.PLAN.R | RA01-72、颜色/新旧schema、source保护、跨周/基线与外部资格矩阵完整 |
| W6.AUTHOR.CONTENT | W6.AUTHOR.VA | builtin模板的schema2可保存/重放/渲染，schema1原字节不变 |
| W6.AUTHOR.EDIT | W6.AUTHOR.CONTENT | 真实组件编辑/dirty/undo，保存重开格式不丢 |
| W6.AUTHOR.REFERENCES | W6.AUTHOR.EDIT | exact #ID -> scoped reader ->3项；错误不改原文 |
| W6.AUTHOR.TEMPLATES | W6.AUTHOR.REFERENCES | 用户模板到报告人工填写闭环，无AI依赖 |
| W6.AUTHOR.HISTORY | W6.AUTHOR.TEMPLATES | 一票一行、保存后的有效富文本/颜色跨日跨周原样继承，状态只取source |
| W6.AUTHOR.DAILY | W6.AUTHOR.HISTORY；本次恢复序列先经SDK020.JOIN.REPLAN | 明确baseline/meeting/来源选择、同日去重、人工未定稿保护；独立人工证据可复用 |
| W6.AUTHOR.DAILY.REPLAN | W6.AUTHOR.DAILY | 固定ASSIST target/profile/save消费者、证据失效范围及下一步 |
| W6.AUTHOR.ASSIST | W6.AUTHOR.DAILY.REPLAN + authoring profile前提 | task-run候选/审批/取消；无真实资格只做fake边界验证 |
| W6.AUTHOR.ASSIST.REPLAN | W6.AUTHOR.ASSIST | profile合成HTTP及provenance链可达，整周输入/验收条件固定 |
| W6.AUTHOR.JOIN | W6.AUTHOR.ASSIST.REPLAN | 同候选app/editor/storage/已安装SDK联合验证 |
| W6.AUTHOR.R | W6.AUTHOR.JOIN | 精确diff与RA证据review；外部未验证项单列 |
| W6.AUTHOR.REPLAN | W6.AUTHOR.R | 原剩余W6.RENDER/PUBLISH及W7逐项continue/amend，不删除未交付 |

### SDK020: Preparation And Integration Gates

Spec: [SDK contract](sdk-020-integration.md), [post-IP execution](sdk-020-post-integration.md),
[observable requirements](specs/sdk-consumer-integration/spec.md).
Goal: use the delivered 0.2.0a1 Python client with the original a2 pack, preserving app authority.
Architecture: existing app adapter plus isolated installed client; no new service or execution engine.
The user's scope ends at IP-SDK020-READY; post-IP nodes are specified, not yet released.

| Node | depends_on | owner_paths / deliverable |
| --- | --- | --- |
| SDK020.PLAN.R | accepted Base delivery and current user request | this change's connected specs, new current SDK guide; exact API/consumer/refusal/stop mapping and scoped publication |
| SDK020.ARTIFACT | SDK020.PLAN.R | owned .tmp/sdk-020-preintegration-20261105 artifact copy/target; hash-verified wheel, unchanged bundled pack and recorded dependency roots |
| SDK020.APP | SDK020.ARTIFACT | requirements-ai-task.txt, out/ai_task_contract.py, tests/test_sdk_020_compatibility.py, scripts/validation/run_project_sdk_preintegration.py and shared run_report_authoring_tests.py explicit isolation mode; narrow exact version migration |
| SDK020.PRE | SDK020.APP | same owned code/test paths; three explicit test files, no Base import or real sockets, source-bound JUnit/receipt |
| SDK020.REPLAN | SDK020.PRE | tasks + IP receipt; verify post-IP source/fixture paths, carry forward valid evidence, stop and wait |
| SDK020.JOIN | SDK020.REPLAN + explicit user release | scripts/validation/project_full_stack*.py, project_summary_support.py, project_management/tests/test_project_full_stack_lifecycle.py and tests for J020 cases; refresh old SDK expectations, then joined 0.2 HTTP and app acceptance |
| SDK020.JOIN.R | SDK020.JOIN | exact joined scope review and normal-stop evidence |
| SDK020.JOIN.REPLAN | SDK020.JOIN.R | tasks and post-IP appendix; refreeze DAILY/ASSIST, no new task authority |

Steps before IP:

1. Verify the Base release receipt and exact wheel/a2 manifest/21 file hashes. Copy only selected
   artifacts to the owned evidence root; do not install into the active main environment.
2. Install the copied wheel with `pip --no-index --no-deps --target` as specified in the SDK contract.
3. Add tests that load the real selected package and refuse unapproved version/mutated pack combinations.
   Add the bounded runner around the existing no-dotenv test entry; verify real socket attempts refuse.
4. Run the exact command in the SDK contract before production edits. Expected RED is
   ANALYSIS_CONTRACT_INVALID from the old package-version admission, not a missing dependency.
5. Change only the requirements pin and existing compatibility guard to SDK_VERSION='0.2.0a1'.
   Preserve manifest/profile/schema/evidence/owner/CAS logic and rerun the same explicit selection.
6. Check actual changed source sizes, whitespace, source/artifact identities and excluded dirty files.
   Write the readiness receipt only for nonempty passing tests with zero real network calls.
7. SDK020.REPLAN records `action=continue`, the next node, exact supporting evidence and remaining
   post-IP gates, then waits. If a real dependency gap is found, record amend and the precise gap;
   do not start a Base service to discover it through a full workflow.

Production API signatures, runner invariants, S020-01..08 and J020-01..06 are specified in the two
appendices. Use TDD at the actual app boundary; these are not a second implementation checklist.
The existing full authoring scope remains below; none is closed by the SDK preparation commit.

### CONTENT: Versioned Editing Foundation

Files：新增 `project_management/app/domain/report_authoring.py`、
`report_authoring_validation.py`、`reporting/fragment_renderers.py`；
修改 `app/api/reports.py`、`app/domain/report_draft_values.py`、
`app/domain/report_publication_contracts.py`、`services/report_drafts.py`、
`storage/report_drafts.py`、`storage/report_publication_packets.py`、
`reporting/html.py`、`services/report_publication.py`、`services/report_publication_reads.py`
及现有report namespace validator。400行以上模块按本职责拆辅助，不重构整个归档模块。
Tests：`test_report_authoring_content.py`、`test_report_authoring_migration.py`，RA01-06/20。
新增RA41/46/66：fragment v1 reader与v2 paint、链接内runs、颜色hash、未知样式拒绝；
同步schema2 context/manifest/intent exact字段及消费者。先独立文档，矩阵context由HISTORY接入。

Consumes：schema1 DTO、canonical_bytes、write_bytes/root-stage锁。
Produces：RichTextFragment、AuthoredEdit、AuthoringTemplateSelection、schema2 reader/renderer、
create_authored/save_authored；此叶只启用builtin selection，user selection明确unsupported，
由TEMPLATES接入真实库，不能放test-only生产fallback。

1. RED：旧`<script>`/`**text**`仍literal；伪source目标、未知节点、错误签名拒绝。
2. RED：同command断在revision/head前后重放只产生一版；旧hash不改；v2intent/manifest精确匹配。
3. 实现v2分派、allowlist与safe renderer，原journal和六文件namespace同时升级全部consumer。
4. 跑validation的CONTENT命令及原 `test_report_drafts.py`、
   `test_report_publication_security.py`，不重跑全部Base或真实provider。
5. 退出：RA01-06/20、schema1字节、quota与owner拒绝均有证据；可渲染/下载新的合法片段。

最小反例示意，fixture用真实public service：

```python
def test_legacy_text_remains_literal(legacy_draft, authoring_service):
    before = legacy_draft.revision_hash
    loaded = authoring_service.get(legacy_draft.actor, legacy_draft.project_id,
                                   legacy_draft.stage_id, legacy_draft.draft_id)
    assert loaded.revision_hash == before
    assert loaded.edits[0].text == "**not rich** <script>literal</script>"
```

### EDIT: WYSIWYG Host Adapter

Files：新增 `ui_web/static/js/report_editor/{index,adapter,fragment_codec}.js`、
`ui_web/static/vendor/milkdown/7.23.0/` 固定bundle/许可证/manifest，
对应局部build入口/lockfile；不引入全站前端构建框架；
修改 `templates/projects/reports/editor.html`、`ui_web/report_forms.py`、
`views/project_reports.py`、`facades/project_reports.py`、`static/js/project_reports.js`；
locale定点追加，不重写全局main.js。
Tests：`ui_web/tests/report_editor_test.mjs`、`test_report_authoring_views.py`，RA02/03/07-11/33/34。
Consumes：CONTENT schema2、原target/save/clipboard/finalize。
Produces：contracts的EditorHandle、真实mounted编辑区与v2 payload。

1. RED：link/list/table/文字颜色/高亮编辑保存重开不丢，补全不清paint；
   只改颜色也dirty，历史淡化不覆盖显式颜色；source区不可改；源码开关不存在。RA41/42。
2. 固定manifest、Milkdown及传递依赖/图标本地资产，禁localStorage和未配置upload。
3. 用公开组件API实现fragment codec/target级编辑，DOM不作为服务端authority。
4. 接dirty/command/Copy/Finalize，替代textarea＋iframe编辑；不关闭CSP来修预览错误。
5. 运行Node/views及真实组件桌面小样；语义不能映射则回PLAN.R，不静默降纯文本或fork核心。

### REFERENCES: Scoped Hash Completion

Files：新增 `project_management/app/{api,domain}/report_completion.py`、
`services/report_completion.py`、`out/provider_references.py`；
修改公共 `app/api/capture_archive.py`、`services/report_archive_reads.py`、
`services/report_sources.py`以提供typed membership projection；
新增 `provider_sync/app/{api,spi}/references.py`、`services/reference_lookup.py`、
`out/jira_reference.py`、`out/hsdes_reference.py`；
新增 `ui_web/views/report_completion.py`、`static/js/report_editor/completion.js`，
仅在现有 `urls.py`、locale/defaults_metrics.py追加本能力route/config。
同一叶拥有`storage/report_reference_admission.py`与`services/report_reference_receipts.py`；
窄扩展`provider_sync/app/spi/capture.py`的retry_after、AccessError HTTP metadata及
`services/capture_session.py`/`out/capture_reader.py`相应消费者，保持旧code。
Tests：RA07-20、`test_report_completion.py`、`provider_sync/tests/test_reference_lookup.py`。

Consumes：Stage、ScopeMembershipSnapshot、公共connection resolver、EditorHandle。
Produces：CompletionResult、签名ReferenceObservation和safe fragments。

1. RED：范围外/unknown membership/foreign actor为0上游；404不能推断确定不存在。
2. 实现membership read与最小字段reader，Jira/HSD独立schema/auth；不借capture做full fetch。
3. 接#唯一触发、防抖/限流/epoch、3变体、disabled owner和错误提示。
4. HSD在无实际字段/auth资格时拒绝；tests注入合成SPI，不冒充live。
5. 跑REFERENCES/Node命令；source/hash/Git/模型账目不变；被移动token不能写入。
6. Readiness补充：2026-11-03Confucius只读复核指出receipt关联与live admission两处设计缺口；
   已在contracts Reference Association Algorithm和completion Deployment/Transport中精确定义，
   不再用完整编辑段落hash拒绝合法人工改字/paint，不允许只凭client reference_id信任provider。
   验证新增跨service第31次拒绝、锁外网络、disabled0上游、404阶段语义和Retry-After；
   Confucius对两处amendment窄复核为CODE_READY，见
   `.tmp/authoring-main-20261103/references-readiness.md`；不启用真实资格，
   仍等待EDIT行为门禁后才进入REFERENCES。

```python
def test_absent_member_never_fetches_outside_scope(report_case, reader_that_raises):
    service = report_case.completion(reader=reader_that_raises)
    result = service.suggest(report_case.actor, report_case.project_id,
                             report_case.stage_id, report_case.draft_id,
                             report_case.request("#ABSENT-1"))
    assert result.error.code == "COMPLETION_OUTSIDE_REPORT_SCOPE"
    assert result.options == ()
```

### TEMPLATES: User Library And Manual Fill

Files：新增 `project_management/models_report_templates.py`，现有 `models.py`显式导入；
新增下一个未占用编号的 `report_templates` migration（编码前读实际叶，不抢其他Agent编号）；
新增 `app/{api,domain}/report_templates.py`、`services/report_templates.py`、
`out/orm_report_templates.py`、`reporting/template_compiler.py`；
新增 `ui_web/{report_template_forms,facades/report_templates,views/report_templates}.py`、
`templates/projects/report_templates/{list,editor}.html`、
`static/js/report_editor/template_builder.js`，定点接项目导航/URL。
Tests：RA21-28，`test_report_template_library.py`、`test_report_template_compilation.py`。
document/fill policy v2的meeting_matrix定义与daily_note_instructions一并校验；
模板模式是规则，具体票据位置/历史由HISTORY管理，不能把企业note复制进模板。

Consumes：CONTENT schema、EDIT adapter、Project owner/ORM、builtin registry。
Produces：ReportTemplateService、revision/usage/command/use、pinned template_snapshot、
ready/draft校验与可视化创建入口。

1. RED：任意创建/复制、CAS/quota/事务rollback、archive-vs-use；模板字串无执行。
2. 实现ORM service及content/slot/data compiler，验证各data块必需行字段，不仅检查块名称。
3. 创建模板v1->报告填写->模板v2；已有draft仍用v1，use先于archive可恢复，新use被拒绝。
4. 库GET/选择/排版不调用AI/工单；copy只复制结构/固定模板文字，无报告业务值。
5. 跑TEMPLATES、合成DB迁移、桌面人工填写；不迁移用户db或清其他运行。
6. Readiness补充：Cicero定位user-template registry接线及先于HISTORY的context缺口，
   已在contracts Pinned User Template Rendering/Standalone Before Continuity细化
   `UserTemplateSelection`、完整use request绑定、`render_pinned`及独立schema1人工链。
   v2 matrix库结构可保存，但无prepared context仍拒绝创建报告，不假造HISTORY。
   该叶同时拥有原draft/render/finalize/schema reader的精确新增消费者；source/Git authority不改。

### HISTORY: Daily and Weekly Continuity

Files：新增 `project_management/app/{api,domain}/report_continuity.py`、
`services/report_continuity.py`、`reporting/meeting_matrix.py`、
`storage/report_continuity_reads.py`、`models_report_series.py`、对应未占用migration；
同职责新增`storage/report_prepared_context.py`及context reader，
按continuity Prepared Context Contract提供DAILY将消费的真实服务器seed，不接受HTTP自报历史；
修改 `models.py`、`services/report_drafts.py`、`services/report_publication.py`、
`services/report_publication_reads.py`、`storage/report_publication_packets.py`、
schema/namespace validators；UI经 `facades/project_reports.py` 提供period/context和常驻备注；
新增 `ui_web/report_series_forms.py`、`views/report_series.py`、
`templates/projects/reports/series.html`，经公共create/list/get/save policy API接
`reports/series/`、detail/policy routes，不能隐式按Stage/title建系列。
Tests：`test_report_continuity.py`、`test_report_week_rollover.py`、
`test_report_meeting_matrix.py`、`test_report_continuity_publication.py`，RA43/47-57/63-69。
同叶core窄扩展`services/report_templates.py`的continuity_prepare use和read_use，
按continuity Prepared Context Contract核验持久use hash，不在stage锁内写DB。

Consumes：CONTENT片段v2、模板v2、既有SourceKey/ReportSelection和六文件publication。
Produces：continuity附录的SeriesPolicyRevision、MeetingIdentity、DailyNote/ReportAction、
DailyAuthoringContext、RowOrderSnapshot，及create/save series、preview/read_period公共服务。
series设置用Project ORM事务；daily内容用原draft/publication writer，不建第二真相库。

1. RED：人工删改/颜色/链接定稿后day2/day3逐片段相同，旧AI句子不复活；比较canonical fragment。
2. RED：共享PR三行、raw source状态前缀、无历史状态不倒填、稳定append/显式reorder/移出重返。
3. RED：series显式create/get/save policy-CAS，GET不创建；新周最后有效note + 更早未结束AR + 常驻备注；保留原日/色/状态，
   周五缺失、跨年、未知日历、另一Stage、历史坏hash均有明确反例。
4. 实现按PublicationRef读有效context，按note/action稳定ID去重，周内累积与周seed投影；
   生成新的context/hash并复用原revision/六文件校验，过限不裁剪。
5. 实现baseline-CAS和commit后可重建head、weekly_view/旧日correction不抢head；
   失败按原packet恢复，不重新解析模型/工单。
6. 运行validation的HISTORY命令与原report publication/source安全用例，
   验收状态是“真实持久化/渲染链通过”，不是样张脚本通过。
7. Readiness补充：Volta指出同源重放可能复活人工删句及HISTORY/DAILY context生产循环，
   已在continuity的Current Day Without New Source Content/Prepared Context Contract明确
   initial/unchanged/pending分支、服务器空槽note ID、不可变seed及commit前baseline CAS。
   不把no_work独自作为新日note生成依据，不在seed建立第二套业务状态。

反例使用公开服务和合成日期：Day1改为红字并删AI一句 -> 定稿 -> Day2 -> Day3 ->
NextWeek，断言每个继承note.body_hash等于Day1定稿hash，同时原publication字节不变。
独立验证输出日期不同导致全文HTML hash不同是预期，不能错用全文相等判断内容继承。

### DAILY: Explicit Draft Preparation

Files：新增 `project_management/app/{api,domain}/report_preparation.py`、
`services/report_preparation.py`、`storage/report_preparations.py`；
修改原 `services/project_runs.py`、其draft构造消费者、run request validator和
`management/commands/project_run.py`；新增 `ui_web/views/report_preparations.py`、
相应forms/facade，定点接Stage reports模板/URL/locale，不改全局调度或他仓服务。
Tests：`test_report_preparation.py`、`ui_web/tests/test_report_preparation_views.py`，
RA44/52/53/58-64/68；旧project_run schema1重放回归。
明确同时覆盖`app/domain/run_values.py`、`run_admission_values.py`、原operation存储/recovery
及worker版本分派，按continuity Daily Worker Dispatch冻结schema2，旧schema1字节不变。

Consumes：HISTORY preview/context/period、原run worker、已合格source/AI接口。
Produces：ReportPreparationService.prepare、BaselinePreview、PreparationResult、
持久meeting slot/固定意图、手动“生成今日草稿”和从saved capture人工填写入口。

1. RED：只有POST准备可运行；GET/切周/午夜零副作用；manual_only不依赖Base。
2. RED：I/O前持久占位；同command不同payload拒绝，不同command同meeting仅一operation，
   返回原effective selection+差异提示，已有编辑直接返回；
   前日未定稿默认pending，显式确认gap记录不删除原稿。
3. 实现先冻结series/template/baseline/meeting，再沿原run推进到draft_ready；
   changed_items模式只在明确授权下分析，旧source/AI水位与editorial分别维护。
4. 接显式source刷新/reprepare API及POST，校验终态operation/draft revision后才替换active slot，
   原draft/fragment保留，冲突返回review要求不覆盖；scheduler不能调用；
   original-command恢复保留runKey/预算/原日期，source drift检查不减弱。
5. 验证Save/AI接受/weekly_view不推进daily baseline；只有用户精确Finalize且Git确认推进。
6. 运行DAILY命令/原worker相关消费者，确认旧schema1操作和非编辑已发布文件可读。
7. Peirce只读readiness已定位worker总是legacy草稿/总是要求Base的实际缺口；
   版本化准备意图先于capture、context_hash在compose后生成，manual_only backend=null，
   saved_capture不派worker。不能提交尚未存在的context_hash或创建多余schema1草稿。

### ASSIST: Explicit Candidate Filling

Files：新增 `project_management/app/{api,domain}/report_assists.py`、
`services/report_assists.py`、`storage/report_assists.py`、`out/report_ai_task.py`、
`ai_bundle/report-authoring/{profile,input.schema,output.schema}.json` 与受控prompt；
新增 `ui_web/views/report_assists.py`、`static/js/report_editor/assist.js`，
定点改URL/locale。Tests：RA29-32/39/45/62，`test_report_assists.py`。

Consumes：已保存draft/template/slot、Base task-run/1、安装SDK和固定pack。
Produces：AssistStatus/Candidate、input/result provenance、Apply-to-dirty及Save再次校验。

1. RED：wrong source/target/profile/hash、缺evidence、cancel unknown和late result拒绝。
2. 固定authoring profile/schema与counterpart资格，不改review-1包冒充新用途。
3. 复用SDK请求/观察/取消，同stage受控runtime记录，网络在锁外，无新supervisor。
4. 面板展示候选，Apply/Reject；Apply只成dirty，Save才持久，禁止自动finalize。
5. 跑ASSIST和实际安装SDK+fake/Base合成case；真实模型需新资格/授权，
   Base不可用不挡人工模板，不把缺环境记成通过。

### JOIN, R And REPLAN

JOIN owner_paths为前述实现闭包、
`ui_web/tests/test_report_authoring_browser.py`、
`ui_web/tests/test_report_authoring_week_browser.py`、
`scripts/validation/run_report_authoring_week.py`、
`project_management/tests/test_report_authoring_exports.py`、当前guide/本change。
不启动旧保留演示或改另仓worker。Consumes：各叶固定hash/tests；
Produces：RA35-40/67-69、原HT28-30相同候选结果与未决列表。

1. 先验证app＋schema2＋真实编辑器＋fakeProvider＋BaseHTTP合成executor＋临时Git。
2. 一条用户链：模板->Stage/已存capture->人工填写->#ID成功/错误->AI候选接受/拒绝->
   Save/reload->stale第二窗口拒绝->copy/download->显式finalize->原字节下载。
   再追加真实编辑器着色/删除->次日->第三日->跨周seed，验证来源状态、AR、stable order、
   旧fragment canonical hash与截图格式；不把静态样张的渲染检查当成本链通过。
3. 新片段在HTML/plain/Markdown/Excel输出均验；Outlook、real Jira/HSD是获准环境单独资格。
4. R围绕精确diff/证据，不重做全库审计；未完成原W6/7、live/Outlook不勾选。
5. REPLAN裁定continue/amend/supersede/retire，记录 `refreeze_actions`、
   `updated_artifacts`、`rerun_gates`、`post_refreeze_preflight_result`；
   后续原W6.RENDER/PUBLISH消费本lane变化前必须依赖此gate。
6. 2026-11-03用户追加的整周full-stack验收为JOIN必需场景：完整走
   2026-10-26..30（合成ISO WW44）及11-02换周，相同工单数据、逐日不同人工note/
   颜色/格式，Save/reopen/Finalize/正常重启并保留每日证据。
   精确步骤与拒绝条件见validation第7节；不是先执行此场景跳过HISTORY/DAILY实现，
   不修改系统日期、真实工单或增加真实模型授权。

Preflight：Registry -> consumer -> RA01-72 -> node及唯一checkbox一致，RA70-72归W7.SCHEDULE。
只认实际退出结果，collect-only/空选择/目录存在/上游probe不是行为通过。
新增方法须有production consumer；命令见validation，缺源码时不执行缺路径命令。
小型反例先于全栈，新信息才升级。本设计窗口没有产品节点完成，不改旧[x]。

### W7 Schedule Boundary

W7.SCHEDULE依赖W6.AUTHOR.REPLAN、W6.REPLAN及W7.DEPLOY的运行身份/凭据资格；
W7.PROTECTION管理共同激活边界。owner_paths限定
`project_management/management/commands/project_run.py`、`out/report_schedule.py`、
`app/domain/report_schedule.py`、`tests/test_report_schedule.py`、相关部署配置与运维文档。
Consumes：同一ReportPreparationService和meeting slot；Produces：显式启用的调度adapter。
先用合成clock执行RA70-72，再按单独授权测试真实任务。默认disabled、misfire=skip，
不补造日报、不自动finalize；本次文档更新不注册任何系统任务或启动服务。

### 2026-11-03 Design Receipt

本轮仅改规格/文档，新增5份作者层文档（含report-authoring能力delta），
父design/proposal/HTML接口handoff与current guide同步；旧Chiplet仅更新导航与研究状态。
OpenSpec `validate add-provider-neutral-project-reporting --strict --no-interactive` 最终exit0；
初次因旧Requirement加入过长说明而strict失败，已把独立行为保留在新capability并重验。
新5文件11个本地链接、代码围栏/空白、40个唯一RA场景、
10个唯一且未勾选W6.AUTHOR节点通过机械核对。文档通过不等于这些场景已执行。

Hooke（GPT-5.5/xhigh）对authoring-v2/contracts/completion做一次独立设计review，
发现2个P1/2个P2：membership证明、schema2精确定稿包、系统数据块必需输出和template-use并发。
修订增加typed membership projection、V2 manifest/intent exact keys、
Data Projection Invariants、DB ReportTemplateUse线性化及对应RA15/23/26，
限定复查确认4项closed，无新直接P1/P2。它不是整库审计或完整测试架构资格；
W6.AUTHOR.PLAN.R/VA保留未完成，待用户确认详细设计和执行包最终冻结。

既有whitespace门禁exit0。size门禁仍因原有
`ui_web/tests/bug_trend_scope_config_test_support.py`650行、
`ui_web/tests/test_bug_trend_scope_config_views.py`624行超过600失败，未修改/豁免。
本轮文件均是Markdown；当前size规则不覆盖openspec/**/*.md，不能以零选中称独立size通过。
未运行产品pytest、browser、Provider/模型、migration或服务启动。
工作期间另一方提交将HEAD由12f7ac2推进至5d83933；保留其产品与任务提交，
本代理没有执行commit/push，也不把他方提交当作本轮新功能已实现。

### Continuity Design Receipt

2026-11-03本次只补规格/架构/执行设计：report-continuity为同change新附录，
同步authoring/contracts/spec/validation/tasks、父design/proposal/handoff、README和current guide。
新增HISTORY/DAILY后共12个W6.AUTHOR唯一未勾选节点；RA01-72共72场景，
其中RA41-72为本轮新增，RA70-72归默认禁用的W7.SCHEDULE，非当前手动交付资格。
原13项本地样张测试不是这些生产场景的验收证据。

已执行：`openspec validate add-provider-neutral-project-reporting --strict --no-interactive` exit0；
12份文档的102个本地链接/围栏、72个唯一RA、12个未勾选节点及HISTORY->DAILY->ASSIST依赖
机械检查通过；既有diff whitespace脚本和限定范围`git diff --check`通过。
全局size仍仅因原未修改的Scope UI两测试文件650/624行超过600失败，未修改或豁免。
未运行manage.py/产品用例、浏览器、provider/模型、迁移、系统调度或Git提交推送。

Bohr（GPT-5.5/xhigh）独立审阅提出1个P1和2个P2：
矩阵非必需、series创建API缺失、同日race与command冲突混淆。
修订加入v2矩阵ready/prepare硬门槛、明确series/API/HTTP/UI所有权、
两层幂等和显式reprepare；限定复核三项均closed。
这不是全库审计、产品测试或PLAN.R/VA最终实施资格，全部实现节点仍未完成。
实际外部workweek映射、具体provider/profile、编辑器paint往返和scheduler运行身份
仍按相应任务资格验证，不以文档通过冒充环境已就绪。

## Prior HTML Delivery

### HTML Report Delivery Packet

Goal: open an actual accepted-summary draft, add a note, copy/download a
self-contained HTML report and optionally finalize it into the stage data Git.
Architecture: read-only archive projection -> versioned renderer -> local draft
revisions -> explicit publication using the existing append owner.
Stack: existing Python/Django/Bulma/htmx, Django escaped templates, standard
browser ClipboardItem; the separate editor Agent now owns the approved
open-source WYSIWYG integration. No AI Base API change is needed.
Spec: html-report-authoring.md and specs/project-reporting/spec.md;
cases/commands: html-report-validation.md HT01-HT32.
Use Superpowers TDD/executing-plans and the existing independent review policy.

Global constraints: owner/CSRF checks; no provider/model side effects; English
generated content and literal source/human notes; independent data root; no
disk-free checks, email send, automatic push or new public capture entry.
Keep the current W2 synthetic demo and W5.JOIN artifacts untouched.
The following steps are implementation guidance; only the checkboxes above
maintain status.

| Leaf | Depends on | Exact ownership and consumers | First RED / independent exit |
| --- | --- | --- | --- |
| W6.HTML.PLAN.R | W5.JOIN.R and user-approved HTML direction | This change's HTML appendices/tasks/spec and current guide; source map for reused MIG-12 and existing archive reader | Fix original-source/edits/finalization/clipboard contract gaps; freeze actual donor blobs before copying; do not mark all W6 ready |
| W6.HTML.SOURCE | W6.HTML.PLAN.R | New `project_management/app/domain/report_contracts.py`, `app/api/reports.py`, `services/report_sources.py`, `services/report_archive_reads.py`; extend `app/api/capture_archive.py` and `services/capture_archive.py` for the public read boundary | `test_report_source_reader.py::test_pinned_public_read_returns_original_acceptance`; HT13/14, source cutoff/owner/hash validated through real archive |
| W6.HTML.RENDER | W6.HTML.SOURCE | New `project_management/reporting/{templates,html,validation}.py`, `reporting/templates/{daily_standup,weekly_timeline}.html`; `tests/test_report_{templates,html}.py` | HT09 RED first; HT01/02/09-12/32 GREEN and deterministic output with all expected fields; no dynamic source fetch |
| W6.HTML.EDIT | W6.HTML.RENDER | New `services/report_drafts.py`, `storage/report_drafts.py`, `app/domain/report_edits.py`, `tests/test_report_drafts.py` | HT15 RED first; HT15-19 plus quota/owner cases GREEN; saved revisions and command replay with Git HEAD unchanged |
| W6.HTML.FINALIZE | W6.HTML.EDIT | New `services/report_publication.py`, `services/report_archive.py`, `tests/test_report_publication.py`, `test_report_publication_security.py`; narrowly extend existing archive namespace validation | HT20 RED first; HT20-24/31 with actual temporary Git, original commit replay and no source/AI side effects |
| W6.HTML.UI | W6.HTML.FINALIZE and W2 | New `ui_web/{project_report_forms,project_report_clipboard}.py`, `facades/project_reports.py`, `views/project_report_views.py`, `templates/projects/reports/{editor,publication}.html`, `static/js/project_report_clipboard.js`, `tests/test_project_report_views.py`; minimal `urls.py` and existing locale additions | HT25/26 RED first; HT25-29 GREEN, exact saved-revision copy and confirmed commit through actual services |
| W6.HTML.R | W6.HTML.UI | Independent bounded candidate review plus same-candidate synthetic browser/Git records and current-doc sync | No unresolved correctness/security issue; HT30 actual email paste separately identified, never inferred from clipboard-only success |

SOURCE publishes `ReportSourceReader.read` and the DTOs in the design.
The exact first SOURCE packet is [html-source-packet](html-source-packet.md);
it fixes the current input hashes, original-acceptance validation, zero-write
read boundary and HT13/14 test construction. Future baseline/publication selection
is explicitly refused until the dependent resolver exists, never silently ignored.
RENDER consumes that immutable DTO and returns `RenderedReport`.
The exact renderer/edit-projection interfaces are in
[html-renderer-packet](html-renderer-packet.md), with no storage/AI side effects.
EDIT consumes the source reader/renderer and publishes `create/get/save/render`.
Its storage ordering and FINALIZE exact file/receipt/lineage operations are in
[html-draft-packet](html-draft-packet.md); no additional Git writer is introduced.
FINALIZE extends the same ReportDraftService with `finalize_and_commit`,
`resume_finalization`, `get_publication`, `read_artifact`, using one archive owner.
UI calls only these public services; its clipboard helper handles versioned DTO
serialization, not report semantics or Git.
Exact forms, clipboard payload, safe previews and desktop interaction cases:
[html-workbench-packet](html-workbench-packet.md).

Before implementing each leaf: add its named failing test, run the exact node to
observe the missing behavior, implement only that boundary, run that node plus
the leaf's matrix, then update current docs and perform its scoped review.
Do not use a missing unrelated environment as the expected RED.
The first code step after PLAN.R is to create
`project_management/tests/test_report_source_reader.py` with HT13 and HT14;
run `.venv/Scripts/python.exe -m pytest project_management/tests/test_report_source_reader.py -q`.
Expected initial RED: the new public report-source API does not yet exist.
Test vector: a real isolated accepted record yields its original input/result
hashes; another owner gets refusal and no draft/report filesystem growth.

Native fixture composition is part of the owning leaf, not a separate platform.
Use existing W5 source/acceptance and W2 UI fixture patterns but a fresh authorized
external data root; never copy real credentials or mutate prior test receipts.
Finalization/HTTP packet review must verify exact source/query and lock consumers
before adding the namespace. Unchanged Base/SDK evidence is reused, not rerun.

W6.HTML is a report-authoring slice, not the entire reporting pipeline.
HT03-08 and production multi-day history depend on W4.DELTA/EVIDENCE and the
complete per-item publication projection; retain them under W4/W6.R with
`project_management/tests/test_report_timeline.py`.
W7.RUN remains necessary for a user to launch new capture/analysis from the UI.
Preflight shared interfaces: SOURCE -> RENDER uses a serialized immutable
ReportSourceSnapshot; RENDER -> EDIT carries exact content/template hashes;
EDIT -> FINALIZE carries expected revision and original bytes; FINALIZE -> UI
returns a verified commit receipt, not a mutable draft state. W7 will call the
same capture/summary/draft public services and will never auto-finalize a report.
These interfaces agree with HTML sections4-7; the SOURCE-specific temporary
baseline refusal and later full baseline support have distinct exit criteria.
The old W3/W4/W5/W6 parents are not marked complete by this exception.
Full Markdown/Excel work stays W6.RENDER/PUBLISH. The former user-template-designer
backlog is promoted to the constrained visual library in W6.AUTHOR.TEMPLATES.
Arbitrary executable template upload, pixel-layout design, offline HTML reimport
and multi-client/mobile testing remain backlog. The new lane does not relabel
the first non-editor workflow qualification.

W1.REPLAN: Harvey (GPT-5.5/xhigh) independently reviewed workbench-plan.md and the actual
BasicAuth, Project API and UI boundaries; no blocking design/validation gaps remained.
refreeze_actions: amend W2 with explicit verified BasicAuth identity, opt-in local_operator mapping,
server-held expiring preview, expected-definition hash guard and Django gettext.
W3-W7 continue under their existing mandatory pre-wave refreeze gates; no capability is retired.
updated_artifacts: workbench-plan.md, design.md, specs/project-reporting/spec.md, tasks.md.
rerun_gates: W1.REPLAN and strict OpenSpec (PASS).
post_refreeze_preflight_result: manual registry/producer-consumer/owner-path/U01-U12/ledger
dependency check PASS. W2.N1 depends_on W1.REPLAN; W2.R requires same-candidate functional evidence.
One Implementation Engineer owns W2 source/tests; coordinator owns this ledger and later-wave design.
No second implementation writer or duplicate progress ledger. Browser validation/independent W2.R
remain coordinator gates; current approval does not mark W2 complete.

W3.CREDENTIALS packet preparation: provider-foundation.md and provider-foundation-source.json
are the exact next packet. An independent GPT-5.5/xhigh review identified TLS trust identity,
orphaned candidate inventory and transport negative-case gaps; all three amended and limited
recheck passed. This is conditional design readiness, not W2.R, W3 code or live credential adoption.
Internal order A -> B -> C is serial; full W3.CREDENTIALS exit still gates W3.ARCHIVE.
Future W3 capture/list/dependency/attachment/HSD and W4 remain in scope under their own detailed gates.

W1 review owner_paths above. W2 UI owns only new project-specific facade/view/template/static/tests and necessary
url/nav hooks, avoiding dirty scope editor. W3 adapters consume existing provider APIs; W4 history owns a new
archive service; W5 AI client consumes externally delivered contract; W6 publication owns reports;
W7 operation/runtime owns launcher adapters. Each REPLAN refines these into exact files before execution.
Remaining high-risk waves cannot be executed until their predecessor REPLAN and validation signoff resolve APIs.
The user-authorized W5.JOIN lane has its own precise packet/signoff and actual
prerequisites above; the old whole-wave ordering does not block that lane.
They are not implemented by placeholder success, nor silently dropped when dependencies are unavailable.
C0 is independent of W1.R/BASE-B and owns only the dev validation script/environment/docs listed in
sdk-intake-plan.md. W4.REPLAN requires C0.R plus W4.R; no app data/service code is pulled forward into C0.

Optional W5.CHAT is not a prerequisite of W5.R or report completion when disabled. Track its residual scope
explicitly; no marking implemented without its own APP-06..08 tests. W7.PROTECTION code/interface verification
is separate from activation: formal schedules, network backup targets and machine reboot remain independently authorized.

## Integration Planning Amendment

2026-11-01 user asked whether app-owned CLI/skill/prompt integration and donor modules were fully enumerated.
Answer before this amendment: no, only broad migration groups existed.
Now `application-integration.md`, `provider-access.md`, `migration-catalog.md` and
`integration-execution.md` provide concrete ownership, deliverables, restrictions and leaf mapping.
This round is planning only: no token has been read/copied, no new Provider CLI or runtime skill installed,
no old code migrated, no product tests/online connection performed for these new capabilities.
W1.R remains pending as previously recorded; this amendment does not waive its gate.
Independent planning review (GPT-5.5/xhigh, Archimedes) identified eight clarification issues;
all were fixed and the limited follow-up found no remaining P0/P1/P2 planning issues.
This is not a counted W1 implementation review or runtime qualification.
Validation: strict OpenSpec pass; 9 documents/13 relative file links pass; 23 leaf packets map
to the unique task ledger; 72 representative donor paths exist (not full dependency closure).
Whole-worktree file-size failures remain the same two unrelated pre-existing scope test files;
whitespace check passed. No new product tests or live calls were run for this docs-only amendment.

W2 refreeze questions already identified, not blockers for W1: authenticated browser owner mapping
must be explicit (CLI local_operator is not a web credential); creating/owning a browser project cannot
be authorized by posting a subject. Scope editor is independently dirty; use existing public APIs.
Keep all W2 writes behind CSRF and verify source preview before immutable stage confirmation.

## W1.N1 Implementation Packet

Files:
domain/contracts.py, validation.py, service.py: DTOs, error mapping, pure orchestration.
app/spi/{catalog,repository}.py: exact Protocol dependencies.
out/{dashboard_scope_catalog,orm_repository}.py: public source API translation and transactions.
models.py, apps.py, migrations/0001_initial.py: persistent tables.
app/api/__init__.py, container.py: application entry.
management/commands/project_catalog.py: production consumer, safe JSON.
tests/test_project_catalog.py, test_scope_catalog.py, test_project_command.py, fakes.py.
Tests additionally include test_project_transactions.py for rollback/capacity/archive races and
test_project_cli_process.py plus process_settings.py for separate CLI processes against a temporary database.

Consume/produce signatures are frozen in design section2. Do not create an HTTP endpoint in this wave.
Local JSON command is the production path, not a test-only scaffold.

Steps:
1. Add a failing test that uses real Project API to create arbitrary Alpha project, then reload/query it.
   Example: `api.create_project(ProjectActor("operator-a"), key="alpha", name="Alpha")`;
   assert reloaded key/name/id, without deriving expected values from production hash helpers.
2. Run focused tests; verify failure because module/behavior is absent, not missing dependency.
3. Implement pure DTO/service + ORM/migration + API and application registration.
4. Add failures for owner mismatch/archive/duplicate identity and frozen scope.
5. Implement source catalog using explicit Jira binding or HSD profile query. Tests use synthetic registered profiles
   and real scope ORM; no remote methods. Sentinels at external transport may forbid accidental calls.
6. Add command tests create/list/show/add-stage/archive, including nonzero safe failures and no arbitrary actor.
7. Implement CLI, run focused and affected provider/scope tests, then migration drift/check/gates.
8. Update current docs and only proven checkboxes, prepare independent scoped review.

## W1 Validation Matrix

| ID | Test file / scenario | Wrong implementation rejected |
| --- | --- | --- |
| P01 | test_project_catalog: create/reload/list two projects, separate actors | hardcoded project/default source, ownerless queries |
| P02 | test_project_catalog: same key same/different name; paginated list | duplicate project/audit, empty false success |
| P03 | test_project_catalog: same stage key same/different definition/name | silently rebind stage or duplicate audit |
| P04 | test_project_catalog: archive/write/read, source missing, external deletion | archived writes, cascade loss, live-only history |
| P05 | test_scope_catalog: Jira exact binding/provider; raw JQL change; mapping-only change | inferred profile, global default query, metric hash invalidates membership |
| P06 | test_scope_catalog: two HSD query profiles, missing reference/hash, Jira scope supplied | HSD disguised as Jira or only one bundled profile works |
| P07 | test_scope_catalog: endpoint change/bad endpoint/credentials canary/unknown provider | endpoint drift ignored, secret-containing snapshot, provider fallthrough |
| P08 | test_project_catalog: second resolve drift, transaction/duplicate bound, max stages | stale source commit, failed write advances state |
| P09 | test_project_command: all CLI commands, JSON and errors, owner not configurable | test-only API with no production consumer or unsafe errors |

Commands from Dashboard root (explicit interpreter `.venv/Scripts/python.exe`):

```powershell
$python = Join-Path (Get-Location) '.venv/Scripts/python.exe'
& $python -m pytest project_management/tests -q
& $python -m pytest bug_metrics/tests/test_api_scope_config.py bug_metrics/tests/test_scope_provider_binding.py -q
& $python manage.py makemigrations project_management --check --dry-run
& $python manage.py check
& $python scripts/check_file_size_limits.py --include-untracked
& $python scripts/check_diff_whitespace.py --include-untracked
openspec validate add-provider-neutral-project-reporting --strict --no-interactive
```

Test DB isolated by pytest/Django; no `manage.py migrate` on user's default DB.
Schema check/read commands do not authorize writes to runtime catalogs. Report interpreter/version and selected tests.
Evidence commands use exact target paths; no collect-only/skip/empty selection as pass, no shell failure suppression.
No copies of enterprise queries/tokens in committed test fixtures.

## Preflight / Refreeze

PLAN.R checks Registry -> propagation -> consumer categories -> nodes/ledger -> validation mapping.
Manual preflight is accepted by project profile; this plan does not build another DAG checker.
On non-continue REPLAN record `refreeze_actions(action,reason)`, `updated_artifacts`, `rerun_gates`,
and `post_refreeze_preflight_result(method,result)`. No implementation of next wave before PASS.
No deterministic completion date or percent; evaluate next user outcome, not total green test count.

## AI Base Counterpart Boundary

2026-11-01用户要求从整个基座角度列出独立增强，不只满足本应用。
`ai-base-enhancement-request.md`定义E1-E9公共能力及BASE-A/B/C/D交付分组，
不在此维护基座实施状态。W5.APP消费实际profile/schema loader与版本包；
W5.CLIENT消费Run/输入/结果/身份/usage/恢复API；W5.ACCEPT保留本地领域校验。
BASE-A fake pack只支持合成适配，不放行生产模型；真实切换要求匹配BASE-B能力资格及应用验收。
CLI、交互skill、MCP/工具型任务及其他应用全迁移不作为不使用它们的首批阻塞。
精确generic协议以基座正式OpenSpec为准；旧严格任务建议不是全平台硬编码标准。
本轮仅补设计和当前文档，不实现平台、不操作凭据、不改变W1.R未通过状态。
后续消费者分析见增强请求5.1/5.2/6.1：RCA草稿/评审、SoC流水线/GUI、Sample及旧Dashboard
Chat按实际调用分别验收，并检查共享启动/策略/资源/存储/SDK升级影响。
已定位测试不等于已运行；上一轮独立中立性审查不覆盖本次追加分析。
W4.REPLAN先冻结基座版本与实际consumer闭包，W5.REPLAN核对迁移回执和新Task资格。

## API Evolution And Handoff Amendment

2026-11-01用户明确：早期开发可以积极修改基座/SDK API，其他应用可同步更新；
必须有专门的变更记录及可转交Agent的迁移说明。API-EVO-01已批准，取代默认旧API兼容要求。
具体API-01至06仍是待基座review的候选，不把授权写成平台已重构或应用已迁移。
`ai-api-evolution.md`维护决策、记录格式、候选及版本/迁移保证；
`ai-base-review-handoff.md`是唯一完整提示词，要求基座review后按自己的OpenSpec增强。
本仓新增W5.MIGRATE以覆盖已有AI工作台，不能用可选W5.CHAT豁免公共SDK升级影响。

Docs-only owner_paths: this change's proposal/design/tasks/spec and integration appendices;
openspec/docs/current-baseline/project-reporting.md; .github/ai-governance/repo-context.md.
profile_source=repo-local; agent_routing_mode=multiagent-configured.
Main agent owns docs; independent Architect Planner Reviewer checks policy/consumer/validation consistency.
Implementation/Debugger agents skipped: no product implementation or incident in this amendment.
No new runtime/credentials/live calls, no W1.R closure, no external repository edits or deployment.
Existing task ledger remains the only Dashboard implementation status; base implementation status belongs to its own change.

Amendment evidence: strict OpenSpec PASS; whitespace PASS; configured size gate PASS for the one
changed governance file (OpenSpec Markdown has no matching size rule). 13 selected documents / 31
relative file targets and fence balance PASS; all 24 leaf packets map once to this ledger,
including W5.MIGRATE and W5.R's dependency on it.
Independent GPT-5.5/xhigh reviewer Franklin found no P0/P1/P2 document issues; two nonblocking clarity
suggestions were applied (mandatory Dashboard consumer reading; explicitly historical old review receipts).
These are documentation checks, not W1.R, base implementation, application migration or live acceptance.
The unrelated whole-worktree W1 size obstruction is not reclassified or waived.

Handoff context clarification: the same handoff now starts with the daily standup use case,
donor -> Dashboard -> AI Base rationale, scope/capture/delta/AI/acceptance/publication workflow,
business-to-E1/E7 mapping, other-app impact references and current-versus-planned boundaries.
The receiver must restate that understanding in its review, not only return an API inventory.
This is documentation clarification only; it does not change API-EVO-01, implementation status or authorization.
The earlier independent review does not claim to cover this later context addition.

## AI Base Independent Review Response

2026-11-01基座返回独立评审。应用方在ai-base-review-response.md回应全部AIB及Q1-Q4，
提供review-fixtures下的候选schema/完整与partial合成样例；它们不是生产ai_bundle或正式HTTP合同。
接受HTTP/Python、inline原子seal、polling、单backend资格作为接入首批；
不删除原provider-neutral/HSD/历史/依赖/附件等业务要求，不把有限Jira闭环当topic完成。
W4.REPLAN还须冻结W5最小持久attempt API及W7复用方；不能再建第二个恢复authority。
当前只交换设计与反馈；旧handoff的自动实施指令暂停适用，产品代码/部署/真实调用均未启动。
Owner paths: current change docs/review-fixtures and current-baseline/project-reporting.md.
Base report and source remain read-only; no author/sign-off columns changed.
Response material checks: strict OpenSpec/whitespace PASS; 14 docs / 38 relative targets PASS;
review schema and 2 golden fixtures PASS with 2 input hashes, 4 source hashes and 3 schema negatives.
Only existing jsonschema and standard library were used; product acceptance/CAS and all live qualifications remain unrun.

CF intake: base returned define-app-scoped-task-run-contract/design.md (task-run/1 draft).
Response section9 confirms per-app signed credentials/operator grants and runStoreId/deadline/retention mechanisms;
CF-A requests application-owned input_hash binding after raw model output, CF-B clarifies replay versus new admission.
Three strict-projection files in review-fixtures are docs-only contract inputs, not installed profiles.
Await base acknowledgement and final design hash; no implementation, credential creation, grant registration,
service activation or product acceptance follows from this response.
CF material checks: 3 schemas, 2 positives, 8 negatives and local candidate reconstruction PASS;
unregistered schema reference rejected without network. OpenSpec/whitespace and 14 docs/42 targets PASS.
No signing/grant/deadline/Run-store runtime qualification is claimed.

## FZ-01 Design Boundary Closure

2026-11-01用户要求尽快冻结并推动执行。基座最终design hash核验为
ff7899333c8ed8f0717b47fc7c1d6a6e5928db575a15553d2501045f123719da。
主代理完整读取最终稿，确认CF-A/B及CF-01至03闭环，无新增设计阻断项。
回执、schema/golden hashes、原子重放向量复算及催办提示唯一维护在ai-base-review-response.md第10节。
已确认内容不再重复审批；基座需登记freeze并按自己的唯一tasks推进BASE-A合成闭环。
当前外部design标题仍proposed，未由本代理改写；收到回执后的状态登记不是另一轮语义审批。
原CF待确认文字保留为历史，以本节和Current Execution为当前状态。
未实施产品代码、启动服务/真实调用、配置凭据或修改用户数据；W1.R和原T12状态不变。

## BASE-A Intake And Parallel Readiness

2026-11-01用户要求评估并行执行及下一步。本轮完成产物完整性核验和分工评估，不自动勾选业务节点。
Source of external status: base define-app-scoped-task-run-contract/tasks.md owns BASE-A evidence (46/515).
Local evidence: manifest SHA 08f081745ce956df13474de15063ec66849aef7a0454b3f0bd8fb4c56ee9bbca,
19 content hashes PASS; wheel de223668e49dc9ed145f6ec3bc5084d453a5611cee5f4f41987dd70a4474179f,
CRC and two source-member bytes PASS. No BASE-B provider/cancel/unknown/native/GC qualification.
Direct Dashboard Python -I import failed with missing httpx before network; no dependency was installed this turn.
Whole-worktree size check still fails only on the same two unrelated scope test files; no bypass/owner changes.
Next: prepare isolated SDK consumer dependencies, resolve/account for local W1 review gate, then follow original
W1.REPLAN -> W2 -> W3 -> W4. These do not depend on BASE-B completion.
W4.REPLAN and actual bundle/attempt/storage contracts still gate production W5 implementation;
SDK intake work is not a waiver or another implementation ledger.
No product/server/provider run, production dependency install, git commit/push or source migration in this assessment.
Assessment docs: OpenSpec strict/whitespace PASS; 14 documents/42 relative file targets PASS.
FZ-01 freeze.json is design-frozen with executionScope BASE-A synthetic only; BASE-B is a proposed
next-stage handoff, not a claim that the peer agent has started or that live permissions expanded.

## Execution Handoff Readiness

2026-11-01用户要求双方分工、依赖及可执行规格/validation明确。
execution-handoff.md is the single current cross-repo handoff; each repo maintains its own OpenSpec implementation.
Observed base ledger still explicitly excludes BASE-B nodes. Handoff B-P1..B-P5 are counterpart requirements,
not a fabricated completed base plan. Dashboard W2-W7 retain required REPLAN detail gates.
This round creates the concrete C0 dev-qualification packet with public signatures, owner paths,
commands, 12 named test cases and exit criteria. C0 implementation is not started.
profile_source=repo-local; agent_routing_mode=multiagent-configured.
One independent Architect Planner Reviewer owns C0.PLAN.R and its validation-plan review;
implementation/debugger agents skipped because this round edits plans only.
Preflight checks: C0 lane and W4.REPLAN dependency, both task authorities, consumer/negative matrix,
no production W5 behavior in C0, and no unsupported BASE-B/whole-project completion claims.
Independent GPT-5.5/xhigh reviewer Lovelace found two P1 and two P2 planning gaps:
async test runner, valid SDK success path, dependency hash receipt and redirect fixture precision.
All four were addressed; limited re-check found no remaining P0/P1/P2 and approved C0.PLAN.R.
Current C0 packet has 12 named cases, concrete payload/response builders and strict command boundaries.
Checks: OpenSpec strict/whitespace PASS; 16 docs/44 relative file targets PASS;
4 Python plan blocks parse; RunSubmit/RunSnapshot/RunResult example dictionaries satisfy the delivered schemas;
input/output fixture hashes match. These are plan/data checks, not executed SDK or product tests.
C0.N1/C0.R remain open; BASE-B implementation-plan readiness is still owned by the base agent.

## Coding-Readiness Preparation

2026-11-01用户要求执行准备直到可以开始编码，并提供对方同类提示词。
Scope of the readiness conclusion is the next C0.N1 packet, not all future W2-W7 or BASE-B.
Reused the already passed C0.PLAN.R instead of another plan-review cycle.
Created the owned ignored .tmp/task-run-c0/ directory; verified/copied 19 pack artifacts plus manifest/wheel.
Installed SDK0.1.0a1, httpx0.28.1 and jsonschema4.26.0 with dependencies in its Python3.13.7 venv;
pip check passed. All 13 pip install entries have SHA-256 evidence in the local UTF-8 report.
The main .venv, global settings, base source, real credentials and business data were not changed.
Installed SDK source bytes match the copied wheel. A bounded MockTransport probe passed three successful
submit/by-key/result calls and one typed timeout with the original key; socket guards observed zero network attempts.
An initial metadata-reading attempt failed under Windows cp1252; explicit UTF-8 report parsing fixed the probe.
No backend service, real authentication, DB transaction, provider or full 12-case C0 suite was run.
Preparation receipt: .tmp/task-run-c0/preparation.json; environment/plan now READY_TO_CODE_C0_N1.
C0.N1/C0.R remain open until the planned validation asset is coded and reviewed.
Base prompt and shared CODE_READY criteria are in execution-handoff.md sections8/9;
base readiness cannot be claimed until its owner returns a scoped evidence-backed reply.

## C0.N1 Implementation And Wait Points

2026-11-01用户询问下一步、能否继续及何时等待联调。本轮继续已审C0.N1，未扩展生产业务范围。
Implemented scripts/validation/test_task_run_sdk_intake.py in the user-selected Dashboard checkout,
on mvp/intel-jira-connectivity. Other agents' dirty files, base source and production settings were untouched.
The script verifies the owned interpreter, copied pack/wheel and installed SDK bytes before import;
uses IsolatedAsyncioTestCase, local-only schema registry and explicit MockTransport;
blocks socket connection/DNS attempts and checks per-test call counts to reject empty/unawaited false passes.
Each run writes a unique exclusive-create receipt; the previous receipt was verified unchanged.

Final command:
`.tmp/task-run-c0/venv/Scripts/python.exe -I scripts/validation/test_task_run_sdk_intake.py --pack-root .tmp/task-run-c0/artifacts/contract-pack`
Result: 12 passed, 0 failures/errors/skips, 11 expected mock requests, 0 real network attempts.
unittest reported 0.330s; an asyncio debug slow-task message was observed, not an unawaited warning or product KPI failure.
Final receipt: .tmp/task-run-c0/sdk-intake-result-20261101T145858363315Z.json.
Negative CLI checks: wrong interpreter and pack outside the local work area returned code2 with requestsSent=0.
Scoped source-size and whitespace checks passed; no base backend/service/provider suite was rerun.
C0.N1 is done, C0.R is not yet signed off. This does not close W1.R, W5, BASE-B or old T12.
Final documentation checks: strict OpenSpec PASS; 4 updated documents/23 relative file targets and
balanced fences PASS. The recorded receipt's scriptSha256 still matches the current script;
documentation-only edits did not rerun the SDK suite or invalidate that source-bound evidence.

Wait policy: current local reviews and W2-W4 work do not wait for BASE-B. First joined synthetic
business flow needs our input/attempt/acceptance services and a matching BASE-A candidate; cancel/unknown/native
recovery joins wait only for corresponding BASE-B features. Live report qualification requires both parties'
matched artifacts and explicit source/backend/deployment permissions. No mock may stand in for a missing real capability.

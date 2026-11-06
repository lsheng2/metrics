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

2026-11-07最新前沿：性能实现已以`60d791b`推送并核对远端。READ/REPLAN/COMMAND完成；
用户授权新建Ego验证空间后，10次实际语言切换全部通过，点击至目标语言与全部列表
p95为3.101s，门槛仍为3.5s。S0/S1、preview/detail与Save的正式20样本结果见
[performance-delivery.md](performance-delivery.md)。浏览器与隔离服务正常退出、零外部连接，
运行代码与冻结S0数据hash未变。独立最终证据复核READY，`W6.PERF.ACCEPT.R`通过；
不重跑整周/S1，不改真实服务，不把本次性能合格当完整Dashboard/live/deployment资格。

2026-11-06诊断与实施历史：停会与两周恢复已以`d21250a`提交，回执见
[meeting-skips-delivery.md](meeting-skips-delivery.md)。
用户随后报告语言切换近一分钟；实际语言POST为0.005s，后续工作台GET为39.602s，
独立profile为34.664s/169次Git调用，约27.937s花在Git调用。
本轮按要求建立[读取性能架构](report-read-performance.md)与[执行/验收计划](performance-execution.md)。
用户当时批准从`W6.PERF.READ`开始实施；不重跑原周、不切换原服务。
克隆原路径31.602s/169 Git；批量读取后8 Git，仍有本地文件读取和重复解析成本。
33项定向服务tests和4个subtests通过；有界本地并发实验及新增消费者见执行计划的READ amendment。
证据根`.tmp/dashboard-read-performance-20261106/`，当时READ/COMMAND/最终SLO尚未关闭。
READ核心两轮限定复审未留阻断项并准入COMMAND实施，不代表最终SLO关闭。
JSON/成功动作不再预构建工作台；HTML失败保留绑定输入，4项组合HTTP与13项受影响
HTTP/form检查通过。baseline/period/skip等共享读取消费者当时仍在验证。
本次实现的scope/refreeze更新见`performance-execution.md`的READ amendment；
未把少量约3秒的样本或只完成的小规模夹具当成100份S1/20样本资格。
上述为实施过程而非当前任务状态；
历史段落中的“尚未profile”以这条已测证据为准，不改写历史回执。

此前入口：用户同意的精简正文与独立完整审计附件已完成限定实现/验证/复审，
基线`9dff849`，见[呈现交付](presentation-delivery.md)与[版本化契约](standup-presentation.md)。
整周/跨周操作闭环证据保留于[week-delivery.md](week-delivery.md)，不重跑；
最终47项限定回归、真实Git新旧两日/原字节验证及实际浏览器样本通过。
后续请求延迟分析与优化结果见本节最新前沿；整个产品的其他未完成资格继续保留。

2026-11-05用户批准Dashboard交付复评，并要求同步文档、调整执行顺序、开始执行。
本轮沿Dashboard main，基线`eb8de2e`；SDK020已通过，不重跑其全部资格。
唯一执行状态仍在本文件，新统一开发契约为`AI_CONTRACT.md`。

`DELIVERY.PLAN.R`、`DELIVERY.GOV`、`W6.AUTHOR.DAILY`和`DAILY.REPLAN`已通过限定范围门禁。
治理文档已以`9852e37`推送并核对origin/main。实际两天链1 passed / 466.75s，
三项模板反例修复后3 passed / 3.04s，隔离Django check通过；未重跑全历史suite。
已验证实际生成周二、人工note/颜色/链接继承、Save/reopen/Finalize、周一六文件不变，
以及同日冲突返回原publication且不新增第三稿。修复仅在两个模板，服务端冲突保护不变。
源码限定复审已关闭，最终运行由协调者绑定；四次未通过/中断证据仍保留，原生异常根因未定。
完整回执见[daily-delivery.md](daily-delivery.md)及[daily-delivery.json](daily-delivery.json)。
本阶段只发布文档/回执；产品与测试改动依赖既有未提交作者层，留待完整源码闭包提交。
这不是clean-install、正式部署、完整工作周或整个topic完成。

用户再次要求持续执行；2026-11-06 `W4.DELTA.CORE/R/REPLAN`完成限定资格。
精确接口/证据/准入与分层验证见[delta-core.md](delta-core.md)，证据根
`.tmp/dashboard-delta-20261105/`，基线`94a80de`。首次输入/接受兼容基线15 passed；
共享合同32 tests、真实Git5 tests、最终真实SDK/loopback Base增量1 test通过。
原生只执行1次合成分析，revision2可读取，无变化零新调用，服务正常退出。
原结果重放/布尔版本/重复读取问题以直接反例修正，限定独立复审READY。
既有作者层+增量源码闭包已完成候选校验与独立发布审查，按限定清单提交后进入ASSIST；
不把完整W4/W5勾成完成。SOURCE依据见[authoring-source-closure.md](authoring-source-closure.md)：
独立Git树1530收集、33实际tests、11 Node、Django及迁移一致性检查通过，13无关路径保留。
DAILY.REPLAN对增量入口作amend：
必须同时冻结输入、接受revision、报告读取及旧attempt准入；未知提交继续原key观察，
不能因timeout重置key/deadline/预算。Git读取路径的实测延迟另行剖析，未声称性能已通过。
`refreeze_actions=[{action:amend,reason:DELTA entry must classify prior accepted/terminal/unknown attempts}]`；
`updated_artifacts`为本仓相对路径：
`openspec/changes/add-provider-neutral-project-reporting/delivery-sequence.md`、
`openspec/changes/add-provider-neutral-project-reporting/daily-delivery.md`、
`openspec/changes/add-provider-neutral-project-reporting/daily-delivery.json`、
`openspec/changes/add-provider-neutral-project-reporting/tasks.md`及
`docs/development/reporting-delivery.md`；
`rerun_gates=[DAILY full browser chain,template regressions,isolated Django check,OpenSpec strict,scoped size/whitespace]`。
`post_refreeze_preflight_result={method:source/consumer/review/evidence and next-gate dependency cross-check,result:PASS}`。
2026-11-06 `W6.AUTHOR.ASSIST/ASSIST.REPLAN`完成限定合成资格，源码基线`4cb995b`。
执行合同见[assist-execution.md](assist-execution.md)，回执见[assist-delivery.md](assist-delivery.md)。
独立authoring profile接入现有SDK；52 tests +8 subtests、10 Node、最终HTTP/Git等4 tests、
其他目标族保存矩阵1 test通过。AI候选、人工改动、Save、真实数据Git与翌日provenance已贯通，
只派发1次合成Base任务，正常退出。后端、UI和最终文档/证据复审均READY。
两项P1和随后发现的保存/限额/损坏状态反例已修正，失败证据保留；
手工编辑不依赖authoring profile，unknown不换key/deadline，Save仍不是Finalize。
源码依明确清单提交，13个无关Scope/config/main.css文件保持原hash。
ASSIST.REPLAN准入：先执行导出样本，再执行原整周/跨周；
完整provider/import/deployment与真实来源/模型资格继续保留，不由本节点关闭。

2026-11-06 `W6.AUTHOR.EXPORT.SAMPLE`限定资格完成，源码基线`2759d46`。
派生Markdown/Excel下载不改原六文件，也不重新渲染已发布HTML；实现合同见
[export-execution.md](export-execution.md)，回执见[export-delivery.md](export-delivery.md)。
最终转换17 tests、真实Git三票/两日1 test、HTTP2 tests、实际浏览器下载/复制及中文手机2 tests、
旧保存/生命周期等28 tests与Node状态3 tests通过。一个P2行数上限遗漏已通过反例修复和限定复审。
Excel是明确声明的文本表格导出，颜色继续由HTML/JSON保真；Outlook/native-client未资格。
2026-11-06 `W6.AUTHOR.JOIN`操作/连续性链路实际通过：
`aa2fb399-4557-4342-b725-8de2dab91aba`保留六个日期及周报，共七份publication；
最终公开API重读42个原始文件hash一致，三次合成Base派发后不再推理。
重复准备、正常重启、#ID第三格式、颜色/粗体/高亮、stale保存409、跨周、
真实非空内容清空及未定稿gap均有证据。两服务正常退出。
准备内容hash与完整意图hash误比较的业务修复7项回归通过；
验证脚本生成器、动态checkout及未触及空槽等错误分别保留原失败和直接反例。
当前validator7 tests与Node13 tests通过；运行详情唯一见week交付回执。
这仍不是最终产品验收：实际HTML仍强制带完整原始摘要/审计明细，不符合精简站会正文；
部分请求等待53-77秒，尚未做关键路径profile。`AUTHOR.R/REPLAN`及完整W6保持未完成，
先确认版本化的呈现/审计边界，再修订原W6.RENDER/PUBLISH；不静默删除审计/权限校验，
不修改旧publication/hash，也不以功能绿色替代最终效果或真实环境资格。

获准顺序：[delivery-sequence.md](delivery-sequence.md)。
治理/环境 -> DAILY短链及提交 -> 增量输入/接受/报告读取闭环 -> ASSIST单目标 ->
导出代表样本 -> 原整周/跨周 -> 后续完整功能和正式资格。
增量窄切片不等待全部名单/附件/HSD扩展，但不关闭完整W3/W4/W5父节点。

本轮证据根`.tmp/dashboard-delivery-20261105/`，已记录原252条dirty路径hash。
治理依据为`plan-review.md`、`history-relocation.json`、50个本地链接检查、
原94节点状态保持检查及配置化size/whitespace/OpenSpec严格检查。SDK0.2解释器、
包来源和pywin32导入通过；没有为治理改动重跑产品或Base测试。
报告作者层已有WIP与其他Scope/config/style改动分开；只修改和提交本包声明的文件。
使用`.tmp/sdk-020-join-20261105/app-venv/Scripts/python.exe`及既有no-dotenv测试入口；
不切换原8017服务，不升级主venv，不启动真实provider/model、部署、调度或发送。
按用户结果形成阶段提交；同一失败两次无新增证据后改变实验，不盲跑完整周。

历史检查点已移至[execution-history.md](execution-history.md)，按需读取；
历史暂停/版本/未完成描述不覆盖本入口。详细源/接口/验收矩阵仍在本change技术附录。

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
- [x] W6.HTML.UI Summary: WYSIWYG authoring is covered by W6.AUTHOR.EDIT/JOIN; no source-mode or separate user-provided Agent prerequisite.
- [ ] W6.HTML.R Review the bounded authoring slice and actual desktop/copy/Git evidence; email-client qualification reported separately if unavailable.
- [x] SDK020.PLAN.R Freeze the selected SDK/pack contract, pre-IP work and post-IP APIs/fixtures; review and publish scoped specifications before implementation.
- [x] SDK020.ARTIFACT Verify final owner receipt/wheel/pack; install SDK into an owned separate target without changing the main environment.
- [x] SDK020.APP Update the exact dependency/runtime version pair with real installed-SDK RED/GREEN tests; preserve all application validators.
- [x] SDK020.PRE Run the explicit application-network-free consumer selection and record source-bound readiness plus protected-WIP integrity.
- [x] SDK020.REPLAN Confirm next joined packet is reachable, classify retained evidence, record IP-SDK020-READY and stop for the user.
- [x] SDK020.JOIN After explicit release of IP, execute the new-SDK real local HTTP consumer cases J020-01..06.
- [x] SDK020.JOIN.R Review the joined candidate, source/acceptance evidence and owned cleanup.
- [x] SDK020.JOIN.REPLAN Refreeze DAILY/ASSIST prerequisites and affected evidence before continuing authoring execution.
- [x] DELIVERY.PLAN.R Review the approved reordered frontier, unified contract and DAILY exact consumer packet; no full historical redesign.
- [x] DELIVERY.GOV Unify agent entrypoints, isolate historical checkpoints and fix selected-environment/test routing without changing user runtime.
- [x] W6.AUTHOR.PLAN.R Review Authoring V2 scope/error policy, template selection and schema migration before implementation. User approved; bounded first-CONTENT review recorded below.
- [x] W6.AUTHOR.VA Freeze RA01-72, source consumer inventory and exact validation commands; RA70-72 deferred to W7.SCHEDULE. First CONTENT slice qualified to start, not product pass.
- [x] W6.AUTHOR.CONTENT Add schema2 fragment persistence, safe rendering and old-revision compatibility. Standalone backend qualified; nonempty reference/Assist receipts remain fail-closed until their owning leaves.
- [x] W6.AUTHOR.EDIT Integrate one WYSIWYG component and the shared editor adapter; no source mode. Scoped lifecycle/native-runtime review closed; whole-flow JOIN remains separate.
- [x] W6.AUTHOR.REFERENCES Implement #ID query, Stage routing, membership/permission/freshness and three-format popup. Backend and UI scoped reviews closed; live Jira/HSDES qualifications remain separate and disabled.
- [x] W6.AUTHOR.TEMPLATES Add user template library, version-CAS, visual block/slot editing and pinned draft creation. Fixed-content rich preview follow-up closed by B2 browser/review.
- [x] W6.AUTHOR.HISTORY Add effective rich-text daily history, source-status prefixes, stable row order and weekly carry-forward. Core/B1/B2 scoped synthetic qualification closed; daily trigger and whole-week JOIN remain separate.
- [x] W6.AUTHOR.DAILY Add manual daily preparation, editorial baseline selection/CAS, pending-draft handling and same-day idempotency.
- [x] W6.AUTHOR.DAILY.REPLAN Bind qualified manual DAILY evidence and the DELTA-first gate; preserve ASSIST profile/save boundaries and unaffected history.
- [x] W4.DELTA.PLAN.R Freeze the bounded cumulative-input/acceptance/reader contract and old-data compatibility before coding the changed-ticket slice.
- [x] W4.DELTA.CORE Implement and verify the same bounded analysis-input contract in prepare, acceptance and report reads; preserve failed-analysis cumulative changes and no-work reuse.
- [x] W4.DELTA.CORE.R Review the changed-source slice and applicable SDK/reader evidence; do not close full W4/W5 or live qualification.
- [x] W4.DELTA.CORE.REPLAN Refreeze ASSIST input/source and remaining full delta/import/capability work.
- [x] W6.AUTHOR.SOURCE Publish the complete verified authoring/DAILY/delta source closure, excluding unrelated Scope/config/style changes; verify a clean candidate can collect/import the required consumers.
- [x] W6.AUTHOR.ASSIST Add explicit AI candidates using a separately qualified authoring profile.
- [x] W6.AUTHOR.ASSIST.REPLAN Verify authoring-profile HTTP qualification and provenance consumers before the final week.
- [x] W6.AUTHOR.EXPORT.SAMPLE Add versioned derived Markdown/Excel downloads without altering original six-file publications, then qualify one rich-text/template/AR/history and clipboard sample before the week.
- [x] W6.AUTHOR.JOIN Validate authoring/save/copy/finalization and the week/cross-week/gap workflow; concise-body alignment, performance and external qualification remain open.
- [x] W6.PRESENT.PLAN.R Freeze/review the approved concise template, renderer, immutable artifact read and audit-export contracts. Strict pinned-family and builder-profile counterexamples are required by the bounded review.
- [x] W6.PRESENT.CORE Implement the opt-in versioned standup body and exact old-format compatibility. Scoped pure/legacy selection 39 passed; strict consumer corruption test passed.
- [x] W6.PRESENT.AUDIT Add owner-checked read-only audit bundles from original publication bytes. Real Git successor/old-byte test and authenticated HTTP download/denial cases passed.
- [x] W6.PRESENT.UI Qualify template creation/edit/save/publication and body/audit downloads on the actual mounted UI. One desktop/390px story passed; builder preserves profile, dirty guards and actual ZIP/original HTML verified.
- [x] W6.PRESENT.R Review scoped source/evidence and truth-sync; final scoped selection 47 passed, no review blockers. Latency profiling and broader product qualification remain separate.
- [x] W6.SKIP.PLAN.R Freeze and independently review skipped-meeting API, immutable calendar evidence, shared admission and bounded validation in meeting-skips.md. Five bounded design findings amended; root-only lock, replay read exception, full context consumer list and partial reservations explicit.
- [x] W6.SKIP.CORE Implement audited skip/restore, prepare/seed admission and frozen report metadata without advancing baselines or changing old bytes. Final core/affected selection: 46 passed; delayed pinned-policy and old seed replay included.
- [x] W6.SKIP.UI Add authenticated bilingual meeting-calendar and recovery controls using existing forms and report APIs. Three HTTP cases and separate desktop/390px Chinese navigation passed; two-week mounted story passed.
- [x] W6.SKIP.JOIN.R Verify two-week resumption, negative consumers and docs; independent source/evidence review closed. See meeting-skips-delivery.md; the broader authoring/live/deployment gates remain open.
- [x] W6.PERF.PLAN.R 统一查询、固定快照/批处理、写锁隔离、负例与性能SLO设计通过独立复核；见performance-plan-review.md，规格通过不等于优化完成。
- [x] W6.PERF.READ 工作台纵向切片已实现并通过独立复核：批量Git、固定H、完整packet验证复用和专用列表投影；最终S0首请求3.860s、20样本p95 2.876s，S1 p95 4.105s。
- [x] W6.PERF.READ.REPLAN 根据S1分段计时剔除未被工作台消费的checkout诊断，保留采集状态和旧API；不增加持久索引、并行Git或延长期限。投影反例9项及独立复审通过。
- [x] W6.PERF.COMMAND 窄preview/prepare/reprepare/detail与错误页已通过HTTP/真实浏览器回归；Save保留锁内CAS且20次p95 1.839s，详情1.448s；无预读历史或隐藏控件。
- [x] W6.PERF.ACCEPT.R 全部后台门槛与原HTML浏览器链已通过；最后10次授权Ego切换p95 3.101s、五表完整且数据不变。独立证据复核READY、文档/严格规格/限定门禁通过，见performance-delivery.md。
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
| DELIVERY.PLAN.R | SDK020.JOIN.REPLAN + 用户批准交付重排 | 统一契约/文档路由及首个DAILY实际消费者就绪复核 |
| DELIVERY.GOV | DELIVERY.PLAN.R | 精简代理入口、历史分离、选定环境/no-dotenv路由；不改真实服务 |
| W6.AUTHOR.DAILY | W6.AUTHOR.HISTORY + DELIVERY.GOV | 明确baseline/meeting/来源选择、同日去重、人工未定稿保护；独立人工证据可复用 |
| W6.AUTHOR.DAILY.REPLAN | W6.AUTHOR.DAILY | 绑定DAILY证据、DELTA.PLAN.R准入及后续ASSIST target/profile/save边界 |
| W4.DELTA.PLAN.R | W6.AUTHOR.DAILY.REPLAN + 已有W3 archive/gateway/capture | 同时冻结增量输入、接受revision及报告读取；完整W4仍保留 |
| W4.DELTA.CORE | W4.DELTA.PLAN.R | accepted基线累积变化、失败不丢B/C、revision2可进入报告 |
| W4.DELTA.CORE.R | W4.DELTA.CORE | 当前源码/fixture与变化源合成证据闭包复核 |
| W4.DELTA.CORE.REPLAN | W4.DELTA.CORE.R | 固定ASSIST及原完整W4/W5的剩余能力，不宣称全部增量已完成 |
| W6.AUTHOR.SOURCE | W4.DELTA.CORE.REPLAN | 完整源码/依赖/测试资源闭包提交，不自动包含无关Scope/model/style改动 |
| W6.AUTHOR.ASSIST | W6.AUTHOR.SOURCE + authoring profile前提 | task-run候选/审批/取消；无真实资格只做fake边界验证 |
| W6.AUTHOR.ASSIST.REPLAN | W6.AUTHOR.ASSIST | profile合成HTTP及provenance链可达，整周输入/验收条件固定 |
| W6.AUTHOR.EXPORT.SAMPLE | W6.AUTHOR.ASSIST.REPLAN | 一个代表性fragment/template/AR样本的导出和复制边界 |
| W6.AUTHOR.JOIN | W6.AUTHOR.ASSIST.REPLAN + W6.AUTHOR.EXPORT.SAMPLE | 同候选app/editor/storage/已安装SDK联合验证 |
| W6.AUTHOR.R | W6.AUTHOR.JOIN | 精确diff与RA证据review；外部未验证项单列 |
| W6.AUTHOR.REPLAN | W6.AUTHOR.R | 原剩余W6.RENDER/PUBLISH及W7逐项continue/amend，不删除未交付 |

### SDK020: Preparation And Integration Gates

Spec: [SDK contract](sdk-020-integration.md), [post-IP execution](sdk-020-post-integration.md),
[observable requirements](specs/sdk-consumer-integration/spec.md).
Goal: use the delivered 0.2.0a1 Python client with the original a2 pack, preserving app authority.
Architecture: existing app adapter plus isolated installed client; no new service or execution engine.
The pre-integration scope ended at IP-SDK020-READY. The user released this stop on
2026-11-05; SDK020.JOIN and subsequent dependency-ordered execution are now authorized,
with real providers/models, formal deployment and scheduling still excluded.

| Node | depends_on | owner_paths / deliverable |
| --- | --- | --- |
| SDK020.PLAN.R | accepted Base delivery and current user request | this change's connected specs, new current SDK guide; exact API/consumer/refusal/stop mapping and scoped publication |
| SDK020.ARTIFACT | SDK020.PLAN.R | owned .tmp/sdk-020-preintegration-20261105 artifact copy/target; hash-verified wheel, unchanged bundled pack and recorded dependency roots |
| SDK020.APP | SDK020.ARTIFACT | requirements-ai-task.txt, out/ai_task_contract.py, tests/test_sdk_020_compatibility.py, scripts/validation/run_project_sdk_preintegration.py and shared run_report_authoring_tests.py explicit isolation mode; narrow exact version migration |
| SDK020.PRE | SDK020.APP | same owned code/test paths; three explicit test files, no Base import or application network, separately counted Windows socketpair IPC, source-bound JUnit/receipt |
| SDK020.REPLAN | SDK020.PRE | tasks + IP receipt; verify post-IP source/fixture paths, carry forward valid evidence, stop and wait |
| SDK020.JOIN | SDK020.REPLAN + explicit user release | scripts/validation/project_full_stack*.py, project_summary_support.py, project_sdk_join*.py, project_management/tests/test_project_full_stack_lifecycle.py and tests for J020 cases; refresh old SDK expectations, then joined 0.2 HTTP and app acceptance |
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

SDK020.REPLAN receipt:
`refreeze_actions=[{node:SDK020.JOIN,action:continue,reason:existing driver refresh and J020 cases
are explicitly specified; SDK/pack artifacts and retained Base fixture entry exist}]`.
`updated_artifacts=[sdk-020-integration.md,specs/sdk-consumer-integration/spec.md,tasks.md]`;
the Windows socketpair clarification separates runtime IPC from forbidden application networking.
`rerun_gates=[network-policy direct tests,installed-SDK consumer selection,OpenSpec strict,scoped size/whitespace]`.
`post_refreeze_preflight_result={method:artifact/source-path and exact API/fixture dependency review,result:PASS}`.
This admits integration development only after user release, not execution of the old joined
driver unchanged. Authoring WIP, DAILY/ASSIST/full-week/real-provider gates remain open.

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

JOIN owner_paths为前述实现闭包、当前guide/本change及
[week-qualification.md](week-qualification.md)中的精确运行器、fixture和专项测试。
实际入口为`project_full_stack.py prepare --scenario full-week`及
`scripts/validation/project_week_browser.py --run-dir ...`，沿用同一launcher的
start/status/restart-app/stop；不再执行早期规划但未实现的
`run_report_authoring_week.py`等文件名。
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

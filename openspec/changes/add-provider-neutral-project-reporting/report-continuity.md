# Report Continuity And Daily Preparation

日期：2026-11-03。状态：proposed，前几轮已确认要求的架构细化，未实施。
父设计：[Report Authoring V2](report-authoring-v2.md)。
契约：[authoring contracts](report-authoring-contracts.md)；
场景：[report-authoring delta](specs/report-authoring/spec.md)；
唯一执行状态：[W6.AUTHOR](tasks.md#w6-authoring-v2)。
本附录不是另一套计划，也不授权采集、模型调用、正式调度或业务写入。

## 1. Decisions And Current Gaps

已经确认：一票一行；`AR`/`AR?`；`ww45.1(Fixed):` 中的状态来自工单；
WYSIWYG 人工增删/颜色/高亮/链接与 AI 初稿合成后保留；逐日累积；
已有票保持位置，新票追加；模板、AI 写作策略、数据绑定分离。

本次补齐的默认设计：

- 一周一个展示周期，同周累积全部已确认 daily notes。
- 换周携带每票最近一次确认更新、未结束 AR 和显式常驻备注，不复制整张旧周表。
  原周全部富文本和归档仍保留；新周提供旧周历史入口。
- `生成今日草稿 / Prepare today's draft` 是默认手动入口。
  定时入口在 W7 单独资格后可启用，默认关闭，永远不自动定稿。
- 每日草稿不是正式 baseline；只有明确 Finalize 且精确数据 Git 提交确认后推进报告基线。

此前本地样张的跨周`all-available-in-report-series`仅是展示探针默认；
本附录将正式默认收敛为最近确认更新+未结束行动，`full_history`仍是可选展示模式。
旧样张不是另一份生产规格，也不证明编辑器保真已经实现。

当前已读代码有 `ReportDraftService.create/save` 的 command/revision-CAS，
`ReportPublicationMixin` 的六文件 packet 与提交恢复，
`ProjectRunService.submit` 的手动运行日志和原操作重放。
它们目前不证明彩色富文本跨日继承、稳定行序、周周期和同日生成去重已经存在。
代码依据为这些实际文件及 `test_report_drafts.py`，不是图谱中的缺失结果。
现有 `ReportEdit.text` 仍是 literal text；不能把样张脚本当成生产实现。

## 2. Three Different Baselines

| 名称 | 权威 | 谁推进 | 不是什么 |
| --- | --- | --- | --- |
| Source snapshot | 已完整或明确 partial 的 Capture/原文归档、source hash/as-of | 显式采集工作流 | 不是用户已确认的日报 |
| Analysis baseline | 每票最后一次通过语义/证据校验的 accepted summary | 原摘要接受服务 | 不是人工编辑后的正文 |
| Editorial baseline | 同系列最后一个正式 daily publication 的完整作者文档 | 用户 Finalize 后的已确认 Git publication | 不是最近一次 AI 输出、草稿 Save 或最新文件 mtime |

新日报使用 source snapshot 取得当前工单状态，使用 analysis baseline 处理源增量，
使用 editorial baseline 继承人工文字、格式、AR、行序和历史。
三者单独记录引用，不能用一个 `last_run` 覆盖三种成功水位。
用户删改 AI 句子不会改写 accepted summary，但后续报告不得因此复活被删句子。
AI 的新建议只进入新 note 或显式选择的可编辑区域，需人工接受。

## 3. Ownership And Flow

```text
Dashboard button / approved scheduler
  -> ReportPreparationService (project_management public API)
  -> existing ProjectRunService + capture/analysis services
  -> ReportContinuityService (verified editorial baseline + period + row order)
  -> ReportDraftService.create_authored / save_authored
  -> WYSIWYG adapter + #ID completion / explicit AI candidate
  -> effective rich-text document
  -> existing finalization packet + stage Git writer
  -> confirmed daily publication
  -> next day's immutable baseline selection
```

| Owner | Responsibility |
| --- | --- |
| `project_management` | Calendar/series identity、周期、baseline 选择、note/AR 版本、排序、准备命令、定稿 |
| `provider_sync` 公共接口 | 授权成员/状态/title/assignee 与采集时间；不生成叙述或改报告 |
| AI Base task-run/1 | 获准任务的计算、取消、原结果与使用量；不决定周边界、顺序、状态或定稿 |
| `ui_web` | 编辑器、色板、保存/未保存提示、生成按钮、确认与错误；不直接读 Git/凭据 |
| Renderer | 同一作者文档投影 HTML/Markdown/plain/Excel；不查询 provider、不调用 AI |

复用原服务、锁、journal 和 writer。新增 continuity/preparation 是领域服务，
不是第二个调度器、LLM 客户端、Git 仓库或全站前端框架。

## 4. Series, Calendar And Period

`ReportSeries` 绑定同一 project、Stage/source definition 和报告用途。
每个独立系列有 UUID，不以标题或 `ww45` 识别。新周不是新 Stage，
不更改批准 scope、清空采集水位或重做全部 AI 分析。
改变 Stage/source definition 不能自动继承另一系列的企业内容。

`SeriesPolicyRevision={series_id, name, revision, revision_hash, project_id, stage_id,
stage_hash, calendar, default_template_selection, created_by, created_at}`。
新增 `ReportSeriesRecord/ReportSeriesPolicyRevision/ReportSeriesCommand` 在现有
project_management ORM 事务中存储设置、不可变修订和 command replay；
不存 daily 内容真相，daily head 仍从 Git publication 重建。
首次由用户明确创建系列并选择日历/模板；服务端校验同project/Stage/owner。
`create_series`/`save_series_policy` 沿原 project lock+CAS，不在 stage 锁内写 DB。
新准备先冻结 policy use，后续改默认模板/日历不会改变已存在 draft/operation。
name为1..160字符，series UUID/归属/hash/操作者/时间由服务端生成；同名不作身份去重。
每Stage最多20个series、每series100个policy revisions，超过时明确拒绝，不删旧记录。
创建/保存必须复验v2就绪模板中恰一个meeting_matrix；当前来源不可用不授权隐式换Stage。

`ReportingCalendar` 为 `{calendar_id, revision, timezone, week_rule, date_map}`：
`week_rule` 只允许 `iso8601` 或 `date_map`。后者是用户批准的日期到
`{workweek_year, workweek, weekday}` 映射，不是从模型猜测 Intel workweek。
日期用 ISO local date，时刻用 UTC；weekday 是周内日，不是“本周第几次点击”。
首次设置必须明确选择日历；缺映射返回 `REPORT_CALENDAR_UNAVAILABLE`。
日历已用修订不可改，后续切换通过新的 series policy revision 生效，不改旧标签。

`MeetingIdentity={local_date, calendar_id, calendar_revision, timezone,
workweek_year, workweek, weekday}`。
`PeriodIdentity={calendar_id, calendar_revision, workweek_year, workweek}`。
同一天重跑仍是同一个 meeting；跨年不能只用周号比较。

周展示有两种产物：

- 日报中的周矩阵：截至该次 daily 定稿的累计视图，冻结输入。
- 单独导出的周报：选择本周已确认日报生成的 `weekly_view`，记录选中的 publication refs；
  缺日报的日期明确标记，不编造内容。它不是新的 daily baseline。

切换 UI 周标签只是读取。首次生成新周日报时，准备命令才按日历产生新的 period context。
浏览器打开、日期经过午夜或读取历史都不自动发起采集、模型、创建草稿或提交。

## 5. Canonical Authored Records

以下类型由应用生成/校验；未知字段拒绝。富文本与模板版本见 authoring contracts。
`PublicationRef={publication_id, manifest_hash, commit}`，读取必须核验归属、六文件与 hash。
`IssueRef={provider_id, endpoint_fingerprint, stable_id, key_at_capture}`；
关联用前三项和 series 的 Stage hash，key 是展示值，不能用行号、title 或 assignee 匹配。

| Value | Fields and constraints |
| --- | --- |
| `SourceStatusSnapshot` | `{availability:"known"|"unavailable"|"not_captured", value:str|null, field_path:str|null, observed_at:Instant|null, source_ref:object|null, source_hash:str|null}`；known 全部可追溯，服务端从已选 source DTO 构造 |
| `DailyNote` | `{note_id, issue_ref, meeting, revision, body_fragment, body_hash, source_status, action_ids[], provenance, prior_revision_hash}`；一个 ticket/meeting 一个逻辑 note，允许多个段落 |
| `NoteProvenance` | `{origin:"human"|"ai_assisted"|"accepted_summary"|"imported", ai_result_ref:object|null, original_fragment_hash:str|null, edited_by, edited_at, accepted_publication:PublicationRef|null}`；操作者/时间由服务端赋值 |
| `ReportAction` | `{action_id, issue_ref, issued_meeting, owner_ref:object|null, body_fragment, basis:"recorded"|"proposed", tracking_state:"open"|"done"|"canceled"|"unknown", evidence_refs[], resolution:object|null}` |
| `PersistentNote` | `{note_id, target:"report"|"issue", issue_ref:IssueRef|null, fragment, revision, carry_forward:bool, provenance}`；显式常驻备注，不伪装每日新进展 |
| `RowOrderSnapshot` | `{revision, group_order:UUID[], rows:[{issue_ref, group_id, position, first_seen_meeting, visibility}]}`；保留移出票的占位与历史身份，不能重新利用其 position |

group_mode=none时row.group_id=null，group_order为空；manual时每行group_id必须在group_order内。
当前publication内新增/修订note的`provenance.accepted_publication`为null，
接受身份由外层publication envelope证明，不能把该publication自身manifest_hash嵌进context，
以免造成自引用hash。后续继承的来源引用由读取方验证并加入context引用表，
不修改原note canonical bytes/body_hash。

`body_fragment` 是 AI 初稿经用户增删/着色后的有效文档，不是每次回放原 AI 文本的
无条件覆盖层。原 AI 结果只作独立 provenance。删除、清空及改 AR 都形成明确新 revision，
不能因空字符串或 omission 又恢复原句。定稿后的 note 不原地编辑，纠错创建关联草稿。

`ReportAction.tracking_state` 是报告行动跟踪状态，不是 Jira/HSDES 状态。
已有 `next_actions` 保持原领域字段名，界面标签为 AR；源行动不能仅通过删正文而消失。
给 source action 加人工解决结论需新的显式 resolution 及依据，不改原 action 证据。
AI/工单状态变成 Fixed 均不能自动把 AR 标 done。
`AR?` 表示建议未确认，不是已获对方承诺；跨日重复展示不重新指派或通知。
`actions`同时是去重catalog：已done/canceled的记录仍可随有效context保留，
但不进入`weekly_seed.unresolved_action_ids`或新周未结束行动区。不能先丢掉已解决身份，
再从未变的source next_actions重新生成同一个open AR。相同source行动保持原action_id/
issued_meeting，新的人工解决修订不被重复来源覆盖；catalog增长仍受context额度约束。

### Source Status Authority

前缀固定语义为 `ww{week}.{weekday}({source_status.value}):`，value 保留 provider 状态原值。
Jira 取适配器映射的 status name；HSDES 取合格 profile 映射的原状态字段，
不得用 Dashboard health bucket 或 AI 结论映射成 Jira 状态。
status 与该 note 的 Capture/source hash、observed_at 一起冻结，非客户端可编辑字段。

当前来源 unavailable 显示明确不可用标记，不能拿旧值冒充当前值。
历史导入未捕获状态时前缀仅 `ww45.1:`，附来源缺口，不从现今状态倒填。
刷新 source 是显式新操作；save/render/finalize 不隐式刷新或悄悄改预览。
已有严格 source-drift 守卫继续保留，冲突时要求显式重新准备/合并，而不是放宽检查。

### Current Day Without New Source Content

每票准备时构造非用户可写的`CurrentObservation={issue_ref,meeting,note_id,
source_state,source_status,capture_id,source_hash,accepted_summary_ref,editorial_base_note_ref}`。
source_state为`initial|changed|unchanged|pending|incomplete|unavailable`。
比较对象是editorial baseline对应票的最近source语义与accepted summary引用，
不是capture ID或整个报告hash；当天capture时间不同但相同工单内容仍为unchanged。
完整source且accepted summary覆盖当前链是复用前提；等hash但partial不能证明无变化。
首个系列没有editorial baseline为initial，不因摘要已存在而误判“今天无需初稿”。

- initial：完整来源和已验证accepted summary可确定性填入首日note；
  尚无摘要则留待填写并显示pending，不由渲染器调用AI。
- unchanged：不创建有正文的今日DailyNote，不复制原AI候选或将旧note改成今日前缀。
  旧日final正文/删除/paint保持原hash；当天只显示非note的“来源未变化”观察提示
  和一个可编辑空槽。只有用户输入/显式提交空编辑时才物化当前note。
- changed：当前source已有新的有效accepted result时可生成当前日初稿；
  只有新source、没有合格新摘要则pending，不能回退旧摘要冒充本日变化。
- incomplete/unavailable/pending：保留旧editorial历史，明确当前来源/分析缺口；
  人工note仍允许，但source_status只能来自当前实际取得的字段，缺失时明确unavailable，
  不把整体partial误说为所有字段必然缺失，也不借旧状态填新前缀。

空槽的note_id由series+issue稳定身份+meeting确定性派生，存入当前observation，
`save_authored`只允许该服务器声明的daily_note目标；首次编辑创建note revision1，
后续编辑递增本日note revision。历史note不因当前空槽存在被改写。
CurrentObservation[]进入DailyAuthoringContext，供next-day比较和目标授权；
它不是用户正文，不算已确认daily note，也不触发AI/推进任何基线。
RA43/62/67增加反例：首日删句/着色定稿后次日完整同源，旧正文不复活、
新日空槽可添加人工note；相同hash但partial明确缺口，不能伪造no-change。

## 6. Persistence And Cross-Day Preservation

`DailyAuthoringContext` 进入 schema2 draft revision：

```text
schema_version: 1
series_id, series_policy_revision, series_policy_hash
report_role: daily | weekly_view
meeting: MeetingIdentity | null
period: PeriodIdentity
base_daily_publication: PublicationRef | null
baseline_choice: initial | previous_final | confirmed_gap
acknowledged_gap_draft_ids: UUID[]
row_order: RowOrderSnapshot
weekly_seed: {baseline: PublicationRef|null, note_refs[], unresolved_action_ids[],
              persistent_note_refs[], earlier_period_refs[]}
notes: DailyNote[]
current_observations: CurrentObservation[]
actions: ReportAction[]
persistent_notes: PersistentNote[]
selected_daily_publications: PublicationRef[]
```

daily 必须有 meeting，weekly_view 的 selected_daily_publications 非空且固定日期/来源。
继承的片段完整存入当前有效 context，并带原 note ID/revision/hash，
不是只存 UI HTML 或过期签名。每个 note 只存一次；单元格只引用这些记录，
避免 “Day2已含Day1，再把Day2整体追加给Day3” 的指数重复。
past context 从已验证 publication 读取，浏览器不能提交任意历史来冒充 baseline。
`weekly_seed.note_refs`只引用该周开始时携带的旧note，同周新note不能被重新标成seed。
换周时seed.baseline使用本次实际选择的`base_daily_publication`；earlier_period_refs
只保留可核验的PublicationRef，不拿PeriodIdentity或更早的baseline字段替代。
默认latest-note按实际meeting日期与note revision选择，不依赖输入数组顺序；
`cross_week_carry=full_history`时不执行默认最近一条压缩。

同周：每列选择 seed + 当前周截至该日期的 notes，按真实日期升序；
源状态、颜色、链接、正文和 AR 来自各自 note revision。
未发生新更新的日期保留已有内容；需要显示“无变化”必须有完整观察证据。
没有当日 note 不能伪造一个今日日期的旧句。

完整有效 context 保存到 `edits.json` 的 `authoring_context`，历史 revisions 仍独立保留。
schema2 manifest/intent 增加 `series_id, report_role, meeting_key, period_key, continuity_hash`；
`continuity_hash` 为有效 context 的 canonical SHA-256。六文件名单不变，
旧 schema1 的 reader/hash/文件字节不变。所有 exact-key validator 必须同步升级。
草稿 revision_hash 同时绑定 context、模板版本、富文本/颜色与 source snapshot。
publication reader、resume、download、next-day reader 都检查同一 hash 和身份。

继续使用原配额：单 fragment16KiB、活跃编辑1MiB、修订历史8MiB、HTML16MiB；
context 单独最多8MiB，全部物化字节计入原 archive 准入，而不是只计引用字节。
超限明确拒绝并保留旧内容；不通过删除颜色、截短 AR 或丢前几天绕过额度。
基线 catalog 在前次 context 中完整携带每票最后已确认 note 引用和未结束行动，
无需每次无限遍历全历史；遇旧格式缺 catalog 用有界历史读取或显式迁移，
不能把读不到当成没有历史。

颜色按精确值保存，不依赖“今天模板中的红色”别名。
历史文字的淡化/最新结果底色不能覆盖用户显式前景/高亮；历史区只读不等于变灰失真。
支持范围、编辑器往返、renderer 和导出均必须验证，未验证不宣称已保证。

## 7. Weekly Rollover

默认 `cross_week_carry="last_confirmed_and_unresolved"`：

1. 选定同系列、早于新周第一会议日的最新已确认 daily publication。
2. 对仍获准展示的每张票，取其最近一次实际已确认 note，不要求恰好发生在周五。
3. 携带该 note 的用户最终文字、颜色/高亮、链接、原日期/原状态及来源，不重写。
4. 独立携带全部 open/unknown AR、未确认建议和常驻备注。即使 AR 来自更早一天，
   也不能被“只带最后一条”过滤掉；按 action_id 去重。
5. 新周只追加新日期内容，完整旧周历史仍通过 earlier_period_refs 可读，
   历史按钮只读归档、不重新解析 AI。

例如（合成示意，不是对真实工单的声明）：

```text
ww45.5(In Analysis): Waiting for validation. AR: @Owner rerun the test.
ww46.1(Fixed): Validation confirmed on the selected build.
```

如果上一条实际记录是 ww45.3，就保留 ww45.3，不能重标为 ww45.5 或 ww46.1。
上周二的未结束 AR 仍带原 issued_meeting；已 done 的历史 AR 可以在旧 note 中保留，
但不会进入新周“未结束行动”集合。

这是展示窗口压缩，不是数据删除。用户之前的其他普通 note 仍完整存在于旧周历史；
需要一直显示的人工说明使用“常驻备注”显式标记。
模板也可选 `full_history` 展示全部历史；额度或旧历史不可用时明确失败，不静默压缩。
周界、跨年、长假/没有周五日报、上一周完全没运行、票关闭后重开均按实际记录处理。
Fixed/Done 不自动移出 scope 或抹掉未结束 AR。

前一工作日有已保存未定稿内容时默认 `REPORT_BASELINE_PENDING`，
提示打开原草稿处理。允许用户明确“以最近正式报告继续”，记录 skipped draft IDs 和 gap，
但不能自动丢弃草稿或把它算作已确认。首轮没有 baseline 时明确初始报告，
从 source/人工内容建立第一版，不伪造前周更新。

## 8. Stable Row Ordering

一票一行，shared PR/assignee 不合并 note、AR 或关闭判断。
模板配置组定义/组顺序、初始排序和新票位置；具体 ticket 的稳定位置在 RowOrderSnapshot。
默认初始排序为 natural key ascending，数字 ID 按数值段排序；
相同展示 key 以 provider/endpoint/stable_id 作确定性 tie-break，不用 AI 评分。
已有明确用户顺序可在首次确认时作为 seed，之后位置固定。

新票批次按初始规则排序后追加到对应组尾；未归组用明确“Unclassified”组。
状态/assignee/更新时间改变不自动挪行。用户显式移动/改组保存新 revision，
后续日期继承；已定稿历史不重新排序。移出后重返的同 stable_id 复用保留位置。
group_by=status 等动态指标视图不等于会议矩阵的稳定分组，不能把两套排序混用。
当天重点用 key_messages 引用，不能靠自动打乱长期跟踪表表达优先级。

## 9. Manual Preparation And Optional Schedule

默认入口在现有 Stage report 页，用新语义 `生成今日草稿` 接原 run submit 路径。
展示所选系列、会议日期/时区、模板、前次正式 baseline 和来源刷新方式。
按钮是业务生成入口，与“禁止补全按钮触发”无关；`#ID` 仍是唯一工单补全触发。

| 操作 | 允许副作用 | 不允许 |
| --- | --- | --- |
| Generate today | 锁定 baseline/template/meeting，显式刷新获准来源、必要时分析，产出已保存草稿 | 自动定稿/发邮件/工单写入 |
| Create from saved capture | 从明确 capture 创建草稿、人工填写 | 偷偷抓最新源/自动启动 AI |
| Save | 校验并保存完整富文本修订 | 推进正式报告基线 |
| Refresh source / regenerate | 显式新命令和 reviewable 候选，保留原人工内容，冲突需确认 | 原地覆盖已编辑草稿或历史 |
| Finalize | 用户确认精确已保存版本，原六文件提交确认后推进 daily baseline | 以预览/下载/未知提交冒充成功 |
| View another week / GET | 只读已有 period/publication | 自动生成、采集、AI、定稿 |

准备的 AI policy 为 `manual_only` 或 `changed_items`。选择 changed_items 是对本次
允许生成候选的显式选择，仍受现有 provider/model 授权和资格约束；
它不是 template render 的隐式调用。无变更且原摘要有效则零模型调用。
可编辑新 note 优先由既有 accepted summary 确定性投影；单独 AI 改写仍走 Assist。
不把人工内容送往新模型隐式训练或当作源事实接受，必要上下文有 provenance。

一个 meeting 只能有一个 active preparation/draft slot。
slot身份按`series_id + meeting.local_date`固定，calendar id/revision只是该次选择元数据，
不能因同日修改日历策略生成第二slot。新日历选择与旧slot不同时返回calendar conflict，
仍保留原meeting标签。命令重放和已有slot读取先于新请求的当前policy/template/baseline准入，
但始终先核验当前owner/project/stage访问权；不借replay绕过权限。
先持久化占位与 command/request hash，再释放锁进行 provider/AI I/O；
不同按钮请求、CLI、scheduler 同日同时到达，后到者返回既有 draft/run，
不得重复付费/采集。已有人工编辑时默认打开，不自动重建。
区分两种幂等，不把“同日”当作“同command”：

- **同 command_id**：规范化request hash相同才重放；不同payload返回
  `REPORT_PREPARATION_COMMAND_CONFLICT`，不替换原选择。
- **不同 command_id、同 meeting slot**：无论template/source/analysis选项是否相同，
  返回原operation/当前draft，`disposition="existing"`，不发起第二次工作。
  返回原`effective_selection`，不同选项放入`selection_conflicts`并提示“已有草稿，
  新选项未应用”。不能让用户误以为新的模板或刷新要求已经执行。
- 已定稿的同日slot返回原publication入口；已失败/取消slot返回原终态和明确恢复/重建动作，
  不因新command自动重跑。显式reprepare走下一段的独立受控操作，不是普通prepare重试。

运行能力检查只针对新工作，在上述原请求/同日工作识别之后执行。表单校验引用语法，
不能用当前模板列表、runtime不可用或AI未配置抢先拒绝原命令重放；新请求仍由服务
验证归属、当前策略/模板、基线及能力，拒绝时不得留下新的准备意图或抓取/模型调用。
`runtime_options()`只返回本地装配能力，不探测网络或启动服务。界面可据此禁用新选择，
错误页面保留用户原值，不静默从AI切换成人工。

首次refresh允许在上述新请求校验之后初始化已配置且获授权的stage数据归档，再持久化
准备slot/意图，最后交给原worker采集。GET预览/查询遇到尚未初始化的stage时返回
initial/不存在，不初始化目录或Git。损坏的控制文件（含JSON null/非对象或非整数版本）
不是不存在，必须明确拒绝，不能因此创建第二份准备记录。

`PreparationResult={disposition:"created"|"existing", preparation_id, operation_id:UUID|null,
draft_id:UUID|null, draft_revision:int|null, publication_ref:PublicationRef|null,
effective_selection, selection_conflicts:("template"|"source"|"analysis"|"calendar"|"baseline")[],
state, links}`。selection只含公开ID/版本/模式，不含凭据、原始query或服务器路径；
links为应用自身已授权URL，state沿原operation/draft词汇，不伪造完成。
过午夜的作业仍写原 meeting，不因当前 clock 改日期；迟到失败不回填假的日结果。

定时模式是 W7 deferred-with-trigger：只有 schedule 配置、运行身份、凭据、授权及
实际任务资格具备才可启用。配置含 timezone、local_time、working_days、calendar revision、
enabled=false 默认、misfire_policy=skip、analysis_mode。
它调用同一个 preparation API；不模拟点击，不另建业务流程，不自动 Finalize。
重复调度与手动触发共享 meeting slot；休眠/停机错过时只记 missed，不补造历史日报。
DST 不存在的本地时间记 missed，重复时间按同一个 occurrence/meeting 幂等，
不执行两次。首次实现不自动安装或启用系统定时任务。

## 10. APIs, Locks And Recovery

新增公共 API 由 `project_management/app/api/report_continuity.py`、
`report_preparation.py` 暴露，逻辑实现分别位于 `services/`；UI 不调用私有存储。
系列设置复用项目配置持久化，日报控制记录复用原 stage runtime/锁。

### Prepared Context Contract

HISTORY先实现`ReportContinuityService.prepare_context(actor,project_id,stage_id,*,
preparation_id,create_command_id,series_id,series_policy_hash,meeting_date,
expected_baseline_ref,selection,template_use_hash) -> PreparedContextRef`，
仅供后续ReportPreparationService调用，不新增接受任意context的HTTP端点。
输入只有已验证记录引用/选择，context由服务读source/series/template/use/publication后构造。
HISTORY的service测试也走这个真实构造与存储路径，不能手写context绕过验证。

原stage runtime下`report-preparations/<preparation_id>/context.json`保存不可变seed：
`schema_version,preparation_id,create_command_id,draft_id,project_id,stage_id,owner_subject,
series_policy_hash,meeting_key,period_key,effective_selection_hash,template_use_hash,
expected_baseline_ref,snapshot_hash,context,context_hash,created_at`。
当前实现还固定`series_id,stage_hash,series_policy_revision,template_request_hash`，
全部纳入精确字段校验；template_request_hash只绑定先于context的选择意图，
最终authored create request另绑定context_hash，避免template use与context互相引用hash。
`pinned_template_use_hash(PinnedTemplateUse)`从原完整use payload规范计算，
调用者不需直读ORM，也不改旧use字节。读取seed须核对URL/路径的preparation_id与内嵌值，
不能以seed字段与自身比较代替请求绑定。
draft_id沿现有stage/create_command派生；context_hash是完整context规范hash。
PreparedContextRef只返回`preparation_id,context_hash,draft_id`；不是浏览器可伪造权限票据。
seed只负责传递已核验context，后续编辑内容权威仍在draft revision和Git publication。
不在seed里维护第二份draft/finalized状态或业务head，绑定由原create command/修订证明。

模板use的只读消费接口为
`ReportTemplateService.read_use(actor,project_id,*,draft_id,template_use_hash)
-> PinnedTemplateUse`。template_use_hash是已持久化use payload的规范hash，不是
模板presentation_hash。读取须核对项目owner、draft、use/command/revision三者一致，
重算原`continuity_prepare`命令hash；不能只按当前模板ID取latest或信任HTTP传入snapshot。
`use(...,use_mode="continuity_prepare")`只接受ready document schema2且恰一个matrix，
保留原standalone schema1的use/command字节和拒绝策略。模板归档后已有合法use仍可读取，
但不能新建use；read_use无写入/配额重置/AI或provider调用。
HISTORY core拥有此窄模板消费接口，后续DAILY先use后prepare_context，两个事务不嵌套持锁。

### Prepared Authority Binding

受同日slot控制的准备与旧内部HISTORY seed须显式区分，不能扫描所有context文件或
在缺失intent时默认放行。`prepare_context`增加server-only `authority`参数：
`{schema_version:1,kind:"daily_preparation_active_slot",preparation_id,
preparation_intent_hash,slot_id,slot_key,draft_id,create_command_id,series_id,meeting_date}`。
只有ReportPreparationService在核验intent/slot后传入；HTTP不能设置authority。
旧内部调用无该authority仍写原schema1 seed；受控调用写声明schema2的seed及authority，
完整校验其与source/series/template/command/meeting一致。

create_authored将具体seed的authority固定到draft-owned不可变binding：
内部binding含`schema_version:1,kind:"internal_prepared_context",project_id,stage_id,
draft_id,create_command_id,request_hash,preparation_id,context_hash,snapshot_hash`；
受slot控制binding为schema2/kind daily_preparation_active_slot，再含
`preparation_intent_hash,slot_id,slot_key`。binding hash和kind同时绑定原不可变create
intent/command，不能把受控binding替换成internal种类绕过guard。
新intent版本严格声明该字段，旧intent读取和六文件publication字节保持兼容；
缺binding、错hash/kind、缺或坏intent/slot均拒绝，不扫目录寻找另一个可用seed。
普通standalone没有该binding，linked correction沿原parent publication CAS。
worker采集/compose和prepared daily定稿前校验活动slot；原已提交精确packet重放只读，
不会因为旧command被读取而恢复它的活动地位。

### Replacement Preservation Seed

Daily界面的终态详情通过`ReportPreparationService.get(actor, project_id, stage_id,
preparation_id)`读取；`for_meeting(..., series_id, meeting_date)`只按明确meeting slot查找，
不存在时返回空，不扫描/创建seed，不调用prepare或operation submit。返回
`PreparationDetails{result:PreparationResult,operation_revision:int|null,
draft_revision_hash:str|null,active_preparation_id:str|null,parent_preparation_id:str|null}`。
期望修订来自已验证的当前记录；准备意图存在但worker/draft尚未创建时显示prepared，
坏记录不能当作缺失。旧准备和其替换链接均可只读访问。UI重建仍由POST执行服务端CAS，
读取详情与点击之间若有变化明确冲突，不按GET观察擅自锁定或推进状态。

重建的新草稿在首次保存版本中包含经应用验证的父稿人工内容，不先暴露缺少人工修改的
中间稿。guarded seed schema3增加server-created preservation对象：
`{schema_version:1,parent_draft_id,parent_draft_revision,parent_draft_revision_hash,
initial_authored_edits,initial_authored_edits_hash,review_issues,preservation_hash}`。
父引用来自已核验replacement intent，不能由HTTP提交。initial_authored_edits使用已有
严格作者内容/来源记录schema，单独hash；preservation_hash绑定父引用、编辑hash和review
issues。context_hash仍绑定完整有效context，最终create request同时绑定context_hash及
preservation_hash。旧schema1/2 seed及旧create request重放原字节不改。
普通saved-capture和refresh worker共同消费该schema3 seed；preservation在seed哈希前完成。
无法匹配的ticket/slot/group输出明确review issue并保留原稿，不静默删除正文/颜色。
`PreparationResult`及草稿读取投影携带typed `preservation_review_issues[]`，
每项`{code,target,reason}`来自已验证preservation payload，不从浏览器或当前模板猜测。
无问题默认为空；重放/排队完成后的结果也必须返回相同有效提示，不能只埋在seed中。
存在未处理的内容保留问题时禁止Finalize，保留原稿及候选并返回明确review-required错误；
不能因为部分可匹配内容已写入就宣称无损完成。后续解决/重建必须显式，不自动忽略提示。

### Daily Worker Dispatch

DAILY显式刷新复用现有ProjectRunService，不先生成旧schema1草稿再转换。
保留旧`RunRequest(command_id,expected_stage_hash,template,timezone)`和四字段序列化原字节，
新增独立`DailyRunRequest`，只由ReportPreparationService冻结选择后创建：

```text
schema_version: 2
command_id, expected_stage_hash, timezone
template: AuthoringTemplateSelection | UserTemplateSelection
target: {
  kind: daily_preparation,
  preparation_id, preparation_intent_hash, draft_id, effective_selection_hash,
  source_mode: refresh,
  analysis_mode: manual_only | changed_items
}
```

此处冻结的是准备意图hash，不是尚未采集完成的context_hash。
真正context_hash只能在source/analysis完成、prepare_context生成seed后进入
`draft-selection.json schema_version=2`，防止要求提交尚未存在的来源/历史内容。
refresh的原API请求capture_id=null，与受理后派生的effective capture_id分别保存/校验：
request_hash从原规范请求重算，不能把effective UUID填回原请求冒充同一重放。
新增version2准备intent保存原request和effective selection，hash不包含自身hash字段，
并逐项验证其派生operation/capture/draft身份。既有saved_capture intent schema1原字节不变。
完整target/input未知字段拒绝，request_hash按版本规范字段计算；旧请求hash不变。
operation_id仍UUID5(stage,"run:"+command)，capture和draft command仍沿旧派生规则，
目标draft_id须与该draft command派生结果一致。Preparation自己的command/operationcommand
关系持久记录，重放不能重新派生不同run。

stored request schema2按原admission_hash绑定request/policy/stage/capture limits，
backend=null仅允许manual_only；changed_items必须具备原合格backend。
manual_only不构造SDK/模型client或调用analysis prepare/advance/cancel，
但仍走现有capture预算/权限/取消及composting检查。saved_capture不进入worker，
由相同prepare service直接从指定capture构造context/draft，0provider/AI调用。

Worker仅在最终compose一步按request版本分派：
旧schema1原`draft_service.create`不变；daily版消费原准备意图与当前capture，
可选changed_items分析完成后由HISTORY生成seed，写schema2 draft-selection
`{schema_version,kind,preparation_id,context_hash,selection,template,draft_id,command_id,payload_hash}`，
然后只调用一次`create_authored(preparation_id)`。不另写一个schema1中间草稿。
RunOperation原字段已能携带结果draft/revision/hash，无需复制第二operation状态authority。

取消、request-only恢复、CLI/status/resume和factory按版本核验原request/admission/hash，
保留operation/capture/准备意图/预算/日期，不续期或换新key。
同日去重与terminal reprepare仍由准备slot负责，raw run只做command幂等。
业务meeting_date可注入历史日期，但执行deadline用真实受控单调/墙钟预算；
完整周合成source cutoff可按fixture日期推进，系统时钟和真实工单updated不改。
核验消费者为run_values/run_admission_values、ProjectOperationRepository、原recovery、
worker/_draft、CLI/forms、factory及draft-selection reader；不得只加DTO不改reader。

`create_authored(preparation_id)`通过注入的context reader读取并校验完整seed，
与当前actor/project/stage/source/template/command/draft身份逐项一致；再次验证baseline/refs。
随机ID、跨目标ID、错误hash或已被reprepare替换的meeting slot均拒绝；
原command相同请求的重放依旧优先，不重新选择最新source/template。
DB template use事务先完成并释放，再按原root/stage锁写seed及draft；
不持stage锁写DB。写seed后未写draft的中断可重放，不删除seed或分配新command绕过。
DAILY再围绕此能力添加公开按钮、同日slot、worker/refesh/分析与恢复编排，
而不是让HISTORY依赖尚未实现的HTTP/UI来测试非空context。

Finalize在同一stage锁下、写packet/commit前复验expected_baseline_ref和meeting slot；
过期直接拒绝，不先提交再抢baseline。Git确认后才更新可重建series-head缓存；
缓存丢失从已核验的daily publication链恢复，不能将缓存自身当历史权威。
weekly_view/旧日correction仅归档不抢head；响应丢失resume核验原packet/commit再修缓存。
daily head按实际meeting local_date的前进及已验证publication链确定，不能按finalized_at
选最大值让晚提交的旧日纠错抢占。未提交packet的resume在同stage锁下仍须执行baseline CAS；
已经确认提交的精确packet只返回原结果，不因后来head前进而重复提交或回退head。
RA63/64覆盖两个同基线窗口、随机/跨target seed、写seed后崩溃、commit后缓存丢失，
必须断言拒绝前无新publication，恢复后不重复commit/source/模型。

```text
ReportContinuityService.create_series(actor, project_id, stage_id, *,
    command_id, name, calendar:ReportingCalendar,
    template_selection:AuthoringTemplateSelection) -> SeriesPolicyRevision
ReportContinuityService.save_series_policy(actor, project_id, stage_id, *,
    command_id, series_id, expected_revision, expected_revision_hash,
    name, calendar:ReportingCalendar,
    template_selection:AuthoringTemplateSelection) -> SeriesPolicyRevision
ReportContinuityService.list_series(actor, project_id, stage_id, *,
    limit=20, offset=0) -> {items:SeriesPolicyRevision[], next_offset:int|null}
ReportContinuityService.get_series_policy(actor, project_id, stage_id, *,
    series_id, revision) -> SeriesPolicyRevision
ReportContinuityService.preview(actor, project_id, stage_id, *,
    series_id, meeting_date, template_selection) -> BaselinePreview
ReportPreparationService.prepare(actor, project_id, stage_id, *,
    command_id, series_id, meeting_date, expected_series_policy_hash,
    expected_baseline_ref, template_selection,
    source_mode: refresh | saved_capture, capture_id:null|UUID,
    analysis_mode: manual_only | changed_items,
    acknowledge_gap_draft_ids:UUID[]) -> PreparationResult
ReportContinuityService.read_period(actor, project_id, stage_id, *,
    series_id, period_key, selected_publication_refs) -> PeriodView
```

`PeriodView`为只读派生值，包含`series_id,period_key,selected_publications,
source_snapshot,weekly_context,matrix`。selected_publications是经过完整hash/owner/
series/period核验的明确日报修订；source_snapshot来自所选最后日期的已归档日报，
不查询当前工单或最新capture。weekly_context以选中的确认历史合成，meeting=null，
selected_daily_publications非空；同日明确选择一个修订，重复/跨系列/跨周选择拒绝。
缺少日期只能标记缺日报，不能从两个已选日期之间推定来源未变化。
选择顺序按会议日期规范化。若周一修正版被明确选择，周二保存的旧周一副本不能覆盖它：
DailyNote取对应选中会议日的有效版本。AR和常驻备注可在后一天被明确修改，不能仅按
issued_meeting归属过滤；用各选中publication已核验的首修订与最终修订辨别本日显式变化，
按日期应用这些变化字段，忽略未改动的继承副本。这样较早的人工正文修正和较晚的行动
解决都能保留。未结束集合从合并后的状态生成，不以实际执行时钟决定业务版本优先级。

`build_meeting_matrix(snapshot,context)`返回共享纯投影：
columns含`local_date,meeting_key,label,state`，rows含`issue_ref,title,current_key,
group_id,position,visibility,cells`，cell含`local_date,note_ids,action_ids,
current_observation_note_id,source_state,state`。日期/累计note及AR选择由此一次计算，
renderer和UI共同消费，不分别实现一份排序/跨日算法。
没有历史当日观察证明时只显示“无记录”，不把无正文等同于来源未变化或采集失败。
当前可编辑空槽由current_observation_note_id绑定，历史单元格无可编辑目标。

显式周报草稿入口为
`ReportDraftService.create_period_view(actor,project_id,stage_id,*,command_id,
series_id,period_key,selected_publication_refs,template) -> ReportDraft`。
它消费同一read_period的验证结果和精确ready weekly模板use，冻结source_snapshot/
weekly_context为只读schema2 revision；不是另一个正文存储。后续Finalize仍提交原六文件，
report_role=weekly_view，不推进daily head；创建/读取/定稿全程零provider/AI调用。
同command重放绑定原选择及模板，不能重新解析latest。周视图不可执行普通save_authored
改变历史；需选择另一组确认日报时显式新command创建另一份视图。

series API是显式设置入口：GET不建默认系列，POST create不从标题/Stage隐式猜UUID，
同command同请求重放同series；save用expected revision/hash，旧draft绑定的policy不变。
HTTP的series/list/detail/policy见contracts；UI在Stage报告页先选已存在series，
无series时提供“创建报告系列”，填写name、日历与v2模板，不访问provider或AI。
`list_series`按created_at/series_id稳定排序，limit1..100，offset>=0，归属先校验。
日历revision切换只用于明确的新准备，旧period按旧映射只读，不重新分桶历史。

preview 只读本地已核验记录，返回 `initial/ready/pending/unavailable`、选中的明确 publication，
日期与缺口；不是权限票据。prepare 在创建意图前重验 baseline ref、归属、Stage hash、模板、
日历和同日 slot。CLI/调度只能由受信 transport 构造 actor/trigger，不接收 caller 凭据。
refresh 消费原 ProjectRunService；saved_capture 不启动 worker。
Base profile 不可用时 manual_only 仍可工作，changed_items 返回可恢复失败/partial，
不能改用其他 provider/model。

显式 `ReportPreparationService.reprepare(actor, project_id, stage_id, *,
command_id, preparation_id, expected_operation_revision, expected_draft_revision,
expected_draft_revision_hash, expected_baseline_ref, template_selection,
source_mode, capture_id, analysis_mode)` 只接受已经终态的原operation。
无draft时expected_draft字段为null，有draft时必须精确匹配已保存且非finalizing版本。
它先保留原draft/内容，按同一个meeting产生新的revision或关联草稿候选，
不抹掉原记录。已finalized时只能创建linked correction；推进最新baseline仍受原CAS。
active slot的替换在同stage锁内先写reprepare意图，成功后后续prepare返回新候选，
失败/未知时可重放同command，不能并发派发两个重建。未保存的浏览器内容先Save；
scheduler永不调用reprepare。新增POST `/preparations/<id>/reprepare/`走原CSRF/owner校验。

状态复用原 operation 状态，附 `preparation_phase`：
`reserved -> collecting -> analyzing -> composing -> draft_ready`；
另有 `partial/failed/canceled/interrupted`，均不等于正式 baseline 更新。
准备意图绑定旧 baseline、series policy、source选择、template use、meeting、原 runKey，
中断恢复继续该意图，不重新选择最新版本、不重置预算。
history 缺失阻止 composing，保留已完成采集/分析，不能用空历史接着跑。

锁顺序沿现有 project/template use 先冻结并释放 DB 锁，再拿 stage 锁；
baseline compare-and-set、同日 slot 和 publication 提交使用同一 stage writer 边界。
Git commit 是正式基线的提交点；series latest 指针只作可重建缓存。
commit 成功而响应/缓存更新失败时，先核验该精确 publication，再重建指针，
不得重复提交或重新抓源。未知 commit 不能显示“已定稿”。
新 baseline 被其他窗口推进时，旧 draft 返回 `REPORT_BASELINE_CONFLICT`，
用户显式合并/重建关联草稿，不能 last-write-wins。
weekly_view 和旧日期 correction 不自动抢占最新 daily head；纠错的既有后续报告不改写，
需要显式选择新 revision 重新准备后续草稿。原 hash 和 parent 链保持可追溯。
作者日报纠错使用
`ReportDraftService.create_linked_revision(actor,project_id,stage_id,*,
command_id,publication_ref) -> ReportDraft`，只接受已验证的daily作者publication。
服务端复制该报告的有效context、template_snapshot、source_snapshot和已接受编辑，
保留原meeting/历史片段，将parent_publication_id及本次expected baseline绑定到原publication。
调用者不能上传替换context或重选模板；原command先重放已保存草稿。
只允许修订该原会议日的可编辑目标，普通历史note仍受保护。
来源证明是经过明确parent引用的已归档快照，不声称是今天最新来源；定稿锁内复验原parent/
snapshot/template身份，而不是关闭所有source-drift守卫或对所有linked草稿直接放行。
若纠错日期早于当前daily head，只归档且不抢head；同日纠错须parent仍为当前head才可推进。
这样旧日纠错和当前日并发修改分别有可验证的CAS规则，原后续报告字节均保持不变。
`ReportSelection.baseline_publication_id` 保持原比较来源语义；
`authoring_context.base_daily_publication` 才是本附录的作者继承基线。
正常日报可以指向同一前次daily，纠错/历史导出不能仅因二者同名就互换。

HTTP 沿原 stage reports namespace，新增 `/preparations/` POST、
`/periods/<period_key>/` GET 和 `/baseline-preview/` GET；返回值携带既有 operation/draft URL。
系列设置新增`/series/` GET/POST、`/series/<id>/?revision=N` GET及`/series/<id>/policy/` POST，
由同一public API和Project ORM事务处理，不要求UI自行创建隐式series。
Save/Finalize/Resume 仍沿原 URL 与 command 协议；新公共方法必须有真实调用者，
不能只由测试构造。`project_run` 增加 versioned authoring selection 后才可接 CLI/调度，
旧 schema1 request/重放保持原解释。

## 11. Failure And Visibility

| Code | Behavior |
| --- | --- |
| `REPORT_BASELINE_PENDING` | 打开未定稿草稿或明确确认 gap；不自动丢弃 |
| `REPORT_BASELINE_CONFLICT` | baseline/series/template 被别人推进；保留全部输入，显式重新选择 |
| `REPORT_HISTORY_UNAVAILABLE` | 来源 publication、片段/hash、权限或 reader 缺口；禁止假报完整继承 |
| `REPORT_CALENDAR_UNAVAILABLE` | 日期没有合格周映射；不调用 AI 猜测 |
| `REPORT_SOURCE_CHANGED` | 来源漂移或状态不可证明；显式刷新/审阅，原历史不变 |
| `REPORT_DOCUMENT_UNSUPPORTED` | 颜色/节点不能往返；保留输入，不静默降级 |
| `REPORT_LIMIT` | 累积/物化输出超额度；停止新保存/生成，保留历史 |
| `REPORT_SCHEDULE_UNAVAILABLE` | 调度未启用/未合格；手动入口继续可用 |
| `REPORT_PREPARATION_COMMAND_CONFLICT` | 同command不同payload拒绝；不同command同meeting返回existing及未应用选项提示 |

UI 增加对应 loading、dirty、saved、baseline pending、source stale、partial、
empty-period、read-only-final 状态。沿用 Bulma 共享 action/tool/editor classes，
颜色使用有标签色板和清除格式命令，不能把任意 CSS 输入当成编辑器扩展。
跨周 carry 行可明确标记来自哪天，颜色本身不承担状态含义。
权限丢失的历史正文不继续自动展示；保存原字节不等于允许向新主体泄露。

## 12. Verification Boundary

RA41-72 及 tasks HISTORY/DAILY 负责本附录，原 RA01-40 不重新编号。
必须实际闭环：AI候选 -> 人工删改/着色/#链接 -> Save/reopen -> Finalize ->
次日/第三日/新周 -> 内容/样式/状态/行序校验。
比较片段 canonical hash 和语义格式，归档下载另比较精确字节；
跨日整个 HTML 的日期不同，不能用全文 hash 相等冒充正确检查。
失效基线、断网、写满/额度、并发、旧日纠错和 scheduler race 都有拒绝判据。
模板拼接、继承和保存不消耗模型 token；让模型读取旧摘要/新证据时仍计输入 token。
本轮只运行文档/规格检查，不运行待实现用例，不重新使用真实企业材料做公开 fixture。

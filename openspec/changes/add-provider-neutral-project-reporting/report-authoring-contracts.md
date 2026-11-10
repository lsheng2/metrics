# Report Authoring Contracts

日期：2026-11-03。状态：accepted，实施中。父设计：[authoring](report-authoring-v2.md)。
方法为本次新增/升级契约；已实现范围以唯一tasks及当前guide为准。
Python 内部及 Dashboard HTTP 沿现有 snake_case；AI 运行自2026-11-11经MDB-2同步task-run端口，值类型归project_management。
连续性、系列/周周期、状态、AR 和触发契约见[report continuity](report-continuity.md)。
本次补齐尚未发布的作者层 schema2；不修改已经产生的 schema1 原字节。

## 1. Rich Text And Template Values

规范 JSON 沿 `capture_values.canonical_bytes`：UTF-8、排序 key、有限数值、原 Unicode。
所有未知字段、未知版本、bool 冒充整数、超界集合和循环内容均拒绝。
hash 为 SHA-256 lower hex，resource/command ID 为规范 UUID string。

`RichTextFragment = {schema_version: 1, blocks: Block[]}`：

| 节点 | 精确字段（除明确可选外必填） |
| --- | --- |
| text inline | `type="text", text: str, marks: ("strong"|"em"|"strike"|"code")[]`；marks 去重固定排序 |
| link inline | `type="link", href: str, text: str`；可选 `reference_id: UUID` |
| break inline | `type="break"` |
| paragraph | `type="paragraph", content: Inline[]` |
| heading | `type="heading", level: 1..3, content: Inline[]` |
| quote | `type="quote", blocks: Block[]`；不得包含递归 template/data/slot |
| list | `type="list", ordered: bool, items: {checked: bool|null, blocks: Block[]}[]`；有 checked 的项目不可为 ordered |
| table | `type="table", headers: Inline[][], rows: Inline[][][]`；非空列且每行列数相同，无 merge cell/嵌套 table |
| code | `type="code", language: str, text: str`；language 仅 allowlist 中的展示值 |

上述 fragment v1 保留读取语义。颜色支持采用新的 **fragment v2**，
与外层 `authoring_schema="report-authoring/2"` 分开分派：

| v2 改动 | 精确字段 |
| --- | --- |
| text inline | 原 type/text/marks，加 `foreground:Color|null, background:Color|null`，两字段必填 |
| link inline | `type="link", href:str, content:TextInlineV2[]`，可选 `reference_id:UUID`；非空，无嵌套link |
| 其他节点 | 原块/换行结构不变，内部 inline 使用 v2；code 块不接收 CSS |

`Color` 仅不透明 RGB 的规范小写 `#rrggbb`；null 表示未显式设置/清除。
不接受任意 style、class、CSS变量、URL、表达式、透明度或脚本。UI 提供合法色板，
服务端独立校验；渲染器只生成 `color`/`background-color` 两种安全属性。
相邻同格式 text runs 可 canonical 合并，但不能删除用户文字或 paint 信息。
链接的每段文字可独立保留颜色/高亮/marks；不能因补全后变成 link 而丢格式。
纯格式修改也是 dirty revision，并改变 fragment/draft hash。
合法低对比颜色给本地提示，不悄悄改成模板色；历史淡化样式不得覆盖显式 paint。

v1->v2 只在显式编辑保存时转成无 paint 的等价内容；旧读取/下载不写新 hash。
JSON fragment 是格式权威，不以 Markdown 往返保留颜色。
HTML/WYSIWYG 必须保真；Markdown/plain 明示不支持颜色，Excel 按已验证能力声明，
无法表达的格式不声称无损，原 fragment/HTML 必须保留。
Vditor公开Markdown桥梁的颜色资格失败；既定备选Milkdown7.23.0的公开schema/JSON探针通过。
EDIT采用直接结构映射，仍须验证实际页面和服务端往返；不降级需求或维护私有fork。

同一 fragment 最多 16 KiB UTF-8、1000 nodes、嵌套深度 6；一份 revision 活跃编辑 <=1 MiB。
继承原 cumulative history8MiB、1000 revisions、snapshot8MiB、HTML16MiB、clipboard2MiB。
用户有意提交的未知节点必须拒绝并保留输入；普通粘贴先本地净化并提示格式移除，
仅在用户看到净化结果后才发合法结构，不把静默丢弃伪装成无损。
服务端不接受 raw HTML 或用户任意 CSS/表达式，所有 text 由 renderer 转义；
v2 的受限 Color 由 renderer 生成安全样式，不是开放 CSS。
普通链接仅 HTTPS、无 userinfo/control chars；引用链接额外绑定受控 provider 的 web origin/path。

编辑器 adapter 的公开契约（新本地 ES module，不依赖后端第三方类型）：

```text
mount(element, {fragment, onDirty, onCompletionToken, readOnly}) -> EditorHandle
EditorHandle.getFragment() -> RichTextFragment
EditorHandle.captureToken() -> {editor_epoch, region_id, local_version,
                              bookmark, expected_text} | null
EditorHandle.applyCandidate(capture, candidate) -> applied | stale
EditorHandle.replaceFragment(expected_local_version, fragment) -> applied | stale
EditorHandle.destroy() -> void
```

bookmark 只在 adapter 内有效，不发服务端。应用fragment与Milkdown/ProseMirror document
经公开schema/transaction和映射表转换，不用正则替换实现编辑内核。没有能保留语义的映射时拒绝。
`applyCandidate` 替换含 `#` 的精确 token，一次 transaction/undo； title/owner 是普通文字。

`ReportTemplateDocument = {schema_version:1, report_kind:"daily"|"weekly",
blocks:TemplateBlock[]}`，每块都有不可变 `block_id: UUID`：

- `content`：`kind, block_id, fragment`。
- `slot`：`kind, block_id, slot_id: UUID, label: str, required: bool,
  initial: RichTextFragment, fill_mode:"manual"|"ai_optional"`。
- `data`：`kind, block_id, source:"key_messages"|"changes"|"register"|"coverage"|"weekly_timeline",
  options:{group_by:"none"|"status"|"assignee", sort_by:"key", optional_columns:("summary_time"|"source_hash")[]}`。

该 v1 定义保留读取。新增模板 document v2 的schema_version=2，使用同样的块基本结构与 fragment v2，
data source 另外允许 `meeting_matrix`。它的 options 不套用动态 status 排序：

```text
row_mode: one_ticket
order_mode: stable_append
initial_sort: key_natural_asc
group_mode: none | manual
groups: [{group_id:UUID, label:str, rank:int}]
history_mode: cumulative
cross_week_carry: last_confirmed_and_unresolved | full_history
note_prefix: workweek_day_source_status
action_labels: {recorded:"AR", proposed:"AR?"}
```

groups 是模板组定义，票据位置由 continuity 的 RowOrderSnapshot 管理。
group_mode=none 时 groups 为空；manual 有明确 Unclassified 兜底组，group ID/rank 唯一。
不接受可执行循环、用户表达式或将模板 group 判断作为 scope 权限。
v2 `daily` 与 `weekly` 模板都必须恰有一个 `meeting_matrix` 和原四项必要区，
weekly 另恰含一个 weekly_timeline。矩阵是正文的必需消费面，
register/changes可放附录但不得漏行/待办。缺矩阵可存draft，不可标ready或用于系列准备。
v1模板保留旧的ready解释和旧版下载能力，但不能被新的系列准备入口选中；
CONTENT阶段的无矩阵文档仅是standalone过渡，不构成daily连续性闭环。

填写说明不混入可执行模板：独立
`TemplateFillPolicy={schema_version:1, instructions:{slot_id:str}}`，
每条 <=4KiB，总量 <=32KiB；只允许对应 `ai_optional` 槽。
禁止用户填写 profile key、工具名、凭据、外部 URL source 或表达式。
模板结构 hash 与 fill_policy_hash 分开计算；排版变化不触发分析或重算摘要。
v2 fill policy 的schema_version=2，增加 `daily_note_instructions:str|null`，只用于 matrix 的新每日叙述，
不生成状态/日期/历史，不为每张票复制一个模板 slot。仍沿单条4KiB/总量32KiB上限，
每次模型输入只含所选目标，不能把它当作执行工具或自动定稿的授权。
最多 128 块、64 slot；document+policy <=256KiB；只要存在未知 data source 即不可使用。

`ReportTemplateRevision`：
`template_id, revision, revision_hash, project_id, name, document, presentation_hash,
fill_policy, fill_policy_hash, readiness:"draft"|"ready", validation_codes[],
created_by, created_at`。
name 1..160 chars。readiness/author/time/hash 服务端生成。
v1 `daily` 必含四个受控数据块各一次；`weekly` 额外恰含一次 timeline。
v2还要求上述恰一个meeting_matrix；prepare同时复验此约束，不能仅信readiness字段。
空模板可保存为 draft，缺 required/data 区不允许用于报告。

### Data Projection Invariants

`data`不是任意renderer占位符；除存在性外还必须验证下列行/字段覆盖。
只允许group/order/声明optional_columns变化，不能按模板条件过滤必需行。

| source | 必须输出 |
| --- | --- |
| key_messages | 全部message ID/text/source_refs；原文与人为override分开，空时明确empty而非伪造摘要 |
| changes | 全部已验证event ID/source identity/kind/before/after/occurred_at或unknown/observed_at；缺比较基线明确initial/unavailable |
| register | 每个完整membership成员恰一行；stable identity/key、title/status/assignee、source/summary引用、全部next_actions、pending_reason、summary age及owner_basis/owner_confirmed语义不能丢 |
| coverage | membership与各part状态、member/accepted/pending counts、source cutoff/timezone、unknown/partial/limitation、baseline及source provenance |
| weekly_timeline | 所有选择日期与对应publication或no_publication、每日期coverage/cutoff与对应成员事件；不造缺失日 |
| meeting_matrix | 选定可见集合中每票恰一行，稳定顺序、逐日source状态前缀、完整有效富文本、weekly seed和未结束AR；缺数据明确pending，不能用notes缺失判断范围外 |

使用现有受校验的 `build_report_model`/source DTO生成这些块，并校验输出identity集合、
完整pending/action数和元数据；即使模板含同名块，输出不满足不变量也必须拒绝。
固定文字/slot可自由编辑，不能冒充或替代系统区的完整性证明。

## 2. Template Library Persistence

复用 `project_management` ORM/repository 事务，不建立模板服务器或新的 Git writer。
新增 ORM 实体位于 `project_management/models_report_templates.py`，
由现有 `models.py` 显式导入以便 Django 发现：

| 实体 | 约束 |
| --- | --- |
| ReportTemplate | UUID PK、Project FK PROTECT、current_revision、archived、created_at；无跨 owner 全局默认 |
| ReportTemplateRevisionRecord | template FK PROTECT、revision、payload_json、payload_hash；unique(template,revision)，只追加 |
| ReportTemplateCommand | Project FK、command UUID、kind、request_hash、result_template/revision/hash；unique(project,command) |
| ReportTemplateUsage | Project OneToOne、retained_payload_bytes、template_count、revision_count；与写入同事务更新，可由不可变记录重算 |
| ReportTemplateUse | Project FK、command UUID、draft UUID、template/revision/hash、完整不可变template快照、request_hash、selected_at；unique(project,command)，无过期删改 |

沿现有 Project transaction/lock 先检查 owner/lifecycle，再精确 command replay，再 current-CAS。
SQLite 锁忙返回 PROJECT_BUSY，不盲重试。保存 revision/command/head/usage/audit 同事务。
上限建议：100 templates/project，100 revisions/template，模板 revision+command+use payload 共50MiB/project；
归档模板仍计数，大小按 canonical payload 计，不是磁盘余量检测。DB 存在额外物理开销，
不能把这个计数说成精确 DB 文件占用；正式部署数据库备份与额度单列。
使用 `ProjectAuditEvent` 的模板事件；无历史硬删除 API。
这些限额需在配置与测试同版本冻结，不删除旧修订来达标。

```text
ReportTemplateService.list(actor, project_id, *, limit=20, offset=0)
    -> {items:TemplateSummary[], next_offset:int|null}
ReportTemplateService.create(actor, project_id, *, command_id, name, document, fill_policy)
    -> ReportTemplateRevision
ReportTemplateService.save(actor, project_id, template_id, *, command_id,
                          expected_revision, name, document, fill_policy)
    -> ReportTemplateRevision
ReportTemplateService.get(actor, project_id, template_id, *, revision)
    -> ReportTemplateRevision
ReportTemplateService.copy(actor, source_project_id, template_id, *, revision,
                          target_project_id, command_id, name) -> ReportTemplateRevision
ReportTemplateService.archive(actor, project_id, template_id, *, command_id,
                             expected_revision) -> TemplateSummary
ReportTemplateService.use(actor, project_id, *, command_id, draft_id, request_hash,
                         selection:UserTemplateSelection,
                         use_mode:"standalone"|"continuity_prepare")
    -> PinnedTemplateUse
```

copy 先验证两项目 owner；复制结构/固定模板文字与填写说明，不读取报告、source 或 AI result。
显式再分配 block/slot ID，并重映射 policy；旧模板不受影响。
同名允许，界面显示模板 ID/版本避免错误去重。
归档不隐藏已被草稿引用的版本，服务端只阻止新选择。

### Pinned User Template Rendering

TEMPLATES开工的明确接线：保留已有builtin `AuthoringTemplateSelection`构造，
新增公开`UserTemplateSelection(template_id,revision,revision_hash,origin="user")`；
两种请求按origin分派，不能把user选项塞入builtin options伪装registry key。
`PinnedTemplateUse={command_id,draft_id,request_hash,template_snapshot,template_definition}`。
use的request_hash绑定整个create请求（selection/template/preparation），不只模板ID。
同command只返回原冻结use；新command严格校验精确revision/hash、ready、owner/未归档，
不强制等于库latest revision，避免旧的明确选择被静默换成新版。

user模板presentation_hash为
`SHA256(canonical_bytes({renderer_version:"template-document/1",document:resolved_document}))`。
填充规则仍独立hash。既有builtin package hash算法不改。
为保留旧DTO消费者，user草稿的`template`仅作兼容展示投影：
`TemplateSelection(template_id,version=str(revision),options={})`；
`TemplateDefinition`同identity/version/options，template_hash=presentation_hash，
renderer_version=`template-document/1`。这些投影必须与pinned snapshot一致，
但绝不作为Django registry查找参数。

```text
ReportRenderer.render_pinned(snapshot, template_snapshot, authored_edits, *,
    authoring_context, draft_id, revision, revision_hash, edition_state)
    -> RenderedReport
```

该入口只按白名单renderer_version和文档schema编译受控content/slot/data块，
不执行用户Django/Jinja/Python/CSS。schema2 user的render/finalize均走此入口；
save/get只读本revision快照，不访问template库head，不重新创建use。
schema1和builtin继续原package-bound registry，不能为user模板放松其校验。
published template.json仍是相同完整snapshot，history/packet reader复算同一hash，
未知renderer返回`REPORT_DOCUMENT_UNSUPPORTED`。UI从pinned文档呈现slot/块顺序，
不能仍硬编码旧两种模板布局后声称用户模板生效。

### Standalone Before Continuity

TEMPLATES叶先交付合法的独立人工填写链，不制造HISTORY/DAILY context：
`use_mode=standalone`只允许ready document schema1且无meeting_matrix，
文字片段可用受支持fragment v1或v2；用户选择时明确“Independent report”，
不能标作daily series baseline。原四项必需data块/weekly timeline规则仍校验。
用户可以保存符合v2规则的matrix模板并达到结构ready，但此阶段不能创建matrix报告。
v2无矩阵不可ready，有矩阵却没有服务端prepared context仍返回
`REPORT_CONTEXT_REQUIRED`，不在use或draft留下虚假连续性记录。
`use_mode=continuity_prepare`由HISTORY/DAILY提供已核验preparation/context后接入；
调用者自报context不接受。系列创建/默认模板选择仍拒绝schema1独立模板。
TEMPLATES的null context不推进daily基线，不开放continuity_changes。

## 3. Draft Schema2 And Compatibility

保留现有 `ReportDraftService`、`ReportDraftStore`、六文件 publication 目录及锁顺序。
新增 `save_authored` 和 `create_authored`，不将 HTML 塞进旧的 `ReportEdit.text`：

```text
ReportDraftService.create_authored(actor, project_id, stage_id, *,
    command_id, selection:ReportSelection, template:AuthoringTemplateSelection,
    preparation_id:UUID|null) -> AuthoredDraft
ReportDraftService.save_authored(actor, project_id, stage_id, draft_id, *,
    command_id, expected_revision, expected_revision_hash,
    edits:AuthoredEditRequest[], continuity_changes:ContinuityChange[]) -> AuthoredDraft
```

`AuthoringTemplateSelection` 为 tagged union：
`{origin:"builtin",template_id,version,options}` 或
`{origin:"user",template_id,revision,revision_hash}`。
同一 project 的 ready user revision 才能被新选择；服务在取得 owner 后解析，复制完整不可变定义，
按下面的 `ReportTemplateUse` 线性化规则冻结选择，然后释放 DB 事务再进入 stage 锁，
禁止 stage lock -> DB template write 的反向锁关系。

模板选择与归档的线性化点固定为DB事务创建 `ReportTemplateUse`：
create_authored先取得合法source（无写锁），再在Project锁/owner检查下校验template ready且未归档，
写入use记录并计入usage。这一事务成功即冻结本次选择；之后template archive不撤销已存在的use，
只阻止新command创建use。释放DB事务后进入stage锁，检查Project/lifecycle/source并写draft；
这里不再回DB复查template archived。不同command不能复用use；同command只重放同request_hash，
未形成draft的use也保留供同command恢复，不能改为新模板。Project归档仍阻止新的stage写入。
避免“持stage锁再查/写template DB”的反向锁，不用跨DB与文件系统分布式事务。
template删除禁止；use快照即使库头变更仍可继续原事务。

schema2 revision 保留 schema1 的 draft/source/time/parent 基本字段，增加：
`authoring_schema="report-authoring/2"`、
`template_snapshot={selection,resolved_document,presentation_hash,fill_policy,fill_policy_hash,
renderer_version}`、
`edits:AuthoredEdit[]`、`authoring_context:DailyAuthoringContext|null`。
只有使用旧v1模板、无 meeting_matrix 的standalone过渡文档可以用 null；
不得成为系列的daily baseline。v2日/周草稿缺context必须拒绝，不能退回独立文档绕过。
有矩阵的草稿从已核验 preparation_id 取得服务端准备的 context，HTTP 不接受原样自报历史。
continuity 的 effective context 与编辑历史均进入本 revision hash。
`AuthoredEditRequest={edit_id,kind:"note"|"narrative_override"|"slot_fill",
target,fragment,expected_original_hash,reference_receipts[],assist_receipt_id:null|UUID}`。
target 复用旧 report/issue/action/message 规则；新增 `{scope:"template_slot",slot_id}`；
slot 必须来自 pinned template_snapshot。
另加 `{scope:"daily_note",note_id}`、`{scope:"report_action",action_id}`、
`{scope:"persistent_note",note_id}`，只能指向本草稿已授权、非历史只读的叙述目标。
`ContinuityChange` 为受控 tagged union：
`move_row(issue_ref,group_id,after_issue_ref|null)`、
`set_action_tracking(action_id,expected_state,state,resolution,evidence_refs[])`、
`add_persistent_note(note_id,target,issue_ref|null,fragment,carry_forward)`、
`set_persistent_carry(note_id,carry_forward)`；字段名中的括号只是类型速记。
每次 <=100 个操作；目标归属/版本/来源复验，与 edits 同一原子 save，
不能通过这些操作改 source_status、meeting、weekly seed 或已定稿片段。
删除常驻文字使用显式空 fragment 修订，停止携带须显式 carry_forward=false；
源 next_actions 不能通过省略某项或清空叙述而被解除。
所有原始事实/日期/状态/coverage/人数目标仍拒绝。值被清空也必须保存到新 revision，
对 required slot 只影响 readiness，不默默删除其历史。

连续性操作的传输对象使用`kind`判别，以下字段均必填，未知字段拒绝：

| kind | Fields |
| --- | --- |
| `move_row` | `issue_ref, group_id:UUID|null, after_issue_ref:IssueRef|null` |
| `set_action_tracking` | `action_id, expected_state, state, resolution:RichTextFragment, evidence_refs:str[]` |
| `add_persistent_note` | `note_id, target:"report"|"issue", issue_ref:IssueRef|null, fragment, carry_forward:bool` |
| `set_persistent_carry` | `note_id, carry_forward:bool` |

resolution须有非空正文；done/canceled须有至少一条属于该工单已保存evidence的引用。
服务端把resolution保存为`{fragment,evidence_refs,resolved_by,resolved_at}`，不接收客户端作者/
时间。这里只改变报告行动跟踪，不回写来源。add_persistent_note只接受本context未占用的
规范UUID；report目标issue_ref=null，issue目标必须与当前获准行精确匹配。
carry flag只影响后续日期/周期，不删除当前或旧归档正文。
move_row的after_issue_ref须为同组有效行或null（组首），重排后每行身份唯一；
未分组时group_id必须null，分组时使用pinned模板定义，不靠改变排序越过scope。

日报完整保存同时支持原note/narrative/slot和新连续性目标；按目标分派校验后在一个
revision中持久化，不因为有authoring_context就禁用slot_fill或绕过reference verifier。
已保存active edit原样提交时先识别同edit_id/target/content，不能拿最初original_hash与
已修改正文再次比较而拒绝普通重复保存。新修改仍校验最新版本，历史目标不可写。
经过补全的当前日note继续校验本draft收据；继承的历史链接沿已核验publication保持原值，
不重新网络查询或续签。来源身份/颜色/人工接受信息不能因分派丢失。

`AuthoredEdit` 由服务端移除传输 receipts，追加
`author,edited_at,origin:"human"|"ai_assisted",source_ai_result_ref:null|object,
reference_observations:ReferenceObservation[]`。
旧 schema1 overlay 转为单个 paragraph 的 literal text，仅在首次显式保存 schema2 时写新修订。
读旧修订不写文件、不转换 hash；混合历史读取按每条 schema 分派。
内置version1模板的资源/hash必须保留；作者层使用独立version2后继时，
create要求明确选择该版本，首次schema1 save_authored可在同一新修订中固定已知后继定义。
旧修订仍引用原version1。legacy save不允许把schema2降回纯文本；旧command重放仍读原修订。
旧 schema1 `save` 保留旧行为；页面新表单以 `payload_version=2` 调用新方法。
旧 run 默认仍产生 schema1 草稿，编辑入口可读；逐步切换 run/create 需明确 consumer 测试，
不能一次全库替换 `TemplateSelection` 或重新提交旧运行。

schema2 保存延续：验证请求形状 -> owner -> 查 command replay -> CAS ->
验证完整 active edits/模板目标/收据 -> 赋作者时间 -> admission ->
immutable command+revision -> current head。不联网、不调用模型。
跨 schema 重放原请求用原 request hash/serializer，不能重算为新格式伪装相同命令。
render 检查 pinned template，不从库的 current_revision 替换；
renderer/serializer 不支持时明确 `REPORT_DOCUMENT_UNSUPPORTED`，旧最终文件仍可直接下载。

### Reference Receipts

lookup 成功发出 Django signing 签名的 observation envelope，绑定
actor/project/stage/draft/target/snapshot/rule/principal identity、membership proof_hash、原始 key/stable ID、
选中变体的 fragment hash、observed_at、transport expiry（5分钟）。
服务端使用现有签名设施，不新增浏览器密钥。它是读取回执，不授予新的 source 访问权。
选择时未过期；Save 验证签名/归属/当前本地 scope 和 fragment 中引用关联，
然后把验证后的 observation 保存为 immutable revision 内容。历史不再依赖签名 key 的有效期。
超期未保存返回 `REFERENCE_RECEIPT_EXPIRED`，保留编辑器内容；用户可重新输入 `#ID` 获取新回执，
或明确解除引用元数据，保留为标注人工的普通文字/链接。这个动作不是另一种补全触发。
编辑 title/owner 后与原 candidate 不同，记录为 human modified，不再把修改内容标为 provider 原值。

#### Reference Association Algorithm

REFERENCES开工前的精确规则：receipt不是整段文字的签名，也不授予新读取权限。
每个可用option由服务端分配不同`reference_id:UUID`，写入该option唯一link及签名envelope。
envelope包含`schema_version=1,reference_id,option_id,variant_fragment_hash,
actor_subject,project_id,stage_id,draft_id,target_hash,snapshot_hash,rule_hash,
principal_id,membership_proof_hash,observation,issued_at,expires_at`，未知字段拒绝。
target_hash为规范target对象hash；variant_fragment_hash为签发时完整option fragment hash。
签名使用固定salt `project-reporting.reference/1`，expiry固定签发后300秒，不因失败重试续期。
同一建议三个option的observation相同；reference_id/variant/hash可以不同。

Save对提交fragment的所有link遍历，不搜索周边title/owner字串：

1. 每个带reference_id的link在本次完整edit列表中必须唯一；重复、伪UUID拒绝。
2. 新ID必须有有效未过期envelope并绑定当前actor/project/stage/draft/target及本地source/proof。
   已保存ID只可从立即当前revision的同一target观察记录恢复，不依赖过期transport签名。
   从另一target/draft或更老且已删除的revision带回ID需要重新有效receipt，不能跨目标冒用。
3. link的href必须与observation.canonical_url精确一致，所有text runs拼接后必须等于
   observation.current_key。marks/paint可改变；位置及周边文字可改变。
   key/href改变仍带ID则返回`REFERENCE_CONTENT_CHANGED`，不自动丢弃元数据后声称成功。
4. title/owner是用户可编辑普通文字，不用variant_fragment_hash比较整段已编辑fragment；
   该hash仅证明签发的候选。保存观察记录为
   `{reference_id,option_id,issued_fragment_hash,content_basis:"human_composed",observation}`。
   观察内provider title/owner保持当时原值；整个当前可见编辑内容仍按人工编排，
   不能把修改后的title/owner重新标作provider事实。渲染引用详情可显示原观察和时间。
5. receipt对应ID在提交fragment中已不存在时不生成观察、不恢复link；
   schema2新修订只保留仍存在的关联，旧修订不改。无receipt的未知ID返回`REFERENCE_INVALID`。
6. 显式“保留为人工链接”仅移除reference_id/待提交receipt，不改可见文字或href；
   普通HTTPS校验仍有效。这个动作不联网、不是新补全触发。

receipt验签在服务adapter执行，纯domain只接收经验证观察；持久层独立复验观察形状、
link关联/URL/identity及当前target。新签名receipt校验或历史观察读取均不发provider请求。
额度沿fragment/revision上限；每edit最多64条关联，完整revision最多512条，拒绝不截断。
RA20增加：大段落内插入后改色/周边/title可保存；改href/key保留ID拒绝；
删除link但旧receipt仍在不会复活；复制ID到另一target/重复ID/无签名ID拒绝。

#### Server-Verified Historical Associations

上述跨draft拒绝规则保留用于客户端复制；连续性/重建服务的显式已验证继承是唯一例外。
新的ReferenceObservationRecord schema2包含原五个record字段，加
`schema_version:2,historical_association`。关联为server-created对象：

- `kind="parent_draft_revision"`：`schema_version:1,parent_draft_id,
  parent_draft_revision,parent_draft_revision_hash,target_hash,reference_id,record_hash`。
- `kind="source_publication"`：`schema_version:1,publication_id,manifest_hash,commit,
  target_hash,reference_id,record_hash`。

record_hash绑定原已保存观察记录的规范内容。服务按精确parent revision或已验证六文件
publication取得对应target/reference record，核对hash、target、reference_id及link
href/key。继承对象只来自当前draft绑定的父稿/正式baseline，不接受任意客户端引用。
schema2历史记录的再次继承必须保留可验证的原关联或有界验证链，不能无限包装或跨目标借用。
当实际继承源已是确认publication时，服务先核验原历史记录，再从该publication中的
已验证原record重绑定source_publication关联；不把运行时父draft作为永久历史依赖。
linked correction与普通next-day继承使用相同出版物关联校验，不能只在每日准备分支生效。
普通新增lookup仍要求当前membership和未过期签名；历史继承不重新签发、不更新
observed_at、不把原scope_snapshot_hash换成当前proof，不调用provider。
因此修改已继承常驻note的相邻文字、颜色或highlights可保存，改key/href仍明确冲突。
解除reference_id仍须用户显式转换为普通人工链接，不静默丢失原验证信息。

### Publication

`PublicationManifestV2`精确keys为旧manifest的
`schema_version=2,publication_id,draft_id,draft_revision,draft_revision_hash,purpose,
parent_publication_id,baseline_publication_id,source_as_of,finalized_at,finalized_by,
snapshot_hash,template_hash,file_hashes`，外加
`authoring_schema="report-authoring/2",template_snapshot_hash,template_document_hash,
fill_policy_hash,edits_hash,series_id,report_role,meeting_key,period_key,continuity_hash`，
无可选额外字段。没有 context 的独立文档取 series_id/meeting_key/period_key/continuity_hash=null、
report_role="standalone"；其他值由已验证 context 派生，不接受 caller 覆盖。
`file_hashes`精确包含snapshot.json/template.json/edits.json/report.html/report.txt五项。
`template_hash`=presentation_hash；template_document_hash=canonical resolved_document hash；
template_snapshot_hash=原template.json字节hash；fill_policy_hash=canonical fill_policy hash；
edits_hash=原edits.json字节hash。file_hashes不得包含manifest自身。

`FinalizationIntentV2`精确keys为当前schema1 intent的
`schema_version=2,command_id,request_hash,publication_id,draft_id,draft_revision,
draft_revision_hash,purpose,finalized_at,finalized_by,snapshot_hash,template_hash,file_hashes,file_sizes`，
再加`authoring_schema,template_snapshot_hash,template_document_hash,fill_policy_hash,edits_hash,
series_id,report_role,meeting_key,period_key,continuity_hash`。
intent中的file_hashes/file_sizes必须精确覆盖六项（含manifest.json），size为非负int且不是bool。
request_hash沿当前公式canonical
`{command_id,draft_id,expected_revision,revision_hash,purpose}`，revision_hash已绑定完整v2 payload；
schema1公式/解析不得改写。publication_id沿原UUID5(draft_id,revision:purpose)。

`template.json`为完整template_snapshot，`edits.json`为
`{schema_version:2,draft_id,selected_revision,selected_revision_hash,revisions,authoring_context}`，
revisions保持各原schema的完整canonical payload及其hash；
每条引用/AI provenance包含在对应overlay中。其他仍为snapshot.json/report.html/report.txt。
authoring_context 与选中 revision 的值相同；continuity_hash=canonical context hash，
含有效用户片段、颜色/链接、原状态、历史引用、行序和未结束 AR。
每个已继承 fragment 必须通过其来源 publication/ref/hash 校验，不能信任自报 hash。
不改变已存在 schema1 payload/intent。校验器按 schema 识别六文件内容，
不允许额外文件或用户控制路径。引用数据只是报告注释，不修改原 source snapshot hash/cutoff。
finalize 额外验证 required slot 有非占位值、无待接受 AI 状态、所有片段可渲染；
仍使用现有 revision/source/baseline/owner 检查和预存字节恢复。
daily 定稿还需在同一 stage writer 边界做 series baseline-CAS；
weekly_view/standalone 不推进 daily head；commit 才是正式基线提交点，runtime指针可重建。
render、copy、保存/定稿不查询最新工单；observed_at 如晚于 source cutoff，输出注明该注释观察时间。

resume按intent.schema_version分派，再按manifest.schema_version精确分派且必须相等；
逐文件校验原字节hash/size，manifest-intent同名字段必须全等，五文件hash与六文件hash对应；
template/document/fill_policy/edits的派生hash重新从retained内容验证，不从当前库读取。
校验snapshot与repository的project/stage/owner、draft revision/hash及原selected template一致。
然后只把原六文件送原append_record；已commit读原receipt，未commit仍执行既有本地source/权限
漂移校验而不重渲染或查询provider。missing/corrupt/mixed schema返回REPORT_ARTIFACT_INVALID。
必须修改的消费者包括`app/domain/report_publication_contracts.py`、
`storage/report_publication_packets.py`、`services/report_publication_reads.py`、
现有report namespace validator及list/download投影，不能只改writer。

## 4. AI Assist Contract

```text
ReportAssistService.submit(actor, project_id, stage_id, draft_id, *,
    command_id, expected_revision, expected_revision_hash, target_ids, instruction)
    -> AssistStatus
ReportAssistService.observe(actor, project_id, stage_id, draft_id, assist_id)
    -> AssistStatus
ReportAssistService.cancel(actor, project_id, stage_id, draft_id, assist_id, *,
    command_id) -> AssistStatus
ReportAssistService.candidate(actor, project_id, stage_id, draft_id, assist_id)
    -> AssistCandidate
```

observe 可以查询既有运行时 run，不得在 GET 上隐式新建/重派模型任务。首次 dispatch 只来自 submit。
新状态：`prepared, observing, candidate_ready, insufficient_evidence,
failed, cancel_requested, canceled, unknown`。
无 run id 的未知 submit 用原 `client_run_key` 查询，不换 key 重试；返回不确定费用保留原状态。
原 profile `id@version`/request/输入哈希先持久化，候选必须核验运行记录身份、profile版本、principal与原结果 hash。
服务经MDB-2同步task-run端口提交（决策10），不复用 summary profile。
`metrics.report_authoring` 的 instructions/schema 以数据固定在 `project_management/ai_profiles/`（取代 `ai_bundle/`）；
profile未声明/禁用、模型未配置或运行时不可用时返回 `REPORT_AI_UNAVAILABLE`，人工编辑不受影响。
2026-11-06实际接口、存储文件、终态/未知结果分类与对应验证入口已细化在
[ASSIST执行合同](assist-execution.md)。该文档补充本节，不建立第二份任务状态。

assist 记录放同一 stage runtime 的 `report-assists/<assist_id>/`，
复用 `storage.paths`、归属/配额/锁，不建立新进程控制器或修改采集/摘要 journal。
同 command 同 payload 得到原 assist；结果与 observation append-only，网络在锁外。
input 包含 pinned snapshot/template hash、允许 target 内容和 evidence allowlist；
output schema 为 `{schema_version:1,targets:[{target_id,status:"filled"|"insufficient_evidence",
fragment:RichTextFragment|null,evidence_refs:str[],reason_code:str|null}]}`。
这里 status 是填写结果，不是工单状态。新 authoring profile 明确输出 fragment v2，
禁止将 source_status、历史 note、行序、AR tracking_state 或颜色保留策略列为 AI 可写目标。
AI 输入可包含上一条用户确认的有效叙述和必要源增量作为有 provenance 的上下文，
但不得直接把用户推测当成源证据或改 accepted summary。
模型不可注入任意 target、href、reference receipt、author/time、权限或 data 块。
候选与源 schema/引文验证失败返回错误，不降级成人工编辑接受。

Apply 只把核验过的候选放到本地 dirty fragment，保留 assist ID；
Save 再核验目标/base revision/hash 与候选来源，写 human acceptance author/time。
即使候选文本与原文相同，未接受的receipt也使编辑器dirty。Save确认后清理客户端临时receipt，
并返回当前日报note的`current_note_hashes`，保留保存期间新增的本地文字及下一次CAS依据。
接受后的文本可继续人工修改并记录差异；从不等同于 SummaryAnalysisService.accept。
一 draft 同时一个活跃 assist。初始 input128KiB/output64KiB/总期限180秒/观察最多16次，
服从更严格的运行时准入限制；不能扩大既有全局预算或清零失败费用。
长轮询按已有 deadline 停止；浏览器关闭不自动撤销运行，重开读取原 assist。

## 5. HTTP Surface

来源选择使用`CaptureArchiveService.list_capture_metadata`的只读分页投影：
`CaptureMetadata{receipt:CaptureReceipt,source_as_of:str}`及`CaptureMetadataPage`。
与原`list_captures`共用同一已验证manifest/游标选择，不重复读取各票正文，
不修改原回执、capture文件或schema。界面显示UTC截止时间及ID，ID始终按完整值提交。

所有 POST 用原 project_actor、owner、CSRF；GET private/no-store。
页面 form 响应保持现有 redirects；ASSIST使用
`{schema_version:1,result:null|object,error:null|{code,message}}`，
以command/assist身份关联原请求；completion与已有Save保留各自已版本化响应。
不返回异常栈/凭据/路径，details 只含已授权 resource ID、字段/目标 ID、retry_after_ms。
未知 request key 拒绝；actor/profile/endpoint/原始 scope 不能由浏览器覆盖。

| Route（相对已有 project 路径） | 行为 |
| --- | --- |
| GET/POST `report-templates/` | 列表/创建；不是 trigger endpoint |
| GET `report-templates/<id>/?revision=N` | 版本读取/编辑界面 |
| POST `report-templates/<id>/save/`、`copy/`、`archive/` | command+CAS，成功返回版本身份 |
| POST `stages/<sid>/reports/drafts/` | payload_version2 选择模板并创建；旧 form version1 保持 |
| POST `stages/<sid>/reports/drafts/<did>/save/` | payload_version2 内容保存；原 URL 不另建竞争存储 |
| POST `stages/<sid>/reports/drafts/<did>/completions/` | 仅 `#ID` token 对应的一次 suggestion query |
| POST `stages/<sid>/reports/drafts/<did>/assists/` | 显式 AI 请求，202或幂等原状态 |
| GET `stages/<sid>/reports/drafts/<did>/assists/` | 当前目标与原assist状态；不派发、取消或刷新工单 |
| GET `stages/<sid>/reports/drafts/<did>/export/?revision=N&format=markdown` | 已保存修订的派生下载，也支持format=xlsx；非新的保存/定稿 |
| GET `stages/<sid>/reports/publications/<pid>/export/?format=markdown` | 也支持format=xlsx；验证原六文件并转换原HTML，不重渲染、不改写publication |
| GET `.../assists/<aid>/`、`candidate/` | 观察原 run/读取候选，不派发新 run |
| POST `.../assists/<aid>/cancel/` | 原运行取消，不意味立即终止 |
| GET/POST `stages/<sid>/reports/series/` | 查询/显式创建系列，服务端UUID、日历/模板校验；不采集 |
| GET `stages/<sid>/reports/series/<series_id>/?revision=N` | 查询授权系列的明确策略修订 |
| POST `stages/<sid>/reports/series/<series_id>/policy/` | command+expected revision/hash保存新策略；不改旧draft或自动生成 |
| GET `stages/<sid>/reports/baseline-preview/` | 只读已确认日报/缺口、模板/日历选择；不抓来源 |
| POST `stages/<sid>/reports/preparations/` | 显式准备今日草稿，原 run worker；同日去重，不定稿 |
| GET `stages/<sid>/reports/preparations/<id>/` | 只读原准备及当前draft/operation修订、有效选择和替换关系；不修复/派发/重新准备 |
| POST `stages/<sid>/reports/preparations/<id>/reprepare/` | 显式重建终态准备，精确revision/CAS，保留用户内容；scheduler不调用 |
| GET `stages/<sid>/reports/periods/<period_key>/` | 已授权周视图；缺日报明确缺失，不隐式生成 |

render/clipboard/finalize/resume/publication/download 沿原 URL，版本化处理新增内容。
400输入、401未登录、403CSRF、404其他 owner/不存在、
409版本/状态/来源冲突、413额度/大小、422结构/模板不就绪、
429限流、502非法上游、503不可用、504查询超时。
调用者重试 save/finalize 使用原 command；触发补全的新 token 请求用新 request_id，
不能将 query 重试机制套到有副作用操作上。

派生导出的DTO、版本/来源hash、格式限制及独立错误映射以
[export-execution.md](export-execution.md)为具体合同。原HTML/plain下载入口和六文件
不变；新的派生字节不能冒充旧publication的原文件，不能回写格式权威。

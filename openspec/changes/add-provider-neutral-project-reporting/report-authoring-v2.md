# Report Authoring V2

日期：2026-11-03。状态：用户已批准直接在main实施，当前实施中；真实调用未启用。
父设计：[design](design.md)。唯一执行状态：[tasks](tasks.md#w6-authoring-v2)。
接口：[contracts](report-authoring-contracts.md)；交互与拒绝：[completion](report-completion.md)；
验收：[validation](report-authoring-validation.md)。这些是同一 OpenSpec 的附录，不是新产品或第二套计划。
每日/跨周基线、富文本继承、排序和触发：[continuity](report-continuity.md)。

## 1. Current Reality And Requirement Delta

| 对象 | 本次实际读取 | 当前行为 / 新需求差距 |
| --- | --- | --- |
| 模板注册 | `project_management/reporting/templates.py` | 仅 `daily-standup/1`、`weekly-timeline/1`；从代码包读取 Django HTML |
| 模板选项 | 同文件 `normalize_options` | 分组、key 排序、四段顺序、可选列；不等于用户创建模板 |
| 模板防替换 | `reporting/html.py::_verified_registry`、`tests/test_report_templates.py` | 当前拒绝替换注册模板，即使调用者重算了 hash |
| 编辑契约 | `app/domain/report_presentation.py`、`report_edits.py` | `ReportEdit.text` 是 literal text，只允许指定叙述目标，不是 Markdown/HTML |
| 保存与定稿 | `services/report_drafts.py`、`storage/report_drafts.py`、`services/report_publication.py` | 已有 revision-CAS、命令重放、精确字节 Git 定稿；必须复用 |
| 页面 | `ui_web/templates/projects/reports/editor.html`、`report_forms.py` | 文本框与 iframe 是过渡界面，不满足 WYSIWYG |
| 原计划 | `html-report-authoring.md` 第 1、3、6 节 | 用户设计器原为 backlog；富文本原交给另一个 Agent；没有 `#ID` 补全 |
| 来源绑定 | `project_management/out/dashboard_scope_catalog.py` | Jira 使用明确 scope/profile；HSDES 使用 saved-query profile，禁止伪造 Jira scope |
| AI | `out/ai_task_contract.py` | 固定 a2 synthetic-only、summary@review-1；不能直接拿来执行任意报告填写 |

Dashboard HEAD 为 `12f7ac285d1bba7f125b947a11a3deaa2fd5d330`，但本表主要来源是该检出中
尚未提交的 `project_management` 实现和当前计划，不是仅靠 HEAD 推断。
工作过程中另一方正常提交将HEAD推进到
`5d83933dc3d3c4f1673ec680c5ee2d03da8f9aed`（2026-11-03，manual HTML reporting workflow）。
这里的代码判断仍来自已读实际文件；不回退该提交、不把他方提交当成本轮代理执行的Git操作。
代码图谱 generation `2026-11-02T01:12:27Z` 未覆盖这些新增文件，已定点读源码；
没有重建索引、读取真实工单、执行产品测试或重启已结束的工作流。

### Confirmed Requirements

- 只有所见即所得编辑，不提供 Markdown 源码模式、模式切换或源码补全。
- 工单补全只有 `#` 加 ID 输入触发；不保留裸 ID、URL、快捷键或按钮触发。
- 三种格式：链接 ID；链接 ID + title；链接 ID + title + `@assignee`。
- 上下箭头选择、Enter 原子应用并关闭；可撤销；取消不修改正文。
- Jira/HSDES 由报告的 Stage 来源区分，不要求用户额外输入系统类型。
- 用户可创建、复制、修改模板；报告可由人工填写，或显式请求 AI 给出填写/修改候选。
- 不再以另一位编辑器 Agent 的交付作为组织前置条件；一个协调者可以统一交付。
- HTML 为主要邮件/报告产物；已有 Markdown/Excel 输出义务不因取消源码 UI 而被删除。
- 一张 ticket 一行，AR/AR? 各自记录；状态位于 `ww45.1(Fixed):` 括号内且只取来源字段。
- 同周逐日累积，稳定票据位置；用户增删文字、颜色、高亮和补全链接与 AI 初稿合成后继承。
- 模板排版与模型写作指令分离；历史复用、格式化、补全、保存和导出不调用模型。

新周 seed/未结束行动、手动生成今日草稿/可选定时和正式 baseline 提交点，
在 continuity 中按明确默认值补齐。它们是待实施的详细设计，不是已上线能力。

上述替代早期“多触发、双模式、用户设计器不在首批报告工作、必须另请 Agent”的范围。
未取消原始证据、完整在途清单、待办/coverage、来源截止时间和显式定稿保证。
此前只授权规格/文档的窗口已经结束。2026-11-03用户明确批准本作者层实施，
直接在Dashboard main执行；这不恢复旧Chiplet T12，也不自动授权真实provider/model或正式调度。

## 2. Layering Decision

**模板是业务层的版本化文档结构，不是第三方编辑器私有 JSON，也不是可执行的 Django/Jinja 代码。**
用户在可视化模板页面创建结构，在报告页面填写内容，无须接触 Markdown 源码。

| 层 | 权威与边界 |
| --- | --- |
| Template Library | 项目内模板 ID、不可变版本、结构、填写槽及受控数据块 |
| Report Application | Stage/snapshot、可编辑目标、草稿修订、AI 建议接受、定稿 |
| Report Continuity / Preparation | 同系列/日历/周周期、来源/分析/编辑三类基线、稳定行序、同日去重、跨周seed |
| Shared Editor Adapter | Milkdown 组件的加载、选区、片段转换、菜单、撤销、销毁 |
| Provider Adapter | 已授权单票读取、站点与字段映射、权限/新鲜度；不调用模型 |
| AI Base | 通用 task-run 执行、原结果与取消状态；不理解 Jira、模板布局或报告定稿 |
| Renderer / Archive | 确定性 HTML/plain/Markdown/Excel 投影；原 stage Git writer 保存精确最终字节 |

原候选Vditor 4.0.1在公开html2md/setValue/getHTML往返探针中丢失文字前景和高亮，
不能成为本应用的格式权威。依原备选路径，固定采用`@milkdown/kit@7.23.0`，
仅WYSIWYG；使用公开`$markSchema`和ProseMirror document/transaction API，
由应用fragment与结构化document直接映射，不经有损Markdown恢复颜色。
本地Chrome156.0.8078.74、禁网络探针已通过paint、带格式link、undo、输入和destroy/remount
JSON语义往返。证据位于`.tmp/authoring-main-20261103/milkdown-qualification.json`及同名PNG；
这只关闭组件能力问题，不替代EDIT的实际页面/保存/重开/粘贴/`#`边界资格。
依赖以lockfile固定，静态bundle/许可证/manifest随应用本地交付，不运行CDN或组件遥测。
Milkdown的AI扩展不跳过本应用保存/预算/审批协议。
不把采用编辑器变成全站 React/Vue 迁移，不引入第二套页面路由。

共享前端契约刻意不包含 Jira/HSDES 字段。第一消费者可以先放在
`ui_web/static/js/report_editor/`，本地 ES module 发布，不强制所有 SDK 用户下载编辑器。
第二个真实消费者需要时，按固定包版本抽取公共组件；不复制两份核心。
本 OpenSpec 不代写 AI Base 仓内执行任务；已有 task-run/1 之外的新公共能力按原跨仓流程冻结。

## 3. Template UX And Content Model

入口为 Projects -> 选中项目 -> **Report templates**。支持空白创建、从内置模板复制、
保存新版本、重命名、归档及预览；无硬删除、任意 HTML/CSS/脚本上传或模板执行器。
模板归档只停止新选择，已绑定草稿和定稿仍保留自己的模板快照。
项目归档后禁止模板写入，历史读取仍按 owner 检查。

模板包含有序块：

| 块 | 用户可做什么 | 运行时行为 |
| --- | --- | --- |
| `content` | 标题、段落、列表、普通表格、固定说明及链接 | 作为模板作者文字输出，不冒充工单事实 |
| `slot` | 定义稳定 slot ID、显示标题、必填与否、初始内容和可选 AI 填写说明 | 人工编辑或显式 AI 建议；每个 draft 保存自己的值 |
| `data` | 从受控目录选择数据区及允许的展示选项，移动位置 | 服务端从同一验证 snapshot 确定性投影，不运行用户表达式 |

初始 `data` 目录：`key_messages`、`changes`、`register`、`coverage`、`weekly_timeline`，
document v2 增加 `meeting_matrix`，其逐票/稳定排序/累积规则见 contracts/continuity。
v1 standup 模板必须恰好包含前四项；weekly 在此基础上包含 timeline。
用于新连续性流程的v2 daily/weekly还必须恰好包含一个meeting_matrix，
缺少时不可ready，也不可用standalone回退绕过系列准备。
没有标题或只有空 slot 的草稿模板可以保存为未就绪版本，但不能用于生成报告。
不能隐藏 pending、未完成行动、真实截止时间/coverage；模板“自由”不授予修改事实的能力。
主矩阵每条新增 note 只写短状态与必要 AR，完整 register/changes/evidence 可放附录；
这只是分层展示，不允许把 Fixed/Done 从采集成员集合移走。
操作员可以自由新增说明区和填写区、调整顺序、展示列与分组；复杂版式和可执行循环不是首批能力。

创建模板不绑定具体工单、principal、日期或已接受摘要。预览用固定合成数据；
进入某个 Stage 的报告创建流程后，才以用户选择的已保存 source snapshot 填充。
从报告“另存为模板”首批不提供，以免把真实正文/工单引用意外复制到通用模板。
跨项目复用首批通过显式结构复制，重发模板/slot ID，不带报告填写值或来源收据。

### Markdown Position

纯 Markdown 能表达很多文字格式，但不能可靠表达稳定 slot ID、只读业务块、
必填/待填状态、版本与 AI 说明的独立身份。因此：

- 模板结构、填写槽和来源收据用应用拥有的 schema。
- 文字片段用中立富文本 AST；编辑器可用 Markdown 作为内部导入/导出桥梁，但不是唯一权威。
- fragment v2 明确定义文字前景/高亮和链接内格式；Markdown 不承担这些值的恢复，
  不能让有损桥梁成为编辑器保存的必经路径。
- Markdown 是支持子集的派生输出，HTML 仍是主要邮件产物；不要求用户编写 Markdown。
- schema1 旧 `ReportEdit.text` 永远按文字解释，不能在升级后突然解释 `**`、链接或 HTML。
- 格式转换要校验语义，不许靠静默删节点或清洗正文制造“保存成功”。

此前研究中的“保存 Markdown 即可”不足以覆盖当前结构化 overlay 与模板契约，
在本方案中明确由版本化业务文档补足，不直接改写旧格式。

## 4. Draft And Template Lifecycle

Template: 创建未就绪版本 -> 保存追加 revision -> 校验就绪 -> 选择精确 revision ->
复制不可变定义进 draft；后续编辑模板不改已有 draft。
`current_revision` 只是库列表默认推荐，不是报告 render 时动态解析的别名。

Draft: 选 Stage/source/template -> 创建已保存 revision1 -> 编辑器本地 dirty ->
保存新 revision -> 可复制/下载 -> 显式 Finalize -> 原 writer 提交精确文件。
AI 候选和补全菜单本身不等于保存；dirty/待接受 AI 状态不能被宣称已经复制或定稿。
失败不清除本地输入。重放原 command 先于新 revision 检查；同 command 不同 payload 拒绝。

schema2 草稿引用完整模板快照与带格式 overlay；source snapshot 仍只存一份。
已定稿修订只读，纠错创建 linked draft。保留 schema1 reader，不重新哈希旧文件。
旧最终六文件下载完全不经过新 renderer；新的六文件布局也复用现有归档 namespace，
只按声明的 payload/manifest schema 升级校验，不放宽 namespace 文件白名单。

后续日期继承的是已确认 publication 的 effective authoring context，而不是原 AI 输出。
同周按日期追加，换周默认 last-confirmed-note + unresolved AR + 常驻备注；
完整旧周保留可读。草稿 Save 不替代 formal baseline，未保存/未定稿有明确提示。
报告的静态最终 HTML 不带编辑器；纠错由 linked draft 产生新版本，不覆盖旧字节。
切换周页面只读，不触发执行；生成按钮默认手动，定时适配在 W7 单独资格后启用。

## 5. AI Filling Is An Explicit Application Operation

人工填写始终可用，不依赖 AI Base。普通模板选择、保存、渲染和 `#ID` 补全不启动 AI。
AI 操作只在**已保存草稿**上选择可编辑 slot/叙述区域，再请求填写或改写。
服务端编译所选区域、模板填写说明及允许的 source evidence；不发送整个浏览器 DOM、
模板执行代码、凭据、隐式聊天历史、开发 skills 或其他项目材料。

应用 task profile 建议为 `project-reporting.authoring@1`，与 `summary@review-1` 分开。
输出是目标 ID -> 富文本片段 + evidence refs + filled/insufficient_evidence，
不是自由生成一份声称权威的完整 HTML，不允许模型修改 data 块、status、coverage 或 owner_confirmed。
缺少证据时 slot 保持 pending，不让模型编造答案。人工可以填写，但标明人工内容。

候选存入独立 assist 记录，绑定 draft revision/hash、模板结构/hash、fill policy hash、
scope/source hash、profile revision、input/result hash、Base run identity。
用户审阅后 Apply 到本地编辑区；下一次 Save 才持久化为 `ai_assisted` overlay。
如果期间有其他编辑/新修订/来源变化，候选不可自动应用；保留输入并显示冲突。
AI 原结果不改写，人工调整与采纳人单独记录；不推进成功摘要水位。

首批使用已有 task-run/1 的有界提交/查询/取消，不新增流式协议或把聊天接口作为 fallback。
浮窗先显示生成状态，完成后展示可滚动的建议及接受/拒绝；流式逐字渲染可后续接入，
不会因 UI 想流式就伪造后端能力。取消未知继续按原 runKey 查询，不宣称退款/已停止。
当前 a2/profile 只具有 synthetic 资格；生产必须有对应 authoring profile/授权及 adapter 资格。

## 6. Error Policy

完整表与用户文案在 [report-completion](report-completion.md)；关键不变量：

- 不在完整报告成员快照中的 ID 不查询全站详情，不泄露它是否在其他项目存在。
- 上游 404 可能同时表示不存在或不可访问；不能无证据将其显示为确定“不存在”。
- membership 不完整是未知，不是 outside；binding/权限变化也不是空列表。
- owner 未指派不是整票失败：前两种格式可用，第三种禁用并解释原因，不插入 `@None`。
- 超时/认证/限流保留原 `#ID` 和正文，不自动选其他 provider、credential 或缓存冒充最新。
- finalization 的失败继续使用原命令和已保留字节恢复，不重新查询工单/AI/模板。
- 跨日历史缺失/前日未定稿/并发基线变化按 continuity 拒绝；不退回原 AI 结果假装保留人工修改。

## 7. UI Contract

继续 Django/Bulma/htmx，沿用 `dashboard-edit-form`、`dashboard-action-bar`、
`dashboard-unsaved-banner`、Iconoir 和当前配色。编辑器是页面局部增强，邮件 HTML 不包含它。
报告中的 data 区只读，选中允许叙述区时就地启用编辑，不把整份受保护报告做无约束 contenteditable。
新增 slot 可在正文内编辑；模板结构操作使用列表、移动图标、类型菜单、必填 checkbox，
不增加独立画布产品或嵌套卡片。
note 的颜色/高亮使用受限色板，历史只读区保留用户显式颜色。
生成今日草稿是业务 action，保存/定稿继续独立；baseline/cutoff/周日期在相邻位置可核对。

候选浮窗锚定当前 token，三行固定顺序；长 title 换行、整体有界滚动。
焦点留在编辑器，用 active-descendant/listbox 语义，loading/error 用邻近 `role=status`。
Enter 在 IME composing 时不接受；有候选时不提交表单；Esc 关闭并保持原文。
鼠标选择与键盘选择走同一原子替换；重复回调不插入两次。
不依赖 iframe 才可编辑；原 preview iframe 失败必须修复展示装配，不关闭产物 CSP。

桌面 Chrome/Ego 是本阶段目标；中英文、长文本、无障碍键盘、剪贴板和真实 Outlook 接收
按原 HT28-30 验收。手机、多浏览器、美化不重新加入当前交付阻塞。

## 8. Execution And Approval

新叶任务沿原 W6 命名为 `W6.AUTHOR.*`，只有 tasks.md 可勾选。
顺序：契约/反例 -> 格式持久化与编辑器 -> lookup -> 用户模板 ->
跨日/跨周历史与稳定行序 -> 手动准备 -> AI 填写 -> 联合作者流程。
每个增量都含配套 renderer/存储/接口消费者校验，不能把 v2 写入后再补历史 reader。
已有 W6.HTML.* 与 W7.E2E 的通过事实保留，但变化的消费者必须重验；不声称旧证据覆盖新 schema。
执行时一个代码写入者；独立 review 是质量步骤，不要求用户另找一个开发 Agent。

详细结构/错误策略已获用户同意，PLAN.R/VA已通过首CONTENT切片的有边界开工审查。
后续叶按实际源码逐一关闭接口与验证门禁；没有真实HSDES单票响应资格时可做fake合约与Jira路径，
但 HSDES live 能力保持 blocked，不把它从验收清单删除。

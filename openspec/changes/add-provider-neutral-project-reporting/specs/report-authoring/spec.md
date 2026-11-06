## ADDED Requirements

### Requirement: Skipped meetings preserve actual editorial continuity
The application SHALL support explicit single-date or inclusive date-range standup
skip and restore records, distinct from missing reports and unfinalized drafts.
Meeting metadata SHALL NOT create source captures, AI runs, drafts or publications,
advance any report baseline, or resolve ticket actions.

#### Scenario: Resume after two empty weeks
- **WHEN** the last confirmed report precedes one or two weeks without meetings
- **THEN** the resumed daily report SHALL inherit the latest actual confirmed
  effective notes, unresolved actions and carry-forward notes with their original
  dates, provider statuses, colors and links
- **AND** it SHALL NOT manufacture intermediate daily updates or a Friday baseline
- **AND** explicit skipped dates SHALL be frozen as separate meeting metadata

#### Scenario: A skipped date conflicts with retained work
- **WHEN** any date in a skip range already has preparation, draft or publication
  work, or concurrent preparation wins the shared admission lock
- **THEN** the complete skip request SHALL be rejected without partial changes
- **AND** unfinalized draft handling SHALL still require explicit gap consent

#### Scenario: Undo and immutable reports
- **WHEN** an operator explicitly restores a skipped date
- **THEN** the calendar SHALL retain the audit record and restore only eligibility
- **AND** existing report snapshots, original downloads and baselines SHALL remain unchanged

### Requirement: WYSIWYG is the only report editing mode
应用 SHALL 通过现成富文本组件在报告的可编辑叙述区和填写槽中就地编辑。
用户 SHALL NOT 被要求打开 Markdown 源码模式；取消源码编辑 SHALL NOT 取消原 Markdown/Excel 导出义务。
原始来源、状态、coverage、截止时间、accepted summary 和已定稿字节 SHALL 保持原权威。

#### Scenario: Formatted content survives a saved revision
- **WHEN** 用户编辑正文或会议注释的受支持格式并保存
- **THEN** 重新打开相同修订 SHALL 保留内容、链接和格式
- **AND** 保存 SHALL 使用版本化、服务端校验的片段，不信任任意编辑器 HTML
- **AND** source事实和accepted summary hash SHALL 不变

#### Scenario: Legacy literal edits are read after upgrade
- **WHEN** 新编辑器读取旧 schema 的 `ReportEdit.text`
- **THEN** 旧值 SHALL 仍按原来的普通文字解释
- **AND** 读取 SHALL NOT 修改旧 revision/hash 或重新渲染已定稿下载

### Requirement: Ticket completion is triggered only by hash-prefixed identifiers
工单补全 SHALL 仅由可编辑正文中的 `#ID` 输入自动触发。
裸 ID、URL、补全快捷键和补全按钮 SHALL NOT 成为替代触发。
上下键和 Enter 只负责选择/确认，工单补全 SHALL NOT 调用模型。

#### Scenario: Three completion formats are offered
- **WHEN** 一个有效、可见、范围内的工单有合格的 title 与 assignee
- **THEN** 菜单 SHALL 依次提供链接 ID、链接 ID加空格及title、前项加空格及`@assignee`
- **AND** Enter SHALL 原子替换含`#`的精确token、关闭浮窗并保留焦点
- **AND** 一次撤销 SHALL 还原该补全动作而非整份报告

#### Scenario: Heading syntax and composition are not completion
- **WHEN** 用户输入标题语法、代码/既有链接中的`#`或处于中文输入法组合状态
- **THEN** 编辑器 SHALL 避免误触发工单查询或以IME确认键接受候选
- **AND** Escape关闭 SHALL 保留原token与正文

#### Scenario: A response arrives after the target changed
- **WHEN** token、光标上下文、目标区域、草稿或服务器修订在响应前改变
- **THEN** 旧结果 SHALL 被丢弃或标记过期
- **AND** SHALL NOT 插入其他位置、覆盖新候选或重复接受

### Requirement: Completion uses the report stage and verified report membership
补全 SHALL 由报告所属 Stage 的冻结来源选定 provider、profile 和 endpoint。
Jira SHALL 使用显式 scope/profile，HSDES SHALL 使用自己的 saved-query profile。
客户端 SHALL NOT 覆盖来源、凭据、actor或原始query；不存在第二个默认provider。

#### Scenario: Provider is implied by the stage
- **WHEN** 用户在 Jira 或 HSDES 报告中输入`#ID`
- **THEN** 服务 SHALL 按对应Stage的来源解释ID，不要求用户增加系统前缀
- **AND** 格式不匹配 SHALL 提示错误，不回退到另一系统

#### Scenario: Identifier is absent from complete report membership
- **WHEN** 本报告完整成员快照没有所输入ID
- **THEN** 服务 SHALL 显示“未列入本报告范围，或编号有误”
- **AND** SHALL NOT 查询范围外详情、扩大范围或声称已确认全站不存在

#### Scenario: Membership coverage cannot prove absence
- **WHEN** 成员集合未完整确认或绑定已变化
- **THEN** 服务 SHALL 显示范围未确认或来源变化
- **AND** SHALL NOT 把未知当作范围外或成功空结果

#### Scenario: A known member is no longer accessible
- **WHEN** 已知成员的上游响应不能区分不存在和无权限
- **THEN** 提示 SHALL 为“不存在或当前账号无法访问”
- **AND** SHALL NOT 泄露旧title/owner、改用其他凭据或伪造删除结论

### Requirement: Completion failures are non-destructive and freshness is explicit
补全 SHALL 提供相互区分的格式、范围、认证、限流、超时、未合格接口与非法响应状态。
失败 SHALL 保留正文、token和未保存修改，且不形成部分引用或修改成功水位。

#### Scenario: Owner is unassigned
- **WHEN** 合格工单明确未指派owner
- **THEN** 前两种可成立的格式 SHALL 可选
- **AND** 第三种 SHALL 禁用并注明未指派，而非插入`@None`

#### Scenario: Lookup times out or is rate limited
- **WHEN** 上游超过请求期限或本地/上游限流
- **THEN** 页面 SHALL 显示对应错误并保留输入
- **AND** SHALL NOT 自动循环请求、用缓存冒充最新或切换认证身份

#### Scenario: Live observation is newer than report cutoff
- **WHEN** 补全成功读取最新title/assignee
- **THEN** 报告注释 SHALL 保留观察时间与原报告截止时间的区别
- **AND** 原快照/accepted summary SHALL NOT 被这次只读查询修改
- **AND** 未验证的客户端时间/字段 SHALL NOT 被保存成可信provider收据

### Requirement: Users can author versioned report templates
用户 SHALL 能通过可视化界面创建、复制、编辑、保存版本和归档项目内模板。
模板 SHALL 包含受支持的固定内容块、人工/AI可填槽和受控数据块；
不要求源码编辑，也 SHALL NOT 执行任意HTML/CSS/Django/Jinja表达式。

#### Scenario: User creates a template and fills it manually
- **WHEN** 用户新增章节/填写槽并保存为就绪模板
- **THEN** 用户 SHALL 能从指定版本创建报告并人工填写
- **AND** 创建模板、选择、保存与渲染 SHALL 不调用模型或Provider

#### Scenario: Template omits mandatory report data
- **WHEN** 旧版详细模板缺少其coverage、register或其他强制来源区
- **THEN** 库 SHALL 允许保留明确未就绪草稿但拒绝用于生成貌似完整报告
- **AND** SHALL 指明缺少的结构，不静默补造或隐藏pending/action

#### Scenario: User selects concise standup presentation
- **WHEN** 用户创建采用显式`standup/1`呈现版本的新连续性模板
- **THEN** 正文 SHALL 只含用户模板内容、每票累计有效notes、来源状态、未结束AR及简短覆盖信息
- **AND** 原始摘要、完整证据和编辑审计 SHALL 继续保留但不强制附在正文
- **AND** 必需meeting_matrix缺失或重复 SHALL 阻止模板就绪，不能隐藏未处理工单
- **AND** 旧模板和已定稿报告的hash、正文及下载字节 SHALL 不变

#### Scenario: Audit attachment is exported independently
- **WHEN** 已授权用户下载一个已定稿报告的完整审计附件
- **THEN** 附件 SHALL 包含该publication的六个原始文件、可读审计视图和版本化文件hash清单
- **AND** 文件 SHALL 来自同一已核验commit，不能混入当前草稿或最新工单内容
- **AND** 下载 SHALL NOT 重新调用来源、模型、正文renderer、Save或Finalize
- **AND** 无权限、缺失或损坏文件及超限 SHALL 明确失败，不静默提供部分附件

#### Scenario: A continuity template omits its meeting matrix
- **WHEN** 新v2 daily/weekly模板缺少或重复meeting_matrix
- **THEN** 模板 SHALL 不得标ready，系列准备 SHALL 拒绝选择
- **AND** 旧v1模板仅保留旧行为，SHALL NOT 被用作无矩阵连续性回退

#### Scenario: Template changes after draft creation
- **WHEN** 库中保存了新版本或模板被归档
- **THEN** 已有draft SHALL 继续绑定完整的原模板快照
- **AND** 新选择归档模板 SHALL 被拒绝，历史定稿不受影响

#### Scenario: Concurrent template save or quota failure
- **WHEN** expected revision失效或模板额度/写入失败
- **THEN** 服务 SHALL 原子拒绝，不产生半个revision/command/head
- **AND** 原版本 SHALL 保留，同command重放仅返回原结果

### Requirement: AI filling is explicit, evidence-bound and provisional
人工填写 SHALL 独立于AI就绪性。AI填写 SHALL 是显式请求，
使用独立authoring profile和受控输入，而不是模板渲染副作用或权威summary接口的隐式复用。
候选 SHALL 绑定模板、目标、来源和草稿版本，在用户接受并保存之前不成为持久编辑。

#### Scenario: User requests AI fill for selected slots
- **WHEN** 用户在已保存草稿中选择填写槽并请求AI
- **THEN** 应用 SHALL 只向获准Base任务提交对应输入
- **AND** 候选 SHALL 不修改数据区、owner确认、source hash或summary水位
- **AND** 人工接受/调整 SHALL 保留操作者和原AI结果来源

#### Scenario: Evidence is insufficient or result is invalid
- **WHEN** AI缺少证据、返回非法目标/schema或不匹配的run身份
- **THEN** 应用 SHALL 保留未填/失败状态并拒绝错误候选
- **AND** SHALL NOT 编造事实、自动定稿或把失败当作人工内容

#### Scenario: Draft changes or cancellation is unresolved
- **WHEN** 候选返回前草稿变化，或Base取消/提交结果未知
- **THEN** 应用 SHALL 保留原候选/任务关联并显示冲突或未知
- **AND** SHALL NOT 以新key重复派发或自动覆盖当前内容

### Requirement: Authoring preserves exact finalization and export guarantees
schema升级 SHALL 使用版本化reader与同一stage归档writer。
保存/复制/下载 SHALL 不等于定稿；定稿 SHALL 保留模板快照、编辑历史、来源收据及精确输出。
首批 SHALL 不自动发邮件、push、修改工单或启用调度。

#### Scenario: Required slot or unsaved content blocks finalization
- **WHEN** 必填槽未填，或编辑器有未保存/未接受内容
- **THEN** 页面 SHALL 标注对应位置并阻止把该内容宣称为已定稿
- **AND** 草稿保存与已保存版本的历史读取 SHALL 继续受支持

#### Scenario: Schema2 finalization resumes after failure
- **WHEN** 定稿在Git副作用前后中断
- **THEN** 恢复 SHALL 只使用原命令和预存的精确六文件packet
- **AND** SHALL NOT 读取当前模板/最新工单来重造原产物
- **AND** 旧schema定稿下载 SHALL 返回原字节

### Requirement: Every ticket retains an independent stable report row
会议矩阵 SHALL 一票一行，组序和初始排序由模板管理。
同系列已有票的位置 SHALL 保持稳定，新票按确定性规则追加到对应组。
共享 PR、assignee、状态或相似标题 SHALL NOT 合并票据历史或触发自动重排。

#### Scenario: Related tickets share a fix
- **WHEN** 三张票引用同一修复且负责人相同
- **THEN** 每张票 SHALL 有独立行、note、来源状态和AR
- **AND** 共同修复 SHALL 仅作为关联或顶部摘要引用

#### Scenario: Existing ticket changes status and a new ticket arrives
- **WHEN** 状态/更新时间改变，或新成员进入范围
- **THEN** 已有票的相对位置 SHALL 不变，新票追加到相应组尾
- **AND** 用户显式重排 SHALL 产生可继承的新修订，不重排旧定稿

#### Scenario: Ticket leaves and returns to the same series
- **WHEN** 同一来源stable ID移出后再次进入
- **THEN** 应用 SHALL 保留身份与历史位置，明确记录成员变化
- **AND** SHALL NOT 将移出解释为关闭、删除历史或另一张新票

### Requirement: Dated status prefixes use source-system facts only
每条有状态快照的note SHALL 使用 `ww45.1(Fixed):` 形式。
括号值 SHALL 来自该次已选来源快照的实际Jira/HSDES状态，不是AI分析、健康分桶或人工推断。
日期、状态、来源hash和观察时间 SHALL 由应用绑定并只读。

#### Scenario: AI describes a fix while the ticket remains in analysis
- **WHEN** 来源状态为In Analysis而AI正文写了修复完成
- **THEN** 前缀 SHALL 仍为该日期的In Analysis
- **AND** AI或人工叙述 SHALL NOT 改写来源状态或推进工单工作流

#### Scenario: Imported history lacks a source-status snapshot
- **WHEN** 旧note有日期但没有可证明的当时状态
- **THEN** 前缀 SHALL 省略状态括号并保留缺口
- **AND** SHALL NOT 从今天的状态倒填过去日期

### Requirement: The effective user-authored rich text is the continuity authority
用户修改后的有效富文本 SHALL 作为后续报告继承依据，保留正文、删除结果、颜色、
高亮、marks、链接和provenance。原AI输出 SHALL 独立保留但不得覆盖已保存人工版本。
支持的颜色/格式 SHALL 显式进入版本化schema、校验、保存、读取与渲染契约。

#### Scenario: User edits and colors an AI-generated note
- **WHEN** 用户增删正文、着色、高亮并插入补全链接，保存后重开并定稿
- **THEN** 重新打开及后续日期 SHALL 保留最终有效文字和格式
- **AND** 只有格式的修改 SHALL 也产生dirty与新revision/hash

#### Scenario: A delayed AI candidate conflicts with user changes
- **WHEN** AI返回前用户已保存新内容或格式
- **THEN** 旧候选 SHALL 被标为冲突，保留当前人工内容
- **AND** SHALL NOT 按最初AI文本重建note或恢复被用户删除的句子

#### Scenario: Unsupported formatting or storage failure occurs
- **WHEN** editor/codec不能保留受支持格式，或保存/额度失败
- **THEN** 应用 SHALL 明确失败并保留输入和旧修订
- **AND** SHALL NOT 静默去掉颜色、截断历史或假报已保存

#### Scenario: A non-rich export cannot represent colors
- **WHEN** 用户导出Markdown/plain或格式能力受限的Excel
- **THEN** 应用 SHALL 明确该格式能力，不把有损导出用作历史恢复权威
- **AND** 原富文本/HTML SHALL 完整保留，不声称所有导出逐像素一致

### Requirement: Daily notes accumulate without rewriting accepted history
同一周每列 SHALL 包含其截止日期前的已确认notes和允许的weekly seed，
按原日期升序显示。每个逻辑note SHALL 只保存一次并由稳定身份关联，
不是复制前一列整段正文后继续嵌套。AR标签 SHALL 使用AR或AR?区分来源依据。

#### Scenario: The second and third day are prepared
- **WHEN** 已有day1、day2、day3各自的note
- **THEN** day1列 SHALL 仅含day1，day2列含day1/day2，day3列含day1/day2/day3
- **AND** 原note的状态、文字、颜色和AR日期 SHALL 保留，不泄漏未来记录

#### Scenario: A day has no confirmed update
- **WHEN** 某日未运行、采集失败或没有记录新note
- **THEN** 应用 SHALL 明确缺失/未更新，不虚构该日进展或“无变化”
- **AND** 已有notes和未结束AR SHALL 不被清空

#### Scenario: A finalized note needs correction
- **WHEN** 用户修改已定稿的历史说明
- **THEN** 应用 SHALL 创建关联新草稿/修订并保留旧publication
- **AND** 已有后续定稿 SHALL 不被自动反写；新选择的修订来源可追溯

### Requirement: Week rollover preserves the latest confirmed position and unresolved work
换周 SHALL 创建新的展示周期而非新的Stage或scope。
默认新周seed SHALL 携带每票最近已确认note、全部未结束AR/未确认建议和常驻备注，
保留原日期、来源状态、用户格式及引用。完整旧周历史 SHALL 继续可读。

#### Scenario: The first report of a new week is prepared
- **WHEN** 上周最后确认记录为ww45.5，新周当前日期为ww46.1
- **THEN** 新周首列 SHALL 先显示原ww45.5记录，再追加真实ww46.1内容
- **AND** SHALL NOT 把旧note重标为本周更新或重算其颜色/状态

#### Scenario: An older action remains unresolved
- **WHEN** 最后一条note来自周五但周二仍有未结束AR
- **THEN** 周二AR SHALL 独立携带并按action ID去重
- **AND** 票据Fixed/Done或翻周 SHALL NOT 自动关闭该AR

#### Scenario: The last weekday or prior week has no publication
- **WHEN** 周五或整个上一周没有确认日报
- **THEN** 应用 SHALL 使用最近实际合格的基线并显示真实日期/间隔
- **AND** 无任何历史时 SHALL 明确初始报告，不编造前周note

#### Scenario: The user selects a compact weekly view
- **WHEN** 模板仅显示最近更新和未结束行动
- **THEN** 更早note的完整用户内容与格式 SHALL 保留在旧周历史
- **AND** 常驻备注 SHALL 不因精简窗口消失，full-history模式不得静默裁剪

#### Scenario: The reporting calendar is missing or crosses a year
- **WHEN** 工作周映射缺失或跨年
- **THEN** 日期身份 SHALL 包含日历修订与工作周年份
- **AND** 缺映射 SHALL 拒绝准备，不用AI猜测或仅靠周号选择历史

### Requirement: Source, analysis and editorial baselines advance independently
Source capture、accepted summary和正式作者报告 SHALL 保持独立引用与成功水位。
新日报 SHALL 继承最近确认的有效作者文档，只有精确daily publication提交确认后
才能推进editorial baseline。Save、AI接受、预览、下载和weekly_view SHALL NOT 代替定稿。

#### Scenario: A saved draft has unfinalized user changes
- **WHEN** 后续日期准备时发现前日已保存未定稿内容
- **THEN** 默认 SHALL 提示处理原草稿并停止自动继承
- **AND** 用户明确选择旧正式基线继续时 SHALL 记录gap，不丢弃或冒充接受原草稿

#### Scenario: Publication commits but the response or cache update is lost
- **WHEN** Git提交已完成而响应/索引更新中断
- **THEN** 恢复 SHALL 核验同一publication并重建可派生head
- **AND** SHALL NOT 重算报告、重复提交或用不确定结果推进成功水位

#### Scenario: Another window advances the baseline
- **WHEN** 草稿携带的expected baseline已失效
- **THEN** 最终提交 SHALL 拒绝旧基线并保留人工内容
- **AND** SHALL 要求显式合并/重新准备，不采用最后写入者覆盖

### Requirement: Daily draft preparation is an explicit idempotent operation
默认每日准备 SHALL 由用户的“生成今日草稿”按钮触发，沿现有运行/采集/分析服务。
选择已保存capture人工填写 SHALL 可独立工作；生成草稿 SHALL NOT 自动定稿。
同系列同meeting的生成入口 SHALL 共享持久化去重与版本保护。

#### Scenario: User creates or changes a report series
- **WHEN** 用户通过系列设置选择日历和模板并明确保存
- **THEN** 应用 SHALL 经公开API创建稳定series ID或CAS保存新策略修订
- **AND** GET SHALL NOT 按标题或Stage隐式创建系列，旧草稿保留原policy

#### Scenario: User explicitly prepares today's draft
- **WHEN** 用户选择日期、模板、基线与来源/分析方式并提交
- **THEN** 应用 SHALL 冻结这些选择并返回可观察的operation或已保存draft
- **AND** 只有显式刷新来源/AI模式可发起对应外部调用，结果仍需人工审阅定稿

#### Scenario: The user clicks twice or today's draft already exists
- **WHEN** 相同命令重试或另一个生成入口请求同一meeting
- **THEN** 应用 SHALL 返回原操作/当前草稿，不覆盖人工修改
- **AND** SHALL NOT 重复采集、派发模型或生成第二份自动baseline
- **AND** 同command不同payload SHALL 拒绝，不同command同meeting的新选项 SHALL 明示未应用

#### Scenario: User navigates to another week or the clock passes midnight
- **WHEN** 页面GET、切周、重开浏览器或已启动作业跨过午夜
- **THEN** 页面读取 SHALL 不发起新运行，已启动作业保留原meeting日期
- **AND** SHALL NOT 自动创建日报、回填缺失日期或定稿

### Requirement: Optional scheduling prepares drafts but never finalizes them
定时入口 SHALL 默认关闭，只有独立配置/授权/运行资格通过后才可启用。
调度 SHALL 调用与手动相同的准备服务并共享meeting去重、权限、预算及恢复；
它 SHALL NOT 推进正式报告基线、自动发送或修改工单。

#### Scenario: Scheduled preparation races with a manual request
- **WHEN** 定时与按钮同时请求同系列同日
- **THEN** 仅一份持久化准备操作 SHALL 获得执行，其余返回相同结果
- **AND** 已有草稿编辑 SHALL 保留，Finalization仍需用户确认
- **AND** 后到命令选项不同时 SHALL 返回原已选选项及差异提示，不假报已应用新选项

#### Scenario: A scheduled occurrence is missed
- **WHEN** 停机、休眠、时区缺口或日历未就绪导致错过运行
- **THEN** 应用 SHALL 明确记录missed/unavailable，不制造已完成日报
- **AND** 重复时刻 SHALL 幂等，恢复时不得默认批量补跑或改变原预算

## Context

See `proposal.md` for motivation. 当前系统已经具备三个关键基础：Django Dashboard 暴露 server-rendered pages、partials 和 `/api/ai-dashboard/*`；Bug Trend/Grafana 已有 chart data、evidence data、`metricsContract`、`evidenceCapability` 和 `evidenceLinkFields`；AI Base 已通过 `dashboard_query_agent`、workspace context、artifact validation、approval 和 publish handoff 与 Dashboard 打通。

当前缺口不是单个 API，而是 UI orchestration：用户需要一个 shell 持有 profile/range/chart/selection 状态，并把 Grafana/Chart.js/AI chat/Django settings/evidence list 放到同一个工作台。该 shell 不能把 Grafana iframe 或 AI Base 内部状态当成 source of truth，否则 ticket evidence、approval 和 provider boundary 会再次漂移。

## Goals / Non-Goals

**Goals:**

- 提供一个 Dashboard-owned `Metrics Workbench` single Web UI。
- 让 chart pane、evidence pane、AI pane、settings/publish/audit pane 可以按声明挂载到固定或 dockable layout。
- 让 evidence-backed chart click 转换为 Metrics-validated PageQueryState selection，并刷新下方 Jira/HSD-ES ticket list。
- 明确不支持 point-level evidence 的 chart 状态，避免展示旧 ticket rows。
- 保留现有 Django/Bulma/HTMX surfaces 和 module public API boundary。
- 保留 Grafana 作为重要 renderer/publish target，而不是把它升级为业务 source of truth。

**Non-Goals:**

- 不把整个 Dashboard 重写成 React SPA。
- 不把产品迁移到 Backstage、Appsmith、ToolJet、Budibase 或 Grafana-only app。
- 不让 AI Base 直接查询 Jira/HSD-ES、直接拥有 chart semantics 或直接发布 Grafana dashboard。
- 不在第一阶段实现任意 chart authoring 的完整 visual editor。
- 不要求所有 chart 都支持 ticket-level evidence。

## Decisions

### Decision 1: Dashboard owns the workbench shell and PageQueryState

Workbench shell 放在 `ui_web`，由 Django route 提供入口页面，由 Dashboard 后端产生 initial context、pane registry 和 safe service status。PageQueryState 至少包含 `profile_id`、`provider_id`、`range_mode`、`begin/end`、`chart_id`、`chart_version`、`calculation_run_id` or `fact_snapshot_id`、`selected_bucket_id`、`selected_series_name` 和 `list_filters`。

PageQueryState 的 canonical representation 是 URL query string。Workbench 可以用 browser local storage 缓存最后一次有效 same-origin `/workbench/` URL，仅用于主导航恢复用户上下文；它不能接受外部 URL、不能替代 server validation，也不能成为 provider/evidence truth。无 `scope_id` 的 server default state 应优先选择与 `profile_id` 同名的 enabled scope，例如 `chiplet-2a-jira`，再退回第一个 enabled scope，避免用户从其它页面返回时落到 unrelated empty scope。

Alternatives considered:

- **AI Base as shell**: chat 体验更自然，但会把 provider/evidence/publish authority 拉出 Dashboard，和既有边界冲突。
- **Grafana as shell**: chart 体验最强，但 Django settings、approval、AI handoff 和 deterministic evidence list 会变成 plugin/application work，风险更高。

Rationale: Dashboard 已经拥有 facts、chart recipes、evidence、validation、approval 和 Grafana publication。shell state 放在 Dashboard 最符合现有 authority model。

### Decision 2: Use a high-density resizable workbench layout

默认 workbench layout 是高密度三窗格：左上 chart pane、左下 evidence pane、右侧 AI pane。chart/evidence 使用水平 splitter 调整高度，evidence list/detail 使用 evidence 内部垂直 splitter 调整宽度，main/AI 使用全局垂直 splitter 调整宽度。chart pane、ticket detail pane 和 AI pane 都可折叠，折叠只改变 layout state，不改变 PageQueryState、selected bucket/series、selected tickets 或 chat session。

第一阶段可以用轻量原生 CSS/JS splitter 实现固定 pane registry + 可拖尺寸；如果后续需要 dock/tab/float，再引入能隔离在 shell asset 中的 lightweight dock layout library，例如 Dockview。dock/splitter layer 只负责 pane placement，不负责业务数据流。

Alternatives considered:

- **Pure Bulma grid only**: 风险最低，但后续 plug-and-pack pane 需求会很快变成自研 layout engine。
- **Full SPA framework migration**: 对现有 Django/HTMX surface 破坏太大。
- **Backstage/low-code portal**: 会引入第二个产品壳和权限/导航模型。

Rationale: 当前用户分析路径需要在 chart、ticket table、ticket detail 和 AI assistant 之间快速调整空间。原生 splitter 可以先满足高密度 resize/collapse 诉求，并且不会把业务状态放进 layout library。dock layer 仍必须是可替换 UI infrastructure。

### Decision 3: Chart pane supports multiple renderer routes through one contract

Chart pane 使用 chart definition/renderer metadata 选择 renderer：

- `chartjs_reference`: 当前 Metrics-owned reference renderer，最适合第一阶段验证 click-to-evidence。
- `grafana_stock_panel`: 优先嵌入 Metrics-generated Grafana single panel 或 solo panel URL，隐藏 Grafana 全局 chrome，并通过 approved data link 或 shell callback 同步 selection。
- `grafana_stock_dashboard`: 仅作为 diagnostics/admin/fallback 入口打开完整 Grafana dashboard page，不作为 workbench chart pane 的默认形态。
- `grafana_plugin`: 如果 stock Grafana 无法稳定完成 event/evidence gate，再进入 Grafana App/Scenes spike。

Rationale: 不能把第一阶段押在 Grafana iframe event internals 上，也不能把完整 Grafana UI 塞进 workbench chart pane。Chart.js reference path 能快速建立 deterministic selection/evidence behavior，Grafana single-panel embed 验证 publish parity 和 compact rendering，plugin path 作为后备。

### Decision 4: Prefer compact Grafana panel embed before SDK/plugin work

Workbench 中的 Grafana chart pane 默认使用 panel-only embed/solo URL，并把 panel id、dashboard uid、profile/range variables 和 evidence data-link contract 作为 pane metadata。完整 Grafana dashboard page 只能通过 utility link、diagnostics pane 或 admin action 打开，不应占据主分析工作区。

Alternatives considered:

- **Full Grafana dashboard iframe**: 实现最简单，但 Grafana 顶部导航、变量区、侧栏和 dashboard chrome 会占用太多空间，放入 workbench pane 后 UX 差。
- **Grafana SDK/App Plugin/Scenes first**: event control 最强，但会把第一阶段推向 Grafana plugin engineering，超过当前 one-window consolidation 的必要复杂度。

Rationale: single-panel embed 是最小可行路径；只有当 panel embed + data link 不能满足 click-to-evidence gate 时，才进入 Grafana App/Scenes。

### Decision 5: Evidence list is always Metrics-owned

Evidence pane 调用 Metrics evidence APIs。Chart click 只提供 selection candidate；后端必须验证 selected run/snapshot、bucket、series、chart id、profile/range 是否匹配。验证失败时清空旧 rows 并显示错误或 unsupported state。

Evidence table 是一个高密度工作区，而不是只读列表。表头提供 list-local controls：字段显隐、可见字段排序、selected ticket count、bulk action 和 export。每行支持 checkbox 多选，selection 是 explicit ticket working set；它可以作为 AI grounding 或 bulk action 输入，但必须和 chart bucket/series selection 分开建模。

点击单个 ticket 时，evidence window 右侧打开 ticket detail pane。该 pane 只展示 Metrics/provider API 已返回或按需获取的 normalized ticket fields、description summary、latest activity、links 和 action buttons。它不能 iframe 完整 Jira/HSD-ES browser page，不能拥有 provider cookies/credentials，也不能把外部系统 navigation 带进 workbench。完整 Jira/HSD-ES 页面只作为 `Open in Jira/HSDES` 外链。

Alternatives considered:

- **Grafana panel 直接查询 ticket list**: 会复制 Jira/HSD-ES 语义，破坏 Metrics ownership。
- **AI Base 解释后生成 list**: 不可确定、不可审计，不适合作为 evidence source。

Rationale: ticket evidence 是业务事实和审计对象，必须从 Metrics 计算产物和 provider facts 中派生。

### Decision 6: AI Base is an optional contextual pane

AI pane 通过 safe context handoff 接收当前 profile/range/chart/selection 和显式 selected-ticket working set。Selected-ticket payload 只包含 safe summary fields，并带 `selectedTicketCount` / `truncated` 元数据；默认最多传递 50 条 ticket summary，避免把大列表或 provider 原始内容直接塞进 AI pane。AI Base 可以解释、draft、dry-run 和请求 publish，但不能绕过 Dashboard APIs。AI 不可用时，workbench 其它 pane 继续工作。

AI pane 不应 iframe 完整 AI Base App chrome。短期允许接入 AI Base compact embed route；长期推荐 Dashboard host-native compact renderer，使用 AI Base backend chat/approval/artifact/diagnostics contract。compact sidebar 默认不显示 context chips，不显示内部 service status strip；全局 service status 只由 workbench bottom status bar 展示。AI pane 可以向右折叠成窄 rail，折叠不丢 chat session、pending approval 或 artifact state。

AI Base compact embed 是显式 surface contract，而不是 Dashboard-side iframe clipping。Dashboard 通过 `embed=workbench` 请求 compact route；AI Base 负责隐藏完整 AppShell navigation、session setup sidebar、session files/details panel 和内部 status chrome，只保留 sidebar 可用的 chat conversation/composer 和轻量 session selector。完整 AI Base UI 继续通过外链打开。

Rationale: 这保持 AI Base 的平台价值，同时避免把用户的 dashboard state 分裂到另一个窗口。

### Decision 7: One-window runtime is a launcher/proxy concern, not product ownership

本 change 可以新增或扩展 local launcher/reverse-proxy，使用户只打开 workbench URL。代理层负责同源路径、service discovery 和 health；业务权限仍在 Dashboard/API 层。

Workbench 页面本身不负责 on-the-fly 启动 Dashboard、Grafana 或 AI Base。AI Base disabled 表示当前 Dashboard process 未启用 sidecar 配置；AI Base unavailable 表示 sidecar 配置已启用但 handshake/runtime probe 不通过。UI 应在 AI pane 和 bottom service status 中给出准确原因、诊断入口和统一 stack launcher 命令，而不是在页面渲染时创建后台进程。

Launcher 的 start、stale cleanup、boot-log audit 和 process-inventory audit 必须读取同一个 Dashboard lifecycle state source。当前 Dashboard/Grafana runtime 由 `ServiceLifecycleEngine` 管理，wrapper 脚本不得再读取旧 `port-lifecycle` state 作为当前进程权威；final cleanup 也不得在 smoke 通过后重新清理当前 Dashboard/Grafana 进程树。

Rationale: 单窗口 UX 需要 runtime glue，但不应该让 proxy 成为业务规则承载点。

## Risks / Trade-offs

- [Risk] Grafana single-panel iframe/data-link 不能可靠地把 click 事件同步回 parent shell。 → Mitigation: 第一阶段用 Chart.js reference path 验证 PageQueryState/evidence；Grafana panel embed path 作为 feasibility gate；失败时进入 Grafana App/Scenes spike。
- [Risk] 实现者为了省事把完整 Grafana dashboard page iframe 放入 chart pane。 → Mitigation: spec 明确主 chart pane SHALL use compact panel-level embed；full dashboard page 只能作为 diagnostics/admin/fallback link。
- [Risk] 引入 dock layout dependency 后前端复杂度上升。 → Mitigation: 固定 layout 先交付；dock layer 只负责 pane placement；业务 interaction 仍用 server routes、HTMX、JSON APIs。
- [Risk] 用户移动 pane 后 evidence context 不明显。 → Mitigation: 全局 toolbar 和 evidence pane header 始终显示 active profile/range/chart/selection。
- [Risk] Grafana variables 与 shell state 不一致。 → Mitigation: shell state 为 source of truth；Grafana pane reload/sync indicator 显示 mismatch。
- [Risk] AI pane 获得过多 context 或敏感字段。 → Mitigation: 复用 safe AI context redaction rules，只传 approved profile/range/chart/selection 和 bounded evidence summaries。
- [Risk] 老 full-page URLs 与新 workbench routes 并存导致导航混乱。 → Mitigation: 保留 legacy pages，新增 workbench entry；完成等价能力后再逐步把主导航指向 workbench。

## Migration Plan

1. 新增 workbench route/template/static shell，默认固定 layout，pane registry 仅包含第一批 pane。
2. 把 Bug Trend chart 和 evidence list 接入 shared PageQueryState，先使用 Chart.js reference renderer 验证 click-to-evidence。
3. 将 Grafana single-panel embed/data-link 接入 shell selection sync，记录是否满足 evidence gate；完整 Grafana dashboard page 只保留为 diagnostics/admin/fallback link。
4. 将 AI Dashboard Workflow/AI Base iframe or route 加入 optional AI pane，并实现 safe context handoff。
5. 扩展 launcher/proxy，打开单一 workbench URL，并在 shell 中显示 service health。
6. 增加 browser/E2E 验证：one-window startup、chart click refreshes evidence、unsupported chart clears evidence、AI unavailable does not block dashboard。
7. 当 workbench 等价覆盖现有 navigation 后，再把 primary nav 默认入口切换到 workbench；legacy pages 暂保留。

Rollback strategy: workbench 是新增入口；如集成失败，保留原 Django/Grafana/AI Base 独立窗口流程。任何主导航切换必须独立提交，并可回退到原页面链接。

## Open Questions

- Grafana stock panel data link 是在同 iframe 内打开 evidence URL、通过代理 route 回写 shell state，还是使用 custom wrapper 捕获 link navigation，需要 implementation spike 后确认。
- Dock layout persistence 第一版使用 browser local storage 还是 server-side user preference，可以在实现时按现有用户/session模型决定。

## 1. Workbench Shell Foundation

- [x] 1.1 新增 unified workbench route、view 和 template，默认渲染 global toolbar、chart pane、evidence pane、AI pane 和 utility pane，并通过 Django test client 验证 workbench URL 返回 200 且包含这些 pane landmarks
- [x] 1.2 定义 pane registry 数据结构和默认 layout 配置，覆盖 chart、evidence、AI、settings、publish/audit、diagnostics panes，并通过单元测试验证每个 pane 有 id、title、capability、source type、target 和 allowed placement
- [x] 1.3 实现 fixed default layout 的基础 CSS/JS shell，验证 desktop 和 mobile screenshot 中 pane 不重叠、toolbar 不遮挡内容、AI pane 可折叠
- [x] 1.4 增加 scoped service-status surface，展示 Dashboard、Grafana、AI Base 可用/不可用状态，并通过 view test 验证 AI Base unavailable 不会阻断 shell 渲染

## 2. Shared PageQueryState

- [x] 2.1 新增 workbench PageQueryState parser/serializer，覆盖 profile、provider、range mode、begin/end、chart id/version、run/snapshot、selected bucket/series 和 list filters，并通过单元测试验证 URL/query 参数往返稳定
- [x] 2.2 将 workbench toolbar profile/range/chart controls 接入 PageQueryState，验证修改 profile/range/chart 会清除 selected bucket/series 并刷新 chart/evidence pane target
- [x] 2.3 将 evidence list-local filters 接入 PageQueryState，验证修改 text/status/severity/owner/component 只刷新 evidence pane，不改变 chart query 参数
- [x] 2.4 增加 invalid selection handling，验证未知 run/bucket/series/profile/range 会显示 validation failure 并清空旧 evidence rows

## 3. Chart And Evidence Pane Integration

- [x] 3.1 把当前 Bug Trend Chart.js reference chart 注册为 workbench chart pane renderer，并通过 browser test 验证 chart 使用 workbench profile/range state 渲染
- [x] 3.2 为 reference chart 增加 bucket/series selection event，验证点击 `new_critical_high` bar 后 evidence pane 请求对应 bucket/series 并显示匹配 ticket rows
- [x] 3.3 实现 Clear selection 行为，验证清除后 evidence pane 回到 visible-range evidence state
- [x] 3.4 实现 chart evidence capability UI 状态，验证 `bucket_series` 启用点级 drilldown、`range_only` 显示 range evidence、`summary_only/unsupported` 清空旧 rows 并显示明确状态
- [x] 3.5 增加 evidence export/link consistency check，验证当前 selection 下导出的 ticket rows 与页面展示 rows 一致

## 4. Grafana Stock Integration Feasibility

- [x] 4.1 扩展 Grafana render config or artifact metadata，使 evidence-backed panels 明确携带 run/snapshot、bucket、series、chart id/version link fields，并通过 `validate_grafana_artifacts.py` 验证 contract 通过
- [x] 4.2 在 workbench 中挂载 Grafana single-panel/solo embed pane，验证 PageQueryState 变化会更新或 reload panel URL variables，且 chart pane 不显示完整 Grafana dashboard chrome
- [x] 4.3 提供 separate full Grafana dashboard diagnostics/admin link，验证 normal analysis 默认停留在 compact panel embed 而不是 full dashboard iframe
- [x] 4.4 实现 Grafana data-link 到 workbench selection sync 的 feasibility path，验证用户点击 Grafana bug trend bar 后不离开 unified UI 且 evidence pane 刷新到对应 tickets
- [x] 4.5 记录 feasibility gate 结果：若 stock panel embed 不能稳定同步 run/bucket/series，则新增 follow-up change 或 task note 进入 Grafana App/Scenes spike，并验证当前 change 仍保留 reference chart drilldown

## 5. AI Pane Integration

- [x] 5.1 将 AI Dashboard Workflow 或 AI Base surface 注册为 optional AI pane，验证 AI Base configured 时 pane 可打开并显示当前 profile/range/chart context
- [x] 5.2 实现 safe workbench-to-AI context payload，验证 payload 包含 profile/provider/range/chart/selection 且不包含 credentials、tokens、private paths 或 raw provider secrets
- [x] 5.3 验证 selected bucket/series evidence context 可被 AI pane 使用于解释请求，并保留 provider/profile/run or snapshot provenance
- [x] 5.4 验证 AI Base disconnected 时 AI pane 显示 unavailable diagnostics，且 chart/evidence/settings/publish panes 仍可用

## 6. Local Runtime And Navigation

- [x] 6.1 扩展 local launcher/proxy 配置，使 Dashboard、Grafana 和 optional AI Base 启动后只打开 workbench URL，并通过 manual or scripted run 验证只产生一个用户入口
- [x] 6.2 在 Dashboard navigation 中增加 workbench entry，并通过 template/view tests 验证 legacy full-page URLs 仍可访问
- [x] 6.3 增加 service health diagnostics pane，验证端口占用、Grafana unavailable、AI Base unavailable 均显示 scoped next action

## 7. Validation And Closure

- [x] 7.1 添加 focused backend tests for PageQueryState、pane registry、evidence selection validation and unsupported states，并验证对应 pytest targets pass
- [x] 7.2 添加 focused browser/E2E test：打开 workbench、点击 chart bar、下方 evidence list 刷新、清除 selection、切换 unsupported chart 清空旧 rows，并验证测试通过
- [x] 7.3 验证 Grafana artifact contract、Grafana parity comparison 和 AI dashboard API surface focused tests pass
- [x] 7.4 运行 `python manage.py check`、`python scripts/check_file_size_limits.py --include-untracked`、`python scripts/check_diff_whitespace.py --include-untracked` 并确认无阻断问题
- [x] 7.5 更新相关 docs/runbook，验证文档说明 one-window workbench launch、chart-to-evidence behavior、unsupported evidence states 和 rollback path
- [x] 7.6 运行 `openspec validate enable-unified-metrics-workbench-ui --strict` 并确认 change 通过

## 8. High-Density Workbench Interaction Upgrade

- [x] 8.1 实现 chart/evidence horizontal splitter，支持上下拖动、双击恢复默认值、最小高度保护，并验证拖动不改变 PageQueryState、selected bucket/series 或 evidence filters
- [x] 8.2 实现 main/AI vertical splitter 和 AI right-rail collapse/expand，支持左右拖动、窄 rail 恢复、最小/最大宽度保护，并验证 chat iframe/context、pending approval 和 artifact state 不因 layout 操作丢失
- [x] 8.3 将 Bug Trend chart pane 折叠/展开接入 layout state，折叠后只保留 chart header 和 selected bucket/series summary，并验证 evidence table 获得额外高度
- [x] 8.4 增加 evidence table high-density toolbar，支持字段显隐、可见字段多字段排序、selected count、bulk action 和 export，验证这些 view-state 不改变 provider truth 或 chart selection
- [x] 8.5 增加 evidence ticket checkbox selection，支持单选/多选/select-all，验证 selected tickets 作为 explicit working set 与 chart bucket/series selection、evidence filters 分开保存
- [x] 8.6 增加 evidence 内部 ticket detail pane，点击单个 ticket 时展示 normalized ticket fields、summary、latest activity、links 和 local actions，验证它不 iframe Jira/HSD-ES full page 且关闭/resize 不清空 ticket list
- [x] 8.7 更新 workbench-to-AI context payload，使 selected-ticket working set 可作为 bounded AI grounding 输入，并验证 payload 不包含 credentials、tokens、private paths、raw provider exceptions 或外部 provider session data
- [x] 8.8 增加 responsive/high-density UI inspection：desktop 宽屏、窄屏和 AI collapsed rail 状态下 chart、ticket list、ticket detail、AI pane 和 bottom service status 不重叠、不遮挡、文本不溢出
- [x] 8.9 增加 focused tests/browser smoke 覆盖 splitter resize、pane collapse、table columns/sort、ticket selection、ticket detail lazy load、AI context separation，并重新运行 `openspec validate enable-unified-metrics-workbench-ui --strict`
- [x] 8.10 增加 Workbench 主导航状态恢复：保存最后一次有效 same-origin `/workbench/` query URL，拒绝外部 URL，并验证从其它 Dashboard 页面返回时不会丢失 profile/scope/range/chart selection
- [x] 8.11 明确 AI Base disabled/unavailable 的运行时边界：页面只显示准确状态、diagnostics 和一键 launcher command，不在 web request 中 on-the-fly 启动外部服务
- [x] 8.12 修复 unified stack launcher lifecycle state source，确保 final stale-process cleanup/audit 不会误停当前 Dashboard/Grafana lifecycle process
- [x] 8.13 接入 AI Base `embed=workbench` compact chat surface，验证 iframe 不显示完整 AppShell navigation、session setup sidebar、session files/details panel 或内部 status chrome
- [x] 8.14 增加 Dashboard global navigation/main work area splitter，支持左右调整并持久化 sidebar 宽度
- [x] 8.15 增加 scope-bound profile/provider synchronization，验证切换 scope 后 toolbar 和 server PageQueryState 均使用正确 provider profile
- [x] 8.16 固化 Dashboard-to-AI Base compact embed contract，传递 `workspace_key` 和 Dashboard agent id，并验证 AI Base 使用固定 workspace/agent 创建或过滤 chat session
- [x] 8.17 统一 Workbench button/input 高密度样式，去掉图表 pane 内重复标题/外层 box，减少无效空间
- [x] 8.18 增加通用 Chart.js legend/tooltip rendering，使用 dataset metadata 解释不同颜色曲线/柱状图

## 9. Dashboard AI Adapter Principle

- [x] 9.1 抽出 Dashboard-owned AI workbench adapter 模块，例如 `ui_web/ai_base_workbench_adapter.py`，集中负责 AI Base SDK binding request、compact embed URL、context patch、host action handler 和 diagnostics projection
- [x] 9.2 保持 Dashboard standalone mode 为默认可运行路径，验证 `METRICS_AI_SIDECAR_ENABLED=False` 或 AI Base unavailable 时 chart/evidence/ticket detail/scope sync/Grafana preview/publish audit 仍可用
- [x] 9.3 将 WorkbenchView/template 中直接拼接 AI Base `embed=workbench` query string 的逻辑迁入 adapter，并为未来 generic `embed=app-chat` / AI Base SDK `resolveBinding()` 切换保留同一调用面
- [x] 9.4 增加 architecture guard 或 focused tests，防止 provider、chart、evidence、ticket detail 和 core PageQueryState 模块 import AI Base SDK/runtime objects
- [x] 9.5 未来任何 Dashboard AI-assisted feature 必须先通过 adapter 接入，并同时覆盖 standalone mode 与 with-AI mode 的测试

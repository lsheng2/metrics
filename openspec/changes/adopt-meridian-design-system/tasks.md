# Tasks

## 1. Frontend toolchain and tokens

- [x] 1.1 建立开发期工具链 `ui_web/frontend/`，所有依赖固定版本并提交 lock 文件；验证：`npm ci` 成功，且 `npm run check` 可以运行
- [x] 1.2 基于 Radix 色阶定义 DTCG tokens（base/light/dark），生成 `ui_web/static/css/theme.css`；验证：`npm run build:tokens -- --check` 通过；临时删除一个 dark 颜色 token 时，parity 校验失败并报出该 token 名
- [x] 1.3 配置 Stylelint，只允许 token 颜色和字体；验证：`npm run lint:css` 通过，在页面 CSS 中写入 hex 颜色时报错
- [x] 1.4 增加 `contrast-pairs.json` 和对比度检查；验证：`npm run qa:contrast` 在 light/dark 下 0 失败
- [x] 1.5 增加 `qa-browser.mjs`（Playwright + axe，覆盖两种主题和两种视口）；验证：对 demo server 运行 `npm run qa:browser`，能输出每个路由的结果
- [x] 1.6 在 `AI_CONTRACT.md` 第 4 节和 `openspec/docs/validation/ui-change-quality-gate.zh.md` 中写入 gate 命令；验证：文档中的命令可以照抄运行

## 2. Vendored runtime assets

- [x] 2.1 用 `build-vendor.mjs` vendored htmx、Chart.js 及插件、Mona Sans / Geist Mono 字体、按使用裁剪的 Iconoir 子集，并写入带 sha256 的 `asset-manifest.json`；验证：`npm run build:vendor -- --check` 通过
- [x] 2.2 删除 Bulma、`vendor_fallbacks.css/js` 和 vendor fallback 测试；验证：模板中没有 CDN URL，页面只引用 `{% static 'vendor/...' %}`

## 3. Foundation, shell and theme

- [x] 3.1 编写 foundation primitives（现按关注点拆分为 `css/foundation/*.css`），用 tokens 实现 Bulma 兼容的 primitives，并新增 page header、filter toolbar、stat、health、avatar、empty state、chip disclosure；验证：`ui_web/tests/test_dashboard_ui_design_system.py` 通过
- [x] 3.2 建立服务端导航注册表 `ui_web/navigation.py` 和 context processor，渲染分组侧边栏、面包屑、可折叠侧栏和手机抽屉；验证：导航相关 Django 测试通过，并在浏览器中检查 `aria-current`、折叠持久化和 Esc 关闭抽屉
- [x] 3.3 实现 light/dark/system 三态主题，首帧前生效，并派发 `dashboard:themechange`；验证：`qa:browser` 的主题一致性检查通过，刷新页面时没有闪现另一主题
- [x] 3.4 实现命令面板（Ctrl/⌘+K 或 `/`，方向键、Enter、Esc）；验证：在浏览器中只用键盘完成一次跳转
- [x] 3.5 增加图表主题桥 `DashboardCharts`，系列颜色只来自 tokens；验证：在 Bug Trend 页面切换主题后，图表重新着色且选择状态保留
- [x] 3.6 编写具有约束力的 `frontend-design-requirements.md`，并同步更新 AI contract、Copilot/agent/skill 入口、UI skill overlay、`ui-design-system.md`、README 和各 docs 索引；验证：`test_dashboard_ui_design_system.py` 与 `test_ui_design_baseline_gate.py` 通过
- [x] 3.7 升级体积门禁并拆分超限文件：
  - 规则覆盖所有文件类型，未认领即失败，glob 分段匹配，legacy allowance 增量为 0（临时冻结，见 3.10）；
  - 拆分 `css/foundation/`（13 个文件）、`css/shell/`（6 个文件），从 `shell.js` 拆出 `command-palette.js`，从 `main.js` 拆出 `table-interactions.js`，`data_health.html` 拆为 2 个 partial；
  - 建立 `ui_web/static_assets.py` 资源清单。

  验证：`scripts/tests/test_check_file_size_limits.py` 通过；全仓库扫描 0 个未认领文件；changed 模式 PASS；`npm run check` 通过；在浏览器中确认拆分后的资源无 404、样式和命令面板正常。
- [x] 3.8 回顾全部 64 个 checkpoint，把重设计过程中积累的 UI/UX、字体、配色、布局、组件、图表、表格、工具链、测试、真实浏览器复查、流程和 pitfall 经验（约 235 条，去重后）写入文档：
  - `frontend-design-requirements.md`：中文摘要、§2 文件架构与资源清单、§7 规则 13–18、§8–§10；
  - 新增 `frontend-design-recipes.md`（精确 token 值、选择器、markup 和每条规则背后的 pitfall）；
  - 新增 `frontend-delivery-playbook.md`（工具链、文件架构、体积门禁、测试契约、ego-browser 复查、调试 pitfall、工作规则、final gates）；
  - `AI_CONTRACT.md` 新增 §7 Frontend Design Non-Negotiables；
  - 按代码核对并修正与实现不符的旧描述。

  验证：`test_dashboard_ui_design_system.py` 通过；文档中无旧路径（`foundation.css`、`shell.css`、`DASHBOARD_STYLESHEETS`）；体积门禁和 whitespace 门禁 PASS。
- [x] 3.9 建立 UI 几何契约注册表 `ui_web/tests/ui_geometry_contract.py`，不再让每次上下文压缩后都要从测试代码里重新推导阈值：
  - 30 条像素级规则分属 9 个界面（shared、tables、provider-tabs、editors、provider-setup、provider-editor、scope-library、workbench、reports），每条记录 key、阈值、单位、比较方式、测量对象、视口和执行模块；
  - 浏览器测试和 support 模块改为引用常量，或在 `page.evaluate` 中读取 `limits.<KEY>`，不再写字面量阈值；
  - `python ui_web/tests/ui_geometry_contract.py` 按界面输出 Markdown 表；
  - meta-test `test_ui_geometry_contract.py`：每条规则唯一声明且必须有测试执行，`enforced_by` 与实际引用一致，扫描所有在浏览器里测量的测试模块并拒绝字面量阈值（不论是否已 import 注册表），CLI 可运行；
  - baseline gate 的三个几何测试改为收集全部违规后一次失败，每行一条 `RULE=limit: metric=value @ 页面 视口`，一轮就能看到所有回归；
  - AI contract、requirements 规则 18、playbook §4.1/§4.3/§6.4/§7 和 `ui-design-system.md` 改为指向注册表，不再复述数值。

  验证：`test_ui_geometry_contract.py` 通过；改动过的浏览器测试和 support 模块所在测试通过（剩余失败均已在 HEAD 上复现）；文档中不再复述阈值数值。
- [x] 3.10 拆完前端存量超限文件，删除对应的 legacy allowance：
  - `main.css` 拆为 14 个 `css/pages/*.css`，`main.js` 拆为 9 个 feature 模块（加上 `table-interactions.js` 共 10 个，按 `FEATURE_SCRIPTS` 顺序初始化），两者删除；
  - 4 个超限模板拆出 6 个 partial：`partials/bug_trend_scope_source_query.html`、`partials/bug_trend_scope_semantic_mapping.html`、`partials/bug_trend_scope_lifecycle_guide.html`、`partials/provider_profile_credentials.html`、`projects/reports/stage_series.html`、`projects/reports/stage_drafts.html`；
  - 3 个超限测试文件拆出 `tests/fixtures/business_scenarios.py`、`tests/fixtures/ui_web_facade_harness.py`、`test_unit_task_sort_value_handling.py`、`test_api_ui_web_member_group_filters.py`，拆分前后收集到的测试 ID 集合一致（94 个）；
  - 删除 `main.css`/`main.js`、`legacy-page-templates`、`legacy-python-tests` 共 4 组条目；剩余 3 组 allowance 由各自 owner 按拆分计划处理：report editor 脚本（唯一的前端 allowance）、AI stack launcher、2 个 Python 模块。此后页面层继续按 feature 拆分，现为 17 个页面样式表和 11 个 feature 模块（design 决策 10）。

  验证：体积门禁 `--include-untracked` PASS，`scripts/tests/test_check_file_size_limits.py` 通过；scope、provider、report 的模板测试和拆分后的测试通过（剩余失败均已在 HEAD 上复现）；浏览器复查拆分后的页面，无 404，交互正常。

## 4. Page migration

- [x] 4.1 首页改为按任务分组的 launchpad；验证：首页 Django 测试通过，并在浏览器中检查 light/dark 和手机宽度
- [x] 4.2 迁移 Bug Trend、Data Health 和 Workbench；验证：对应的 view 测试和浏览器测试通过，并截图复查
- [x] 4.3 迁移 Team/Developer Velocity（图表并入 content partial，删除四个 chart partial 路由）、Forecast、Current Tasks 和 Pull Requests；验证：velocity、forecast、tasks、PR 相关测试通过，并截图复查
- [x] 4.4 缺失值统一通过 `or_dash`、`status_tag` 输出弱化的 "—"，`timestamp` 和 `age_seconds` 同样处理；验证：`test_filter_dashboard_format.py` 与 scope library 的 view 测试通过
- [x] 4.5 迁移 AI Dashboard Workflow 页面：加 page header，readiness 改为卡片，表单使用网格，空表格使用 empty row；验证：AI workflow 相关测试通过，并截图复查
- [x] 4.6 迁移 Provider Setup、Provider Profile Config 和 Scope Config 表单：
  - 编辑器统一为“一张卡片”：表单是唯一的 box，左侧 2px `--provider-color` 色条；provider tabs 贴在卡片顶边，选中 tab 的下划线用 provider 色；手机宽度下 tab 条横向滚动并隐藏 meta；
  - Scope Config 重写主模板和 5 个 partial（source query、semantic mapping、metadata、metadata validation、query builder controls）：所有可编辑内容放进 tab body，用 hairline 分节，不再嵌套方框；source-mode 开关改为 radiogroup，选中态只由 `:has(> input:checked)` 表达；
  - required 提示改为 help 之后右对齐的弱化文字；dirty marker 去掉无效的 `is-light`；状态和消息统一用 `status_tag`、`.message`；
  - 修复多值 textarea 显示字面 `\n` 的缺陷：10 处 `join:"\n"` 改为 `join:"&#10;"`，新增回归测试 `test_shouldRenderMultiValueTextareasOneValuePerLine`；
  - 规则写回 requirements 中文摘要、§6.2、§6.9 和 §7 规则 19，recipes §4.1/§4.3/§5/§7/§10/§11，playbook §4.3/§5.2/§6.2，以及 `AI_CONTRACT.md` §7（Editors、Learnings travel with the work）。

  验证：scope/provider/data health/design system/geometry 共 13 个测试文件 108 passed；`npm run check` 通过（对比度 152 对 0 失败）；`qa:browser` 覆盖 Provider Setup 列表、provider editor、Scope Config（已有 scope 与新建 HSD-ES）4 个路由 × light/dark × 1440/390，共 16 项 0 失败；体积门禁和 whitespace 门禁 PASS；ego-browser 第 44–45 轮在 light/dark、1440/390 宽度下复查，无横向溢出、无 JS 错误、无字面 `\n`。
- [x] 4.7 迁移 Scope Library 和 Scope Audit：
  - Scope Library 重写：lifecycle 改为带编号徽标的步骤条，不画连接线；readiness matrix 移入 popover（ghost 按钮加图标，宽面板限高并可滚动，手机上表格变为卡片）；results bar 显示数量和 binding policy；
  - 表格：列宽只写在 `col` 上，合计 89rem，宽屏不出现横向滚动；较窄屏幕上 Name、Actions 列 sticky（背景不透明、hover 同步、表头 z 高一级、菜单展开时提升到 dropdown 层）；行操作统一为 Edit 加 More 菜单，Audit/Duplicate/Export/Archive 放进菜单，Delete 只对已归档行出现；Provider 列改用新的 `provider_tag` filter，修复截断；
  - `.workbench-menu` 基础规则迁入 foundation `work-items.css`；`table-interactions.js` 的 `fitTableMenu` 在滚动表格内让菜单向上翻转或撑高容器，菜单不再被裁切；
  - Scope Audit 重写：page header（scope 名称、config hash、Bug Trend 和 Edit Scope）；Data coverage 改为 `stat-grid is-compact`，缺值显示 "—"；Observed values 卡片头带 count badge；Count 列用 `is-numeric`；
  - foundation card 模式修复：子元素保持自然宽度，tag 不再撑满整行；`is-numeric` 在卡片中恢复左对齐；light 主题下放在 canvas 上的 muted 条加 1px 边框；
  - 删除 `scope-config.css` 中的 `.scope-library-*` 规则；tag 不再使用 `is-light`；
  - 规则写回 requirements §3.1、§6.3、§6.6，recipes §4.5、§6.2、§7，以及 `AI_CONTRACT.md` §7（Primitives first）。

  验证：scope library、audit、provider、action、filter 测试 57 passed；baseline gate、data health、workbench、provider setup 相关测试中，readiness 表缺少表格契约的一项失败已修复，修复后复跑 25 passed 和 56 passed；`npm run check` 通过；`qa:browser` 覆盖 Scope Library 和 Scope Audit × light/dark × 1440/390，共 8 项 0 失败；size 和 whitespace 门禁 PASS；ego-browser 第 46–47 轮复查行菜单不被裁切、sticky 列、readiness popover（桌面和手机）、手机卡片模式，无横向溢出、无 JS 错误。
- [x] 4.8 迁移 Grafana selection，并新增不依赖 context 的 404/500 错误页：
  - 新增 `standalone_base.html` frame（`css/shell/standalone.css`）：只有 brand header 和一个居中面板，不加载 script，也不依赖 context processor；Django 用空 context 渲染 `500.html` 也能正常显示；
  - 主题 no-flash 脚本拆为 `partials/theme_bootstrap.html`，brand 拆为 `partials/app_brand.html`，`base.html` 与 standalone frame 共用；home 链接用 `{% url ... as %}` 加 `default:'/'`，不写死 `/`；
  - 404/500 面板依次为图标、eyebrow、标题、正文、meta（请求路径或时间）和操作区，操作区只有一个 primary；不展示 `exception`；“Go back”默认隐藏，有浏览历史时才显示；
  - Grafana selection bridge 改为继承 standalone frame，加 `is-embedded`（surface 背景）；在 iframe 内保持原 postMessage 行为；顶层打开时显示说明文字，以及带当前选区 query 的 “Open in Workbench” 按钮；
  - 规则写回 recipes §2.1、§2.8，requirements §5，以及 `AI_CONTRACT.md` §7（User flow）。

  验证：新增 `test_error_pages.py`（404 走真实 client，500 走 `defaults.server_error`），扩展 bridge 测试；error pages、workbench chart views、frontend assets、dashboard shell browser 测试共 21 passed，tweak 后复跑 18 passed；`npm run lint:css` 通过；ego-browser 第 48 轮和 48b 轮覆盖 404/500 × light/dark × 1440/390，以及 bridge 640×360 的 status 态和 fallback 态，无横向溢出、无 JS 错误，字体已加载。
- [x] 4.9 迁移项目详情、报告模板和报告阶段页面：
  - A 组（`projects/list`、`detail`）和 B 组（`report_templates/*`）：page header 加 command bar；状态统一用 `|status_tag`；Archive 改为中性按钮或 danger-outline；表格使用共享 density 和 cardable 契约；
  - C 组（stage workbench、drafts、publications、series、run、preparation、meetings 等 12 个模板）：新增 `partials/form_error_summary.html`，禁止直接输出 `{{ form.errors }}`（design-system 测试守护）；卡片内平铺表格的边缘单元格与卡片标题左对齐（`ui_design_browser_metrics_support.py` 的 `tableEdgeFailures` 守护）；修复 assist 抽屉在跨过手机断点时的回归（增加 drawer closing 态）；
  - D 组（editor、`register_blocks`（新拆出）、toolbar、pinned blocks、period、recovery、assist、publication）：每个区域只有一个 `is-primary`；command bar 包含导出控件和 `status-line`；band/row 使用不透明 surface；矩阵空单元格改用 `data-matrix-empty` 标记，两个 browser 测试的选择器在同一变更中更新，避免退化为永远通过；`report state` msgctxt 区分“已定稿”状态和“定稿时间”；JS 文案从 `data-message-*` 读取；`:empty` 挂载点和 `details` 内层 grid 规则见 recipes §12.2；
  - 原计划的 `.dashboard-form-grid` token 化并入 4.10，与断点迁移一起验证。

  验证：report browser 测试按文件、独立进程运行 16 个文件，共 72 项，71 passed。剩余 1 项是 `visualTemplateLibrary` strict 选择器，属于已登记的存量失败。`test_report_query_browser` 在 4 进程并行时 daily generate 超过 15s 超时，单独运行通过（58.9s）。非浏览器 view 测试 63 passed；另有 2 项失败（"Run stage report" 缺失、finalize 返回 503），已在 HEAD 复现。node 测试 26/26 通过。与 HEAD 的模板契约对比只移除了 `data-server-disabled`，它在 HEAD 中就是 draft-only 死分支。size、whitespace、`git diff --check`、`npm run check`（对比度 152 对，0 失败）、`lint:css` 均通过。已复查测试证据截图：editor 桌面和手机、publication、history 矩阵、assist、meetings。
- [x] 4.10 CSS 清理，并退役 Bulma 兼容层：
  - z-index 全部改用 layer token，`css/pages/*.css` 中不再有原始 z-index；foundation 只在按钮组和输入组内部保留局部叠放值 1/2。计数统一使用 `.count-badge`；删除 `.provider-status-cell .tag` 的 margin hack；
  - 删除死模板 `partials/bug_trend_scope_metadata_options.html` 和 `.scope-metadata-*` 规则，修正 `bug-trend-scope-config-micro-architecture.zh.md` 中的引用；
  - workbench evidence 表头 sticky，背景不透明；`.is-missing-required` 的 padding 和 `workbench-*.css` 中的硬编码值改为 token；bug-trend 图例色块统一为与 Chart.js legend 相同的 8px；
  - 模板中的 Bulma 布局、排版、间距 helper（`notification`、`title`、`columns`、`level`、`is-size-*`、`m*-N`/`p*-N` 等）和 `tag is-light` 迁移到 Meridian 原语。toast 改用 DOM API 构建，删除 compat CSS；`is-light` 只保留给不带语义色的 ghost `.button`；
  - 新增两条强制测试：`test_shouldNotRenderRetiredLegacyMarkup` 和 `test_shouldDefineEveryModifierClassUsedInMarkup`；
  - Data Health chip 截断：4.9 卡片化后，展开状态下列宽随内容增长，已不再裁切。卡片模式下，超长 tag 在胶囊内换行，不再静默裁切（`pages/dense-tables.css`）；
  - 细滚动条：`scrollbar-width` 不继承，改为在 `foundation/base.css` 中用 `* { scrollbar-width: thin }`，表格等内部滚动容器不再出现 15px 的经典滚动条；
  - 规则已写回 requirements §6.2、§6.8、§7 rule 8、§9 DoD 第 2/4 条，recipes §2.1、§6.2，playbook 的探针说明，以及 `AI_CONTRACT.md` §7。

  验证：design-system 测试 15 passed。在 HEAD 上反向运行，新测试分别拦下 571 处退役 class、93 处 `tag is-light` 和 176 个未定义 modifier。非浏览器测试 666 passed，另有 6 项存量失败（`_validate_page` 替身等），在 HEAD 上可复现。22 个浏览器测试文件以 3 进程并行运行，18 个文件全部通过；其余失败或是已登记的存量失败，或是并行负载下的抖动（`report_query_browser` 单独运行时，在 HEAD 和本分支上都通过）。收尾后复跑 shell、geometry、baseline gate、data health 和 scope audit，共 37 passed。size、whitespace、`git diff --check`、`npm run check`（对比度 152 对，0 失败）和 `lint:css` 均通过。ego-browser 第 55–56 轮复查了 toast（桌面右下角 416px、手机全宽）、loader 居中、help-tip hover 和细滚动条；6 个高密度页面在 1440 和 390 下、所有 details 展开时，被裁切和被折行的 tag 都是 0；注入超长值后，tag 在卡片内换行。
- [x] 4.11 Shell i18n：zh_Hans 覆盖新增的 shell 文案；验证：切换到 zh-hans 时 shell 中不出现未翻译的英文
  - 目录：新增 195 条 zh_Hans 译文，目录共 648 条（其中 15 条带 msgctxt），`.mo` 用 polib 编译；
  - 服务状态改为 `pgettext_lazy('service state', ...)` 词表配合 `service_state_label` 过滤器，原值仍保留在 `data-service-status`；toast 和命令面板的提示文案改为读取 `data-message-*`，脚本中不再保留英文兜底；命令面板支持中英文搜索；状态栏时间改为 24 小时制；命令改用 `%(command)s` 占位符传入；
  - 页面名统一取自导航注册表：删除 11 个页面中重复导航标签的 `title`/`page_title`。此前像 "Bug Trend Indicator" 这样的旧标题只在整页加载时出现，经 htmx 切页后又变回导航标签。3 个深层页面（Scope Audit、Scope Config、Profile Config）的标题和上级 crumb 改为 `{% trans %}`；
  - 新增 `ui_web/tests/test_i18n_catalog.py`，共 5 项检查：目录完整性、`.mo` 与 po 同步、占位符一致、shell block 中无裸写英文、zh-hans 首页 shell 中无白名单以外的英文；
  - 规则已写回 requirements 中文摘要、§7 rule 10、§9 DoD 第 11 条，recipes §2.2、§2.4、§11，playbook §6.2，`AI_CONTRACT.md` §7，以及 design.md 的 Non-Goals 和决策 11。

  验证：补译之前，审计列出 192 条缺失译文；在 HEAD 模板上，新 gate 拦下 18 处 shell block 裸写英文；`.mo` 过期时，同步测试和 shell 测试都会失败。i18n 及相关视图测试共 172 passed；shell、baseline gate、workbench 和 scope 相关测试 29 passed。ego-browser 第 58 轮：zh-hans 下状态栏、命令面板（“浅色”“深色”“侧边栏”“工作台”“bug”都能命中）、toast（“请求失败”/“关闭”）、404/500、bridge 和手机 shell 中，剩下的英文只有种子项目名、HTTP 状态行、URL 和 UTC。第 59 轮：13 个侧栏页面和 3 个深层页面的标签页标题、crumb 与页面名全部为中文，0 泄漏。size、whitespace 和 `git diff --check` 检查均通过。

## 5. Integration verification

- [x] 5.1 运行 `ui_web` 的非浏览器测试，以及迁移过的浏览器测试；除已知、与本 change 无关的既有失败外全部通过

  验证（最终代码，每个文件单独进程）：87 个非浏览器文件 672 passed、27 subtests passed，另有 6 项存量失败，均已在 HEAD worktree 上复现：stage pagination ×2 和 project_run_views ×2 是测试替身缺少 `_validate_page`，project_report_views ×2 是 "Run stage report" 缺失和 finalize 返回 503。22 个浏览器测试文件 90 passed，另有 4 项存量失败，同样在 HEAD 上失败：bug-trend ×2 和 monkey ×1 mock 了已删除的 `create_jira_client`；`visualTemplateLibrary` 的 strict 选择器匹配到 5 个 `template_choice`。`scripts/tests/test_check_file_size_limits.py` 与 tasks/forecast/velocity 测试 222 passed；node 测试 5 个文件 26/26 通过。
- [x] 5.2 对导航页面和深层页面（项目、报告、scope config）运行 `npm run check` 与 `npm run qa:browser`，覆盖 light/dark × desktop/phone，结果为 0 失败

  验证：`npm run check` 通过（tokens 与 vendor 无漂移，stylelint 无告警，对比度 152 对、0 失败）。qa:browser 以封闭模式运行：跨域请求全部拦截，外部 script、stylesheet、font 判为失败。导航发现的 13 个路由共 52 项检查、0 失败；13 个深层路由（项目 ×2、stage 报告、报告模板列表与详情、Scope Audit、Scope Config、Provider Setup 新建与 2 个 profile、带选中 bucket 的 Workbench、Workbench 范围、Bug Trend 范围）共 52 项检查、0 失败。首轮运行时 Workbench 超时：折叠的 Grafana iframe 会立即加载，而 3001 端口上的本机进程不响应。现在 iframe 改为展开时才加载，并跟随当前主题（`grafana-embeds.js`，有浏览器测试覆盖）。
- [x] 5.3 在临时 `STATIC_ROOT` 下运行 `collectstatic --noinput` 并成功；隔离环境下 `manage.py check` 通过

  验证：用 `scripts/validation/run_report_authoring_tests.test_settings` 构造隔离 settings，`check` 报告 0 个问题。collectstatic 输出到临时 `STATIC_ROOT`：在当前生效的配置下复制 274 个文件（Django 6 会忽略旧的 `STATICFILES_STORAGE`，实际使用 `StaticFilesStorage`）；改用 WhiteNoise `CompressedManifestStaticFilesStorage` 后同样是 274 个文件，814 个 post-processed，所有 CSS `url()` 都能解析，manifest 中 css/js/vendor 条目共 143 个。
- [x] 5.4 运行 `scripts/check_file_size_limits.py`、`scripts/check_diff_whitespace.py` 和 `git diff --check`，全部通过

  验证：`check_file_size_limits.py --include-untracked` 结果为 PASS（checked=302），只剩 `report_editor/index.js` 和 `template_builder.js` 两个登记的 legacy 脚本，且行数都低于 HEAD；`check_diff_whitespace.py --include-untracked` 结果为 PASS；`git diff --check` 无输出。
- [x] 5.5 在真实浏览器中对每个页面截取 light 和 dark 的 after 截图，并复查
  - 复查中发现 Workbench 在 1024px 以下仍保持 IDE 框架，导致 splitter 错位、内容被裁切。现改为可滚动的堆叠页面，1024px 及以上保持 IDE 布局（recipes §2.7）；
  - Workbench evidence pane 中出现两份筛选表单，加上 card 的 `min-height:100%`，在 390px 下留出约 180px 空白。共享 partial 现通过 `workbench_evidence` 改用 Workbench 的 URL 状态表单，每个区域只渲染一份；`min-height` 只在 IDE 模式下生效（测试 `test_shouldRenderOneUrlStateEvidenceFilterInsideWorkbenchEvidenceCard`）；
  - 手机上 evidence 筛选是 6 行单列，与上方两列的 toolbar 不一致。删除 540px 单列规则后，1024px 以下统一为两列，Text 和操作按钮占满整行；Bug Trend 在 390px 下的表单高度从约 330px 降到 209px。代码中的 viewport 断点现在只剩 768px，以及 Workbench 的 1024px/1023px；
  - 规则已写回 recipes §2.7 和 §3.4、requirements（断点规则 4 和“只渲染一次”）、playbook §5.2 和 §6.4，以及 `AI_CONTRACT.md` §7。

  验证：ego-browser 第 68 轮在最终代码上覆盖 34 个路由（导航发现的 21 个，加 13 个深层页，含 404/500 预览），light/dark × 1440/390 共 136 张截图，长页面另补 bottom 截图。自动探针检查主题、页面级横向溢出、Bulma 残留和未样式化按钮，problems 为空。第 69 轮生成 12 张联系表，并逐张复查。第 67 轮复测 Workbench evidence（390/1000/1440 × light/dark）：只有 1 份表单且位于 card 内，不会触发 bug-trend 请求，Clear selection 只有 1 个，横向溢出为 0，筛选往返为 83→1→83 行。第 70 轮确认 Bug Trend 在 390px 下为两列（167px × 2），横向溢出为 0。
- [x] 5.6 运行 `openspec validate adopt-meridian-design-system --strict` 并通过

  验证：`npx --no-install openspec validate adopt-meridian-design-system --strict` 输出 "Change 'adopt-meridian-design-system' is valid"。

## 6. Closure review fixes

- [x] 6.1 资源加载口径（发现 1）：spec、`AI_CONTRACT.md`、requirements 和 playbook 写明共享层只走唯一资源清单，报告专属的样式表、脚本和 ES module 只由页面模板的 `extra_css`/`extra_js` 加载
  - `test_frontend_assets.py` 中原来的脚本测试扩展为 `test_shouldLoadEveryTopLevelAssetOnceThroughTheManifestOrItsPageTemplate`，同时覆盖顶层 `js/*.js` 和 `css/*.css`：既不在清单中、也不由页面模板加载的孤儿资源会失败；页面模板重复加载清单中的资源也会失败。

  验证：4 passed。临时放入一个孤儿 CSS 文件后测试失败，删除后恢复通过。
- [x] 6.2 主题切换位置与框架例外（发现 2、6）：spec、proposal 和 design 改为"侧栏底部的主题切换，或命令面板的主题动作"；"每个颜色 token 同时定义 light/dark"限定为主题 token，provider 身份色和报告 paper 色只在 base tokens 中定义一次；"每个页面渲染同一框架"补充例外：404/500 和 iframe 桥接页继承 `standalone_base.html`。

  验证：两个 change 的 `openspec validate --strict` 均通过。
- [x] 6.3 页面 CSS 不再使用 `!important`（发现 3）
  - Workbench 工具栏控件都带 `is-small`，foundation 已经给出相同的高度，删除冗余的 `!important` 尺寸和 padding 覆盖；
  - dirty 和 required-missing 状态改为 `foundation/forms.css` 提供的 hook，聚焦时 dirty 边框保持不变；页面层不再争夺控件的 border 和 box-shadow；
  - `.has-help-tip` 的 `overflow: visible` 移到 `pages/dense-tables.css`，改用特异性足够、无需 `!important` 的选择器；
  - stylelint 对 pages、shell 和报告页样式启用 `declaration-no-important`。唯一例外是覆盖导出 HTML 内联样式的那条声明，带写明原因的 disable 注释；
  - 新增 `ui_web/tests/required_field_browser_support.py`，取代 provider 和 scope 测试支持代码中 4 份相同的 JS，并检查 hook 在视觉上确实生效，包括字段处于 `:focus` 时。

  验证：在 pages 样式中插入 `!important`，lint 报错退出（exit 2），还原后通过。负向探测 A：删除 hook 规则后，dirty 测试失败，scope required 测试失败（3 != 0）；探测 B：把 dirty 选择器降为 `.is-dirty-control`，特异性输给 `:focus`，dirty 测试失败。两次探测后 forms.css 都按字节还原。ego-browser 第 73 轮：Workbench 工具栏 8 个控件在 light/dark × 1440/390 下高度都是 28px，横向溢出为 0；Provider 页 missing 边框为 danger 色，dirty 边框为 warning 混合色，聚焦后不变；help-tip 在 hover 时气泡可见，所在 `th` 不裁切。
- [x] 6.4 qa:browser 记录网络失败（发现 4）：`qa-browser.mjs` 增加 `requestfailed` 监听，记录同源、且原因不是 `net::ERR_ABORTED` 的失败请求。

  验证：对 8793 运行，导航路由 52 项检查 0 失败，11 条深层路由 44 项检查 0 失败，没有误报。
- [x] 6.5 Milkdown vendor 哈希校验（发现 5）：新增 `ui_web/frontend/scripts/check-report-editor-vendor.mjs` 并接入 `npm run check`。它把 CRLF 折叠为 LF 后，校验 bundle、metafile、package.json 和 package-lock 的 sha256；`build_report_editor_vendor.py` 的 `sha256()` 也同样折叠换行。

  验证：改动 bundle 的一个字节后脚本 exit 1 并点名该文件，还原后通过。重新生成 manifest 时只有 `package_json_sha256` 变化。
- [x] 6.6 过期表述（发现 7、8）：删除 requirements 中"旧 Bulma 布局类只允许存量"的条款，清理 8 份文档中的 Bulma 表述；修正 playbook 中的 `FEATURE_SCRIPTS` 列表、不存在的 `PAGE_SCRIPTS` 和 legacy allowance 的称谓，requirements 中的 shell 列表（补 `standalone`），以及 design 和 proposal 中的计数（17 个页面样式表、11 个 feature 模块，首页共 59 个资源：41 个样式表、18 个脚本）。`standardize-dashboard-ui-design-system` 中指向不存在 requirement 的 delta header 由 MODIFIED 改为 ADDED。

  验证：全仓 grep Bulma（排除 archive、vendor 和"已退役"这类表述）无残留；两个 change 的 strict 校验通过。
- [x] 6.7 Workbench 选择 chip 在手机上延伸到操作按钮下方（复查时发现；第 68 轮截图中已经存在）
  - chip 的文本放进内层 `span.is-truncated`，完整值写在 `title`；页面 CSS `.workbench-selection-tag` 只占用标题剩下的空间，最宽不超过自身内容；
  - foundation 新增 `.tag > .is-truncated { line-height: var(--leading-tight) }`。tag 的 line-height 为 1，在 overflow hidden 下会裁掉降部字母和下划线；
  - `PHONE_STACK_SCRIPT` 新增两项测量：pane header 中标题组与操作区的重叠量，以及每个 pane 标题的行数；
  - 规则已写回 spec（场景 "A heading carries a long value on a phone"）、recipes §2.7 和 §5、requirements（tags 条目和复查经验）以及 `AI_CONTRACT.md` 的 Primitives first 条目。

  验证：还原模板和 CSS 后，重叠量为 208.53px，测试失败；只保留 `min-width: 0` 时，标题行数为 `[2, 1, 1]`，测试失败。修复后 ego-browser 第 75 轮（390/1100/1440 × light/dark）：3 个 pane 标题都是单行，chip 与 Collapse 之间留出 8px，横向溢出为 0；chip 在 390 和 1100 下截断，1440 下完整显示，文字高 14px、chip 高 20px，`all_open_bugs` 的下划线完整。
- [x] 6.8 在最终代码上重跑全部 gate

  验证（每个文件单独进程）：87 个非浏览器文件 672 passed、27 subtests passed；22 个浏览器测试文件 90 passed。失败项与 5.1 登记的 6 项和 4 项存量失败完全相同。`scripts/tests/test_check_file_size_limits.py` 与 tasks/forecast/velocity 测试 222 passed；node 测试 26/26。`npm run check` 通过：report editor vendor 与 manifest 一致，stylelint 无告警，对比度 152 对、0 失败。qa:browser 覆盖 Workbench（含选中 bucket 的深层 URL）和 Bug Trend × light/dark × 1440/390，共 12 项、0 失败。size、whitespace、`git diff --check` 和隔离环境下的 `manage.py check` 均通过；两个 change 的 strict 校验通过。

## Workflow follow-up

- 按 allowlist 提交，commit 带 Co-authored-by trailer。
- 评审通过后归档本 change。`standardize-dashboard-ui-design-system` 的 delta 已修正（6.6），但 `scripts/validate_ui_design_gate.ps1` 仍按名称校验它，因此本次不归档；由其 owner 归档时同步更新该脚本和对应测试。

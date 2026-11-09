# Proposal

## Why

Dashboard 前端长期依赖 Bulma 默认样式和不断累积的页面级 CSS，存在以下问题：
- 视觉陈旧，信息密度低，也没有暗色主题。
- 导航是一排平铺的顶部菜单。
- 颜色、字体和间距没有单一来源，图表颜色写死在代码里。
- 部分第三方资源依赖 CDN fallback。
- 没有自动化的对比度、可访问性和页面溢出门禁。

用户要求一次彻底的现代化重设计，目标是清新、简洁、高密度、支持 light/dark 切换，并改善用户动线。设计规则要沉淀为后续所有 agent 必须遵守的标准，同时引入现代化的工具、流程和质量保证。

## What Changes

- **BREAKING（前端实现层）**：用 Meridian design system 取代 Bulma。
  - DTCG design tokens 由 Style Dictionary 生成 `theme.css`。
  - `css/foundation/*.css`（按关注点拆分）提供 primitives，并保留模板和测试依赖的 Bulma 兼容 class 词汇。
  - `css/shell/*.css`、`shell.js` 和 `command-palette.js` 提供应用框架。
  - 移除 Bulma CSS 和 `vendor_fallbacks.css/js`；凡是依赖 Bulma 内部样式或 CDN fallback 的代码，都必须改用 Meridian primitives。
  - `ui_web/static_assets.py` 成为唯一的有序资源清单；页面样式和脚本按 feature 放 `css/pages/<feature>.css` 与 `js/<feature>.js`，删除兜底的 `main.css`/`main.js`（分别拆成 14 个页面样式表和 9 个 feature 模块）。
- 新增 light、dark、system 三态主题。主题在首帧渲染前应用，选择持久化保存，图表通过 `DashboardCharts` 跟随主题变化。
- 新的应用框架和用户动线：
  - 分组侧边栏，来源于服务端 navigation registry，可折叠、可调整宽度。
  - topbar 提供上下文和主题切换。
  - 命令面板，快捷键 Ctrl/⌘+K 或 `/`。
  - 手机端改为抽屉式导航。
  - 首页改为按任务分组的 launchpad。
- 所有页面改用共享 primitives：page header、toolbar、stat/KPI、card、dense table、tag/health/avatar、disclosure 和 empty state。缺失值统一显示为 "—"。
- Velocity 页面的图表改为随页面内容一起渲染。移除四个不再使用的 velocity chart partial 路由；任务下钻仍然是独立的 HTMX partial。
- 第三方运行时资源全部本地 vendored 并固定版本：htmx、Chart.js 及其插件、Mona Sans / Geist Mono 可变字体、Iconoir 子集。`asset-manifest.json` 记录每个文件的 sha256。
- 新增开发期前端工具链 `ui_web/frontend/` 和两道质量门禁：
  - `npm run check`：token 漂移、vendor manifest、Stylelint 和 WCAG 对比度检查。
  - `npm run qa:browser`：Playwright + axe-core，覆盖 light/dark 两种主题和 desktop/phone 两种宽度。
- 新增具有约束力的 `openspec/docs/current-baseline/frontend-design-requirements.md`，并同步更新 `AI_CONTRACT.md`、agent 入口、UI skill overlay 和验证文档。
- 升级仓库体积门禁：`.github/file-size-limits.json` 的规则覆盖所有文件类型（模板、CSS、JS、mjs、PowerShell、YAML、Markdown 等），未被认领的文件直接失败；glob 按路径分段匹配。已超限的存量文件登记为临时冻结的 legacy allowance（不得增长，必须写明 owner 和拆分计划，过期条目会让 meta-test 失败）；本 change 拆完全部前端存量超限文件并删除对应条目。
- 浏览器几何约束（padding、行高、控件高度差、溢出容差等）集中登记在 `ui_web/tests/ui_geometry_contract.py`，浏览器测试从注册表读取阈值，不再在测试代码里散落魔法数字。

## Capabilities

### New Capabilities
- `dashboard-design-system`：Dashboard 的设计系统，覆盖以下内容：
  - 视觉 token 的单一来源。
  - light/dark/system 主题。
  - 应用框架导航和命令面板。
  - 共享 primitives。
  - 对比度和可访问性。
  - vendored 运行时资源。
  - 前端质量门禁。

### Modified Capabilities
- `dashboard-ui-baseline`：
  - "Existing frontend stack remains the baseline" 和 "Workbench shell preserves Dashboard UI technology baseline" 中的 Bulma 改为 Meridian design system。
  - "HTMX partials load independent dashboard components" 中，velocity 图表不再作为独立 partial，只保留 velocity 任务下钻。

## Impact

- 代码：
  - `ui_web/static/css/`：新增 `theme.css`、`foundation/`、`shell/`、`pages/`，删除 `main.css`。
  - `ui_web/static/js/`：新增 `shell.js`、`command-palette.js`、`charts.js` 和 10 个 feature 模块（`table-interactions.js` 等），删除 `main.js`。
  - `ui_web/static_assets.py` 与 `ui_web/templatetags/dashboard_assets.py`：有序资源清单及其模板标签。
  - `scripts/check_file_size_limits.py`、`.github/file-size-limits.json`：体积门禁升级及其测试。
  - `ui_web/static/vendor/`、`ui_web/templates/**`、`ui_web/navigation.py` 及其 context processor。
  - `ui_web/urls.py` 与 velocity views：删除 chart partial。
  - `ui_web/frontend/`：仅在开发期使用的 npm 工具链。
- 依赖：
  - 新增开发期 Node 依赖，全部固定版本：style-dictionary、stylelint、playwright-core、@axe-core/playwright 等。
  - 运行时不新增 Python 依赖，也不引入前端框架或 bundler。
- 测试：UI 相关的 Django/Playwright 测试迁移到新 primitives 和 vendored 资源；删除 vendor fallback 测试。
- 文档：新增 frontend design requirements；更新 AI contract、agent 和 skill 入口、UI design system contract 以及验证文档。
- 保持不变：页面 URL、facade、module public API、业务数据以及其余 htmx partial 契约。

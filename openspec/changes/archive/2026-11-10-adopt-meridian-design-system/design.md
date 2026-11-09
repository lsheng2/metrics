# Design

## Context

- 当前 Dashboard 是 Django SSR + HTMX 的模块化单体。
  - 页面由 `ui_web/templates/**` 渲染。
  - 交互依赖 HTMX partial 和少量原生 JS。
  - 图表使用 Chart.js。
- 改造前的样式层：
  - Bulma 0.9 的默认样式，加上持续堆积的 `main.css`（改造中已拆分并删除）。
  - 颜色、字号直接写在 CSS 和图表 JS 中。
  - 部分资源靠 CDN 加 `vendor_fallbacks.css/js` 兜底。
- 模板和测试大量依赖 Bulma 风格的 class 名，例如 `.button`、`.table`、`.tag`、`.box`、`.columns`、`.is-*` 修饰符。
  - Django 测试和 Playwright 测试都以这些 class 作为选择器或断言对象。
- 部署环境是 Intel 内网，运行时不能依赖公网 CDN。
- 运行时只有 Python；Node 只能作为开发期工具链。
- 仓库没有 CI workflow，质量门禁由开发者和 agent 按 `AI_CONTRACT.md` 在本地执行。
- 动机见 proposal.md 的 Why，行为要求见 `specs/dashboard-design-system/spec.md` 与 `specs/dashboard-ui-baseline/spec.md`。

## Goals / Non-Goals

**Goals:**
- 所有视觉决策都有唯一来源（tokens），并能被机器校验：漂移、硬编码颜色、对比度。
- 不改动页面 URL、view、facade 和 module API，只替换表现层；模板改动限于结构和 class。
- 运行时零构建、零 CDN：生成物和 vendored 文件都提交到仓库。
- 让以后的 agent 有可执行的规则文档和 gate 命令，而不是凭风格偏好修改。

**Non-Goals:**
- 不引入 SPA、React/Vue、Tailwind、组件库或打包器。
- 不重写 Milkdown 报告编辑器，只调整它的外层样式。
- 不在本 change 中把 npm gates 接入 CI，仓库目前没有 CI。
- 不改写页面正文中尚未走 `{% trans %}` 的历史英文（例如页内 `h2`）。i18n 的范围是：shell 全部翻译，凡走 `{% trans %}`/`gettext` 的 msgid 都有 zh_Hans 译文（见决策 11）。

## Decisions

### 1. DTCG tokens + Style Dictionary 生成 `theme.css`

- 做法：
  - `ui_web/frontend/tokens/*.tokens.json` 采用 DTCG 格式。
  - 原始色阶取自 Radix Colors（light/dark 两套 ramp），只在构建期解析，不输出为 CSS 变量。
  - `build-tokens.mjs` 输出 `:root`（base）、`:root,[data-theme="light"]` 和 `[data-theme="dark"]` 三个块。
  - `--check` 模式比对已提交的 `theme.css`，并要求每个颜色 token 在 light 和 dark 中都有定义。
- 备选方案：
  - 手写 CSS 变量：无法做漂移检查和成对的对比度校验。
  - Open Props：变量体系太泛，与项目的语义 token 不对应。
  - Tailwind theme：需要 Tailwind 构建，且属于被禁止的平行框架。
- 理由：DTCG 是 W3C 社区格式，Style Dictionary 是事实标准；Radix 色阶本身为 light/dark 都做过对比度设计。

### 2. 自研 foundation primitives，保留 Bulma 兼容的 class 词汇

- 做法：
  - 删除 Bulma。
  - `css/foundation/*.css` 用 tokens 重新实现 `.button`、`.table`、`.tag`、`.box/.card`、`.columns`、`.field/.control`、`.message`、`.tabs` 等 primitives，按关注点拆分（base、layout、typography、buttons、forms、tables、disclosure、feedback、page-patterns、charts、status、work-items、helpers）。
  - 新增 `.page-header`、filter toolbar（`.dashboard-top-toolbar`）、`.stat`、`.health`、`.avatar`、`.empty-state`、`.is-empty-row`、`.chip-disclosure` 等 primitives。
- 备选方案：
  - 继续用 Bulma 0.9 并覆盖主题：Bulma 0.9 没有 CSS 变量和暗色模式，覆盖成本高，难以做到高密度。
  - 升级到 Bulma 1.x：需要 Sass 工具链，默认尺寸依然偏松散。
  - 把 class 全部改为 BEM 或 utility：模板和测试改动量巨大，却不带来用户可见的价值。
- 取舍：Bulma 风格的 class 名现在代表 Meridian primitives，以 `frontend-design-requirements.md` 列出的词汇为准，不以 Bulma 官方文档为准。

### 3. 字体：Mona Sans（可变字宽）+ Geist Mono

- 做法：
  - 用 Fontsource 包 vendored latin 和 latin-ext 两个子集的 woff2，共约 165 KB。
  - 预加载 Mona Sans latin。
  - `--stretch-display` 用于页面标题和 KPI 数值；正文使用正常字宽。
- 备选方案：
  - Inter：过于普遍，也没有字宽轴。
  - 系统字体栈：各操作系统渲染不一致，Windows 上的 Segoe UI 观感偏旧。
- 理由：可变字宽能在不放大字号的前提下拉开层级，适合高密度界面；Geist Mono 用于数字、ID 和代码，等宽对齐效果好。

### 4. light/dark/system 三态主题，首帧之前生效

- 做法：
  - `base.html` 的 `<head>` 内联脚本读取 `localStorage['dashboard-theme']`，默认值为 `system`，在首次绘制前写入 `<html data-theme>`。
  - `shell.js` 负责侧栏底部的切换控件（命令面板的主题动作也通过 `window.DashboardShell` 切换），监听 `prefers-color-scheme` 的变化，并派发 `dashboard:themechange` 事件。
- 备选方案：
  - 服务端 cookie：需要改动 view，还要处理缓存差异。
  - 按时间自动切换：不符合平台惯例，用户难以预期。
- 说明：system 模式跟随操作系统的应用颜色模式（例如 Windows "选择应用模式"），与系统时钟无关。

### 5. 图表主题桥 `DashboardCharts`

- 做法：
  - `charts.js` 通过 `getComputedStyle` 读取 CSS 变量，并缓存结果。
  - 收到 `dashboard:themechange` 时清空缓存，再对所有图表执行 `chart.update('none')`。
  - 数据系列使用 `--color-chart-1`…`--color-chart-8` 调色板和 `--color-series-<key>` 语义 token。同一系列在两种主题下色相一致，只调整明度。
- 备选方案：
  - 在 JS 中复制一份调色板：会与 tokens 漂移。
  - 主题切换后用 HTMX 重新请求图表：会重新取数，并丢失选择状态。

### 6. 服务端导航注册表 + 原生命令面板

- 做法：
  - `ui_web/navigation.py` 定义分组、链接和当前项的匹配规则。
  - context processor `dashboard_navigation` 同时供给侧边栏、面包屑和命令面板。
  - 命令面板基于原生 `<dialog>`，配合 combobox/listbox ARIA 和原生 JS。
- 备选方案：
  - 在 `base.html` 中硬编码导航：入口会分散，面包屑和命令面板无法复用。
  - cmdk、ninja-keys：分别依赖 React 和 web component，与项目技术栈不符。

### 7. 运行时资源 vendored，并用 hash manifest 管控

- 做法：
  - `build-vendor.mjs` 从固定版本的 npm 包复制 htmx、Chart.js、插件、字体，以及按实际使用裁剪的 Iconoir 子集，复制到 `ui_web/static/vendor/`。
  - 同时写出包含 sha256 的 `asset-manifest.json`。
  - `--check` 模式检测缺失文件和内容漂移。
  - Milkdown 报告编辑器 bundle 由 `scripts/validation/build_report_editor_vendor.py` 在 `ui_web/editor_build/` 本地构建，并写出自己的 manifest（bundle、metafile、源入口 `report_milkdown.js`、`package.json`、lockfile 的 sha256）；`npm run check` 中的 `check-report-editor-vendor.mjs` 把 CRLF 折叠为 LF 后重新计算这五个 hash，所以只改源入口而不重建会让 `check` 失败。
- `defaults.py` 声明的 `STATICFILES_STORAGE`（whitenoise `CompressedManifestStaticFilesStorage`）自 Django 5.1 起已不生效，实际使用的是不带 hash 的 `StaticFilesStorage`。本 change 不修改 storage，但所有资源都保持 manifest-safe，并在 manifest backend 下验证 `collectstatic`；迁移到 `STORAGES` 后就能得到带 hash 的文件名和长缓存（见 Risks）。
- 备选方案：
  - CDN：内网无法访问，还涉及 CSP 和隐私问题。
  - django-compressor 或打包器：会增加运行时或部署期的构建步骤。

### 8. 质量门禁：静态检查 + 浏览器检查 + 人工视觉复查

- `npm run check`：依次运行 token 漂移检查、vendor manifest 检查、Milkdown bundle hash 检查、Stylelint（只允许 token 颜色和字体，pages、shell 和报告样式禁用 `!important`）、对比度检查。对比度检查读取 `contrast-pairs.json`：文字对阈值 4.5:1，UI 和焦点对阈值 3:1。
- `npm run qa:browser`：使用 playwright-core 加 @axe-core/playwright，覆盖 light/dark 两种主题和 1440×900、390×844 两种视口，检查 HTTP 错误、横向溢出、主题不一致、console 错误、同源请求返回错误或没有响应（导航或 htmx 交换中止的请求除外），以及 serious/critical 级别的 axe 违规。
- 人工复查：在真实浏览器中按 light、dark、手机宽度三种情况查看受影响页面，并截图作为证据。
- 备选方案：
  - Lighthouse CI：一次只测一页，偏重性能，运行较慢。
  - Chromatic、Percy：SaaS 服务，页面数据会离开内网。
  - BackstopJS 像素对比：页面使用实时数据，结果不稳定。

### 9. 数据呈现约定

- 缺失值通过 `dashboard_format` 的 `or_dash`、`status_tag` filter 统一输出弱化的 "—"；`timestamp` 和 `age_seconds` 遇到空值也输出同样的结果。
- Velocity 图表随 content partial 一并渲染，减少请求，并删除四个 chart partial 路由；任务下钻仍然走单独的 partial。

### 10. 资源文件架构与体积门禁

- 做法：
  - CSS 分层：`css/foundation/*.css` 放 primitives；`css/shell/*.css` 放外壳（frame、sidebar、topbar、palette、statusbar、responsive、standalone）；页面样式按 feature 放 `css/pages/<feature>.css`（17 个），不设兜底的总样式表，原 `main.css` 已全部拆分并删除。pages 和 shell 层由 Stylelint 禁用 `!important`，控件的 dirty 和 required-missing 状态由 `foundation/forms.css` 的 hook 统一提供。
  - JS 按职责拆分：`shell.js` 负责主题、侧栏和抽屉，并暴露 `window.DashboardShell`；`command-palette.js` 和 11 个 feature 模块各自独立，每个模块在 `DOMContentLoaded` 和 `htmx:afterSwap` 上自初始化，`FEATURE_SCRIPTS` 的顺序就是初始化顺序；原 `main.js` 已全部拆分并删除。
  - `ui_web/static_assets.py` 是共享资源的唯一有序清单：`base.html` 通过 `{% dashboard_stylesheets %}` 和 `{% dashboard_scripts %}` 渲染，浏览器测试内联同一份清单。只有报告页通过 `extra_css`/`extra_js` 加载自己专用的资源，且不得重复加载清单中的文件；`test_frontend_assets.py` 对孤儿资源和重复加载双向检查。
  - 体积门禁借鉴 `phone_teams_copilot` 的检查器：
    - 规则覆盖所有文件类型，未被规则或豁免认领的文件直接失败；
    - glob 按路径分段匹配；
    - legacy allowance 必须写明 owner 和拆分计划，只在 changed 模式下、且 base 已超限时生效，允许新增 0 行。它只是临时冻结：owner 拆分到上限以下后删除条目，过期条目会让 `test_legacy_allowances_name_an_owner_and_still_cover_over_cap_files` 失败。dashboard 模板、样式表和 shell/feature 脚本不再有任何 allowance；唯一剩下的前端 allowance 是报告编辑器脚本（`legacy-report-editor-scripts`）。
  - 浏览器几何约束集中在 `ui_web/tests/ui_geometry_contract.py`：每条约束有稳定 key、阈值、单位、比较方式、所属界面、测量对象、适用视口和执行它的测试模块；Python 断言引用常量，`page.evaluate` 接收 `browser_limits()` 并读取 `limits.<KEY>`；`test_ui_geometry_contract.py` 扫描所有在浏览器里测量的测试模块，拒绝字面量阈值、无人执行的规则和与实际引用不符的 `enforced_by`；baseline gate 收集全部违规后一次失败。改阈值只改注册表并经设计确认，不在测试代码里重新推导。
- 备选方案：
  - 使用 bundler 或 CSS `@import` 合并：前者增加构建步骤，后者在运行时串行加载。
  - 调高上限或豁免大文件：问题会持续累积。之前 CSS、JS 和模板没有被任何规则覆盖，被静默跳过，结果才出现 3000 行以上的文件。
- 取舍：首页加载的本地 CSS/JS 文件（含本地 vendored 文件）从 14 个增加到 59 个（41 个样式表、18 个脚本）。换来的是可审阅的文件粒度和明确的归属；长缓存要等 storage 迁移到 `STORAGES` 后才生效（见 Risks）。如果首次加载的请求数成为瓶颈，在 `ui_web/frontend` 增加构建期按清单顺序拼接的步骤，源码分层不变。

### 11. Shell 双语：页面名单一来源 + 目录完整性门禁

- 做法：
  - shell 中的文案（导航、顶栏、命令面板、状态栏、toast、loading、错误页）全部走 `{% trans %}` 或 `gettext`。zh_Hans 目录已补齐到 648 条，`.mo` 由 polib 编译后随仓库提交。
  - 页面名只来自导航注册表。`base.html` 用当前导航项的 label 填写 `title` 和 `page_title`，与 htmx 切页后 `syncNavigationState` 写入的名称相同。只有深层页面（Scope Audit、Scope Config、Profile Config）自行设置标题，且同样走 `{% trans %}`。
  - 机器值与显示文案分开：服务状态的原值保留在属性中，显示文案通过 `pgettext_lazy('service state', ...)` 词表和 `service_state_label` 过滤器翻译。脚本中的文案从 `data-message-*` 读取，不设英文兜底。
  - 品牌、产品名、键名、缩写、命令、URL，以及外部服务返回的明细，都保持原文。命令通过 `%(command)s` 占位符传入，不写进 msgid。时间统一使用 24 小时制。
  - 门禁是 `ui_web/tests/test_i18n_catalog.py`。它按 `makemessages` 的方式提取 msgid：模板用 `templatize`，Python 用 `ast`。检查项包括：每条 msgid 都有译文；`.mo` 与 po 一致；占位符一致；shell block 中没有裸写的英文；渲染 zh-hans 首页后，shell 中除白名单外不出现英文。
- 备选方案：
  - `makemessages`/`compilemessages`：依赖 GNU gettext，开发机上没有 `xgettext` 和 `msgfmt`；而且会重写整个 po 的格式和注释，带来大量无关 diff。
  - 逐页渲染所有页面再检查英文：要依赖各页面的 facade 和数据，测试成本高。静态检查 shell block 再加上渲染首页，已经覆盖整个 shell。
- 取舍：页面正文中遗留的、未走 `{% trans %}` 的英文不在本 change 范围内。门禁只保证两件事：走了 trans 的文案都有译文，shell 中没有英文。

## Risks / Trade-offs

- [Bulma 风格 class 的语义已经改变，贡献者可能按 Bulma 文档的习惯去使用] → 以 `frontend-design-requirements.md` 列出的词汇为准；Stylelint 和 UI 测试会拦截常见的误用。
- [Node 工具链只在开发期使用，仓库也没有 CI，gate 依赖人或 agent 自觉执行] → `AI_CONTRACT.md` 第 4 节把 `npm run check` 和 `qa:browser` 定为 UI 变更的完成条件；生成物已提交，并且都有 `--check` 漂移检测。
- [`qa:browser` 默认只覆盖导航中的一级页面] → 修改项目详情、报告等深层页面时，必须通过 `DASHBOARD_QA_ROUTES` 显式传入这些路由。
- [未归档的 `standardize-dashboard-ui-design-system` change 中，MODIFIED delta 曾指向一条主 spec 里不存在的 requirement，归档时会失败] → 本 change 不依赖它。closure review 时已把该 delta 改为 ADDED（主 spec 中确实没有这条 requirement），两个 change 可以按任意顺序归档。它暂不归档，因为 `scripts/validate_ui_design_gate.ps1` 按名称校验它，何时归档由其 owner 决定。
- [移除 Bulma 后，没有被测试覆盖的页面可能出现样式退化，例如报告编辑器、Grafana selection] → 对所有导航页面以及项目和报告深层页面做真实浏览器巡检，并迁移相关的 Django/Playwright 测试。
- [可变字体增加首屏体积，约 165 KB] → 只 vendored latin 和 latin-ext 子集，预加载主字体，并设置 `font-display: swap`。
- [用户把 system 模式误解为按时间切换] → 切换控件明确列出三种状态，文档说明 system 跟随操作系统设置。
- [`defaults.py` 中的 `STATICFILES_STORAGE` 自 Django 5.1 起不生效（HEAD 上就是如此），实际 storage 是不带 hash 的 `StaticFilesStorage`，没有长缓存] → 本 change 不修改生产 storage。切换后部署流程必须执行 `collectstatic`，测试设置也要改用非 manifest storage，影响超出本 change 的范围。资源保持 manifest-safe，验收时用 manifest backend 运行 `collectstatic`；迁移到 `STORAGES` 列为后续事项。

## Migration Plan

1. 随一次发布整体上线：没有数据库迁移，没有新的 Python 运行时依赖，也不需要在运行时安装 Node。
2. 部署方式不变（当前生效的是不带 hash 的 `StaticFilesStorage`）。发布前，在临时 `STATIC_ROOT` 下用 manifest backend 运行一次 `collectstatic --noinput`：它会重写 CSS 中的 `url()` 并给文件名加 hash，引用缺失时直接失败，以此保证迁移到 `STORAGES` 后资源可以直接使用。
3. 回滚：revert 本 change 的提交后重新执行 `collectstatic`。`localStorage['dashboard-theme']` 和侧栏折叠状态这类浏览器端残留不会影响旧版本。

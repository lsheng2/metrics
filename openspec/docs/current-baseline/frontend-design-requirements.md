# Meridian Frontend Design Requirements

Status: **binding** for every change that touches `ui_web` templates, CSS, JavaScript, icons,
charts or frontend tooling, whether written by Codex, Copilot, Claude or a human.
Authority: referenced from [AI_CONTRACT.md](../../../AI_CONTRACT.md) §2 and §4.
Companion documents:

- [ui-design-system.md](ui-design-system.md): the class-level contract table for editors, forms,
  tables, provider tabs and the Workbench, plus the older layout/visual-state gate scripts.
- [ui-change-quality-gate.zh.md](../validation/ui-change-quality-gate.zh.md): what an OpenSpec UI
  change must specify before implementation.
- [frontend-design-recipes.md](frontend-design-recipes.md): binding recipes with exact token values,
  selectors, markup and the pitfall behind each (shell, pages, forms, tables, tags, charts, report
  paper, provider editor, formats and copy).
- [frontend-delivery-playbook.md](frontend-delivery-playbook.md): binding delivery practice:
  toolchain, file architecture, the file-size gate, test contracts, real-browser review, debugging
  pitfalls and working rules.

If this document conflicts with older UI notes, plans or OpenSpec design docs, this document wins
for visual language, tokens, theming, shell, primitives and frontend QA. Product behavior still
comes from OpenSpec specs. This document holds the short normative rules; the two companion
documents hold the detail and are equally binding. When code and a document disagree, verify the
code, then fix the document in the same change.

## 中文摘要（设计思路）

- 定位：日常使用的运营型 metrics dashboard。目标是**清新、简洁、现代、高信息密度**：数据是主角，
  界面框架退到背景里；颜色只用来表达含义，不做装饰，也不能是唯一信号。
- 视觉语言 "Meridian"：Radix Colors 的 Slate 中性色 + Indigo 强调色；Mona Sans（可变字宽）做 UI
  字体，Geist Mono 做 ID/hash/代码；13px 基准字号、32px 控件、4px 栅格；细边框加极轻阴影，
  不用粗框、渐变或大面积饱和色块。色值按对比度调优（如 tertiary 文字、warning 黄只能做图标填充），
  不按色阶惯例取值；具体数值见 recipes 文档。
- 主题：Light / Dark / System 三态切换（开关在侧栏底部，命令面板也能切换）。System 跟随操作系统的应用
  外观（`prefers-color-scheme`），**不看时间**。两个主题都是一等公民，都必须通过对比度门禁；页面 CSS
  不得按 `[data-theme]` 分支，差异一律是 token。
- 动线：左侧导航（可折叠、可拖宽，手机上是抽屉）+ 顶栏面包屑 + Ctrl/⌘+K 命令面板，全部由
  `ui_web/navigation.py` 一份注册表生成。页面统一为“页头 → 筛选工具栏 → 结果条 → KPI → 图表 →
  明细表”，筛选写进 URL（`hx-push-url`），可以分享、可以后退。固定的外壳（顶栏、状态栏）必须为自己预留空间。
- 文件架构：tokens（DTCG JSON）→ 生成的 `theme.css`（不手改）；`static/css/foundation/` 按关注点拆分基础组件；
  `static/css/shell/` 放外壳；页面样式按 feature 放 `static/css/pages/<feature>.css`，行为按单一职责放
  `static/js/<feature>.js`，**不设兜底的总样式表或总脚本**。`ui_web/static_assets.py` 是共享 CSS/JS 的唯一清单：新增共享资源
  只登记在这里，不用 bundler、不用 `@import`、不走 CDN；浏览器测试也从同一份清单内联资源。只有报告页通过
  `extra_css`/`extra_js` 加载自己专用的资源，且不得重复加载清单里的文件（`test_frontend_assets.py` 双向检查）。feature 模块各自在
  DOMContentLoaded 与 `htmx:afterSwap` 上自初始化，所以 `FEATURE_SCRIPTS` 的顺序就是初始化顺序。
- 体积门禁：模板 300、CSS 400、浏览器 JS 400、前端脚本 300、Python 源码 400 行等（见 §8）。文件接近上限时
  **先按关注点拆分**（模板拆 partial、CSS 按组件族拆、JS 抽 feature 模块），不得用豁免或放宽上限解决；
  legacy allowance 只是临时冻结：文件不得增长，owner 负责拆到上限以下并删除条目。迁移时直接删除过时规则，不保留兼容层或别名。
- 组件与页面：优先用基础组件，页面 CSS 不得覆盖基础组件的 display、尺寸、padding、字号；required 标记是安静的
  文字而不是红色胶囊；表格单元格 padding-block 和密集行高不超过注册表的 `TABLE_CELL_PADDING_BLOCK_MAX`、
  `DENSE_ROW_HEIGHT_MAX`，每个 `<table>` 都带 `responsive-admin-table` 或
  `dashboard-dense-table`，手机上按容器宽度折叠成卡片；空值统一显示灰色破折号（`or_dash`）。
- 编辑器（Provider Setup、Scope Config）：整张表单是唯一的卡片，左侧 2px provider 色条；provider tabs 贴在卡片
  顶边，选中 tab 的下划线用 provider 色；所有可编辑内容放在 tab body 里，用 hairline 分节，不嵌套方框；required
  提示是 help 之后右对齐的弱化文字；状态统一用 `status_tag`，消息统一用 `.message`；多值 textarea 每行一个值
  （`join:"&#10;"`，不能用 `join:"\n"`）。
- 图表：颜色只能经由 `DashboardCharts` 的 scriptable 函数取得，后端 payload 只传语义（slot、key），不传颜色；
  报告 `.paper` 是固定浅色的独立表面，不被全局基础样式污染。
- 工具与流程：npm 锁定的第三方库 vendored 到本地并记录 hash，不走 CDN；本地构建的 Milkdown 报告编辑器 bundle
  也在自己的 manifest 里记录 hash，`npm run check` 会重新校验；Iconoir 图标子集按实际使用自动生成
  （图标类名必须是字面量）；Stylelint 禁止原始颜色，并在 pages、shell 和报告样式里禁止 `!important`；对比度脚本检查
  两套主题，新增配色必须登记为 `error` 级别；Playwright + axe-core 在两种主题、桌面和手机宽度下检查可访问性、
  横向溢出、控制台错误和失败的同源请求。
- 测试与契约：改写模板前先读一次相关测试并把契约（受保护文案、class 顺序、id）固化到笔记里；像素级几何阈值
  只登记在 `ui_web/tests/ui_geometry_contract.py`（`python ui_web/tests/ui_geometry_contract.py` 按界面打印），
  测试按 key 引用，不写字面量，也不从测试代码里重新推导（meta-test 扫描所有在浏览器里测量的模块）；改阈值只改
  注册表，并需设计确认；baseline gate 一次列出全部违规，每行一条“规则=阈值: 指标=实测值 @ 页面 视口”；
  服务端测试验证文案与 class，浏览器测试验证几何与计算样式；先跑聚焦测试，浏览器测试分片运行；
  已有失败先在干净的 `git worktree` 里确认是否为存量问题。
- 真实浏览器复查：自动化门禁之后，用隔离端口的预览服务和 ego-browser 在浅色、深色、1440 与 390 宽度下逐页
  肉眼复查；这一步抓到过门禁漏掉的堆叠按钮、被裁切的工具栏、过重的深色文字、手机宽度下压到操作按钮底下的长 chip 等问题。
- 硬规则：只用 token；页面级 CSS 不得覆盖基础组件的 display 和尺寸，也不得用 `!important`；滚动容器必须是定位元素；
  图表颜色只能经由 `DashboardCharts`；旧 Bulma 布局词汇已全部退役，任何模板都不得再使用（设计系统测试全量拦截）；
  代码与文档冲突时以代码为准，并在同一次变更里修正文档。
- 中英双语：界面同时支持 English 和简体中文（`zh-hans`）。所有用户可见文案都要走 `{% trans %}` 或 `gettext`；新增 msgid
  须在同一次变更中补上 `zh_Hans` 译文，并用 polib 编译 `.mo`，`test_i18n_catalog.py` 是对应的门禁。页面名统一由导航
  注册表提供，只有深层页面才自行设置 `title`/`page_title`。机器值保留在属性里，显示文案另行翻译。脚本里的文案从
  `data-message-*` 读取，不设英文兜底。品牌、产品名、键名、缩写、命令、URL 不翻译，命令通过占位符传入。时间一律使用 24 小时制。
- 知识沉淀：每完成一轮 UI 工作，都要把新规则、数值和踩过的坑写回本文档、recipes 或 playbook（不可违反的规则
  同时写进 `AI_CONTRACT.md` §7），并在同一次变更里勾选 `tasks.md`。只存在于聊天记录、会话笔记或交接提示词里的
  规则，到下一次交接就会丢失（§7 规则 19）。

## 1. Design Intent

The dashboard is an operational tool used daily by engineering leads and developers. It must feel
like a current product dashboard: calm, fresh, precise and information-dense.

Principles, in priority order:

1. **Data is the hero.** Chrome (navigation, borders, backgrounds) recedes. Ink hierarchy
   (primary, secondary, tertiary text) carries structure before any color does.
2. **Color means something.** Accent marks interaction and selection; semantic colors mark state;
   chart colors mark series. Never decorate with color, and never let color be the only signal.
3. **Dense, not cramped.** A 13px base, 32px controls and a strict 4px rhythm let a 1440×900
   screen show the answer without scrolling, while spacing stays consistent everywhere.
4. **One system.** Tokens → primitives → patterns → pages. Pages compose primitives; they do not
   invent buttons, tags, cards, colors or spacing.
5. **Both themes are first-class.** Every surface is designed and checked in light and dark.
6. **Accessible by construction.** WCAG 2.2 AA: contrast, focus, names, keyboard, reduced motion.
7. **Server-rendered and progressive.** Django templates and htmx stay the architecture; JavaScript
   enhances behavior and never owns business state.
8. **Reproducible assets.** Every runtime asset is pinned, vendored, hashed and served locally.

Anti-patterns that made the previous UI look dated, and are now rejected in review:
heavy or colored borders around everything, bold uppercase labels on every field, saturated fills
for neutral information, red "Required" pills, mixed button heights in one row, boxes nested in
boxes, centered hero titles, default framework blue, icon soup, and page-specific restyling of
shared components. Real-browser review has also rejected stacked or clipped toolbar buttons,
heavy dark-theme text, over-saturated warning yellow, duplicate in-page breadcrumbs and create
forms placed before the list they extend.

## 2. Architecture And File Ownership

| Layer | Files | Owns | Rules |
| --- | --- | --- | --- |
| Tokens | `ui_web/frontend/tokens/base.tokens.json`, `theme.light.tokens.json`, `theme.dark.tokens.json`, `contrast-pairs.json` | Every color, font, size, radius, shadow, duration, easing and z-index value (W3C DTCG format; colors reference Radix ramps as `{ramp.<scale>.<step>}`) | Edit JSON, then `npm run build:tokens`. Never hand-edit the output. |
| Generated theme | `ui_web/static/css/theme.css` | CSS custom properties on `:root` and `[data-theme="dark"]` | Generated by Style Dictionary; `npm run check` fails on drift. |
| Primitives | `ui_web/static/css/foundation/*.css`: `base`, `layout`, `typography`, `buttons`, `forms`, `tables`, `disclosure`, `feedback`, `page-patterns`, `charts`, `status`, `work-items`, `helpers` (this load order) | Reset and document; layout and surfaces; typography and paper; controls; tables and tags; disclosure and tabs; pagination, progress, loader, skeleton; page header, description list, stat, pipeline; chart card, frame, legends and palette slots; delta, empty state, status dot, count badge, health, avatars; work-item refs, results bar, board, meta strip, popover; helpers | The only place that defines reusable components. A new primitive goes to the file of its concern. |
| Shell | `ui_web/static/css/shell/*.css` (`frame`, `sidebar`, `topbar`, `palette`, `statusbar`, `responsive`, `standalone`), `ui_web/static/js/shell.js` (theme, collapse, drawer, nav sync, popovers; exposes `window.DashboardShell`), `command-palette.js` | Sidebar, rail, mobile drawer, topbar, breadcrumbs, theme switch (sidebar foot), command palette, popovers, status bar; the context-free `standalone_base.html` frame for 404/500 and iframe bridge pages | Pages never restyle the shell. No `!important` (stylelint). |
| Page layer | `ui_web/static/css/pages/<feature>.css`, `ui_web/static/js/<feature>.js` (the `FEATURE_SCRIPTS` modules) | Feature surfaces (Workbench panes, editors, provider tabs, scope config, bug trend) and the contracts in `ui-design-system.md` | Compose primitives; see §7. One stylesheet per feature and one module per behavior; no catch-all page stylesheet or script; no `!important` (stylelint). |
| Asset manifest | `ui_web/static_assets.py`, `ui_web/templatetags/dashboard_assets.py` | The ordered stylesheet and script lists that `base.html` renders; browser tests inline the same lists (`ui_web/tests/dashboard_asset_support.py`) | Adding a shared CSS or JS file means adding it to the manifest and nowhere else. No bundler, no CSS `@import` chains, no second list. `test_frontend_assets.py` fails on a top-level file that neither the manifest nor a page template loads, and on a template that loads a manifest file again. |
| Report pages | `report_editor.css`, `report_assist.css`, `report_exports.css`; `project_reports.js`, `report_exports.js`, `report_daily.js`, `project_run_status.js`; `static/js/report_editor/` (ES modules plus the vendored Milkdown bundle) | Milkdown editor chrome, report assist, exports, daily preparation, run status and the fixed-light "paper" surface | The only assets loaded per page, by the report templates through `extra_css`/`extra_js` (recipes §9, §12.2), never through the manifest. Token-only and stylelinted like every other file, no `!important`; paper uses `--color-paper-*` tokens in both themes. `scripts/validation/build_report_editor_vendor.py` builds the bundle; `npm run check` re-hashes it. |
| Charts | `ui_web/static/js/charts.js` → `window.DashboardCharts` | Chart.js defaults, palette, series colors, re-theming | All chart colors come from here. |
| Navigation | `ui_web/navigation.py`, `ui_web/context_processors.py` | Sidebar groups, breadcrumbs, command palette entries, active state | Add a page by adding one `NavItem`. |
| Template helpers | `ui_web/templatetags/dashboard_format.py`, `avatar_filters.py`, `pull_request_filters.py`, `ui_web/templates/partials/avatar.html`, `task_health.html` | Timestamps, ages, status tones, series labels, initials, avatar palette slots | Reuse before writing template logic. |
| Vendored runtime | `ui_web/static/vendor/**` with `asset-manifest.json` and `THIRD_PARTY_NOTICES.md` | htmx, Chart.js (+ date-fns adapter, annotation plugin), modern-normalize, Mona Sans, Geist Mono, Iconoir subset | Produced by `npm run build:vendor`; never edited by hand; no CDN. |

`ui_web/static_assets.py` is the authority for load order. Stylesheets load as modern-normalize,
fonts, `theme.css`, foundation, Iconoir, shell, then `pages/` files and page `extra_css`; scripts
load synchronously in `<head>` as htmx, Chart.js and plugins, `charts.js`, `shell.js`,
`command-palette.js`, then `FEATURE_SCRIPTS`, whose order is also init and `htmx:afterSwap` order;
page `extra_js` renders at the end of `<body>`. Do not reorder. Details and the file-size gate:
playbook §2–§3.
## 3. Visual Language

### 3.1 Color

- Neutrals are Radix **Slate**; the accent is Radix **Indigo**; semantic families are Grass
  (success), Amber (warning), Red (danger) and Blue (info). Dark values come from the matching
  Radix dark ramps, not from inverting light values.
- Components use **semantic tokens only**: `--color-canvas`, `--color-surface`,
  `--color-surface-muted|hover|active|raised|inverse`, `--color-border|-subtle|-strong|-input`,
  `--color-text|-secondary|-tertiary|-disabled`, `--color-accent|-hover|-text|-subtle|-border`,
  `--color-{success,warning,danger,info}{,-text,-subtle,-subtle-hover,-border}`,
  `--color-neutral-*`, `--color-focus-ring`, `--color-focus-halo`.
- Text on a tinted fill uses the matching `-text` token on the matching `-subtle` fill. Solid
  fills (`--color-success` …) carry glyphs only (`--color-on-*`), never body text.
- Tints are written as `color-mix(in srgb|oklab, var(--token) N%, transparent|var(--token))`.
  Raw hex, `rgb()`, `hsl()`, `oklch()` and named colors are rejected by Stylelint. Elements whose
  contrast is measured by tests (report paper and toolbar) use opaque token backgrounds: tests read
  `rgba(0,0,0,0)` as black and `color-mix()` computes to `color(srgb …)`.
- Values are tuned for measured contrast, not ramp convention (recipes §1.1): tertiary text is at
  least 4.5:1 on every surface, the solid warning fill is a glyph fill only (never text, a line or a
  chart mark), warning tints are pale, dark-theme accent hover is darker than the accent, and chart
  and health colors are at least 3:1 on `--color-surface`. Tune the token, never the threshold.
- Accent budget: one primary action per region, links, active navigation, focus, selection and
  "on" toggles. A neutral label, count or heading is never accent-colored.
- In light mode `--color-surface-muted` equals `--color-canvas`: a muted strip or well placed on
  the canvas (not inside a card) needs a 1px `--color-border` to stay visible in both themes.
- Primary buttons are **ink** (`.button.is-primary` = `--color-surface-inverse`); accent-filled
  buttons (`.is-link`) are reserved for the single most important call to action on a page.
- Data colors:
  - Categorical series use the 8 palette slots `--color-chart-1..8`. Python passes a slot index or
    a series key, never a color; templates expose slots as `data-palette-slot="N"`.
  - Bug trend series use `--color-series-<series-key>`.
  - Forecast health uses `--color-health-{green,yellow,orange,red,gray}` as a dot or stripe beside
    the status **name** (`partials/task_health.html`, `.health`, `.board-card` stripe).
  - Provider identity is Jira green, HSD-ES blue, GitHub purple (`--color-provider-*`,
    `is-provider-green|blue|purple`), shown as a thin border or left accent, never a large fill.
- Status tags use `.tag.is-success|is-warning|is-danger|is-info` (subtle fill + text token); the
  tone comes from `status_tag` / `status_tone`, and an unknown status is neutral. Required markers
  are quiet neutral text (`.dashboard-required-tag`), not red pills; red is reserved for actual
  errors.

### 3.2 Typography

- UI font: **Mona Sans Variable**; mono: **Geist Mono Variable** for IDs, keys, hashes, code and
  JQL. The stacks fall back to Microsoft YaHei UI / PingFang SC / Noto Sans SC for Chinese text.
  `font-family` must be a `var(--font-*)`, `inherit` or `monospace`.
- Scale tokens: `--text-2xs` 11px (micro badges), `-xs` 12px (labels, table headers, help, meta),
  `-sm` 13px (default UI and table text), `-md` 14px (card titles, emphasized body), `-lg` 16px
  (section headings), `-xl` 20px (page titles), `-2xl` 26px and `-3xl` 34px (KPI values).
- Weights: 400 body; 500 buttons, labels, navigation and table headers; 600 titles and KPI
  values; 700 only for rare emphasis. Do not bold whole paragraphs or every label. The dark theme
  lightens the weights (380/480/580/680) through the `weight` token group; `.paper` keeps fixed
  weights. Labels and buttons never exceed 500 (a gate asserts it).
- Width axis: `--stretch-display` for the page title and KPI values; `--stretch-condensed` is
  available for exceptionally dense tables; body text stays normal width.
- Numbers use tabular figures (`.table` does this; elsewhere `.is-tabular`) and numeric cells are
  right-aligned with `.is-numeric`.
- Sentence case for titles, buttons and labels. Uppercase only through `.eyebrow`
  (11px, `--tracking-caps`).
- Empty values render as a muted em dash: `<span class="has-text-grey-light">—</span>`. With
  `{% load dashboard_format %}`, use `{{ value|or_dash }}` for a single value and
  `{{ status|status_tag }}` for a toned machine-status tag; `timestamp` and `age_seconds` already
  return the dash. Never print `-`, `None`, `N/A` or an empty tag for a missing value.

### 3.3 Space, Radius, Elevation, Motion, Layers

- Spacing uses `--space-*` (0.5, 1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10, 12 → 2px … 48px). There is no
  `--space-3-5` or `--space-7`; pick an existing step. Only hairlines (`1px`) may be literal.
  Layout tokens: `--layout-sidebar-width` 15rem, `--layout-sidebar-rail` 3.25rem,
  `--layout-topbar-height` 2.75rem, `--layout-statusbar-height` 1.75rem.
- Controls: `--control-height` 32px, `--control-height-sm` 28px, `--control-height-xs` 24px for
  in-table controls. Buttons and inputs in one row share one height.
- Radius: `--radius-xs` inline `code`, `--radius-sm` `kbd`, `pre` and chip disclosures,
  `--radius-md` buttons and inputs, `--radius-lg` cards, panels and framed tables, `--radius-xl`
  dialogs and drawers, `--radius-full` pills, tags, count badges and avatars.
- Elevation: resting cards use a border plus `--shadow-xs`; only floating layers (popover,
  dropdown, command palette, drawer, toast) use `--shadow-md|lg`.
- Motion: `--duration-fast|base|slow` with `--ease-standard|exit`; honor
  `prefers-reduced-motion`. Nothing animates during a theme switch.
- Stacking uses `--z-sticky|topbar|statusbar|dropdown|overlay|drawer|toast`; never a raw z-index.
  Replace literal radii and z-indexes with tokens whenever a legacy rule is touched.

### 3.4 Icons

- Icons are **Iconoir** only: `<i class="iconoir-<name>" aria-hidden="true"></i>`.
- `build:vendor` generates the Iconoir CSS subset from icon names actually used in templates and
  JavaScript. After adding or removing an icon run `npm run build:vendor`; `npm run check` fails
  otherwise. Dynamic names must appear literally somewhere the scanner reads (for example the
  Python value that produces them).
- Icon classes are literal `iconoir-<name>` strings (never built with `{% if %}`), and the name
  must exist in the pinned Iconoir version; unknown names fail `build:vendor`. Global CSS draws
  icons as `mask` images at 1em; features do not carry local icon rules or copies.
- Icon-only buttons need `aria-label` and `title`. Icons support a label; they do not replace one
  in dense tables or toolbars, except universally understood actions (close, more, collapse).

## 4. Themes: Light, Dark, System

- `<html data-theme="light|dark" data-theme-preference="light|dark|system">` is set before first
  paint by the inline script in `base.html` from `localStorage["dashboard-theme"]`. The default
  is `system`.
- **System follows the operating system's app appearance** (`prefers-color-scheme`), not the
  time of day. The System option's tooltip states which appearance is currently detected. On
  Windows this is Settings → Personalization → Colors → "Choose your default app mode".
- The theme switch (`.theme-switch[data-theme-switch]` in the sidebar footer; the command palette
  offers the same actions) is a `role="radiogroup"`. `shell.js` applies the change, sets
  `data-theme-switching` for one frame so every surface flips together without transitions,
  syncs other tabs through the `storage` event and dispatches `dashboard:themechange`.
  `charts.js` listens and re-themes every Chart.js instance.
- Page CSS must not branch on `[data-theme]`. If a value differs by theme it is a token. The
  report "paper" surface and the provider identity colors are intentionally theme-independent.
- Every new foreground/background pairing is added to `tokens/contrast-pairs.json` (text 4.5:1,
  UI boundaries and chart marks 3:1) and must pass in both themes.

## 5. Shell And User Flow

- Frame: sidebar (expanded 15rem, user-resizable 168–360px, collapsible to a 3.25rem rail with
  Ctrl/⌘+\; the theme switch and collapse button sit in its footer), sticky topbar (breadcrumb
  group, the page `<h1>`, `header_extra`, a search button while the sidebar is collapsed), content
  well, service status bar. At ≤768px the sidebar becomes a drawer opened from the topbar. From
  1024px the Workbench is a full-bleed IDE mode (`body.has-workbench-shell`) that hides the topbar
  and carries its own title; below 1024px it is an ordinary scrolling page under the topbar whose
  panes stack (chart, evidence, AI) and whose splitters hide (recipes §2.7). Fixed chrome reserves
  its own space from the same layout tokens (recipes §2).
- Pages outside the shell (the 404/500 error pages and iframe bridge pages) extend
  `standalone_base.html`: brand header, one centered panel with exactly one primary action, no
  scripts and no context processors, because Django renders `500.html` with an empty context. The
  theme bootstrap and brand are shared partials, so both frames stay in step (recipes §2.8).
- Navigation, breadcrumbs and the command palette (Ctrl/⌘+K or `/`) all render from
  `ui_web/navigation.py`. Never hand-code navigation links in page templates. A new page adds a
  `NavItem` (key, label, `url_name`, Iconoir icon, description, keywords, active rules).
- The topbar `<h1>` is the page title. In-page headings start at `<h2>`. Deeper pages override the
  `breadcrumbs` block with bare ancestor links; never put `nav.breadcrumb` in page content.
- Context processors (`dashboard_navigation`, `member_groups`, `service_status_bar`) return `{}`
  for `HX-Request`, so filters and switchers render from view context. Every `hx-push-url` target
  belongs to its `NavItem`'s `active_url_names` so navigation stays active.
- Page anatomy, top to bottom, omitting what a page does not need:
  1. `.page-header` with `<h2 class="page-header__title">`, one-sentence
     `.page-header__meta`, and `.page-header__actions` for page-level actions.
  2. Filter toolbar: `form.box.dashboard-tool-form.dashboard-top-toolbar` with
     `.dashboard-tool-grid.is-toolbar`, one `.dashboard-tool-field` per control and
     `.dashboard-tool-actions` (Apply as `.button.is-primary`, Clear as a ghost link). Query forms
     use GET with `hx-get` + `hx-push-url="true"` so state lives in the URL and Back works.
  3. `.results-bar`: result count on the left, view switches (`aria-pressed` segmented buttons),
     expand/collapse and export on the right. Create forms follow the list they extend.
  4. KPIs: `.stat-grid` of `.stat` (`__label`, `__value`, `__unit`, `__hint`, `.delta`).
  5. Charts: `.chart-grid` of `.chart-card` with a fixed-height `.chart-frame` and
     `.series-toggles` legends.
  6. Evidence and detail tables, disclosures or boards.
- Drilldowns keep context: the same scope, filters and calculation run as the clicked element.
- A region renders each filter form and Clear action once. A partial shared by pages whose state
  lives in different URLs takes a host flag and renders the host's URL-state form instead of its
  own (the Workbench evidence pane, recipes §2.7).
- Destructive actions (archive, delete, unbind) are visually secondary, confirm intent and never
  sit next to the primary action without separation.
- Partial regions refreshed by htmx keep their own loading, empty and error states (§6.7) so one
  failure never blanks the page.

## 6. Components And Patterns

Use these before writing new markup. `ui-design-system.md` lists the editor, form, table, provider
and Workbench contracts that sit on top of them.

### 6.1 Surfaces

`.card` (`.card-header` > `.card-header-title`, `.card-header-meta`, `.card-header-actions`;
`.card-content`; `.card-footer`) is the default container. `.box` is a plain padded surface (the
filter toolbar). Do not nest bordered surfaces; inside a card use spacing, `.description-list`,
`.meta-strip` or a hairline divider instead; a flush disclosure or tab strip attaches to its panel
without a second border (recipes §7).

### 6.2 Controls

- `.button` (default, outline), `.is-primary` (ink), `.is-link` (accent), `.is-light` (ghost),
  semantic variants, `.is-small`; `.buttons` and `.dashboard-action-group` for rows.
  `.toggle-button` wraps a checkbox or radio presented as a toggle; its selected look comes from
  `:has(> input:checked)`, never a class toggled by script.
- Form fields: label above the control (`.label`, 12px medium), `.input`, `.select > select`,
  `.textarea`, `.checkbox`, `.radio`, `.help`. Every control has a visible label or, in a dense
  table, an accessible name. Multi-value textareas hold one value per line.
- Segmented controls and view switches are buttons with `aria-pressed` or radios inside
  `label.toggle-button` (`role="radiogroup"`); tabs use `role="tablist|tab|tabpanel"`.
- Page-header actions are `button is-small`, tool and filter forms never use `is-small`, and one
  row never mixes heights. Never add `is-light` to a semantic variant (it once made "Archive" read
  as plain text) or to a `.tag`; a design-system test enforces both. Secondary editor actions are
  plain `.button`, only Cancel is the ghost. Destructive actions stay visibly buttons, secondary
  to the primary action.
- Required markers are `.dashboard-required-tag` text; dirty and validation banners come from
  `dashboard_editor_state_banners.html`; help tips use `.help-tip` popovers (recipes §4).

### 6.3 Data

- Tables: `.table` inside `.table-container` (add `.is-framed` when the table sits directly in page
  flow). Headers are sticky; numbers use `.is-numeric`; a second line uses `.cell-meta`; empty
  tables use `<tr class="is-empty-row"><td colspan="N">…</td></tr>`. Dense operational tables
  add `.dashboard-dense-table`.
- Table cell padding-block and dense row height stay within `TABLE_CELL_PADDING_BLOCK_MAX` and
  `DENSE_ROW_HEIGHT_MAX` in the geometry registry (rule 18). Every `<table>` carries
  `responsive-admin-table` or `dashboard-dense-table`; on phones tables collapse by container width
  (`container-type` on `.responsive-admin-table-box`), not viewport width. Task, PR and people
  tables follow recipes §6; stable ids such as the `#pr-*` out-of-band targets are not renamed.
- Work items: `.work-item-ref` (`__key` in mono, `__title`, optional `.cell-meta` parent) and
  `.item-key` for a key on its own.
- Wide admin tables show every column on wide screens (`col` widths sum to the table minimum),
  pin the name and action columns with opaque cells on narrower screens, and line up row actions
  as one primary button plus a "More" menu. Menus inside a scrolling table are fitted by
  `table-interactions.js` (flip up or pad the box), never by un-clipping the scroll box. On phones
  card cells keep tags and buttons at their natural width (recipes §6.2).
- People: `partials/avatar.html` (initials tinted by the `avatar_slot` filter), `.person` for an
  avatar beside a name, `.avatar-stack` for decorative group summaries.
- Tags: `.tags` > `.tag` (inline-flex with a built-in icon gap), semantic variants, `.is-small`. A long
  value truncates inside the tag in a child `span.is-truncated` with the full value in `title`; the page
  row gives that tag `flex: 1 1 0; min-width: 0; max-width: max-content`, so it never runs under
  neighbouring actions and the heading beside it never wraps.
  Tags are pills (`--radius-full`). Counts use `.count-badge`; state dots use `.status-dot`;
  forecast health uses `.health`.
- Facts: `.description-list` for key/value blocks, `.meta-strip` for one-line run metadata.

### 6.4 Disclosure And Board

- Grouped rows use `<details class="disclosure">` with `.disclosure__summary`
  (`__chevron`, `__title`, `__meta`, `__aside`) and `.disclosure__body`. On phones the meta and
  avatar stack are hidden; the title and count remain.
- Boards use `.board` > `.board__column` > `.board-card`; health is a stripe plus the status name.

### 6.5 KPI And Charts

- `.stat-grid` / `.stat` for KPIs; `.stat.is-<tone>` marks a KPI that needs attention (value takes
  the tone color and a dot leads the label).
- Charts live in `.chart-card` > `.chart-frame` (fixed height; timelines set `--chart-rows`).
  Colors come only from `DashboardCharts.seriesColor(name, index)`, `paletteColor(index)`,
  `token(name)` and `alpha(color, opacity)`. Legends use `.series-toggles` with one
  `aria-pressed` toggle per series shared by every chart on the page.
- Python payloads carry semantics (slot, series key, state), never colors. Chart options read
  colors through scriptable functions so a theme flip recolors without reload, and a chart with
  no data shows `.empty-state` inside its card (recipes §8).

### 6.6 Overlays

`.popover` / `.popover__panel` for small anchored menus; the command palette and drawer belong to
the shell. Escape closes overlays and focus returns to the trigger. Reference content that is not
needed on every visit (a readiness matrix, a legend) moves into a popover behind a ghost button
with an icon; a wide panel caps its height and scrolls, and a table inside it keeps the table
contract and turns into cards on phones (recipes §4.5).

### 6.7 States

- Empty: `.empty-state` (`__icon`, `__title`, `__body`, `__actions`) explains why and what to do.
- Loading: `.skeleton-block` / `.skeleton-lines` for first load, `.loader` and
  `partials/loading_indicator.html` (`hx-indicator`) for refreshes.
- Errors: `.message.is-danger` with `role="alert"`, a plain-language cause and a recovery action;
  partial errors stay inside their region.
- Editors: dirty, required and validation banners follow `ui-design-system.md`.

### 6.8 Report Paper

Authored report content lives in `.paper`, a fixed-light surface with fixed weights. Descendant
primitives that would restyle it end with `:where(:not(.paper *))`, report editor chrome is
token-only, and toolbar icons are Iconoir masks (recipes §9).

### 6.9 Provider Editor And Scope Config

Provider identity is a thin accent (`--provider-color` through `is-provider-green|blue|purple`),
never a large fill. Each editor is one card: the form carries a 2px provider rail, the provider
tabs sit on its top edge and the selected tab's underline takes the provider color. Every editable
section lives in the tab body, divided by hairlines, never in nested boxes; context that always
exists renders without template guards, and secondary tab meta hides on phones. Required hints
are quiet text after the help tip, statuses go through `status_tag`, messages are `.message`
blocks and the signature is a `dl` with `or_dash` values. The editors' geometry, class order,
required-field order and copy are pinned by tests (recipes §10, playbook §4.3); read them before
rewriting either template.

## 7. Engineering Rules

1. **Tokens only.** No literal colors, font families, shadows, durations or z-indexes. `var()`
   fallbacks may only name another real token.
2. **Page CSS must not override a primitive's `display`, box size, padding, font-size or
   line-height.** Compose a documented modifier, or add a new modifier to the owning
   `foundation/` file and this document. (A page rule that forced `.tag` to `inline-block` inside
   flex `.tags` silently removed every icon gap.) Page CSS owns page layout only: grid placement
   and widths. Never win a cascade fight with a stronger selector or `!important`; primitives that
   components restyle sit in `:where()`, and ported Bulma rules are re-checked for specificity.
   Stylelint rejects `!important` in `pages/`, `shell/` and `report_*.css`; the one exception
   collapses an export's inline style and carries a disable comment with its reason. Control
   states use the `forms.css` hooks `is-dirty-control` and `is-required-missing-control`.
3. **Scroll containers are positioned** (`position: relative`) so visually hidden text
   (`.is-sr-only`) cannot widen the page. `.table-container`, `.board` and the responsive admin
   table already are.
4. **Breakpoint**: `@media (max-width: 768px)` for phone layouts and `(min-width: 769px)` for the
   complement. Documented exceptions: container queries (tables, Workbench toolbar) and the
   Workbench layout pair 1024px/1023px (two panes side by side need the width). Form grids size
   their columns from the container and need no breakpoint. Stylelint allow-lists every media
   width per file, so a new breakpoint needs a documented reason, a `.stylelintrc.json` entry and
   a recipe update.
5. **Inline `style`** is allowed only to pass data-driven custom properties
   (for example `style="--chart-rows: 12"`). No inline colors, spacing or layout.
6. **JavaScript** uses delegated listeners that survive htmx swaps, no inline `on*` handlers, no
   global state beyond `window.DashboardCharts` and `window.DashboardShell`, and must work with
   JavaScript-rendered content arriving through htmx. Real htmx behavior is tested; never ship
   shims for `hx-post`, `hx-trigger` or `hx-on`.
7. **No CDN or ad-hoc downloads.** New runtime libraries are added to
   `ui_web/frontend/package.json`, copied by `build-vendor.mjs`, recorded in
   `asset-manifest.json` and `THIRD_PARTY_NOTICES.md`, and committed. No frontend framework
   (React, Vue, Tailwind runtime, component kits) without an approved OpenSpec change.
8. **Retired Bulma vocabulary.** The compatibility layer is deleted, and
   `ui_web/tests/test_dashboard_ui_design_system.py` keeps it deleted. Templates never use
   `.section`, `.container`, `.columns` / `.column`, `.level*`, `.panel*`, `.hero*`,
   `.notification`, `.title` / `.subtitle`, `.content`, `.is-size-*`, `.is-flex*`,
   `.is-align-*` / `.is-justify-*`, `.has-text-weight-*`, the spacing helpers `m*-N` / `p*-N`
   or `.is-striped`, and `is-light` appears only on a plain `.button` (the ghost). Every `is-*`
   and `has-*` class in a template must match a stylesheet rule, so a misspelled or deleted
   modifier fails the suite. Supported Bulma-derived names: controls (`.button(s)`, `.field`,
   `.control`, `.label`, `.input`, `.select`, `.textarea`, `.checkbox`, `.radio`, `.help`,
   `.delete`), `.tag(s)`, `.table` and `.table-container`, `.card*`, `.box`, `.message*`,
   `.tabs`, `.pagination`, `.progress`, `.loader`, and the helpers in `foundation/helpers.css`:
   visibility (`.is-hidden`, `.is-invisible`, `.is-sr-only`, `.is-hidden-mobile|tablet`),
   `.is-fullwidth`, `.is-truncated`, `.is-tabular`, `.has-text-left|centered|right` and the
   `.has-text-*` tones. Layout, spacing and type belong to primitives and page CSS, never to new
   helpers. The tests read templates only: grep scripts and Python presenters before retiring a
   class they build.
9. **Test contracts.** Many classes, `data-*` attributes and texts are asserted by tests
   (provider tab colors, editor banners, page headings such as "Bug Trend Indicator"). Search
   `ui_web/tests` before renaming or removing one, and update tests only when the contract
   intentionally changes.
10. **i18n.** The UI ships English and Simplified Chinese (`zh-hans`); layouts tolerate longer
    and CJK labels. Every user-visible string in `ui_web` templates and Python goes through
    `{% trans %}`/`{% blocktrans %}` or `gettext`/`gettext_lazy`/`pgettext_lazy`, and its msgid
    gets a non-empty `zh_Hans` translation and a recompiled `.mo` in the same change.
    `ui_web/tests/test_i18n_catalog.py` is the gate: it extracts msgids the way `makemessages`
    does and fails on a missing translation, a stale `.mo`, a lost `%(name)s` placeholder, bare
    English in a shell block, or English in the zh-hans shell outside the verbatim list.
    - Page names come from `ui_web/navigation.py`. Only a deep page below its navigation entry
      sets `title`/`page_title` (through `{% trans %}`); the `title`, `page_title`,
      `breadcrumbs` and `header_extra` blocks never hold bare English.
    - Machine values stay in attributes (`data-service-status="connected"`); display text is
      translated separately, for example through the `pgettext_lazy('service state', ...)`
      vocabulary and the `service_state_label` filter (recipes §11).
    - Script-built copy (toasts, palette hints) reads `data-message-*` attributes rendered with
      `{% trans %}`; scripts carry no English fallback.
    - Brand ("Metrics Dashboard"), product names (Grafana, AI Base, Jira), key names (Ctrl, Esc,
      Enter), acronyms (WAF, UTC), environment variable names, commands, URLs, HTTP status lines
      and details reported by external services stay verbatim. A command enters a message
      through a placeholder (`%(command)s`), never inside a msgid.
    - Clock times use the 24-hour format; the command palette matches translated labels and
      English keywords.
11. **Accessibility.** Landmarks and one `<h1>`; ordered headings; labels for every control;
    visible `:focus-visible` ring (accent ring plus halo); pointer targets ≥24px; color never
    the only signal; `prefers-reduced-motion` respected.
12. **Line endings.** Keep each file's existing line endings; generated files, Markdown and new
    files are LF. After a scripted edit assert there are no mixed endings.
13. **File architecture.** Primitives live in `static/css/foundation/`, the shell in
    `static/css/shell/`, page layers in `static/css/pages/<feature>.css` and
    `static/js/<feature>.js`. Register every new shared CSS or JS file in `ui_web/static_assets.py`
    only; only report pages load their own assets, through `extra_css`/`extra_js`. No bundler,
    `@import` chain or second list. Primitives never depend on page files.
14. **No catch-all layers.** Page styles live in one `pages/<feature>.css` per feature and behavior
    in one `js/<feature>.js` per concern; never add a shared catch-all stylesheet or script. When a
    task touches a page, move what it owns into its feature files and delete what the move makes
    dead. No compatibility shims, aliases or fallbacks for old names; grep for references, then
    remove obsolete code.
15. **Size gate: split before you add.** Per-file caps are enforced by
    `scripts/check_file_size_limits.py` (§8). A template, stylesheet or script approaching its cap
    is split by concern (partials, one CSS file per component family, JS feature modules) before
    more is added. Never solve a size failure with an exemption, a looser cap or minified lines;
    every changed file must be claimed by a rule or an explicit exemption.
16. **Formats and copy.** Dates, durations, empty values and tones come from `dashboard_format`
    filters, not ad-hoc formatting; Python helpers return `''`, never `'-'`. Reuse existing msgids;
    sentence case, no trailing colons on labels, no emoji in error blocks.
17. **Templates and htmx.** Multi-line template comments use `{% comment %}`; `{% load %}` comes
    first; never put `{{` inside inline JavaScript. A GET `hx-get` includes an outer form only
    through `hx-include`. Never put `hx-trigger="every Ns"` on an ancestor of a swapped region.
    Partials render standalone with missing context keys.
18. **Test contracts first.** Before rewriting a template or stylesheet, read the constraining
    tests once and write down protected strings, class order and ids (playbook §4.3). Geometry
    limits are not re-derived from test code: `ui_web/tests/ui_geometry_contract.py` is the single
    registry (key, limit, unit, comparison, surface, what it measures, viewports, enforcing
    modules) and `python ui_web/tests/ui_geometry_contract.py` prints it by surface. A new or
    changed pixel threshold is added there and referenced by key (`limits.<KEY>` inside
    `page.evaluate`); `test_ui_geometry_contract.py` scans every test module that measures the
    browser and fails on literal thresholds, unused or undeclared rules. The baseline gate reports
    every violation in one failure, one line per rule, metric, page and viewport. Prove behavior at
    the lowest layer that can see it: server tests for copy and classes, browser tests for geometry
    and computed color.
19. **Learnings travel with the work.** Each completed UI round writes its new rules, values and
    pitfalls into this document, the recipes or the playbook (and `AI_CONTRACT.md` §7 when it is a
    non-negotiable), and checks its task off in the OpenSpec `tasks.md`, in the same change. A rule
    kept only in chat, a session note or a handoff prompt is lost at the next handoff; a stale
    statement found on the way is corrected against the code, not left for later.

## 8. Toolchain And Quality Gates

Node ≥22. First run: `cd ui_web/frontend; npm ci`.

| Gate | Command | Fails on |
| --- | --- | --- |
| Token and vendor freshness | `npm run check` (token, vendor, Milkdown bundle, CSS lint and contrast checks; no JavaScript lint, no browser QA) | `theme.css` or vendored files out of date with tokens/`package-lock.json`, iconoir subset drift, the Milkdown report-editor bundle or its build inputs differing from their manifest hashes |
| CSS lint | `npm run lint:css` | Raw colors, literal font families, invalid CSS (Stylelint + `stylelint-config-standard`) over every stylesheet under `ui_web/static/css/`, subfolders included; `!important` in `pages/`, `shell/` and `report_*.css` |
| Contrast | `npm run qa:contrast` | Any `level: error` pair in `tokens/contrast-pairs.json` below its minimum in either theme (152 pairs today; new pairs are added at `error`, never `warn`) |
| Browser QA | `$env:DASHBOARD_QA_BASE_URL='http://127.0.0.1:<port>'; npm run qa:browser` (optional `DASHBOARD_QA_BASIC_AUTH=user:pass`, `DASHBOARD_QA_ROUTES`, `DASHBOARD_QA_VIEWPORTS`, `DASHBOARD_QA_FULL_PAGE=1`) | HTTP ≥400, page-level horizontal overflow, wrong applied theme, console errors, same-origin requests that return an HTTP error or get no response (requests aborted by navigation or an htmx swap excepted), serious/critical axe-core WCAG 2.2 AA violations; routes come from the sidebar, in light and dark at 1440×900 and 390×844 |
| Django tests | explicit paths with the selected app interpreter, for example `python -I -m pytest ui_web/tests/test_frontend_assets.py ui_web/tests/test_dashboard_shell_browser.py -p no:cacheprovider` plus the touched page's tests, with `METRICS_*`/`DJANGO_*` cleared and the synthetic Jira variables set (playbook §4.2) | Template contracts, shell behavior, layout metrics |
| Repository gates | `python -I scripts/check_file_size_limits.py --include-untracked`, `python -I scripts/check_diff_whitespace.py --include-untracked`, `git diff --check` | Oversized or unclaimed files, whitespace errors |

File-size caps (changed-file mode; first matching rule wins): Django templates 300 lines, CSS under
`ui_web/static/css/` 400, browser JS 400, frontend tooling `.mjs` 300, frontend config and token
JSON 300, JS tests 600, Python tests 600, Python source 400, AI guidance Markdown 260, other
Markdown 1200, PowerShell 400. Every changed file must be claimed by a rule or an explicit
exemption (vendored, generated, binary, translation catalogs); an unclaimed file fails. Files
already over their cap are legacy allowances: frozen (never grow), owned, with a split plan; the
owner splits the file and deletes the entry, and a meta-test fails on an allowance whose files are
back under their cap. `--all` and explicit-path runs stay strict. Playbook §3 explains how to split
before a file reaches its cap.

Browser QA runs against an isolated development server (its own port and database), never the
user's long-running instance. Screenshots and `report.json` are written to
`ui_web/frontend/.qa/browser/` (git-ignored). Test runs shard browser groups into separate
processes, start with the focused file, and verify a suspected pre-existing failure in a clean
`git worktree` before labelling it (playbook §4.2 and §4.4).

Visual review: after automated gates, open every touched page in a real browser in light, dark
and a 390px-wide viewport, and check hierarchy, alignment, truncation, density and states (empty,
loading, error, long text, Chinese labels). Agents in this repository use ego-browser for this
review, against a freshly restarted preview server with synthetic data and cache disabled (playbook
§5). Keep screenshots out of the repository unless a change explicitly owns visual baselines.

## 9. Definition Of Done For UI Work

A UI change is complete only when all of the following hold:

1. It uses existing tokens and primitives, or it adds the missing token/primitive to the owning
   layer and updates this document in the same change.
2. No retired Bulma vocabulary, undefined modifier class or page-level `!important` was added
   (the design-system tests and stylelint enforce them).
3. Light and dark both look intentional and pass contrast; System follows the OS setting.
4. Desktop 1440×900 and phone 390px have no page-level horizontal overflow and no clipped
   controls, checked in light (its heavier weights set wider text than dark); tables scroll
   inside their container with the thin token scrollbar.
5. Empty, loading and error states exist for every data region touched.
6. `npm run check`, browser QA for the touched routes, focused Django tests and repository gates
   pass, or each failure is recorded with its pre-existing cause.
7. Real-browser visual review was done and its findings fixed or explicitly deferred.
8. Every touched file is within its size cap, a file near its cap was split by concern first, and
   each new shared CSS or JS file is registered in `ui_web/static_assets.py` (report-page assets
   load through their page templates).
9. The constraining test contracts were read before the rewrite and still pass; a contract that
   changed intentionally was updated with a reason.
10. The recipes, the class contract table and the OpenSpec `tasks.md` describe any new primitive,
    token or hook in the same change.
11. Every new user-visible string has its `zh_Hans` translation and a recompiled `.mo`, and
    `ui_web/tests/test_i18n_catalog.py` passes.

## 10. Change Control

- Token changes: edit the JSON, run `npm run build:tokens` and `npm run qa:contrast`, review both
  themes, and record the semantic change here when meaning (not just value) changes.
- New primitive: add it to the `foundation/` file of its concern with tokens only, document it in
  §6 and the recipes, and use it from at least one template in the same change.
- New shared stylesheet or script: register it in `ui_web/static_assets.py` and nowhere else; an
  asset used only by a report page is loaded by that page's template instead. Split the owning
  file first when it nears its size cap.
- Report editor bundle: change `ui_web/editor_build/`, then run
  `scripts/validation/build_report_editor_vendor.py`; commit the changed inputs (source entry,
  `package.json`, lockfile) with the bundle, metafile and manifest (playbook §1.3).
- Rewriting a legacy page: move its styles to `pages/<feature>.css`, delete the rules and scripts
  that become dead, and keep every string and class that a test asserts.
- Dependency changes: pin the exact version in `package.json`, run `npm install`, then
  `npm run build`; commit `package-lock.json`, vendored output, the manifest and notices together
  (playbook §1.1).
- Documentation drift: when a recipe or value here disagrees with the code, verify the code and fix
  the document in the same change.
- Exceptions to this document require a written reason in the OpenSpec change or commit message.
  Silent page-local overrides are review failures.

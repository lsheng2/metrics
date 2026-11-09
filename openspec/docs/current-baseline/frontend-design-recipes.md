# Meridian Frontend Design Recipes

Status: **binding** as part of [frontend-design-requirements.md](frontend-design-requirements.md).
That document holds the normative rules; this one holds the exact tokens, selectors, values and
markup behind them, and the pitfall that produced each recipe. Process, tooling and testing live in
[frontend-delivery-playbook.md](frontend-delivery-playbook.md).

If a selector or value here disagrees with the code, fix the document in the same change. Every page follows these
recipes; page styles live in `ui_web/static/css/pages/<feature>.css` and behavior in `ui_web/static/js/<feature>.js`
(see the playbook's file layers), so a recipe names the file that owns it.

## 1. Token Reference

Tokens are authored in `ui_web/frontend/tokens/*.tokens.json` and generated into `theme.css`. Never write a value below
into a component; reference the token.

### 1.1 Color values that were tuned for contrast

| Token | Light | Dark | Rule |
| --- | --- | --- | --- |
| `--color-accent` | `#3e63dd` | `#3e63dd` | Interaction and selection only. |
| `--color-accent-hover` | `#3358d4` | `#435db1` | Dark hover is *darker* than the accent so on-accent text keeps AA. |
| `--color-text-tertiary` | `#696c75` | `#8e929a` | At least 4.5:1 on canvas, surface, muted, raised and hover. `#80838d` and `#777b84` failed. |
| `--color-border-input` | `#8b8d98` | `#696e77` | The 3:1 control boundary (WCAG 1.4.11). |
| `--color-warning` (solid) | `#ffc53d` | `#ffc53d` | About 1.6:1 on white: glyph fill only, never text, a line or a chart mark. |
| `--color-warning-text` | `#966400` | | AA-tuned amber text. |
| `--color-info-text` | `#0969da` | | AA-tuned. |
| `--color-warning-subtle` | `#fff7c2` | `#302008` | Pale fill; the saturated step looked alarming. |
| `--color-on-warning` | amber 12 | amber 1 | Dark ink on the solid warning fill in both themes. |
| `--color-on-success\|danger\|info` | | | Glyph-only on solid fills (3:1), for example the `.provider-tab-check` tick. |

- Chart slots `--color-chart-1..8` run indigo, teal (`#12a594`), orange (step 10, `#ef5f00`; step 9 is 2.97:1), crimson,
  cyan, grass, violet, amber (`#ab6400`). Every slot is at least 3:1 on `--color-surface` in both themes.
- Bug-trend series tokens: `--color-series-all-open-bugs`, `-all-open-critical-high` (orange 10), `-new-critical-high`,
  `-new-medium-low`, `-fixed-or-closed-bugs`.
- Health tokens (`--color-health-green|yellow|orange|red|gray`) are chosen by contrast on `--color-surface` and
  `--color-surface-muted` (at least 3:1), not by ramp convention. Light: `#3e9b4f` (grass 9 is 2.88:1 on muted),
  `#b07a00`, `#ef5f00`, `#e5484d`, `#8b8d98`. Dark: `#53b365`, `#ffc53d`, `#ff801f`, `#ec5d5e`, `#696e77`. Register every
  new health or chart color in `contrast-pairs.json` with level `error`.
- Provider colors are theme-independent: green `#2f9e44`, blue `#1c7ed6`, purple `#8b5cf6` (`--color-provider-*`). Tests
  assert the blue as `rgb(28, 126, 214)`.
- Paper tokens `--color-paper-*` are emitted on `:root` and mirror the report export palette: bg `#ffffff`, bg-muted
  `#f8fafc`, text `#1f2933`, link `#0f766e`, rule `#cbd5e1`, table-header `#ecfeff`, accent `#0f766e`, control `#64748b`,
  selection `#bfdbfe`.

### 1.2 Type values

- Weights: light 400/500/600/700, dark 380/480/580/680 (a `weight` group in `theme.dark.tokens.json`; light strokes look
  heavier on dark). `.paper` redeclares `--weight-*` from `--weight-paper-*` (fixed 400/500/600/700) so authored content
  stays at 700 bold.
- Buttons, labels, navigation and table headers are weight 500 or lighter (the baseline gate caps button weight at 500).
  Never 650, 700 or 800 on labels or kickers.
- Mona Sans keeps its slashed zero (the font has no plain-zero alternate), which helps separate 0 from O in data. Tables
  and numbers use `font-variant-numeric: tabular-nums`.
- Width axis: `--stretch-display` (112%) on page titles and `.stat__value`; `--stretch-condensed` (92%) is defined and
  currently unused. Preload `vendor/fonts/mona-sans-latin-wdth-normal.woff2`; fonts are Fontsource woff2 (latin and
  latin-ext) with `font-display: swap`.
- The root is 16px, so `1.72rem` is 27.5px. Tests assert pixel values; convert before changing a rem value that a geometry
  test measures.

### 1.3 Layout, space, radius, layers

| Group | Tokens |
| --- | --- |
| Layout | `--layout-sidebar-width` 15rem, `--layout-sidebar-rail` 3.25rem, `--layout-topbar-height` 2.75rem, `--layout-statusbar-height` 1.75rem, `--layout-content-max` 112rem, `--layout-gutter` 1.25rem |
| Space | `--space-1 2 3 4 5 6 8 10 12`, `--space-px`, `--space-0-5`, `--space-1-5`, `--space-2-5`. No `--space-3-5` or `--space-7`: pick an existing step. |
| Radius | xs 3px (inline `code`), sm 4px (`pre`, `kbd`, chip-disclosure summary), md 6px (buttons, inputs, board cards), lg 10px (surfaces), xl 14px (dialogs, drawers), full (pills, tags, avatars, dots, count badges, series toggles) |
| Controls | `--control-height` 2rem, `-sm` 1.75rem, `-xs` 1.5rem; `--control-label-height` 1.375rem is the field label row (form-field label, a fieldset legend that sits in the same row) |
| Layers | sticky 10, topbar 30, statusbar 35, dropdown 40, overlay 45, drawer 50, toast 60 |

Tags are pills (`--radius-full`), not `--radius-xs`. Literal radii and raw z-indexes in legacy page CSS are replaced with
`var(--radius-*)` and `var(--z-*)` whenever a rule is touched.

## 2. Document And Shell

### 2.1 `base.html` contract

- `<meta name="color-scheme" content="light dark">`; the server default is `data-theme="light"`.
- htmx config meta: `{"historyCacheSize":0,"refreshOnHistoryMiss":true,"includeIndicatorStyles":false}`. Back navigation
  therefore reloads the full page; verify it with `history.back()`.
- Two inline scripts run before first paint, each inside try/catch: the shared `partials/theme_bootstrap.html` restores
  `dashboard-theme` (`data-theme`, `data-theme-preference`), and a `base.html`-only script restores
  `metricsDashboard.sidebarCollapsed` (`html[data-sidebar="collapsed"]`) and `metricsDashboard.sidebarWidth` (applied as
  `--dashboard-sidebar-width` only when 168–360). The brand link is `partials/app_brand.html` (see 2.8).
- Scripts load synchronously in `<head>` (htmx, Chart.js UMD, the date-fns adapter bundle required by `type: 'time'`, the
  annotation plugin which self-registers, `charts.js`, `shell.js`, `command-palette.js`, then the feature modules in
  `FEATURE_SCRIPTS` order; the exact list is `ui_web/static_assets.py`) because inline page scripts use them;
  `extra_js` renders at the end of body. Strip the `//# sourceMappingURL` comment from vendored UMD files: under the
  manifest backend a missing map breaks `collectstatic`.
- Blocks: `html_class`, `title`, `extra_css`, `body_class`, `breadcrumbs`, `page_title`, `header_extra`, `content`,
  `footer`, `extra_js`. `base.html` reads `request.GET`, so the `request` context processor is required.
- `#loading-indicator` is the global `progress.app-progress`; use `hx-indicator="#loading-indicator"`. `.htmx-indicator`
  fades but still occupies space.
- `.app-toasts#notification-container[aria-live="polite"]` is fixed and sits *outside* `#main-content`, otherwise an htmx
  swap wipes it. 4xx/5xx responses are not swapped; `htmx:responseError` and `htmx:sendError` replace the container's
  content with one toast: `div.message.is-danger > div.message-header` (a `p` title and
  `button.delete[type=button][aria-label="Dismiss"]`) `+ div.message-body` (`p > strong` with status, text and URL, plus a
  retry hint for 503). `htmx-lifecycle.js` builds it with DOM APIs, never `innerHTML` with response text. The toast has
  no `role`: the container already is the live region, and a nested `role="alert"` would announce twice. It sits on the
  raised surface with a 3px inset tone edge and `--shadow-lg`.
- `partials/loading_indicator.html` (in-region loading) is `div.loader-block[role=status] > span.loader[aria-hidden=true]
  + span.is-sr-only` "Loading…": a centered spinner whose text is read, not shown.
- Scrollbars: `html { scrollbar-color: var(--color-scrollbar) transparent }` passes the token color down, and
  `* { scrollbar-width: thin }` (in `foundation/base.css`) applies the thin bar to every scroll container, because
  `scrollbar-width` does not inherit; without it, inner table containers drew the classic 15px bar. Strips that hide
  their bar set `scrollbar-width: none` on the component.

### 2.2 Title, breadcrumbs, document title

- The topbar `h1.app-crumbs__page` is the `page_title`; in-page headings start at `h2`. The topbar is sticky (2.75rem) and
  the document scrolls.
- Top-level pages show "Group / Page" through the default `{% block breadcrumbs %}`. Deeper pages override the block with
  bare `<a>` ancestor links starting at the navigation destination (no group); the current page stays the `page_title`.
  Never put `nav.breadcrumb` in page content.
- `nav.app-crumbs__trail[data-shell-crumb-trail]` hides itself when it has no children (the group span has no surrounding
  whitespace for `:empty`). Items are at most 14rem with an ellipsis; at ≤768px only the last item shows. Tests select
  `.app-crumbs__trail a[href]`.
- After an htmx swap into `#main-content`, `shell.js` (`syncNavigationState`) sets `aria-current`, the crumb page text,
  resets the trail to the group span and sets `document.title` to "label · Metrics".
- Page names come from the navigation registry: `base.html` fills `title` and `page_title` with the active item's
  label, the same name `syncNavigationState` writes after a sidebar swap. Top-level pages override neither block (a
  restated or legacy title such as "Bug Trend Indicator" showed on full loads only). A deep page sets both through
  `{% trans %}` (`{% trans "Scope Audit" %}`) and translates its ancestor crumb links;
  `test_shouldTranslateShellBlocksInEveryTemplate` rejects bare English in `title`, `page_title`, `breadcrumbs` and
  `header_extra`.
- The report editor exit guard is a document-level capture click listener on `a[href]`, so topbar crumbs are guarded too.

### 2.3 Sidebar, rail, drawer, splitter

- Expanded 15rem, rail 3.25rem. Collapse with the `[data-shell-collapse]` button or Ctrl/⌘+\; the state persists in
  `metricsDashboard.sidebarCollapsed`. The theme radiogroup (`.theme-switch[data-theme-switch]` with `[data-theme-choice]`
  buttons) and the collapse button live in `.app-sidebar__footer`, not in the topbar. When the sidebar is collapsed (and
  on phones) the topbar shows a search button that opens the palette.
- Sidebar splitter (`data-dashboard-sidebar-splitter`, `role="separator"`): min 168, max 360, default about 248, arrow
  keys ±16, double-click resets, persisted in `metricsDashboard.sidebarWidth`.
- Drawer (≤768px): `.app-main` gets `inert`, a scrim covers the page, focus moves to the active nav link, and Escape, a
  scrim click, a nav click or widening past 768px close it and restore focus to the opener.
- Drawer motion lives only on `html[data-drawer]` states: the resting phone sidebar has no transition (otherwise it
  slides across the content whenever the viewport crosses 768px); `open` transitions `transform`; `closing` transitions
  `transform` plus `visibility 0s linear var(--duration-slow)`. `shell.js` sets `closing` on phones and clears it after
  the computed `transitionDuration` + 50ms only if it is still `closing`; on desktop it deletes the attribute at once.
  Reduced motion targets `html[data-drawer] .app-sidebar` (a bare `.app-sidebar` loses to the state rules). Guard:
  `test_shouldHideDrawerAtOnceWhenViewportCrossesPhoneBreakpoint`.
- `NavItem` carries `key`, `label` (`gettext_lazy`), `url_name`, `icon` (the full class string, for example
  `iconoir-home-simple`), `description`, `active_url_names`, `active_url_prefixes`, `partial_url_name`,
  `member_group_filter`, `keywords`. Links render as `.app-nav__link` with `data-nav-label` and `data-nav-group-label`;
  `qa:browser` route discovery reads those links. Any `hx-push-url` target must appear in the item's `active_url_names`,
  so a pushed partial URL keeps navigation active.
- Member-group submenus: the parent link is a plain full-page link; a separate chevron
  `.menu-toggle.app-nav__toggle[data-target][aria-expanded]` toggles `ul.menu-submenu.is-hidden`. Sub-links use
  `hx-get="{partial}?member_group_id=…"`, `hx-target="#main-content"`, `hx-indicator="#loading-indicator"` and
  `hx-push-url`. There is no "All Groups" entry, and the member-group switcher is safe only on velocity pages (not Current
  Tasks).
- The context processors `dashboard_navigation`, `member_groups` and `service_status_bar` return `{}` for `HX-Request`.
  Page filters and switchers must therefore render from view context, or they vanish after sidebar htmx navigation.
- Icon names must exist in the pinned Iconoir version (7.12.2 has no heartbeat, keyboard, command, chart-line,
  sparks-solid or db-check); `build:vendor` fails on unknown names.

### 2.4 Command palette

Native `<dialog class="command-palette" data-shell-palette>`. Ctrl/⌘+K toggles; `/` opens it only outside text entry and
without modifiers; Escape closes natively; `aria-activedescendant` tracks the active item; Enter runs it (the first by
default); Ctrl/⌘+Enter opens a new tab. Items carry `data-palette-href` or `data-palette-action` (`theme:*`,
`sidebar:toggle`); the current page is `aria-current="page"`. `command-palette.js` uses `window.DashboardShell`.
Search matches `data-palette-text`: navigation items join the translated label, group and description with the English
label and group (`{% language 'en' %}`) and the item's keywords; actions join their `{% trans %}` labels with English
words. "bug" and "缺陷" both find Bug Trend.

### 2.5 Theme switching mechanics

- `window.DashboardShell.applyTheme(pref)` sets `data-theme-switching` only when the resolved theme changes, syncs the
  radio controls, then forces a style flush (`getComputedStyle(root)`) *after* syncing, removes the flag with
  `setTimeout(0)` and dispatches `dashboard:themechange` (`{theme, preference}`) only when the resolved theme changed. Do
  not hold the flag for a frame: transitions must never run during a flip.
- A live `matchMedia('(prefers-color-scheme: dark)')` change listener makes System follow the OS without reload; Chromium
  fires it on the next frame, so probes wait one `requestAnimationFrame`. A `storage` event syncs other tabs. Tooltips
  come from `data-theme-hint-light|dark`.
- After a probe leaves `localStorage["dashboard-theme"]` set, clear it: a leftover made System look stuck on light.
  Headless Chromium defaults to light.

### 2.6 Fixed chrome reserves its space

- `--app-statusbar-offset` defaults to `0px` on `.app-body` and becomes `--layout-statusbar-height` when `.app-body:has(>
  .workbench-status-bar)`. `.app-body` pads its bottom by it; `.app-shell` and `.app-main` use `min-height: calc(100dvh -
  var(--app-statusbar-offset))`.
- `html { scroll-padding-top: var(--layout-topbar-height) }` and, with a status bar, `scroll-padding-bottom:
  var(--layout-statusbar-height)`.
- `.app-content` bottom padding is `--space-8` (`--space-6` on phones); toasts sit at `calc(var(--app-statusbar-offset) +
  var(--space-4))`.
- Why: tests that appended hosts to `document.body` had their clicks intercepted by the fixed bar.

### 2.7 Workbench full-bleed mode

- `html_class` and `body_class` add `has-workbench-shell`. From 1024px the Workbench is a full-bleed IDE frame
  (`shell/statusbar.css`): `position: fixed` (`inset: 0 0 var(--app-statusbar-offset) 0`), content edge to edge, no
  topbar (so the `h1` is hidden), chart over evidence beside the AI pane in a two-column grid sized by the splitters, the
  chart filling its pane and a collapsed AI pane shrinking to a 40px rail whose button reads "AI".
- Below 1024px it is an ordinary scrolling page with the topbar. The panes stack at full width (chart, evidence, AI), the
  pane splitters are hidden, the chart keeps the standard 22.5rem frame, and collapsing the AI pane hides only its body:
  the header stays and the button reads "Expand", like the chart pane (`pane-layout.js` picks the label with
  `matchMedia('(min-width: 1024px)')`). The 1024px/1023px pair is the only Workbench layout breakpoint, because two panes
  side by side need that width (§3.4). The base styles are the stacked page; the IDE frame lives in `min-width: 1024px`
  blocks. Guarded by `test_shouldStackWorkbenchPanesIntoAScrollablePageOnPhones` (390×844: scrollable page, visible
  topbar, stacked full-width panes, `WORKBENCH_PHONE_CHART_MIN_HEIGHT`, one-line pane titles, pane headings that stay
  clear of their actions within `OVERFLOW_TOLERANCE`, revealed ticket detail, AI pane above the status bar).
- Splitters are focusable `role="separator"` elements, so each needs `aria-valuenow/min/max`. `syncSplitterValue(splitter,
  value, min, max)` also sets `aria-valuetext` "N pixels", is NaN-safe and must run on init, in every setter and in
  double-click resets (axe `aria-required-attr`). Constants: AI rail 40 (tests bound it by
  `WORKBENCH_COLLAPSED_AI_WIDTH_MAX`), expanded 280–600 (floor guarded by `WORKBENCH_AI_PANE_MIN_WIDTH`), default 340
  (`--workbench-ai-width`); chart-evidence `--workbench-chart-height` default `38vh`, collapsed ≤52, min 50, max = grid
  height − 240; ticket-detail 180–360, default 245 (`--workbench-ticket-detail-width`), ArrowLeft widens by 16. The
  ticket-detail splitter must work without `#workbench-grid`.
- `initializeWorkbenchShell()` runs at load and on every `htmx:afterSwap`, guarded by `dataset.workbenchInitialized`.
  Persisted keys: `metricsWorkbench.aiWidth`, `.chartHeight`.
- Required hooks: `data-dashboard-layout`, `data-dashboard-sidebar`, `data-dashboard-sidebar-splitter`,
  `data-workbench-nav-link`, `data-workbench-status-bar`, `data-workbench-job-status`.
- `.workbench-toolbar` is a CSS container (`container: workbench-toolbar / inline-size`); `@container workbench-toolbar
  (max-width: 65.5rem)` switches its grid to four columns.
- Evidence in the page flow (Bug Trend, and the stacked Workbench) caps the table wrap and the ticket detail with
  `--evidence-page-max-height: max(18rem, 100dvh − topbar − statusbar-offset − space-8 − space-6)`, defined on
  `.workbench-evidence-layout`, so the sticky header, the horizontal scrollbar and the detail fit on screen. Bug Trend also
  makes the detail sticky: `#bug-trend-content .workbench-ticket-detail { position: sticky; top:
  calc(var(--layout-topbar-height) + var(--space-3)); align-self: start }`. Scope that rule to `#bug-trend-content`:
  `#bug-trend-evidence-container` is shared with the Workbench, where `.workbench-pane-body` is the scroller.
- At ≤768px the ticket detail stacks under the evidence table on both pages (one column, detail splitter hidden).
  `openDetail()` in `workbench-evidence.js` then scrolls it into view with `scrollIntoView({ block: 'nearest' })`, only
  when the detail sits below the table: beside the table, `scrollIntoView` would also scroll the `overflow: hidden`
  full-bleed ancestors. Handlers call `openDetail()` after filling the detail, so the scroll uses its final height.
- The evidence partial (`partials/bug_trend_evidence.html`) is shared. The Workbench includes it `with
  workbench_evidence=True`: the partial then renders the Workbench's single URL-state filter form
  (`partials/workbench_evidence_filter.html`, `hx-target=".workbench-shell"`, `hx-push-url`) and omits its htmx Clear
  selection, because the pane header owns the URL-state one. Without evidence the Workbench renders the same form in
  the pane body. The Bug Trend form and Clear selection target `bug_trend_evidence` and render only on Bug Trend.
  Guarded by `test_shouldRenderOneUrlStateEvidenceFilterInsideWorkbenchEvidenceCard`.
- `.workbench-evidence-card` fills its pane (`min-height: 100%`) only inside the 1024px+ IDE frame. In the stacked page
  the pane row is content-sized, and a percentage min-height resolves against the stretched row, so any sibling's
  height reappears as blank space inside the card (a duplicate filter form once left about 180px under the table and
  under the detail).
- The first `.workbench-menu-panel` inside `.workbench-evidence-actions` opens with `right: auto; left: 0`, or it slides
  under the sidebar once the heading wraps (the rule is shared with `.scope-row-menu` and the provider menus).

### 2.8 Standalone frame (error and bridge pages)

- Pages outside the shell extend `standalone_base.html`: `{% dashboard_stylesheets %}`, the theme bootstrap partial, the
  brand partial in `{% block header %}` and `main.standalone-main#app-content`. It loads no script and needs no context
  processor, because Django's `server_error` renders `500.html` with an empty `Context`. Styles live in
  `css/shell/standalone.css`.
- `partials/theme_bootstrap.html` is the only theme no-flash script; `base.html` and the standalone frame both include
  it. `partials/app_brand.html` resolves home with `{% url 'ui_web:homepage' as brand_home_url %}` plus `|default:'/'` (a
  failed reverse stays silent). Never hardcode `/`: `METRICS_BASE_URL` may prefix every route.
- Error panel: `section.standalone-panel[aria-labelledby]` with `__icon` (`.is-danger` for 5xx), `p.eyebrow` ("Error
  404"), `h1.standalone-panel__title`, `__body`, `__meta` (the quoted `request_path`, or a `{% now %}` time) and
  `__actions` with exactly one primary. Never print `exception`. "Go back" ships `hidden`; a small `extra_js` reveals it
  only when `history.length > 1`. The bottom padding is double the top, so the panel sits on the optical centre.
- Embedded bridge pages (the Grafana selection page inside the 360px panel iframe) set `body_class` `is-embedded`
  (surface background, compact padding) and empty the header block. A `.standalone-status[role=status]` with `.loader`
  shows while the script posts to the parent; opened top-level, the script hides it and reveals the `hidden` fallback
  (one sentence and a primary link that carries the non-empty selection query).
- Verify with DEBUG off: DEBUG on renders Django's technical page, so the local demo needs preview routes. Tests use the
  client for 404 and `defaults.server_error(RequestFactory().get(...))` for 500.

## 3. Page Anatomy And Filters

### 3.1 Page wrapper and header

- Wrapper `article#<page>.block` holds `header.page-header` with `h2.page-header__title` (optional help tip) and
  `p.page-header__meta`. The header stays outside the error branch. Errors render `.message.is-danger[role=alert]`;
  disabled or unconfigured states render `.empty-state.is-warning`. `GracefulTemplateView` sets `context["error"]`, so
  partials must render when context keys are missing.
- `.page-header` is a wrapping flex row (space-between, gap `--space-3`, margin-bottom `--space-4`); the title is
  `--text-xl` semibold; `__meta` is `--text-sm` secondary and lets `<code>` ids and hashes wrap anywhere. Action order:
  language switcher, `button is-small` links, the primary action last; a creating button uses `iconoir-plus`. Page-header
  buttons keep `is-small`; tool and filter forms never do.
- Keep `.scope-library-header` on the Scope Library header only (tests hover `.scope-library-header .page-header__title`).
  Provider list pages have no breadcrumb. Bug Trend actions are icon links in `page-header__actions` (Scope Audit
  shield-check, Scope Config settings, Scope Library filter-list); Scope Config shows the Scope Audit crumb only `{% if
  config.id %}`.
- Homepage cards are data-driven from `dashboard_navigation` (skip group `overview`) plus `global_service_statuses`, in
  `repeat(auto-fill, minmax(16.5rem, 1fr))`. Service tones: success for connected, available, ready; info for configured,
  starting; warning for auth, degraded, other; neutral for disabled, unavailable, unreachable, stopped. Count badges use
  `.count-badge`, group titles use `.eyebrow`.

### 3.2 Filter toolbar

- Markup: `form#<id>.box.dashboard-tool-form.dashboard-top-toolbar[aria-label]` with `hx-get`, `hx-target`,
  `hx-push-url="true"` and one `.dashboard-tool-grid.is-toolbar`.
- `.dashboard-tool-grid.is-toolbar`: flex wrap, `align-items: flex-end`, `gap: var(--space-2) var(--space-2-5)`; `>
  .dashboard-tool-field { flex: 1 1 10rem; max-width: 22rem }`; `> .dashboard-tool-actions { flex: 0 0 auto }`, with
  `.is-right` taking `margin-left: auto`. The plain grid is `repeat(auto-fit, minmax(10rem, 1fr))`.
- Every select has `label.label[for]` (help tip inside the label, no trailing colon) and a first option "All". Apply
  (`is-primary`) and Clear share one `.dashboard-tool-actions`; Clear renders only when a selection exists. Render hidden
  params only when they carry a value. Velocity filters use `.dashboard-tool-field.has-inline-help` with the view toggles
  in `.is-right`.
- Control heights come only from foundation sizes. One size per form: page-level filters use the default 32px and no
  `is-small`; filters nested in a card may use `is-small`. Never hard-code button or control heights in page CSS.
  `--workbench-toolbar-control-height` is `var(--control-height-sm)`. Mixed rules such as `.dashboard-tool-actions
  .button` (2rem) and `.buttons.are-small .button` (1.75rem) clash at equal specificity: unify them in one place.
- The view chooses the partial from `HX-Target`, computes `view_queries.{list,board,clear}` so a layout switch keeps
  filters (strip `view` and `expand_all`), and never reads the data container in `__init__`: resolve it in
  `populate_context` so an unconfigured source still renders the page.
- Forecast uses one compact toolbar row with no "Forecast Parameters" title. The facade hard-codes `task_title="SUMMARY"`;
  never display it.

### 3.3 Results bar and view switches

`.results-bar`: left `p.results-bar__count[role=status]` with `<strong>N</strong> task(s)` (plus "match the filters" when
filtered); right `.results-bar__actions` holding a layout segmented control
`.buttons.has-addons.are-small[role=group][aria-label="Layout"]` whose buttons carry `aria-pressed`, `is-selected`,
`hx-get` and push. "Expand all" shows only for list, grouped and lazy layouts; "Collapse all" only when `expand_all and
lazy_loading_enabled`. A zero result renders an `.empty-state` with a Clear action when filtered. List pages put
`.results-bar` above `.table-container.responsive-admin-table-box.is-framed`; a create form is a `details.popover` button
(open server-side when the form has errors) and the table comes first.

### 3.4 Grids and narrow screens

- Single-column grids use `grid-template-columns: minmax(0, 1fr)` (report forms, form fields); otherwise a long word
  widens the page.
- `.chart-grid.is-2` is `repeat(auto-fit, minmax(min(100%, 30rem), 1fr))` with no media query.
- Sanctioned exceptions to the single 768px breakpoint: container queries on `.responsive-admin-table-box` (`@container
  (max-width: 40rem)`) and on `.workbench-toolbar`, and the Workbench layout pair `min-width: 1024px` / `max-width:
  1023px` (§2.7). Form grids need no breakpoint: `.dashboard-form-grid` sizes its columns from the container, and below
  1024px the Workbench toolbar and evidence filter grids keep two columns down to phone width, with the first field and
  the action spanning both, so filters stay dense and the two forms line up. Stylelint allow-lists every media width
  per file (`media-feature-name-value-allowed-list` in `ui_web/frontend/.stylelintrc.json`), so any other width fails
  `npm run check`. Existing legacy media queries at other widths are migrated to 768px when their rules are touched;
  do not add new ones.
- `.dashboard-form-grid` is three columns; `.is-stacked` is one column (gap `--space-3`). `.dashboard-form-field` is a
  two-row grid with a minimum label row.
- A starter gallery uses `.template-starter-grid` (`repeat(auto-fill, minmax(16rem, 1fr))`) of `.template-starter` cards.
  Never lay several `form.box` cards out in fixed columns (the retired `.columns` caused a 70px overflow).
- Wide primary columns get a min width so phones scroll inside the container (`.task-table__task` 16rem,
  `.pr-table__title` 18rem).
- At ≤768px `.disclosure__meta` and `.disclosure__summary > .avatar-stack` are hidden; never put `min-width: 0` on
  `.disclosure__title`.
- Every row of buttons wraps: `.buttons.has-addons` and report toolbars use `flex-wrap: wrap` (a `nowrap` four-button
  group was 512px wide); `.dashboard-tool-actions .button` is full width on phones.

## 4. Controls And Forms

### 4.1 Buttons

| Variant | Look | Rule |
| --- | --- | --- |
| `.button` | outline, 32px, weight 500, `--radius-md`, `--shadow-xs` | Default for secondary actions. |
| `.is-primary` | ink (`--color-surface-inverse`) | One per region; place the primary action last. |
| `.is-link` | accent solid | The single most important call to action. |
| `.is-light` | ghost | Only on a plain `.button`: never with a semantic variant, never on a `.tag` (test-enforced). |
| `.is-info` | soft accent | |
| `.is-success\|warning\|danger` | always soft: subtle fill, `-border`, `-text`, `-subtle-hover` on hover | Never solid. |
| `.is-selected`, `.is-active`, `.toggle-button:has(> input:checked)` | soft-accent selected state | Toggles use these plus `aria-pressed`, not `is-info`. |
| `.is-small` | 28px, `--text-xs`, icon 0.875rem | The icon rule has specificity (0,3,0); overrides must match it and load later. |

- A rule that overrides a primitive silently breaks it (`.select.is-small` once lost the padding that makes room for its
  arrow). Inline action forms use `.dashboard-action-form.is-row` (flex wrap, gap `--space-2`) or `.is-stacked` (grid).
- Toggle: `label.button.is-small.toggle-button` whose `input` is absolutely positioned (`inset: 0`, opacity 0); focus ring
  through `:has(> input:focus-visible)` (2px, offset 1px, z-index 2). Inputs need ids so htmx can restore focus after a
  swap.
- Segmented source-mode switch: `.buttons.has-addons[role=radiogroup][aria-label]` of
  `label.button.is-small.toggle-button[for]`, each wrapping its radio. The selected look comes only from
  `.toggle-button:has(> input:checked)`: no `.is-sr-only` radios, no `is-primary`, no class toggled by script. No other
  segmented primitive exists.
- Icon buttons need `aria-label` and `title`. "Test connection" is a plain neutral `.button` with `formnovalidate`.
  Destructive actions are visually secondary; row menus use `z-index: var(--z-dropdown)`.

### 4.2 Text controls and selects

- `.input`, `.textarea`, `.select select`: side borders `--color-border-strong` with `border-bottom-color:
  var(--color-border-input)`; hover darkens every side; focus is the accent border plus a 3px `--color-focus-halo`.
- `.select.is-small select { padding: 0 var(--space-6) 0 var(--space-2) }` and `.select.is-small:not(.is-multiple)::after
  { right: var(--space-2-5) }`: a size modifier must not shorten the padding that makes room for the arrow.
- Labels are 12px medium secondary text in sentence case. The kicker pattern (`.scope-config-kicker`) is xs, weight 500,
  secondary; only `.eyebrow` is uppercase. Textareas that hold JSON, JQL or ids get `spellcheck="false"`.

### 4.3 Required, dirty and validation markers

- `.dashboard-required-tag` is quiet text, not a `.tag`: `--text-2xs`, tertiary, weight 400, no background, border or
  padding, `margin-left: auto`, placed after the label text and its help tip. Wording: "Required to save", "Required for
  test", "Required for enable/test". Never `tag is-small is-danger`; a design-system test forbids danger tags for required
  markers.
- Dirty marker: `span.tag.is-warning.dirty-marker[data-dirty-marker]` with the text "Unsaved *", appended to
  `label[for=id]`. Label order is text, help tip, required tag, dirty marker; `.dashboard-required-tag ~ .dirty-marker`
  drops the marker's auto margin so both sit together on the right.
- Behavior (`form-validation.js` for required state and confirms, `editor-forms.js` for dirty state and auth panels):
  `fieldShell` is the closest `.dashboard-form-field`, `.provider-form-field`,
  `.scope-config-form-field`, `.provider-json-panel` or `.scope-config-form-field-wide`; the label prefers
  `data-required-label`; required defaults come from the form's `data-required-actions` with per-field overrides; only
  visible, enabled fields count (a closed `details` is ignored), in DOM order; `[data-disable-when-clean]` and
  `[data-dirty-guard]` use the confirm text "Discard unsaved changes?"; dirty classes are `is-dirty-field` and
  `is-dirty-control`. The control states `is-dirty-control` (`editor-forms.js`) and `is-required-missing-control`
  (`form-validation.js`) are styled once by the `foundation/forms.css` hooks (warning border and ring; danger border
  and ring), never by page CSS. Auth panels toggle `.is-hidden` and disable inputs through `[data-auth-modes]`,
  `[data-auth-empty-panel]`, `[data-provider-ids]` and `[data-provider-auth-select]`. The label-strip selector must
  include `.dashboard-required-tag`.
- Editors carry exactly one `[data-required-summary]` and one `[data-dirty-banner]`; `data-dirty-form` may appear only on
  Scope Config and the provider editor; tool forms never carry it.
- Messages are `.message.is-X > .message-body` (`.notification` is retired). Errors use `role="alert"`; info, success and
  warning use `role="status"`. The provider page renders `<p><code>field</code>: msg</p>`; Scope Config keeps the plain
  `field: message` strings because tests assert them. Inline links in a `.message-body` take the tone text color and an
  underline from the foundation, so color is never the only cue.
- Never print `{{ form.errors }}`: Django's error dict exposes field names such as `series_id` or
  `expected_series_policy_hash`. A form whose fields are all visible puts `p.help.is-danger#<id>_error` under each control
  (the control carries `aria-invalid` and `aria-describedby`) and its non-field errors in one danger message. A form with
  hidden or loop-rendered fields includes `partials/form_error_summary.html` with `form=`: one danger message listing
  non-field errors, then `<strong>label</strong> error` per field. When two forms mirror one selection (daily preview and
  prepare), only the first form shows its summary. A design-system test forbids raw `.errors }}` output.

### 4.4 Action bar and signature grid

- `.dashboard-action-bar` holds `.dashboard-action-group` rows: primary (Save, Enable), secondary (Test, Create Scope) and
  cancel. Cancel is `type="reset"[data-dirty-reset]` and its group takes `margin-left: auto`. Gap is `--space-2` inside a
  group and `--space-3` between groups. No forced button heights. The bar is shared with `projects/reports/assist.html`,
  so keep its base rules generic.
- Signature grid markup: `dl.dashboard-signature-grid > div.dashboard-signature-item > dt.dashboard-signature-label + dd >
  code.dashboard-signature-value` (`|or_dash` for empty values). Values are mono 2xs and `overflow-wrap: anywhere`.
- Live save, copy or export feedback is one `p.status-line[role=status]` that keeps its `data-*-status` hook. It is xs
  secondary text with a `::before` tone dot and collapses when `:empty`. JS sets the text and toggles only `is-success`,
  `is-warning` and `is-danger` on that element: never `is-light`, never a `.tag` or `.message`. Inside an action bar
  it sits beside the primary button with `margin: 0; min-width: 0`.
- `.dashboard-form-field` sizes every `.input`, `.select` and `select` inside it to `--control-height` at `--text-sm`, so
  `is-small` there is a no-op: leave it off. A checkbox row that end-aligns with those controls takes `min-height:
  var(--control-height)`. Compact chrome (a block head select, matrix inputs) keeps `is-small` beside 28px icon buttons.

### 4.5 Help tips and popovers

- `partials/help_tip.html` renders a `span.help-tip[role=note]` whose `::after` bubble reveals on hover or focus. The
  bubble needs a parent from the reveal list in `pages/common.css` (`h2`–`h4`, `.page-header__title`,
  `.card-header-title`, `.label`, `th`, `dt`, `strong`, `summary`, `p`, `span`). `.card` never clips (no `overflow: hidden`; edge children
  inherit the radius), so tips and popovers escape; never clip an ancestor of a help tip. `.stat__label` clips overflow,
  so `.stat__label:has(.help-tip) { overflow: visible }`.
- `<details class="popover"><summary class="button …">…</summary><div class="popover__panel">…</div> </details>`;
  `shell.js` closes it on outside click and Escape and returns focus to the summary. Panel: min 16rem, max `min(26rem,
  calc(100vw - 2 * var(--layout-gutter)))`, `z-index: var(--z-dropdown)`, `.is-start` aligns left.
- A tip beside a tag in a table cell wraps both in `span.scope-tag-tip` (inline-block, `flex: none`, nowrap) inside a
  `td.has-help-tip`, so the zero-width anchor keeps the tag's baseline; `pages/dense-tables.css` sets `overflow:
  visible` on `has-help-tip` cells of dense and admin tables, so the cell never clips the bubble.
- Wide reference popovers (Scope Library "Readiness matrix") add a page class on the panel: `width: min(52rem,
  calc(100vw - 2 * var(--layout-gutter))); max-width: none; max-height: min(70vh, 40rem); overflow-y: auto`. The panel
  stays right-aligned (`left: 0` pushes it off a phone screen). The summary is a ghost `button is-small is-light` with a
  leading icon so it reads as a control, not a label.
- A table inside a popover keeps the table contract: Chromium hides closed `details` content with `content-visibility`,
  so layout probes (`offsetWidth`, `getClientRects`) still count it as visible. Prose tables wrap through
  `.table.<name> :is(th, td) { white-space: normal; overflow-wrap: break-word; vertical-align: top }`, sit in a
  `responsive-admin-table-box` and add `is-cardable` plus `data-label` cells, so phones get cards instead of a sideways
  scroll.

## 5. Tags, Tones And Status

- `.tag` is neutral by default (`--tone-*` custom properties), a pill, 1.25rem high (`.is-small` 1.125rem at `--text-2xs`,
  `.is-medium` 1.5rem), inline-flex with `gap: var(--space-1)`. Its outline is an inset 1px box-shadow, so `border-color`
  or `border-left-width` on a tag is a no-op. Identity cues use a `::before` 7px dot colored by `--provider-color`.
- Define `--provider-color` once: `:where(.is-provider-green|blue|purple) { --provider-color: var(--color-provider-*) }`,
  neutral `--color-text-tertiary`. Use it for the tab underline, the check badge, tag dots and card accents.
- The provider rail is `border-left: 2px solid var(--provider-color, var(--color-border-strong))` on the editor form,
  over the box's 1px border. Tests read the form's `borderLeftColor` and the selected tab's `borderBottomColor`, so keep
  both as real borders, never a shadow or pseudo-element.
- Wrap tag groups in `span.tags`. A page-level `display` override on `.tag` (for example `inline-block`) kills the flex
  gap and every icon spacing. The only tolerated legacy override is `height: auto; line-height: 1rem` on
  `.responsive-admin-table .tag, .dashboard-dense-table .tag` and `.provider-status-cell .tag` so wrapped text is not
  clipped; migrate it, never extend it.
- Dense tags are `tag.is-small`. A table cell holds one `status_tag` plus an optional `.cell-meta` (two tags truncate to
  an ellipsis).
- A tag holding an unbounded value (the Workbench selection chip `.workbench-selection-tag`) keeps its flex display and
  wraps the text in `span.is-truncated`; `foundation/tables.css` gives `.tag > .is-truncated` `line-height:
  var(--leading-tight)`, because the tag's line-height 1 under `overflow: hidden` clips descenders and underscores. In
  its flex row the page gives the tag `flex: 1 1 0; min-width: 0; max-width: max-content`, so it takes only the room the
  heading leaves, the heading never wraps, and the full value is in `title`.
- `.tag` has no `is-light` variant: every tone is already soft. `test_shouldNotRenderRetiredLegacyMarkup` allows
  `is-light` only on a plain `.button` (the ghost button).
- `status_tone` maps machine statuses by whole word with the precedence danger (failed, error, blocked, invalid,
  unreachable, rejected, denied) > warning > neutral > success. `status_tag` renders `<span class="tag is-X">value</span>`
  (a plain `tag` for neutral) or the dash when empty. Run it against the real facade labels before asserting text in a
  test ("Base URL required" is warning). Tracker workflow statuses use an explicit `is_done`, not `status_tone`.
- `.status-dot.is-success|warning|danger|info` (0.5rem) shares the tone classes. `.count-badge` is a 1.25rem tabular
  `--text-2xs` pill. `.health[data-health=GREEN|YELLOW|ORANGE|RED|GRAY]` renders `.health__dot` beside the status name and
  sets `--health-color`; never color alone.
- `.delta`: inline-flex, tabular, medium weight, 0.75rem icons; `.is-up` uses `--color-success-text`, `.is-down`
  `--color-danger-text`. Pick static `iconoir-arrow-up` or `-down` through `{% if %}`; prefix `+` when positive and use
  `&minus;` when negative; show "First month in range" when the change is None.
- Pull request policy chips are `span.tag.is-small {{ policy.css_class }}`: `is-success` (Ready), empty for the neutral
  "In review" and `is-danger` (blocked). The values and their icons are test-asserted.

## 6. Tables And Data Cells

### 6.1 Base table

- `.table` is tabular-nums; cell padding `--space-1-5 --space-2-5`; header cells muted, 12px, weight 500, nowrap; the last
  row has no bottom border. Descendant rules end with `:where(:not(.paper *))` so report paper keeps its own table
  styling.
- Helpers: `.is-numeric` (right-aligned, nowrap), `.is-nowrap`, `.cell-meta` (block, tertiary, xs), `td :is(time, .tag)`
  nowrap (`code` is excluded so long hashes wrap), `td > code` at xs. Truncated ids keep the full value in `title`.
- Empty row: `<tr class="is-empty-row"><td colspan="N">…</td></tr>` is centered, tertiary, padding `--space-6 --space-4`.
  When the column count changes, update `task_table_colspan` (in `ui_web/facades/tasks_facade.py`) and every fixture
  colspan (`scripts/ui_design_fixture_hooks.py` and the baseline gate test).
- Links in tables are accent-colored except `.button`, `.tag` and `.work-item-ref__title`.
- Never set `display: flex` on a `<td>`; wrap the content in a `div`.
- `.table-container` is `position: relative; overflow: auto` with sticky header cells at `--z-sticky`; being positioned
  keeps `.is-sr-only` text from widening the page. `.is-framed` (border, `--radius-lg`, surface) is for tables sitting
  directly in page flow. Inside `.box` or `.card` leave the table flush and unframed. Never frame `pinned_blocks.html`
  (export inline styles).
- A flush table whose `.table-container` is a direct child of a `.card` gives its first and last cells `--space-4` inline
  padding, so cell text shares the card title's edge. The rule lives in `pages/dense-tables.css`, after the
  `.responsive-admin-table` / `.dashboard-dense-table` density rules and before the cardable `@container` block: all three
  are specificity (0,2,1), so only source order decides. In `foundation/tables.css` it silently loses to the later density
  rules. The selector wraps the container part in `:where()` to stay at (0,2,1) so the cardable phone rule still resets
  cell padding; never raise it. The baseline gate's `table_edge_failures` metric (`ALIGNMENT_TOLERANCE`) fails any flush
  card table whose first header cell text is off the card title's text edge.
- Cells and rows that tests measure use opaque backgrounds (`--color-surface`, `--color-surface-muted`); a transparent
  cell parses as black in the contrast tests. Put row hover or tint on the `tr`, not the `td`. Avoid `color-mix()` on
  measured elements (it computes to `color(srgb …)`).

### 6.2 Responsive and dense tables

- Every `<table>` carries `responsive-admin-table` or `dashboard-dense-table`.
- `.responsive-admin-table { min-width: var(--responsive-admin-table-min-width, 58rem); table-layout: fixed }` inside
  `.table-container.responsive-admin-table-box` (`overflow-x: auto` plus `container-type: inline-size`, which
  `is-cardable` needs). Narrow tables set the variable (44rem for the scope binding audit).
- `.responsive-admin-table.is-cardable` at `@container (max-width: 40rem)`: `td::before` labels (xs, weight 500, sentence
  case); `tr.is-empty-row` resets border, background and padding and `tr.is-empty-row > td` is `display: block; padding:
  var(--space-5) var(--space-3)`.
- Data-health tables: `.data-health-page table { table-layout: auto }`; wrap cells with `.table.responsive-admin-table
  td:not(.is-nowrap) { overflow-wrap: break-word; white-space: normal }` (the `:not(.is-nowrap)` is needed because that
  selector, (0,3,1), beats `.table td.is-nowrap`); `.data-health-table-container table { min-width: 70rem }`. Raw machine
  values (`stale_config`, `auth_failed`, `provider_owned_saved_query`) stay in the HTML. The 11-column Provider Sync table
  sits at its min-content width near 1440px and scrolls inside its container when values are long; that is by design.
  Check width-sensitive layouts in light: dark's lighter weights set narrower text, so a table that fits in dark can
  overflow by a few pixels in light.
- Report matrix tables: `dashboard-dense-table report-matrix`, cells `min-width: 12rem`, `white-space: normal`,
  `vertical-align: top`, opaque bodies.
- Data-health counts are a `.stat-grid.is-compact`; Inferred is `is-info` above 0, Config required and Ambiguous are
  `is-warning` above 0. Keep help tips inside `.stat__label`.
- Card mode keeps children at their natural width (`td > * { justify-self: start; max-width: 100% }`): tags and buttons
  never stretch, nowrap or ellipsis children still stop at the column edge, and `.is-numeric` reverts to `text-align:
  start` so values line up under their labels. A tag longer than the value column wraps inside its pill (`white-space:
  normal; overflow-wrap: anywhere; height: auto; min-height: 1.25rem`) instead of being clipped. Table mode keeps tags on
  one line: auto-layout tables (data health) grow the column and scroll in their container, and fixed-layout tables
  size their `colgroup` for the longest expected value. `.tag` is `inline-flex`, so `text-overflow: ellipsis` never
  applies to its text and `overflow: hidden` alone clips silently.
- Column widths live only on `colgroup > col.<page>-col-*` (card mode hides the colgroup); set
  `--responsive-admin-table-min-width` to their sum so wide screens show every column without scrolling (Scope Library:
  89rem, nine columns).
- Pinned columns (Scope Library): the first and the action cells are `position: sticky` (`left: 0`, `right: 0`) with an
  opaque `--color-surface` background, `--color-surface-hover` through `.is-hoverable tbody tr:hover > td.<pinned>`, an
  inset 1px box-shadow hairline as separator, body cells at `--z-sticky`, header cells one above (the corner two) through
  `.table.<name> thead th` (needed to beat `.table-container > .table thead th`), and `td:has(.workbench-menu[open])`
  raised to `--z-dropdown`. The card-mode container query turns pinning off.
- Row actions: one primary action plus a "More" `.workbench-menu`, left-aligned in a nowrap `.scope-primary-actions` with
  a shared `min-width`, so every row lines up. Audit, duplicate, export and archive live in the menu; delete appears
  only for archived rows with its typed confirmation and impact `title`.
- Row menus: the `.workbench-menu` base (summary plus a right-aligned `.workbench-menu-panel` at `--z-dropdown`;
  `.is-upward` opens above) lives in foundation `work-items.css`. Inside a `.table-container` the capture-phase `toggle`
  listener in `table-interactions.js` flips an open menu upward when the panel fits above its summary, otherwise pads the
  box bottom until the panel fits, and clears the padding when the last menu closes. Never set `overflow: visible` on a
  scroll box through `:has([open])`.
- Provider identity in a cell uses the `provider_tag` filter (`tag is-small` with the provider dot, or the dash); a cell
  whose binding still needs configuration renders the dash.

### 6.3 Task and PR tables

- Task table: `table.table.is-hoverable.is-fullwidth.dashboard-dense-table.task-table`, never `is-striped`. Each task owns
  a `<tbody>`; separate them with `tbody + tbody > tr:first-child > td { border-top }` because foundation drops the
  last-row border. Columns: Assignee `.person`, Task `.work-item-ref` (parent in `.cell-meta` with an sr-only "Parent: "),
  Health, Spent, Assignee spent, Estimate, `<abbr title="Story points">SP</abbr>`, Subtasks; numeric columns carry
  `is-numeric`.
- Child rows: `button.button.is-small.is-light.task-children-toggle[aria-expanded]
  [aria-controls=children-ID][aria-label="N subtasks"]` with `hx-get`, `hx-target="next tbody"`, `hx-swap="innerHTML"`,
  `hx-trigger="click once"`; the next `<tbody id=children-ID hidden>` receives the rows (`tr.is-child-row`, background on
  the `tr`). The chevron rotates 90° on `[aria-expanded=true]`; `.loader` replaces the icon during `.htmx-request`. No
  `hx-on`, no `is-hidden`, no `aria-busy` on an innerHTML target. Empty result: "No subtasks found."
- Tree table: `tr.task-row[data-level]`, `hidden` rendered server-side for level ≥2,
  `button.task-tree__toggle[aria-expanded]`, indent through `style="--tree-level:N"`, Expand and Collapse all through
  `data-task-tree-expand` with `aria-controls`, one delegated click handler.
- PR page order: filters → results bar → review-activity disclosure `#pr-review-activity` → framed table. Keep the OOB
  targets `#pr-main-*`, `#pr-additional-*`, `#pr-policy-*`, rows with `hx-trigger="revealed"` and `hx-swap="none"`, and
  `.review-loader`.
- People: `partials/avatar.html` takes `person`, `avatar_size`, `avatar_labelled` (a labelled avatar is `role="img"` with
  `aria-label` and `title`; one beside a name is `aria-hidden`). `.avatar` is 1.25rem (`.is-medium` 1.5rem), initials 0.625rem
  semibold, tint `color-mix(in oklab, var(--palette-color) 18%, var(--color-surface))`, text a 55% mix with
  `--color-text`. A provider photo (`.avatar__image`) covers the initials; a capture-phase `error` listener in
  `table-interactions.js` removes a broken image (no inline `onerror`). `.avatar-stack` rings are 2px `--color-surface`, overlap
  `-var(--space-1)`, at most 8, `aria-hidden`.
- Work items: `.work-item-ref` shows the mono key beside a title clamped to two lines (`-webkit-line-clamp` with
  `overflow-wrap: anywhere`; the full text lives in `title`).

## 7. Surfaces, Disclosure, Facts

- Card: `section.card[aria-labelledby] > header.card-header > h3.card-header-title (+ span.card-header-meta,
  .card-header-actions)`. Never nest bordered surfaces: inside a card use spacing, `.description-list`, `.meta-strip` or a
  hairline. A header that counts rows ends with a `.count-badge` (Observed values, Binding Audit History). A
  `.table-container` that directly follows `.card-content` gets its top hairline from `foundation/layout.css`; pages never
  draw their own.
- Step strips (Scope lifecycle): `section[aria-labelledby] > h3 + ol > li` with a 1rem numbered badge and no connector
  pseudo-elements (a wrapped line would start with a dangling connector). In light mode `--color-surface-muted` equals
  `--color-canvas`, so a muted strip or well sitting on the canvas also needs a 1px `--color-border`.
- `.description-list`: muted keys, grid `minmax(7rem, max-content) minmax(0, 1fr)`; `.is-2` has two pairs per row only at
  ≥1024px (one column at ≤768px); frameless inside `.box` and `.card`.
- `.stat-grid` columns `minmax(11rem, 1fr)`; `.is-compact` `minmax(8.5rem, 1fr)`, gap `--space-2`, muted tiles without
  shadow, value `--text-lg`, `role="group"` with an `aria-label`. `.stat.is-success|warning|danger|info` colors the value
  and a leading dot. Forecast KPIs: finish with a `timeuntil` hint, total estimate with `.stat__unit` "d" and an optional
  `<progress class="progress is-small">` (shown when total ≠ completed + remaining).
- `.meta-strip`: `<section class="meta-strip[ is-warning]" aria-label data-freshness>` with a tone tag (and `.status-dot`)
  plus `dl.meta-strip__facts`: Run as `code` truncated to 9 characters with the full id in `title`, Coverage `a → b`,
  Completed via `|timestamp`, Config as a 12-char hash. When data is not fresh a `p.meta-strip__note` carries the note;
  there is no separate banner.
- Disclosure: `<details class="disclosure">` with `__summary` (`__chevron`, `__title`, `__meta`, `__aside`) and `__body`;
  border, `--radius-lg`, `--shadow-xs`, `overflow: clip`, summary min height 2.5rem, `iconoir-nav-arrow-right` rotating
  90° when open. Nested disclosures drop frame and shadow and use a top separator (summary 2.25rem, title `--text-sm`).
  `.is-flush` (inside surfaces): no frame, a top hairline `--color-border-subtle`, summary `padding-inline: 0`, no hover
  background, focus offset 2px; the summary stays at least `ADVANCED_SUMMARY_MIN_HEIGHT` tall (measured on the provider
  editor's Advanced section). Summary headings are `<h{{ level|add:3 }}>` (h3 at
  level 0, never h1), so every caller of `group_renderer` must pass `level`; icons are `aria-hidden`. Lazy bodies use
  `hx-trigger="toggle once from:closest details"` (`toggle` does not bubble; use `load` for groups rendered open).
  Available members render as a default-collapsed `#available-members` disclosure with a count badge and an
  `avatar-stack[aria-hidden]` of at most 8. `group_renderer` falls back to the task table when `item.items.0.type` is
  missing, so a member group without stages still renders.
- `.chip-disclosure`: summary holds count tags with a chevron `::after`; `__list` is flex-wrap, max 30rem, margin-top
  `--space-1-5`.
- Tabs: foundation `:where(.tabs)` is a zero-specificity underline default (accent underline on `li.is-active`; excluded
  from the `X:not(:last-child)` margin list). The strip scrolls horizontally (`overflow-x: auto`, hidden scrollbar). Only
  `a` is styled, so a disabled tab is a `span[aria-disabled]` with its own style. There is no boxed variant. Provider
  tabs (provider editor and Scope Config) are `div.tabs.provider-tabs.provider-tab-list > ul[role=tablist][aria-label] >
  li.provider-tab-item[role=presentation] > a[role=tab][aria-selected][aria-controls][data-dirty-guard]` over one
  `.provider-tab-body[role=tabpanel][aria-labelledby]`. The selected tab's underline takes its own `--provider-color`, so
  the `li` needs no provider class; `.provider-tab-check` is a 1rem circle with an `--color-on-accent` tick,
  `.provider-tab-dot` 0.5rem. Quiet meta after the label (profile count, "Template only") is hidden on phones so every
  tab stays visible. Tab height and the gap between the selected tab and its body stay within
  `PROVIDER_CHOICE_HEIGHT_MAX` and `TAB_ATTACHMENT_GAP_MAX` in `ui_web/tests/ui_geometry_contract.py`.
- Board: `.board[role=region][aria-label][tabindex=0] > section.board__column[aria-labelledby]` (h3 + `.count-badge`) `>
  ol.board__cards > li > .board-card[data-health]`. Columns are `minmax(16rem, 1fr)`; the card is neutral with a 3px inset
  health stripe (`box-shadow: inset 3px 0 0 var(--health-color, transparent), var(--shadow-xs)`, padding-left
  `calc(var(--space-3) + 3px)`); never tint the card; the health name stays as text. Show every workflow stage; an empty
  column renders `li.board__empty` "No tasks".
- Pipeline: `ol.pipeline > li.pipeline__step[.box].is-success|warning|danger|info > .pipeline__head + .pipeline__title +
  .pipeline__body`; the counter badge (`::before`, 1.375rem) uses `--pipeline-tone`, `-subtle`, `-text`; grid
  `repeat(auto-fit, minmax(min(100%, 16rem), 1fr))`. Used by the AI workflow and the provider "Data handoff" (11rem).
  Handoff steps are Source, Metadata (`is-success` when `metadata_supported`, else `is-warning`), Field mappings, Value
  mappings, Readiness.
- Empty states: `.empty-state[.is-warning]` with `__icon`, `__title`, `__body` (max 36rem), `__actions`; icon classes are
  literal. Inside a chart card the state fills the frame (no border or background). Bug Trend renders
  `.empty-state[data-testid=bug-trend-chart-empty]` instead of a blank shell (`chart_has_data = bool(chart_data.labels)`
  in the view).

## 8. Charts

### 8.1 Chart card and frame

`section.card.chart-card[aria-labelledby] > header.card-header > h3.card-header-title (+ span.card-header-meta) >
.chart-card__body > .chart-frame > canvas[role=img][aria-label]`. The `<script>` follows the section and only renders when
data exists. `.chart-frame` is `position: relative; height: var(--chart-height, 17.5rem)`; `.is-timeline` is
`calc(var(--chart-rows, 6) * 1.75rem + 3.5rem)` with `--chart-rows` set from the template or JavaScript. `.chart-grid > *
{ min-width: 0 }`. `maintainAspectRatio: false` needs that positioned, sized parent. Protected ids: `teamVelocityChart`,
`teamStoryPointsChart`, `velocityChart`, `storyPointsChart`, `taskForecastChart-<id>` and the show/hide-all ids. Chart
scripts are an IIFE with no `typeof Chart` polling and no `console.log`, and destroy the previous instance first. No text
alternative beyond `aria-label` is specified yet (known gap).

### 8.2 `window.DashboardCharts`

- API: `token(name)` (cached `getComputedStyle`, cleared on theme change), `alpha(color, opacity)` (hex, `rgb()`,
  `hsl()`), `paletteColor(index)` (wraps over 8 slots), `seriesColor(name, index)` (`--color-series-<slug>`, else
  `paletteColor`), `seriesCssColor`, `refresh()`.
- Use scriptable colors (`() => DashboardCharts.seriesColor(name, i)`) for series, ticks, grid, border and title. Chart.js
  v4 copies `defaults.scale` colors into each chart's options, so static colors never follow a theme change.
  `refreshCharts` (on `dashboard:themechange` and the reduced-motion change) records the previous colors, clears the token
  cache, reapplies defaults, drops copied scale colors (`forgetThemedScaleColors`) and calls `chart.update('none')`.
- Defaults: 11px `--font-sans`, animation 320ms (0 under reduced motion), line width 2, point radius 2.5 (hover 5, hit 6),
  bar radius 3 with `maxBarThickness` 32, ticks `maxRotation: 0`, `autoSkipPadding: 16`, `padding: 6`, scale border
  hidden, legend `usePointStyle` 8px, tooltip on `--color-surface-inverse` with radius 6.
- Payloads carry semantics (slot, key, `done`), never colors: no `color`, `background_color` or `border_color`, and no
  hash or HSL colors. The bug-trend API keeps `points[].color` for Grafana parity (`bug_metrics/app/api/series.py`; tests
  assert `#bdbdbd` and `#f2c94c`); templates never read it. `ColorUtils.palette_slot` is the first two bytes of sha256
  modulo 8, plus 1, in the same order as `paletteColor`.

### 8.3 Options and legends

- Common: pointer cursor, x grid hidden, y `beginAtZero`, y `grace: '10%'` when annotation labels sit on top, tension 0.25
  for trend lines, one accent series with an `alpha()` fill for team velocity.
- Threshold lines are dashed (`borderDash [4, 4]`, width 1, `alpha(token('--color-text-tertiary'), 0.6)`); equal rounded
  thresholds (`toFixed(1)`) share one label at `position: 'end'`; seniority bands use the same grouping ("senior ·
  lead/arch ~4.0") with `alpha(tertiary, ~0.05)` fills.
- Stacked bars: surface-color top border, `itemSort` descending, a "Total X SP" footer; developer velocity maps 0 to null
  with `spanGaps`.
- Forecast timeline: one accent, done bars thinner (`borderWidth` 8 vs 15, round cap), no in-chart titles, y over dated
  tasks only with ticks from `afterBuildTicks` and `autoSkip: false` (`stepSize: 1` with a 0.5 min lands on 0.5), x labels
  `MMM d` through `Intl.DateTimeFormat` with the html `lang`, tooltips filtered by `datasetIndex`, a dashed "Today"
  annotation.
- Interactive series use the shared HTML legend `.series-toggles[role=group]` of
  `button.series-toggle[data-palette-slot][aria-pressed]` plus Show all / Hide all (`is-light`); the canvas legend is
  `display: false` (it is not keyboard accessible). `.series-toggle` is a pill (`min-height: var(--control-height-sm)`, 0.5rem
  swatch); `aria-pressed="false"` gives a dashed border, transparent background, tertiary text and a hollow swatch. Legend
  changes use `replaceState`; opening a period uses `pushState`. The bug-trend legend is
  `.bug-trend-legend.is-sr-only[role=note]` (a test reads its text) with the Chart.js legend kept (`display: true`,
  `position: 'top'`, `generateLabels`).
- `[data-palette-slot="1..8"] { --palette-color: var(--color-chart-N) }` is shared by avatars and toggles;
  `--series-color` is only for named bug-trend series. Series labels use the `series_label` filter and the JS
  `readableSeriesLabel`; evidence `series_name` is a comma-joined sorted set.

## 9. Report Paper And Editor Chrome

- `.paper` is the fixed-light document surface: `color-scheme: light`, paper bg, text and selection, and restored document
  typography (lists `disc`/`decimal` with `padding-left: var(--space-5)`, h1 xl / h2 lg / h3 md / h4–6 sm, blockquote with
  a 3px paper rule, `code` and `pre` on bg-muted, `--color-paper-link` underlined links, cells with a 1px paper rule and
  opaque paper bg). `.paper` alone styles rendered prose; the retired `.content` broke its headings in dark mode.
- Markup: `<div class="report-editor-surface paper" aria-readonly="true">` with help text outside; add `paper` wherever
  report content renders. Export HTML only inlines `<p style="margin:0 0 8px 0">` and blockquote, so `.paper` must style
  tables, lists, headings and links.
- Authored paint colors are chosen against white (`#0055aa`, `#008000`, `#aa0000`; highlights `#fff4cc`, `#dff7e8`,
  `#fde2e2`). Chrome around paper follows the theme.
- Documented inline-paint exceptions: the toolbar swatch `style="background:#…"` synced with `data-color`;
  `.report-readonly-data main { padding: 0 !important }` (exports inline `<main style="padding:24px">`; the only
  `!important` outside `foundation/`, kept by a stylelint disable comment with its reason); fragment-codec
  `node.style.color`.
- Report CSS (`report_editor.css`, `report_assist.css`, `report_exports.css`) is token-only and linted, with no
  `!important`. Report pages are the only pages that load their own assets: `reports/editor.html` loads the editor,
  assist and exports CSS, `project_reports.js`, `report_exports.js` (module), the Milkdown bundle and
  `report_editor/index.js` (module); `report_templates/editor.html` loads the editor CSS, the bundle and
  `report_editor/template_builder.js` (module); `publication.html` loads the exports CSS and `report_exports.js`;
  `preparation.html`, `preparation_error.html` and `stage.html` load `report_daily.js`; `run.html` loads
  `project_run_status.js` (`defer`). None reloads a manifest file. `period.html` loads none, so shared report rules
  belong in foundation or the page layer.
- Chrome values: toolbar sticky at `top: calc(var(--layout-topbar-height) + var(--space-2))` with `--z-sticky`,
  `--color-surface-raised`, `--shadow-sm`; section band and row editor opaque `--color-surface`; completion menu
  `--z-dropdown` + `--shadow-md`; assist dialog `--z-overlay` + `--shadow-lg`; `.report-export-frame` min-height 32.5rem;
  `.report-assist-preview` max-height 15rem; task checkbox paper-control (paper-accent when checked); `.report-icon-pair`
  icons 0.75rem at (0,3,0). Paper contrast pairs (text on bg, bg-muted, table-header and selection ≥4.5; links ≥4.5;
  accent and control ≥3) are registered in `contrast-pairs.json`.

## 10. Provider Editor And Scope Config

Both editors are rewritten and share these rules and selectors (`pages/provider-setup.css`, `pages/provider-editor.css`,
`pages/editor-*.css`, `pages/scope-*.css`).

- One card: the form `form.dashboard-edit-form.box.<editor>.is-provider-X[aria-label]` is the only framed surface (box
  border, `--radius-lg`, `--shadow-xs`, `--space-4` padding) with a 2px `--provider-color` left rail
  (`.provider-setup-editor`, `.scope-config-provider-workflow`); no `overflow: hidden`, no halo. `.provider-tab-shell`
  inside it is an unframed grid, and `.provider-tab-shell > .provider-tabs` takes negative `--space-4` margins so the tab
  strip sits on the card's top edge.
- Everything editable lives in the tab body as `section.provider-section` blocks with `h3.provider-section-title` (md
  semibold) and `.provider-section-help` (xs), divided by `--color-border-subtle` hairlines (`.provider-section +
  .provider-section`, `.disclosure + .provider-section`). A section is a grid (gap `--space-3`); a form grid inside it
  drops its flow margin and a full-width field spans `grid-column: 1 / -1`. Context is a muted lead
  `p.provider-context-panel` (`--radius-md`, no border). Flatten nested boxes.
- Scope Config body order: hidden `provider_id`, context lead, Provider binding (4-cell grid: `status_tag`, profile
  select with a `button is-small` "Save binding", provider, blockers; then the always-rendered detail panel), flush
  `details.disclosure.is-flush` "Workflow order" (open for a new scope), Identity, Source population, Semantic mapping,
  Display fields. State banners, the action bar and the signature `dl` follow the body inside the shell. The page meta
  shows `enabled`/`draft` through `status_tag` beside one "Dashboard status" help tip.
- Source population: the Jira branch is one section with the radio switch (§4.1) in its heading; each
  `.scope-source-panel` is a grid (gap `--space-3`) and the inactive one carries `hidden` plus `.is-inactive`. Other
  providers get a source section and a metadata section. An htmx target that may stay empty hides itself with
  `:not(:has(*)) { display: none }` instead of reserving space.
- Context that always exists renders unconditionally: no `{% if %}` guard around `scope_provider_context` or
  `detail_rows` (the facade always supplies three rows per provider).
- The connection test result renders once, inside the editor above the actions:
  `#provider-connection-test-result.message.<status_tone>[role=status][aria-live=polite]` with the header "Connection
  test: {status}" and details as a `dl`.
- The advanced JSON section is closed for an existing profile and open only without `profile_id`. Save needs profile id
  and display name; Test needs base URL, auth mode and the HSD-ES query, tenant and subject; focus lands on the first
  missing field. An existing enabled profile has Save and Enable disabled and Test enabled.
- Dropping an editor field means removing it from the dataclass, facade, unused imports and
  `scripts/ui_design_fixture_hooks.py` (Scope Config still uses `provider_detail_rows`). Scope Config and the editor share
  selectors: edit them in one CSS pass, and delete dead rules (`.provider-overview-strip`, `.provider-editor-header`,
  `.provider-bind-row`, duplicates, legacy `.task-filters`) after grepping for references.
- Evidence dates use `|timestamp:"date"`; the detail pane uses `data-created-label` and `data-updated-label`
  (`|iso_datetime`) while raw `dataset.created/updated` stay for the AI payload. The evidence summary cell is `max-width:
  30rem` with an ellipsis. Report starters carry their label visibly once, on the submit button.

## 11. Formats And Copy

- `dashboard_format` filters: `or_dash` (None or blank becomes the muted em dash `<span class="has-text-grey-light">—</span>`), `status_tag`, `status_tone`, `iso_datetime` (`YYYY-MM-DD HH:MM` in UTC for aware values; naive, date-only and unparsable values pass through), `timestamp(value, precision='minute'|'date')` (emits `<time datetime title>`), `age_seconds` (`45s`, `12m`, `3h 5m`, `2d 4h`), `split_csv`, `series_label`. `avatar_filters`: `initials`, `avatar_slot`.
- An empty cell is the em dash through `or_dash`, never `-`. Python helpers return `''` instead of `'-'` and let `or_dash` render (`{{ None|or_dash }}` works inside `{% with %}`). Never add keys to `run_metadata_payload` (a test asserts the exact dict); format in the template.
- Multi-value textareas hold one value per line: `{{ values|join:"&#10;" }}`. Django does not interpret `\n` inside a filter argument, so `join:"\n"` renders a literal backslash-n; the `&#10;` literal is already safe and the browser decodes it inside the textarea.
- Formats: dates `date:"M j, Y"`, durations `floatformat:1` plus "d", story points `floatformat:"-1"` behind an `is not None` check, velocity `floatformat:2`. Health labels are `status.name|title`; zero renders a muted "0"; "Unassigned" is muted.
- Wording: "SP per logged day" or "SP/day", never "ideal day"; rolling label "N-month average"; no trailing colons on labels; no emoji in error blocks; sentence case; grep rewritten templates for leaked placeholders such as "DASH".
- Service states: `_SERVICE_STATES` in `dashboard_format.py` is a literal `pgettext_lazy('service state', ...)` vocabulary. Templates render `{{ state|service_state_label }}` and keep the raw value in `data-service-status`; an unknown state passes through unchanged, so a new state joins the vocabulary and the catalog together.
- Clock times are 24-hour (`%H:%M:%S`). The status bar shows local time; error-page reference times are UTC and say so.
- Toasts: `#notification-container` carries `data-message-request-failed`, `-network-error`, `-dismiss` and `-waf-retry`; `htmx-lifecycle.js` reads them from `container.dataset` and appends the verbatim HTTP status line and path as the detail.
- Commands in messages are placeholders: `gettext('... restart %(command)s ...') % {'command': DASHBOARD_RESTART_COMMAND}`. The command constants live in `workbench_service_status.py`, and the zh-hans shell test strips them before looking for English.

## 12. Projects And Report Templates

Selectors live in `pages/projects.css` and `pages/report-templates.css`.

- Admin tables (`project-table`, `stage-table`, `template-table`) are `responsive-admin-table is-cardable` with
  `data-label` cells. Each table sets `--responsive-admin-table-min-width` and puts column widths on `th.<table>-col-*`
  only, so phone cards keep full-width cells. Hashes render `<code title="full">{{ hash|slice:":12" }}</code>` in an 8.5rem
  column. The action column is end-aligned and returns to start inside `@container (max-width: 40rem)`; a cell with
  several actions wraps them in `div.<page>-row-actions` (inline-flex, wrap, gap `--space-1`). The empty row is
  `tr.is-empty-row`.
- Create and add flows that need a few fields (Create project, Add stage) are a `details.popover` whose summary is the
  `button is-primary is-small`; the panel holds a `dashboard-edit-form` with `dashboard-form-grid is-stacked`, and the
  popover opens itself when the form has errors. A field error is `p.help.is-danger#<id>_error` and the control carries
  `aria-invalid` plus `aria-describedby`.
- Read-only facts (stage preview) are a `dl.description-list`; the provider is `provider_tag`, identifiers are `code` and
  long queries are `pre`. Destructive actions sit last in their own card: `dashboard-action-form is-row` with a required
  confirm checkbox and a `button is-danger is-small` with `iconoir-archive`.
- Template library: a "Create template" card holds the starter grid (each starter labels itself once, on its submit
  button) and the "Library" card holds the table; pagination sits after the card.
- Template editor order: page header (revision, 12-character hash `code`, readiness tag, archived tag), messages, then one
  form with a "Template settings" card, `section.template-blocks` (an h3 and the Add buttons, the sticky report toolbar,
  `div.template-block-list`), the clone templates and the action bar (`p.status-line` beside Save). The archive card
  follows the form. The save bar is not sticky: the fixed statusbar would cover it and obscure focus (WCAG 2.4.11).
- A block is `article.template-block` placed straight on the canvas like `.report-row-editor`, never inside a card:
  border, `--radius-lg`, `--color-surface`, `--shadow-xs` and a 3px inset rail
  (`box-shadow: inset 3px 0 0 var(--template-block-rail)`) named by kind: content `--color-border-strong`, slot
  `--color-accent`, data `--color-chart-2` (info blue reads as accent). Its head holds the small kind select and square
  icon commands (`button is-small is-light`, `width: var(--control-height-sm); padding: 0`, `aria-label` and `title`);
  remove takes a danger-subtle hover.
- Saved rows and JS clones render one include: `block_editor.html` with `row=None` and `matrix_group.html` with
  `group=None` inside sibling `<template data-template-row-template>` and `<template
  data-template-matrix-group-template>` within `[data-template-builder]`. JS clones `template.content.firstElementChild`
  and never builds markup strings. Cloned controls use implicit labels (`label.dashboard-form-field > span.label +
  control`) because ids would collide.
- Panels switch with `hidden`; an empty group list hides through `:not(:has(*))`. Field panels are a grid
  `minmax(0, 2fr) minmax(0, 1fr) auto` with `align-items: end`; a `fieldset > legend.label` in that row takes
  `--control-label-height` as min-height and line-height so the labels share one line, `.template-block__wide` spans
  `1 / -1`, and the grid drops to one column at 768px. The matrix panel is a borderless `--color-surface-muted` inset.
- An archived template wraps the editable form in the literal `<fieldset disabled aria-disabled="true">` and Save carries
  `disabled aria-disabled="true"`; the archive confirm checkbox is disabled as well.

### 12.1 Stage report workbench, preparations, runs and meetings

Selectors live in `pages/project-reports.css`; form-grid alignment and in-table control height are shared from
`pages/editor-forms.css` and `pages/dense-tables.css`.

- Every page root is one `article.block.project-reports`; partials never add a second `<article>` (tests count them).
  The page header holds the stage name as h2 (plus the key in `code` on the workbench), the language switcher and one
  navigation button (Meeting calendar, Report workbench or Back).
- Messages are `div.message.is-X[role] > div.message-body`. The body is a grid on `--space-1-5`, so every line, and every
  run of mixed inline text, links and tags, sits in its own `<p>`; bare inline nodes would each become a grid row.
- Cards: `section.card[aria-labelledby] > header.card-header > h3.card-header-title#id`; secondary text is a
  `span.card-header-meta` inside the h3; a tag or count badge goes in `div.card-header-actions`. The optional
  `.card-content` stacks its children on one gap, and the table container follows as a direct card child:
  `div.table-container.responsive-admin-table-box > table.table.is-fullwidth.is-hoverable.is-narrow.responsive-admin-table.is-cardable.project-reports-table.<x>-table`.
- Header cells carry `scope="col"` and a `report-col-*` width class; the action column header is
  `<span class="is-sr-only">Open</span>`. Every other cell has `data-label`; a cell mixing text, tags and links wraps them
  in one `<span>` so card mode keeps them on a line. Empty tables use `tr.is-empty-row`. A paginated table shows no count
  badge; its pager is `nav.pagination.is-small.project-reports-pager` after the container.
- Forms use `dashboard-form-grid` (`minmax(min(100%, 11rem), 1fr)`); a trailing `.dashboard-action-group` takes
  `align-self: end` so buttons share the control row, and `.is-right` pushes a lone submit to the end. Controls inside
  table cells (`.input.is-small`, `.select.is-small`, buttons) share the 1.72rem dense height. Paired form cards sit in
  `.project-reports-grid` (`minmax(min(100%, 34rem), 1fr)`); checkbox groups are `fieldset.project-reports-checks` with
  a `legend.label`.
- The daily preparation partial renders from `detail`, `stage` and `daily_result` alone (the history page reuses it) and
  keeps every `data-report-daily-*` hook. The baseline is a muted `div.project-reports-baseline` holding
  `dl.description-list.is-2.project-reports-facts`; the result is `div.message {{ state|status_tone }}` with the summary,
  ids, unapplied choices and a `.buttons` row.
- Disabled runtimes still render their card with a neutral "Runtime disabled" or "Refresh disabled" tag; the run submit
  button exists only when a run form is offered, and a primary action that cannot proceed carries
  `disabled aria-disabled="true"`.
- The run status fragment returns exactly one root, `#project-run-status-fragment`. Its state h2 text is exactly the
  state (the status dot is an empty `span`), facts are `dl.description-list.is-2`, item rows fill gaps with `or_dash`, and
  the poll error is `div.message.is-warning[data-run-poll-error]` toggled through `hidden`. The fragment has no
  `hx-get`, doctype or `<html>`.
- Meetings: the query form is `form.box.dashboard-tool-form.dashboard-top-toolbar[data-meeting-query-form]`; the calendar
  card holds the change form (`.dashboard-edit-form` with a `.project-meeting-change` row: the reason grows, the three
  same-size actions wrap below it) above the table. Status tags: skipped `is-warning`, occupied `is-info`, unrecorded
  neutral. Rows keep `data-meeting-date` and `data-meeting-state`.
- Page CSS files are LF in the working tree. Any new Iconoir glyph must be added to the subset and rebuilt with
  `npm --prefix ui_web/frontend run build:vendor`.

### 12.2 Report editor, publication and period pages

Selectors live in `report_editor.css` (editor pages only), `report_assist.css`, `pages/project-reports.css` (command
bar, publication list) and `pages/dense-tables.css` (matrix cells, because `period.html` loads no report CSS).

- Editor order inside `article.block.project-reports[data-report-editor]`: `header.page-header` as a direct child (meta:
  state tag, revision with the 12-character hash `code`, source cutoff `|timestamp`), finalized and required-slot
  messages, the readiness `div.stat-grid.is-compact[role=group]`, the recovery strip, the authoring form (command bar,
  sticky toolbar, `section.report-body-editor`), the Finalization card (draft only), the Resume card, the Source state
  and Publication target `.project-reports-grid`, and the closed `details.disclosure.report-export-preview`.
  Article-level strips without a foundation margin (`.report-recovery`, `.report-authoring-form`) take
  `:not(:last-child) { margin-bottom: var(--space-4) }` to join the block rhythm.
- Command bar `div.report-command-bar`: one `dashboard-action-group` of `is-small` buttons (Save is the only
  `is-primary`, Download HTML stays an `<a>`, copy is a real `<button disabled>`), the export controls pushed to the far
  edge (`margin-inline-start: auto`) and `p.status-line` rows (`flex: 1 0 100%`). On the publication page the bar is an
  article child and takes the `--space-4` block margin; inside the form it uses the form grid gap.
- A status line may receive one script-appended follow-up `.button` ("Keep as human link") spaced by
  `.status-line > .button`; the next `textContent` write removes it. Script-built copy comes from `data-message-*`
  attributes on the editor root with an English fallback, never from bare literals in JS.
- Recovery strip `div.report-recovery`: a borderless `--color-surface-muted` flex row (`--radius-md`, xs secondary text)
  with the status `p` and a small action group; the empty checkpoint select hides through `.select:has(> select[hidden])`.
- Toolbar: `div.report-toolbar-group` sets divided by a `--color-border-subtle` inline-start hairline, never spacer
  elements. Icon-only commands carry `aria-label` and `title`.
- Bands: `div.report-section-band` (bordered `--radius-lg` surface, grid gap `--space-3`) titled by
  `h3.report-band-title` (md semibold, tags inline). Rows are `article.report-row-editor` divided by a
  `--color-border-subtle` top hairline, never a second frame, yet they keep the opaque `--color-surface` because contrast
  tests read their background. Row field labels are `h4.report-field-title` (xs semibold secondary). The field grid is
  `repeat(auto-fit, minmax(min(100%, 14rem), 1fr))` and needs no breakpoint. An empty direct band child (a JS mount
  point) is `display: none`, so it opens no extra grid gap until a script fills it.
- Matrix cells stack their direct children with `:not(:empty) ~ :not(:empty) { margin-top: var(--space-1-5) }`; JS
  mount points must therefore be literally empty (no whitespace). The genuinely-empty-cell marker is a neutral
  `span.tag[data-matrix-empty]`: data attributes are the test and JS hooks, classes only style. Persistent notes and
  unsaved ARs (`.report-persistent-note`, `.report-new-action`) group their fields under a `--color-border` top hairline
  and consecutive ones add `--space-2`.
- `<details>` with laid-out content: Chromium places the non-summary children inside `::details-content`, so the grid
  and gap go on an inner wrapper (`.report-action-fields`), never on `details` itself.
- One English word used as both a state and a time label needs a context: the state tag uses
  `{% trans "Finalized" context "report state" %}` ("已定稿") while the column and fact label stays plain "Finalized"
  ("定稿时间"); the po file carries the `msgctxt` entry.
- Publication page: page header (h2 "Published edition", meta `code` id), the command bar (Download HTML and Download
  text `<a>`s plus export controls with the audit bundle), a "Manifest" card (`dl.description-list.is-2`; hashes 12
  characters with the full value in `title`, times `|timestamp`, actor `|or_dash`, commit `code` plus
  `checkout_state|status_tag`), then for standups a "New revision" card (the linked-revision button and the revision form
  with one primary) or an info note.
- Period page: the matrix in a framed table container, then a "Selected publications" card holding
  `ul.report-publication-list` (grid, gap `--space-1`, sm text).

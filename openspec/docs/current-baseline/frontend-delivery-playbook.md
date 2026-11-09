# Meridian Frontend Delivery Playbook

Status: **binding** as part of [frontend-design-requirements.md](frontend-design-requirements.md). It describes how frontend work is delivered: tooling, build, file architecture, the file-size gate, testing, real-browser review, debugging pitfalls and working rules. Tokens, selectors, values and markup live in [frontend-design-recipes.md](frontend-design-recipes.md).

Run commands from the repository root in PowerShell unless noted. Never paste secrets into commands, logs or docs; the Jira variables used by tests are synthetic.

## 1. Toolchain And Build

### 1.1 Commands

Node ≥22. First run: `npm --prefix ui_web/frontend ci`.

| Script | Does |
| --- | --- |
| `build:tokens` | DTCG tokens → `ui_web/static/css/theme.css` (Style Dictionary, custom `meridian/declarations` format, no `color/css` transform) |
| `build:vendor` | Copies pinned runtime assets into `ui_web/static/vendor/`, builds the Iconoir subset, writes `asset-manifest.json` |
| `lint:css` | Stylelint over every stylesheet under `ui_web/static/css/` (the glob must include subfolders, `**/*.css`) |
| `qa:contrast` | Checks `tokens/contrast-pairs.json` in both themes (currently 152 pairs, 0 failures, 0 warnings) |
| `check` | `build-tokens --check` + `build-vendor --check` + `lint:css` + `qa:contrast`. It has no JavaScript lint and no browser QA. |
| `qa:browser` | Playwright + axe-core over the sidebar routes (see §5.3) |

- Pinned versions (change only with a lockfile update): htmx.org 2.0.11, chart.js 4.6.1, chartjs-adapter-date-fns 3.0.0, chartjs-plugin-annotation 3.1.0, @fontsource-variable mona-sans and geist-mono 5.3.0, iconoir 7.12.2, modern-normalize 3.0.1, style-dictionary 5.8.0, stylelint 17.16.0 with stylelint-config-standard 40.0.0 (stylelint 18 needs Node ≥22.22), playwright-core 1.65.0, @axe-core/playwright 4.14.0, @radix-ui/colors 3.0.0, culori 4.0.2.
- Dependency change: pin the exact version in `package.json`, `npm install`, `npm run build`; commit `package-lock.json`, vendored output, the manifest and `THIRD_PARTY_NOTICES.md` together. No CDN, no ad-hoc downloads, no frontend framework without an approved OpenSpec change.

### 1.2 Tokens

- Sources: `base.tokens.json` (Radix ramps, scale, type, radius, shadow, duration, z-index), `theme.light.tokens.json`, `theme.dark.tokens.json`, `contrast-pairs.json`. Semantic colors reference `{ramp.<scale>.<step>}`. Dimensions and durations are authored as CSS strings. Never hand-edit `theme.css`.
- `build-tokens.mjs` asserts color parity: every color token needs a light and a dark value, or it exits 1 ("Every color token needs a light and a dark value"). A group-level `$type` is inherited; non-color tokens (the dark `weight` group) are exempt. The custom format exists because the stock color transform mangles non-hex values.
- A new foreground/background pair is added to `contrast-pairs.json` at level `error` (never `warn`): text 4.5:1, UI boundaries, focus and chart marks 3:1. The checker merges base `:root` variables, so paper pairs are checked as well. Tune the token value, not the threshold. Measured failures that shaped the palette: warning yellow text, tertiary text, health green on muted fills, orange step 9 (see recipes §1.1).
- Never let the word "token" reach a data-health page through an asset name (`tokens.css` was renamed `theme.css` because a test forbids it).
- Fonts: Fontsource woff2 (latin and latin-ext, about 165 KB), `font-display: swap`, a preload for `vendor/fonts/mona-sans-latin-wdth-normal.woff2`.

### 1.3 Vendor, icons and static serving

- `build-vendor.mjs` owns `ui_web/static/vendor/**`. `asset-manifest.json` records `schema_version`, `generator`, `build_command`, package hashes, `packages`, `icons` and per-file sha256; `build-vendor --check` also reports unmanaged files. `.gitattributes` marks `ui_web/static/vendor/** -text` because the manifest hashes raw bytes.
- Icon scan roots: `ui_web/templates/**/*.html`, `project_management/reporting/templates/**/*.html`, `ui_web/static/js/**/*.js` (skipping `report_editor/vendor`) and `ui_web/**/*.py` (skipping tests and frontend). The regex is `\biconoir-([a-z0-9]+(?:-[a-z0-9]+)*)`; `-solid` names map to `icons/solid/`; unknown names fail the build. Icon classes are literal (`iconoir-{% if %}` is forbidden; `test_frontend_assets.py` enforces it). Rerun `npm run build:vendor` after adding or removing an icon.
- Global CSS draws icons with `--icon: url()` and `mask` at 1em. Report-local mask rules and `report_editor/vendor/iconoir/` were deleted: report pages use the global subset.
- Static storage: `metrics/settings/defaults.py` declares `STATICFILES_STORAGE` (WhiteNoise `CompressedManifestStaticFilesStorage`), but Django 5.1+ ignores that setting, so the effective backend is the default `StaticFilesStorage` with unhashed URLs. Keep every asset manifest-safe anyway, since moving the declaration to `STORAGES` is the intended fix: the manifest backend rewrites every CSS `url()`, so each target must exist and vendored files must not carry a `//# sourceMappingURL` comment. Validate with `collectstatic --noinput` into a temporary `STATIC_ROOT` with `STORAGES['staticfiles']` set to that backend.
- htmx, Chart.js, the date-fns adapter and the annotation plugin are vendored, never fetched from a CDN, and never replaced by homemade shims.

### 1.4 Stylelint

- `.stylelintrc.json` extends `stylelint-config-standard` with: `color-no-hex`, `color-named: never`, `function-disallowed-list` (`rgb`, `rgba`, `hsl`, `hsla`, `hwb`, `lab`, `lch`, `oklab`, `oklch`) and a `font-family` allowlist (`var(`, `inherit`, `monospace`). `color-mix()`, `transparent` and `currentcolor` are allowed. ID selectors, vendor prefixes (`-webkit-line-clamp`) and `!important` are allowed; many standard style rules are switched off. `theme.css` and vendored CSS are ignored; report CSS is linted like any other file.
- Fix a file with `npx --no-install stylelint <file> --fix`. For a mechanical re-tokenization use a deterministic script, then hand-fix what lint reports.
- Never write the literal selector sequence `.button, .input, .textarea, .select select, .tag` (one per line) in CSS; a design-system test forbids it. Share via primitives instead.

## 2. File Architecture

One asset manifest, no bundler, no CSS `@import` chains.

| Layer | Files | Owns |
| --- | --- | --- |
| Tokens | `ui_web/frontend/tokens/*.tokens.json` → `theme.css` | Every color, font, size, radius, shadow, duration, z-index |
| Primitives | `ui_web/static/css/foundation/*.css`, loaded in this order | `base` (reset, document), `layout` (block rhythm and surfaces: box, card, message), `typography` (label, help, paper), `buttons`, `forms` (input, textarea, select, checkbox, radio, field, control), `tables` (table, table-container, tags), `disclosure` (chip-disclosure, disclosure, tabs), `feedback` (pagination, progress, loader, loader-block, skeleton, delete, icon, htmx indicator), `page-patterns` (page-header, description-list, eyebrow, stat-grid, stat, pipeline), `charts` (chart grid, card and frame, series toggles, categorical `data-palette-slot` colors), `status` (delta, empty-state, status-dot, count-badge, health, avatar, person, avatar-stack), `work-items` (work-item-ref, item-key, results-bar, board, board-card, meta-strip, popover), `helpers` (visibility, width, truncation, tabular numbers, text alignment, text tones) |
| Shell | `ui_web/static/css/shell/`: `frame`, `sidebar`, `topbar`, `palette`, `statusbar`, `responsive`, `standalone`; `ui_web/static/js/shell.js`, `command-palette.js` | Sidebar, rail, drawer, topbar, breadcrumbs, theme switch, palette, status bar, popovers, toasts, the standalone frame |
| Pages | `ui_web/static/css/pages/<feature>.css` (`common`, `home`, `dense-tables`, `scope-config`, `scope-query`, `scope-library`, `editor-forms`, `provider-setup`, `provider-editor`, `editor-responsive`, `delivery-views`, `projects`, `report-templates`, `project-reports`, `workbench-shell`, `workbench-panes`, `workbench-evidence`); `ui_web/static/js/<feature>.js` modules in `FEATURE_SCRIPTS`: `table-interactions` (task-tree expand, lazy child rows, avatar fallback), `navigation-menus`, `searchable-pickers`, `scope-source-modes`, `editor-forms` (dirty state, auth-mode panels), `form-validation` (required messages, confirms), `workbench-state`, `pane-layout` (splitters, collapse), `workbench-evidence`, `htmx-lifecycle` (progress, error toasts) | Feature surfaces composed from primitives |
| Charts | `ui_web/static/js/charts.js` → `window.DashboardCharts` | Chart defaults, palette, series colors, re-theming |
| Manifest | `ui_web/static_assets.py`, `ui_web/templatetags/dashboard_assets.py` | The ordered stylesheet and script lists and their rendering in `base.html` |

- **Adding a CSS or JS file means adding it to `ui_web/static_assets.py` and nowhere else.** `base.html` renders the manifest through `dashboard_assets`, and Playwright tests inline the same list (`ui_web/tests/dashboard_asset_support.py` imports `STYLESHEETS` from the manifest and provides `PAGE_SCRIPTS`, `strip_static_asset_tags`, `inline_dashboard_assets` and `shell_fragment_html(fragment, theme='dark')`). A second hand-maintained list is a bug.
- Stylesheet order is cascade order: modern-normalize, fonts, `theme.css`, the foundation files in the order above, Iconoir, the shell files, then `pages/` files; page `extra_css` renders after all of them. Script order is dependency order: htmx, Chart.js, the date-fns adapter, the annotation plugin, `charts.js`, `shell.js` (publishes `window.DashboardShell`), `command-palette.js`, then `FEATURE_SCRIPTS`; page `extra_js` renders at the end of `<body>`. All manifest scripts load in `<head>` because inline page scripts use them. Primitives never depend on page files.
- **One concern per file.** Page styles go to the `pages/<feature>.css` of the feature they style and behavior to the `static/js/<feature>.js` module of its concern; there is no catch-all stylesheet or script to fall back on, so a rule or behavior that fits no file gets a new file registered in the manifest. Each module keeps its state inside its own `DOMContentLoaded` handler (or, like `table-interactions.js`, uses document-level delegation only) and re-initialises swapped markup on `htmx:afterSwap`, so `FEATURE_SCRIPTS` order is init and after-swap order (`htmx-lifecycle.js` stays last). Prefer delegated listeners; add no globals beyond `window.DashboardCharts` and `window.DashboardShell`.
- A new primitive goes to the foundation file of its concern, with tokens only, documented in the recipes and used by at least one template in the same change.
- Page CSS is loaded per page through `extra_css` only when several pages do not share the rules; shared rules belong in foundation or the page layer.
- Report editor CSS (`report_editor.css`, `report_assist.css`, `report_exports.css`) and `static/js/report_editor/` stay separate from the dashboard layers, and are token-only.
- Line endings: keep each file's existing endings. In this working tree templates, Python, most tests, most CSS/JS and token JSON are CRLF while generated files, Markdown, `package.json` and new files are LF (the index is LF and `core.autocrlf=true`). Use an editor that preserves endings; after a scripted edit assert there are no mixed endings. PowerShell `Set-Content` is unreliable for this.

## 3. File-Size Gate

`python -I scripts/check_file_size_limits.py --include-untracked` runs in changed-file mode and is required before review, together with `python -I scripts/check_diff_whitespace.py --include-untracked` and `git --no-pager diff --check`.

| Files (first matching rule wins) | Cap (lines) |
| --- | --- |
| Django templates `**/templates/**/*.html` | 300 |
| CSS `ui_web/static/css/**/*.css` | 400 |
| Browser JS `ui_web/static/js/**/*.js`, `ui_web/editor_build/*.js` | 400 |
| Frontend tooling `ui_web/frontend/scripts/*.mjs` | 300 |
| Frontend config and token JSON | 300 |
| JS tests `ui_web/tests/**/*.mjs` | 600 |
| Python tests / Python source | 600 / 400 |
| AI guidance markdown (`AI_CONTRACT.md`, `AGENTS.md`, `CLAUDE.md`, `.github/**`, `.agents/**`) | 260 |
| Other Markdown (including `openspec/`) | 1200 |
| PowerShell | 400 |

The table lists the frontend-relevant rules; `.github/file-size-limits.json` is the authority for every rule (YAML 400, other JSON 1200, repository config 300, AI guidance JSON 220) and exemption.

- Every changed file must be claimed by a rule or an explicit exemption (vendored, generated, binary, translation catalogs); an unclaimed file fails the gate.
- Files already over their cap are legacy allowances with `max_added_lines` 0, an owner and a split plan. An allowance is a temporary freeze, not a home: in changed-file mode the file never grows, and its owner splits it below the cap and deletes the entry (`test_legacy_allowances_name_an_owner_and_still_cover_over_cap_files` fails on a stale entry). `--all` and explicit-path runs stay strict and show the debt. Frontend pages, styles and scripts have no allowances; never add one for them.
- **Split before you add.** When a template, stylesheet or script approaches its cap, split it by concern before adding more: partials for templates, one CSS file per component family or feature, extracted JS feature modules. Never fix a size failure with an exemption, a minified line or a looser cap.
- Giant files also slow the work itself (every read, edit and review pays for the whole file); give each feature its own file so parallel work has disjoint ownership.
- When migrating, delete the obsolete rules, classes and scripts it replaces (grep for references first). No compatibility shims or aliases; rename old variable usages directly.
- Update the owning documents and `tasks.md` in the same change as a new primitive or contract.

## 4. Testing Strategy

### 4.1 Layers

| Layer | Where | Use for |
| --- | --- | --- |
| Tooling gates | `npm run check`, `lint:css`, `qa:contrast` | Token drift, raw colors, contrast, vendor and icon drift |
| Server tests | `ui_web/tests/` (`SimpleTestCase`/Django test client) | Template contracts, copy, classes, `data-*` hooks, context keys, template filters, doc assertions (`test_dashboard_ui_design_system.py`) |
| Browser tests | `ui_web/tests/*browser*.py` with Playwright, rendering real templates with inlined assets | Computed styles, geometry, focus, keyboard, theme flips, overflow, htmx-free interaction |
| Geometry registry | `ui_web/tests/ui_geometry_contract.py`, guarded by `test_ui_geometry_contract.py` | Every pixel threshold declared once by key; rejects literal thresholds in tests, rules no test enforces and stale `enforced_by` lists |
| Baseline gate | `ui_web/tests/test_ui_design_baseline_gate.py` with `ui_design_browser_metrics_support.py` and `scripts/ui_design_fixture_hooks.py` | Layout metrics across surfaces at 1440×900 and 390×900 |
| Route QA | `npm run qa:browser` against a running server | Overflow, console errors, axe, both themes, both viewports |
| Real browser | ego-browser review (§5) | Hierarchy, alignment, truncation, density, states |

Prove behavior at the lowest layer that can see it: copy and classes in server tests, geometry and computed color in browser tests, whole-page health in route QA, taste in the real browser.

### 4.2 Running tests

- Use the project's selected interpreter explicitly (`<app-venv>\Scripts\python.exe -I -m pytest <file> -p no:cacheprovider`); system Python has no pytest. Root `conftest.py` sets `DJANGO_SETTINGS_MODULE=metrics.settings.development`.
- Clear inherited `METRICS_*` and `DJANGO_*` variables, then set synthetic Jira values or `ui_web/container.py` raises `PROVIDER_ENDPOINT_INVALID` during page tests:

```powershell
Get-ChildItem Env: | Where-Object { $_.Name -like 'METRICS_*' -or $_.Name -like 'DJANGO_*' } | ForEach-Object { Remove-Item "Env:$($_.Name)" }
$env:METRICS_JIRA_SERVER_URL='https://tracker.example.test'; $env:METRICS_JIRA_AUTH_MODE='server_pat'; $env:METRICS_JIRA_API_TOKEN='<synthetic-placeholder>'
```

- `scripts/validation/run_report_authoring_tests.py <explicit paths> -q -p no:cacheprovider --tb=short` is the alternative for report tests: synthetic settings, in-memory SQLite, a temporary `STATIC_ROOT` and a loopback-only network guard.
- Run focused files first (15–25 s each). The full non-browser `ui_web` run takes about 12 minutes, so run it once at the end. Browser tests have "Browser" in the class name: select with `-k "not Browser"` (`--ignore-glob=*_browser.py` misses `test_browser_*.py`). Default pytest paths omit some modules; always name the affected paths.
- Browser tests need `chromium_headless_shell` (`python -m playwright install chromium-headless-shell`). A failed browser launch cascades `SynchronousOnlyOperation` into later tests, so run browser groups in separate processes. In-memory SQLite is per process, so manual shards work (xdist is not installed; at most about 6 Playwright shards at once).
- Isolated Django check: configure settings through the test helper (`settings.configure(**test_settings(Path(temp)))`), `django.setup()`, `call_command('check')`.
- Logs are UTF-8; sanitize before printing to a cp1252 console. `scripts/validate_ui_*.ps1` hard-code a missing `.venv`: run the same checks with the selected Python.
- Diagnostic tests and temporary subclasses of `TestUiDesignBaselineGate` are deleted before commit.

### 4.3 Contracts to persist before rewriting a page

Before rewriting a template or stylesheet, read the constraining tests once (`ui_web/tests/*support.py`, `test_dashboard_ui_design_system.py`, `test_ui_design_baseline_gate.py`, the page's own tests) and write the contract down in a scratch note kept outside the repository: protected strings and classes, class order, ids, fixture hooks. Geometry thresholds are not part of the note: print them with `python ui_web/tests/ui_geometry_contract.py`. Re-deriving contracts after every context compaction cost five consecutive planning rounds. Write the template and CSS first once the contract exists; do not re-read the same files. Grep tests before moving links, headings or breadcrumbs.

Pinned by tests (search `ui_web/tests` before changing any):

- Titles and labels: "Bug Trend Indicator", "AI Dashboard Workflow", "Bug Trend Scope Audit", "Provider Profile Config", "Metrics Workbench", "Report workbench", "Archived", "New Scope", "New Profile", "Cancel Editing", "Filter evidence", "No chart data for this range", "Recalculate this scope before using this chart as current evidence.", "Profile Editor" (aria-label), "New profile draft"; scope audit labels "Total issues", "Issues with created/updated/resolved date", "Status transitions", "Resolution transitions".
- Editor copy present: 'Base URL', 'Authentication method', 'System status', 'Clear saved credentials', 'HSD-ES Connection Probe', 'Dashboard profile key', 'Field Bindings', 'Not set', 'Windows Integrated Auth', 'Your username', 'Connection test: success', 'Last test: success', "Authentication details", 'Base URL required'; Scope Config: 'Choose provider first', 'Save binding', 'Save Draft requires', 'Enable Scope requires', 'Source population', 'inactive source mode is ignored', 'Validate values', 'provider-tab-check', 'Jira</span>', 'HSD-ES</span>', `role="tablist"`, `role="tabpanel"`, 'scope-query-builder-toolbar', `hx-target="#scope-metadata-options"`, and `dashboard-required-tag` in the main template; 'Metadata discovery context' is absent under Jira. Absent from the editor: 'Credential ref', 'Onboarding status', 'provider-profile-table-box', 'Advanced source settings'; 'Save scope config' absent from Scope Config; "Scope Audit" absent on new or duplicate drafts; `meetings.html` has exactly one `h2`.
- Data-health pages never contain "token" and keep raw values in the HTML (`partial`, `stale_config`, `auth_failed`, `Bearer [redacted]`, `disabled`, `provider_owned_saved_query`, `Policy: compatibility_allowed`). Report starter labels ("Copy daily starter", zh-hans "复制每日起始模板") are visible exactly once, on the submit button. `test_project_csrf_language.py` asserts "Create project" / "创建项目" and that the description is not shown.
- Class order and ids: `provider-setup-choice is-provider-blue is-selected`; `scope-provider-choice is-provider-green is-selected`; `scope-config-provider-panel provider-tab-shell is-provider-X`; `dashboard-edit-form box scope-config-provider-workflow is-provider-X`; `provider-action-cancel`, `scope-editor-actions`, `scope-provider-tag`, `.scope-library-header`; exact `id="…" name="…" value=""` substrings. Scope Config color checks read the workflow form's `borderLeftColor` (`workflow_frame_is_blue`) and the selected tab's `borderBottomColor` (`selected_tab_underline_is_blue`), both `rgb(28, 126, 214)`; update a test honestly when the design changes, never fake a border.
- Structure: every `<form>` carries `dashboard-edit-form`, `dashboard-tool-form` or `dashboard-action-form`; every `<table>` carries `responsive-admin-table` or `dashboard-dense-table`; tool forms have no `is-small` buttons and no `data-dirty-form`; top toolbars carry `dashboard-top-toolbar`.
- Geometry: every pixel threshold is one rule in `ui_web/tests/ui_geometry_contract.py` (key, limit, unit, comparison, surface, what it measures, viewports, enforcing modules). Python assertions use its constants; measurement JavaScript receives `browser_limits()` as `limits` and reads `limits.<KEY>`. Never copy a number into a test, note or document. Checks that are not thresholds stay in the tests: the padding selector `th, tr:not(.is-empty-row) > td`, icon buttons have names, the sidebar splitter ArrowRight grows `--dashboard-sidebar-width` and persists it, at least 3 `[role=tab]`, the connection-test result sits above the actions, 2 signature items, and on phones the scope library `thead` is `display: none` with a grid first cell. Viewports: baseline gate 1440×900 and 390×900; scope library 1920×900, 1532×768, 1180×820 and 390×900; data health 760 and 390.
- Report tests: contrast ≥4.5 against the nearest opaque background, `textFits`, toolbar icons at least `REPORT_TOOLBAR_ICON_MIN_SIZE` with an Iconoir `maskImage`. Contrast tests parse `rgba(0,0,0,0)` as black, so measured elements use opaque backgrounds and no `color-mix()`.
- Gate fixtures render partials standalone. The gate collects every violation and fails once with `N browser metric violation(s):`, one line per `RULE=limit: metric=value (expected …) @ page viewport`: fix them all, then rerun. A threshold changes only in the registry, with design approval; `test_ui_geometry_contract.py` scans every test module that measures the browser (`.evaluate*(`, `bounding_box(`, `getBoundingClientRect`) and fails on a literal threshold, a rule no test enforces, or an `enforced_by` list that drifted. When a table's column count changes, update `task_table_colspan` and the fixture colspans.
- Navigation and shell hooks: `data-dashboard-layout`, `data-dashboard-sidebar`, `data-dashboard-sidebar-splitter`, `data-workbench-nav-link`, `data-workbench-status-bar`, `data-workbench-job-status`, `.app-crumbs__trail a[href]`. `test_dashboard_shell_browser.py` covers live System follow, pinning, palette, rail and drawer.
- Test helpers: browser tests build pages with `strip_static_asset_tags(html)` plus injected htmx/Chart stubs, so `url()` targets inside inlined `fonts.css`/`iconoir.css` do not load (non-blocking). Full-page headless tests render the light theme; `shell_fragment_html` defaults to dark. After a `matchMedia` change wait one `requestAnimationFrame`.

### 4.4 Known pre-existing failures and baselines

- Classes seen on the base commit, unrelated to frontend changes: `facade_factory` pollution in report browser tests (`default_report_facade() takes 0 positional arguments but 1 was given`; passes in isolation, fails after `test_report_authoring_browser.py` in the same process because `report_authoring_browser_support.py` saves `View.facade_factory` through the class, which unwraps the staticmethod, and restores the bare function with `setattr`), the baseline-gate core-surfaces test, a monkey-journey test, two bug-trend browser tests patching a non-existent `create_jira_client`, `visualTemplateLibrary` strict mode (five `[name=template_choice]`), and a timing-flaky concurrent-federation test. Task, PR, velocity and forecast pages return 500 on a dev server without tracker keys (`METRICS_PROJECT_KEYS` unset), and Django's own 500 page overflows at 322px.
- Verify before labelling a failure pre-existing: reproduce it in a clean `git worktree add --detach <temp-dir> <base>` (then `git worktree remove --force`), and check whether it is environment-dependent. Do not fix it unless your change caused it; record it.

## 5. Real-Browser Review

### 5.1 Preview server

- Run an isolated server on its own port (never the user's long-running instance) with synthetic seeded data, a placeholder Basic-auth credential, the project operator env set, `--noreload` and cached template loaders. Python and template edits need a restart (an uncached-loader config avoids it); static CSS and JS need none, but still disable the browser cache. A stale cached template once misled a review round.
- The venv `python.exe` is a launcher with a child process: find both and `Stop-Process -Id` each. Start the server detached, verify with `Get-NetTCPConnection -LocalPort <port> -State Listen`, and restart it before the final review.
- Seed with `seed_bug_trend_sample` and `project_catalog create` (keys `[a-z0-9][a-z0-9_-]{0,63}`, lowercase). Charts need a completed run whose `config_version_hash` equals the scope's current hash. When demo units are wrong (for example worklogs must be second durations for `ProportionalStoryPointCalculator`), fix the demo seed data, not production code.

### 5.2 ego-browser protocol

- Keep review scripts outside the repository, one `.mjs` per round, run with `ego-browser nodejs -e "await import('file:///…')"`. Use `taskSpace(name)` with a new name each round (a space can vanish on restart) and never touch another task space; call `task.finish({keep:[]})` once at the end.
- The API is not Playwright (no `locator`, `$`, `goBack`): `click(sel, {label})`; `mouse.down/up` and `press` reject `label`; use `page.evaluate`, `page.cdp` and `task.newPage()`. `EGO_*` variables do not reach the node process. Console capture needs `egoAutomated.disable` and `Runtime.enable`.
- Always enable `Network` and `Network.setCacheDisabled` first (stale JS otherwise); send Basic auth through `Network.setExtraHTTPHeaders`; set viewports with `Emulation.setDeviceMetricsOverride` (1440×900 and 390×844); un-minimize a minimized window with `Browser.setWindowBounds {windowState:"normal"}` before screenshots; crop with `Page.captureScreenshot` and a clip; screenshot paths are absolute with forward slashes. Ignore the red "Adobe PDF" icon (`div#aiFabShadowRoot`, a browser extension). A full-page shot taken after a scripted scroll misplaces fixed chrome: the sidebar starts mid-image and the skip link (hidden with `translateY(-300%)`) appears just above the scroll offset. Take a viewport shot for scrolled targets; neither artifact is a product defect.
- Never click shell pages by coordinate (`mouse.click(12, 12)` hit the sidebar brand link). Click a stable element: `#main-content` with a small offset, `.app-crumbs__page`, `#workbench-chart-title`. A very tall splitter put a computed y off-screen.
- Switch themes with `[data-theme-choice="dark"]` or `localStorage["dashboard-theme"]` and clear the value afterwards. Add a metrics pass per page: `overflowX`, unclassed tables, pending htmx, error text, card leaks, clipped buttons or tags, applied theme. Skip elements clipped by an ancestor whose `overflow-x` is not `visible` (a wide table scrolling in `.table-container`, the `ul` of a `.tabs` strip) and elements inside a closed `<details>` (forced layout still measures them); report scroll containers that overflow by only a few pixels separately, because they draw a full scrollbar for nothing. For tabs, check the strip's `scrollWidth`/`clientWidth` and whether every tab is visible.
- Visual review found what the gates missed: stacked toolbar buttons, a clipped toolbar, duplicate in-page breadcrumbs, heavy dark-theme text, over-saturated warning yellow, a create form placed before the list, a 70px overflow, an `is-light` override that made "Archive" look like plain text, the Workbench IDE frame squeezed onto a phone, and a duplicated evidence filter form that left 180px gaps. Review both themes and both viewports for every touched page and fix findings or defer them in writing. Do not restyle other pages before style direction is confirmed.

### 5.3 `qa:browser`

- Environment: `DASHBOARD_QA_BASE_URL` (required), `DASHBOARD_QA_BASIC_AUTH`, `DASHBOARD_QA_ROUTES`, `DASHBOARD_QA_VIEWPORTS` (default `1440x900,390x844`), `DASHBOARD_QA_FULL_PAGE=1`, `DASHBOARD_QA_THEMES` (default `light,dark`), `DASHBOARD_QA_SKIP_ROUTES`, `DASHBOARD_QA_CONCURRENCY` (3), `DASHBOARD_QA_BROWSER_CHANNEL` (default `msedge`), `DASHBOARD_QA_BROWSER_PATH`. Routes default to `/` plus every `.app-nav__link[href]`; the theme is applied through an init script writing `localStorage["dashboard-theme"]`.
- Fails on navigation error, HTTP ≥400, overflow >1px, requested ≠ applied theme, console or page errors, failed same-origin requests and serious or critical axe findings (wcag2a, 2aa, 21a, 21aa, 22aa). Moderate and minor axe findings warn; "Failed to load resource" console noise is ignored. Output goes to `ui_web/frontend/.qa/browser/report.json` and `report.md` (git-ignored with `node_modules/`).
- The run is hermetic: every cross-origin request is blocked. A blocked script, stylesheet or font fails the route (runtime assets are vendored, never loaded from a CDN); other blocked requests (Grafana embeds, provider avatars) are warnings. Third-party embeds therefore load on demand: the Grafana preview keeps its URL in `data-grafana-src` and `grafana-embeds.js` sets `src` when the `<details>` opens, with the dashboard theme, and re-themes it on `dashboard:themechange`.
- Each run deletes and recreates `.qa/browser`, so copy a report you want to keep. Deep routes (detail pages, editors, a Workbench with a selected bucket) are not in the sidebar: list them in `DASHBOARD_QA_ROUTES`, which replaces the default route list, and run the navigation routes separately.

## 6. Debugging Pitfalls

### 6.1 htmx 2

- htmx 2 defaults `selfRequestsOnly=true`: a test page served from another origin (for example `set_content`) blocks requests. Serve fixtures from the app origin and let real htmx send `HX-Request`; never reintroduce shims that ignore `hx-post`, `hx-trigger` or `hx-on`.
- Disabled and unchecked inputs are not sent. A GET request does not include an enclosing form: use `hx-include="#form-id"`. `hx-vals` overrides same-named inputs. A GET with `hx-push-url` pushing empty parameters is acceptable.
- Back navigation reloads the full page (`historyCacheSize: 0`); verify with `history.back()`, not a re-navigation. Partial endpoints must return a fragment for `HX-Request` and a full page otherwise.
- Never put `hx-trigger="every 2s"` on an ancestor of a status region: it re-fires for every descendant swap. Polling uses data attributes that carry the status URL and a script-owned timer.
- Out-of-band targets are stable ids; do not rename them (the PR page targets are listed in recipes §6). Toasts render into `#notification-container` (`aria-live="polite"`) as one `.message.is-danger` built with DOM APIs (recipes §2.1).

### 6.2 Django templates

- `{# #}` comments are single-line only: use `{% comment %}` for multi-line. `{% load %}` goes on line 1 or immediately after `{% extends %}`. A new templatetag library needs a server restart. Avoid `{{` inside inline JS (use `json_script` data). `level|add:3` renders empty when `level` is undefined.
- String literals in filter arguments are not escape-processed: `join:"\n"` renders a literal backslash-n (it shipped in ten Scope Config textareas). Use `join:"&#10;"` (recipes §11) and assert the rendered `&#10;` in a server test.
- The cached template loader hides edits on a running server; restart before judging a template change.
- Translations live in `ui_web/locale/zh_Hans/LC_MESSAGES/django.po` (CRLF, one line per string, no comments or flags); reuse an existing msgid before adding one. GNU gettext is not installed (no `xgettext` or `msgfmt`), so never run `makemessages`: append the entry, compile with `polib.pofile(po).save_as_mofile(mo)` (polib is a development tool, not in `requirements.txt`), commit both files and restart the server, which caches catalogs. `test_i18n_catalog.py` lists every missing translation as `path: (context, msgid)`; then probe the zh-hans pages in a real browser with the `django_language=zh-hans` cookie. Tests use the `zh-hans` language code. Orphan po entries stay: `{% trans variable %}` translates runtime values that extraction cannot see.
- Partials must render standalone in gate fixtures: no required context beyond what the fixture hook supplies, and tolerant of missing keys.
- Keep text inside templates short and sentence case. Keep Python helpers free of presentation strings; formatting belongs to `dashboard_format` filters (recipes §11).

### 6.3 Cascade and specificity

- Foundation primitives that components restyle are wrapped in `:where()` so that a single class overrides them. Bulma-style `X:not(:last-child)` margins at (0,2,0) once beat component rules (the provider tabs broke); re-check specificity whenever a Bulma rule is ported.
- Reference points: base `a` (0,0,1), `a:hover` (0,1,1), `.button.is-small .icon` (0,3,0); the helpers in `foundation/helpers.css` are `!important`. Declare neutral rules before semantic ones so the semantic color wins at equal specificity.
- Never hide a bug with a stronger selector, `!important` or an override of a primitive's display, size or weight; fix the primitive or choose a different variant. A page override is acceptable only for page layout (grid placement, widths).
- The Bulma compatibility layer is retired. `foundation/helpers.css` keeps only visibility (`is-hidden`, `is-invisible`, `is-sr-only`, `is-hidden-mobile|tablet`), `is-fullwidth`, `is-truncated`, `is-tabular`, text alignment and the `has-text-*` tones. In `ui_web/tests/test_dashboard_ui_design_system.py`, `test_shouldNotRenderRetiredLegacyMarkup` rejects the retired vocabulary in every template (and `is-light` anywhere but a plain `.button`), and `test_shouldDefineEveryModifierClassUsedInMarkup` rejects an `is-*`/`has-*` class that no stylesheet defines, so deleting a helper fails the suite instead of silently unstyling markup. Classes built in JavaScript or Python strings are outside those tests: grep `ui_web/static/js`, presenters and convertors before retiring a class.
- Measure before and after: when a style does not apply, read `getComputedStyle` in the browser and check which rule wins and which file loaded last, instead of guessing.

### 6.4 Layout and measurement

- Fixed chrome must reserve its own space (recipes §2.6): a fixed bar plus content padding that is not tied to the same token breaks at one viewport.
- `.responsive-admin-table-box` is a size container (`container-type: inline-size`): tables collapse by container width (`@container (max-width: 40rem)`), not viewport width, so the same partial works in a narrow column and on a phone. Viewport media queries stay at 768px for the shell, plus the Workbench 1024px/1023px layout pair (recipes §3.4); form grids size their columns from the container, and stylelint rejects any other width per file.
- Clipping bugs hide in `overflow: hidden` ancestors: tags, focus rings and popovers need either room or `overflow: visible`.
- A percentage `min-height` resolves only once the parent's height is definite. A grid item stretched to a content-sized row becomes definite after the row has been sized from every child, so a sibling's height counts twice: once in the row and again as blank space inside the percentage child (recipes §2.7). Keep fill-the-pane percentages inside frames with a fixed height. To locate a gap, read each box's `getBoundingClientRect()` and toggle one rule at a time in the browser before editing.
- Geometry assertions belong in browser tests with explicit viewport sizes and a registry limit; a pass at 1440 says nothing about 390.

## 7. Working Rules

- **Plan around constraints.** Persist the contract (§4.3) before editing; implement from it; do not spend a checkpoint on read-only research that produces no edit.
- **Parallel lanes.** Give each lane disjoint file ownership. Only one owner edits shared files: foundation, shell, `theme.css` sources, `static_assets.py`, `navigation.py`, `dashboard_format.py`, shared JS, `dashboard_asset_support.py`, `ui_geometry_contract.py`, the design documents and `tasks.md`. Lanes report their needs instead of editing those files.
- **Focused first.** Run the nearest test file before any wide run; shard browser tests; run the full suite once at the end. Do not run the same long suite repeatedly to "see".
- **Do not restyle unrelated pages** before style direction is confirmed on one reference page; migrate page by page in the order of the OpenSpec task list.
- **Docs travel with code.** A new primitive, token, hook or contract updates the recipes, the class contract table and `tasks.md` in the same change. Sync stale framework mentions (Bulma) across documents, skills and overlays, but keep every string a test asserts, keep `ui_web.tests.test_ui_design_baseline_gate` named in the overlay, and do not rename `ui-design-system.md`.
- **Baselines.** Component-catalog baseline PNGs are stale after a redesign and need re-baselining as a task of their own.
- **Truth over memory.** Verify a remembered rule against the current code before writing or acting on it; the code wins and the document is corrected in the same change.
- **Commits.** Commit from an explicit allowlist of paths, never `git add -A`; include the Copilot co-author trailer; keep unrelated user changes untouched; never commit `ui_web/frontend/.qa/`, `node_modules/` or logs.

## 8. Final Gates

Run, in order, and record the evidence before claiming closure:

1. `npm --prefix ui_web/frontend run check` (tokens, vendor, stylelint, contrast).
2. Focused server and browser tests for every touched surface, plus `test_dashboard_ui_design_system.py`.
3. `collectstatic --noinput` into a temporary `STATIC_ROOT` with `STORAGES['staticfiles']` set to the WhiteNoise manifest backend (proves every CSS `url()` resolves; §1.3 explains why the configured storage cannot prove it).
4. Isolated `manage.py check`: `settings.configure(**test_settings(temp))` from `scripts/validation/run_report_authoring_tests.py`, `django.setup()`, then `call_command('check')`.
5. `python -I scripts/check_file_size_limits.py --include-untracked` and `python -I scripts/check_diff_whitespace.py --include-untracked`, then `git --no-pager diff --check`.
6. `qa:browser` against the preview server, then a real-browser pass in both themes at 1440 and 390 for each touched page.
7. `openspec validate adopt-meridian-design-system --strict` (or the validation of the active change).

Only the evidence of a command that ran counts; a gate that was skipped is reported as skipped.

# Dashboard AI Development Contract

Effective: 2026-11-05, following the user's approved delivery reassessment.
This is the single repository-level development contract for Codex, Copilot and Claude.
It does not grant permissions beyond the current user request or higher-level instructions.

## 1. Read And Execute One Plan

- Read this contract, the current task frontier, and the relevant module/specification before work.
  Use [README](README.md) and the current guides for product context; load detailed history only
  when it answers a concrete question. Do not repeatedly reload unchanged historical reports.
- OpenSpec owns requirements and changes; Superpowers supplies implementation and quality methods.
  One change has one authoritative `tasks.md`, one implementation coordinator and one evidence trail.
  Delta-spec and archive authoring rules are in
  [repo context](.github/ai-governance/repo-context.md#openspec-authoring).
- The current reporting ledger is
  [provider-neutral reporting tasks](openspec/changes/add-provider-neutral-project-reporting/tasks.md).
  Skill-default plan/ledger locations must not create a second execution state.
- Reuse approved decisions. Before a coding packet identify its user outcome, producer/consumers,
  exact interface, owned files, environment, negative checks, expected cost and stopping condition.
- Separate implementation, validation, external qualification and publication. An unchecked parent
  summary is not an instruction to reimplement its completed children.
- User pauses stop product execution after safe owned cleanup. Analysis or documentation requests
  do not resume implementation; a later explicit resume does. Read the newest request at handoff.

## 2. Preserve The Product Boundaries

- Dashboard is a modular monolith. Modules communicate through public `app/api/` boundaries.
  Domain logic stays framework-free; structured values use `@dataclass(slots=True)`.
- `project_management` owns projects/stages, accepted summaries, report editing and publication;
  `provider_sync` and provider adapters own external access. Chiplet is an instance, not a default.
- Reuse existing libraries and module APIs. Keep provider-specific authentication, IDs, queries and
  pagination in adapters. Do not invent a parallel product module for each provider.
- Use semantic HTML, htmx and the Meridian design system (DTCG tokens -> generated `theme.css`,
  `css/foundation/` primitives, `css/shell/` + `shell.js` frame, `css/pages/<feature>.css` page
  layers, one asset manifest in `ui_web/static_assets.py`). Every UI change follows the binding
  [frontend design requirements](openspec/docs/current-baseline/frontend-design-requirements.md)
  and its equally binding [recipes](openspec/docs/current-baseline/frontend-design-recipes.md)
  and [delivery playbook](openspec/docs/current-baseline/frontend-delivery-playbook.md); §7 lists
  the non-negotiables. Chart.js charts take colors from `DashboardCharts`; the approved locally
  bundled Milkdown/ProseMirror adapter supports report editing. This editor is an explicit JS-library
  exception, not permission to replace the application with a new frontend framework.
- Keep source, accepted-analysis and editorial baselines separate. Save is not Finalize.
  Only verified data-Git finalization advances the editorial baseline; weekly views do not.
- Canonical rich-text fragments preserve human text, deletion, paint, links and provenance.
  Markdown/plain/HTML are projections, not an excuse to round-trip away unsupported formatting.
- Ticket status comes from the captured provider record, never the model. Current assignee,
  explicit action owner and suggested owner remain distinct. Preserve one ticket per stable row.
- UI supports English and Simplified Chinese. Canonical generated business output is English;
  raw evidence and proper names retain their original text.
- Keep comments focused on non-obvious invariants, compatibility or security constraints.
  Prefer clear code; see [comment policy](.github/ai-governance/code-comment-policy.md).

## 3. Development And Runtime AI Are Different

- Runtime AI receives only its versioned task profile, bounded explicit input and output schema.
  It must not load development instructions, planning skills or repository-wide authority.
- AI Base owns execution facts and public SDK/API contracts. Dashboard owns source eligibility,
  evidence validation, candidate acceptance, human acceptance and report publication.
- Reuse the installed SDK. Do not build a second SDK journal, process manager or persistent task engine.
  Summary and authoring have separate business profiles and acceptance rules.
- Persist the exact request/key/store/profile/deadline before dispatch. Unknown submit is observed
  by its original key; it is not permission for another POST, new deadline or refunded budget.
- Schema/hash validity is not business acceptance. AI Apply only changes local dirty content;
  Save verifies the server-owned candidate receipt under the existing revision/CAS boundary.
- Changes to SDK/profile/pack/runtime compatibility require explicit selection and consumer checks.
  Never patch immutable released artifacts, old request bytes or historical receipts in place.
- The repository is early-stage and keeps no backward compatibility: when a consumer migrates to the
  SDK or embedded runtime, delete the legacy path with its settings, scripts, fixtures and tests in
  the same change and drop it from current docs; do not keep a fallback, mode switch or shim (for
  example the retired `embed=workbench` / `METRICS_AI_BASE_EMBED_MODE` path). User data, released
  artifacts and historical receipts are not legacy paths; the rule above still applies to them.

## 4. Match Tests To The Risk

- Use TDD for behavior changes: reproduce a meaningful failure, make the smallest correct change,
  then run direct and affected-consumer checks. Adding missing proof of existing behavior need not
  manufacture a product failure or change already-correct code.
- Test observable business contracts. One test may use several assertions for one user story or
  invariant. Mock external/SPI boundaries, not the business logic being qualified.
- HTTP/CSRF/owner validation, template coverage, schema/nullable values, dependency wiring and
  mounted editor behavior are required where they carry a contract. There is no blanket ban on
  testing views, templates, containers or validation rules.
- Reporting uses its existing L0 pure, L1 storage/service, L2 HTTP, L3 mounted-browser and L4 joined
  layers. Each layer answers a different question; pure field tests must not require a full Git,
  database, browser or Base fixture. Mutable state remains isolated between scenarios.
- Use explicit test paths: default pytest discovery does not cover all modules, including
  `project_management` and `provider_sync`. Collection, empty selections and skips are not acceptance.
- Reporting, `ui_web` and `project_management` tests run with the selected SDK interpreter through
  the isolated no-dotenv entry in [development and validation](docs/development/reporting-delivery.md).
  Do not accidentally run migrated consumers in the retained legacy `.venv` or test against the
  existing 8017 service.
- Deleting or renaming a test, script or fixture updates every current regression list, guide and
  command that names it in the same change (grep the old name). Archived changes and historical
  receipts stay unchanged as evidence.
- Inspect the actual HTTP result/state before waiting for navigation. Preserve failed responses,
  screenshots and logs under unique names. A later pass does not explain an earlier failure.
- Before review/commit, run the scoped size/whitespace gates and inspect staged bytes and paths.
  Django integration changes also require isolated `check` or its recorded equivalent.
- UI changes also pass the frontend gates in §7 and the Definition of Done of the frontend design
  requirements before any completion claim.

## 5. Control Execution Cost

- Deliver a small complete user workflow before expanding another subsystem. A completed packet
  should produce a scoped commit or an explicit reason it cannot yet be published.
- Review implementation, evidence and the next dependency boundary together when appropriate.
  Re-review only the changed findings/consumers; missing expected evidence is readiness, not
  automatically a newly discovered product defect.
- One production writer per repository. Use another agent only for a distinct independent task
  or gate. Codex subagents explicitly use `gpt-5.5` with `xhigh`; do not alter the main model.
- After two equivalent failures without new information, change the hypothesis or instrumentation.
  Do not blindly retry, weaken checks, extend an existing operation deadline or invent progress.
- Record setup, call and cleanup separately when measuring cost. Do not add overlapping timers,
  equate pytest/JUnit duration with whole-turn wall time, or promise unmeasured savings.
- At each packet boundary and after 60 minutes on the same question, decide continue, narrow the
  experiment or return to local design. Do not disguise new architectural scope as endless cleanup.
- Bind evidence to runtime code, test/fixture inputs and environment. Reuse unaffected evidence
  with an explicit dependency rationale; changed shared fixtures may invalidate consumers.

## 6. Safety And Source Authority

- Preserve pre-existing work verbatim unless this request explicitly owns the change. Stage an
  allowlist, never the whole dirty tree; verify the remote SHA after an authorized push.
- Development data is isolated from user data. Do not load real credentials, call real providers
  or models, migrate production databases, activate scheduling or send reports without authorization.
- Code-origin push permission is not data-Git export permission. Data remotes, backup destinations
  and formal activation keep their separate approval boundaries.
- Source reading is not provider writing. Recheck owner/scope/principal at the relevant boundary;
  do not use old cache membership or a same-host match as permission.
- Never guess Jira/HSD-ES endpoint, auth, paging or field semantics. Consult the authoritative
  [provider source references](docs/development/provider-source-authority.md) when changing them.
- Do not log or commit credentials, cookies, authorization headers or enterprise runtime content.
  Synthetic credentials must be clearly synthetic and restricted to owned test fixtures.
- No disk-free-space admission checks. Application quotas, path/ownership checks and actual I/O
  failure handling remain required; failed writes must not advance successful watermarks.
- Declare process ownership, command bounds, evidence and cleanup before long runs. Stop only
  owned resources; normal exit and emergency cleanup are separate conclusions.
- Keep one current guide and explicit supersession links. Historic documents and external donor
  instructions are evidence, not competing authority. No global skill/hook/config changes by default.

## 7. Frontend Design Non-Negotiables

These rules condense the binding frontend requirements, recipes and delivery playbook linked in §2.
The documents hold the exact values and win on detail; when code and a document disagree, verify
the code and fix the document in the same change.

- **Look.** Meridian is calm, fresh and information-dense: Radix Slate neutrals with an Indigo
  accent, Mona Sans for UI, Geist Mono for IDs, hashes and code, a 13px base, 32px controls, a 4px
  grid, hairline borders and faint shadows. Data is the hero. Color carries meaning, never
  decoration, and is never the only signal. Reject heavy or colored borders, bold uppercase labels,
  red "Required" pills, nested boxes, gradients, saturated neutral fills and default framework blue.
- **Tokens only.** Colors, fonts, spacing, radii, shadows, motion and z-indexes come from
  `theme.css` variables. Edit `ui_web/frontend/tokens/*.tokens.json`, then `npm run build:tokens`;
  never hand-edit `theme.css`. A new foreground/background pair joins `contrast-pairs.json` at level
  `error`; tune the token, not the threshold.
- **Themes.** Light, Dark and System are first-class. System follows the OS appearance
  (`prefers-color-scheme`), never the clock. Page CSS never branches on `[data-theme]`; theme
  differences are tokens, and both themes pass the contrast gate.
- **User flow.** `ui_web/navigation.py` is the single registry for the sidebar (collapsible,
  resizable, a drawer on phones), breadcrumbs and the Ctrl/Cmd+K command palette. Pages read
  page header -> filter toolbar -> results bar -> KPIs -> charts -> detail table; filters live in
  the URL, and a region renders each filter form and Clear action once (a shared partial takes its
  host page's URL-state form). Fixed chrome reserves its own space; list pages put the list before
  create forms. Pages outside the shell (404/500, iframe bridges) extend `standalone_base.html`,
  which needs no context. Phones break at 768px; the only other viewport width is the Workbench
  1024px IDE frame, which stacks into a scrolling page below it (stylelint allow-lists widths per file).
- **Primitives first.** Compose `css/foundation/` primitives. Page CSS owns page layout only and
  never overrides a primitive's display, size, padding or type, nor wins with `!important`
  (stylelint rejects it outside `foundation/`; control states use the `forms.css` hooks
  `is-dirty-control` and `is-required-missing-control`). The
  Bulma compatibility layer is retired: templates use none of its layout, spacing, size or weight
  classes, and every `is-*`/`has-*` class matches a stylesheet rule (design-system tests enforce
  both; grep scripts and presenters before retiring a class). Every table carries
  `dashboard-dense-table` or `responsive-admin-table`; empty values render as a muted dash through
  `dashboard_format`. Long ids and values truncate (`truncatechars`, or `span.is-truncated` inside a
  tag) with the full value in `title`; they never wrap the heading beside them or run under
  neighbouring actions.
  Menus and tips inside scroll boxes are fitted by script or placement, never by setting
  `overflow: visible` on the scroll box; pinned table cells are opaque.
- **Editors.** An editor is one card: the form carries the 2px `--provider-color` rail, provider
  tabs sit on its top edge with a provider-colored underline, and every section lives in the tab
  body divided by hairlines, never in nested boxes. Required hints are quiet right-aligned text
  after the help tip; statuses use `status_tag`, messages `.message`, toggles `:has(> input:checked)`;
  `is-light` is only the ghost `.button`; multi-value textareas join with `&#10;`, never `"\n"`.
- **Charts and paper.** Chart colors come only from `DashboardCharts`; payloads carry semantic
  slots and keys, never colors. Report `.paper` is a fixed-light surface isolated from primitives.
- **Bilingual.** English and Simplified Chinese ship together: every user-visible string goes
  through `{% trans %}`/`gettext` and gets its `zh_Hans` translation and recompiled `.mo` in the
  same change (`ui_web/tests/test_i18n_catalog.py` gates it). Page names come from the navigation
  registry; machine values stay in attributes; scripts read `data-message-*` without English
  fallbacks; brand, product and key names, acronyms, commands and URLs stay verbatim, and
  commands enter messages through placeholders. Times are 24-hour.
- **Files and assets.** Primitives live in `css/foundation/`, the frame in `css/shell/`, page styles
  in `css/pages/<feature>.css` and behavior in one-concern `js/<feature>.js` modules; there is no
  catch-all page stylesheet or script. Register each shared file once in `ui_web/static_assets.py`:
  no bundler, `@import` chain, second list or CDN. Only report pages load their own assets, through
  `extra_css`/`extra_js`, and never a manifest file again (`test_frontend_assets.py` enforces both
  directions). Feature modules self-initialise on DOMContentLoaded
  and `htmx:afterSwap`, so `FEATURE_SCRIPTS` order is init order. Libraries, fonts and icons are
  pinned and vendored by `npm run build:vendor`; icon classes are literal `iconoir-<name>`;
  `npm run check` re-hashes every vendored file and the Milkdown report-editor bundle.
- **Size gate.** Every tracked file is claimed by a rule in `.github/file-size-limits.json` or a
  reasoned exemption (templates 300, CSS 400, browser JS 400 lines). Split by concern before a file
  nears its cap; never raise a cap, add an exemption or minify to pass. A legacy allowance is a
  temporary freeze, not a home: the file never grows, its owner splits it, then deletes the entry.
- **Proof.** Read the constraining tests before rewriting a template. Pixel thresholds live once in
  `ui_web/tests/ui_geometry_contract.py` (print them with `python ui_web/tests/ui_geometry_contract.py`):
  tests compare against its constants or `limits.<KEY>`, never a literal, and a limit changes there
  only with design approval. A UI change is done only after `npm run check`, focused tests, the size
  and whitespace gates, `qa:browser` for touched routes on an isolated server, and a real-browser
  review of every touched page in light, dark and at 390px.
- **Learnings travel with the work.** Each completed UI round writes its new rules, values and
  pitfalls into the requirements, recipes or playbook (and here when non-negotiable) and checks
  off `tasks.md` in the same change. A rule kept only in chat, a session note or a handoff prompt
  is lost at the next handoff; fix any stale statement found on the way against the code.

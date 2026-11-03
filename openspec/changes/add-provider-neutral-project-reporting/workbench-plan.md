# W2 Project Workbench Packet

Goal: an authenticated operator can create, inspect, scope and archive a project from the desktop UI.
Architecture: existing Django/Bulma shell -> ui_web facade -> public project_management API;
BasicAuth supplies verified transport identity, Django session holds a bounded preview, gettext owns UI text.
Spec: [project-reporting](specs/project-reporting/spec.md), [design](design.md).
Status and dependencies: only [tasks](tasks.md); W2 implementation waits for W1.R and W1.REPLAN.
profile_source: repo-local. agent_routing_mode: multiagent-configured.

## 1. Scope And Decisions

This is the next architectural slice of the accepted product, not a new platform design.
Reuse the existing shell and local CSS/icons. No new frontend framework, auth provider, report runner,
provider connection UI, live calls or dependency on BASE-B.
The other agent's dirty Scope Config templates, CSS and tests remain untouched.
Mobile, additional browsers and cosmetic redesign are backlog by the user's explicit instruction.

Current evidence: BasicAuthMiddleware validates configured accounts but does not expose the verified
username to views. With no accounts configured, legacy routes are open. New project routes must not
inherit that open access. Django Session/CSRF middleware is already installed.
W1 exposes local_operator through CLI; it is not an HTTP credential.

Use verified Basic Auth instead of a second login system. Browser owners are `basic:<username>` by default.
An explicit deployment setting `METRICS_PROJECT_LOCAL_OPERATOR_USERNAME`, default empty, maps one exact
verified username to `local_operator` so CLI and browser may intentionally share that owner's projects.
Changing this setting changes access and must be documented as an operator-controlled configuration;
it never rewrites existing ownership. Do not infer the mapping from the first or only configured account.

Use one server-side session preview, not a client-authored descriptor or an approval token signed using
the repository's development SECRET_KEY. Preview data is not an execution permit or tracker permission.
Changing Basic Auth identity in an existing browser session invalidates that preview's owner association.

## 2. Exact Boundaries

### Verified Identity

`BasicAuthMiddleware` initializes `request.metrics_basic_auth_username = None` on every request.
It sets the attribute only after its existing configured credential check succeeds.
No query/form/cookie/header field may supply this attribute; remote-user and Django superuser fallback
are not supported by this first project route implementation.

`project_actor(request) -> ProjectActor` in `ui_web/project_access.py`:

- Require a nonempty verified username, without control/leading/trailing whitespace.
- If it exactly equals the nonempty configured local operator username, return `ProjectActor("local_operator")`.
- Otherwise return `ProjectActor("basic:" + username)`, respecting the domain's 160-character bound.
- Missing verification returns HTTP401 with a Basic challenge; malformed configured identity returns
  HTTP403 with safe English text. It must not read project/source storage first.
- Every project route, including language POST, uses this owner resolution.
- Responses with project/preview content use `Cache-Control: private, no-store`.

Legacy Basic Auth admission behavior is unchanged; publishing verified identity is the only shared
middleware extension. Its valid/invalid/disabled configuration paths receive targeted tests.

### Domain Preview And Confirmation

Public `ApiForProjectManagement` adds:

```text
preview_stage(actor, project_id, *, key, name, selection) -> StagePreview
add_stage(actor, project_id, *, key, name, selection,
          expected_definition_hash: str | None = None) -> StageSummary
```

`StagePreview` is a frozen slots dataclass: `project_id`, normalized `key` and `name`, `selection`,
`descriptor`, `definition_hash`. Re-export it from the public API; no ui_web imports from domain/out/models.
Preview validates actor/key/name/selection, checks project ownership and archive state, then resolves
the catalog. It writes no Project, Stage or Audit record.
Confirmation checks the expected lower-case 64-character SHA256, when supplied, against the resolved
descriptor inside the domain's add_stage flow before storage. A different hash returns SOURCE_CHANGED.
Keep W1's double-resolution consistency check, transactional archive/identity checks and idempotency.
CLI keeps its existing behavior by omitting the optional expected hash; Web must always supply it.

### Server Preview

`ProjectManagementFacade(api, source_catalog)` provides:

```text
list_projects(actor, *, offset: int) -> list context with next/previous offsets
get_project(actor, project_id) -> project detail and selectable source labels
preview_stage(actor, project_id, *, key, name, selection) -> StagePreview
confirm_stage(actor, project_id, preview_data) -> StageSummary
```

It consumes only public Project API and existing public BugTrend/profile registry APIs.
`ProjectSourceChoices.list_choices() -> tuple[ProjectSourceChoice, ...]` in `ui_web/project_sources.py`
returns frozen slots DTOs containing `key`, `label`, `provider_id`, `selection` only.
Keys are `jira/<profile_id>/<positive_decimal_scope_id>` and `hsdes/<profile_id>`;
the Django ChoiceField accepts only the current server-produced keys. Jira choices require enabled explicit scope/profile binding; HSD choices
have no Jira scope_id. No raw connection settings, passwords or provider network requests.
The domain remains final authority if a displayed source is disabled or changed later.

POST preview stores exactly one session entry `project_stage_preview`:

```text
preview_id: random 256-bit URL-safe value
actor_subject, project_id, key, name
selection: {profile_id, scope_id}
definition_hash: SHA256
issued_at: UTC epoch seconds
```

Only server-produced fields enter the entry. The preview response displays the current descriptor,
but query/connection data is not duplicated into the session.
Require `SESSION_ENGINE=django.contrib.sessions.backends.db` for preview/confirmation; another backend
returns a safe HTTP503 without storing or consuming a preview. In particular, a signed-cookie backend
must not silently turn server-held confirmation state into client-authored data.
Confirmation accepts `preview_id` only, compares it in constant time, checks actor/project and a
600-second maximum age with nonnegative elapsed time, then calls add_stage with the stored expected hash.
Reject missing/tampered/expired/other-owner/other-project previews with HTTP409 and no business mutation.
On success or source drift remove the preview. A duplicate confirmation cannot add another Stage/Audit.
Archive and language actions do not approve a pending preview.
Each rendered form supplies an explicit GET-safe language return URL, not the current POST-only action.
Switching language from confirmation returns project detail. A valid same-owner/project, unexpired session
preview initializes the detail editor with its key/name/selection, preserving the draft without approving it.
Write-only routes still return405 for GET; language switching cannot redirect normal UI controls to them.

### Routes And Forms

All route names are under `ui_web` and preserve the configured METRICS_BASE_URL prefix.

| Route / name | Methods | Input / output |
| --- | --- | --- |
| `projects/` / `projects` | GET, POST | GET stable owner list offset0..2147483647/limit50; POST create key/name -> redirect detail |
| `projects/<uuid:project_id>/` / `project_detail` | GET | Frozen stages/source state; no provider/model side effects |
| `projects/<uuid:project_id>/preview/` / `project_stage_preview` | POST | Valid key/name/source choice -> preview confirmation HTML |
| `projects/<uuid:project_id>/stages/` / `project_stage_confirm` | POST | preview_id -> domain confirmation -> redirect detail |
| `projects/<uuid:project_id>/archive/` / `project_archive` | POST | explicit confirmation checkbox -> archive -> redirect detail |
| `projects/language/` / `project_language` | POST | Django set_language with en/zh-hans and same-origin next |

All writes retain Django CSRF protection. No csrf_exempt or trusted actor from POST.
GET on a write-only route returns405. Owner mismatch returns404. Domain conflict/source drift returns409;
form shape failures return400 with bound fields and inline errors. Invalid, negative or overly long
offsets are400, never silently page0 or an integer-conversion500; the UI bound stays within database
integer range and is not a ticket/scope retention limit. Internal failures are not converted to
empty success. Do not expose raw exception text. Domain conflict feedback is localized UI text with
unchanged English error codes; authentication failure remains a safe401 Basic challenge.
Archived detail remains readable; creation/preview controls disabled. Source unavailable/changed is
displayed without changing the stored definition. There is no run/report button before W7 qualification.

Forms: `ProjectListQueryForm(offset)`, `ProjectCreateForm(key,name)`, `StagePreviewForm(key,name,source)`,
`StageConfirmForm(preview_id)`, `ProjectArchiveForm(confirm)`.
Source is a server-generated choice key encoding a safe ScopeSelection, not a free-form JQL/descriptor.
Validation shows field errors, preserves entered text, and moves focus to the first invalid field using
existing form-state behavior or native autofocus on the invalid control. Non-field errors use role=alert.

## 3. UI And Language

Reuse `base.html`, dashboard-edit-form/form-grid/form-field, dashboard-action-bar/action-group,
dashboard-action-form, responsive-admin-table and dashboard-dense-table. Existing Iconoir icons,
compactDashboard tokens, <=8px frame radii; no new global colors, font sizes or nested cards.
Add only a Projects navigation link and a language block in the new screens.
List: title, compact create form, paginated table with name/key/state/created date.
Detail: name/key/archive state, Scope Library link, frozen stage table, add-stage editor.
Preview: literal provider/query/endpoint and definition hash, confirm/back controls.
No marketing copy, fake report output or functionality explanation banner.

Use Django gettext/gettext_lazy and checked-in `ui_web/locale/zh_Hans/LC_MESSAGES/django.po` plus
generated `.mo`. English source strings remain the default. Compile with GNU msgfmt if available or
the pinned development-only `polib==1.2.0` compiler in an owned isolated tools environment.
Do not hand-write a gettext binary or add a runtime translation service.
Activate LocaleMiddleware after SessionMiddleware and before CommonMiddleware; allow only en/zh-hans.
The new forms, status/errors, navigation labels and language selection are translated.
Business names, raw query text, identifiers, descriptor hashes and API errors remain unchanged.
Existing unrelated legacy pages are not claimed fully localized in W2.
No call to any model occurs on language switch. TranslationPort remains future independent display work.

## 4. Validation Matrix

Each case exercises real domain/ORM/facade/routes. Only external provider/model transport is blocked;
do not replace the Project API or its owner checks with accepting mocks.

| ID / layer | File / test family | Initial state, action, observable result |
| --- | --- | --- |
| U01 L1 | `ui_web/tests/test_project_access.py` | Valid Alice/Bob Basic Auth produce distinct owners; query actor, REMOTE_USER and unsigned session values never override them |
| U02 L1 | same | Auth absent/invalid/disabled or malformed account never reads Project; explicit local operator mapping is exact, case-sensitive and opt-in |
| U03 L2 | `project_management/tests/test_stage_preview.py` | Owned preview returns normalized data/hash and zero new Project/Stage/Audit; archived/other-owner refused before catalog |
| U04 L2 | same | Source changes between preview and confirm, including during double resolve: SOURCE_CHANGED, zero Stage/Audit; original no-hash CLI remains valid |
| U05 L2 | `ui_web/tests/test_project_views.py` | Create two arbitrary projects through real POST; fresh GET lists only owner records; forms preserve failed input; stable pagination |
| U06 L2 | same | Real source choices include explicit Jira binding and HSD profile without Jira ID; disabled/mismatched sources cannot be confirmed |
| U07 L2 | `ui_web/tests/test_project_stage_views.py` | Preview -> confirm creates one exact Stage/Audit; tampered/expired/missing/other-project/other-owner/replayed preview makes no additional mutation; signed-cookie session backend returns503 |
| U08 L2 | same | Archive between preview and confirm prevents stage write; historical stages still readable; archived controls disabled |
| U09 L2 | `ui_web/tests/test_project_csrf_language.py` | enforce_csrf_checks on every POST route; missing token403; write-route GET405; another owner's detail404/no data; anonymous request401 |
| U10 L2 | same | en and zh-hans render labels/errors, locale POST redirects locally; Project/Stage/Audit and descriptor/raw bytes unchanged |
| U11 L1/L2 | existing W1/provider suites | Shared API optional hash preserves CLI, transaction/owner and public provider scope behavior |
| U12 L3 | desktop Ego synthetic browser | Empty -> create -> invalid form -> Jira/HSD preview/confirm -> locale -> archive -> read; no page overflow, operable keyboard/focus, no clipped commands |

Commands from the Dashboard root, with the existing `.venv/Scripts/python.exe`:

```powershell
.\.venv\Scripts\python.exe -m pytest project_management/tests/test_stage_preview.py ui_web/tests/test_project_access.py -q
.\.venv\Scripts\python.exe -m pytest ui_web/tests/test_project_views.py ui_web/tests/test_project_stage_views.py ui_web/tests/test_project_csrf_language.py -q
.\.venv\Scripts\python.exe -m pytest project_management/tests bug_metrics/tests/test_api_scope_config.py bug_metrics/tests/test_scope_provider_binding.py -q
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations project_management --check --dry-run
openspec validate add-provider-neutral-project-reporting --strict --no-interactive
```

Run full size/whitespace gates on the byte-matched owned review candidate, retaining the main checkout's
unrelated failures separately. No production DB migration or real profile/credential configuration.
Browser validation uses a dedicated test settings module/database with synthetic scopes/profiles/accounts,
one loopback server and explicit owned process cleanup. Fixture initialization takes an explicit per-run
root below `.tmp/project-reporting-w2/`, refuses a conflicting ambient DJANGO_SETTINGS_MODULE, validates
resolved containment/reparse components and a fixture ownership receipt before any data mutation.
It never flushes an unknown database; prefer a fresh empty per-run root without a flush operation.
Settings loading suppresses `.env` reads and does not create directories on import.
Add subprocess tests for wrong settings and escaping/unowned roots using harmless sentinel data;
also prove the ordinary owned fixture initialization and server settings identity.
Desktop target1440x900; Ego is accepted as Chrome
equivalent by the user. One functional run per stable candidate; not a repeated visual-polish loop.
Detailed browser fixture/server command and evidence path are fixed before U12 is launched.

## 5. Implementation Order And Exit

Owned files:

- `metrics/middleware.py`, `metrics/settings/defaults.py`, `metrics/settings/defaults_metrics.py`,
  `.env.example`: verified username propagation, locale middleware/languages, explicit owner mapping.
- `project_management/app/domain/contracts.py`, `service.py`, `app/api/__init__.py`:
  StagePreview and expected-definition confirmation. No W1 schema or migration change.
- `ui_web/project_access.py`, `project_forms.py`, `project_sources.py`,
  `facades/project_management.py`, `views/project_management_views.py`, `urls.py`:
  authentication, validated forms, safe source choices, public API consumer, session preview and routes.
- `ui_web/templates/projects/{list,detail,preview,language_switcher}.html`, `templates/base.html`,
  `ui_web/locale/zh_Hans/LC_MESSAGES/{django.po,django.mo}`, `.gitignore` (exact compiled catalog inclusion):
  minimal shared-shell UI and static translations. The compiled catalog must be distributable, not ignored.
- `project_management/tests/test_stage_preview.py`;
  `ui_web/tests/test_project_{access,views,stage_views,csrf_language}.py`,
  `ui_web/tests/project_fixtures.py`: isolated fixtures and U01-U11 cases.
- `scripts/validation/project_ui_settings.py`, `scripts/validation/project_ui_fixture.py`:
  explicitly invoked synthetic browser fixture; no automatic execution on import.
- Current change files and `openspec/docs/current-baseline/project-reporting.md`: truth sync.

No ownership over `ui_web/static/css/main.css`, the other agent's scope editor/tests, external repositories,
real DB/state, stored provider profiles or main Codex configuration is added.

1. Add U01-U04 RED tests; implement verified identity, core preview/hash guard and public exports.
2. Add U05-U09 RED route/form tests; implement safe source choices, facade, session preview and routes.
3. Add U10 RED language checks; implement gettext resources/compile output and minimal shared shell hooks.
4. Run affected U11, static gates, then U12 on the same candidate; record actual commands/results.
5. Independent W2.R reviews these boundaries and actual evidence; fix relevant findings before W2.REPLAN.

First RED command is the U01/U03-focused first command above after adding the new test files.
Exit is a usable, owner-isolated desktop project/stage workflow. It is not a report, provider capture
qualification, task submission or permission to start paid AI execution.

Propagation: verified username -> project_actor -> facade/API/session preview/audit; source selection ->
catalog preview/hash -> confirm guard -> immutable Stage; locale preference -> template/form labels only.
All three families have explicit negative cases above. Publication, scheduler, backend runs, provider
credentials and old Chiplet runtime stay non-goals. Current human guide receives the verified W2 behavior.

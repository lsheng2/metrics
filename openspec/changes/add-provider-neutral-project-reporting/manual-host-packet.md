# Manual Runtime And Full-Stack Host Packet

Scope: W7.E2E.HOST then W7.E2E.QUALIFY, in that order after RUN review.
This refines [manual-full-stack](manual-full-stack.md), sections 2/5/6.
State is maintained only in tasks.md. No schedule, live activation, data push,
production migration or UI redesign is part of these leaves.

## HOST Ownership

| File | Responsibility |
| --- | --- |
| `project_management/runtime.py` | Explicit runtime registry, one serial worker thread, bounded queue/stop |
| `project_management/services/project_run_recovery.py` | Trusted startup reconciliation over bounded stored operation metadata |
| `project_management/storage/project_operation_discovery.py`, `project_management/app/domain/run_contracts.py` | Bounded location discovery and immutable recovery-candidate DTOs |
| `project_management/services/project_runs.py`, `storage/project_operations.py` | Narrow startup-recovery delegation/metadata reader, retaining RUN's validated journal authority |
| `project_management/app/api/run_factories.py` | Trusted default composition and read-only status composition |
| `project_management/management/commands/project_serve.py` | Loopback server lifecycle, explicit runtime start/finally stop |
| `project_management/management/commands/project_run.py` | Same-service status and explicit local start/cancel/resume |
| `ui_web/project_run_forms.py` | Strict bounded form DTO conversion |
| `ui_web/facades/project_runs.py` | Only public project/run API consumers |
| `project_management/services/report_archive.py`, `ui_web/facades/project_reports.py` | Read-only absent-stage handling so the first Run is reachable before capture initializes its archive |
| `project_management/services/report_drafts.py` | Narrow historical-revision edition-state correction for the run-produced report link |
| `ui_web/views/project_run_views.py` | Auth/CSRF/PRG/private responses, no business implementation |
| `ui_web/templates/projects/reports/stage.html` | Add actual runtime readiness/run/status entry |
| `ui_web/templates/projects/reports/run.html` | Exact operation/revision, progress and produced-draft links |
| `ui_web/urls.py`, `project_language_returns.py`, locale `.po/.mo` | Scoped route and language wiring |
| `metrics/settings/defaults_metrics.py`, `.env.example` | Disabled defaults and documented configuration |
| `project_management/tests/test_project_runtime.py` | Worker start/stop/notification/read-only composition |
| `ui_web/tests/test_project_run_views.py` | FS07 authorization, CSRF, forms and GET-no-execution |

Reuse current Django/Bulma/htmx/Iconoir. Leave `main.css`, Scope Config and old
AI workbench untouched. Existing report routes keep their exact APIs.
The existing report default factory can use the runtime's actual report
service when one is installed, without constructing any worker on a GET.

First-run prerequisite: the current report facade calls archive readers that
require an initialized stage Git repository. A new catalog stage has no such
repository until its explicit Run. Do not pre-capture/seed a report to hide this
in the fixture. Add the read-only public
`CaptureArchiveService.stage_archive_status(actor, project_id, stage_id) ->
Literal["absent", "ready"]` to the existing report archive-access mixin.
It verifies owner, configured root and path containment using existing
primitives, and returns absent only when the entire stage directory is absent.
For a present stage it performs the existing identity verification; malformed,
foreign or partially initialized storage is an explicit error, not absent.
This is strictly a no-lock/no-parent-creation read. It does not enter CombinedLocks,
initialize a repository, or create `archive-root.json`, `projects/`, runtime or
lock directories. The facade exposes `archive_stage_status="absent"|"ready"`
and `can_create_draft=False` for absent storage, with empty draft choices.
The report facade shows the configured/no-retained-archive state with no draft
creation choices when absent, while the separate ready runtime Run form remains
usable. This read creates no directories/Git/threads. Update the explicit test
archive SPI doubles rather than adding a permissive duck-typed fallback.

## Runtime API

```python
class ProjectRunRuntime:
    def __init__(self, run_service, worker): ...
    def start(self): ...
    def stop(self, timeout_seconds): ...
    def notify(self, actor, project_id, stage_id, operation_id): ...

def build_project_runtime(): ...
def build_run_read_service(): ...
def install_project_runtime(runtime): ...
def get_project_runtime(): ...
def clear_project_runtime(runtime): ...
```

`get_project_runtime` returns the registered runtime or None and never builds
it. The install function refuses a different already installed runtime.
`start` explicitly creates one worker thread and attaches its notifier to the
service. Starting twice cannot create a second thread. No AppConfig/import/GET
starts anything. Read composition builds no SDK client or provider connection;
its mutating start refuses RUN_UNAVAILABLE without an explicitly active runtime.
An existing command replay and historical status remain inspectable.

Queue notification contains only the verified actor and bound IDs; the worker
reloads authoritative request and reauthorizes them. Duplicate notifications
are coalesced. A full volatile queue cannot erase the durable queued operation.
Use timeout-bounded queue waits plus a stop event, not busy loops.

`stop` first disables new submission, records cancel intent for owned queued/
active work, wakes the worker and joins only within timeout_seconds. It returns
the actual RuntimeStopResult, including unresolved active identity if the
thread has not exited. No forced thread kill, success before exit or implicit
shutdown of AI Base. Close Django thread-local connections on worker exit.
Exceptions become fixed safe operation errors and must not silently kill the
worker and strand every subsequent queued run.

For an explicit runtime start, mark abandoned capturing/analyzing operations
interrupted only after nonblocking stage execution-lock verification. Leave
another host's locked operation untouched. Resume remains an explicit command,
not automatic replay during import/start. Existing queued records need not be
auto-drained; status offers resume with original identity.

The exact internal producer for startup is
`ProjectRunService.reconcile_interrupted() -> tuple[str, ...]`, returning IDs
actually transitioned to interrupted. It is server-only, not a Web route.
Its storage discovery contract is:

```text
OperationLocation(project_id, stage_id, operation_id)
OperationRecoveryCandidate(location, actor_subject, admission_hash,
                           has_initial_event)
list_operation_locations(root: Path, *, limit=10000)
    -> tuple[OperationLocation, ...]
read_operation_recovery_candidate(root: Path, location, archive_limits)
    -> OperationRecoveryCandidate
```

Both DTOs are frozen slots dataclasses. Locations contain IDs, not free-form
paths. Listing validates the configured root and acquires only the existing
root budget lock while taking a bounded directory-identity snapshot, then
releases it before record reads or execution-lock acquisition. The directory
walk is explicit and bounded at each project/stage/operation level, counts
entries before filtering, rejects reparse paths and noncanonical UUID
directories, and uses at most one lookahead beyond the shared 10,000 scan cap.
Known `active.json`/`execution.lock` files are not operation directories.
Return locations sorted by project/stage/operation IDs; overflow is RUN_LIMIT,
lock contention is RUN_BUSY, malformed structure is RUN_STORAGE_INVALID.

Candidate reading creates nothing and takes no write/execution lock. It uses
the existing operation repository/read validators with actual archive limits
to verify the immutable request's full admission hash, path binding, actor and
timestamps. A missing/malformed request is RUN_STORAGE_INVALID, not silently
skipped. A valid request with no initial event is a request-only candidate;
the later under-execution-lock reread still validates the complete event set
and refuses a gapped history. Share a private bounded location iterator with
the existing admission scan when useful; do not recursively reacquire the root
lock from a caller that already owns it or build another index.

The recovery helper consumes those candidates,
using the same bounded path checks and full admission-record validator as RUN.
For each candidate, reconstruct the original actor/project/stage context from
that validated record, then reauthorize it through Project API and archive
identity checks before acquiring the stage execution lock.
Under a free execution lock, reread the current revision and CAS only
capturing/analyzing/cancel_requested to interrupted, preserving cancellation
intent. Busy stages remain unchanged. Queued/terminal operations stay unchanged.
Malformed/unverifiable stored metadata prevents enabling this runtime instead
of silently dropping claims. This helper starts no provider/SDK request.
An empty valid configured root is a valid zero-work startup, not permission
to initialize it on a GET.

A request-only interrupted admission can be completed through the original
submit replay while the notifier is still detached, preserving its original
ID/backend/budget/deadline. It remains queued for explicit user resume; startup
must not enqueue it automatically. This gives the operator an observable
recovery path without a second operation or hidden model dispatch.
Call reconciliation before attaching the notifier/starting the worker.
Request-only records repaired to queued are excluded from the returned tuple:
that tuple contains only actual transitions to interrupted. Startup does not
claim that queued repair is interrupted work or a completed report.

## Composition And Credentials

Read settings only in explicit factories. Use the settings table in the parent
packet. The run scope is derived from actual project/stage; configuration
supplies only base URL, source app, runStoreId, grant and limit revisions.
No secret goes into operation JSON. Only the lazy SDK client factory consumes
the separately configured credentialRef/token.

`AiTaskContract.load` verifies the package-pinned a2 artifacts. They are
synthetic-only, so default configuration cannot promote them to live.
The explicit validation composition can register an exact synthetic provider/
backend and set enabled=true. Normal deployment remains disabled until the
required matching qualification/configuration exists.

For validation only, a trusted settings callable
`METRICS_PROJECT_RUNTIME_FACTORY` may return a fully composed runtime.
It is None by default, cannot be selected through HTTP, and must not be an
arbitrary import string from a Web form. The validation settings module owns
its fixture inputs and fresh data paths; ordinary settings do not import it.

Use existing `build_project_api`, `build_capture_archive_service`,
`create_provider_access_service`, `capture_limits_from_settings`,
`build_report_service`, `SummaryAnalysisService` and Run service constructors.
No alternate provider/PAT store, AI client protocol or copied Git writer.
Configured but unreachable Base must not prevent browsing stored reports.

## Server And Routes

`project_serve --host 127.0.0.1 --port <port>`:

- Validate host/port before starting the worker; refuse non-loopback/autoreload.
- Install/start the runtime explicitly and run the existing Django WSGI app.
- Serve local static assets in the local development/validation mode using
  Django's existing static-file handler; no external asset proxy.
- In finally, stop/join worker and clear only this registry instance.
  Report unsuccessful drain rather than a fabricated clean stop.
- For owned validation, optional `--stop-file <absolute-owned-file>` and
  `--lifetime-seconds <positive>` provide bounded graceful shutdown. These are
  trusted CLI inputs, never Web parameters. A periodic bounded server request
  loop can check these without adding another business worker.

When cleanup evaluates a RuntimeStopResult, emit one JSON line to stdout:
`{"schema_version":1,"event":"project_runtime_stopped","stopped":bool,
"active_operation_id":uuid_or_null,"unresolved":[uuid,...]}`.
The command exits nonzero when startup/serving fails, stop raises, stopped is
false, or unresolved is nonempty. This line is a stop observation, not by itself
proof of successful startup; QUALIFY requires it together with readiness and
normal process exit. Clear the installed registry in nested finally even if
cleanup fails, without clearing another runtime that prevented installation.

The outer validation launcher reuses the repository Service Lifecycle Engine
and its process-provenance/stop-command support. Do not implement a parallel
PID manager or stop by port. If the app port is occupied, choose a new one
before launching; leave the user's old demo/server alone.
The fixture stop command writes only the recorded unique stop handle.
Its SLE graceful-stop bound must cover the worker's remaining original run
deadline plus cancellation/cleanup margin (at most 620 seconds for this
600-second policy), not SLE's short generic default. An idle worker still exits
immediately. A forceful fallback is reported as abnormal, not normal shutdown.

Routes under the existing stage prefix:

```text
POST runs/                         -> submit
GET  runs/<operation_id>/          -> status
POST runs/<operation_id>/cancel/    -> cancel(expected_revision)
POST runs/<operation_id>/resume/    -> resume(expected_revision)
```

Run form: command_id, expected_stage_hash, template_id, template_version,
timezone. The server constructs the bound project/stage and template options.
Cancel/resume forms accept only positive expected_revision.
Unknown/duplicate scalar fields and backend/path/actor injection refuse 400.
All mutating routes preserve BasicAuth identity, CSRF and PRG; foreign owner404.
Error status: invalid400, unavailable503, missing404, conflict/busy409, limit413;
no raw exceptions in the page. All status/form responses are private/no-store.
Successful redirect points to the original operation, including exact replay.

GET status and htmx polling call read APIs only. Poll at a bounded 2-second
interval while nonterminal, stop polling on terminal; refresh never advances
analysis. Show execution_mode=synthetic, original creation/deadline, complete
population/item states and fixed pending errors. Link the produced draft with
its recorded `revision`, plus a separate latest-draft link if it changed.
The original-version link targets `report_draft_render?revision=<recorded>`;
the separate edit/latest link uses `report_draft_edit`, whose existing GET
intentionally loads the latest revision and does not honor a revision query.
Do not label a link to that editor as an exact historical revision.
When rendering a historical revision, `ReportDraftService.render` may label it
final only if that exact revision is the validated finalization packet's
draft_revision. An older draft must not become "final" merely because a later
revision was finalized. Keep publication downloads on their original-byte API.
Cancel does not claim remote stop/refund. Dirty report editor behavior remains
owned by the report UI, not this status page.
Language safe-return adds only the new GET route; POST return maps to status.

CLI uses trusted local_operator and the same service. Status is read-only.
Start requires `--execute-local` if there is no runtime in this process; its
synchronous execution uses the same ProjectRunWorker and execution lock.
There is no pretend cross-process in-memory notifier. Cancel/resume for
existing work retain original IDs and deadlines. Do not add a new HTTP token
scheme or automatic cross-process worker spawn just for CLI convenience.

## HOST Tests

- Runtime not started: GET reports/status has zero provider/SDK/thread starts.
- New stage before any archive initialization: authenticated stage GET exposes
  Run without creating files; the first explicit POST can initialize/capture.
  A present corrupt archive remains an error, not an invented empty history.
- After editing/finalizing revision2, the original run's revision1 link renders
  revision1 as a draft, while the latest editor/publication uses revision2.
  This is a focused report-service test, not another full publication matrix.
- Two start calls use one worker; duplicate notify does not run twice.
- Explicit start marks an abandoned operation interrupted but leaves a stage
  held by another execution lock unchanged; request-only recovery becomes
  visible with the original identity and zero capture/SDK requests.
- Discovery overflow/malformed/reparse/request-hash cases refuse without
  loading another candidate, and returned interrupted IDs exclude queued
  request-only repairs.
- Stop idle and stop active return observed exit/unresolved accurately.
- Unexpected worker error does not kill later queue processing.
- New submit to offline runtime refuses; historical reads/replay still work.
- Authenticated browser create/replay/refresh/cancel/resume use actual Run
  service on a controlled repository SPI; other owner404 and missing CSRF403.
- Forged actor/backend/path, invalid hashes/revisions and expired deadline
  never capture/dispatch; exact route language returns avoid 405.
- Live-mode configuration against a2 is refused before SDK construction.

Run only new runtime/UI files plus affected existing language tests with
`--ds=provider_sync.tests.connection_test_settings`. Record the commands in
`.tmp/html-reports/host-implementation.md`; no default `.env` or user DB.

The QUALIFY launcher test in
`project_management/tests/test_project_full_stack_lifecycle.py` must falsify a
short SLE timeout without a real 600-second sleep. Use the real lifecycle engine
with its platform-operation SPI and a controlled clock: the owned service begins
graceful exit on the stop command and exits after 10 simulated seconds. Calling
the launcher's stop path must exit normally with zero terminate/kill calls;
leaving the generic 5-second timeout would fail that outcome. A second scenario
never exits gracefully and verifies a forced/terminated result is recorded as
abnormal, not a clean worker shutdown. Bind a safe maximum620-second grace to
the project service and explicitly pass it to the real SLE stop call; merely
setting a ServiceSpec field is not enough. Actual idle FS09 shutdown must also
produce the worker's normal-stop receipt and matching process exit evidence.

## QUALIFY: One Actual Joined Candidate

Exact launcher commands, owned manifest/vector, dynamic capture binding and
receipt boundary are in
[full-stack-qualification-packet](full-stack-qualification-packet.md).

Owned new scripts:
`scripts/validation/project_full_stack.py`,
`project_full_stack_settings.py`, `project_full_stack_fixture.py` and a small
`project_full_stack_base.py` only if needed by the new explicit vector format.
Reuse `project_summary_support` verification/environment/SDK guards and SLE.
Do not rewrite W5's old receipts, lifetime or exact-vector behavior.
New fixtures may compose the same Base `create_task_run_candidate` directly.

New external data root:
`D:/AIGC/scrum_dashboard_validation/full-stack/<uuid>/`.
Each run owns its catalog DB, archive, Base store, connection/stop handles,
logs and receipt. Only the launcher can initialize/migrate that DB.
Validate containment and owner markers; no code-repo runtime data.
The default interactive lifetime is 1800 seconds; each operation remains600.
The credential expires no later than lifetime plus shutdown margin.

The fixture creates a real project/stage through actual ORM/public APIs and
registers one exact synthetic Jira scenario. The provider fixture uses the
actual ProviderAccessService/adapter/capture pipeline and refuses nonregistered
requests. The Base executor checks the entire registered source vector,
project/stage/rule/principal and schema, allowing only the newly produced
capture UUID. It cannot accept arbitrary ticket text. It records actual
dispatch count. No preinserted accepted summary, draft or HTML.
The installed a2 SDK uses real HTTP loopback, retries=0/trust_env=false.
Guard external connects/DNS so neither child can call a real provider/model.

Use the existing W2 bootstrap pattern in
`scripts/validation/project_ui_fixture.py::seed`: `ApiForBugTrend.save_scope_config`
with `SavedScopeConfig`, `set_scope_provider_binding`, then actual
`build_project_api().create_project/add_stage`. Reuse the profile-registry-only
fixture AppConfig with explicit `METRICS_PROJECT_PROFILE_RECORDS_OVERRIDE`,
or the equivalent scoped registry SPI. Set its synthetic Jira endpoint/query
to exactly match the registered transport fixture. Keep default
DashboardScopeCatalog as the actual Stage reader so ordinary project/report
pages resolve the same source as the worker; W5's internal FixedCatalog alone
does not configure those default UI consumers.
Do not import W2's settings or invoke its root guard/seed CLI, which are bound
to the old W2 data directory. The new settings supply their own isolated paths,
owner marker and unique session/CSRF/language cookie names. The profile fixture
AppConfig starts no thread/service. If SLE merges the launcher's environment,
sanitize that dedicated launcher process environment before child creation
using the existing child-environment allowlist; normal workstation/global
environment and other application processes are not changed.

The launcher provides safe status/URL plus a local stop command; synthetic
browser login credentials are local test credentials, not Jira/model tokens.
Its result never prints the Base signed service token.
Run an actual browser flow on the stable candidate:

1. Stage -> Run -> durable queued/capturing/analyzing -> produced draft.
2. Save English plus Unicode notes; switch UI language without changing data.
3. Download exact original HTML; copy HTML/plain in a real click and verify a
   dedicated synthetic paste sink. Record actual permission failure separately.
4. Explicitly confirm finalization; verify six Git files and download bytes.
5. Second unchanged run -> new saved draft, same accepted summary, unchanged
   Base dispatch count. Refresh shows original run-produced draft revision.
6. Gracefully stop/restart the application with the same owned DB/archive/
   Base store; original report remains readable and no automatic new dispatch.
7. Stop both owned services and confirm their SLE process identities exited.

Do not rerun this entire flow for a docs-only change. A source correction
invalidates only dependent results; retain earlier failures as evidence.
Actual Windows Outlook paste (blank draft, no recipients, no send) is FS10.
Unavailable UI control or a screenshot tool timeout is reported precisely,
not accepted as proven fidelity. User-owned messages and old demos are untouched.
Current docs get the real startup/stop commands and limitations after results,
not a claim that synthetic flow enables live daily reporting.

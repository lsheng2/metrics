# Manual Full-Stack Delivery

Status: detailed design for the user's 2026-11-02 continuous E2E request.
Owner: Dashboard; task state only in tasks.md.
Depends on: existing W5.JOIN and [HTML authoring](html-report-authoring.md).
This packet does not declare remaining provider/delta/import/production
qualifications complete.

Workflow-only acceptance was completed on2026-11-03; exact outcomes and
remaining editor/live boundaries are in
[manual-workflow-delivery](manual-workflow-delivery.json). This does not mark
all FS08 authoring or FS10 Outlook cases complete.

2026-11-03 scope amendment: the user assigned WYSIWYG implementation to another
Agent. The current workflow closure covers steps1/2/4/5 below and the saved
HTML/download/explicit-finalization parts of step3. Direct editor behavior,
formatted-copy interaction and Outlook integration are deferred until that
delivery. See [editor handoff](rich-text-editor-handoff.md). Do not claim the
complete FS08 authoring journey or WYSIWYG acceptance from the reduced run.

## 1. Observable Exit

From the desktop project/stage page an authenticated owner can:

1. Start a bounded manual run and see its durable status.
2. Follow real capture -> stage Git -> installed a2 SDK -> actual Base HTTP
   -> accepted summary -> saved HTML draft.
3. Edit/save a meeting note, preview/copy/download and explicitly finalize.
4. Repeat an unchanged run without an additional Base dispatch.
5. Refresh/restart the application and inspect the original operation/report.

The first full-stack fixture uses explicit synthetic Jira responses and an
explicit synthetic Base executor. Project/Stage ORM, provider adapter, archive,
operation, SDK, HTTP, acceptance, reports and UI are the actual application.
No fake domain services, direct accepted-record insertion or canned HTML may
replace these components. Real provider/model qualification remains separately
gated; the UI must show the selected environment's execution mode.

Changed work requiring not-yet-implemented cumulative delta is pending with
`ANALYSIS_DELTA_REQUIRED`, never forced through repeated full-history AI calls.
That limitation remains visible until W4.DELTA/W5.INPUT is implemented.
The first E2E slice is first-baseline plus same-source reuse, not all daily
multi-day cases or an alternative to their required work.

FS08/09 own a new unique directory below
`D:/AIGC/scrum_dashboard_validation/full-stack/<run-id>/` containing a dedicated
catalog.sqlite3, separate archive root, Base fixture store and runtime/logs.
Never load/migrate the W2 demo DB, reuse W5 accepted data in place, or write under
the fixed Base source tree. Any needed source fixture is an explicit read-only
input; generate new operation/project IDs through actual app APIs.
Before and after the run verify the selected W2 DB/W5 receipt+artifact files by
hash without reading their confidential contents. If the user is actively editing
the W2 demo, do not misattribute that independent change; instead prove the new
fixture's configured paths cannot target it and record the concurrent observation.

## 2. Runtime Ownership

Use one explicitly started application runtime with one serial run worker
thread. Do not start threads at module import, on a GET, or in AppConfig.ready.
The new trusted local management command `project_serve` constructs runtime
services, starts the worker and runs Django with no autoreloader. Existing
`runserver`/legacy Dashboard startup does not silently enable new capture.

Service Lifecycle Engine owns the web process at the outer launcher boundary.
The app's runtime owns its worker thread and durable operation state; AI Base
owns its own execution/worker/store. Dashboard never stops a shared AI Base,
adopts a process solely by port or introduces another PID/keeper manager.
On shutdown reject new submissions, request cancellation of owned work, wait
within the original operation bounds, then retain any unresolved state.
No cycle, sleep or process wait is unbounded.

Application inspection, report browsing and stored operation status construct
only the read services. A configured-but-offline Base is not a reason to hide
already authorized reports or start another service.

## 3. Operation Contract

Frozen slots DTOs under `project_management/app/domain/run_contracts.py`:

```text
RunPolicy(timeout_seconds=600, max_analysis_items=10,
          max_observations_per_attempt=16, max_queued_operations=16)
RunRequest(command_id, expected_stage_hash, template, timezone)
RunOperation(operation_id, command_id, project_id, stage_id, actor_subject,
             stage_hash, policy_hash, created_at, deadline_at, capture_id,
             state, revision, cancel_requested, item_results,
             draft_id, draft_revision, draft_revision_hash, snapshot_hash,
             template_hash, error_code, execution_mode)
ItemRunResult(source_key_hash, state, attempt_id, accepted_summary_id, error_code)
```

Types: UUIDs for command/operation/capture/project/stage/draft/attempt; lower-case
SHA-256 for stage/policy; UTC ISO instants; finite positive integer limits.
The server derives IDs, actor, policy, endpoint/backend and deadlines; HTTP
accepts only RunRequest fields and may not inject backend URL, token, scope,
path, actor, fixture module or execution mode.

`operation_id=UUID5(stage_id, "run:"+command_id)`,
`capture_id=UUID5(operation_id, "capture")`. Exact request payload hash is persisted.
Repeated command/same payload returns the original operation even after its
deadline; another payload conflicts. It never creates another capture.
One nonterminal operation per stage; global queued bound is checked before new
acceptance. No arbitrary per-day run cap is reintroduced.

States: `queued`, `capturing`, `analyzing`, `draft_ready`, `partial`,
`cancel_requested`, `canceled`, `failed`, `interrupted`.
`draft_ready` means a saved draft, not finalized Git publication. `partial`
includes per-item pending reasons. Unknown AI outcome is retained in item state
and prevents another attempt/key for that source; it is not zero usage.

```text
ProjectRunService.submit(actor, project_id, stage_id, request) -> RunOperation
ProjectRunService.get(actor, project_id, stage_id, operation_id) -> RunOperation
ProjectRunService.list(actor, project_id, stage_id, *, limit=20) -> tuple[RunOperation,...]
ProjectRunService.cancel(actor, project_id, stage_id, operation_id, *,
                         expected_revision) -> RunOperation
ProjectRunService.resume(actor, project_id, stage_id, operation_id, *,
                         expected_revision) -> RunOperation
ProjectRunWorker.execute(actor, project_id, stage_id, operation_id) -> RunOperation
```

Exact assembly:

```text
ProjectRunService(project_api, archive, capture_service, analysis_service,
                  draft_service, backend_resolver, *,
                  policy=None, capture_limits=None, clock=None, notifier=None)
ProjectRunWorker(run_service)
ProjectRunRuntime(run_service, worker)
  .start() -> None
  .stop(timeout_seconds) -> RuntimeStopResult
  .notify(actor, project_id, stage_id, operation_id) -> None
```

`backend_resolver(actor,project_id,stage_id) -> AiBackendTarget` is a trusted
server dependency and never constructs scopes from posted arbitrary strings.
Archive methods create the bounded operation repository only after owner/path
verification, sharing existing repository root/locks. Worker execution uses the stored trusted
actor and exact scope after reauthorization, never a caller-provided subject.
`cancel` durably records intent before returning. `resume` keeps original
IDs/backend/deadline; it cannot extend the original policy or reset usage.

`RuntimeStopResult(stopped, active_operation_id, unresolved)` reports actual
worker exit. There is no forced thread-stop or shared Base process termination.
The serial worker consumes a bounded queue; queue notification is not execution
authority. Durable queued request survives failed notification and is explicitly
resumable with its original ID. A queued/running operation is never silently
forgotten to free capacity; current runtime occupancy plus durable pending
claims is used for new admission.

Before draft creation the worker persists its exact derived `ReportSelection`:
capture_id=operation.capture_id, purpose=standup, timezone from the original
validated request, parent_publication_id=null. baseline_publication_id is null
for first baseline; once the verified publication resolver exists, resolve the
exact latest allowed standup ID at this boundary and retain it without later
auto-refresh. Persist the selection, normalized TemplateSelection and payload
hash before calling draft_service.create with command_id=UUID5(operation_id,
"draft"). Until that resolver exists use an explicitly initial-baseline report,
not an invented comparison.
Record returned draft_id, revision, revision hash, snapshot hash and template
hash in the durable operation. Status links the produced revision, while a
separate Open latest draft action may follow later human edits. Human edits
must never rewrite which version the original run produced.

## 4. Persistence And Ordering

Extend existing stage runtime:

```text
runtime/operations/<operation-id>/
  request.json
  state.json
  events/<sequence>.json
runtime/operations/active.json
```

`request.json` is immutable; each transition has an immutable event with expected
revision before atomic state replacement. A torn state is reconstructed from
valid contiguous events. Source/capture/attempt/publication truth remains in
their existing archives, not copied into a new database.
All local mutations obey existing root-budget -> stage locks and admissions;
no lock is held across provider/model HTTP or template rendering.
The single process worker additionally owns an execution lock for each stage,
preventing a second explicitly started runtime from executing the same operation.
Use `runtime/operations/execution.lock` with nonblocking portalocker exclusive
lock; only the worker execution path acquires it, before claiming/running an
operation. Holding it across execution never implies holding root/stage mutation
locks. On contention leave the durable queued/interrupted state unchanged and
return RUN_BUSY; do not run a second worker or mark the operation failed.
The lock's kernel ownership is not inferred from a PID file. Status GET does not
acquire write claims or create directories.

Flow:

1. Submit revalidates owner, active stage hash, configured archive and runtime
   readiness; persist request and queued event before notifying the worker.
2. Worker claims the original operation; captures through
   `ProjectCaptureService.capture(AccessContext(...))`.
3. Persist capture receipt reference. Enumerate every member from committed
   membership; partial capture stays partial and missing details stay pending.
4. Prepare eligible items through SummaryAnalysisService using the original
   backend target/deadline. Persist each attempt reference before advancing.
5. Advance only queued/running or original-key-unknown observations with a
   bounded interval/count. No automatic new POST/key/store on a transport error.
6. On accepted/no_work use the existing source report query; on incomplete
   analysis retain pending. Save a draft through ReportDraftService with a
   deterministic command ID derived from the operation. Never auto-finalize.
7. Only after draft/state persistence release the active operation slot.

Cancellation during capture is checked at bounded item/page boundaries. Stop
accepting new material and seal available material using existing partial
finalization; an in-flight HTTP call keeps its timeout and is not declared
terminated before it returns. Cancellation before dispatch does not dispatch.
Exact capture propagation is an optional trusted callback:
`ProjectCaptureService.capture(context, *, cancel_requested=None)` passes it to
`ProviderAccessService.open_capture(context, *, online=False, cancel_requested=None)`.
The provider session's existing `authorize` callback first checks cancellation,
then retains its current `_writable_stage` check before every network page.
Cancellation raises the new fixed `AccessError("CAPTURE_CANCELED")`; no caller
can provide this callback over HTTP. Before archive preparation it simply
refuses; after preparation the existing capture error path seals retained
material as partial. This does not replace request/deadline/permission checks,
clear partial bytes or add a new polling thread. Legacy callers that omit the
callback retain their current behavior.
For an existing Base run, use installed `TaskRunClient.cancel(scope_key, run_id)`
and preserve its observed result/remote-stop uncertainty. Application cancel
does not imply a refund or backend process termination.

Add the explicit application boundary:

```text
SummaryAnalysisService.cancel(actor, project_id, stage_id, attempt_id, *,
                              backend) -> AnalysisCancellation
AnalysisCancellation(state, attempt_id, run_id, remote_stop, error_code)
CaptureArchiveService.request_analysis_cancel(actor, project_id, stage_id,
                                              attempt_id) -> AnalysisAttempt
CaptureArchiveService.read_analysis_observations(actor, project_id, stage_id,
                                                attempt_id) -> tuple[Mapping,...]
```

request_analysis_cancel persists `analysis_attempts/<attempt-id>/cancel.json`
with original attempt hash and timestamp under the existing stage/root locks.
An exact existing intent replays. Extend only this exact namespace path.
claim_analysis_dispatch and accept_analysis check the intent under the same
mutation locks, so a cancellation that wins prevents any later dispatch or
acceptance. An already accepted result remains historical; cancellation does not
undo it. Reserve control-write headroom so the normal16-observation limit cannot
prevent recording cancellation intent.

cancel reads the stored attempt, validates backend identity, and records intent
before network. Never-dispatched returns local canceled without SDK. If dispatched
with no validated remote runId, only get_by_client_key on the original key is
allowed; a missing/unknown response records remote_stop=unknown and never POSTs
a new run. With a known validated runId call SDK.cancel exactly once per
explicit cancellation observation. Validate the delivered RunCancelResponse
schema and its nested run snapshot through the existing contract identity checks;
retain cancelApplied and dispatch.remoteStop without assuming they are equal.
The a2 schema exists in the frozen pack and may be loaded without changing its
bytes. Advance sees persisted cancellation before attempting dispatch or accept.
Resume may reconcile the original key/run but never converts canceled intent
into a new attempt or returns a late summary as newly accepted.
Cancellation/reconciliation has a bounded HTTP timeout without extending the
original execution deadline; never starts new inference after it expires.

On app restart, a persisted running operation is displayed as interrupted until
an explicit resume can safely claim it. If capture has a complete committed
receipt, resume can proceed from that receipt and existing attempts. Partial/
uncertain capture requires explicit pending outcome rather than silent recapture.
After the original deadline only read/reconciliation/partial sealing is allowed;
do not accept a newly late summary through the old permit. Historical inspection
remains available. Full native crash recovery qualification is separate from a
normal restart/no-work demonstration.

## 5. UI, CLI And Composition

Stage route: `/projects/<project_id>/stages/<stage_id>/` shows scope, latest
capture/draft/report, operation state and an explicit Run form. Include links
from the existing stage table. It does not execute anything on GET.

POST `runs/`, `runs/<operation_id>/cancel/`, `runs/<operation_id>/resume/`;
GET `runs/<operation_id>/` is status/htmx polling only. All preserve verified
BasicAuth identity, CSRF, owner404 and private/no-store; same error conventions
as HTML routes. Polling never advances the worker or resubmits a command.
The run page does not use `hx-trigger="every 2s"` from the vendored htmx bundle;
it loads a scoped local status controller over
the same GET/HX-Request endpoint: one request at a time, a2-second interval and
10-second request bound, no POST or worker advance. Each response must be the
same operation's single status fragment; terminal fragments omit the next URL.
Leaving the page aborts pending reads. Stale replies cannot replace another
document. Errors preserve the last observed state with an unavailable marker
and ordinary refresh link. Data attributes, not a polling `hx-get` ancestor,
carry the status URL so Cancel and link clicks inside the fragment never poll.

CLI `project_run start/status/cancel/resume` calls the same services with the
existing trusted local_operator identity. Runtime endpoint binding is explicit,
not the browser's posted URL. A CLI without a running worker may inspect state
but refuses an asynchronous start unless an explicit local worker executes it.
CLI convenience is part of the existing W7 leaf, not necessary for claiming
that web-run state can be inspected.

New explicit composition module under `project_management` owns the runtime
registry/factories; configurable hooks come only from trusted server settings.
Production defaults remain disabled until deployment supplies archive identity,
provider authorization, AI target/credential and matching qualification.
The full-stack validation composition uses its dedicated settings and cannot
load `.env` or register synthetic handlers into the user's normal Dashboard.

Settings read only in composition (not at import):

| Setting | Default / boundary |
| --- | --- |
| `METRICS_PROJECT_RUN_ENABLED` | false; absence does not start a worker |
| `METRICS_PROJECT_AI_TARGET` | empty mapping; validated AiBackendTarget fields with fixed scope derived from project/stage at submit, no secret |
| `METRICS_PROJECT_AI_CREDENTIAL_REF` | empty; explicit target-bound credential identity |
| `METRICS_PROJECT_AI_TOKEN` | empty; only client factory reads it, never serialized to operation/archive/report/log |
| `METRICS_PROJECT_RUN_TIMEOUT_SECONDS` |600, at most the existing600-second analysis deadline; capture/analysis share this original total |
| `METRICS_PROJECT_RUN_MAX_ANALYSIS_ITEMS` |10, excess retained pending rather than omitted |
| `METRICS_PROJECT_RUN_MAX_QUEUED` |16, bounded installation admission without an arbitrary daily cap |

The current a2 AiTaskContract is synthetic-only. Production credentials cannot
upgrade that qualification. Live mode requires a separately delivered qualified
contract/backend and its existing authorization gates. Do not implement
`execution_mode=live` by labeling a synthetic result differently.
The validation runtime injects its own strongly scoped backend resolver and
client factory from an owned manifest, using real installed SDK and loopback
HTTP transport with retries=0/trust_env=false. No posted setting enables it.

`project_serve --host 127.0.0.1 --port <available-port>` refuses non-loopback and
autoreload. Command constructs runtime, starts it explicitly, runs Django's
application server and stops/join its owned worker in finally. A missing/
invalid runtime configuration prevents enabling Run while stored reports remain
accessible using the ordinary report-only server. No unrequested daemon/SSO.

## 6. Validation And Files

Serial implementation leaves are W7.E2E.CANCEL -> RUN -> HOST -> QUALIFY.
CANCEL's exact source/API/negative-test mapping is in
[manual-cancel-packet](manual-cancel-packet.md).
RUN's exact event journal, transition, source mapping and validation packet is
[manual-run-packet](manual-run-packet.md).
HOST and the actual joined QUALIFY flow use
[manual-host-packet](manual-host-packet.md).
CANCEL consumes the already installed a2 SDK and actual archive, independent
of UI; RUN consumes completed report APIs plus cancellation; HOST binds the
real Django/server worker and UI; QUALIFY uses only this matched candidate.
These are subsets of existing W7.RUN, not completion of W7.DEPLOY/PROTECTION
or the original whole feature. State only in tasks.md.

Exact owner families:
`app/domain/run_contracts.py`, `app/api/project_runs.py`,
`services/{project_runs,project_run_worker}.py`, `storage/project_operations.py`,
`runtime.py`, `management/commands/project_serve.py`,
`ui_web/{project_run_forms,facades/project_runs,views/project_run_views}.py`,
`ui_web/templates/projects/{stage,run}.html`, scoped URLs/locales.
`ProjectCaptureService` and SummaryAnalysisService gain cancellation only at
their existing public boundaries, with old callers remaining compatible.
The final implementation packet freezes exact settings and constructor types
against completed HTML service APIs before W7 code.

| ID / layer | Test file | Observable outcome |
| --- | --- | --- |
| FS01 L2 | `project_management/tests/test_project_runs.py` | identical submission gives one operation/capture; conflicting payload or owner never dispatches |
| FS02 L2 | same | complete capture + accepted result -> draft_ready with exact draft ID/revision/hash and persisted derived ReportSelection, zero final publication |
| FS03 L2 | same | unchanged repeat -> no new Base executor call, original accepted timestamp retained |
| FS04 L2 | same | partial member/detail/analysis -> honest partial/pending or refused register, never omitted members |
| FS05 L2 | `test_project_run_cancellation.py` | cancel queued/capturing/analyzing -> durable intent blocks dispatch/accept; no new run for unknown remote ID; nested cancel result identity/remoteStop validated, no automatic finalization |
| FS06 L2/L3 | `test_project_run_recovery.py` | interruption before/after capture receipt/attempt reference -> original IDs/deadline/draft revision, nonblocking execution-lock contention cannot launch a second worker |
| FS07 L2 | `ui_web/tests/test_project_run_views.py` | owner/CSRF/idempotency/GET-no-side-effect and refresh preserve operation status |
| FS08 L3 | explicit full-stack fixture | real browser POST -> capture/Git -> installed SDK/actual HTTP -> accepted -> editable draft -> HTML download/confirmed Git |
| FS09 L3 | same | second unchanged run, worker normal shutdown and restart -> original report bytes and no duplicate dispatch |
| FS10 L3 | HTML HT30 | copy into user-selected Outlook draft without sending, readable retained formatting |

First FS08 input is one bounded complete ticket, not an invented entire CRC
scope. Validate a second arbitrary project for ownership/isolation, without
duplicating the entire native matrix. Base fixture must register explicit
source/output vectors and actual application IDs; synthetic mode is enforced
and outbound real provider/model connections forbidden.

The interactive fixture must not depend on a hardcoded pre-captured run ID.
Its dedicated executor registration binds exact synthetic project/stage/rule/
principal and known fields/comment bodies/IDs. It may accept new UUID capture
IDs created by the real manual operation while verifying every source value
and input schema against the registered synthetic vector; its response binds
that supplied capture ID and original input identity. It must reject any
nonregistered evidence/project/stage or arbitrary real ticket text.
This is a test-only exact synthetic scenario, not a production summarizer, and
does not mutate the Base application/SDK or relax its authentication/Run schema.
A second unchanged manual operation is expected to avoid this executor entirely.

FS08 launcher runtime lifetime and each operation deadline are different.
Use a bounded configurable fixture lifetime default1800seconds for interactive
browser/Outlook validation, signed synthetic credentials expiring no later than
that lifetime plus a small shutdown margin. Every application run still shares
the original600second maximum; no operation or accepted attempt is renewed.
The launcher records the real expiry and stop handle, rejects unexpected owned
paths/ports, and shuts down its dedicated Base/app normally at the end of the
validation. It never changes the old W5 fixture's540second or prior run receipts
in place. A user-facing preview may be left running only as an explicitly
requested runtime with its own lifetime/ownership record and URL.

Capture, AI and draft services keep their existing unit/integration coverage.
Use narrow failures first, then one stable-candidate actual loopback/browser
run. Do not add a second per-attempt runner or redo the upstream Base suite.
Live qualification failure cannot be hidden by synthetic acceptance.

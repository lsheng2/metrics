# Manual Operation Implementation Packet

Scope: W7.E2E.RUN, consuming completed CANCEL and report services.
Authority: [manual-full-stack](manual-full-stack.md), section 3-4.
Status belongs only in tasks.md. This packet is not the full W7 deployment,
cumulative delta, live qualification or background scheduling implementation.

## Files And Existing Interfaces

| Owner file | Responsibility |
| --- | --- |
| `app/domain/run_contracts.py` | Frozen slots RunPolicy/RunRequest/RunOperation/ItemRunResult/RuntimeStopResult and fixed RunError |
| `app/domain/run_values.py` | Exact request, policy, persisted DTO and transition validation |
| `app/domain/run_admission_values.py` | Full admitted-record hash and initial operation validation |
| `app/domain/run_item_values.py` | Optional focused item-progress transition validation |
| `storage/project_operations.py` | Immutable requests/events/derived selection, atomic state projection, bounded reads and CAS |
| `services/project_operation_archive.py` | Internal archive owner/lock/admission bridge; no network |
| `services/capture_archive.py` | Add only that cohesive bridge mixin |
| `services/project_runs.py` | Public submit/get/list/cancel/resume and durable transition orchestration |
| `services/project_run_worker.py` | One operation's capture/analysis/draft execution |
| `services/project_run_reads.py` | Optional focused read/replay helpers if needed for file-size limits |
| `app/api/project_runs.py` | Public exports for the above application API |
| `tests/test_project_runs.py` | Admission, replay and actual-service outcomes |
| `tests/test_project_run_recovery.py` | CAS, interrupted state and execution-lock behavior |
| `tests/test_project_run_cancellation.py` | Operation-level consumer of the completed cancellation boundary |
| `tests/project_run_fixtures.py` | Reuse existing memory repository/provider fixtures; no fake domain services |

Paths in this table are relative to `project_management/`.
Do not edit UI, runtime server, Base SDK/source or global settings in RUN.
The next HOST leaf owns thread/HTTP composition.

The operation cancellation fence also narrowly extends
`services/summary_analysis.py`, `services/summary_journal.py` and their actual
test SPI signatures as specified below. Old callers omitting the trusted
callback retain their current behavior; the Base SDK/protocol is unchanged.

Existing providers and their precise methods:

- Project API: `get_project(actor, project_id)` returns project plus stages.
  Only the stage matching `stage_id` supplies the scope and definition hash.
- `CaptureArchiveService.initialize_stage(actor, project_id, stage_id)` creates
  the registered archive through its existing guarded owner; only explicit new
  submit may use this, never status/list or implicit import.
- `ProjectCaptureService.capture(AccessContext(...), cancel_requested=...)`
  returns the actual committed CaptureReceipt.
- `CaptureArchiveService.read_capture(...)` returns CaptureManifest. Its
  `membership.items` is the whole population, not only `snapshots`.
- `SummaryAnalysisService.prepare(..., backend=..., deadline_at=...)`,
  async `advance(...)` and async `cancel(...)` use the retained journal.
- `ReportDraftService.create(..., command_id=..., selection=..., template=...)`
  returns exact draft ID/revision/revision_hash/snapshot_hash and
  `template_definition.template_hash`. Reuse its deterministic create replay.
- Archive `_stage_for_read/_stage_for_write`, `_validate_root_before_lock`,
  `_locks`, `repository_factory.open` and `repository.verify_identity` are the
  existing same-module primitives for the new internal operation bridge.
  `_report_repository(write=True)` cannot be reused during capture because
  its active-capture refusal is intentional; do not weaken that report guard.
- `storage.paths.{controlled_path,inspect_components,read_bytes,write_bytes}`
  remain the containment/regular-file/atomic-write authority.
  `storage.admission.admit/GrowthEstimate` measure application-owned usage.
  `storage.locks.exclusive_lock` supplies the nonblocking portalocker lock.

The operation repository receives the actual `archive.config.limits` from the
archive bridge, not an infinite/default proxy. Every mutation (including event,
state, active marker and derived selection) admits its combined temporary and
retained growth under the same budget/stage locks. Tests with a deliberately
small configured quota must fail before any new operation/event files appear.
CaptureLimits are also frozen in the admitted request, so a new runtime's
larger settings cannot enlarge a resumed operation's original capture budget.

## Public API And Validation

Use the signatures and DTO fields in manual-full-stack section 3 verbatim.
Time values persisted on operations are UTC ISO strings; the injected clock
returns an aware datetime. RunRequest contains a real TemplateSelection and
an IANA timezone name. Validate exact UUID/SHA-256 inputs and reject bool-as-int.
Normalize template options through the existing renderer template definition
before request hashing. UI language never enters the request hash.

For this slice RunPolicy bounds are:
timeout 1..600 seconds; max_analysis_items 1..100 (default 10);
max_observations_per_attempt 1..16 (default 16);
max_queued_operations 1..128 (default 16).
These are explicit trusted configuration values, not browser fields.
Policy is serialized and hash-bound in the immutable request. Existing
operations retain their original policy when the runtime settings change.

RunError codes map only to fixed English messages:
`RUN_INVALID`, `RUN_NOT_FOUND`, `RUN_UNAVAILABLE`, `RUN_BUSY`,
`RUN_COMMAND_CONFLICT`, `RUN_REVISION_CONFLICT`, `RUN_SOURCE_CHANGED`,
`RUN_LIMIT`, `RUN_DEADLINE_EXPIRED`, `RUN_INTERRUPTED`,
`RUN_CAPTURE_UNCERTAIN`, `RUN_STORAGE_INVALID`, `RUN_STORAGE_UNAVAILABLE`.
Keep analysis/provider error codes in bounded item/error fields only after
their existing typed allowlists; never put exception text or paths in status.
Foreign owner is RUN_NOT_FOUND. Archived/source-drift new work is refused.
Historical status and recording cancellation remain owner-readable.

The immutable request stores:
schema version, operation/project/stage/actor identity, command ID, canonical
request hash, normalized request, original policy/hash, created/deadline times,
deterministic capture ID, trusted backend target and execution_mode=synthetic.
It contains no credential or token. Backend resolver is called for new
admission only. Exact command replay reads the persisted backend, deadlines
and result before new-runtime readiness, queue or expiry checks.
Reauthorization is still required for every replay.

One nonterminal operation per stage. `queued`, `capturing`, `analyzing`,
`cancel_requested` and `interrupted` occupy the stage slot.
`draft_ready`, `partial`, `canceled`, `failed` are terminal.
An unknown analysis remains durably pending in the existing analysis journal,
even if its operation is partial; a new operation must not replace that attempt.

## Journal And Lock Order

Keep the directory layout in manual-full-stack. Add
`runtime/operations/<operation-id>/draft-selection.json` for the immutable
derived report request; this is not another report or accepted-source authority.
All fields are validated before use. Max 1,000 operation directories per stage,
1,024 events per operation, and 1 MiB per request/event read. Limits refuse
explicitly; no truncation or automatic deletion.

An event contains schema version, operation ID, request hash, sequence,
previous event hash, UTC recorded time and the complete next RunOperation.
The next operation revision equals sequence. The initial queued event is 1;
the request binds its original state. Later events must follow the transition
rules and immutable identities below. State.json is only a projection of the
last valid contiguous event, including its event hash.

User idempotency and admitted execution identity are different hashes.
`request_hash` covers the normalized RunRequest. A separate `admission_hash`
covers the complete canonical immutable request record excluding that hash
field itself, including backend, policy, capture limits, actor/project/stage,
IDs and original times. Events bind both hashes. On read, recompute the full
hash, verify the record against the requested stage/operation path, derive
operation_id from stage/command and capture_id from operation, and validate the
backend scope and original created/deadline relationship. Event1 must equal the
request-derived queued operation; every later event passes the same legal
transition and immutable-field checks as a write. A well-typed altered record
or a hash-consistent illegal transition is not accepted as valid history.

Write request (exclusive), then initial event (exclusive), then state (atomic).
Transitions validate expected revision under the root-budget -> stage locks,
admit the combined event/state/active growth, append event, replace state, then
update the reconstructable stage active.json.
No external side effect happens before the initial queued event is durable.
If initial request survived alone, exact submit replay can finish event 1 from
that original request; it cannot allocate a new ID or deadline.

Reads reconstruct a missing/stale state.json from complete contiguous validated
events in memory without repairing disk. Malformed requests/events, missing
middle events or an invalid hash chain refuse RUN_STORAGE_INVALID.
A valid unprojected tail event is current truth, not a reason to repeat the
previous side effect. An active.json cache never overrides this event truth.
New admission scans bounded authoritative operation requests/events under the
same budget lock, including request-only pending acceptance.

Global pending admission scans only registered stage operation directories,
with a hard 10,000-directory scan ceiling and path/reparse checks. Count durable
nonterminal operations across stages, not merely the current process's queue.
If the bounded scan cannot establish capacity, refuse RUN_LIMIT.
No secret/source/artifact bodies are read for this scan and no counts from
another actor are returned to the caller.

The execution lock lives at `runtime/operations/execution.lock`.
Only explicit worker execution/recovery takes it, before root/stage mutation
locks, and holds it across that operation. Its directory was created by
accepted submit, not a GET. Kernel lock contention returns RUN_BUSY without
changing operation state. Code holding root/stage locks never waits for this
execution lock. HTTP, template rendering and observation sleeps hold neither
root nor stage mutation lock.

Allowed transitions:

```text
queued -> capturing | canceled | interrupted | failed
capturing -> analyzing | partial | cancel_requested | interrupted | failed
analyzing -> analyzing | draft_ready | partial | cancel_requested | interrupted | failed
cancel_requested -> canceled | interrupted | partial
interrupted -> queued | cancel_requested | canceled | partial | failed
terminal -> same exact replay only
```

Revision-only same-state transitions may retain an attempt result or prepared
draft selection. They must not clear cancel intent, change any immutable
identity, replace an accepted attempt, or rewrite a produced draft revision.
A worker that raced cancellation reloads state and honors the flag; it cannot
overwrite it with a stale whole-object update.

## Execution And Recovery

`ProjectRunWorker.execute(actor, project_id, stage_id, operation_id)` is
synchronous. The serial runtime calls it in its one worker thread; it may use
asyncio.run only around async analysis work outside Django's request event loop.
It reauthorizes the stored actor and stage and uses the stored policy/backend.
Clock checks occur at every external boundary using the original deadline.

1. Under the execution lock, claim queued/interrupted work using revision CAS.
   Inspect original capture by its deterministic ID. A complete committed
   capture is reused; do not recapture after a crash between receipt commit and
   operation projection. A new queued operation without any capture starts it.
2. Persist capturing before invoking the real capture service. Its callback
   reads only durable operation cancellation with the existing safe read path.
   A partial committed capture or an interrupted uncertain capture is an
   explicit partial/RUN_CAPTURE_UNCERTAIN outcome, not a silent recapture.
   Preserve and, where possible through finalize_partial, seal pending bytes.
3. Enumerate all committed members. Construct SourceChainKey using manifest
   source principal/rule and each member's provider/endpoint/stable ID.
   Missing details or incomplete capture produce pending entries, never closed
   tickets or omissions. Only a complete capture enters strict analysis.
4. Prepare at most max_analysis_items, retaining other members as pending.
   Persist each returned attempt reference before advance. A crash after
   prepare but before this event is recovered by the same deterministic
   prepare/journal identity, not a new key.
5. no_work retains the original accepted summary ID/time. Ready uses the
   original attempt/key; queued/running advances are capped by the original
   remaining observation count and deadline, with at most a 1-second interval.
   Unknown/rejected/unsupported cumulative delta becomes explicit pending;
   never full-history retry, automatic new key or changed backend.
6. Before draft creation persist exact ReportSelection and normalized template
   with their payload hash and UUID5(operation_id, "draft") command.
   Baseline remains explicitly initial/null in this first slice; no fabricated
   day comparison. Source selection uses the actual capture ID.
7. Create the draft through the actual report service outside mutation locks.
   Persist the returned original draft/revision/hashes; do not finalize it.
   Report creation errors retain item/capture/attempt progress and a safe
   partial outcome, not success or disappearance.

`cancel` CAS-writes operation intent first. For any retained nonaccepted
attempt, it records archive.request_analysis_cancel before returning; no model
request or acceptance is allowed as a consequence of the Web cancel POST.
Remote cancellation is reconciled by the executing/resumed worker using the
completed cancellation service. In-flight capture/analysis can take its
existing bounded timeout to return. Until then status remains cancel_requested,
not a false claim of thread or remote process termination.

There is an explicit atomic fence for attempts not yet known to the operation.
Add optional trusted `cancel_requested: Callable[[], bool] | None = None` to
SummaryAnalysisService.prepare/advance and the archive's prepare_analysis,
claim_analysis_dispatch and accept_analysis methods. The service passes it
through; the archive checks it inside its existing root/stage mutation lock
before new preparation, dispatch claim or acceptance. Existing acceptance
replay remains historical and is not undone. The callback reads the original
operation's validated cancellation flag without taking a write lock or doing
provider/model I/O. Run and analysis services must share the same archive
authority/locks, as in their existing composition.

The worker reloads cancellation before each member and passes that callback
to preparation and advance. A check only before calling prepare is insufficient:
the Web cancel can win after that check. If prepare won first, preserve its
attempt reference even if cancellation wins before the operation records it;
then reconcile that original attempt through SummaryAnalysisService.cancel.
No newly prepared attempt is dispatched after the durable operation cancel wins.
Do not hold root/stage locks across SDK calls or add a second dispatch lock/PID
manager. Preserve the full remote cancellation observation and unknown outcome;
local canceled state is not remote-stop confirmation.

Reconciliation is bounded by one 10-second worker control window, without
renewing any inference deadline. Pass the remaining budget to the cancellation
service through an optional trusted `timeout_seconds` argument, bounded to
0 < value <= 10; old callers retain the existing 10-second default.
If the window is exhausted, keep remaining attempts explicitly unknown/pending.
No automatic replacement attempts or success/refund claim follows.

Resume merges per-member progress by source_key_hash in original membership
order. A bound attempt ID cannot be cleared/replaced; an accepted summary ID
cannot be cleared/replaced; accepted/no_work items cannot regress to pending.
Unexpected/duplicate member state is refusal, not discarded history.
Pending new members may be initialized once, but rereading the same manifest
never resets observations or accepted items. Enforce these rules in the shared
transition validator as well as the worker. Unknown outcomes remain explicit
pending; do not keep dispatching new items after an unresolved exposure in this
single-backend slice.

Queued cancellation with no active execution becomes canceled directly.
Active cancellation is never undone by resume. Deadline expiry permits only
read/reconciliation/partial sealing, never a new inference or late acceptance.
Resume preserves IDs/policy/deadline/backend and validates expected_revision;
terminal operations replay without notification. Otherwise it durably requests
the original work and notifies the runtime. A failed notifier leaves queued
state for later explicit resume, not a failed/forgotten operation.

HOST's explicit runtime start may inspect stale nonterminal operations under
nonblocking execution locks and mark abandoned capturing/analyzing work
interrupted. It does not automatically reexecute them. Ordinary GET/list never
acquires execution claims, starts threads or writes recovery state.

## Tests And Cost

| Case / file | Setup, action and required result |
| --- | --- |
| FS01 / test_project_runs | Same command twice returns same request/deadline/capture; mismatched payload/foreign owner have zero capture or SDK side effects |
| FS01b / same | Separate runtimes/stages share durable queue limit; request-only crash counts pending; stale active cache cannot free occupied stage |
| FS01c / same | Actual configured archive quota rejects new request/transition without partial writes; no infinite proxy; offline new submit has no archive initialization |
| FS02 / same | Actual capture/analysis/report services on memory repository SPI yield exact saved draft identity and zero publications |
| FS03 / same | Second unchanged capture uses original accepted summary and creates a new draft without an additional SDK POST |
| FS04 / same | Partial capture, missing detail, analysis limit, unknown and delta-required retain the whole population with explicit pending |
| FS05 / test_project_run_cancellation | Queued and active cancellation persist flag; race with a result cannot clear intent or newly accept; archived owner may still cancel |
| FS05b / same | Cancel between two members, and after worker's initial check but before prepare/claim, produces no later attempt/dispatch; retained remote attempt invokes real cancellation service with bounded control budget |
| FS06a / test_project_run_recovery | Missing state after valid event recovers in memory with no write; changed/gapped event, altered backend/capture budget/actor and hash-consistent illegal transition refuse; stale revision cannot transition |
| FS06b / same | Complete capture before lost receipt transition resumes original capture/attempt/draft; original deadline remains unchanged |
| FS06e / same | Resume after one accepted member preserves its exact attempt/summary and processes only remaining members; transition cannot clear/replace accepted progress |
| FS06c / same | Real nonblocking execution lock prevents second worker, GET leaves it and all files unchanged |
| FS06d / same | Interrupted uncertain capture does not recapture; failed notification remains visible/resumable; late result cannot accept |

Begin with the missing public RunRequest/ProjectRunService behavior RED.
Existing report/source tests are reusable evidence, not all rerun per fix.
Run the three new files using the explicit synthetic settings:

```powershell
.\.venv\Scripts\python.exe -m pytest project_management/tests/test_project_runs.py project_management/tests/test_project_run_recovery.py project_management/tests/test_project_run_cancellation.py -q --ds=provider_sync.tests.connection_test_settings
```

Use actual services plus low-level repository/provider/HTTP SPIs for fast branch
tests; one real filesystem lock case is not a full native process matrix.
The actual ORM+Git+HTTP joined run is FS08/09 in the next qualification leaf.
Record exact RED/GREEN commands, case scope, timings and unchanged-source
evidence in `.tmp/html-reports/run-implementation.md`, then request a scoped
independent review before HOST consumes the service.

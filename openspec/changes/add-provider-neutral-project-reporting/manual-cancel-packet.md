# Manual Run Cancellation Packet

Scope: W7.E2E.CANCEL only, refining section 4 of
[manual-full-stack](manual-full-stack.md). State remains solely in tasks.md.
The parent design already passed its scoped readiness review; this appendix
maps the existing producer APIs and pins bounded cancellation observations.
No new public run endpoint, worker, live backend or scheduler belongs here.

## Source And Ownership

Current implementations, not the older graph generation, are the source:

| File | Change |
| --- | --- |
| `project_management/app/domain/summary_contracts.py` | Add `AnalysisAttempt.cancel_requested: bool = False`, frozen slots `AnalysisCancellation(state, attempt_id, run_id, remote_stop, error_code=None)`, safe `ANALYSIS_CANCELED` error |
| `project_management/app/api/summary_analysis.py` | Export the cancellation DTO with the existing public service |
| `project_management/services/summary_journal_reads.py` | Validate/read the optional immutable cancel intent and expose bounded original observations |
| `project_management/services/summary_journal.py` | Persist cancellation through the existing append owner; serialize dispatch/accept/cancel decisions under existing locks |
| `project_management/services/summary_analysis.py` | Add async cancel, inspect durable intent before advance, preserve existing request/key/deadline |
| `project_management/services/summary_cancellation.py` | Optional focused helper for cancellation orchestration; no independent journal or client |
| `project_management/out/ai_task_contract.py` | Load existing hash-verified `RunCancelResponse`; validate nested snapshot and exact observed run ID |
| `project_management/storage/repository.py` | Permit only `analysis_attempts/<uuid>/cancel.json` in the existing namespace |
| `project_management/services/capture.py` | Thread the trusted optional cancellation callback |
| `provider_sync/app/api/access.py` | Invoke cancellation before opening a connection and in the existing per-page authorizer |
| `provider_sync/app/api/access_contracts.py` | Fixed English `CAPTURE_CANCELED` error |
| `project_management/tests/test_analysis_cancellation.py` | Service/SDK and journal cancellation behaviors |
| `project_management/tests/test_capture_cancellation.py` | Before-connection and between-pages capture behavior |
| Adjacent summary/capture fixture files | Update only actual SPI contracts consumed by the new behavior |

Use existing `SummaryScenario`, installed SDK with explicit MockTransport, and
the report tests' memory repository SPI where suitable. Do not mock the domain
service or replace real owner/acceptance guards. One actual temporary-Git case
proves the new namespace/readback; the already verified Git implementation
does not need a new repository for every cancellation branch.

## Exact Contract

```python
async def cancel(self, actor, project_id, stage_id, attempt_id, *, backend):
    ...

def request_analysis_cancel(self, actor, project_id, stage_id, attempt_id):
    ...

def read_analysis_observations(self, actor, project_id, stage_id, attempt_id):
    ...

def record_analysis_observation(self, actor, project_id, stage_id, attempt_id,
                                observation, *, cancellation=False):
    ...

def validate_cancel(self, attempt, value, *, expected_run_id):
    ...

def capture(self, context, *, cancel_requested=None):
    ...

def open_capture(self, context, *, online=False, cancel_requested=None):
    ...
```

`cancel` returns `AnalysisCancellation`; journal cancel returns the validated
`AnalysisAttempt`; observation reads return detached `tuple[Mapping, ...]`.
`validate_cancel` returns the validated nested snapshot or raises the existing
safe analysis error. `expected_run_id` comes only from an identity-validated
stored observation or original-key lookup, never from caller input.
Source IDs, backend, logical/input hash, grant, limits and original deadline
remain governed by the current `validate_snapshot` checks.

The immutable cancel envelope follows the existing analysis-event format:
`kind=cancel`, original `attempt_id`, payload containing the original intent
hash and UTC request timestamp. Its UUID5 record identity uses the existing
attempt ID and literal `cancel`. Validate both envelope identity and intent
hash on every read; a missing file means no intent, malformed data is refusal.
Older intent records omit the new boolean and decode as false; never rewrite
an existing intent to introduce the field. A valid cancel file sets it true.

Cancellation is a control observation: owner-checked read authorization plus
the existing root/stage mutation locks may record it even when the project
became archived. It does not grant permission to capture, dispatch or accept.
Quota/write failure is reported, not silently treated as durable cancellation.
No filesystem free-space queries are added.

Normal observations remain capped at 16. One additional observation slot is
reserved exclusively for a cancellation response, independent of the immutable
cancel-intent record. The ordinary recorder cannot consume slot 17.
The cancellation recorder requires a valid intent. Once that reserved slot is
used, cancel returns its retained outcome without new HTTP. Earlier unknown
observations can be reconciled by explicit cancellation while room remains.
This bounds control traffic without resetting the inference budget. Preserve
the full response including `cancelApplied` and nested `dispatch.remoteStop`.
There is no claim of unlimited reconciliation or confirmed remote termination.

Under the same journal locks:

1. Existing exact acceptance replays as historical acceptance.
2. A cancellation intent prevents a new dispatch or acceptance.
3. If acceptance won first, cancellation does not remove it.
4. Existing dispatch means possible remote execution, not a safe new POST.

`advance` returns canceled without constructing a client if it observes local
intent. A race after that read is still fenced by dispatch/accept mutation
guards; a cancellation error maps to canceled without accepting late content.
The original POST claim defines the local dispatch decision; cancellation
cannot retroactively declare a concurrently claimed HTTP request never sent.

## Network Ordering

Validate actor/attempt/backend, persist cancel intent, then:

1. Never dispatched: return canceled, no run ID, remote_stop=not_requested,
   zero SDK construction/requests.
2. Dispatched with a validated stored run: use that original run ID.
3. Dispatched without a validated run: GET only the original client key.
   Missing/unknown lookup returns cancel_requested with remote_stop=unknown;
   it cannot submit, switch stores or create another key.
4. With the validated run ID, call installed `TaskRunClient.cancel` at most
   once per explicit observation. Validate the envelope, nested snapshot and
   run ID before recording/returning it.
5. `cancelApplied=false` and terminal success do not authorize acceptance
   after our local intent. Report local canceled with the actual remote-stop
   value; preserve remote terminal state in the observation.

Use a maximum 10-second control-call budget per cancel invocation. This budget
also applies after the original execution deadline because cancellation and
read reconciliation do not start inference. It never changes `deadlineAt`.
Transport errors retain only safe typed codes and remote_stop=unknown. Invalid
identity/schema responses are refused and cannot become a trusted run ID.
No lock spans an SDK call.

Capture checks the callback before provider setup, then before every page
through the existing authorizer, retaining the normal owner/deadline checks.
A callback returning true raises `AccessError("CAPTURE_CANCELED")`.
Before archive prepare this leaves no capture; afterwards the existing partial
finalization preserves captured pages/members. The current in-flight HTTP call
is bounded by its existing timeout and is not forcibly killed.

## Test Matrix And Execution

| Case | Initial state and action | Required observable outcome |
| --- | --- | --- |
| CN01 | Prepared, no dispatch; cancel then advance | Persisted intent; no SDK call/acceptance |
| CN02 | Dispatch claimed, no run observation; lookup missing | Original-key GET only; unknown remote stop, no POST |
| CN03 | Valid running observation; cancel response | Exact run cancel; retained cancelApplied and remoteStop |
| CN04 | Wrong backend, wrong nested run/store/scope/hash, malformed envelope | Safe refusal; no trusted outcome or acceptance |
| CN05 | Cancel wins before claim/accept; accepted wins before cancel | New work fenced; original accepted record remains readable |
| CN06 | 16 normal observations then cancel; further ordinary observation | Intent plus reserved control outcome succeeds; ordinary overflow refused |
| CN07 | Reconstruct services after cancel, retry original ID | Original intent/IDs/deadline, no replacement POST |
| CN08 | Other owner and damaged cancel-intent hash | Refusal, no journal growth or HTTP |
| CN09 | Callback true before connection; then true after first comments page | Zero first-case requests; second retains A/B and marks partial without fetching C |
| CN10 | Actual temporary Git persist/reopen cancel namespace | Exact original cancel bytes and request survive; unsafe sibling path refused |

First RED is CN01 through the missing public `cancel` method.
Run scoped commands from Dashboard using:

```powershell
.\.venv\Scripts\python.exe -m pytest project_management/tests/test_analysis_cancellation.py -q --ds=provider_sync.tests.connection_test_settings
.\.venv\Scripts\python.exe -m pytest project_management/tests/test_capture_cancellation.py -q --ds=provider_sync.tests.connection_test_settings
.\.venv\Scripts\python.exe -m pytest project_management/tests/test_summary_analysis.py project_management/tests/test_summary_acceptance.py -q --ds=provider_sync.tests.connection_test_settings
```

The implementer records exact test nodes, RED/GREEN output, timings, files and
any unproved native boundary in `.tmp/html-reports/cancel-implementation.md`.
Run changed-file size/whitespace checks. Do not run the complete repository or
Base test suites. Independent review checks this boundary before W7.E2E.RUN
consumes it. Browser and actual Base HTTP integration remain W7.E2E.QUALIFY.

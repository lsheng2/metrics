---
id: MDB2-WIN-RETENTION-20261126
title: Retained-window scheduler calibration repair
status: accepted
owner: Dashboard validation
created: 2026-11-26
last_reviewed: 2026-11-26
docs_impact: operations
human_docs: [openspec/docs/current-baseline/performance-kpis.md, docs/development/reporting-delivery.md]
implemented_by: []
tests: []
supersedes: [MDB2-WIN-LOW-EVENT-20261126]
superseded_by: []
---

# Scheduler Retention Repair

**Goal:** obtain trustworthy native calibration within the existing small
collector envelope, then resume the actual Windows performance closure.
**Architecture:** keep the ETW profile and decoder; repair the ordinary
workload ordering and scope of state reconstruction in a separately versioned
private method. The owner's ten-capture amendment versions only the bounded
collector authorization controller. No new process manager or production interface.
**Tech stack:** Windows, selected dev9 Python, existing TraceEvent 3.2.8 /
.NET 10.0.15 decoder, current SLE and measurement guard.
**Execution:** use systematic debugging, TDD and independent review. The
existing MDB2 `tasks.md` is the sole ledger; keep the 28-node DAG.
Profile source: `repo-local`; agent routing: `multiagent-configured`.
The applicable profile is `.github/skills/lsheng2-dag-based-planning/templates/project-profile.md`.

The owner's 2026-11-26 continued-closure authorization permits evidence-led
method/KPI decisions. This accepted direction still requires independent
plan/validation and implementation review before a new native run. No native
success or final performance acceptance is asserted here.

## Evidence And Alternatives

Baseline: Dashboard `ef42b2cb8fbb5a606ccd78ca3310a1f3b978e831`, AIB
`1a6ac981b67f148bbaaed6750e6874896ada0bcc`, both clean before this amendment.
Use the admitted dev9 wheel and unchanged r3 policy from
[PERF-SPEC-001](../../docs/current-baseline/performance-kpis.md).

Original calibration `le1126-cal1` stays `CALIBRATION_REFUSED`.
Private evidence under `D:/AIGC/d9-1122/close-1126/`:

- `retained-calibration-inspection.json`: a nonqualifying 1,000,000-event
  sensitivity replay still fails on an unrelated timestamp tie and missing
  incoming evidence for the synthetic witness.
- `raw-scheduler-survey/survey-r2.json`: direct raw ETL parsing, with no ETLX
  conversion, counts 529,161 events, zero reported loss and 137 selected rows.
  It also lacks the synthetic witness's scheduler/lifetime events.
- The witness interval is approximately 0.27-0.33 s after recorder readiness;
  the earliest retained CSwitch is around 2.61 s. Many active CPU ranges begin
  7-14.3 s after readiness and end around 17.1 s. This interval is not retained.
- The pinned collector uses circular memory. Microsoft's logging-mode
  reference documents eviction of oldest events in that mode; the downloaded
  source is `logging-mode-constants.html`. This supports a retention hypothesis,
  not attribution of the separate application delay or a particular evicting event.
- `scheduler.py` currently rejects any target QPC tie anywhere in the capture,
  even before the last incoming anchor of a later requested interval. Its
  refusal is broader than the interval being classified.
- Follow-up `raw-scheduler-survey/survey-r3.json` found zero differences between
  all 327,054 CSwitch payload NewThreadID values and SDK-decoded IDs. The real
  trace includes same-thread Running events, Ready notifications before a
  switch-out, and outgoing Standby during CPU migration. These are additional
  supported-state questions, not a parser identity defect or product cause.

| Alternative | Decision |
| --- | --- |
| Raise only the event limit | Insufficient: does not restore missing witness transitions |
| Enlarge buffers or add more event families/flushes | Rejected for this slice; changes privileged method and increases cost |
| Late witness plus interval-scoped replay | Selected; preserve the collector, decoder, raw evidence and safety limits |

## Authority And Limits

The new ordinary method is `scheduler-retention-v2`; its ETW/receipt protocol
and decoded format remain `scheduler-observation-v1`. The prospective
authorization revision is `scheduler-grant-ten-v1`. Store these identities explicitly.
Old v1 receipts are not v2 calibration: do not rewrite their method, verdict,
helper hashes or source identity.

The retained-window revision changes the calibration all-decoded-event cost limit:
250,000 -> 1,000,000. The observed 529,161-event retained trace cost 8,151,035
ETL bytes, 66,575,760 derived bytes and about 4.98 s for the bounded decoder.
The new count cap matches the existing decoder ceiling and later diagnostic
cap; independent byte/time/loss/coverage gates remain mandatory. Count all
events in the retained ETL, including metadata, not just selected target rows.
This limit is not a count of all events generated before circular eviction.

Unchanged bounds: 128 MiB actual buffer pool; 512 MiB raw plus temporary
artifacts; 512 MiB derived artifacts; 50,000 selected rows; 128 markers;
30 s active calibration; at most 40 measured pages; 90 s recording;
360 s collector; 120 s whole decode. Preserve the 40 ms deliberate wait and
1,000 ms native wait timeout. Product P1-P4, auth, real-leak checks and
production stop budgets are unchanged.

The historical session is
`a905e77e-ebb5-4307-a41f-11549903dfb6`, helper PID 103804,
original expiry `2026-11-26T22:02:52.4175985+08:00`.
Its actual allowance is two captures, one already consumed. The outer helper
implementation's possible six-capture ceiling is not this session's allowance.
It cannot admit another calibration: both `circular-session.ps1` and
`Assert-LowEventCaptureRequest` require calibration at count zero. The earlier
count 1 admission plan was incorrect; the old failure/history remain unchanged.

The 18:45 UAC request returned user-canceled; its withdrawn launch is not a grant.
A new eight-hour/two-capture session became READY at 19:11:
`212e4042-2d56-44c7-b874-91e123ad9567`, PID 105020, original expiry
`2026-11-27T03:11:02.4615447+08:00`, count zero, no active capture.
The owner then explicitly authorized a ceiling of ten captures. The existing
two-capture session remains unchanged; it is not the ten-capture grant.

Create a reviewed versioned controller under private `collector10/`. Keep the
eight-hour expiry, 8 GiB session ETL bound, exact command allowlist and all
per-run bounds. Only the prospective count ceiling becomes ten; no automatic
retry or unbounded renewal. Preserve the original seven privileged files and
all old receipts. New copied source hashes belong to the new grant revision.
An independent collector-only review must bind the exact new source scope
before its launcher requests UAC. Final ordinary-method review/freeze follows
actual grant admission. This is not permission to alter a running helper.

Until the reviewed ten-capture launch is READY, keep `policy.json` session null
and refuse native method freeze/collection before apps start. Bind its actual
directory, PID/incarnation, original expiry, launch-ready/scope and source hashes.
Admit calibration only with READY/no active capture, count 0/max 10, zero ETL
bytes and empty history. Calibration remains first; diagnostics may consume
counts 1 through 9 only with matching proof and fresh per-run owner-go receipts.
The owner-go is one `diagnostic-go-<run_name>.json` artifact with kind
`scheduler-diagnostic-owner-go`; "run-go" is not a second approval mechanism.
At count 10, refuse before creating resources. The old two/six limits must not
remain hidden in PowerShell or Python consumers, and must not be used as a fallback.
Never reset a count, extend expiry or disguise calibration as diagnostic.
A subsequent diagnostic also needs valid method proof, separate approval and
remaining capacity; a calibration pass alone does not authorize its execution.
Live admission checks current readiness, incarnation and expiry before launch.
Offline proof instead validates the frozen grant and recorded admission from
that capture. It must not query current remaining capacity or compare expiry
with replay time: successful capture consumes quota and replay may occur later.

## Contracts And Consumers

| ID | Producer -> Consumer | Required Proof / Refusal |
| --- | --- | --- |
| RET-IDENTITY | New freeze/producer -> replay and operator report | Current source/input/dev9/helper hashes, reviewed new grant scope/revision and ordinary method; refuse old/wrong/changed identities |
| RET-WINDOW | Raw decoder -> interval selector -> versioned state model | Audit all target identities/clocks first; classify only necessary observations; retain full raw evidence and selection bounds |
| RET-WITNESS | Late ordinary native thread + real CSS route -> calibration proof | Actual start/stop lifetime, wait/ready/run, marker/clock/request join; no inferred Sleep duration or metadata-only coverage |
| RET-BUDGET | Fixed v2 policy -> producer/decoder/replay | Prospective event cap and separately authorized ten-capture grant; all loss/byte/time/pool/ownership/cleanup gates stay fail-closed |
| RET-CLAIM | Complete raw/native gates -> dated report | Calibration is never P1-P4 acceptance; original failure remains; no phase promotion from collection success |

These are local slices of existing `PERF-IDENTITY`, `PERF-RECIPE`,
`PERF-INTERVAL`, `PERF-WINDOW`, `PERF-CLEANUP` and `PERF-CLAIM`, not new
application contracts or DAG nodes. Code/doc propagation applies to private
tools, receipt consumers and operator guidance. Public API, Django settings,
deployment, UI and data-schema propagation are not applicable because those
surfaces do not change; AI loaders and product architecture boundaries remain unchanged.

Consumer census: validation scripts, private output/receipts, ordinary workload
adapters, collector request boundary, decoder, current operator docs and test
doubles apply. Production API/UI/storage, migrations, live providers/models,
Linux and other Apps do not change. Public KPI qualification remains an
unchanged downstream consumer and must not accept these diagnostic receipts.

## Implementation Slice

Private root: `D:/AIGC/d9-1122/retention-v2-1126/`.
Reuse base modules from `D:/AIGC/d9-1122/low-event-1126/` without editing them.
The existing native decoder can write a fresh uniquely named output under
its admitted `decoder/artifacts/` root; bind that path/hash in v2 evidence.
Parent is the only repository writer and privileged/app executor. One
implementation agent may own the disjoint private producer/admission/decoder
files and their tests while parent owns interval/witness/proof files. No shared
file writes or live runs are parallel; all agents stop before a measurement window.

| File / Interface | Responsibility |
| --- | --- |
| `policy.json` | Fixed method/cost bounds; unresolved grant refuses; verified fresh grant binds original expiry and count-zero allowance |
| `collector10/`, `session_control_v2.py` | Versioned ten-capture control plane and matching ordinary consumer; original controllers remain immutable |
| `retention_interval.py::partition(decoded, start_qpc, end_qpc, pid, tid)` | Full target audit, minimal retained-window selection, documented strict state model |
| `witness_v2.py::validate_witness(...)` | Existing marker/lifetime/wait/release checks with the v2 interval consumer |
| `kernel_adapter_v2.py::RetentionCapture` | Existing three-arm workload with late witness/CSS/save order |
| `source_freeze_v2.py` | New source/input/helper/policy identity, shared helper hash preservation |
| `run_retention.py` | One admitted calibration; existing SLE, measurement guard, output witness and normal cleanup |
| `decode_retention.py` | Existing pinned decoder under the unchanged 120 s whole-process deadline |
| `proof_v2.py` | Source-bound collection, decoder, clocks, scopes, cleanup and native semantic replay; fresh output only |
| `test_interval_v2.py`, `test_late_witness.py`, `test_contract_v2.py`, `test_proof_v2.py` | Behavior/negative fixtures and owned boundary failures |

### 1. Interval Repair

First demonstrate the current incorrect refusal with a hand-checked sequence:

```python
from test_scheduler import fixture, ready, switch

data = fixture()
early_ready = ready(60)
early_ready["event_index"] = 61
data["scheduler_rows"] = [
    switch(50, incoming=True),
    switch(60), early_ready,
    switch(90, incoming=True),
    switch(110), ready(140),
    switch(150, incoming=True, cpu=2),
    switch(210, cpu=2),
]
result = partition(data, start_qpc=100, end_qpc=200, pid=20, tid=21)
assert result["ticks"] == {"running": 60, "ready": 10, "blocked": 30}
```

The old consumer fails this positive case. New behavior must first validate
the full target inventory, lifetime/incarnation, event uniqueness, CPU fields
and relative/QPC agreement. Select the latest genuine incoming transition at or
before the span and the first CSwitch closing observation at or after it. Include all
events tied with either boundary. A tie at the anchor, inside the necessary
range or at its close still refuses classification. Do not sort a tie into
invented causality, adjust timestamps, or assign unknown states to waiting.
Record the anchor/close and excluded prefix/suffix counts beside the result.
The original unfiltered decoder output stays unchanged.

Negative cases include relevant ties, a contradictory self-event, missing incoming/closing
or wakeup, wrong CPU, duplicate indices, changed/reused identity, clock jump,
invalid lifetime, loss/truncation/omission and unknown state 7/9 within the
classified range. Identity/clock corruption outside the selected range must
also refuse; interval scoping must not hide global provenance defects.

The native-sequence follow-up refines the model before any new capture:

| Observation | Permitted Interpretation | Required Refusal |
| --- | --- | --- |
| Ready notification while already running | Keep CPU occupancy until an actual switch-out | Never use that earlier notification as a wakeup for a subsequent Wait |
| Ready notification while already ready | Keep the existing ready interval; do not reset its start | Invalid identity, CPU field or tied chronology still refuses |
| Outgoing Ready=1 | Thread is runnable but not executing after switch-out | Require the matching typed name; do not apply this to unknown 7/9 |
| Outgoing Standby=3 | Enter a pending standby dispatch, not an immediately accepted ready slice | Require a Ready notification since the last genuine incoming or after switch-out, then a matching genuine incoming without contradictory CPU/identity evidence |
| Outgoing Wait=5 | Blocked until a subsequent target Ready notification | Missing wakeup before genuine incoming refuses |
| Same-thread Running=2 CSwitch | Zero-duration observation only when already running on the same CPU | Cannot supply the incoming anchor, wake a ready/blocked thread or silently migrate CPU |
| Closing evidence | Require the first genuine target CSwitch at/after the interval end | A Ready-only or self-only suffix is insufficient; no weaker closing mode |

Known-state meanings are grounded in the downloaded Microsoft
`dotnet-threadstate.html` and pinned `KernelTraceEventParser-3.2.8.cs`.
The reference `ThreadTimeComputer-3.2.8.cs` records Ready notifications
independently of switch-out and notes preemption limitations. Its full
stack-based display is not a drop-in strict stackless partitioner; this slice
does not enable stack collection to obtain that display.
Do not coerce unsupported outgoing states into Ready or Wait. Add the exact
native sequence as a regression plus wrong-CPU, missing-wakeup, fake-anchor,
Ready-only-close and unsupported-self negatives before changing the model.
Only a completed, consistent Standby -> genuine incoming pair can contribute
ready time. An unresolved standby, missing Ready chain, conflicting self-event,
extra outgoing event while pending, changed identity or relevant timestamp tie
invalidates the complete partition; do not publish partial classified totals.

### 2. Retained Calibration Ordering

Keep the existing fixture, warmup, four-stream hold and 40-page ceiling.
After the workload prefix and its normal stream cleanup, collect the
post-workload native snapshots, then perform the native witness and real CSS
probe adjacent to the save request. Retain the outer `server_after` snapshots
after the CSS probe and the final driver marker after both witness and probe.
Expose the post-workload snapshot phase explicitly; do not claim that an
earlier marker is later than the request.

The oracle remains decoded Thread/Start and Thread/Stop plus the full
wait -> ready -> running transition, the actual request join and an admissible
server interval. Merely moving the witness later does not establish PASS.
Test actual ordering through the adapter boundary, failure cleanup and a
deliberately missing/evicted witness. Unknown decoder/lifetime state is a refusal.

### 3. Freeze, Review And One Native Run

1. Add the failing interval/ordering/admission tests before changing helpers.
2. Implement the minimum private v2 consumers; retain frozen v1 dependencies.
3. Run new tests and affected original collector/clock/decoder boundary tests.
4. Run private size/whitespace checks, repository hygiene, OpenSpec strict and
   source/policy/link/ownership preflight; independently review implementation.
5. Resolve the new UAC grant, bind its actual receipt and count-zero allowance,
   publish the scoped spec/docs packet, and independently review the final
   policy/source/helper vector before freeze. Authenticate the unchanged helper.
6. Close reviewers and stop build/test activity before the exclusive native
   measurement window. Use one fresh run name and do not retry automatically.
7. Decode within bounds, independently replay every evidence gate, and produce
   a new dated report with collection, integrity and calibration statuses split.
8. Retain all failures and prove normal app/collector/decoder cleanup. A
   refused calibration remains an open method issue, not a failed product KPI.

The RED invocation explicitly binds the regression test to the existing
`scheduler` consumer. GREEN uses `retention_interval`; there is no production
fallback between them. Execute the private Python suites with:

```powershell
& D:/AIGC/d9-1122/venv/Scripts/python.exe -I -B -m unittest discover -s D:/AIGC/d9-1122/retention-v2-1126 -p test_*.py -v
& D:/AIGC/d9-1122/venv/Scripts/python.exe -I -B -m unittest discover -s D:/AIGC/d9-1122/low-event-1126 -p test_*.py -v
& D:/AIGC/d9-1122/venv/Scripts/python.exe -I D:/AIGC/d9-1122/retention-v2-1126/check_plan.py
```

Native collection is not ready while the new grant is unresolved. Once its
actual receipt is bound, publish the concrete `run_retention.py --inputs ...
--session ... --name le1126-ret2-cal1` command in the execution report, using
the new clean-source input and verified session path, with no placeholders.
Do not execute the former count-1 command. After the reviewed collection,
decode and replay use these explicit owned paths:

```powershell
& D:/AIGC/d9-1122/venv/Scripts/python.exe -I -B D:/AIGC/d9-1122/retention-v2-1126/decode_retention.py --run D:/AIGC/d9-1122/retention-v2-1126/le1126-ret2-cal1 --output D:/AIGC/d9-1122/low-event-1126/decoder/artifacts/le1126-ret2-cal1.json
& D:/AIGC/d9-1122/venv/Scripts/python.exe -I -B D:/AIGC/d9-1122/retention-v2-1126/proof_v2.py --run D:/AIGC/d9-1122/retention-v2-1126/le1126-ret2-cal1 --decoded D:/AIGC/d9-1122/low-event-1126/decoder/artifacts/le1126-ret2-cal1.json --output D:/AIGC/d9-1122/retention-v2-1126/le1126-ret2-cal1/native-proof.json
```

Command evidence must bind these executors and targets. Reject collect-only,
wrong roots/interpreters, source-keyword stuffing, unresolved placeholders,
shell failure suppression and arbitrary extra switches. Governance uses the
existing size/whitespace scripts and strict OpenSpec validation. Exact elapsed
setup/call/cleanup phases belong in the dated report, not an invented estimate.

## Documentation And Exit

Update PERF-SPEC-001's observation policy and link this amendment from current
guidance and the original design. Preserve all v1 source, methods, reports and
raw data. Add a new report, never edit the published calibration report.
`W3.REPLAN`/`PERF.PROBE` continue to own the refreeze/method work; do not add a
second ledger or call PERF.CERTIFY/CLOSE.R complete from this slice.

The next release question remains a fresh uninstrumented full P1-P4 recipe,
applicable reporting/provider evidence, full-profile qualification and final
independent acceptance. A useful native state partition can inform that work;
it cannot replace any of those gates or identify an OS/product cause by itself.

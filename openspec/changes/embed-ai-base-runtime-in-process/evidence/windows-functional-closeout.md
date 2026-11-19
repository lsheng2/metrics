# Windows Functional Closeout

Status: in progress. This is not yet FUNC.ACCEPT.
Scope: Windows Dashboard MDB-2 functional acceptance only. Performance,
Linux, other Apps, publication and main integration remain outside this packet.
The sole task ledger remains the parent `tasks.md`.

## Authorization And Method

On 2026-11-19 the owner approved returning the main effort to functional
acceptance and continuing until the scoped functionality is verified.
The existing 114 functional evidence keys and signed stop/cleanup bounds remain.
No candidate wheel, production timeout, runtime API or business implementation
has been changed by this packet.

Use a frozen source commit for formal native, migration, mapped and final
qualifier runs. Earlier successes are retained under their actual source and
fixture identities, not relabelled as a later qualification.

## Formal Native Baseline

At `314441b15637d4aa74e02504eae15397ac1b8367`, the actual native producer passed
all six groups with zero failures, errors or skips:

| Group | Tests |
| --- | ---: |
| B5 chat and slow/non-reader stop | 12 |
| Backpressure and capacity | 22 |
| Repeated disconnect | 1 |
| Native failure/rollback | 4 |
| Persisted context-exit recovery | 1 |
| Native signals | 16 |
| Total | 56 |

Artifact base: `D:/AIGC/artifacts/mdb2-windows-20261117/`.
Producer input and semantic receipt:
`inputs/windows-native-w2/54a7c3cb-3cda-4e90-959e-6be36b08c545/`.
Raw run: `conformance-runs/933aa680-4078-4b78-8891-b5802bc5e4af/`.
Both source observations were clean and matched the frozen commit.
This pass does not retroactively explain the historical intermittent failure.

## Added Failure-Recovery Proof

Independent assessment confirmed that the earlier context-exit recovery proof
does not establish recovery after an incomplete runtime stop. Two focused
test-only files now cover that additional safety question:

- `ai_host/tests/failed_shutdown_recovery_entry.py`
- `ai_host/tests/test_failed_shutdown_recovery.py`

The actual serve child seeds completed task/session/approval/history state
through public runtime APIs and the existing conformance package plus scripted
loopback model. A test-only callback is then submitted to the real store
executor and held with a bounded wait. The real runtime stop reports
`completed=false`, `timed_out=true`, `persistent_state_flushed=false`,
`stop_timeout` and unclosed resources; the actual host exits 3.

A fresh child opens the same durable state, reacquires the lock, compares the
saved public semantics, and repeats the task/chat idempotency keys without new
model requests or tool effects. That child stops with exit 0 and completed
persistence. A clean control and wrong-identity negative distinguish the
failure mode and reject incorrect recovery.

The test harness also has a targeted timeout regression: descendant exit
observation and a truthful process receipt happen before the original wait
timeout is re-raised; emergency tree cleanup cannot be classified as normal.
No installed module bytes or product lifecycle constants are patched on disk.

Latest local proof:
`functional-closeout-20261119/native-failed-stop-reviewfix-20261119-093957/`
contains the two-test PASS and process/observation artifacts. The preceding
adjacent five-test run is under
`functional-closeout-20261119/native-failed-stop-20261119-090914/`.
Counts overlap other suites and are not summed with the native56.
Pre-freeze independent review found two missing direct assertions for recorded
facts. The test now requires store close to return false and requires zero new
context resolutions on replay; the two-test rerun passed after those changes.

This establishes a controlled failure safety property for acknowledged public
runtime state. It does not simulate the historical Windows I/O mechanism,
promise persistence of unacknowledged work, or qualify other Apps.

## Remaining Gates

The added test snapshot still requires independent review and a final frozen
source. Then complete native receipt refresh, same-source migration/rollback,
complete evidence binding and explicit module lanes through
`qualify_ai_runtime.py --profile functional`.
Only resolved evidence plus independent FUNC.R permits the new
`windows-functional-acceptance.json` receipt. Performance must remain NOT_RUN.

During the frozen qualification packet, node results are retained in immutable
producer and review receipts. The sole ledger is reconciled after the packet,
because editing it mid-run would invalidate the required clean-source identity.

Docs impact: validation only. Product architecture, public interfaces and
operator lifecycle semantics are unchanged; the development guide names the
new test proof and its limited claim.

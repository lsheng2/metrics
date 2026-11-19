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

## Windows Observation Corrections

The next frozen attempt at `30faf9e9493e8f34b5db2666a1e2b8eef1cd3f1a`
retained passing B5/backpressure/disconnect groups but failed one signal case:
`drain-stop-file` raised `WinError 5` in process inventory before its first
stop trigger. Raw evidence is
`conformance-runs/0998aecf-fa01-476c-8704-1d16bd7f504c/`.
That attempt is not a complete native PASS.

The inventory API now accepts an explicit root PID. Native test callers query
their owned host subtree before creation-time inspection, rather than querying
all test-runner descendants and filtering afterward. The ordinary host exit
inventory still defaults to its own process. Unreadable in-scope processes
remain errors; missing roots do not become a clean empty inventory. Creation
time guards remain in place, and failures retain PID/root/image context.
The original exception did not record the inaccessible PID, so do not claim
its exact process identity was established retrospectively.

`process-scope-red/junit.xml` records the missing root-scope/error-context
checks before implementation; `process-scope-green/junit.xml` records 43
passing scope/readiness/exit-inventory checks. The original failing signal
case also passed in the targeted native follow-up.

A separate clean-control attempt reported SDK completion and confirmed flush
in about 32 ms, but failed later in exit cleanup. Diagnostic observations also
showed a test-entry `permissionerror` before readiness. These are retained as
distinct observations, not attributed to the earlier SDK close/commit failures.

The test observation protocol had a deterministic Windows sharing defect:
holding a reader on the current JSON file caused its writer's `Path.replace`
to fail with `WinError 5`. `observation-sharing-repro/result.json` records that
counterexample. The protocol now writes exclusive, immutable numbered snapshots.
Readers require the newest snapshot to parse completely; they never silently
fall back to an older successful snapshot. No older snapshot is replaced.
This is test IPC, not another runtime state store or a legacy compatibility path.

The new snapshot/scope unit group passed 15 checks, and the native failed-stop
recovery file passed both cases in `observation-snapshots-native/`. Five
bounded clean-control diagnostics then passed in
`exit-phase-diagnostics/a09f188c-1240-4bfa-8b74-670ea8a7ef47/`.
Those diagnostics do not substitute for final qualification. Product shutdown
budgets and the installed wheel remain unchanged.

## Execution Preconditions

The formal interface group later exposed another incomplete SDK teardown after
the short-request behavior itself passed. The failing run is
`conformance-runs/d0f403b2-950d-4bb8-8af3-c3143ea89511/`; its command ultimately
timed out and is not accepted. Diagnostics remained separate from qualification.

Execution inspection found that formal subprocesses inherited the user's
C-drive TEMP/TMP while the diagnostic drivers selected D. The owner requested
D-drive artifacts and temporary storage. Subsequent formal execution explicitly
sets both variables to the owned D directory recorded in
`functional-closeout-20261119/frozen-d-environment/environment.json`.
This environmental correction is not claimed as the proved cause of the old
teardown failure and does not change any runtime budget.

At the unchanged `4d4e00f` source, that explicit environment produced a complete
native56 PASS in
`inputs/windows-native-w2/da9bd97e-26a7-4ff8-9ef3-7f1fa5bb9f0b/`.
Its raw run is `conformance-runs/662ead0e-0587-49aa-bfb5-a6faa1abf392/`.

The supplemental executor then found a missing parent directory for pytest's
basetemp. Its failed setup output is retained in
`functional-closeout-20261119/w2-complete-4d4e00f/`. The final qualifier had the
same precondition gap: `run_pytest_lane` now creates the parent and leaves the
fresh basetemp itself to pytest. The dedicated RED reproduced the missing
directory; the 39-case qualifier/profile regression and a real subprocess lane
smoke passed. Evidence is under `qualifier-path-red`, `qualifier-path-green`,
and `qualifier-actual-lane-smoke` in the closeout artifact directory.
This validation-tool change requires the next clean input freeze.

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

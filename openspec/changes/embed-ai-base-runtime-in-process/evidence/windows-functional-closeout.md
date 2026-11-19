# Windows Functional Closeout

Status: FUNC.ACCEPT passed on 2026-11-20 for the scope below.
Scope: Windows Dashboard MDB-2 functional acceptance only. Performance,
Linux, other Apps, remote push and main integration remain outside this packet.
The sole task ledger remains the parent `tasks.md`.

## Accepted Baseline

The generated [functional acceptance receipt](windows-functional-acceptance.json)
has SHA256 `a6992f45482ff4b01c498e0df725c6131a78356a9f2d2d898d6ce8032ccaa670`.
It accepts all 114 functional evidence keys at clean Dashboard source
`ff09d6ff97dd62e56fb3bfc44914c5c08582a144`, paired with AIB source
`d589ac8e6572a903edc3846e7d78195e85858868` and `ai-base-runtime==0.1.1.dev4`.
The wheel SHA256 remains
`b332f338f77bf2e966de7495eea6b5968606eb670287588d97a3a4d82905ec94`.

| Complete module lane | Passed primary cases | Execution |
| --- | ---: | --- |
| ai_host | 262 | Reused complete original lane |
| metrics | 19 | Reused complete original lane |
| bug_metrics | 250 | Reused complete original lane |
| jira_sync | 32 | Reused complete original lane |
| ui_web | 759 | Reused complete original lane |
| project_management | 971 | Complete new execution |
| scripts | 548 | Complete new execution |

All seven lanes have zero failures/errors/skips and exact execution inventory
reconciliation. Native 56, complete conformance 74/recovery 39, mapped 49 business
proof, migration/rollback and both independent review gates are bound through
the receipt. Counts overlap between producers; they are not added together.
The accepted workflow includes the actual Windows host/browser, session/context,
approval/publication, task-run, recovery and stop paths with synthetic inputs.
It does not qualify real providers/models/data or all unrelated Dashboard plans.

The original final run `135bef80-bdec-45b5-af7b-00fdc0a1c5fc` remains a failed
execution: its project lane reached the 3600-second outer suite cap.
Reviewed resumption `f22ee8cf-e452-494e-a1de-9d210874a3e4` reused only its five
complete green lanes and reran admission/pip plus the entire final two lanes.
The project lane took 3724.16s under a 7200-second outer suite cap. Individual
tests, selections, application stop deadlines and assertions were unchanged.
The new qualification SHA256 is
`a3a95c4ea86845bb30a66118387721fd8e02ac3708ae22da44464e9a7b009752`.
Its owning read-only validator replays all provenance, not just the PASS label.

W2.R and FUNC.R each reached 1/1 clean pass. FUNC.R closed its one counted P1
scope-substitution finding; final P0-P3 counts are zero. The code-tested source
above precedes the documentation-only closeout commit, reported separately.
Performance remains `NOT_RUN`. Original tasks 0.6, 6.2, 6.3, 9.5, 10.2, 10.3, 10.4
remain open for their AIB-wide, Linux/image, all-platform or performance parts.
Next is W3.REPLAN and the separate performance phase, not whole-change archive.

The following sections preserve historical attempts under their actual source
identities. Their former pending statements do not override this accepted baseline.

## Authorization And Method

On 2026-11-19 the owner approved returning the main effort to functional
acceptance and continuing until the scoped functionality is verified.
The existing 114 functional evidence keys and signed stop/cleanup bounds remain.
Candidate wheel, production timeouts and runtime APIs were not changed.
Host observation/exit-loading, publication transaction and validation corrections
are described below and are included in the accepted source-bound qualification.

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

## Historical Qualification Attempts

### Broad Module Convergence

The subsequent pre-freeze sweep retained actual module results rather than
restarting frozen native qualification after every fixture issue. These are
convergence checks, not final acceptance:

- Metrics: 19 passed; bug_metrics: 250 passed; jira_sync: 32 passed.
- UI raw summary: 120 failed, 613 passed, 49 errors. Most later errors followed
  one Playwright close failure that left the synchronous event loop active.
- Project raw summary: 942 passed, 33 failed. Failures were concentrated in
  retired backend/dict fixture shapes, incomplete stat doubles and missing
  process-exit observation on a lifecycle fake.
- Scripts raw summary: 497 passed, two failed: a stale file-size allowance and
  a native late-exit classification race.

Raw results are under
`functional-closeout-20261119/module-preflight-dca47b2c7dc942e48b3f21cf2f697a3b/`
and `module-preflight-23f1bf9016bd4cdbac43dc18e1308fa8/`.
Framework summary totals can include subtests and are not additive unique-case
counts. No failing or diagnostic run is accepted as qualification.

Execution inventory now observes collection, primary/subtest call reports,
non-pass outcomes and deselection without changing execution. Reconciliation
requires exact invocation/root/output binding and testcase identity coverage;
only a total explained by the observed passed subtests may be corrected in a
new derived XML. Original XML is never rewritten. Strict `validate_junit`
remains unchanged. Actual metrics and bug_metrics runs confirmed respectively
19+2 and 250+2 reports while retaining 19 and 250 primary testcase records.
Evidence: `normalized-modules-06a55d70b343498399766cd469b0b833/result.json`,
`qualified-report-green.xml` (91 checks), and `report-binding-green.xml`
(40 focused report checks) under the closeout artifact directory.

BrowserPage now owns an ExitStack for socket restoration, Playwright and
browser closure; ProjectPage reuses it. Partial startup and close failures
still propagate while remaining resources are unwound. The lifecycle matrix
went from 13 failed/4 passed to 17 passed. The repaired UI checks passed 32
cases in `ui-fixes-green.xml`; `browser-driver-fault.xml` also proves an
owned driver failure does not leave a running loop and a new session opens.
The Chinese unavailable fixture now disables `task_run_port`, not a retired
`backend` attribute. The toolbar case retains its final heading/code assertions
and waits for actual code-block focus/selection before typing. Its original
intermittent failure was not reproduced separately; no product-editor cause is
claimed. The UI gate now checks the documented isolated-runner file path.

Typed project fixtures use the current principal, dataclasses, canonical JSON
and codecs rather than restoring old backend or mapping interfaces. The
affected group passed 72 cases; the stat double preserves all real stat fields
except its deliberately changed inode, with five direct checks passing.

SLE now reconciles late exit using the retained original observation, without
weakening identity checks. A nonzero active exit cannot become a normal
already-stopped result. PID-file recovery rechecks identity before follow-up
kill; force requests remain distinct from actual force. Evidence:
`sle-exit-race-red.xml`, `sle-nonzero-red.xml`,
`sle-consumer-final-green.xml` (59 checks), and `sle-stuck-native.xml`.
The stuck toy now remains blocked until force or a separate test-cleanup
marker; process and port release are checked before that cleanup. Its old
60-second natural expiry cannot serve as force proof.

The first final qualifier at 0ab6412 reached the complete `ai_host` module:
259 passed, two failed. Raw run:
`qualifier-runs/eaca194d-129c-4a91-89a9-eeede94a4758/`.
That failed module result is not qualification.

The publication failure was an actual `database is locked` at the publication
INSERT, after approval consumption. It is distinct from the historical SDK
store-stop timing failures. A file-backed SQLite counterexample holds an audit
write between the latest-publication SELECT and INSERT. The existing App lock
still serializes publication/import/history; the latest-row SELECT now precedes
the database transaction, whose first statement writes. No timeout or external
import retry was added. `publication-contention-file-red.xml` records the RED;
`publication-file-green.xml` records 10 passing file-backed publication checks,
and `publication-owner-green.xml` records six owner checks in a separate process.
A mixed-module attempt selected the wrong in-memory fixture and is not counted;
the new regression explicitly requires a file-backed database.

The report fixture failed at Git initialization in a 253-character archive
directory. Actual GitRunner probes reproduced success at 230/244 and failure
at 253, despite its existing per-command longpath option. The proposed change
to separate Git metadata was rejected because it changed the persistent archive
layout and would reject existing archives. The proposal is preserved in
`functional-closeout-20261119/rejected-git-layout-proposal/`; all those storage
changes were removed. Archive format and Git security policy remain unchanged.

The qualifier instead allocates pytest working directories below
`<owned_root>/qt/<run-id-hex>/<lane>`, separate from its verbose log paths.
Canonical-path/reparse checks remain, and pytest still owns each fresh leaf.
`qualifier-depth-red.xml` and `qualifier-depth-green.xml` record RED and 40 GREEN
executor/profile checks. The original real report-recovery scenario passed
under that layout in
`functional-closeout-20261119/short-report-8c0678d896eb41f2a2461120c673d1f5/`.
This qualifies the controlled validation layout, not arbitrary-depth Git roots.

The d1f8448 refresh passed native56, complete74, recovery39, W2.R and
migration/rollback. Its mapped run
`mapped-proof-runs/b4c6da8c-aa8f-4c58-86ac-3aaa1341ea83/` then passed 40
cases before the actual repository boundary checker rejected a private import
in the failed-shutdown test entry. That import was used only for source-file
identity. The entry now inspects the actual store object's class to record its
source path/hash without importing a private module. Fault injection and
production behavior are unchanged; the boundary/retirement/recovery group
passed 54 cases in `functional-closeout-20261119/store-identity-green.xml`.
The failed run and `boundary-failure-d1f8448.json` are retained. Static
repository witnesses must pass before another long frozen packet.

At `244c027c5fc8715d780fbc9dec80e18d51a99f7a`, native56, complete
conformance74, recovery/observation39, native producer/consumer composition,
independent W2.R and same-source migration/rollback passed. Their immutable
receipts remain under the closeout artifact root and
`inputs/windows-native-w2/31f43c71-5369-4f65-96ed-95b90280bcae/`,
`inputs/windows-w3/c1b96aa7-4d7e-4f60-9ac8-97d85830b759/`.
They do not qualify subsequent changed source.

The following mapped run `mapped-proof-runs/883e0385-f83a-4e0d-a81a-6fc3c20a27cc/`
failed after 24 passing cases. Creating a chat session returned 504; cleanup
completed SDK stop, but the host then stalled while first importing
`ai_host.serve_exit` and exited 3 under the unchanged watchdog. These are
separate observations, not an established shared OS cause. The exact-case
profiled diagnostic in `root-cause-runs/9cdc41bd-071e-44e8-b0ce-8cf367979292/`
passed and is not qualification.

The command now loads its exit module before serving, so first-time discovery
of that module is not paid inside the stop budget. A deterministic subprocess
finder rejects late module discovery: three cases failed before the change,
then all 75 focused exit/lifecycle/budget/binding/admission cases passed.
Evidence: `exit-import-red-r2.xml` and `exit-import-green.xml` under
`functional-closeout-20261119/`. Exit codes and all cleanup/deadline requirements
are unchanged. This fixes that lazy-import exposure, not arbitrary filesystem
latency or the earlier 504.

The final ff09d6f freeze completed native refresh, same-source migration/rollback,
business proof and all explicit functional module lanes through the reviewed
same-source resumption above. Resolved evidence and independent FUNC.R now
support `windows-functional-acceptance.json`; performance remains NOT_RUN.

During the frozen qualification packet, node results are retained in immutable
producer and review receipts. The sole ledger is reconciled after the packet,
because editing it mid-run would invalidate the required clean-source identity.

Docs impact: validation/status. Current guides and the sole ledger now distinguish
accepted Windows functionality from deferred performance/global requirements.
Product architecture, public interfaces and operator lifecycle semantics did
not change in the documentation-only closeout.

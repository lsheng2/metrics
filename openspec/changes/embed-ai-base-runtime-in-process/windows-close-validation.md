# Windows Closure Validation Matrix

This is an executable validation design, not a record of tests already run.
Use [steps](windows-close-steps.md), the structural DAG and the original
requirements together. `V0` expands the original long clauses into a finite
inventory; the groups below do not authorize dropping an unnamed assertion.
The owner's functional-first amendment is defined in
[windows-performance-phase.md](windows-performance-phase.md). V8 numerical
KPIs and exclusive benchmarking follow FUNC.ACCEPT. Native correctness,
data integrity, bounded stop/cancel and resource-return proof stay in V4-V7/V9.
The approved [B5-r1 amendment](evidence/windows-b5-owner-decision.md) changes
only the source of the backlog workload, not its safety bounds. Preserve V0's
historical census/digests; native receipts bind the amendment hash and both
`B5-chat` and `B5-transport`. Neither proof alone closes `B5-stream-stop`.

## V0: Coverage And Evidence Reuse

`evidence/windows-coverage.json` is produced by WIN.RECONCILE after execution is
authorized. It contains rows with:

```json
{
  "task_id": "5.10",
  "clause_id": "host-order-invalid-host-authenticated-stopping",
  "classification": "verify-existing",
  "owner_node": "W2.HOST",
  "producer_paths": ["ai_host/wiring.py"],
  "consumer_paths": ["ai_host/tests/conformance_order_cases.py"],
  "required_check": "invalid Host is rejected at L1 before auth and shutdown",
  "evidence_refs": [],
  "reuse_decision": "rerun",
  "deferred_trigger": null
}
```

Every real evidence reference records command/argv, executable, working
directory, returncode, actual testcase IDs, source/fixture/environment hashes,
runtime wheel identity, artifact path/hash and cleanup result. No empty
selection, collect-only, xfail, expected pending or ASGI-not-applicable row is
counted as a passing Windows requirement.

Reuse is permitted only when all relevant producer/consumer/fixture/runtime/
dependency inputs match, and the new claim is no broader than the old one.
Record changed files and why they do or do not affect each reused row.
Old S0b adapter evidence supplies comparison methodology, not current-runtime
acceptance. The dev4 publication packet proves its named publication workflow;
retirement evidence proves its named paths. Neither closes all 5.10/10.4.
Do not sum overlapping groups. If JUnit aggregate attributes disagree with
concrete testcase nodes, preserve both and reconcile the inventory explicitly.

### Original Task Routing

| Original tasks | Current planning classification | Node/check |
| --- | --- | --- |
| 0.1-0.5, PUB.CORRELATION, PUB.REFREEZE | retain accepted historical decisions/receipts | V0; no reimplementation |
| 0.6 | candidate identity available; whole-AIB delivery still external | V1; do not mark original complete from Windows milestone |
| 1.1 | implement standard dependencies/installation | W1.INSTALL / V1 |
| 1.2-1.4 | verify existing settings/helper/boundaries; implement missing signed host clauses | W1.RETIRE, W2.HOST / V3-V7 |
| 2.1-2.3 | existing auth/audit implementation; verify every original clause | W2.HOST / V3-V7 |
| 3.1-3.3, 4.1-4.2 | accepted publication slice; final dependency-aware revalidation | V0, V9 |
| 4.3-4.5 | existing context/host actions; reconcile package/provider-negative checks | V3, V6, V9 |
| 5.1-5.4, 5.8 | existing typed profiles/ports/records; exact clause verification | V1, V3, V7, V9 |
| 5.5-5.6 | incomplete full host lifecycle/policy | W2.HOST / V4-V7 |
| 5.7, 5.9 | core removal done; launcher/test/document consumers still to reconcile | W1.LAUNCH, W1.RETIRE / V2-V3 |
| 5.10 | shipped lane is partial evidence; remaining full Windows functional assertions required | W2.CERTIFY / V3-V7 |
| 5.11 | implement aggregate runtime qualification command | W3.JOIN / V11 |
| 5.12 | current docs partly synchronized; finish install/launcher/static-restart guidance | W1.INSTALL, W1.RETIRE / V1-V3 |
| 6.1 | remove remaining standalone WSGI entry | W1.RETIRE / V3 |
| 6.2; Linux portions of 6.3 | deferred-with-trigger: later owner-authorized Linux work | retain definitions and original unchecked criteria |
| Windows portions of 6.3 | standard operator guide and actual commands | W1.INSTALL, W1.RETIRE / V1-V2 |
| 7.1-7.3 | existing pane/context/action flow; missing edges must be checked | V6, V9 |
| 7.4-7.6 | retain accepted UI/local-data slices; rerun affected consumers | V0, V2, V9 |
| 8.1-8.2 | removed main routes; finish remaining consumers/current docs | W1.RETIRE / V3, V9 |
| 9.1-9.5, 9.7 | Windows launch/stop/audit and residual gates | W1.LAUNCH, W1.RETIRE / V2-V3 |
| 9.6, 9.8-9.10 | retain accepted provenance/plugin fixes; protect in changed launchers | V2 |
| 10.1 | accepted bounded browser publication; final candidate revalidation | V9 |
| 10.2 | final required affected-module/gate bundle, no default discovery shortcut | V11 |
| 10.3 | Windows synthetic old/new restore required; image clause deferred | V10 |
| 10.4 | split native functional safety/behavior from numerical performance; whole task remains open until both pass | W2/W3 V4-V7/V9; PERF.CERTIFY V8 |

Any task whose non-Windows/global clause remains deferred stays unchecked as a
whole. Windows clause rows can pass separately; do not convert partial evidence
into full-task or whole-project completion.

## Gate Details

| ID | Positive payload and required negatives | Owner/tests |
| --- | --- | --- |
| V1 | Fresh venv, direct runtime wheel provenance, complete package hash/import identity, pinned dependencies and pip check; wrong hash/version/files, editable/shadowed package or missing wheel fails before service start | `test_admission.py`; **new** `test_windows_install_smoke.py`; `check_app_package(METRICS_APP)` |
| V2 | Schema-2 profile; only owned serve/Grafana processes; stop-file then >=15s before force; all entrypoints/audits agree. Foreign listener, reused PID, wrong executable/command/start marker, early exit, malformed profile, stuck owned process and absent Jira credentials are negatives | profile/SLE/provenance/audit tests; forwarding `test_windows_launchers.py`; native `test_windows_launcher_real_paths.py`, `test_windows_launcher_sle_paths.py`, `test_windows_launcher_stack_real_paths.py`; exit-status, controlled-stop, startup-safety and source-copy tests listed in the DAG |
| V3 | Full original import/asyncio rules and active-Windows legacy absence; package has exact two App task profiles and valid tools/actions. Mutate each rule family, zero-target scan, false exclusion and misplaced test literal to prove rejection | **new** boundary/retirement checker tests; existing task/profile/settings/auth tests |
| V4 | Prebind rejects occupied port within2s without runtime import/lock; dev non-loopback refusal; anonymous production bind warning; three model variables/redaction; static autoreload off; handle.ended observed and normal versus failed host states distinguished | **new** `ai_host/tests/test_serve_binding.py`, `test_serve_liveness.py`; existing settings/serve cases |
| V5 | Monotonic stage budgets, non-skipped cleanup, 0/1/3/130 precedence, second signal <=1s, active-project budget extension/tightening, unknown exit inventory refusal and blocked stdout hard-exit bound | **new** `test_serve_shutdown_budget.py`, `test_serve_exit_inventory.py`; existing lifecycle/project-runtime tests |
| V6 | L0/L1/runtime order, same principal/challenge, all valid Host forms incl IPv6/configured host, auth saturation, production anonymous approval denial, assets/navigation and context/action behavior | `conformance_host_cases.py`, `conformance_order_cases.py`, `conformance_http_cases.py`, `conformance_boundary_cases.py`; existing Workbench/context tests |
| V7 | Runtime lifetime/transport completeness: heartbeat/disconnect, admission counters/return, body reception/backpressure, facade cancellation/lag, idempotency, persisted abrupt-exit recovery, no global env/tracer/signal/atexit mutation, bounded startup rollback/stable errors | shipped testkit plus `conformance_runtime_cases.py`, `conformance_recovery_cases.py`, `conformance_environment_cases.py`; reuse current fixtures/server |
| V8 | Deferred until FUNC.ACCEPT: numerical timing/concurrency KPIs on real serve under exclusive measurement; source drift, omitted samples or abnormal cleanup fails | PERF.PROBE/PERF.CERTIFY; `windows_host_qualification.py --phase performance`; exact KPI map in phase document |
| V9 | Actual Workbench -> chat -> context change with same session -> approval -> rendered Grafana timestamps/values -> history/audit; repeated commands without extra side effects; reject/failed publish and task-run/assist recovery; clean stop/no residual child or listener | existing workbench/publication browser joins, publication recovery, summary/report runtime joins, served runtime join |
| V10 | Actual isolated old-version snapshot -> new-version migrate/start/read/restart -> old-version restore/start/read; preserve original DB/state/archive bytes. Wrong owner, reparse escape, missing/mixed snapshot member, corrupt hash and old active-wire input fail | **new** migration rehearsal script/tests; native archive/path helpers and old/new host harness |
| V11 | Functional profile: V0-V7/V9-V10 plus explicit functional module gates; full profile additionally V8. Reject profile promotion, missing clauses/aspects, caller reclassification, wrong candidate, false pass, empty selection, command failure and stale artifact | `qualify_ai_runtime.py --profile functional|full`, named qualifier tests; original 10.2 requirements |

The original 5.10 requirement is runtime "not running", not a pre-start
Metrics WSGI handle. The public blocking handle exists only after startup.
The census therefore names the retained WSGI callable after final stop,
separately from `close_http` and the real Waitress stopping matrix.
Do not introduce an async Metrics authentication shim or count an ASGI probe
as WSGI host qualification. No original requirement or evidence key is removed.
The slow-callback probe enables diagnostics on its owned runtime loop and
checks a deliberate callback plus cleanup; it is not a performance KPI.

### V5: Stop Sequence And Bounds

These are the signed design values, not performance targets to tune:

| Stage | Deadline or rule |
| --- | --- |
| Stop detection/main-thread waits | <=0.5s slices |
| Runtime HTTP terminal events | t0+2s |
| Host in-flight drain | t0+3s; decrement on iterator close |
| Connection flush | t0+6.5s, then close leftovers |
| Server/thread shutdown | t0+7.5s; Waitress dispatcher shutdown on serve-http thread |
| Project worker | request_stop then wait_stopped(620), <=0.5s joins |
| Runtime final stop | <=1.0s |
| Explicit exit | inventory/required cleanup/output, then os._exit for every exit path |
| Watchdog | t0+9.2s; active project t0+659.2s; after worker return T, min(current,T+1.2s) |
| Watchdog stdout wait | <=0.1s before hard exit3 |
| Overall idle-run stop | trigger to actual process exit <=10s |
| Second stop signal | actual process exit130 <=1s |
| Outer Windows launcher | stop-file first, >=15s grace, then owned-force reported as abnormal |

Prove each stage error still attempts subsequent cleanup. Test all relevant
signal-first/stop-file-first/lifetime-first second-signal combinations in owned
native Windows children; direct calls to a signal handler alone are not native
signal qualification. Preserve process/thread/callback ownership diagnostics.

### V6/V7: Required Assertion Inventory

The W2.VA inventory must include these groups, without counting the ASGI
non-applicability row as success:

1. Invalid Host x credential present/absent x running/stopping, for Django, `/ai`
   and assets. Invalid Host returns L1 400; valid Host during stop returns L1
   503/Retry-After2 before auth. Running unauthenticated requests return401,
   including `/ai` before its authenticated308 redirect and assets.
2. Host forms `127.0.0.1:8793`, `localhost:8793`, `[::1]:8793`, configured host;
   unconfigured hostile host rejected. Same owner/principal and Basic challenge
   across Django/runtime, malformed Basic settings fail closed.
3. L0 body policy N=8388608, Waitress bound N+1=8388609: invalid Content-Length400;
   over-limit413 before sending body; exact-limit reaches auth; chunked
   overflow413; incomplete body never reaches app/admission. Distinguish L0's
   generated error page from L1/runtime. Bound queues/backpressure must be real.
4. Unauthenticated requests above capacity consume no short-request slots;
   authenticated short requests remain usable. Streams and short requests have
   separate4/4 budgets; assets do not consume either, including blocked-loop200.
5. End, exception, client abort and stop all return admission slots; admitted
   work drains to zero; completed close_http implies stream in-flight zero.
   Preserve diagnostics in-flight/rejected counts and OD-W1-4 I1/I2.
6. Stream heartbeat2s, disconnect detected within heartbeat+1s, repeated20
   disconnects without accumulating tasks/threads; per-block delivery not
   buffered to completion. Terminal events precede client close.
7. Facade wait timeout raises RuntimeCallTimeout and cancels its coroutine;
   loop-thread misuse fails fast. Blocked loop yields bounded503/504 for short
   calls, then records loop_stall_count/loop_lag_max_seconds when released.
8. Persisted task/session/approval survive context exit followed immediately by
   os._exit; lock is reacquired; same client_run_key does not redispatch.
   Preserve schema3 business bindings and original native archive hashes.
9. Process-wide environment/tracer/signal/atexit invariants, Windows Proactor,
   slow callback behavior, RuntimeBusy, stable exported error codes, bounded
   start timeout/rollback, and ended visibility <=1s. SDK fixture assertions must
   actually exercise the Metrics host where the contract is host-specific.
10. Approval persistence and production anonymous-decision refusal, resource
    ownership/frame-ancestors, same-session context replacement, host actions
    restricted to the Workbench, sanitized auth logging with no audit row.

### V8: Native Measurement Method

This is the final performance phase, not a W2.CERTIFY prerequisite. W2.VA
signed off the baseline-fixture adaptation required by W1.REPLAN; PERF.KPI
rechecks that approval against the final functional baseline.
The old baseline command name is no longer an executable current interface.
Bind the adapted test fixture to the original threaded server/static-handler
architecture and source hashes, while both arms use the same current
Django/settings/routes/assets/report fixtures and sampling recipe. An inability
to preserve that comparison is an owner-decision gate, not permission to choose
a cheaper baseline or reintroduce an old production interface.

Run baseline and combined host with identical synthetic data, Django/settings,
page/asset set, auth, machine and sampling recipe from `s0b-spike-report.md`
and its signoff. Use the current AIB adapter only for the candidate group.
Do not invent a cheaper baseline or substitute a test double.

- Write `HEAVY_RUN_ACTIVE` before the first process. Hold it through the last
  verdict JSON. Record start/end and each-minute process snapshots plus CPU.
  Capture HEAD and status hashes before/after; any source/status drift invalidates.
- B3: with 100ms source event spacing, first event <=200ms and inter-arrival
  p95 <=150ms. Record samples, not just a boolean.
- B4/M5 functional proof is required before FUNC.ACCEPT: repeated disconnects and normal/error/abort/stop release tests; bounded
  return to zero and no leaked owned threads/tasks.
- B5 functional proof is required before FUNC.ACCEPT as two complementary
  groups under B5-r1: actual public chat subscriptions with a deterministic
  local model prove terminal ordering and session/run identity; controlled
  active/idle/approximately8MiB slow/non-reader streams through the same
  installed adapter and actual serve prove backpressure and cleanup.
  Heartbeat2s, quotas4/4, threads14 and terminal grace2s are unchanged.
  Slow readers resume after3s and receive terminal before EOF; never-readers
  may lose output at the signed flush deadline. Each normal process exits0
  within10s, no running project job or residual owned resource. Native stop
  triggers remain required; no padded chat data or substituted wheel.
  This socket backlog is not the bounded runtime response-queue proof:
  `conformance_backpressure_cases.py` pauses the installed WSGI iterator,
  checks producer suspension/resumption and verifies generator/capacity cleanup.
- B6/B9: each required page+asset p95 <=1.2 times baseline. Repeat B6 with
  production settings, DEBUG=False and collectstatic output. In the **same**
  saturation interval, excess stream returns503/Retry-After2 and every short
  request succeeds200 in <100ms. Do not discard inconvenient samples.
- B7 functional proof is required before FUNC.ACCEPT: original browser subset equivalent. Cold AI pane starts with empty cache;
  assets all200, no final503; assets still200 during loop blockage.
- B1/stop functional proof is required before FUNC.ACCEPT: native second-signal behavior and terminal/exit evidence for
  supported Windows triggers. Any normal-stop claim also checks descendant and
  listening-port absence, not only parent exit.
- Reuse unaffected functional proof through V0; rerun it after relevant
  optimization. B9 still requires behavior and latency in the same final
  saturation interval, even when its functional behavior already passed.
- After final JSON, stop only owned resources and remove the guard. If cleanup
  fails, retain an explicit failed receipt, not a green performance result.

## Concrete Command Selection

### Planned Tool Interfaces

The new tools are deliberately bounded scripts, not a new execution framework.
All paths below are in the JSON `planned_paths` inventory with a producer node.

| Tool | Required CLI arguments | Inputs and successful output |
| --- | --- | --- |
| `windows_install_smoke.py` | `--inputs` JSON path, `--output` new receipt path | release-inputs record; new owned Windows venv/wheelhouse, exact installation argv, pip/admission/start/stop results |
| `windows_host_qualification.py` | `--inputs`, `--output`, `--phase conformance` or `--phase performance` | approved source/fixture/candidate/baseline records; all clause IDs for the selected phase, raw samples and cleanup; one phase cannot claim the other |
| `windows_migration_rehearsal.py` | `--inputs`, `--output` | verified old/new executable records and owned synthetic snapshot set; per-step upgrade/restore/read/cleanup and original-file integrity |
| `qualify_ai_runtime.py` | `--inputs`, `--output`, required `--profile functional` or `--profile full` | final frozen inputs plus complete census and repo-owned phase policy; selected-profile receipt with explicit deferred aspects, never profile promotion |
| `check_embedded_runtime_boundaries.py` | `--root` repository path, `--output` | AST import/asyncio inventory, checked-file count, violating references; no runtime startup |
| `check_retired_ai_paths.py` | `--root`, `--output`, `--platform windows` or `--platform all` | original9.5 inventory plus exact scope/dispositions; windows result lists Linux deferrals and never claims the all-scope gate |

`--inputs` is an owner-generated record, not a free-form shell-command request.
Its schema1 fields are: `source` (commit or explicitly labelled working-tree
export, archive/file hashes), `candidate` (wheel path/version/SHA256/manifest),
`python` (bootstrap and candidate absolute executables/versions), `wheelhouse`
(path plus per-wheel hashes and constraints), `owned_root` (canonical path and
ownership marker), `fixtures` (source paths/hashes), `checks` (approved V IDs
and concrete evidence paths), and `rollback` (old source/SDK/dependency/start
argv/config hashes, synthetic snapshot inventory). Required fields vary by
tool; reject absent required bindings rather than insert guessed defaults.
Only W3 accepts `source.kind=commit` for the final release claim; earlier
working-tree installation probes must preserve their exact exported file hashes.

Validate that input and output paths resolve within declared roots, reject
reparse escapes and an already existing output, and reject changed hashes before
mutations/launch. No `.env` or real user state enters a source export.
The qualifier selects commands from its approved registry and resolves argv
values from verified records; it never executes arbitrary command text from JSON.
Every tool returns0 only for its stated successful payload; validation,
missing-input, command or cleanup failure returns nonzero with a unique failed
receipt. Process termination failures cannot be hidden behind a business PASS.

### Existing Command Examples

Run from Dashboard repo root with the documented `$python`. These are
execution commands, not commands run by this planning revision.

```powershell
& $python -I scripts/validation/run_report_authoring_tests.py scripts/tests/test_dashboard_runtime_instance_profile.py scripts/tests/test_service_lifecycle_stopping.py scripts/tests/test_service_lifecycle_provenance.py scripts/tests/test_stack_process_inventory_audit.py scripts/tests/test_stack_boot_log_audit.py -q --tb=short -p no:cacheprovider -o asyncio_default_fixture_loop_scope=function
& $python -I scripts/validation/run_report_authoring_tests.py ai_host/tests/test_settings.py ai_host/tests/test_serve_lifecycle.py ai_host/tests/test_lifecycle.py project_management/tests/test_project_runtime.py -q --tb=short -p no:cacheprovider -o asyncio_default_fixture_loop_scope=function
& $python -I scripts/validation/run_report_authoring_tests.py ai_host/tests/conformance_host_cases.py ai_host/tests/conformance_http_cases.py ai_host/tests/conformance_order_cases.py ai_host/tests/conformance_process_cases.py ai_host/tests/conformance_runtime_cases.py ai_host/tests/conformance_recovery_cases.py ai_host/tests/conformance_backpressure_cases.py ai_host/tests/conformance_boundary_cases.py ai_host/tests/conformance_environment_cases.py -p ai_base_runtime.testkit.pytest_plugin -p ai_host.tests.conformance_fixtures -o ai_host_modes=blocking_wsgi -q --tb=short -p no:cacheprovider -o asyncio_default_fixture_loop_scope=function
& $python -I scripts/validation/run_report_authoring_tests.py ai_host/tests/test_workbench_browser_join.py ai_host/tests/test_publication_browser_join.py ai_host/tests/test_summary_runtime_join.py ai_host/tests/test_report_runtime_join.py -q --tb=short -p no:cacheprovider -o asyncio_default_fixture_loop_scope=function
```

Add the exact newly produced test paths from V1-V11 when their owning node
implements them. The supported Windows conformance command includes runtime,
recovery and backpressure cases. The ASGI non-applicability placeholder in
`conformance_suite.py` is recorded separately, not selected into accepted JUnit.
Native signal/stream receipts remain separate mandatory proof.

Final original10.2 module bundle uses explicit paths `ai_host/tests`,
`metrics/tests`, `bug_metrics/tests`, `jira_sync/tests`, `ui_web/tests`,
`project_management/tests`, `scripts/tests`. Verify which paths exist at
WIN.RECONCILE; do not substitute default pytest discovery. Run each independent
database lane separately if its fixtures conflict. Preserve the test inventory
and exact selected nodes so splits do not omit cases. Heavy native100-publication
or browser cases may reuse matching earlier proof only through V0 review, never
silently disappear through `-k`, deselect or skip. Functional-profile execution
excludes only the exact performance-only modules in the phase document,
records their deferral, and keeps all functional native/browser cases.
The full profile runs them in the later performance lane, not nested inside
an exclusive measurement interval.

Planning/static gates:

```powershell
& $python scripts/check_file_size_limits.py --include-untracked
& $python scripts/check_diff_whitespace.py --include-untracked
openspec validate embed-ai-base-runtime-in-process --strict --no-interactive
```

## Command Evidence Taxonomy

| Lane | Executor and target | Option/negative semantics |
| --- | --- | --- |
| focused / conformance / browser | exact candidate Python; `-I` plus `run_report_authoring_tests.py`, explicit owned test paths; required plugins/mode for conformance | `-k`, ignores and report paths are modifiers, not target proof; collect-only/setup-only/empty selection cannot pass |
| installation | resolved bootstrap/candidate Python and pip argv; owned venv/wheelhouse and exact requirements/wheel inputs | no unresolved placeholders, no editable, no online fallback for offline verification; validate returncode and semantic admission |
| static / package | candidate Python and named checker; OpenSpec CLI with exact change | missing roots/zero files/no package payload are failures; no print-PASS command substitutes |
| native / migration | candidate or explicitly pinned old Python and owned fixture scripts, concrete run/source/config paths | require process/source identity and semantic payload; setup-only or parent-exit-only is insufficient |
| plan-preflight | PowerShell JSON parser and explicit PF-DAG procedure on the actual DAG/ledger | record actual artifact paths and all structural checks; template sample or placeholder input is not evidence |

All commands are recorded as executor plus argv after dynamic values resolve.
The setup binding `$python` is not itself a passing check. Owned run/port/data
paths come from validated manifest fields and are recorded as concrete values.
Reject shell operators (`;`, `||`, pipes, redirection, substitution) in
evidence-bearing argv; shell display/formatting is not the executed test.
Only independently validated gates can be chained. Never turn a failure into
success with an output-filter or loose string match.

## Close Receipt And Remaining Gates

`windows-functional-acceptance.json` records only functional acceptance,
performance NOT_RUN and the remaining 10.4 aspects. It is not acceptable as
a full-profile performance receipt. The final combined receipt below must
revalidate functional evidence affected by performance changes.

`windows-acceptance.json` includes: final pair of commits; wheel/dependency/
fixture identities; every Windows clause and its result; reused versus fresh
evidence; review state; scoped file counts; source/state restoration proof;
normal/forced cleanup classification; owner authorization references; and all
deferred original clauses with their future trigger.

The remaining AIB release gates and Linux requirements stay in their existing
ledgers. No new “complete” status is invented to bypass them.

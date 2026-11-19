# Reporting Development And Validation

Current development rules: [AI Contract](../../AI_CONTRACT.md).
Current behavior and task state:
[reporting guide](../../openspec/docs/current-baseline/project-reporting.md) and
[one task ledger](../../openspec/changes/add-provider-neutral-project-reporting/tasks.md).
The approved delivery order and interfaces are in
[delivery sequence](../../openspec/changes/add-provider-neutral-project-reporting/delivery-sequence.md).

## Environment

The migrated `ai_host`, summary, report-assist and project-run boundaries use
the embedded runtime candidate recorded in `ai_host/runtime_artifact.json`.
The current candidate is `ai-base-runtime==0.1.1.dev4`, built from AIB
`d589ac8e6572a903edc3846e7d78195e85858868`. Its wheel SHA256 is
`b332f338f77bf2e966de7495eea6b5968606eb670287588d97a3a4d82905ec94`.
This is a development candidate, not full AIB or Dashboard qualification.
Current execution priority is Windows. Linux, WSL and Linux-container validation
are deferred; their interfaces and environment definitions remain available for
later qualification and are not prerequisites for this Windows packet.

The remaining Windows work is specified in the
[MDB-2 closure plan](../../openspec/changes/embed-ai-base-runtime-in-process/windows-close-plan.md),
with detailed steps and a clause-to-evidence matrix. Installation and entrypoint
retirement passed W1. The active sequence is remaining host functional work,
frozen-candidate rehearsal, joint acceptance and `FUNC.ACCEPT`. Only afterward
does the [performance phase](../../openspec/changes/embed-ai-base-runtime-in-process/windows-performance-phase.md)
freeze KPIs, collect probes, optimize and certify. Functional acceptance explicitly
leaves performance unqualified; stop/cancel/cleanup bounds remain functional.
The owner has resumed execution; the plan is not evidence that its gates passed.
The existing MDB-2 `tasks.md` remains the sole migration status ledger.

Windows B5 shutdown qualification requires two complementary proofs under the
approved [B5-r1 decision](../../openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-b5-owner-decision.md):
real AIB chat subscriptions prove session/run identity and termination; controlled
active/idle/approximately8MiB streams through the same installed adapter and actual
serve prove slow/non-reader backpressure and cleanup. Both are required. This
does not add chat-text streaming or change the candidate, heartbeat2s, quotas4/4,
threads14, terminal grace2s, slow-reader pause3s or normal exit0 within10s.
This is the acceptance method, not a claim that B5 or the full host has passed.
The approximately8MiB unread workload may span Waitress and TCP buffers.
Qualification binds all512 payload blocks plus real pending server output;
it does not require the entire workload to remain in Waitress's own queue.
Every registered descendant needs a terminal exit observation. The host's
0/130 contract does not require independently completed helpers to return the
same exit code as the host.

The native qualification entry is `scripts/validation/windows_host_qualification.py
--phase conformance --inputs <frozen-inputs.json> --output <new-owned-receipt.json>`.
It requires a clean source commit, the B5-r1 amendment path/hash and
`python.environments.candidate`; actual dependency fingerprints are compared
before and after execution. Its `windows-host-conformance` receipt validates
the functional B1/B4/B5 keys, including actual commands, exact test inventories
and stream/process outcomes. A plain JUnit cannot replace that receipt.
Producer and aggregate input files are separate immutable documents. The native
checker resolves and hashes the receipt's producer input, then requires matching
source, candidate, fixture, owner root, amendment and candidate interpreter/
environment bindings. The aggregate may add receipt references and historical
interpreter roles; neither can replace the selected candidate binding.
`--phase performance` remains deferred. Command availability is not evidence
that W2.CERTIFY or final joint acceptance has passed.

For a native stream shutdown failure, retain the original run and inspect
`serve.log` before repeating the full matrix. The test entry records the runtime
stop result and explicit-exit/inventory boundaries; a stalled final stage also
dumps thread stacks before the unchanged watchdog deadline. These observations
do not replace cleanup assertions or explain an earlier failure merely because
a later run passes. They are test diagnostics, not production API fields.
Test entry preludes must leave callback-registering imports, including
`unittest.mock`, until the shared serve bootstrap installs exit capture.
Load such helpers inside `configure`/`prepare`; an unobserved callback is an
exit failure, not a reason to relax the inventory.
`ai_host/tests/test_failed_shutdown_recovery.py` adds a separate safety proof:
after acknowledged public runtime writes, controlled pending store work
causes a real incomplete stop and serve exit3; a fresh child must recover the
same task/session/approval/history state without duplicate effects. Its clean
control and identity negative prevent that proof from silently becoming a
normal-stop or lock-only smoke. This does not explain a historical OS stall
or guarantee unacknowledged work survives. Keep all production budgets intact.
Native test process inventory uses the known host PID as its root; permission
errors inside that subtree remain failures. Test observation writers publish
immutable numbered snapshots, avoiding replacement of a file concurrently held
by a Windows reader. Readers reject an incomplete latest snapshot rather than
using stale success. These are test-observation rules, not runtime storage APIs.
Native signal tests wait for the complete expected cleanup-phase value, not
file existence. An implicit lifetime stop may already have closed HTTP before
the parent observes readiness; only a live process in its expected controlled
cleanup phase can satisfy that test's initial observation. Normal lifetime
and explicit first-stop cases still require HTTP readiness. Stop/signal
deadlines remain unchanged.

The actual-repository pytest witnesses
`scripts/tests/test_embedded_runtime_boundaries.py::test_current_repository_obeys_embedded_runtime_boundaries`
and `scripts/tests/test_retired_ai_paths.py::test_current_repository_has_no_retired_windows_paths`
run the existing checkers against this checkout and require nonzero coverage
with no violations. Their JUnit evidence is usable by the final qualifier;
raw checker JSON alone is not a supported evidence binding.
The Windows host's non-running HTTP proof retains the public WSGI callable
after final stop, separately checks `close_http`, and uses the real Waitress
stopping matrix. `start_blocking` exposes no pre-start WSGI handle. Do not
substitute an ASGI request or an async authentication shim for this synchronous
host; ASGI host qualification remains not applicable.
`conformance_boundary_cases.py` verifies full-short-capacity authentication,
real same-origin navigation retry, embedded CSP and closed/stopped HTTP.
`conformance_environment_cases.py` observes the actual Windows loop,
process-state ownership and a deliberately slow callback diagnostic.
The Workbench browser witness records cold asset requests and their 200
responses; these are functional checks, not startup/latency KPIs.

An aggregate JUnit may copy whole already-green input suites with a hashed
provenance list. Reject failed/skipped inputs and duplicate testcase IDs,
preserve every input case, and validate the output inventory with the existing
JUnit checker. This is report aggregation, not another test execution, and
cannot replace the producer-owned native or migration receipts.
Run the explicit conformance/testkit lane in a separate process from ordinary
GUI/business tests. Resource baselines are process-scoped; a mixed-process
observer failure is not a measured leak or a reason to loosen its thresholds.
All selected cases must still execute, and only whole green reports may merge.
Startup readiness polls treat malformed/truncated HTTP like other transient
transport failures, while retaining the original absolute deadline and owned
process check. SLE reports such probes as unreachable; normal API reads remain
strict and failed probes never establish readiness or endpoint ownership.

The migration qualification entry is `scripts/validation/windows_migration_rehearsal.py
--inputs <frozen-inputs.json> --output <new-owned-receipt.json>`. It refuses dirty
source for formal qualification. Inputs include hashed snapshot/retained-publication
records and exact `candidate`, `old_app`, `old_base` interpreter fingerprints.
Only the new candidate carries the clean-install/no-legacy-SDK gate; the old
environment is used solely for the isolated, pinned restore. The qualifier
accepts its `windows-migration-rehearsal` receipt kind only for the Windows
portion of task 10.3, after semantic replay. This command's presence does not
mean final migration or joint acceptance has passed.

Use the separately installed candidate interpreter:

```powershell
$reportingPython = 'D:\AIGC\artifacts\mdb2-windows-20261117\windows-venv-r4\Scripts\python.exe'
& $reportingPython -I -c "import sys; from pathlib import Path; sys.path.insert(0, str(Path.cwd())); from ai_host.admission import admit_runtime_candidate; print(admit_runtime_candidate()['version'])"
```

Admission checks the wheel provenance, exact package-file set and hashes, and
the actual import path without importing the runtime package. Missing manifests,
editable installs and package shadowing are rejected. Do not use a retained old
environment or an editable source install for migrated consumers. No existing
service or user database is silently switched.

### Windows Offline Installation

The owned artifact root is `D:\AIGC\artifacts\mdb2-windows-20261117`.
Its `wheels/` directory contains the runtime and Windows dependency wheels.
The installation qualifier takes the release-input record, validates ownership
and candidate files before creating anything, creates a fresh venv, acquires
dependency wheels, then installs offline. Network acquisition alone inherits
the existing process HTTP/HTTPS proxy; installation and tests use a private
home with pip configuration disabled and no user-site or shared dependencies.
Source-built dependencies must already have verified compatible wheels in the
wheelhouse. The recorded rcssmin/rjsmin wheels match the candidate's Python 3.13
Windows payload; their source archive identities are retained with the inputs.

`scripts/validation/windows_install_smoke.py --inputs <absolute-input-json>
--output <new-owned-receipt-json>` is a one-time qualification command, not an
environment repair command. It refuses an existing environment or receipt.
For another run, prepare an input record naming a fresh prefix under its marked
artifact root. Failed receipts and environments are retained for diagnosis.
Only a `PASS` receipt establishes the installed interpreter as usable.

To install another development environment from a successful qualification,
run from the Dashboard repository root:

```powershell
$artifacts = 'D:\AIGC\artifacts\mdb2-windows-20261117'
$installed = Get-Content -Raw "$artifacts\evidence\install-r4.json" | ConvertFrom-Json
if ($installed.result -ne 'PASS') { throw 'Installation qualification has not passed' }
$wheelhouse = Join-Path $artifacts 'wheels'
foreach ($wheel in $installed.wheels.PSObject.Properties) {
    if ((Get-FileHash -LiteralPath (Join-Path $wheelhouse $wheel.Name)).Hash.ToLowerInvariant() -ne $wheel.Value) {
        throw 'Wheelhouse hash mismatch'
    }
}
$constraints = $installed.constraints.path
if ((Get-FileHash -LiteralPath $constraints).Hash.ToLowerInvariant() -ne $installed.constraints.sha256) {
    throw 'Windows constraints hash mismatch'
}
if ((Get-FileHash -LiteralPath 'requirements.txt').Hash.ToLowerInvariant() -ne $installed.requirements_sha256) {
    throw 'Requirements changed; requalify this dependency set'
}
$newEnvironment = Join-Path (Get-Location) '.venv-embedded'
if (Test-Path -LiteralPath $newEnvironment) { throw 'Choose a new environment path' }
& 'C:\Python313\python.exe' -I -m venv $newEnvironment
if ($LASTEXITCODE -ne 0) { throw 'Environment creation failed' }
$reportingPython = Join-Path $newEnvironment 'Scripts\python.exe'
$env:PIP_CONFIG_FILE = 'nul'
$runtimeWheel = Join-Path $wheelhouse 'ai_base_runtime-0.1.1.dev4-py3-none-any.whl'
& $reportingPython -I -m pip --isolated install --no-index --find-links $wheelhouse --only-binary=:all: -c $constraints $runtimeWheel
if ($LASTEXITCODE -ne 0) { throw 'Runtime installation failed' }
& $reportingPython -I -m pip --isolated install --no-index --find-links $wheelhouse --only-binary=:all: -c $constraints -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& $reportingPython -I -m pip --isolated check
if ($LASTEXITCODE -ne 0) { throw 'Dependency check failed' }
& $reportingPython -I -c "import sys; from pathlib import Path; sys.path.insert(0, str(Path.cwd())); from ai_host.admission import admit_runtime_candidate; print(admit_runtime_candidate()['version'])"
if ($LASTEXITCODE -ne 0) { throw 'Runtime admission failed' }
```

The qualifier also checks complete package files, module/distribution locations,
disabled user-site and managed `.pth` ownership, and runs package checks and the
real no-model `serve` page/asset/normal-stop smoke. A dependency download or
`pip check` alone is not a successful install receipt. Linux dependency effects
remain deferred and unqualified.

The publication bridge consumes the runtime-issued read-only
`ToolApproval.approval_id`. It does not derive approval identity from model
arguments, audit events or the runtime's private persistence. The prior dev2
record is retained in the MDB-2 change's `evidence/runtime-artifact-e155d4c.json`.
The dev3 record remains in `evidence/runtime-artifact-0e8b29f.json`. Dev4 corrects
HTTP-close accounting: an already-ended client stream does not make a later
normal stop fail, while terminal-send failures during HTTP close remain errors.
Authentication failures are Metrics-owned observability: `MetricsHost.record_audit`
and the runtime-mounted WSGI branch both emit a single sanitized `ai_auth_failed`
log with path, client address and reason, and never write `RuntimeAuditEvent` rows
for that category. This is host behavior, not an AI Base SPI change.

### Workbench Consumer

The Workbench uses this same candidate through `ai_host.pane` and the registered
`metrics.workbench` context provider. The host authenticates the request and uses
`metrics.workbench.<profile_id>` as the runtime session key. A keyed open restores
the persisted context, so the host explicitly binds the newly resolved ContextRef
within the same one-second pane budget before returning the embed path.
The browser loads `EmbedHost` from `handle.ui.asset_url("embed-host.js")`; its
`context-changed` message carries only the session id. htmx preserves the iframe
by its session-specific id. Evidence selection stays local until `Ask AI`,
which sends ordered ticket ids through a server-rendered Workbench refresh;
the server enforces the 50-ticket/4 KiB ContextRef limit. Ticket bodies are not
sent to the iframe by a private message. The context binding uses only the
in-process public runtime port.

Use `ai_host/tests/test_workbench_context_ref.py`,
`ai_host/tests/test_workbench_context_provider.py`,
`ai_host/tests/test_workbench_pane.py` and
`ui_web/tests/test_workbench_ai_host_actions.py` for focused checks.
`ai_host/tests/test_workbench_browser_join.py` starts the real `serve` command with
the installed candidate, synthetic data and a scripted model endpoint; its
temporary archive must remain outside any source checkout. The test records
browser requests, screenshots and owned process shutdown. Run the host test lane
separately so its file-backed SQLite fixture governs runtime callback connections.
The bounded approved-publication join is recorded separately under MDB-2 task
10.1. Full lifecycle, deployment and final release qualification remain open.

### Approved Chart Publication

The Workbench agent uses `metrics.catalog` and `metrics.chart_workflow` to read
the selected profile's approved recipes and validate chart intent. Both are
read tools. `metrics.publish_chart` is an external tool requiring a runtime
approval. Its preview binds the generated dashboard, target, normalized render
configuration, selected range/series and a stable data fingerprint. Data
readiness is checked before requesting approval; unsupported semantics stay
`needs_metric_recipe` rather than being mapped to a different metric.

The human decides the approval in the embedded AI pane. The runtime checks the
preview again before execution. Dashboard then imports the approved bytes,
without rerendering, and stores the runtime approval id, tool-call id, approver,
digest and target in `AiChartPublication`. A repeated completed tool call reads
the same stored result; it does not issue another import. A failed import has
status `failed` and no success URL. A lost database acknowledgement can retry
the same approved bytes and deterministic Grafana UID with overwrite enabled.

The read-only `/api/ai-publish-history/` endpoint and Workbench publication pane
read these records. New successful publications supersede the previous success
for the same Grafana base URL and UID; failed attempts do not replace it.
Historic audit records are not reconstructed into publication history.

Focused checks are `ai_host/tests/test_metrics_tools.py`,
`ai_host/tests/test_publication_boundaries.py`,
`ai_host/tests/test_publication_runtime_join.py`,
`ai_host/tests/test_publication_recovery.py` and the `bug_metrics/tests/test_ai_chart_*`
tests. `ai_host/tests/test_publication_browser_join.py` uses production settings
with synthetic Basic credentials, an isolated database, a scripted model and its
own local Grafana instance. It verifies the actual imported chart data, not just
the import acknowledgement. Run it on the selected candidate interpreter with
a fresh external `--basetemp` directory. No live provider/model or existing
Grafana instance is part of that test.

Run every reporting, `ui_web` and `project_management` test through the existing no-dotenv
entry with the selected interpreter in isolated mode (`-I`), naming test files or nodes explicitly:

```powershell
& $reportingPython -I scripts/validation/run_report_authoring_tests.py <test files or nodes> -q --tb=short -p no:cacheprovider -o asyncio_default_fixture_loop_scope=function
```

Plain `pytest` is not equivalent: `pytest.ini` discovers only `tasks`, `forecast`, `velocity` and
`ui_web` tests, so `project_management` and other modules are silently omitted, and the root
`conftest.py` loads development settings that read `.env`. The runner denies external networking
and suppresses dotenv loading; local browser HTTP and separately scoped runtime IPC remain permitted.

Evidence runs add durations and a unique evidence filename:

```powershell
& $reportingPython -I scripts/validation/run_report_authoring_tests.py ui_web/tests/test_report_daily_ui_browser.py::TestReportDailyUiBrowser::test_shouldCarryEditablePersistentReferenceIntoActualNextDay -q --tb=short -p no:cacheprovider --durations=5 --junitxml=.tmp/dashboard-delivery-20261105/daily-two-day.xml
```

The named next-day case is the DAILY closure target; its existence alone is not a pass.
Do not run a missing test node as evidence. The tasks ledger records its implementation
and actual result.

## Embedded Task Boundary

Dashboard persists its original UTF-8 canonical request and source hash.
The adapter uses the runtime's public `canonical_digest` and `canonical_json` for
runtime requests and output bytes. A returned observation carries both
`source_input_sha256` and the runtime's `input_sha256`; result content retains
the runtime's actual `output_sha256`. Never change historical archive hashes,
normalize old request bytes in place, or equate the two encodings for Unicode.

Unknown dispatch is observed with the original request through read-only
`lookup`, then `get`/`result`. It never becomes a second `start`. Cancellation
shares one remaining time budget across lookup, cancel and observation;
acknowledgement alone does not prove settled execution.

New project-run admission records accept only schema 3 and persist the original
principal and exact task-profile binding. Old active operation records are
rejected, not silently converted. Business publications remain untouched.
The runtime observation contract has no completion timestamp; report readers
leave the optional summary time unset rather than reuse the retired wire field.

The registered host command is `serve`. Project
shutdown uses `request_stop()` followed by `wait_stopped(timeout)`, with no
`stop` alias. Failed startup drains owned resources without replacing an
already installed owner. Host-loopback smoke and fault-path tests do not
replace the full stream, signal, performance, browser and publication gates.

`serve` detects an ended runtime and shuts down instead of leaving a dead AI
pane behind. An already ended loop is not given another HTTP-close coroutine;
the runtime context's final stop still determines cleanup success.
Shutdown stops listener admission, closes runtime HTTP, drains
response iterators through `close()`, flushes connections, and closes the
Waitress dispatcher on its server thread before stopping the project worker.
The signed absolute deadlines and watchdog remain in the Windows validation
matrix; their full native qualification is still open.

Normal and failed exits emit `serve_exit_inventory` before explicit database
and logging cleanup, then `serve_exit_cleanup` and the final status line.
Unknown callbacks/resources or failed cleanup produce exit 3, overriding a
startup/runtime exit 1; clean exit is 0 and a second stop signal is 130.
The original startup failure code is retained and printed even when cleanup
also fails, so a startup timeout is not hidden behind the exit3 diagnostic.
Do not bypass an inventory failure with a compatibility launcher.
Static auto-refresh is disabled; restart `serve` after changing static files.
Non-loopback binding is refused when anonymous approvals are enabled;
otherwise absent Basic users produce an address-only warning.

## Validation Selection

| Layer | Proof | Fixture boundary |
| --- | --- | --- |
| L0 | schema, null/empty, dates, sort, fragments, delta, hashes | Pure values; no Git, database, browser or runtime |
| L1 | durable command, CAS, recovery, source/summary/editorial preservation | Real isolated store only for the transaction being proved |
| L2 | auth, CSRF, forms/JSON, error codes, nullable serialization | Cheap boundary fixtures plus a small real-service wiring subset |
| L3 | real Milkdown editing, paint, keyboard, popup, Save/reopen | Mounted editor and real local HTTP/storage; synthetic upstream |
| L4 | matched application/runtime/publication and complete week | Stable candidate, owned services/data, explicit normal cleanup |
| External qualification | actual provider/model/Outlook/deployment/scheduling | Separate authorization and evidence; never inferred from local JOIN |

Reuse immutable input/profile/source fixtures. Do not share mutable command, draft, archive
or acceptance state between independent cases. Case failures must preserve the actual response
and stop widening the test set until the relevant lower-level cause is understood.
Do not rebuild a week for every bad field or treat a passing same-source week as proof of delta analysis.

Report service doubles are real `ReportDraftService` instances seeded with real drafts and
publications, or subclasses that override only what the case needs (for example
`UnusedReportService` in `ui_web/tests/test_project_run_views.py`). Do not hand-build fake service
classes: when the facade/service contract changes, a real-service double fails the test, while an
ad hoc fake hides the drift. Patch view facade factories with
`ProjectRouteTestSupport.patch_view_factory`, not a manual `setattr` restore.

## Review And Publication

Use one writer and a bounded independent reviewer. A packet review can cover source, evidence
and the next dependency boundary; later evidence completion need not repeat unchanged source review.
After two equivalent failures without new evidence, change the hypothesis/diagnostic.
Review cost at packet boundaries and after 60 minutes on the same user problem.

Record runtime source, fixture/test and environment fingerprints separately.
Test files can be native fixture dependencies. A validator-only edit and a
changed application fixture have different effects on retained qualification
evidence; compare their recorded fingerprints before reusing results.

Stage only approved paths. The retained authoring WIP is not all another owner's work:
publish its verified closure separately from unrelated Scope/config/style edits.
A working-tree qualification is not a clean-install or formal deployment qualification.
Normal stop, emergency cleanup and still-running unrelated services are separate statements.

## DAILY Evidence

The current bounded packet is recorded in
[DAILY delivery evidence](../../openspec/changes/add-provider-neutral-project-reporting/daily-delivery.md).
The template counterexample exercises a single day's cell so another column cannot mask
reversed history/current-note ordering. The browser chain additionally proves actual next-day
creation, reference preservation, human text/paint and publication identity.
Observe GET/POST responses before waiting for navigation; retain failed attempts independently.
Same-meeting replay with changed effective choices intentionally returns 409 and the original
result. Test the visible unapplied-choice message and publication link; do not assume every
idempotent return redirects or change the service to silently ignore selected choices.
Only the complete chain plus its scoped review closes DAILY. This is not the full-week,
changed-source AI, clipboard/Outlook or clean-release qualification.

The 2026-11-05 manual two-day chain and three direct template cases are qualified in the
current worktree. The existing publication is reachable from a same-day conflict result;
history is displayed before the current source-status prefix within each cell.
That original docs-only checkpoint is superseded for source packaging by the verified
authoring/DAILY/delta closure `4cb995b` on main. Its unrelated Scope/config/style changes
were excluded. Request latency and the recorded native diagnostic incident remain explicit
limitations, not implied fixes.

## ASSIST Validation

The [ASSIST packet](../../openspec/changes/add-provider-neutral-project-reporting/assist-execution.md)
specifies the current profile, API, local receipt and editor contracts. Its task/qualification
state remains in the single ledger. Use the selected runtime interpreter, not the legacy venv.

Run pure profile/target tests and `test_report_assist_service.py` /
`test_report_assist_recovery.py` before `ui_web/tests/test_report_assist_browser.py`.
The browser cases mount the actual editor and save via real local HTTP; only the upstream
task-run port is synthetic at this layer. They cover receipt retirement and same-text
acceptance as well as text/paint/cancel/unavailable states and mobile contrast/hit targets.

`ai_host/tests/test_report_runtime_join.py` separately uses the installed runtime,
the App-owned authoring profile and real data Git. It verifies recovery after a
lost admission reply, Save, human paint/provenance, publication and next-day
inheritance. Its model endpoint and source records are synthetic. The paired
`ai_host/tests/test_summary_runtime_join.py` checks summary recovery and original
archive identity without a second task submission.

Evidence is retained under `.tmp/dashboard-assist-20261106/`, with unique XML and native
run directories. Do not count initial RED or an earlier happy-path source as final closure.
The export/clipboard sample and original five-day/cross-week chain now have separate
delivery receipts. Those historical receipts qualify only their recorded source
and environment.

### Served Runtime Join

`project_full_stack.py` starts one real `serve` process with its embedded runtime
and one bounded loopback model fixture. `ProjectRunFixtureAppConfig` supplies
synthetic Jira data only to this controlled validation composition. The general
UI fixture does not replace provider access. Use a fresh external data root:

```powershell
$prepared = & $reportingPython -I scripts/validation/project_full_stack.py prepare --data-root D:\AIGC\scrum_dashboard_validation\mdb2-runtime-join | ConvertFrom-Json
$run = $prepared.run_dir
try {
    & $reportingPython -I scripts/validation/project_full_stack.py start --run-dir $run --lifetime-seconds 600
    if ($LASTEXITCODE -ne 0) { throw 'Start failed' }
    & $reportingPython -I scripts/validation/project_runtime_join.py run --run-dir $run
    if ($LASTEXITCODE -ne 0) { throw 'Runtime join failed' }
    & $reportingPython -I scripts/validation/project_full_stack.py restart-app --run-dir $run
    if ($LASTEXITCODE -ne 0) { throw 'Restart failed' }
    & $reportingPython -I scripts/validation/project_runtime_join.py reopen --run-dir $run
    if ($LASTEXITCODE -ne 0) { throw 'Recovery failed' }
} finally {
    & $reportingPython -I scripts/validation/project_full_stack.py stop --run-dir $run
}
```

`run` exercises the actual HTTP project-run and report-assist consumers, schema-3
admission, duplicate commands and exactly two model dispatches. It is once-only
for a given run. `reopen` is read-only and may repeat; each invocation writes a
unique receipt under `evidence/runtime-reopen-<uuid>/`. Failed evidence is retained
separately, not overwritten. The stop receipt must report normal cleanup; a
successful business operation alone does not prove successful service shutdown.

## Derived Export Validation

[The export packet](../../openspec/changes/add-provider-neutral-project-reporting/export-execution.md)
uses saved HTML as its source, with separate Markdown/Excel adapters and no new
publication files. Pure compiler checks precede one real-Git sample and mounted
browser downloads. The published path must pass with the renderer/source/finalize
methods poisoned, and preserve both publications' original bytes and Git head.

Run `project_management/tests/test_report_exports.py` without Git/browser fixtures.
Large parameterized values need explicit short pytest IDs on Windows; otherwise
`PYTEST_CURRENT_TEST` itself can exceed the OS environment-variable bound.
Repeatability tests change controlled clocks, not the system time. Bounds must
reject content rather than rely on openpyxl's truncating string assignment.

`ui_web/tests/test_report_export_browser.py` verifies actual downloaded files and
browser Clipboard API readback after Save, including paint in HTML. That proves
the browser route, not Outlook/native-app paste. Current evidence and limitations
are in [export delivery](../../openspec/changes/add-provider-neutral-project-reporting/export-delivery.md).
The original full-week/cross-week scenario has its own retained qualification receipt.

## Full Week Qualification

Use the existing owned launcher and the
[week packet](../../openspec/changes/add-provider-neutral-project-reporting/week-qualification.md).
The fixed `full-week` scenario uses three synthetic Jira records and the installed
embedded runtime and loopback model, with actual source capture and accepted summaries on the first day.
Later unchanged captures reuse those summaries. The browser driver performs the
six meeting dates through the actual templates, editor, Save and Finalize routes.
The dedicated fixture also supplies the bounded reference reader for `#ALPHA-101`
completion through the normal report factory; it does not create another project
runtime or replace the completion view. The `single` and general UI scenarios
do not enable that reader. Dispatch counts read the model fixture's
`model/executor-observations.jsonl`.

```powershell
& $reportingPython -I scripts/validation/project_full_stack.py prepare --data-root D:\AIGC\scrum_dashboard_validation\mdb2-full-week --scenario full-week
```

Use the exact owned `run_dir` returned by `prepare` for `start`, `status` and
`project_week_browser.py --run-dir`. Do not select a run by directory age or use
another application's port. The driver stops its owned services in its finalizer
and retains all artifacts. Initial setup, per-operation deadlines and the service
lifetime are independent bounds; never extend an existing operation to make it pass.

After an interruption or PC restart, inspect the prior run's responses, canonical
checkpoints and stop receipt before starting anything. A finalized day needs its
verified publication, not only a screenshot or a successful Save. A failure and
normal cleanup are separate conclusions. A changed runtime requires a new frozen
candidate; do not combine its days with an earlier failed candidate or rewrite
historical request/hash bytes.

For a validator-only failure after publication, `--resume-after` can continue the
same run before the weekly-view step. It permits only the explicitly named
validator files to differ, verifies every retained day by reading actual original
artifacts again, and writes a new evidence directory. Application/shared-fixture
changes, incomplete checkpoints or a different source commit require a new run.
Old failures remain part of the evidence even if corrected validation later passes.

The refresh preparation binding uses the validated content hash; its active slot
separately binds the full stored intent. Initial saved-capture and replacement
formats retain their existing hash definitions. The shared producer/consumer rule
is covered by `test_report_preparation_publication_guard.py`; stale, superseded,
missing and downgraded bindings must continue to refuse publication.

The historical [qualified week receipt](../../openspec/changes/add-provider-neutral-project-reporting/week-delivery.md)
binds six daily publications, a weekly view, explicit empty-note/gap handling and
42 original-file rechecks. It is an operation/continuity qualification, not a
performance qualification and does not qualify the new embedded composition.
Concise business output and separate audit downloads
are covered by the later presentation receipt below, without rewriting that week.
Profile the recorded long prepare/view waits before choosing an optimization;
do not use more week runs to locate a read-path problem. The later Report Read
Performance section records that profiling and the qualified optimization.

## Concise Presentation

`standup/1` is a template presentation profile, not a new AI or source protocol.
It selects `template-document/2`; missing profile preserves legacy hashes/bytes.
Read/Save/render/Finalize route all user or pinned-renderer claims through the
strict validator. The builder must preserve the profile on Save.

Run the pure `test_report_standup.py` / `test_report_audit.py`, then the focused
`test_report_standup_publication.py` real-Git successor and original-byte test.
`test_report_presentation_guards.py` attacks an internally rehashed unknown
renderer through actual draft consumers. HTTP tests are
`ui_web/tests/test_report_standup_views.py`; the mounted sample is
`test_report_standup_browser.py`. Use the same selected runtime/no-dotenv entry.
No extra full week or model dispatch is needed for this presentation boundary.

Audit export reads all six original files in one owner-checked, verified
publication pass. The deterministic ZIP has a separate generator revision and
does not alter publication format or re-render its body. The 32 MiB limit applies
before and after packaging. Runtime source/accepted/editorial authorities are
unchanged; original-week public readback remains separate from preview generation.

Evidence: `.tmp/dashboard-presentation-20261106/` and
[presentation delivery](../../openspec/changes/add-provider-neutral-project-reporting/presentation-delivery.md).

## Skipped Meetings

The [skip packet](../../openspec/changes/add-provider-neutral-project-reporting/meeting-skips.md)
adds a local append-only Django calendar chain. It does not change the runtime/profile
or start providers, scheduling or model work. Apply migration `0004` only in an
authorized deployment; tests use the isolated runner database.

Pure cases: `project_management/tests/test_report_meeting_contracts.py`.
State/admission: `test_report_meetings.py`, including an intent-only interruption
and original-command repair. Joined real-Git consumers:
`test_report_meeting_resumption.py`; retained legacy seed replay:
`test_report_history_core.py::test_should_prepare_immutable_context_seed_from_source_publication_and_template_use`.
The comparison normalizes absent legacy authority to `None` without changing bytes.

HTTP: `ui_web/tests/test_report_meeting_views.py`.
Mounted editor: `ui_web/tests/test_report_meeting_browser.py`, using real HTTP,
ORM, archive and Git. Finalize Friday, record two skipped weeks, resume Monday,
Save/reopen/Finalize, export and restore. The external source is synthetic and the
AI client is forbidden. A separate Chinese/390px case checks language navigation.
This is a direct two-date jump, not fourteen artificial daily runs.

Keep evidence under `.tmp/dashboard-skips-20261106/` with unique XML/run directories.
The seed snapshot uses its originally pinned calendar, even if the series policy
advances while preparation is delayed. Never read a live calendar to render an
already saved or published report. Validate old/new context readers, weekly
selection, original-byte downloads and missing-versus-skipped coverage separately.

## Source Observations

[The source-observation packet](../../openspec/changes/add-provider-neutral-project-reporting/source-observation.md)
separates source comparison from accepted-summary note eligibility. It keeps the
v1/v2 context shape and original source hashes. The source reader must continue
to check completeness before emitting `summary_pending` or `summary_stale`;
otherwise legacy `pending` plus a hash would no longer prove a complete capture.
Do not replace this invariant with a new interpretation of partial coverage.

Run `project_management/tests/test_report_source_observations.py` for manual
same/different hashes, uncertain sources and baselines, late/revised summaries,
old canonical bytes, human deletion/paint/link/AR, saved-empty notes and both
renderers. `ui_web/tests/test_report_source_observation_ui.py` covers actual
view-model/template output and gettext. Source producer tests separately protect
complete-source gating and unchanged accepted-summary reuse.

`test_report_source_observation_publication.py` uses the native capture service,
source reader, preparation worker and local Git with a synthetic provider and
`manual_only`. It captures twice, finalizes two days, verifies no duplicated note,
checks all six old files and inspects the derived Markdown/Excel.
`ui_web/tests/test_report_source_observation_browser.py` mounts Milkdown, verifies
the observation is not editable, then saves and reopens a colored human note.
The browser fixture is distinct from the native-Git proof; do not call it live
provider or model qualification. It checks EN/zh-Hans, 1440px/390px, text fit,
page overflow and observation contrast.

Evidence stays under `.tmp/dashboard-source-observation-20261107/`.
Keep failed runs separately; a test-fixture error is not a product regression.
No full-week, S1, model dispatch or real enterprise-source run is needed for this
boundary. The selected runtime environment and no-dotenv entry above still apply.
Changing UI labels requires regenerating the checked-in zh-Hans `.mo` from its
`.po` with the existing `polib` compiler before bilingual validation.

## Report Read Performance

The later user-workflow changes are qualified separately below. Existing performance
receipts are historical measurements of their named candidates, not measured SLOs
for recovery checkpoint writes or the new controls.

2026-11-06的症状与profile已固定为
[性能基线](../../openspec/changes/add-provider-neutral-project-reporting/performance-baseline.json)：
语言POST为毫秒级，工作台GET的主要成本是169次串行Git读取及重复packet校验。
这是历史单样本诊断，不是p95；原probe缺完整数据指纹，实施时需固定同一合成克隆做对照。

[架构](../../openspec/changes/add-provider-neutral-project-reporting/report-read-performance.md)
与[执行计划](../../openspec/changes/add-provider-neutral-project-reporting/performance-execution.md)
已落实读取与窄操作入口，任务状态仍以唯一ledger为准，完整验收不等于源码复审通过。
原始数据Git、权限、最新写锁校验和六文件bytes不变；不引入默认跨请求缓存或持久索引。

`scripts/validation/profile_report_reads.py`对已有owned synthetic实例运行真实Django HTTP；
`--scenario workbench|baseline|preparation|editor --samples 20`保留首请求与所有稳态样本，
`--dataset s1`选择页20/5秒规模门槛。输出目录只能在该run的evidence下，出站网络被禁止。
结果包含代码、运行数据、runtime/Django路径和前后指纹；`passed`只代表对应场景，不能替代
实际点击到最终列表可用的浏览器证据。首次超过10秒时停止扩样定位，不能提高期限。

S1使用`prepare_report_scale.py --manifest-from <owned-synthetic-run>`构建一次持久数据，
再运行reader采样。构建时的buffered Git/identity/quota替身只缩短测试准备，实际来源读取、
Git对象、checkout物化、六文件校验都恢复正常实现。不要用临时pytest目录保留大型验收数据，
不要把未物化index的fixture误判为健康checkout性能，也不要反复构建100份数据定位读取问题。
`profile_report_saves.py`接受同run的实际浏览器种子，可用`--resume-receipt`继续已确认修订；
每次用新命令和最新CAS，不修改或重放旧请求bytes。

验证先跑`test_git_read_batch.py`、`test_archive_read_limits.py`，随后query/consumer及
`ui_web/tests/test_report_query_views.py`与`test_report_query_browser.py`。
小规模原生fixture检验无误后才运行持久S1；`test_s1_scale_fixture_materializes_100_native_publications`
是显式慢门槛，不属于每次快速回归。手工Ego任务页消失时停止该surface并请求重建授权，
不接管用户页或把两次预检冒充十次最终样本。本次不授权8017、真实来源或正式模型切换。

2026-11-07用户授权新建专用验证空间后的十次实际语言切换全部通过；
从Apply点击到目标语言及五张完整表格绘制后的p95为3.101s，门槛仍为3.5s。
该次只补浏览器门槛，运行代码和S0数据前后hash一致，未重跑整周或重建S1；
旧测试与性能回执先核对文件hash和适用边界再复用，不冒充本次重新执行。
具体原始样本、截图、代码/数据/环境指纹与正常清理记录见
[性能交付回执](../../openspec/changes/add-provider-neutral-project-reporting/performance-delivery.md)。
此结果仅关闭本机限定性能门槛，不授权真实来源/模型、定时任务或生产服务切换。

## User Workflow Hardening

[The workflow packet](../../openspec/changes/add-provider-neutral-project-reporting/standup-user-workflow.md)
extends daily authoring to context v3. Legacy v1/v2 readers remain byte-preserving.
The current editable observation set is not the cumulative read-only observation
history. Period merge, skip snapshot freezing, reprepare preservation, both report
renderers and both editor/period templates consume the new history.

`test_report_user_workflow.py` and `test_report_workflow_changes.py` are the
bounded pure checks for zero-member meetings, reentry, freshness, observation-only
days, human AR and explicit discussion. Update older tests that reused an old
capture as if it were fresh: retain their content-equality assertion and supply
a new capture/time for the no-freshness-warning case. Do not weaken date disclosure
to preserve the old test wording.

`test_report_user_workflow_publication.py` uses real local Git and a synthetic
source projection for four selected dates spanning empty scope/reentry, then
checks all original publication files. `test_report_recovery.py` exercises
atomic checkpoint persistence, sequence/idempotency, independent tabs, size,
binding, corruption and expiry. `test_report_recovery_views.py` covers authenticated
JSON, CSRF and no-store. `report_recovery_test.mjs` covers serialized checkpoint
writes and exact restore binding.

Mounted `test_report_user_workflow_browser.py` closes and recreates the browser,
restores unsaved painted notes, AR, persistent content and review selection, then
Saves and exercises owner changes/closure/reopen. A separate lost-Save-response
case commits the real server request but drops its response, proving stale
recovery remains download-only and does not overwrite the saved revision.
Wait for the actual final checkpoint HTTP response, not a truthy async JavaScript
predicate that can finish before the write. Preserve that failed probe separately.

Evidence root remains `.tmp/dashboard-user-workflow-20261107/`; work continued
on 2026-11-08 without changing historical filenames. No real provider/model,
production migration, existing service switch or S1/full-week rerun is implied.

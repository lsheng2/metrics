# Windows Closure Steps

Read [the plan](windows-close-plan.md) and [validation matrix](windows-close-validation.md).
Node IDs below are defined in the JSON DAG. Only `tasks.md` tracks completion.
Paths labelled **new** are planned outputs, not commands claimed to exist today.

## Common Execution Contract

1. Recheck Dashboard HEAD/status and candidate hash before each wave. Preserve
   unrelated changes; a scope change requires an explicit `REPLAN` decision.
2. Resolve `$python` from the candidate environment in the reporting guide,
   then from the verified new Windows environment after `W1.INSTALL`. Record its
   absolute executable, Python version, distribution versions and wheel hash.
   Never infer it from the current shell or upgrade the retained `.venv`.
3. For each behavior change: write the named negative test, observe the expected
   failure, change the owning implementation, rerun that test, then its affected
   consumers. A missing-evidence check on already-correct code needs no invented
   production failure. Current test entry:

```powershell
$python = 'D:\AIGC\artifacts\mdb2-windows-20261117\windows-venv-r4\Scripts\python.exe'
& $python -I scripts/validation/run_report_authoring_tests.py ai_host/tests/test_admission.py -q --tb=short -p no:cacheprovider -o asyncio_default_fixture_loop_scope=function
```

4. Before packet review run scoped size/whitespace/OpenSpec checks and isolated
   Django checks when applicable. Stage an explicit allowlist and commit the
   working package after review; no push/main merge is implicit.
5. Store raw results in unique owned external run directories. Commit sanitized
   receipts and hashes, not credentials, databases or bulk test artifacts.

## WIN.RECONCILE

**Inputs:** original tasks 0-10, publication/retirement packets, current source,
candidate manifest and the historical SDK020 delivery receipt.
**Owned output:** **new** `evidence/windows-coverage.json` and
`evidence/windows-release-inputs.json`; existing `tasks.md`.

1. Enumerate every original task and every mandatory Windows clause of 5.10 and
   10.4. Record task/clause ID, current implementation owner, test/receipt path,
   source/fixture/runtime fingerprints, and one of `proven`, `verify-existing`,
   `implement`, `deferred-with-trigger`. Do not infer status from checkbox count.
2. Use the routing table in the validation document. For `proven`, resolve and
   hash the evidence and justify unchanged dependency scope. For
   `verify-existing`, assign the missing assertion to W1/W2, not new production
   architecture. A partial clause cannot close its whole original task.
3. Verify the dev4 wheel still exists and hashes correctly. Record a durable
   owner-selected wheelhouse location; copy verified bytes there only after
   owner resume. A path under `temp` is source material, not the final installer.
4. Materialize rollback prerequisites **before expensive host work**. Start with
   pre-MDB2 Metrics commit `ee7bfb0e734e1123ba5c611997fedd6052f50049`; verify it
   contains the old startup command and required configuration. Use an isolated
   source export/copy, never switch this checkout or re-add old code to it.
5. Resolve the old runtime/SDK/dependencies from
   `add-provider-neutral-project-reporting/sdk-020-join-delivery.json` and its
   referenced selection/integrity manifests. The existing
   `.tmp/sdk-020-join-20261105/app-venv/Scripts/python.exe` is only a candidate
   input, not proof. Historical receipt names SDK `0.2.0a1`, wheel SHA256
   `1ab6c7aa7255abeb4637734f65613827d39593ff72b7ef9d630885922c2dd134`;
   preserve its source-patch/integrity evidence instead of assuming a clean
   historical commit equals the qualified tree.
6. In an owned synthetic lane, prove the selected old source/environment can
   start, read its seeded state and stop normally. Record the exact old startup
   argv, source tree/archive hash and environment manifest. If any material is
   missing or inconsistent, stop with `ROLLBACK_BASELINE_UNAVAILABLE`; request
   that specific artifact or an explicit scope decision. Do not silently replace
   old-version rollback with restarting the new version.
7. Preserve an immutable rollback source tag **inside the owned rehearsal source
   copy only**, named `mdb2-windows-rollback-baseline`; record that repository,
   tag and exact commit with the source archive/environment hashes. Refuse an
   existing tag pointing elsewhere; never move it. Creating this private test
   reference after OWNER.RESUME does not create a tag in the shared checkout or
   publish it. Record deferred Linux image checks separately; no Docker image
   is claimed. Missing verified old source still blocks the probe.

**Exit:** complete clause routing and executable old/new artifact inputs, or an
explicit blocking prerequisite before W1. Existing good evidence is preserved.

## W1.VA

Review `V1`-`V3` with the Validation Engineer role before changing installation or
process ownership. Confirm direct wheel provenance, an offline installation
failure case, foreign-listener/PID-reuse cases, and no-dotenv actual entrypoint
tests. Require new checkers to reject their own mutations before their green
output is trusted. This is one bounded design signoff, not a full test run.

## W1.INSTALL

**Modify:** `requirements.txt`, `README.md`, reporting guide.
**New:** `scripts/validation/windows_install_smoke.py`,
`scripts/tests/test_windows_install_smoke.py`.
**Reuse:** `ai_host.admission.admit_runtime_candidate()` unchanged unless a
demonstrated defect requires a separately justified correction.

1. Add exact runtime/Waitress pins; move portalocker to 4.4.2; remove the unused
   Windows gunicorn requirement. Keep Django/WhiteNoise versions fixed.
   Linux definitions remain preserved but unqualified; report their deferred
   shared-dependency impact instead of advertising a working Linux image.
2. Write the installer test first: a fresh owned venv installed only by the old
   requirements must not count as admitted. Mutated wheel bytes, absent wheel,
   incomplete package manifest and shadowing fail before launching a service.
3. Build a wheelhouse from the exact runtime artifact and required dependencies.
   Record every wheel's filename/SHA256 and the resolved Windows constraints.
   Dependency acquisition may use the already authorized package source;
   verification installation is offline and cannot silently fall back online.
4. Install the runtime by its verified file path **before** installing named
   requirements. Admission requires PEP-610 archive provenance. Installation
   code uses `subprocess.run(argv, check=True, timeout=...)`, not shell strings:

```python
subprocess.run(
    [lane_python, "-m", "pip", "--isolated", "install", "--no-index",
     "--find-links", wheelhouse, verified_runtime_wheel],
    check=True, timeout=600,
)
subprocess.run(
    [lane_python, "-m", "pip", "--isolated", "install", "--no-index",
     "--find-links", wheelhouse, "-r", requirements_path],
    check=True, timeout=600,
)
```

   These variables are resolved by the new smoke script from its owned lane and
   verified release-input record; no unresolved token is allowed in evidence.
   Timeouts bound installer operations, not product runtime deadlines.
5. Run `pip check`, candidate admission and package validation. Start the actual
   `serve` on an available owned loopback port with synthetic data/no model;
   verify page and `/ai` state, then stop normally and verify port/PID release.
6. Document the real operator install sequence and artifact location. Do not
   change the pinned candidate merely to rename a development version.

**Exit:** `V1`; fresh installation works without the old shared environment.

## W1.LAUNCH

**Modify:** the runtime-instance profile; the current Windows launcher/stopper
surfaces and both audit scripts listed in the DAG, including the existing
`e2e_start_bug_trend.ps1`, `e2e_stop_bug_trend.ps1` and
`e2e_restart_bug_trend.ps1` wrappers; `e2e_bug_trend.services.json`;
`scripts/validation/project_ui_fixture.py`.
**Tests:** existing profile, launcher, lifecycle and audit tests; **new**
`scripts/tests/test_windows_launchers.py` for actual entrypoint behavior.

1. Make instance profile schema 2. Keep only `django`, `grafana` and the external
   model gateway service; remove AI Base backend/frontend ports/CLI options.
   Project model URL projection uses `METRICS_AI_MODEL_BASE_URL`; old schema
   objects are refused, not silently converted.
2. Extend the profile tests with exact positive/negative behavior:

```python
profile = build_dashboard_runtime_instance_profile(
    repo_root=tmp_path, workspace_root=tmp_path, port_profile="worktree-1",
)
assert set(profile.service_ports) == {"django", "grafana", "external-litellm"}
assert {item.service_name for item in profile.shared_consumed_bindings} == {"external-litellm"}
payload = profile.as_dict()
payload["schema_version"] = 1
path = tmp_path / "profile.json"
path.write_text(json.dumps(payload), encoding="utf-8")
with pytest.raises(ValueError):
    read_dashboard_runtime_instance_profile(path)
```

   `tmp_path` is pytest-owned. This must fail against schema 1 before implementation.
3. Use existing `ServiceSpec.from_values(...)` and SLE identity records for
   `manage.py serve --host 127.0.0.1 --port <owned port> --stop-file <owned file>`.
   Concrete port/path values come from the profile/launch record, not a fixed
   global TEMP PID file or whichever process happens to listen.
4. Configure the service `stop_command` to create its owned stop-file.
   `stop_runtime` calls `stop_service(spec.name,
   graceful_timeout_seconds=spec.graceful_timeout_seconds)` per service;
   Dashboard waits at least 15 seconds, Grafana retains its own bound.
   Apply this on restart as well as stop. Do not pass a blanket 5-second bound.
5. PowerShell entrypoints become thin callers of the existing lifecycle owner.
   Preserve practical Workspace/Port/Action inputs; remove retired AI Base
   options rather than silently ignoring them. Hidden launches stay hidden.
   Local backend start/stop stays backend-only; it must not initialize demo
   data, migrate the database or import Grafana content as an incidental action.
   Use the explicitly selected runtime Python or the fresh `.venv-embedded`
   convention; a missing interpreter fails, never falls back to retained `.venv`
   or arbitrary PATH Python. Propagate native nonzero exit codes.
   The editor task registry is also an entrypoint. Route its stack actions
   directly to the canonical script; remove obsolete convenience wrappers and
   their task references. Cross-worktree stop invokes current code against
   registered target profiles, without executing an older target-worktree script
   or recovering ownership from a port. Enumeration and per-target failures
   must reach the caller; remaining registered targets are still attempted.
   Normal operations never request `force_by_port` or kill a process tree
   selected only by port. Refuse a foreign listener or safely choose another
   approved port; never adopt it.
6. On Windows, `terminate_process` is also forceful. Normal-stop acceptance
   requires the stop-command path and zero child exit; `terminated`/`killed`
   are abnormal even if the generic `StopResult.forced` flag is false.
   Report the actual forced PID and method without conflating `force_requested`.
   Change generic SLE code only for a proven reusable defect, with neutral tests
   and its package `AGENTS.md`; do not hardcode Metrics into SLE.
   The actual Grafana stop path reproduced forced termination instead of a
   cooperative stop. A **new** generic `service_lifecycle_engine/controlled_stop.py`
   may support its existing `ServiceSpec.stop_command`, using persisted process
   identity and a targeted Windows process-group control event. Keep windows
   hidden, reject wrong/missing identity or undeliverable control, and never
   broadcast into a shared console. This is a SLE primitive, not another host.
   Standard Dashboard/Grafana stop must pass normally; deliberate stuck-process
   scenarios separately prove abnormal escalation and nonzero caller status.
   Preserve the actual stopped-service exit status, not only the stop helper's
   or PowerShell wrapper's status. A **new** generic SLE `process_exit.py` can
   retain existing child handles or a Windows process handle for this observation;
   it owns no process registry or launcher. Unknown/nonzero service exit cannot
   satisfy a normal-stop assertion. Record it in termination evidence and test
   a cooperative worker that deliberately exits nonzero.
7. Update process/boot audits to recognize `serve` and its provenance, not
   runserver or missing AI Base processes. Keep stdout encoding-safe.
8. Exercise each real entrypoint on controlled synthetic data, then its real
   stop entrypoint. Prove a deliberately unrelated listener remains alive;
   prove wrong PID/command/start identity refuses stopping; prove a stuck owned
   process is force-stopped only after its grace interval and labelled abnormal.

**Exit:** `V2`; no new process manager, no extra AI Base process, all owned
services cleanly stopped after the qualification run.

## W1.RETIRE

1. Remove `metrics/wsgi.py` and `WSGI_APPLICATION`; retain only the `serve`
   composition. Reconciliation found `metrics/asgi.py` was still present despite
   the older task note, so remove that standalone entry as well. Do not add aliases.
2. Implement **new** `scripts/check_embedded_runtime_boundaries.py` and
   `scripts/check_retired_ai_paths.py`, with corresponding **new**
   `scripts/tests/test_embedded_runtime_boundaries.py` and
   `scripts/tests/test_retired_ai_paths.py`.
3. Boundary checker: use Python AST/import nodes, enforce original 1.4 and
   scoped `asyncio.run` rule. Ordinary test fixtures are not production
   import violations; enumerate their separate classification.
4. Residual checker: implement original 9.5(a/b/c) inventories. Classify exact
   Linux deployment paths as deferred in the Windows report, never as passed
   under the whole-repository original gate. Active Windows references to an
   obsolete interface always fail; test literals/history are evidence only.
   Missing target roots and a zero-file scan fail.
5. Prove three independent mutations: legacy route/config in code, forbidden
   import/asyncio call, and current operator docs pointing to a retired startup.
   Add wrong-scope and ignored-directory negative cases.
6. Reconcile remaining 5.7/5.9/8.1 consumers from source and the clause census.
   Keep current typed factories; do not recreate deleted DTOs because an old
   task names their migration-origin filenames.
7. Update README Windows installation/start/stop, runtime-isolation guide,
   runbook, current Grafana/AIB architecture and reporting documentation.
   Remove unused external-runtime URL projections from the profile and stack
   wrapper; update default stack smoke to the current server-rendered workflow
   form. Generated fixture commands must remain parseable PowerShell literals.
   Describe existing Linux recipes as deferred/unqualified; do not delete their
   definitions or silently mark the Docker task complete.

**Exit:** `V3`; current Windows startup/configuration/consumer paths are coherent,
and deferred original criteria remain visible in the task ledger.

## Wave Review And Replan

For `W1.R`/`W2.R`, freeze source, run affected checks and submit one scoped
independent behavior review. Close all findings; publish a scoped local commit.
The same bounded review session can produce the downstream `REPLAN` assessment:
compare the remaining plan to actual interfaces, fixtures and results, check
the next wave's first negative test and list continue/amend/supersede/retire.
Reconcile DAG/table/ledger before opening the next wave. No repeated broad
testing for receipt-only or wording-only updates.

## W2.VA

W1.REPLAN classifies W2 as **amend**, with W3 continuing after the amendment.
The historical `serve_baseline.py` still calls a retired command. Before W2
implementation, approve a test-only adaptation of the original threaded
`WSGIServer` + `StaticFilesHandler` baseline. Keep its same current Django
settings, synthetic page/report fixtures, route and asset set, authentication
posture and sample recipe. Do not restore a production command or SDK path.
Record the mapping to the original source and its hashes. If that mapping
cannot preserve the signed comparison, obtain the owner's decision first.

Use `V4`-`V8`, `V10`-`V11` and the exact original 5.10/10.4 clauses. Validate the ability to
deliver native Windows control events to an owned child, block/release a loop,
hold streams, measure first-byte/inter-arrival timing, exercise stdout stalls
and record whole-machine CPU/process snapshots. A helper process can be used
only as a test fixture, not an alternative production host.

Approve exact fixtures before long runs. Establish the comparison baseline
from S0b's same Django/settings/assets route set and sampling method; a different
baseline or relaxed threshold needs owner approval, not an agent substitution.
Unavailable native Windows measurement is a blocker, not a skip.
Approve the migration/aggregate-checker negative fixtures here as well; their
scripts are produced in W2.HOST so W3 runs frozen tools instead of writing them
after the final source/fixture freeze.

## W2.HOST

**Modify:** `ai_host/settings.py`, `state.py`, `wiring.py`, `lifecycle.py`,
`management/commands/serve.py`, `manage.py`, relevant settings and project-runtime
stop contract if needed to meet the already approved design.
**New:** `ai_host/serve_control.py`, host tests named in `V4`-`V7`,
`scripts/validation/windows_host_qualification.py`, `windows_migration_rehearsal.py`,
`qualify_ai_runtime.py` and their named checker tests under `scripts/tests/`.

1. Implement binding policy before acquiring runtime resources: loopback
   classification per design decision 3; development anonymous-approval posture
   refuses non-loopback; unconfigured Basic users on permitted production
   non-loopback bind emit only the approved address warning.
2. Preserve prebind-before-runtime-import/check semantics and Waitress socket
   ownership. Set `WHITENOISE_AUTOREFRESH=False` explicitly and document restart
   after static changes. Monitor `handle.ended` within 0.5 seconds; latch failure
   state/end_code and run the same cleanup, never leave a dead runtime served.
3. Extend the existing host lifetime owner, not another runtime engine.
   `serve_control.py` contains the host's monotonic stop budget/watchdog support;
   `lifecycle.py` remains the ordered cleanup owner; `wiring.py` tracks admitted
   responses until iterator `close()`, not merely application return.
4. Implement design decision 2 section 7 literally: stop listener on the Waitress
   loop; close runtime HTTP by t0+2; drain by t0+3; flush until t0+6.5; close/join
   HTTP by t0+7.5; request/await project stop; clear/detach; finish runtime context;
   inventory and explicit exit. Continue later cleanup after earlier errors.
5. Watchdog starts at t0+9.2; an active project run expands to t0+659.2; after
   `wait_stopped(620)` returns at T, tighten to min(current,T+1.2). Every main
   wait is sliced at most 0.5 seconds. Watchdog output gets at most 0.1 seconds
   in a helper thread before hard exit 3, even if stdout is blocked.
6. Before Django import, record exit callback ownership as specified by R24-host.
   Inventory callbacks, non-daemon threads, child processes, finalizers and
   handlers; explicitly run required cleanup and fail unknown/failed entries.
   Do not add an allowlist entry merely to make a failing inventory pass.
7. All serve exits perform required cleanup/output then `os._exit`: normal 0;
   bind/start/runtime failure 1; cleanup failure overrides with 3; second signal
   after any stop trigger gives 130 within one second. Test in child processes
   so `os._exit` cannot terminate pytest.
8. Add only missing cross-stack assertions to the explicit conformance lane.
   Keep testkit plugin/mode out of root pytest configuration. Cover body
   chunking, IPv6/configured Host, anonymous-approval refusal, auth under
   saturation, resource return and blocked-loop behavior using the real host.
9. Implement the bounded migration and aggregate qualification tools described
   under W3 below. Unit-test wrong snapshot ownership/hash, mixed source identity,
   missing mandatory rows and command failure now; do not run the final rehearsal
   or broad browser bundle yet. Tools reuse existing host/store/test runners.
10. Commit the complete host implementation after focused negatives/consumers
   pass, before timing measurement. No AIB wheel change unless a reproduced
   runtime defect and its separate authorization require it.

**Exit:** implemented design obligations plus `V4`-`V7` focused evidence; not yet
10.4 performance acceptance.

## W2.CERTIFY

1. Run the complete registered Windows conformance lane and all added Metrics
   cases. Map every original required clause to actual testcase/receipt IDs.
2. Run the native qualification driver against actual `serve` and the pinned
   runtime, not the S0b adapter. Follow `V8`'s exclusive interval and thresholds.
3. For each scenario retain raw samples, terminal event/client observation,
   server process exit and ownership cleanup. A passed command without the
   semantic payload or missing sample is a failure.
4. On failure preserve the run, return to the owning W2.HOST test or W1 launcher
   test, repair the class, and requalify affected scenarios. No threshold changes.
5. Only after all mandatory Windows rows pass may W2.R accept the package.

## W3.FREEZE

Record final Dashboard commit, exact AIB source/wheel/package files, Windows
constraints, fixture and relevant environment fingerprints. Reuse the already
qualified W2 candidate. Do not rebuild from the dirty AIB worktree.
A metadata-only release version still requires a fresh immutable artifact and
admission/affected installed checks; never overwrite dev4 bytes.

Any runtime-affecting change after this point returns through the appropriate
review/REPLAN gates. An evidence-only commit records its own SHA in the final
response or a later receipt, never self-references an unknown commit SHA.

## W3.REHEARSE

**Frozen tools produced by W2.HOST:** `scripts/validation/windows_migration_rehearsal.py`
and `scripts/tests/test_windows_migration_rehearsal.py`; reuse archive/path
ownership helpers and existing old/new host harnesses, not another lifecycle
engine. A harness defect returns to W2.HOST/refreeze rather than being patched
during final evidence collection.

1. Use the executable old baseline established in WIN.RECONCILE to generate
   synthetic old state. Stop every owned writer and snapshot DB, state root and
   archive together with one timestamp and complete file inventory/hash set.
2. Copy that set to a different owned destination. Reject wrong/missing markers,
   reparse escapes, mixed timestamps, mismatched source/env and changed hashes
   before touching it. Never operate on source originals or real user data.
3. Install the new frozen environment, run migrations against the copy, retire
   only copied `runtime/operations/`, update copied profile/config and start
   actual serve. Verify health, pane, session persistence across a new-host
   restart, retained publication data, `RUN_BUSY` and old active-wire refusal.
4. Legacy AI chat/approval/skills state is not imported into the new runtime
   (original Q8). Preserve its backup; do not claim old conversations migrate.
5. Stop the new host. Restore the complete old snapshot into another owned
   destination; start **old code with old dependencies/config**, verify original
   business records, then stop. Recheck every original snapshot hash unchanged.
6. Save argv, source/environment identity and all positive/negative results.
   Linux image restoration remains deferred; Windows executable restore does
   not claim the image clause of original 10.3 passed.

## W3.JOIN

**Frozen tools produced by W2.HOST:** `scripts/validation/qualify_ai_runtime.py` and
`scripts/tests/test_qualify_ai_runtime.py`, a fail-closed test/evidence launcher.
It calls existing admission/testkit/pytest/browser checks, not another SDK.

1. Qualifier admits candidate and runs `pip check` before starting test services.
   Execute the manifest-selected gates in `V11`; preserve exact argv/returncodes.
   Mutated candidate, missing mandatory suite, empty selection, stale fingerprint,
   inconsistent testcase inventory or any failure returns nonzero.
2. On the frozen final environment run real Workbench session/context and
   publication browser tests, actual task-run/assist recovery, and final broad
   required module gates. Local Grafana must render the expected timeline/data,
   not merely acknowledge import.
3. Verify approved publication/audit correlation, repeats without extra model
   dispatch/import, refused/failed operations without publication, normal stops
   and no owned descendants/listeners. Keep state/data isolated per case.
4. Combine existing unaffected evidence and these fresh results through the
   coverage census. Different candidates or changed dependencies cannot be
   combined by adding their pass counts.

## Close And Delivery

`CLOSE.R` independently verifies the finite V0-V11 coverage table, both source
identities, code/doc agreement, all required findings and preserved deferrals.
`WIN.ACCEPT` writes **new** `evidence/windows-acceptance.json`, containing one row
per original Windows clause and its evidence. Close original task checkboxes
only where every original clause is met; partial Linux/global tasks remain open.

Report the four-goal Windows milestone separately from whole-AIB qualification.
`DELIVERY` waits for named owner authorization before push, merge or worktree
retirement. Verify remote SHA only after an authorized push; preserve all AIB
other-App WIP. Never delete a checkout merely because the Windows packet passed.

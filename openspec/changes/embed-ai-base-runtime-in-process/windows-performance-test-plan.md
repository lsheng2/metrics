# Windows Performance Implementation And Test Plan

> For agentic workers: use `superpowers:executing-plans` for the steps below.
> Execution status exists only in the existing `tasks.md`, not this document.

**Goal:** Measure and, where evidence requires, improve the Windows Dashboard
embedded-runtime composition without weakening functional contracts or KPIs.

**Architecture:** Reuse the current native host, the approved threaded WSGI
comparison fixture and the existing sample/process/transport helpers. Add a
small performance producer and semantic checker, not a second runtime,
process manager, benchmark framework or legacy host interface.

**Tech Stack:** CPython 3.13.7, the frozen dev4 wheel and matching dependency
pins, Django, Waitress, httpx, SLE, pytest, Windows counters and conditional ETW.

**Spec:** [performance phase](windows-performance-phase.md);
[signed V8 method](windows-close-validation.md#v8-native-measurement-method);
[research](windows-performance-research.md); [DAG](windows-close-dag.json).

## Global Constraints

- Windows only; synthetic state, loopback endpoints, no real providers/models.
- Source baseline: Dashboard `eb84aa23a123a191d4b5f6569e69e3d00d75268b`;
  AIB main `6591ad57f15c78f575cf43dd5d7d3e076df99f7b` is context, not the wheel.
- Measured wheel: dev4, SHA256
  `b332f338f77bf2e966de7495eea6b5968606eb670287588d97a3a4d82905ec94`.
- No inherited dotenv or `ai_base_runtime` source-import fallback; exact
  installed artifact admission and dependencies are checked before and after
  measurement. Dashboard validation/application code comes from the declared
  source repository, not from an undeclared checkout.
- Root `D:/AIGC/pf1120` owns environment, inputs, temporary state and evidence.
  `$python` below resolves to `D:/AIGC/pf1120/venv/Scripts/python.exe`.
  Every command below runs from `D:/AIGC/scrum_dashboard`.
- Tests set `TEMP` and `TMP` to `D:/AIGC/pf1120/temp`; clients bypass proxies
  for loopback. Path depth is controlled without changing archive format.
- Existing stop, cancellation, persistence, approval, quota, auth, 10-second
  normal-stop proof and emergency-exit contracts stay unchanged.
- KPI-P1 through KPI-P4 and the exact recipe in the phase document remain
  unchanged. Additional diagnostic counters are not acceptance thresholds.
- Preserve old failures and immutable accepted receipts. Fresh results name
  their own source, installed package, fixture and environment identities.
- One repository writer. No tests, profilers, environment installation or Git
  writes run concurrently with a measurement window. Only owned resources stop.

## Approaches And Selection

Selected: repair and reuse the signed native benchmark; layer targeted
diagnostics only after a reproducible outlier. This preserves comparability
and keeps instrumentation cost out of the primary latency measurement.

Not selected: replace the measurement with a new load-test framework, which
would require a new baseline/method approval; or run broad always-on ETW,
which previously produced large, sometimes lossy captures without a reproduced
failure. Neither addresses the currently identified measurement gaps.

## Contract Registry And Propagation

These are refinements of existing `INV-6`, not new runtime contracts.

| Contract | Risk | Authoritative producer | Consumers | Disconfirming check |
| --- | --- | --- | --- | --- |
| PERF-IDENTITY | high | Frozen input plus `ai_host/runtime_artifact.json` and `windows_host_performance_contract.py` | performance driver, semantic checker, aggregate qualifier | Wrong source, wheel, dependency set, baseline or fixture digest is refused before starting children |
| PERF-RECIPE | high | Repo-owned certify/pilot recipe in `windows_host_performance_contract.py` | probe fixture, sample/transport collectors and evidence checker | Eight frames, echo-only probing, caller-selected smaller certify recipe or missing production phase fails |
| PERF-INTERVAL | high | Raw block/slot/stream timestamps and identities | page/transport validators and native receipt checker | Fast pages copied from another run, missing slot, stale frame, malformed timestamp or non-overlapping saturation fails |
| PERF-WINDOW | high | `MeasurementWindow` owner id and Windows observations | driver, final receipt, checker | Foreign Metrics workload, wrong guard, source drift or verdict after guard release fails |
| PERF-CLEANUP | high | SLE identities, terminal process observations and socket/listener checks | child/phase receipts, final checker | Parent exit with surviving child/listener, PID reuse, unknown exit or force cannot be normal |
| PERF-CLAIM | high | Dedicated performance semantic checker | `windows_qualification_evidence.validate_binding`, full qualifier and docs | JUnit-only, conformance-only, pilot/diagnostic, partial or forged PASS cannot establish performance |

Source owners are `scripts/validation/windows_host_*.py`, the performance-only
test fixtures and their named tests. The aggregate consumer is
`scripts/validation/windows_qualification_evidence.py`; its consumer tests must
exercise real semantic routing, not monkeypatch it into a success label.
Existing conformance/native receipts retain their schema and checker.

Sibling surfaces: development/production, seq/c4, baseline/candidate/saturated,
loop-short/direct-asset/excess, normal/failure cleanup, standalone/aggregate
validation, and functional/performance test consumers of `RuntimeProbe`.
No authority is migrated into UI code, a provider adapter or a second journal.

## Consumer Universe

| Category | Disposition and concrete boundary |
| --- | --- |
| Public API | Applies as unchanged measured `/ai` routes and assets; no SDK/API signature change |
| Internal service/facade | Applies to actual `serve`, WSGI bridge and idle project runtime |
| UI route/template | Applies as six unchanged measured pages and their assets; UI redesign is not included |
| Export/report | Applies to synthetic report fixture and JSON performance receipts, not business exports |
| Audit/log/event | Applies to owned timings, process observations and sanitized access logs |
| Validation script | Applies to the native producer, evidence checker and full-profile consumer |
| Migration/schema | Not applicable: no product schema or user-state migration |
| Background job | Applies only to the real idle project worker; no scheduler activation |
| Cache/index/search | Applies to declared warmup and static configuration; no cache policy change |
| External artifact | Applies to immutable dev4 wheel, installed files and private traces |
| CLI/admin | Applies to performance validation CLI; ETW elevation is conditional and collector-only |
| Docs/operator | Applies to this plan, phase, DAG, sole ledger and reporting-delivery guide |
| Test double/fixture | Applies to synthetic provider/model boundaries and the approved baseline adaptation |

## Execution Nodes

This is the performance continuation subset of the complete 28-node DAG;
the earlier functional nodes retain their completed evidence and state.

| Node | Depends on | Deliverable and exit criterion |
| --- | --- | --- |
| W3.REPLAN | FUNC.ACCEPT | Research, this plan and structured refreeze independently reviewed; no remaining plan blocker |
| PERF.KPI | W3.REPLAN | Signed recipe, baseline architecture and execution environment pinned; no new threshold |
| PERF.PROBE | PERF.KPI | RED/GREEN tool-integrity checks, faithful native equivalence, a labelled pilot and a full diagnostic run |
| PERF.PROBE.R | PERF.PROBE | Independent review of implementation, raw diagnostic evidence and functional impact |
| PERF.PROBE.REPLAN | PERF.PROBE.R | Classify next wave as continue/amend/supersede/retire from measured evidence |
| PERF.OPTIMIZE | PERF.PROBE.REPLAN | One evidenced owner fix plus regression, or explicit no-change decision after full valid passing measurements |
| PERF.OPTIMIZE.R | PERF.OPTIMIZE | Changed functional consumers and candidate identity reviewed |
| PERF.CERTIFY | PERF.OPTIMIZE.R | Fresh exclusive full recipe and read-only semantic replay pass |
| CLOSE.R | PERF.CERTIFY | Independent bounded Windows evidence review |
| WIN.ACCEPT | CLOSE.R | Combined result only after actual full-profile consumer accepts current functional and performance evidence |

```mermaid
flowchart LR
    F["FUNC.ACCEPT"] --> R["W3.REPLAN"] --> K["PERF.KPI"]
    K --> P["PERF.PROBE"] --> PR["PERF.PROBE.R"]
    PR --> RR["PERF.PROBE.REPLAN"] --> O["PERF.OPTIMIZE"]
    O --> OR["PERF.OPTIMIZE.R"] --> C["PERF.CERTIFY"]
    C --> CR["CLOSE.R"] --> W["WIN.ACCEPT"]
```

### PERF.KPI: Freeze Without Retuning

1. Verify the original dev4 wheel and create a separate environment from the
   same 83 package versions. Run `pip check` and installed-origin admission.
2. Pin source commit, clean status, interpreter/dependency fingerprint, wheel,
   fixture/source file hashes, W2.VA/S0b references, OS/machine and clock data.
3. Preserve the baseline `ThreadingMixIn`/Django `WSGIServer`/
   `WSGIRequestHandler`/`StaticFilesHandler`, 0.5-second server timeout and real
   idle worker. Current routes/seed/assets/report fixtures are shared.
4. Freeze the method and fixture specification at PERF.KPI. PERF.PROBE
   implements fixture materialization and resolves dynamic route IDs and asset
   hashes during guarded setup, before warmup or accepted samples. Write a
   separate immutable resolved-input artifact then; the final receipt binds
   both the initial request and this materialization. There is no dependency
   on an unimplemented driver to finish the design-only PERF.KPI gate.
5. The committed `evidence/windows-performance-inputs.json` is a portable
   manifest of pinned policies and references. Per-run immutable inputs under
   the private root additionally bind concrete source SHA, paths and environment.
   A commit does not embed its own SHA; reports name the final source commit.

## Producer And Consumer Data Contract

The per-run request extends the existing `windows_qualification_inputs`
schema: `schema_version`, `acceptance_profile=full`, `source`, `owned_root`,
`python`, `candidate`, `fixtures` and `checks` retain their meanings and
validation. Its required `performance` object contains `recipe_id`,
`policy_ref={path,sha256}`, `functional_acceptance_ref={path,sha256}` and
`mode`. Mode in argv and input must agree. The repo-owned recipe id is
`windows-mdb2-s0b-r1`; it fixes all counts and thresholds in the phase document.

The performance receipt uses `schema_version=1`,
`kind=windows-host-performance`, `phase=performance`, `mode`, `status`,
`collection_status`, `violations`,
`acceptance_eligible`, `producer_input={path,sha256}`, `source`,
`candidate`, `environment_before`, `environment_after`, `resolved_inputs`,
`measurements`, `measurement_window`, `cleanup` and `errors`.
Every referenced artifact uses `{path,sha256}` inside the owned run directory.
`resolved_inputs` and `measurements` each have exactly `development` and
`production` entries. Resolved inputs bind actual page URLs, asset hashes,
seed/fixture identity, auth differential, interpreter and installed origins.
Measurement files retain the existing `pages`, `blocks`, `spacing` and
`saturation` structures, with complete identities/timestamps added.
Collection integrity and numerical outcomes are distinct: a complete diagnostic
with a KPI violation can inform optimization, but cannot be acceptance.
Preserve all cell results and violations, not only the first failing ratio.
Abort on functional, ownership or collection-integrity failure; do not abort
the prescribed remaining diagnostic cells solely to discard a slow result.

Only mode `certify`, status `PASS`, empty errors, unchanged identities and
successful raw-data/window/cleanup recomputation make `acceptance_eligible`
true. The checker derives that conclusion and never trusts the supplied flag.
Pilot/diagnostic receipts may report completed collection, but are always
ineligible. A `native` alias or a functional conformance kind cannot bypass
the dedicated performance checker.

Finalization order is: stop children normally; verify terminal identities and
listeners; finish CPU/source/environment checks; write the window and final
verdict while the guard matches; release only the owned guard; return the
process outcome. A finalization/release error records FAIL before returning
nonzero. In-progress files may be finalized to failure; after the producer
has exited, its result and raw artifacts are immutable. No historical receipt
is rewritten. Tests must exercise write/release failures explicitly.

### PERF.PROBE: Correct The Measurement Chain

Owned files are enumerated by this node in the JSON DAG. Keep modules cohesive
and below their existing size limits; split new producer/contract/checker files
by those responsibilities, without modifying the size policy.

Interfaces to retain or implement:

```python
RuntimeProbe(*, spacing_events=8)  # Existing functional default is unchanged.
host_probe(
    ai_host_factory, ai_server_factory, ai_clock_and_limits,
    *, config=None, spacing_events=8,
)  # Performance callers explicitly select 50.
load_performance_request(input_arg, output_arg, *, mode) -> dict
run_performance(request, *, mode) -> dict
validate_performance_result(receipt, request) -> dict
validate_bound_receipt(key, path, request) -> dict
```

`windows_host_qualification.py` retains `--phase conformance` and dispatches
`--phase performance` to the new producer with required
`--mode pilot|diagnostic|certify`. This is a validation-tool interface, not a
runtime public API. No caller may supply arbitrary KPI or sample-count values.
The current argv authority is the
[planned tool table](windows-close-validation.md#planned-tool-interfaces);
the concrete commands below instantiate it, not a separate interface.

1. Add falsifying tests for the recipe and raw evidence before changing helpers.
   Example discriminators:

```python
def test_b3_eight_frames_cannot_satisfy_performance():
    payload = valid_performance_payload()
    payload["spacing"]["indices"] = list(range(8))
    with pytest.raises(ValueError):
        validate_transport(payload)

def test_b9_echo_only_cannot_satisfy_performance():
    payload = valid_performance_payload()
    payload["saturation"]["probes"] = [
        p for p in payload["saturation"]["probes"] if p["kind"] != "direct_asset"
    ]
    with pytest.raises(ValueError):
        validate_transport(payload)
```

   `valid_performance_payload` belongs in the new performance test-support
   module and builds the complete repo-owned recipe. It is never a production
   data source or a substitute for real native collection.
2. Add the explicit 50-frame performance profile while preserving the existing
   eight-frame functional fixture. Adapt both native entry and the separate
   performance conformance consumer; rerun affected functional probe tests.
3. Discover the direct runtime asset through the authenticated embedded page.
   Pair loop-short and direct-asset probes by scheduled slot; bind URL, start,
   completion, HTTP status, content identity and admission/reclamation evidence.
4. Preserve raw per-sample and block times, stream events and complete slot
   identities. Validate the complete interleaved schedule and overlap with the
   held-stream interval. Duplicate/bunched replacement slots are not coverage.
5. Exercise direct readiness with BadStatusLine, RemoteDisconnected and
   IncompleteRead. Use the existing bounded poll contract; do not extend its
   deadline, hide invalid metadata or ignore an exited process.
6. Extend cleanup proof through existing SLE/process ownership: preserve
   creation identities and terminal observations, then verify no owned listener
   or descendant remains. Do not count a forced cleanup as normal.
7. The driver owns guard acquisition through final verdict. After children
   stop, collect final source/environment/window checks, then write the verdict
   while the guard still matches. Only then release the guard. A release or
   cleanup failure cannot leave the authoritative receipt marked PASS.
8. Classify Windows process observations as owned measurement processes,
   tooling unrelated to the Metrics workload, foreign Metrics workload or
   unresolved identity. Reject foreign/unresolved relevant workloads before
   certification. Persist classification, executable/creation identity and
   command fingerprint, not credentials or unrestricted command-line contents.
9. Add producer-owned native performance evidence routing. Bind source, recipe,
   environment, candidate, fixture, each raw artifact hash, complete phases,
   window and cleanup. Standalone and aggregate validators recompute from raw
   evidence and reject partial files or caller-supplied success labels.
10. Run native equivalence in both settings modes, then one pilot:
    all six pages, seq/c4, all three arms, one warmup and one block of five
    samples per cell; B3 still has 50 frames, and B9 still has both probe kinds.
    Pilot output is explicitly NOT_QUALIFIED and cannot map V8 evidence keys.
11. Compare pilot durations with the unchanged fixture safety lifetime before
    the full diagnostic. If the prescribed recipe cannot finish within that
    harness bound, replan the observation mechanism; do not call a truncated
    run valid or silently enlarge a production budget.
12. Freeze clean tool/source bytes and run the complete signed diagnostic
    recipe without a profiler. Preserve every outcome. This is the measurement
    input to the independent probe review, not certification.

### PERF.OPTIMIZE: Root Cause Before Change

For each reproducible failure, record the affected metric/cell, raw samples,
source and input identity, hypothesis, a counterexample and a single-variable
experiment. Separate HTML, assets, runtime loop/queue, scheduler and storage
cost; setup or pytest duration is not response latency.

Use a short user-mode span/cProfile experiment for an evidenced Python owner;
use kernel CPU/ready/wait/FileIO capture only for an evidenced scheduling or
I/O question. A paired unprofiled control is mandatory. No automatic broad
Minifilter capture or py-spy-based KPI conclusion.

An `ai_host` fix requires focused RED/GREEN plus the affected stop, transport,
auth and joined consumer checks. A fix in AIB, Django/report owners, third-party
code or global machine settings requires a scoped refreeze/owner decision
before mutation; do not patch the installed wheel or expand this node silently.
A new AIB candidate requires its own source/wheel pin and Dashboard reacceptance.

Two equivalent failures without new information trigger a new hypothesis or
instrumentation. After 60 minutes on one question, narrow or replan. If no
current problem is reproduced and all complete diagnostic KPIs pass, record
no product change rather than manufacture an optimization.

### PERF.CERTIFY And Combined Closure

1. Freeze the reviewed candidate/tooling and input manifest. Stop other owned
   Metrics tasks; unresolved foreign work is a coordination blocker, not
   permission to kill somebody else's process.
2. Run a fresh unprofiled full recipe in both settings modes, preserving
   all 11,520 page-plus-assets samples, 48 candidate/baseline cell comparisons,
   complete B3 and same-interval B9 observations. The count excludes warmup.
3. Run the producer-owned checker against the stored receipt. Recompute all
   criteria, including normal cleanup and final guard/source observations.
4. Use the existing full-profile qualifier only with evidence it actually
   accepts. Historical `ff09d6f` functional bindings must not be relabelled as a
   new commit. Reuse needs the existing validator's supported identity rules;
   otherwise run the required current-source native/mapped/module producers.
   Cross-source reuse is not silently added as a performance shortcut.
5. Independent CLOSE.R checks both current applicability and remaining global
   deferrals. Only then issue WIN.ACCEPT; push/release remain separate.

## Test Matrix And Exact Executors

Use the pinned `$python`, `-I -B`, explicit test paths and the no-dotenv runner.
Every invocation records argv, cwd, interpreter identity, exit code and raw
stdout/stderr/JUnit hashes. Nonzero exit, timeout, zero selection, unexpected
deselection or skip cannot become a passed test lane.

| Tier | Target files | Positive control | Required negatives |
| --- | --- | --- | --- |
| T1 recipe/math | `scripts/tests/test_windows_host_qualification.py` and `test_windows_performance_evidence.py` | Complete raw 50-frame/full-cell fixture | Eight frames, missing asset probe, NaN/Inf, reversed time, duplicate/missing index, partial phase, p95 threshold boundary |
| T1 provenance | `scripts/tests/test_windows_performance_inputs.py` | Correct native request/receipt | Wrong source/wheel/env, unowned path, reparse escape, false PASS, diagnostic promotion, stale or edited raw artifact |
| T1 window/cleanup | `scripts/tests/test_windows_performance_window.py`, `test_windows_performance_processes.py` | Guard remains through verdict; normal owned exit | Foreign relevant process, unknown identity, early guard removal, source drift, writer failure, leftover child/listener, PID reuse, force |
| T2 consumers | Existing qualification/profile/native tests | Performance kind routed to its actual semantic checker | JUnit/conformance substitution and full-profile promotion without all required evidence |
| T3 governance | Existing size/whitespace/OpenSpec plus DAG preflight | Nonzero owned path count, matching graph/ledger | Missing owner, unknown dependency, cycle, stale expected count, changed original census |
| T4 native | `ai_host/tests/test_windows_baseline_equivalence.py`, separate performance conformance file, pilot/full driver | Real baseline/serve with installed package, production assets and normal cleanup | Readiness protocol family, incorrect static auth differential, invalid fixture and no-dispatch failure |

Initial focused harness invocation, before native workloads:

```powershell
& $python -I -B scripts/validation/run_report_authoring_tests.py scripts/tests/test_windows_host_qualification.py scripts/tests/test_windows_performance_evidence.py scripts/tests/test_windows_performance_inputs.py scripts/tests/test_windows_performance_window.py scripts/tests/test_windows_performance_processes.py scripts/tests/test_windows_qualification_profiles.py scripts/tests/test_qualify_ai_runtime.py -q --tb=short -p no:cacheprovider -o asyncio_default_fixture_loop_scope=function --basetemp D:/AIGC/pf1120/temp/unit-r1 --junitxml D:/AIGC/pf1120/evidence/unit-r1.xml
```

Native support lanes run serially, never during a performance window:

```powershell
& $python -I -B scripts/validation/run_report_authoring_tests.py ai_host/tests/test_windows_baseline_equivalence.py -q --tb=short -p no:cacheprovider -o asyncio_default_fixture_loop_scope=function --basetemp D:/AIGC/pf1120/temp/equiv-r1 --junitxml D:/AIGC/pf1120/evidence/equiv-r1.xml
& $python -I -B scripts/validation/run_report_authoring_tests.py ai_host/tests/conformance_runtime_cases.py ai_host/tests/conformance_performance_cases.py -p ai_base_runtime.testkit.pytest_plugin -p ai_host.tests.conformance_fixtures -o ai_host_modes=blocking_wsgi -q --tb=short -p no:cacheprovider -o asyncio_default_fixture_loop_scope=function --basetemp D:/AIGC/pf1120/temp/transport-r1 --junitxml D:/AIGC/pf1120/evidence/transport-r1.xml
```

The producer commands use newly frozen inputs and fresh outputs:

```powershell
& $python -I -B scripts/validation/windows_host_qualification.py --phase performance --mode pilot --inputs D:/AIGC/pf1120/inputs/pilot-r1.json --output D:/AIGC/pf1120/runs/pilot-r1.json
& $python -I -B scripts/validation/windows_host_qualification.py --phase performance --mode diagnostic --inputs D:/AIGC/pf1120/inputs/diagnostic-r1.json --output D:/AIGC/pf1120/runs/diagnostic-r1.json
& $python -I -B scripts/validation/windows_host_qualification.py --phase performance --mode certify --inputs D:/AIGC/pf1120/inputs/certify-r1.json --output D:/AIGC/pf1120/runs/certify-r1.json
```

These are planned commands, not evidence that their files or flags already
exist. PERF.PROBE must implement and test them before execution.
Fresh retry names advance the suffix; no run overwrites an earlier result.

Pre-review/commit gates:

```powershell
& $python -I -B scripts/check_file_size_limits.py --include-untracked
& $python -I -B scripts/check_diff_whitespace.py --include-untracked
openspec validate embed-ai-base-runtime-in-process --strict --no-interactive
```

Command evidence taxonomy: the accepted executor is the pinned interpreter or
the installed OpenSpec CLI; positional paths must belong to the declared lane.
PowerShell variable resolution happens before recording the argv. Pipes,
redirection, shell substitutions, `;`, `||`, printed command strings and
unresolved placeholders are not executed-gate evidence. An external capture
wrapper may record stdout/stderr without changing the target argv or suppressing
failure. `--collect-only`, `--setup-only`, `--lf`, unexpected `-k`/deselection,
or a target named only as an option value cannot establish lane coverage.

## Review, Truth Sync And Stop Conditions

All six contracts are high risk because they govern external evidence and
qualification. PLAN.R uses the repo DAG review overlay with an explicit
authority/consumer matrix; implementation review uses authority-boundary
coverage. Derived numerical/status claims are pinned to raw-data validators;
research recommendations are advisory, not qualification.

Docs impact is validation/operations. Update this change and
`docs/development/reporting-delivery.md`; no product architecture, UI,
README installation command, SDK interface or AI routing policy changes merely
because the performance tool becomes executable. If an optimization changes
one of those surfaces, its refreeze must register the corresponding docs owner.
DCP deployment applicability is not applicable: no rollout or production data.

The optional Dashboard Debugger role is used only after a concrete failure.
The parent handles environment/probe execution; extra implementation agents
must never write the repository concurrently. Reviewers do not run benchmarks.

Do not proceed on unresolved plan findings, broken fixture equivalence, missing
source/package identity, incomplete raw evidence, a newly failing functional
contract, an occupied/foreign measurement window, source drift, or failed
cleanup. Do not invent a need to solve every historical intermittent failure
before collecting current unprofiled measurements. KPI changes, a new runtime
candidate, real-provider work, Linux and publication retain separate decisions.

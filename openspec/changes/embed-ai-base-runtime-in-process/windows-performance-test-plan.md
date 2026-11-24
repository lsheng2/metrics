# Windows Performance Implementation And Test Plan

The [2026-11-21 owner decision](windows-performance-phase.md#final-delivery-candidate-decision-2026-11-21)
requires latest-AIB candidate admission and renewed Dashboard functional evidence
before final performance certification. This plan's dev4 inputs and completed
experiments remain historical/frozen evidence, not qualification of the new
candidate. The signed workload and numerical thresholds are unchanged.

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

## Dev9 Reference Refreeze (2026-11-22)

The current baseline is Dashboard `5d15ddf3a8efeb84ae9518e72ab43277eff4d5d0`,
after dev9 functional acceptance at `423846c`. Use `D:/AIGC/d9-1122`, its
installed interpreter, `windows-functional-acceptance-dev9.json` and
`windows-performance-inputs-dev9.json`. This replaces only the historical
candidate/source/root references below. The dev9 wheel/source/hash are fixed
by the current phase amendment. The 83 dependency versions differ from the
signed method only for the runtime, after canonical package-name comparison.
`profile_source=repo-local`; `agent_routing_mode=multiagent-configured`.

W3.REPLAN/PERF.KPI must review this refreeze before PERF.PROBE continues.
The parent coordinates plan/policy/evidence; one Implementation Engineer owns
the validator/test slice, and an independent reviewer checks both validation
architecture and behavior. A separate debugger is unnecessary: the exact
input-path failure is reproduced and independently confirmed.

Restore the already specified producer/aggregate distinction. An immutable
producer input exists before its receipt; the later aggregate input binds that
receipt's SHA256. Requiring both input paths to be identical makes the final
full qualifier circular. Compare their stable identities instead, after
canonical-root/hash admission, schema/full-profile validation and the fixed
performance contract. Keep the original producer input/hash, raw measurements,
receipt SHA, write witness and every numeric/cleanup/window check unchanged.

| Contract | Producer and consumer | Required proof |
| --- | --- | --- |
| PERF-IDENTITY | Producer manifest -> performance contract/evidence checker -> full qualifier | Distinct immutable manifests with equal source, candidate, owner, fixtures, performance refs/mode and candidate interpreter/environment succeed; mutate each family and require refusal |
| PERF-CLAIM | Receipt/raw artifacts/witness -> standalone and aggregate replay | Input SHA and receipt SHA stay distinct; missing, stale, edited, outside-root, wrong-mode or non-certify evidence cannot become acceptance |
| PERF-RECIPE | Versioned dev9 policy -> request loader and sampling helpers | Baseline, full recipe and execution modes equal the original signed policy; old-candidate/nonmatching references are rejected, while byte-identical owned copies retain existing admission |

Add the distinct-manifest positive and sibling negatives to the existing
performance input/evidence/replay test owners. Replace abbreviated producer
fixtures with complete manifests; do not weaken checks to retain `{}` fixtures.
No runtime/SDK/UI/storage/API, KPI, timeout, leak or Linux change is part of
this correction. Reader docs change only for validation and operations.

After focused RED/GREEN and independent review, commit the reviewed changes before final input
freeze. Share that final source and fixture vector across certify and fresh
native/migration/mapped producers; do not relabel the earlier functional
source. The existing full qualifier supplies the final seven-module execution,
then CLOSE.R/WIN.ACCEPT. Another FUNC.ACCEPT loop is not required merely for
these validation-tool changes, but affected product changes would require
their own functional requalification.

## Process-Window Correction (2026-11-23)

Baseline `6e5aa244a45c515cf2516bcd4b2152aaae59d620` passed the prior
validator/input-adapter review and was published. Native equivalence passed
3/3 and transport/performance conformance passed31/31. Its first pilot
completed both settings' samples but failed the exclusive-window observer
during owned shutdown. Preserve that pilot and all original input bytes.

The native census and subsequent CIM query are not atomic. In the failed
window, two current-run processes had complete owned identities before stop;
the later query returned incomplete details after the stop request. A bounded
native diagnostic reproduced both incomplete detail and omitted PID outcomes.
The latter currently falls through to unrelated, so merely ignoring teardown
errors would also preserve a fail-open sibling. One PID was reused during
the run; a cached PID or name is not an identity.

This is a bounded amendment within PERF.PROBE, with repo-local profile and
configured independent review. Parent owns orchestration/docs; one
Implementation Engineer owns the observation/checker tests; the independent
Architect Planner Reviewer checks validation architecture before code and the
final behavior before another source freeze. No runtime optimization, SDK
publication, threshold, sampling cadence, stop/leak budget or Linux work is
included. DCP deployment remains not applicable.

| Authority | Producer -> consumer | Required behavior and negative check |
| --- | --- | --- |
| OBS-CENSUS | Native census/retained handle/CIM -> enrichment/classifier | Every Python/Git row has complete detail or an explicit error; omitted rows and malformed global JSON cannot become unrelated |
| OBS-OWNER | Current SLE/descendant admission -> window registration | Bind current run, PID, parent, image, exact native creation, command fingerprint and sensor identity while the handle is retained; reject missing, contradictory or reused identities |
| OBS-TERMINAL | Pre-CIM native handle -> current snapshot resolution -> final cleanup | Resolve only the registered exact incarnation with observed exit0; keep unknown/live/nonzero/forced/residual-process paths failing |
| OBS-REPLAY | Raw registrations/resolutions/cleanup -> performance checker -> full qualifier | Verify structured facts and their joins; a clean classification or new Boolean alone is not evidence |

Use a small internal `scripts/validation/windows_host_process_window.py`
for native read-only capture, owned by PERF.PROBE. Reuse existing read-only
native primitives and lifecycle observation patterns; do not change shared
SLE, app or SDK APIs. Existing environment, identity, process-registration,
cleanup and performance-evidence owners wire it together. Related window,
process, replay and shared performance fixture tests are the test owners;
new focused cases use `scripts/tests/test_windows_process_window.py` to keep
existing near-limit files within their configured size bounds.
Code-review correction keeps native acquisition in that helper and moves pure
replay checks to `scripts/validation/windows_host_process_window_evidence.py`.
Focused claim/admission/release tests use
`scripts/tests/test_windows_process_window_contract.py`; both paths belong to
the same PERF.PROBE authority, not another runtime or acceptance interface.
Replay derives required resolutions from raw observations even if summaries
are deleted. Persist the classifier's actual observed owned-identity input set
and privacy-safe command fingerprints. Replay the same owning classifier for
every raw row, including complete identities and unrelated tooling, and verify
all classifications, blockers and terminal facts. This preserves the approved
live admission algorithm rather than introducing a second classifier.
Root admission must match the original SLE start marker before
authorizing descendants. Failed observer release is a failing capture outcome,
not just a diagnostic field. Original real-CIM liveness assertions and their
observation bounds remain unchanged.

Acquisition order is native census, read-only handle and exact creation
identity, one CIM query, same-handle terminal observation, then deterministic
handle release. Unknown native identity or contradictory complete metadata
must fail closed. A terminal resolution requires a current-run owner
registration and the same native incarnation; it cannot erase a previous
blocker, pause observations during stop, or infer identity from PID alone.
Malformed global CIM output always blocks. Persist privacy-bounded versioned
registration and resolution facts in the run's window/machine artifacts.

Snapshot ownership and final normal cleanup are distinct. The sensor may
resolve a proven owned terminal incarnation immediately, without waiting for
every service stop. Before qualification, the owning replay checker also joins
that resolution to the same run's retained cleanup observations and verifies
exit0, no force, and no surviving descendants/listeners. Existing guard,
source, write-witness, raw timing and cleanup conditions remain mandatory.

T1 must falsify omitted/incomplete/malformed details, inaccessible handles,
live unresolved work, complete foreign commands, stale creation/PID reuse,
wrong parent/run/image/command, and exceptions during handle release.
T2 must exercise actual standalone and aggregate replay against forged clean
summaries, missing registration, changed incarnation, wrong-run or missing
cleanup, forced/unknown exit, and existing witness/source/guard failures.
T3 covers file ownership, unchanged28-node DAG, size/whitespace and OpenSpec.
T4 uses bounded real short-lived children and a stale registered creation
identity; do not attempt unbounded OS PID-reuse forcing.

Review this amendment before implementation. After RED/GREEN and independent
code review, publish the scoped correction, freeze a new input family, and
rerun native support/pilot before the unchanged full diagnostic and later
certification sequence. No historical failed window is reclassified. The
earlier input family and support runs retain their actual source identities.
Reader-doc impact is validation/operations only.

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
New raw per-run artifacts produced by the measurement tool, including resolved
inputs, measurements, window proof and cleanup proof, are stored under that run
directory and referenced by `{path,sha256}`. Producer inputs, the frozen
performance policy, the historical functional acceptance reference, wheel and
environment records retain the existing `windows_qualification_inputs` allowed
roots: declared repository or owned root, canonical path resolution, reparse
rejection and exact hash checks. Do not copy an environment or relax ownership
solely to move those external references into a run directory.
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
Bounded block artifacts are written as immutable per-block records during active
collection; the complete raw result is assembled after active sampling. Direct
asset probes bind to the resolved runtime asset prefix and record response-body
SHA256 separately from ETag metadata.

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

Replay also requires `receipt-write-witness.json` in the run directory. The
window's `ended_monotonic` closes process/source observation, not guard ownership.
The witness records actual write start/completion and a subsequent matching
guard observation; their order must follow that observation end. It binds the
final receipt path, bytes and SHA256 without a self-referential hash. Missing
targets, different supplied receipt content or missing raw facts fail closed.
The guard is released only after the witness is persisted. A witness/release
failure invalidates the producer result. Pre-write validation is internal
preparation only; standalone and aggregate acceptance require the witness.

Page assets are compared with each page's sanity observation; their union,
not every page, must equal the resolved arm asset manifest. The direct runtime
asset URL, content hash and size are materialized before warmup. Sample
intervals prove block/saturation membership; the KPI remains HTML HTTP plus
asset HTTP time, excluding parsing and hashing.

The performance adapter registers resolved launch intent before calling the
existing SLE `PlatformOperationSet.start_process`; seed commands use the same
predeclaration. Exact argv, current driver parent and canonical run-root
membership establish ownership before SLE's slower provenance capture publishes
`prepared`. Ambiguous or foreign roots remain failures; later registration
never erases an earlier foreign-workload error.
Persisted `prepared`/`ready` rows are not an alternate startup admission path:
they cannot prove a PID's current incarnation. Missing trailing asset probes
cannot shrink the coverage universe; derive mandatory slots from held duration
and require every observed slot, including the optional tail, to be complete.
Probe failures retain structured slot/resource/timing/error-class observations;
they still abort collection and never become successful latency samples.
Current-driver identity and matching launcher ancestry are separately observed,
so absolute command paths cannot self-block and do not whitelist another run.
Aggregate `sha256` binds the validated receipt; `producer_input_sha256` names
its input separately. Accepted-input producer errors publish a failed requested
output even before sampling. A late failure may invalidate a previous success
witness: fail-closed diagnostics do not receive a fabricated ownership witness.
The failure output includes `failure_artifacts` references for preserved
phase measurement/process/resolved files and final window/cleanup observations.
References are owned-run paths with actual SHA256s; absent partial artifacts
are not invented and old receipts are not rewritten to add them.

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

### Bounded Asset Localization Before A Full Retry

The first full diagnostic at source `93b0bea` was incomplete after three
direct-asset read timeouts. Its immutable evidence is retained under
`D:/AIGC/pf1120/runs/diagnostic-r1-performance-run`. This is a collection
failure, not a certified KPI result. A simultaneous page sample had ordinary
HTML timing and a seconds-long asset phase; the mechanism is not yet known.

Use a private, explicitly nonqualifying experiment before another full retry:

1. Reuse the admitted dev4, real `candidate_saturated` fixture, development
   settings, `bug_trend`, sequential page-plus-assets requests and four held
   streams. Keep ordinary request timeout configuration and production budgets.
2. Calibrate instrumentation with 40 samples and a 120-second sampling bound.
   Then use at most 4,000 samples or 600 seconds, stopping at the first
   read error or diagnostic 1,000-ms trigger. That trigger controls capture,
   not a replacement KPI; the ordinary performance recipe remains unchanged.
3. Use HTTPX response hooks for client header-arrival observations and retain
   every attempted request's identifier, path, start/end and exception class.
   Observe server WSGI entry/header boundaries and SDK resource resolution,
   manifest/asset materialization, and WhiteNoise opening, using monotonic and
   thread-CPU times. Do not wrap body iterators or change file-wrapper behavior.
4. Pair the real asset with an authenticated, same-byte memory control in the
   isolated test fixture. Run server-traced and untraced-server control modes.
   Never cache or replace the real SDK asset handler as part of instrumentation.
5. Buffer traces in bounded memory; report discarded prefixes explicitly.
   Preserve source/helper hashes, candidate identity, actual process ownership
   and normal cleanup. Do not capture authorization, cookies, query values,
   response bodies, private filenames or raw exception messages in spans.
6. Store private bootstrap/trace tools and results under the owned D-drive
   root, without modifying installed package files or production URLs.
   Their artifact kind is not `windows-host-performance`; all such experiment
   results have `acceptance_eligible=false`.

Interpret nested spans as overlapping observations, not additive costs.
Header logging is not body completion. A non-reproduction does not explain the
earlier failure. Only evidence localizing a reproducible owner may lead to an
optimization/refreeze; SDK, shared application or global machine changes keep
their existing owner decision boundary.

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

## Current Function Profiling Packet (2026-11-24)

The owner authorized the next
[bounded production HTML function profile](windows-function-profile.md).
It retains the boundaries below but narrows this new packet to production HTML,
adds request-local function observations and defines its own nonrenewable
320-second active allowance. It does not rerun or relabel the prior packet.

## Short-Latency Diagnostic Refreeze (2026-11-23)

The owner explicitly authorized a100ms **diagnostic capture trigger**, keeping
the SDK, all acceptance KPI, signed sample counts and production stop/leak
budgets unchanged. This supersedes only the1000ms trigger/current-target
selection of the older circular experiment below. It does not authorize
kernel collection, a product optimization or a new candidate.

Source `fa0b060` with immutable dev9 completed96 blocks/11520 page samples.
The original receipt and standalone semantic replay are retained under
`D:/AIGC/d9-1122`; PERF.PROBE.R passed1/1 with no findings. Collection/window/
cleanup passed, but development direct CSS119.3983ms and production sequential
draft_edit candidate/baseline P95 ratio1.58434 failed their unchanged limits.
Neither prior failures nor current functional proofs are relabelled.

The next wave is **amend**: first localize the short latency, then decide
whether an owner fix exists. PERF.OPTIMIZE cannot close as no-change from this
numerically failing diagnostic. The sole ledger and28-node DAG are retained;
`profile_source=repo-local`, `agent_routing_mode=multiagent-configured`.

### Bounded Packet

- Private versioned adapters live under `D:/AIGC/d9-1122/subsecond/`.
  Reuse the reviewed client/server timing and Windows clock helpers by copying
  them to the new directory; old helpers and installed package files stay
  immutable. Parent owns the runner, ordinary-token fixture and integration.
- Run one paired **trace/control** experiment. Each arm has at most300 seconds
  of active sampling, split into at most150 seconds per scenario:
  production sequential draft_edit without held streams, then development
  draft_edit with four concurrent page clients and four held runtime streams.
  Fixture setup, warmup, evidence harvest and normal stop are separately timed.
  Do not interpret results from a different setting as reproduction of a
  failed setting.
- A100ms individual request to the resolved HTML route or runtime CSS route
  triggers retention. Other static assets, memory-control requests and the
  total multi-asset page are not trigger targets. Retain the first matching
  request per scenario immutably; after normal in-flight completion, harvest
  that scenario before continuing. Every request/error is retained in bounded
  buffers with explicit prefix-loss counts; errors never become latency passes.
  First-trigger stopping censors exposure: cross-arm summaries report actual
  counts/durations and cannot claim an unbiased speedup or absence of profiler
  perturbation. Request ids join client/server records within an arm; they
  are not reused as cross-arm identities.
- Both arms have the same authenticated memory-control endpoint and client
  recording. Only trace enables in-memory server boundary timing. Never
  replace the real SDK asset route or alter file/response iterators.
  Warmup is unarmed. Validate status, bytes/hash, auth refusal and asset vectors
  before measured work. Use ordinary tokens, synthetic data and loopback only.
- Retain request id, exact process incarnation, native PID/TID, monotonic/QPC/
  precise-UTC brackets and thread CPU for matching client/server records.
  Windows clock helpers may run without ETW; no marker-API result claims a
  decoded kernel event. Missing clock/identity or a truncated matching interval
  prevents quantitative attribution.
  The baseline `fa0b060` belongs to the retained full diagnostic. New captures
  bind the actual clean, reviewed plan-publication commit and new helper
  hashes. The dev9 wheel and installed payload stay pinned; unchanged CSS
  filename/size/hash may legitimately match dev4 and must not be invented anew.
- Use the existing measurement guard, process observer, SLE and original
  normal-stop path. Stop request admission at the active deadline, record
  unfinished/in-flight work separately and fail the300s bound if it overruns;
  never extend a deadline or discard an incomplete page to manufacture success.
  Observer/ownership/cleanup failures stop the experiment. The already-approved
  exact-indexer pause may be reused with bounded automatic restoration.
- Capture status is `TRIGGERED`, `NOT_REPRODUCED` or `FAIL`, always
  `acceptance_eligible=false`. Compare matched spans and perturbation between
  arms, without adding overlapping spans or assigning an OS cause from a slow
  software boundary alone. No blind full-recipe retry or repeated no-hit loop.
- A later kernel capture needs its own frozen collector and fresh UAC if
  required; an expired earlier collector/session is not renewed implicitly.
  A production or SDK change still requires the existing owner/refreeze path.

### Validation And Exit

Before implementation, independently review this amendment and its validation
architecture. Before live execution, require focused RED/GREEN tests for
trigger-path filtering, exact100ms edge, unarmed warmup, first-trigger
immutability, bounded/prefix-loss buffers, deadline admission/overrun,
wrong wheel/version/source/clock, mismatched request/PID/TID, trace/control
mode, unexpected auth/status/hash, late trigger and abnormal cleanup.
Use the actual private APIs and real owning script consumers, not text checks
or test-only replacement logic. Run existing unchanged clock/server-wrapper
negative tests where relevant, plus a small owned native calibration proving
both arms' payload/identity and normal exit. Then freeze private helper hashes
and clean source identity and settle all tests/reviewers before sampling.

Exit means retained same-request localization evidence or an explicit bounded
miss, with normal cleanup and unchanged source/candidate. It is not PERF.CERTIFY,
the full7+3 qualifier or WIN.ACCEPT. Current human guidance is synchronized in
`docs/development/reporting-delivery.md`; application behavior is unchanged.

## Circular Diagnostic Amendment (2026-11-21)

Historical recipe: its1000ms trigger and dev4/bug_trend selection are superseded
for the new short-latency packet above; original captures remain unchanged.
The owner authorized the smaller circular-capture experiment after the two
anomaly-free file-mode windows. This amends the diagnostic slice of PERF.PROBE,
not the signed measurement recipe, DAG nodes, formal acceptance or runtime.
Profile source remains `repo-local`; routing remains `multiagent-configured`.
Source baseline is clean Dashboard `79681f3`; AIB and the dev4 wheel are unchanged.
The sole execution ledger is still `tasks.md`.

**Outcome:** retain the same slow request, native PID/TID and defensible clock
bridge inside a usable bounded kernel interval, or explicitly report a miss.
No circular-buffer size promises a fixed number of retained seconds.

**Owners and interfaces:** private versioned tools are new files below
`D:/AIGC/pf1120/circular-trace/`; the earlier `asset-trace/`, collectors and
receipts remain immutable. The parent owns collector/profile, launcher,
orchestration and these documents. A separate implementer may own Python
clock/trigger/fixture adapters and their tests in that private directory only.
The current test plan, sole ledger and reporting-delivery guide are the only
planned repository edits until a real product defect is established.

| High-risk boundary | Producer -> consumer | Required behavior and negative check |
| --- | --- | --- |
| Capture authority | fixed collector/session -> WPR | Hash-frozen tools; protected ACL; token; exact actions and run id; reject arbitrary executable/path, stale token, traversal, reparse, overlap and changed tools |
| Save decision | first client trigger -> ordinary controller -> privileged collector | Only matching current capture may save; immutable trigger receipt; no-trigger windows cancel without ETL; gap/boundary triggers cannot claim full coverage |
| Clock/identity | Windows clock samples and ETW markers -> offline join | Request id, PID, native TID, monotonic/QPC/frequency, precise UTC bracket and uncertainty; reject missing markers, mismatched identities, clock discontinuity and incomplete intervals |
| Claim | app result + collector/decoder evidence -> investigation report | Diagnostic only; reported loss, overwritten history, capture gaps and normal/forced cleanup remain explicit; synthetic calibration never counts as a reproduced product failure |

Consumer census: applies to diagnostic audit/log/event, validation scripts,
external artifacts, temporary CLI/admin controls, documentation and fixtures.
Product public API, business services/UI/exports, persistence/migrations,
background jobs and product cache policy are unchanged. The circular buffer
is diagnostic memory only, not an App cache or a new runtime journal.

### Bounded Implementation And Validation

1. Write failing private tests before implementing clock/trigger and collector
   decisions. Wrong/missing request identity, out-of-order clock brackets,
   a second trigger replacing the first, no-trigger save, expired session and
   command injection must fail at the real consumer boundary.
2. Reuse the original real Windows fixture, four held streams and `bug_trend`
   load. Copy/adapt private timing wrappers without editing installed files.
   Keep the existing one-second diagnostic trigger, two-second direct probe
   read wait and all application stop/watchdog budgets unchanged.
3. Add sparse Windows ETW string markers using the native provider API and
   the fixed provider id `fc8d33b5-f242-4f27-913e-84ca401125ae`.
   Mark clock calibration, the first client trigger and slow server spans.
   Payloads contain synthetic request ids, bounded route paths, PID/TID and
   timing only; never headers, credentials, query strings or response bodies.
   Marker API success alone is insufficient: the ETL decoder must observe it.
4. Use WPR memory mode with 64 MiB kernel buffers plus a small marker buffer.
   Enable context switches/ready threads, process/thread and image identity,
   and file/disk I/O; omit sampled CPU and broad Minifilter collection.
   Preserve context-switch/ready and relevant file/disk initiation stacks.
   Freeze and validate the actual profile before elevation.
5. A fresh session is limited to eight hours, six recording attempts,
   90 seconds each, the existing six-minute per-collector safety deadline,
   and 8 GiB saved-ETL admission threshold. No service, scheduled task or
   machine-policy change. Application code refuses an elevated token.
   A no-trigger window is canceled, not saved; a controlled short calibration
   save consumes one attempt. At most five diagnostic windows remain.
6. First run a small, explicitly synthetic calibration. Verify ordinary-token
   marker PID/TID and clock payload in the actual ETL, bounded recorder memory,
   source/tool hashes, normal stop/cancel and no owned residue. If its saved
   ETL exceeds 512 MiB, stop this recipe and narrow it before another run;
   this is an artifact-cost stop condition, not a performance KPI.
7. Only after calibration, run one <=600-second/4,000-sample diagnostic with
   the existing load. Start recording after fixture warmup, rotate bounded
   windows with explicit gaps, and save on the first trigger. Stop after the
   trigger, five windows, app completion or an ownership/collector failure.
   Do not retry repeatedly when all windows miss the anomaly.
8. Decode only a triggered trace or the one calibration trace. Check reported
   loss, actual retained event bounds, marker/clock uncertainty and matching
   process/thread lifetime. Require the complete relevant request/span
   interval before quantitative attribution. Capture-end/rundown activities,
   overlapping spans and unrelated PIDs must not become causal evidence.
   Retain the earlier frozen candidate and run-to-completion cleanup proof.

Tests use `D:/AIGC/pf1120/venv/Scripts/python.exe -I -B -m pytest` with explicit
private test paths and fresh JUnit/basetemp paths on D. PowerShell tests run
the collector's actual decision functions with controlled requests and a
side-effect interception boundary; actual WPR capability is proven separately.
The parent alone owns actual app/profiler execution; no tests, source edits,
builds or Git writes overlap the diagnostic window. Native capture is
deliberately intrusive and never admitted as formal KPI measurement.

An independent bounded review checks plan/permission boundaries before launch
and implementation/negative checks before elevation. Do not reopen the already
completed performance-tool code review or run unrelated App/Linux suites.
Docs impact: diagnostic validation/operations only; synchronize the current
guide and record the result without closing PERF.PROBE or WIN.ACCEPT on a miss.

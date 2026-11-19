# Windows Performance Phase

Status: planned, not qualified. Owner ordering amendment: 2026-11-17.
This document defines a later phase of the existing MDB-2 change. Completion
state lives only in [tasks.md](tasks.md). It creates no new runtime interface.

## Entry And Claims

Finish `W2.HOST -> W2.CERTIFY -> W2.R -> W2.REPLAN -> W3.FREEZE ->
W3.REHEARSE -> W3.JOIN -> FUNC.R -> FUNC.ACCEPT` first. Only then may
`W3.REPLAN -> PERF.KPI -> PERF.PROBE -> PERF.OPTIMIZE -> PERF.CERTIFY` run.
Functional acceptance does not certify performance or authorize release.

No performance measurements or optimization are needed to accept the functional
milestone. Native stop, cancellation, disconnect, admission, stream terminal
events, leak prevention and correct exit codes remain functional requirements,
including their existing contractual bounds. A slow but correct page is a
performance matter; hanging forever or losing an accepted result is not.

## Original Clause Disposition

The immutable original census is `evidence/windows-coverage.json`. Do not edit
its original requirement digests or historic evidence to change the phase.
The qualifier must derive phase selection from a versioned, repo-owned policy,
not a caller's `deferred` flag, optional suite list or arbitrary `-k` selector.

| Original 10.4 clause | Functional milestone | Performance milestone |
| --- | --- | --- |
| B1-native-second-signal | Required native exit130/bound, V5 | Rerun if affected |
| B4-disconnect-leaks | Required disconnect and 20-release safety, V7 | Rerun if affected |
| M5-capacity-return | Required normal/error/abort/stop return, V7 | Rerun if affected |
| B5-stream-stop | Required terminal ordering, slow/non-reader stop and exit0/bound, V5/V7 | Rerun if affected |
| B7-browser-parity | Required browser behavior, V9 | Rerun if affected |
| cold-and-stalled-assets | Required asset200/no slot/no final503, V6/V9 | Rerun if affected |
| repeat-order-matrix | Required actual adapter order matrix, V6 | Rerun if affected |
| B3-incremental-timing | Per-block streaming correctness remains V7; numerical KPI deferred | Required KPI-P1 |
| B6-page-assets | Page/asset correctness remains V9; numerical KPI deferred | Required KPI-P2 |
| B6-production-static | Production/static/auth correctness remains V6/V9 | Required KPI-P3 |
| B9-saturation | Required independent 4/4 quotas, excess503/Retry-After2, short200 and page usability, V6/V7 | Same-interval timing KPI-P4 |
| exclusive-window | Ordinary functional runs retain normal ownership/isolation | Required exclusive performance evidence |
| source-and-cleanup | Every functional run binds source and proves cleanup | Performance samples, source stability and cleanup required |

Mixed clauses use separate evidence aspects, `functional` and `performance`.
The original clause becomes complete only when all applicable aspects pass.
Original task 10.4 stays unchecked at FUNC.ACCEPT. All non-10.4 functional
clauses remain in scope; unknown or newly added clauses fail phase-policy
validation rather than silently disappearing. The ASGI non-applicability and
previously authorized Linux/global deferrals remain explicit, never counted.

## KPI Freeze At PERF.KPI

These are existing signed limits, not new measurements or claimed results:

| ID | Workload and observable | Existing threshold |
| --- | --- | --- |
| KPI-P1 | B3, source events every 100 ms | First event <=200 ms; inter-arrival p95 <=150 ms |
| KPI-P2 | B6, each prescribed page including referenced static assets | Candidate p95 <=1.2 times matched baseline |
| KPI-P3 | B6 again with production settings, DEBUG=False and collectstatic | Same per-page/asset ratio <=1.2 |
| KPI-P4 | B9, same saturation interval for four held streams, excess stream, short requests and pages | Excess503 with Retry-After2; every short200 and <100 ms; page/asset p95 ratio <=1.2 |

At PERF.KPI, independently verify the exact routes, asset hashes, fixture size,
warmup/sample counts, p95 calculation and timeout treatment against the signed
S0b recipe and W2.VA-approved faithful threaded WSGI baseline. Store them with
the two source identities, wheel SHA256, dependencies, OS and machine identity
in `evidence/windows-performance-inputs.json` before collection.
CPU, memory, threads, open handles, startup and phase timings are diagnostic
probes, not newly invented acceptance limits. Any additional KPI or threshold
change requires an owner decision; do not choose it after seeing results.

## Bounded Execution

1. `PERF.PROBE`: finish existing `windows_host_*` sample/process/environment/
   transport/benchmark helpers and `windows_host_qualification.py --phase
   performance`. Reuse the existing SLE/full-stack lifecycle. Validate missing
   samples, wrong baseline, source drift, false-green receipt and failed cleanup
   with synthetic tests first. Diagnostic runs do not confer acceptance.
2. `PERF.OPTIMIZE`: classify measured cost by owner (Django/static/auth,
   Waitress bridge, runtime or test fixture). Change only the evidenced owner,
   one hypothesis at a time; preserve failed traces. An AIB change needs its
   separate authorization and a newly pinned immutable wheel. Never relax
   budgets, authentication, quotas, ownership, approval or data semantics.
   If all KPIs already pass, record a no-change decision and move to certification.
3. `PERF.CERTIFY`: freeze the optimized candidate and affected functional
   regression results; rerun the signed recipe under `HEAVY_RUN_ACTIVE`.
   Guard precedes the first process and remains through last verdict JSON.
   Record start/end/every-minute processes and CPU, source/status fingerprints,
   raw samples, normal stop and descendant/listener absence. No other Metrics
   Python/tests/Git writes run in that window. Clean up only owned resources.
4. `CLOSE.R`: independently check KPI outcomes and functional evidence still
   applicable to these bytes. A runtime change requires renewed affected
   functional acceptance; the old FUNC.ACCEPT receipt remains historical.
5. `WIN.ACCEPT`: write combined `evidence/windows-acceptance.json`. Original
   mixed/global tasks close only to their actually fulfilled scope. Publication,
   main integration and worktree retirement still require OWNER.RELEASE.

## Preserved WIP And Test Lanes

Existing performance-only WIP remains recoverable and unqualified:
`ai_host/tests/windows_perf_fixture.py`, `windows_perf_entry.py`,
`test_windows_baseline_equivalence.py`, `scripts/validation/windows_host_samples.py`,
`windows_host_processes.py`, `windows_host_environment.py`, `windows_host_transport.py`,
`windows_host_benchmark.py` and `scripts/tests/test_windows_host_qualification.py`.
Move the numerical spacing/saturation test out of `conformance_runtime_cases.py`
into a separate `conformance_performance_cases.py` before functional certification.
Keep the existing functional saturation, asset and cancellation tests.

W2 implements exact-path lane selection in the qualifier: functional module
discovery excludes only the two performance-only `test_*.py` modules above;
the separate performance conformance file is not included in its explicit
conformance argv. Report these paths as deferred, not skipped or passed.
PERF.PROBE runs those preserved tests explicitly with the conformance plugins
where required. Do not globally register the SDK plugin or hide ordinary
functional failures through pytest exclusions.

## Acceptance Tool Contract

W2 extends `qualify_ai_runtime.py` with required `--profile functional|full`.
No default profile and no generic unqualified PASS. The input and receipt carry
the same `acceptance_profile`, exact source/candidate/fixture identities and
required/validated/deferred aspects. A functional receipt reports
`functional_status=PASS`, `performance_status=NOT_RUN` and cannot satisfy `full`.
`full` requires current functional evidence plus all performance aspects.

The tool validates the complete original task and clause census before phase
projection, rejects caller-reclassification, wrong/missing profile, missing
functional B9 behavior, missing stop/leak rows and false promotion of a
functional receipt. Unknown native/rehearsal formats continue to fail closed
until their producer-owned semantic validators exist. It is a bounded
extension of the current qualifier, not a new orchestration framework.

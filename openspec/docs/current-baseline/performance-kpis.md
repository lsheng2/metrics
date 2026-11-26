# Performance KPI Specification

| Document Control | Value |
| --- | --- |
| Document ID | PERF-SPEC-001 |
| Revision | 2026-11-26.3 |
| Status | Active registry; current Windows performance acceptance remains OPEN |
| Owners | Dashboard application and validation; AIB owns embedded-runtime behavior |
| Current platform | Windows, one Dashboard application with one embedded AIB runtime |
| Current MDB-2 policy | `windows-mdb2-s0b-r3`, reference-refreshed dev9 policy |
| Change authority | Owner authorization of 2026-11-26 permits evidence-led KPI revision and continued closure |
| Results index | [Performance test reports](../validation/performance-reports/README.md) |
| Report format | [KPI test report template](../validation/performance-report-template.md) |

## 1. Purpose And Authority

This is the single human-readable performance KPI register for this Dashboard
project and its AIB composition. It consolidates application latency,
reporting reads/writes, provider materialization, measurement conditions,
safety prerequisites and result status. It is not a production availability SLA.

The executable source of numerical truth remains each named owning checker and
its frozen policy. For MDB-2, use the
[current policy JSON](../../changes/embed-ai-base-runtime-in-process/evidence/windows-performance-inputs-dev9-r3-refresh.json).
This document and that checker must agree. A disagreement blocks certification;
never choose whichever representation is easier to pass.
OpenSpec changes retain decision history and implementation plans. Their dated
older values do not override this register's current-policy links.

An individual report records what happened in one execution against one policy
revision. Updating this specification does not change a historical result.
Successful functional testing, profiler collection or code review alone does
not certify numerical performance.

## 2. Scope And Metric Classes

| Class | Meaning | Closure Treatment |
| --- | --- | --- |
| Release KPI | A numerical application outcome with a fixed workload and comparator | Every applicable KPI must pass a qualifying run |
| Safety prerequisite | Correctness, auth, lifecycle, data and resource invariants with existing bounds | Mandatory; not relaxed as a performance optimization |
| Observation budget | Bounds on diagnostic tooling, traces and offline analysis | Controls an experiment, not application performance |
| Diagnostic measure | CPU, memory, throughput and component timing used to explain behavior | Report values and method; no invented pass threshold |
| External qualification | Real provider/model/network behavior | Separate explicit environment and authorization; synthetic tests are not proof |

The current Windows embedded-runtime closure uses KPI-P1 through KPI-P4 and
the safety/measurement gates below. Reporting KPI-R* and provider KPI-C* remain
visible in this project-wide register with their own applicability and evidence.
Their historical pass records are not silently renewed for a different source,
SDK, fixture or workload. Relevant dependency changes require requalification.

Linux, other AIB consumer Apps, internet/provider/model SLA, mobile-device
performance and arbitrary unbounded data histories are not covered by this
Windows milestone. They require separately named qualification profiles.

### 2.1 Coverage And Ownership

| Aspect | Owner / Metric Family | Applicability And Decision |
| --- | --- | --- |
| Page/read latency and saturation | Dashboard + installed AIB, P2/P3/P4 | Release gates, per route/mode/phase; no pooling |
| Incremental delivery | AIB transport + Dashboard client, P1 | Deterministic local events; not real-model TTFT |
| Reporting queries, editing and language UI | `project_management` / `ui_web`, R1-R10 | Bounded S0/S1 application and browser lanes |
| Materialization and data scale | `provider_sync`, C1/C2 | 10k/50k fake facts; local storage cost only |
| Aggregation, cached chart API and concurrent refresh | `provider_sync` + chart consumer, C3-C5 | Required definition/baseline gaps; block project-wide closure |
| Startup, throughput, CPU, memory, threads, handles, I/O and queueing | Owning process/module, D1-D6 below | Diagnostic measures; numeric optimization targets need a baseline |
| Admission, cancellation, resource return, shutdown and recovery | AIB + Dashboard lifecycle, SAFE-* | Mandatory functional/safety gates; not discretionary performance tuning |
| Real provider/model/network latency | Provider adapter / runtime | External qualification; NOT_RUN without its own real environment evidence |
| Browser paint, editor typing and visual rendering | `ui_web` | R4 covers language switching only; other browser timing is not certified by HTTP tests |
| Trace overhead and analysis cost | Validation tools, observation budgets | Experiment validity/cost, never a product latency substitute |

Requirements with missing budgets are explicitly `OPEN_DEFINITION`, not
`NOT_APPLICABLE`. A numeric target proposed after a baseline remains prospective
until its workload, rationale, checker and review are frozen.

## 3. Common Conditions And Assumptions

### 3.1 Candidate And Environment

- Use the admitted immutable AIB wheel, not an editable source install for
  certification. The current candidate is `ai-base-runtime==0.1.1.dev9`,
  source `fc680c3702ac4eaeae0a75486fa173b280929447`, wheel SHA256
  `c729b2c9a0c37c86ef811ad86dfda613548c516a74df414fb663074ad20575ec`.
- Current Windows qualification uses CPython 3.13.7, Waitress 3.0.2 and the
  83-distribution pinned environment. Each run records actual executable,
  import origins, package versions, OS/build, logical CPUs, memory and clocks.
- Use owned synthetic state, ordinary-token application processes and loopback.
  Do not use the operator's running 8017 service, real credentials, production
  database, provider writes or model dispatch as an implicit benchmark fixture.
- Exact source/test/fixture/environment hashes, clean source status, installed
  candidate identity and normal cleanup are prerequisites, not optional notes.
- No test/build/review/Git write overlaps an exclusive numerical measurement
  window. Capture start/end/every-minute process and CPU observations with the
  existing measurement guard. Incomplete ownership observations invalidate a run.
- Record setup, warmup, active measurement, artifact processing and cleanup
  separately. Do not add overlapping timers or equate pytest time with total cost.

### 3.2 Workload Profiles

| Profile | Data And Load | Important Boundary |
| --- | --- | --- |
| MDB2-WIN | Existing hash-bound native fixture, shared routes/data/assets across all three arms | Not the reporting S0/S1 fixture; record resolved seed and asset identities |
| REPORT-S0 | Owned clone of 8 captures, 9 drafts, 7 publications, with original revisions/sizes | Original retained week remains read-only |
| REPORT-S1 | 100 captures, 100 drafts, 100 publications; 5 revisions/draft; 3 fixed synthetic tickets; workbench page size 20 | All publication bytes/materialized state must be complete |
| CACHE-C10K | 10,000 deterministic fake-provider facts, fresh isolated test DB/profile | Payload construction is outside the materialization timer |
| CACHE-C50K | 50,000 equivalent facts, distinct fresh profile | No real provider fetch or network latency included |

For MDB2-WIN, the baseline is the signed threaded Django WSGI/static-handler
composition with its real idle worker, not a reduced fake application.
The candidate uses the actual installed blocking WSGI adapter, 14 Waitress threads,
separate 4-stream/4-short-request admission budgets and authenticated direct assets.
Preserve the approved differential: anonymous baseline static 200 versus
candidate static 401; anonymous pages 401; authenticated required resources 200.

Both development and production are mandatory. Production requires
`DEBUG=False` and successful nonempty `collectstatic` output.

### 3.3 Statistical And Failure Rules

- Percentiles use nearest rank: sort all valid required observations and select
  index `ceil(q*n)-1`. Always report `n`, median, P95/P99 as applicable and maximum.
- MDB2-WIN measures 6 pages (`home`, `projects`, `project_detail`, `stage_reports`,
  `draft_edit`, `bug_trend`), 2 client modes (`seq=1`, `c4=4`), 3 arms
  (`baseline`, `candidate`, `candidate_saturated`) and 2 settings phases.
  Each cell has 4 blocks x 40 measured requests = 160 samples; total 11,520 page samples.
  Warmup is 10 serial requests per page/arm per phase, separate from measurements.
- Alternate forward/reverse arm order by block. Never pool different pages,
  phases, client modes or workload classes to hide a failing cell.
- Page time is HTTP HTML time plus the sequential HTTP time of distinct
  referenced static assets. Asset parsing and digest calculation are outside
  this timer. This is not a browser rendering, paint or user-interaction metric.
- Keep cold-process requests separate from steady state. Do not clear user/OS
  caches or disable security software to manufacture a cold or faster result.
- Timeouts, wrong status/body/hash, missing/duplicate samples, early stream EOF,
  invalid slot/window timing, source drift and abnormal cleanup are failures.
  No trimming tails, replacing failed samples or retry-until-green certification.
- A measurement-integrity failure is `INVALID/INCOMPLETE`, not a numerical
  pass or a numerical failure attributed to application code.
- `PASS` means the stated scope has complete valid evidence and meets every
  applicable criterion. `FAIL` retains a valid observed failure. `NOT_RUN` and
  `NOT_APPLICABLE` require separate reasons; neither is a passing test.
  A diagnostic report may show a local numeric exceedance without establishing
  a release-level verdict. Record that distinction, not just one green/red label.

## 4. Embedded-Runtime Release KPIs

Owners and code:
[page sampling and policy](../../../scripts/validation/windows_host_samples.py),
[transport sampling and tail policy](../../../scripts/validation/windows_host_transport.py),
[policy admission](../../../scripts/validation/windows_host_performance_contract.py)
and [raw evidence replay](../../../scripts/validation/windows_host_performance_evidence.py).
The current machine policy link in section 1 supplies the frozen exact values.

| ID | Aspect And Measurement | Current Criterion | Conditions |
| --- | --- | --- | --- |
| KPI-P1.FIRST | Controlled incremental stream first event | <=200 ms | 50 indexed events, 100 ms producer spacing; actual adapter and client |
| KPI-P1.GAP | Stream inter-arrival P95 | <=150 ms | 49 gaps; every event 0..49 present and ordered |
| KPI-P2.ORDINARY | Development page+assets P95 / matched baseline P95 | <=1.20 | Every page, candidate arm in both modes; candidate_saturated when mode is seq |
| KPI-P2.SATURATED | Development c4/candidate_saturated page+assets P95 | Ratio <=1.25 AND P95 <=800 ms | Every one of the 6 pages; 4 page clients plus 4 held streams |
| KPI-P3.ORDINARY | Production counterpart of KPI-P2.ORDINARY | <=1.20 | Same complete recipe; DEBUG=False and collectstatic |
| KPI-P3.SATURATED | Production counterpart of KPI-P2.SATURATED | Ratio <=1.25 AND P95 <=800 ms | Same concurrent saturated class, every page |
| KPI-P4.P99 | Loop-backed short and direct-asset request P99 | Strictly <100 ms | Separately by kind and settings phase during the same 4-stream hold |
| KPI-P4.MAX | Maximum latency of those requests | <=200 ms | All required observations included; not a replacement for P99 |

P4's capacity prerequisites are functional: excess stream requests must return
503 with `Retry-After: 2`, short/assets must return 200, and capacity must be
returned. SAFE-QUOTA owns these rules; one active plus 3 idle streams form the
hold. Do not relabel a capacity or cleanup defect as an adjustable latency KPI.

P1 is a transport scheduling/delivery check with deterministic local events.
It is not real-model time-to-first-token or model generation throughput.
P4 uses a one-second paired schedule for both short and asset probes, with an
excess-stream probe every fifth slot. Scheduled and actual timestamps must be
retained. HTTP request latency and schedule lateness are different quantities.
No new lateness tolerance is established by this document.

The absolute 800 ms guard exists only for the approved concurrent-saturated
class. Other page cells retain their ratio rule; do not silently apply 800 ms to
every page or discard the ratio rule. No universal browser-paint limit is inferred.

## 5. Reporting Release KPIs

Threshold provenance:
[reporting performance execution](../../changes/add-provider-neutral-project-reporting/performance-execution.md#5-performance-gates).
Executable owners:
[language](../../../scripts/validation/profile_report_language.py),
[reads](../../../scripts/validation/profile_report_reads.py) and
[saves](../../../scripts/validation/profile_report_saves.py).
These scripts exercise the real Django request/view/storage path using
in-process `django.test.Client`, with external network denied. They are not
native socket, embedded-host, or browser timing. R4 requires a real browser.
Report the actual transport; never substitute one lane's PASS for another.

| ID | Aspect | Criterion | Measurement Conditions |
| --- | --- | --- | --- |
| KPI-R1 | Language POST latency | P95 <=150 ms; 0 archive Git calls | 20 serial POSTs, exclude redirected GET; keep redirect/cookie/auth checks |
| KPI-R2 | S0 workbench first process request | <=5 s | Fresh app process; not an OS-cache purge |
| KPI-R3 | S0 steady workbench GET | P95 <=3 s | 20 serial requests; complete expected lists |
| KPI-R4 | Apply click to target language and rendered lists | P95 <=3.5 s | 10 actual browser switches; target language, all 5 tables and 2 animation frames |
| KPI-R5 | S0 baseline preview local read | P95 <=3 s | 20 serial local reads, correct original content |
| KPI-R6 | S0 preparation detail local read | P95 <=3 s | 20 serial reads; exclude external model execution and disclose it separately |
| KPI-R7 | Loaded-editor Save POST | P95 <=2 s | 20 saves on an owned clone; successful Save and reopen; no navigation time |
| KPI-R8 | Healthy S0 workbench Git process count | <=16 per view | Wrapped native Git runner; the underlying commands actually execute |
| KPI-R9 | Duplicate complete publication reads/validation | 0 duplicate blob reads; at most 1 validation per identical packet/view | Request-local scope only; no shared permission cache |
| KPI-R10 | S1 page-20 workbench | P95 <=5 s; Git processes <=24 | 20 serial reads of complete 100/100/100 data; original byte/read budgets remain |

If the first actual GET exceeds 10 s or counts do not improve in an optimization
packet, stop expanding a slow sample set and profile. This is an investigation
stop rule, not permission to omit the failed observation from a report.
Two-readers/one-writer correctness and peak memory are recorded separately.
Save is not Finalize; no performance result permits weakening CAS, write locks,
provenance, six-file validation, ownership or original publication bytes.

## 6. Provider And Cache Performance

| ID | Aspect | Current Criterion | Status/Method |
| --- | --- | --- | --- |
| KPI-C1 | Materialize 10,000 deterministic facts | Strictly <15 s; exact record count | Owning opt-in integration test; one timed bulk operation, not P95 |
| KPI-C2 | Materialize 50,000 deterministic facts | Strictly <75 s; exact record count | Same method and isolated DB/profile |
| KPI-C3 | Aggregate generation cost at declared scale | OPEN_DEFINITION: numerical budget needs baseline | Required by provider-sync-cache spec; coverage gap, not accepted |
| KPI-C4 | Repeated local chart API latency at declared scale | OPEN_DEFINITION: numerical budget needs baseline | Required by the same spec; not the unrelated MDB2 HTML timer |
| KPI-C5 | Concurrent refresh behavior | OPEN_DEFINITION: latency/cost budget needs baseline | Single-flight correctness is separate; measure refresh owner and waiting/stale consumers |

[The provider performance test](../../../provider_sync/tests/test_provider_sync_performance.py) implements
C1/C2, guarded by `METRICS_RUN_PROVIDER_PERF_TESTS`. A skipped opt-in test is
NOT_RUN, not PASS. The owning test runs 10k then 50k in one isolated test
database with distinct profiles; the 50k operation is not measured in a second
empty database. Payload construction is outside each timer.
The [provider cache specification](../../specs/provider-sync-cache/spec.md)
also calls for C3-C5 performance coverage; its missing numeric definitions are
explicit open work in this central register. Define workload, baseline and
threshold before a future qualifying run, using this project's existing owner.

Before C3-C5 qualification, the owning provider/cache change must bind concrete
API/aggregate entrypoints, chart/query cardinality and payload sizes, 10k/50k
fact inputs, warm/cold cache state, concurrency and sample counts. Measure a
bounded baseline, freeze numerical budgets with rationale and negative tests,
then run a new qualifying report. The current MDB2 documentation packet does
not authorize unrelated provider implementation or mark this work completed.

Provider network/auth/rate-limit time must be reported separately from local
materialization. Chart rendering must not perform a hidden live provider fetch.
Do not invent a common external-provider SLA or call synthetic parity a live result.

## 7. Safety Prerequisites

These remain functional contracts even when measured in milliseconds/seconds.
The performance-retuning authorization does not turn them into optional KPIs.
Full details and stage ownership remain in the
[Windows validation contract](../../changes/embed-ai-base-runtime-in-process/windows-close-validation.md).

| ID | Required Invariant/Bound | Evidence |
| --- | --- | --- |
| SAFE-AUTH | Auth/Host/CSRF/owner isolation and approved data/side-effect semantics preserved |Actual HTTP, scope and approval/refusal tests |
| SAFE-STOP | Normal idle stop exits 0 within 10 s; second signal exits 130 within 1 s | Native Windows process evidence, not direct handler calls |
| SAFE-ACTIVE | Existing active-project shutdown/worker/watchdog budgets remain unchanged | Stage-budget and native lifecycle receipts |
| SAFE-DISCONNECT | Heartbeat 2 s; disconnect observed within heartbeat+1 s; 20 releases without accumulating resources | Installed adapter/testkit plus native host proof |
| SAFE-QUOTA | Separate 4/4 stream/short quotas; assets use neither; every terminal path returns capacity | Normal/error/abort/stop and backpressure tests |
| SAFE-CLEANUP | No owned surviving descendants/listeners, explicit normal exit and observer release |SLE/native census and final result witness |
| SAFE-DATA | Exact content/hash/provenance, no extra model/provider dispatch or duplicate publication |Fixture and runtime outcome checks |

Forced cleanup is retained as failure, not normal stop. Do not increase
production stop budgets or waive a real leak to meet performance goals.

## 8. Diagnostic Measures And Observation Budgets

Record CPU utilization/time, private/working-set memory, thread and handle
counts, page/operation throughput, cold startup, DB/Git/file time, queue wait,
ready/blocked time and optional real-provider/model time with phase boundaries.
For each, state process scope, counter units, sampling cadence, workload,
baseline, instrumentation overhead and whether it is application or host-wide.
Do not manufacture a numerical PASS when no release requirement exists.

Resource correctness is enforced by SAFE-DISCONNECT/SAFE-CLEANUP. A CPU or memory
optimization target needs a measured baseline and explicit frozen rationale;
an arbitrary percentage/RSS ceiling is not added merely to fill a table.
Browser rendering and true user-interaction time require real-browser timers;
HTTP-only measurements cannot stand in for them.

| ID | Measurement Definition | Required Conditions / Result Treatment |
| --- | --- | --- |
| D1.STARTUP | Launch to authenticated readiness, with stage durations | Cold process and cache state explicit; startup deadline is not a latency target |
| D2.CPU | Process CPU seconds / wall seconds and logical-core normalization | Identify PIDs/incarnations and sampling cadence; distinguish target from host CPU |
| D3.MEMORY | Baseline, peak and settled private/working-set bytes; thread/handle deltas | Same workload/lifetimes and observer method; RSS alone neither proves nor clears a leak |
| D4.THROUGHPUT | Successful completed operations / active wall time, plus offered concurrency | Exclude expected overload responses from successes; do not sum overlapping block timers |
| D5.COMPONENT | HTML/assets, DB/Git/file time, queue wait and CPU/ready/blocked partition | Preserve same-request PID/TID/clock correlation; overlapping component times are not additive |
| D6.RECOVERY | Cancel/disconnect/recovery/normal-stop durations and outstanding-work counts | Applicable SAFE-* bounds still gate; timed-out/forced cleanup remains failure |

These rows define what must be disclosed when used in an investigation. They
do not claim that every counter has already been measured, or that an unmeasured
CPU, memory, startup or throughput release budget exists.

The [scheduler retention amendment](../../changes/embed-ai-base-runtime-in-process/windows-scheduler-retention.md)
versions the ordinary calibration/replay method while retaining the frozen
[low-event collector](../../changes/embed-ai-base-runtime-in-process/windows-low-event-observation.md).
Separate bounds remain: 30 s active calibration/40 pages, 90 s recording, 360 s collector,
120 s whole decode, 128 MiB actual ETW buffer pool, 512 MiB raw+temporary artifacts,
512 MiB derived artifacts, 128 markers and 50,000 selected rows. The original v1
calibration ceiling is 250,000 all-decoded events. Prospective
`scheduler-retention-v2` calibration uses 1,000,000, matching the existing
decoder ceiling and later 80 s diagnostic cap. Implementation review, source
freeze and new native proof remain required before that method is accepted.
Zero loss, no truncation/omission, complete target identity/clock coverage and
normal cleanup remain evidence-quality requirements.

The event ceilings are investigation-cost policy, not product latency KPI.
The 2026-11-26 calibration exceeded its original event ceiling despite low byte
cost and zero loss. Its refusal remains immutable. Any amended analysis or
budget must have a new version, rationale and review; it cannot rewrite the
original refusal. A retained elevated helper keeps its original immutable
privileged scope and expiry. No amount of KPI authority renews that expiry.
The old helper has two captures total and one already consumed; it cannot run
another calibration because the unchanged collector permits calibration only
at count zero. A new owner-authorized grant is required, with its own verified
launch receipt, scope, PID/incarnation and original eight-hour expiry. Admit
calibration at count 0/max 2 with empty history and zero ETL bytes. A new grant
does not reset or renew the old one. The 18:45 UAC request on 2026-11-26 was
canceled; unresolved grant means no native freeze/run. Diagnostic execution
still requires valid calibration, separate approval and remaining capacity.

## 9. Current Results And Gaps

This table is an index, not a new execution report. Read the exact report and
source/policy/fixture identity before reusing evidence.

| Profile/Metric | Latest Relevant Recorded Result | Current Claim |
| --- | --- | --- |
| MDB2 r3 full certificate at db00210 | Historical complete PASS, 11,520 pages, dev9 | Not current-source acceptance after subsequent changes |
| MDB2 r3 certificate at c845224 | Complete FAIL: development seq/candidate bug_trend ratio 1.5376 >1.20 | KPI-P2 failure retained; other passing cells do not make the run pass |
| MDB2 diagnostic at d7dd699 | INCOMPLETE: probe not bound to scheduled slot | No release verdict from the incomplete run; raw exceedances remain diagnostic evidence |
| Scheduler calibration at 7dd8545 | 529,161 events >250,000; zero loss; native proof refused | Not a product KPI result and not native calibration acceptance |
| Reporting S0/S1, 2026-11-07 | Scoped historical PASS; language UI 3.101 s, S0 GET 2.876 s, S1 GET 4.105 s, Save 1.839 s P95 | See original receipt; fresh-current applicability must be justified |
| Provider C1/C2 | Executable thresholds exist | No current run evidence established by this documentation packet |
| Provider C3-C5 | Required aspects found; explicit performance budgets incomplete | OPEN_DEFINITION; not silently exempted |

Historical reporting evidence:
[delivery report](../../changes/add-provider-neutral-project-reporting/performance-delivery.md).
Current observation record:
[dated report](../validation/performance-reports/2026-11-26-low-event-calibration.md).
Source receipts, review gates and future results are indexed in
[the report register](../validation/performance-reports/README.md).

## 10. Change Control And Closure

The owner's 2026-11-26 authorization permits the implementation agent to change
an unreasonable performance KPI after profiling/debugging and substantive
analysis, without asking again for each number. It does not permit retroactive
PASS, discarded samples, weaker functional invariants or missing evidence.

For every change:
1. Preserve the failing run and reproduce/localize the issue or record a bounded miss.
2. Separate an application defect, measurement defect, environmental variation
   and an unsuitable requirement; explain uncertainty and user impact.
3. Record the old/new criterion, units, workload class, rationale, affected
   consumers, negative tests and comparability limits in this document.
4. Create a new immutable machine-policy revision when executable criteria
   change. Update owning code/tests, this register and current operator guidance
   together; independently review before qualifying measurements.
5. Freeze the new policy/source/candidate/fixture/environment before running.
   Generate a new dated report; never overwrite a prior report or raw receipt.

Windows MDB2 closes only after a fresh uninstrumented full recipe, semantic
raw-data replay, applicable functional and full-profile support lanes, independent
optimization/no-change and combined-evidence reviews, and the actual Windows
acceptance writer all pass. The sole progress ledger remains
[MDB2 tasks](../../changes/embed-ai-base-runtime-in-process/tasks.md).
The wider project registry is not fully closed while required C3-C5 definitions
or applicable R/C qualification gaps remain. Report scoped closure explicitly.

### Revision History

| Revision | Change | Numerical Impact |
| --- | --- | --- |
| 2026-11-26.1 | Consolidated existing P/R/C criteria, measurement boundaries, safety/diagnostic distinctions, report governance and known gaps | None; no budget or KPI was changed by consolidation |
| 2026-11-26.2 | Prospective retained-window calibration repair with unchanged collector and strict interval evidence | Calibration observation-cost cap 250,000 ->1,000,000 events; all application KPI, byte/time/loss/cleanup and privilege bounds unchanged |
| 2026-11-26.3 | Corrected calibration admission to require a separate verified count-zero UAC grant; canceled request is not readiness | None; same eight-hour/two-capture collector, product KPI and safety bounds |

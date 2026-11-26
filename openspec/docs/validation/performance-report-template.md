# Performance KPI Test Report Template

Use one new file per run under `performance-reports/`, named
`YYYY-MM-DD[-HHMM]-<profile>-<run-id>.md`. This is a template, not test evidence.
Do not mark placeholders or unexecuted checks PASS. Once finalized, reports and
raw receipts are immutable; publish a new report for reruns or policy revisions.

## 1. Report Control

| Field | Required Value |
| --- | --- |
| Report ID / revision | Unique id; revision 1 |
| Kind | certification / diagnostic / calibration / baseline / analysis |
| Collection / integrity / numerical / acceptance status | Separate fields; DRAFT / PASS / FAIL / INVALID / INCOMPLETE / NOT_RUN / NOT_APPLICABLE as applicable |
| Started / finished | Absolute timestamps with time zone; also retain UTC |
| Author / independent reviewer | Actual participants and receipt references |
| KPI specification revision | PERF-SPEC-001 revision and file hash; for retrospective reports identify the policy actually used at test time |
| Machine policy | Exact recipe id, version, path and SHA256 |
| Overall claim | Qualified scope and exclusions; never generic unqualified PASS |
| Previous/superseded report | Link without modifying that report |

## 2. Objective And Scope

State the hypothesis or release question, all applicable KPI ids, workload
profiles, changed components, boundaries and explicit non-goals.
Explain why this run can answer the question. A calibration, reduced pilot or
profiled experiment is not a complete uninstrumented release measurement.

## 3. Frozen Configuration And Assumptions

| Item | Actual Value / Evidence |
| --- | --- |
| Dashboard / AIB source | Full SHAs; clean/status fingerprints |
| Runtime candidate | Version, wheel/source SHA256, installed-origin verification |
| Dependencies/interpreter | Versions, executable and environment fingerprint |
| Host | OS/build, CPU/logical cores, RAM, storage, relevant background activity |
| Instance/auth | Owned synthetic instance, loopback, ordinary/elevated token boundary |
| Data | Counts, sizes, revisions, snapshot/fixture hashes, seed and ownership |
| Cache state | First process request versus warm; no implied OS-cache purge |
| Settings | Development/production, DEBUG, server/threads/quotas, collectstatic |
| Baseline | Architecture and why comparable; deliberate auth differences |
| Instrumentation | Tool/version/hash, interval, target scope, overhead/limitations |
| Timer boundary | Native HTTP / in-process Django Client / browser / bulk operation; exact start and completion events |
| Assumptions | Each assumption and how verified; unknown values remain unknown |

## 4. Test Design And Execution

Record the exact executable commands, resolved endpoints/resources, request
ordering, repetitions, warmup, concurrency, held streams, scheduling cadence,
expected statuses, timing start/end points and percentile definition.
State timeout, missing-sample, invalid-window, source-drift and cleanup treatment
before reviewing results. Record actual sample counts and any stop condition.

| Phase | Start / End | Wall Time | Outcome / Artifact |
| --- | --- | --- | --- |
| Setup/admission | | | |
| Warmup | | | |
| Active measurement | | | |
| Decode/analysis | | | |
| Normal cleanup | | | |

## 5. Measurement Validity

| Gate | PASS / FAIL / NOT_RUN | Evidence / Reason |
| --- | --- | --- |
| Correct source/candidate/fixture/environment | | |
| Source stable and owned measurement window valid | | |
| Required samples/slots/events complete | | |
| Status/content/hash/auth/semantic checks | | |
| Loss/truncation/omission/clock/identity checks when applicable | | |
| Normal stop, exits, descendants/listeners and observer release | | |
| Raw references, final write witness and semantic replay | | |

A failed applicability or integrity gate prevents release acceptance. Keep
collection success, numerical results and acceptance eligibility separate.
Use NOT_APPLICABLE with a reason for a gate outside the run's declared scope.
Unknown or unavailable metadata stays explicit; it must not be filled by guessing.

## 6. KPI Results

Use one row per KPI and workload cell, or link a complete machine-readable
matrix when large. Include all cells, not only regressions or highlights.

| KPI ID | Phase / Workload / Arm | n | Baseline | Median | P95 | P99 | Max | Criterion | Verdict | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| | | | | | | | | | | |

Always identify units. Ratios need their absolute baseline and candidate values.
Single bulk operations must be reported as such, not labelled P95. State
expected overload responses separately from unexpected errors.
Record the observed difference and ratio, sample variation and uncertainty.
For a ten-sample nearest-rank P95, the P95 is the maximum; do not imply stronger
tail confidence. Disclose every failed attempt and its separate report id.

## 7. Resource And Component Findings

Report CPU, memory, threads/handles, Git/DB/file costs, queue/ready/blocked
intervals, throughput, startup and tooling costs where relevant. Separate
host-wide and target-process measures; do not add overlapping intervals.
Distinguish observation, hypothesis and established cause. Include contrary
evidence and instrumentation limitations.

## 8. Failure Analysis And Actions

| Finding | Reproduction / Evidence | Classification | Owner | Action / Verification |
| --- | --- | --- | --- | --- |
| | | application / method / environment / requirement / unresolved | | |

If proposing a KPI change, record the old/new values, workload class, user
impact, evidence, statistical limitations and approval authority. This report
does not reinterpret its original result under a future policy.

## 9. Evidence Manifest

| Artifact | Role | Source/Run Identity | SHA256 / Reference |
| --- | --- | --- | --- |
| | raw samples / policy / logs / screenshots / trace / cleanup / replay | | |

Keep large traces and sensitive logs in the protected local artifact root;
commit redacted metadata and references only. Do not include credentials,
authorization headers, cookies or enterprise payloads.
Hash the referenced files, including executable checkers and their inputs.
If a run predates this template, preserve its original receipt and mark this
document as a retrospective presentation, not a newly executed test.

## 10. Review And Final Decision

Record the actual independent review verdict and scope, unresolved risks,
which KPI ids and milestone clauses close, and which remain open.
Name any required follow-up as a new report/run, not an edit to this report.
Update the central KPI results index only after references and claims validate.
The last line must state either a precisely scoped acceptance or
**No performance acceptance is established by this report.**

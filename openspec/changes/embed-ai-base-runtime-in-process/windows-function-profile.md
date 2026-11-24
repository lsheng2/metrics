# Bounded Production HTML Function Profile

Date: 2026-11-24. Status: executed; function attribution refused.
Docs impact: operations. Current guide: `docs/development/reporting-delivery.md`.
This amends only the next diagnostic packet, not the existing task DAG or KPI.

The [execution checkpoint](evidence/windows-function-profile-checkpoint.md)
supersedes this recipe's unproven engine-isolation assumption. On the tested
Python 3.13.7, cProfile captured foreign-thread functions. Request-envelope
identity is insufficient; do not reuse these function ranks for attribution.
Future recipes must prove concurrent engine isolation and calibrate overhead
before any new owner-authorized application window. The original recipe and
raw outputs below are retained as history, not a current readiness claim.

## Question And Authority

The owner authorized a limited-duration investigation of production HTML CPU
hotspots without changing KPI. This packet measures function-level wall time
with cProfile and records coarse request-thread CPU separately; it does not
measure CPU time for individual functions. The retained trace contains a
151.0556 ms production HTML request with 148.7548 ms inside WSGI execution and
coarse thread CPU of 156.25 ms. A separate unprofiled control also reproduced
slow HTML. Neither identifies a function or proves an OS/SDK cause.

Use the admitted dev9 interpreter and immutable wheel in `D:/AIGC/d9-1122`.
All private diagnostic changes live in a new `function-profile/` directory.
The original subsecond V1/V2/V3 code, inputs, failures and receipts remain
unchanged. Dashboard/AIB product code and installed package files are not edited.

## Method And Limits

- Reuse the V3 request recorder, clocks, source/package admission, measurement
  guard, synthetic fixture, SLE, probes and normal-stop path. Only the
  production sequential `draft_edit` scenario runs; no held streams and no
  development CSS scenario.
- Use standard-library `cProfile` on the exact resolved HTML WSGI call in the
  request's own thread. The measured-page client sends an explicit diagnostic
  header only for its armed HTML target. The server also requires the exact
  fixture route and a valid diagnostic request id. Warmup, assets, probes,
  snapshot requests and invalid ids do not activate function profiling.
- Both arms keep the same software boundary timing and endpoints. `profile`
  enables cProfile; `control` does not instantiate/enable a profiler. No new
  dependency, kernel collector, privilege elevation or real provider is needed.
- Default cProfile timing is real/wall time, not per-function CPU time. Retain
  call counts, exclusive/cumulative wall time and coarse request-thread CPU
  separately. Cumulative times overlap; never sum them or describe wall time
  as CPU. Instrumented requests are not samples for performance acceptance.
- Retain a ring of at most 16 completed profile objects and explicit eviction
  counts. No statistics conversion, sorting, serialization or disk write is
  performed inside the profiled WSGI call. At harvest, emit bounded function
  rows with original counts and explicit truncation. Do not record arguments,
  locals, response bodies or credentials.
- Preserve the response iterable and original exception semantics; stop the
  profiler in `finally`. Record collector errors separately and fail the
  diagnostic if collection is incomplete. Never replace a failed request with
  a successful profile.
- One native calibration per arm: at most 10 active seconds and four pages.
  Then one profile/control pair: at most 150 active seconds and 2000 pages
  per arm, retaining the first eligible 100 ms HTML trigger and stopping
  admission as in the original runner. Total active allowance is 320 seconds
  across calibration and the pair, not renewable by retries.
- Setup, unarmed warmup, harvest and normal stopping are measured separately.
  Existing request, process-stop and cleanup bounds remain unchanged. An
  overrun, incomplete page, source drift, observer fault or abnormal cleanup
  is a failure, not permission to extend a window.
- Existing exact-indexer quiet-window helpers may be reused only with their
  previously authorized live PID/incarnation identities and automatic
  restoration. No new external pause target is implicitly authorized.
  Settle tests/reviewers before native sampling; never measure while they run.

## Evidence Contract

Bind the actual clean reviewed source commit, all private helper hashes,
interpreter and installed candidate admission in new immutable inputs before
starting. Retain ordinary-token proof, resolved HTML path, source/wheel identity,
same-request id, native PID/TID, process incarnation, monotonic/QPC/UTC brackets,
profile call interval, coarse thread CPU and original client/server rows.

The profile for the triggering request must resolve exactly once to its own
server identity and complete request interval. Missing/evicted trigger profile,
clock mismatch, profiler exception or truncated timing interval prevents
attribution. Function-list truncation must be reported; it never proves that
an omitted function was absent. In control, an empty profile collection is
required. A bounded miss remains a miss, not a performance pass.

Compare exposure/counts and function shares cautiously. A profiler-only trigger
may be instrumentation-induced; it does not explain the earlier unprofiled
failure. Report the hot observed call chain and identify what further evidence
would distinguish CPU computation, waits or instrumentation cost. No unbiased
speedup, causal proof or KPI compliance is inferred from first-hit samples.

## Validation And Exit

Before implementation, independently review the recipe and its boundaries.
Before native work, run focused tests for exact route/header/id selection,
unarmed warmup, control with no profiler, return/iterator/exception preservation,
bounded retention, statistics labels, collection errors and exact trigger joins.
Reuse unaffected V3 tests; do not reimplement the lifecycle or source admission.
Run size/whitespace and strict OpenSpec checks, then independent integrated
code/recipe review before publishing and freezing the capture inputs.

Native calibration proves actual entrypoint wiring, authenticated snapshot
access, matching request profile in profile mode, none in control, unchanged
HTML/assets and normal exit. Calibration failure consumes its allowance and
stops the pair; no blind repeat. The paired run also stops on any failure.
Retain failure captures and restored quiet-window receipts.

Exit with bounded same-request function evidence or an explicit miss/failure,
not a product fix. PERF.OPTIMIZE, PERF.CERTIFY, CLOSE.R and WIN.ACCEPT remain
open. CSS 119.3983 ms and draft_edit ratio 1.58434 retain their existing failing
limits. A product/SDK optimization or new profiling window needs a subsequent
owner decision. Linux, real models/providers and full qualification are excluded.

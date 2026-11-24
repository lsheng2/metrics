# Windows Tail Policy And Focused Asset Investigation

Date: 2026-11-24. Status: owner-approved direction; implementation pending.
Docs impact: operations/validation; current guide:
`docs/development/reporting-delivery.md`.
`profile_source=repo-local`; `agent_routing_mode=multiagent-configured`.

The owner approved continuing the evidence-based KPI reassessment and reasonable
optimization. This renews existing PERF.KPI/PERF.PROBE ownership, not a second
DAG or task ledger. No product optimization is justified until an owner path
and a falsifying regression are established.

## Policy Decision

Create recipe `windows-mdb2-s0b-r2` and a new
`evidence/windows-performance-inputs-dev9-r2.json`. Keep the old policy, frozen
inputs, raw samples and failures unchanged. Current admission must reject old
recipe/policy references, including a stale recipe relabelled at only one layer.

Evaluate loop-backed short requests and direct assets separately, and keep
development and production separate:

- Nearest-rank P99 must be strictly below 100 ms.
- Every observed latency must be at most 200 ms.
- All samples count; no trimming, retry substitution or pooled endpoint classes.
- HTTP success, asset identity, cadence, quotas, excess503/Retry-After2,
  complete streams/samples, normal stop and genuine leak detection remain hard
  requirements. Pilot/diagnostic receipts remain ineligible for certification.
- P1 streaming bounds and P2/P3 page-plus-assets P95 ratio <=1.2 are unchanged.
  The full six-page, two-mode, three-arm, four-block recipe is unchanged.

This replaces an every-sample100ms performance rule, not a correctness bound.
The full dev9 diagnostic had one119.398ms CSS sample among785 successful
development probes, with P99 46.247ms; production CSS maximum was65.083ms.
Page P95227.544->360.508ms is not waived: six consecutive samples exceeded500ms
in a3.7724s episode after32 normal samples. It is not proven cold-start latency.

## Authority Propagation

| Authority | Producer | Consumers | Required Negative Check |
| --- | --- | --- | --- |
| PERF-RECIPE/P4, high risk | New frozen policy and transport evaluator | Performance contract, benchmark resolved recipe, standalone/aggregate replay, conformance performance adapter | P99=100 fails; max>200 fails; one200ms sample among100 may pass; no cross-kind pooling |
| PERF-IDENTITY, high risk | New recipe ID/policy path and clean source | Input preparation, semantic checker, active test fixtures, current docs | Old recipe, old canonical policy, altered tail limits and mixed resolved recipe fail |
| PERF-INTERVAL, high risk | Existing request/page/slot clocks and identities | Focused asset report and unchanged full checker | Missing/duplicate requests, wrong asset vectors, incomplete pages and overruns cannot pass |

Runtime APIs, business services, user UI, persisted user data, providers, SDK
payload and production process budgets are non-goals. Applies: validation
scripts, CLI, diagnostic artifacts, current operator docs and test fixtures.
No cache/search, scheduling, data migration or external-data changes apply.

## Focused Native Packet

The remaining question is the production sequential draft-edit whole-page
tail, not an isolated100ms HTML call. Use a new private directory on D:,
the admitted dev9 interpreter/wheel, existing SLE/measurement guard and fixture.
Keep the faithful baseline, candidate and four-stream saturated candidate.
Preserve the static-auth differential and asset hashes.

After ten unmeasured warmup pages per arm, run one calibration page per arm,
bounded to ten active seconds in total. Then run only draft_edit/seq with
four alternating forward/reverse blocks of40 pages per arm, at most180 active
seconds overall. All480 pages are required to call that diagnostic complete.
A miss/overrun/failure is retained, not retried or extended. Setup, warmup,
harvest and normal stop are separate. This subset is never full qualification.

Reuse request-local monotonic/header/body timing and native PID/TID witnesses;
join every asset request to its page. Retain bounded raw records and explicit
loss counts. An observed slow page retains its exact resource intervals, not
a substitute HTML trigger. No cProfile or other function profiler is used.
Optional bounded GC callback observations may record generation, phase,
timestamp and native TID only; do not force collection, change GC thresholds,
block on locks in callbacks or infer causality from overlap alone.

Do not change response iterables, file-wrapper optimization, assets, auth or
server implementation for this probe. Baseline/candidate software timing must
have equivalent coverage. Use ordinary tokens and the previously authorized
exact-indexer quiet window with automatic restoration; no new UAC/kernel
collector or foreign pause target is authorized.

## Validation And Refreeze

1. Independent method/validation preflight before implementation.
2. TDD on tail boundaries, per-kind evaluation, malformed/error rows, stale
   recipe and policy references; run affected producer/replay/aggregate tests.
3. Private collector tests must prove actual request/page joins, deadline
   admission, complete fixed counts, losses, failed harvest and cleanup facts.
4. Size/whitespace, strict OpenSpec and existing DAG preflight; independent
   integrated code/contract review before scoped publication and input freeze.
5. Settle agents/tests before the single native packet; inspect exact artifacts
   and normal restoration before any optimization or acceptance claim.

Refreeze action: `amend` the P4 numerical policy and the narrow diagnostic
target. Updated artifacts are this amendment, existing phase/test-plan/guide/
task/DAG references, the new policy and the declared validation/test owners.
Rerun gates are focused performance tests, existing OpenSpec/DAG preflight,
PERF.KPI/PERF.PROBE review and later full certification. P4 retrospective
replay is sensitivity analysis only. PERF.CERTIFY, CLOSE.R and WIN.ACCEPT remain
open; no broad closure is granted by this packet.

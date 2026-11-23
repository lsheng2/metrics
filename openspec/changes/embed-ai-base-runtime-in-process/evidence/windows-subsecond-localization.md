# Windows Subsecond Localization Checkpoint

Date: 2026-11-23.

This checkpoint records the bounded Windows subsecond localization packet. It is
diagnostic evidence only. It does not change the dev9 SDK, product code,
sampling/KPI policy, stop/leak budgets, Linux/provider/model scope, or the
Windows acceptance gates.

## Verified Inputs

- Dashboard source HEAD: `2233d49b8e16c62025028e9e3757e651756856f2`, clean
  before this documentation packet.
- Runtime candidate: `ai-base-runtime==0.1.1.dev9`, source
  `fc680c3702ac4eaeae0a75486fa173b280929447`, wheel SHA256
  `c729b2c9a0c37c86ef811ad86dfda613548c516a74df414fb663074ad20575ec`.
- Retained full diagnostic source: `fa0b060`; its full official diagnostic
  still has CSS119.3983ms and production seq/draft_edit ratio1.58434 open.
- Review gates:
  - `D:/AIGC/d9-1122/subsecond-plan-gate.json`: complete 1/1, no pending findings.
  - `D:/AIGC/d9-1122/subsecond-code-gate.json`: complete 1/1, no pending findings.
  - `D:/AIGC/d9-1122/subsecond-target-gate.json`: complete 1/1, no pending findings.
- Private code manifest: `D:/AIGC/d9-1122/subsecond-code-manifest-r2.json`
  records 22 source/test files. The target-refinement gate states v2 changed
  only `localization_scenarios.py` and
  `tests/test_localization_scenarios.py`; `v2-green1.xml` records 67 passing
  tests.

## Native Calibration

- `D:/AIGC/d9-1122/subsecond/runs/cal-trace-r1/result.json` has window PASS and
  normal cleanup. It captured development c4 HTML187.8063ms, not the runtime CSS
  failure, which motivated the narrower v2 primary-target selection.
- `D:/AIGC/d9-1122/subsecond/v2/runs/cal-control-r1/result.json` has window
  PASS and normal cleanup with control tracing disabled.

## Paired Experiment

Only one actual paired experiment is recorded. It was not rerun.

Trace arm:

- Result file:
  `D:/AIGC/d9-1122/subsecond/v2/runs/probe-trace-r1/result.json`.
- Overall status remains `FAIL`; `window_result` is `PASS`.
- `production_seq` triggered after 29.813s of active sampling and 128 attempted
  pages. The matched request is
  `probe-trace-r1-production_seq-page-9681`, status 200, clientHTML151.0556ms,
  preWSGI1.0024ms, WSGI call148.7548ms and coarse thread CPU156.25ms. The same
  request joins client/server records by request id, with their respective
  PID/native TID retained. Spans overlap and
  must not be summed.
- `development_c4` ran with normal cleanup and no eligible CSS trigger. The
  failure was optional non-trigger attribution harvest selecting an old
  normal-request example that had already left the bounded server tail.

Control arm:

- Result file:
  `D:/AIGC/d9-1122/subsecond/v2/runs/probe-control-r1/result.json`.
- Overall status is `TRIGGERED`; `window_result` is `PASS`.
- `production_seq` triggered after 46.472s of active sampling and 206 attempted
  pages with productionHTML163.4204ms and server tracing disabled.
- `development_c4` was NOT_REPRODUCED after 145.384s of active sampling and 952
  attempted pages, with normal cleanup and peak concurrency 4.

## Tail Diagnosis And V3 Boundary

`D:/AIGC/d9-1122/subsecond-tail-diagnosis-r1.json` independently confirms the
trace-arm development failure was an attribution-tail defect: 64,509 client
attempts, 14,509 client drops, 286,104 server drops and 100,000 retained server
rows left the oldest selected normal request outside the server tail. A recent
normal CSS request joined correctly at 11.2289ms. No actual first trigger was
substituted.

V3 fixes only optional non-trigger attribution: when trigger is absent, no
attribution is claimed. Actual first-trigger attribution still requires the
complete same request. Evidence:

- `D:/AIGC/d9-1122/subsecond-test-evidence/v3-red1.xml`: two expected red
  failures before the v3 attribution helper existed.
- `D:/AIGC/d9-1122/subsecond-test-evidence/v3-green1.xml`: 69 passing tests in
  3.524s.
- `D:/AIGC/d9-1122/subsecond-v3-offline-regression.json`: consumes old raw data,
  keeps `original_producer_status` as `FAIL`, marks `acceptance_eligible` false,
  attributes production HTML to the same request and leaves development c4
  attribution null.

V3 has not run live. Code review does not replace future frozen-input/native
checks before it can be used as a producer.

Version lineage is derived in
`D:/AIGC/d9-1122/subsecond-version-lineage-r2.json`, checked by
`D:/AIGC/d9-1122/build-subsecond-lineage-v2.ps1 -Verify`. It binds the unchanged
V1, V2 and V3 manifests and source roots by hash. The V3 manifest's three-file
delta is relative to V2, not V1. The cumulative V1-to-V3 delta additionally
includes `tests/test_localization_scenarios.py`, inherited unchanged from V2.
The lineage checker verifies all 66 manifest entries and distinguishes these
two baselines; original manifests and native receipts are not rewritten.
The checker compares parsed JSON values across Windows PowerShell 5.1 and
PowerShell 7 while retaining byte-exact SHA256 checks for source and manifests.
The r1 lineage and checker remain historical evidence of the formatting defect.

All native fixtures stopped normally, including the failed trace arm. Every
authorized indexer pause was restored without emergency rescue; the final
parent audit found no heavy-run guard, owned test/helper residue or suspended
indexer threads. No existing collector session was extended or reused.

## Interpretation

Established:

- A traced production HTML slow response is predominantly inside WSGI execution
  for the matched request, with coarse thread CPU of similar magnitude.
- A production HTML slow response also occurs in the control arm with server
  tracing disabled.
- The CSS fault is not closed by the development c4 miss or by the attribution
  repair.

Not established:

- Specific Python function, GC, OS scheduler, kernel, UAC, SDK or provider root
  cause.
- Exact trace perturbation or unbiased speedup percentile.
- Performance certification, no-change decision, full 7+3 qualifier,
  `WIN.ACCEPT`, Linux/model/provider qualification or any product code change.

Next recommendation: if authorized separately, run a bounded function-level CPU
profile for the production HTML path and collect careful same-request CSS
evidence if the CSS failure recurs.

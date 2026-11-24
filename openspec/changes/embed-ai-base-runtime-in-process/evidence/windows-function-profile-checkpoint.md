# Windows Function Profile Checkpoint

Date: 2026-11-24. Diagnostic only; function attribution is **refused**.
Current analysis: `D:/AIGC/d9-1122/function-profile-analysis-r1.json`.

## Inputs And Execution

- Source: `1bf83cf9960509735aac29960f0c32275da8c87d`, clean during collection.
- Runtime: `ai-base-runtime==0.1.1.dev9`, wheel SHA256
  `c729b2c9a0c37c86ef811ad86dfda613548c516a74df414fb663074ad20575ec`.
- Frozen input:
  `D:/AIGC/d9-1122/function-profile/inputs/frozen-1bf83cf-r1.json`,
  SHA256 `76d7fd6c0091abb9453c3682148647d83bd4bdb0e83ba96afa391523bbf83f8e`.
- Packet: `D:/AIGC/d9-1122/function-profile/fp1124-r1-packet.json`.
  One calibration per arm and one main pair ran; no application retry.
- Active sampling totaled 30.390 seconds of the 320-second allowance.
  Packet wall time was 427.744 seconds; scenario setup/warmup totaled
  256.383 seconds. Setup, admission, harvest and cleanup are not active samples.

| Arm | Outcome | Active Seconds | Pages | HTML Trigger |
| --- | --- | ---: | ---: | ---: |
| Calibration profile | TRIGGERED | 0.273 | 1 | 111.621 ms |
| Calibration control | NOT_REPRODUCED | 0.912 | 4 | none |
| Main profile | TRIGGERED | 0.261 | 1 | 106.898 ms |
| Main control | TRIGGERED | 28.944 | 128 | 151.331 ms |

All four producer windows passed their existing checks and stopped normally.
The original packet status remains `COMPLETE`; this means collection completed,
not that function attribution or performance acceptance passed.
The quiet-window receipt restored both original indexer incarnations without
errors or emergency rescue. The measurement guard was removed.

## Reliable Boundary Observation

The main control used no cProfile and retained no function profiles. Its slow
HTML request took 151.3313 ms, with 149.2544 ms inside the matching WSGI call and
coarse thread CPU of 140.625 ms. Slow HTML therefore remains observable without
the function profiler. These values do not identify a function, GC, OS, SDK or
provider cause, and coarse CPU must not be treated as an exact utilization ratio.

The instrumented main request had 103.3071 ms in WSGI and 93.75 ms coarse thread
CPU, but its function statistics fail the thread-isolation check below.
Unequal first-hit exposures cannot produce unbiased comparative percentiles.

## Function Attribution Refused

The main profile contains three calls to the WSGI wrapper despite one selected
HTML request. Server events within that profile interval include:

- Target HTML: native TID `70376`.
- Memory probe: native TID `13548`.
- Direct CSS probe: native TID `35640`.

An isolated two-thread reproduction under the same Python 3.13.7 interpreter
confirmed that cProfile records the foreign thread's distinctive function.
The reproduction source and output are:

- `D:/AIGC/d9-1122/function-profile-thread-scope-probe.py`
- `D:/AIGC/d9-1122/function-profile-thread-scope-r1.json`

That output records separate native TIDs and normal thread completion. The
standard-library `profile` comparison records the owner function and excludes
the foreign function in this offline test. This is only a thread-isolation
check, not a native application qualification or an overhead measurement.

The earlier validator correctly joined the profile envelope to a request, but
that metadata join did not prove the profiler engine's function rows belonged
exclusively to that thread. Single-thread tests and calibration missed this
boundary. Consequently `function_attribution_eligible=false` and
`function_attribution_status=REFUSED_CROSS_THREAD` are authoritative for analysis.
Do not use the retained function rankings as same-request hotspots or as a
basis for a product optimization. The raw statistics, producer statuses and
initial review/test evidence are preserved, not rewritten into a passing claim.

## Remaining Decision

No product code, SDK, KPI, sample counts, stop budgets or real-leak thresholds
changed. The historical CSS 119.3983 ms and draft_edit ratio 1.58434 failures,
PERF.OPTIMIZE, PERF.CERTIFY, CLOSE.R and WIN.ACCEPT remain open.

The next diagnostic must first prove engine-level thread isolation with
concurrent negative fixtures, then calibrate profiler perturbation before a
new separately authorized application window. The offline `profile` result is
one candidate, not an approved replacement. Do not reuse this cProfile packet
for function attribution on the tested interpreter. No further application
sampling was performed after discovering the scope defect.

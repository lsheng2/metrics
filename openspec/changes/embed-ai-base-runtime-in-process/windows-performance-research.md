# Windows Performance Research

Research date: 2026-11-20. This is method selection for the existing MDB-2
performance phase, not a performance result or an additional task ledger.
Owner direction remains: identify the mechanism before changing a KPI.

## Evidence Hierarchy

1. Current source and frozen artifact identity establish what is measured.
2. Unprofiled, controlled HTTP/stream observations establish response latency.
3. Component spans and CPU/process observations localize cost.
4. A paired, narrowly scoped profiler capture investigates a specific mechanism.
5. A fresh unprofiled run tests whether an optimization actually helped.

Recorder success, a flame graph, or a passing profiled test does not establish
performance acceptance. Historical failed and instrument-invalid runs remain
available; later successful observations do not explain them.

## Tool Decisions

| Tool | Useful question | Decision and limitation |
| --- | --- | --- |
| Existing HTTP/stream sampler and monotonic clocks | Do the signed B3/B6/B9 observations meet their limits? | Primary qualification path after measurement-integrity repairs. Do not replace it with a new load framework. |
| Windows process/CPU counters | Was a measured interval busy, and which owned processes/threads existed? | Retain start/end/every-minute observations and identify foreign Metrics workloads. Counters do not identify a blocked call's cause. |
| WPR/ETW plus WPA or the existing Microsoft TraceProcessor tools | Was a named thread running, ready but not scheduled, or waiting on I/O? | Preferred deeper Windows investigation after a reproducible outlier. Correlate owned PID, TID, operation window and trace coverage. |
| py-spy 0.4.3 | Which Python frames occur during a reproduced slow operation? | Optional diagnostic aid, never the qualification clock. Use a paired unprofiled control and record sampling errors. |
| CPython cProfile | Which Python call paths account for CPU work in a bounded operation? | Separate diagnostic run. Its timings are not benchmark results, especially across Python/C boundaries. |
| pyperf | How should small repeatable Python microbenchmarks handle warmup and process isolation? | Method reference or later owner-local microbenchmark only; do not substitute its automatic recipe for signed end-to-end HTTP sampling. |
| Browser navigation/resource timings | Is a user-visible delay in server response, assets, or rendering? | Optional localization if HTTP results do not explain the UI. Do not relabel B6's page-plus-assets HTTP metric as LCP/INP. |

No new system service, startup task, global profiler, security-policy change,
CPU-affinity change, power-plan change or antivirus exclusion is part of this
plan. Linux, WSL and Linux-container tooling are not execution dependencies.

## Clocks And Attribution

CPython 3.13's `perf_counter` and `monotonic` use the same monotonic clock.
The Windows implementation uses the performance counter. Differences between
readings are meaningful; the arbitrary epoch is not a wall-clock timestamp.
Use an adjacent UTC/monotonic pair when correlating a run with ETW, and retain
the alignment limitation rather than implying exact clock calibration.

Wall duration includes waiting. Process CPU and thread CPU exclude waiting and
have different scopes. They are complementary observations, not additive
components. Do not add overlapping server, file-I/O, runtime-stop and parent
durations. Record setup, steady-state measurement and cleanup separately.

WPA's sampled CPU view helps attribute executed work. Its precise CPU view and
context-switch information help distinguish running, ready and waiting time.
A stack sampled in SQLite or a file close is only an observation of location;
it does not prove how long that call ran or which driver caused a delay.

## Profiler Perturbation And Capture Bounds

The py-spy documentation warns that nonblocking remote reads can produce
partial samples or errors. The retained local 50 Hz run had 99 sampling errors;
the lower-rate three-case run still had 37. Those captures must not be used
to tune production deadlines or establish an unperturbed latency distribution.
Do not infer that nonblocking sampling has zero performance impact.

WPR file mode is not inherently size bounded. Previous broad local captures
produced multi-gigabyte ETLs, and the Minifilter run lost events and had a capped
export. Prefer a short kernel-only capture around one reproduced operation.
Use Minifilter only when an observed file-I/O delay makes driver attribution
the next discriminator, not as a default all-system collection.

Reuse the existing restricted collector design if privileged collection becomes
necessary: only the collector is elevated; application tests keep the ordinary
token; record one owned instance; stop/save in cleanup; retain failed captures.
The prior temporary elevated helper exited on 2026-11-19 and is not current
permission state. A new Windows consent may be needed, but non-elevated baseline
and harness validation do not wait on it. Never launch repeated pending prompts.

Trace analysis must record event/buffer loss, initialization coverage, PID/TID
association, truncated exports and timestamp conversion rules. Zero reported
loss is necessary evidence about the recorder, not proof that every relevant
activity is represented in a selected export.

## Existing Local Findings

- Functional Windows acceptance exists separately at source `ff09d6f`; current
  Dashboard main `eb84aa23` includes the subsequently checked metadata hints.
- The original dev4 wheel remains the measured runtime. AIB main's dev5
  Sample/RCA candidate is not a replacement baseline for Dashboard.
- The retained performance dispatcher intentionally refuses execution.
- The retained stream helper expects eight events, whereas the S0b B3 recipe
  used fifty. The performance lane must explicitly preserve the signed count.
- S0b's saturation run measured both a loop-backed short request and a direct
  AI asset every second. The retained helper's echo-only sampling is incomplete.
- The designed approximately 6.5-second unread-client flush wait is distinct
  from the historical later close/commit failures. Neither becomes a new KPI.
- Earlier diagnosis and the later functional closeout contain different
  failures and source revisions. Preserve those distinctions when selecting
  new experiments.

## Primary Sources

Official pages/source files were retrieved directly on 2026-11-20. The web
search interface returned no usable content, so the research used the official
HTTP endpoints and versioned upstream source below. Raw copies and SHA256s are
retained in the private performance evidence root, not committed as source.

- Microsoft WPR overview:
  https://learn.microsoft.com/en-us/windows-hardware/test/wpt/windows-performance-recorder
- Microsoft WPR command-line options:
  https://learn.microsoft.com/en-us/windows-hardware/test/wpt/wpr-command-line-options
- Microsoft CPU analysis:
  https://learn.microsoft.com/en-us/windows-hardware/test/wpt/cpu-analysis
- CPython 3.13.7 clocks:
  https://github.com/python/cpython/blob/v3.13.7/Doc/library/time.rst
- CPython 3.13.7 profiling:
  https://github.com/python/cpython/blob/v3.13.7/Doc/library/profile.rst
- CPython 3.13.7 asyncio diagnostics:
  https://github.com/python/cpython/blob/v3.13.7/Doc/library/asyncio-dev.rst
- py-spy 0.4.3 options and platform support:
  https://github.com/benfred/py-spy/blob/v0.4.3/README.md
- pyperf sampling methodology:
  https://github.com/psf/pyperf/blob/main/doc/run_benchmark.rst

Local supporting records: `evidence/windows-external-diagnostics.md`,
`evidence/windows-root-cause-diagnostics.md`, `evidence/windows-functional-closeout.md`,
`s0b-spike-report.md`, and `evidence/windows-w2-validation.md`.

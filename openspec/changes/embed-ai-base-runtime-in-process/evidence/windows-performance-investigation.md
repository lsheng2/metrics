# Windows Performance Investigation Checkpoint

Date: 2026-11-21. Status: investigation in progress; elevated kernel capture
verified, but the anomaly was not reproduced in that run. Performance
acceptance has NOT passed.

This report supplements the existing performance plan and sole `tasks.md`.
The [machine-readable evidence index](windows-performance-investigation.json)
pins 18 private result/audit artifacts by SHA256, including the kernel
follow-up audit and its nested references. It is a later parent audit, not a
rewrite of any original producer receipt.

## Scope And Candidate

- Windows, owned synthetic state and loopback only.
- Runtime remains `ai-base-runtime==0.1.1.dev4`, wheel SHA256
  `b332f338f77bf2e966de7495eea6b5968606eb670287588d97a3a4d82905ec94`.
- AIB main remains `6591ad57f15c78f575cf43dd5d7d3e076df99f7b`.
- No product behavior, installed runtime files, KPI or production timeout was
  changed. Post-experiment admission reverified all 131 runtime package files,
  no legacy SDK, no user-site import and no unowned `.pth` file.
- No Linux, real-provider/model, release, push or main-branch merge occurred.

## What Ran

| Run | Dashboard source | Result and meaning |
| --- | --- | --- |
| pilot-r6 | `103929236c4ee344710f1ce83ca63854aa9a63bc` | 360 samples, complete replay, no numeric violations, normal cleanup; pilot is ineligible |
| diagnostic-r1 | `93b0bea33dfb595f6bde42db36aa795f6fd9ccd9` | Incomplete after 2,880 development sequential samples; three direct-asset read timeouts; no c4/production completion |
| asset-trace-smoke-r1 | `7e4478da76c6d0f3721739bf69df4b9126b3797e` | 40 samples, 3,190 client requests, 19,076 server events, no trace loss or anomaly; instrumentation calibration only |
| asset-trace-r1 | same `7e4478d` | Anomaly captured after 1,557 samples with server boundary timing enabled |
| asset-control-r1 | same `7e4478d` | Anomaly captured after 2,250 samples without server timing wrappers |
| asset-etw-r1 | `7035834cd3f382a0e9cec6d528fa62f5c1203e42` | 3,648 samples in 600.115 seconds; no anomaly trigger; two bounded kernel captures saved; diagnostic only |

The localization runs keep client timing/correlation in both modes. They are
not an uninstrumented KPI qualification or a substitute for the full recipe.
All workloads stopped normally without force; follow-up checks found no owned
processes/listeners or remaining measurement guard. WPR is not recording.

## Observed Failure

The original diagnostic's three missing direct-asset slots were 457, 460 and
461, all during `seq/bug_trend/candidate_saturated/block 3`.
Their immediately preceding loop-short requests took about 1.8-5.5 ms.

The overlapping page sample, index 36, took:

- total: 7,362.774 ms;
- HTML: 23.221 ms;
- asset/component phase: 7,339.553 ms.

This was the largest of the 2,880 page samples; the next largest was about
462 ms. Stream events continued during the anomaly. These observations narrow
the investigation to asset/request handling rather than ordinary HTML
generation or a continuous whole-process freeze.

The request used HTTPX's configured two-second read wait, not a two-second
whole-transaction deadline. No outer watchdog fired. The full diagnostic was
correctly retained as `FAIL` / `INCOMPLETE`; its partial data cannot establish
any full-recipe KPI pass.

## Localization And Control

The same CSS bytes, size 14,840 and SHA256
`ab5bacd6bc30ce6113f2b5a81795551c426cbb2dbeac68eb69b1075bc1753c63`,
were served by a separate authenticated memory-control endpoint in the
isolated diagnostic fixture. The real SDK asset route was not cached or
replaced. SDK/WhiteNoise wrappers only timed calls in memory; no installed
files, response iterators or file-wrapper behavior were modified.

| Observation | Traced run | Untraced-server control |
| --- | ---: | ---: |
| Triggering Dashboard static request | 2,182.545 ms (`charts.js`) | 2,219.169 ms (`pane-layout.js`) |
| Largest retained AI probe request | 1,694.450 ms | 1,942.156 ms |
| Largest retained memory-control request | 15.334 ms | 11.823 ms |

For traced CSS request `asset-trace-r1-probe-99470`:

- client to WSGI entry: 0.840 ms;
- complete client request: 1,694.450 ms;
- SDK resource-resolution span: 1,688.570 ms;
- manifest-materialization span, enclosing resolution: 1,690.379 ms;
- asset-materialization span: 2.114 ms;
- client time after response headers: 0.137 ms.

The slow resolution span reported zero thread CPU time at the available
counter granularity. That is consistent with waiting, not proof of a specific
kernel wait or driver. The overlapping Dashboard static request spent about
2,180 ms before WSGI entry, while its measured WhiteNoise opening took only
0.477 ms. Thus the observations do not justify blaming WhiteNoise file opening
for that particular request.

Installed-source inspection confirms that successful dev4 asset requests
resolve resource paths, open/parse the manifest, and open/read/hash asset bytes
before `start_response`. WhiteNoise caches discovery/stat metadata but opens
the selected file per GET. A candidate access-log 200 is a header/application
boundary observation, not proof that the response body reached the client.

## Limits And Neutral Interpretation

- The seconds-long symptom also occurred without server timing wrappers.
  It is not solely an artifact of those wrappers.
- The software observation boundary is now concrete: a slow SDK resource
  resolution and a simultaneous pre-WSGI delay. The responsible Windows
  component, I/O wait, scheduling delay or shared cause is NOT yet established.
- Nested server spans overlap; do not add their durations.
- Bounded trace buffers discarded prefixes: traced client 49,542 rows and
  server 495,558 events; control client 93,471 rows. The correlated anomaly
  records remain present. Retained tails are not whole-run distributions.
- A fast memory control is a useful discriminator, not proof that a cache
  change would resolve every observed delay.
- The original functional milestone remains separate. None of these
  experiments promotes historical functional bindings or closes `WIN.ACCEPT`.

## KPI And Next Gate

Do not retune KPI-P1 through KPI-P4 yet. Ordinary probe/control timings are
far below 100 ms, while the failures are seconds-long waits rather than a small
threshold-edge fluctuation. Investigate the waiting mechanism first.

The earlier ordinary-token WPR CPU capture attempt failed with exit 1, error `0xc5585011`,
`Failed to enable the policy to profile system performance.`
That failure remains historical evidence, not the current blocker. A fresh
UAC-approved collector session successfully recorded both follow-up windows
without changing machine policy; the application remained unelevated.

### Elevated Follow-Up

The same owned page/asset workload ran for 600 seconds with four held streams.
Neither the one-second diagnostic trigger nor a request error occurred. The
retained client tail reports maxima of 110.343 ms for page/asset requests,
46.399 ms for the probe role, and 14.067 ms for the memory control. These are
not full-run percentiles: 182,401 client rows and 1,290,704 server events were
discarded from the bounded buffers.

| Kernel window (Asia/Shanghai, November 21) | Reported event/buffer loss | Largest exported host-associated file interval | ETL bytes |
| --- | --- | ---: | ---: |
| 08:24:56.977-08:26:30.324 | 0 / 0 | 20.2084 ms | 4,567,597,056 |
| 08:29:52.876-08:31:25.689 | 0 / 0 | 8.0587 ms | 4,726,980,608 |

Both WPR start/stop calls returned zero. The existing Microsoft TraceProcessor
decoder selected 373,850 / 387,512 file activities and exported the longest
3,000 per category. No Minifilter events were selected; that provider was not
enabled. Zero reported loss is not proof of universal ownership or event
coverage, and these two windows do not cover all 600 seconds. No new
scheduling-stack attribution is claimed without a reproduced slow request.

The stop/save/hash phases took about 130 and 248 seconds. Those are collector
costs, not application shutdown latency. The 9,294,577,664-byte total exceeded
the existing 8 GiB *admission* threshold after the second capture; that policy
was not a final-file cap. No further capture was admitted, and the temporary
helper acknowledged `EXITED`. Both named WPR instances were then checked as
not recording. Nine owned PIDs, port 7857 and the measurement guard were absent.
Receipt/witness and ETL hashes matched; all 131 admitted runtime files and the
frozen wheel hash matched again.

This establishes usable elevated collection and an anomaly-free bounded run,
not a fix or an explanation of the original failure. Capturing no anomaly
cannot distinguish intermittent behavior from profiler perturbation.
Docs impact is limited to this troubleshooting checkpoint and the current
reporting-delivery guide; no product interface or operational setting changed.

Next:

1. Independently reviewed next experiment: a small circular kernel buffer
   for scheduling/ready-thread and file/disk events, saved on the existing
   one-second diagnostic trigger. Keep the 90-second recording limit and
   other admission limits; buffer bytes do not guarantee retained seconds.
   Verify actual span coverage instead of repeating broad file-mode captures.
2. Preserve the ordinary-token workload, original trigger and limits. Require
   a slow request plus its request id, PID/TID, adjacent UTC/monotonic clocks
   and clock uncertainty in the same usable capture. Current request receipts
   have approximate UTC/QPC anchors, not a calibrated slow-request witness.
   A changed fixed collector must be separately frozen and admitted, not
   substituted into this exited session or given a larger allowance silently.
3. Attribute the delay before selecting an owner fix. A verified, immutable
   resource snapshot/cache is a possible SDK design option, not an implemented
   or validated fix. Any new AIB wheel needs the existing owner/refreeze and
   Dashboard reacceptance gates; never patch the installed candidate.
4. Return to the complete 11,520-sample diagnostic, then independent review,
   fresh certification and the actual combined qualifier. No partial or
   instrumented run closes those gates.

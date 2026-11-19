# External Diagnostics Continuation

Status: root cause unconfirmed. This is a diagnostic checkpoint, not a native
certification, KPI result, or functional acceptance.
Initial source baseline: `4af59f8b139d0ac684c2985b2d6a4bef6c215ae1`.
2026-11-19 diagnostic source baseline: `19d4bfba864bde43762ee4e84bf941bce0c5db93`.
Docs impact: none. Diagnostic evidence only; no product behavior, public
interface, configuration contract or operator procedure changed.

## Scope

The owner authorized continued root-cause work and assessment of KPI, architecture,
and bugs. System profiling permissions were authorized; a prior UAC-approved
synthetic smoke verified WPR start/stop. Subsequent elevated collector launches
required separate Windows consent responses. The temporary session below
demonstrated reuse of one approved elevated process for fixed collectors only
and has since exited.

The candidate wheel, production timeout settings, application code and user data
remain unchanged. New probes use synthetic state on D and the existing no-dotenv
test entry. Only the ETW collector is elevated; the application runs under the
original normal token.

## Comparisons

Artifact base:
`D:/AIGC/artifacts/mdb2-windows-20261117/root-cause-analysis/`.

| Evidence | Observation | Permitted conclusion |
| --- | --- | --- |
| `external-runs/96dcb704-310d-4128-a5c4-a647b1693721` | Frozen non-reader CTRL_BREAK case failed with `server_close_failed`, `server_thread_alive`, then runtime timeout. External py-spy at 50 Hz reported 99 stack-read errors and sampling lag. | A failure was reproduced under sampling, but this is not an unperturbed timing measurement. |
| `external-runs/a78a2218-d7c8-4b84-9c3c-4b019f8e91ed` | Same diagnostic launcher and case with no profiler passed. | One control passed; it does not explain historical failures or establish causality by itself. |
| `external-runs/442af593-b543-47f3-af30-ee5c79c94506` | Same case with memory-mode ETW, no py-spy, passed. | Observed native behavior in this run only, not closure of the complete acceptance set. |
| `etw-runs/4cf180a6-ccb1-4eb0-92d0-530fd162f643` | WPR start/stop succeeded; ETL 465,567,744 bytes. | Collector capability confirmed. |
| Same ETL, TraceEvent extraction | 1,400,975 decoded events; 1,115,972 FileRundown events; reported events lost = 0. | No reported loss is not proof of complete process/file initialization coverage. |
| Same ETL, TraceProcessor association | Many associated activities lacked issuing process/thread context; some apparent durations started at the trace boundary. | Do not use these entries to claim a 20-second disk delay, a responsible driver, or a new KPI. |
| `etw-runs/c18a58e8-e6a2-492d-b9e0-2ec797b1e454/not-started.json` | New file-mode/Minifilter request remained at UAC consent; three planned tests never started. The verified waiting caller was withdrawn. | Authorization/UI checkpoint, not an application or ETW capture failure. |
| `external-runs/5740388b-be78-439b-960a-1a49665a36b3` | Three observation-policy cases passed in 49.85 s with 5 Hz py-spy. Independent review counted 37 sampling errors. | No reproduced slow stop; not frozen-policy qualification or a complete sampled timeline. |
| `etw-runs/e3e832a4-8c30-4181-93ad-7c43bd6425bf` | File-mode Minifilter ETL saved: 5,283,774,464 bytes. Raw decoder saw 41,551,618 events, reported 8,909 events lost, and omitted 28,766,545 selected events after its export cap. | Retain raw trace; capped extraction and missing events cannot establish complete causal attribution. |
| `external-runs/ea7f8665-ed9b-4faf-8288-8710ae6fc8c6` | Frozen-policy, no-profiler three-case control: 3 passed, 9 deselected in 46.68 s. | Current selected cases passed without extending production deadlines; historical failures remain open. |
| `external-runs/edbe052b-477c-4e2b-8637-cfe92651f93f` | Same frozen-policy selection, kernel ETW without Minifilter or py-spy: 3 passed, 9 deselected in 54.35 s. | No reproduced failure in this paired diagnostic run; suite time is not shutdown latency. |
| `etw-runs/085cac15-357b-4b1d-b9ac-99c4f83c43a0` | Reused the elevated session; ordinary-token tests; saved 5,212,471,296-byte ETL with start/stop exit 0. | Permission reuse verified; decoder association/loss checks remain separate from recorder success. |
| `external-runs/2610edf9-a20f-4929-85f2-184be160d41d` | Full B5 order, frozen policy, no py-spy or ETW: 12 passed in 165.58 s. All wrappers/descendants returned 0 without forced cleanup; subsequent PID review found no matching live processes. | Full diagnostic order passed, but it did not reproduce or explain the historical failure; not fresh formal certification. |

The external launcher checks that the interpreter PID is the owned wrapper or
its descendant before attaching py-spy. Its per-run `attachments.json` records
the wrapper, interpreter, sampler, arguments and exit result.

## Analysis Tools

The data decoders use Microsoft libraries, not a custom ETL binary parser:

- `Microsoft.Diagnostics.Tracing.TraceEvent` 3.2.8 for raw event inspection.
- `Microsoft.Windows.EventTracing.Processing.All` 1.12.10 for file/disk and
  Minifilter activity association.
- Tool assemblies execute using the already installed .NET 10.0.15 runtime.
- Sources, package locks and binaries are under `D:/AIGC/tools/performance/`.
  Application Python dependencies were not changed.

SDK first-run initialization generated one untrusted localhost development
certificate while building the diagnostic tool. Its exact new thumbprint and
creation time were verified, no user/machine trust entry existed, and that
certificate plus key were removed. The cleanup receipt is
`tool-bootstrap-certificate-cleanup.json`. This was not a security-policy change
or a proposed application workaround.

The decoder now records timestamp/duration precision flags. Those flags do not
by themselves prove capture completeness. Missing initialization and ownership
association still require comparison with a better-covered trace.

The 2026-11-19 file-mode kernel trace has a useful association result after a
diagnostic exporter correction. The original exporter incorrectly discarded
all converted durations when `TraceTimestamp.IsPartial` or
`TraceDuration.IsPartial` was true. Microsoft package XML describes that flag
in terms of unavailable raw `Value`; converted `DateTimeOffset` / `Duration`
values remain available. It is not a standalone missing-event indicator.

A regression failed against `owned-io.json`, and passed against the separately
saved `owned-io-converted.json`. The revised tool preserves the flags, rejects
negative timestamp intervals, records loss metadata, and is built separately
as `owned-traceprocessor/bin-converted-time/OwnedTraceProcessor.dll`.
Original exports and binaries remain available. No application code changed.

The new export reports zero lost events and zero lost buffers, 236,826
PID-or-path-selected file activities, 4,583 disk activities and no Minifilter
activities. It retains the 3,000 longest entries per category; it is not an
exhaustive activity export. `stop-window-correlation.json` then filters by each
owned interpreter PID and its stop window, using the adjacent wall/monotonic
identity timestamps as an approximate alignment, not formal clock calibration.

| Passing case | Largest exported file interval in stop window | Largest exported disk interval | SDK stop |
| --- | ---: | ---: | ---: |
| Non-reader stop-file | 40.550 ms | 27.115 ms | 123.371 ms |
| Non-reader CTRL_BREAK | 11.600 ms | 10.800 ms | 52.149 ms |
| Real-chat lifetime | 8.995 ms | 8.940 ms | 71.325 ms |

These are measurements in passing cases, not explanations of the older failed
cases. Zero reported loss alone is still not universal completeness. The
improved PID/thread/path associations and bounded timestamps support these
specific rows, not a claim that second-scale I/O or scheduling delays cannot
occur later. Do not sum file, disk and SDK intervals, which overlap.

## Independent Checks

Agent Singer (`gpt-5.5`, `xhigh`) produced `kpi-review.md` and
`pyspy-perturbation-review.md` in the artifact base, without executing workloads
or changing application code.

- The 10-second normal-stop proof, absolute 6.5/7.5-second host stages, 1-second
  SDK stop bound and final watchdog are different contracts, not one performance
  percentile that can be tuned interchangeably.
- In py-spy 0.4.3's non-native `--nonblocking --idle` path, the reviewed source
  did not show per-thread suspension as the explanation. Cross-process reads,
  thread enumeration and timer-resolution changes can still perturb execution.
- No supported historical application root cause was established by this review.

Agent Noether (`gpt-5.5`, `xhigh`) prepared metadata-validated memory and separate
file-mode profiles in `light-etw/`. They are app-close profiles, not instructions
to reboot Windows. Static WPR metadata validation is not a runtime capture pass.

## Capture Policy

Use a fresh run directory and default to the file-mode kernel-only variant.
The Minifilter variant is reserved for a short, localized driver-attribution
question; do not repeat its lossy broad capture as if it were valid evidence.
The owned collector limits recording to 90 seconds and stops
recording if temporary trace files exceed a 512 MiB soft limit. Post-processing
and metadata can make the final artifact larger; this is not a final-file hard cap.

The completed three-case selection was non-readers and real-chat lifetime stop.
The diagnostic observation policy allows natural completion beyond the production
stage limits; it does not select new production values or qualify the application.
A 5 Hz external Python sampler is optional, with an unprofiled control retained.

The previous unconfirmed UAC launch was withdrawn by stopping only its exact
pending PowerShell caller, verified by command and creation identity. The
collector checks the withdrawal marker before doing any recording. That guard
was exercised without elevation and refused to start. If the old Windows consent
dialog remains visible, dismiss it; a new attempt must use a new run directory.

The old UAC checkpoint is superseded by the temporary session below. Do not
leave repeated elevation requests waiting indefinitely.

## Temporary Unattended Session

On 2026-11-19 the owner requested reuse of approved UAC rather than having to
remain at the PC. A temporary helper was approved and verified as elevated:
`admin-sessions/ee0d4c10-7a8f-4be2-8db9-3c63d3fa4857`.

- Only `capture`, `stop`, `status`, and `exit` requests are accepted. Capture
  modes select fixed, hashed collector tools; no caller-supplied command or
  executable is accepted.
- Private control files have protected NTFS ACLs for the current user, SYSTEM
  and Administrators. The capability token is not copied into evidence.
- The session accepts work for at most eight hours (expiry 2026-11-19 13:34
  Asia/Shanghai), at most six captures, and stops admitting captures once
  completed ETLs total 8 GiB. This total is an admission limit, not a hard
  final-file cap; one capture can exceed the remaining allowance.
- Each capture has the existing 90-second recording limit, 512 MiB temporary
  file soft limit, and a six-minute collector safety deadline. Save/metadata
  costs can substantially exceed the temporary-file threshold.
- No service, scheduled task, UAC change or machine security-policy change
  was installed. The ETW test driver explicitly refuses to launch application
  tests if its token is elevated.
- A regression first reproduced capture dispatch after an exit request; the
  helper now refuses new captures once closing. Negative tests cover token,
  action, mode, unknown fields and capture allowance.
- `state.json`, `launch.json`, and GUID-matched request responses record the
  session lifecycle. An actual new capture completed through this session
  without another UAC launch.

The helper is for this diagnostic packet only. Explicitly exit it when no
further privileged collection is needed; do not retain it as a permanent
administration interface.

At 2026-11-19 05:55 Asia/Shanghai the helper acknowledged `EXITED` with no active
capture. `unattended-cleanup.json` records no remaining owned helper, collector
or compiler-server PIDs. The compiler server was created by this tool build and
its command/creation time were checked before stopping it. No repeated
elevation request remains pending. The eight-hour allowance was not consumed
or converted into a persistent privilege.

## Frozen-Control Comparison

`frozen-control-comparison.json` binds the six new case logs by SHA256.
All six processes returned 0 without forced cleanup and reported confirmed
persistent-state flush. SDK stop durations range from 44.7 to 123.4 ms.
The four non-reader cases spent 6.48-6.50 seconds in the designed flush wait;
the two real-chat lifetime cases spent less than 1 ms in that wait.

This does not establish a latency distribution or explain the older
tempfile-close and SQLite-commit/close failures. It does show that these passing
cases did not need observation-policy timeout extensions. Do not sum overlapping
stage timers or call total pytest duration a shutdown measurement.

Read-only agent Feynman (`gpt-5.5`, `xhigh`) reviewed the earlier three-case
observation run separately in `observed-three-case-review.md`. It confirmed
clean exits and the non-reader flush-window wait but found 37 py-spy sampling
errors. Its sampled stacks do not establish the root cause. Re-instrumenting
the already-designed unread flush wait is not a substitute for catching the
historical later close/commit failure.

`unattended-package-integrity.json` rechecked all 131 admitted package files
with zero mismatches. `unattended-tools-manifest.json` binds the helper,
negative tests, corrected exporter source and separately built binary.

## KPI And Architecture Disposition

No production KPI reset or architectural rewrite is currently justified by the
available causal evidence. A functional failure remains open; this is not a claim
that the implementation has no bug. Do not replace the failed normal-stop proof
with a sampled or extended-budget pass.

The next decision must follow valid evidence: fix a demonstrated ownership,
ordering or runtime defect if present; otherwise classify the measured lower-level
latency and then reconsider internal stage allocation and the stated operating
conditions. Keep clean exit, persistence and abnormal-stop reporting distinct.

The full-order no-profiler diagnostic also passed, so repeating identical
successful runs or extending timeout values is not the next discriminator.
The remaining question is the historical later close/commit failure: record
bounded queue submit/start/end and shutdown phase boundaries, then correlate
a reproduced failure with the now-usable kernel I/O path. Keep the designed
6.5-second unread-client flush wait separate from that later failure.
This is a diagnostic checkpoint, not a topic closure or an owner decision gate.

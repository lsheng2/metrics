# External Diagnostics Continuation

Status: root cause unconfirmed. This is a diagnostic checkpoint, not a native
certification, KPI result, or functional acceptance.
Source baseline: `4af59f8b139d0ac684c2985b2d6a4bef6c215ae1`.
Docs impact: none. Diagnostic evidence only; no product behavior, public
interface, configuration contract or operator procedure changed.

## Scope

The owner authorized continued root-cause work and assessment of KPI, architecture,
and bugs. System profiling permissions were authorized; a prior UAC-approved
synthetic smoke verified WPR start/stop. Subsequent elevated collector launches
can still require a separate Windows consent response.

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

## Next Capture

Use a fresh run directory with the file-mode Minifilter variant and a short
failure window. The owned collector limits recording to 90 seconds and stops
recording if temporary trace files exceed a 512 MiB soft limit. Post-processing
and metadata can make the final artifact larger; this is not a final-file hard cap.

The intended three cases are the non-reader cases and real-chat lifetime stop.
The diagnostic observation policy allows natural completion beyond the production
stage limits; it does not select new production values or qualify the application.
A 5 Hz external Python sampler is optional, with an unprofiled control retained.

The previous unconfirmed UAC launch was withdrawn by stopping only its exact
pending PowerShell caller, verified by command and creation identity. The
collector checks the withdrawal marker before doing any recording. That guard
was exercised without elevation and refused to start. If the old Windows consent
dialog remains visible, dismiss it; a new attempt must use a new run directory.

Resume requires the user to be available for the new UAC confirmation. Do not
leave a repeated unattended elevation request waiting indefinitely.

## KPI And Architecture Disposition

No production KPI reset or architectural rewrite is currently justified by the
available causal evidence. A functional failure remains open; this is not a claim
that the implementation has no bug. Do not replace the failed normal-stop proof
with a sampled or extended-budget pass.

The next decision must follow valid evidence: fix a demonstrated ownership,
ordering or runtime defect if present; otherwise classify the measured lower-level
latency and then reconsider internal stage allocation and the stated operating
conditions. Keep clean exit, persistence and abnormal-stop reporting distinct.

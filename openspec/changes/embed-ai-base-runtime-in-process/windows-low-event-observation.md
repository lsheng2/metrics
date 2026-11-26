---
id: MDB2-WIN-LOW-EVENT-20261126
title: Scheduler-first Windows observation
status: accepted
owner: Dashboard validation
created: 2026-11-26
last_reviewed: 2026-11-26
docs_impact: operations
human_docs: [docs/development/reporting-delivery.md]
implemented_by: [D:/AIGC/d9-1122/low-event-1126/run_kernel.py]
tests: [D:/AIGC/d9-1122/low-event-1126/test_scheduler.py, D:/AIGC/d9-1122/low-event-1126/test_observation.py]
supersedes: []
superseded_by: []
---

# Low-Event Windows Observation Design

## Decision And Scope

The owner authorized redesign and independent review on 2026-11-26, then
approved the next stage's fresh bounded UAC and reuse within its original expiry.
Keep the existing `tasks.md` and 28-node closure DAG; this is the PERF.PROBE
method boundary, not a new performance policy or parallel execution ledger.
The current stage is private implementation, independent code review and one calibration.
The diagnostic window needs a separate go decision after calibration evidence.

Do not change AIB, the installed dev9 payload, application behavior, r3 KPI,
real-leak detection, production stop limits or formal sample counts. No Linux,
provider/model, production data, cache optimization or full-qualification run.
The exact candidate remains `ai-base-runtime==0.1.1.dev9`, wheel SHA256
`c729b2c9a0c37c86ef811ad86dfda613548c516a74df414fb663074ad20575ec`.
Planning baseline: Dashboard `d7dd699`, AIB `1a6ac98`; implementation must freeze
the later actual clean source, not pretend that a documentation commit is that baseline.

## Evidence And Question

Private immutable references, all under `D:/AIGC/d9-1122/`:

| Reference | Established fact | Not established |
| --- | --- | --- |
| `static-wait-1125/report.md` and `checkpoint.json` | A same-request CSS observation: client937.767ms, manifest resolution931.2499ms, coarse thread CPU increment0; its exclusive window was invalid | Precise off-CPU time, an OS cause, or the cause of the separate bug_trend burst |
| `kernel-inspection-1126/retention-analysis.md`; `kernel-decoder-1126/artifacts/survey-kw1126-cal2.json` | R2 contains1,562,853events, including1,060,774FileRundown,22,453CSwitch,11,855ReadyThread and73,032stack events | That rundown caused overwrite/loss or that a smaller profile will retain the request |
| `kernel-wait-r3-1126/kw1126-cal3/calibration-refusal.json` | R3 reports21,698lost events, independently confirmed by tracerpt, and zero selected target kernel rows; no native proof or diagnostic followed | Application failure, AIB failure, or useful same-request scheduling coverage |

Pin historical claims through the refusal's referenced SHA256 files and the
survey's references; verify their bytes and these exact fields before review.
The earlier calibration/code-review passes do not qualify this new method.
The new question is deliberately smaller: **during the same slow manifest
resolution interval, is its native thread running, ready-but-not-running,
blocked, or not reconstructible?** A `bug_trend` page and a direct CSS request
are different observations. Do not silently change the target back to page HTML.

## Alternatives

| Option | Information and cost | Decision |
| --- | --- | --- |
| Application boundary timing only | Least extra collection; existing evidence already localizes a long resolution span but cannot separate scheduling from blocking | Retain as the correlation/control layer, not sufficient alone |
| Scheduler events plus sparse markers | Remove file/rundown, image and stack families at collection; preserve thread-state discrimination | Recommended next method, subject to native calibration |
| File-centric or full-stack tracing | May identify a file operation or stack after blocking is established; greater volume and privacy/decoder requirements | Not this packet; needs an evidenced question and separate review/authorization |

Do not enlarge buffers, add repeated flushes, change decoders to ignore loss,
or claim that post-capture PID filtering reduces kernel event production.
The proposed reduction is in enabled event families, not merely exported rows.

## Collection Contract

Create a new versioned private method under
`D:/AIGC/d9-1122/low-event-1126/`; do not edit R1/R2/R3 or installed packages.
Reuse the existing collector ownership/request protocol, SLE cleanup,
measurement guard, bounded buffers, clock helpers and request-id join.
Version only changed helpers and bind every imported external helper hash.
Do not introduce a second process manager, generic admin broker or profiler framework.

The WPR profile has exactly `ProcessThread`, `CSwitch` and `ReadyThread` system
keywords, plus the existing marker GUID
`fc8d33b5-f242-4f27-913e-84ca401125ae` (level4, keyword0x1).
No FileIO/FileIOInit/Filename, DiskIO/DiskIOInit, Loader, CpuConfig,
ThreadPriority, sampled CPU, minifilter, stack collection or inherited base profile.
Do not use CompactCSwitch or an unverified process-level kernel filter.
Reject a forbidden family both in the profile and in decoded event inventory.
Process/thread identity rundown is allowed and reported separately.
Do not describe omission of `CaptureStateOnSave` as disabling automatic rundown.

Keep declared buffers at64x1024KiB kernel plus8x128KiB markers initially.
Query actual owned ETW session properties at start and before save/cancel:
session name/id, buffer size/count, allocated pool and loss counters. Configured
65MiB is not measured allocation; Windows may adjust per-processor reservation.
The combined allocated-buffer stop threshold is128MiB. This is not a
collector working-set limit or a change to application resource acceptance.
An unavailable or ambiguous query prevents calibration admission.

Sparse markers cover capture boundaries, the calibration thread and the first
matching slow request/span; no every-request, every-switch or stack marker.
Maximum128decoded markers. Application timings stay in bounded local memory.
Marker payloads contain synthetic request/capture ids, bounded route kind,
native PID/TID and clock values only: no headers, secrets, bodies, arbitrary
file names, full command lines or enterprise records. Private ETL may still
contain system process metadata; protect its ACL and never commit/upload it.

One admitted SAVE retains the existing single pre-stop flush ordering and
fixed-instance stop/cancel behavior. Its time counts against the original
90-second recording deadline; no renewed deadline or second flush. Flush0
and stop0 are necessary, not sufficient: reject loss or missing coverage.
This isolates the event-family change from a second simultaneous save-method change.

## Calibration And Cost Limits

One calibration, at most30seconds of active work and40measured pages.
Reuse the current development-settings three-arm fixture and its four held
streams; SDK CSS path, status200,14,840bytes and admitted response hash are
verified through the real route. The two-second direct-probe wait is unchanged.
Setup/warmup, active work, save/decode and normal cleanup have separate clocks.
The calibration thread starts only after recorder readiness and exits before
save; it runs in an ordinary-token, owned diagnostic process, never AIB code.
It emits identity/clock markers, performs a bounded CPU segment and a deliberate
native wait released by another owned thread. Record requested and actual
wait/release times; actual ETW transitions, not an assumed Sleep duration,
are the oracle. Scheduling stress, affinity, priorities and system settings
must not be changed to manufacture ready latency.

Require the full deliberate wait -> ready -> running transition and the
calibration thread lifetime in the decoded ETL. Also require real CSS
client/server/clock/payload joins and an admissible scheduler interval for its
server thread. A short CSS request need not contain a wait or ReadyThread event
if bracketing transitions prove it remained running.
The synthetic witness proves measurement capability, not reproduction.

Observation-cost ceilings:

| Resource | Calibration | Later diagnostic |
| --- | --- | --- |
| All decoded native events, including metadata/rundown | <=250,000 | <=1,000,000 |
| Raw ETL plus capture-local temporary files | <=512MiB combined | <=512MiB combined |
| All derived decode artifacts | <=512MiB combined | <=512MiB combined |
| Selected rows / exported markers | <=50,000 /128, no omission | Same |
| Active workload | <=30s /40pages | <=80s /4,000page attempts, first trigger stops admission |

These are investigation-cost guards, not performance KPI. File-size observation
is a stop/admission threshold, not a filesystem quota guaranteeing no transient
overshoot. Record actual peak sizes and failed writes, cancel owned collection
on violation, retain bounded refusal evidence, and never delete old evidence
to make the new capture fit. No disk-free-space admission check.
Decode has one <=120s child deadline inside the existing decoder safety ceiling;
timeouts fail and owned children must be reaped. No unlimited symbol downloads.
Keep the existing360s collector safety deadline,8h nonrenewable session lifetime,
six-attempt ceiling and8GiB session cap as outer limits. This packet admits only
one calibration and, after the separate decision, one diagnostic, not six retries.

## Evidence And Claim Contract

Use a new explicit schema/method id, `scheduler-observation-v1`.
Do not make the old `native_proof.py::require_coverage` FileIO requirement optional,
reuse an old `CALIBRATION_VERIFIED` receipt, or upgrade a failed old ETL.
The new checker owns only the narrower question. Its records remain
`acceptance_eligible=false` and cannot enter formal performance qualification.

Reuse the pinned TraceEvent parser and strict truncation/loss refusal.
A versioned decoder extension must export CPU identity and typed scheduler
payloads, process/thread lifetime evidence and same-QPC ordering, not silently
substitute the event header's PID/TID for the thread being scheduled/readied.
The old indexed decoder's string rows and category bounds are not sufficient
by themselves. ReadyThread's awakened TID and both CSwitch old/new threads
must resolve to a unique owned process/thread lifetime, including pre-existing
server threads; missing mapping, PID/TID reuse or conflicting rundown blocks.
Unknown enum values remain unknown, never repaired into a valid state.

For the exact resolution span retain a request id, process creation identity,
thread lifetime, QPC/frequency, monotonic brackets and precise-UTC uncertainty.
Use a proven incoming state before the span and a closing transition after it,
on every CPU on which the target runs. Preserve timestamp tie ordering and
reject ambiguous contradictory transitions, impossible simultaneous running,
clock discontinuity, missing boundary evidence or a reused thread identity.
Any expanded lookup must stay within the same ETL and existing decode bounds.
Global category minima/maxima, markers alone, zero-loss alone and sparse
target events do not prove interval completeness. Report unknown coverage
instead of assigning the uncovered time to waiting.

Partition only admitted intervals into disjoint running, ready and blocked
durations; their sum must match the span within recorded clock/timestamp
precision. Do not add nested application intervals or coarse thread-CPU
ticks to that sum. Scheduled-running time can include interrupts; it is not
proof of Python execution. Ready time is scheduling delay, not proof of its
responsible competing process. A wait reason is not a file/antivirus/lock cause.

Required outcomes:

| State | Meaning and next action |
| --- | --- |
| `CALIBRATION_VERIFIED` under the new method id | Synthetic discriminator, real route and all integrity/cost/cleanup gates pass; request the diagnostic go decision |
| `CALIBRATION_REFUSED` | Any failure, unknown or budget breach; no workload diagnostic, no automatic rerun |
| `NOT_REPRODUCED` | Authorized bounded diagnostic has no >=100ms direct CSS trigger; cancel without saved diagnostic ETL; root cause remains open |
| `TRIGGER_UNATTRIBUTABLE` | Matching request retained, but loss/coverage/identity/clock/cost prevents state reconstruction; no causal conclusion |
| `TRIGGER_SCHEDULER_CLASSIFIED` | Valid same-request state partition, no root-cause or KPI claim; decide a narrowly evidenced follow-up |

Collection, decoded validity, state classification and normal cleanup are
separate fields. Any failed guard makes the overall result invalid even if
classification data exists. Always retain the original failure/status.

## Ownership, Tests And Execution Gate

| Boundary | Producer -> consumer | Required negative or positive proof |
| --- | --- | --- |
| Profile/cost | Frozen profile + native properties -> collector and proof | Reject forbidden event families, inherited profiles, adjusted pool over cap, lost events, truncated decode, output overflow and observed cap breach |
| Authority | Session/request + original incarnation -> collector/controller | Wrong token/capture, path traversal/reparse, replay, overlapping/expired session, changed helper/profile, unapproved diagnostic and ambiguous child exit cannot start/promote collection |
| Correlation | Ordinary fixture/markers -> decoder/join | Wrong source/wheel/hash/request/PID/TID/lifetime, missing marker, QPC drift, metadata-only coverage, valid other-thread events and late trigger fail |
| Classification | Typed transitions -> state partition/result | Known wait/ready/run plus continuously-running positives; missing edges, TID reuse, CPU migration, tied events, invalid enum, ReadyThread-header confusion and duplicate transitions |
| Claims/cleanup | Real route + guards + SLE -> proof/operator report | 401/503/body mismatch, sample error, forced/unknown exit, live descendants/listeners, missing receipt witness and first-trigger replacement are not success |

Parent is the only writer/integrator and owns privileged collection and app
execution. Architect Planner Reviewer (`gpt-5.5`, `xhigh`, isolated context)
independently checks design now and changed implementation before any UAC.
No separate implementation agent is needed for this small, coupled private method.
Review risk is high: authority, persisted receipts/replay, diagnostics,
cross-file identities, PID/TID reuse and mocked negative boundaries apply.

Authorized implementation sequence:
1. Freeze a new private directory, profile and explicit method contract.
   Add failing actual-consumer tests for each boundary above before helper edits.
2. Implement the narrow profile/exporter/reducer and calibration witness;
   reuse existing owners. No product, candidate, policy or historical edits.
3. Run Tier1 negative/positive tests, Tier2 affected collector/clock/decoder
   suites and Tier3 hygiene. Obtain an independent implementation PASS;
   bind exact helper/build/parser hashes and clean source/environment.
4. Obtain fresh bounded UAC for the newly hash-frozen method, then run only the
   one calibration as Tier4. Verify native inventories, coverage, actual budgets,
   unauthenticated refusals, normal stop and no owned residue.
5. Report calibration evidence. Only a separate go decision enables one later
   diagnostic, using this same new helper without changing hashes or expiry.
   The diagnostic keeps existing development workload order and direct CSS
   >=100ms trigger, not an invented claim of a bug_trend reproduction.

The current R3 helper65716 was authenticated READY/idle on2026-11-26; its
original expiry is16:47:51Asia/Shanghai and capture_count1. Preserve it until
expiry or user-requested shutdown. It is not authorized to load the new profile,
reset calibration count or extend its lifetime. Do not use it as an arbitrary
admin shell. A new helper can be reused within its own frozen method/expiry;
this requires one new UAC, not one prompt for every operation.
No helper, capture, app or process configuration is changed by this design.

## Documentation And Verification

The private tools change diagnostic operations only; product behavior is unchanged.
Current human guidance links here and historical receipts remain untouched.
This method supersedes the broad-profile continuation for this next packet only,
not its historical evidence or the formal KPI contract.
The private implementation's `review/state.json` and `frozen-method.json` bind
its code gate and actual source/helper hashes. A native calibration proof is
still required before requesting the diagnostic go decision.
Historical facts are pinned by the named receipt/hash/field checks; online
references are explanatory, not proof of this machine's capabilities. Future
profile behavior and state reconstruction are proposed, not derived claims
about the unmodified implementation.

Primary Microsoft references retrieved2026-11-26 (read-only):
`https://learn.microsoft.com/en-us/windows-hardware/test/wpt/systemprovider`,
`https://learn.microsoft.com/en-us/windows-hardware/test/wpt/keyword--in-systemprovider-`,
`https://learn.microsoft.com/en-us/windows-hardware/test/wpt/capturestateonsave-in-systemprovider`,
`https://learn.microsoft.com/en-us/windows/win32/api/evntrace/ns-evntrace-event_trace_properties`.
They distinguish system keywords/stacks, automatic save rundown, actual buffer
allocation and loss counters. They do not guarantee retention or zero overhead.
Validate source and docs with scoped size/whitespace, OpenSpec strict,
local-link/reference checks, negative tests and independent implementation review.
Design review does not replace the code gate or native calibration.

# Performance KPI Test Report: Low-Event Calibration

## 1. Report Control

| Field | Value |
| --- | --- |
| Report ID / revision | PERF-WIN-20261126-LE01 / 1 |
| Kind | Diagnostic-method calibration, not product certification |
| Collection / method status | CALIBRATION_COLLECTED / CALIBRATION_REFUSED |
| Numerical product result / acceptance | NOT_RUN / not eligible |
| Test date / documentation date | 2026-11-26 / 2026-11-26 |
| Author | Implementation agent; retrospective presentation of original receipts |
| Specification | PERF-SPEC-001 revision 2026-11-26.1, introduced after this run |
| Actual test policy | `scheduler-observation-v1`, 250,000-event calibration ceiling |
| Raw run / capture | `le1126-cal1` / `d06e1501-dc05-44c7-bb12-388cb3295aba` |
| Overall claim | No native calibration proof, product KPI verdict or acceptance |

The specification is a later classification/index, not the policy used at
execution time. Original helper/policy hashes reside in the frozen method and
refusal references below. This report does not claim that the later document's
hash was frozen before the original run.

## 2. Objective And Scope

Determine whether the narrowed Windows collector can retain reliable
same-request scheduling evidence after the earlier broad-profile failures.
This is a measurement-capability calibration, not reproduction of the
`bug_trend` page burst or formal P1-P4 qualification.

## 3. Frozen Configuration And Assumptions

| Item | Actual Configuration / Evidence |
| --- | --- |
| Dashboard source | `7dd854517341adcc8d852c8862fa308b3b99f9c9` |
| AIB repository source | `1a6ac981b67f148bbaaed6750e6874896ada0bcc` |
| Installed candidate | `ai-base-runtime==0.1.1.dev9`; frozen method binds wheel and installed origins |
| Method identity | Frozen method binds 102 helpers and the selected input/environment |
| Platform/token | Windows; ordinary-token application, bounded elevated collector only |
| Workload | Actual three-arm development fixture; 4 held streams; 40 measured pages |
| Designated request | Real runtime CSS, status 200, 14,840 bytes |
| Event families | Process/thread, context-switch, ready-thread and sparse markers; no file/disk/image/stack families |
| Host details | Use raw environment and process records referenced by `result.json`; not remeasured for this report |
| Measurement boundary | Native HTTP request plus QPC/clock witnesses; event totals are host-wide |

No AIB/application implementation, production stop or numerical KPI change
was part of the run. Successful collection was only a prerequisite for native
coverage validation, not evidence that the latter would pass.

## 4. Test Design And Execution

One calibration was admitted under the 30 s active-work / 40-page bound.
Collector and decoder invocations are retained in the raw run and decode
receipts; no command is re-executed by formatting this report.

| Phase | Recorded Timing / Outcome |
| --- | --- |
| Setup/warmup | Separate from active collection; original `result.json` carries clock/process witnesses |
| Recording began | 2026-11-26T14:09:47.848515+08:00 = 2026-11-26T06:09:47.848515Z |
| Stop began | 2026-11-26T14:10:04.4163353+08:00 = 2026-11-26T06:10:04.4163353Z |
| Recording to stop | 16.5669717 s measured by QPC; do not recompute using rounded wall clocks |
| Pre-stop flush | 1.8724701 s; completed normally |
| Decoder child created | 2026-11-26T06:13:38.7458798Z = 2026-11-26T14:13:38.7458798+08:00 |
| Decoder execution | 120 s deadline; exited 0 without force |
| Final cleanup | Owned application incarnations absent, ports clear, collector/decoder terminal |

A single overall setup-to-final-write wall duration is not established by this
retrospective table. Do not equate the recording interval with whole-run cost.

## 5. Measurement Validity

| Gate | Outcome | Boundary |
| --- | --- | --- |
| Bound source/environment and collection window | PASS in original receipt | Not a new current-source run |
| Real CSS status/size and collection | PASS | One request does not certify a percentile |
| Native event-cost cap | FAIL | 529,161 >250,000 |
| Reported loss/truncation/omission | 0 / false / 0 | Necessary, not sufficient for interval coverage |
| Scheduler coverage validation | NOT_RUN to completion | Proof CLI refused at the event-budget gate first |
| Native calibration proof | NOT_PUBLISHED | No `CALIBRATION_VERIFIED` result |
| Normal cleanup | PASS | No forced collector exit or surviving owned application processes/listeners |
| Product certification | NOT_APPLICABLE to this calibration | No full uninstrumented recipe |

## 6. Results

| Measure | Observed | Criterion / Outcome |
| --- | --- | --- |
| Measured pages | 40 | Within 40-page calibration bound |
| Designated CSS request | 6.2617 ms | Single diagnostic sample; no P4 verdict |
| Actual ETW buffer pool | 84,934,656 bytes | Below 128 MiB |
| Saved ETL | 8,151,035 bytes | Raw/temporary admission below 512 MiB |
| Final temporary artifacts | 22,020,096 bytes | Original artifacts preserved |
| Maximum observed temporary bytes | 88,342,528 bytes | Below 512 MiB |
| Derived decode artifacts | 66,575,760 bytes | Below 512 MiB |
| All decoded native events | 529,161 | FAIL: exceeds 250,000 |
| Context switches / ready events | 327,054 / 183,407 | Host-wide counts, not application cause |
| Markers / selected scheduler rows | 13 / 137 | Within 128 / 50,000 export bounds |
| Marker / payload decode errors | 0 / 0 | Decoder exited 0 |
| Application cleanup | 9 registered incarnations absent; 3 ports clear | Normal stop and live census passed |
| Native proof CLI | Exit 1: Native event budget exceeded | Proof not published |

## 7. Resource And Component Findings

The original native gate stopped before the remaining target-state coverage
checks. Zero reported loss, small ETL and bounded buffer allocation do not prove
those unchecked properties. Native buffer allocation is not application RSS.
No valid running/ready/blocked partition or CPU/function attribution follows.

## 8. Failure Analysis And Actions

| Finding | Classification | Disposition |
| --- | --- | --- |
| Event count exceeds original calibration cap | Observation-cost refusal | Retain original failed result; review cost policy separately |
| Target-state coverage not fully validated | Unresolved method capability | Offline retained-trace analysis must not infer success from zero loss |
| Slow request cause | Not established | No product optimization or KPI change justified by this run alone |

Any revised cost policy, decoder analysis or later capture needs a separate
versioned record and review. This report neither waives integrity checks nor
authorizes a retry. Subsequent owner authorization is recorded separately.

## 9. Evidence Manifest

The [machine-readable refusal](../../../changes/embed-ai-base-runtime-in-process/evidence/windows-low-event-calibration-20261126.json)
contains exact SHA256 references to the original six artifacts:
collection result, decode execution, decoded output, frozen method,
implementation-review gate and ETL. Resolve and verify those references before reuse.

Original collection/decoded artifacts remain in
`D:/AIGC/d9-1122/low-event-1126/`; the protected ETL is in the named capture
under `D:/AIGC/pf1120/circular-runs/le1126-cal1/`.
Large/private traces are not repository attachments.

## 10. Review And Final Decision

The original implementation review passed 1/1 before UAC; it did not certify
native measurement capability. The refusal's publication checked referenced
hashes and fact equality. This documentation packet performs its own separate
review; it does not relabel that implementation review as a native PASS.

No diagnostic workload or second calibration followed within this run.
The elevated helper was retained within its original expiry. That historical
observation does not promise current liveness or renew privileged authority.
All application, collector and decoder work from this run is terminal.

**No performance acceptance is established by this report.**

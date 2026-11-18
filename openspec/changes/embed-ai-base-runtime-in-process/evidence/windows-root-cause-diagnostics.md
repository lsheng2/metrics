# Windows Shutdown Root-Cause Diagnostics

Date: 2026-11-18. Status: root cause unconfirmed; not a qualification receipt.
Source checkout: Dashboard `moonfish`, `7b8d1ab47c8b73e3b35e6b19a1b41f7920e8ac2c`.
The only tracked changes during these experiments are this evidence and the task ledger.
Owner direction: identify the cause first, assess actual latency next, decide KPI values last.

## Scope And Integrity

- Windows only, synthetic state and loopback endpoints; no live providers or user data.
- Production constants and installed wheel files were not edited.
- All 131 package files listed in `ai_host/runtime_artifact.json` still match their hashes.
- Candidate remains `ai-base-runtime==0.1.1.dev4`, AIB source
  `d589ac8e6572a903edc3846e7d78195e85858868`, wheel SHA256
  `b332f338f77bf2e966de7495eea6b5968606eb670287588d97a3a4d82905ec94`.
- All diagnostic state, temporary output, SQLite files and evidence use D.
- Failures are retained. Passing diagnostic runs do not replace the failed native receipt.
- No production behavior, API, operator procedure or KPI changed: `docs_impact: none`.
  This report describes diagnostic evidence, not a newly accepted operating contract.

## Evidence Manifest

Artifact base: `D:/AIGC/artifacts/mdb2-windows-20261117/root-cause-runs/`.

Machine-readable receipt:
`summary-c73bf989-d98c-4e14-bddc-e71fb9673aa1/diagnostic-summary.json`.
SHA256: `f54d79fbac4df7bf46da46cc149777c6df079e2349fa0426196eeac4a8abd18a`.

The receipt binds run outputs, the final 12 cases' traces/logs/process records,
profiler RED/GREEN evidence and six diagnostic tool snapshots.
These are diagnostic bindings, not the full qualification input contract.
The first experiments did not snapshot every helper revision; do not claim exact
source-replay equivalence for those earlier diagnostic runs.

| Run | Experiment | Observed result |
| --- | --- | --- |
| `3e793a3f-7cdb-48f3-8b9c-a6987d7ec581` | Standalone file/tempfile/SQLite close, three iterations | Temporary close about 2-3 ms; SQLite WAL close about 8-13 ms |
| `d24d75f9-33aa-4f2e-ae7c-7cb76699307f` | Two profiled CTRL_BREAK non-readers, unchanged production budgets | Both exit 0, observed stop about 6.66-6.68 s |
| `8b8a4ee5-db59-4907-af97-e666f4eb7030` | Full B5 order, unchanged production budgets, close-only profiler | 11 pass / 1 fail: real chat with lifetime stop |
| `8aea0d21-88e3-4dfc-b81d-ee9ee5cf79ca` | Standalone fsync plus 50 explicit SQLite commits | All complete; no second-scale primitive observed |
| `2047dcc2-c85d-4d32-898c-ace4163720bc` | First extended profiler, three selected cases | INVALID: observer interfered with database close |
| `80ae6d83-131f-4273-9022-5040f8c5cfe3` | Repaired observer, three selected cases, diagnostic policy | Three complete; no profiler errors |
| `bd57c9e5-461b-41aa-8e4d-628b563a62e3` | Repaired observer, full B5 order, diagnostic policy | Twelve complete; no profiler errors |
| `fd2b01df-a34a-424a-82d1-a56b5c0f556c` | Windows FileIO/DiskIO/Minifilter recorder start | Refused with `0xc5585011`; no recording session left |

## Different Failure Surfaces

The historical native run `2f2f5391-9102-4255-a0d7-aba8aa6dc8a4` remains a failure:
non-reader CTRL_BREAK, Waitress close/join incomplete, then SDK store close incomplete.
Its captured stacks are at temporary file close and SQLite connection close.

The new unchanged-budget run `8b8a4ee5...` failed in a different place:

- Real chat with lifetime stop; the non-reader cases completed in this run.
- HTTP shutdown completed; pending bytes were zero.
- Waitress flush returned in under 1 ms and server close in about 3 ms.
- The SDK final stop timed out; the stack snapshot was at
  `domain_store.py:164`, `connection.commit()`.
- The runtime reported `runtime_loop` unclosed; this is not the older
  `runtime_store/state_lock` report.

A sampled stack identifies where a thread was at that instant. It does not
measure the entire call duration or establish the reason for that wait.
Do not merge these failures into one proven cause, or attribute either to
disk, antivirus, a leaked cursor, lock competition or insufficient KPI margin.

## Observer Defect And Exclusion

The first extended profiler read `connection.in_transaction` on the return from
`connection.close()`. SQLite correctly raised `ProgrammingError` because the
connection was already closed. This observer error changed the cleanup result.
All three failures in `2047dcc2...` are excluded from product conclusions.
Its `instrumentation-invalid.json` preserves that disposition without deleting logs.

The diagnostic regression test reproduced the exact failure in
`profiler-red2-20261118.xml`; after limiting metadata reads to call entry,
`profiler-green-20261118.xml` passes. Observer exceptions are also contained and
marked `profiler_error`, which invalidates a diagnostic run rather than altering
the observed operation. Both later runs contain zero such errors.

The earlier full-run lifetime failure used the close-only observer, before the
invalid metadata read was introduced. It is not explained by that later defect.

## Natural-Completion Observation

The `observe` policy exists only as in-memory overrides in the diagnostic child:
SDK stop 30 s, server absolute deadline 30 s, final watchdog absolute deadline
45 s, and a parent wait that does not assert the production 10 s limit.
The flush deadline remains 6.5 s. These are observation safeguards, not proposed KPIs.
No observation-policy result is eligible for formal qualification.

In the last full run:

- All 12 processes exited 0 without parent-forced cleanup.
- All 12 reported completed runtime stop and confirmed persistent-state flush.
- SDK total stop durations were 33.4-71.1 ms.
- The maximum of 70 measured SQLite `commit()` calls was 25.1 ms.
- The maximum of 1,144 measured SQLite `execute()` calls was 30.1 ms.
- The maximum of 12 `RuntimeStore.close_until()` calls was 27.8 ms.
- The maximum measured buffered-file `close()` was 4.2 ms.
- Non-reader flush waiting still consumed approximately 6.5 s as designed.

These are this run's observations, not p95/p99 estimates, a latency guarantee
or an explanation of earlier failures. Successful runs did not need the
extended observation interval. Profiler timing and per-process TEMP placement
are additional differences from the original native run.

## Independent Causal Audit

Read-only agent `01a1eee4-fd9d-76c1-a7e4-2a7277e75331`
(`gpt-5.5`, `xhigh`) inspected installed storage/lifecycle code and the evidence.
Its final calibration: no supported application root cause yet.

`RuntimeStore.close_until()` drains registered futures before connection close.
The close primitive itself has no cancellable deadline, but the facade wait is
bounded. That mechanism is not, by itself, a confirmed defect or the root cause.
Retaining the store/lock on incomplete cleanup is deliberate ownership reporting.
The audit recommends queue submit/start/end and runtime phase observations in
addition to commit/close spans, not a timeout increase.

## Next Discriminating Work

1. Keep production values frozen. Add safe store-operation submit/start/end
   and runtime-stop phase observations if the user-mode path is continued.
2. Capture a reproduced slow stop alongside Windows FileIO, DiskIO and Minifilter
   events to distinguish application scheduling/locking from kernel I/O waits.
   Only analyze the synthetic PIDs and file paths; keep raw ETL private on D.
3. The current token does not list `SeSystemProfilePrivilege`. Recorder startup
   returned "Failed to enable the policy to profile system performance".
   Do not alter machine policy or elevate without user involvement.
4. The prepared `capture_shutdown_trace.ps1` uses a unique recorder instance,
   stops it in `finally`, and preserves evidence on D. An authorized elevated
   session is needed to attempt the next kernel capture.
5. Reassess latency and KPI only after a supported cause/fix and representative
   measurements. Fresh native certification and full functional acceptance
   remain separate, open work.

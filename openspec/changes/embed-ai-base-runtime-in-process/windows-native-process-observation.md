---
id: MDB2-WIN-NATIVE-DETAILS-20261126
title: Native process detail observation
status: accepted
owner: Dashboard validation
created: 2026-11-26
last_reviewed: 2026-11-26
docs_impact: operations
human_docs: [openspec/docs/current-baseline/performance-kpis.md, docs/development/reporting-delivery.md]
implemented_by: []
tests: []
supersedes: []
superseded_by: []
---

# Native Process Observation

## Goal And Evidence

Repair the Windows measurement observer without changing application code, AIB,
numerical KPI, ownership requirements, real-leak detection or stop budgets.
This is a bounded `PERF.PROBE` slice under the owner's continued-performance
closure authorization, not a new process manager or execution ledger.
The existing `tasks.md` and 28-node DAG remain authoritative.
Project profile: repo-local; routing: multiagent-configured.

The reviewed retained-window method froze source `dcd7323` and 135 helpers.
Attempt `le1126-ret2-cal1` was INVALID before any app, measured page or ETW
capture started. Two snapshots could not recover command identity for six
short-lived Git processes. Their observed parents were the desktop client and
codebase-memory service, but parent names do not prove the missing commands
were harmless. The driver exited, its measurement guard was removed and the
ten-capture helper remained READY/count0/empty history/zero bytes.
Preserve the terminal-error and measurement-window files at
`D:/AIGC/d9-1122/retention-v2-1126/le1126-ret2-cal1/`.

The current observer takes a native process inventory and retains handles, then
starts PowerShell/CIM to obtain command lines. Its detail stage took about
2.97-3.39 s in the bounded comparison. A read-only native command query took
about 0.36-1.36 ms in those same first three snapshots. The 53-snapshot native
survey had no missing identity and released every acquired handle.
A separate controlled experiment used one owned `git cat-file --batch` per
trial: query while alive, close stdin, verify normal exit, then query CIM.
All three trials retained native command/creation identity while CIM reported
the original PID missing; all retained handles were released.
These are observer experiments, not application performance measurements.

The command classifier also reproduces two distinct errors:

| Input | Current Result | Required Result |
| --- | --- | --- |
| `"git" "-C" "D:/synthetic" "rev-parse" "HEAD"` | relevant unknown Git | read-only Git |
| `git -C status commit -m synthetic` | read-only Git | relevant Git write |

The first follows from retained quotes in the existing Windows argument split.
The second follows from searching every argument for command words, including
global-option values. Correct parsing must select the real subcommand.

Private evidence:
`D:/AIGC/d9-1122/process-details-1126/native-details-probe-1.json` and
`native-lifetime-probe-1.json`, with exact probe source hashes.
The historical failure remains INVALID. No attribution of `bug_trend` or other
application delay is made from these observations.

## Design And Boundaries

Reuse `ProcessWindowCapture` and its held read-only handles. Capture native
command details immediately while opening the target process, before any slow
external query. The isolated Windows detail reader uses dynamically resolved
`NtQueryInformationProcess` command-line information, a bounded response buffer,
strict UTF-16 length/pointer checks and the already-observed creation time.
Recheck creation on the same borrowed handle and retain its bounded native
executable path. Complete identity is command, canonical creation and image
path together; a failed field yields only a sensor error, not partial identity.
Unsupported API, malformed buffer, access denial, missing/terminated process
or unresolved identity remains an explicit sensor error, never a clean row.
This Windows-specific capability must fail closed on unsupported hosts.

Use the existing command-normalization helper after the existing splitter.
Parse Git global options and their values before selecting exactly one
subcommand. Preserve the existing read/write classifications; an unrecognized
command or ambiguous/unsupported option remains relevant unknown. Do not infer
read-only behavior from a process name, parent, exit code or occurrence of a
read-command word inside another argument.

The production measurement path no longer starts PowerShell/CIM for each
snapshot. Stable SLE ownership registration is outside this change; native
detail identities must match its existing process-identity representation.
Store raw command text only in ephemeral observer data; published snapshots
keep existing fingerprints, not command lines or token-bearing arguments.
Retained handle ownership, creation identity, terminal observations, close
failure refusal and existing registered-terminal resolution remain intact.
Record observation method and elapsed time separately from application timers.
Do not claim that faster capture eliminates every process-exit race.

No alternate legacy/CIM mode, permission downgrade, broad admin command,
process termination, security-software change, indexer suspension, provider/model
call or Linux execution belongs to this slice. Existing elevated collector
source and expiry remain unchanged; its grant was not consumed.

## Propagation And Validation

| Contract | Producer | Consumers | Disconfirming Evidence |
| --- | --- | --- | --- |
| OBS-DETAIL | `windows_host_process_details.py`, held-handle capture | `windows_host_environment.py`, identity enrichment | terminated/missing/unsupported native query, malformed/oversized/out-of-buffer Unicode, close failure refuse |
| OBS-IDENTITY | exact native creation plus normalized command identity | owned process registration, driver and terminal resolution | native versus existing stable-process identity equivalence; PID reuse and foreign near-match refuse |
| OBS-GIT | parsed executable/global options/subcommand | process relevance and raw replay | quoted reads admitted; option values named status/log cannot hide writes; unknowns remain blockers |
| OBS-CLAIM | observation metadata and sanitized snapshot | measurement-window writer, evidence replay, current docs | no raw command leakage, source drift, missing samples or unknown identity promotion |

Implementation files:
`scripts/validation/windows_host_process_details.py`,
`windows_host_process_window.py`, `windows_host_environment.py`,
`windows_host_process_identity.py`, and their focused `scripts/tests/` consumers.
Native detail logic belongs in one cohesive module; do not duplicate handle
ownership or modify released AIB packages. Add only the new owner paths to
`PERF.PROBE`, retaining DAG IDs/dependencies and current pending statuses.

Consumer census: validation scripts, native process handles, serialized
observations/replay, operator docs and test doubles apply. Production API/UI/
storage, migrations, scheduling, live providers, SDK packages and other Apps do
not change. Shared SLE is a compatibility consumer of identity representation,
not a source-edit target. No generic application fallback is introduced.

1. Independently review this bounded plan and its negative/ownership coverage.
2. Reproduce both classifier defects and the short-lived detail loss in focused
   tests, then implement the minimum owner-scoped correction.
3. Run detail/buffer/handle/identity/classifier tests, all affected existing
   observer/evidence tests and the native controlled-Git smoke. Use the selected
   dev9 interpreter and isolated no-dotenv test entry; no live application data.
4. Run scoped size, whitespace and strict OpenSpec gates. Independently review
   implementation, actual evidence and changed consumers before a new run.
5. Commit/push the scoped packet; preserve all old source freezes and raw
   failures. Create a separately named private method/input freeze for the new
   source. Existing helper count0/max10 and original expiry must still validate.
6. Close reviewers and test/build activity. Execute one fresh bounded native
   calibration, decode and replay; preserve any refusal without automatic retry.
7. A method pass precedes further authorized diagnostics and a new uninstrumented
   full P1-P4 recipe. R/C qualification and final combined acceptance remain
   independent required work; this observer change closes none of them alone.

If unresolved process identity persists, retain it as a blocker and inspect
new evidence. Never permit terminal/unrelated status solely to get a green run.
If ordinary native access requires broader privileges or any privileged
collector change, stop that action and use the owner's explicit permission
boundary rather than silently expanding the retained UAC grant.

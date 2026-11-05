# Reporting Development And Validation

Current development rules: [AI Contract](../../AI_CONTRACT.md).
Current behavior and task state:
[reporting guide](../../openspec/docs/current-baseline/project-reporting.md) and
[one task ledger](../../openspec/changes/add-provider-neutral-project-reporting/tasks.md).
The approved delivery order and interfaces are in
[delivery sequence](../../openspec/changes/add-provider-neutral-project-reporting/delivery-sequence.md).

## Environment

Reporting validation uses the existing separately installed interpreter:

```powershell
$reportingPython = Join-Path (Get-Location) '.tmp/sdk-020-join-20261105/app-venv/Scripts/python.exe'
& $reportingPython -I -c "import sys, pywintypes, ai_base_application_sdk; from importlib.metadata import version; print(sys.executable); print(version('ai-base-application-sdk')); print(ai_base_application_sdk.__file__)"
```

Expected SDK is exactly `0.2.0a1`; its module must resolve under that selected venv.
It uses the unchanged `task-run/1` a2 pack. Exact wheel/pack and installation identities
remain in the [SDK contract](../../openspec/changes/add-provider-neutral-project-reporting/sdk-020-integration.md).
The retained main `.venv` contains SDK0.1.0a2 and is not a supported shortcut for migrated
report consumers. No current service is silently switched or upgraded.
The import check is environment evidence only, not a business test.

Use the existing no-dotenv entry, with explicit test nodes and a unique evidence filename:

```powershell
& $reportingPython -I scripts/validation/run_report_authoring_tests.py ui_web/tests/test_report_daily_ui_browser.py::TestReportDailyUiBrowser::test_shouldCarryEditablePersistentReferenceIntoActualNextDay -q --tb=short --durations=5 --junitxml=.tmp/dashboard-delivery-20261105/daily-two-day.xml
```

The named next-day case is the DAILY closure target; its existence alone is not a pass.
Do not run a missing test node as evidence. The tasks ledger records its implementation
and actual result. The runner denies external networking and suppresses dotenv loading;
local browser HTTP and separately scoped runtime IPC remain permitted.

## Validation Selection

| Layer | Proof | Fixture boundary |
| --- | --- | --- |
| L0 | schema, null/empty, dates, sort, fragments, delta, hashes | Pure values; no Git, database, browser or Base |
| L1 | durable command, CAS, recovery, source/summary/editorial preservation | Real isolated store only for the transaction being proved |
| L2 | auth, CSRF, forms/JSON, error codes, nullable serialization | Cheap boundary fixtures plus a small real-service wiring subset |
| L3 | real Milkdown editing, paint, keyboard, popup, Save/reopen | Mounted editor and real local HTTP/storage; synthetic upstream |
| L4 | matched application/SDK/Base/publication and complete week | Stable candidate, owned services/data, explicit normal cleanup |
| External qualification | actual provider/model/Outlook/deployment/scheduling | Separate authorization and evidence; never inferred from local JOIN |

Reuse immutable input/profile/source fixtures. Do not share mutable command, draft, archive
or acceptance state between independent cases. Case failures must preserve the actual response
and stop widening the test set until the relevant lower-level cause is understood.
Do not rebuild a week for every bad field or treat a passing same-source week as proof of delta analysis.

## Review And Publication

Use one writer and a bounded independent reviewer. A packet review can cover source, evidence
and the next dependency boundary; later evidence completion need not repeat unchanged source review.
After two equivalent failures without new evidence, change the hypothesis/diagnostic.
Review cost at packet boundaries and after 60 minutes on the same user problem.

Record runtime source, fixture/test and environment fingerprints separately.
For the SDK020 proof, the final strengthened test assertion did not change the runtime;
the delivery receipt explicitly preserves this distinction.
Do not extend that example to assume all test files are irrelevant: some are native fixture dependencies.

Stage only approved paths. The retained authoring WIP is not all another owner's work:
publish its verified closure separately from unrelated Scope/config/style edits.
A working-tree qualification is not a clean-install or formal deployment qualification.
Normal stop, emergency cleanup and still-running unrelated services are separate statements.

## DAILY Evidence

The current bounded packet is recorded in
[DAILY delivery evidence](../../openspec/changes/add-provider-neutral-project-reporting/daily-delivery.md).
The template counterexample exercises a single day's cell so another column cannot mask
reversed history/current-note ordering. The browser chain additionally proves actual next-day
creation, reference preservation, human text/paint and publication identity.
Observe GET/POST responses before waiting for navigation; retain failed attempts independently.
Same-meeting replay with changed effective choices intentionally returns 409 and the original
result. Test the visible unapplied-choice message and publication link; do not assume every
idempotent return redirects or change the service to silently ignore selected choices.
Only the complete chain plus its scoped review closes DAILY. This is not the full-week,
changed-source AI, clipboard/Outlook or clean-release qualification.

The 2026-11-05 manual two-day chain and three direct template cases are qualified in the
current worktree. The existing publication is reachable from a same-day conflict result;
history is displayed before the current source-status prefix within each cell.
Product/test files still depend on the retained authoring WIP, so the checkpoint publishes
its docs/receipt separately from a complete source release. Request latency and the recorded
native diagnostic incident remain explicit limitations, not implied fixes.

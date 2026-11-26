# Performance Test Report Register

Specification: [PERF-SPEC-001](../../current-baseline/performance-kpis.md).
Format: [test report template](../performance-report-template.md).
One report per execution/policy; retain failed and superseded runs unchanged.
This index is not a second task ledger or a substitute for raw semantic validation.

## Current Reports

| Date | Profile / Kind | Result | Report | Acceptance Scope |
| --- | --- | --- | --- | --- |
| 2026-11-26 | Scheduler observation calibration | FAIL: event-cost limit | [Low-event calibration](2026-11-26-low-event-calibration.md) | None; no native proof or product KPI certification |

## Historical Evidence Inventory

These links are original receipts, not newly executed tests. Dates and source
identity must be read from each record before making a reuse claim.

| Date | Evidence | Result And Boundary |
| --- | --- | --- |
| 2026-11-07 | [Reporting S0/S1 delivery](../../../changes/add-provider-neutral-project-reporting/performance-delivery.md) | Scoped historical reporting PASS; old candidate/source, not current dev9 timing proof |
| 2026-11-25 | `D:/AIGC/d9-1122/runs/certify-r3-1124d.json` | Complete r3 PASS at db00210; historical |
| 2026-11-25 | `D:/AIGC/d9-1122/runs/certify-editor-sync-r3-1125a.json` | Complete FAIL at c845224: seq/development bug_trend ratio |
| 2026-11-25 | `D:/AIGC/d9-1122/runs/diagnostic-perf-ref-refresh-r3-1125.json` | Receipt FAIL / collection INCOMPLETE at d7dd699: scheduled-slot integrity |

## Publication Rules

- A fresh run or changed policy gets a new dated report id and new raw directory.
- Finalized reports are immutable. Correct an interpretation through a separate
  dated addendum/report that links the old record and explains the correction.
- Record setup, sampling, cleanup and review separately; a PASS in one layer
  does not promote another layer.
- Certification rows must bind the central specification revision, exact
  machine policy and accepted source/candidate/fixture/environment.
- Missing, skipped or undocumented results stay NOT_RUN/INCOMPLETE, never PASS.

# Full Week Authoring Evidence

Date: 2026-11-06. Source base: `6b1b543ded78aae0d5e299edaa37ba3159540c29`.
Scope: `W6.AUTHOR.JOIN`. Task state belongs only to [tasks.md](tasks.md).
The joined operation/continuity workflow passed, including cross-week and
pending-gap/explicit-clear evidence. This does not close the whole topic: the
concise-report presentation contract and observed request latency remain open.
The exact scenario and recovery boundaries are in [week-qualification.md](week-qualification.md).

## Runtime And Source

The scenario uses actual Dashboard HTTP, worker, local Milkdown, installed
SDK `0.2.0a1`, fixed a2 `task-run/1` pack, loopback Base and local data Git.
Jira responses and model output are explicitly synthetic. No company Jira/HSD
endpoint or real model is called. Three separate tickets retain constant source
facts, assignees, comments and statuses throughout the simulated meeting dates.

Retained run:
`D:/AIGC/scrum_dashboard_validation/full-stack/aa2fb399-4557-4342-b725-8de2dab91aba`.
The run manifest records the SDK wheel/pack/Base source and store identities.
`evidence/week/source.json` records the actual working-tree file fingerprints.
This is working-tree qualification, not a clean installation or formal deployment.
The unrelated Scope/config/main.css changes are not part of the source publication.

Observed selected environment: Python 3.13.7, Django 6.0.7, Playwright 1.57.0,
Chrome 157.0.8103.39, openpyxl 3.1.5 and Markdownify 1.2.3.
Dates are synthetic ISO WW44.1-5 and WW45.1, not a claim about a custom Intel calendar.

## Product Fix

The earlier run `eb203842-ac01-4e00-ad40-7161c033fefe` accepted its three summaries,
saved Monday revision 2, then returned `REPORT_REVISION_CONFLICT` on Finalize.
Both services stopped normally before the user-reported PC restart. The restart
was not the cause of this recorded failure.

The draft binding used the preparation content hash while the publication guard
compared the full stored-intent hash. The shared `preparation_binding_hash()` now
keeps the producer and consumer consistent. The active slot still validates the
full intent hash independently. Source eligibility, owner, revision, active-slot,
baseline and original-byte guards remain in place; no old schema or hash was changed.

Evidence under `.tmp/dashboard-week-20261106/`:

| Evidence | Result / meaning |
| --- | --- |
| `publication-guard-red-01.xml` | Test setup error: manual preparation has no initial materialized note; not product-failure proof |
| `publication-guard-red-02.xml` | Actual refresh/save/finalize reproduced the same publication guard failure |
| `publication-guard-green-01.xml` | 7 passed: initial refresh, saved/refresh replacement, superseded/missing/downgraded bindings and saved-capture baseline |
| `format-validator-red-01.xml` | Two direct counterexamples reproduced exhausted-generator false negatives |
| `resume-checkout-red-01.xml` | Reproduced incorrect comparison of moving checkout state as immutable history |
| `untouched-slot-red-01.xml` | Exposed the missing distinction between an untouched empty slot and an explicit empty edit |
| `untouched-slot-green-01.xml` | 7 passed: formatting, source-resume restrictions, immutable data comparison and empty-slot mutation checks |
| Node editor/export selection | 13 passed; actual codec/lifecycle/revision behavior |
| Isolated Django check | No issues, using this run's synthetic no-dotenv settings |

The bounded independent review found no remaining issue in the product hash fix
or the validator-only recovery rules. Final run evidence is a separate gate.

## Validator Corrections

The replacement run finalized Monday through Wednesday before its formatting
validator failed. The archived Wednesday fragment already contained green text,
yellow highlighting, `strong`, the scoped ticket hyperlink and assignee. The
validator consumed a generator for the color check and then inspected the exhausted
generator for bold/highlight. Materializing that list fixes the checker, not the editor.

Recovery re-reads actual publication files through the public service. It treats
`checkout_state=current/stale` as an observed checkout projection and still compares
publication ID/manifest/hash/commit, draft revision/context and all original file
hashes exactly. Unknown checkout values and actual immutable differences fail.
Only named validator modules/tests may differ from the original source fingerprint;
application, shared fixture, SDK, Base and vendor changes refuse reuse.

The Thursday run then demonstrated correct stale-window refusal/reconciliation
and paint-only saving, but its ALPHA-102 clear action targeted an already empty,
unchanged slot. That no-op is retained as `untouched_empty_ids`, not as a successful
deletion. The final pending-draft branch must provide the real nonempty Save ->
clear -> Save/reopen proof. Fresh week runs seed the Thursday target first.

Original evidence remains in `evidence/week/`. Validator-only resume evidence is
in separate `evidence/week-resume-*` directories. No original failure, progress
record or finalized report was rewritten to produce a pass.

## Exit Evidence

Final result:
`evidence/week-resume-4d9b6420-464d-493f-b75b-7ee2b7e2d3ec/result.json`
under the retained run. The browser driver exited 0 with `status=passed`.
Its source comparison permits only the documented validator changes; the application,
shared fixture, vendor, SDK and Base remained the same candidate.

| Meeting | Publication | Result |
| --- | --- | --- |
| 2026-10-26 | `88c6b2c7-0853-5806-9f95-fac1954946b8` | Three first SDK/Base accepted summaries; red human note/link; Save is not Finalize |
| 2026-10-27 | `95ca371e-decd-5fa9-b7da-ddc3187e8c0d` | Blue notes/green persistent note; Monday unchanged |
| 2026-10-28 | `f113d908-2710-5854-bc86-100ba240946f` | Normal app restart, third-format completion, undo/redo, bold/highlight |
| 2026-10-29 | `cfcb9a02-bb62-5925-b2ad-40c8fccd0805` | Paint-only Save, stale-window 409 with retained/reconciled input; ALPHA-102 untouched empty slot explicitly recorded |
| 2026-10-30 | `39b0b3b1-0d32-531e-a581-9712696710a8` | Mixed paint, one resolved AR and other open ARs; earlier notes unchanged |
| 2026-11-02 | `1c176c04-9df3-58a9-bfd8-1a214adeafba` | Original Friday date/status/paint, unresolved ARs and persistent note carried forward |

Weekly view `d649bc54-ff26-5b52-877b-be0ce27b363e` did not replace the daily baseline.
All days have exactly the same three accepted summary IDs and source hashes.
Total Base dispatches remain 3; these are synthetic executions, not paid model calls.
The distinct pending series preserved draft `47c89181-7f31-52a5-9ceb-6e022438fe50`
while acknowledgement created `88396da9-6bce-5d1f-a983-90a1dec245a7`.
That branch contains the actual write/Save/clear/Save/reopen proof and retains its
explicit empty-note hash after the gap.

After the entire workflow, public API readback re-read all seven publications and
matched all 42 original artifact hashes:
`evidence/final-publication-readback.json`. This compares actual archive reads,
not only the previously copied evidence files. Final normal-stop receipt:
`evidence/stop/a18139b0-d4a5-43dc-9eb8-ea0361895dc1/stop-receipt.json`;
both owned services stopped without force.

Read-only Ego inspection additionally captured the actual archived HTML in
`evidence/visual/friday-report.png` and `next-week-report.png`; the dedicated
TaskSpace was finished. This visual check is separate from operation-page screenshots.
The source/evidence hashes and bounded conclusion are in [week-delivery.json](week-delivery.json).

## Remaining Boundaries

The default template still requires `key_messages`, `changes`, `register` and
`coverage` in `app/domain/report_templates.py`. The pinned renderer includes
original accepted narratives and detailed source evidence after the meeting matrix.
The observed output is therefore substantially longer than the user's concise
daily standup request. It also puts source-action information next to effective
editorial AR state without a sufficiently clear presentation boundary.
Correct matrix/history persistence does not qualify that overall user-facing result.

The next W6.RENDER/PUBLISH design should separate a concise standup body
(per-ticket cumulative notes, provider status, current ARs and compact coverage)
from complete audit material retained in the archive and available separately.
Use an explicit versioned template/renderer policy, preserve old snapshots/hashes
and original downloads, and keep source evidence/permissions/coverage guards.
Do not merely remove mandatory sections or silently change old renderer semantics.
This contract adjustment requires confirmation before implementation.

Observed browser-action-to-response waits include Friday preparation 53.14s,
weekly creation 55.90s, next-Monday preparation 76.61s and next-Monday finalization
41.76s. These are stored `*-timing.json` values, not a CPU profile or isolated SDK
latency. A bounded read/preparation-path profile is needed before proposing a fix;
do not hide this usability limitation by increasing existing operation deadlines.

Real Jira/HSD completion, real model execution, Outlook/native-client paste,
clean installation, formal activation and scheduling remain separate qualifications.
Existing DAILY, ASSIST and EXPORT samples retain their original bounded scope;
this week does not replace changed-source delta or provider-specific testing.

# DAILY Delivery Evidence

Date: 2026-11-05. Status: bounded working-tree qualification complete.
The only task status authority remains [tasks.md](tasks.md).
This packet implements [delivery sequence section 4](delivery-sequence.md#4-w6authordaily);
it does not qualify the whole application, a clean release, or the full workweek.

## Scope

One synthetic Jira member, `ALPHA-1`, has captured status `Fixed` on both
2026-11-02 and 2026-11-03. The test uses actual saved-capture preparation,
ORM, data Git, HTTP routes, mounted Milkdown, completion admission, signed
reference receipts, Save, reopen and Finalize. Only upstream ticket lookup
is synthetic; no authoring JSON is directly seeded to bypass the editor.

The new persistent target is saved before `#ALPHA-1` completion. Keyboard
selection chooses the linked ID, title and owner option. Tuesday edits the
inherited reference and neighboring human text, preserving its publication
association instead of obtaining a new upstream observation.

The contract checks are separate:

- Save does not advance the editorial baseline; verified Finalize does.
- Tuesday is a distinct draft and publication bound to its saved revision.
- Both daily human notes survive Save, reopen and publication.
- Historical note hashes, original Monday publication identity and all six
  published files remain unchanged.
- The inherited link retains its ID, URL, provenance and newly selected paint.
- Repeated Tuesday preparation resolves to Tuesday's existing publication.
- Only one external-reference observation and zero Base clients are used.

## Changes And Evidence

| Surface | Change / proof |
| --- | --- |
| `ui_web/tests/test_report_daily_ui_browser.py` | Add the real two-day journey; preserve response bodies, screenshots and per-POST timing under unique run directories. |
| `ui_web/templates/projects/reports/pinned_blocks.html` | Display older notes before the current-day source-status prefix inside each cell. No data, acceptance or publication format changes. |
| `ui_web/templates/projects/reports/daily_preparation.html` | Expose the existing publication link when a finalized preparation is returned with unapplied choices. Keep its conflict status and original effective selection. |
| `ui_web/tests/test_report_history_template.py` | Exercise actual view models/templates for both current-note states and the finalized-publication link, without Git/DB/browser fixtures. |
| Existing DAILY C evidence | Its 39-file manifest was compared with the current checkout. Before the template correction, only the newly extended browser test differed. Unchanged backend/auth/preparation evidence is retained; affected ordering is revalidated here. |

Evidence root: `.tmp/dashboard-delivery-20261105/`.
The selected SDK environment and no-dotenv runner are documented in
[development and validation](../../../docs/development/reporting-delivery.md).

| Run | Observed result |
| --- | --- |
| `daily-two-day-attempt-01.xml` | Failure at the click's 30-second automatic navigation wait; a Windows temporary-directory cleanup lock error also occurred. No reliable Finalize POST receipt was captured. |
| `daily-two-day-attempt-02.xml` | Actual Monday and Tuesday Save/reopen/Finalize reached. The old GET-preview helper timed out during same-day replay. This was not a complete pass. |
| `cell-order-red.xml` | Two expected failures: the Tuesday prefix appeared before Monday's historical text inside the same cell. |
| `cell-order-green.xml` | Both template cases passed after the one-line ordering correction. |
| Isolated Django check | Existing no-dotenv test settings, temporary paths and network denial; no issues or silenced checks. |
| `daily-two-day-attempt-03.xml` | Both days finalized, then the test incorrectly expected a 302 for changed-baseline replay. The captured 409 correctly returned the existing finalized preparation with `selection_conflicts=("baseline",)`. This is not a passing chain. |
| `existing-publication-link-red.xml` | Expected failure: the result template did not consume the existing publication URL. |
| `daily-template-final-green.xml` | All three template cases passed after adding the publication link. |
| Attempt 04 | Native Windows access violation during a partially written timed thread dump; no completed JUnit verdict. See `native-diagnostic-incident.md` under the evidence root. |
| `daily-two-day-attempt-05.xml` | One passed in 466.75 seconds; both days, current/historical notes, reference provenance, paint, exact publication identity, six unchanged Monday files and same-day conflict replay verified. Normal test teardown completed. |

All failed full-chain attempts are retained. Their successful intermediate
steps do not substitute for a complete chain. GET and POST response observation
now precedes navigation assertions, with bounded waits. This changes the test
observer, not any application/SDK operation deadline or retry policy.
The temporary timed `faulthandler` sampler was removed after attempt 04;
response/body and timing evidence remain. Its coincidence with the native fault
is an isolation hypothesis, not a proven root cause.

Final evidence is in
`.tmp/dashboard-delivery-20261105/daily-two-day-199e2d7e-b773-49bf-a6f3-7776a6764b4b/`.
The coordinator inspected the actual Tuesday reopened/editor screenshots, result
and saved `tuesday-report.html`. File identities and scope are recorded in
[daily-delivery.json](daily-delivery.json). Pytest duration is not the complete
development-turn elapsed time.

Attempt 02's slow-request stacks show local Git reads during request processing.
Its measured Monday Finalize POST took 22.229 seconds. This is diagnostic evidence,
not a proven explanation of every earlier timeout, a latency target or permission
to claim a fast production workflow. The packet keeps this cost visible before
the larger workweek qualification.

### Same-Day HTTP Contract

`POST .../reports/preparations/` keeps the existing distinction:

| Request | HTML response and effect |
| --- | --- |
| Existing meeting, matching effective choices | Redirect to the original draft/operation/publication; no new work. |
| Existing meeting, changed effective choices | 409 with the original result and unapplied choices; do not silently apply a new baseline/template/source or rerun work. |

After Tuesday Finalize, a new baseline preview names Tuesday's current head,
whereas Tuesday's original preparation was based on Monday. The different-command
replay therefore legitimately reports a baseline conflict. The test must check
that specific 409, follow the existing publication link and verify that only the
original two drafts remain. Requiring an unconditional 302 was a test assumption,
not a reason to weaken the service contract. The missing direct publication link
was corrected at its template consumer, with a separate RED/GREEN test.

## Review And Next Gate

`daily-source-review.md` identified per-cell chronological-order coverage,
Tuesday daily-note persistence coverage and distinct publication identity.
The template correction has a direct RED/GREEN counterexample. The extended
browser test covers the other findings and the full manual chain now passes.
`daily-fix-review.md` is the bounded follow-up, not another whole-history review.
`daily-replay-review.md` confirms the publication-link/replay correction and the
next-gate direction. The coordinator bound attempt 05 after that source review;
the only later test change removed the temporary sampler. The reviewer did not
claim to execute the runtime test.

DAILY.REPLAN binds this evidence and preserves the three baseline authorities.
The next implementation is not ASSIST: `W4.DELTA.PLAN.R` must first freeze cumulative
input, accepted revisions, reader reconstruction and pending-attempt admission.
The new admission check is necessary because `_require_no_pending_analysis` currently
compares each old attempt with only the latest accepted attempt.

The next gate distinguishes historical accepted attempts, verified terminal
failures and unresolved submissions. Unknown submission is still observed by its
original key. No new key, refreshed deadline or refunded budget is inferred from
a transport timeout. Full index/import/provider work and authoring@1 qualification
remain their separate tasks.

## Publication Boundary

The governance/order packet was published as `9852e37` on `origin/main`.
The retained authoring implementation contains earlier uncommitted source.
A scoped DAILY commit does not by itself establish a reproducible clean checkout
or deployed release; source closure remains part of release qualification.
This checkpoint publishes documentation and the receipt only. The four changed
product/test files remain in the working tree with their existing dependencies.
For example, `report_authoring_fragments.py` is required by these tests but is
not present in HEAD. Publishing only the small test/template package would leave
that dependency absent. Its complete source closure must be scoped separately;
unrelated Scope/config/style changes are not included by implication.
No real provider/model, existing 8017 service, scheduling, sending, data remote,
production database or immutable SDK release was changed by this packet.

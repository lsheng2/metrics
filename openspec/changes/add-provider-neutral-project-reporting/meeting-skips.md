# Skipped Meetings And Resumption

Date: 2026-11-06. User-approved report-authoring addition.
State: [tasks.md](tasks.md), `W6.SKIP.*`; no second execution ledger.
profile_source: repo-local. agent_routing_mode: single-agent with bounded independent review.
Source baseline: `aa595d68a9032371faa883b29a244442b5431aec`.
Thirteen pre-existing Scope/config/shared-style changes remain excluded.
Docs impact: user, architecture, API; current guide:
[project-reporting.md](../../docs/current-baseline/project-reporting.md).

## Outcome And Invariants

Operators can record or undo a skipped standup for one local date or an inclusive
range. Resumption uses the latest actual finalized daily report, never an invented
yesterday/Friday report. This extends [continuity](report-continuity.md).

- A skip is meeting metadata, not a draft, capture, AI run or publication.
  It advances no baseline and never closes tickets or ARs.
- No report does not prove cancellation. Distinguish `unrecorded`, `skipped` and
  dates occupied by preparation/report work.
- Dates are literal local ISO dates in the series timezone. Explicit inclusive
  ranges include any selected weekends, without asserting they are scheduled days.
  Workweek labels still come only from the selected reporting calendar.
- An existing preparation, retained seed, draft or daily publication blocks a skip
  covering its date. Reject the whole range, without partial mutation or deletion.
  Unfinalized drafts continue to require the existing explicit gap acknowledgement.
- Restore means eligible again, not that a meeting occurred. Preserve skip/restore
  audit history. Do not automatically generate a report after restore.
- Same-week notes accumulate. Across empty weeks retain each ticket's latest actual
  confirmed effective note, unresolved ARs and carry-forward notes, including their
  original date/status, text, deletion, paint and links.
- Recovery uses explicitly selected fresh source or labeled saved capture.
  Source/accepted-summary/editorial baselines remain separate. Missing evidence and
  existing input/retention limits fail visibly; never invent missed daily statuses.

## Storage And Concurrency

Add `ReportMeetingChange` alongside report series models:
`series, revision, command, request_hash, payload_json, payload_hash`.
Unique `(series, revision)` and `(series, command)` constraints protect the
append-only audit chain. Derive current state; no second durable task engine.

Canonical payload: schema 1, project/stage/series/actor, revision, previous hash,
command/request hash, `skip|restore`, inclusive dates, optional reason, policy hash,
calendar identity/timezone, server timestamp. Genesis binds project/stage/series/
owner. Reads verify contiguous revisions, hashes and identity before using records.
Limits: 62 days per mutation, 366 per query/frozen window, 240 single-line reason
characters, 1,000 changes per series. Invalid dates, bool revisions, controls,
unknown actions and overlimits fail explicitly.

Mutations acquire the existing archive-root `budget.lock`, already acquired by all
preparation/seed/publication writers before their stage lock. Hold it through
occupancy checks and atomic DB commit. This also works before a first report:
do not create a stage directory or initialize Git just to skip a meeting.
Require an explicitly configured archive root. Lock order: root lock, then DB
transaction; never hold a DB lock while waiting for an archive lock.
`ReportArchiveRepositoryAccess._meeting_calendar_repository` is the root-only
helper: use `exclusive_lock(config.root / "budget.lock")`, never
`_report_repository(write=True)` or `CombinedLocks` to create an absent stage.

Prepare checks skipped state before source/runtime work and inside its existing
writer reservation. Direct `prepare_context` checks before source work and inside
`_write_seed`. Existing original-command replay still precedes new-work admission.
Skip checks retained intents/seeds/drafts/publications, including partial
reservations and older daily paths, not only the active slot pointer.
The early prepare guard is after original-command lookup but before runtime
admission, `continuity.preview`, baseline composition and saved-capture reading.
Ownership/path/original-command verification may read Git; no skip or refusal
creates a Git commit. This is not a promise that replay requires zero reads.

## Public API

`project_management.app.api.report_meetings` exports `ReportMeetingService` and
framework-neutral frozen/slotted DTOs from `app/domain/report_meetings.py`.
Compose it with the existing continuity service; no SDK change.

```python
ReportMeetingService(continuity_service)
read(actor, project_id, stage_id, *, series_id, from_date, through_date)
change(actor, project_id, stage_id, *, series_id, command_id,
       expected_revision, expected_revision_hash, expected_series_policy_hash,
       action, from_date, through_date, reason="")
```

Read returns series/policy identity, calendar revision/hash, selected interval and
one row per local date (`unrecorded|skipped|occupied`, reason/audit metadata and
existing-work identifier when available). Empty calendar: revision 0/genesis hash.
Change returns the original recorded revision/hash and replay disposition.
Same command/payload replays without reapplying, including after a later restore.
Different payload conflicts. New commands check both calendar and policy CAS.

| Error | HTTP | Meaning |
| --- | --- | --- |
| `REPORT_MEETING_SKIPPED` | 409 | Restore skipped date before new preparation |
| `REPORT_MEETING_OCCUPIED` | 409 | Retained work in range; no selected day changed |
| `REPORT_MEETING_REVISION_CONFLICT` | 409 | Calendar/policy/command conflict; retain input |
| `REPORT_INVALID` | 422 | Bad dates/action/reason/schema |
| `REPORT_LIMIT` | existing mapping | Bounded calendar/ledger exceeded |
| `REPORT_ARTIFACT_INVALID` | existing mapping | Corrupt history, never an empty calendar |
| access errors | existing 401/404 | Do not reveal foreign calendars |

## Immutable Report Consumer

Old context schema 1 and six-file publications keep their exact bytes.
New prepared contexts with calendar history use context schema 2, adding one
`meeting_skips` snapshot (schema 1). Only server preparation produces it; no
client-supplied snapshot is accepted.

Snapshot binds series, calendar revision/hash, date interval, effective skipped
dates, reasons and recording attribution. The current meeting cannot be skipped.
Save/render/finalize/download consume the frozen snapshot, not live calendar state.
Existing seed replay keeps the original snapshot rather than refreshing it.
The snapshot's calendar identity comes from the preparation's pinned meeting,
not the current series policy, so a delayed original operation remains recoverable
after a subsequent policy revision.

Same-week continuation retains the previous snapshot start; a new period starts
after the actual baseline meeting. Initial reports can include earlier explicit
skips within the bounded window. Weekly views use selected daily publications'
frozen evidence, never the live calendar. A whole empty week is viewed through the
calendar; a weekly publication still requires real selected daily publications.
The non-publication empty-week entry is GET `reports/meetings/` with the selected
interval. A weekly context preserves the latest selected daily's complete frozen
snapshot, including its as-of revision; it does not recalculate historic truth
from the live calendar or union a subsequently restored date back into the result.

One compact `Standups skipped: <dates/ranges>` notice appears separately from ticket
statuses and unfinalized-draft warnings in pinned HTML/plain, editor, Markdown/Excel
and audit JSON. Old reports without the extension render identically. Explicit
skips do not count as unexplained missing reports; other coverage warnings remain.
Later restore cannot change a frozen draft snapshot or old publication bytes.

## UI Contract

Link `Meeting calendar` from the stage workbench to `reports/meetings/`.
GET selects series/from/through dates. POST adds action, reason, command, expected
calendar revision/hash and policy hash. Reuse Basic Auth, CSRF, private/no-store,
strict form/JSON keys and current project ownership. GET never writes.

Use shared Bulma form grid/action group, Iconoir icons and English/zh-CN labels.
No shared CSS, new framework or calendar-widget dependency. Fit 1440px and 390px.
Keep error dates/reason visible; provide explicit refresh and restore.
Show skipped dates separately in baseline preview and link a rejected generation
back to the calendar. No blank reports are generated for empty weeks.

## Authority And Consumers

| ID / risk | Producer | Consumers | Negative proof |
| --- | --- | --- | --- |
| SKIP-STATE / high | domain/model/service | public API, calendar UI | malformed/foreign/corrupt/CAS/replay/undo/quota |
| SKIP-ADMISSION / high | meeting service/root lock | preparation, direct seed, existing CLI/worker | occupied-range atomicity, races, zero provider/model/new-preparation work, no Git commits; ownership/replay/archive reads allowed |
| SKIP-SNAPSHOT / high | server preparation | context validator, save, render, weekly/export/audit | old bytes, forged/future snapshot, later restore |
| SKIP-UX / normal | forms/facade | calendar, stage and preview links | auth/CSRF/JSON, retained errors, mobile overflow |
| SKIP-RESUME / high | existing baseline/rollover | normal editor/save/finalize after gap | 1/3/7/14 days, cross-year, paint/AR/deletions, no intermediate reports |

The exact SKIP-SNAPSHOT validator consumers are
`app/domain/report_authoring_revision.py` (revision payloads),
`app/domain/report_continuity_edits.py`, `app/domain/report_meeting_matrix.py`,
`services/report_preparation_seed.py`, `app/domain/report_publication_validation.py`,
`services/report_preservation.py`, `services/report_period_views.py`, and
`reporting/pinned.py`. Verify the actual validator call sites before editing;
carry the extension through each, and exercise Save/reopen/Finalize/original
download plus old schema-1 and malformed schema-2 counterexamples.
Concrete helpers added during implementation: `out/report_meetings.py`,
`services/report_meeting_occupancy.py`, `services/report_meeting_snapshot.py`,
`app/domain/report_meeting_snapshot.py` and `services/report_continuity_replay.py`.
The shared error registry in `app/domain/report_contracts.py` and the seed
serializer/comparison in `services/report_continuity_seed_binding.py` are also
owned consumers. The latter normalizes missing optional authority for old replay;
the unchanged serializer is extracted there to keep the service under 400 lines.

Public API, services, UI, export, audit, migration, docs and fixtures apply.
Existing CLI/worker consume the preparation guards; a new calendar CLI is not
required. Scheduler is deferred and must use the same API when enabled.
No cache/search, SDK profile, provider, external artifact format or deployment
activation changes.

## Execution Plan

Use TDD, one writer and a bounded independent Architect Planner Reviewer for plan/
validation design and final source/evidence. Explicit subagent `gpt-5.5`/`xhigh`.
No exact-pass ledger/model configuration change. Direct-main execution is approved.

`W6.SKIP.PLAN.R -> W6.SKIP.CORE -> W6.SKIP.UI -> W6.SKIP.JOIN.R`
is one implementation wave; JOIN.R includes this slice's final refreeze.

| Node | Files and deliverable | Exit |
| --- | --- | --- |
| PLAN.R | this appendix, continuity/spec/tasks | API/authority/validation review, OpenSpec strict |
| CORE | new `app/domain/report_meetings.py`, `app/api/report_meetings.py`, `services/report_meetings.py`, migration `0004_report_meeting_changes.py`; series model and narrow prep/seed/context/render/period consumers | audited API RED/GREEN, pure/store negatives, actual Git readback |
| UI | new `ui_web/report_meeting_forms.py`, `facades/report_meetings.py`, `views/report_meetings.py`, `templates/projects/reports/meetings.html`; URL/language/locale/stage/preview wiring | strict HTTP, real skip/restore/error page |
| JOIN.R | scoped tests/receipt/current and development guides/tasks | mounted two-week resumption, independent review, scoped publication |

Helpers may split by ownership to keep source under 400 and tests under 600 lines.
Do not put test-only cleanup methods in production.
Use SDK0.2.0a1 reporting interpreter and existing no-dotenv/network-denying runner:

```powershell
& .tmp/sdk-020-join-20261105/app-venv/Scripts/python.exe -I scripts/validation/run_report_authoring_tests.py project_management/tests/test_report_meetings.py -q --junitxml=.tmp/dashboard-skips-20261106/core.xml
& .tmp/sdk-020-join-20261105/app-venv/Scripts/python.exe -I scripts/validation/run_report_authoring_tests.py ui_web/tests/test_report_meeting_views.py -q --junitxml=.tmp/dashboard-skips-20261106/http.xml
& .tmp/sdk-020-join-20261105/app-venv/Scripts/python.exe -I scripts/validation/run_report_authoring_tests.py ui_web/tests/test_report_meeting_browser.py -q --junitxml=.tmp/dashboard-skips-20261106/browser.xml
```

Targets above become executable when created; use unique RED/GREEN XML.
L0: interval/chain/snapshot/date projection. L1: transaction, replay, stale CAS,
partial reservation, actual archive and unchanged baseline/hash.
Partial-reservation fixtures must include an intent written before slot creation
fails, subsequent original-command slot repair, and a seed with no draft yet.
An absent-stage skip must leave both stage/runtime and archive-root identity absent.
L2: strict API/auth/CSRF, failure-state input retention.
L3: actual editor/HTTP/ORM/Git with synthetic external boundary. Finalize colored
notes on 2026-11-06, skip 11-09..22, resume 11-23, save/reopen/finalize. Assert
Friday note/status/paint, unresolved AR/persistent content, original files, compact
skip notice, restore and zero intermediate draft/publication/source/model work.
Complement with parameterized shorter and cross-year gaps and initial no-baseline
cases; do not construct fourteen artificial days.

Reuse prior SDK/AI/full-week evidence only within unchanged boundaries. This does
not close live provider/model/Outlook/deployment, observed latency or broader
Dashboard migration. Finish with scoped size/whitespace, isolated Django check/
migration consistency, OpenSpec/link checks, bounded review, scoped commit and
remote SHA verification. Preserve pre-existing work.

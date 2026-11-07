# Standup User Workflow Hardening

Date: 2026-11-07; updated 2026-11-08. Status: implemented and validated within this packet.
Owner: Dashboard / project_management; no AI Base SDK change.
Docs impact: architecture, user, API, migration, operations.
Human docs: `openspec/docs/current-baseline/project-reporting.md`,
`docs/development/reporting-delivery.md`.
Single execution ledger: [tasks.md](tasks.md), `W6.USER.*`.
Supersedes the current-only observation/display limits in
[source-observation.md](source-observation.md), not its source/summary separation.

## Confirmed Gaps And Outcomes

The six probes in `.tmp/dashboard-corner-audit-20261107/test_user_scenarios.py`
reproduced behavior on `bb0e841`. They are diagnostic evidence, not passing
acceptance of the desired behavior.

| ID | Real user case | Required outcome |
| --- | --- | --- |
| U01 | New week has zero current tickets | The real meeting date still exists; prior notes and open AR remain visible in historical rows; zero current members is not zero work |
| U02 | Tuesday reuses Monday's capture, or a meeting is backfilled | Show source cutoff and reused/date-mismatched source explicitly; never imply Jira was checked for the meeting date |
| U03 | A human types `AR: @Bob` in prose | Prose stays prose; explicit Add AR creates independently tracked work that survives newer notes and rollover |
| U04 | A ticket leaves scope and returns | Stable row and prior observation survive; same accepted summary cannot resurrect deleted AI wording; reentry is distinct from first appearance |
| U05 | Tuesday has only a no-change observation | Wednesday's accumulated history retains Tuesday's observed meeting, without converting it into an authored note |
| U06 | All notes are manually filled without AI | Source completeness, AI-summary availability, note coverage and human meeting review are separate counts |
| U07 | A meeting is held but a ticket is not discussed | Only an explicit user choice records discussed/not discussed/no additional update; generation, Save or Finalize does not imply review |
| U08 | Browser or PC crashes before Save | An acknowledged recovery checkpoint survives; explicit restore cannot overwrite a different server revision or imply Save/Finalize |

## Design Choice

Use one versioned authored context and the existing draft writer, not an
additional event store, inferred text parser or AI workflow. A context describes
the selected meeting and its cumulative presentation; immutable publications
remain historical authority. Source comparison, authored prose, actionable work
and human discussion stay distinct. Rendering never calls a provider or model.

Creating dummy DailyNotes for observations is rejected: it conflates system facts
with human authorship and reproduces deletion bugs. An unbounded scan of all past
publications on every page is rejected: the prepared context carries bounded
source history needed for the next meeting. Recovery is a separate local-server
checkpoint, not browser localStorage holding enterprise text and not automatic
creation of saved or published revisions.

## Context Version 3

Keep all existing context keys. New contexts use integer `schema_version=3`,
mandatory `meeting_skips` (null or the existing frozen skip snapshot), plus:

```text
past_observations: CurrentObservation[]
meeting_history: [{meeting: MeetingIdentity, capture_id: UUID|null,
                   source_as_of: Instant|null}]
meeting_reviews: [{issue_ref: IssueRef, meeting: MeetingIdentity,
                   state: discussed|not_discussed|no_additional_update,
                   recorded_by: str, recorded_at: Instant}]
```

`current_observations` remains only the current meeting's observations and
continues to authorize current-note edits. `past_observations` contains no
current-date entry. Retain all available observations for the current period
and the latest prior-period observation per stable issue, including departed
issues. This collection supplies reentry comparison; do not maintain a second
latest-observation database.

`meeting_history` records real meeting identities independently of ticket count.
Retain current-period meetings, the preceding actual meeting even when empty,
plus dates needed by carried observation anchors.
Store original capture ID/time; unknown legacy values are null, not guessed.
Each logical date and issue/date pair is unique. Future observations, inconsistent
calendar/period, overlapping past/current observations, reviews without a valid
row/date, duplicate IDs or unknown keys fail closed. Existing 8 MiB context quota
still applies before persistence.

On preparation, load the verified prior finalized context, derive retained
history, compare each current source against that issue's latest observation,
then independently decide summary-note eligibility. A previously used accepted
summary cannot generate a new initial note merely because membership disappeared.
Never equate permission loss with closure. Retained content is already authorized
report history; reentry still uses normal current source/scope authorization.

Legacy v1/v2 readers preserve exact keys/canonical bytes. Explicit preparation
or new v3-specific edits can create a v3 successor; no read rewrites old files.
Only available legacy observations are inherited; do not fabricate observations
for prior meetings absent from their old context. Existing original downloads
remain byte reads. `freeze_meeting_snapshot` must not downgrade v3 to v2.
Weekly union merges observations, meeting identities and review records from
explicitly selected immutable daily publications, preserving correction precedence.
Same-day reprepare keeps human reviews only for the same source snapshot;
refreshed source requires new human review.

## Projections And Source Freshness

The current daily meeting always produces a column, including zero members and
no notes. Historical observation-only days also produce columns. Dates outside
the active week remain seed context, not extra week columns.

One shared observation projection combines notes and system observations in
date order; notes retain their original date/status/paint. Never show future
observations in an earlier column. Both concise and generic matrix output use
the same rule. Current editable slots remain restricted to current observations;
past observation rows cannot become editing targets.

Source equality is a content comparison, not a freshness claim:

- Equal hash and a new capture on the selected meeting's local date:
  `No source change`.
- Same capture as the preceding observation:
  `Source not refreshed; using saved capture`.
- Capture local date differs from meeting local date:
  `Source date differs from meeting date`.
- Missing source time in an old observation:
  `Source observation time unavailable`.
- Incomplete/unavailable/comparison-unavailable warnings always remain visible.

Priority is source uncertainty, then reused capture, then date mismatch, then
ordinary source-state text. A human note may replace ordinary no-note labels,
but cannot hide stale/uncertain source. Concise reports always include one short
source-cutoff/timezone line. Reentry is labeled `Returned to scope`; do not
claim the unobserved interval was unchanged.

Readiness is derived, not another stored mutable status:

```text
Source: complete / incomplete / unavailable counts from verified ReportRows
AI summaries: available / unavailable counts (not human acceptance)
Notes: current-date notes present / current tickets (empty notes are explicit)
Meeting review: explicit review records / current tickets
Publication: existing draft/saved/finalized lifecycle
```

Zero denominator displays `No current tickets`, not fictitious 100% review.
Missing/skipped reports retain separate labels. Finalize remains an explicit
report-level decision; unreviewed rows are shown, not silently marked reviewed
or blocked by a new undocumented mandatory policy.

## Human AR And Meeting Review API

Reuse `ReportDraftService.save_authored(..., continuity_changes=...)` and its
existing revision/hash CAS, command replay, owner check and archive quotas.
Additional neutral commands:

```text
add_report_action(action_id: UUID, issue_ref: IssueRef,
                  owner_ref: {owner_id, display_name}|null, fragment: RichTextFragment)
set_action_owner(action_id: UUID, expected_owner_ref: object|null, owner_ref: object|null)
set_meeting_review(issue_ref: IssueRef,
                   state: discussed|not_discussed|no_additional_update|unreviewed)
```

Commands are JSON objects with `kind` plus exactly the named arguments. Non-null
owners require nonblank bounded identifier/display name. They are explicit report
owners, not verified provider accounts or notification recipients. IDs are unique,
issue identity must belong to a retained report row, and context must be daily.
Human actions use the existing action shape with v3 `provenance`:
`{origin:"human",created_by,created_at,updated_by,updated_at}`; basis is `recorded`,
tracking starts `open`, evidence refs start empty. Source actions keep their legacy
shape and evidence. Plain `AR:`/`@` input never creates an action.

Reuse `set_action_tracking` for open/done/canceled/unknown. Human action closure
requires a nonempty resolution plus server actor/time, but no invented provider
evidence. Source-action closure retains existing evidence rules. Changing owner
requires exact expected-owner match as well as draft CAS for human-created AR.
Provider-derived action owners remain evidence; reassignment is a new explicit
human follow-up AR rather than rewriting source attribution. Closed actions stay
in the catalog to prevent resurrection; open/unknown actions carry independently.
The editor provides explicit reopen. On a departed row, current-meeting AR
management remains available without an editable current ticket note.

Review commands attach server actor/time and current meeting identity.
`unreviewed` removes the current review record. Review records what the host
confirmed, not that a provider fact or AI conclusion is true. Programmatic and
UI calls go through the same command validator.

## Recovery Checkpoints

Use `ReportRecoveryService(draft_service)` within project_management. It uses
the existing stage/root lock, path protections and quota admission. Recovery
never calls capture, AI, Save, Finalize or data-Git append.

```text
list(actor, project_id, stage_id, draft_id) -> recovery summaries
put(actor, project_id, stage_id, draft_id, *,
    client_id, sequence, base_revision, base_revision_hash,
    snapshot_hash, template_hash, content) -> receipt
get(actor, project_id, stage_id, draft_id, client_id) -> bound checkpoint
discard(actor, project_id, stage_id, draft_id, client_id, expected_sequence)
```

Store mutable atomic checkpoints at the owned draft runtime path
`recovery/<client_id>.json`. Server envelope binds owner/project/stage/draft,
base revision/hash, snapshot/template and server time; hashes detect corruption.
Limit 4 independent client checkpoints per draft, 1 MiB per checkpoint and
existing root/stage quota. Retention is seven days; expired checkpoints cannot
restore. Cleanup removes only validated expired checkpoint files, never authored
revisions or publications. Lower sequence is rejected; same sequence/same bytes
replays; same sequence/different bytes conflicts. Tabs use different client IDs.

Authenticated, CSRF-protected routes under the existing draft URL:
`recovery/` GET(list)/POST(put), `recovery/<client_id>/` GET/read and POST/discard.
Unknown fields, unsafe fragments, malformed JSON, foreign targets, oversize and
wrong owner fail closed. Responses are private/no-store. Content is bounded
neutral editor state, not HTML, credentials, cookies, CSRF tokens or scripts.
An unavailable/unconfigured archive factory returns safe 503 JSON without a
traceback response; recovery failure does not block ordinary manual editing.

The editor checkpoints dirty state after a short debounce, one request in flight,
with a visible receipt time or failure state. A receipt guarantees only the
acknowledged checkpoint; unsent/offline/newer edits remain at risk. Keep the
actual Save command/body when its response is uncertain; recovery cannot turn
unknown Save into a new command or automatic POST.

Exact checkpoint `content` is `{edits: AuthoredEditRequest[], continuity_changes:
ContinuityChange[], save_request: null|{command_id,expected_revision,
expected_revision_hash,edits,continuity_changes}}`. Each array is bounded to 100
items. Partial human input may be recovered, but Save still requires valid AR
body/resolution. Checkpoint validates exact JSON keys, fragments and target
membership without claiming the reference/AI receipts were newly accepted.
The input debounce is 1500ms, maximum continuous-edit delay 10000ms and per-request
timeout 8000ms. Only acknowledged data is recoverable; this is not offline backup.

Reopening offers Restore / Discard and checkpoint time. Restore is explicit
and only enabled for the same base revision, source/template and targets.
Restored edits are dirty; normal Save validates them again. If server revision
advanced or draft finalized, keep the buffer viewable/downloadable for manual
reconciliation; never overwrite the server revision. Clear only the acknowledged
client checkpoint after Save when no newer local changes remain. A failed save,
stale response or another tab must not erase it. Recovered reference/AI receipts
do not become new authority; normal expiration/refusal/human-link rules apply.

## UI Contract

Target: report editor, read-only weekly matrix, concise report and source summary.
Django/Bulma/htmx plus existing Milkdown; compact existing fields/selects and
icon+text commands, no new framework or global CSS changes.

- Current row: meeting-review select; Add AR with owner/body inputs.
- Current AR: owner, open/done/canceled controls, resolution and explicit reopen.
- Removed row: historical identity and current AR controls; no fake provider status.
- Header: separate source/AI/note/review counts; recovery status and controls.
- Read-only history: observations/notes chronological, correct dates.
- Mobile: constrain controls, wrap labels, no page overflow, >=4.5:1 contrast.
- EN/zh-Hans UI; canonical business output English.
- States: zero tickets, stale source, validation, unassigned owner, unreviewed,
  dirty, saving, recovery unavailable/conflict/restored, completed.

## Contract Propagation And Execution

profile_source: repo-local. agent_routing_mode: multiagent-configured.
One production writer, bounded independent plan/validation and behavior reviews.
No separate debugger for already reproduced deterministic cases.
Baseline `bb0e8417f757518dbb2f9ba236a8d7cdfcef8def`, own main.
Preserve 13 pre-existing Scope/config/main.css files and original enterprise demos.

| Contract / risk | Producers -> consumers | Negative checks |
| --- | --- | --- |
| USER-HISTORY high | continuity builder/v3 validator -> seed, preservation, period union, matrix, both renderers, editor | current-only target auth, reentry old summary, zero scope, future observations, old hashes |
| USER-READINESS normal | source/context -> shared presentation -> report/editor | stale capture not current, no AI not missing notes, generation not discussion |
| USER-AR high | continuity commands -> authored Save -> publication/rollover/UI | foreign issue/action, duplicate ID, stale owner/CAS, empty resolution, source evidence, no prose parsing |
| USER-RECOVERY high | editor -> recovery API/service/store -> explicit restore -> Save | owner/CSRF, size/path/sequence, conflict/finalized binding, malformed content, unknown Save, crash, tabs |

Public API, internal service, UI, export/report, audit, schema, recovery storage,
current docs and fixtures apply as above. Validation scripts reuse existing
runners. Scheduler/cache/index/provider adapters/SDK are not changed. No production
activation, external data or model. Exports remain projections of saved HTML;
old published bytes never rerender. No new credentials or external packages.

| Node | Depends on | Files / result |
| --- | --- | --- |
| W6.USER.PLAN.R | user approval | this spec, requirements/tasks; independent compatibility/security/test review |
| W6.USER.CORE | PLAN.R | domain/report_continuity*, new report_observation_history/report_workflow_changes, meeting_matrix, reporting/observations+standup+pinned, services/report_period_views+report_preservation+report_meeting_snapshot; core through real Save |
| W6.USER.CORE.REPLAN | CORE | scoped review and editor/recovery interface refreeze |
| W6.USER.EDIT | CORE.REPLAN | ui_web view models/editor partials/report_editor JS/catalog; AR/review/removed/empty rows |
| W6.USER.RECOVERY | CORE.REPLAN | new domain/service/storage/API recovery modules, ui_web routes and recovery JS |
| W6.USER.ACCEPT.R | EDIT + RECOVERY | current docs/evidence, representative native/browser chain, scoped review/publication |

Convert six probes to RED tests in `test_report_user_workflow.py`; add
`test_report_workflow_changes.py` for commands and strict v3/legacy checks.
Run pure tests, then affected history/period/skip/preservation/authoring cases.
Add `test_report_recovery.py` for storage/API and `report_recovery_test.mjs`
for sequences/restoration. HTTP cases use real auth/CSRF and error paths.
One synthetic native Git chain covers human AR, observation-only day, zero-scope
rollover/reentry and old bytes. Mounted cases cover AR/review/save/reopen and
browser close/reopen restoration, EN/zh-Hans and desktop/390px.

Use `.tmp/sdk-020-join-20261105/app-venv/Scripts/python.exe -I
scripts/validation/run_report_authoring_tests.py` with explicit paths; Node uses
the existing ESM entry. Evidence: `.tmp/dashboard-user-workflow-20261107/`,
unique RED/GREEN files. No full-week/Base/S1 reruns unless their dependency changes.
Run scoped size/whitespace, isolated Django check, OpenSpec strict and gettext
validation. Collection/skips are not acceptance. Update tasks at node boundaries;
after two equivalent failures change instrumentation; after 60 minutes reassess.
Current guide truth-sync and all required user controls are closure criteria.

## Refreeze Receipt

Independent CORE admission and recovery refreeze by
`01a1b6a5-6b83-7be3-bc59-d832b9647cf9` found no material blocker. Core requires
previous-empty-meeting retention and current-only edit targets; both are included.
Recovery remains a separately bounded service with exact same-base restore.
The retained CORE tests passed 22/22 before UI, and source/UI boundary checks
then passed 83/83. Recovery storage/HTTP passed 12/12 before mounted validation.
Native Git and browser closure have separate run receipts; counts here describe
the refreeze stage, not final total coverage.

`refreeze_actions=[{action:continue,reason:core and recovery contract boundaries are reachable}]`.
`updated_artifacts=[standup-user-workflow.md,tasks.md]` within this change.
`post_refreeze_preflight_result={method:review current-only editing, v3 consumers,
recovery neutral JSON and native/browser targets,result:PASS}`.
The final UI inventory additionally includes `projects/reports/period.html` for
observation-only weekly cells and `projects/reports/recovery.html` for checkpoint
controls. No old runtime or third-party SDK is replaced.

## Final Delivery Receipt

Evidence root: `.tmp/dashboard-user-workflow-20261107/`.
Final source/test fingerprints and deduplicated case inventory:
`validation-receipt-8e719262-6f28-4931-9e02-21c2a01f8770.json`.
The prior receipt is retained as pre-cleanup evidence; the final source differs
only by unused-import/format cleanup, followed by the attribution recheck.

| Lane | Evidence | Result |
| --- | --- | --- |
| Current core, commands, recovery, UI and mounted browser | `final-candidate-01.xml` | 101 passed, including isolated Django/SDK/gettext check |
| Legacy save/period/skip/reprepare consumers | `final-history-01.xml` | 65 passed |
| Final touched save/renderer consumers | `final-changed-consumers-01.xml` | 9 passed |
| Native four-date publication chain | `native-chain-01.xml` | 1 passed; empty new week, human AR, reentry, observation-only day, 24 original-file comparisons |
| Real capture/manual worker/backfilled dates | `native-capture-backfill-01.xml` | 1 passed; equal source with explicit date mismatch, original bytes and Markdown/Excel |
| Prior observer browser and unavailable recovery HTTP | `final-compatibility-01.xml` | 12 passed |
| Final human AR attribution cleanup | `final-attribution-01.xml` | 10 passed |
| Node recovery/editor/export | `node --test ui_web/tests/report_recovery_test.mjs ui_web/tests/report_editor_test.mjs ui_web/tests/report_exports_test.mjs` | 18 passed |

These overlapping Python lanes contain 179 distinct checks including one isolated
environment/system check, not 179 unrelated E2E runs. The four-date native chain
uses a synthetic source projection and real data Git; the separate capture chain
uses the native capture service with synthetic provider transport. Neither calls
real Jira/HSD-ES or a model. The final changed-consumer/attribution lanes cover
late narrow refinements without repeating the 648-second history fixture set.
Durations are test/fixture timings, not latency SLOs or whole-task wall time.

Browser evidence `browser-2c24d835-b6f9-4261-a125-4d22ccafa119/` includes English
input, Chinese desktop/390px restoration, saved color/note/persistent content,
AR owner change, completion and reopen. The second mounted case commits a real
Save and drops its reply: after reopening, restoration is disabled, download
contains the original Save identity, discard succeeds and revision 2 is unchanged.
All owned test processes/browser servers exited normally.

Failures retained: initial source/command RED, missing recovery API RED,
unconfigured factory RED, period-display RED, human action-attribution RED,
and the initial browser predicate that closed before the checkpoint response.
They are not counted as acceptance. Existing old source-observation fixtures
now distinguish fresh recapture from same-capture/backfilled use.

Independent reviewer `01a1b6cc-e4c9-7d41-929a-f0e6f3bd850c` found no remaining
source correctness/security issue after bounded delta checks. Its initial evidence
gap was closed by the completed `final-history-01.xml`; final P0/P1/P2/P3 are zero.
This is bounded independent source/evidence review, not automated exact-pass
certification. OpenSpec strict, whitespace and all 36 scoped Python/doc size
checks passed. The 13 protected unrelated Scope/config/main.css files are unchanged.

Publication scope is 54 explicitly allowlisted code/test/doc/catalog files to
the user's own `origin/main`. No push to upstream, enterprise evidence export,
formal service switch, scheduler activation or SDK change. Prior performance
measurements remain tied to their original candidates; no new production SLO
or offline-recovery guarantee is claimed.

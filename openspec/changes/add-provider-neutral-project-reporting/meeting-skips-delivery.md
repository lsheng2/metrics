# Skipped Meetings Delivery

Date: 2026-11-06. Scope: `W6.SKIP.*`.
Source base: `aa595d68a9032371faa883b29a244442b5431aec`.
Task status remains in [tasks.md](tasks.md); contract:
[meeting-skips.md](meeting-skips.md).

## Delivered

The stage workbench links to a bilingual meeting calendar. Operators select a
single date or an inclusive range, record a skip/reason, or restore eligibility.
An append-only, hashed Django history records actor, server time and both calendar
and policy CAS. Original-command replay returns its original receipt without
reapplying a superseded skip or advancing the project revision.

Unrecorded days, explicitly skipped days and occupied report dates are distinct.
Any retained preparation intent, context seed, draft or daily publication rejects
the complete overlapping skip range. Intent-only interruption and slot repair are
covered. A root-only lock coordinates with the existing stage writer and does not
initialize stage/runtime/Git for a first skip. Date preparation and seed writing
both recheck admission under their existing writer lock.

The resumed report carries actual confirmed notes/paint/status/dates and unresolved
ARs. It never generates intervening reports. New schema-2 contexts freeze skipped
dates and reasons; legacy context schema 1 and the original six-file publication
contract remain unchanged. HTML/plain, Markdown/Excel and original audit context
preserve the notice. Restoring dates later does not change saved or published bytes.
Empty-week viewing uses the calendar; a weekly publication still selects actual
daily publications. Its skip notice comes from the latest selected daily snapshot.

Manual work uses the existing SDK0.2.0a1 environment but does not instantiate an AI
client. No provider/model/scheduler SDK interface or runtime profile changed.

## Validation

Evidence root: `.tmp/dashboard-skips-20261106/`.
All commands used the selected interpreter and the no-dotenv, external-network-
denying `run_report_authoring_tests.py` with explicit targets.

| Evidence | Result and boundary |
| --- | --- |
| `core-red-01.xml`, `core-red-02.xml` | Missing public meeting API reproduced before implementation |
| `core-green-02.xml` | 8 passed: audited range/undo/replay, conflict, seed/intent occupancy, race, first-stage and corrupt/foreign refusal |
| `strict-red-01.xml` | Reproduced replay project-revision mutation and unhashable action; corrected both |
| `resumption-red-01.xml` | Existing next-date context lacked the planned calendar snapshot |
| `policy-red-01.xml` | Delayed old-policy preparation incorrectly used the latest calendar |
| `final-core-01.xml` | 46 passed, no failures/errors/skips; dates/quotas, calendar state, real-Git resumption, pinned-policy fix, existing history and publication guards |
| `http-red-01.xml` | Missing calendar route before implementation |
| `ui-state-red-01.xml` | Invalid-range reason was lost and preview lacked skipped state |
| `http-green-02.xml` | 3 passed: actual GET/POST, JSON, CSRF/owner, errors/input retention, undo and skipped-day refusal |
| `browser-01.xml` | 1 passed, 189.04s: actual mounted editor/HTTP/ORM/Git, two-week skip and resumption, desktop/390px, original bytes and three exports |
| `locale-browser-01.xml` | 1 passed, 19.10s: Chinese calendar navigation/selection, unique form IDs, desktop/390px |
| `weekly-consumer-01.xml` | 1 passed: expanded real-Git resumption also preserves selected weekly snapshot after restore and refuses empty-week publication |

Counts above overlap where a consumer was strengthened; they are not summed as
independent scenarios. The original full week and unchanged SDK/profile tests were
not rerun. The newer pinned-calendar fix only affects delayed policy changes; the
mounted sample used the same policy throughout. Its earlier proof remains valid.
The seed serializer extraction moved unchanged behavior to the existing binding
module; final service tests cover the resulting code.

Two test-assembly corrections were retained: `render` needs its exact revision,
and rollover note catalog order is not the stable row-order contract. Tests compare
note ID/hash associations instead. An injected OSError is correctly translated by
the existing archive layer; the fixture now expects that public domain error.
The generic error registry had to register the new meeting codes. No production
guard was weakened to obtain a pass.

An existing optional-authority mismatch was exposed by the old seed replay test.
Comparison now normalizes absent authority to `None`; original stored bytes are
unchanged. Replay runs before rebuilding current source/calendar context.
The archived HTML validator disallows editor-only data attributes, so the new
static notice uses ordinary escaped paragraphs rather than expanding the allowlist.

## Retained Scenario

Browser artifacts:
`.tmp/dashboard-skips-20261106/browser-3c136756-4f25-4217-be39-044867a0dad0/`.

1. Prepare 2026-11-06, enter red human note and a carry-forward follow-up note,
   Save/reopen and explicitly Finalize.
2. Record 2026-11-09..22 as skipped with reason `Planning break`. Verify all fourteen
   rows, no report-source query and no AI client; preview a skipped day refuses
   generation.
3. Prepare 2026-11-23 from the actual previous final. Preserve Friday's canonical
   note and persistent content, enter blue Monday note, Save/reopen/Finalize.
4. Download HTML/Markdown/Excel, restore the skipped interval and verify both
   original publications and the frozen Monday notice remain unchanged.

The test retains screenshots, `report.html`, `report.md`, `report.xlsx`, both
original six-file packets and `result.json`. A post-run check matched all twelve
original-file hashes. Exactly two drafts exist; SDK/provider/model calls are zero.
The service-level complementary sample covers actual structured unresolved ARs;
the mounted sample's additional follow-up is a human persistent note.
Temporary browser/app fixtures exited normally with pytest.

## Review And Release

The independent plan review raised five contract clarifications; root-only locking,
read-versus-write terminology, full validator consumer inventory, empty-week
semantics and partial-reservation cases were made explicit before implementation.
The bounded independent source review found no blocking issue. Its remaining
request for post-fix pinned-calendar evidence is satisfied by `final-core-01.xml`.

Isolated Django check reported no issues; migration dry-run reported no pending
model changes. Scoped size and whitespace checks and OpenSpec strict passed.
The final size selection checked 37 governed files and the local-link pass checked
72 links. Independent evidence-only follow-up verified the pinned-policy,
weekly-consumer and Chinese-browser XML and closed its remaining evidence request.
Current reporting/development guides now explain skipped meetings and correct the
stale whole-week/SDK statements; unrelated Scope/config/shared CSS remains intact.

The retained synthetic demo database alone received migration 0004 after both
demo services were confirmed stopped. Its SQLite backup is
`environment/catalog-before-meetings-f04d82c0-68f4-4d78-9e53-9e38f394b2c8.sqlite3`
under retained run `aa2fb399-4557-4342-b725-8de2dab91aba`.
Reopening that demo is a usability aid, not clean-install/production qualification.
The 1800-second demo start returned app port 8127 and Base port 48600; authenticated
calendar GET returned 200/private/no-store. Existing Base dispatch count remained
three; no new model task was submitted. Current process identity is in the retained
run's lifecycle records, not a static PID promise.

This closes the skipped-meeting implementation and bounded local qualification,
not the whole Dashboard release. Live Jira/HSD/model, Outlook, formal deployment,
the previously observed 53-77s request waits and broader migration retain their
separate gates. No real service or production database was switched.

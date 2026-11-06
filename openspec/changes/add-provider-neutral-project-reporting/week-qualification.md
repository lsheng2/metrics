# Full Week Qualification Packet

Date: 2026-11-06. Source base: `6b1b543ded78aae0d5e299edaa37ba3159540c29`.
Node: `W6.AUTHOR.JOIN`; task state stays in `tasks.md`.
profile_source: repo-local. agent_routing_mode: multiagent-configured.
One implementation coordinator/writer and one bounded independent fixture/evidence
reviewer. Reuse completed DAILY, DELTA, ASSIST and EXPORT proof; do not rerun their
malformed-field suites inside this long workflow.

## Required Result

Execute the original user scenario on one frozen runtime candidate:
2026-10-26, 27, 28, 29, 30 and 2026-11-02, ISO WW44.1-5 then WW45.1.
Use three independent synthetic Jira tickets with constant facts/comments/status/
assignee across all captures. The first summaries must be produced and accepted
through installed SDK0.2.0a1 and real loopback Base HTTP; all later unchanged captures
reuse those accepted summaries with zero new Base dispatches.

Create user daily/weekly templates and a report series through the real UI.
Prepare each day through the existing button/worker, edit real Milkdown content,
Save, reopen and explicitly Finalize. Retain per-day canonical notes/paint and
original publication files. Perform a normal app-process restart before Wednesday.
Friday's weekly view must not advance the daily baseline. New-week seed preserves
original date/status/format of the last confirmed note plus unresolved ARs and
carry-forward notes. Run a separate pending-draft/explicit-gap branch without
altering the completed main series.

## Existing Runtime To Reuse

`scripts/validation/project_full_stack.py` already owns prepare/start/status/
restart-app/stop with a fresh UUID run directory, explicit owner markers, isolated
SQLite/data Git, sanitized environment, process identity and normal-stop evidence.
Its settings suppress dotenv and use synthetic credentials. Existing single-ticket
fixture and qualification receipts must remain compatible and untouched.

Extend the launcher with an allowlisted `--scenario full-week` choice; default
remains the existing single-ticket scenario. Persist the scenario in the runtime
manifest. Resolve settings and fixture modules from an internal fixed map, never a
caller-provided import path. `validate_manifest` must reject unknown scenarios.
The same stored choice is consumed by prepare/start/restart/status/stop.

Data remains under the existing owned validation root outside source repositories.
Do not delete prior runs, use the old 8017 service, switch the main legacy venv,
modify Base's fixed source/released pack, or activate real credentials/model/provider.

## Fixture Interfaces

New `project_week_data.py` holds only pure synthetic constants: the fixed three-ID
JQL and row definitions. Example identities are ALPHA-101/102/103, statuses include
In Analysis and Fixed, and a shared PR/owner does not merge rows. Provider timestamps
remain unchanged; meeting dates do not change Windows time or provider facts.

New `project_week_fixture.py` reuses current fixture/service assembly, with explicit
parameters added to `project_full_stack_fixture.py`:

```text
synthetic_profile_records(query=FROZEN_JQL) -> list[dict]
prepare_catalog(run_dir, *, query=FROZEN_JQL, vector_builder=None) -> catalog
build_runtime_environment(connection, *, records=None, provider_factory=None) -> ProjectRunRuntime
```

Default callers keep their exact existing behavior. `_scope_config(query=...)`
must freeze the same chosen query into the scope, profile, catalog and capture
request; no string rewriting of existing vectors/receipts.

The week provider fixture uses the existing Jira capture adapter/access service and
strict synthetic `requests` transport. It admits only the fixed host, GET, known
membership/issue/comment paths and exact pagination/field/query parameters.
It returns three real normalized source records through the capture pipeline.
Keep a redacted request/response-hash log in this run's evidence. No pre-seeded
accepted summary and no direct write of final authoring context.

Build three initial input/output vectors through existing `build_initial_input`,
one per stable source identity. `project_full_stack_base.py` may select a vector
from an explicit fixture `cases` collection by exact binding/stable ID. It still
validates input schema, dynamic capture identity, complete normalized input and
output binding. Default one-vector behavior remains unchanged. Unknown/changed
input fails; the synthetic executor records every dispatch.

New `project_week_settings.py` imports the current isolated settings and changes
only the profile-record query and runtime factory for this fixed scenario.
The runtime reuses real capture, summary journal, report service and worker.
Inject only the reference-read boundary for `#ID`; retain real membership checks,
signed receipts, Save verification and historical association. The synthetic
reference reader uses the same three ticket values and live membership proof,
not invented scope membership or a view-level replacement of business logic.

## Browser Driver

New `project_week_browser.py` consumes an owned run directory and its verified
runtime manifest. It uses the actual published app URL and synthetic account, with
outbound browser requests denied except loopback/data/blob. Do not print credentials.
Record the runtime source/test/vendor/SDK/fixture fingerprints before the first day.

Reuse public routes and existing data attributes for:

- Report templates: copy continuity daily and weekly starters, save an actual
  user modification, retain their template IDs/revisions/hashes.
- Stage reports: create series with ISO8601/Asia-Shanghai and the daily template.
- Daily preview/prepare: choose meeting date, refresh source and changed_items.
  Observe actual POST status/body before navigation or polling waits.
- Editor: current `daily_note` regions, shared formatting controls, persistent
  note/AR controls, `#ID` popup, Save, reopen, original-byte/derived downloads.
- Publication: explicit finalized result and read-only weekly/new-week flow.

Only stable routes/selectors observed in repository templates or actual DOM may be
used. Helper files may split driver operations, UI routines and read-only assertions;
do not create another runtime worker or product execution engine.

Use a read-only assertion helper in a separate process with the same isolated
settings when full canonical context is required. It calls public report/source
APIs on the retained archive, not direct SQL/file mutation. Each assertion result
binds the run/project/stage/series/draft/publication and expected source fingerprints.

## Day Matrix

| Day | User operations | Required evidence |
| --- | --- | --- |
| Mon 10-26 | First real capture/SDK/Base summaries; edit/delete initial AI wording, red note/link; retain multiple open ARs; Save/reopen/Finalize | Three separate rows, provider status, three accepted source identities; Save alone does not advance editorial baseline |
| Tue 10-27 | Refresh unchanged; blue note and green carry-forward note; Save/reopen/Finalize | Monday note ID/hash/paint unchanged; accepted summaries reused |
| Wed 10-28 | Normal app-process restart; refresh unchanged; highlight/bold note; `#ALPHA-101` third format, undo/redo; Save/reopen/Finalize | Same Base store/dispatch count; reference receipt/link/owner preserved; three days in order |
| Thu 10-29 | Add then remove text, clear another target, paint-only save; stale second-window save rejected with local text retained | No old sentence resurrection, 409 does not overwrite; prior days unchanged |
| Fri 10-30 | Mixed paint/note; resolve one AR, keep another; Save/reopen/Finalize; create/download weekly view | Five daily updates per ticket; weekly view does not become daily baseline; HTML/JSON paint and exports retained |
| Mon 11-02 | New period, unchanged source; inspect seed; append new note and Finalize | Last confirmed per-ticket note keeps old date/status/paint; unresolved AR and persistent note carried; old week immutable |

For every meeting, repeat prepare before finalization with the same effective
choices and verify the original operation/draft, no duplicate capture/summary.
After finalization, changed-baseline replay may correctly return 409 with the
existing publication; do not weaken that protection to force a redirect.

Use a separate series for the pending-draft branch: save without finalizing,
preview the next day, confirm the explicit gap and verify the old draft remains.
This branch must not change main-series baseline or create new unchanged-source AI.

## Bounds, Evidence And Stop

Each request/navigation has an explicit bound; failures preserve its response and
screenshot before stopping. Do not use repeated whole-week runs as a debugger.
First prove fixture matching and the first day. On a product failure, reproduce
at the owning lower layer before deciding whether the matched-candidate run must
restart. Do not combine changed-runtime days into a claimed same-candidate pass.

Retain original six publication bytes, Markdown/Excel projections, canonical
context and per-note/AR/persistent-note hashes; edited/reopened/finalized screenshots;
prepare/operation/draft IDs, expected 409s, source hashes, accepted summary IDs,
dispatch/provider counters and restart/normal-stop receipts. No secrets or
enterprise source text in logs or commits.

The driver owns only resources created by its run. Use existing normal `stop`
in a finally path; emergency forced stop is a separate failed-cleanup conclusion.
Keep the data/evidence directory. All known owned exec sessions must finish before
reporting. Formal deployment, scheduler, real provider/model and Outlook stay
outside this synthetic gate.

## Validation And Ownership

Owner files: new `scripts/validation/project_week_*.py`; minimal explicit scenario
extensions in `project_full_stack.py`, `project_full_stack_fixture.py`,
`project_full_stack_base.py`, `project_full_stack_identity.py`; their focused tests
under `project_management/tests/`; this packet/tasks/validation/current docs.
No production changes are pre-authorized as speculative fixes; a discovered bug
must get its own focused reproduction within the existing reporting owner.

Validator-only recovery is permitted after an already finalized daily checkpoint,
before the weekly-view step. `project_week_browser.py --resume-after <meeting-date>`
must re-read every retained publication through the public report service, verify
its canonical context/original bytes and same source/summary identities, and then
continue only later dates in a new evidence directory. It must not edit or finalize
the retained days again. Source comparison may exclude only the named browser
driver/assertion/recovery modules and their direct validator tests; all application,
shared fixture, SDK/Base, vendor and capture files must match the original run.
Record the exact validator changes and prior evidence path. Reject an unfinished
checkpoint, a changed runtime, a different commit or a later persisted day outside
the requested recovery boundary. Existing failure/progress/stop files stay unchanged.
This reuses the launcher/store and is not a new product task engine.
Public readback also returns `publication.checkout_state`, a current/stale view of
the moving Git working tree. Record it but do not compare it as immutable history;
the publication manifest/hash/commit, all six original file hashes, draft revision
and canonical context must still match exactly. Any unknown checkout value fails.
An explicit `--resume-evidence` name can select an earlier owned resume directory;
it cannot reference a path outside this run. Original per-day response evidence
must be unique across that directory and the first `week` directory.

The retained Thursday run revealed a scenario setup error: ALPHA-102's unchanged
current slot was already empty, so filling it with `''` was a no-op, not a saved
deletion. The approved continuity policy creates no note for an untouched unchanged
slot. Recovery records that exact case as `untouched_empty_ids`, requiring an
unchanged source observation and no submitted edit for that note. This does not
qualify explicit deletion. The pending-draft branch must additionally type and Save
real content for ALPHA-102, then clear, Save/reopen and verify an explicit empty
note remains unchanged after the gap. Fresh full-week execution first saves text
in Thursday's clear target before clearing it. Do not relabel the older no-op as
a passing clear action or alter its finalized publication.

The pre-week toolbar counterexample reproduced double command dispatch: a newly
created persistent editor and the last regular note both received the same color.
The bounded fix owns `report_editor/{index,report_continuity}.js` and
`ui_web/tests/test_report_continuity_toolbar_browser.py`; one controller dispatches
to the last focused editor. Storage/provenance and all other editing behavior stay
unchanged, with focused browser/Node and affected AI/export lifecycle consumers.

The first week attempt (`eb203842-ac01-4e00-ad40-7161c033fefe`) stopped at Monday
finalization with `REPORT_REVISION_CONFLICT`; both services stopped normally before
the user-reported PC restart. Its three accepted summaries, revision-2 human edits
and failed HTTP response remain retained. A read-only check established that the
active slot and draft refer to the same preparation, but the publication guard
compared the draft's content hash with the full stored-intent hash.

The corrective boundary owns `app/domain/report_preparation_validation.py`,
`services/report_preparation_worker.py`, `services/report_publication_preparation_guard.py`
and `tests/test_report_preparation_publication_guard.py` under `project_management/`.
Use one pure hash-selection helper for seed creation and finalization:
`preparation_binding_hash(validated_intent) -> str`. Schema-1 saved capture uses the
full intent hash; refresh and replacement intents use their validated
`preparation_intent_hash` or `reprepare_intent_hash`. The active slot still binds
the complete intent bytes separately. This changes no persisted schema or old hash.
Regression tests must publish edited/reopened initial refresh, saved replacement
and refreshed replacement drafts, while refusing superseded parents without
publication or a finalization intent. Retain the existing missing/downgraded-binding
and stale-revision tests. No Base, provider or UI version guard is relaxed.
Only after this lower-layer proof and bounded review may a new frozen-candidate week
start. The failed run remains a failed run, not a successful day in the new result.

Before the long run, tests must reject unknown scenario/vector/member, mismatched
query and wrong binding, preserve default single-vector compatibility, and verify
row data/source hashes remain identical across fixture creation. Check command
assembly uses selected settings/SDK and retains owned process identity/cleanup.
Use existing selected SDK/no-dotenv gates; no global test discovery.

Review fixture/source eligibility, final evidence and next remaining W6/W7 gates
with one bounded independent reviewer. Only complete main-week and required branch
evidence can close JOIN; screenshot-only or pre-seeded-summary runs cannot.

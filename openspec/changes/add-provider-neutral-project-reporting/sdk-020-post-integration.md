# Execution After IP-SDK020-READY

Date: 2026-11-05. Status: authorized after the user's explicit release of the reached IP.
Necessary small counterpart fixes are allowed; immutable releases and historical evidence remain
unchanged. Execution state stays in [tasks.md](tasks.md).
This appendix consumes [SDK 0.2 integration contract](sdk-020-integration.md), the existing
[authoring contracts](report-authoring-contracts.md), [continuity](report-continuity.md) and
[validation matrix](report-authoring-validation.md). It does not replace those authoritative values.

## 1. Sequence And Replan Boundaries

```text
Base SDK release + SDK020.ARTIFACT + SDK020.APP + SDK020.PRE
 -> SDK020.REPLAN -> IP-SDK020-READY [STOP HERE]
 -> explicit release of stop -> SDK020.JOIN
 -> SDK020.JOIN.R / REPLAN
 -> W6.AUTHOR.DAILY closure
 -> W6.AUTHOR.DAILY.REPLAN
 -> W6.AUTHOR.ASSIST service/profile/save + UI
 -> W6.AUTHOR.ASSIST.REPLAN
 -> W6.AUTHOR.JOIN full week / exports
 -> W6.AUTHOR.R -> W6.AUTHOR.REPLAN -> remaining W6/W7
```

Pure manual DAILY work has no inherent SDK dependency; its independent existing evidence remains
valid unless affected. This selected resumed sequence deliberately reaches the SDK stop first.
Changing a shared dependency invalidates only affected evidence, not every historical green test.
Replan nodes classify the next packet as continue/amend/supersede/retire and record reason, changed
artifacts, affected checks and preflight result; they do not silently cancel required scenarios.

## 2. SDK020.JOIN: First Actual HTTP Consumer

Owner: Dashboard joined driver and app code; necessary small SDK/service fixes may be implemented
in Base under the user's integration authorization and recorded separately for its owner.
Entry: READY receipt is valid, user releases the stop, final SDK bytes still match, source/fixture
and process ownership are declared, and no unqualified live configuration is used.

Reuse the owned source-isolated approach in `scripts/validation/project_full_stack.py`,
the corresponding Base fixture and `project_management/tests/test_project_full_stack_lifecycle.py`.
The already retained `.tmp/task-run-w5-clean-merged-20261103/base-source/` is a candidate source
dependency to verify, not a running server or permission to reuse an old store.
The first joined action is to prepare a new versioned fixture manifest for SDK 0.2 and validate
the existing driver's package expectations; do not edit old manifests or bypass their guards.
This first JOIN edit includes `scripts/validation/project_summary_support.py` and the artifact/
SDK expectations in `project_full_stack.py`; they still encode the old SDK choice today.
The handoff is ready for that integration development, not a claim that the old joined command
already runs unchanged against SDK0.2. Publish a new fixture selection, never retag an old run.

The new fixture root is `.tmp/sdk-020-join-20261105/`. Its `sdk-selection.json` fixes the
SDK version/wheel digest and unchanged pack digest. The driver accepts only the published
selection; legacy roots retain their original SDK identity for historical inspection/cleanup.
The joined interpreter is `app-venv/Scripts/python.exe` under this root, with the delivered
wheel installed locally and a `.pth` entry for the existing Dashboard host dependencies.
This dependency-sharing path and actual versions are recorded in the environment receipt;
the local SDK must precede the shared legacy package in both module and metadata resolution.
Every app/worker/CLI child uses the manifest's same interpreter. No main-venv upgrade or
mutation of a running service is part of this integration.

### Fixture And Construction Contract

- New owned run directory, temporary app catalog/archive and Base RunStore, not production DBs.
- Registered synthetic application identity and opaque scope match the actual created
  project/stage. Credentials are generated only inside the protected fixture, never Git.
- Source transport returns a complete synthetic ticket with comments 201/202/203 and literal
  source status. App capture and `build_initial_input` create actual source/input hashes.
- Base fixture receives the real app-produced input. Do not overwrite binding IDs/hashes to fit
  the default published golden input. Existing factory accepts explicit profiles/grants/backend;
  this is a fixture assembly boundary, not a new public API.
- Choose the unchanged `project-reporting.summary@review-1` from the trusted a2 pack.
  Synthetic executor output must reference the actual input's evidence/binding.
- Use the installed 0.2.0a1 SDK over real loopback HTTP; no MockTransport in this joined proof.
  Set `METRICS_PROJECT_CAPTURE_PAGE_SIZE=2` for the strict existing synthetic Jira fixture.

Production application interfaces:

```text
CaptureArchiveService.prepare / append_page / append_snapshot / finalize
SummaryAnalysisService.prepare -> AnalysisPreparation
SummaryAnalysisService.advance -> AnalysisStep(accepted or safe non-success)
SummaryJournal.accept_analysis -> AcceptedSummary
ReportDraftService.create or create_authored -> saved draft
```

Preserve original argument contracts in source/authoring specs. Public SDK HTTP routes remain
POST `/api/runs`, GET `/api/runs/by-client-key`, GET `/api/runs/{id}/result`,
GET `/api/runs/{id}` and POST `/api/runs/{id}/cancel`; scope/store/app checks apply on every call.

### Joined Cases And Exit

| Case | Action | Required observation |
| --- | --- | --- |
| J020-01 first input | capture -> prepare -> one submit -> result -> app acceptance | exact request/result/input/profile refs, one synthetic dispatch and one accepted summary |
| J020-02 lost response | drop first submit response, retain state, resume consumer | original key/store/deadline; no second POST/dispatch; one acceptance |
| J020-03 wrong result | inject wrong identity/hash/evidence in a separate case | no acceptance/publication; preserve failure evidence |
| J020-04 unchanged source | explicit second capture with identical semantic source | no new analysis attempt or Base dispatch; accepted bytes unchanged |
| J020-05 cancel | cancel intent before acceptance, include late completion | no late business acceptance; remote-stop/usage uncertainty remains explicit |
| J020-06 normal stop/reopen | close owned services, reopen same owned case state | original store/ref preserved; no unintended new work; normal owned cleanup |

Run direct/affected tests first, then one bounded joined candidate. Preserve original failures;
do not re-run the whole week to diagnose an SDK envelope failure. Record API/SDK/fixture hashes,
app and Base IDs, side-effect counts, result bytes, acceptance state and normal stop receipt.
An old a2 joined report or Base's 599-test baseline is not a new 0.2 joined qualification.
Exit only on these selected semantics and cleanup, then SDK020.JOIN.R/REPLAN.

The 2026-11-05 selected candidate passed these cases; see
[the delivery receipt](sdk-020-join-delivery.json). Its driver is
`scripts/validation/project_sdk_join.py run --run-dir <owned-run-dir>`, followed by
the existing launcher `stop`, `start`, the driver `reopen`, and final `stop`.
Use the joined venv interpreter for every command. Faults occur after actual HTTP
responses; only their focused unit tests use MockTransport. The evidence-only
wrong-evidence variant keeps transport hashes consistent to reach the application's
semantic evidence validator. A canceled business result does not prove remote work
was stopped: this candidate explicitly recorded `remote_stop=not_requested`.
The driver is an application qualification helper, not a new SDK TestKit or journal.

## 3. DAILY Closure With The Selected SDK

Owner paths remain the existing DAILY service/store/worker, CLI, forms, routes and tests in tasks.
Do not redo closed journal/preservation reviews unless the migrated dependency affects them.

Exact public boundaries:

```text
ReportContinuityService.preview(actor, project_id, stage_id, *,
    series_id, meeting_date, template_selection) -> BaselinePreview
ReportPreparationService.prepare(actor, project_id, stage_id, *,
    command_id, series_id, meeting_date, expected_series_policy_hash,
    expected_baseline_ref, template_selection, source_mode, capture_id,
    analysis_mode, acknowledge_gap_draft_ids) -> PreparationResult
ReportPreparationService.get(actor, project_id, stage_id, preparation_id)
ReportPreparationService.for_meeting(actor, project_id, stage_id, *, series_id, meeting_date)
ReportPreparationService.reprepare(actor, project_id, stage_id, *,
    command_id, preparation_id, expected_operation_revision, expected_draft_revision,
    expected_draft_revision_hash, expected_baseline_ref, template_selection,
    source_mode, capture_id, analysis_mode) -> PreparationResult
```

`source_mode` is saved_capture or refresh; `analysis_mode` is manual_only or changed_items.
PreparationResult includes preparation/operation/draft/publication identity, effective_selection,
selection_conflicts and typed preservation review issues. The precise mapping is defined in continuity.
POST prepares/reprepares; GET preview/detail/period reads never creates work.

Next exact consumer proof: create Monday through the visible manual path; edit/color/link and
Finalize; create Tuesday, not merely preview it; edit an inherited persistent reference without
new unapproved lookup; Save/reopen/Finalize with Monday's fragment/hash unchanged.
Also verify pending Monday drafts, explicit gap acknowledgement, same-day replay and stale CAS.

Use existing `ui_web/tests/test_report_daily_ui_browser.py`, `test_report_daily_http_contracts.py`
and the corresponding preparation/preservation tests. Extend a narrow missing case rather than
re-running every old module. Cross-day frontend steps use mounted Milkdown, not a textarea fixture.
Exit: reachable manual/changed-items paths, preservation and refusals mapped to current evidence.
DAILY.REPLAN fixes the ASSIST entry snapshot and any affected proof before new implementation.

Current source preflight: the implemented UI owner is `ui_web/views/report_daily.py`
with `ui_web/facades/report_daily.py`, not the early placeholder `report_preparations.py`.
The existing `TestReportDailyUiBrowser.test_shouldPrepareManualDailyEditPaintReopenFinalizeAndPreviewNextDay`
stops at next-day preview. The next narrow test must create Tuesday, edit an inherited
persistent reference through the mounted editor, Save/reopen/Finalize and compare Monday's
unchanged fragment/hash. This is missing consumer evidence, not a reason to rerun all closed
CONTENT/EDIT/REFERENCES/TEMPLATES/HISTORY tests or to claim DAILY is already complete.

## 4. ASSIST: Profile, Candidate, Apply And Save

The delivered a2 pack does not contain `project-reporting.authoring@1`.
This is a concrete prerequisite, not permission to use summary@review-1 for authoring.
Dashboard owns its prompt/input/output schema and fixed app bundle; Base's existing synthetic
fixture factory can register this profile and matching grant without Base source edits.
Joint qualification must verify the exact profile definition/output-schema digest and capability.
Production registration/real execution remains separate. Missing qualification yields
`REPORT_AI_UNAVAILABLE` while manual editing continues.

Owner files to create/update are the ASSIST paths already named in tasks:
`project_management/services/report_assists.py`, `storage/report_assists.py`,
`out/report_ai_task.py`, `app/domain/report_assists.py`, its public API,
`ai_bundle/report-authoring/`, `ui_web/views/report_assists.py` and
`ui_web/static/js/report_editor/assist.js`.
Existing standard/continuity save, attribution, serialization and publication consumers must
be included together; a slot-only implementation cannot qualify current-day notes.

```text
submit(actor, project_id, stage_id, draft_id, *, command_id,
       expected_revision, expected_revision_hash, target_ids, instruction) -> AssistStatus
observe(actor, project_id, stage_id, draft_id, assist_id) -> AssistStatus
cancel(actor, project_id, stage_id, draft_id, assist_id, *, command_id) -> AssistStatus
candidate(actor, project_id, stage_id, draft_id, assist_id) -> AssistCandidate
```

### Immutable Input And Output

Input binds owner/project/stage/draft/revision/hash, pinned source/template/fill policy hashes,
target IDs/current fragment hashes, bounded evidence allowlists, profile/output schema hashes
and original backend/grant identity. Caller cannot select credentials, endpoint or arbitrary profile.
Only current narrative targets and ai_optional template slots are editable.
Source facts/status/date, history, row order, AR tracking and hidden state are forbidden targets.

```json
{
  "schema_version": 1,
  "targets": [
    {
      "target_id": "a-server-selected-target",
      "status": "filled",
      "fragment": {"schema_version": 2, "blocks": []},
      "evidence_refs": [],
      "reason_code": null
    }
  ]
}
```

This illustrates the envelope only; actual filled fragments and evidence must satisfy the
authoring schemas and requested target allowlist. `insufficient_evidence` requires no filled
fragment and an explicit reason. These are filling statuses, never ticket statuses.
Input128KiB/output64KiB/180-second total/16 observations are app maxima; use stricter Base limits.
No output repair/retry is implicit. Raw results are retained unchanged.

### State And Transaction

Persist exact request/command and one-active-assist claim in the existing stage runtime before I/O.
`prepared -> submitted/unknown -> observing -> candidate_ready/insufficient_evidence/failed`;
cancel_requested/canceled remain distinct. Reads query the original key; they never submit.
No stage lock is held during SDK I/O. On resume keep the original key/store/profile/deadline.
Cancel/result races cannot revive a canceled candidate or advance source/summary/publication state.

Apply uses `EditorHandle.replaceFragment(expectedLocalVersion, fragment)` on the captured
editor epoch/target; color-only edits also invalidate a stale candidate. One native undo transaction.
Apply marks dirty, Reject leaves text unchanged, and only Save persists human acceptance.
Save verifies the server-owned assist receipt under the already-held archive lock.

Required consumers: both `report_authoring.py` and `report_continuity_edits.py` request validators;
`report_authoring_drafts.py` standard/continuity branches; `attributed_authored_edits` and
continuity attribution; note provenance in the effective authoring context; `report_editor/index.js`
receipt serialization; draft/publication readers. No nested re-acquisition of the same stage lock.

Required negatives: foreign/stale/history target before I/O; duplicate command conflict;
wrong profile/store/input/output/evidence; unknown submit original-key recovery; cancel/late result;
Apply after user text/color change; manual Save while AI unavailable; preserved provenance on
later human edits, next day and publication without reapplying the candidate.

HTTP: existing actor/owner/CSRF and strict JSON checks; POST assists, GET status/candidate,
POST cancel. Use the authoring envelope/status codes, including 409 conflict, 503 unavailable,
502 invalid upstream and safe English errors with static bilingual UI.
Service/profile/save tests precede mounted UI tests; real local Base HTTP profile registration
is a separate joined proof. ASSIST.REPLAN binds that evidence before the full-week node.

## 5. Full Week And Export Qualification

Use [authoring validation section 7](report-authoring-validation.md#7-full-week-user-qualification)
without changing its accepted scenario. New synthetic project/stage/series, three separate ticket
rows, ISO calendar/Asia-Shanghai, 2026-10-26..30 plus 2026-11-02 rollover. Do not change system time.

| Day | Required action/difference | Preservation check |
| --- | --- | --- |
| Monday | Generate, edit/delete AI prose, add red note/link and open AR, Save/reopen/Finalize | Save does not advance editorial head; Git-confirmed Finalize does |
| Tuesday | Same ticket facts; add blue note and green persistent note | Monday note IDs/body hashes/paint unchanged; deleted AI prose absent |
| Wednesday | Normal app restart; highlight/bold, actual #ID third option, undo/redo | No extra AI run from restart; native edit history and scoped reference correct |
| Thursday | Delete/clear current text, color-only Save, stale second-window Save | Refusal preserves local input/latest revision; no empty-value fallback to old AI |
| Friday | Fifth note, resolve one AR, leave another, generate weekly_view/download | Five-day ordered notes, one ticket per stable row; weekly_view does not advance daily head |
| Next Monday | Prepare new week and add note | Latest confirmed per-ticket update retains original date/status/paint; unresolved AR/persistent notes carry; old week unchanged |

Every day prepares twice without duplicate work, Saves and reopens at least once, and explicitly
Finalizes. The initial synthetic AI dispatch is counted; unchanged days create no new AI analysis.
Source status appears after `wwxx.x` exactly as captured, never inferred by AI.

The same candidate must prove HTML/JSON formatting, safe clipboard payload, original finalized
download bytes and declared plain/Markdown/Excel limitations. Do not silently drop color and call
all export formats lossless. Clipboard transport and actual Outlook paste remain different gates.
The six publication files remain the existing snapshot/template/edits/HTML/TXT/manifest contract.

Preserve per-day screenshots of the actual edited note, canonical fragment/hash comparisons,
publication refs/Git commits, run/dispatch counts, failures and normal cleanup.
Do not replace UI operations by writing final JSON contexts directly.

## 6. Final Closure And Non-Goals

W6.AUTHOR.R reviews the final exact candidate, changed consumers and evidence union.
W6.AUTHOR.REPLAN explicitly classifies remaining W6/W7/exports/live qualifications; nothing
unimplemented disappears because the editor or SDK subset passed.
Update current guides and make bounded commits without unrelated WIP or enterprise data.

Formal scheduling, provider/model credentials and real calls, service deployment/migration,
Outlook and wider browser/mobile matrices retain their independent authorization/qualification.
An SDK-only package, fake profile, package import or OpenSpec validation cannot close them.

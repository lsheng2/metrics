# AI Authoring Execution Packet

Date: 2026-11-06. Implementation and qualification state is recorded in `tasks.md`.
Parent contracts: `report-authoring-contracts.md` section 4 and
`sdk-020-post-integration.md` section 4. State stays in `tasks.md`.
Depends on qualified DELTA.CORE and `W6.AUTHOR.SOURCE`.
One writer and one bounded independent plan/behavior reviewer.

## Business Boundary

Explicit AI action proposes content for a current editable target. It does not
refresh tickets, change source status/date/row order/AR tracking, accept a summary,
save a draft or publish. Apply is one local undoable edit. Save is the user's
acceptance under the existing draft revision/hash CAS.

The first mounted path is a current daily note; standard notes/narrative fields,
existing persistent notes/AR body and `ai_optional` template slots use the same
contract. Historical notes, fixed template blocks and manual-only slots refuse.
Only saved target content is sent; unsaved changes must be saved before AI submit.
Manual editing stays available when the authoring profile is not qualified.

## Domain And Profile

`app/domain/report_assists.py` owns immutable DTOs, target resolution, bounded input
and output validation. Target IDs are `canonical_hash(target_mapping)` and are
derived by the server from its draft, never authorization supplied by the browser.

Input binds schema version, project/stage/actor/draft ID/revision/hash, snapshot
hash, pinned template/fill-policy hashes, requested target IDs/mappings/current
fragment hashes and fill instructions. Source evidence is namespaced by issue
source-key hash; human notes are labeled context, not converted into provider facts.
128KiB input / 64KiB output / 180 seconds / 16 observations remain maxima.

`ai_bundle/report-authoring/profile.json` defines
`project-reporting.authoring@1`, local input/output schemas and prompt.
`out/report_ai_task.py` verifies a pinned profile manifest and reuses installed SDK
and the existing wire-envelope validators. Summary result validation remains unchanged.
Extract a neutral result-envelope method only as needed to avoid duplicating it;
the summary and authoring semantic validators remain separate.

Output is the already specified `{schema_version:1,targets:[...]}`. Exact requested
target set, no duplicates/unknown fields, valid canonical fragment v2, explicit
evidence allowlist and grounded quotes are mandatory. `insufficient_evidence` has
no filled fragment. AI cannot create reference receipts/IDs or arbitrary URLs;
link destinations must come from the frozen source/context allowlist.
Generated narrative is English; proper names and quoted source may retain original text.

## Persistence And SDK Calls

`storage/report_assists.py` uses existing controlled paths/quota and stage lock:

```text
runtime/report-assists/<assist_id>/intent.json
runtime/report-assists/<assist_id>/dispatch.json
runtime/report-assists/<assist_id>/exchange-<00..15>.json
runtime/report-assists/<assist_id>/observation-<00..15>.json
runtime/report-assists/<assist_id>/candidate.json
runtime/report-assists/<assist_id>/cancel.json
runtime/report-assists/<draft_id>/active.json
```

Intent is immutable and written before dispatch claim. It includes original command
hash, request/clientRunKey, deadline, source/profile/backend/grant identity. One active
assist per draft. The existing stage lock protects state only; SDK I/O happens outside.
No new supervisor, queue or SDK persistence layer.
Each file has a versioned payload/hash envelope. Exchange slots are claimed under
the stage lock before SDK I/O, including uncertain outcomes; one completed exchange
adds at most one observation. Existing observations also count against the bound.
Exhaustion returns `REPORT_AI_LIMIT` without another SDK call. A canceled or failed
outcome is not inferred from a network timeout.

Summary and authoring reuse `app/domain/task_run_observations.py` for execution
settlement after validating identity. Terminal timestamp, no unresolved exposure,
and confirmed remote stop or definite dispatch knowledge are required.
Definite submit rejection (400/413/422 with `correct_request`) settles without
business acceptance. Invalid results/stale drafts after verified settlement fail;
wrong-store/unverified snapshots stay unknown. `cancel_requested` remains observable
by its original key. Cancellation blocks Apply/Save immediately, even if remote
settlement is still unknown.

`services/report_assists.py`:

```text
submit(actor, project_id, stage_id, draft_id, *, command_id,
       expected_revision, expected_revision_hash, target_ids, instruction) -> AssistStatus
observe(actor, project_id, stage_id, draft_id, assist_id) -> AssistStatus
candidate(actor, project_id, stage_id, draft_id, assist_id) -> AssistCandidate
cancel(actor, project_id, stage_id, draft_id, assist_id, *, command_id) -> AssistStatus
```

Submit alone can claim/send POST; repeated command uses the original stored intent.
Observe always uses GET by original key, then GET result for a verified success.
Store raw snapshot/result unchanged with their hashes; recheck draft ownership,
revision and cancellation before candidate publication. Failed/unknown outcomes do
not advance a business baseline or manufacture retry budget. Cancel is recorded
before remote I/O, blocks candidate use immediately, and preserves unresolved remote
exposure until verified. Closing a browser is not a cancellation.

Default factory is unavailable. An explicitly configured server-side adapter factory
must provide the qualified authoring profile/backend/client boundary. Do not infer
authoring permission from an existing summary grant; caller cannot provide endpoint,
token or profile. Local synthetic qualification registers the distinct profile using
the existing Base factory. Production registration remains separately authorized.
`build_report_service` injects a lazy receipt verifier. Missing authoring files,
registration or qualification cannot prevent manual report creation/editing.
Only an explicit assist or non-null receipt loads the authoring contract.

## Save And Provenance

Request parsers accept nullable UUID `assist_receipt_id`; acceptance is in the service,
not the shape parser. `ReportAuthoringDraftMixin.save_authored` calls an injected
receipt verifier using the already-held repository, before either standard or
continuity edit application. No nested stage-lock acquisition.

Verify stored candidate identity, exact frozen draft/revision/snapshot/target and
canonical fragment equality; reject stale/canceled/forged/foreign receipt. Return
server-owned source result reference for each accepted edit, including assist/run/
profile/input/output/target hashes. Both attribution paths mark initial acceptance
`ai_assisted`; later human edits mark human but retain source result provenance.
Daily effective note context carries it through next-day inheritance and publication.
No client-supplied origin, author or AI-result reference is trusted.

## HTTP And Editor

Add the four already specified routes under the draft's `assists/` path. Reuse
ProjectAccessMixin, owner checks, CSRF, strict JSON parsing and private/no-store errors.
409 is stale/busy/canceled, 422 invalid candidate/target, 503 unavailable. GET never
dispatches; requests have bounded body size and validated command/revision.

`ui_web/static/js/report_editor/assist.js` handles submit, bounded status observation,
candidate preview, Apply/Reject/Cancel. It receives the active editor state via the
existing controller; no parallel editor document. Capture editor epoch/local version
before request; text/paint/selection change or editor destruction prevents stale Apply.
Apply uses `EditorHandle.replaceFragment(expectedLocalVersion, fragment)`, stores
assist ID for Save, and marks dirty. A later local edit clears the unaccepted receipt.
AI unavailable and server errors leave original content intact. The mounted browser
test must observe the actual Save receipt/provenance, not only popup visibility.

The button uses the existing active editor, with a nonmodal floating panel, shared
Bulma action/field classes and locally bundled Iconoir icons. No shared CSS tokens,
new editor, source mode, or external UI service is introduced. The panel respects
the viewport and fixed status bar, preserves focus/selection, and exposes translated
loading, unavailable, stale, insufficient, canceled, unknown and limit states.
Candidate/default text contrast and actual action hit targets are measured at
1440px and 390px. Reopening a stored candidate cannot overwrite edits that were
already dirty when the panel opened.

Applying identical text still makes AI acceptance dirty because the receipt is new.
After Save acknowledges acceptance, local pending receipt IDs are retired. The Save
response adds `current_note_hashes:{note_id:body_hash}` for current daily notes, so a
second Save can use the accepted CAS baseline without losing newer local text.
Saving/uncertain-save states disable AI Apply. Refreshing the page can retrieve the
stored candidate with GET; it does not require another generation.

## Concrete HTTP Shapes

Public Python entry: `project_management.app.api.reports.ReportAssistService`;
construction: `project_management.app.api.report_factories.build_report_assist_service`.
All paths below share the owner-checked project/stage/draft prefix.

```text
GET assists/
  -> {schema_version:1,result:{available,targets:[{target_id,target}],latest:AssistStatus|null},error:null}
POST assists/
  {command_id,expected_revision,expected_revision_hash,target_ids:[sha256],instruction}
  -> {schema_version:1,result:AssistStatus,error:null}
GET assists/<assist_id>/
  -> {schema_version:1,result:AssistStatus,error:null}
GET assists/<assist_id>/candidate/
  -> {schema_version:1,result:{schema_version:1,targets:[...]},error:null}
POST assists/<assist_id>/cancel/
  {command_id}
  -> {schema_version:1,result:AssistStatus,error:null}
```

`AssistStatus={assist_id,state,candidate:null,error_code:null|string}`.
POST returns 202 for prepared/observing/unknown, otherwise 200; successful observation
returns 200 even when its business state is failed or unknown. Error responses are
`{schema_version:1,result:null,error:{code,message}}`. No stack, credentials or paths
are returned. 401 is missing actor, 403 is CSRF middleware, 404 is foreign/missing
resource, 409 is stale/busy/canceled/finalized, 422 is invalid input/candidate, and
503 is an unavailable authoring dependency/storage. Errors preserve the original
draft. `error_code` on an observed status is diagnostic, not permission to resubmit.
JSON request bodies are limited to 16KiB, instructions to 4000 UTF-8 bytes, targets
to 8; unknown/duplicate keys and caller-provided endpoint/profile are rejected.

## Validation And Closure

| Layer | Required cases |
| --- | --- |
| L0 | allowed/current vs history/manual slot; evidence/unsafe href/unknown target; exact candidate and source hashes; provenance retained after human edits |
| L1 | durable submit/key replay, stale revision before I/O, unknown submit only GET, one active claim, cancel/late result, standard+daily Save receipt verification |
| L2 | auth/CSRF/foreign owner/strict body/HTTP error mapping, default unavailable manual path |
| L3 | mounted current note submit/preview/Apply/undo/Save/reopen; reject stale after text or paint; default unavailable state |
| L4 | actual SDK + distinct registered Base profile on loopback; candidate receipt survives Save and publication; no real model/provider |

Use existing no-dotenv runner and selected SDK interpreter. New tests live in
`project_management/tests/test_report_assist*.py` and `ui_web/tests/test_report_assist*.py`.
Run pure/service counterexamples before browser; one representative joined target
before expanding target variants. Preserve failed responses, no timed native sampler.
Review source/evidence/next-gate together. After ASSIST.REPLAN proceed to representative
exports, then the original three-ticket full-week/cross-week acceptance.

Additional counterexamples bind this packet to actual nodes:

- `test_report_assist_recovery.py`: missing profile/manual Save, verified failure vs
  unknown identity, canceled-late-result settlement, pre-I/O bound, last admitted
  result, and malformed stored pointer.
- `test_report_assist_browser.py`: mounted daily Save provenance, text/paint staleness,
  undo/human paint, Chinese unavailable/manual Save, identical-text acceptance,
  delayed Save followed by newer edits, stored candidate reopening, desktop/mobile.
- `test_report_assist_http.py`: installed SDK and distinct registered Base profile,
  real data-Git publication, subsequent human provenance/paint and next-day inheritance.

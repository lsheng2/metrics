# HTML Report Authoring

Status: user-approved direction on 2026-11-02; detailed design for implementation.
Owner: Dashboard `project_management`; no AI Base API change.
Docs impact: architecture, API, user workflow and validation.
Current behavior: [project-reporting guide](../../docs/current-baseline/project-reporting.md).
Execution state belongs only to [tasks](tasks.md); acceptance cases are in
[HTML report validation](html-report-validation.md).

## 1. Decision And Scope

2026-11-03 amendment: [Report Authoring V2](report-authoring-v2.md) supersedes
only the built-in-only/template-designer-backlog and separate-editor-Agent assumptions.
It adds WYSIWYG-only content, hash-ID completion, user template versions and explicit AI fill
as proposed contracts. HTML-first, source provenance and exact finalization remain.
The schema1 implementation below is not proof that Authoring V2 is implemented.

The user approved reusable daily/weekly report templates and requested HTML as
the primary report, formatted copy into email, manual edits/notes and an explicit
choice to commit the finished report to Git.

Use one verified report data model, versioned built-in templates and an editable
application draft. Copy/export renders a static, self-contained HTML document.
The application editor is not embedded in the exported email.

Alternatives not selected:

- Arbitrary uploaded HTML or unrestricted contenteditable as the source of truth
  loses structured provenance and permits active content. Not first-release scope.
- Generating each format with an LLM spends tokens and can change facts. Rendering,
  comparison and manual edits must not invoke an LLM.
- A general pixel-layout designer remains outside scope. The first implementation
  used built-in templates; the later user requirement adds a constrained visual
  block/slot template library through Authoring V2.

HTML becomes the default format. Existing required Markdown/Excel work remains;
HTML delivery must not silently retire it. Management-review templates, offline
HTML editing/reimport and unrestricted layout design remain backlog.
User-authored block/slot templates are explicitly planned in W6.AUTHOR.TEMPLATES.
Do not implement email sending, email-account integration, remote Git setup or
automatic push in this change.

## 2. User Workflow

1. Select an owned project/stage and a retained capture or published report.
2. Generate a draft using `daily-standup/1` or `weekly-timeline/1`.
3. Review the source cutoff, pending coverage and difference baseline.
4. Edit report narrative or add meeting notes in the HTML application page; save.
5. Preview, copy the formatted body or download an `.html` file.
6. Optionally choose **Finalize and commit**. This commits the exact selected
   draft revision to the existing independent stage data Git repository.

Saving, previewing, copying and downloading a draft do not commit a final report
or advance a meeting/publication checkpoint. They also do not prove an email was
sent. An uncommitted export identifies itself as a draft in its metadata.
Previously captured raw material and accepted summaries continue their existing
automatic archival protocol; this new manual gate applies only to report
finalization, not to preservation of source evidence.

Finalized editions are immutable. A correction starts a new draft linked by
`parent_publication_id`; finalizing it adds another edition without modifying the
original. Users can inspect the original, edits and final content separately.
No new writes are allowed for archived projects. Existing authorized artifacts
remain readable; this is not an exception allowing archive mutation.

## 3. Templates And Daily Semantics

| Template | Required content | Configurable presentation |
| --- | --- | --- |
| `daily-standup/1` | Key messages, changes since baseline, complete open/action register, pending/coverage and cutoff | Section order; grouping by owner/status; stable priority/key order; selected optional columns |
| `weekly-timeline/1` | Same issue identities aligned across dated columns, current next action/owner, missing-day and coverage states | One to seven explicit local dates; ascending dates; no fabricated days or silent truncation |
| `management-review/1` | Future projection of accepted risks/actions | Disabled until its own acceptance; new inference requires a separate analysis policy |

The first implementation uses developer-owned Django templates with autoescaping
and inline styles. Template options are allowlisted JSON, not executable code,
caller paths, raw CSS, prompts or uploaded templates. Core scope/coverage metadata,
pending rows and unresolved actions cannot be hidden by a standup template.
Template identity contains ID, version, package content hash and renderer version.
Changing presentation does not change the Stage rule, AI profile or model input.
This is the built-in schema1 implementation. V2 user templates are validated application
documents, not arbitrary replacements for Django source. Structure and fill-policy hashes
are separate; only an explicit AI operation consumes the filling instructions.

Maintain distinct authorities:

- Analysis baseline: last successfully accepted summary for each source chain.
- Meeting baseline: the exact prior finalized `purpose=standup` publication,
  recorded by ID and immutable per-item source/summary references.
- Day column: an explicit publication ID selected for a local date. Default to
  the latest finalized standup edition for that date; keep older editions
  selectable. A later generation time never changes the source cutoff.

The report date is the capture `finalized_at` converted to the selected IANA
timezone. Record that timezone and the original UTC value. Keep draft creation,
human edit and finalization times separate. Weekly columns use those report
dates. No ISO/company workweek inference from labels; custom calendars are a
separate presentation option when configured.

Compare source identities and retained events, not Markdown, HTML or edited
narratives. First observation is not necessarily a newly created ticket;
scope entry/exit is separate from creation/closure. A Closed/Fixed status does
not complete an outstanding action. Access loss, missing membership, missing
capture and pending analysis are not "no change".

Keep captured intermediate transitions, including Closed -> Reopened between
meetings and A -> B -> A content. Event occurrence time comes from retained
provider evidence; when unavailable show observation time and unknown occurrence
time. Do not assign an event to yesterday merely because it was first read today.
Classification uses an explicit versioned status/comparison policy, never global
hardcoded Jira or HSD status names. Policy mismatch makes comparison unavailable.

A partial report with complete membership includes every pending item and
original summary age. It may become the latest displayed standup edition, but
not `latest_complete`. Its receipt pins per-item versions so an unfinished item
does not lose its outstanding comparison/analysis baseline. Incomplete membership
cannot produce an apparently complete register or a new standup checkpoint.
Without a committed baseline the comparison says `initial_baseline`, not "today
all tickets are new". A copied but uncommitted draft is not a new default baseline.

## 4. Data Contracts

New contracts are pure frozen slots DTOs in
`project_management/app/domain/report_contracts.py`, exported through
`project_management/app/api/reports.py`. Canonical JSON uses existing
`capture_values.canonical_bytes`; UTF-8, sorted keys, finite numbers and preserved
Unicode. Hashes are lower-case SHA-256; IDs are UUID strings unless stated.

| Value | Required fields and validation |
| --- | --- |
| `ReportSelection` | `capture_id`, `baseline_publication_id: str \| None`, `parent_publication_id: str \| None`, `purpose: standup \| historical_export`, `timezone`; all selected records must belong to the same owner/project/stage |
| `ReportSourceSnapshot` | `schema_version=1`, `project_id`, `stage_id`, `owner_subject`, `rule_hash`, `source_commit`, `capture_id`, `source_as_of`, `report_date`, `timezone`, `baseline_publication_id`, `comparison_policy_hash`, `coverage`, `key_messages`, `rows`, `events`, `days`; computed only by the trusted source reader |
| `ReportRow` | `source_key: SourceChainKey`, `identity: WorkItemIdentity`, literal `title/status/assignee`, `source_hash`, `source_url \| None`, `coverage`, `summary_ref \| None`, `what/current_position/verification`, `next_actions`, `blocker_refs`, `limitation_refs`, `evidence`, `summary_as_of \| None`, `pending_reason \| None` |
| `SummaryReference` | `summary_id`, `revision`, `target_capture_id`, `source_hash`, `input_hash`, `result_hash`, `owning_commit`; original candidate and result hashes are preserved |
| `ReportMessage` | `message_id`, `text`, `source_refs`; default text is drawn from accepted content or deterministic factual counts, never newly inferred |
| `ReportEvent` | `event_id`, `source_key`, `kind`, `before`, `after`, `occurred_at \| None`, `observed_at`, `source_refs`; event kind from the versioned comparison policy |
| `ReportDay` | `report_date`, `publication_id \| None`, `state: published \| no_publication`, `source_as_of \| None`, `coverage`, `rows`, `events`; fully resolved nonrecursive values, no renderer I/O |
| `TemplateSelection` | `template_id`, `version`, `options`; registry resolves package hash/renderer version, rejects unknown versions/options |
| `ReportEdit` | `edit_id`, `kind: note \| narrative_override`, `target`, `text`, `expected_original_hash \| None`; server adds verified actor/time/revision |
| `ReportDraft` | `draft_id`, `revision >= 1`, `revision_hash`, `selection`, `snapshot_hash`, complete snapshot, template selection/hash, ordered edits, `created_at`, `updated_at`, `parent_publication_id`, `state: draft \| finalizing \| finalized` |
| `RenderedReport` | `draft_id`, `revision`, `revision_hash` (null only for unpersisted pure rendering), `snapshot_hash`, `template_hash`, `html_document: bytes`, `html_fragment: str`, `plain_text: str`, SHA-256 and byte counts of each; `content_language=en` |
| `PublicationManifest` | `schema_version=1`, `publication_id`, `draft_id`, `draft_revision`, `purpose`, `parent_publication_id`, `baseline_publication_id`, `source_as_of`, `finalized_at`, `finalized_by`, `snapshot_hash`, `template_hash`, `file_hashes`; committed content without its own hash or Git commit ID |
| `ReportPublication` | `manifest: PublicationManifest`, `manifest_sha256`, `commit_id`, `checkout_state`; returned receipt verified against the committed manifest and `CommitReceipt`, not serialized into itself |

`source_commit` pins one consistent Git read view. `coverage` retains the
membership coverage plus every `CaptureCoverage` part and summary validity,
not a single boolean derived from issue status. `source_as_of` is the selected
manifest's `finalized_at`, not the current wall clock.

`next_actions` preserves the accepted candidate's action, owner_id, owner_basis,
owner_quote, owner_confirmed and evidence fields. A report-local action target
is `(source_key_hash, summary_id, action_index)`; it never implies stable action
identity across different summaries. Existing W5.JOIN owner_confirmed=false
is not promoted by rendering or finalization.

Evidence contains the verified capture/hash/pointer/ref ID and literal quote.
Blockers/limitations in review-1 are evidence IDs, not prose; the source reader
resolves their authorized evidence instead of printing invented explanations.
Unavailable summaries remain null/pending, not synthesized by the renderer.
Event kinds are `created`, `entered_scope`, `left_scope`, `closed`, `reopened`,
`status_changed`, `field_changed`, `content_changed`, `access_lost`; unknown
comparison is represented in coverage, not emitted as a fabricated event.
A `no_publication` day does not imply that no capture happened on that date.

## 5. Public Services And HTTP

Signatures are proposed new interfaces, not currently available commands:

```text
ReportSourceReader.read(actor, project_id, stage_id,
                        selection: ReportSelection) -> ReportSourceSnapshot

ReportRenderer.render(snapshot, template, edits,
                      *, draft_id, revision, revision_hash=None,
                      edition_state="draft") -> RenderedReport

ReportDraftService.create(actor, project_id, stage_id, *,
    command_id, selection, template) -> ReportDraft
ReportDraftService.get(actor, project_id, stage_id, draft_id) -> ReportDraft
ReportDraftService.save(actor, project_id, stage_id, draft_id, *,
    command_id, expected_revision, edits, template) -> ReportDraft
ReportDraftService.render(actor, project_id, stage_id, draft_id, *,
    revision) -> RenderedReport
ReportDraftService.finalize_and_commit(actor, project_id, stage_id, draft_id, *,
    command_id, expected_revision) -> ReportPublication
ReportDraftService.resume_finalization(actor, project_id, stage_id, draft_id,
    *, command_id) -> ReportPublication
ReportDraftService.get_publication(actor, project_id, stage_id,
    publication_id) -> ReportPublication
ReportDraftService.read_artifact(actor, project_id, stage_id,
    publication_id, format: html | plain_text) -> bytes
```

The trusted source reader consumes the existing archive and accepted records
through the proposed public archive query
`CaptureArchiveService.read_report_material(actor, project_id, stage_id, selection) -> ReportSourceSnapshot`.
Its injected contract and bounded query implementation are frozen in
[HTML source packet](html-source-packet.md); pass `contract` and `limits` as
keyword-only arguments so query construction never loads model clients.
It must not use
`SummaryAnalysisService.prepare/advance` to retrieve data: these are execution
boundaries. Inside the archive module, reuse its source/evidence validators and
commit-pinned reads; ui_web must not import its private helpers or read files.
ReportRenderer uses registered, preloaded templates and is deterministic over
supplied verified values, with no clock, filesystem, tracker, model, credentials
or Git calls during render.

Routes are relative to `/projects/<project_id>/stages/<stage_id>/reports/`:

| Method and suffix | Input and outcome |
| --- | --- |
| `POST drafts/` | Allowlisted selection/template and command UUID; create revision1 and redirect to editor |
| `GET drafts/<draft_id>/` | Owner-checked HTML editor; read only |
| `POST drafts/<draft_id>/save/` | Command UUID, expected revision, edits/template; atomically save next revision |
| `GET drafts/<draft_id>/render/?revision=N` | Exact saved revision; standalone HTML preview/download, no save or commit |
| `GET drafts/<draft_id>/clipboard/?revision=N` | Versioned JSON with HTML fragment/plain text and matching hashes; private/no-store |
| `POST drafts/<draft_id>/finalize/` | Command UUID, expected revision, explicit confirmation; local finalization/commit |
| `POST drafts/<draft_id>/resume/` | Original command UUID; retry the retained finalization, never re-read newer input |
| `GET publications/<publication_id>/` | Immutable edition with provenance and verified artifact choices |
| `GET publications/<publication_id>/download/?format=html` | Exact committed bytes, not rerendered output; plain_text also allowed |

All routes use `project_actor`, existing BasicAuth/owner checks and Django CSRF
on POST. Caller-supplied actor, filesystem path, commit hash, namespace, source
facts, arbitrary HTML and Git remote are rejected. Responses use
`Cache-Control: private, no-store`. Foreign records return404, unauthenticated401,
invalid inputs400, missing CSRF403, unsupported method405, conflicts409,
payload/quota limits413, local I/O unavailable503 with safe English error codes.
Do not translate exceptions into empty successful reports.

Codes: `REPORT_INVALID`, `REPORT_NOT_FOUND`, `REPORT_REVISION_CONFLICT`,
`REPORT_SOURCE_CHANGED`, `REPORT_COMPARISON_UNAVAILABLE`, `REPORT_TEMPLATE_UNSUPPORTED`,
`REPORT_EDIT_TARGET_INVALID`, `REPORT_FINALIZING`, `REPORT_FINALIZED`,
`REPORT_LIMIT`, `REPORT_FINALIZATION_PENDING`, `REPORT_ARTIFACT_INVALID`.
Existing archive/ownership error meanings remain unchanged.

## 6. Editing And Clipboard

The browser editor allows notes at report, issue or action level and overrides
of `key_message`, `what`, `current_position`, `verification`, action display text
or proposed next-owner display text. Targets are server-issued IDs in the pinned
snapshot; snapshot facts/status/counts/dates/evidence/coverage are not editable.
For a correction to a source fact, add an explicitly human-authored note.

Narrative overrides retain the original text/hash, author and edit time. Final
output identifies human text as `Meeting note` or `Edited by ...`; proposed
owners remain human proposals, never silently become Jira assignees or accepted
model decisions. Neither edits nor finalization enter subsequent AI input by
default or alter accepted-summary, raw-source or issue-action completion state.
Generated labels/narrative remain English; human notes and quotations preserve
their original language and are marked as human/source text, not auto-translated.

2026-11-03 user correction supersedes the former textarea-first choice:
the target is direct WYSIWYG editing of rendered rich text through an existing
open-source component. The authoring coordinator owns that integration; the latest
request does not require a separate user-supplied editor Agent.
Current literal-text forms are transitional, not accepted editor functionality.
The completed non-editor workflow did not expand its editor-specific test matrix.
The current APIs, required versioned rich-text input boundary, ownership and
deferred integration tests are in [editor handoff](rich-text-editor-handoff.md).
Preserve server validation, provenance and immutable revisions; never mark
untrusted DOM HTML safe or accept active pasted content. Actual source links
continue through the provider-aware safe-link adapter. Offline reimport remains
out of scope.

The copied HTML fragment contains the entire report body including table wrappers
and inline styles. Use a single browser `ClipboardItem` with `text/html` and
`text/plain`. Do not copy HTML source as plain text, assemble native CF_HTML
offsets in JavaScript, include editor controls or rely on the application CSS.
Prefetch the matching saved revision before enabling the Copy button; the user's
click invokes clipboard write. Unsaved edits or a mismatched preview revision
disable Copy until the chosen edits are saved. No invisible auto-copy on load.
Permission/API failures show failure and leave the valid `.html` download
available; do not claim copying succeeded or silently downgrade to plain text.

Email artifact choices: light background, explicit text colors, system font stack,
simple tables with inline padding/borders/backgrounds, safe absolute source URLs,
no flex/grid/sticky headers, external CSS/fonts/images, JavaScript or localhost
links. Tables wrap long values. Sections always exist in the static output;
no collapsed content that requires a click. Weekly output splits more than seven
selected dates into explicitly separate artifacts, not smaller unreadable fonts.

The target is formatted paste into an HTML-mode email composer without hand
reformatting. Clipboard formats alone do not prove receiving-client layout.
The user identified Windows Outlook and supplied its About screenshot on
2026-11-02: Microsoft Outlook version `1.2026.1020.100`, client version
`20261023003.06`, WebView2 `156.0.4314.50 (Stable)`. These are the target
environment baseline, not executed paste evidence. Do not retain the Session ID.
Record the actual versions and compose mode again when running HT30; an
application update changes the tested environment, not the report contract.
No further client/version clarification is required to proceed with local work.
An unsupported/plain-text composer is disclosed, not advertised as equivalent.
No real recipient or Send action is part of validation.

## 7. Storage, Commit And Recovery

Extend the existing external stage data root, not the code repository:

```text
<data-root>/projects/<project-id>/stages/<stage-id>/
  runtime/report-drafts/<draft-id>/
    intent.json
    revisions/00000001.json
    commands/<command-id>.json
    current.json
    finalization.json
    finalization-files/<publication-id>/
      snapshot.json
      template.json
      edits.json
      report.html
      report.txt
      manifest.json
  archive/report_publications/<publication-id>/
    snapshot.json
    template.json
    edits.json
    report.html
    report.txt
    manifest.json
```

Draft revisions are immutable local application records outside Git. Retain every
saved revision; `current.json` is the only mutable head and uses atomic replace.
They have the same root containment, owner, ACL/link and measured occupancy
guards as other stage runtime data. Browser localStorage is not durable authority.
They are not a second raw/summary archive and are not an off-device backup.

Create/save command replay first verifies actor/stage, then finds the persisted
command. Identical payload replays its original revision even if the current
revision has moved; same ID/different payload conflicts. Only a new command
checks expected_revision and allocates the next revision. All changes use the
existing root-budget -> stage lock order. No network/rendering under those locks.
Persist a command intent and immutable revision before publishing current.json;
on failure repair from the original command or refuse, never discard a revision
or use another request's head to hide a conflict.

Finalization renders outside the write lock, then reacquires the shared locks and
checks the owner, lifecycle, exact draft revision/hash, source visibility/current
source and baseline. A newer capture/summary or incompatible source policy
refuses a current standup (`REPORT_SOURCE_CHANGED`); create a new draft, explicitly
reconcile notes, or request a historical export. Never silently rebase edits.
Explicit historical exports keep the old cutoff and never advance live display.

Before a Git side effect, durably store all six exact file payloads in the
controlled `finalization-files/<publication-id>/` directory under admitted
root/stage quotas. Use immutable writes with file flush and the existing atomic
publication primitives; verify every retained file's byte length and SHA-256.
`manifest.json` contains hashes of the other five payloads, never its own hash.
Then atomically persist finalization.json containing the original command and
its canonical payload hash, selected revision, purpose, source/baseline/template
hashes, all six file hashes/sizes and controlled references, publication ID and
original timestamp. No caller can supply these references.

Only that complete durable packet changes the draft to finalizing; edits then
fail. A partial pre-intent byte packet is not an approved finalization. A retry
checks the still-current draft/source and reuses equal bytes or refuses a
conflicting packet. It does not silently discard retained files or pretend a
partial packet committed. Publication ID is a deterministic UUID5 of the draft ID and
`revision:purpose`; another command cannot create a second identical edition.
Resume needs the original command and exact payload; edits do not resume an intent.
After finalization.json exists, resume reads and verifies the retained six
payloads and passes those exact bytes to append_record. It never rerenders,
reloads a newer template or substitutes a current draft. A missing/corrupt
payload returns REPORT_ARTIFACT_INVALID and preserves the pending intent.

Register `report_publications` as one tightly validated namespace of the existing
`StageRepository.append_record`, with exactly the six file names above.
The finalization service owns no alternate Git writer, `git add .`, hooks or push.
It uses current authorized root/stage locks, quota reservation, original
fingerprint and the existing candidate/ref-CAS recovery. The committed
PublicationManifest has neither commit_id nor checkout_state. ReportPublication
adds the manifest hash and those post-commit values from the verified Git receipt,
avoiding self-referential hashes or a pre-commit success claim.

Only a verified committed edition finalizes the draft and updates the rebuildable
publication projection. A crash after commit but before response/projection replays
the same commit; it does not create a new edition, rerender under a new template
or call Jira/AI. A failed commit keeps the draft and finalization intent and does
not advance any publication checkpoint. Checkout materialization can be stale
despite a valid commit; show that separate state and do not overwrite manual files.
A projection may be rebuilt from Git; draft status is not publication proof.

Committed payload contains the chosen original snapshot, resolved template,
all saved edit revisions up to the selected revision with their provenance,
and exact HTML/plain bytes plus hashes. Do not commit `.env`, credentials,
developer code, unrelated pending drafts or raw files outside the manifest.
Raw/summary references already point to their existing preserved stage history.
Repository target is the registered stage archive, not a path typed into a form.
Separate report-repo export/remote selection is outside this first slice.

## 8. Bounds And Failure Policy

Initial configurable limits: snapshot8MiB, individual human text16KiB UTF-8,
all human edits per revision1MiB,1000 saved revisions per draft, HTML16MiB,
saved edit history8MiB, clipboard fragment2MiB. These are application limits, not claims about Outlook
or system capacity. Draft/artifact/runtime/Git growth all count against existing
root/stage quotas; never sample disk free space or restore the removed gate.

Exceeding a limit refuses explicitly with the original data retained. No automatic
ticket/date/comment/long-word truncation or deletion. Clipboard-only overflow
does not invalidate a within-limit full HTML download. New growth must reserve
finalization overhead through existing admission before acceptance.
Quota, malformed-template, escaping, stale revision and write failures leave
source/summary/publication checkpoints unchanged.

## 9. Incremental Delivery

The original HTML delivery below remains a historical bounded slice. Its source/edit/finalization
evidence is retained; new schema2/templates/completion/AI behaviors use W6.AUTHOR
and do not inherit full acceptance from this earlier slice.

The narrow HTML demo lane depends on W1/W2, W3.ARCHIVE/GATEWAY/CAPTURE and W5.JOIN,
not every remaining W3-W7 capability. It reads the already verified first complete
capture/accepted-summary combination and explicitly unsupported/pending states.
It must not synthesize a populated multi-day production history for a one-day
fixture. Multi-day comparison remains dependent on W4.DELTA/EVIDENCE and complete
per-item publication projection; synthetic renderer examples do not close it.

Leaf order and exact files/tests are in tasks.md. Exit for this lane: the user can
open an actual accepted-summary draft, edit/save a note, preview/copy/download
HTML, explicitly finalize once into real isolated data Git, and read the original
committed bytes. Public capture/run buttons remain W7 until their runtime packet
is implemented and qualified. A prepared-summary authoring demo is not yet
"click Run to collect new tickets" or the complete daily reporting product.

## 10. Source Checks

On 2026-11-02 official pages were fetched read-only with HTTP200. The W3C
clipboard document describes `text/html`/`text/plain`; Microsoft's Windows
documentation describes HTML fragment context. These support the format boundary,
not a guarantee of email-client rendering or user-granted clipboard permission.

```text
https://www.w3.org/TR/clipboard-apis/
https://learn.microsoft.com/en-us/windows/win32/dataxchg/html-clipboard-format
```

The current archive writer/lock/query and W5.JOIN source were inspected directly.
Codebase-memory generation2026-11-02T01:12:27Z predates summary journal changes;
those files were read rather than treating graph absence as absence of code.
No index rebuild, live provider/model call or existing demo modification is needed
to approve these report interfaces.

Draft storage/write ordering is further fixed in
[HTML draft packet](html-draft-packet.md), reusing the same root/stage lock and
Git owner. The returned draft snapshot is stored once, not duplicated per edit.

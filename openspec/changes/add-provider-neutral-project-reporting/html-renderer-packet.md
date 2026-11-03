# HTML Renderer Packet

Status: implementation detail for W6.HTML.RENDER, not an implementation result.
Parent: [authoring design](html-report-authoring.md).
Input: SOURCE public DTOs; output: editor/clipboard/publication consumers.
Task and tests: tasks.md W6.HTML.RENDER, HT01/02/09-12/32.

## Exact Interface And Values

```text
TemplateSelection(template_id="daily-standup", version="1", options={})
ReportEdit(edit_id, kind, target, text, expected_original_hash=None,
           author=None, edited_at=None)
TemplateDefinition(template_id, version, options, template_hash, renderer_version)
ReportRenderer(registry=None, *, max_html_bytes=16777216,
               max_clipboard_bytes=2097152)
  .render(snapshot, template, edits=(), *, draft_id, revision, revision_hash=None,
          edition_state="draft") -> RenderedReport
  .template_definition(template) -> TemplateDefinition
```

Construct the default registry by explicitly reading only the package's two
registered templates at ReportRenderer construction. No file/model/network
access during render. A supplied registry must contain preloaded registered
template values, not arbitrary user template paths. TemplateDefinition is
serialized for drafts/finalization. New value types may live in
`app/domain/report_presentation.py`, exported from `app/api/reports.py`, to keep
SOURCE contracts narrow and <=400 lines.

`RenderedReport` has the parent fields plus `clipboard_available: bool`.
It also exposes `revision_hash: str | None`. Pure unpersisted renderer calls may
omit it and show `unbound`; draft-service render must pass the exact saved
revision SHA-256 and include it in HTML/plain provenance. Never derive it from
rendered HTML or substitute snapshot_hash for the draft revision hash.
HTML/plain text use the exact rendered content from this call. SHA fields are
computed on UTF-8 bytes, not escaped/normalized strings; content_language is en.
Document is a standalone `<!doctype html>` with language/charset metadata and
one body. html_fragment is the complete content inside the body, not raw-source
text or half of a table. plain_text preserves all logical fields/rows.
`edition_state` is draft or final only, displayed in report provenance.

Supported `options`:

- `group_by`: none (default), status, assignee. Use literal field values,
  deterministic stable ordering; unknown remains Unknown, not dropped.
- `sort_by`: key (default). Add other sort policies only with a source field and
  test; unknown options fail rather than being ignored.
- `section_order`: permutation of key_messages/changes/register/coverage,
  default that sequence. No missing or duplicate required section.
- `optional_columns`: subset of source_hash/summary_time; default summary_time.
  All core issue/action/coverage columns remain mandatory.

Weekly day data is already resolved in snapshot.days; renderer accepts at most
seven ordered distinct date values. If no days are available, display the current
snapshot under its own report_date with initial-baseline/no-published-history
status. Do not synthesize prior days. More than seven days returns REPORT_LIMIT;
future caller-side batch export may split explicitly, never silently truncate.
A previous parent sentence about splitting more than seven dates describes that
future batch operation, not a hidden renderer side effect.

## HTML And Text Projection

Use current Django template Engine/Context with autoescape enabled; trusted
developer templates are the only markup. A view-model helper converts DTOs to
literal fields and validated hrefs. Do not use mark_safe on source/human text,
template-code interpolation, browser innerHTML from untrusted content, or a
handwritten HTML parser/sanitizer.

Daily output:

1. Project/stage, report date, source cutoff/timezone, baseline/edition metadata.
2. Key messages from snapshot with human overrides explicitly labeled.
3. Changes with occurrence/observation timestamps and exact before/after values.
4. One issue row/group for every member with title/status/current assignee,
   what/current position/verification, each next action/owner/basis, human notes,
   pending reason and summary age.
5. Evidence appendix per issue and coverage counts/limitations. Every referenced
   evidence ref appears with its capture/pointer/source hash and literal value.
   Long evidence stays wrapped, not truncated or moved onto another ticket.

Weekly output aligns stable source identity rows across supplied dates, preserving
per-day state/coverage and current action/owner. If a day lacks a publication,
show No published report, not No changes. The latest register and evidence
appendix remain available in the document; no CSS-hidden content.

Use a light report palette independent from Dashboard's dark UI:
white background, dark neutral text, restrained teal headings, explicit borders;
text labels accompany colored status indications. System font stack
Segoe UI/Arial/sans-serif at fixed legible sizes. Layout uses normal document
flow and simple tables, inline padding/borders/colors, width100%, bounded table
columns and normal wrapping. No app-shell navigation, buttons, scripts, forms,
SVG, remote images/fonts/styles, gradients or dynamic CSS dependencies.

Validate each source_url as absolute HTTPS without credentials/control characters
or untrusted query. Source provider/key mapping was made by SOURCE; a corrupted
URL refuses instead of becoming an active unsafe link. Unknown links stay text.
Human notes are literal text, not clickable arbitrary links.

## Human Edit Projection

`target` is an allowlisted mapping:

- Report note: `{scope:"report"}`.
- Issue note: `{scope:"issue", source_key_hash:<hash>}`.
- Action note: issue keys plus `summary_id`, `action_index`.
- Narrative override: add `field` = what/current_position/verification.
- Action override: action keys plus `field` = action/owner_display.
- Key-message override: `{scope:"message", message_id:<id>, field:"text"}`.

No unknown keys. A target must resolve exactly once in the pinned snapshot.
For overrides expected_original_hash is SHA-256 of the original UTF-8 display
text, never the text after an earlier override. Multiple overrides for the same
target in a revision refuse. Notes do not alter source facts/counts/status.
`kind` is note/narrative_override. `text` is nonempty literal UTF-8 without null
or forbidden control characters; allow newline/tab, preserve all Unicode.
Per-note/all-notes bounds follow the parent design. Stable edit_id is UUID.
Saved edits require server-populated author/edited_at; pure preview tests may
supply synthetic verified authors. Never infer user provenance from HTML.

Canonical snapshot and accepted candidate remain unchanged after rendering.
Human overrides include original text in the retained edit history, and final
output identifies edited content. owner_display is explicitly a human proposal,
not confirmed Jira assignment. Human note content is not fed to AI.

Expose pure helpers from `app/domain/report_edits.py`:
`validate_edit_targets(snapshot, edits) -> tuple[ReportEdit,...]` and
`original_target_text(snapshot, target) -> str | None`, reused by EDIT service.
An invalid target/hash/duplicate override returns REPORT_EDIT_TARGET_INVALID.
The service, not renderer, supplies author/time and preserves revision history.

## Bounds And Independent Validation

Serialize snapshot and total edits to enforce parent size bounds before render.
After render enforce full document16MiB; overflow is REPORT_LIMIT, never truncation.
If only clipboard fragment exceeds2MiB, return clipboard_available=false but
retain the full valid document/plain text for download. Copy endpoint later
returns REPORT_LIMIT; it does not replace output with a shortened report.

Use standard-library HTMLParser in validation/tests to inspect the actual
rendered DOM, not renderer string-concatenation functions as expected values.
Semantic expected test values are hand-authored fixture fields. Check complete
row/action/evidence association and all labels/identities, not aggregate
substring presence only. Mutation tests remove a row, exchange owners, inject
an active attribute and alter a note. All must be detected.
A pure runtime safety validator may check registered tags/attributes/URLs and
required document structure; no claim to be a general sanitizer.

## Files And First Test Cycle

Create `reporting/__init__.py`, `reporting/templates.py`, `reporting/html.py`,
`reporting/validation.py`, `reporting/view_model.py`,
`reporting/templates/daily_standup.html`, `weekly_timeline.html`,
`app/domain/report_presentation.py`, `app/domain/report_edits.py`,
`tests/report_render_fixtures.py`, `tests/test_report_templates.py`,
`tests/test_report_html.py`, `tests/test_report_edits.py`.
Modify public exports only in app/api/reports.py. No source reader/storage or UI
changes; interface mismatch is reported to coordinator, not patched silently.

First RED: render a source title containing `<script>` and a human note with
`<img onerror=...>` through the missing renderer; actual GREEN verifies literal
safe output, no such active elements and original source/notes unchanged.
Then HT01/02/10/11/12/32 and edit-target cases. Use all supplied rows including
one pending/one Fixed with an open retest, safe Jira link, null HSD link,
long Unicode evidence, two distinct owners and both template modes.

```powershell
.\.venv\Scripts\python.exe -m pytest project_management/tests/test_report_templates.py project_management/tests/test_report_html.py project_management/tests/test_report_edits.py -q
```

Rendering has no Git/network/native side effects; keep these fast tests free of
real capture setup. The SOURCE integration already proves its production input.
Actual browser/Outlook paste and final Git byte equality belong to later HT28-30.

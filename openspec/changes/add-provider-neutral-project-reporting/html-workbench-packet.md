# HTML Workbench Packet

Status: precise W6.HTML.UI consumer design, dependent on completed public report
services. State is maintained only in tasks.md.
Primary path: existing Project -> Stage -> saved ReportDraft -> final publication.
Target: desktop Chrome/Ego and confirmed Windows Outlook, no mobile matrix.

## UI Composition

Reuse Dashboard base.html, Bulma compact form/table classes, existing Iconoir
icons and Django gettext en/zh resources. No marketing, hero, theme rewrite or
edits to another agent's global CSS/scope editor. New editor is an unframed
document workspace: metadata, small action toolbar, content preview and labeled
edit forms. The report preview itself is a document, not nested decorative cards.

Add a stage-detail link in the existing project stage table, then show:

- Source identity and exact capture cutoff/coverage; available saved drafts and
  published editions as actual records, never fabricated example output.
- Create draft action for a captured source and template selector.
- Manual Run/status area only when the W7 runtime registry is ready; no such
  behavior created by a GET or fake enabled button when missing.
- Clear pending/error state if no capture or accepted summary exists.

Draft editor: title/project/stage, revision, source cutoff and coverage;
toolbar commands Save, Copy formatted report, Download HTML, Finalize and commit;
template selector and language control. Use familiar icons with title/aria labels.
Finalization additionally requires a checkbox confirming the exact revision and
displays the target as the registered data archive, not a free-form Git URL.
The public read `ReportDraftService.publication_target(actor, project_id,
stage_id) -> ReportArchiveTarget(archive_id, project_id, stage_id)` supplies the
actual registered archive-root UUID and bound project/stage IDs. The editor
combines these with its already authorized project/stage names. It exposes no
filesystem path, remote or credential, and does not initialize an archive.
Finalized edition has no editing form; "Create revision" explicitly opens a new
linked draft and leaves the existing edition downloadable.

Inline edit controls are plain textareas/form fields adjacent to selected
narrative/notes. Include Add meeting note target choices for report/issue/action.
Core status, source counts, original quotes, coverage and timestamps are
read-only. Human additions have author/time labels. No raw HTML/source editor.
Draft action choices are server-generated IDs, never arbitrary posted pointers.

Preview is rendered via an iframe whose URL is the exact saved revision render
endpoint with restrictive sandbox (no scripts/forms/top navigation) or an
equally isolated safe document. No source/human HTML is assigned directly to
the application DOM. Download returns exact bytes with safe filename and
Content-Disposition; report metadata never exposes filesystem/credential paths.
Final artifact responses use restrictive CSP/nosniff and private/no-store.

## Route And Form Boundary

Use the parent HTML routes; one new `ui_web/facades/project_reports.py`
consumes only public `project_management/app/api/reports.py` and the public
project catalog. Views may use its existing `ProjectAccessMixin` behavior,
not duplicate auth. Pass verified project_actor before invoking any service.
No template code reads model credentials, files or a private archive API.

Forms:

```text
ReportCreateForm: command_id, capture_id, template_id, template_version, timezone,
                  baseline_publication_id?, parent_publication_id?, purpose
ReportSaveForm: command_id, expected_revision, template_id, template_version,
                validated options, desired edits
ReportFinalizeForm: command_id, expected_revision, confirm
ReportResumeForm: command_id
ReportRenderQueryForm: revision (positive int)
ReportDownloadQueryForm: format(html|plain_text)
```

Use Django forms for scalar bounds, UUIDs/enums and payload lengths.
Nested desired edits can be a bounded JSON field internally or server
reconstructed from a formset, not trusting client author/time/facts. Unknown
keys/error types follow ReportError safe status mapping. Long revision strings,
negative numbers, duplicate operation keys and malformed JSON fail400.
Create/save/finalize use POST->redirect on success so refresh cannot repeat
submission with a new command ID. Server-generated command IDs are persisted in
the form and stable through a validation retry; a conflicting double submit
returns the original operation/revision per the service, not duplicate work.

Change language through the existing endpoint and explicitly add these new GET
route names to its safe-return allowlist. A language switch from a POST-only
route returns the matching GET editor/detail with saved state, never a405 page.
Locale switches do not save unsaved edits or start generation; preserve visible
unsaved input by avoiding navigation or requiring explicit save first.

## Clipboard Contract

Clipboard endpoint returns JSON:

```text
schema_version=1
draft_id, revision, snapshot_hash, template_hash
html_fragment, html_sha256, plain_text, plain_sha256
clipboard_available
```

Only a saved exact revision is returned. A fixture/repository path or raw
report.html string is not an accepted user request.
Load this bounded payload after the page has the saved revision. The copy
button starts disabled, becomes enabled only on successful matching payload
and no unsaved edits, and invokes `navigator.clipboard.write` in its click
handler with a single ClipboardItem for text/html and text/plain.
If fetch returns an error, mismatched IDs/hash, unsupported API or clipboard
permission denial, show a localized failure; never "Copied" without fulfilled
write promise. Enable HTML download independently. No clipboard reads required
for normal UI operation; tests may paste into a dedicated synthetic sink.

Track form dirty state with a small project-specific external JS file.
On any note/template edit disable Copy and Finalize until save; a concurrent
server update still must be rejected by expected_revision on submit.
Do not silently save on Copy or invoke synchronous execCommand fallback.
Cleanly handle htmx/page navigation and exactly one listener per rendered editor.

## Factories And Safety

The default report facade factory constructs the existing configured archive,
preloaded contract, source reader and renderer once per explicit runtime or
bounded request cache. It cannot construct an SDK client or open provider
connection. Native provider credentials are not needed for reading stored
authorized report records. A missing archive/contract yields an explicit safe
unavailable state, not a synthetic report.

The validation fixture owns its runtime registry/settings and injects actual
report services, not mocks of acceptance or Git. For route unit tests external
source transport may be synthetic, but real project/service owner checks stay.
No arbitrary import string or callable from a Web form.

Public composition entry:
`project_management.app.api.report_factories.build_report_service() -> ReportDraftService`.
It uses current configured archive and package-pinned AiTaskContract plus the
reviewed source reader/renderer. Tests may replace this trusted factory with
actual services on an owned synthetic root. No public actor/path/model setting.
The runtime composition may supply the same service instance to its worker/UI;
the report-only default builds no SDK client or worker thread.

Public listing required by the stage page:

```text
ReportDraftService.list_drafts(actor, project_id, stage_id, *,
                               limit=20, offset=0) -> ReportDraftPage
ReportDraftService.list_publications(actor, project_id, stage_id, *,
                                     limit=20, offset=0) -> ReportPublicationPage
ReportDraftPage(items: tuple[ReportDraftSummary,...], next_offset: int | None)
ReportDraftSummary(draft_id, revision, revision_hash, source_as_of, updated_at,
                   state, template_id, parent_publication_id)
ReportPublicationPage(items: tuple[ReportPublication,...], next_offset: int | None)
```

Lists are owner-checked, limit1..100 and offset>=0, stable lexicographic ID order
with explicit next offset. They enumerate at most1000existing directory/manifest
identities before refusing REPORT_LIMIT; no silent first-N success. Selected
identities may consume one bounded lookahead entry to establish overflow.
Bound the iterator before sorting/materialization. The existing GitRunner
already bounds subprocess output/time; a publication-specific directory read
must also avoid loading an entire recursive file inventory before this check.
Any new repository list helper uses the same Git runner and original commit
authority, not unchecked working-tree files or another subprocess manager.
Selected
items use the existing validated draft/publication readers. No new list index
or metadata cache. The stage view uses20rows per page and does not read all
artifact bodies into a template. Missing archive configuration is a safe
unavailable state, not an implicit empty new archive. An empty valid registered
archive list returns zero items; corruption is not converted into an empty list.
Draft directories must pass the existing containment/link checks; listing is
read-only and cannot initialize/migrate/repair an archive.

Stage page consumes public Project API for stage identity and archive.list_captures
for source choices, selecting the actual latest known capture only when the
bounded query is complete. More pages stay navigable and are not assumed absent.
The opaque capture cursor must survive the create POST and validation retry;
the server revalidates it through the original archive query and rebuilds the
same page's choices. A posted capture ID alone cannot bypass source ownership
or the saved-page selection. Include the compiled zh `.mo` in runtime/review
artifacts and verify actual zh labels, not only source `.po` presence.
Links to a run-produced draft include its explicit revision; opening latest is a
separate action. Current SOURCE slice refuses older capture/new changed
comparison as specified, and the UI displays that refusal rather than pretending
to generate a report.

## Validation

HT25-27: real Django Client plus CSRF-enforced client; two owners/two projects;
positive create/save/render/download/finalize routes and unauthorized/archived/
stale/invalid cases. Assert response status, exact returned IDs/bytes and
unchanged protected source, not private view method calls.
Targeted legacy project-language tests catch navigation regressions.

HT28-29: one stable-candidate desktop flow (1440x900) with saved English and
Unicode human text; verify no clipped command, no overflow hiding fields,
keyboard-operable input and true saved revision shown. Clipboard failure is an
actual rejected browser write or permission case, not just text substitution.

HT30: paste only synthetic copied HTML into a blank Outlook HTML-mode draft
without recipients. Verify tables, status text/colors, safe links, notes and
all rows, with no manual reformat. Do not send; do not navigate other messages
or record private mailbox/session data. If native UI control is unavailable,
record the precise gap rather than claiming clipboard-only success as Outlook
acceptance.

First RED: missing auth cannot create/read a draft and valid exact-source form
can create one through the public service. Then add save/copy revision behavior.
Use source fixture retained across related read-only route tests to keep costs
bounded, independent draft IDs for write cases.

Owned files: those in tasks W6.HTML.UI, plus project stage-detail view/template,
project_management report factories and tests when needed by actual composition.
Record exact additional files before editing; no unrelated view/CSS changes.

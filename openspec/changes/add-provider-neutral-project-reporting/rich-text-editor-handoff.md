# Rich-Text Editor Handoff

Decision date: 2026-11-03. Owner: the user's separate editor Agent.
Docs impact: user workflow, API integration and validation.
Task status remains only in [tasks](tasks.md).

## Accepted Requirement And Ownership

The user requires direct editing of rendered rich text, not a Markdown/text
textarea beside a preview. The previous textarea-first choice in
html-report-authoring section6 is superseded. A maintained open-source editor
component is approved in principle; component selection and its exact document
format belong to the editor Agent, not a second implementation in this lane.

The workflow Agent closes capture -> actual SDK/Base HTTP -> accepted summary
-> saved report -> HTML/plain download -> explicit local data-Git publication.
It does not enhance the old editor or expand textarea/toolbar/paste tests.
It leaves editor source files to the editor Agent. Existing backend test
evidence remains valid only for unchanged code.

The editor Agent owns component integration, direct rich-text editing,
selection/undo/redo, formatting and paste handling, dirty-state behavior,
sanitization, dependency/license records and its own focused tests.
Coordinate shared `ui_web/urls.py`, locales and backend DTO/storage changes
before writing them. Do not replace the capture, AI, draft journal or Git writer.

## Existing Integration Boundary

Public Python services are exported from
`project_management/app/api/reports.py`. `ReportDraftService` provides
create/get/save/render/finalize_and_commit/resume_finalization and immutable
publication/artifact reads. It is the persistence/permission authority.

Base HTTP path is
`/projects/<project_id>/stages/<stage_id>/reports/`:

| Operation | Current endpoint / contract |
| --- | --- |
| Load | GET `drafts/<draft_id>/`; owner-checked saved snapshot and revision |
| Save | POST `drafts/<draft_id>/save/`; CSRF, command UUID, expected_revision, template, edits |
| Preview | GET `drafts/<draft_id>/render/?revision=N`; exact saved revision HTML |
| Copy | GET `drafts/<draft_id>/clipboard/?revision=N`; HTML/plain and matching hashes |
| Finalize | POST `drafts/<draft_id>/finalize/`; command UUID, expected_revision, explicit confirm |
| Recover | POST `drafts/<draft_id>/resume/`; original finalization command only |
| Download | GET `publications/<publication_id>/download/?format=html` or `plain_text` |

Current form encoding lives in `ui_web/report_forms.py`: repeated
`edit_id/edit_kind/edit_target/edit_text/edit_operation` fields, server-issued
targets, and add/keep/remove operations. Domain `ReportEdit.text` is currently
literal text, not Markdown or trusted HTML. Existing support must not be
advertised as lossless rich-text persistence.

If the component needs formatting beyond that contract, the editor Agent
proposes and implements a versioned structured-document/edit DTO, allowlist,
server validation, serializer and renderer adapter with the workflow owner.
Never insert raw editor HTML into `ReportEdit.text` and mark it safe, silently
strip formatting to claim success, or rewrite existing revision hashes.
Old revisions remain readable; new format/version and migration behavior must
be explicit in its OpenSpec and delivery receipt.

## Invariants

- Human report changes remain overlays with author/time/original provenance.
  Editing the rendered report does not change raw Jira evidence or accepted AI
  content/hash, source facts, scope, dates, coverage or counts.
- Save is revision-CAS plus idempotent command replay, not Git finalization.
  Copy/download/finalize bind the exact saved revision; unsaved content is not
  falsely reported as copied or committed.
- Finalized editions are immutable; a correction creates a linked new draft.
  Publication stores exact static HTML/plain bytes without editor code.
- Owner/CSRF/private-no-store, quotas and source-drift checks remain enforced.
  No external assets, active markup, implicit model call, mail send or Git push.
- UI supports en/zh; generated business text remains English. Preserve human
  notes/source language. Do not add disk-free-space checks.

## Deferred Integration Gate

The current workflow may finish without WYSIWYG/Outlook acceptance. Do not
check W6.HTML.UI/R complete solely because its old textarea or backend passes.
Existing HT28/29/30 and the editing/copy portion of FS08 wait for the editor
delivery; report workflow evidence is recorded separately, not relabeled.

The editor Agent returns: source file inventory and fixed candidate hashes,
component version/license, document schema/version, public API deltas, server
sanitization policy, exact test command/results, known limits and a runnable
desktop entry. A screenshot alone is not an integration receipt.

Observed transitional-editor issue for that integration: the current preview
iframe showed `127.0.0.1 refused to connect` during the workflow run, while
standalone HTML downloads succeeded. Its frame/CSP integration was not
investigated or qualified in this lane. Replace or repair that presentation
as part of the delivered editor, without weakening static-artifact security.
The first automatic scroll to the finalization checkbox also failed in Ego;
an explicit scroll followed by native checkbox/button clicks finalized the
unchanged saved revision successfully. These observations are not WYSIWYG
or Outlook acceptance.

Then run one joined desktop Chrome/Ego journey: open generated report, edit
rendered text and add a formatted note, save/reload without losing formatting,
reject a stale second window, copy/download that saved revision, explicitly
finalize and compare committed bytes, then reload the original edition.
Check untrusted paste refusal/sanitization and owner/CSRF through focused tests.
Outlook paste into an empty draft with no recipients/send remains a distinct
receiving-client check; unavailability is reported, not replaced by DOM evidence.

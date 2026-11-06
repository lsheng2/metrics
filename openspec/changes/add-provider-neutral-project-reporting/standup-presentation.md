# Concise Standup And Audit Output

Date: 2026-11-06. User approved the concise body plus independent complete audit
attachment after [week delivery](week-delivery.md). Source base: `9dff849`.
Parent: [design.md](design.md). State belongs only to [tasks.md](tasks.md).
profile_source: repo-local. agent_routing_mode: multiagent-configured.
One implementation writer; one bounded independent plan/code reviewer. No new
framework, provider, AI profile, publication store or runtime engine.

## Outcome And Compatibility

New standup templates present one row per stable ticket, cumulative effective notes
with the original `wwN.d(provider status):` prefix, current unresolved ARs and
persistent notes. Include a short project/stage/date header and honest coverage.
Do not append accepted-summary prose, raw evidence, internal hashes or old
source-action state as competing business content. Explicit empty notes remain
empty; no old AI narrative is used as fallback. Unknown/missing/partial sources
remain visible, and removed rows retain their historical identity.

The six immutable publication files remain unchanged as a storage contract.
`snapshot.json` and `edits.json` retain full source evidence, accepted-summary
references, all editorial revisions, paint, provenance and action state.
A separately downloadable deterministic audit ZIP includes these exact original
six files plus an escaped readable `audit.html` and a versioned hash inventory.
This is a derived attachment, not a new publication or a re-render of old HTML.
No provider/model/Save/Finalize call is allowed while downloading it.

An optional `presentation_profile: "standup/1"` extends a schema-2 template
document. Absence retains the exact legacy schema-1/2 validation, renderer
`template-document/1`, presentation hashes and bytes. Presence is valid only on
schema 2 and selects renderer `template-document/2`; unknown/null profile or a
profile/renderer mismatch fails closed. The new profile requires exactly one
`meeting_matrix` data block; content and slots remain editable. Other source-data
blocks belong to legacy detail templates, not the concise body.
The fill-policy schema remains 2; no source or AI policy migration occurs.

New `standup_daily` and `standup_weekly` library actions create concise templates
and appear first. Existing starter actions and template revisions keep their
meaning. Users edit/copy these templates through the current builder; its Save
must preserve the profile, not silently revert to the legacy renderer. Existing
reports are never automatically converted. Selecting a new template for a new
meeting uses existing template-use/series/CAS contracts.

## Interfaces And Owners

| Contract / risk | Producer | Consumers / required behavior | Negative checks |
| --- | --- | --- | --- |
| PRESENT-TEMPLATE / high | `app/domain/report_templates.py`: `template_renderer_version(document)`, `is_pinned_renderer(value)` | template hashes/snapshots, `report_authoring.py`, `storage/report_drafts.py`, `services/report_draft_rendering.py`, UI view model | old hashes/bytes unchanged; profile not dropped; wrong renderer rejected before Save |
| PRESENT-BODY / high | new `reporting/standup.py`: `compile_standup_report(source, template, edits, context) -> (html, plain)` | `reporting/pinned.py`, `ReportRenderer`, original Save/Finalize/clipboard and Markdown/Excel paths | edited/deleted content not resurrected; no duplicate rows; true source status; unresolved ARs and partial coverage retained |
| PRESENT-AUDIT / high | `ReportDraftService.read_publication_artifacts(actor, project_id, stage_id, publication_id) -> ReportPublicationArtifacts` | existing public API, `ReportExportService.publication(format_name="audit_zip")` and new `reporting/report_audit.py` | one verified commit/owner; tamper/missing file rejected; no writes, render or external calls |
| PRESENT-UI / high | template forms/builder and publication export control | actual mounted editor, strict GET export route | foreign owner401/404, wrong method405, unknown/duplicate query400; audit unavailable on drafts; en/zh labels and keyboard controls |

The pure renderer/profile/readiness policy is factored into
`app/domain/report_template_presentation.py`, re-exported by `report_templates.py`;
this keeps the existing 400-line source boundary without duplicating validation.
Public artifact access delegates to `services/report_publication_reads.py` under
the existing service identity/error boundary. The additional direct consumer test
is `tests/test_report_presentation_guards.py`.

Plan review requires PRESENT-TEMPLATE to cover the closed contract family:
`validate_template_snapshot`, `_validate_pinned_template_binding`, `is_pinned_document`,
UI `is_pinned_template`, and finalization/resume through the draft/publication readers.
A user template, a `template-document/*` claim or any presentation-profile claim
must enter the strict pinned validator, never the generic legacy fallback.
Counterexamples must reject null/unknown/mismatched profiles at read, Save, render,
Finalize and resume; legacy absence keeps the original algorithm. Builder Save
preserves the exact profile and concise data choices. These are acceptance gates,
not optional UI polish. The initial RED tests preceded this explicit matrix wording;
no implementation preceded review. Review verdict: ready with these conditions.

`ReportPublicationArtifacts` is an immutable dataclass with `publication` and
`files` (the six named bytes), returned by one repository/read-validation pass.
`ReportPublicationReader.get()` may reuse this pass; it must not bypass
`validate_publication_files` or permit a caller to mark bytes trusted.

`ReportExport` remains the response DTO. Audit uses `format="audit_zip"`,
`media_type="application/zip"`, `generator_revision="report-audit/1"` and the
original manifest SHA as `source_sha256`. ZIP file names and timestamps are fixed;
paths are never accepted from the request. `audit.html` escapes all original
JSON/text and distinguishes source snapshot from effective editorial content.
`audit-manifest.json` records each included file SHA, publication ID, original
commit and generator revision, but no current time or moving checkout state.
Use the existing 32 MiB export bound for input aggregate and final attachment;
fail explicitly with `REPORT_LIMIT`, never truncate. No new dependency.

HTTP reuses
`GET /projects/<project>/stages/<stage>/reports/publications/<id>/export/?format=audit_zip`.
It keeps existing BasicAuth/owner/private-no-store/attachment headers. Draft
exports accept only Markdown/Excel. All ordinary HTML/plain publication downloads
remain exact committed bytes. Audit export is available for both legacy and new
publications, but does not silently make old detailed HTML concise.

## UI Contract

Reuse Django/Bulma/Iconoir, existing editor toolbar, table styles, template rows,
dirty-state signals and export selector. New concise starters are the primary
library choices; old choices remain named detail starters. Only meeting-matrix
data is offered for a concise template. No new component library or global CSS.

The editor continues using the approved cumulative matrix and current-note/AR
controls. Its data blocks no longer include raw summary/evidence sections for the
new template. Final output is a compact three-column `Ticket / Updates / AR`
projection of the same effective context, with stable widths and wrapping.
Fixed/custom template content and filled slots preserve canonical rich text.
Statuses and action ownership are not inferred by the renderer.

Desktop Chrome is the primary product gate; a small 390px render smoke checks
wrapping for the new output/control without reopening the multi-browser backlog.
Use local synthetic screenshots only; no external design service or uploaded data.

## Implementation And Validation

1. TEMPLATE/BODY: add a pure counterexample for a concise schema-2 template and
   human-edited context; validate readiness, old hash stability, safe links,
   original provider prefixes, empty notes, multiple tickets, unresolved ARs,
   partial coverage and absence of old AI/evidence text in the body.
   Implement the isolated compiler and exact renderer consumers only.
2. AUDIT: add pure ZIP/hash/safe-HTML/limit tests. Implement one owner-checked
   publication read pass and existing exporter dispatch. Test a real Git
   publication with current renderer/source/finalize poisoned after publishing:
   the audit must still return the original six bytes and leave Git head unchanged.
3. UI: TDD exact forms/query/metadata tests, then a mounted sample creates a
   concise template, edits colored notes, Save/reopens, Finalizes, downloads
   body/Markdown/Excel/audit and checks both visible output and ZIP originals.
   Exercise required/error/dirty/disabled and legacy-template Save compatibility.
4. Review source/evidence and current docs together, update the existing ledger,
   allowlist commit/push and verify remote SHA/unrelated-file hashes.

Named new tests: `project_management/tests/test_report_standup.py`,
`test_report_audit.py`, `test_report_standup_publication.py`,
`ui_web/tests/test_report_standup_views.py`, `test_report_standup_browser.py`.
Existing affected cases: template compilation/rendering/library, report exports,
authoring migration, continuity template UI, and JS template/export lifecycle.

Run with `.tmp/sdk-020-join-20261105/app-venv/Scripts/python.exe -I
scripts/validation/run_report_authoring_tests.py` and explicit test paths; use
unique XML evidence under `.tmp/dashboard-presentation-20261106/`.
Pure tests precede real Git/HTTP and a single mounted browser story. No full week,
new Base run or real provider/model is required for a presentation-only change.
Preserve original 42-file evidence; do a read-only original-byte check if a
modified reader affects it. A narrow passing test is not a whole-product gate.

Additional gates: isolated Django `check`, configured selected file-size and
whitespace, OpenSpec strict and local links. UI/source/runtime and docs evidence
are separate. No silent deadline extension or global config change.

## Refreeze And Stop

`refreeze_actions=[{action:amend,reason:approved concise body separates presentation
from immutable audit evidence}]`. Updated artifacts are this packet, the
report-authoring spec, tasks and current reporting guide. Rerun gates are the
named PRESENT tests plus affected template/publication/export consumers.
Preflight method: source producer/consumer/API and exact existing ledger mapping;
result must be recorded by `W6.PRESENT.PLAN.R`.

Scope includes the named compiler/domain/service/publication-reader files, exact
UI forms/view models/templates/JS/translation consumers, their focused tests,
current guide/README and this change. No provider, summary, operation, Base SDK,
source-capture or lifecycle change is included. No schema migration is needed.
Current request latency is an independent observed issue: do not combine a
read-path rewrite with this presentation change. Keep the profiling task open.
Stop and narrow if a new correctness issue requires changing source/acceptance or
editorial baseline semantics; do not restart another week to diagnose it.

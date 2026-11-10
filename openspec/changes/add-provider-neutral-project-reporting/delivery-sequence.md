# Dashboard Delivery Sequence

> 2026-11-11: the SDK/Base/pack prerequisites below are superseded by
> [MDB-2](../embed-ai-base-runtime-in-process/proposal.md); completed steps keep their evidence and
> remaining AI work follows tasks.md W4.REPLAN/W5 on the in-process task-run port.

Date: 2026-11-05. Status: user-approved reassessment, staged execution.
Parent: [design.md](design.md). State belongs only to [tasks.md](tasks.md).
profile_source: repo-local. agent_routing_mode: one implementation writer with bounded independent review.
This amendment changes the delivery order, not the original feature/quality requirements.

## 1. Frontier And Boundaries

```text
SDK020.JOIN.REPLAN [qualified]
 -> DELIVERY.PLAN.R -> DELIVERY.GOV
 -> W6.AUTHOR.DAILY -> W6.AUTHOR.DAILY.REPLAN
 -> W4.DELTA.PLAN.R -> W4.DELTA.CORE -> W4.DELTA.CORE.R -> W4.DELTA.CORE.REPLAN
 -> W6.AUTHOR.SOURCE
 -> W6.AUTHOR.ASSIST -> W6.AUTHOR.ASSIST.REPLAN
 -> W6.AUTHOR.EXPORT.SAMPLE -> W6.AUTHOR.JOIN -> W6.AUTHOR.R -> W6.AUTHOR.REPLAN
 -> remaining provider/history/workbench/deployment qualification
```

W3 archive/gateway/capture and the early summary/HTML/manual-run slices are existing prerequisites.
The bounded Jira changed-source slice may use those without waiting for every list/attachment/HSD
extension. It does not close W3.R, full W4.INDEX/DELTA/EVIDENCE/IMPORT, W5.MIGRATE or full W5 acceptance.
The old broad-wave dependencies remain for full-product closure; this is a declared limited lane.
No live providers/models, formal migration, scheduling or sending is implicitly enabled.

## 2. Contract And Consumer Matrix

| Contract | Producer | Consumers | Negative proof |
| --- | --- | --- | --- |
| DELIVERY-GOV / high | root AI_CONTRACT and selected environment guide | AGENTS, CLAUDE, Copilot, BKM, project profile and next agent packet | same authority, no competing test ban, explicit reporting paths/environment |
| DELIVERY-DAILY / high | preparation/continuity and verified publication | report_daily views, mounted editor, save, historical-reference resolver, finalize | actual Tuesday creation/edit; no Monday mutation or new historical lookup |
| DELIVERY-DELTA / high | bounded source-version analysis input | SummaryJournal prepare/accept and ReportSourceReader | rejected/failed intermediate analysis cannot lose cumulative changes; revision is not always one |
| DELIVERY-ASSIST / high | distinct authoring profile and server candidate | standard/continuity save, attribution, UI serialization, publication | wrong/stale/history targets refuse; local Apply is not Save/summary acceptance |
| DELIVERY-EXPORT / high | canonical fragments/template/context | HTML/plain/Markdown/Excel/clipboard readers | no lost row/AR/text; paint limitations explicit; original publication bytes preserved |
| DELIVERY-RELEASE / high | scoped source closure and exact environment | clean-checkout install/launch, worker, CLI and qualified providers | working-tree-only or legacy SDK cannot be relabeled a deployed product |

Consumer universe: public API, services, UI, exports, persistence, CLI/runtime, audit, validation
and current docs apply. No new global cache, background scheduler, alternate data store or SDK engine.
Existing source/analysis/editorial authorities and all old immutable bytes remain unchanged.

## 3. DELIVERY.GOV

Owner files: root AI_CONTRACT/AGENTS/CLAUDE; the relevant `.github` governance/profile entries;
`docs/development/reporting-delivery.md`, provider references, this change's design/tasks/history
and current SDK guide. Do not change model defaults, user credentials or unrelated Scope/CSS WIP.

Actions: preserve the original historical task text byte-for-byte in `execution-history.md`;
leave the checkbox ledger in tasks; make entrypoints reference one small local contract.
Use the already qualified SDK0.2 interpreter and existing no-dotenv runner. Check version/module
origin and required native imports before the first expensive fixture. Do not build another runner.
Validation: local links, explicit governance contradictions, unchanged active ledger, file size/
whitespace and OpenSpec strict checks. These are documentation gates, not product acceptance.

## 4. W6.AUTHOR.DAILY

Owner: `ui_web/tests/test_report_daily_ui_browser.py` and the minimum affected existing editor,
daily facade/view, reference, preparation or save consumer if the new test exposes a defect.
Do not preemptively rewrite the completed history or preservation algorithms.
The observed fixes own `ui_web/templates/projects/reports/{pinned_blocks,daily_preparation}.html`
and `ui_web/tests/test_report_history_template.py`: chronological cell content and a consumed
existing-publication link, with direct template counterexamples before browser verification.

Existing production APIs:

```text
ReportPreparationService.prepare(actor, project_id, stage_id, *, command_id, series_id,
    meeting_date, expected_series_policy_hash, expected_baseline_ref, template_selection,
    source_mode, capture_id, analysis_mode, acknowledge_gap_draft_ids)
ReportDraftService.save_authored(actor, project_id, stage_id, draft_id, *, command_id,
    expected_revision, expected_revision_hash, edits, continuity_changes=())
ReportDraftService.finalize_and_commit(actor, project_id, stage_id, draft_id, *,
    command_id, expected_revision)
ReportContinuityService.preview(actor, project_id, stage_id, *,
    series_id, meeting_date, template_selection)
```

Add `TestReportDailyUiBrowser.test_shouldCarryEditablePersistentReferenceIntoActualNextDay`.
Reuse the real saved-capture/ORM/data-Git fixture, actual routes and mounted Milkdown.
Only the upstream reference boundary is synthetic; do not seed final authoring JSON or bypass Save.

1. Prepare Monday through visible controls with saved_capture/manual_only.
2. Add a colored current note and a persistent carry-forward note through visible controls.
   Save the new persistent target before requesting its scoped completion; an unpersisted
   client-only target must not bypass server target admission. Reopen and obtain its link using
   actual `#ID` completion and the real signed-receipt/save path.
3. Save, reopen and Finalize Monday. Record its draft revision, note/fragment hashes, link record
   and publication reference. Save alone must not advance the editorial head.
4. Prepare Tuesday through the actual POST, not just preview. Its inherited persistent link keeps
   provider key/href/reference association. Change adjacent text and paint in the actual editor.
5. Save/reopen/Finalize Tuesday; assert visible text/color, unchanged Monday bytes/hash,
   chronological source-derived prefixes and the Tuesday editorial head.
6. Repeated preparation of the same meeting returns the existing work. No Base client is created,
   and Tuesday does not issue a new upstream lookup merely to preserve/edit the inherited link.
   Matching effective choices redirect; changed choices return 409 with the original result.
   After Finalize, a fresh preview can name a different baseline. Verify its unapplied-baseline
   message, the original publication link and exactly two drafts, not an unconditional 302.

Use `docs/development/reporting-delivery.md`'s explicit command and unique evidence paths.
Preserve response status/body before navigation waits; capture edited/reopened/finalized screenshots.
This test closes missing consumer proof. If it passes on existing code, report that honestly.
If it fails, add the smallest lower-layer reproduction before production changes, then re-run
only that rejection, affected consumers and the two-day chain. No full-week diagnostic loop.

Exit: the above mounted chain plus unaffected existing DAILY evidence is reviewed and bound;
record a scoped stage commit. A clean release of all historical authoring WIP is a separate
source-closure/publication responsibility, not a reason to stage unrelated files.

## 5. W4.DELTA.PLAN.R And CORE

The current implementation is deliberately initial-only: `prepare_analysis` raises
ANALYSIS_DELTA_REQUIRED for changed accepted sources, acceptance rebuilds initial input and writes
revision 1, and the report reader requires expected_revision=0/base_summary_id=null.
Changing only the first condition is invalid.

PLAN.R freezes the exact bounded input/result/evidence contract before CORE coding. Inspect:
`app/domain/summary_input.py`, `summary_validation.py`, `summary_contracts.py`,
`services/summary_journal.py`, `summary_journal_reads.py`, `report_sources.py`, and the fixed pack.
The pack already has baseline/delta fields. Reuse it where its declared bounds express the complete
input; a changed business profile requires a new explicit revision/qualification, not a patched pack
or an assumption that the entire SDK must change.

CORE owner paths are those files plus a focused pure delta-input helper if needed, their summary
tests and one source-to-summary-to-report consumer test. Reuse the existing archive, operation
journal, SDK and accepted-CAS boundary.

The common input contract must bind project/stage/provider/endpoint/principal/rule, accepted
summary ID/revision/source capture, ordered retained source versions, target capture, profile
and evidence hashes. Initial inputs keep their old serializer/hash. Acceptance recomputes the
same admitted input, compares the original accepted revision, writes the next revision, and
the reader verifies that same derivation instead of assuming every record is initial.
No metadata-only hash success may replace the semantic evidence/owner checks.

The same gate freezes `_require_no_pending_analysis`: an older accepted attempt must not block
later revisions merely because it is not the latest accepted attempt. Verified terminal failure
may permit a different-input attempt; unresolved submission must still be observed by its original
key and must block conflicting dispatch. A timeout is not evidence of terminal failure, and
reclassification must not change an existing key, request, deadline or consumed budget.

Required tests, frozen by PLAN.R before implementation:

- `test_shouldBuildCumulativeInputFromAcceptedBaseline`: accepted A, captured B then C, all
  required added/edited/deleted evidence remains represented; no last-fetch-only shortcut.
- `test_shouldPreserveChangesAcrossFailedAnalysis`: B result rejected/failed, C capture arrives,
  next attempt still derives from accepted A and retains B/C evidence.
- `test_shouldAdvanceAcceptedRevisionAndReadItInReport`: valid second analysis becomes revision 2
  and is consumed by the production report source reader, not only a direct journal assertion.
- `test_shouldRejectStaleOrRevokedDeltaBeforeAcceptance`: source/principal/accepted revision
  changed while a result was in flight; no accepted or editorial advancement.
- `test_shouldReuseUnchangedPostDeltaWithoutInference`: capture after accepted revision 2 has no
  semantic change; no new attempt/dispatch and accepted bytes are unchanged.
- `test_shouldAdmitChangedInputAfterEarlierAcceptedRevisions`: older accepted attempts do not
  become false pending blockers after revision 2, while only one new intent is admitted.
- `test_shouldKeepUnknownPriorSubmissionBlockingNewDispatch`: capturing C while B's submission
  remains unknown retains original-key recovery and does not issue a competing request.

L0 pure delta/evidence first, L1 real archive/CAS second, then one synthetic installed-SDK/local-HTTP
changed-source slice. Re-run affected initial/no-change/recovery consumers, not all old SDK tests.
Full index reconstruction, historical import, large-input chunking and other provider capabilities
remain explicit full W4/W5 work; do not silently truncate input or call the limited slice complete product.

## 6. ASSIST, Exports And Final Qualification

2026-11-06 source-closure amendment: `W6.AUTHOR.SOURCE` follows DELTA.CORE.REPLAN.
It publishes the retained, reviewed authoring/DAILY/delta dependency closure as one scoped
source packet, including its local editor assets, template resources, fixtures and migrations.
It excludes unrelated Scope UI/spec/main.css and model-default changes. Verify the candidate
tree's imports, explicit test collection, native asset manifest and isolated Django schema check;
collection is a packaging check, never a replacement for the already executed business tests.
Keep the root AI contract's authorization and disabled-runtime defaults intact.

ASSIST consumes the qualified source and DAILY context after this source closure.
Its exact service/profile/Apply/Save contracts remain in `sdk-020-post-integration.md` section 4
and `report-authoring-contracts.md`. Start with one actual editable target end-to-end, then cover
the other declared target consumers. Both standard and continuity save, provenance and JS receipt
serialization must be included. Do not merely remove the current fail-closed receipt check.

EXPORT.SAMPLE uses one saved draft containing paint, links, notes, an open AR and pinned template.
Qualify its intended render/export/clipboard paths before spending a week fixture.
Plain/Markdown limitations remain explicit; Outlook transport is a separate qualification.

The original full-week scenario remains 2026-10-26..30 plus 2026-11-02, three independent rows,
same source each day, varied human notes/paint, duplicate preparation, Save/reopen/Finalize and
normal restart. It proves editorial continuity, not changed-source analysis.
The separate DELTA proof supplies that complementary coverage; do not alter the requested week
or combine mismatched candidates to manufacture an overall pass.

W6.AUTHOR.REPLAN then enumerates remaining lists/HSD/dependencies/attachments/index/import,
existing-workbench compatibility, full exports, clean-install/deployment/backup and optional
default-disabled scheduling. External credentials, real execution and activation need their own
authorization. No required capability disappears because the manual reporting slice is useful.

# Docs Moved To OpenSpec

本项目后续以 OpenSpec 作为规范来源。

- Normative baseline specs: `openspec/specs/`
- Active/future changes: `openspec/changes/`
- Windows AIB/Dashboard closure plan: [execution plan](../openspec/changes/embed-ai-base-runtime-in-process/windows-close-plan.md), functional acceptance first, followed by the separate [performance phase](../openspec/changes/embed-ai-base-runtime-in-process/windows-performance-phase.md); one task ledger.
- Current B5 fixture decision: [approved B5-r1](../openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-b5-owner-decision.md); both real-chat and same-adapter backpressure proofs are required, with unchanged safety bounds.
- Windows native functional proof progress: [B5, queue bounds and disconnect evidence](../openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-w2-b5-progress.json); development evidence, not frozen W2/W3 acceptance.
- Windows resumed validation: [storage recovery and W2 integration](../openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-w2-resume.json); frozen native certification and joint acceptance remain separate.
- Windows functional closeout: [accepted evidence and limits](../openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-functional-closeout.md) and [formal receipt](../openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-functional-acceptance.json); 114/114 functional keys accepted at `ff09d6f`, with performance NOT_RUN.
- Supporting docs migrated from this folder: `openspec/docs/`
- Migration inventory: `openspec/docs/baseline-docs-inventory.md`
- Case studies and operator walkthroughs: `docs/case_study/`
- New user onboarding walkthroughs: `docs/onboarding/`
- UI design system contract: `openspec/docs/current-baseline/ui-design-system.md`
- Frontend design requirements (binding for every UI change): `openspec/docs/current-baseline/frontend-design-requirements.md`
- UI gate overlay/report: `.github/skills/lsheng2-ui-design/templates/project-overlay.md`, `.github/skills/lsheng2-ui-design/reports/ui-gate-report.md`
- Provider/Profile/Scope monkey-user E2E checklist: `.github/skills/lsheng2-ui-design/reports/provider-profile-scope-monkey-e2e-checklist.md`
- Full UI manifest gate: `scripts\validate_ui_full_manifest_gate.ps1 -BaseUrl http://127.0.0.1:8000 -NoScreenshots`
- Safe synthetic screenshot diff gate: `scripts\validate_ui_visual_diff_gate.ps1`

旧 `docs/` 下除这个兼容入口外的文档已经迁入 `openspec/docs/` 分类目录。若需要新增产品要求，请优先创建或更新 OpenSpec change，而不是在这里新增独立设计文档。

# Docs Moved To OpenSpec

本项目后续以 OpenSpec 作为规范来源。

- Normative baseline specs: `openspec/specs/`
- Active/future changes: `openspec/changes/`
- Central performance KPI specification: [PERF-SPEC-001](../openspec/docs/current-baseline/performance-kpis.md), covering current metrics, workload conditions, assumptions, evidence and open gaps.
- Performance test evidence: [dated report register](../openspec/docs/validation/performance-reports/README.md) and [report template](../openspec/docs/validation/performance-report-template.md); keep one immutable report per run/policy.
- Windows dev10 trial checkpoint: [valid bounded pilot](../openspec/docs/validation/performance-reports/2026-11-27-2024-dev10-pilot-r2.md) and [preserved failed first run](../openspec/docs/validation/performance-reports/2026-11-27-1906-dev10-pilot-r1.md); functional acceptance plus observed usability supports a controlled human trial, not formal performance certification.
- Required real provider/model acceptance: [authorized Windows packet](../openspec/changes/embed-ai-base-runtime-in-process/windows-live-acceptance.md) and [operator runbook](validation/dashboard-ai-e2e-runbook.zh.md); synthetic PASS does not replace actual business E2E.
- Windows observation method: [retained-window calibration repair](../openspec/changes/embed-ai-base-runtime-in-process/windows-scheduler-retention.md), with frozen collector bounds and no product KPI change.
- Windows process observation repair: [native details and Git command identity](../openspec/changes/embed-ai-base-runtime-in-process/windows-native-process-observation.md), preserving fail-closed ownership and all KPI/safety bounds.
- Windows AIB/Dashboard closure plan: [execution plan](../openspec/changes/embed-ai-base-runtime-in-process/windows-close-plan.md), functional acceptance first, followed by the separate [performance phase](../openspec/changes/embed-ai-base-runtime-in-process/windows-performance-phase.md); one task ledger.
- Windows page KPI renewal: [concurrent saturated policy](../openspec/changes/embed-ai-base-runtime-in-process/windows-page-policy-amendment.md); unchanged runtime, prospective evidence only.
- Windows editor selection repair: [focused regression evidence](../openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-editor-selection-repair.json); Dashboard-only command-boundary repair, not final combined acceptance.
- Current B5 fixture decision: [approved B5-r1](../openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-b5-owner-decision.md); both real-chat and same-adapter backpressure proofs are required, with unchanged safety bounds.
- Windows native functional proof progress: [B5, queue bounds and disconnect evidence](../openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-w2-b5-progress.json); development evidence, not frozen W2/W3 acceptance.
- Windows resumed validation: [storage recovery and W2 integration](../openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-w2-resume.json); frozen native certification and joint acceptance remain separate.
- Historical Windows functional closeout: [accepted evidence and limits](../openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-functional-closeout.md) and [formal receipt](../openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-functional-acceptance.json) at `ff09d6f`; not the current candidate.
- Supporting docs migrated from this folder: `openspec/docs/`
- Current Windows candidate: dev11, pinned in [development guidance](development/reporting-delivery.md#environment). The [dev10 functional receipt](../openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-functional-acceptance-dev10.json) at `3b60b05` remains historical: 3332 tests and114/114 keys; [dev10 performance policy](../openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-performance-inputs-dev10-r3.json) keeps its unchanged r3 numerical rules. Neither it nor the [dev9 refresh](../openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-functional-acceptance-dev9-refresh.json) qualifies dev11.
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

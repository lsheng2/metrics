# Docs Moved To OpenSpec

本项目后续以 OpenSpec 作为规范来源。

- Normative baseline specs: `openspec/specs/`
- Active/future changes: `openspec/changes/`
- Supporting docs migrated from this folder: `openspec/docs/`
- Migration inventory: `openspec/docs/baseline-docs-inventory.md`
- Case studies and operator walkthroughs: `docs/case_study/`
- New user onboarding walkthroughs: `docs/onboarding/`
- UI design system contract: `openspec/docs/current-baseline/ui-design-system.md`
- UI gate overlay/report: `.github/skills/lsheng2-ui-design/templates/project-overlay.md`, `.github/skills/lsheng2-ui-design/reports/ui-gate-report.md`
- Provider/Profile/Scope monkey-user E2E checklist: `.github/skills/lsheng2-ui-design/reports/provider-profile-scope-monkey-e2e-checklist.md`
- Full UI manifest gate: `scripts\validate_ui_full_manifest_gate.ps1 -BaseUrl http://127.0.0.1:8000 -NoScreenshots`

旧 `docs/` 下除这个兼容入口外的文档已经迁入 `openspec/docs/` 分类目录。若需要新增产品要求，请优先创建或更新 OpenSpec change，而不是在这里新增独立设计文档。

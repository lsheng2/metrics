# OpenSpec Supporting Docs

本目录保存 OpenSpec 主规格之外的支持材料。项目后续的规范来源以 `openspec/specs/` 和 active changes 为准；这里的文档用于解释历史背景、运行验证、迁移决策和 backlog。

## Normative Sources

- 当前 baseline requirements: `openspec/specs/dashboard-ui-baseline/`, `openspec/specs/engineering-metrics-baseline/`, `openspec/specs/bug-trend-baseline/`, `openspec/specs/provider-facts-and-sync/`
- 未来 Grafana/Jira/HSD-ES/AI target: `openspec/changes/define-grafana-jira-first-ai-dashboard-target/`
- 当前 baseline migration change: `openspec/changes/baseline-existing-dashboard-capabilities/`

## Folders

- `current-baseline/`: 反映当前已实现系统的背景、架构和 contract supporting docs。规范性要求以 `openspec/specs/` 为准。
  - `openspec/docs/current-baseline/ui-design-system.md`: 当前已实现的 Dashboard UI shared component contracts、使用边界和验证命令。
  - `openspec/docs/current-baseline/frontend-design-requirements.md`: 具有约束力的前端设计要求（Meridian 视觉语言、tokens、light/dark 主题、导航动线、组件目录、工具链与 QA gates），所有 UI 改动必须遵循。
  - `openspec/docs/current-baseline/frontend-design-recipes.md`: 具有约束力的前端 recipes（精确 token 值、选择器、标记模式，以及每条规则背后的 pitfall），是 frontend-design-requirements.md 的组成部分。
  - `openspec/docs/current-baseline/frontend-delivery-playbook.md`: 具有约束力的前端交付手册（工具链、文件架构与体积门禁、测试契约、真实浏览器复查、调试 pitfalls 与工作规则），是 frontend-design-requirements.md 的组成部分。
- `future-target/`: 尚未全部实现的产品目标、策略和 design input。进入实施前必须转成 active OpenSpec change。
  - `ai-base-gcx-metrics-contract.zh.md`: 记录 optional AI base 与 `gcx` 如何通过 Metrics-owned catalog、validator 和 publication precondition 协作。
- `validation/`: 测试策略、运行手册、C0/C1 evidence 和 validation gate 材料。
  - `ui-change-quality-gate.zh.md`: UI change 在 OpenSpec proposal/design/tasks 阶段必须定义的视觉、交互和浏览器验收门槛。
- UI gate runtime evidence lives under `.github/skills/lsheng2-ui-design/reports/`; hooked visual state scenarios use the repo-local `scripts/ui_design_fixture_hooks.py` module declared by the overlay.
- The full manifest UI gate is `scripts\validate_ui_full_manifest_gate.ps1 -BaseUrl http://127.0.0.1:8000 -NoScreenshots`; it runs all manifest routes with hooks and refreshes the aggregate report.
- The safe synthetic screenshot diff gate is `scripts\validate_ui_visual_diff_gate.ps1`; refresh its committed sanitized baselines with `-UpdateBaseline` only after accepting the visual change.
- The Provider/Profile/Scope monkey-user E2E checklist lives at `.github/skills/lsheng2-ui-design/reports/provider-profile-scope-monkey-e2e-checklist.md`.
- `historical/`: 研究记录、handoff、postmortem、旧架构说明等非规范材料。
- `backlog/`: 尚未进入 active OpenSpec change 的候选想法。

## Migration Rule

旧 `docs/` 中的内容不得直接视为 normative requirement。每条可执行要求必须先进入 `openspec/specs/` 或 `openspec/changes/<change>/specs/`，再由对应 apply/archive workflow 推进。

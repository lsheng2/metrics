# Baseline Docs Migration Inventory

本 inventory 记录从旧 `openspec/docs/` 迁移到 OpenSpec supporting docs 的文件分类。分类优先级为：当前代码事实、已存在测试、OpenSpec 主规格、仍准确的旧文档。

| Original path | Classification | New path | Disposition |
| --- | --- | --- | --- |
| `docs/architecture-manual.md` | `current-baseline` | `openspec/docs/current-baseline/architecture-manual.md` | Supporting architecture background; normative baseline lives in `openspec/specs/`. |
| `docs/bug-trend-architecture-spec.md` | `current-baseline` | `openspec/docs/current-baseline/bug-trend-architecture-spec.md` | Supporting historical architecture and DAG notes; implemented behavior migrated into `bug-trend-baseline`. |
| `docs/bug-trend-scope-config-micro-architecture.zh.md` | `current-baseline` | `openspec/docs/current-baseline/bug-trend-scope-config-micro-architecture.zh.md` | Supporting details for scope config behavior. |
| `docs/grafana-approved-data-surfaces.json` | `current-baseline` | `openspec/docs/current-baseline/grafana-approved-data-surfaces.json` | Supporting allowlist evidence for Grafana data surface governance. |
| `docs/grafana-bug-trend-chart-spec-reference.zh.md` | `current-baseline` | `openspec/docs/current-baseline/grafana-bug-trend-chart-spec-reference.zh.md` | Supporting chart spec field reference. |
| `docs/grafana-chart-render-contract-architecture.md` | `current-baseline` | `openspec/docs/current-baseline/grafana-chart-render-contract-architecture.md` | Supporting render contract architecture; normative baseline lives in `bug-trend-baseline`. |
| `docs/grafana-jira-fact-table-architecture.md` | `current-baseline` | `openspec/docs/current-baseline/grafana-jira-fact-table-architecture.md` | Supporting fact table architecture notes. |
| `docs/bug-trend-dashboard-product-requirements.zh.md` | `future-target` | `openspec/docs/future-target/bug-trend-dashboard-product-requirements.zh.md` | Product target input; must become or attach to active OpenSpec changes before implementation. |
| `docs/grafana-ai-dashboard-composition-design.zh.md` | `future-target` | `openspec/docs/future-target/grafana-ai-dashboard-composition-design.zh.md` | Future AI/Grafana composition design input. |
| `docs/jira-operations-platform-strategy.zh.md` | `future-target` | `openspec/docs/future-target/jira-operations-platform-strategy.zh.md` | Provider operations platform strategy input. |
| `docs/grafana-bug-trend-deployment-guide.zh.md` | `validation-runbook` | `openspec/docs/validation/grafana-bug-trend-deployment-guide.zh.md` | Operational deployment/runbook material. |
| `docs/c0-validation-closure-evidence.md` | `validation-runbook` | `openspec/docs/validation/c0-validation-closure-evidence.md` | Runtime evidence record. |
| `docs/c1-evidence-link-validation-evidence.md` | `validation-runbook` | `openspec/docs/validation/c1-evidence-link-validation-evidence.md` | Runtime evidence record. |
| `docs/validation/README.md` | `validation-runbook` | `openspec/docs/validation/README.md` | Validation folder index. |
| `docs/validation/ai-validation-operating-model.md` | `validation-runbook` | `openspec/docs/validation/ai-validation-operating-model.md` | Validation operating model. |
| `docs/validation/e2e-runtime-runbook.md` | `validation-runbook` | `openspec/docs/validation/e2e-runtime-runbook.md` | Runtime E2E runbook. |
| `docs/validation/gate-and-ci-plan.md` | `validation-runbook` | `openspec/docs/validation/gate-and-ci-plan.md` | Gate and CI plan. |
| `docs/validation/jira-grafana-test-plan.md` | `validation-runbook` | `openspec/docs/validation/jira-grafana-test-plan.md` | Jira/Grafana test plan. |
| `docs/validation/test-case-catalog.md` | `validation-runbook` | `openspec/docs/validation/test-case-catalog.md` | Test-case catalog. |
| `docs/validation/test-strategy.md` | `validation-runbook` | `openspec/docs/validation/test-strategy.md` | Validation strategy. |
| `docs/service-lifecycle-engine.zh.md` | `validation-runbook` | `openspec/docs/validation/service-lifecycle-engine.zh.md` | Local runtime/service lifecycle engine supporting module notes. |
| `docs/ai-base-dashboard-query-agent-handoff.md` | `historical` | `openspec/docs/historical/ai-base-dashboard-query-agent-handoff.md` | Historical handoff, not normative. |
| `docs/implementation-start.md` | `historical` | `openspec/docs/historical/implementation-start.md` | Historical implementation start note. |
| `docs/jira-dashboard-research-and-architecture.md` | `historical` | `openspec/docs/historical/jira-dashboard-research-and-architecture.md` | Research/background record. |
| `docs/lsheng2-coding-review-postmortem.zh.md` | `historical` | `openspec/docs/historical/lsheng2-coding-review-postmortem.zh.md` | Postmortem. |
| `docs/lsheng2-multiagent-creation-architecture-manual.md` | `historical` | `openspec/docs/historical/lsheng2-multiagent-creation-architecture-manual.md` | Skill/agent architecture history. |
| `docs/backlog/README.md` | `backlog` | `openspec/docs/backlog/README.md` | Backlog index. |
| `docs/backlog/chart-spec-catalog.md` | `backlog` | `openspec/docs/backlog/chart-spec-catalog.md` | Candidate chart catalog work. |
| `docs/backlog/jira-onboard-page.md` | `backlog` | `openspec/docs/backlog/jira-onboard-page.md` | Candidate Jira onboarding work. |

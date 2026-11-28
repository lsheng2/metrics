# Custom Agents

This repository carries four project-local custom agents adapted from the mature `system_integration_agent_ai` workflow.

| Agent | Use When | R2 Change Role | Primary Output |
| --- | --- | --- | --- |
| Architect Planner Reviewer | Architecture, R2 change plans, implementation handoffs, code reviews | Plan (proposal, design, `tasks.md`), milestone review, replanning, final review | Handoff packet or findings-first review |
| Implementation Engineer | Execute an approved handoff | Approved milestones that change production/test/doc/config/artifact files, run with `r2-change-loop` | Scoped code/test/doc changes plus review packet |
| Validation Engineer | Test-plan signoff, stale/wrong-owner test review, gate-profile selection, closure-claim review | `feature_list.json` and acceptance-test signoff for high-risk authority, cross-module contracts, governance/validation changes, UI/runtime claims, or non-obvious test ownership | Validation verdict, authority matrix, focused gates |
| Dashboard Debugger | Jira/Azure/Django/htmx/calculation debugging | Debug or incident work only | Fix-ready diagnosis and validation command |

Pick the lane in `AI_CONTRACT.md` §1. R2 work (dependencies, multiple owners, or independent review gates) runs as an OpenSpec change with the `r2-change-loop` skill. R0/R1 work needs no agent team: a failing-first test or a one-page brief with an obvious validation command.

Do not involve all four agents by default. An R2 change invokes an agent only when that agent owns a distinct gate, milestone, evidence question, or failure mode. For nontrivial changes, list skipped plausible agents with a short reason.

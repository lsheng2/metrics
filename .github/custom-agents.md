# Custom Agents

This repository carries four project-local custom agents adapted from the mature `system_integration_agent_ai` workflow.

| Agent | Use When | DAG Default | Primary Output |
| --- | --- | --- | --- |
| Architect Planner Reviewer | Architecture, DAG plans, implementation handoffs, code reviews | `PLAN.R`, `W*.R`, `W*.REPLAN`, `CLOSE.R` | Handoff packet or findings-first review |
| Implementation Engineer | Execute an approved handoff | Implementation nodes `W*.N*` when a node changes production/test/doc/config/artifact files | Scoped code/test/doc changes plus review packet |
| Validation Engineer | Test-plan signoff, stale/wrong-owner test review, gate-profile selection, closure-claim review | `W*.VA` for high-risk authority, cross-module contracts, governance/validation changes, UI/runtime claims, or non-obvious test ownership | Validation verdict, authority matrix, focused gates |
| Dashboard Debugger | Jira/Azure/Django/htmx/calculation debugging | Debug or incident nodes only | Fix-ready diagnosis and validation command |

Use the DAG skill when the work has dependencies, multiple owners, or independent review gates. Use a simple checklist for one-file fixes with an obvious validation command.

Do not involve all four agents by default. A DAG plan should invoke an agent only when that agent owns a distinct gate, implementation node, evidence question, or failure mode. For nontrivial plans, list skipped plausible agents with a short reason.

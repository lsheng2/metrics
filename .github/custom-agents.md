# Custom Agents

This repository carries four project-local custom agents adapted from the mature `system_integration_agent_ai` workflow.

| Agent | Use When | Primary Output |
| --- | --- | --- |
| Architect Planner Reviewer | Architecture, DAG plans, implementation handoffs, code reviews | Handoff packet or findings-first review |
| Implementation Engineer | Execute an approved handoff | Scoped code/test/doc changes plus review packet |
| Validation Engineer | Test-plan signoff, stale/wrong-owner test review | Validation verdict and focused gates |
| Dashboard Debugger | Jira/Azure/Django/htmx/calculation debugging | Fix-ready diagnosis and validation command |

Use the DAG skill when the work has dependencies, multiple owners, or independent review gates. Use a simple checklist for one-file fixes with an obvious validation command.

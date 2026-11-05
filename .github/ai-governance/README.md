# AI Governance BKM

This directory is the repo-local BKM library for AI-assisted work. It adapts useful practices from the longer-running `system_integration_agent_ai` project to this Django metrics dashboard.

Use these files as small, focused references rather than loading every policy for every task.

| File | Use When |
| --- | --- |
| `behavioral-first-principles.md` | Starting nontrivial code, architecture, or debugging work |
| `context-loading-policy.md` | Deciding what to read before editing |
| `shell-execution-policy.md` | Running terminal commands, especially on Windows |
| `closure-verification-policy.md` | Claiming a class of work is complete or review-ready |
| `code-comment-policy.md` | Adding, removing, or reviewing production comments |
| `backlog-management-policy.md` | Capturing deferred work, backlog triage, and promotion to DAG planning |
| `repo-context.md` | Needing a short machine-facing project summary |

Keep this layer compact. `AI_CONTRACT.md` is the development authority; the root agent files
are thin entrypoints. Product architecture lives in README and `openspec/docs/`.
Reporting environment and validation routing are in `docs/development/reporting-delivery.md`.

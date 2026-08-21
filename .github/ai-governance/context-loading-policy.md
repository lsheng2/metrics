# Context Loading Policy

Status: active BKM.

## Default Order

1. User request and selected files.
2. `CLAUDE.md`.
3. `.github/copilot-instructions.md`.
4. The specific BKM file relevant to the task.
5. Target module code and nearest tests.
6. Broader docs only when the local owner path is still ambiguous.

## Task Matrix

| Task Type | Extra Context |
| --- | --- |
| Code change | `code-comment-policy.md`, target module tests, owner public API |
| Django settings/view/template change | `repo-context.md`, `python manage.py check` as validation |
| DAG plan or multi-agent handoff | Shared `dag-based-planning` skill and `.github/skills/dag-based-planning/templates/project-profile.md` |
| Runtime debugging | `.github/agents/dashboard-debugger.agent.md`, failing command/URL/log excerpt, nearest owner tests |
| Diagram work | `.github/skills/drawio/SKILL.md` for complex diagrams; Mermaid skill for simple Markdown diagrams |
| Completion or review claim | `closure-verification-policy.md` and actual command output |

## Rules

1. Do not load the whole repo narrative for a one-file fix.
2. Prefer owning abstractions and nearby tests over broad exploration.
3. If a stable behavior or public contract changes, check whether `README.md`, `CLAUDE.md`, or `docs/` need truth-sync.
4. When in a dirty worktree, separate pre-existing changes from the files owned by the current task.

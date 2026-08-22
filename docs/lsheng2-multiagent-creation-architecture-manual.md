# Metrics Multiagent Routing Adoption Note

Status: project-local adoption note. The reusable `lsheng2-multiagent-creation` user manual and architecture manual live in the shared skill checkout, not in this repository.

## Source Of Truth

Use these layers in order:

1. Shared skill manuals: `%USERPROFILE%/.copilot/skills/lsheng2-multiagent-creation/README.md`, `USER_MANUAL.md`, `ARCHITECTURE.md`, and `SKILL.md`.
2. Metrics project profile: `.github/skills/lsheng2-dag-based-planning/templates/project-profile.md`.
3. Metrics custom agent index: `.github/custom-agents.md`.
4. Metrics agent files: `.github/agents/*.agent.md`.

The old `.github/skills/dag-based-planning/templates/project-profile.md` path is compatibility-only. Do not use it as the primary project truth for new DAG plans.

## Metrics Current State

Metrics already has the four canonical DAG role agents as hand-written project-local agents:

| Canonical DAG Role | Project Agent | File | Reconciliation Decision |
| --- | --- | --- | --- |
| Architect Planner Reviewer | Architect Planner Reviewer | `.github/agents/architect-planner-reviewer.agent.md` | preserve |
| Implementation Engineer | Implementation Engineer | `.github/agents/implementation-engineer.agent.md` | preserve |
| Validation Engineer | Validation Engineer | `.github/agents/validation-engineer.agent.md` | preserve |
| Dashboard Debugger | Dashboard Debugger | `.github/agents/dashboard-debugger.agent.md` | preserve |

No duplicate template agents should be created for this repository. If the shared skill is updated later, use `check multiagent setup for this project` or `dry-run multiagent creation` first and compare proposed changes against the hand-written agents before editing.

## Routing Rule

Metrics uses `agent_routing_mode=multiagent-configured` only because all three project-local surfaces agree:

- `.github/agents/*.agent.md` defines compatible agent frontmatter and role boundaries.
- `.github/custom-agents.md` names the same agents and DAG defaults.
- `.github/skills/lsheng2-dag-based-planning/templates/project-profile.md` has a `DAG Agent Routing` section with the same role responsibilities.

These agents are routing defaults, not mandatory participants. A DAG plan should invoke an extra agent only when that agent owns a distinct gate, implementation node, evidence question, or failure mode.

## Maintenance Policy

- Preserve hand-written agent files by default.
- Use `map` for equivalent differently named agents in future projects; do not create duplicates.
- Use `update` only for small missing routing text in compatible generated or owned files.
- Use `create` only when no compatible agent exists.
- Use `defer` when ownership or purpose conflicts.
- Do not copy shared skill architecture text into project docs. Link to the shared skill manuals and keep this file limited to Metrics adoption facts.

## Validation For Future Changes

When this routing setup changes, run or account for:

```powershell
python scripts/check_diff_whitespace.py --include-untracked
python scripts/check_file_size_limits.py --include-untracked
```

For DAG planning changes that touch Django settings, URLs, views, templates, containers, or integration behavior, also run:

```powershell
python manage.py check
```

---
name: lsheng2-dag-based-planning
description: Use when Codex needs DAG-backed plans, dependency graphs, implementation ledgers, invariant contracts, multi-agent handoffs, or machine-checkable task DAGs from the lsheng2 planning workflow.
argument-hint: init project profile, feature/fix scope, source spec, or plan file
---

# Lsheng2 DAG-Based Planning Adapter

## Codex-Only Adapter Layer

This adapter is for Codex only. It is maintained in this repository so projects can install it into `.agents/skills/lsheng2-dag-based-planning/`.

Copilot should continue to use the repository root `SKILL.md` or a project-local `.github/skills/lsheng2-dag-based-planning/SKILL.md` adapter. Do not point Copilot at this Codex adapter, and do not mirror these wrapper scripts into `.github/skills/`.

## Canonical Source

The canonical workflow remains the user-level personal skill:

`%USERPROFILE%/.copilot/skills/lsheng2-dag-based-planning/SKILL.md`

Load that file first. If the personal skill is unavailable in a project-local environment, fall back to `.github/skills/lsheng2-dag-based-planning/SKILL.md` only when that project-local adapter exists. Then resolve the target project's repo-local profile at `.github/skills/lsheng2-dag-based-planning/templates/project-profile.md`, with `.github/skills/dag-based-planning/templates/project-profile.md` accepted only as the documented legacy compatibility path.

## Codex Script Wrappers

Use local wrappers from this adapter root when Codex instructions say `python scripts/...`:

- `scripts/init_project_profile.py`
- `scripts/lint_project_profile.py`
- `scripts/dag_setup_doctor.py`
- `scripts/sync_personal_skills.py`
- `scripts/sync_agent_adapters.py`
- `scripts/run_maintainer_checks.py`

Each wrapper forwards to the canonical script under `%USERPROFILE%/.copilot/skills/lsheng2-dag-based-planning/scripts/` on Windows or `~/.copilot/skills/lsheng2-dag-based-planning/scripts/` on Unix-like systems.

`sync_personal_skills.py` still synchronizes the three canonical personal skill repos by default. It does not update project-local Codex adapters unless a workflow explicitly adds that installation step.

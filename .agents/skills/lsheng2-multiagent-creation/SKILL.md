---
name: lsheng2-multiagent-creation
description: Use when Codex needs to set up, adapt, review, or repair project-local custom agents and Codex role adapters for DAG-based planning.
argument-hint: target repository, dry-run, create/update agents, repair routing, validate setup, or install Codex adapters
---

# Lsheng2 Multiagent Creation Adapter

## Codex-Only Adapter Layer

This adapter is for Codex only. It is maintained in this repository so projects can install it into `.agents/skills/lsheng2-multiagent-creation/`.

Copilot should continue to use the repository root `SKILL.md` or a project-local `.github/skills/lsheng2-multiagent-creation/SKILL.md` adapter. Do not point Copilot at this Codex adapter, and do not mirror Codex role adapters into `.github/skills/`.

## Canonical Source

The canonical workflow remains the user-level personal skill:

`%USERPROFILE%/.copilot/skills/lsheng2-multiagent-creation/SKILL.md`

Load that file first. If the personal skill is unavailable in a project-local environment, fall back to `.github/skills/lsheng2-multiagent-creation/SKILL.md` only when that project-local adapter exists. This adapter adds Codex installation guidance only.

## Codex Applicability

The canonical `lsheng2-multiagent-creation` skill has templates and instructions, but no executable scripts to wrap.

For Codex, install role adapters from `role-adapters/` into project-local `.agents/skills/` only when the project already has compatible Copilot custom agents or when the setup workflow creates them. Keep `.github/agents/*.agent.md` as the Copilot source of truth.

The default role adapter templates are:

- `role-adapters/lsheng2-agent-router/SKILL.md`
- `role-adapters/architect-planner-reviewer/SKILL.md`
- `role-adapters/implementation-engineer/SKILL.md`
- `role-adapters/validation-engineer/SKILL.md`
- `role-adapters/dashboard-debugger/SKILL.md`

Do not create duplicate role definitions in Codex. A Codex role adapter should point to the matching `.github/agents/*.agent.md` canonical role file and explain that it is Codex-only.

---
name: lsheng2-agent-router
description: Use when Codex needs to choose a project-local DAG role adapter, map existing Copilot custom agents to Codex role skills, or route work among Architect Planner Reviewer, Implementation Engineer, Validation Engineer, and Dashboard Debugger.
argument-hint: DAG node, handoff, incident, validation gate, or role-selection request
---

# Lsheng2 Agent Router

## Codex-Only Adapter Layer

This adapter is for Codex only. It must not be treated as a Copilot custom agent, and it should not be mirrored into `.github/skills/`.

Copilot remains the owner of canonical role definitions in `.github/agents/*.agent.md` and `.github/custom-agents.md`.

Use this skill only to help Codex select or delegate to existing project-local roles.

## Routing

Read `.github/custom-agents.md` first, then load only the role file that matches the current work.

| Work Type | Codex Adapter | Canonical Role File |
| --- | --- | --- |
| Architecture, DAG plan review, handoff review, closure review | `architect-planner-reviewer` | `.github/agents/architect-planner-reviewer.agent.md` |
| Approved implementation nodes or scoped code/test/doc/config changes | `implementation-engineer` | `.github/agents/implementation-engineer.agent.md` |
| Validation architecture, gate selection, stale/wrong-owner test risk | `validation-engineer` | `.github/agents/validation-engineer.agent.md` |
| Reproduced failures, runtime symptoms, htmx/Jira/Azure/Django/debug evidence | `dashboard-debugger` | `.github/agents/dashboard-debugger.agent.md` |

Agents are routing defaults, not mandatory participants. Use one only when it owns a distinct gate, implementation node, evidence question, or failure mode.

## Codex Delegation

When delegating to a Codex subagent or separate task, include the selected role name, canonical role file path, user request or DAG node, owner paths, out-of-scope paths, required project rules from `AGENTS.md`, expected output shape from the canonical role file, and validation commands or evidence requirements.

Do not pass the entire chat history when a focused prompt is enough. Preserve existing `.github/agents/*.agent.md` files unless the user explicitly asks to change Copilot custom agents.

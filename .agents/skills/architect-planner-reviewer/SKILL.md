---
name: architect-planner-reviewer
description: Use when Codex should act as the project's Architect Planner Reviewer for architecture plans, DAG planning/review gates, implementation handoffs, public API contracts, or closure review.
argument-hint: plan, DAG node, architecture question, handoff, or review gate
---

# Architect Planner Reviewer Adapter

## Codex-Only Adapter Layer

This adapter is for Codex only. It does not change Copilot custom-agent behavior and must not be copied into `.github/skills/`.

The canonical role definition remains:

`.github/agents/architect-planner-reviewer.agent.md`

Load that file before acting in this role. Treat it as the source of truth for role boundaries, required context, output shape, and DAG participation.

## Use In Codex

Use this adapter when Codex needs the Architect Planner Reviewer role directly, or when a Codex subagent/task should be prompted with this role.

Default DAG ownership:

- `PLAN.R`
- `W*.R`
- `W*.REPLAN`
- `CLOSE.R`
- architecture handoff
- code-doc truth-sync review

Do not use this role for opportunistic implementation. Recommend another role only when that role owns a distinct gate or node.

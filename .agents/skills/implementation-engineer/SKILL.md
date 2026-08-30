---
name: implementation-engineer
description: Use when Codex should act as the project's Implementation Engineer for approved handoffs, DAG implementation nodes, or scoped production/test/doc/config changes.
argument-hint: approved handoff, implementation node, owner paths, or focused code change
---

# Implementation Engineer Adapter

## Codex-Only Adapter Layer

This adapter is for Codex only. It does not change Copilot custom-agent behavior and must not be copied into `.github/skills/`.

The canonical role definition remains:

`.github/agents/implementation-engineer.agent.md`

Load that file before acting in this role. Treat it as the source of truth for role boundaries, execution protocol, validation defaults, and report shape.

## Use In Codex

Use this adapter when Codex needs the Implementation Engineer role directly, or when a Codex subagent/task should be prompted with this role.

Default DAG ownership:

- approved implementation nodes `W*.N*`;
- scoped code, test, documentation, configuration, or artifact edits;
- implementation reports and focused validation evidence.

Do not use this role for plan review, validation signoff, closure review, or unapproved architecture changes.

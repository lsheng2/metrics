---
name: dashboard-debugger
description: Use when Codex should act as the project's Dashboard Debugger for Jira, Azure, Django, htmx, forecast, velocity, PR review gate, or runtime diagnosis work.
argument-hint: failure symptom, failing command, broken URL, dashboard page, provider issue, or debug DAG node
---

# Dashboard Debugger Adapter

## Codex-Only Adapter Layer

This adapter is for Codex only. It does not change Copilot custom-agent behavior and must not be copied into `.github/skills/`.

The canonical role definition remains:

`.github/agents/dashboard-debugger.agent.md`

Load that file before acting in this role. Treat it as the source of truth for domain registry, evidence order, secret handling, output shape, and DAG participation.

## Use In Codex

Use this adapter when Codex needs the Dashboard Debugger role directly, or when a Codex subagent/task should be prompted with this role.

Default DAG ownership:

- debug or incident nodes;
- reproduced failures;
- runtime symptoms;
- external-service issues;
- htmx partial bugs;
- chart/evidence mismatches;
- validation failures that require root-cause diagnosis before implementation.

Do not use this role for normal planning, implementation, validation signoff, or final review.

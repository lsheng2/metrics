---
name: lsheng2-coding-review
description: Use when Codex needs lsheng2 coding review, architectural code review, dirty code review, exact-pass iteration review, or P0-P3 review fix loops.
argument-hint: review target and exact pass count, e.g. review dirty code in 2 exact-pass iterations
---

# Lsheng2 Coding Review Adapter

## Codex-Only Adapter Layer

This adapter is for Codex only. It is maintained in this repository so projects can install it into `.agents/skills/lsheng2-coding-review/`.

Copilot should continue to use the repository root `SKILL.md` or a project-local `.github/skills/lsheng2-coding-review/SKILL.md` adapter. Do not point Copilot at this Codex adapter, and do not mirror these wrapper scripts into `.github/skills/`.

## Canonical Source

The canonical workflow remains the user-level personal skill:

`%USERPROFILE%/.copilot/skills/lsheng2-coding-review/SKILL.md`

Load that file first. If the personal skill is unavailable in a project-local environment, fall back to `.github/skills/lsheng2-coding-review/SKILL.md` only when that project-local adapter exists. In Codex, reuse the review rules, gate scripts, project-local config, receipt requirements, and exact-pass semantics, but adapt reviewer-agent invocation to the available Codex role/subagent/task tools.

## Codex Script Wrappers

Use local wrappers from this adapter root when Codex instructions say `python scripts/...`:

- `scripts/ensure_project_config.py`
- `scripts/exact_pass_gate.py`
- `scripts/review_process_report.py`
- `scripts/review_type_profiles.py`

Each wrapper forwards to the canonical script under `%USERPROFILE%/.copilot/skills/lsheng2-coding-review/scripts/` on Windows or `~/.copilot/skills/lsheng2-coding-review/scripts/` on Unix-like systems.

The scripts are mechanically usable in Codex, but reviewer execution is not identical to VS Code Copilot custom agents. Treat `reviewer_agent` as a Codex role/subagent label and record the actual model used in each gate event.

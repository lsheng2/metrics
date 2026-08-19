# Copilot Instructions

Canonical repo-level instruction entrypoint for AI coding in this repository.

## Load Order

1. Root `CLAUDE.md` for architecture, testing, frontend, and configuration rules.
2. `.github/ai-governance/README.md` and the matching BKM file when the task touches coding flow, validation, shell commands, comments, or closure claims.
3. Target module files and nearby tests before editing.
4. `.github/skills/dag-based-planning/templates/project-profile.md` when a task needs DAG-backed planning, multi-agent handoff, or review gates.

## Stable Repo Truths

1. This is a Django modular monolith for software delivery metrics.
2. Module communication goes through public APIs under each module's `app/api/` package.
3. Domain code stays framework-free and uses `@dataclass(slots=True)` for dataclasses.
4. UI code uses semantic HTML, Bulma, htmx, and Chart.js. Avoid React-style frontend architecture.
5. External tracker behavior should reuse `sd-metrics-lib` where practical.
6. Secrets belong in `.env` or deployment environment variables and must not be committed or pasted into docs, tests, or chat output.

## Implementation Rules

1. Start from the owning module and the nearest existing test.
2. Keep changes inside the module boundary unless the public API contract must change.
3. Use focused tests first: `pytest path/to/test_file.py::TestClass::test_method`.
4. Run `python manage.py check` for configuration or Django integration changes.
5. Before review of a nontrivial code wave, run `python scripts/check_file_size_limits.py --include-untracked` and `python scripts/check_diff_whitespace.py --include-untracked`.
6. Use `.github/ai-governance/closure-verification-policy.md` before making broad completion claims.

## Agent And Skill Routing

1. Use `.github/agents/architect-planner-reviewer.agent.md` for architecture plans, handoffs, and reviews.
2. Use `.github/agents/implementation-engineer.agent.md` to execute approved handoffs.
3. Use `.github/agents/validation-engineer.agent.md` for test-plan signoff and stale/wrong-owner test review.
4. Use `.github/agents/dashboard-debugger.agent.md` for runtime debugging across Django, tracker adapters, htmx partials, and templates.
5. Use `.github/skills/dag-based-planning/` for dependency-aware plans and multi-agent execution ledgers.
6. Use `.github/skills/drawio/` for complex architecture diagrams.
7. Use `.github/ai-governance/` as the local BKM library for repeatable AI coding practices.

## Local BKM Index

1. `.github/ai-governance/context-loading-policy.md` — progressive context loading.
2. `.github/ai-governance/shell-execution-policy.md` — PowerShell-first command rules on Windows.
3. `.github/ai-governance/closure-verification-policy.md` — completion, gates, and evidence rules.
4. `.github/ai-governance/code-comment-policy.md` — when comments are allowed or required.
5. `.github/ai-governance/behavioral-first-principles.md` — short behavior baseline for AI work.

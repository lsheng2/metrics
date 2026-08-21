# Copilot Instructions

Canonical repo-level instruction entrypoint for AI coding in this repository.

## Load Order

1. Root `CLAUDE.md` for architecture, testing, frontend, and configuration rules.
2. `.github/ai-governance/README.md` and the matching BKM file when the task touches coding flow, validation, shell commands, comments, or closure claims.
3. Target module files and nearby tests before editing.
4. Shared `dag-based-planning` skill plus `.github/skills/dag-based-planning/templates/project-profile.md` when a task needs DAG-backed planning, multi-agent handoff, or review gates.

## Stable Repo Truths

1. This is a Django modular monolith for software delivery metrics.
2. Module communication goes through public APIs under each module's `app/api/` package.
3. Domain code stays framework-free and uses `@dataclass(slots=True)` for dataclasses.
4. UI code uses semantic HTML, Bulma, htmx, and Chart.js. Avoid React-style frontend architecture.
5. External tracker behavior should reuse `sd-metrics-lib` where practical.
6. Secrets belong in `.env` or deployment environment variables and must not be committed or pasted into docs, tests, or chat output.

## Intel Jira MVP Routing

1. Current MVP goal: Intel Jira bug trend indicator dashboard for saved Jira scopes. Source docs: `docs/implementation-start.md`, `docs/architecture-manual.md`, and `docs/mvp-bug-trend-architecture-spec.md`.
2. M0 Intel Jira Server/Data Center PAT connectivity has passed; preserve it and do not leak credentials.
3. Next architecture gate is M1 durable Jira history: cursor, issue, snapshot, transition, calculation-run, bucket, and bucket-membership artifacts before chart polish.
4. `jira_scope_config` is the single authority for project-specific Jira semantics. Do not move workflow status, severity, component, milestone, or bug-type truth into global env vars or hardcoded calculators.
5. Bug trend pages must read local durable history/aggregate artifacts, not live-query Jira on every dashboard render. Drilldown must use the same `calculation_run_id` as the clicked chart bucket.
6. Planned owner boundaries: `jira_sync` fetches/cursors/status, `jira_history` persists issues/snapshots/transitions, `bug_metrics` owns scope config and trend buckets, and `ui_web` renders views/partials/charts.

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
5. Use the shared `dag-based-planning` skill with `.github/skills/dag-based-planning/templates/project-profile.md` for dependency-aware plans and multi-agent execution ledgers.
6. Use `.github/skills/drawio/` for complex architecture diagrams.
7. Use `.github/ai-governance/` as the local BKM library for repeatable AI coding practices.

## Local BKM Index

1. `.github/ai-governance/repo-context.md` — compact project map, owner boundaries, validation commands, and local pitfalls.
2. `.github/ai-governance/context-loading-policy.md` — progressive context loading.
3. `.github/ai-governance/shell-execution-policy.md` — PowerShell-first command rules on Windows.
4. `.github/ai-governance/closure-verification-policy.md` — completion, gates, and evidence rules.
5. `.github/ai-governance/code-comment-policy.md` — when comments are allowed or required.
6. `.github/ai-governance/behavioral-first-principles.md` — short behavior baseline for AI work.

## Local Pitfalls

1. `pytest.ini` does not include `pull_requests/tests/`; for pull-request work, run the focused `python -m pytest pull_requests/tests/... -q` command explicitly.
2. `README.md` and `CLAUDE.md` mention different dev-server ports (`8000` vs `8002`); preserve the command used by the current task or ask before standardizing docs.
3. Do not simplify Azure PR pagination in `AzurePullRequestRepository`; short/overlapping Azure pages require fixed-stride paging plus de-duplication.
4. For Intel Jira setup/current-state details, prefer links in `docs/implementation-start.md` and `docs/architecture-manual.md`; never paste `.env` secrets into docs, tests, or chat output.
5. Do not build or polish bug/feature charts before the durable Jira history and calculation-run artifacts exist and have focused validation.

## Additional requirements

- Please always answer me in Chinese. You can think in English, but when answer or conclude, please use Chinese. If any professional keywords or function name/parameters/formulas, folder/file names, it is not necessary to translate to Chinese, you can keep it in English.

# Project DAG Plan Documentation Review Overlay

This project-local overlay customizes `dag-plan-doc-review` for this repository. Keep cross-project DAG process rules in the skill-level base rule asset; put only project-specific authority, document, validation, and naming requirements here.

## Project-Specific Authority Rules

- Treat `CLAUDE.md`, `.github/copilot-instructions.md`, `.github/ai-governance/`, and `.github/skills/lsheng2-dag-based-planning/templates/project-profile.md` as the AI-workflow authority set for DAG plan reviews.
- Treat `openspec/docs/historical/implementation-start.md`, `openspec/docs/current-baseline/architecture-manual.md`, and `openspec/docs/current-baseline/bug-trend-architecture-spec.md` as the current Intel Jira bug trend MVP authority set when a plan touches `jira_sync/`, `jira_history/`, `bug_metrics/`, `ui_web/`, `ops/`, or Grafana artifacts.
- Enforce the modular-monolith owner boundaries from `CLAUDE.md`: cross-module communication goes through `*/app/api/`, domain code stays framework-free, and UI behavior stays in semantic HTML, Bulma, htmx, and Chart.js surfaces.
- A DAG plan must keep `jira_scope_config` as the single project-specific Jira semantics authority. Workflow statuses, severities, components, milestones, and bug-type truth must not move into global environment variables or hardcoded calculators.
- Bug trend dashboard plans must preserve durable-history ownership: pages and drilldowns read persisted history, calculation runs, buckets, and bucket memberships; they must not re-query live Jira during dashboard render.

## Project-Specific DAG Artifact Rules

- Use repo-relative owner paths from the project profile. Valid families include module roots, module-local tests, `openspec/docs/`, `ops/`, `scripts/`, `.github/`, `ui_web/templates/`, and `ui_web/static/` only when the node explicitly owns them.
- Record `git rev-parse HEAD` and `git status --porcelain=v1 --untracked-files=all` at plan creation. Pre-existing dirty paths must be named as baseline evidence or excluded from the plan with a reason.
- Every plan that changes bug trend evidence, export, chart catalog, Grafana JSON, parity scripts, audit behavior, or AI chart governance must name both producer and consumer surfaces, including relevant `ops/grafana/`, `scripts/`, `openspec/docs/`, and UI/API paths.
- Multi-wave plans must include `W*.REPLAN` before any later implementation wave, and the next wave must depend on that replan node. Non-`continue` refreeze decisions must record `refreeze_actions`, `updated_artifacts`, `rerun_gates`, and `post_refreeze_preflight_result`.
- Plans may use `.github/agents/*.agent.md` as routing defaults only through explicit DAG Agent Routing. Do not require all four agents for every DAG.

## Project-Specific Validation Rules

- For nontrivial code waves, require the project governance checks `python scripts/check_file_size_limits.py --include-untracked` and `python scripts/check_diff_whitespace.py --include-untracked` unless the plan records a scoped non-applicability reason.
- Require `python manage.py check` for Django settings, URL, view, template, container, or integration changes.
- Focused tests must be selected from the touched owner path. Remember that `pytest.ini` excludes `pull_requests/tests/`, so pull-request work must run explicit `python -m pytest pull_requests/tests/... -q` commands.
- Static Grafana JSON validation is artifact evidence only. Runtime Grafana or browser claims require the matching runtime check or an explicit residual risk.
- A plan touching persisted Django models, migrations, calculation artifacts, Jira sync/history, evidence membership, chart drilldowns, export, audit, or configuration semantics defaults to high risk unless `PLAN.R` accepts a narrower classification.

## Reviewer Prompt Additions

- Require the reviewer to inspect this overlay, the repo-local DAG project profile, and the authority documents relevant to the plan's owner paths.
- Require findings for any plan that uses a home/global/unrelated-repo profile as project truth, bypasses the local overlay, or treats the legacy profile path as the only source after a canonical profile exists.
- Require findings for code-doc truth drift across `CLAUDE.md`, `.github/copilot-instructions.md`, `.github/ai-governance/`, `README.md`, `openspec/docs/`, project agents, and project skill profile files when the plan changes stable behavior.

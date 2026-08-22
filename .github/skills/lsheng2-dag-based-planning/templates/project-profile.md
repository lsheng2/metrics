# Project Profile

Everything repository-specific lives here so the DAG workflow stays portable.

## Identity

- Project: Metrics Django dashboard.
- Profile source: repo-local; migrated from the legacy `.github/skills/dag-based-planning/templates/project-profile.md` path for the renamed `lsheng2-dag-based-planning` skill.
- Plan location: `docs/` for stable architecture or implementation plans; `.github/` for AI workflow/customization changes.
- Shell: PowerShell on Windows.
- Runtime: Python from the active environment; project commands use `python manage.py ...` and `python -m pytest ...`.

## Source Roots

- `tasks/`
- `forecast/`
- `velocity/`
- `pull_requests/`
- `jira_sync/`
- `jira_history/`
- `bug_metrics/`
- `ui_web/`
- `metrics/`
- `ops/`
- `scripts/`

## Owner Path Families

Legitimate `owner_paths` include source roots above plus current docs, tests, templates, static assets, configuration, and AI customization that the plan explicitly changes.

- `.github/agents/`
- `.github/skills/`
- `.github/copilot-instructions.md`
- `.github/file-size-limits.json`
- `CLAUDE.md`
- `README.md`
- `docs/`
- module-local `tests/`
- `ui_web/templates/`
- `ui_web/static/`

## Test Roots

- `tasks/tests/`
- `forecast/tests/`
- `velocity/tests/`
- `pull_requests/tests/`
- `jira_sync/tests/`
- `jira_history/tests/`
- `bug_metrics/tests/`
- `ui_web/tests/`

## Doc Truth Roots

- `CLAUDE.md`
- `README.md`
- `docs/`
- `.github/copilot-instructions.md`
- `.github/ai-governance/`
- `.github/custom-agents.md`
- `.github/agents/`
- `.github/skills/`

## Hard Gate Commands

PowerShell:

```powershell
$python = Join-Path (Get-Location) '.venv/Scripts/python.exe'
& $python scripts/check_file_size_limits.py --include-untracked
& $python scripts/check_diff_whitespace.py --include-untracked
& $python manage.py check
```

Focused tests:

```powershell
$python = Join-Path (Get-Location) '.venv/Scripts/python.exe'
& $python -m pytest tasks/tests/test_api_tasks_health.py -q
& $python -m pytest ui_web/tests/test_unit_field_filters.py -q
```

Focused test commands are examples only. Each DAG node must name the focused tests for its actual owner path before using them as closure evidence.

## Rolling-Horizon Refreeze Gates

Metrics uses the shared project-agnostic `W*.REPLAN` rule for multi-wave DAG plans: every implementation wave followed by another implementation wave needs a `W*.REPLAN` node after the wave behavior review, and the next implementation wave must depend on that replan node.

- Replan node kind or label vocabulary: use `replan-review` in checker inputs and `W*.REPLAN` in plan prose, Mermaid graphs, and ledgers.
- Checker command or review procedure that proves every implementation wave followed by another implementation wave has `W*.REPLAN`: run the copied/adapted DAG checker template with a real plan input passed through `--plan`, or record an explicit plan preflight row that checks node table, Mermaid graph, and ledger dependencies against `W*.REPLAN`. `--sample` mode is only a template self-check and is not closure evidence.
- Checker command or review procedure that proves the next implementation wave depends on the previous `W*.REPLAN`: run the copied/adapted DAG checker template with a real plan input passed through `--plan`, or record a preflight row naming the first node of the next wave and its `depends_on` edge. `--sample` mode is only a template self-check and is not closure evidence.
- Approved command/result shape for downstream predicate checks: project-profile-approved commands such as focused `python -m pytest ... -q`, `python manage.py check`, `python scripts/check_file_size_limits.py --include-untracked`, `python scripts/check_diff_whitespace.py --include-untracked`, or a plan-specific grep/query; record exact command and `PASS`/`FAIL` result.
- Approved artifact roots for `updated_artifacts` in non-`continue` decisions: existing plan-owned repo-relative paths under `docs/`, `.github/`, module-local `tests/`, `scripts/`, `ops/`, or the touched module owner paths declared by the replan node.
- Approved gate node ids or command patterns for `rerun_gates`: DAG gate node ids such as `W*.PREFLIGHT`, `W*.VA`, `W*.R`, `CLOSE.PREFLIGHT`, `CLOSE.R`, or project-profile-approved commands listed in this profile and the plan.
- Required post-refreeze preflight command/result shape: exact preflight command or method plus `result: PASS`; for plans with copied checker templates, prefer `python path/to/dag-checker-template.py --plan path/to/checker-input.json`.

Non-`continue` decisions must record `refreeze_actions`, `updated_artifacts`, `rerun_gates`, and `post_refreeze_preflight_result` before implementation continues. A Metrics plan may not claim broad closure over downstream wave feasibility when these fields are missing.

## DAG Agent Routing

Project-local custom agents are routing defaults for DAG-backed work, not mandatory participants in every plan. Choose agents by gate purpose and evidence need:

| DAG point | Default agent | Required when | Not required when |
| --- | --- | --- | --- |
| `PLAN.R` | `Architect Planner Reviewer` | Nontrivial DAG plan, architecture boundary, public API contract, owner split, or implementation handoff. | Tiny one-owner fix using a short checklist instead of DAG. |
| Implementation node `W*.N*` | `Implementation Engineer` | The plan has an approved handoff and the node changes production/test/doc/config/artifact files. | The main agent is already executing a tiny local edit, or the node is review-only / documentation-review-only and does not execute an approved implementation handoff. |
| `W*.VA` | `Validation Engineer` | High-risk authority, validation/governance change, cross-module consumer matrix, UI/runtime claim, stale/wrong-owner test risk, or nontrivial gate selection. | Low-risk text-only or single-owner cleanup where the plan names an obvious focused check. |
| `W*.R` and `CLOSE.R` | `Architect Planner Reviewer` | Behavior review, code-doc truth sync, architecture signoff, or final closure. | Exact-pass review skill already routes this role through the configured reviewer agent. |
| `W*.REPLAN` | `Architect Planner Reviewer`, with `Validation Engineer` when validation scope changed | Multi-wave refreeze, changed downstream assumptions, or amended validation gates. | Single-wave plans with no remaining implementation wave. |
| Debug or incident node | `Dashboard Debugger` | The DAG node starts from a reproduced failure, runtime symptom, Django/Jira/Grafana issue, htmx partial bug, or chart/evidence mismatch. | Planned implementation without a failing runtime symptom. |

Do not force all four agents into every DAG. Extra agents are overhead unless they own a distinct gate, evidence question, or failure mode. A DAG plan should list skipped agents with a short reason when the plan is nontrivial and the skipped role could plausibly apply.

## Scope Gate Configuration

Record at plan creation:

```powershell
git rev-parse HEAD
git status --porcelain=v1 --untracked-files=all
```

Generated or local runtime outputs may be ignored only when they are not part of the work:

- `__pycache__/`
- `.pytest_cache/`
- `db.sqlite3`
- `.coverage*`
- `screenshots/` when generated by manual browser verification

Do not add unrelated dirty files to a plan after implementation starts. Either record them as pre-existing baseline paths or create a separate node that owns them.

## Discovery Evidence

This canonical profile was migrated from the mature legacy project profile at `.github/skills/dag-based-planning/templates/project-profile.md` after the shared skill was renamed to `lsheng2-dag-based-planning`. Treat the evidence below as the current audit trail for profile facts.

| Profile Area | Evidence Used | Confidence |
| --- | --- | --- |
| Identity | `CLAUDE.md`, `README.md`, `metrics/`, Django app roots | high |
| Source roots | Workspace file tree and module directories: `tasks/`, `forecast/`, `velocity/`, `pull_requests/`, `jira_sync/`, `jira_history/`, `bug_metrics/`, `ui_web/`, `metrics/`, `ops/`, `scripts/` | high |
| Test roots | Module-local `tests/` directories present in source roots | high |
| Doc truth roots | `CLAUDE.md`, `README.md`, `docs/`, `.github/copilot-instructions.md`, `.github/ai-governance/`, `.github/agents/`, `.github/skills/` | high |
| Hard gate commands | `CLAUDE.md`, `.github/copilot-instructions.md`, and existing scripts under `scripts/` | medium; commands should still be run for each closure claim |
| Rolling-horizon refreeze gates | Shared `lsheng2-dag-based-planning` skill core and Metrics hard gate commands in this profile | medium; copied plan checkers must be adapted per plan before used as closure gates |
| DAG agent routing | `.github/custom-agents.md` and `.github/agents/*.agent.md` | high |
| Authority boundaries | `CLAUDE.md`, module structure, and public `app/api/` package convention | high |
| Consumer universe defaults | Module structure, `ui_web/` federation pattern, `ops/`, `scripts/`, docs and test directories | medium |
| Risk level defaults | Repo architecture rules, audit/export/governance patterns, and closure verification policy | medium |

## Code-Doc Truth Sync

Every DAG plan that changes code, contracts, validation behavior, operator workflow, public API, UI/user-visible behavior, configuration behavior, or AI customization must assess:

- Architecture docs: `docs/architecture-manual.md`, `docs/implementation-start.md`, and related docs under `docs/`.
- README/index surfaces: `README.md` and module-local README/AI context if present.
- AI guidance and BKM: `CLAUDE.md`, `.github/copilot-instructions.md`, `.github/ai-governance/`, `.github/custom-agents.md`, `.github/agents/`, `.github/skills/`.
- Validation docs/plans: focused tests and any implementation plan under `docs/`.

Use `update-required`, `no-doc-change`, or `deferred-with-trigger` with owner paths and reason.

## Authority Boundaries

Common authority boundaries in this repository:

- Task search and enrichment owner: `tasks/` public API plus repositories.
- Forecast owner: `forecast/` public API and domain calculators.
- Velocity owner: `velocity/` public API and calculators.
- Pull-request owner: `pull_requests/` public API and policy/review gates.
- Jira sync owner: `jira_sync/` fetches Jira data, owns sync cursors/status, and exposes sync health through public APIs and management commands.
- Jira history owner: `jira_history/` persists local issue snapshots, transitions, and history artifacts behind its public API.
- Bug metrics owner: `bug_metrics/` owns Jira scope config, bug trend calculation artifacts, evidence/export, chart catalog, renderer decision, audit, and AI chart governance.
- UI federation owner: `ui_web/facades/`, `ui_web/views/`, and `ui_web/templates/`.
- Configuration owner: `metrics/settings/defaults_metrics.py`, module `config_loader.py`, and containers.
- Tracker integration owner: module `out/` repositories and `sd-metrics-lib` integration.

## Consumer Universe Defaults

When building a DAG plan in this repository, evaluate these concrete consumer categories before implementation:

| Category | Common Metrics Surfaces |
| --- | --- |
| public API | `*/app/api/`, module `container.py`, cross-module API repository adapters |
| internal service/facade | `ui_web/facades/`, domain services, convertors, utility registries |
| UI route/template/component | `ui_web/urls.py`, `ui_web/views/`, `ui_web/templates/`, `ui_web/static/` |
| export/report | CSV/export APIs, bug evidence export, report scripts, generated evidence files |
| audit/log/event | audit models, bug trend governance events, operator-facing state transitions |
| validation script | `scripts/`, Grafana validators, file-size and whitespace checks |
| migration/schema | Django `models.py`, migrations, persisted DTO compatibility |
| background job/scheduler | management commands, sync commands, demo/start scripts |
| cache/index/search | `state/` caches, task search cache, query/result cache code |
| external artifact | `ops/`, Grafana JSON, Docker files, deployment configs |
| CLI/admin command | Django management commands, local PowerShell scripts |
| docs/operator workflow | `docs/`, `README.md`, `CLAUDE.md`, `.github/copilot-instructions.md` |
| test double/fake/fixture | module-local `tests/`, mocks, fixtures, builder helpers |

Each category should be marked `applies`, `not-applies`, or `deferred-with-trigger` in the plan. A category marked `not-applies` needs a reason when the changed authority is high risk.

## Risk Level Defaults

Default to `high` risk when a changed authority affects any of these Metrics surfaces:

- module public APIs under `*/app/api/`;
- persisted Django models, migrations, or calculation artifacts;
- config semantics, hashes, or environment/default behavior;
- evidence list, export, audit, permissions, or governance state;
- Jira sync/history, bug trend calculation artifacts, evidence membership, chart catalog, renderer decisions, or AI chart governance;
- external artifacts under `ops/`, deployment scripts, or validation scripts;
- cross-module routing through `ui_web` facades/views/templates;
- tracker integration behavior or any live/saved source data boundary.

Use `normal` only when the authority is internal to one module and has no export, audit, persistence, config, or cross-module consumer. Use `low` only for text-only or display-only changes with no behavior or contract impact.

## Initialization Follow-ups

- No current `TBD` entries.
- Keep the legacy `.github/skills/dag-based-planning/templates/project-profile.md` path only as a compatibility copy unless the project intentionally updates older agent references.
- Re-run discovery if source roots, CI, validation commands, module boundaries, or deployment artifacts change substantially.
- Before any closure claim, run or explicitly account for the hard gate commands relevant to the touched owner paths.
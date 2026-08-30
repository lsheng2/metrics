# Jira/Grafana MVP Test Strategy

## Goal

Validate the Jira/Grafana Bug Trend MVP governance plan from ingredient-level behavior to runtime UI evidence, while preserving the core architecture rule: Metrics owns Jira scope semantics, calculation artifacts, evidence contracts, chart catalog, audit, renderer decisions, and AI chart governance. Grafana and AI are consumers or proposal sources, not semantic owners.

For long-running AI-assisted implementation work, use [ai-validation-operating-model.md](ai-validation-operating-model.md) to choose the validation gate profile before editing and to phrase closure claims after validation.

## Scope

This strategy covers:

- Jira saved scope config, scope audit, local Jira history, sync health, calculation health.
- Bug Trend chart data, evidence list, list-local filters, CSV export, audit events.
- Chart Catalog, EvidenceContract, renderer route decision, Grafana C-stock artifacts, and Grafana link-out evidence.
- AI draft chart validation, personal publish, and cloud approval boundary.
- Browser-visible Bug Trend behavior and runtime C0/C1 evidence records.

This strategy does not cover unrelated velocity, forecast, task board, or pull-request features except through repository-wide smoke/full test gates.

## Validation Layers

| Layer | Purpose | Primary Commands Or Files | Closure Standard |
| --- | --- | --- | --- |
| Ingredient/domain | Validate pure business rules and module-owned API contracts. | `bug_metrics/tests/`, `jira_history/tests/`, `jira_sync/tests/` | Each authority has focused positive and negative tests at its owner. |
| Integration/facade | Validate cross-module transport without moving ownership into UI. | `ui_web/tests/test_api_bug_trend_facade.py`, `ui_web/tests/test_bug_trend_*` | UI/facade transports API-owned truth and does not recompute it. |
| Artifact/governance | Validate Grafana artifacts, C0/C1 evidence records, file hygiene, and docs-gates. | `scripts/validate_grafana_artifacts.py`, `scripts/check_c0_validation_evidence.py`, `scripts/check_c1_evidence_link_evidence.py`, hygiene scripts | External artifacts cannot bypass Metrics-owned APIs or omit required evidence parameters. |
| Browser/UI | Validate user-visible chart/evidence behavior and Chart.js rendering. | `ui_web/tests/test_browser_bug_trend_dashboard.py`, local browser smoke | Dashboard renders nonblank charts, evidence state changes correctly, unavailable states are visible. |
| Runtime Grafana | Validate local Grafana dashboard render and link-out evidence behavior. | `openspec/docs/validation/c0-validation-closure-evidence.md`, `openspec/docs/validation/c1-evidence-link-validation-evidence.md` plus checkers | Runtime evidence documents contain passed records and checker scripts reject stale/pending claims. |
| Full local | Detect broad regressions outside the MVP slice. | [gate-and-ci-plan.md](gate-and-ci-plan.md) `Full Local Gate` | Default pytest, explicit non-`pytest.ini` roots, Django check, and hygiene gates pass. |
| Release | Validate merge/release readiness. | [gate-and-ci-plan.md](gate-and-ci-plan.md) `Release Gate` | Full local, artifact, browser, and runtime evidence gates pass. |

## Risk Model

Treat a contract as high risk when it affects any of these surfaces:

- persisted Django models or migrations;
- module public APIs under `*/app/api/`;
- Jira sync/history, scope config, calculation run, evidence membership, or export;
- `BugTrendPageQueryState`, `chart_id`, `calculation_run_id`, `bucket`, `series`, `allowed_series_names`, or list-local filters;
- `BugTrendAuditEvent`, chart publish state, AI chart validation, or cloud approval boundary;
- Grafana JSON, approved data surface allowlist, parity checker, or evidence link;
- UI route/template behavior that affects chart, evidence, export, scope config, or Data Health.

High-risk contracts require one negative check per concrete consumer or an explicit non-goal reason.

## Contract Propagation Policy

Every new or changed authority field must be tracked across producers and consumers.

| Authority Field | Producer | Required Consumers | Required Negative Checks |
| --- | --- | --- | --- |
| `scope_id` | Scope selector, scope config API, Grafana variable | chart-data API, evidence API, export API, Data Health, scope config, Grafana dashboard | malformed id returns 400; disabled scope cannot become chart source; wrong scope cannot expose evidence. |
| `begin` / `end` | Page query, Grafana variables | chart-data API, evidence API, export API, parity checker | malformed dates return 400; uncovered ranges do not claim current chart/evidence. |
| `calculation_run_id` | `bug_metrics` calculation run | evidence list, export, chart metadata, C0/C1 evidence | evidence/export remains pinned when newer run exists; stale config run is rejected for current semantics. |
| `chart_id` | Chart Catalog, selector, Grafana artifact | chart-data API, evidence API, export API, Grafana links, parity checker, validator, audit | unknown/unpublished chart returns 400; non-default chart is not silently treated as default. |
| `allowed_series_names` | Chart Catalog `chart_spec.series` | range evidence, bucket evidence, bucket-series evidence, export | selected `series` cannot bypass chart spec; unknown AI series rejected before publication. |
| `evidence_capability` | EvidenceContract | chart selector, evidence panel, export/link policy | `summary_only` charts do not render ticket-level evidence. |
| `event_type` / audit fields | `bug_metrics` audit APIs | scope config, export, chart draft/validation/publish flows | governance action cannot complete without audit event. |

## Coverage Closure Criteria

A Jira/Grafana MVP change can be closed only when all of the following are true:

1. The owning module has focused tests for the authority it owns.
2. Every concrete consumer path appears in either a focused test, artifact validator, browser test, or runtime evidence checker.
3. Each high-risk consumer has a negative check or a documented non-goal.
4. Grafana artifacts pass the allowlist validator and do not encode semantic SQL or Jira table access.
5. Browser-level behavior is covered either by automated Playwright tests or by a C0/C1 evidence record checked by script.
6. `python manage.py check`, file-size, and whitespace gates pass for nontrivial changes.
7. Broad closure claims name unverified residual risks, especially when runtime Grafana cannot be run in CI.

## AI-Assisted Closure Addendum

Every AI-assisted feature or fix must record the selected gate profile: `focused`, `feature`, `feature-ui`, `artifact`, `governance`, `runtime`, or `release`. If a test or reviewer finds a defect, the next fix must expand the failure class across sibling entry points before claiming closure.

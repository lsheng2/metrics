# AI-Assisted Validation Operating Model

## Purpose

This document defines how humans and AI agents should validate long-running work in this repository. It turns validation from an after-the-fact test list into an operating model: every AI-assisted change must identify the authority it changes, the consumers that can observe it, and the gate profile that can reject an unsafe implementation.

The core rule is simple:

```text
Do not close from intent. Close from a changed-authority matrix plus executed gates.
```

## Operating Principles

1. Validate the owner first. The module that owns a rule must have the first focused test for that rule.
2. Validate consumers next. A value produced but never consumed is not a feature; a value consumed but not produced is a broken contract.
3. Treat missing coverage as a finding. A green suite only proves the checks that actually ran.
4. Expand the failure class. A reviewer finding is a sample, not the full boundary.
5. Separate runtime claims from artifact claims. A valid Grafana JSON file is not the same thing as a rendered Grafana dashboard.
6. Prefer explicit non-goals over silence. If a consumer is not covered, name why and what would trigger coverage.

## AI Change Classification

Before editing, classify the change into the highest applicable category.

| Change Type | Applies When | Minimum Gate Profile |
| --- | --- | --- |
| Ingredient | Pure calculator, parser, mapper, validator, or utility. | `focused` |
| API contract | `*/app/api/` DTOs, service methods, query state, public module API. | `feature` |
| Cross-module | A value crosses from one app into another app, usually through `ui_web` facade or API repository. | `feature` |
| UI behavior | View, template, htmx, Chart.js, evidence table, form, route, or user-visible state. | `feature-ui` |
| External artifact | Grafana JSON, deployment artifact, data-source allowlist, parity script, runtime evidence document. | `artifact` |
| Governance | Audit, export, approval, AI validation, chart publication, exact-pass review, policy gate. | `governance` |
| Runtime claim | Any statement that the browser, live API, local demo, or Grafana works end to end. | `runtime` |
| Release | Merge/release readiness, broad branch health, or final closure. | `release` |

If a change fits multiple categories, use the strictest gate profile. For example, a `chart_id` change touching API, UI, export, and Grafana uses `governance` plus `runtime` when a runtime claim is made.

## Required Pre-Edit Validation Shape

For nontrivial AI-assisted changes, capture this before the first edit:

| Field | Required Answer |
| --- | --- |
| Owner path | The module/file that owns the behavior. |
| Changed authority | Field, state, contract, API, route, artifact, or invariant being changed. |
| Producer | Where the value or behavior is created. |
| Consumers | Concrete code paths, templates, scripts, artifacts, docs, and tests that consume it. |
| Falsifiable hypothesis | One local statement the first edit is meant to prove or repair. |
| First focused check | The cheapest command that can reject the hypothesis. |
| Gate profile | One of the profiles below. |

Do not start broad implementation until this table can be filled for the current slice. For tiny local fixes, the table may be a short note in chat rather than a new document.

## Gate Profiles

### `focused`

Use for single-owner fixes.

Minimum gates:

```powershell
& .venv\Scripts\python.exe -m pytest <nearest-test-file-or-test-node> -q
```

Add `python manage.py check` only if Django config, URL routing, models, views, or templates changed.

### `feature`

Use when a feature changes producer and consumer code but does not make browser/runtime claims.

Minimum gates:

```powershell
& .venv\Scripts\python.exe -m pytest <producer-test-file> <consumer-test-file> -q
& .venv\Scripts\python.exe manage.py check
```

Required review checks:

- at least one negative test for the changed authority;
- test doubles updated when public API shape changes;
- every new symbol has one production call site or an explicit non-goal.

### `feature-ui`

Use when user-visible Bug Trend UI, htmx, template state, chart state, or evidence UI changes.

Minimum gates:

```powershell
& .venv\Scripts\python.exe -m pytest <producer-test-file> <ui-test-file> -q
& .venv\Scripts\python.exe -m pytest ui_web\tests\test_browser_bug_trend_dashboard.py -q
& .venv\Scripts\python.exe manage.py check
```

Browser tests are required when a claim depends on rendered Chart.js output, clickable evidence behavior, form submission, htmx swapping, or visible error/empty state.

### `artifact`

Use for Grafana JSON, approved API surfaces, parity checks, deployment artifacts, or evidence documents.

Minimum gates:

```powershell
& .venv\Scripts\python.exe -m pytest bug_metrics\tests\test_grafana_data_surface_contract.py bug_metrics\tests\test_grafana_bug_trend_parity.py -q
& .venv\Scripts\python.exe scripts\validate_grafana_artifacts.py --artifact-root ops\grafana --allowlist openspec/docs/current-baseline/grafana-approved-data-surfaces.json
```

If C0/C1 evidence documents or checkers change, also run:

```powershell
& .venv\Scripts\python.exe -m pytest bug_metrics\tests\test_c0_validation_evidence_checker.py bug_metrics\tests\test_c1_evidence_link_checker.py -q
& .venv\Scripts\python.exe scripts\check_c0_validation_evidence.py --evidence docs\c0-validation-closure-evidence.md
& .venv\Scripts\python.exe scripts\check_c1_evidence_link_evidence.py --evidence docs\c1-evidence-link-validation-evidence.md
```

### `governance`

Use for audit, export, approval, AI validation, chart catalog, evidence contracts, or architecture boundary changes.

Minimum gates:

```powershell
& .venv\Scripts\python.exe -m pytest bug_metrics\tests ui_web\tests\test_api_bug_trend_facade.py ui_web\tests\test_bug_trend_views.py ui_web\tests\test_bug_trend_fact_table_ui.py ui_web\tests\test_bug_trend_chart_selector_views.py ui_web\tests\test_bug_trend_api_contracts.py ui_web\tests\test_data_health_views.py jira_history\tests jira_sync\tests -q
& .venv\Scripts\python.exe scripts\validate_grafana_artifacts.py --artifact-root ops\grafana --allowlist openspec/docs/current-baseline/grafana-approved-data-surfaces.json
& .venv\Scripts\python.exe manage.py check
```

Use `lsheng2-coding-review` exact-pass review when the change adds or changes a high-risk authority, crosses module boundaries, or changes validation/governance rules.

### `runtime`

Use when claiming the local app, browser flow, or Grafana runtime works.

Minimum gates:

```powershell
& .venv\Scripts\python.exe -m pytest ui_web\tests\test_browser_bug_trend_dashboard.py -q
& .venv\Scripts\python.exe scripts\check_c0_validation_evidence.py --evidence docs\c0-validation-closure-evidence.md
& .venv\Scripts\python.exe scripts\check_c1_evidence_link_evidence.py --evidence docs\c1-evidence-link-validation-evidence.md
```

Runtime evidence must be regenerated or explicitly revalidated when live URLs, Grafana artifacts, C0/C1 schema, chart data shape, or evidence-link semantics change.

### `release`

Use before merge to default branch or broad release claims.

Minimum gates: run the `Release Gate` defined in [gate-and-ci-plan.md](gate-and-ci-plan.md). That document is the command authority for release validation.

## Finding-Class Expansion

When a review or test finds a bug, expand it before patching the next line of code.

| Found Issue | Required Expansion |
| --- | --- |
| Malformed request input | Check sibling GET, POST, JSON API, export, and Grafana-facing routes. |
| Missing `chart_id` propagation | Check chart-data, evidence, export, Grafana target, Grafana link, parity script, validator, and audit. |
| Evidence mismatch | Check visible range, bucket, bucket-series, list-local filters, export, and stale-run behavior. |
| Missing audit event | Enumerate every action in the same governance family and test each event. |
| Stale or wrong run | Check chart metadata, evidence, export, Data Health, and C0/C1 evidence. |
| Validator accepts unsafe artifact | Add one positive fixture and at least one negative fixture that would otherwise pass syntax-only checks. |
| UI error state missing | Check page view, partial view, JSON API, and browser-visible copy. |

The fix is not closed until the expanded sibling entry points are either tested or explicitly rejected as non-goals.

## Closure Claim Language

Use precise claims:

- `focused gate passed` means the touched owner test passed.
- `MVP governance gate passed` means the commands in [gate-and-ci-plan.md](gate-and-ci-plan.md) passed for the Jira/Grafana scope.
- `runtime evidence passed` means the C0/C1 evidence docs were current and their checkers passed.
- `full local gate passed` means default pytest, explicit non-`pytest.ini` roots, Django check, and hygiene gates passed.
- `release gate passed` means the `Release Gate` in [gate-and-ci-plan.md](gate-and-ci-plan.md) passed, including full local, artifact, browser, and runtime evidence gates.

Do not say `all tests passed` unless both default pytest and explicit excluded roots were run and passed in the same closure window. Do not say `Grafana runtime validated` when only static artifact validation or evidence-document checking ran.

## CI Evolution Path

1. Add separate CI jobs for default pytest, explicit module roots, Django/hygiene, Grafana artifacts, and browser tests.
2. Keep runtime Grafana as checked evidence until a service-backed CI job can start Grafana and import the dashboard.
3. Add an automated C0/C1 evidence regeneration script before calling Grafana runtime validation fully automated.
4. Add a validation-matrix checker only after the contract matrix stabilizes enough to avoid noisy false positives.

## AI Agent Responsibilities

Before editing, the AI agent must name the gate profile and first focused check. After editing, the next action must be that focused check when it exists. Before final response, the AI agent must report:

- changed owner paths;
- validation commands actually run;
- failures encountered and fixed;
- what was not verified;
- whether any dirty files remain outside the scoped change.

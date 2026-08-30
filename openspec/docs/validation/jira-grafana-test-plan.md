# Jira/Grafana MVP Test Plan

## Current Status

The Jira/Grafana MVP governance plan is implemented through P3 and has local validation evidence. The current automated baseline includes focused contract tests, UI/facade tests, Grafana artifact validation, Django configuration checks, Playwright browser tests, and C0/C1 evidence checkers.

Latest local validation snapshot:

| Gate | Result |
| --- | --- |
| Focused Bug Metrics/UI/Grafana governance pytest slice | `113 passed` |
| Additional non-`pytest.ini` MVP roots and checker tests | `37 passed` |
| Grafana artifact validator | `PASS grafana artifacts checked=1` |
| Django system check | `System check identified no issues` |
| Playwright Bug Trend browser tests | `4 passed` |
| C0 runtime closure evidence checker | `PASS c0 validation evidence nodes=4` |
| C1 evidence-link checker | `PASS c1 evidence-link validation nodes=4` |

## Test Waves

### W0 - Ingredient Contract Tests

Owner paths:

- `bug_metrics/app/api/`
- `bug_metrics/models.py`
- `jira_history/app/api/`
- `jira_sync/app/api/`

Required command:

```powershell
& .venv\Scripts\python.exe -m pytest bug_metrics\tests\test_api_bug_trend_contracts.py bug_metrics\tests\test_api_scope_config.py bug_metrics\tests\test_api_scope_audit.py bug_metrics\tests\test_api_bug_trend_data_health.py bug_metrics\tests\test_bug_trend_page_query_state.py bug_metrics\tests\test_api_evidence_export.py bug_metrics\tests\test_api_chart_catalog.py bug_metrics\tests\test_api_ai_chart_governance.py jira_history\tests\test_api_scope_audit_facts.py jira_sync\tests\test_api_jira_sync_data_health.py jira_sync\tests\test_sync_jira_scope_command.py bug_metrics\tests\test_c0_validation_evidence_checker.py bug_metrics\tests\test_c1_evidence_link_checker.py bug_metrics\tests\test_grafana_bug_trend_parity.py -q
```

Exit criteria:

- Scope config semantics flow only through `JiraScopeConfig`.
- Scope audit reads local history and does not mutate data.
- Calculation and sync health read owner artifacts and do not trigger recovery actions.
- Evidence and export are pinned to calculation runs and active chart state.
- Chart Catalog, EvidenceContract, renderer decision, and AI governance enforce negative cases.

### W1 - UI And Facade Tests

Owner paths:

- `ui_web/facades/`
- `ui_web/views/`
- `ui_web/templates/`
- `ui_web/urls.py`

Required command:

```powershell
& .venv\Scripts\python.exe -m pytest ui_web\tests\test_api_bug_trend_facade.py ui_web\tests\test_bug_trend_views.py ui_web\tests\test_bug_trend_scope_config_views.py ui_web\tests\test_bug_trend_scope_audit_views.py ui_web\tests\test_bug_trend_fact_table_ui.py ui_web\tests\test_bug_trend_chart_selector_views.py ui_web\tests\test_bug_trend_api_contracts.py ui_web\tests\test_data_health_views.py -q
```

Exit criteria:

- UI exposes but does not recompute API-owned truth.
- Scope config, audit, chart selector, evidence filters, export link, malformed API requests, and Data Health render expected states.
- `chart_id` is preserved through chart-data, evidence, and export routes.

### W2 - Grafana Artifact And Governance Tests

Owner paths:

- `ops/grafana/`
- `openspec/docs/current-baseline/grafana-approved-data-surfaces.json`
- `scripts/validate_grafana_artifacts.py`
- `scripts/compare_grafana_bug_trend_parity.py`

Required commands:

```powershell
& .venv\Scripts\python.exe -m pytest bug_metrics\tests\test_grafana_data_surface_contract.py bug_metrics\tests\test_grafana_bug_trend_parity.py -q
& .venv\Scripts\python.exe scripts\validate_grafana_artifacts.py --artifact-root ops\grafana --allowlist openspec/docs/current-baseline/grafana-approved-data-surfaces.json
```

Run-selected reference parity command, required when claiming live local Grafana parity for a seeded or real calculation run. The script uses the supplied run as the expected reference and verifies the chart-data API response selects the same calculation run and chart payload:

```powershell
& .venv\Scripts\python.exe scripts\compare_grafana_bug_trend_parity.py --calculation-run-id <run-id> --artifact ops\grafana\bug_trend_dashboard.json --begin <begin> --end <end>
```

Exit criteria:

- Grafana uses only approved Metrics-owned HTTP API surfaces.
- Grafana does not read raw Jira tables, lifecycle semantics, or arbitrary SQL.
- Evidence links include `scope_id`, `begin`, `end`, `run`, `bucket`, `series`, and `chart_id` where applicable.
- Parity compares the chart definition actually named by the artifact, not only the default chart.

### W3 - Browser And Runtime Evidence Tests

Owner paths:

- `ui_web/tests/test_browser_bug_trend_dashboard.py`
- `openspec/docs/validation/c0-validation-closure-evidence.md`
- `openspec/docs/validation/c1-evidence-link-validation-evidence.md`
- `scripts/check_c0_validation_evidence.py`
- `scripts/check_c1_evidence_link_evidence.py`

Required commands:

```powershell
& .venv\Scripts\python.exe -m pytest ui_web\tests\test_browser_bug_trend_dashboard.py -q
& .venv\Scripts\python.exe scripts\check_c0_validation_evidence.py --evidence docs\c0-validation-closure-evidence.md
& .venv\Scripts\python.exe scripts\check_c1_evidence_link_evidence.py --evidence docs\c1-evidence-link-validation-evidence.md
```

Exit criteria:

- Browser test proves a nonblank Chart.js chart and evidence rendering for mock Jira-derived data.
- C0 evidence proves real local runtime reference UI and Grafana render checks were performed.
- C1 evidence proves Grafana link-out evidence resolves to Metrics evidence rows with matching row count/title.

### W4 - Full Local And Release Gates

Use [gate-and-ci-plan.md](gate-and-ci-plan.md) as the command authority for `Full Local Gate` and `Release Gate`. Do not copy a separate release command list into this plan; this prevents full/release gates from drifting across validation documents.

Important note: `pytest.ini` currently includes `tasks/tests`, `forecast/tests`, `velocity/tests`, and `ui_web/tests`. It does not include every app-specific test root. CI and local full gates must explicitly run `bug_metrics/tests`, `jira_history/tests`, `jira_sync/tests`, and `pull_requests/tests` as defined in [gate-and-ci-plan.md](gate-and-ci-plan.md).

## Release Blocking Criteria

Block merge when any of these fail:

- focused owner tests for changed code;
- Grafana artifact validator for changed Grafana/API surface artifacts;
- C0/C1 evidence checker when runtime evidence is claimed;
- browser tests for chart/evidence UI changes;
- `manage.py check` for Django integration/config changes;
- file-size or whitespace gates for nontrivial changes;
- exact-pass review gate when requested for architecture/governance changes.

## Residual Risk

The strongest remaining risk is that local Grafana runtime rendering is not yet a normal pytest-only CI job. It is covered by C0/C1 checked evidence records and artifact validators, but a hosted CI job would need a Grafana service plus the Infinity datasource to make runtime Grafana rendering fully automatic.

# Validation Documentation Index

This folder is the validation source of truth for the Jira/Grafana Bug Trend MVP governance plan.

## Documents

| Document | Purpose |
| --- | --- |
| [test-strategy.md](test-strategy.md) | Overall validation strategy, risk model, layers, and coverage policy. |
| [ai-validation-operating-model.md](ai-validation-operating-model.md) | Long-term AI-assisted validation model: change classification, gate profiles, finding expansion, and closure wording. |
| [jira-grafana-mvp-test-plan.md](jira-grafana-mvp-test-plan.md) | Execution plan for Jira/Grafana MVP validation from ingredient tests through runtime evidence. |
| [test-case-catalog.md](test-case-catalog.md) | Categorized inventory of existing and planned test cases mapped to code paths and contracts. |
| [gate-and-ci-plan.md](gate-and-ci-plan.md) | Local gates, full gates, proposed CI jobs, and merge-blocking policy. |
| [e2e-runtime-runbook.md](e2e-runtime-runbook.md) | Browser, Grafana, C0, and C1 runtime validation runbook. |

## Current Validation Snapshot

Last verified on 2026-08-21 in the local workspace:

```powershell
& .venv\Scripts\python.exe -m pytest bug_metrics\tests\test_api_bug_trend_contracts.py bug_metrics\tests\test_api_scope_config.py bug_metrics\tests\test_api_scope_audit.py bug_metrics\tests\test_api_bug_trend_data_health.py bug_metrics\tests\test_bug_trend_page_query_state.py bug_metrics\tests\test_api_evidence_export.py bug_metrics\tests\test_api_chart_catalog.py bug_metrics\tests\test_api_ai_chart_governance.py bug_metrics\tests\test_grafana_data_surface_contract.py ui_web\tests\test_bug_trend_views.py ui_web\tests\test_bug_trend_scope_config_views.py ui_web\tests\test_bug_trend_scope_audit_views.py ui_web\tests\test_bug_trend_fact_table_ui.py ui_web\tests\test_bug_trend_chart_selector_views.py ui_web\tests\test_bug_trend_api_contracts.py ui_web\tests\test_data_health_views.py ui_web\tests\test_api_bug_trend_facade.py -q
# 113 passed

& .venv\Scripts\python.exe -m pytest jira_history\tests\test_api_scope_audit_facts.py jira_sync\tests\test_api_jira_sync_data_health.py jira_sync\tests\test_sync_jira_scope_command.py bug_metrics\tests\test_c0_validation_evidence_checker.py bug_metrics\tests\test_c1_evidence_link_checker.py bug_metrics\tests\test_grafana_bug_trend_parity.py -q
# Additional non-pytest.ini MVP roots and evidence-checker tests must pass before closure

& .venv\Scripts\python.exe scripts\validate_grafana_artifacts.py --artifact-root ops\grafana --allowlist docs\grafana-approved-data-surfaces.json
# PASS grafana artifacts checked=1

& .venv\Scripts\python.exe manage.py check
# System check identified no issues

& .venv\Scripts\python.exe -m pytest ui_web\tests\test_browser_bug_trend_dashboard.py -q
# 4 passed

& .venv\Scripts\python.exe scripts\check_c0_validation_evidence.py --evidence docs\c0-validation-closure-evidence.md
# PASS c0 validation evidence nodes=4

& .venv\Scripts\python.exe scripts\check_c1_evidence_link_evidence.py --evidence docs\c1-evidence-link-validation-evidence.md
# PASS c1 evidence-link validation nodes=4
```

The `113 passed` command is the `bug_metrics`/`ui_web` governance slice plus Grafana surface tests. It is not the whole MVP closure gate by itself because `pytest.ini` does not include `bug_metrics`, `jira_history`, `jira_sync`, or `pull_requests` by default.

## Ownership

- Test strategy owner: validation architecture for the Metrics dashboard.
- Contract owner: each module that owns the authority under test.
- Runtime evidence owner: the person running local browser/Grafana validation must update the evidence documents and run the matching checker.
- AI-assisted implementation owner: the agent or human making the change must choose a gate profile from [ai-validation-operating-model.md](ai-validation-operating-model.md) before claiming closure.

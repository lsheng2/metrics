# Gate And CI Plan

## Gate Classes

The gate classes below are the concrete command layer for the AI-assisted operating model in [ai-validation-operating-model.md](ai-validation-operating-model.md). New AI-assisted changes should first classify the change, then run the matching gate profile.

| Gate Class | When To Run | Required Commands | Blocks Merge |
| --- | --- | --- | --- |
| Focused owner gate | After every code change in a module or script. | The smallest relevant `pytest` command for touched owner paths. | Yes. |
| Jira/Grafana MVP governance gate | Before claiming MVP closure or pushing governance changes. | Focused suite listed below, Grafana validator, `manage.py check`. | Yes. |
| Browser gate | For chart, htmx, template, evidence interaction, or visual rendering changes. | `ui_web/tests/test_browser_bug_trend_dashboard.py`. | Yes when UI behavior changed. |
| Runtime evidence gate | When claiming local C0/C1 runtime closure. | C0/C1 checker scripts after evidence docs are updated. | Yes for runtime closure claims. |
| Full local gate | Before broad local closure claims. | Default pytest, explicit non-`pytest.ini` roots, Django check, hygiene scripts. | Yes. |
| Release gate | Before merge to default branch or release branch. | Full local gate plus Grafana artifact, browser, and runtime evidence gates. | Yes. |
| Exact-pass review gate | For architecture/governance-heavy changes or explicit user request. | `lsheng2-coding-review` gate with required clean passes. | Yes when requested or declared in plan. |

## Local MVP Governance Gate

Run this before saying the Jira/Grafana MVP governance plan is still green. The first command covers the `bug_metrics`/`ui_web` governance slice; the second command covers additional MVP roots that `pytest.ini` does not include by default.

```powershell
& .venv\Scripts\python.exe -m pytest bug_metrics\tests\test_api_bug_trend_contracts.py bug_metrics\tests\test_api_scope_config.py bug_metrics\tests\test_api_scope_audit.py bug_metrics\tests\test_api_bug_trend_data_health.py bug_metrics\tests\test_bug_trend_page_query_state.py bug_metrics\tests\test_api_evidence_export.py bug_metrics\tests\test_api_chart_catalog.py bug_metrics\tests\test_api_ai_chart_governance.py bug_metrics\tests\test_grafana_data_surface_contract.py ui_web\tests\test_bug_trend_views.py ui_web\tests\test_bug_trend_scope_config_views.py ui_web\tests\test_bug_trend_scope_audit_views.py ui_web\tests\test_bug_trend_fact_table_ui.py ui_web\tests\test_bug_trend_chart_selector_views.py ui_web\tests\test_bug_trend_api_contracts.py ui_web\tests\test_data_health_views.py ui_web\tests\test_api_bug_trend_facade.py -q
& .venv\Scripts\python.exe -m pytest jira_history\tests\test_api_scope_audit_facts.py jira_sync\tests\test_api_jira_sync_data_health.py jira_sync\tests\test_sync_jira_scope_command.py bug_metrics\tests\test_c0_validation_evidence_checker.py bug_metrics\tests\test_c1_evidence_link_checker.py bug_metrics\tests\test_grafana_bug_trend_parity.py -q
& .venv\Scripts\python.exe scripts\validate_grafana_artifacts.py --artifact-root ops\grafana --allowlist docs\grafana-approved-data-surfaces.json
& .venv\Scripts\python.exe manage.py check
```

Current observed result on 2026-08-21: first pytest command `113 passed`; second pytest command `37 passed`; Grafana validator PASS; Django check PASS.

## Browser And Runtime Gate

```powershell
& .venv\Scripts\python.exe -m pytest ui_web\tests\test_browser_bug_trend_dashboard.py -q
& .venv\Scripts\python.exe scripts\check_c0_validation_evidence.py --evidence docs\c0-validation-closure-evidence.md
& .venv\Scripts\python.exe scripts\check_c1_evidence_link_evidence.py --evidence docs\c1-evidence-link-validation-evidence.md
```

Current observed result on 2026-08-21: `4 passed`, C0 checker PASS, C1 checker PASS.

## Full Local Gate

```powershell
& .venv\Scripts\python.exe -m pytest -q
& .venv\Scripts\python.exe -m pytest bug_metrics\tests jira_history\tests jira_sync\tests pull_requests\tests -q
& .venv\Scripts\python.exe manage.py check
& .venv\Scripts\python.exe scripts\check_file_size_limits.py --include-untracked
& .venv\Scripts\python.exe scripts\check_diff_whitespace.py --include-untracked
```

The second pytest command is explicit because `pytest.ini` does not include all module-local test roots.

## Release Gate

Use this before merge to the default branch, release branches, or broad release-readiness claims.

```powershell
& .venv\Scripts\python.exe -m pytest -q
& .venv\Scripts\python.exe -m pytest bug_metrics\tests jira_history\tests jira_sync\tests pull_requests\tests -q
& .venv\Scripts\python.exe scripts\validate_grafana_artifacts.py --artifact-root ops\grafana --allowlist docs\grafana-approved-data-surfaces.json
& .venv\Scripts\python.exe -m pytest ui_web\tests\test_browser_bug_trend_dashboard.py -q
& .venv\Scripts\python.exe scripts\check_c0_validation_evidence.py --evidence docs\c0-validation-closure-evidence.md
& .venv\Scripts\python.exe scripts\check_c1_evidence_link_evidence.py --evidence docs\c1-evidence-link-validation-evidence.md
& .venv\Scripts\python.exe manage.py check
& .venv\Scripts\python.exe scripts\check_file_size_limits.py --include-untracked
& .venv\Scripts\python.exe scripts\check_diff_whitespace.py --include-untracked
```

## Proposed CI Jobs

No `.github/workflows/` files are currently present in this repository. When CI is added, use these jobs.

### Job 1 - Python Unit And API

Trigger: every PR and push to protected branches.

Commands:

```powershell
& .venv\Scripts\python.exe -m pytest tasks\tests forecast\tests velocity\tests ui_web\tests -q
& .venv\Scripts\python.exe -m pytest bug_metrics\tests jira_history\tests jira_sync\tests pull_requests\tests -q
```

### Job 2 - Django And Hygiene

Trigger: every PR.

Commands:

```powershell
& .venv\Scripts\python.exe manage.py check
& .venv\Scripts\python.exe scripts\check_file_size_limits.py --include-untracked
& .venv\Scripts\python.exe scripts\check_diff_whitespace.py --include-untracked
```

### Job 3 - Grafana Artifact Governance

Trigger: every PR that touches `ops/grafana/`, `scripts/validate_grafana_artifacts.py`, `docs/grafana-approved-data-surfaces.json`, `bug_metrics/app/api/`, or `ui_web/views/bug_trend_view.py`.

Commands:

```powershell
& .venv\Scripts\python.exe -m pytest bug_metrics\tests\test_grafana_data_surface_contract.py bug_metrics\tests\test_grafana_bug_trend_parity.py -q
& .venv\Scripts\python.exe scripts\validate_grafana_artifacts.py --artifact-root ops\grafana --allowlist docs\grafana-approved-data-surfaces.json
```

Run-selected reference parity is a local/runtime gate unless CI seeds a known `BugTrendCalculationRun` id. The script uses the provided run as the expected reference and rejects mismatched API payload `calculation_run_id` or chart data:

```powershell
& .venv\Scripts\python.exe scripts\compare_grafana_bug_trend_parity.py --calculation-run-id <run-id> --artifact ops\grafana\bug_trend_dashboard.json --begin <begin> --end <end>
```

### Job 4 - Browser UI

Trigger: every PR that touches `ui_web/views/`, `ui_web/templates/`, `ui_web/static/`, `bug_metrics/app/api/`, or chart/evidence tests.

Commands:

```powershell
& .venv\Scripts\python.exe -m pytest ui_web\tests\test_browser_bug_trend_dashboard.py -q
```

### Job 5 - Runtime Evidence Document Gate

Trigger: every PR that changes C0/C1 evidence documents or checker scripts.

Commands:

```powershell
& .venv\Scripts\python.exe -m pytest bug_metrics\tests\test_c0_validation_evidence_checker.py bug_metrics\tests\test_c1_evidence_link_checker.py -q
& .venv\Scripts\python.exe scripts\check_c0_validation_evidence.py --evidence docs\c0-validation-closure-evidence.md
& .venv\Scripts\python.exe scripts\check_c1_evidence_link_evidence.py --evidence docs\c1-evidence-link-validation-evidence.md
```

### Job 6 - Optional Grafana Runtime Automation

Trigger: nightly or manually dispatched after Grafana service setup is automated.

Requirements:

- Grafana installed or service container available.
- Infinity datasource plugin installed.
- Django backend seeded with Bug Trend demo data.
- `ops/grafana/bug_trend_dashboard.json` imported.

Commands:

```powershell
& .venv\Scripts\python.exe scripts\regenerate_c0_c1_runtime_evidence.py
& .venv\Scripts\python.exe scripts\check_c0_validation_evidence.py --evidence docs\c0-validation-closure-evidence.md
& .venv\Scripts\python.exe scripts\check_c1_evidence_link_evidence.py --evidence docs\c1-evidence-link-validation-evidence.md
```

`scripts\regenerate_c0_c1_runtime_evidence.py` is a planned script, not a current repository file. Until it exists, this job is a design target rather than an executable CI gate.

## Exact-Pass Review Gate

Use the `lsheng2-coding-review` skill for architecture-heavy changes. A clean pass means:

- configured reviewer agent returns `VERDICT: PASS`;
- P0/P1/P2/P3 counts are all zero;
- the gate script records the PASS;
- no pending finding remains open;
- required consecutive clean passes are reached.

For each FAIL, the next review result must include a closure ledger for all pending findings. Do not claim review closure from chat prose alone.

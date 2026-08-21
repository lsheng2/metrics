# Jira/Grafana MVP Test Case Catalog

This catalog groups existing and planned test cases by validation layer. Test code stays in module-owned `tests/` folders; this document is the cross-cutting index under `docs/validation/`.

## Ingredient And Contract Tests

| Category | Test File | Covered Behavior |
| --- | --- | --- |
| Bug Trend calculation and evidence contracts | `bug_metrics/tests/test_api_bug_trend_contracts.py` | Matching completed runs, stale config rejection, range coverage, evidence by run/bucket, historical fact stability, timezone buckets, severity/status/resolution semantics, display fields. |
| Page query state | `bug_metrics/tests/test_bug_trend_page_query_state.py` | Visible-range evidence, bucket-series evidence, list-local filters, chart/list sync validation, selected chart scope, run pinning. |
| Scope config | `bug_metrics/tests/test_api_scope_config.py` | Load/save/validate/activate saved configs, semantic hash behavior, draft boundary, audit handoff mapping. |
| Scope audit | `bug_metrics/tests/test_api_scope_audit.py`, `jira_history/tests/test_api_scope_audit_facts.py` | Observed value counts, mapped/unmapped classification, unchanged coverage transport, read-only audit behavior. |
| Evidence export | `bug_metrics/tests/test_api_evidence_export.py` | Export equals current evidence result and records audit. |
| Data Health | `bug_metrics/tests/test_api_bug_trend_data_health.py`, `jira_sync/tests/test_api_jira_sync_data_health.py` | Calculation health and sync health read owner artifacts without writes. |
| Sync command | `jira_sync/tests/test_sync_jira_scope_command.py` | Mock Jira sync creates local durable artifacts and calculation run. |
| Chart Catalog | `bug_metrics/tests/test_api_chart_catalog.py` | Built-in chart registration, evidence contract validation, summary-only unsupported reason, renderer route decision, P2C trigger logic. |
| AI governance | `bug_metrics/tests/test_api_ai_chart_governance.py` | SQL/secrets rejection, evidence contract mismatch rejection, unknown series rejection, personal publish audit, cloud pending boundary. |

## UI, Facade, And HTTP Contract Tests

| Category | Test File | Covered Behavior |
| --- | --- | --- |
| Facade transport | `ui_web/tests/test_api_bug_trend_facade.py` | Saved scope options and chart id transport through facade. |
| Main Bug Trend view | `ui_web/tests/test_bug_trend_views.py` | Saved scope chart payload, stale guidance, no-run evidence behavior. |
| Scope config UI | `ui_web/tests/test_bug_trend_scope_config_views.py` | Audit value handoff, save and recalc prompt, validation errors, malformed GET/POST id handling. |
| Scope audit UI | `ui_web/tests/test_bug_trend_scope_audit_views.py` | Read-only audit table with observed values, mapped/unmapped state, and coverage. |
| Evidence table UI and APIs | `ui_web/tests/test_bug_trend_fact_table_ui.py` | Visible evidence, chart selector, bucket-series evidence, filters, export link, display columns, chart-data JSON, unapproved params, chart spec series filtering, unknown chart id, summary-only evidence state. |
| Chart selector UI | `ui_web/tests/test_bug_trend_chart_selector_views.py` | Selected chart cannot expose series outside catalog spec; summary-only chart shows unsupported evidence state. |
| Public JSON/CSV API malformed input | `ui_web/tests/test_bug_trend_api_contracts.py` | Malformed chart-data/evidence/export dates return 400 instead of 500. |
| Data Health UI | `ui_web/tests/test_data_health_views.py` | Health page renders latest sync/calculation state without recovery actions. |

## Grafana And Artifact Governance Tests

| Category | Test File Or Script | Covered Behavior |
| --- | --- | --- |
| Grafana data surface contract | `bug_metrics/tests/test_grafana_data_surface_contract.py` | Accepts committed artifact, rejects unapproved params, missing required params, unapproved path, external host, hardcoded semantics, raw Jira reads, SQL, unapproved datasource, empty artifact root. |
| Grafana artifact validation | `scripts/validate_grafana_artifacts.py` | Validates committed JSON artifacts against `docs/grafana-approved-data-surfaces.json`. |
| Grafana parity | `scripts/compare_grafana_bug_trend_parity.py`, `bug_metrics/tests/test_grafana_bug_trend_parity.py` | Run-pinned local/runtime command that compares artifact-declared chart target with Metrics chart API using artifact `chart_id`; unit coverage verifies artifact `chart_id` extraction and default behavior. |
| Approved data surface | `docs/grafana-approved-data-surfaces.json` | Declares allowed Metrics API paths and optional `chart_id` for chart-data. |

## Browser And Runtime Tests

| Category | Test File Or Evidence | Covered Behavior |
| --- | --- | --- |
| Automated browser tests | `ui_web/tests/test_browser_bug_trend_dashboard.py` | Mock Jira sync, nonblank Chart.js render, two-bucket series, evidence click state, unavailable state. |
| C0 runtime closure | `docs/c0-validation-closure-evidence.md`, `scripts/check_c0_validation_evidence.py` | Reference UI click/clear, live API checks, local Grafana render, checker-enforced runtime closure. |
| C1 evidence link | `docs/c1-evidence-link-validation-evidence.md`, `scripts/check_c1_evidence_link_evidence.py` | Grafana link target resolution, row count/title match against reference Metrics evidence, C-stock link-out decision. |
| C0 checker tests | `bug_metrics/tests/test_c0_validation_evidence_checker.py` | Checker rejects pending, failed, inconsistent runtime closure, and URL/query mismatch evidence. |
| C1 checker tests | `bug_metrics/tests/test_c1_evidence_link_checker.py` | Checker rejects pending, mismatched row count/title, missing residual risk, missing `chart_id`, and resolved-link/query mismatch evidence. |

## Hygiene And Review Gate Tests

| Category | Command Or Tool | Covered Behavior |
| --- | --- | --- |
| Django integration | `python manage.py check` | URL/view/settings/model integration errors. |
| File size | `scripts/check_file_size_limits.py --include-untracked` | Keeps files within repository size limits. |
| Whitespace | `scripts/check_diff_whitespace.py --include-untracked` | Rejects trailing whitespace and diff hygiene problems. |
| Exact-pass review | External `lsheng2-coding-review` process gate | Review process gate, not repository test coverage. Use when architecture/governance changes require independent exact-pass review. |

## Planned Additions

| Gap | Planned Test Case | Preferred Location |
| --- | --- | --- |
| CI does not currently auto-run local Grafana service render | Add optional CI job with Grafana service, Infinity datasource, seeded data, and screenshot/canvas check. | `.github/workflows/validation.yml` when CI is introduced. |
| C0/C1 evidence is checked but evidence generation is partly manual/local | Add script to regenerate C0/C1 evidence from live local services. | `scripts/` plus docs under `docs/validation/`. |
| Cross-contract coverage matrix is currently documented, not machine-checked | Add a lightweight checker that ensures each authority field in `docs/validation/test-strategy.md` has named test files. | `scripts/check_validation_matrix.py` if this becomes a recurring release gate. |
| Pull-request module tests are outside `pytest.ini` roots | Add explicit CI job for `pull_requests/tests`. | CI configuration. |

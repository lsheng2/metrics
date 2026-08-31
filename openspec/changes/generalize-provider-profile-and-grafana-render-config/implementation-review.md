# Implementation Review

日期：2026-08-31

## 结论

本轮已完成 Phase 4 的 Metrics-side AI dashboard composition contract，并完成 Phase 5 中除 file-size gate 之外的主要验证。当前架构方向保持 Metrics-owned semantics：AI base 和 `gcx` 只能消费 catalog、提交 draft render config、通过 Metrics validator/precondition 后再进入 Grafana 操作。

## 架构检查

### Provider/profile boundary

- `profile_id` 仍是主要入口。AI composition catalog 从 provider profile readiness 派生 profile、chart support、range modes 和 source population metadata。
- Catalog response 只暴露 public source metadata，不暴露 provider credentials 或 raw native query text。
- AI draft validation 不允许未知 series；`new_critical` 不会被自动映射为 `new_critical_high`。

### Grafana/render boundary

- AI 生成物是 render config draft，不是 Metrics backend code patch。
- gcx publication precondition 调用同一套 Grafana render/artifact validator，失败时 `mutation_allowed=false`，不会产生可导入 Grafana 的 approved mutation。
- 有效 draft 仍返回 `approval_required`，表示 validator pass 不等于自动发布。

### AI/gcx ownership

- AI base `D:\AIGC\Report_creater_agent\` 和 `gcx` 被记录为 optional clients/operators。
- Metrics 保留 profile registry、chart recipe、facts、aggregate、evidence、validator、audit 和 source credentials ownership。
- AI base absence 不影响 non-AI dashboard path。

### Secret handling

- 新 catalog test 覆盖 response 中不出现 `native_query_text`、`password`、`token`、`api_key`。
- gcx precondition 使用 Grafana artifact validator 检查 secret-shaped fields、provider-native literals、unapproved datasource/API surface 和 business calculation patterns。

### Rollback path

- 新 API 是 additive：现有 `get_ai_dashboard_context`、`create_ai_provider_chart_draft`、provider chart APIs 和 generated dashboard validation 未改变调用方式。
- 如果 AI/gcx integration 不启用，已有 provider sync/cache/Grafana dashboard 仍继续工作。

## Validation Evidence

| Gate | Result |
| --- | --- |
| Phase 4 focused AI contract tests | PASS: `.venv/Scripts/python.exe manage.py test bug_metrics.tests.test_api_ai_dashboard_context -v 2`，14 tests OK |
| Focused provider/Grafana/API suite | PASS: `.venv/Scripts/python.exe manage.py test provider_sync.tests.test_api_provider_sync_cache provider_sync.tests.test_api_hsdes_live_sync bug_metrics.tests.test_api_provider_aggregate_contracts bug_metrics.tests.test_api_hsdes_provider_profile bug_metrics.tests.test_api_provider_profile_registry ui_web.tests.test_provider_chart_api_surface ui_web.tests.test_data_health_views bug_metrics.tests.test_grafana_render_config bug_metrics.tests.test_grafana_data_surface_contract bug_metrics.tests.test_api_ai_dashboard_context -v 2`，116 tests OK |
| Grafana artifact validator | PASS: `.venv/Scripts/python.exe scripts/validate_grafana_artifacts.py --artifact-root ops/grafana --allowlist openspec/docs/current-baseline/grafana-approved-data-surfaces.json`，4 artifacts checked |
| Django system check | PASS: `.venv/Scripts/python.exe manage.py check`，no issues |
| Diff whitespace | PASS: `.venv/Scripts/python.exe scripts/check_diff_whitespace.py --include-untracked` |
| File-size limits | PASS: `.venv/Scripts/python.exe scripts/check_file_size_limits.py --include-untracked`，37 files checked |

## Closeout Refactor

为关闭 file-size gate，本轮将 oversized files 拆成 focused modules：

- Provider aggregate coordinator 保留在 `provider_aggregates.py`，Jira rows、HSD-ES rows、result shaping、source population 分别拆到 `provider_aggregate_jira.py`、`provider_aggregate_hsdes.py`、`provider_aggregate_results.py`、`provider_aggregate_sources.py`。
- Provider sync cache DTO/range identity 拆到 `provider_sync/app/api/cache_contracts.py`。
- HSD-ES readiness static API contract 拆到 `hsdes_readiness_contract.py`。
- Grafana render config required-field constants 拆到 `scripts/grafana_render_config_contracts.py`。
- UI provider/Grafana dashboard helper 拆到 `ui_web/facades/provider_dashboard_facade.py`。
- Duplicate render-config rejection test 从 data-surface contract test file 删除；同等行为由 `test_grafana_render_config.py` 覆盖。

Remaining risk：无新的 P1 blocker。后续仍建议继续把 `ApiForBugTrend` facade 拆薄，但当前 changed files 已全部通过 line-count gate。

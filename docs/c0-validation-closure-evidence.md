# C0 Validation Closure Evidence

日期：2026-08-20

本文件是 C0.V1-C0.V4 的运行态验证记录。当前状态是 pending；在 browser/API/Grafana runtime validation 实际执行前，`scripts/check_c0_validation_evidence.py --evidence docs/c0-validation-closure-evidence.md` 必须失败。

| node_id | status | command_or_manual_step | exit_code_or_result | scope_id | begin | end | calculation_run_id | observed_url | evidence_before_after | grafana_runtime_state | residual_risk | closure_verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C0.V1 | passed | VS Code browser page smoke, canvas pixel check, Chart.js click on all_open_bugs 26WW32, Clear selection click | page loaded real Jira scope; canvas nonWhite=35398; evidence 39 -> 34 -> 39 | 3 | 2026-06-01 | 2026-08-09 | e0ad52ca-3be4-445e-b428-ce078ec64e13 | http://127.0.0.1:8002/bug-trend/?scope_id=3&begin=2026-06-01&end=2026-08-09 | visible range 39; click all_open_bugs 26WW32 returned 34; Clear selection restored 39 |  | none |  |
| C0.V2 | passed | curl live API checks for chart-data and evidence positive/negative cases | chart-data 50 points; target value 34; evidence selection 34; chart-data run param 400; evidence without run 400 | 3 | 2026-06-01 | 2026-08-09 | e0ad52ca-3be4-445e-b428-ce078ec64e13 |  |  |  | none |  |
| C0.V3 | passed | local Grafana 13.2.0 on 127.0.0.1:3001 with yesoreyeram-infinity-datasource v4.0.0; imported ops/grafana/bug_trend_dashboard.json | dashboard rendered without No data; panel shows Bug Trend/value legend; canvas nonWhite=2360 | 3 | 2026-06-01 | 2026-08-09 | e0ad52ca-3be4-445e-b428-ce078ec64e13 | http://127.0.0.1:3001/d/metrics-bug-trend-c-stock/metrics-bug-trend-c-stock-spike?orgId=1&var-scope_id=3&var-begin=2026-06-01&var-end=2026-08-09 |  | runtime_render_validated | none |  |
| C0.V4 | passed | scripts/check_c0_validation_evidence.py --evidence docs/c0-validation-closure-evidence.md | checker expected to pass for full runtime closure after this record |  |  |  |  |  |  | runtime_render_validated | none | full_c0_runtime_closure |
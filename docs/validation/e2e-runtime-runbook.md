# E2E Runtime Validation Runbook

## Purpose

This runbook validates the Jira/Grafana MVP in a running local environment. It complements pytest by proving that the browser-visible dashboard, Chart.js canvas, Metrics API, and Grafana C-stock link-out path work together.

## Prerequisites

- Python virtual environment is available at `.venv/Scripts/python.exe`.
- Database migrations have run.
- Bug Trend demo or real local data exists for a saved scope.
- Django backend is running at `http://127.0.0.1:8002/`.
- For Grafana runtime validation, Grafana is running at `http://127.0.0.1:3001/` with the Infinity datasource plugin and the committed dashboard imported.

## Start Local Demo

Use VS Code tasks when available:

```text
Demo: Start E2E Bug Trend
```

Equivalent command sequence:

```powershell
& .venv\Scripts\python.exe manage.py migrate
& .venv\Scripts\python.exe manage.py seed_bug_trend_sample
& scripts\local_start_backend.ps1 -Workspace (Get-Location)
& scripts\local_open_bug_trend.ps1
```

## C0 Reference UI Runtime Check

Validate the Django/Chart.js reference UI:

1. Open `/bug-trend/?scope_id=<scope>&begin=<begin>&end=<end>`.
2. Confirm the chart canvas is nonblank.
3. Click one bucket/series, preferably `all_open_bugs` or `fixed_or_closed_bugs`.
4. Confirm the evidence title changes to the selected bucket/series.
5. Confirm evidence row count changes from visible range to selected membership.
6. Click Clear selection and confirm visible-range evidence returns.
7. Record the result in `docs/c0-validation-closure-evidence.md`.
8. Run:

```powershell
& .venv\Scripts\python.exe scripts\check_c0_validation_evidence.py --evidence docs\c0-validation-closure-evidence.md
```

## C0 API Runtime Check

Validate live Metrics APIs:

1. Request chart data:

```powershell
curl.exe --noproxy 127.0.0.1 "http://127.0.0.1:8002/api/charts/data/?scope_id=<scope>&begin=<begin>&end=<end>&chart_id=default_bug_trend"
```

2. Request evidence for a selected run/bucket/series:

```powershell
curl.exe --noproxy 127.0.0.1 "http://127.0.0.1:8002/api/charts/evidence/?scope_id=<scope>&begin=<begin>&end=<end>&run=<run>&bucket=<bucket>&series=<series>&chart_id=default_bug_trend"
```

3. Confirm malformed dates return 400, not 500.
4. Confirm missing required run for selected evidence returns 400.
5. Record the result in `docs/c0-validation-closure-evidence.md`.

## Grafana C-stock Runtime Check

Validate Grafana as a link-out renderer:

1. Open the committed Grafana dashboard.
2. Set variables for `scope_id`, `begin`, and `end`.
3. Confirm the panel renders data and does not show `No data`.
4. Confirm the panel data target calls `/api/charts/data/` with `chart_id=default_bug_trend` or the intended catalog chart id.
5. Resolve a data link for a chart point.
6. Confirm the resolved link points to `/api/charts/evidence/` and carries `scope_id`, `begin`, `end`, `run`, `bucket`, `series`, and `chart_id`.
7. Record the result in `docs/c1-evidence-link-validation-evidence.md`.
8. Run:

```powershell
& .venv\Scripts\python.exe scripts\check_c1_evidence_link_evidence.py --evidence docs\c1-evidence-link-validation-evidence.md
```

## Automated Browser Test

Run the current Playwright-based Django browser tests:

```powershell
& .venv\Scripts\python.exe -m pytest ui_web\tests\test_browser_bug_trend_dashboard.py -q
```

The test file covers:

- mocked Jira sync into durable local artifacts;
- nonblank Chart.js rendering;
- one-bucket and two-bucket chart data;
- evidence state loaded for clicked bucket/series;
- unavailable state when selected range is not covered by a completed run.

## Runtime Evidence Rules

- Do not mark C0/C1 evidence as passed until the runtime check has actually been executed.
- Every runtime evidence row must include enough identifiers to reproduce the check: scope, date range, run, bucket, series, URL, and observed result.
- Grafana C1 evidence rows with captured payloads must include `chart_id`, and the checker parses `resolved_link_url` to ensure it matches the evidence table fields.
- C0 reference and Grafana observed URLs must use query variables that match the evidence row's `scope_id`, `begin`, and `end` fields.
- Checker scripts are required before closure. A manually edited evidence document is not enough.
- C-stock supports linked evidence through Metrics APIs. It does not support same-page evidence list ownership; that remains a future Grafana App/Scenes path if the product requires it.

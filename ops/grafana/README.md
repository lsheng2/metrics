# Grafana Artifacts

This directory owns provisioned Grafana artifacts for the C-stock feasibility spike.

Committed JSON artifacts in this directory must pass:

```powershell
.venv\Scripts\python.exe scripts\validate_grafana_artifacts.py --artifact-root ops\grafana --allowlist openspec/docs/current-baseline/grafana-approved-data-surfaces.json
```

The validator intentionally fails when no JSON artifacts are present, so an empty artifact selection cannot be treated as a successful C-stock gate.

`render_configs/ip_quality_dashboard.json` is the editable Metrics-owned render config for the IP Quality Dashboard. `ip_quality_dashboard.generated.json` is generated from that config and the approved data-surface allowlist:

```powershell
.venv\Scripts\python.exe scripts\grafana_render_config.py --render-config ops\grafana\render_configs\ip_quality_dashboard.json --allowlist openspec\docs\current-baseline\grafana-approved-data-surfaces.json --output ops\grafana\ip_quality_dashboard.generated.json
```

Review render-config changes first. The generated JSON is committed so Grafana import and validator gates can run without rebuilding it, but it should be regenerated rather than edited directly.

Local deployment and runtime validation steps are documented in:

```text
openspec/docs/validation/grafana-bug-trend-deployment-guide.zh.md
```

The current local validation path uses Grafana OSS on `127.0.0.1:3001`, the Infinity datasource plugin, and the datasource UID `metrics-bug-trend-api`.

Provider parity runtime preview:

```powershell
.venv\Scripts\python.exe scripts\e2e_provider_parity.py restart --profile-id nvu-ttl-hsdes --begin-ww 26WW32 --end-ww 26WW35 --force-by-port
```

This restarts the Django backend, re-imports `provider_parity_dashboard.json`, validates the Metrics-owned provider chart API through Grafana, and opens the dashboard. HSD-ES browser SSO only proves the human can reach the saved query; it does not configure the Django backend. Until live HSD-ES sync credentials are configured, `nvu-ttl-hsdes` charts use the local seed-backed aggregate preview and show `seeded_preview` freshness/status.

For `range_mode=ww`, the launcher resolves `begin_ww` / `end_ww` into calendar dates and sets Grafana's native `from` / `to` URL parameters to the same range using browser-local absolute timestamps. The native Grafana time picker remains manually editable because stock Grafana does not support hard min/max picker limits from dashboard variables or custom placement of the native picker inside a dashboard row. Metrics still uses the WW variables as the backend data-range authority in WW mode. The dashboard keeps the top controls in three logical groups: Profile first; `Provider Fetch / Cache Window` for `range_mode`, `Begin WW`, `End WW`, and Refresh; and `Display Time Window` for the native Grafana time picker plus the `Sync Range` link. If a user changes `Begin WW` / `End WW` inside Grafana, use `Sync Range` to reopen the dashboard with `from` / `to` recalculated for the selected WW range.

Renderer route decision for the built-in chart is recorded in Metrics Chart Catalog as `default_bug_trend`. C-stock is validated only for chart values and Metrics evidence link-out; same-page evidence requires the separate P2C App/Scenes spike trigger.

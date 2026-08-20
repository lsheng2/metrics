# Grafana Artifacts

This directory owns provisioned Grafana artifacts for the C-stock feasibility spike.

Committed JSON artifacts in this directory must pass:

```powershell
.venv\Scripts\python.exe scripts\validate_grafana_artifacts.py --artifact-root ops\grafana --allowlist docs\grafana-approved-data-surfaces.json
```

The validator intentionally fails when no JSON artifacts are present, so an empty artifact selection cannot be treated as a successful C-stock gate.

Local deployment and runtime validation steps are documented in:

```text
docs/grafana-bug-trend-deployment-guide.zh.md
```

The current local validation path uses Grafana OSS on `127.0.0.1:3001`, the Infinity datasource plugin, and the datasource UID `metrics-bug-trend-api`.
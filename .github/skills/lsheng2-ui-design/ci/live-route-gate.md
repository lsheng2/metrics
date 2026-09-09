# Live Route UI Gate

Use this after starting the local application server with seeded test data.
The full manifest wrapper delegates to `scripts\validate_ui_live_routes.ps1`; report refresh delegates to `create_ui_gate_report.py`.

```powershell
scripts\validate_ui_full_manifest_gate.ps1 -BaseUrl http://127.0.0.1:8000
scripts\validate_ui_full_manifest_gate.ps1 -BaseUrl http://127.0.0.1:8000 -NoScreenshots
scripts\validate_ui_visual_diff_gate.ps1
scripts\validate_ui_visual_diff_gate.ps1 -UpdateBaseline
scripts\refresh_ui_gate_report.ps1 -BaseUrl http://127.0.0.1:8000 -IncludeHooked
```

`validate_ui_visual_diff_gate.ps1` compares the sanitized component catalog against the committed synthetic baseline. Use `-UpdateBaseline` only when the component catalog change is intentionally accepted.

Keep live route screenshots and JSON output local unless the project explicitly asks to publish sanitized artifacts.

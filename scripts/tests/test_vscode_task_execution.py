import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("action", ["Start", "Stop", "Restart"])
@pytest.mark.parametrize("downstream_exit", [0, 23, "binding"])
def test_editor_stack_tasks_use_current_binding_and_propagate_failure(tmp_path, action, downstream_exit):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in ("start", "stop", "restart"):
        old = ROOT / "scripts" / f"e2e_{name}_dashboard_ai_stack.ps1"
        if old.exists():
            shutil.copy2(old, scripts / old.name)
    (scripts / "e2e_dashboard_ai_stack.ps1").write_text(
        "[CmdletBinding()]\n"
        "param([ValidateSet('start','stop','restart')][string]$Action,[string]$DashboardWorkspace,"
        "[string]$DashboardBaseUrl,[string]$ModelBaseUrl,[string]$JiraProfileId,[string]$BeginWw,"
        "[string]$EndWw,[int]$DjangoPort,[int]$GrafanaPort,[switch]$SkipJiraSync,[switch]$SkipSmoke,[switch]$NoOpen)\n"
        "$Action | Set-Content -LiteralPath (Join-Path $DashboardWorkspace 'called.txt')\n"
        "if ($env:SYNTHETIC_FAILURE_MODE -eq 'binding') { function Child { [CmdletBinding()]param() }; Child -RemovedOption }\n"
        "exit ([int]$env:SYNTHETIC_EXIT_CODE)\n",
        encoding="utf-8",
    )
    task = next(item for item in json.loads((ROOT / ".vscode/tasks.json").read_text())["tasks"]
                if item["label"] == f"Current Worktree: Dashboard AI Stack: {action}")
    command = task["command"].replace("${workspaceFolder}", str(tmp_path))
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command], cwd=tmp_path,
        env={**os.environ, "SYNTHETIC_EXIT_CODE": "0" if downstream_exit == "binding" else str(downstream_exit),
             "SYNTHETIC_FAILURE_MODE": str(downstream_exit)},
        capture_output=True, text=True, timeout=20,
    )
    assert (tmp_path / "called.txt").exists(), result.stderr
    assert (tmp_path / "called.txt").read_text().strip() == action.lower()
    if downstream_exit == "binding":
        assert result.returncode != 0, result.stderr
    else:
        assert result.returncode == downstream_exit, result.stderr


def test_editor_has_no_force_task_or_retained_interpreter():
    payload = json.loads((ROOT / ".vscode/tasks.json").read_text())
    for task in payload["tasks"]:
        command = task.get("command", "")
        assert "-ForceByPort" not in command
        assert ".venv\\Scripts\\python.exe" not in command
        assert "Force By Port" not in task["label"]

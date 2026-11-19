from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import audit_stack_process_inventory


def write_runtime_state(tmp_path: Path) -> Path:
    dashboard_state_path = tmp_path / "state" / "e2e" / "service-lifecycle-engine" / "metrics-bug-trend-default.json"
    dashboard_state_path.parent.mkdir(parents=True)
    dashboard_state_path.write_text(
        json.dumps(
            {
                "services": {
                    "django": {"pid": 100},
                    "grafana": {"pid": 200},
                }
            }
        ),
        encoding="utf-8",
    )
    return dashboard_state_path


def write_process_snapshot(tmp_path: Path, processes: list[dict[str, object]]) -> Path:
    snapshot_path = tmp_path / "processes.json"
    snapshot_path.write_text(json.dumps(processes), encoding="utf-8")
    return snapshot_path


def test_shouldPassWhenOnlyExpectedDashboardProcessesRemain(tmp_path, capsys):
    dashboard_state_path = write_runtime_state(tmp_path)
    snapshot_path = write_process_snapshot(
        tmp_path,
        [
            {
                "ProcessId": 100,
                "ParentProcessId": 1,
                "Name": "python.exe",
                "CommandLine": f"{tmp_path}\\.venv\\Scripts\\python.exe manage.py serve --host 127.0.0.1 --port 8002 --stop-file {tmp_path}\\state\\local\\serve-stop\\django-8002.stop",
            },
            {"ProcessId": 101, "ParentProcessId": 100, "Name": "python.exe", "CommandLine": "child"},
            {
                "ProcessId": 200,
                "ParentProcessId": 1,
                "Name": "grafana.exe",
                "CommandLine": f"grafana.exe server --config {tmp_path}\\state\\grafana\\runtime\\grafana-e2e-3001.ini",
            },
            {
                "ProcessId": 201,
                "ParentProcessId": 200,
                "Name": "gpx_infinity_windows_amd64.exe",
                "CommandLine": "gpx_infinity_windows_amd64.exe",
            },
            {
                "ProcessId": 202,
                "ParentProcessId": 200,
                "Name": "gpx_grafana-prometheus-datasource_windows_amd64.exe",
                "CommandLine": "gpx_grafana-prometheus-datasource_windows_amd64.exe",
            },
        ],
    )

    exit_code = audit_stack_process_inventory.main(
        [
            "--dashboard-workspace",
            str(tmp_path),
            "--dashboard-state",
            str(dashboard_state_path),
            "--process-snapshot-json",
            str(snapshot_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Process inventory audit passed" in output
    assert "grafana_plugins=2" in output


def test_shouldFailWhenStaleWorktreeGrafanaAndPluginsRemain(tmp_path, capsys):
    dashboard_state_path = write_runtime_state(tmp_path)
    snapshot_path = write_process_snapshot(
        tmp_path,
        [
            {
                "ProcessId": 200,
                "ParentProcessId": 1,
                "Name": "grafana.exe",
                "CommandLine": f"grafana.exe server --config {tmp_path}\\state\\grafana\\runtime\\grafana-e2e-3001.ini",
            },
            {
                "ProcessId": 900,
                "ParentProcessId": 1,
                "Name": "grafana.exe",
                "CommandLine": f"grafana.exe server --config {tmp_path}\\.worktrees\\service-lifecycle-engine\\state\\grafana\\runtime\\grafana-e2e-3011.ini",
            },
            {
                "ProcessId": 901,
                "ParentProcessId": 900,
                "Name": "gpx_grafana-loki-datasource_windows_amd64.exe",
                "CommandLine": "gpx_grafana-loki-datasource_windows_amd64.exe",
            },
        ],
    )

    exit_code = audit_stack_process_inventory.main(
        [
            "--dashboard-workspace",
            str(tmp_path),
            "--dashboard-state",
            str(dashboard_state_path),
            "--process-snapshot-json",
            str(snapshot_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "stale Grafana E2E process" in output
    assert "not owned by the current Grafana demo process" in output


def test_shouldFailWhenLifecycleStatePointsToMissingDashboardProcesses(tmp_path, capsys):
    dashboard_state_path = write_runtime_state(tmp_path)
    snapshot_path = write_process_snapshot(tmp_path, [])

    exit_code = audit_stack_process_inventory.main(
        [
            "--dashboard-workspace",
            str(tmp_path),
            "--dashboard-state",
            str(dashboard_state_path),
            "--process-snapshot-json",
            str(snapshot_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "expected Dashboard Django lifecycle process is not running" in output
    assert "expected Dashboard Grafana lifecycle process is not running" in output


def test_shouldFailWhenLifecyclePidWasReusedByWrongProcess(tmp_path, capsys):
    dashboard_state_path = write_runtime_state(tmp_path)
    snapshot_path = write_process_snapshot(
        tmp_path,
        [
            {
                "ProcessId": 100,
                "ParentProcessId": 1,
                "Name": "gpx_grafana-mssql-datasource_windows_amd64.exe",
                "CommandLine": "gpx_grafana-mssql-datasource_windows_amd64.exe",
            },
            {
                "ProcessId": 200,
                "ParentProcessId": 1,
                "Name": "python.exe",
                "CommandLine": "python.exe unrelated.py",
            },
        ],
    )

    exit_code = audit_stack_process_inventory.main(
        [
            "--dashboard-workspace",
            str(tmp_path),
            "--dashboard-state",
            str(dashboard_state_path),
            "--process-snapshot-json",
            str(snapshot_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "Metrics serve process" in output
    assert "Grafana runtime" in output


def test_shouldEscapeUnencodableCommandLineWhenConsoleCannotEncodeIt(tmp_path):
    dashboard_state_path = write_runtime_state(tmp_path)
    stale_config = f"{tmp_path}\\.worktrees\\stale\\state\\grafana\\runtime\\grafana-e2e-3011-\u2717.ini"
    snapshot_path = write_process_snapshot(
        tmp_path,
        [{"ProcessId": 900, "ParentProcessId": 1, "Name": "grafana.exe", "CommandLine": f"grafana.exe server --config {stale_config}"}],
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "audit_stack_process_inventory.py"),
            "--dashboard-workspace",
            str(tmp_path),
            "--dashboard-state",
            str(dashboard_state_path),
            "--process-snapshot-json",
            str(snapshot_path),
        ],
        capture_output=True,
        env={**os.environ, "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"},
        check=False,
    )

    assert completed.returncode == 1
    assert b"UnicodeEncodeError" not in completed.stderr
    assert "grafana-e2e-3011-\\u2717.ini" in completed.stdout.decode("cp1252")


def test_dashboardAiStackRunsProcessInventoryAuditBeforeOpeningBrowser():
    script = (ROOT / "scripts" / "e2e_dashboard_ai_stack.ps1").read_text(encoding="utf-8")

    assert "Invoke-ProcessInventoryAudit -Phase 'final'" in script
    assert script.index("Invoke-ProcessInventoryAudit -Phase 'final'") < script.index("Start-Process $workbenchUrl")
    final_section = script[script.index("Invoke-BootLogAudit -Phase 'final'"):script.index("Start-Process $workbenchUrl")]
    assert "Clear-StaleDemoProcesses" not in final_section
    assert "Get-DashboardLifecycleStatePath" in script
    assert "service-lifecycle-engine\\metrics-bug-trend-default.json" in script

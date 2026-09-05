from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import audit_stack_process_inventory


def write_runtime_state(tmp_path: Path) -> tuple[Path, Path, Path]:
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
    ai_base_workspace = tmp_path / "ai-base"
    ai_base_state_path = ai_base_workspace / ".tmp-validation" / "runtime" / "dev-stack-state.dashboard_query_agent.json"
    ai_base_state_path.parent.mkdir(parents=True)
    ai_base_state_path.write_text(
        json.dumps(
            {
                "processes": [
                    {"role": "backend", "pid": 300},
                    {"role": "frontend", "pid": 400},
                ]
            }
        ),
        encoding="utf-8",
    )
    return dashboard_state_path, ai_base_workspace, ai_base_state_path


def write_process_snapshot(tmp_path: Path, processes: list[dict[str, object]]) -> Path:
    snapshot_path = tmp_path / "processes.json"
    snapshot_path.write_text(json.dumps(processes), encoding="utf-8")
    return snapshot_path


def test_shouldPassWhenOnlyExpectedDashboardAndAiBaseProcessesRemain(tmp_path, capsys):
    dashboard_state_path, ai_base_workspace, ai_base_state_path = write_runtime_state(tmp_path)
    snapshot_path = write_process_snapshot(
        tmp_path,
        [
            {
                "ProcessId": 100,
                "ParentProcessId": 1,
                "Name": "python.exe",
                "CommandLine": f"{tmp_path}\\.venv\\Scripts\\python.exe manage.py runserver 127.0.0.1:8002 --noreload",
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
            {
                "ProcessId": 300,
                "ParentProcessId": 1,
                "Name": "powershell.exe",
                "CommandLine": f"powershell.exe -EncodedCommand backend {ai_base_workspace}",
            },
            {"ProcessId": 301, "ParentProcessId": 300, "Name": "python.exe", "CommandLine": "uvicorn app.main:app"},
            {
                "ProcessId": 400,
                "ParentProcessId": 1,
                "Name": "powershell.exe",
                "CommandLine": f"powershell.exe -EncodedCommand frontend {ai_base_workspace}",
            },
            {"ProcessId": 401, "ParentProcessId": 400, "Name": "node.exe", "CommandLine": "vite"},
        ],
    )

    exit_code = audit_stack_process_inventory.main(
        [
            "--dashboard-workspace",
            str(tmp_path),
            "--dashboard-state",
            str(dashboard_state_path),
            "--ai-base-workspace",
            str(ai_base_workspace),
            "--ai-base-state",
            str(ai_base_state_path),
            "--process-snapshot-json",
            str(snapshot_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Process inventory audit passed" in output
    assert "grafana_plugins=2" in output


def test_shouldFailWhenStaleWorktreeGrafanaAndPluginsRemain(tmp_path, capsys):
    dashboard_state_path, ai_base_workspace, ai_base_state_path = write_runtime_state(tmp_path)
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
            "--ai-base-workspace",
            str(ai_base_workspace),
            "--ai-base-state",
            str(ai_base_state_path),
            "--process-snapshot-json",
            str(snapshot_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "stale Grafana E2E process" in output
    assert "not owned by the current Grafana demo process" in output


def test_shouldFailWhenLifecycleStatePointsToMissingDashboardProcesses(tmp_path, capsys):
    dashboard_state_path, ai_base_workspace, ai_base_state_path = write_runtime_state(tmp_path)
    snapshot_path = write_process_snapshot(tmp_path, [])

    exit_code = audit_stack_process_inventory.main(
        [
            "--dashboard-workspace",
            str(tmp_path),
            "--dashboard-state",
            str(dashboard_state_path),
            "--ai-base-workspace",
            str(ai_base_workspace),
            "--ai-base-state",
            str(ai_base_state_path),
            "--process-snapshot-json",
            str(snapshot_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "expected Dashboard Django lifecycle process is not running" in output
    assert "expected Dashboard Grafana lifecycle process is not running" in output


def test_shouldFailWhenLifecyclePidWasReusedByWrongProcess(tmp_path, capsys):
    dashboard_state_path, ai_base_workspace, ai_base_state_path = write_runtime_state(tmp_path)
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
            "--ai-base-workspace",
            str(ai_base_workspace),
            "--ai-base-state",
            str(ai_base_state_path),
            "--process-snapshot-json",
            str(snapshot_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "Django runserver" in output
    assert "Grafana runtime" in output


def test_shouldFailWhenAiBaseVisibleNoExitWindowModeReturns(tmp_path, capsys):
    dashboard_state_path, ai_base_workspace, ai_base_state_path = write_runtime_state(tmp_path)
    snapshot_path = write_process_snapshot(
        tmp_path,
        [
            {
                "ProcessId": 300,
                "ParentProcessId": 1,
                "Name": "powershell.exe",
                "CommandLine": f"powershell.exe -NoExit -EncodedCommand dashboard_query_agent {ai_base_workspace}",
            },
        ],
    )

    exit_code = audit_stack_process_inventory.main(
        [
            "--dashboard-workspace",
            str(tmp_path),
            "--dashboard-state",
            str(dashboard_state_path),
            "--ai-base-workspace",
            str(ai_base_workspace),
            "--ai-base-state",
            str(ai_base_state_path),
            "--process-snapshot-json",
            str(snapshot_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "visible -NoExit window mode" in output


def test_dashboardAiStackRunsProcessInventoryAuditBeforeOpeningBrowser():
    script = (ROOT / "scripts" / "e2e_dashboard_ai_stack.ps1").read_text(encoding="utf-8")

    assert "Invoke-ProcessInventoryAudit -Phase 'final'" in script
    assert script.index("Invoke-ProcessInventoryAudit -Phase 'final'") < script.index("Start-Process $workbenchUrl")
    final_section = script[script.index("Invoke-BootLogAudit -Phase 'final'"):script.index("Start-Process $workbenchUrl")]
    assert "Clear-StaleDemoProcesses" not in final_section
    assert "Get-DashboardLifecycleStatePath" in script
    assert "service-lifecycle-engine\\metrics-bug-trend-default.json" in script

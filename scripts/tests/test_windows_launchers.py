from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))



pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell launcher coverage")


def write_fake_bug_trend_workspace(workspace: Path) -> None:
    scripts = workspace / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "e2e_bug_trend.py").write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import json",
                "import sys",
                "from pathlib import Path",
                "workspace = Path(__file__).resolve().parents[1]",
                "(workspace / 'argv.json').write_text(json.dumps(sys.argv[1:]), encoding='utf-8')",
            ]
        ),
        encoding="utf-8",
    )


def run_powershell(script: Path, args: list[str], workspace: Path, *, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "METRICS_DASHBOARD_PYTHON": sys.executable,
        "PYTHONIOENCODING": "utf-8",
        **(extra_env or {}),
    }
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *args],
        cwd=workspace,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )


@pytest.mark.parametrize(
    ("script_name", "args", "expected_prefix"),
    [
        ("e2e_start_bug_trend.ps1", ["-OpenEntrypoint", "none", "-DjangoPort", "9123", "-GrafanaPort", "3923"], ["start"]),
        ("e2e_stop_bug_trend.ps1", [], ["stop"]),
        ("e2e_restart_bug_trend.ps1", ["-OpenEntrypoint", "none", "-DjangoPort", "9123", "-GrafanaPort", "3923"], ["restart"]),
        ("local_start_backend.ps1", ["-Port", "9123"], ["start-backend"]),
        ("local_stop_backend.ps1", ["-Port", "9123"], ["stop-backend"]),
    ],
)
def test_windows_entrypoints_call_owned_lifecycle_without_force_by_port(tmp_path: Path, script_name: str, args: list[str], expected_prefix: list[str]) -> None:
    write_fake_bug_trend_workspace(tmp_path)

    completed = run_powershell(
        ROOT / "scripts" / script_name,
        ["-Workspace", str(tmp_path), *args],
        tmp_path,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    argv = json.loads((tmp_path / "argv.json").read_text(encoding="utf-8"))
    assert argv[: len(expected_prefix)] == expected_prefix
    assert "--workspace" in argv
    assert str(tmp_path) in argv
    assert "--force-by-port" not in argv
    if "-Port" in args:
        assert "--django-ports" in argv
        assert "9123" in argv
    if "-DjangoPort" in args:
        assert "--django-ports" in argv
        assert "9123" in argv
        assert "--grafana-ports" in argv
        assert "3923" in argv


def test_windows_entrypoints_reject_retired_force_by_port_option(tmp_path: Path) -> None:
    write_fake_bug_trend_workspace(tmp_path)

    completed = run_powershell(
        ROOT / "scripts" / "e2e_stop_bug_trend.ps1",
        ["-Workspace", str(tmp_path), "-ForceByPort"],
        tmp_path,
    )

    assert completed.returncode != 0
    assert not (tmp_path / "argv.json").exists()


@pytest.mark.parametrize(
    ("script_name", "args"),
    [
        ("e2e_start_bug_trend.ps1", ["-OpenEntrypoint", "none"]),
        ("e2e_stop_bug_trend.ps1", []),
        ("e2e_restart_bug_trend.ps1", ["-OpenEntrypoint", "none"]),
        ("local_start_backend.ps1", ["-Port", "9123"]),
        ("local_stop_backend.ps1", ["-Port", "9123"]),
    ],
)
def test_windows_entrypoints_propagate_python_nonzero_exit(tmp_path: Path, script_name: str, args: list[str]) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "e2e_bug_trend.py").write_text("raise SystemExit(37)\n", encoding="utf-8")

    completed = run_powershell(
        ROOT / "scripts" / script_name,
        ["-Workspace", str(tmp_path), *args],
        tmp_path,
    )

    assert completed.returncode == 37


def test_unified_stack_stop_does_not_call_ai_base_stop(tmp_path: Path) -> None:
    write_fake_bug_trend_workspace(tmp_path)
    dashboard_scripts = tmp_path / "scripts"
    (dashboard_scripts / "e2e_stop_bug_trend.ps1").write_text(
        "param([string]$Workspace)\n"
        "Set-Content -Path (Join-Path $Workspace 'dashboard-stop.txt') -Value 'stopped'\n",
        encoding="utf-8",
    )
    ai_base_workspace = tmp_path / "ai-base"
    (ai_base_workspace / "scripts").mkdir(parents=True)
    (ai_base_workspace / "scripts" / "stop-minimal-chat-dev.ps1").write_text(
        "Set-Content -Path (Join-Path $PSScriptRoot '..\\ai-base-stop-called.txt') -Value 'called'\n"
        "exit 44\n",
        encoding="utf-8",
    )

    completed = run_powershell(
        ROOT / "scripts" / "e2e_dashboard_ai_stack.ps1",
        ["-Action", "stop", "-DashboardWorkspace", str(tmp_path)],
        tmp_path,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert (tmp_path / "dashboard-stop.txt").read_text(encoding="utf-8").strip() == "stopped"
    assert not (ai_base_workspace / "ai-base-stop-called.txt").exists()


def test_unified_stack_rejects_retired_ai_base_workspace_option(tmp_path: Path) -> None:
    write_fake_bug_trend_workspace(tmp_path)
    completed = run_powershell(
        ROOT / "scripts" / "e2e_dashboard_ai_stack.ps1",
        ["-Action", "stop", "-DashboardWorkspace", str(tmp_path), "-AiBaseWorkspace", str(tmp_path / "ai-base")],
        tmp_path,
    )

    assert completed.returncode != 0


def test_unified_stack_forwards_owned_ports_and_can_skip_browser_open(tmp_path: Path) -> None:
    write_fake_bug_trend_workspace(tmp_path)
    for audit_name in ("audit_stack_boot_logs.py", "audit_stack_process_inventory.py"):
        (tmp_path / "scripts" / audit_name).write_text(
            "from __future__ import annotations\n"
            "import sys\n"
            "print('audit ok')\n"
            "raise SystemExit(0)\n",
            encoding="utf-8",
        )
    (tmp_path / "scripts" / "e2e_start_bug_trend.ps1").write_text(
        "param([string]$Workspace,[string]$OpenEntrypoint,[int]$DjangoPort,[int]$GrafanaPort)\n"
        "$payload = @{ workspace=$Workspace; open=$OpenEntrypoint; django=$DjangoPort; grafana=$GrafanaPort } | ConvertTo-Json\n"
        "Set-Content -Path (Join-Path $Workspace 'stack-start.json') -Value $payload\n"
        "New-Item -ItemType Directory -Path (Join-Path $Workspace 'state\\e2e') -Force | Out-Null\n"
        "Set-Content -Path (Join-Path $Workspace 'state\\e2e\\bug_trend_ports.json') -Value ('{\"django_port\":' + $DjangoPort + ',\"grafana_port\":' + $GrafanaPort + ',\"workbench_url\":\"http://127.0.0.1:' + $DjangoPort + '/workbench/\"}')\n"
        "New-Item -ItemType Directory -Path (Join-Path $Workspace 'state\\e2e\\service-lifecycle-engine') -Force | Out-Null\n"
        "Set-Content -Path (Join-Path $Workspace 'state\\e2e\\service-lifecycle-engine\\metrics-bug-trend-default.json') -Value '{\"services\":{}}'\n",
        encoding="utf-8",
    )

    completed = run_powershell(
        ROOT / "scripts" / "e2e_dashboard_ai_stack.ps1",
        [
            "-Action",
            "start",
            "-DashboardWorkspace",
            str(tmp_path),
            "-DjangoPort",
            "9123",
            "-GrafanaPort",
            "3923",
            "-SkipJiraSync",
            "-SkipSmoke",
            "-NoOpen",
        ],
        tmp_path,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    payload = json.loads((tmp_path / "stack-start.json").read_text(encoding="utf-8"))
    assert payload == {"workspace": str(tmp_path), "open": "none", "django": 9123, "grafana": 3923}

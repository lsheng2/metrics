from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TESTS_ROOT = Path(__file__).resolve().parent
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))

from test_windows_launcher_real_paths import (
    ROOT,
    SELECTED_WINDOWS_PYTHON,
    assert_http_ok,
    assert_no_w1_processes,
    copy_qualified_infinity_plugin,
    copy_source_tree,
    find_free_port,
    new_artifact_run_dir,
    run_real_powershell,
    synthetic_serve_environment,
    termination_records,
    write_fixture_fingerprints,
    write_source_fingerprints,
)


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell launcher coverage")


def test_e2e_restart_powershell_runs_real_dashboard_and_grafana_on_owned_ports() -> None:
    run_root = prepare_real_stack_run("e2e-restart-real-ps")
    source = run_root / "source"
    django_port = find_free_port()
    grafana_port = find_free_port()
    environment = real_stack_environment(run_root, source)
    command_log = run_root / "commands.jsonl"

    try:
        restart = run_real_powershell(
            source / "scripts" / "e2e_restart_bug_trend.ps1",
            [
                "-Workspace",
                str(source),
                "-OpenEntrypoint",
                "none",
                "-DjangoPort",
                str(django_port),
                "-GrafanaPort",
                str(grafana_port),
            ],
            source,
            environment,
            command_log,
            "e2e-restart",
            timeout=240,
        )
        assert restart.returncode == 0, restart.stderr + restart.stdout
        assert_summary_ports(source, django_port, grafana_port)
        assert_http_ok(f"http://127.0.0.1:{django_port}/ai/")
        assert_http_ok(f"http://127.0.0.1:{grafana_port}/api/health")
        stop = stop_stack(source, environment, command_log, django_port, grafana_port, "e2e-stop")
        assert stop.returncode == 0, stop.stderr + stop.stdout
        assert_normal_two_service_stop(source)
        write_source_fingerprints(run_root / "source-fingerprints.after.json", source)
        write_fixture_fingerprints(run_root / "fixture-fingerprints.after.json", run_root)
    finally:
        cleanup = stop_stack(source, environment, command_log, django_port, grafana_port, "cleanup-stop")
        (run_root / "cleanup-stop.returncode").write_text(str(cleanup.returncode), encoding="utf-8")
        assert_no_w1_processes(source)


def test_dashboard_stack_powershell_runs_real_start_stop_on_owned_ports() -> None:
    run_root = prepare_real_stack_run("dashboard-stack-real-ps")
    source = run_root / "source"
    django_port = find_free_port()
    grafana_port = find_free_port()
    environment = real_stack_environment(run_root, source)
    command_log = run_root / "commands.jsonl"

    try:
        start = run_real_powershell(
            source / "scripts" / "e2e_dashboard_ai_stack.ps1",
            [
                "-Action",
                "start",
                "-DashboardWorkspace",
                str(source),
                "-DjangoPort",
                str(django_port),
                "-GrafanaPort",
                str(grafana_port),
                "-SkipJiraSync",
                "-NoOpen",
            ],
            source,
            environment,
            command_log,
            "stack-start",
            timeout=260,
        )
        assert start.returncode == 0, start.stderr + start.stdout
        assert "Running process inventory audit: final" in start.stdout
        assert "Smoke checks passed." in start.stdout
        assert "Dashboard E2E stack is ready." in start.stdout
        assert_summary_ports(source, django_port, grafana_port)
        editor_tasks = json.loads((source / ".vscode/tasks.json").read_text(encoding="utf-8"))
        editor_stop = next(task for task in editor_tasks["tasks"] if task["label"] == "Current Worktree: Dashboard AI Stack: Stop")
        editor_entry = run_root / "editor-stop.ps1"
        editor_entry.write_text(editor_stop["command"].replace("${workspaceFolder}", str(source)), encoding="utf-8")
        stop = run_real_powershell(
            editor_entry,
            [],
            source,
            environment,
            command_log,
            "editor-stack-stop",
            timeout=120,
        )
        assert stop.returncode == 0, stop.stderr + stop.stdout
        assert_normal_two_service_stop(source)
        write_source_fingerprints(run_root / "source-fingerprints.after.json", source)
        write_fixture_fingerprints(run_root / "fixture-fingerprints.after.json", run_root)
    finally:
        cleanup = run_real_powershell(
            source / "scripts" / "e2e_dashboard_ai_stack.ps1",
            ["-Action", "stop", "-DashboardWorkspace", str(source), "-DjangoPort", str(django_port), "-GrafanaPort", str(grafana_port)],
            source,
            environment,
            command_log,
            "cleanup-stop",
            timeout=120,
        )
        (run_root / "cleanup-stop.returncode").write_text(str(cleanup.returncode), encoding="utf-8")
        assert_no_w1_processes(source)


def prepare_real_stack_run(prefix: str) -> Path:
    run_root = new_artifact_run_dir(prefix)
    source = run_root / "source"
    copy_source_tree(source)
    write_source_fingerprints(run_root / "source-fingerprints.before.json", source)
    return run_root


def real_stack_environment(run_root: Path, source: Path) -> dict[str, str]:
    grafana_bin = Path(r"C:\Program Files\GrafanaLabs\grafana\bin\grafana.exe")
    assert grafana_bin.exists(), "local Grafana binary is required for native stack launcher coverage"
    environment = synthetic_serve_environment(run_root, source_root=source)
    environment["METRICS_DASHBOARD_PYTHON"] = str(SELECTED_WINDOWS_PYTHON)
    environment["GRAFANA_BIN"] = str(grafana_bin)
    plugin_dir = copy_qualified_infinity_plugin(run_root)
    environment["GRAFANA_PLUGINS_PATH"] = str(plugin_dir)
    environment["GF_PATHS_PLUGINS"] = str(plugin_dir)
    return environment


def assert_summary_ports(source: Path, django_port: int, grafana_port: int) -> None:
    summary = json.loads((source / "state" / "e2e" / "bug_trend_ports.json").read_text(encoding="utf-8"))
    assert summary["django_port"] == django_port
    assert summary["grafana_port"] == grafana_port


def stop_stack(source: Path, environment: dict[str, str], command_log: Path, django_port: int, grafana_port: int, label: str):
    return run_real_powershell(
        source / "scripts" / "e2e_stop_bug_trend.ps1",
        ["-Workspace", str(source), "-DjangoPort", str(django_port), "-GrafanaPort", str(grafana_port)],
        source,
        environment,
        command_log,
        label,
        timeout=120,
    )


def assert_normal_two_service_stop(source: Path) -> None:
    records = termination_records(source)[-2:]
    by_service = {record["service"]: record for record in records}
    assert set(by_service) == {"django", "grafana"}
    assert all(record["reason"] == "stop_command" for record in by_service.values())
    assert all(record["stopped"] and not record["forced"] and not record["force_requested"] for record in by_service.values())
    assert all(record["exit_code"] == 0 for record in by_service.values())

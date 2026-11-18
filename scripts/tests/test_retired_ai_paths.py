import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest
from scripts.tests.test_embedded_runtime_boundaries import source_tree


def check(root, platform="windows"):
    return importlib.import_module("scripts.check_retired_ai_paths").check(root, platform=platform)


def test_current_repository_has_no_retired_windows_paths():
    result = check(Path(__file__).resolve().parents[2], platform="windows")
    assert result["checked_files"] > 0
    assert result["passed"] and not result["violations"], result


@pytest.mark.parametrize("path,text", [
    ("metrics/settings.py", "METRICS_AI_SIDECAR_ENABLED = True"),
    ("ui_web/routes.py", "route = '/api/ai-dashboard/workflow/'"),
    ("scripts/validation/consumer.py", "from ai_base_application_sdk import TaskRunClient"),
    ("scripts/start.ps1", "$env:METRICS_AI_BASE_URL = 'http://127.0.0.1:48300'"),
    ("ui_web/static/host.js", "notify('ai-base.host-action');"),
    ("project_management/services/worker.py", "execution_mode = 'remote'"),
    ("README.md", "Start with gunicorn metrics.wsgi:application."),
    ("docs/start.md", "python manage.py runserver 8000"),
    ("docs/run.md", "Use the installed SDK and project_serve."),
    (".github/run.md", "python scripts/e2e_bug_trend.py stop --force-by-port"),
    (".vscode/tasks.json", '{"command":"e2e_start_bug_trend.ps1 -ForceByPort"}'),
    ("scripts/old_wrapper.ps1", "param([string]$AiBaseWorkspace)"),
    ("ui_web/test_production.py", "old_client = 'TaskRunClient'"),
    ("ui_web/ignored/route.py", "old = 'connector_endpoint'"),
])
def test_retired_active_surfaces_fail_even_if_ignored_by_git(source_tree, path, text):
    file = source_tree / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(text, encoding="utf-8")
    (source_tree / ".gitignore").write_text("ui_web/ignored/\n", encoding="utf-8")
    result = check(source_tree)
    assert not result["passed"]
    assert any(row["path"] == path for row in result["violations"])


def test_linux_definition_remains_explicitly_deferred_on_windows(source_tree):
    path = source_tree / "ops/docker/Dockerfile"
    path.parent.mkdir(parents=True)
    path.write_text("CMD gunicorn metrics.wsgi:application\n", encoding="utf-8")
    windows = check(source_tree)
    assert windows["passed"]
    assert windows["deferred"][0]["path"] == "ops/docker/Dockerfile"
    assert not check(source_tree, "all")["passed"]


def test_test_literals_and_historical_specs_are_not_active_paths(source_tree):
    for name in ("scripts/tests/test_old.py", "openspec/changes/old/tasks.md", "docs/case_study/old.md"):
        path = source_tree / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("TaskRunClient sidecar project_serve", encoding="utf-8")
    assert check(source_tree)["passed"]


def test_checker_rejects_missing_root_and_empty_code_inventory(source_tree):
    assert not check(source_tree / "ui_web")["passed"]
    for path in source_tree.rglob("*.py"):
        path.unlink()
    assert not check(source_tree)["passed"]


def test_explicit_legacy_detection_is_not_a_legacy_import(source_tree):
    path = source_tree / "scripts/validation/windows_install_smoke.py"
    path.parent.mkdir(parents=True)
    path.write_text(
        "import importlib.util\n"
        "def import_probe():\n"
        "    return importlib.util.find_spec('ai_base_application_sdk') is not None\n",
        encoding="utf-8",
    )
    assert check(source_tree)["passed"]
    with path.open("a", encoding="utf-8") as output:
        output.write("\nroute = '/api/ai-dashboard/workflow/'\n")
    assert not check(source_tree)["passed"]


@pytest.mark.parametrize("path,source", [
    ("scripts/check_retired_ai_paths.py", "CODE_MARKERS = fetch('/api/ai-dashboard/workflow/')"),
    ("scripts/validation/windows_install_smoke.py", "LEGACY_SDK_MODULES = ('/api/ai-dashboard/workflow/',)"),
])
def test_policy_exception_cannot_hide_executable_or_unrelated_legacy_values(source_tree, path, source):
    file = source_tree / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(source, encoding="utf-8")
    assert not check(source_tree)["passed"]


@pytest.mark.parametrize("script,extra,source", [
    ("check_embedded_runtime_boundaries.py", [], "import ai_base_runtime"),
    ("check_retired_ai_paths.py", ["--platform", "windows"], "route = '/api/ai-dashboard/workflow/'"),
])
def test_cli_failure_is_nonzero_and_cannot_overwrite_a_report(source_tree, script, extra, source):
    (source_tree / "ui_web/bad.py").write_text(source, encoding="utf-8")
    output = source_tree / "result.json"
    command = [
        sys.executable, "-I", str(Path(__file__).resolve().parents[2] / "scripts" / script),
        "--root", str(source_tree), "--output", str(output), *extra,
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert result.returncode == 1, result.stderr
    payload = json.loads(output.read_text())
    assert payload["passed"] is False and payload["violations"]
    before = output.read_bytes()
    repeated = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert repeated.returncode != 0
    assert output.read_bytes() == before


@pytest.mark.parametrize("path", [
    "metrics/wsgi.py", "metrics/asgi.py",
    "scripts/e2e_start_dashboard_ai_stack.ps1",
    "scripts/e2e_stop_dashboard_ai_stack.ps1",
    "scripts/e2e_restart_dashboard_ai_stack.ps1",
])
def test_retired_entrypoint_file_is_rejected_even_without_legacy_text(source_tree, path):
    (source_tree / path).write_text("", encoding="utf-8")
    result = check(source_tree)
    assert not result["passed"]
    assert any(row["path"] == path for row in result["violations"])

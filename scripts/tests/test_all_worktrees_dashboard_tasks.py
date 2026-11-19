from __future__ import annotations

from pathlib import Path
import json
import os
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]


def test_all_worktrees_inventory_is_read_only_and_uses_git_worktrees() -> None:
    script = (ROOT / "scripts" / "all_worktrees_dashboard_ports_inventory.ps1").read_text(encoding="utf-8")

    assert "git -C $Workspace worktree list --porcelain" in script
    assert "runtime-instance.json" in script
    assert "bug_trend_ports.json" in script
    assert "Get-NetTCPConnection" in script
    assert "e2e_stop_bug_trend.ps1" not in script


def invoke_owned_worktree_fixture(tmp_path, *, first_fails=False, git_fails=False):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    stopper = scripts / "all_worktrees_stop_dashboard_project_services.ps1"
    shutil.copy2(ROOT / "scripts" / stopper.name, stopper)
    (scripts / "e2e_bug_trend.py").write_text(
        "import json,os,pathlib,sys\n"
        "workspace=sys.argv[sys.argv.index('--workspace')+1]\n"
        "with open(os.environ['SYNTHETIC_CALL_LOG'],'a') as out:\n"
        "    out.write(json.dumps(workspace)+'\\n')\n"
        "raise SystemExit(23 if workspace==os.environ.get('SYNTHETIC_FAIL_ROOT') else 0)\n",
        encoding="utf-8",
    )
    targets = [tmp_path / "first", tmp_path / "second"]
    for target in targets:
        (target / "scripts").mkdir(parents=True)
        (target / "scripts/e2e_stop_bug_trend.ps1").write_text(
            "param([string]$Workspace)\n"
            "'legacy invoked' | Add-Content -LiteralPath $env:SYNTHETIC_LEGACY_LOG\nexit 99\n",
            encoding="utf-8",
        )
        profile = target / "state/local/runtime-instance.json"
        profile.parent.mkdir(parents=True)
        profile.write_text('{"schema_version":2}', encoding="utf-8")
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    call_log = tmp_path / "calls.jsonl"
    legacy_log = tmp_path / "legacy.txt"
    driver = (
        "function git { "
        "$global:LASTEXITCODE=[int]$env:SYNTHETIC_GIT_EXIT; if ($global:LASTEXITCODE -ne 0) { return }; "
        "$rows=@(); foreach($path in ($env:SYNTHETIC_WORKTREES | ConvertFrom-Json)) { $rows+=('worktree '+$path); $rows+=''}; "
        "if ($args -contains '-z') { [string]::Join([char]0,$rows) } else { $rows } }; "
        "& $env:SYNTHETIC_STOPPER -Workspace $env:SYNTHETIC_WORKSPACE"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", driver], capture_output=True, text=True, timeout=45,
        env={**os.environ, "METRICS_DASHBOARD_PYTHON": sys.executable,
             "SYNTHETIC_STOPPER": str(stopper), "SYNTHETIC_WORKSPACE": str(tmp_path),
             "SYNTHETIC_CALL_LOG": str(call_log), "SYNTHETIC_LEGACY_LOG": str(legacy_log),
             "SYNTHETIC_WORKTREES": json.dumps([str(path) for path in [*targets, unrelated]]),
             "SYNTHETIC_GIT_EXIT": "44" if git_fails else "0",
             "SYNTHETIC_FAIL_ROOT": str(targets[0]) if first_fails else ""},
    )
    calls = [json.loads(line) for line in call_log.read_text().splitlines()] if call_log.exists() else []
    return result, calls, legacy_log, targets


@pytest.mark.parametrize("first_fails", [False, True])
def test_all_worktree_stop_uses_current_code_and_attempts_each_registered_workspace(tmp_path, first_fails):
    result, calls, legacy, targets = invoke_owned_worktree_fixture(tmp_path, first_fails=first_fails)
    assert calls == [str(path) for path in targets], result.stdout + result.stderr
    assert not legacy.exists()
    assert (result.returncode != 0) is first_fails


def test_failed_worktree_enumeration_is_not_reported_as_empty_success(tmp_path):
    result, calls, legacy, _ = invoke_owned_worktree_fixture(tmp_path, git_fails=True)
    assert result.returncode != 0
    assert not calls and not legacy.exists()

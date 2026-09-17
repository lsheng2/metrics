from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_all_worktrees_inventory_is_read_only_and_uses_git_worktrees() -> None:
    script = (ROOT / "scripts" / "all_worktrees_dashboard_ports_inventory.ps1").read_text(encoding="utf-8")

    assert "git -C $Workspace worktree list --porcelain" in script
    assert "runtime-instance.json" in script
    assert "bug_trend_ports.json" in script
    assert "Get-NetTCPConnection" in script
    assert "e2e_stop_bug_trend.ps1" not in script


def test_all_worktrees_stop_uses_each_worktree_stop_launcher() -> None:
    script = (ROOT / "scripts" / "all_worktrees_stop_dashboard_project_services.ps1").read_text(encoding="utf-8")

    assert "git -C $Workspace worktree list --porcelain" in script
    assert "scripts\\e2e_stop_bug_trend.ps1" in script
    assert "-ForceByPort" in script
    assert "all_worktrees_dashboard_ports_inventory.ps1" not in script

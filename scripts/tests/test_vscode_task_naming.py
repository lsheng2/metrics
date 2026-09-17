from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_vscode_tasks_make_worktree_scope_explicit() -> None:
    payload = json.loads((ROOT / ".vscode" / "tasks.json").read_text(encoding="utf-8"))
    labels = [task["label"] for task in payload["tasks"]]

    assert all(label.startswith(("Current Worktree:", "All Worktrees:")) for label in labels)
    assert "Current Worktree: Dashboard AI Stack: Start" in labels
    assert "Current Worktree: Dashboard AI Stack: Stop" in labels
    assert "Current Worktree: Dashboard AI Stack: Restart" in labels
    assert "All Worktrees: Dashboard Ports Inventory" in labels
    assert "All Worktrees: Stop Dashboard Project Services" in labels


def test_vscode_task_dependencies_reference_existing_labels() -> None:
    payload = json.loads((ROOT / ".vscode" / "tasks.json").read_text(encoding="utf-8"))
    labels = {task["label"] for task in payload["tasks"]}
    dependency_labels = []
    for task in payload["tasks"]:
        depends_on = task.get("dependsOn", [])
        if isinstance(depends_on, str):
            dependency_labels.append(depends_on)
        else:
            dependency_labels.extend(depends_on)

    assert all(label in labels for label in dependency_labels)


def test_all_worktrees_tasks_call_all_worktree_scripts() -> None:
    payload = json.loads((ROOT / ".vscode" / "tasks.json").read_text(encoding="utf-8"))
    commands = {task["label"]: task.get("command", "") for task in payload["tasks"]}

    assert "scripts\\all_worktrees_dashboard_ports_inventory.ps1" in commands["All Worktrees: Dashboard Ports Inventory"]
    assert "scripts\\all_worktrees_stop_dashboard_project_services.ps1" in commands["All Worktrees: Stop Dashboard Project Services"]
    assert "-ForceByPort" in commands["All Worktrees: Stop Dashboard Project Services"]

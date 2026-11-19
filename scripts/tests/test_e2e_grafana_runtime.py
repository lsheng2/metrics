from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from e2e_grafana_runtime import (
    INFINITY_DATASOURCE_PLUGIN_ID,
    resolve_grafana_plugins_path,
    shared_worktree_grafana_plugins_path,
    write_runtime_grafana_config,
)


@pytest.fixture(autouse=True)
def isolated_git_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GRAFANA_PLUGINS_PATH", "GF_PATHS_PLUGINS"):
        monkeypatch.delenv(name, raising=False)


def run_git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def make_repository(path: Path) -> Path:
    path.mkdir(parents=True)
    run_git(path, "init", "-q")
    run_git(path, "commit", "-q", "--allow-empty", "-m", "init")
    return path


def add_worktree(repository: Path, worktree: Path) -> Path:
    run_git(repository, "worktree", "add", "-q", "--detach", str(worktree))
    return worktree


def main_checkout_plugins(repository: Path) -> Path:
    return repository.resolve() / "state" / "grafana" / "data" / "plugins"


def test_nested_worktree_runtime_config_uses_main_checkout_plugin_cache(tmp_path):
    repository = make_repository(tmp_path / "repo")
    worktree = add_worktree(repository, repository / ".worktrees" / "feature")
    (main_checkout_plugins(repository) / INFINITY_DATASOURCE_PLUGIN_ID).mkdir(parents=True)

    runtime_config = write_runtime_grafana_config(worktree, 3999)

    assert f"plugins = {main_checkout_plugins(repository).as_posix()}" in runtime_config.read_text(encoding="utf-8")


def test_worktree_outside_main_checkout_uses_main_checkout_plugin_cache(tmp_path):
    repository = make_repository(tmp_path / "repo")
    worktree = add_worktree(repository, tmp_path / "workspaces" / "feature")
    (main_checkout_plugins(repository) / INFINITY_DATASOURCE_PLUGIN_ID).mkdir(parents=True)

    assert shared_worktree_grafana_plugins_path(worktree) == main_checkout_plugins(repository)
    assert resolve_grafana_plugins_path(worktree) == main_checkout_plugins(repository)


def test_main_checkout_has_no_shared_plugin_cache(tmp_path):
    repository = make_repository(tmp_path / "repo")

    assert shared_worktree_grafana_plugins_path(repository) is None


def test_directory_outside_git_has_no_shared_plugin_cache(tmp_path):
    workspace = tmp_path / "plain"
    workspace.mkdir()

    assert shared_worktree_grafana_plugins_path(workspace) is None

import importlib
from pathlib import Path

import pytest


@pytest.fixture
def source_tree(tmp_path):
    for name in ("ai_host", "project_management", "ui_web", "metrics", "scripts"):
        directory = tmp_path / name
        directory.mkdir()
        (directory / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "README.md").write_text("Current embedded host.\n", encoding="utf-8")
    return tmp_path


def check(root):
    return importlib.import_module("scripts.check_embedded_runtime_boundaries").check(root)


@pytest.mark.parametrize("path,source,rule", [
    ("ui_web/view.py", "import ai_base_runtime", "runtime_owner"),
    ("scripts/launch.py", "from waitress import create_server", "runtime_owner"),
    ("ai_host/client.py", "from ai_base_runtime import _internal", "private_runtime"),
    ("ai_host/client.py", "import ai_base_runtime._internal.state", "private_runtime"),
    ("ai_host/client.py", "from app.services import old", "base_app_import"),
    ("project_management/client.py", "from ai_host import task_runs", "host_dependency"),
    ("project_management/app/domain/value.py", "from django.db import models", "domain_framework"),
    ("project_management/app/domain/value.py", "import asgiref.sync", "domain_framework"),
    ("ai_host/lifetime.py", "import asyncio as loop\nloop.run(work())", "loop_runner"),
    ("project_management/services/report_assists.py", "from asyncio import run as execute\nexecute(work())", "loop_runner"),
    ("project_management/services/project_run_worker.py", "import asyncio\nasyncio.run(work())", "loop_runner"),
    ("ui_web/test_production.py", "import ai_base_runtime", "runtime_owner"),
    ("ui_web/ignored/route.py", "import ai_base_runtime", "runtime_owner"),
])
def test_checker_rejects_each_owned_boundary_mutation(source_tree, path, source, rule):
    file = source_tree / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(source, encoding="utf-8")
    (source_tree / ".gitignore").write_text("ui_web/ignored/\n", encoding="utf-8")
    result = check(source_tree)
    assert not result["passed"]
    assert any(row["rule"] == rule and row["path"] == path for row in result["violations"])


def test_test_fixtures_and_unrelated_loop_owners_are_classified_separately(source_tree):
    for path, source in {
        "ai_host/client.py": "from ai_base_runtime import start_blocking\nfrom waitress import create_server",
        "project_management/tests/test_profile.py": "from ai_host import package\nimport ai_base_runtime",
        "ai_host/tests/test_loop.py": "import asyncio\nasyncio.run(work())",
        "ui_web/view.py": "import asyncio\nasyncio.run(work())",
    }.items():
        file = source_tree / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(source, encoding="utf-8")
    result = check(source_tree)
    assert result["passed"], result
    assert result["checked_files"] >= 4
    assert result["classified"]["test"] == 2


def test_missing_scope_and_zero_source_do_not_pass(tmp_path, source_tree):
    assert not check(tmp_path / "missing")["passed"]
    assert not check(source_tree / "ai_host")["passed"]
    for path in source_tree.rglob("*.py"):
        path.unlink()
    assert not check(source_tree)["passed"]


def test_invalid_python_is_not_silently_omitted(source_tree):
    (source_tree / "ai_host/broken.py").write_text("def broken(", encoding="utf-8")
    result = check(source_tree)
    assert any(row["rule"] == "invalid_python" for row in result["violations"])

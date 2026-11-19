import importlib
import json
from pathlib import Path
import subprocess
import sys


TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))


def test_native_fixture_copies_tracked_source_and_planned_files_only(tmp_path, monkeypatch):
    fixture = importlib.import_module("test_windows_launcher_real_paths")
    source = tmp_path / "repo"
    source.mkdir()
    subprocess.run(["git", "init", str(source)], check=True, capture_output=True, timeout=15)
    for name in ("app.py", ".env.production", "db.sqlite3"):
        (source / name).write_text("synthetic-only", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(source), "add", "app.py", ".env.production", "db.sqlite3"],
        check=True, capture_output=True, timeout=15,
    )
    (source / "unrelated.md").write_text("retain private local note", encoding="utf-8")
    (source / "planned.py").write_text("# planned source\n", encoding="utf-8")
    plan = source / "openspec/changes/embed-ai-base-runtime-in-process/windows-close-dag.json"
    plan.parent.mkdir(parents=True)
    plan.write_text(json.dumps({"planned_paths": {"planned.py": "W1.LAUNCH"}}), encoding="utf-8")
    monkeypatch.setattr(fixture, "ROOT", source)
    target = tmp_path / "copy"
    fixture.copy_source_tree(target)
    assert (target / "app.py").read_text() == "synthetic-only"
    assert (target / "planned.py").is_file()
    assert not (target / ".env.production").exists()
    assert not (target / "db.sqlite3").exists()
    assert not (target / "unrelated.md").exists()
    assert (source / ".env.production").read_text() == "synthetic-only"

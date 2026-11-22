from __future__ import annotations

import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.tests.aib_joint_dev_support import (
    dashboard_source,
    executable,
    formal_input_with_development_receipt,
    init_git_repo,
    runtime_source,
    sha256,
    write_json,
)
from scripts.validation.windows_qualification_inputs import QualificationError


def inputs():
    return importlib.import_module("scripts.validation.aib_joint_dev_inputs")


def cli():
    return importlib.import_module("scripts.validation.aib_joint_dev")


def worker():
    return importlib.import_module("scripts.validation.aib_joint_dev_worker")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def isolated_script(*parts: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-I", "-B", *parts],
        cwd=repo_root(),
        capture_output=True,
        text=True,
        timeout=30,
    )


def assert_phase_timings(timings, expected_states):
    phases = timings["phases"]
    assert timings["schema_version"] == 1
    assert set(phases) == {
        "setup",
        "snapshot",
        "build",
        "install",
        "test",
        "post_run_verification",
        "external_cleanup",
    }
    for name, state in expected_states.items():
        assert phases[name]["state"] == state
    assert phases["test"]["includes_fixture_cleanup"] is True
    assert phases["external_cleanup"] == {
        "state": "not_performed",
        "measurement": "not_separately_measured",
    }
    assert timings["total_seconds"] >= 0
    assert 0 <= timings["non_overlapping_phase_seconds"] <= timings["total_seconds"] + 0.001


def test_isolated_direct_cli_help_noargs_and_failure_bootstrap_repo_imports(tmp_path):
    help_result = isolated_script("scripts/validation/aib_joint_dev.py", "--help")
    assert help_result.returncode == 0
    assert "usage:" in help_result.stdout
    assert "ModuleNotFoundError" not in help_result.stderr

    noargs = isolated_script("scripts/validation/aib_joint_dev.py")
    assert noargs.returncode == 2
    assert "usage:" in noargs.stderr
    assert "ModuleNotFoundError" not in noargs.stderr

    failed_stage = isolated_script(
        "scripts/validation/aib_joint_dev.py",
        "source",
        "--aib-root",
        str(tmp_path / "missing-aib"),
        "--python",
        str(tmp_path / "missing-python.exe"),
        "--data-root",
        str(tmp_path / "runs"),
    )
    assert failed_stage.returncode == 1
    assert '"status": "failed"' in failed_stage.stderr
    assert "ModuleNotFoundError" not in failed_stage.stderr


def test_child_direct_worker_entry_bootstraps_repo_imports():
    result = isolated_script("scripts/validation/aib_joint_dev_worker.py", "--help")
    assert result.returncode == 0
    assert "usage:" in result.stdout
    assert "ModuleNotFoundError" not in result.stderr


def test_development_subprocess_environment_disables_bytecode(tmp_path):
    env = inputs().development_environment(tmp_path)
    assert env["PYTHONDONTWRITEBYTECODE"] == "1"
    assert env["PYTHONNOUSERSITE"] == "1"


def test_source_mode_runs_from_owned_dashboard_copy_without_original_tmp_or_pyc(tmp_path, monkeypatch):
    dashboard = dashboard_source(init_git_repo(tmp_path / "dashboard"))
    (dashboard / "scripts/validation").mkdir(parents=True)
    (dashboard / "scripts/validation/aib_joint_dev_worker.py").write_text("# copied worker\n", encoding="utf-8")
    aib = runtime_source(init_git_repo(tmp_path / "aib"))
    python = executable(tmp_path / "python/Scripts/python.exe")
    data_root = tmp_path / "runs"
    calls = []

    def fake_command(argv, *, cwd, run_dir, label, timeout):
        calls.append({"argv": [str(part) for part in argv], "cwd": Path(cwd), "run_dir": Path(run_dir)})
        assert Path(cwd).is_relative_to(run_dir / "copy")
        assert Path(argv[3]).is_relative_to(run_dir / "copy")
        assert argv[1:3] == ["-I", "-B"]
        assert Path(argv[argv.index("--dashboard-root") + 1]) == Path(cwd)
        assert Path(argv[argv.index("--aib-src") + 1]) == aib / "packages/runtime/src"
        (Path(cwd) / "tmp_ui_validation").mkdir()
        (Path(cwd) / "ai_host/__pycache__").mkdir()
        (Path(cwd) / "ai_host/__pycache__/copied.pyc").write_bytes(b"copy-bytecode")
        Path(argv[argv.index("--junitxml") + 1]).write_text(
            "<testsuite tests='1' failures='0' errors='0' skipped='0'>"
            "<testcase classname='source' name='case_0'/></testsuite>",
            encoding="utf-8",
        )
        write_json(
            Path(argv[argv.index("--origin-output") + 1]),
            {
                "stage": "source",
                "expected_root": str(aib / "packages/runtime/src"),
                "origin": str(aib / "packages/runtime/src/ai_base_runtime/__init__.py"),
            },
        )
        return {"label": label, "argv": [str(part) for part in argv], "returncode": 0}

    monkeypatch.setattr(cli(), "run_development_command", fake_command)

    assert cli().main(["source", "--aib-root", str(aib), "--python", str(python), "--data-root", str(data_root)]) == 0

    assert calls
    assert not (dashboard / "tmp_ui_validation").exists()
    assert not list(dashboard.rglob("*.pyc"))
    assert not list(aib.rglob("*.pyc"))
    run_dir = calls[0]["run_dir"]
    receipt = json.loads((run_dir / "evidence/aib-joint-development-receipt.json").read_text(encoding="utf-8"))
    assert Path(receipt["copied_dashboard"]) == calls[0]["cwd"]
    assert receipt["source_aib_src"] == str(aib / "packages/runtime/src")
    origin = Path(receipt["module_origins"]["origin"])
    assert origin.name == "__init__.py"
    assert origin.parent.name == "ai_base_runtime"
    assert_phase_timings(
        receipt["timings"],
        {
            "setup": "measured",
            "snapshot": "measured",
            "build": "not_applicable",
            "install": "not_applicable",
            "test": "measured",
            "post_run_verification": "measured",
        },
    )


def test_source_failure_receipt_measures_copy_test_and_postcheck_phases(tmp_path, monkeypatch):
    dashboard = dashboard_source(init_git_repo(tmp_path / "dashboard"))
    (dashboard / "scripts/validation").mkdir(parents=True)
    (dashboard / "scripts/validation/aib_joint_dev_worker.py").write_text("# copied worker\n", encoding="utf-8")
    aib = runtime_source(init_git_repo(tmp_path / "aib"))
    python = executable(tmp_path / "python/Scripts/python.exe")
    data_root = tmp_path / "runs"
    seen_run_dir = None

    def failing_command(argv, *, cwd, run_dir, label, timeout):
        nonlocal seen_run_dir
        seen_run_dir = Path(run_dir)
        Path(argv[argv.index("--junitxml") + 1]).write_text(
            "<testsuite tests='1' failures='1' errors='0' skipped='0'>"
            "<testcase classname='source' name='case_0'><failure message='boom'/></testcase></testsuite>",
            encoding="utf-8",
        )
        write_json(
            Path(argv[argv.index("--origin-output") + 1]),
            {"stage": "source", "origin": str(aib / "packages/runtime/src/ai_base_runtime/__init__.py")},
        )
        raise RuntimeError("source product test failed")

    monkeypatch.setattr(cli(), "run_development_command", failing_command)

    assert cli().main(["source", "--aib-root", str(aib), "--python", str(python), "--data-root", str(data_root)]) == 1

    receipt = json.loads((seen_run_dir / "evidence/aib-joint-development-receipt.json").read_text(encoding="utf-8"))
    assert receipt["status"] == "failed"
    assert receipt["source_after"] == receipt["source_before"]
    assert receipt["junit"]["valid"] is False
    assert receipt["module_origins"]["payload"]["stage"] == "source"
    assert_phase_timings(
        receipt["timings"],
        {
            "setup": "measured",
            "snapshot": "measured",
            "build": "not_applicable",
            "install": "not_applicable",
            "test": "failed",
            "post_run_verification": "measured",
        },
    )


@pytest.mark.parametrize(
    "receipt_update",
    [
        {"returncode": 1, "timed_out": False, "cleanup_uncertain": False},
        {"returncode": None, "timed_out": True, "cleanup_uncertain": True},
        {"returncode": 0, "timed_out": False, "cleanup_uncertain": True},
    ],
)
def test_source_command_failure_receipt_fails_even_with_green_artifacts(tmp_path, monkeypatch, receipt_update):
    dashboard = dashboard_source(init_git_repo(tmp_path / "dashboard"))
    (dashboard / "scripts/validation").mkdir(parents=True)
    (dashboard / "scripts/validation/aib_joint_dev_worker.py").write_text("# copied worker\n", encoding="utf-8")
    aib = runtime_source(init_git_repo(tmp_path / "aib"))
    python = executable(tmp_path / "python/Scripts/python.exe")
    data_root = tmp_path / "runs"
    seen_run_dir = None

    def failing_command(argv, *, cwd, run_dir, label, timeout):
        nonlocal seen_run_dir
        seen_run_dir = Path(run_dir)
        Path(argv[argv.index("--junitxml") + 1]).write_text(
            "<testsuite tests='1' failures='0' errors='0' skipped='0'>"
            "<testcase classname='source' name='case_0'/></testsuite>",
            encoding="utf-8",
        )
        write_json(
            Path(argv[argv.index("--origin-output") + 1]),
            {"stage": "source", "origin": str(aib / "packages/runtime/src/ai_base_runtime/__init__.py")},
        )
        receipt = {"label": label, "argv": [str(part) for part in argv], **receipt_update}
        raise inputs().DevelopmentCommandError("source command failed", receipt)

    monkeypatch.setattr(cli(), "run_development_command", failing_command)

    assert cli().main(["source", "--aib-root", str(aib), "--python", str(python), "--data-root", str(data_root)]) == 1

    receipt = json.loads((seen_run_dir / "evidence/aib-joint-development-receipt.json").read_text(encoding="utf-8"))
    assert receipt["status"] == "failed"
    assert receipt["commands"][0] == {"label": "source-tests", "argv": receipt["commands"][0]["argv"], **receipt_update}
    assert receipt["junit"]["valid"] is True
    assert receipt["module_origins"]["payload"]["stage"] == "source"
    assert receipt["timings"]["phases"]["test"]["state"] == "failed"
    assert receipt["timings"]["phases"]["post_run_verification"]["state"] == "measured"


def test_source_request_rejects_overlap_unowned_root_and_foreign_interpreter(tmp_path):
    module = inputs()
    dashboard = dashboard_source(init_git_repo(tmp_path / "dashboard"))
    aib = runtime_source(init_git_repo(tmp_path / "aib"))
    python = executable(tmp_path / "venv/Scripts/python.exe")
    data_root = tmp_path / "data"

    with pytest.raises(ValueError, match="outside"):
        module.validate_source_request(aib, python, dashboard / "runs", dashboard_root=dashboard)

    data_root.mkdir()
    (data_root / "foreign.txt").write_text("must remain\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unowned"):
        module.validate_source_request(aib, python, data_root, dashboard_root=dashboard)
    assert (data_root / "foreign.txt").read_text(encoding="utf-8") == "must remain\n"

    repo_python = executable(aib / ".venv/Scripts/python.exe")
    with pytest.raises(ValueError, match="interpreter"):
        module.validate_source_request(aib, repo_python, tmp_path / "clean-data", dashboard_root=dashboard)


def test_source_inventory_includes_tracked_and_unignored_new_code_only(tmp_path):
    module = inputs()
    repo = init_git_repo(tmp_path / "repo")
    (repo / "tracked.py").write_text("tracked\n", encoding="utf-8")
    (repo / "new_tool.py").write_text("new\n", encoding="utf-8")
    (repo / ".env.local").write_text("SECRET=value\n", encoding="utf-8")
    (repo / "cache").mkdir()
    (repo / "cache/blob.py").write_text("cache\n", encoding="utf-8")
    (repo / ".gitignore").write_text("cache/\n", encoding="utf-8")
    import subprocess

    subprocess.run(["git", "add", "tracked.py", ".gitignore"], cwd=repo, check=True, capture_output=True, timeout=15)

    inventory = module.source_inventory(repo)
    paths = {item["path"] for item in inventory["files"]}
    assert {"tracked.py", "new_tool.py", ".gitignore"}.issubset(paths)
    assert ".env.local" not in paths
    assert "cache/blob.py" not in paths


def test_input_drift_rejects_changed_source_bytes(tmp_path):
    module = inputs()
    repo = init_git_repo(tmp_path / "repo")
    source = repo / "tool.py"
    source.write_text("before\n", encoding="utf-8")
    import subprocess

    subprocess.run(["git", "add", "tool.py"], cwd=repo, check=True, capture_output=True, timeout=15)
    before = module.source_inventory(repo)
    source.write_text("after\n", encoding="utf-8")

    with pytest.raises(ValueError, match="drift"):
        module.assert_inventory_unchanged(repo, before)


@pytest.mark.parametrize(
    "stage,expected,observed",
    [
        ("source", "D:/owned/aib/packages/runtime/src", "D:/old/site-packages/ai_base_runtime/__init__.py"),
        ("wheel", "D:/owned/venv", "D:/AIGC/Report_creater_agent/packages/runtime/src/ai_base_runtime/__init__.py"),
    ],
)
def test_worker_rejects_wrong_import_origin(stage, expected, observed):
    with pytest.raises(ValueError, match="origin"):
        worker().validate_module_origin(stage, Path(expected), Path(observed))


def test_cli_invalid_stage_has_no_side_effects(tmp_path, capsys):
    data_root = tmp_path / "runs"
    assert cli().main(["unknown", "--data-root", str(data_root)]) == 2
    assert not data_root.exists()
    assert "usage:" in capsys.readouterr().err


def test_failure_receipt_is_development_only_and_preserves_command_logs(tmp_path):
    run_dir = tmp_path / "run"
    log_dir = run_dir / "logs"
    log_dir.mkdir(parents=True)
    write_json(log_dir / "source-tests.command.json", {"label": "source-tests", "returncode": 1})
    evidence = run_dir / "evidence"
    evidence.mkdir()
    (evidence / "source-tests.xml").write_text(
        "<testsuite tests='1' failures='0' errors='0' skipped='0'/>",
        encoding="utf-8",
    )
    write_json(evidence / "source-origin.json", {"origin": "D:/owned/src/ai_base_runtime/__init__.py"})
    write_json(evidence / "package-probe.json", {"distribution": "ai-base-runtime"})

    receipt = cli().failure_receipt(
        "source",
        run_dir,
        RuntimeError("boom"),
        before={"aib": {}},
        after={"aib": {"inventorySha256": "after"}},
        timings={"test_seconds": 1.25},
    )

    assert receipt["kind"] == "aib-joint-development-run"
    assert receipt["status"] == "failed"
    assert receipt["acceptance_eligible"] is False
    assert receipt["commands"] == [{"label": "source-tests", "returncode": 1}]
    assert receipt["source_after"] == {"aib": {"inventorySha256": "after"}}
    assert receipt["junit"]["valid"] is False
    assert receipt["module_origins"]["payload"]["origin"].endswith("__init__.py")
    assert receipt["package_probe"]["payload"]["distribution"] == "ai-base-runtime"
    assert receipt["timings"]["test_seconds"] == 1.25
    assert "PASS" not in json.dumps(receipt)


def test_development_receipt_cannot_be_promoted_to_formal_inputs(tmp_path, monkeypatch):
    dashboard = dashboard_source(tmp_path / "dashboard")
    owned = tmp_path / "owned"
    write_json(owned / "owner.json", {"owner": "mdb2-windows-closure", "root": str(owned), "repository": str(dashboard)})
    receipt = write_json(
        owned / "dev-receipt.json",
        {"kind": "aib-joint-development-run", "stage": "source", "acceptance_eligible": False},
    )
    formal = formal_input_with_development_receipt(tmp_path, receipt)

    import scripts.validation.windows_qualification_inputs as formal_inputs

    monkeypatch.setattr(formal_inputs, "ROOT", dashboard)
    with pytest.raises(QualificationError, match="source.kind=commit"):
        formal_inputs.load_request(formal, owned / "out.json", profile="functional")

    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["acceptance_eligible"] is False
    assert sha256(receipt) == json.loads(formal.read_text(encoding="utf-8"))["checks"]["evidence_bindings"]["task:1.1"]["sha256"]


@pytest.mark.parametrize(
    "command",
    [
        {"label": "lane", "returncode": 1, "timed_out": False, "cleanup_uncertain": False},
        {"label": "lane", "returncode": None, "timed_out": True, "cleanup_uncertain": True},
        {"label": "lane", "returncode": 0, "timed_out": False, "cleanup_uncertain": True},
    ],
)
def test_success_receipt_rejects_failed_command_family(tmp_path, command):
    junit = tmp_path / "tests.xml"
    junit.write_text(
        "<testsuite tests='1' failures='0' errors='0' skipped='0'>"
        "<testcase classname='lane' name='case_0'/></testsuite>",
        encoding="utf-8",
    )
    origin = write_json(tmp_path / "origin.json", {"stage": "source", "origin": "D:/aib/ai_base_runtime/__init__.py"})
    with pytest.raises(ValueError, match="command"):
        cli()._receipt("source", tmp_path, {}, {}, cli()._timing_model(), [command], junit, origin)

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.tests.aib_joint_dev_support import (
    dashboard_source,
    init_git_repo,
    locked_wheelhouse,
    runtime_source,
    runtime_wheel,
    sha256,
    write_json,
)


def wheel_module():
    return importlib.import_module("scripts.validation.aib_joint_dev_wheel")


def inputs():
    return importlib.import_module("scripts.validation.aib_joint_dev_inputs")


def dev_cli():
    return importlib.import_module("scripts.validation.aib_joint_dev")


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


def test_private_manifest_uses_actual_wheel_bytes_without_release_source_claims(tmp_path):
    wheel = runtime_wheel(tmp_path / "dist/ai_base_runtime-0.1.1.dev8-py3-none-any.whl")
    manifest = wheel_module().build_development_manifest(
        wheel,
        aib_inventory={"dirty": True, "files": [{"path": "packages/runtime/src/ai_base_runtime/__init__.py"}]},
        dashboard_inventory={"dirty": True, "files": [{"path": "ai_host/runtime_artifact.json"}]},
    )

    assert manifest["kind"] == "aib-private-development-wheel"
    assert manifest["wheelSha256"] == sha256(wheel)
    assert manifest["packageFiles"]["ai_base_runtime/__init__.py"]
    assert manifest["acceptanceEligible"] is False
    assert "sourceCommit" not in manifest
    assert "sourceTree" not in manifest


def test_wheel_request_rejects_lock_drift_and_never_creates_data_root(tmp_path):
    dashboard = dashboard_source(init_git_repo(tmp_path / "dashboard"))
    aib = runtime_source(init_git_repo(tmp_path / "aib"))
    wheelhouse_root = tmp_path / "wheel-root"
    wheelhouse, lock, lock_sha = locked_wheelhouse(wheelhouse_root)
    (wheelhouse / "django-6.0.7-py3-none-any.whl").write_bytes(b"changed")
    data_root = tmp_path / "data"

    with pytest.raises(ValueError, match="lock|hash|mismatch"):
        inputs().validate_wheel_request(
            aib,
            tmp_path / "Python313/python.exe",
            tmp_path / "build/Scripts/python.exe",
            wheelhouse,
            lock,
            lock_sha,
            data_root,
            dashboard_root=dashboard,
        )
    assert not data_root.exists()


@pytest.mark.parametrize(
    "xml",
    [
        "<testsuite tests='0' failures='0' errors='0' skipped='0'/>",
        "<testsuite tests='1' failures='0' errors='0' skipped='0'/>",
        "<testsuite tests='2' failures='0' errors='0' skipped='0'><testcase classname='lane' name='case_0'/></testsuite>",
        "<testsuite tests='1' failures='1' errors='0' skipped='0'><testcase><failure/></testcase></testsuite>",
        "<testsuite tests='1' failures='0' errors='0' skipped='1'><testcase><skipped/></testcase></testsuite>",
        "<root><testcase classname='lane' name='case_0'/></root>",
        "<not-xml",
    ],
)
def test_junit_summary_rejects_zero_failure_skip_and_malformed_outputs(tmp_path, xml):
    report = tmp_path / "tests.xml"
    report.write_text(xml, encoding="utf-8")

    with pytest.raises(ValueError):
        dev_cli().summarize_successful_junit(report)


def test_copy_dashboard_snapshot_updates_only_the_copy_manifest(tmp_path):
    dashboard = dashboard_source(init_git_repo(tmp_path / "dashboard"))
    original_manifest = (dashboard / "ai_host/runtime_artifact.json").read_text(encoding="utf-8")
    target = tmp_path / "snapshot"
    manifest = {
        "kind": "aib-private-development-wheel",
        "distribution": "ai-base-runtime",
        "version": "0.1.1.dev8",
        "wheelSha256": "1" * 64,
        "packageFiles": {"ai_base_runtime/__init__.py": "2" * 64},
        "acceptanceEligible": False,
    }

    copied = wheel_module().copy_dashboard_snapshot(dashboard, target, manifest)

    assert json.loads((copied / "ai_host/runtime_artifact.json").read_text(encoding="utf-8")) == manifest
    assert (dashboard / "ai_host/runtime_artifact.json").read_text(encoding="utf-8") == original_manifest


def test_runtime_snapshot_copies_only_inventoried_runtime_files(tmp_path):
    aib = runtime_source(init_git_repo(tmp_path / "aib"))
    (aib / "packages/runtime/secret.txt").write_text("do not copy\n", encoding="utf-8")
    inventory = inputs().source_inventory(aib, "packages/runtime")

    copied = wheel_module().copy_runtime_snapshot(aib, tmp_path / "runtime-copy", inventory)

    assert (copied / "src/ai_base_runtime/__init__.py").is_file()
    assert not (copied / "secret.txt").exists()


def test_runtime_snapshot_rejects_after_inventory_drift(tmp_path):
    aib = runtime_source(init_git_repo(tmp_path / "aib"))
    inventory = inputs().source_inventory(aib, "packages/runtime")
    (aib / "packages/runtime/src/ai_base_runtime/__init__.py").write_text("changed\n", encoding="utf-8")

    with pytest.raises(ValueError, match="drift|hash"):
        wheel_module().copy_runtime_snapshot(aib, tmp_path / "runtime-copy", inventory)


def test_runtime_snapshot_rejects_reparse_inventory_entries(tmp_path, monkeypatch):
    aib = runtime_source(init_git_repo(tmp_path / "aib"))
    inventory = inputs().source_inventory(aib, "packages/runtime")
    target_name = "packages/runtime/src/ai_base_runtime/__init__.py"
    input_module = inputs()

    def fake_reparse(path: Path) -> bool:
        return path.as_posix().endswith(target_name)

    monkeypatch.setattr(input_module, "is_reparse_or_symlink", fake_reparse)
    with pytest.raises(ValueError, match="reparse|symlink"):
        wheel_module().copy_runtime_snapshot(aib, tmp_path / "runtime-copy", inventory)


def test_wheel_stage_child_python_commands_use_no_bytecode_flag(tmp_path, monkeypatch):
    dashboard = dashboard_source(init_git_repo(tmp_path / "dashboard"))
    (dashboard / "scripts/validation").mkdir(parents=True)
    (dashboard / "scripts/validation/aib_joint_dev_worker.py").write_text("# copied worker\n", encoding="utf-8")
    aib = runtime_source(init_git_repo(tmp_path / "aib"))
    run_dir = tmp_path / "run"
    request = SimpleNamespace(
        dashboard_root=dashboard,
        aib_root=aib,
        bootstrap_python=tmp_path / "bootstrap/python.exe",
        build_python=tmp_path / "build/python.exe",
        wheelhouse=SimpleNamespace(wheelhouse=tmp_path / "wheelhouse"),
    )
    commands = []

    def fake_command(argv, *, cwd, label, run_dir, timeout):
        argv = [str(part) for part in argv]
        commands.append((label, argv))
        assert argv[1:3] == ["-I", "-B"]
        if label == "build-wheel":
            wheel_dir = Path(argv[argv.index("--wheel-dir") + 1])
            runtime_wheel(wheel_dir / "ai_base_runtime-0.1.1.dev8-py3-none-any.whl")
        elif label == "probe-package":
            write_json(Path(argv[argv.index("--output") + 1]), {"distribution": "ai-base-runtime"})
        elif label == "wheel-tests":
            Path(argv[argv.index("--junitxml") + 1]).write_text(
                "<testsuite tests='1' failures='0' errors='0' skipped='0'>"
                "<testcase classname='wheel' name='case_0'/></testsuite>",
                encoding="utf-8",
            )
            write_json(
                Path(argv[argv.index("--origin-output") + 1]),
                {"stage": "wheel", "origin": str(run_dir / "env/private-wheel/Lib/site-packages/ai_base_runtime/__init__.py")},
            )
        return {"label": label, "argv": argv, "returncode": 0}

    module = wheel_module()
    monkeypatch.setattr(module, "_command", fake_command)
    monkeypatch.setattr(module, "verify_wheelhouse_lock", lambda lock: lock)
    monkeypatch.setattr(module, "verify_installed_package_files", lambda manifest, site_root: {"files": manifest["packageFiles"]})

    result = module.prepare_wheel_run(request, run_dir)

    assert [label for label, _ in commands] == [
        "build-wheel",
        "create-venv",
        "install-private-wheel",
        "install-dashboard-requirements",
        "probe-package",
        "wheel-tests",
    ]
    assert result["module_origins"]["payload"]["stage"] == "wheel"
    assert_phase_timings(
        result["timings"],
        {
            "setup": "measured",
            "snapshot": "measured",
            "build": "measured",
            "install": "measured",
            "test": "measured",
            "post_run_verification": "measured",
        },
    )
    assert [item["name"] for item in result["timings"]["phases"]["snapshot"]["segments"]] == [
        "aib_runtime_copy",
        "dashboard_copy_after_build",
    ]


@pytest.mark.parametrize(
    "failed_label,failed_phase,expected_labels",
    [
        ("build-wheel", "build", ["build-wheel"]),
        ("create-venv", "install", ["build-wheel", "create-venv"]),
        ("install-private-wheel", "install", ["build-wheel", "create-venv", "install-private-wheel"]),
        (
            "install-dashboard-requirements",
            "install",
            ["build-wheel", "create-venv", "install-private-wheel", "install-dashboard-requirements"],
        ),
        (
            "probe-package",
            "test",
            ["build-wheel", "create-venv", "install-private-wheel", "install-dashboard-requirements", "probe-package"],
        ),
        (
            "wheel-tests",
            "test",
            [
                "build-wheel",
                "create-venv",
                "install-private-wheel",
                "install-dashboard-requirements",
                "probe-package",
                "wheel-tests",
            ],
        ),
    ],
)
@pytest.mark.parametrize(
    "receipt_update",
    [
        {"returncode": 1, "timed_out": False, "cleanup_uncertain": False},
        {"returncode": None, "timed_out": True, "cleanup_uncertain": True},
        {"returncode": 0, "timed_out": False, "cleanup_uncertain": True},
    ],
)
def test_wheel_command_failures_stop_stage_and_preserve_receipt(
    tmp_path, monkeypatch, failed_label, failed_phase, expected_labels, receipt_update,
):
    dashboard = dashboard_source(init_git_repo(tmp_path / "dashboard"))
    (dashboard / "scripts/validation").mkdir(parents=True)
    (dashboard / "scripts/validation/aib_joint_dev_worker.py").write_text("# copied worker\n", encoding="utf-8")
    aib = runtime_source(init_git_repo(tmp_path / "aib"))
    run_dir = tmp_path / "run"
    request = SimpleNamespace(
        dashboard_root=dashboard,
        aib_root=aib,
        bootstrap_python=tmp_path / "bootstrap/python.exe",
        build_python=tmp_path / "build/python.exe",
        wheelhouse=SimpleNamespace(wheelhouse=tmp_path / "wheelhouse"),
    )
    commands = []

    def fake_command(argv, *, cwd, label, run_dir, timeout):
        argv = [str(part) for part in argv]
        commands.append(label)
        wheel_dir = run_dir / "build/wheels"
        wheel_dir.mkdir(parents=True, exist_ok=True)
        runtime_wheel(wheel_dir / "ai_base_runtime-0.1.1.dev8-py3-none-any.whl")
        evidence = run_dir / "evidence"
        evidence.mkdir(parents=True, exist_ok=True)
        write_json(evidence / "package-probe.json", {"distribution": "ai-base-runtime"})
        (evidence / "wheel-tests.xml").write_text(
            "<testsuite tests='1' failures='0' errors='0' skipped='0'>"
            "<testcase classname='wheel' name='case_0'/></testsuite>",
            encoding="utf-8",
        )
        write_json(
            evidence / "wheel-origin.json",
            {"stage": "wheel", "origin": str(run_dir / "env/private-wheel/Lib/site-packages/ai_base_runtime/__init__.py")},
        )
        receipt = {"label": label, "argv": argv, **receipt_update}
        if label == failed_label:
            raise inputs().DevelopmentCommandError(f"{label} failed", receipt)
        return {"label": label, "argv": argv, "returncode": 0, "timed_out": False, "cleanup_uncertain": False}

    module = wheel_module()
    monkeypatch.setattr(module, "_command", fake_command)
    monkeypatch.setattr(module, "verify_wheelhouse_lock", lambda lock: lock)
    monkeypatch.setattr(module, "verify_installed_package_files", lambda manifest, site_root: {"files": manifest["packageFiles"]})

    with pytest.raises(module.WheelRunError) as captured:
        module.prepare_wheel_run(request, run_dir)

    assert commands == expected_labels
    context = captured.value.context
    assert context["commands"][-1] == {"label": failed_label, "argv": context["commands"][-1]["argv"], **receipt_update}
    assert context["timings"]["phases"][failed_phase]["state"] == "failed"
    if failed_label == "wheel-tests":
        assert context["source_after"]["dashboard"] == context["source_after"]["dashboard"]
        assert context["timings"]["phases"]["post_run_verification"]["state"] == "measured"


def test_wheel_failed_test_keeps_timing_and_postcheck_context(tmp_path, monkeypatch):
    dashboard = dashboard_source(init_git_repo(tmp_path / "dashboard"))
    (dashboard / "scripts/validation").mkdir(parents=True)
    (dashboard / "scripts/validation/aib_joint_dev_worker.py").write_text("# copied worker\n", encoding="utf-8")
    aib = runtime_source(init_git_repo(tmp_path / "aib"))
    run_dir = tmp_path / "run"
    request = SimpleNamespace(
        dashboard_root=dashboard,
        aib_root=aib,
        bootstrap_python=tmp_path / "bootstrap/python.exe",
        build_python=tmp_path / "build/python.exe",
        wheelhouse=SimpleNamespace(wheelhouse=tmp_path / "wheelhouse"),
    )

    def fake_command(argv, *, cwd, label, run_dir, timeout):
        argv = [str(part) for part in argv]
        if label == "build-wheel":
            wheel_dir = Path(argv[argv.index("--wheel-dir") + 1])
            runtime_wheel(wheel_dir / "ai_base_runtime-0.1.1.dev8-py3-none-any.whl")
        elif label == "probe-package":
            write_json(Path(argv[argv.index("--output") + 1]), {"distribution": "ai-base-runtime"})
        elif label == "wheel-tests":
            Path(argv[argv.index("--junitxml") + 1]).write_text(
                "<testsuite tests='1' failures='1' errors='0' skipped='0'>"
                "<testcase classname='wheel' name='case_0'><failure message='boom'/></testcase></testsuite>",
                encoding="utf-8",
            )
            write_json(
                Path(argv[argv.index("--origin-output") + 1]),
                {"stage": "wheel", "origin": str(run_dir / "env/private-wheel/Lib/site-packages/ai_base_runtime/__init__.py")},
            )
            raise RuntimeError("wheel tests failed")
        return {"label": label, "argv": argv, "returncode": 0}

    module = wheel_module()
    monkeypatch.setattr(module, "_command", fake_command)
    monkeypatch.setattr(module, "verify_wheelhouse_lock", lambda lock: lock)
    monkeypatch.setattr(module, "verify_installed_package_files", lambda manifest, site_root: {"files": manifest["packageFiles"]})

    with pytest.raises(module.WheelRunError) as captured:
        module.prepare_wheel_run(request, run_dir)

    context = captured.value.context
    assert context["source_after"]["dashboard"] == context["source_after"]["dashboard"]
    assert_phase_timings(
        context["timings"],
        {
            "setup": "measured",
            "snapshot": "measured",
            "build": "measured",
            "install": "measured",
            "test": "failed",
            "post_run_verification": "measured",
        },
    )


def test_package_probe_rejects_installed_bytes_that_do_not_match_manifest(tmp_path):
    site = tmp_path / "venv/Lib/site-packages"
    package = site / "ai_base_runtime"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("changed\n", encoding="utf-8")
    manifest = {
        "distribution": "ai-base-runtime",
        "version": "0.1.1.dev8",
        "wheelSha256": "1" * 64,
        "packageFiles": {"ai_base_runtime/__init__.py": "2" * 64},
    }

    with pytest.raises(ValueError, match="package"):
        wheel_module().verify_installed_package_files(manifest, site)

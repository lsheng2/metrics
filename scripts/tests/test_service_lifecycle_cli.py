from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import service_lifecycle_engine.engine as lifecycle_module
import service_lifecycle_engine_cli
from service_lifecycle_engine import ServiceLifecycleEngine, ServiceSpec


def test_doctor_resolves_relative_paths_from_workspace(monkeypatch, tmp_path, capsys):
    workspace = tmp_path / "workspace"
    config = workspace / "scripts" / "services.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({"project_name": "sample", "services": [{"name": "web", "preferred_ports": [8123], "command": [sys.executable, "server.py"]}]}), encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.chdir(outside)

    args = argparse.Namespace(
        workspace=str(workspace),
        service_config="scripts/services.json",
        instance="default",
        state_directory="state/service-lifecycle-engine",
        json=True,
        fail_on_problem=False,
    )

    service_lifecycle_engine_cli.run_doctor(args)

    diagnostics = json.loads(capsys.readouterr().out)
    assert diagnostics[0]["service"] == "web"
    assert diagnostics[0]["status"] == "not_registered"


def test_diagnose_services_reports_identity_unknown_for_running_legacy_state(monkeypatch, tmp_path):
    lifecycle = ServiceLifecycleEngine("test-project", tmp_path, state_directory=tmp_path / "state")
    lifecycle.write_state({"web": {"port": 8123, "pid": 12345, "health_url": ""}})
    spec = ServiceSpec.from_values("web", [8123], [sys.executable, "server.py"])

    monkeypatch.setattr(lifecycle_module, "process_exists", lambda pid: True)

    diagnostics = lifecycle.diagnose_services((spec,), port_process_resolver=lambda host, port: [12345])

    assert diagnostics[0]["status"] == "identity_unknown"
    assert diagnostics[0]["command_matches"] is None


def test_doctor_fail_on_problem_exits_nonzero_for_identity_unknown(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    config = workspace / "services.json"
    workspace.mkdir()
    config.write_text(json.dumps({"project_name": "sample", "services": [{"name": "web", "preferred_ports": [8123], "command": [sys.executable, "server.py"]}]}), encoding="utf-8")
    state_directory = workspace / "state"
    lifecycle = ServiceLifecycleEngine("sample", workspace, state_directory=state_directory)
    lifecycle.write_state({"web": {"port": 8123, "pid": 12345, "health_url": ""}})
    monkeypatch.setattr(lifecycle_module, "process_exists", lambda pid: True)

    args = argparse.Namespace(
        workspace=str(workspace),
        service_config=str(config),
        instance="default",
        state_directory=str(state_directory),
        json=True,
        fail_on_problem=True,
    )

    try:
        service_lifecycle_engine_cli.run_doctor(args)
    except SystemExit as error:
        assert error.code == 1
    else:
        raise AssertionError("doctor should fail on identity_unknown when requested")


def test_legacy_port_lifecycle_cli_entrypoint_is_removed():
    assert importlib.util.find_spec("port_lifecycle_cli") is None

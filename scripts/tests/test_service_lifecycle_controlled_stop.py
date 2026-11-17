from __future__ import annotations

import importlib
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from service_lifecycle_engine import PlatformOperationSet, ServiceLifecycleEngine

controlled_stop_module = importlib.import_module("service_lifecycle_engine.controlled_stop")


def test_stopServiceShouldFormatStopCommandWithPersistedIdentity(tmp_path):
    commands = []
    operations = PlatformOperationSet(
        process_exists=lambda pid: pid == 12345,
        process_matches_command=lambda pid, command: True,
        process_start_marker=lambda pid: "started:12345",
        run_command=lambda command, cwd: commands.append((command, cwd)),
        wait_process_exit=lambda pid, timeout: True,
    )
    lifecycle = ServiceLifecycleEngine("project", tmp_path, state_directory=tmp_path / "state", platform_ops=operations)
    lifecycle.write_state({
        "api": {
            "host": "127.0.0.1",
            "port": 8100,
            "pid": 12345,
            "lifecycle_state": "ready",
            "command": ["python", "api.py"],
            "stop_command": [
                "python",
                "scripts/service_lifecycle_engine/controlled_stop.py",
                "--pid",
                "{pid}",
                "--expected-start-marker",
                "{process_start_marker}",
                "--expected-command-line",
                "{command_line}",
            ],
            "provenance": {
                "wrapper_pid": 12345,
                "process_start_marker": "started:12345",
                "command_line": "python api.py",
                "capability": "registered_process",
            },
        }
    })

    result = lifecycle.stop_service("api", graceful_timeout_seconds=0.1)

    assert result.reason == "stop_command"
    assert commands == [
        (
            (
                "python",
                "scripts/service_lifecycle_engine/controlled_stop.py",
                "--pid",
                "12345",
                "--expected-start-marker",
                "started:12345",
                "--expected-command-line",
                "python api.py",
            ),
            tmp_path.resolve(),
        )
    ]


def test_controlledStopShouldRejectWrongProcessIdentity(monkeypatch):
    calls = []
    monkeypatch.setattr(controlled_stop_module.platform_ops, "process_exists", lambda pid: True)
    monkeypatch.setattr(controlled_stop_module.platform_ops, "process_start_marker", lambda pid: "observed")
    monkeypatch.setattr(controlled_stop_module.platform_ops, "get_process_command_line", lambda pid: "python api.py")
    monkeypatch.setattr(controlled_stop_module, "send_control_event", lambda pid, event: calls.append((pid, event)) or {"sent": True})

    result = controlled_stop_module.controlled_stop(12345, expected_start_marker="expected", expected_command_line="python api.py")

    assert result["reason"] == "identity_mismatch"
    assert result["exit_code"] == 3
    assert calls == []


@pytest.mark.parametrize("marker,command", [("", ""), ("", "python api.py"), ("started", ""), (" ", "python api.py")])
def test_controlled_stop_requires_complete_identity_before_observing_or_signalling(monkeypatch, marker, command):
    calls = []
    monkeypatch.setattr(controlled_stop_module.platform_ops, "process_exists", lambda pid: True)
    monkeypatch.setattr(controlled_stop_module.platform_ops, "process_start_marker", lambda pid: marker)
    monkeypatch.setattr(controlled_stop_module.platform_ops, "get_process_command_line", lambda pid: command)
    monkeypatch.setattr(controlled_stop_module, "send_control_event", lambda *args: calls.append(args) or {"sent": True})
    result = controlled_stop_module.controlled_stop(12345, expected_start_marker=marker, expected_command_line=command)
    assert result["reason"] == "missing_identity"
    assert result["exit_code"] != 0
    assert calls == []


def test_windows_sigterm_request_does_not_silently_send_ctrl_c(monkeypatch):
    calls = []
    monkeypatch.setattr(controlled_stop_module, "send_windows_control_event", lambda *args: calls.append(args) or {"sent": True})
    result = controlled_stop_module.send_control_event(12345, "sigterm")
    assert result["sent"] is False
    assert calls == []

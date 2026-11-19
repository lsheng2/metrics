from contextlib import nullcontext
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from service_lifecycle_engine import PlatformOperationSet, ProcessExitObservation, ServiceLifecycleEngine


COMMAND = ("python", "api.py")


def lifecycle(tmp_path, phase, *, exited=True, exit_code=0):
    state = {"alive": True, "matches": True, "code": None, "checks": 0}
    actions = []

    def end_original():
        state.update(alive=not exited, matches=False, code=exit_code if exited else None)

    def matches(pid, command):
        state["checks"] += 1
        if phase == "before-terminate" and state["checks"] == 2:
            end_original()
        return state["matches"]

    def waited(seconds):
        end_original()
        return False

    operations = PlatformOperationSet(
        process_exists=lambda pid: state["alive"],
        process_matches_command=matches,
        process_start_marker=lambda pid: "original" if state["matches"] else "changed",
        run_command=lambda command, cwd: actions.append("stop-command"),
        terminate_process=lambda pid: actions.append("terminate"),
        terminate_is_forceful=True,
        kill_process=lambda pid: actions.append("kill"),
        wait_process_exit=lambda pid, seconds: waited(seconds),
        wait_port_available=lambda host, port, timeout: True,
        observe_process_exit=lambda pid: nullcontext(ProcessExitObservation(lambda: state["code"], waited)),
    )
    engine = ServiceLifecycleEngine("exit-race", tmp_path, state_directory=tmp_path / "state", platform_ops=operations)
    engine.write_state({
        "api": {
            "host": "127.0.0.1", "port": 8100, "pid": 12345, "lifecycle_state": "ready",
            "command": list(COMMAND), "stop_command": ["stop"] if phase == "after-command" else [],
            "provenance": {
                "wrapper_pid": 12345, "process_start_marker": "original", "capability": "registered_process",
            },
        },
    })
    return engine, actions


@pytest.mark.parametrize(("phase", "reason", "forced"), [
    ("after-command", "stop_command", False),
    ("before-terminate", "already_stopped", False),
    ("after-terminate", "terminated", True),
])
def test_retained_exit_reconciles_registered_late_exit(tmp_path, phase, reason, forced):
    engine, actions = lifecycle(tmp_path, phase)
    result = engine.stop_service("api", graceful_timeout_seconds=0.1)
    assert result.stopped is True
    assert result.exit_code == 0
    assert result.reason == reason
    assert result.forced is forced
    assert result.force_requested is False
    assert "kill" not in actions
    assert engine.read_state()["api"]["lifecycle_state"] == "stopped"


@pytest.mark.parametrize("phase", ["after-command", "before-terminate", "after-terminate"])
def test_live_changed_identity_without_retained_exit_is_never_killed(tmp_path, phase):
    engine, actions = lifecycle(tmp_path, phase, exited=False)
    result = engine.stop_service("api", graceful_timeout_seconds=0.1)
    assert result.stopped is False
    assert result.exit_code is None
    assert "identity_changed" in result.reason
    assert "kill" not in actions


def test_pid_file_recovery_does_not_kill_a_changed_identity_after_wait(tmp_path):
    engine, actions = lifecycle(tmp_path, "after-terminate", exited=False)
    result = engine._stop_process(
        "api", 8100, 12345, 0.1, "pid_file_recovery", expected_command=COMMAND,
    )
    assert actions == ["terminate"]
    assert result.stopped is False
    assert result.forced is True
    assert result.reason == "pid_file_recovery:identity_changed_before_kill"


def test_pid_file_recovery_reports_retained_late_exit_without_followup_kill(tmp_path):
    engine, actions = lifecycle(tmp_path, "after-terminate")
    result = engine._stop_process(
        "api", 8100, 12345, 0.1, "pid_file_recovery", expected_command=COMMAND,
    )
    assert actions == ["terminate"]
    assert result.stopped is True
    assert result.forced is True
    assert result.exit_code == 0
    assert result.reason == "pid_file_recovery:terminated"


def test_active_nonzero_late_exit_is_not_a_normal_noop_stop(tmp_path):
    from e2e_bug_trend import normal_stop_result

    engine, actions = lifecycle(tmp_path, "before-terminate", exit_code=3)
    result = engine.stop_service("api", graceful_timeout_seconds=0.1)
    assert result.stopped is True
    assert result.exit_code == 3
    assert actions == []
    assert normal_stop_result(result) is False

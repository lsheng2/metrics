from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from service_lifecycle_engine import PlatformOperationSet, ServiceLifecycleEngine, ServiceSpec, StopResult


def test_normal_prepare_does_not_treat_unregistered_pid_files_as_stop_authority(tmp_path):
    terminated = []
    operations = PlatformOperationSet(
        process_exists=lambda pid: True,
        process_matches_command=lambda pid, command: True,
        terminate_process=terminated.append,
        wait_process_exit=lambda pid, timeout: True,
    )
    engine = ServiceLifecycleEngine("isolation", tmp_path, state_directory=tmp_path / "sle", platform_ops=operations)
    engine._write_pid_file("unselected", 8101, 12345, ("python", "other.py"))
    selected = ServiceSpec.from_values("api", [8100], ["python", "api.py"])
    engine.prepare_startup([selected])
    assert terminated == []
    assert engine._pid_file("unselected", 8101).exists()


def test_explicit_generic_grace_override_is_not_silently_ignored(tmp_path):
    observed = []
    engine = ServiceLifecycleEngine("override", tmp_path, state_directory=tmp_path / "sle")
    engine.write_state({"api": {"pid": 12345, "port": 8100, "lifecycle_state": "ready"}})

    def stop(name, graceful_timeout_seconds):
        observed.append(graceful_timeout_seconds)
        return StopResult(name, 8100, 12345, True, False, "stop_command", exit_code=0)

    engine.stop_service = stop
    selected = ServiceSpec.from_values("api", [8100], ["python", "api.py"], graceful_timeout_seconds=15)
    engine.prepare_startup([selected], graceful_timeout_seconds=0.7)
    assert observed == [0.7]

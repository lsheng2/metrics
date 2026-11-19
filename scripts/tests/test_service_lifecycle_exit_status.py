from pathlib import Path
import json
import socket
import subprocess
import sys
from types import SimpleNamespace
from contextlib import nullcontext
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import e2e_bug_trend
from service_lifecycle_engine import ServiceLifecycleEngine, ServiceSpec
from service_lifecycle_engine import platform_ops


@pytest.mark.parametrize("code,expected", [(0, True), (3, False), (None, False)])
def test_normal_stop_requires_observed_zero_service_exit(code, expected):
    result = SimpleNamespace(
        name="api", stopped=True, forced=False, reason="stop_command", exit_code=code,
    )
    assert e2e_bug_trend.normal_stop_result(result) is expected


def test_already_stopped_noop_allows_explicit_recovery_without_rewriting_prior_exit():
    result = SimpleNamespace(
        name="api", stopped=True, forced=False, reason="already_stopped", exit_code=3,
    )
    assert e2e_bug_trend.normal_stop_result(result)
    assert result.exit_code == 3


@pytest.mark.parametrize("entry", ["start_runtime", "start_selected_runtime"])
def test_restart_refuses_new_work_when_this_attempt_stopped_abnormally(tmp_path, entry):
    from service_lifecycle_engine import StopResult

    args = SimpleNamespace(
        workspace=str(tmp_path), grafana_bin=sys.executable, grafana_homepath=str(tmp_path),
        service_config=str(ROOT / "scripts/e2e_bug_trend.services.json"),
        django_ports="9100", grafana_ports="9200", scope_id="synthetic",
        begin="2026-01-01", end="2026-02-01", open_entrypoint="none",
    )
    reached = []

    class Boundary:
        def restart_services(self, specs, **options):
            callback = options.get("after_prepare")
            if callback is not None:
                callback([StopResult("api", 9100, 12345, True, False, "stop_command", exit_code=3)])
            reached.append("start")
            raise AssertionError("Service start was reached")

        def profile_step(self, label, callback, **options):
            reached.append(label)
            raise AssertionError("Mutation was reached")

    with pytest.raises(RuntimeError, match="Abnormal service stop"):
        getattr(e2e_bug_trend, entry)(args, tmp_path, Boundary())
    assert reached == []


@pytest.mark.parametrize("exit_code,separate_stopper", [(0, False), (3, True)])
def test_native_service_exit_is_preserved_in_result_and_termination_record(tmp_path, exit_code, separate_stopper):
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    stop_file = tmp_path / "stop"
    worker = tmp_path / "worker.py"
    worker.write_text(
        "import pathlib, socket, sys, time\n"
        "server = socket.socket()\n"
        "server.bind(('127.0.0.1', int(sys.argv[1])))\n"
        "server.listen()\n"
        "while not pathlib.Path(sys.argv[2]).exists():\n"
        "    time.sleep(0.01)\n"
        "server.close()\n"
        "raise SystemExit(int(sys.argv[3]))\n",
        encoding="utf-8",
    )
    engine = ServiceLifecycleEngine("exit-proof", tmp_path, state_directory=tmp_path / "sle")
    spec = ServiceSpec.from_values(
        "api", [port], [sys.executable, str(worker), "{port}", str(stop_file), str(exit_code)],
        stop_command=[sys.executable, "-c", "import pathlib,sys; pathlib.Path(sys.argv[1]).touch()", str(stop_file)],
        health_url=None, graceful_timeout_seconds=5,
    )
    state = engine.start_service(spec, port=port)
    try:
        if separate_stopper:
            program = (
                "import dataclasses,json,sys; from pathlib import Path; sys.path.insert(0,sys.argv[1]); "
                "from service_lifecycle_engine import ServiceLifecycleEngine; "
                "root=Path(sys.argv[2]); e=ServiceLifecycleEngine('exit-proof',root,state_directory=root/'sle'); "
                "print(json.dumps(dataclasses.asdict(e.stop_service('api',graceful_timeout_seconds=5)),default=str))"
            )
            stopped = subprocess.run(
                [sys.executable, "-I", "-c", program, str(ROOT / "scripts"), str(tmp_path)],
                check=True, capture_output=True, text=True, timeout=60,
            )
            result = SimpleNamespace(**json.loads(stopped.stdout.splitlines()[-1]))
        else:
            result = engine.stop_service("api", graceful_timeout_seconds=5)
    finally:
        if platform_ops.process_exists(state.pid):
            stop_file.touch()
            if not platform_ops.wait_process_exit(state.pid, 5):
                platform_ops.kill_process(state.pid)
                platform_ops.wait_process_exit(state.pid, 5)
    assert result.stopped and not result.forced
    assert getattr(result, "exit_code", None) == exit_code
    records = list((tmp_path / "sle").rglob("*.jsonl"))
    events = [json.loads(line) for path in records for line in path.read_text(encoding="utf-8").splitlines() if line]
    assert any(row.get("service") == "api" and row.get("exit_code") == exit_code for row in events)


def test_stop_waits_on_retained_process_observation_not_early_pid_status(tmp_path):
    from service_lifecycle_engine import PlatformOperationSet

    class Observation:
        ended = False

        def __call__(self):
            return 0 if self.ended else None

        def wait(self, seconds):
            self.ended = True
            return True

    observation = Observation()
    operations = PlatformOperationSet(
        process_exists=lambda pid: not observation.ended,
        process_matches_command=lambda pid, command: True,
        process_start_marker=lambda pid: "started",
        run_command=lambda command, cwd: None,
        wait_process_exit=lambda pid, seconds: True,
        observe_process_exit=lambda pid: nullcontext(observation),
    )
    engine = ServiceLifecycleEngine("wait-proof", tmp_path, state_directory=tmp_path / "sle", platform_ops=operations)
    engine.write_state({"api": {
        "pid": 12345, "port": 8100, "lifecycle_state": "ready", "command": ["python", "api.py"],
        "stop_command": ["stop"], "provenance": {"wrapper_pid": 12345, "process_start_marker": "started",
                                              "capability": "registered_process"},
    }})
    result = engine.stop_service("api", graceful_timeout_seconds=5)
    assert observation.ended
    assert result.exit_code == 0


def test_windows_observation_can_wait_for_process_signal_after_exit_code_is_set(monkeypatch):
    import ctypes
    from ctypes import wintypes
    from service_lifecycle_engine import observe_process_exit

    ended = {"value": False}

    def wait(handle, milliseconds):
        if milliseconds:
            ended["value"] = True
        return 0 if ended["value"] else 258

    def query(handle, pointer):
        ctypes.cast(pointer, ctypes.POINTER(wintypes.DWORD))[0] = 0
        return True

    kernel = SimpleNamespace(
        OpenProcess=Mock(return_value=42), WaitForSingleObject=Mock(side_effect=wait),
        GetExitCodeProcess=Mock(side_effect=query), CloseHandle=Mock(return_value=True),
    )
    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: kernel)
    with observe_process_exit(987654321) as observation:
        assert observation() is None
        assert observation.wait(0.3)
        assert observation() == 0

from __future__ import annotations

from contextlib import contextmanager
import subprocess
import sys
import time

import pytest


def test_process_classifier_rejects_foreign_or_unresolved_metrics_workload():
    from scripts.validation.windows_host_processes import classify_process_observations

    rows = [
        {"pid": 11, "identity": "owned-candidate", "command": ["python", "windows_perf_entry.py"], "metrics_workload": True},
        {"pid": 12, "identity": "foreign", "command": ["python", "manage.py", "serve"], "metrics_workload": True},
        {"pid": 13, "identity": None, "command": ["python", "manage.py", "serve"], "metrics_workload": True},
        {"pid": 14, "identity": "pytest", "command": ["python", "-m", "pytest"], "metrics_workload": False},
    ]

    result = classify_process_observations(rows, owned_identities={"owned-candidate"})

    assert [row["classification"] for row in result["processes"]] == [
        "owned_measurement",
        "foreign_relevant",
        "unresolved_relevant",
        "tooling_unrelated",
    ]
    assert result["certification_blockers"] == ["foreign_relevant:12", "unresolved_relevant:13"]
    assert all("manage.py serve" not in row.get("command_fingerprint", "") for row in result["processes"])


def test_raw_process_rows_are_enriched_from_real_command_and_creation_evidence(tmp_path):
    from scripts.validation.windows_host_processes import (
        classify_process_observations,
        enrich_process_observations,
        process_identity,
    )

    repo = tmp_path / "repo"
    owned = tmp_path / "owned"
    repo.mkdir()
    owned.mkdir()
    python = owned / "venv" / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.write_text("python", encoding="utf-8")
    owned_command = f'"{python}" -I "{repo / "ai_host/tests/windows_perf_entry.py"}" serve --root "{owned}"'
    foreign_command = f'"C:/Python313/python.exe" -I "{repo / "manage.py"}" runserver'

    rows = [
        {"pid": 101, "parent_pid": 1, "name": "python.exe", "threads": 2},
        {"pid": 202, "parent_pid": 1, "name": "python.exe", "threads": 2},
        {"pid": 303, "parent_pid": 1, "name": "python.exe", "threads": 2},
        {"pid": 404, "parent_pid": 1, "name": "explorer.exe", "threads": 20},
    ]
    enriched = enrich_process_observations(rows, {
        101: {"command_line": owned_command, "creation_date": "20261120101010.000000+480", "executable_path": str(python)},
        202: {"command_line": foreign_command, "creation_date": "20261120101110.000000+480", "executable_path": "C:/Python313/python.exe"},
        303: {"command_line": "", "creation_date": "", "executable_path": "C:/Python313/python.exe", "sensor_error": "access_denied"},
    }, source_root=repo, owned_root=owned)

    owned_identity = process_identity(101, "20261120101010.000000+480", owned_command)
    result = classify_process_observations(enriched, owned_identities={owned_identity})

    assert [row["classification"] for row in result["processes"]] == [
        "owned_measurement",
        "foreign_relevant",
        "unresolved_relevant",
        "tooling_unrelated",
    ]
    assert result["certification_blockers"] == ["foreign_relevant:202", "unresolved_relevant:303"]


def test_cleanup_requires_descendant_and_listener_absence_not_parent_exit_only():
    from scripts.validation.windows_host_processes import cleanup_is_normal, stop_arms

    parent_only = {
        "services": {"candidate": {"stopped": True, "exit_code": 0, "forced": False, "force_requested": False, "reason": "stop_command"}},
        "normal": True,
        "owned_descendants_absent": False,
        "listeners_absent": True,
    }

    assert cleanup_is_normal(parent_only) is False
    parent_only["owned_descendants_absent"] = True
    assert cleanup_is_normal(parent_only) is True

    missing_facts = {
        "services": {"candidate": {"stopped": True, "exit_code": 0, "forced": False, "force_requested": False, "reason": "stop_command"}},
        "normal": True,
    }
    assert cleanup_is_normal(missing_facts) is False


def test_stop_arms_derives_descendant_and_listener_absence_from_observations():
    from scripts.service_lifecycle_engine.models import StopResult
    from scripts.validation.windows_host_processes import stop_arms

    class Ops:
        def process_exists(self, pid):
            return pid == 321

        def get_listening_process_ids(self, host, port):
            return [321] if port == 8123 else []

    class Engine:
        platform_ops = Ops()

        def read_state(self):
            return {"candidate": {"pid": 321, "host": "127.0.0.1", "port": 8123}}

        def stop_service(self, name, *, graceful_timeout_seconds):
            return StopResult(name, 8123, 321, True, False, "stop_command", exit_code=0)

    cleanup = stop_arms(Engine(), ["candidate"])

    assert cleanup["normal"] is False
    assert cleanup["owned_descendants_absent"] is False
    assert cleanup["listeners_absent"] is False


def test_stop_arms_retains_descendant_exit_observation_before_stop(monkeypatch):
    from scripts.service_lifecycle_engine.models import StopResult
    from scripts.validation import windows_host_processes as processes
    from scripts.validation.windows_host_processes import stop_arms

    monkeypatch.setattr(processes, "living_children", lambda root_pid: [
        {"pid": 556, "parent_pid": root_pid, "created": 123},
    ])

    class Observation:
        def __init__(self, pid):
            self.pid = pid

        def wait(self, seconds):
            return self.pid != 556

        def __call__(self):
            return 0 if self.pid != 556 else None

    class Ops:
        def process_exists(self, pid):
            return pid == 556

        def get_listening_process_ids(self, host, port):
            return []

        @contextmanager
        def observe_process_exit(self, pid):
            yield Observation(pid)

    class Engine:
        platform_ops = Ops()

        def read_state(self):
            return {"candidate": {"pid": 321, "host": "127.0.0.1", "port": 8123}}

        def stop_service(self, name, *, graceful_timeout_seconds):
            return StopResult(name, 8123, 321, True, False, "stop_command", exit_code=0)

    cleanup = stop_arms(Engine(), ["candidate"])

    assert cleanup["normal"] is False
    assert cleanup["owned_descendants_absent"] is False
    assert cleanup["observations"]["candidate"]["owned_processes"][556]["terminal_exit_code"] is None
    assert "owned_process_still_running:556" in cleanup["observations"]["candidate"]["observation_errors"]


def test_stop_arms_missing_pid_port_or_platform_observation_is_failure():
    from scripts.service_lifecycle_engine.models import StopResult
    from scripts.validation.windows_host_processes import stop_arms

    class Engine:
        platform_ops = None

        def read_state(self):
            return {"candidate": {"host": "127.0.0.1"}}

        def stop_service(self, name, *, graceful_timeout_seconds):
            return StopResult(name, -1, None, True, False, "stop_command", exit_code=0)

    cleanup = stop_arms(Engine(), ["candidate"])

    assert cleanup["normal"] is False
    assert cleanup["owned_descendants_absent"] is False
    assert cleanup["listeners_absent"] is False
    assert cleanup["observations"]["candidate"]["observation_errors"]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Toolhelp inventory is required")
def test_owned_toy_child_inventory_and_retained_exit_handle_survive_parent_exit(tmp_path):
    from ai_host.exit_processes import living_children
    from scripts.service_lifecycle_engine import platform_ops
    from scripts.service_lifecycle_engine.process_exit import observe_process_exit

    ready = tmp_path / "ready.txt"
    release = tmp_path / "release.txt"
    child_pid_file = tmp_path / "child-pid.txt"
    child_code = "import time; time.sleep(1)"
    parent_code = "\n".join([
        "import subprocess, sys, time",
        "from pathlib import Path",
        "ready=Path(sys.argv[1]); release=Path(sys.argv[2]); child_pid=Path(sys.argv[3])",
        "child=subprocess.Popen([sys.executable, '-I', '-c', sys.argv[4]])",
        "child_pid.write_text(str(child.pid), encoding='utf-8')",
        "ready.write_text('ready', encoding='utf-8')",
        "deadline=time.monotonic()+5",
        "while not release.exists() and time.monotonic()<deadline:",
        "    time.sleep(0.02)",
        "sys.exit(0)",
    ])
    parent = subprocess.Popen(
        [sys.executable, "-I", "-c", parent_code, str(ready), str(release), str(child_pid_file), child_code]
    )
    child_pid = None
    try:
        deadline = time.monotonic() + 5
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ready.exists()
        child_pid = int(child_pid_file.read_text(encoding="utf-8"))
        children = living_children(root_pid=parent.pid)
        assert child_pid in {row["pid"] for row in children}
        with observe_process_exit(parent.pid) as parent_exit, observe_process_exit(child_pid) as child_exit:
            release.write_text("stop", encoding="utf-8")
            assert parent.wait(timeout=5) == 0
            assert parent_exit() == 0
            assert child_exit.wait(5)
            assert child_exit() == 0
    finally:
        if parent.poll() is None:
            parent.terminate()
            parent.wait(timeout=5)
        if child_pid and platform_ops.process_exists(child_pid):
            platform_ops.kill_process(child_pid)

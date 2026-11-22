from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
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


def test_process_relevance_covers_validation_pytest_and_git_write_families(tmp_path):
    from scripts.validation.windows_host_processes import enrich_process_observations

    repo = tmp_path / "repo"
    owned = tmp_path / "owned"
    repo.mkdir()
    owned.mkdir()
    rows = [
        {"pid": 10, "name": "python.exe"},
        {"pid": 11, "name": "python.exe"},
        {"pid": 12, "name": "git.exe"},
        {"pid": 13, "name": "git.exe"},
        {"pid": 14, "name": "python.exe"},
    ]
    details = {
        10: {"command_line": f'"{sys.executable}" -I "{repo / "scripts/validation/windows_host_qualification.py"}" --phase performance', "creation_date": "a"},
        11: {"command_line": f'"{sys.executable}" -m pytest "{repo / "ai_host/tests/conformance_performance_cases.py"}"', "creation_date": "b"},
        12: {"command_line": f'git -C "{repo}" commit -m perf', "creation_date": "c"},
        13: {"command_line": f'git -C "{repo}" status --porcelain', "creation_date": "d"},
        14: {"command_line": f'"{sys.executable}" -m pytest "{tmp_path / "other/tests.py"}"', "creation_date": "e"},
    }

    enriched = enrich_process_observations(rows, details, source_root=repo, owned_root=owned)

    by_pid = {row["pid"]: row for row in enriched}
    assert by_pid[10]["metrics_workload"] is True
    assert by_pid[10]["relevance"] == "performance_validation"
    assert by_pid[11]["metrics_workload"] is True
    assert by_pid[11]["relevance"] == "performance_validation"
    assert by_pid[12]["metrics_workload"] is True
    assert by_pid[12]["relevance"] == "git_write"
    assert by_pid[13]["metrics_workload"] is False
    assert by_pid[13]["relevance"] == "git_read"
    assert by_pid[14]["metrics_workload"] is False
    assert by_pid[14]["relevance"] == "tooling_unrelated"


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
    from scripts.validation import windows_host_process_cleanup as cleanup
    from scripts.validation.windows_host_processes import stop_arms

    monkeypatch.setattr(cleanup, "living_children", lambda root_pid: [
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


def test_owner_registration_rejects_descendant_native_creation_mismatch(monkeypatch):
    from scripts.validation import windows_host_process_identity as identity
    from scripts.service_lifecycle_engine import platform_ops

    class Ops:
        def process_command_line(self, pid):
            return f"python.exe child-{pid}"

        def process_start_marker(self, pid):
            return f"marker-{pid}"

    monkeypatch.setattr(identity, "living_children", lambda root_pid: [
        {"pid": 556, "parent_pid": root_pid, "created": 111, "name": "conhost.exe"},
    ])
    monkeypatch.setattr(platform_ops, "get_process_created_at", lambda pid: f"created-{pid}")
    monkeypatch.setattr(identity, "native_process_rows_by_pid", lambda pids: {
        int(pid): {
            "pid": int(pid),
            "parent_pid": 321 if int(pid) == 556 else 1,
            "name": "conhost.exe" if int(pid) == 556 else "python.exe",
        } for pid in pids
    })

    class Capture:
        def __init__(self, rows):
            self.rows = rows

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def facts(self):
            return {
                row["pid"]: {
                    "handle_opened": True,
                    "native_creation": 222 if row["pid"] == 556 else 333,
                    "parent_pid": row["parent_pid"],
                    "image_name": row["name"],
                } for row in self.rows
            }

    monkeypatch.setattr(identity, "ProcessWindowCapture", Capture)

    facts = identity.owned_process_identity_facts_from_state(
        {"pid": 321, "provenance": {"process_start_marker": "marker-321"}}, Ops(),
    )

    assert 321 in {row["pid"] for row in facts["registrations"]}
    assert 556 not in {row["pid"] for row in facts["registrations"]}


def test_cleanup_native_observation_does_not_default_non_python_descendant_image(monkeypatch):
    from contextlib import ExitStack, contextmanager
    from scripts.validation import windows_host_process_cleanup as cleanup

    calls = []
    monkeypatch.setattr(cleanup, "living_children", lambda root_pid: [
        {"pid": 556, "parent_pid": root_pid, "created": 111},
    ])

    def fake_native(pid, *, parent_pid=None, image_name=""):
        calls.append((pid, image_name))
        return {
            "handle_opened": True, "handle_closed": True, "native_creation": 111,
            "parent_pid": parent_pid, "image_name": "conhost.exe",
        }

    monkeypatch.setattr(cleanup, "native_process_fact", fake_native)

    class Ops:
        @contextmanager
        def observe_process_exit(self, pid):
            yield lambda: 0

    with ExitStack() as stack:
        capture = cleanup._capture_owned_process_observations({"pid": 321}, Ops(), stack, run_id="window-1")

    assert (556, "") in calls
    assert capture["owned_processes"][556]["native_image_name"] == "conhost.exe"


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
        "deadline=time.monotonic()+30",
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


@pytest.mark.skipif(sys.platform != "win32", reason="Windows command and creation sensors are required")
def test_admitted_toy_interpreter_identity_matches_sensor_and_sle_registry(tmp_path):
    from scripts.service_lifecycle_engine import PlatformOperationSet
    from scripts.service_lifecycle_engine import platform_ops
    from scripts.validation import windows_host_environment as environment
    from scripts.validation.windows_host_processes import (
        classify_process_observations,
        enrich_process_observations,
        owned_process_identity_facts_from_state,
        process_identity,
    )
    from ai_host.exit_processes import living_children

    ready = tmp_path / "ready.txt"
    release = tmp_path / "release.txt"
    code = "\n".join([
        "import json, os, sys, time",
        "from pathlib import Path",
        "Path(sys.argv[1]).write_text(json.dumps({'pid': os.getpid(), 'executable': sys.executable}), encoding='utf-8')",
        "deadline=time.monotonic()+30",
        "release=Path(sys.argv[2])",
        "while not release.exists() and time.monotonic()<deadline:",
        "    time.sleep(0.02)",
    ])
    child = subprocess.Popen([sys.executable, "-I", "-c", code, str(ready), str(release)])
    diagnostic = {"expected_pid": child.pid, "attempts": []}
    try:
        deadline = time.monotonic() + 5
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ready.exists()
        ready_payload = json.loads(ready.read_text(encoding="utf-8"))
        ops = PlatformOperationSet()
        facts, observed_identity, details = {}, None, {}
        observed_pid = int(ready_payload["pid"])
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            state = {
                "pid": child.pid,
                "provenance": {"process_start_marker": ops.process_start_marker(child.pid)},
            }
            facts = owned_process_identity_facts_from_state(state, ops)
            details = environment._windows_process_details([{"pid": observed_pid, "name": "python.exe"}]).get(observed_pid, {})
            command_line = details.get("command_line") or ""
            created = details.get("creation_date") or ""
            observed_identity = process_identity(observed_pid, created, command_line)
            descendants = living_children(root_pid=child.pid)
            diagnostic["attempts"].append({
                "poll": child.poll(),
                "process_exists": platform_ops.process_exists(observed_pid),
                "cim_row_present": bool(details),
                "command_present": bool(command_line),
                "creation_present": bool(created),
                "executable_present": bool(details.get("executable_path")),
                "ready_pid_matches": observed_pid == child.pid,
                "ready_pid_is_descendant": observed_pid in {row["pid"] for row in descendants},
                "command_sha256": hashlib.sha256(command_line.encode("utf-8")).hexdigest() if command_line else None,
                "sensor_identity_present": bool(observed_identity),
                "sle_marker_present": bool(facts.get("sle_marker")),
                "descendant_identity_present": observed_identity in facts.get("identities", set()),
            })
            if observed_identity and observed_identity in facts.get("identities", set()):
                break
            time.sleep(0.1)
        enriched = enrich_process_observations(
            [{"pid": observed_pid, "name": "python.exe", "parent_pid": child.pid}],
            {observed_pid: details},
            source_root=Path.cwd(),
            owned_root=tmp_path,
        )
        enriched[0]["metrics_workload"] = True

        result = classify_process_observations(enriched, owned_identities=facts["identities"])

        evidence_dir = Path(os.environ.get("PERF_PROBE_EVIDENCE_DIR", str(tmp_path / "evidence")))
        evidence_dir.mkdir(parents=True, exist_ok=True)
        diagnostic.update({
            "result": "observed" if observed_identity and facts.get("sle_marker") else "missing_sensor_fact",
            "ready_pid": ready_payload.get("pid"),
            "pid_redirector_mismatch": ready_payload.get("pid") != child.pid,
            "last_attempt": diagnostic["attempts"][-1] if diagnostic["attempts"] else {},
            "classification": result["processes"][0]["classification"],
        })
        (evidence_dir / "observation-followup-toy-identity.json").write_text(
            json.dumps(diagnostic, sort_keys=True, indent=2) + "\n", encoding="utf-8",
        )
        assert child.poll() is None, diagnostic
        if ready_payload.get("pid") != child.pid:
            assert diagnostic["last_attempt"]["ready_pid_is_descendant"], diagnostic
        assert details, diagnostic
        assert details.get("command_line") and details.get("creation_date") and details.get("executable_path"), diagnostic
        assert facts["sle_marker"] or facts["descendant_identities"], diagnostic
        assert observed_identity in facts["identities"]
        assert result["processes"][0]["classification"] == "owned_measurement"
    finally:
        release.write_text("stop", encoding="utf-8")
        child.wait(timeout=5)

from __future__ import annotations

from contextlib import contextmanager
import json
from types import SimpleNamespace

import pytest


def test_measurement_window_binds_verdict_before_guard_release(tmp_path, monkeypatch):
    from scripts.validation import windows_host_environment as environment

    monkeypatch.setattr(environment, "source_snapshot", lambda root: {"head": "same"})
    monkeypatch.setattr(environment, "machine_snapshot", lambda **kwargs: {"processes": [], "cpu": {"idle": 1, "kernel": 2, "user": 3}})
    run = tmp_path / "run"
    run.mkdir()

    with environment.MeasurementWindow(tmp_path, run, tmp_path) as window:
        verdict = run / "receipt.json"
        verdict.write_text('{"status":"PASS"}\n', encoding="utf-8")
        window.bind_verdict(verdict)
        assert (tmp_path / "HEAVY_RUN_ACTIVE").exists()

    record = environment.read_json(run / "measurement-window.json")
    assert record["result"] == "PASS"
    assert record["verdict"]["path"] == str(verdict)
    assert record["verdict"]["guard_id"] == record["id"]
    assert record["verdict"]["written_monotonic"] <= record["ended_monotonic"]
    assert not (tmp_path / "HEAVY_RUN_ACTIVE").exists()


def test_measurement_window_writer_failure_cannot_leave_pass(tmp_path, monkeypatch):
    from scripts.validation import windows_host_environment as environment

    monkeypatch.setattr(environment, "source_snapshot", lambda root: {"head": "same"})
    monkeypatch.setattr(environment, "machine_snapshot", lambda **kwargs: {"processes": [], "cpu": {"idle": 1, "kernel": 2, "user": 3}})
    run = tmp_path / "run"
    run.mkdir()

    with pytest.raises(ValueError):
        with environment.MeasurementWindow(tmp_path, run, tmp_path) as window:
            window.record["errors"].append("writer_failed")

    record = environment.read_json(run / "measurement-window.json")
    assert record["result"] == "FAIL"
    assert not (tmp_path / "HEAVY_RUN_ACTIVE").exists()


def test_measurement_window_blocks_foreign_relevant_workload(tmp_path, monkeypatch):
    from scripts.validation import windows_host_environment as environment

    monkeypatch.setattr(environment, "source_snapshot", lambda root: {"head": "same"})
    monkeypatch.setattr(environment, "machine_snapshot", lambda **kwargs: {
        "processes": [{"pid": 9, "identity": "foreign", "command": ["python", "manage.py", "serve"], "metrics_workload": True}],
        "cpu": {"idle": 1, "kernel": 2, "user": 3},
    })
    run = tmp_path / "run"
    run.mkdir()

    with pytest.raises(ValueError, match="relevant"):
        with environment.MeasurementWindow(tmp_path, run, tmp_path, owned_process_identities={"owned"}):
            pass

    record = environment.read_json(run / "measurement-window.json")
    assert record["result"] == "FAIL"
    assert record["process_classification"]["certification_blockers"] == ["foreign_relevant:9"]


def test_measurement_window_blocks_foreign_workload_derived_from_raw_snapshot(tmp_path, monkeypatch):
    from scripts.validation import windows_host_environment as environment
    from scripts.validation.windows_host_processes import enrich_process_observations

    repo = tmp_path / "repo"
    owned = tmp_path / "owned"
    repo.mkdir()
    owned.mkdir()
    foreign_command = f'"C:/Python313/python.exe" -I "{repo / "manage.py"}" runserver'
    monkeypatch.setattr(environment, "source_snapshot", lambda root: {"head": "same"})
    monkeypatch.setattr(environment, "machine_snapshot", lambda source_root=None, owned_root=None: {
        "processes": enrich_process_observations(
            [{"pid": 12, "parent_pid": 1, "name": "python.exe", "threads": 2}],
            {12: {"command_line": foreign_command, "creation_date": "20261120101110.000000+480", "executable_path": "C:/Python313/python.exe"}},
            source_root=repo,
            owned_root=owned,
        ),
        "cpu": {"idle": 1, "kernel": 2, "user": 3},
    })
    run = tmp_path / "run"
    run.mkdir()

    with pytest.raises(ValueError, match="relevant"):
        with environment.MeasurementWindow(owned, run, repo, owned_process_identities={"not-foreign"}):
            pass

    record = environment.read_json(run / "measurement-window.json")
    assert record["result"] == "FAIL"
    assert record["process_classification"]["certification_blockers"] == ["foreign_relevant:12"]


def test_measurement_window_does_not_fallback_to_unenriched_snapshot(tmp_path, monkeypatch):
    from scripts.validation import windows_host_environment as environment

    monkeypatch.setattr(environment, "source_snapshot", lambda root: {"head": "same"})
    monkeypatch.setattr(environment, "machine_snapshot", lambda: {"processes": [], "cpu": {"idle": 1, "kernel": 2, "user": 3}})
    run = tmp_path / "run"
    run.mkdir()

    with pytest.raises(TypeError):
        with environment.MeasurementWindow(tmp_path, run, tmp_path):
            pass


def test_measurement_window_persists_only_sanitized_process_rows(tmp_path, monkeypatch):
    from scripts.validation import windows_host_environment as environment

    monkeypatch.setattr(environment, "source_snapshot", lambda root: {"head": "same"})
    monkeypatch.setattr(environment, "machine_snapshot", lambda **kwargs: {
        "processes": [{
            "pid": 7,
            "identity": "irrelevant",
            "command": ["python.exe", "-m", "pytest", "--token=secret"],
            "command_line": "python.exe -m pytest --token=secret",
            "executable_path": "C:/Python313/python.exe",
            "metrics_workload": False,
        }],
        "cpu": {"idle": 1, "kernel": 2, "user": 3},
    })
    run = tmp_path / "run"
    run.mkdir()

    with environment.MeasurementWindow(tmp_path, run, tmp_path) as window:
        verdict = run / "receipt.json"
        verdict.write_text('{"status":"PASS"}\n', encoding="utf-8")
        window.bind_verdict(verdict)

    lines = [json.loads(line) for line in (run / "machine.jsonl").read_text(encoding="utf-8").splitlines()]
    persisted = lines[0]["processes"][0]
    assert "command" not in persisted
    assert "command_line" not in persisted
    assert "executable_path" not in persisted
    assert "secret" not in json.dumps(lines)


def test_windows_process_details_never_executes_process_names_or_cim(monkeypatch):
    from scripts.validation import windows_host_environment as environment

    captured = {}

    @contextmanager
    def native_capture(rows, *, capture_details):
        captured["rows"] = rows
        assert capture_details is True
        yield SimpleNamespace(details=lambda: {
            1: {"command_line": "python.exe", "creation_date": "2026-11-26T12:00:00",
                "executable_path": "C:/Python/python.exe"},
        })

    def forbidden_spawn(*_args, **_kwargs):
        raise AssertionError("Process details must not spawn PowerShell/CIM")

    monkeypatch.setattr(environment, "capture_process_window", native_capture)
    monkeypatch.setattr(environment.subprocess, "run", forbidden_spawn)
    rows = [
        {"pid": 1, "name": "python.exe\"; throw \"boom", "threads": 1},
    ]

    details = environment._windows_process_details(rows)

    assert captured["rows"] == rows
    assert details[1]["command_line"] == "python.exe"


def _write_prepared_lifecycle_state(run_root, service_root, *, pid, command):
    lifecycle = service_root / "lifecycle"
    lifecycle.mkdir(parents=True)
    payload = {
        "services": {
            "candidate_saturated": {
                "name": "candidate_saturated",
                "pid": pid,
                "port": 8123,
                "host": "127.0.0.1",
                "command": command,
                "lifecycle_state": "prepared",
                "provenance": {
                    "wrapper_pid": pid,
                    "process_start_marker": "sle-marker",
                    "capability": "registered_process",
                },
            }
        }
    }
    (lifecycle / "windows-host-qualification-qualification.json").write_text(
        json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8",
    )


def test_measurement_window_uses_observed_identity_registration_not_persisted_state(tmp_path, monkeypatch):
    from scripts.validation import windows_host_environment as environment
    from scripts.validation.windows_host_processes import process_identity

    run = tmp_path / "run"
    raw_phase = run / "raw" / "development"
    command = [
        "D:/AIGC/pf1120/venv/Scripts/python.exe", "-I",
        str(tmp_path / "repo" / "ai_host/tests/windows_perf_entry.py"),
        "serve", "--root", str(raw_phase), "--instance", str(raw_phase / "candidate_saturated"),
    ]
    command_line = " ".join(command)
    wrapper_identity = process_identity(34772, "11/20/2026 9:46:23 PM", command_line)
    child_identity = process_identity(15040, "11/20/2026 9:46:23 PM", command_line + " child")
    _write_prepared_lifecycle_state(run, raw_phase, pid=34772, command=command)
    monkeypatch.setattr(environment, "source_snapshot", lambda root: {"head": "same"})
    monkeypatch.setattr(environment, "machine_snapshot", lambda **kwargs: {
        "processes": [
            {
                "pid": 34772,
                "parent_pid": 1,
                "name": "python.exe",
                "identity": wrapper_identity,
                "command": command,
                "metrics_workload": True,
                "relevance": "metrics_runtime",
            },
            {
                "pid": 15040,
                "parent_pid": 34772,
                "name": "python.exe",
                "identity": child_identity,
                "command": ["python.exe", "-c", "child"],
                "metrics_workload": True,
                "relevance": "metrics_runtime",
            },
        ],
        "cpu": {"idle": 1, "kernel": 2, "user": 3},
    })
    run.mkdir(exist_ok=True)

    with environment.MeasurementWindow(
        tmp_path, run, tmp_path, owned_process_identities={wrapper_identity, child_identity},
    ) as window:
        verdict = run / "receipt.json"
        verdict.write_text('{"status":"PASS"}\n', encoding="utf-8")
        window.bind_verdict(verdict)

    record = environment.read_json(run / "measurement-window.json")
    assert record["result"] == "PASS"
    assert record["snapshots"][0]["ownership_setup"]["startup_identity_count"] == 0
    assert record["snapshots"][0]["process_classification"]["certification_blockers"] == []


def test_measurement_window_rejects_same_basename_process_with_wrong_parent(tmp_path, monkeypatch):
    from scripts.validation import windows_host_environment as environment
    from scripts.validation.windows_host_processes import process_identity

    run = tmp_path / "run"
    raw_phase = run / "raw" / "development"
    command = [
        "D:/AIGC/pf1120/venv/Scripts/python.exe", "-I",
        str(tmp_path / "repo" / "ai_host/tests/windows_perf_entry.py"),
        "serve", "--root", str(raw_phase), "--instance", str(raw_phase / "candidate_saturated"),
    ]
    _write_prepared_lifecycle_state(run, raw_phase, pid=34772, command=command)
    foreign_command = " ".join(command)
    foreign_identity = process_identity(15040, "11/20/2026 9:46:23 PM", foreign_command)
    monkeypatch.setattr(environment, "source_snapshot", lambda root: {"head": "same"})
    monkeypatch.setattr(environment, "machine_snapshot", lambda **kwargs: {
        "processes": [
            {
                "pid": 34772,
                "parent_pid": 1,
                "name": "python.exe",
                "identity": process_identity(34772, "11/20/2026 9:46:23 PM", foreign_command),
                "command": command,
                "metrics_workload": True,
                "relevance": "metrics_runtime",
            },
            {
                "pid": 15040,
                "parent_pid": 99999,
                "name": "python.exe",
                "identity": foreign_identity,
                "command": command,
                "metrics_workload": True,
                "relevance": "metrics_runtime",
            },
        ],
        "cpu": {"idle": 1, "kernel": 2, "user": 3},
    })
    run.mkdir(exist_ok=True)

    with pytest.raises(ValueError, match="foreign_relevant:15040"):
        with environment.MeasurementWindow(tmp_path, run, tmp_path):
            pass

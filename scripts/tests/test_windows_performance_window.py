from __future__ import annotations

import json
import subprocess

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


def test_windows_process_details_does_not_embed_process_names_in_script(monkeypatch):
    from scripts.validation import windows_host_environment as environment

    captured = {}

    def fake_run(argv, **kwargs):
        captured["script"] = argv[-1]
        return subprocess.CompletedProcess(argv, 0, stdout="[]", stderr="")

    monkeypatch.setattr(environment.subprocess, "run", fake_run)

    environment._windows_process_details([
        {"pid": 1, "name": "python.exe\"; throw \"boom", "threads": 1},
    ])

    assert "boom" not in captured["script"]
    assert "python.exe" not in captured["script"]

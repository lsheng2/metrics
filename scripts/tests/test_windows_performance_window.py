from __future__ import annotations

import pytest


def test_measurement_window_binds_verdict_before_guard_release(tmp_path, monkeypatch):
    from scripts.validation import windows_host_environment as environment

    monkeypatch.setattr(environment, "source_snapshot", lambda root: {"head": "same"})
    monkeypatch.setattr(environment, "machine_snapshot", lambda: {"processes": [], "cpu": {"idle": 1, "kernel": 2, "user": 3}})
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
    monkeypatch.setattr(environment, "machine_snapshot", lambda: {"processes": [], "cpu": {"idle": 1, "kernel": 2, "user": 3}})
    run = tmp_path / "run"
    run.mkdir()

    with pytest.raises(ValueError):
        with environment.MeasurementWindow(tmp_path, run, tmp_path) as window:
            window.record["errors"].append("writer_failed")

    record = environment.read_json(run / "measurement-window.json")
    assert record["result"] == "FAIL"
    assert not (tmp_path / "HEAVY_RUN_ACTIVE").exists()


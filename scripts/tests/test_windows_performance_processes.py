from __future__ import annotations


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

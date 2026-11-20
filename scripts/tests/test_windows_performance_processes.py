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
    from scripts.validation.windows_host_processes import cleanup_is_normal

    parent_only = {
        "services": {"candidate": {"stopped": True, "exit_code": 0, "forced": False, "force_requested": False, "reason": "stop_command"}},
        "normal": True,
        "owned_descendants_absent": False,
        "listeners_absent": True,
    }

    assert cleanup_is_normal(parent_only) is False
    parent_only["owned_descendants_absent"] = True
    assert cleanup_is_normal(parent_only) is True


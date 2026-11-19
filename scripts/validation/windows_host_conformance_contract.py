"""Candidate-specific native lanes shared by execution and semantic replay."""
KIND = "windows-host-conformance"
B5_KEY = "clause:10.4:B5-stream-stop:functional"
B1_KEY = "clause:10.4:B1-native-second-signal:functional"
B4_KEY = "clause:10.4:B4-disconnect-leaks:functional"
NATIVE_KEYS = {B1_KEY, B4_KEY, B5_KEY}
TRIGGERS = ["stop-file", "SIGINT", "SIGTERM", "CTRL_BREAK_EVENT", "lifetime"]
NATIVE_BREAKS = ["stop-file", "CTRL_BREAK_EVENT"]
LIMITS = {"heartbeat": 2.0, "streams": 4.0, "requests": 4.0, "terminal_grace": 2.0}
BASE_ARGS = ["-q", "--tb=short", "-p", "no:cacheprovider", "-o", "asyncio_default_fixture_loop_scope=function"]
LANES = {
    "b5": {"targets": ["ai_host/tests/test_serve_native_streams.py"], "covered": [B5_KEY]},
    "backpressure": {
        "targets": ["ai_host/tests/conformance_backpressure_cases.py"], "plugin": True, "covered": [B5_KEY],
    },
    "disconnect": {"targets": ["ai_host/tests/test_serve_native_disconnect.py"], "covered": [B4_KEY]},
    "signal": {"targets": ["ai_host/tests/test_serve_native_signal.py"], "covered": [B1_KEY]},
    "failure": {"targets": ["ai_host/tests/test_serve_native_failure.py"], "covered": []},
    "recovery": {"targets": ["ai_host/tests/conformance_recovery_cases.py"], "covered": []},
}
LANE_TARGETS = {lane: tuple(config["targets"]) for lane, config in LANES.items()}


def _ids(module, names):
    return [f"{module}::{name}" for name in names]


_sdk_names = (
    "test_w1_host_public_composition", "test_w1_host_socket_identity_order", "test_w1_host_lifecycle_close",
    "test_w1_host_core_state", "test_w1_host_audit_duplicate_event_id", "test_w1_stream_terminal_before_eof",
    "test_w1_disconnect_slot_reclamation", "test_w1_stream_incremental_spacing", "test_w1_separate_quotas",
    "test_w1_body_cap_admission_order", "test_w1_short_timeout", "test_w1_diagnostics_snapshot",
    "test_w1_app_route_namespace", "test_w1_manifest_asset_boundaries", "test_w1_manifest_asset_denials",
    "test_w1_wsgi_loop_lag_assets", "test_w1_wsgi_loop_lag", "test_w1_wsgi_buffered_body_prerequisite",
    "test_w2_public_chat_pipeline", "test_w2_public_task_profile", "test_w2_public_approval_cycle",
)
_stream = "ai_host.tests.test_serve_native_streams"
_signal = "ai_host.tests.test_serve_native_signal"
EXPECTED_JUNIT_CASES = {
    "b5": _ids(_stream, [
        *(f"test_real_chat_streams_preserve_identity_and_terminate_before_normal_exit[{t}]" for t in TRIGGERS),
        *(f"test_controlled_active_idle_and_slow_stream_flush_before_normal_exit[{t}]" for t in TRIGGERS),
        *(f"test_non_reader_cannot_block_bounded_normal_exit[{t}]" for t in NATIVE_BREAKS),
    ]),
    "backpressure": [
        "ai_host.tests.conformance_backpressure_cases::test_installed_wsgi_queue_blocks_producer_until_consumed_and_releases_on_close[blocking_wsgi]",
        *(f"._conformance.py::{name}__blocking_wsgi" for name in _sdk_names),
    ],
    "disconnect": [
        "ai_host.tests.test_serve_native_disconnect::test_real_serve_repeated_stream_disconnects_release_runtime_slots_and_exit_cleanly",
    ],
    "failure": _ids("ai_host.tests.test_serve_native_failure", (
        "test_real_serve_observes_ended_runtime_and_exits_one",
        "test_real_serve_observes_internal_loop_fault_without_public_stop_and_releases_resources",
        "test_real_start_timeout_reports_rollback_and_releases_lock_after_exit[timeout-clean-1-True]",
        "test_real_start_timeout_reports_rollback_and_releases_lock_after_exit[timeout-stuck-3-False]",
    )),
    "recovery": ["ai_host.tests.conformance_recovery_cases::test_context_exit_then_os_exit_preserves_runs_sessions_approvals"],
    "signal": _ids(_signal, [
        *(f"test_native_normal_stop_triggers_complete_cleanup_and_exit_zero[{t}]" for t in TRIGGERS),
        *(f"test_native_second_signal_during_cleanup_exits_130_in_one_second[{p}-{t}]"
          for p in ("drain", "flush") for t in TRIGGERS),
        "test_native_second_control_event_after_stop_file_exits_130_in_one_second",
    ]),
}

"""Test-only observations around the unchanged installed adapter and serve."""
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ai_host.exit_inventory import install_exit_capture

install_exit_capture()

from dataclasses import asdict
import json
import signal
import threading
import time
from urllib.parse import urlsplit

from ai_host.tests.serve_test_entry import main


def emit(event, **values):
    print(json.dumps({"event": event, "at": time.monotonic(), **values}, separators=(",", ":")), flush=True)


def configure(temp):
    endpoint = sys.argv[4]
    if endpoint != "-" and urlsplit(endpoint).hostname != "127.0.0.1":
        raise ValueError("Synthetic model must use loopback")
    return {
        "METRICS_STATE_DIR": str(Path(sys.argv[1]) / "durable-state"),
        "METRICS_AI_MODEL_BASE_URL": "" if endpoint == "-" else endpoint,
        "METRICS_AI_MODEL_NAME": "" if endpoint == "-" else "scripted",
        "METRICS_AI_MODEL_API_KEY": "" if endpoint == "-" else "scripted-test-key",
    }


def prepare():
    import waitress
    from ai_host import lifecycle, package
    from ai_host.management.commands.serve import Command
    from ai_host.tests.conformance_runtime_probe import RuntimeProbe

    probe = RuntimeProbe()
    package.METRICS_APP = probe.package(base=package.METRICS_APP)
    original_server = waitress.create_server
    original_run = Command._run_bound_server
    original_wait = Command._wait_for_stop
    original_stop = lifecycle.stop_owned_resources
    original_flush = lifecycle._flush_waitress_channels

    def observed_server(*args, **kwargs):
        server = original_server(*args, **kwargs)
        probe.server = server
        return server

    def observed_wait(command, stop_event, stop_file, deadline, handle):
        probe.handle = handle
        trigger = sys.argv[5]
        emit(
            "stream_host_ready", deadline=deadline,
            threads=probe.server.adj.threads,
        )
        if trigger in {"SIGINT", "SIGTERM"}:
            def on_trigger():
                marker = Path(sys.argv[1]) / "signal"
                while not marker.exists() and not stop_event.is_set():
                    time.sleep(0.02)
                if marker.exists():
                    emit("stream_signal_sent", trigger=trigger)
                    signal.raise_signal(getattr(signal, trigger))

            threading.Thread(target=on_trigger, name="test-stream-signal", daemon=True).start()
        return original_wait(command, stop_event, stop_file, deadline, handle)

    def observed_run(command, listener, options):
        if sys.argv[5] == "lifetime":
            options = {**options, "lifetime_seconds": 10.0}
        return original_run(command, listener, options)

    def observed_stop(**kwargs):
        emit("stream_stop_started", started_at=kwargs["budget"].started_at)
        outcome = original_stop(**kwargs)
        emit("stream_stop_finished", outcome=asdict(outcome), counts=dict(probe._counts))
        return outcome

    def observed_flush(server, deadline):
        def backlog():
            return sum(channel.total_outbufs_len for channel in tuple(server.active_channels.values()))

        emit("stream_flush_started", pending_bytes=backlog())
        result = original_flush(server, deadline)
        emit("stream_flush_finished", pending_bytes=backlog())
        return result

    waitress.create_server = observed_server
    Command._run_bound_server = observed_run
    Command._wait_for_stop = observed_wait
    lifecycle.stop_owned_resources = observed_stop
    lifecycle._flush_waitress_channels = observed_flush


if __name__ == "__main__":
    raise SystemExit(main(configure=configure, prepare=prepare))

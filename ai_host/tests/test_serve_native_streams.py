from datetime import datetime, timedelta, timezone
import json
import threading
import time

import pytest
from ai_base_runtime.testkit import scripted_model_endpoint
from ai_base_runtime.testkit.host_support._domain_assertions import _response

from ai_host.tests.conformance_runtime_probe import until
from ai_host.tests.native_stream_support import EventReader, native_stream_host


TRIGGERS = ["stop-file", "SIGINT", "SIGTERM", "CTRL_BREAK_EVENT", "lifetime"]
STREAM_ROOT = "/ai/apps/metrics/api/qualification/"


class HeldReply(dict):
    def __init__(self):
        super().__init__()
        self.entered, self.release = threading.Event(), threading.Event()

    def __call__(self, request):
        self.entered.set()
        assert self.release.wait(30), "Synthetic model callback was not released"
        return _response("Synthetic completion.")


def write_proof(root, proof_id, host, exited_at, observations, **extra):
    records = host.records()
    ready = next(row for row in records if row.get("event") == "stream_host_ready")
    assert ready["threads"] == 14
    started = next(row for row in records if row.get("event") == "stream_stop_started")
    stopped = next(row for row in records if row.get("event") == "stream_stop_finished")
    assert stopped["outcome"]["exit_code"] == 0, stopped
    http = stopped["outcome"]["http_result"]
    assert http["completed"] and not http["unfinished_stream_ids"], http
    assert not http["undelivered_stream_ids"] and not http["error_codes"], http
    assert http["elapsed_seconds"] <= 2
    (root / "streams.json").write_text(json.dumps({
        "amendment": "B5-r1", "proof_id": proof_id, "trigger": host.trigger,
        "triggered_at": host.triggered_at, "stop_started_at": started["started_at"],
        "exited_at": exited_at, "observations": observations, "server": records, **extra,
    }, indent=2), encoding="utf-8")
    return started["started_at"]


@pytest.mark.parametrize("trigger", TRIGGERS)
def test_real_chat_streams_preserve_identity_and_terminate_before_normal_exit(tmp_path, trigger):
    replies = [HeldReply(), HeldReply()]
    with scripted_model_endpoint(replies) as model:
        try:
            with native_stream_host(tmp_path, endpoint=model.model.base_url, trigger=trigger) as host:
                before = host.snapshot()
                assert before["limits"] == {"heartbeat": 2, "streams": 4, "requests": 4, "terminal_grace": 2}
                readers, streams, identities = [], [], []
                try:
                    for index in range(2):
                        session = host.request("POST", "/ai/api/chat/sessions", {
                            "appId": "metrics", "agent": "dashboard", "sessionKey": f"metrics.b5-{index}",
                        })
                        run = host.request("POST", "/ai/api/chat/messages", {
                            "sessionId": session["sessionId"], "content": "Synthetic hold.",
                            "clientMessageKey": f"b5-{index}",
                            "deadlineAt": (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat().replace("+00:00", "Z"),
                        })
                        assert replies[index].entered.wait(5)
                        stream = host.stream(f'/ai/api/chat/runs/{run["runId"]}/events')
                        streams.append(stream)
                        reader = EventReader(stream).start()
                        readers.append(reader)
                        identities.append({"sessionId": session["sessionId"], "runId": run["runId"]})
                    until(lambda: all(len(reader.events) >= 2 for reader in readers), timeout=4)
                    for reader, identity in zip(readers, identities):
                        states = [item["payload"] for item in reader.events if item["payload"]["type"] == "chat.state"]
                        assert states and all(all(row[key] == value for key, value in identity.items()) for row in states)
                        assert states[-1]["status"] == "running"
                        assert any(item["payload"]["type"] == "heartbeat" for item in reader.events)
                    host.trigger_stop()
                    observations = [reader.finish() for reader in readers]
                    exited_at = host.wait_stopped()
                    started_at = write_proof(
                        tmp_path, "B5-chat", host, exited_at, observations, identities=identities, before=before,
                    )
                    assert all(row["terminal_at"] - started_at <= 2 for row in observations)
                    assert len(model.requests) == 2
                finally:
                    for stream in streams:
                        stream.close()
                    for reply in replies:
                        reply.release.set()
        finally:
            for reply in replies:
                reply.release.set()


@pytest.mark.parametrize("trigger", TRIGGERS)
def test_controlled_active_idle_and_slow_stream_flush_before_normal_exit(tmp_path, trigger):
    with native_stream_host(tmp_path, trigger=trigger) as host:
        streams, readers = [], []
        try:
            for kind in ("active", "idle", "backlog"):
                stream = host.stream(STREAM_ROOT + kind)
                streams.append(stream)
                reader = EventReader(stream)
                readers.append(reader)
                if kind != "backlog":
                    reader.start()
            until(lambda: host.snapshot()["counts"].get("backlog_blocks") == 512, timeout=5)
            before = host.snapshot()
            assert before["limits"] == {"heartbeat": 2, "streams": 4, "requests": 4, "terminal_grace": 2}
            assert before["pending_bytes"] > 1_048_576, before
            triggered_at = host.trigger_stop()
            time.sleep(max(0, triggered_at + 3 - time.monotonic()))
            resumed_at = time.monotonic()
            readers[-1].start()
            observations = [reader.finish() for reader in readers]
            exited_at = host.wait_stopped()
            started_at = write_proof(
                tmp_path, "B5-transport", host, exited_at, observations,
                workload="slow", before=before, resumed_at=resumed_at,
            )
            assert all(row["terminal_at"] - started_at <= 2 for row in observations[:2])
            payloads = [row["payload"] for row in observations[-1]["events"] if row["payload"]["type"] == "backlog"]
            assert [row["index"] for row in payloads] == list(range(512))
            assert sum(len(row["data"]) for row in payloads) == 512 * 16300
            assert resumed_at - triggered_at >= 3
        finally:
            for stream in streams:
                stream.close()


@pytest.mark.parametrize("trigger", ["stop-file", "CTRL_BREAK_EVENT"])
def test_non_reader_cannot_block_bounded_normal_exit(tmp_path, trigger):
    with native_stream_host(tmp_path, trigger=trigger) as host:
        stream = host.stream(STREAM_ROOT + "backlog")
        try:
            until(lambda: host.snapshot()["counts"].get("backlog_blocks") == 512, timeout=5)
            before = host.snapshot()
            assert before["limits"] == {"heartbeat": 2, "streams": 4, "requests": 4, "terminal_grace": 2}
            assert before["pending_bytes"] > 1_048_576
            host.trigger_stop()
            exited_at = host.wait_stopped()
            write_proof(tmp_path, "B5-transport", host, exited_at, [], workload="never-read", before=before)
            flushed = next(row for row in host.records() if row.get("event") == "stream_flush_finished")
            assert flushed["pending_bytes"] > 0
        finally:
            stream.close()

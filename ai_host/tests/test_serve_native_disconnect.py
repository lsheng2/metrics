import json
import time

from ai_host.tests.native_stream_support import native_stream_host


STREAM_PATH = "/ai/apps/metrics/api/qualification/idle"
REPEAT = 20


def write_receipt(path, receipt, **extra):
    receipt.update(extra)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")


def public_diagnostics(host):
    return host.request("GET", "/ai/api/diagnostics")


def wait_for_settled_disconnect(host, baseline, closed_at, cycle):
    deadline = closed_at + baseline["limits"]["heartbeat"] + 1.0
    samples = []
    while time.monotonic() <= deadline:
        snapshot = host.snapshot()
        samples.append({"at": time.monotonic(), "snapshot": snapshot})
        if (
            snapshot["counts"].get("streams", 0) == 0
            and snapshot["pending_bytes"] == 0
            and snapshot["tasks"] == baseline["tasks"]
            and snapshot["threads"] == baseline["threads"]
        ):
            reclaimed_at = samples[-1]["at"]
            cycle.update({
                "reclaimed_at": reclaimed_at,
                "elapsed": reclaimed_at - closed_at,
                "after": {
                    "at": reclaimed_at,
                    "probe": snapshot,
                    "diagnostics": public_diagnostics(host),
                },
                "samples": samples,
            })
            return snapshot
        time.sleep(0.025)
    cycle.update({
        "timed_out_at": time.monotonic(),
        "samples": samples,
    })
    raise AssertionError(f"disconnect {cycle['index']} did not settle within heartbeat + 1s")


def test_real_serve_repeated_stream_disconnects_release_runtime_slots_and_exit_cleanly(tmp_path):
    proof = tmp_path / "disconnects.json"
    receipt = {
        "schema_version": 1,
        "proof_id": "W2.HOST.native_disconnect",
        "endpoint": STREAM_PATH,
        "repeat": REPEAT,
        "trigger": "stop-file",
        "cycles": [],
    }
    try:
        with native_stream_host(tmp_path, trigger="stop-file") as host:
            baseline = host.snapshot()
            ready = next(row for row in host.records() if row.get("event") == "stream_host_ready")
            write_receipt(
                proof, receipt,
                baseline={"probe": baseline, "diagnostics": public_diagnostics(host), "ready": ready},
            )
            try:
                assert ready["threads"] == 14
                assert baseline["limits"] == {
                    "heartbeat": 2.0, "streams": 4, "requests": 4, "terminal_grace": 2.0,
                }
                assert baseline["counts"].get("streams", 0) == 0
                assert baseline["pending_bytes"] == 0
                for index in range(REPEAT):
                    cycle = {
                        "index": index,
                        "before": {
                            "at": time.monotonic(),
                            "probe": host.snapshot(),
                            "diagnostics": public_diagnostics(host),
                        },
                    }
                    receipt["cycles"].append(cycle)
                    stream = host.stream(STREAM_PATH)
                    try:
                        active = None
                        active_deadline = time.monotonic() + 3
                        while time.monotonic() < active_deadline:
                            active = host.snapshot()
                            if active["counts"].get("streams", 0) == 1:
                                break
                            time.sleep(0.025)
                        assert active is not None and active["counts"].get("streams", 0) == 1, active
                        cycle["active"] = {
                            "at": time.monotonic(),
                            "probe": active,
                            "diagnostics": public_diagnostics(host),
                        }
                    finally:
                        cycle["closed_at"] = time.monotonic()
                        stream.close()
                    snapshot = wait_for_settled_disconnect(host, baseline, cycle["closed_at"], cycle)
                    assert snapshot["counts"].get("streams_done", 0) == index + 1
                    assert cycle["after"]["diagnostics"]["streamInFlightCount"] == 0
                    write_receipt(proof, receipt, latest=snapshot)
                final = host.snapshot()
                final_diagnostics = public_diagnostics(host)
                assert final["counts"].get("streams", 0) == 0
                assert final["counts"].get("streams_done", 0) == REPEAT
                assert final["pending_bytes"] == 0
                assert final["tasks"] == baseline["tasks"]
                assert final["threads"] == baseline["threads"]
                assert final_diagnostics["streamInFlightCount"] == 0
                host.trigger_stop()
                exited_at = host.wait_stopped()
                records = host.records()
                stopped = next(row for row in records if row.get("event") == "stream_stop_finished")
                assert stopped["outcome"]["exit_code"] == 0, stopped
                http = stopped["outcome"]["http_result"]
                assert http["completed"] and not http["unfinished_stream_ids"], http
                assert not http["undelivered_stream_ids"] and not http["error_codes"], http
                assert not stopped["outcome"]["cleanup_errors"], stopped
                write_receipt(
                    proof,
                    receipt,
                    final={"probe": final, "diagnostics": final_diagnostics},
                    exited_at=exited_at,
                    server=records,
                )
            except BaseException as error:
                write_receipt(
                    proof,
                    receipt,
                    error=repr(error),
                    server=host.records(),
                )
                raise
    except BaseException as error:
        receipt.setdefault("error", repr(error))
        if (tmp_path / "process.json").exists():
            receipt["process"] = json.loads((tmp_path / "process.json").read_text(encoding="utf-8"))
        if proof.exists():
            write_receipt(proof, receipt)
        raise
    receipt["process"] = json.loads((tmp_path / "process.json").read_text(encoding="utf-8"))
    write_receipt(proof, receipt)

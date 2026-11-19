"""Queue bounds are distinct from native socket flush/backlog evidence."""
import asyncio
from dataclasses import replace
from io import BytesIO
import json
import threading
import time

from ai_base_runtime.apps import AgentDefinition, AppPackage, AppRoute
from ai_base_runtime.spi import HttpLimits
from ai_host.tests.conformance_runtime_probe import until
from ai_host.wiring import build_wsgi_application


def test_installed_wsgi_queue_blocks_producer_until_consumed_and_releases_on_close(
    ai_host_mode, ai_host_factory, ai_clock_and_limits, ai_credentials, tmp_path,
):
    produced, lock = [], threading.Lock()
    finished = threading.Event()
    block = json.dumps({"type": "data", "data": "x" * 65506}, separators=(",", ":")).encode() + b"\n"
    assert len(block) == 65532

    async def stream(request):
        try:
            for index in range(100):
                yield block
                with lock:
                    produced.append(index)
                await asyncio.sleep(0)
        finally:
            finished.set()

    package = AppPackage(
        app_id="queueprobe", agents=(AgentDefinition(name="agent", instructions="Synthetic queue test."),),
        routes=(AppRoute(operation_id="queueprobe.stream", method="GET", path="/stream", handler=stream, stream=True),),
    )
    config = replace(ai_clock_and_limits.config, http_limits=HttpLimits(max_streams=4, max_requests=4))
    with ai_host_factory(
        settings=ai_clock_and_limits.settings, config=config, apps=(package,), start_timeout=15,
    ) as session:
        statuses = []
        application = build_wsgi_application(lambda *_: (), session.handle.wsgi_app())
        request = {
            "REQUEST_METHOD": "GET", "PATH_INFO": config.root_path + "/apps/queueprobe/stream",
            "SCRIPT_NAME": "", "SERVER_NAME": "127.0.0.1", "SERVER_PORT": "8793",
            "HTTP_HOST": "127.0.0.1:8793", "wsgi.url_scheme": "http", "wsgi.input": BytesIO(),
            "HTTP_AUTHORIZATION": dict(ai_credentials.headers(ai_credentials.owner))["Authorization"],
        }
        response = application(request, lambda status, headers: statuses.append(status))
        consumed = 0
        try:
            assert statuses == ["200 OK"]
            until(lambda: len(produced) == 16)
            held = len(produced)
            time.sleep(0.1)
            assert len(produced) == held == 16
            assert not finished.is_set()
            assert application.requests.count == 1
            iterator = iter(response)
            for _ in range(20):
                chunk = next(iterator)
                assert chunk == block
                consumed += len(chunk)
            until(lambda: len(produced) > held)
            advanced = len(produced)
        finally:
            response.close()
        assert finished.wait(3)
        until(lambda: session.handle.blocking.diagnostics.snapshot(
            ai_credentials.owner, timeout=1,
        ).stream_in_flight_count == 0)
        assert application.requests.count == 0
        (tmp_path / "backpressure.json").write_text(json.dumps({
            "paused_producer_blocks": held, "after_consumption_blocks": advanced,
            "block_bytes": len(block), "consumed_bytes": consumed,
            "stream_in_flight_after_close": 0, "host_in_flight_after_close": application.requests.count,
            "generator_closed": finished.is_set(),
        }, indent=2), encoding="utf-8")

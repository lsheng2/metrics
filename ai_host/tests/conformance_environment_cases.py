import asyncio
import atexit
from dataclasses import replace
import hashlib
import json
import logging
import os
import signal
import sys
import threading
import time

from opentelemetry import trace

from ai_base_runtime.apps import AgentDefinition, AppPackage, AppRoute
from ai_base_runtime.testkit import scripted_model_endpoint
from ai_host.tests.conformance_runtime_cases import auth_headers
from ai_host.tests.conformance_runtime_probe import until


def process_snapshot():
    return {
        'environment': {
            key: hashlib.sha256(value.encode('utf-8', 'surrogatepass')).hexdigest()
            for key, value in os.environ.items()
        },
        'tracer': trace.get_tracer_provider(),
        'signals': {
            name: signal.getsignal(getattr(signal, name))
            for name in ('SIGINT', 'SIGTERM', 'SIGBREAK') if hasattr(signal, name)
        },
    }


def observation_package():
    async def loop_info(request):
        loop = asyncio.get_running_loop()
        values = {
            'is_proactor': isinstance(loop, asyncio.ProactorEventLoop),
            'slow_callback_seconds': loop.slow_callback_duration,
        }
        loop.set_debug(True)
        return values

    async def slow_callback(request):
        time.sleep(0.12)
        return {'completed': True}

    return AppPackage(
        app_id='loop-probe', agents=(AgentDefinition(name='agent', instructions='Synthetic loop probe.'),),
        routes=(
            AppRoute(operation_id='loop.info', method='GET', path='/api/loop', handler=loop_info),
            AppRoute(operation_id='loop.slow', method='GET', path='/api/slow', handler=slow_callback),
        ),
    )


def test_windows_loop_diagnostics_and_embedding_preserve_process_ownership(
    ai_host_mode, ai_host_factory, ai_server_factory, ai_clock_and_limits, ai_credentials, monkeypatch, caplog,
):
    assert sys.platform == 'win32', 'This is the explicitly selected native Windows qualification lane.'
    registrations, signal_calls = [], []
    register, register_thread, set_signal = atexit.register, threading._register_atexit, signal.signal

    def capture_register(callback, *args, **kwargs):
        registrations.append(sys._getframe(1).f_globals.get('__name__', '<unknown>'))
        return register(callback, *args, **kwargs)

    def capture_thread_register(callback, *args, **kwargs):
        registrations.append(sys._getframe(1).f_globals.get('__name__', '<unknown>'))
        return register_thread(callback, *args, **kwargs)

    def capture_signal(number, handler):
        signal_calls.append(number)
        return set_signal(number, handler)

    with scripted_model_endpoint([]) as endpoint:
        config = replace(
            ai_clock_and_limits.config, model=endpoint.model,
            http_limits=replace(ai_clock_and_limits.config.http_limits, short_request_timeout_seconds=1),
        )
        before = process_snapshot()
        monkeypatch.setattr(atexit, 'register', capture_register)
        monkeypatch.setattr(threading, '_register_atexit', capture_thread_register)
        monkeypatch.setattr(signal, 'signal', capture_signal)
        with caplog.at_level(logging.WARNING, logger='asyncio'):
            with ai_host_factory(
                settings=ai_clock_and_limits.settings, config=config,
                apps=(observation_package(),), start_timeout=15,
            ) as session:
                assert process_snapshot() == before
                assert trace.get_tracer_provider() is before['tracer']
                with ai_server_factory(session) as server:
                    headers = auth_headers(server, ai_credentials)
                    root = server.root_path + '/apps/loop-probe/api/'
                    response = server.request('GET', root + 'loop', headers=headers, timeout=2)
                    assert response.status == 200
                    loop = json.loads(response.body)
                    assert loop['is_proactor']
                    assert 0 < loop['slow_callback_seconds'] <= 0.1
                    previous = len(caplog.records)
                    response = server.request('GET', root + 'slow', headers=headers, timeout=2)
                    assert response.status == 200 and json.loads(response.body) == {'completed': True}
                    until(lambda: any(
                        record.name == 'asyncio' and 'Executing ' in record.getMessage()
                        and ' took ' in record.getMessage()
                        for record in caplog.records[previous:]
                    ))
                    until(lambda: session.handle.blocking.diagnostics.snapshot(
                        ai_credentials.owner, timeout=1,
                    ).short_in_flight_count == 0)
            assert process_snapshot() == before
            assert trace.get_tracer_provider() is before['tracer']
        assert not signal_calls
        assert atexit.register is capture_register and threading._register_atexit is capture_thread_register
        assert signal.signal is capture_signal
        # Dependency cleanup remains host-owned; the embedded runtime installs no own hooks.
        assert not any(name.startswith('ai_base_runtime') for name in registrations), registrations

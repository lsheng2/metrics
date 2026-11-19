import base64
from contextlib import contextmanager
from dataclasses import replace
import logging
from types import SimpleNamespace

from django.conf import settings as django_settings
from django.test import override_settings
import pytest

from ai_base_runtime import start_blocking
from ai_base_runtime.spi import HttpLimits, Principal
from ai_base_runtime.testkit import ClockAndLimits, ControlledClock, LogCapture, TestCredentials
from ai_host.host import MetricsHost
from ai_host.settings import build_host_config, build_runtime_settings
from ai_host.state import attach, detach
from ai_host.tests.conformance_server import metrics_server


PASSWORD = 'synthetic-conformance-password'


class MetricsCredentials(TestCredentials):
    def headers(self, principal):
        if principal is None or principal.anonymous:
            return ()
        token = base64.b64encode(f'{principal.id}:{PASSWORD}'.encode()).decode()
        return (('Authorization', f'Basic {token}'),)


@pytest.fixture(scope='session')
def django_db_modify_db_settings(tmp_path_factory):
    django_settings.DATABASES['default'].setdefault('TEST', {})['NAME'] = str(
        tmp_path_factory.mktemp('metrics-conformance-db') / 'catalog.sqlite3',
    )


@pytest.fixture
def ai_credentials():
    return MetricsCredentials(
        owner=Principal(id='conformance-owner', display_name='conformance-owner'),
        other=Principal(id='conformance-other', display_name='conformance-other'),
        anonymous=Principal(id='local_operator', display_name='local_operator', anonymous=True),
    )


@pytest.fixture
def ai_clock_and_limits(tmp_path):
    state_dir = tmp_path / 'runtime'
    state_dir.mkdir()
    clock = ControlledClock()
    config = replace(
        build_host_config(), state_dir=state_dir, clock=clock, model=None,
        root_path='/conformance/ai', allowed_hosts=('127.0.0.1', 'localhost'),
        http_limits=HttpLimits(max_streams=2, max_requests=2, short_request_timeout_seconds=0.2),
    )
    return ClockAndLimits(build_runtime_settings(), config, clock)


@pytest.fixture
def ai_host_factory(ai_credentials, transactional_db):
    @contextmanager
    def factory(*, settings, config, apps, start_timeout):
        users = {principal.id: PASSWORD for principal in (ai_credentials.owner, ai_credentials.other)}
        with override_settings(
            METRICS_BASIC_AUTH_USERS=users, METRICS_BASE_URL=config.root_path.removesuffix('/ai'),
            ALLOWED_HOSTS=list(config.allowed_hosts),
        ):
            host = MetricsHost(config)
            context = start_blocking(settings, host, apps, start_timeout=start_timeout)
            with context as handle:
                attach(handle)
                try:
                    yield SimpleNamespace(handle=handle, context=context, host=host, settings=settings, apps=apps)
                finally:
                    detach(handle)
            assert handle.stop_result is not None and handle.stop_result.completed, handle.stop_result

    return factory


@pytest.fixture
def ai_server_factory():
    return metrics_server


@pytest.fixture
def ai_logs():
    capture = LogCapture()

    class CaptureHandler(logging.Handler):
        def emit(self, record):
            fields = {key: getattr(record, key) for key in ('path', 'client_addr', 'reason') if hasattr(record, key)}
            capture.append(logger=record.name, level=record.levelno, message=record.getMessage(), fields=fields)

    handler = CaptureHandler()
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        yield capture
    finally:
        root.removeHandler(handler)
        handler.close()

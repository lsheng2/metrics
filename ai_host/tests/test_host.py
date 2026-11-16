import base64
import asyncio

import pytest
from django.test import override_settings

from ai_host.host import MetricsHost
from ai_base_runtime.spi import AuditEvent
from ai_host.models import RuntimeAuditEvent
from datetime import UTC, datetime


def basic_header(username, password):
    token = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('ascii')
    return f'Basic {token}'


class RawRequest:
    def __init__(self, authorization):
        self._authorization = authorization

    def header_values(self, name):
        if name.lower() == 'authorization' and self._authorization is not None:
            return (self._authorization,)
        return ()


@override_settings(METRICS_BASIC_AUTH_USERS={'alice': 'wonder'})
def test_shouldAuthenticateBasicPrincipalWithSharedDecision():
    principal = MetricsHost().authenticate(RawRequest(basic_header('alice', 'wonder')))

    assert principal.id == 'alice'
    assert principal.display_name == 'alice'
    assert principal.anonymous is False


@override_settings(METRICS_BASIC_AUTH_USERS={'alice': 'wonder'})
def test_shouldRejectInvalidRuntimeCredentials():
    assert MetricsHost().authenticate(RawRequest(basic_header('alice', 'wrong'))) is None


@override_settings(METRICS_BASIC_AUTH_USERS=None)
def test_shouldAuthenticateAnonymousLocalOperatorWhenBasicAuthIsUnset():
    principal = MetricsHost().authenticate(RawRequest(None))

    assert principal.id == 'local_operator'
    assert principal.anonymous is True


@pytest.mark.asyncio
@override_settings(METRICS_BASIC_AUTH_USERS=None)
async def test_shouldNotAllowAnonymousApprovalInProductionHost():
    assert await MetricsHost().can_decide(MetricsHost().authenticate(RawRequest(None)), object()) is False


@pytest.mark.django_db
def test_shouldPersistAuditEventIdempotently():
    event = AuditEvent(
        event_id='event-1',
        category='tool_result',
        occurred_at=datetime(2026, 11, 16, 1, 0, tzinfo=UTC),
        sequence=7,
        runtime_id='runtime-1',
        principal_id='alice',
        app_id='metrics',
        session_id='session-1',
        run_id='run-1',
        tool_call_id='tool-call-1',
        approval_id='approval-1',
        tool_name='metrics.catalog',
        result_status='succeeded',
        result_code=None,
    )
    host = MetricsHost()

    asyncio.run(host.record_audit(event))
    asyncio.run(host.record_audit(event))

    rows = list(RuntimeAuditEvent.objects.filter(event_id='event-1'))
    assert len(rows) == 1
    assert rows[0].category == 'tool_result'
    assert rows[0].sequence == 7
    assert rows[0].payload['tool_call_id'] == 'tool-call-1'

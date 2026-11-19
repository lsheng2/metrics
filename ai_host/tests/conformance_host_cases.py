import base64
import json
import time
from urllib.parse import urlsplit

from django.test import override_settings
import pytest

from ai_base_runtime.apps import AgentDefinition, AppPackage, AppRoute
from ai_base_runtime.spi import AuditEvent
from ai_host.models import RuntimeAuditEvent
from ai_host.run_sync import run_sync
from ai_host.tests import conformance_urls


def identity_package(visits):
    async def identity(request):
        visits.append(request.principal.id)
        return {'principal': request.principal.id}

    return AppPackage(
        app_id='probe', agents=(AgentDefinition(name='agent', instructions='Synthetic host identity probe.'),),
        routes=(AppRoute(
            operation_id='probe.identity', method='GET', path='/api/identity', handler=identity,
        ),),
    )


def headers(server, credentials, mode):
    head = (('Host', urlsplit(server.base_url).netloc),)
    if mode == 'owner':
        return (*head, *credentials.headers(credentials.owner))
    if mode == 'wrong':
        token = base64.b64encode(f'{credentials.owner.id}:synthetic-wrong'.encode()).decode()
        return (*head, ('Authorization', f'Basic {token}'))
    if mode == 'duplicate':
        auth = credentials.headers(credentials.owner)
        return (*head, *auth, *auth)
    return head


@pytest.mark.parametrize('credential_mode', ['owner', 'missing', 'wrong'])
def test_django_and_runtime_share_principal_and_auth_challenge(
    ai_host_mode, ai_host_factory, ai_server_factory, ai_credentials, ai_clock_and_limits, credential_mode,
):
    visits = []
    conformance_urls.VISITS.clear()
    with override_settings(ROOT_URLCONF='ai_host.tests.conformance_urls'):
        with ai_host_factory(
            settings=ai_clock_and_limits.settings, config=ai_clock_and_limits.config,
            apps=(identity_package(visits),), start_timeout=15.0,
        ) as session:
            with ai_server_factory(session) as server:
                responses = [
                    server.request('GET', path, headers=headers(server, ai_credentials, credential_mode), timeout=2)
                    for path in ('/django-identity/', server.root_path + '/apps/probe/api/identity')
                ]
                if credential_mode == 'owner':
                    assert [response.status for response in responses] == [200, 200]
                    assert [json.loads(response.body)['principal'] for response in responses] == [
                        ai_credentials.owner.id, ai_credentials.owner.id,
                    ]
                else:
                    assert [response.status for response in responses] == [401, 401]
                    for response in responses:
                        assert dict((key.lower(), value) for key, value in response.headers)['www-authenticate'] == (
                            ai_clock_and_limits.config.www_authenticate
                        )
                    assert visits == conformance_urls.VISITS == []


@pytest.mark.parametrize('credential_mode', ['owner', 'missing'])
def test_invalid_host_is_rejected_before_django_or_runtime_views(
    ai_host_mode, ai_host_factory, ai_server_factory, ai_credentials, ai_clock_and_limits, credential_mode,
):
    visits = []
    conformance_urls.VISITS.clear()
    with override_settings(ROOT_URLCONF='ai_host.tests.conformance_urls'):
        with ai_host_factory(
            settings=ai_clock_and_limits.settings, config=ai_clock_and_limits.config,
            apps=(identity_package(visits),), start_timeout=15.0,
        ) as session:
            with ai_server_factory(session) as server:
                auth = ai_credentials.headers(ai_credentials.owner) if credential_mode == 'owner' else ()
                for path in ('/django-identity/', server.root_path + '/apps/probe/api/identity'):
                    response = server.request(
                        'GET', path, headers=(('Host', 'rebind.attacker.example'), *auth), timeout=2,
                    )
                    assert response.status == 400 and response.body == b'Bad Request'
                assert visits == conformance_urls.VISITS == []


@pytest.mark.parametrize('credential_mode', ['missing', 'wrong', 'duplicate'])
def test_runtime_auth_failure_logs_once_without_inserting_runtime_audit(
    ai_host_mode, ai_host_factory, ai_server_factory, ai_credentials, ai_clock_and_limits, ai_logs, credential_mode,
):
    with ai_host_factory(
        settings=ai_clock_and_limits.settings, config=ai_clock_and_limits.config,
        apps=(identity_package([]),), start_timeout=15.0,
    ) as session:
        before = RuntimeAuditEvent.objects.count()
        before_dropped = session.handle.blocking.diagnostics.snapshot(
            ai_credentials.owner, timeout=1,
        ).dropped_auth_audit_count
        with ai_server_factory(session) as server:
            response = server.request(
                'GET', server.root_path + '/apps/probe/api/identity',
                headers=headers(server, ai_credentials, credential_mode), timeout=2,
            )
            assert response.status == 401
            deadline = time.monotonic() + 2
            while True:
                records = [record for record in ai_logs.records() if record.message == 'ai_auth_failed']
                count = RuntimeAuditEvent.objects.count()
                diagnostics = session.handle.blocking.diagnostics.snapshot(ai_credentials.owner, timeout=1)
                if records or count != before or diagnostics.dropped_auth_audit_count > before_dropped:
                    break
                assert time.monotonic() < deadline, 'Authentication outcome was not observable.'
                time.sleep(0.01)
            assert count == before
            assert len(records) == 1, diagnostics
            assert diagnostics.dropped_auth_audit_count == before_dropped + 1
            assert 'synthetic-wrong' not in repr(records)


@pytest.mark.asyncio
async def test_auth_failure_callback_logs_sanitized_fields_without_database_write(
    ai_host_mode, ai_host_factory, ai_clock_and_limits, ai_logs,
):
    with ai_host_factory(
        settings=ai_clock_and_limits.settings, config=ai_clock_and_limits.config,
        apps=(identity_package([]),), start_timeout=15.0,
    ) as session:
        before = await run_sync(RuntimeAuditEvent.objects.count)
        event = AuditEvent(
            event_id='conformance-auth-callback', category='authentication_failed',
            occurred_at=ai_clock_and_limits.clock.utc_now(), sequence=1,
            runtime_id='synthetic-conformance', path='/conformance/ai/apps/probe/api/identity',
            client_addr='127.0.0.1', reason='authentication_required',
        )
        await session.host.record_audit(event)
        assert await run_sync(RuntimeAuditEvent.objects.count) == before
        records = [record for record in ai_logs.records() if record.message == 'ai_auth_failed']
        assert len(records) == 1
        assert dict(records[0].fields) == {
            'path': event.path, 'client_addr': event.client_addr, 'reason': event.reason,
        }

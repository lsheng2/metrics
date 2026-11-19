from datetime import UTC, datetime
import sqlite3
import time

from django.db import connections
import pytest

from ai_base_runtime.spi import AuditEvent
from ai_host.host import MetricsHost
from ai_host.models import RuntimeAuditEvent
from ai_host.run_sync import run_sync


def durable_event():
    return AuditEvent(
        event_id='immutable-audit-probe', category='tool_result',
        occurred_at=datetime(2026, 11, 17, tzinfo=UTC), sequence=1,
        runtime_id='synthetic-audit-runtime', tool_call_id='synthetic-call',
        result_status='succeeded',
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_durable_audit_repeated_delivery_is_one_unchanged_row():
    host = MetricsHost()
    await host.record_audit(durable_event())
    await host.record_audit(durable_event())
    rows = await run_sync(lambda: list(RuntimeAuditEvent.objects.values()))
    assert len(rows) == 1
    assert rows[0]['event_id'] == 'immutable-audit-probe'
    assert rows[0]['result_status'] == 'succeeded'


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
@pytest.mark.parametrize('operation', [
    'instance_update', 'query_update', 'instance_delete', 'query_delete',
    'bulk_update', 'bulk_upsert', 'update_or_create',
])
async def test_audit_mutation_is_rejected_without_changing_the_stored_event(operation):
    await MetricsHost().record_audit(durable_event())

    def mutate():
        row = RuntimeAuditEvent.objects.get(event_id='immutable-audit-probe')
        if operation == 'instance_update':
            row.result_status = 'declined'
            row.save()
        elif operation == 'query_update':
            RuntimeAuditEvent.objects.filter(pk=row.pk).update(result_status='declined')
        elif operation == 'instance_delete':
            row.delete()
        elif operation == 'query_delete':
            RuntimeAuditEvent.objects.filter(pk=row.pk).delete()
        elif operation == 'bulk_update':
            row.result_status = 'declined'
            RuntimeAuditEvent.objects.bulk_update([row], ['result_status'])
        elif operation == 'bulk_upsert':
            value = {field.name: getattr(row, field.name) for field in row._meta.fields if not field.primary_key}
            value['result_status'] = 'declined'
            RuntimeAuditEvent.objects.bulk_create(
                [RuntimeAuditEvent(**value)], update_conflicts=True,
                unique_fields=['event_id'], update_fields=['result_status'],
            )
        else:
            RuntimeAuditEvent.objects.update_or_create(
                event_id=row.event_id, defaults={'result_status': 'declined'},
            )

    with pytest.raises(ValueError):
        await run_sync(mutate)
    rows = await run_sync(lambda: list(RuntimeAuditEvent.objects.values('event_id', 'result_status')))
    assert rows == [{'event_id': 'immutable-audit-probe', 'result_status': 'succeeded'}]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_locked_audit_write_is_bounded_and_retry_inserts_once():
    path = connections['default'].settings_dict['NAME']
    blocker = sqlite3.connect(path, timeout=5)
    blocker.execute('BEGIN IMMEDIATE')
    host = MetricsHost()
    started = time.monotonic()
    try:
        with pytest.raises(sqlite3.OperationalError):
            await host.record_audit(durable_event())
    finally:
        blocker.rollback()
        blocker.close()
    assert time.monotonic() - started < 7
    assert await run_sync(RuntimeAuditEvent.objects.count) == 0
    await host.record_audit(durable_event())
    await host.record_audit(durable_event())
    assert await run_sync(RuntimeAuditEvent.objects.count) == 1

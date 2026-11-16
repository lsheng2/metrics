from dataclasses import asdict
from datetime import UTC, datetime
import json
import sqlite3

from django.conf import settings as django_settings
from django.db import connections

from ai_base_runtime.spi import Principal

from ai_host.run_sync import run_sync
from ai_host.settings import build_host_config
from metrics.auth import check_basic_authorization


class MetricsHost:
    def __init__(self, config=None):
        self.config = config or build_host_config()

    def authenticate(self, request):
        authorization = None
        values = request.header_values('authorization')
        if len(values) == 1:
            authorization = values[0]
        identity = check_basic_authorization(django_settings.METRICS_BASIC_AUTH_USERS, authorization)
        if identity is None:
            return None
        return Principal(
            id=identity.username,
            display_name=identity.username,
            anonymous=identity.anonymous,
        )

    async def can_decide(self, principal, approval):
        if not isinstance(principal, Principal):
            return False
        return not principal.anonymous or self.config.allow_anonymous_approval

    async def record_audit(self, event):
        await run_sync(_insert_audit_event, event)


def _insert_audit_event(event):
    payload = asdict(event)
    payload['occurred_at'] = event.occurred_at.isoformat()
    db_path = connections['default'].settings_dict['NAME']
    connection = sqlite3.connect(db_path, timeout=5, uri=str(db_path).startswith('file:'))
    try:
        connection.execute(
            '''
            INSERT OR IGNORE INTO ai_host_runtimeauditevent (
                event_id, category, occurred_at, sequence, runtime_id,
                principal_id, app_id, session_id, run_id, tool_call_id,
                approval_id, tool_name, result_status, result_code, payload, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                event.event_id,
                event.category,
                event.occurred_at.isoformat(),
                event.sequence,
                event.runtime_id,
                event.principal_id or '',
                event.app_id or '',
                event.session_id or '',
                event.run_id or '',
                event.tool_call_id or '',
                event.approval_id or '',
                event.tool_name or '',
                event.result_status or '',
                event.result_code or '',
                json.dumps(payload, separators=(',', ':')),
                datetime.now(UTC).isoformat(),
            ),
        )
        connection.commit()
    finally:
        connection.close()

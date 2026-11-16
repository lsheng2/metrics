import re

from ai_base_runtime.apps import ContextRef
from ai_base_runtime.contracts import canonical_json


CONTEXT_KIND = 'metrics.workbench'
CONTEXT_BYTE_LIMIT = 4096
TICKET_LIMIT = 50
_ID = re.compile(r'[A-Za-z0-9._:-]{1,160}')
_PROFILE = re.compile(r'[a-z0-9][a-z0-9._-]{0,159}')
_DATE = re.compile(r'(?:[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{2,4}WW[0-9]{2})')
_SERIES = re.compile(r'[A-Za-z0-9 ._:-]{0,160}')
_FIELDS = frozenset({
    'binding_key', 'profile_id', 'provider_id', 'range_mode', 'begin', 'end',
    'chart_id', 'bucket', 'series', 'ticket_ids', 'ticket_ids_total',
    'ticket_ids_truncated',
})


def build_context_ref(state, *, ticket_ids=()):
    if not re.fullmatch(r'[1-9][0-9]{0,18}', state.scope_id):
        return None
    values = {
        'binding_key': f'metrics.scope.{state.scope_id}',
        'profile_id': state.profile_id, 'provider_id': state.provider_id,
        'range_mode': state.range_mode, 'begin': state.begin, 'end': state.end,
        'chart_id': state.chart_id, 'bucket': state.selected_bucket_id,
        'series': state.selected_series_name,
        'ticket_ids': [], 'ticket_ids_total': len(ticket_ids),
        'ticket_ids_truncated': bool(ticket_ids),
    }
    if any(not isinstance(item, str) or not _ID.fullmatch(item) for item in ticket_ids):
        return None
    for item in ticket_ids[:TICKET_LIMIT]:
        values['ticket_ids'].append(item)
        values['ticket_ids_truncated'] = len(values['ticket_ids']) < len(ticket_ids)
        if _wire_size(values) > CONTEXT_BYTE_LIMIT:
            values['ticket_ids'].pop()
            values['ticket_ids_truncated'] = True
            break
    ref = ContextRef(kind=CONTEXT_KIND, values=values)
    return ref if valid_context_ref(ref) else None


def valid_context_ref(ref):
    if not isinstance(ref, ContextRef) or ref.kind != CONTEXT_KIND:
        return False
    values = ref.values
    if set(values) != _FIELDS or _wire_size(values) > CONTEXT_BYTE_LIMIT:
        return False
    patterns = {
        'binding_key': r'metrics\.scope\.[1-9][0-9]{0,18}',
        'profile_id': _PROFILE, 'chart_id': _ID,
        'begin': _DATE, 'end': _DATE,
        'bucket': r'[A-Za-z0-9._:-]{0,160}', 'series': _SERIES,
    }
    if any(not isinstance(values[key], str) or not re.fullmatch(pattern, values[key])
           for key, pattern in patterns.items()):
        return False
    tickets = values['ticket_ids']
    return (
        values['provider_id'] in {'jira', 'hsdes'}
        and values['range_mode'] in {'ww', 'date'}
        and isinstance(tickets, tuple) and len(tickets) <= TICKET_LIMIT
        and all(isinstance(item, str) and _ID.fullmatch(item) for item in tickets)
        and type(values['ticket_ids_total']) is int
        and values['ticket_ids_total'] >= len(tickets)
        and type(values['ticket_ids_truncated']) is bool
        and values['ticket_ids_truncated'] == (values['ticket_ids_total'] > len(tickets))
    )


def context_payload(ref):
    return {'kind': ref.kind, 'values': dict(ref.values)}


def _wire_size(values):
    return len(canonical_json({'kind': CONTEXT_KIND, 'values': dict(values)}))

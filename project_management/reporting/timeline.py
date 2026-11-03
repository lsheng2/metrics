import json
from typing import Mapping

from project_management.app.domain.capture_values import json_value
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_edits import source_key_hash


def validate_days(snapshot) -> None:
    if len(snapshot.days) > 7:
        raise ReportError('REPORT_LIMIT')
    dates = [day.report_date for day in snapshot.days]
    if len(dates) != len(set(dates)) or dates != sorted(dates):
        raise ReportError('REPORT_INVALID')


def build_timeline(snapshot, current_rows):
    days = _timeline_days(snapshot)
    row_index = {row['source_key_hash']: row for row in current_rows}
    for day in days:
        for row in day.get('source_rows', ()):
            row_hash = source_key_hash(row.source_key)
            if row_hash not in row_index:
                row_index[row_hash] = _minimal_row(row)
    timeline_rows = []
    for row_hash, row in row_index.items():
        cells = []
        for day in days:
            cells.append(_timeline_cell(day, row_hash))
        timeline_rows.append({'display_key': row['display_key'], 'title': row['title'], 'cells': cells})
    return {'days': days, 'rows': timeline_rows, 'day_events': _day_event_rows(days)}


def _timeline_days(snapshot):
    if not snapshot.days:
        return [{
            'report_date': snapshot.report_date,
            'state': 'initial-baseline / no-published-history',
            'publication_id': 'None',
            'source_rows': snapshot.rows,
            'rows': snapshot.rows,
            'events': snapshot.events,
            'coverage': snapshot.coverage,
        }]
    return [{
        'report_date': day.report_date,
        'state': 'Published' if day.state == 'published' else 'No published report',
        'publication_id': day.publication_id or 'None',
        'source_rows': day.rows,
        'rows': day.rows,
        'events': day.events,
        'coverage': day.coverage,
    } for day in snapshot.days]


def _minimal_row(row):
    return {
        'source_key_hash': source_key_hash(row.source_key),
        'display_key': row.identity.display_key,
        'title': _display(row.title),
    }


def _timeline_cell(day, row_hash):
    if day['state'] == 'No published report':
        event_text = _day_event_text(day, row_hash)
        text = f"No published report; coverage {_coverage_summary(day['coverage'])}"
        if event_text:
            text = f'{text}; events {event_text}'
        return {'text': text}
    matches = [row for row in day['rows'] if source_key_hash(row.source_key) == row_hash]
    event_text = _day_event_text(day, row_hash)
    if not matches:
        text = f"Not present in published report; coverage {_coverage_summary(day['coverage'])}"
        if event_text:
            text = f'{text}; events {event_text}'
        return {'text': text}
    row = matches[0]
    actions = '; '.join(_day_action_text(action) for action in row.next_actions) or 'No actions'
    text = (
        f"{_display(row.status)}; current position {_string_or_empty(row.current_position) or 'Unavailable'}; "
        f"{actions}; pending {row.pending_reason or 'None'}; coverage {_coverage_summary(row.coverage)}"
        f"; day coverage {_coverage_summary(day['coverage'])}"
    )
    if event_text:
        text = f'{text}; events {event_text}'
    return {'text': text}


def _day_action_text(action):
    return (
        f"action {_string_or_empty(action.get('action'))}; owner {_owner_display(action) or 'Unknown'}; "
        f"basis {_display(action.get('owner_basis'))}; state {_display(action.get('state'), 'unknown')}"
    )


def _day_event_text(day, row_hash):
    rows = []
    for event in day['events']:
        if source_key_hash(event.source_key) == row_hash:
            rows.append(
                f"{event.event_id} {event.kind} before {_json_text(event.before)} "
                f"after {_json_text(event.after)} occurred {event.occurred_at or 'unknown'} observed {event.observed_at}"
            )
    return '; '.join(rows)


def _day_event_rows(days):
    rows = []
    for day in days:
        for event in day['events']:
            rows.append({
                'report_date': day['report_date'],
                'identity': _event_identity(event),
                'event_id': event.event_id,
                'kind': event.kind,
                'before': _json_text(event.before),
                'after': _json_text(event.after),
                'occurred_at': event.occurred_at or 'unknown',
                'observed_at': event.observed_at,
            })
    return rows


def _event_identity(event):
    key = event.source_key
    return f'{key.provider_id}/{key.endpoint_id}/{key.stable_id}'


def _coverage_summary(value):
    if not isinstance(value, Mapping):
        return _display(value)
    return ';'.join(f"{item['label']}={item['value']}" for item in _coverage_items(value))


def _coverage_items(value, prefix=''):
    if not isinstance(value, Mapping):
        return [{'label': prefix or 'coverage', 'value': _display(value)}]
    items = []
    for key in sorted(value.keys()):
        current = value[key]
        label = f'{prefix}.{key}' if prefix else key
        if isinstance(current, Mapping):
            items.extend(_coverage_items(current, label))
        else:
            items.append({'label': label, 'value': _display(current)})
    return items


def _display(value, unknown='Unknown') -> str:
    if value is None or value == '':
        return unknown
    if isinstance(value, Mapping):
        for key in ('displayName', 'display_name', 'name', 'display', 'id', 'key'):
            if value.get(key):
                return str(value[key])
        return _json_text(value)
    if isinstance(value, (tuple, list)):
        return ', '.join(_display(item, unknown) for item in value)
    return str(value)


def _json_text(value) -> str:
    if value is None:
        return 'None'
    return json.dumps(json_value(value), ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _string_or_empty(value) -> str:
    return '' if value is None else str(value)


def _owner_display(action: Mapping) -> str:
    for field in ('owner_display', 'ownerDisplay', 'displayName', 'owner_id'):
        value = action.get(field)
        if type(value) is str and value:
            return value
    return ''

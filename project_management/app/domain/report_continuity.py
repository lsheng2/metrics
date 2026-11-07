import re
from dataclasses import asdict, dataclass
from datetime import date
from typing import Literal, Mapping
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from project_management.app.domain.capture_values import canonical_bytes, decode_json, sha256_bytes
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.report_authoring_fragments import plain_text_fragment
from project_management.app.domain.report_continuity_context import validate_daily_authoring_context
from project_management.app.domain.report_continuity_rollover import (
    build_weekly_seed,
    select_base_actions,
    select_persistent_notes,
    select_seed_notes,
    summary_identity,
)
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_draft_values import validate_hash_text, validate_uuid_text
from project_management.app.domain.report_observation_history import all_observations, retained_history

MAX_CONTEXT_BYTES = 8_388_608
@dataclass(frozen=True, slots=True)
class ReportingCalendar:
    calendar_id: str
    revision: int
    timezone: str
    week_rule: Literal['iso8601', 'date_map']
    date_map: Mapping

@dataclass(frozen=True, slots=True)
class MeetingIdentity:
    local_date: str
    calendar_id: str
    calendar_revision: int
    timezone: str
    workweek_year: int
    workweek: int
    weekday: int

@dataclass(frozen=True, slots=True)
class PeriodIdentity:
    calendar_id: str
    calendar_revision: int
    workweek_year: int
    workweek: int

@dataclass(frozen=True, slots=True)
class PublicationRef:
    publication_id: str
    manifest_hash: str
    commit: str

@dataclass(frozen=True, slots=True)
class PreparedContextRef:
    preparation_id: str
    context_hash: str
    draft_id: str

@dataclass(frozen=True, slots=True)
class PeriodView:
    series_id: str
    period_key: str
    selected_publication_refs: tuple[PublicationRef, ...]
    source_snapshot: object
    weekly_context: Mapping
    matrix: object

def meeting_identity(calendar: ReportingCalendar, local_date: str) -> MeetingIdentity:
    calendar = validate_calendar(calendar)
    parsed = _date(local_date)
    if calendar.week_rule == 'iso8601':
        iso = parsed.isocalendar()
        year, week, weekday = iso.year, iso.week, iso.weekday
    else:
        item = calendar.date_map.get(local_date)
        if item is None:
            raise ReportError('REPORT_CALENDAR_UNAVAILABLE')
        if not isinstance(item, Mapping) or set(item) != {'workweek_year', 'workweek', 'weekday'}:
            raise ReportError('REPORT_CALENDAR_UNAVAILABLE')
        year = _positive_int(item['workweek_year'], 'REPORT_CALENDAR_UNAVAILABLE')
        week = _positive_int(item['workweek'], 'REPORT_CALENDAR_UNAVAILABLE')
        weekday = _positive_int(item['weekday'], 'REPORT_CALENDAR_UNAVAILABLE')
    return MeetingIdentity(local_date, calendar.calendar_id, calendar.revision, calendar.timezone, year, week, weekday)
def period_identity(meeting: MeetingIdentity) -> PeriodIdentity:
    return PeriodIdentity(meeting.calendar_id, meeting.calendar_revision, meeting.workweek_year, meeting.workweek)
def meeting_key(meeting: MeetingIdentity) -> str:
    return f'{meeting.calendar_id}:{meeting.calendar_revision}:{meeting.local_date}'
def period_key(period: PeriodIdentity) -> str:
    return f'{period.calendar_id}:{period.calendar_revision}:{period.workweek_year}:ww{period.workweek}'
def validate_calendar(value) -> ReportingCalendar:
    if not isinstance(value, ReportingCalendar):
        raise ReportError('REPORT_CALENDAR_UNAVAILABLE')
    if not value.calendar_id or type(value.calendar_id) is not str:
        raise ReportError('REPORT_CALENDAR_UNAVAILABLE')
    if type(value.revision) is not int or value.revision < 1:
        raise ReportError('REPORT_CALENDAR_UNAVAILABLE')
    try:
        ZoneInfo(value.timezone)
    except (TypeError, ZoneInfoNotFoundError):
        raise ReportError('REPORT_CALENDAR_UNAVAILABLE') from None
    if value.week_rule not in {'iso8601', 'date_map'} or not isinstance(value.date_map, Mapping):
        raise ReportError('REPORT_CALENDAR_UNAVAILABLE')
    seen = set()
    for key, item in value.date_map.items():
        _date(key)
        if not isinstance(item, Mapping) or set(item) != {'workweek_year', 'workweek', 'weekday'}:
            raise ReportError('REPORT_CALENDAR_UNAVAILABLE')
        mapped = (
            _bounded_int(item['workweek_year'], 1, 9999),
            _bounded_int(item['workweek'], 1, 53),
            _bounded_int(item['weekday'], 1, 7),
        )
        if mapped in seen:
            raise ReportError('REPORT_CALENDAR_UNAVAILABLE')
        seen.add(mapped)
    return value
def build_row_order(previous, rows, matrix_options):
    options = _matrix_options(matrix_options)
    previous_rows = tuple(() if previous is None else previous.get('rows', ()))
    existing = {_issue_key(item['issue_ref']): item for item in previous_rows}
    current = tuple(_issue_ref_from_row(row) for row in rows)
    current_by_key = {_issue_key(ref): ref for ref in current}
    result = []
    used = set()
    for item in sorted(previous_rows, key=lambda row: row['position']):
        key = _issue_key(item['issue_ref'])
        group_id = _group_id(item.get('group_id'), options)
        visible = 'visible' if key in current_by_key else 'removed'
        result.append({**item, 'group_id': group_id, 'visibility': visible})
        used.add(key)
    start = max((row['position'] for row in result), default=0)
    new_refs = tuple(ref for ref in current if _issue_key(ref) not in used)
    for offset, ref in enumerate(sorted(new_refs, key=_natural_issue_key), 1):
        result.append({
            'issue_ref': ref,
            'group_id': _new_group(options),
            'position': start + offset,
            'first_seen_meeting': None,
            'visibility': 'visible',
        })
    return {'revision': (previous or {}).get('revision', 0) + 1, 'group_order': options['group_order'], 'rows': tuple(result)}


def build_daily_authoring_context(*, series_id, series_policy_revision, series_policy_hash, meeting,
                                  source_snapshot, matrix_options, baseline_context=None,
                                  base_daily_publication=None, acknowledged_gap_draft_ids=()):
    period = period_identity(meeting)
    base = None if baseline_context is None else validate_daily_authoring_context(baseline_context, series_id=series_id, meeting=meeting)
    same_period = base is not None and base['period'] == asdict(period)
    base_observations = {_issue_key(item['issue_ref']): item for item in all_observations(base)}
    row_order = build_row_order(None if base is None else base.get('row_order'), source_snapshot.rows, matrix_options)
    options = _matrix_options(matrix_options)
    seed_notes = tuple(select_seed_notes(base, same_period, options['cross_week_carry']))
    notes = list(seed_notes)
    actions = list(select_base_actions(base))
    persistent_notes = tuple(select_persistent_notes(base, same_period))
    actions_by_id = {action['action_id']: action for action in actions}
    observations = []
    for row in source_snapshot.rows:
        issue_ref = _issue_ref_from_row(row)
        previous = base_observations.get(_issue_key(issue_ref))
        state = _source_state(row, previous)
        action_ids = []
        for action in tuple(row.next_actions or ()):
            saved = _report_action(series_id, issue_ref, meeting, action)
            existing = actions_by_id.get(saved['action_id'])
            if existing is not None and existing['tracking_state'] in {'done', 'canceled'}:
                continue
            if existing is None:
                actions.append(saved)
                actions_by_id[saved['action_id']] = saved
            action_ids.append(saved['action_id'])
        if _should_create_summary_note(row, previous, state):
            note = _daily_note(series_id, issue_ref, meeting, row, action_ids, source_snapshot.source_as_of, source_snapshot.capture_id)
            notes.append(note)
        observations.append(_current_observation(series_id, issue_ref, meeting, row, state, source_snapshot.source_as_of, source_snapshot.capture_id))
    context = {
        'schema_version': 3,
        'series_id': validate_uuid_text(series_id),
        'series_policy_revision': _positive_int(series_policy_revision, 'REPORT_ARTIFACT_INVALID'),
        'series_policy_hash': validate_hash_text(series_policy_hash),
        'report_role': 'daily',
        'meeting': asdict(meeting),
        'period': asdict(period),
        'base_daily_publication': None if base_daily_publication is None else asdict(base_daily_publication),
        'baseline_choice': 'initial' if not base else 'previous_final',
        'acknowledged_gap_draft_ids': tuple(validate_uuid_text(item) for item in acknowledged_gap_draft_ids),
        'row_order': row_order,
        'weekly_seed': build_weekly_seed(base, same_period, seed_notes, actions, persistent_notes, base_daily_publication),
        'notes': tuple(notes),
        'current_observations': tuple(observations),
        'actions': tuple(actions),
        'persistent_notes': persistent_notes,
        'selected_daily_publications': (),
        **retained_history(base, asdict(meeting), asdict(period), source_snapshot.capture_id, source_snapshot.source_as_of),
    }
    _context_size(context)
    return _plain_json(context)


def _daily_note(series_id, issue_ref, meeting, row, action_ids, source_as_of, capture_id):
    text = row.current_position or row.what or row.title or row.identity.display_key
    fragment = plain_text_fragment(text)
    note_id = str(uuid5(UUID(series_id), f"note:{_issue_key(issue_ref)}:{meeting.local_date}"))
    return {
        'note_id': note_id,
        'issue_ref': issue_ref,
        'meeting': asdict(meeting),
        'revision': 1,
        'body_fragment': fragment,
        'body_hash': sha256_bytes(canonical_bytes(fragment)),
        'source_status': _source_status(row, source_as_of, capture_id),
        'action_ids': tuple(action_ids),
        'provenance': {
            'origin': 'accepted_summary',
            'ai_result_ref': None if row.summary_ref is None else asdict(row.summary_ref),
            'original_fragment_hash': sha256_bytes(canonical_bytes(fragment)),
            'edited_by': None,
            'edited_at': None,
            'accepted_publication': None,
        },
        'prior_revision_hash': None,
    }


def _report_action(series_id, issue_ref, meeting, action):
    action_identity = {
        'issue': _issue_key(issue_ref),
        'action': action.get('action', ''),
        'owner_id': action.get('owner_id'),
        'evidence': tuple(action.get('evidence', ())),
    }
    action_id = str(uuid5(UUID(series_id), f"action:{canonical_bytes(action_identity).decode('utf-8')}"))
    basis = 'recorded' if action.get('owner_basis') == 'explicit' else 'proposed'
    state = action.get('state') if action.get('state') in {'open', 'done', 'canceled', 'unknown'} else 'unknown'
    return {
        'action_id': action_id,
        'issue_ref': issue_ref,
        'issued_meeting': asdict(meeting),
        'owner_ref': None if action.get('owner_id') is None else {'owner_id': action.get('owner_id')},
        'body_fragment': plain_text_fragment(action.get('action', '')),
        'basis': basis,
        'tracking_state': state,
        'evidence_refs': tuple(action.get('evidence', ())),
        'resolution': None,
    }


def _current_observation(series_id, issue_ref, meeting, row, state, source_as_of, capture_id):
    return {
        'issue_ref': issue_ref,
        'meeting': asdict(meeting),
        'note_id': str(uuid5(UUID(series_id), f"note:{_issue_key(issue_ref)}:{meeting.local_date}")),
        'source_state': state,
        'source_status': _source_status(row, source_as_of, capture_id),
        'capture_id': capture_id,
        'source_hash': row.source_hash,
        'accepted_summary_ref': None if row.summary_ref is None else asdict(row.summary_ref),
        'editorial_base_note_ref': None,
    }


def _source_state(row, previous):
    if row.source_hash is None or row.pending_reason == 'source_missing':
        return 'unavailable'
    if row.pending_reason == 'source_incomplete':
        return 'incomplete'
    if previous is None:
        return 'initial'
    # The source reader checks completeness before summary lookup, including legacy pending rows.
    if (previous.get('source_hash') is None
            or previous.get('source_state') not in {'initial', 'changed', 'unchanged', 'pending'}):
        return 'pending'
    return 'unchanged' if previous['source_hash'] == row.source_hash else 'changed'


def _should_create_summary_note(row, previous, state):
    if (row.summary_ref is None or state in {'incomplete', 'unavailable'}
            or row.pending_reason in {'source_missing', 'source_incomplete', 'summary_pending', 'summary_stale'}):
        return False
    previous_ref = None if previous is None else previous.get('accepted_summary_ref')
    return state in {'initial', 'changed'} or summary_identity(previous_ref) != summary_identity(asdict(row.summary_ref))


def _source_status(row, source_as_of, capture_id):
    availability = 'known' if row.status is not None and row.source_hash is not None else ('not_captured' if row.pending_reason == 'source_missing' else 'unavailable')
    return {
        'availability': availability,
        'value': row.status if availability == 'known' else None,
        'field_path': 'status' if availability == 'known' else None,
        'observed_at': source_as_of if availability == 'known' else None,
        'source_ref': None if availability != 'known' else {
            'capture_id': capture_id,
            'identity': _issue_ref_from_row(row),
            'field_path': 'status',
            'observed_at': source_as_of,
        },
        'source_hash': row.source_hash,
    }


def _issue_ref_from_row(row):
    return {
        'provider_id': row.identity.provider_id,
        'endpoint_fingerprint': row.source_key.endpoint_id,
        'stable_id': row.identity.stable_id,
        'key_at_capture': row.identity.display_key,
    }


def _issue_key(issue_ref):
    return (issue_ref['provider_id'], issue_ref['endpoint_fingerprint'], issue_ref['stable_id'])


def _natural_issue_key(issue_ref):
    return tuple(_natural_parts(issue_ref['key_at_capture'])) + _issue_key(issue_ref)


def _natural_parts(text):
    parts = []
    for item in re.split(r'(\d+)', text.lower()):
        parts.append((0, int(item)) if item.isdigit() else (1, item))
    return parts


def _matrix_options(value):
    value = value or {'group_mode': 'none', 'groups': ()}
    groups = tuple(value.get('groups', ()))
    order = tuple(group['group_id'] for group in sorted(groups, key=lambda item: item['rank']))
    return {
        'group_mode': value.get('group_mode', 'none'),
        'group_order': () if value.get('group_mode') == 'none' else order,
        'cross_week_carry': value.get('cross_week_carry', 'last_confirmed_and_unresolved'),
    }


def _group_id(value, options):
    if options['group_mode'] == 'none':
        return None
    if value not in options['group_order']:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return value


def _new_group(options):
    return None if options['group_mode'] == 'none' else options['group_order'][0]


def _context_size(context):
    if len(canonical_bytes(context)) > MAX_CONTEXT_BYTES:
        raise ReportError('REPORT_LIMIT')


def _plain_json(value):
    try:
        return decode_json(canonical_bytes(value))
    except ArchiveError:
        raise ReportError('REPORT_ARTIFACT_INVALID') from None


def _date(value):
    try:
        return date.fromisoformat(_text(value))
    except ValueError:
        raise ReportError('REPORT_CALENDAR_UNAVAILABLE') from None


def _text(value):
    if type(value) is not str:
        raise ReportError('REPORT_INVALID')
    return value


def _positive_int(value, code):
    if type(value) is not int or value < 1:
        raise ReportError(code)
    return value


def _bounded_int(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ReportError('REPORT_CALENDAR_UNAVAILABLE')
    return value

from datetime import date, datetime
from typing import Mapping

from project_management.app.domain.capture_values import canonical_bytes, sha256_bytes
from project_management.app.domain.report_authoring_fragments import validate_rich_text_fragment
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_draft_values import validate_hash_text, validate_uuid_text


CONTEXT_KEYS = {
    'schema_version', 'series_id', 'series_policy_revision', 'series_policy_hash', 'report_role',
    'meeting', 'period', 'base_daily_publication', 'baseline_choice', 'acknowledged_gap_draft_ids',
    'row_order', 'weekly_seed', 'notes', 'current_observations', 'actions', 'persistent_notes',
    'selected_daily_publications',
}
NOTE_KEYS = {'note_id', 'issue_ref', 'meeting', 'revision', 'body_fragment', 'body_hash', 'source_status',
             'action_ids', 'provenance', 'prior_revision_hash'}
ACTION_KEYS = {'action_id', 'issue_ref', 'issued_meeting', 'owner_ref', 'body_fragment', 'basis',
               'tracking_state', 'evidence_refs', 'resolution'}
OBSERVATION_KEYS = {'issue_ref', 'meeting', 'note_id', 'source_state', 'source_status', 'capture_id',
                    'source_hash', 'accepted_summary_ref', 'editorial_base_note_ref'}


def validate_daily_authoring_context(value, *, series_id=None, meeting=None):
    if not isinstance(value, Mapping) or set(value) != CONTEXT_KEYS:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if value['schema_version'] != 1:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    context_series = validate_uuid_text(value['series_id'])
    if series_id is not None and context_series != validate_uuid_text(series_id):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if value['report_role'] == 'weekly_view':
        return _weekly_view_context(value)
    if value['report_role'] != 'daily':
        raise ReportError('REPORT_ARTIFACT_INVALID')
    context_meeting = _meeting(value['meeting'])
    period = _period(value['period'])
    if period['calendar_id'] != context_meeting['calendar_id'] or period['calendar_revision'] != context_meeting['calendar_revision']:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if meeting is not None:
        expected = _meeting({
            'local_date': meeting.local_date,
            'calendar_id': meeting.calendar_id,
            'calendar_revision': meeting.calendar_revision,
            'timezone': meeting.timezone,
            'workweek_year': meeting.workweek_year,
            'workweek': meeting.workweek,
            'weekday': meeting.weekday,
        })
        if context_meeting['calendar_id'] != expected['calendar_id'] or context_meeting['calendar_revision'] != expected['calendar_revision']:
            raise ReportError('REPORT_ARTIFACT_INVALID')
    current_date = None if meeting is None else date.fromisoformat(meeting.local_date)
    publication = _publication_ref(value['base_daily_publication'])
    if value['baseline_choice'] not in {'initial', 'previous_final', 'confirmed_gap'}:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    row_order = _row_order(value['row_order'])
    notes = tuple(_note(item, context_meeting, current_date) for item in _items(value['notes']))
    _unique(((_issue_key(note['issue_ref']), note['meeting']['local_date']) for note in notes))
    actions = tuple(_action(item, context_meeting, current_date) for item in _items(value['actions']))
    action_ids = {action['action_id'] for action in actions}
    note_ids = {note['note_id'] for note in notes}
    for note in notes:
        if any(action_id not in action_ids for action_id in note['action_ids']):
            raise ReportError('REPORT_ARTIFACT_INVALID')
    observations = tuple(_observation(item, context_meeting, current_date) for item in _items(value['current_observations']))
    _unique((_issue_key(item['issue_ref']) for item in observations))
    persistent = tuple(_persistent_note(item) for item in _items(value['persistent_notes']))
    persistent_ids = {note['note_id'] for note in persistent}
    weekly_seed = _weekly_seed(value['weekly_seed'], note_ids, action_ids, persistent_ids)
    selected = tuple(_publication_ref(item) for item in _items(value['selected_daily_publications']))
    if selected:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return {**value, 'base_daily_publication': publication, 'row_order': row_order, 'weekly_seed': weekly_seed,
            'notes': notes, 'actions': actions, 'current_observations': observations,
            'persistent_notes': persistent, 'selected_daily_publications': selected}


def _weekly_view_context(value):
    if value['meeting'] is not None:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    period = _period(value['period'])
    selected = tuple(_required_publication_ref(item) for item in _items(value['selected_daily_publications']))
    if not selected:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    expected = {'calendar_id': period['calendar_id'], 'calendar_revision': period['calendar_revision']}
    notes = tuple(_note(item, expected, None) for item in _items(value['notes']))
    actions = tuple(_action(item, expected, None) for item in _items(value['actions']))
    observations = tuple(_observation(item, expected, None) for item in _items(value['current_observations']))
    action_ids = {action['action_id'] for action in actions}
    note_ids = {note['note_id'] for note in notes}
    for note in notes:
        if any(action_id not in action_ids for action_id in note['action_ids']):
            raise ReportError('REPORT_ARTIFACT_INVALID')
    persistent = tuple(_persistent_note(item) for item in _items(value['persistent_notes']))
    persistent_ids = {note['note_id'] for note in persistent}
    row_order = _row_order(value['row_order'])
    weekly_seed = _weekly_seed(value['weekly_seed'], note_ids, action_ids, persistent_ids)
    return {**value, 'period': period, 'base_daily_publication': _publication_ref(value['base_daily_publication']),
            'row_order': row_order, 'weekly_seed': weekly_seed, 'notes': notes, 'actions': actions,
            'current_observations': observations, 'persistent_notes': persistent,
            'selected_daily_publications': selected}


def _note(value, expected_meeting, current_date):
    if not isinstance(value, Mapping) or set(value) != NOTE_KEYS:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    meeting = _dated_meeting(value['meeting'], expected_meeting, current_date)
    fragment = validate_rich_text_fragment(value['body_fragment'])
    if validate_hash_text(value['body_hash']) != sha256_bytes(canonical_bytes(fragment)):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return {**value, 'note_id': validate_uuid_text(value['note_id']), 'issue_ref': _issue(value['issue_ref']),
            'meeting': meeting, 'body_fragment': fragment, 'source_status': _source_status(value['source_status'])}


def _action(value, expected_meeting, current_date):
    if not isinstance(value, Mapping) or set(value) != ACTION_KEYS:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if value['basis'] not in {'recorded', 'proposed'} or value['tracking_state'] not in {'open', 'done', 'canceled', 'unknown'}:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return {**value, 'action_id': validate_uuid_text(value['action_id']), 'issue_ref': _issue(value['issue_ref']),
            'issued_meeting': _dated_meeting(value['issued_meeting'], expected_meeting, current_date),
            'body_fragment': validate_rich_text_fragment(value['body_fragment'])}


def _observation(value, expected_meeting, current_date):
    if not isinstance(value, Mapping) or set(value) != OBSERVATION_KEYS:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if value['source_state'] not in {'initial', 'changed', 'unchanged', 'pending', 'incomplete', 'unavailable'}:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    summary = _summary_ref(value['accepted_summary_ref'])
    return {**value, 'issue_ref': _issue(value['issue_ref']),
            'meeting': _dated_meeting(value['meeting'], expected_meeting, current_date),
            'note_id': validate_uuid_text(value['note_id']), 'source_status': _source_status(value['source_status']),
            'accepted_summary_ref': summary}


def _dated_meeting(value, expected, current_date):
    meeting = _meeting(value)
    if meeting['calendar_id'] != expected['calendar_id'] or meeting['calendar_revision'] != expected['calendar_revision']:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if current_date is not None and date.fromisoformat(meeting['local_date']) > current_date:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return meeting


def _meeting(value):
    expected = {'local_date', 'calendar_id', 'calendar_revision', 'timezone', 'workweek_year', 'workweek', 'weekday'}
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    parsed = dict(value)
    date.fromisoformat(_str(parsed['local_date']))
    _str(parsed['calendar_id'])
    _positive_int(parsed['calendar_revision'])
    _str(parsed['timezone'])
    _bounded_int(parsed['workweek_year'], 1, 9999)
    _bounded_int(parsed['workweek'], 1, 53)
    _bounded_int(parsed['weekday'], 1, 7)
    return parsed


def _period(value):
    expected = {'calendar_id', 'calendar_revision', 'workweek_year', 'workweek'}
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    parsed = dict(value)
    _str(parsed['calendar_id'])
    _positive_int(parsed['calendar_revision'])
    _bounded_int(parsed['workweek_year'], 1, 9999)
    _bounded_int(parsed['workweek'], 1, 53)
    return parsed


def _issue(value):
    expected = {'provider_id', 'endpoint_fingerprint', 'stable_id', 'key_at_capture'}
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    parsed = dict(value)
    for item in parsed.values():
        _str(item)
    return parsed


def _source_status(value):
    expected = {'availability', 'value', 'field_path', 'observed_at', 'source_ref', 'source_hash'}
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if value['availability'] == 'known' and (value['field_path'] is None or value['source_ref'] is None or value['source_hash'] is None):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if value['availability'] not in {'known', 'unavailable', 'not_captured'}:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if value['source_hash'] is not None:
        validate_hash_text(value['source_hash'])
    if value['observed_at'] is not None:
        _time(value['observed_at'])
    if value['source_ref'] is not None:
        _source_ref(value['source_ref'])
    return dict(value)


def _row_order(value):
    if not isinstance(value, Mapping) or set(value) != {'revision', 'group_order', 'rows'}:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    groups = tuple(validate_uuid_text(item) for item in _items(value['group_order']))
    rows = []
    for row in _items(value['rows']):
        if not isinstance(row, Mapping) or set(row) != {'issue_ref', 'group_id', 'position', 'first_seen_meeting', 'visibility'}:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        group_id = None if row['group_id'] is None else validate_uuid_text(row['group_id'])
        if group_id is not None and group_id not in groups:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        if row['visibility'] not in {'visible', 'removed'}:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        rows.append({**row, 'issue_ref': _issue(row['issue_ref']), 'group_id': group_id, 'position': _positive_int(row['position'])})
    _unique((row['position'] for row in rows))
    _unique((_issue_key(row['issue_ref']) for row in rows))
    return {'revision': _positive_int(value['revision']), 'group_order': groups, 'rows': tuple(rows)}


def _weekly_seed(value, note_ids, action_ids, persistent_ids):
    expected = {'baseline', 'note_refs', 'unresolved_action_ids', 'persistent_note_refs', 'earlier_period_refs'}
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    note_refs = tuple(validate_uuid_text(item) for item in _items(value['note_refs']))
    unresolved = tuple(validate_uuid_text(item) for item in _items(value['unresolved_action_ids']))
    if any(item not in note_ids for item in note_refs) or any(item not in action_ids for item in unresolved):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return {
        'baseline': _publication_ref(value['baseline']),
        'note_refs': note_refs,
        'unresolved_action_ids': unresolved,
        'persistent_note_refs': _persistent_refs(value['persistent_note_refs'], persistent_ids),
        'earlier_period_refs': tuple(_required_publication_ref(item) for item in _items(value['earlier_period_refs'])),
    }


def _persistent_refs(value, persistent_ids):
    refs = tuple(validate_uuid_text(item) for item in _items(value))
    if any(item not in persistent_ids for item in refs):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return refs


def _persistent_note(value):
    expected = {'note_id', 'target', 'issue_ref', 'fragment', 'revision', 'carry_forward', 'provenance'}
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return {**value, 'note_id': validate_uuid_text(value['note_id']), 'fragment': validate_rich_text_fragment(value['fragment'])}


def _publication_ref(value):
    return None if value is None else _required_publication_ref(value)


def _required_publication_ref(value):
    if not isinstance(value, Mapping) or set(value) != {'publication_id', 'manifest_hash', 'commit'}:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return {'publication_id': validate_uuid_text(value['publication_id']),
            'manifest_hash': validate_hash_text(value['manifest_hash']),
            'commit': _commit(value['commit'])}


def _summary_ref(value):
    if value is None:
        return None
    expected = {'summary_id', 'revision', 'target_capture_id', 'source_hash', 'input_hash', 'result_hash', 'owning_commit'}
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return {**value, 'revision': _positive_int(value['revision']), 'source_hash': validate_hash_text(value['source_hash']),
            'input_hash': validate_hash_text(value['input_hash']), 'result_hash': validate_hash_text(value['result_hash']),
            'owning_commit': _commit(value['owning_commit'])}


def _source_ref(value):
    expected = {'capture_id', 'identity', 'field_path', 'observed_at'}
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    _str(value['capture_id'])
    _issue(value['identity'])
    _str(value['field_path'])
    _time(value['observed_at'])


def _items(value):
    if not isinstance(value, (list, tuple)):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return value


def _issue_key(issue_ref):
    return (issue_ref['provider_id'], issue_ref['endpoint_fingerprint'], issue_ref['stable_id'])


def _unique(values):
    values = tuple(values)
    if len(values) != len(set(values)):
        raise ReportError('REPORT_ARTIFACT_INVALID')


def _str(value):
    if type(value) is not str:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return value


def _time(value):
    try:
        parsed = datetime.fromisoformat(_str(value).replace('Z', '+00:00'))
    except ValueError:
        raise ReportError('REPORT_ARTIFACT_INVALID') from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReportError('REPORT_ARTIFACT_INVALID')


def _commit(value):
    value = _str(value)
    if len(value) != 40 or any(character not in '0123456789abcdef' for character in value):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return value


def _positive_int(value):
    if type(value) is not int or value < 1:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return value


def _bounded_int(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return value

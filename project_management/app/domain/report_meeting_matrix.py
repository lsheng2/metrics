from dataclasses import dataclass
from typing import Literal, Mapping

from project_management.app.domain.report_continuity_context import validate_daily_authoring_context


@dataclass(frozen=True, slots=True)
class MeetingMatrixColumn:
    local_date: str
    meeting_key: str | None
    label: str
    state: Literal['captured', 'missing', 'not_captured', 'unavailable']


@dataclass(frozen=True, slots=True)
class MeetingMatrixCell:
    local_date: str
    note_ids: tuple[str, ...]
    action_ids: tuple[str, ...]
    current_observation_note_id: str | None
    source_state: str | None
    state: Literal['content', 'empty', 'missing', 'not_captured', 'unavailable']


@dataclass(frozen=True, slots=True)
class MeetingMatrixRow:
    issue_ref: Mapping
    title: str | None
    current_key: str
    group_id: str | None
    position: int
    visibility: str
    cells: tuple[MeetingMatrixCell, ...]


@dataclass(frozen=True, slots=True)
class MeetingMatrixProjection:
    columns: tuple[MeetingMatrixColumn, ...]
    rows: tuple[MeetingMatrixRow, ...]


def build_meeting_matrix(snapshot, context) -> MeetingMatrixProjection:
    context = validate_daily_authoring_context(context)
    columns = _columns(snapshot, context)
    notes = {}
    observations = {}
    actions = {}
    for note in context['notes']:
        notes.setdefault(_issue_key(note['issue_ref']), []).append(note)
    for observation in context['current_observations']:
        observations[(_issue_key(observation['issue_ref']), observation['meeting']['local_date'])] = observation
    for action in context['actions']:
        if action['tracking_state'] in {'done', 'canceled'}:
            continue
        actions.setdefault(_issue_key(action['issue_ref']), []).append(action)
    titles = {_source_issue_key(row): row.title for row in snapshot.rows}
    keys = {_source_issue_key(row): row.identity.display_key for row in snapshot.rows}
    rows = []
    for row in sorted(context['row_order']['rows'], key=lambda item: item['position']):
        issue_key = _issue_key(row['issue_ref'])
        rows.append(MeetingMatrixRow(
            row['issue_ref'],
            titles.get(issue_key),
            keys.get(issue_key, row['issue_ref']['key_at_capture']),
            row['group_id'],
            row['position'],
            row['visibility'],
            tuple(_cell(column, row['issue_ref'], notes, observations, actions) for column in columns),
        ))
    return MeetingMatrixProjection(columns, tuple(rows))


def _columns(snapshot, context):
    states = {}
    cutoff = _column_cutoff(context)
    for day in tuple(getattr(snapshot, 'days', ()) or ()):
        if cutoff is not None and day.report_date > cutoff:
            continue
        states[day.report_date] = 'captured' if day.state == 'published' else 'missing'
    for note in context['notes']:
        local_date = note['meeting']['local_date']
        if _note_in_context_period(note, context) and (cutoff is None or local_date <= cutoff):
            states.setdefault(local_date, 'captured')
    for observation in context['current_observations']:
        local_date = observation['meeting']['local_date']
        if cutoff is not None and local_date > cutoff:
            continue
        states.setdefault(local_date, 'captured')
    return tuple(MeetingMatrixColumn(
        local_date,
        _meeting_key_for_date(context, local_date),
        local_date,
        states[local_date],
    ) for local_date in sorted(states))


def _column_cutoff(context):
    if context['meeting'] is not None:
        return context['meeting']['local_date']
    dates = tuple(observation['meeting']['local_date'] for observation in context['current_observations'])
    return max(dates) if dates else None


def _cell(column, issue_ref, notes, observations, actions):
    issue_key = _issue_key(issue_ref)
    date_notes = tuple(sorted(
        (note for note in notes.get(issue_key, ()) if note['meeting']['local_date'] <= column.local_date),
        key=lambda item: (item['meeting']['local_date'], item['revision'], item['note_id']),
    ))
    observation = observations.get((issue_key, column.local_date))
    action_ids = tuple(action['action_id'] for action in actions.get(issue_key, ()) if action['issued_meeting']['local_date'] <= column.local_date)
    if column.state in {'missing', 'not_captured', 'unavailable'}:
        state = column.state
    elif observation is not None and observation['source_status']['availability'] != 'known':
        state = observation['source_status']['availability']
    elif date_notes:
        state = 'content'
    elif observation is not None:
        state = 'empty'
    else:
        state = column.state if column.state in {'missing', 'not_captured', 'unavailable'} else 'empty'
    return MeetingMatrixCell(
        column.local_date,
        tuple(note['note_id'] for note in date_notes),
        action_ids,
        None if observation is None else observation['note_id'],
        None if observation is None else observation['source_state'],
        state,
    )


def _meeting_key_for_date(context, local_date):
    for note in context['notes']:
        if note['meeting']['local_date'] == local_date:
            meeting = note['meeting']
            return f"{meeting['calendar_id']}:{meeting['calendar_revision']}:{meeting['local_date']}"
    for observation in context['current_observations']:
        if observation['meeting']['local_date'] == local_date:
            meeting = observation['meeting']
            return f"{meeting['calendar_id']}:{meeting['calendar_revision']}:{meeting['local_date']}"
    return None


def _note_in_context_period(note, context):
    meeting = note['meeting']
    period = context['period']
    return (
        meeting['calendar_id'] == period['calendar_id']
        and meeting['calendar_revision'] == period['calendar_revision']
        and meeting['workweek_year'] == period['workweek_year']
        and meeting['workweek'] == period['workweek']
    )


def _issue_key(issue_ref):
    return (issue_ref['provider_id'], issue_ref['endpoint_fingerprint'], issue_ref['stable_id'])


def _source_issue_key(row):
    return (row.identity.provider_id, row.identity.endpoint_id, row.identity.stable_id)

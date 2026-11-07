from datetime import date
from typing import Mapping

from project_management.app.domain.capture_values import canonical_bytes
from project_management.app.domain.report_contracts import ReportError


HISTORY_KEYS = {'past_observations', 'meeting_history', 'meeting_reviews', 'meeting_skips'}
REVIEW_STATES = {'discussed', 'not_discussed', 'no_additional_update'}


def issue_key(value):
    return value['provider_id'], value['endpoint_fingerprint'], value['stable_id']


def in_period(meeting, period):
    return all(meeting[key] == period[key] for key in (
        'calendar_id', 'calendar_revision', 'workweek_year', 'workweek',
    ))


def all_observations(context):
    if not context:
        return ()
    return tuple(sorted(
        (*context.get('past_observations', ()), *context.get('current_observations', ())),
        key=lambda item: (item['meeting']['local_date'], issue_key(item['issue_ref'])),
    ))


def known_meetings(context):
    if not context:
        return ()
    result = {item['meeting']['local_date']: item for item in context.get('meeting_history', ())}
    for observation in all_observations(context):
        result.setdefault(observation['meeting']['local_date'], {
            'meeting': observation['meeting'], 'capture_id': observation['capture_id'],
            'source_as_of': observation['source_status']['observed_at'],
        })
    if context['meeting'] is not None:
        result.setdefault(context['meeting']['local_date'], {
            'meeting': context['meeting'], 'capture_id': None, 'source_as_of': None,
        })
    return tuple(result[key] for key in sorted(result))


def retained_history(base, meeting, period, capture_id, source_as_of):
    retained, anchors = [], {}
    for observation in all_observations(base):
        if observation['meeting']['local_date'] >= meeting['local_date']:
            continue
        if in_period(observation['meeting'], period):
            retained.append(observation)
        else:
            anchors[issue_key(observation['issue_ref'])] = observation
    retained = sorted((*anchors.values(), *retained), key=lambda item: (
        item['meeting']['local_date'], issue_key(item['issue_ref']),
    ))
    dates = {item['meeting']['local_date'] for item in retained}
    if base and base['meeting']:
        dates.add(base['meeting']['local_date'])
    meetings = {
        item['meeting']['local_date']: item for item in known_meetings(base)
        if item['meeting']['local_date'] < meeting['local_date']
        and (in_period(item['meeting'], period) or item['meeting']['local_date'] in dates)
    }
    meetings[meeting['local_date']] = {
        'meeting': meeting, 'capture_id': capture_id, 'source_as_of': source_as_of,
    }
    reviews = tuple(item for item in (base or {}).get('meeting_reviews', ())
                    if item['meeting']['local_date'] in meetings
                    and item['meeting']['local_date'] < meeting['local_date'])
    return {'past_observations': tuple(retained), 'meeting_history': tuple(meetings[key] for key in sorted(meetings)),
            'meeting_reviews': reviews, 'meeting_skips': None}


def upgrade_context(context):
    if context['schema_version'] == 3:
        return context
    return {**context, 'schema_version': 3, 'meeting_skips': context.get('meeting_skips'),
            'past_observations': (), 'meeting_history': known_meetings(context), 'meeting_reviews': ()}


def preserved_reviews(parent, current):
    observations = {item['note_id']: item for item in current['current_observations']}
    same_source = {
        issue_key(item['issue_ref']) for item in parent['current_observations']
        if item['note_id'] in observations
        and item['capture_id'] == observations[item['note_id']]['capture_id']
        and item['source_hash'] == observations[item['note_id']]['source_hash']
    }
    return (
        *[item for item in current['meeting_reviews'] if item['meeting'] != current['meeting']],
        *[item for item in parent.get('meeting_reviews', ()) if item['meeting'] == current['meeting']
          and issue_key(item['issue_ref']) in same_source],
    )


def validate_history(context):
    from project_management.app.domain.report_continuity_context import _dated_meeting, _issue, _items, _observation, _time

    expected = context['meeting'] or context['period']
    cutoff = None if context['meeting'] is None else date.fromisoformat(context['meeting']['local_date'])
    if cutoff and not in_period(context['meeting'], context['period']):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    meetings = {}
    for item in _items(context['meeting_history']):
        if not isinstance(item, Mapping) or set(item) != {'meeting', 'capture_id', 'source_as_of'}:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        meeting = _dated_meeting(item['meeting'], expected, cutoff)
        local = meeting['local_date']
        if local in meetings:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        if item['capture_id'] is not None and (type(item['capture_id']) is not str or not item['capture_id']):
            raise ReportError('REPORT_ARTIFACT_INVALID')
        if item['source_as_of'] is not None:
            _time(item['source_as_of'])
        meetings[local] = item
    if cutoff and (cutoff.isoformat() not in meetings or meetings[cutoff.isoformat()]['meeting'] != context['meeting']):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    rows = {issue_key(row['issue_ref']) for row in context['row_order']['rows']}
    for collection, field in ((context['notes'], 'note_id'), (context['actions'], 'action_id')):
        identities = [item[field] for item in collection]
        if len(identities) != len(set(identities)) or any(issue_key(item['issue_ref']) not in rows for item in collection):
            raise ReportError('REPORT_ARTIFACT_INVALID')
    seen, ids = set(), set()
    past = tuple(_observation(item, expected, cutoff) for item in _items(context['past_observations']))
    for name, collection in (('past', past), ('current', context['current_observations'])):
        for observation in collection:
            local = observation['meeting']['local_date']
            key = issue_key(observation['issue_ref']), local
            if (key in seen or observation['note_id'] in ids or key[0] not in rows or local not in meetings
                    or observation['meeting'] != meetings[local]['meeting']):
                raise ReportError('REPORT_ARTIFACT_INVALID')
            if cutoff and ((name == 'past' and local >= cutoff.isoformat()) or (name == 'current' and local != cutoff.isoformat())):
                raise ReportError('REPORT_ARTIFACT_INVALID')
            seen.add(key)
            ids.add(observation['note_id'])
    reviews = []
    reviewed = set()
    for item in _items(context['meeting_reviews']):
        if not isinstance(item, Mapping) or set(item) != {'issue_ref', 'meeting', 'state', 'recorded_by', 'recorded_at'}:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        ref = _issue(item['issue_ref'])
        meeting = _dated_meeting(item['meeting'], expected, cutoff)
        key = issue_key(ref), meeting['local_date']
        if (key in reviewed or key[0] not in rows or key[1] not in meetings
                or meeting != meetings[key[1]]['meeting'] or item['state'] not in REVIEW_STATES
                or type(item['recorded_by']) is not str or not item['recorded_by']):
            raise ReportError('REPORT_ARTIFACT_INVALID')
        _time(item['recorded_at'])
        reviewed.add(key)
        reviews.append(dict(item))
    if len(canonical_bytes(context)) > 8_388_608:
        raise ReportError('REPORT_LIMIT')
    return {**context, 'past_observations': past, 'meeting_history': tuple(meetings.values()),
            'meeting_reviews': tuple(reviews)}

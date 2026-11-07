SOURCE_OBSERVATION_LABELS = {
    'initial': 'Initial source; note pending',
    'changed': 'Source changed; note pending',
    'unchanged': 'No source change',
    'pending': 'Source comparison unavailable',
    'incomplete': 'Source incomplete',
    'unavailable': 'Source unavailable',
}


REVIEW_LABELS = {
    'discussed': 'Discussed',
    'not_discussed': 'Not discussed',
    'no_additional_update': 'No additional update confirmed',
}


def source_observation_label(observation, *, has_note=False, context=None):
    if observation is None:
        return ''
    state = observation.get('source_state')
    if state in {'pending', 'incomplete', 'unavailable'}:
        return SOURCE_OBSERVATION_LABELS[state]
    if context and context.get('schema_version') == 3:
        freshness = _freshness_label(observation, context)
        if freshness:
            return freshness
    if has_note and state in {'initial', 'changed', 'unchanged'}:
        return ''
    return SOURCE_OBSERVATION_LABELS.get(state, 'Source comparison unavailable')


def source_observation_text(observation, *, has_note=False, context=None):
    label = source_observation_label(observation, has_note=has_note, context=context)
    if not label or has_note:
        return label
    meeting, status = observation['meeting'], observation['source_status']
    value = status['value'] if status['availability'] == 'known' else 'Unavailable'
    return f"ww{meeting['workweek']}.{meeting['weekday']}({value}): {label}"
from datetime import datetime
from zoneinfo import ZoneInfo

from project_management.app.domain.report_observation_history import all_observations, in_period, issue_key, known_meetings




def history_entries(context, issue_ref, through_date, notes, *, exclude_note_id=None):
    selected = {item['meeting']['local_date']: item for item in notes
                if item['meeting']['local_date'] <= through_date}
    observations = {item['meeting']['local_date']: item for item in all_observations(context)
                    if issue_key(item['issue_ref']) == issue_key(issue_ref)
                    and item['meeting']['local_date'] <= through_date
                    and in_period(item['meeting'], context['period'])}
    reviews = {item['meeting']['local_date']: item for item in context.get('meeting_reviews', ())
               if issue_key(item['issue_ref']) == issue_key(issue_ref) and item['meeting']['local_date'] <= through_date}
    result = []
    for day in sorted(selected.keys() | observations.keys() | reviews.keys()):
        note, observation = selected.get(day), observations.get(day)
        if observation and observation['note_id'] == exclude_note_id:
            continue
        if note:
            result.append({'kind': 'note', 'note': note})
        text = source_observation_text(observation, has_note=note is not None, context=context)
        if text:
            result.append({'kind': 'observation', 'text': text})
        if day in reviews:
            meeting = reviews[day]['meeting']
            result.append({'kind': 'review', 'text':
                           f"ww{meeting['workweek']}.{meeting['weekday']}: {REVIEW_LABELS[reviews[day]['state']]}"})
    return tuple(result)


def _freshness_label(observation, context):
    previous = [item for item in all_observations(context)
                if issue_key(item['issue_ref']) == issue_key(observation['issue_ref'])
                and item['meeting']['local_date'] < observation['meeting']['local_date']]
    prior = previous[-1] if previous else None
    if prior and observation['capture_id'] == prior['capture_id']:
        return 'Source not refreshed; using saved capture'
    metadata = next((item for item in known_meetings(context) if item['meeting'] == observation['meeting']), None)
    observed = None if metadata is None else metadata['source_as_of']
    if observed is None:
        return 'Source observation time unavailable'
    local = datetime.fromisoformat(observed.replace('Z', '+00:00')).astimezone(ZoneInfo(observation['meeting']['timezone'])).date()
    if local.isoformat() != observation['meeting']['local_date']:
        return 'Source date differs from meeting date'
    prior_meetings = [item['meeting']['local_date'] for item in known_meetings(context)
                      if item['meeting']['local_date'] < observation['meeting']['local_date']]
    if prior and prior_meetings and prior['meeting']['local_date'] < max(prior_meetings):
        return 'Returned to scope; compared with last observed source'
    return ''

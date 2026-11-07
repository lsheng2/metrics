SOURCE_OBSERVATION_LABELS = {
    'initial': 'Initial source; note pending',
    'changed': 'Source changed; note pending',
    'unchanged': 'No source change',
    'pending': 'Source comparison unavailable',
    'incomplete': 'Source incomplete',
    'unavailable': 'Source unavailable',
}


def source_observation_label(observation, *, has_note=False):
    if observation is None:
        return ''
    state = observation.get('source_state')
    if has_note and state in {'initial', 'changed', 'unchanged'}:
        return ''
    return SOURCE_OBSERVATION_LABELS.get(state, 'Source comparison unavailable')


def source_observation_text(observation, *, has_note=False):
    label = source_observation_label(observation, has_note=has_note)
    if not label or has_note:
        return label
    meeting, status = observation['meeting'], observation['source_status']
    value = status['value'] if status['availability'] == 'known' else 'Unavailable'
    return f"ww{meeting['workweek']}.{meeting['weekday']}({value}): {label}"

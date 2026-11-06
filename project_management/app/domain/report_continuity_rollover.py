from dataclasses import asdict


def select_seed_notes(base, same_period, cross_week_carry):
    if not base:
        return ()
    if same_period or cross_week_carry == 'full_history':
        return tuple(base.get('notes', ()))
    latest = {}
    for note in base.get('notes', ()):
        key = _issue_key(note['issue_ref'])
        current = latest.get(key)
        if current is None or _note_sort_key(note) > _note_sort_key(current):
            latest[key] = note
    return tuple(latest[key] for key in sorted(latest))


def select_base_actions(base):
    return () if not base else tuple(base.get('actions', ()))


def select_persistent_notes(base, same_period):
    if not base:
        return ()
    notes = tuple(base.get('persistent_notes', ()))
    return notes if same_period else tuple(note for note in notes if note.get('carry_forward') is not False)


def build_weekly_seed(base, same_period, seed_notes, actions, persistent_notes, base_daily_publication):
    action_ids = tuple(action['action_id'] for action in actions if action.get('tracking_state') not in {'done', 'canceled'})
    prior_seed = {} if not base else base.get('weekly_seed', {})
    earlier = prior_seed.get('earlier_period_refs', ()) if same_period else (
        () if not base_daily_publication else (asdict(base_daily_publication),)
    )
    baseline = prior_seed.get('baseline') if same_period else (
        None if base_daily_publication is None else asdict(base_daily_publication)
    )
    note_refs = prior_seed.get('note_refs', ()) if same_period and prior_seed else tuple(note['note_id'] for note in seed_notes)
    return {
        'baseline': baseline,
        'note_refs': tuple(note_refs),
        'unresolved_action_ids': action_ids,
        'persistent_note_refs': tuple(note['note_id'] for note in persistent_notes),
        'earlier_period_refs': tuple(earlier),
    }


def summary_identity(value):
    if value is None:
        return None
    return tuple(value.get(key) for key in ('summary_id', 'revision', 'source_hash', 'input_hash', 'result_hash'))


def _issue_key(issue_ref):
    return (issue_ref['provider_id'], issue_ref['endpoint_fingerprint'], issue_ref['stable_id'])


def _note_sort_key(note):
    return (note['meeting']['local_date'], note['revision'], note['note_id'])

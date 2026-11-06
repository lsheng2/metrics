from hashlib import sha256

from scripts.validation.project_week_data import WEEK_COLORS, WEEK_DAYS, WEEK_ITEMS


def text_of(value):
    if isinstance(value, dict):
        if value.get('type') == 'text':
            return value.get('text', '')
        return ''.join(text_of(child) for child in value.values())
    if isinstance(value, list):
        return ''.join(text_of(child) for child in value)
    return ''


def verify_checkpoint(checkpoint, day, expected, previous=None, *, new_week=False, untouched_empty_ids=()):
    snapshot, context = checkpoint['snapshot'], checkpoint['context']
    rows = snapshot['rows']
    statuses = {number: status for number, status, *_ in WEEK_ITEMS}
    if [row['identity']['stable_id'] for row in rows] != ['101', '102', '103']:
        raise AssertionError('Report must contain three independently ordered tickets.')
    summaries = {}
    hashes = {}
    for row in rows:
        identifier = row['identity']['stable_id']
        if row['status'] != statuses[identifier] or row['summary_ref'] is None:
            raise AssertionError('Captured source status or accepted summary is missing.')
        summaries[identifier] = row['summary_ref']['summary_id']
        hashes[identifier] = row['source_hash']
    current = {note['issue_ref']['stable_id']: note for note in context['notes']
               if note['meeting']['local_date'] == day}
    absent = set(statuses) - set(current)
    if set(current) - set(statuses) or absent - set(untouched_empty_ids):
        raise AssertionError('Every daily ticket must retain an explicit current note, including empty edits.')
    for identifier in absent:
        observation = next((item for item in context.get('current_observations', ())
                            if item['issue_ref']['stable_id'] == identifier), None)
        if (expected[identifier] != '' or observation is None or observation['source_state'] != 'unchanged'
                or observation['source_status']['value'] != statuses[identifier]
                or any(edit.get('target', {}).get('note_id') == observation['note_id']
                       for edit in checkpoint.get('edits', ()))):
            raise AssertionError('An absent note is not an untouched unchanged-source slot.')
    for identifier, note in current.items():
        if note['source_status']['value'] != statuses[identifier]:
            raise AssertionError('Note prefix status was not captured from the ticket.')
        if expected[identifier] not in text_of(note['body_fragment']):
            raise AssertionError(f'Missing expected human note for {identifier}.')
        if expected[identifier] == '' and text_of(note['body_fragment']) != '':
            raise AssertionError('Explicit human deletion was resurrected.')
        if expected[identifier]:
            nodes = list(text_nodes(note['body_fragment']))
            color = '#008000' if day == '2026-10-29' and identifier == '103' else WEEK_COLORS[WEEK_DAYS.index(day)]
            if color not in {node.get('foreground') for node in nodes}:
                raise AssertionError('The current human note did not retain the chosen color.')
            if day == '2026-10-28' and identifier == '101':
                if not any(node.get('background') == '#fff4cc' and 'strong' in node.get('marks', ()) for node in nodes):
                    raise AssertionError('Wednesday highlight/bold formatting was lost.')
            if day == '2026-10-30' and identifier == '101' and '#aa0000' not in {node.get('foreground') for node in nodes}:
                raise AssertionError('Friday mixed paint was lost.')
    if previous is not None:
        old_rows = previous['snapshot']['rows']
        if summaries != {row['identity']['stable_id']: row['summary_ref']['summary_id'] for row in old_rows}:
            raise AssertionError('Unchanged source produced different accepted summary identities.')
        if hashes != {row['identity']['stable_id']: row['source_hash'] for row in old_rows}:
            raise AssertionError('The qualification source changed across meeting dates.')
        retained = {note['note_id']: note for note in context['notes']}
        previous_notes = previous['context']['notes']
        if new_week:
            last = max(note['meeting']['local_date'] for note in previous_notes)
            previous_notes = [note for note in previous_notes if note['meeting']['local_date'] == last]
        for note in previous_notes:
            other = retained.get(note['note_id'])
            if other is None or any(other[key] != note[key] for key in ('body_hash', 'body_fragment', 'meeting', 'source_status')):
                raise AssertionError('Confirmed historical text/paint/date/status changed or vanished.')
    return {'summary_ids': summaries, 'source_hashes': hashes,
            'untouched_empty_ids': sorted(absent),
            'current_note_hashes': {key: note['body_hash'] for key, note in current.items()}}


def verify_files(directory, hashes):
    for name, expected in hashes.items():
        if sha256((directory / name).read_bytes()).hexdigest() != expected:
            raise AssertionError('Retained publication evidence bytes changed.')


def text_nodes(value):
    if isinstance(value, dict):
        if value.get('type') == 'text':
            yield value
        for child in value.values():
            yield from text_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from text_nodes(child)

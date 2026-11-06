from copy import deepcopy

import pytest

from scripts.validation.project_week_assertions import verify_checkpoint


def checkpoint():
    rows, notes, expected = [], [], {}
    for number, state in (('101', 'In Analysis'), ('102', 'Fixed'), ('103', 'Open')):
        text = f'Human note {number}'
        expected[number] = text
        rows.append({'identity': {'stable_id': number}, 'status': state,
                     'summary_ref': {'summary_id': f'summary-{number}'}, 'source_hash': f'source-{number}'})
        notes.append({
            'note_id': f'note-{number}', 'issue_ref': {'stable_id': number},
            'meeting': {'local_date': '2026-10-26'}, 'source_status': {'value': state},
            'body_hash': f'hash-{number}',
            'body_fragment': {'blocks': [{'type': 'paragraph', 'content': [
                {'type': 'text', 'text': text, 'foreground': '#aa0000', 'background': None, 'marks': []},
            ]}]},
        })
    return {'snapshot': {'rows': rows}, 'context': {'notes': notes}}, expected


def test_shouldRejectMergedRowsWrongProviderStatusLostPaintAndChangedHistory():
    value, expected = checkpoint()
    assert len(verify_checkpoint(value, '2026-10-26', expected)['summary_ids']) == 3
    for mutation in ('rows', 'status', 'paint'):
        broken = deepcopy(value)
        if mutation == 'rows':
            broken['snapshot']['rows'].pop()
        elif mutation == 'status':
            broken['context']['notes'][0]['source_status']['value'] = 'AI guessed state'
        else:
            broken['context']['notes'][0]['body_fragment']['blocks'][0]['content'][0]['foreground'] = '#008000'
        with pytest.raises(AssertionError):
            verify_checkpoint(broken, '2026-10-26', expected)
    older = deepcopy(value)
    older['context']['notes'][0]['body_hash'] = 'different-original-hash'
    with pytest.raises(AssertionError):
        verify_checkpoint(value, '2026-10-26', expected, older)


def test_shouldRejectPartialMainlineButAllowExplicitManualGapBranch():
    from scripts.validation.project_week_ui import terminal_is_eligible

    assert terminal_is_eligible('draft_ready', 'changed_items')
    assert not terminal_is_eligible('partial', 'changed_items')
    assert not terminal_is_eligible('failed', 'manual_only')
    assert terminal_is_eligible('partial', 'manual_only')


@pytest.mark.parametrize('day,colors', [
    ('2026-10-28', ['#008000']),
    ('2026-10-30', ['#0055aa', '#aa0000']),
], ids=['highlighted-bold', 'mixed-paint'])
def test_shouldInspectSameTextNodesForColorAndAdditionalFormatting(day, colors):
    value, expected = checkpoint()
    for note in value['context']['notes']:
        note['meeting']['local_date'] = day
        note['body_fragment']['blocks'][0]['content'][0]['foreground'] = colors[0]
    nodes = value['context']['notes'][0]['body_fragment']['blocks'][0]['content']
    nodes[0].update(background='#fff4cc', marks=['strong'])
    if len(colors) > 1:
        nodes.append({'type': 'text', 'text': ' red segment', 'foreground': colors[1]})

    assert len(verify_checkpoint(value, day, expected)['current_note_hashes']) == 3

    broken = deepcopy(value)
    if day == '2026-10-28':
        broken['context']['notes'][0]['body_fragment']['blocks'][0]['content'][0]['marks'] = []
    else:
        broken['context']['notes'][0]['body_fragment']['blocks'][0]['content'].pop()
    with pytest.raises(AssertionError):
        verify_checkpoint(broken, day, expected)


def test_shouldDistinguishUntouchedUnchangedSlotFromLostExplicitEmptyEdit():
    value, expected = checkpoint()
    expected['102'] = ''
    value['context']['notes'] = [note for note in value['context']['notes']
                                 if note['issue_ref']['stable_id'] != '102']
    value['context']['current_observations'] = [{
        'issue_ref': {'stable_id': '102'}, 'source_state': 'unchanged',
        'source_status': {'value': 'Fixed'}, 'note_id': 'note-102',
    }]
    value['edits'] = []
    with pytest.raises(AssertionError):
        verify_checkpoint(value, '2026-10-26', expected)
    verified = verify_checkpoint(value, '2026-10-26', expected, untouched_empty_ids={'102'})
    assert verified['untouched_empty_ids'] == ['102']
    for mutation in ('changed', 'missing-observation', 'submitted-edit'):
        broken = deepcopy(value)
        if mutation == 'changed':
            broken['context']['current_observations'][0]['source_state'] = 'changed'
        elif mutation == 'missing-observation':
            broken['context']['current_observations'] = []
        else:
            broken['edits'] = [{'target': {'scope': 'daily_note', 'note_id': 'note-102'}}]
        with pytest.raises(AssertionError):
            verify_checkpoint(broken, '2026-10-26', expected, untouched_empty_ids={'102'})

import json

import pytest

from scripts.validation.profile_report_saves import EditorIdentity, save_payload


def test_save_sample_uses_latest_revision_and_note_hash_without_mutating_seed():
    note_id = '00000000-0000-4000-8000-000000000001'
    seed = {'payload_version': '2', 'expected_revision': '2', 'authored_edits': json.dumps([{
        'kind': 'note', 'target': {'scope': 'daily_note', 'note_id': note_id},
        'expected_original_hash': 'a' * 64,
        'fragment': {'blocks': [{'content': [{'type': 'text', 'text': 'original', 'foreground': '#aa0000'}]}]},
    }])}
    current = {'revision': 8, 'revision_hash': 'b' * 64, 'current_note_hashes': {note_id: 'c' * 64}}
    result = save_payload(seed, current, 1)
    edit = json.loads(result['authored_edits'])[0]
    assert result['expected_revision'] == '8'
    assert result['expected_revision_hash'] == 'b' * 64
    assert edit['expected_original_hash'] == 'c' * 64
    assert edit['fragment']['blocks'][0]['content'][0]['text'].endswith('Sample 01.')
    assert json.loads(seed['authored_edits'])[0]['fragment']['blocks'][0]['content'][0]['text'] == 'original'
    with pytest.raises(KeyError):
        save_payload(seed, {**current, 'current_note_hashes': {}}, 2)


def test_editor_identity_comes_from_the_mounted_article_not_hidden_untrusted_text():
    identity = EditorIdentity(
        '<input data-revision="99"><article data-report-editor data-revision="3" '
        'data-revision-hash="hash" data-draft-id="id"></article>'
    ).identity
    assert identity['data-revision'] == '3'
    assert identity['data-draft-id'] == 'id'

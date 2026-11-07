from copy import deepcopy
from dataclasses import asdict, replace

import pytest

from project_management.app.domain.capture_values import canonical_bytes, sha256_bytes
from project_management.app.domain.report_authoring_fragments import plain_text_fragment
from project_management.app.domain.report_continuity_context import validate_daily_authoring_context
from project_management.tests.test_report_history_composer_fix2 import context, snapshot
from project_management.tests.test_report_history_core_review_regressions import schema2_matrix_document
from project_management.tests.test_report_standup import pinned, render


def manual_source(reason='summary_pending'):
    source = snapshot()
    row = replace(
        source.rows[0], pending_reason=reason, summary_ref=None, what=None,
        current_position=None, verification=None, next_actions=(), evidence=(),
        blocker_refs=(), limitation_refs=(), summary_as_of=None,
    )
    return replace(source, rows=(row,), events=())


@pytest.mark.parametrize('reason', ['summary_pending', 'summary_stale'])
def test_manual_same_source_is_unchanged_without_materializing_a_note(reason):
    source = manual_source(reason)
    monday = context(source, '2026-11-02')
    next_capture = replace(
        source, capture_id='80000000-0000-4000-8000-000000000002',
        source_as_of='2026-11-03T01:00:00Z',
    )
    tuesday = context(next_capture, '2026-11-03', monday)

    assert monday['current_observations'][0]['source_state'] == 'initial'
    assert tuesday['current_observations'][0]['source_state'] == 'unchanged'
    assert tuesday['current_observations'][0]['capture_id'] == next_capture.capture_id
    assert tuesday['current_observations'][0]['accepted_summary_ref'] is None
    assert tuesday['notes'] == []
    assert 'ww45.2(In Progress): No source change' in render(next_capture, tuesday).plain_text


@pytest.mark.parametrize('reason', ['summary_pending', 'summary_stale'])
def test_manual_changed_source_keeps_change_and_current_provider_status(reason):
    source = manual_source()
    monday = context(source, '2026-11-02')
    changed = replace(
        source, rows=(replace(source.rows[0], source_hash='f' * 64, status='Fixed', pending_reason=reason),),
    )
    tuesday = context(changed, '2026-11-03', monday)

    assert tuesday['current_observations'][0]['source_state'] == 'changed'
    assert tuesday['current_observations'][0]['source_status']['value'] == 'Fixed'
    assert tuesday['notes'] == []
    assert 'ww45.2(Fixed): Source changed; note pending' in render(changed, tuesday).plain_text


@pytest.mark.parametrize('reason,has_hash,expected', [
    ('source_incomplete', True, 'incomplete'),
    ('source_missing', False, 'unavailable'),
    ('summary_pending', False, 'unavailable'),
])
def test_source_uncertainty_cannot_be_hidden_by_hash_or_accepted_summary(reason, has_hash, expected):
    source = snapshot()
    source = replace(source, rows=(replace(source.rows[0], pending_reason=None),))
    monday = context(source, '2026-11-02')
    uncertain = replace(source, rows=(replace(
        source.rows[0], pending_reason=reason, source_hash=source.rows[0].source_hash if has_hash else None,
        status='In Progress' if has_hash else None,
    ),))
    tuesday = context(uncertain, '2026-11-03', monday)

    assert tuesday['current_observations'][0]['source_state'] == expected
    assert tuesday['notes'] == monday['notes']
    assert 'No source change' not in render(uncertain, tuesday).plain_text
    if not has_hash:
        assert tuesday['current_observations'][0]['source_status']['value'] is None


@pytest.mark.parametrize('version', [1, 2])
def test_legacy_pending_hash_is_comparable_without_rewriting_old_context(version):
    source = manual_source()
    monday = context(source, '2026-11-02')
    monday['current_observations'][0]['source_state'] = 'pending'
    if version == 2:
        monday['schema_version'] = 2
        monday['meeting_skips'] = {
            'schema_version': 1, 'series_id': monday['series_id'], 'revision': 1,
            'revision_hash': 'a' * 64,
            'calendar': {'calendar_id': 'intel-workweek', 'revision': 7, 'timezone': 'Asia/Shanghai'},
            'from_date': '2026-11-02', 'through_date': '2026-11-02', 'days': [],
        }
    original = canonical_bytes(monday)
    tuesday = context(source, '2026-11-03', monday)

    assert tuesday['current_observations'][0]['source_state'] == 'unchanged'
    assert canonical_bytes(validate_daily_authoring_context(monday)) == original
    assert canonical_bytes(monday) == original
    assert set(tuesday['current_observations'][0]) == set(monday['current_observations'][0])


@pytest.mark.parametrize('previous_state,previous_hash', [
    ('incomplete', 'same'), ('unavailable', None), ('pending', None),
])
def test_uncomparable_baseline_requires_a_new_complete_observation(previous_state, previous_hash):
    source = manual_source()
    monday = context(source, '2026-11-02')
    observation = monday['current_observations'][0]
    observation['source_state'] = previous_state
    if previous_hash is None:
        observation['source_hash'] = None
        observation['source_status'] = {
            'availability': 'unavailable', 'value': None, 'field_path': None,
            'observed_at': None, 'source_ref': None, 'source_hash': None,
        }
    tuesday = context(source, '2026-11-03', monday)
    following_week = context(source, '2026-11-09', tuesday)

    assert tuesday['current_observations'][0]['source_state'] == 'pending'
    assert 'Source comparison unavailable' in render(source, tuesday).plain_text
    assert following_week['current_observations'][0]['source_state'] == 'unchanged'


def test_revised_summary_materializes_without_claiming_a_source_change():
    source = snapshot()
    row = replace(source.rows[0], pending_reason=None)
    source = replace(source, rows=(row,))
    monday = context(source, '2026-11-02')
    revised_ref = replace(row.summary_ref, revision=2, result_hash='f' * 64)
    revised = replace(source, rows=(replace(row, summary_ref=revised_ref, current_position='New accepted analysis.'),))
    tuesday = context(revised, '2026-11-03', monday)

    assert tuesday['current_observations'][0]['source_state'] == 'unchanged'
    assert len(tuesday['notes']) == 2
    note = tuesday['notes'][-1]
    assert note['meeting']['local_date'] == '2026-11-03'
    assert note['provenance']['ai_result_ref'] == asdict(revised_ref)
    assert note['body_fragment']['blocks'][0]['content'][0]['text'] == 'New accepted analysis.'
    assert tuesday['notes'][0] == monday['notes'][0]


def test_same_summary_preserves_human_deletion_paint_links_and_unresolved_actions():
    source = snapshot()
    source = replace(source, rows=(replace(source.rows[0], pending_reason=None),))
    monday = context(source, '2026-11-02')
    fragment = plain_text_fragment('Human correction only.')
    fragment['blocks'][0]['content'][0].update(foreground='#aa0000', background='#fff4cc', marks=['strong'])
    fragment['blocks'][0]['content'] = [*fragment['blocks'][0]['content'], {
        'type': 'link', 'href': 'https://example.test/run',
        'content': [{'type': 'text', 'text': 'Evidence', 'marks': [], 'foreground': None, 'background': None}],
    }]
    monday['notes'][0].update(body_fragment=fragment, body_hash=sha256_bytes(canonical_bytes(fragment)))
    original = canonical_bytes(monday)
    tuesday = context(source, '2026-11-03', monday)

    assert tuesday['current_observations'][0]['source_state'] == 'unchanged'
    assert canonical_bytes(tuesday['notes']) == canonical_bytes(monday['notes'])
    assert tuesday['actions'] == monday['actions']
    output = render(source, tuesday)
    assert output.plain_text.count('Human correction only.') == 1
    assert source.rows[0].current_position not in output.plain_text
    assert '#aa0000' in output.html_fragment and '#fff4cc' in output.html_fragment
    assert 'https://example.test/run' in output.html_fragment
    assert 'ww45.2(In Progress): No source change' in output.plain_text
    assert canonical_bytes(monday) == original


@pytest.mark.parametrize('concise', [True, False], ids=['standup', 'matrix'])
@pytest.mark.parametrize('state,label', [
    ('initial', 'Initial source; note pending'),
    ('changed', 'Source changed; note pending'),
    ('unchanged', 'No source change'),
    ('pending', 'Source comparison unavailable'),
    ('incomplete', 'Source incomplete'),
    ('unavailable', 'Source unavailable'),
])
def test_renderers_show_the_current_observation_without_an_authored_note(concise, state, label):
    source = manual_source()
    ctx = context(source, '2026-11-03')
    ctx['current_observations'][0]['source_state'] = state
    template = pinned() if concise else pinned(schema2_matrix_document())
    output = render(source, ctx, template)

    assert f'ww45.2(In Progress): {label}' in output.plain_text
    assert label in output.html_fragment
    assert ctx['notes'] == []


@pytest.mark.parametrize('concise', [True, False], ids=['standup', 'matrix'])
@pytest.mark.parametrize('state,show_warning', [
    ('unchanged', False), ('incomplete', True), ('unavailable', True), ('pending', True),
])
@pytest.mark.parametrize('text', ['', 'Today is a human observation.'], ids=['saved-empty', 'human'])
def test_saved_note_replaces_no_change_but_not_source_uncertainty(state, show_warning, text, concise):
    source = snapshot()
    source = replace(source, rows=(replace(source.rows[0], pending_reason=None),))
    ctx = context(source, '2026-11-03')
    ctx = deepcopy(ctx)
    ctx['current_observations'][0]['source_state'] = state
    body = plain_text_fragment(text)
    ctx['notes'][0].update(body_fragment=body, body_hash=sha256_bytes(canonical_bytes(body)))
    output = render(source, ctx, pinned() if concise else pinned(schema2_matrix_document()))
    matrix_text = output.plain_text if concise else output.plain_text.split('Meeting matrix\n', 1)[1]

    assert 'No source change' not in matrix_text
    assert ('Source ' in matrix_text) == show_warning
    if text:
        assert text in matrix_text
    assert source.rows[0].current_position not in matrix_text

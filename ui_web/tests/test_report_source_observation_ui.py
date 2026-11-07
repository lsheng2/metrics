from dataclasses import replace

from bs4 import BeautifulSoup
from django.template.loader import render_to_string
from django.utils.translation import override
import pytest

from project_management.app.domain.capture_values import canonical_bytes, sha256_bytes
from project_management.app.domain.report_authoring_fragments import plain_text_fragment
from project_management.app.domain.report_meeting_matrix import build_meeting_matrix
from project_management.tests.test_report_history_composer_fix2 import context, snapshot
from project_management.tests.test_report_source_observations import manual_source
from ui_web.report_continuity_view_model import matrix_cell


def rendered_cell(source, ctx, *, language='en', read_only=False):
    cell = build_meeting_matrix(source, ctx).rows[0].cells[-1]
    notes = {note['note_id']: note for note in ctx['notes']}
    observations = {item['note_id']: item for item in ctx['current_observations']}
    view = matrix_cell(cell, notes, observations, {}, {}, read_only)
    with override(language):
        body = render_to_string('projects/reports/pinned_blocks.html', {
            'report_body': {'blocks': [{
                'kind': 'data', 'source': 'meeting_matrix', 'label': 'Meeting matrix',
                'matrix': {'columns': [{'label': '2026-11-03'}],
                           'rows': [{'current_key': 'ALPHA-1', 'cells': [view]}]},
            }]},
        })
    return BeautifulSoup(body, 'html.parser')


@pytest.mark.parametrize('language,label', [('en', 'No source change'), ('zh-hans', '来源未变化')])
def test_editor_shows_translated_observation_outside_empty_editable_slot(language, label):
    source = manual_source()
    monday = context(source, '2026-11-02')
    tuesday = context(source, '2026-11-03', monday)
    soup = rendered_cell(source, tuesday, language=language)

    notice = soup.select_one('[data-matrix-source-observation]')
    assert notice is not None and notice.get_text(strip=True) == label
    assert notice.find_parent(attrs={'data-report-wysiwyg-region': True}) is None
    assert soup.select_one('[data-continuity-current-note-id]') is not None
    assert 'ww45.2(In Progress):' in soup.get_text()
    assert tuesday['notes'] == []


@pytest.mark.parametrize('state,label', [
    ('incomplete', 'Source incomplete'), ('unavailable', 'Source unavailable'),
    ('pending', 'Source comparison unavailable'),
])
def test_editor_keeps_uncertainty_visible_alongside_a_human_note(state, label):
    source = manual_source()
    ctx = context(source, '2026-11-03')
    observation = ctx['current_observations'][0]
    observation['source_state'] = state
    body = plain_text_fragment('Human follow-up.')
    ctx['notes'] = [{
        'note_id': observation['note_id'], 'issue_ref': observation['issue_ref'],
        'meeting': observation['meeting'], 'revision': 1,
        'body_fragment': body, 'body_hash': sha256_bytes(canonical_bytes(body)),
        'source_status': observation['source_status'], 'action_ids': [],
        'provenance': {
            'origin': 'human', 'ai_result_ref': None, 'original_fragment_hash': None,
            'edited_by': 'archive-owner', 'edited_at': '2026-11-03T01:00:00Z', 'accepted_publication': None,
        },
        'prior_revision_hash': None,
    }]
    soup = rendered_cell(source, ctx)

    assert soup.select_one('[data-matrix-source-observation]').get_text(strip=True) == label
    assert soup.select_one('[data-continuity-current-note-id]') is not None


def test_readonly_existing_note_does_not_repeat_its_prefix_or_no_change_notice():
    source = snapshot()
    source = replace(source, rows=(source.rows[0],))
    ctx = context(source, '2026-11-03')
    ctx['current_observations'][0]['source_state'] = 'unchanged'
    soup = rendered_cell(source, ctx, read_only=True)

    assert soup.get_text().count('ww45.2(In Progress):') == 1
    assert soup.select_one('[data-matrix-source-observation]') is None
    assert soup.select_one('[data-continuity-current-note-id]') is None

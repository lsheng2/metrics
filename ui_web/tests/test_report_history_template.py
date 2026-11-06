import pytest
from django.template.loader import render_to_string

from project_management.app.domain.report_authoring_fragments import plain_text_fragment
from project_management.app.domain.report_continuity import PublicationRef
from project_management.app.domain.report_meeting_matrix import MeetingMatrixCell
from project_management.app.domain.report_preparation import PreparationResult
from ui_web.facades.report_daily import ProjectReportDailyFacadeMixin
from ui_web.report_continuity_view_model import matrix_cell


@pytest.mark.parametrize('has_current_note', (False, True))
def test_should_render_history_before_current_source_prefix_in_each_cell(has_current_note):
    previous = {
        'meeting': {'workweek': 45, 'weekday': 1},
        'source_status': {'value': 'In Analysis'},
        'body_fragment': plain_text_fragment('Previous human note.'),
    }
    observation = {
        'meeting': {'workweek': 45, 'weekday': 2},
        'source_status': {'value': 'Fixed'},
    }
    notes = {'previous': previous}
    if has_current_note:
        notes['current'] = {
            **observation,
            'body_fragment': plain_text_fragment('Current human note.'),
            'body_hash': 'b' * 64,
        }
    cell = matrix_cell(
        MeetingMatrixCell('2026-11-03', tuple(notes), (), 'current', 'complete', 'content'),
        notes, {'current': observation}, {}, {}, False,
    )
    body = render_to_string('projects/reports/pinned_blocks.html', {
        'report_body': {'blocks': [{
            'kind': 'data',
            'source': 'meeting_matrix',
            'label': 'Meeting matrix',
            'matrix': {
                'columns': [{'label': '2026-11-03'}],
                'rows': [{'current_key': 'ALPHA-1', 'cells': [cell]}],
            },
        }]},
    })

    assert body.count('ww45.1(In Analysis):') == 1
    assert body.count('ww45.2(Fixed):') == 1
    assert body.index('ww45.1(In Analysis):') < body.index('Previous human note.')
    assert body.index('Previous human note.') < body.index('ww45.2(Fixed):')
    assert body.index('ww45.2(Fixed):') < body.index('data-report-wysiwyg-region')


def test_should_link_conflicting_finalized_preparation_to_existing_publication():
    project_id = '70000000-0000-4000-8000-000000000001'
    stage_id = '70000000-0000-4000-8000-000000000002'
    publication_id = '74000000-0000-4000-8000-000000000001'
    publication_url = f'/projects/{project_id}/stages/{stage_id}/reports/publications/{publication_id}/'
    result = PreparationResult(
        disposition='existing',
        preparation_id='71000000-0000-4000-8000-000000000001',
        operation_id=None,
        draft_id='73000000-0000-4000-8000-000000000001',
        draft_revision=2,
        publication_ref=PublicationRef(publication_id, 'b' * 64, 'c' * 40),
        effective_selection={
            'meeting_date': '2026-11-03', 'source_mode': 'saved_capture', 'analysis_mode': 'manual_only',
            'template_selection': {'template_id': 'daily-matrix', 'revision': 1},
        },
        selection_conflicts=('baseline',),
        state='finalized',
        links={'publication': publication_url, 'draft': '/existing-draft/'},
    )
    body = render_to_string('projects/reports/daily_preparation.html', {
        'detail': {'project': {'id': project_id}}, 'stage': {'id': stage_id},
        'daily_result': ProjectReportDailyFacadeMixin()._result_row(result),
    })

    assert 'Existing preparation' in body
    assert 'Unapplied choices: baseline' in body
    assert f'href="{publication_url}"' in body

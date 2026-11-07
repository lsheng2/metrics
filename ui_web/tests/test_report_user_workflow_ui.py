from types import SimpleNamespace

from bs4 import BeautifulSoup
from django.template.loader import render_to_string

from project_management.app.domain.report_continuity_edits import apply_continuity_changes
from project_management.tests.report_user_workflow_fixtures import daily, human, new_action, source_for
from project_management.tests.test_report_standup import pinned
from ui_web.report_continuity_view_model import pinned_matrix


def matrix_html(source, ctx):
    draft = SimpleNamespace(snapshot=source, authoring_context=ctx, template_snapshot=pinned())
    matrix = pinned_matrix(draft, {})
    return BeautifulSoup(render_to_string('projects/reports/pinned_blocks.html', {
        'report_body': {'blocks': [{'kind': 'data', 'source': 'meeting_matrix', 'label': 'Meeting matrix', 'matrix': matrix}]},
    }), 'html.parser')


def test_history_observations_are_readonly_and_only_current_date_mounts_an_editor():
    monday = human(daily(source_for(), '2026-11-02'), 'Monday note.')
    tuesday = daily(source_for('2026-11-03', 2), '2026-11-03', monday)
    source = source_for('2026-11-04', 3)
    ctx = daily(source, '2026-11-04', tuesday)
    soup = matrix_html(source, ctx)
    assert len(soup.select('[data-continuity-current-note-id]')) == 1
    assert soup.select('[data-continuity-current-note-id]')[0]['data-continuity-current-note-id'] == ctx['current_observations'][0]['note_id']
    assert 'ww45.2(In Progress): No source change' in soup.get_text()
    assert len(soup.select('[data-meeting-review]')) == 1
    assert soup.select_one('[data-continuity-add-action]') is not None


def test_human_action_controls_include_unassigned_owner_close_and_reopen():
    source = source_for()
    ctx = daily(source, '2026-11-02')
    ctx = apply_continuity_changes(ctx, (new_action(ctx),), 'host', '2026-11-02T02:00:00Z')
    soup = matrix_html(source, ctx)
    assert soup.select_one('[data-report-action-owner]') is not None
    state = soup.select_one('[data-report-action-state]')
    assert {item['value'] for item in state.select('option')} == {'open', 'unknown', 'done', 'canceled'}


def test_readonly_period_displays_an_observation_only_day():
    source = source_for('2026-11-03', 2)
    ctx = daily(source, '2026-11-03', daily(source_for(), '2026-11-02'))
    draft = SimpleNamespace(snapshot=source, authoring_context=ctx, template_snapshot=pinned())
    matrix = pinned_matrix(draft, {}, read_only=True)
    html = render_to_string('projects/reports/period.html', {
        'matrix_view': matrix,
        'detail': {'project': {'id': source.project_id, 'name': 'Demo'}},
        'stage': {'id': source.stage_id, 'name': 'Stage'}, 'period': {'period_key': '2026:ww45'},
    })
    assert 'ww45.2(In Progress): No source change' in BeautifulSoup(html, 'html.parser').get_text()

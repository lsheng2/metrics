from copy import deepcopy
from dataclasses import replace

import pytest

from project_management.app.api import reports as report_api
from project_management.app.domain.capture_values import canonical_bytes
from project_management.app.domain.report_continuity_context import validate_daily_authoring_context
from project_management.tests.report_user_workflow_fixtures import daily, human, source_for
from project_management.tests.test_report_standup import render


def test_zero_ticket_new_week_retains_real_date_notes_and_unfinished_actions():
    source = source_for('2026-11-06', summary=True)
    friday = human(daily(source, '2026-11-06'), 'Retain this human note.')
    empty = replace(source_for('2026-11-09', 2), rows=())
    monday = daily(empty, '2026-11-09', friday)
    matrix = report_api.build_meeting_matrix(empty, monday)
    output = render(empty, monday)
    assert [column.local_date for column in matrix.columns] == ['2026-11-09']
    assert len(matrix.rows) == 1
    assert matrix.rows[0].visibility == 'removed'
    assert 'Retain this human note.' in output.plain_text
    assert 'Retest fixed patch on board A0' in output.plain_text
    assert 'No current tickets' in output.plain_text
    assert 'Outside current scope' in output.plain_text


def test_no_change_observation_is_retained_after_a_third_day_without_a_note():
    monday = human(daily(source_for(), '2026-11-02'), 'Monday note.')
    tuesday = daily(source_for('2026-11-03', 2), '2026-11-03', monday)
    source = source_for('2026-11-04', 3)
    wednesday = daily(source, '2026-11-04', tuesday)
    output = render(source, wednesday)
    assert 'ww45.2(In Progress): No source change' in output.plain_text
    assert 'ww45.3(In Progress): No source change' in output.plain_text
    assert output.plain_text.index('ww45.1') < output.plain_text.index('ww45.2') < output.plain_text.index('ww45.3')
    assert [column.local_date for column in report_api.build_meeting_matrix(source, wednesday).columns] == [
        '2026-11-02', '2026-11-03', '2026-11-04',
    ]
    assert len(wednesday['notes']) == 1
    assert len(wednesday['current_observations']) == 1


def test_returning_ticket_does_not_resurrect_previously_replaced_summary():
    source = source_for(summary=True)
    monday = human(daily(source, '2026-11-02'), 'Human correction only.')
    tuesday = daily(replace(source_for('2026-11-03', 2), rows=()), '2026-11-03', monday)
    returned_source = source_for('2026-11-04', 3, summary=True)
    wednesday = daily(returned_source, '2026-11-04', tuesday)
    assert wednesday['current_observations'][0]['source_state'] == 'unchanged'
    assert len(wednesday['notes']) == 1
    output = render(returned_source, wednesday)
    assert 'Human correction only.' in output.plain_text
    assert source.rows[0].current_position not in output.plain_text
    assert 'Returned to scope' in output.plain_text


@pytest.mark.parametrize('authored', [False, True])
def test_same_capture_is_disclosed_even_when_a_human_note_exists(authored):
    source = source_for()
    monday = daily(source, '2026-11-02')
    tuesday = daily(source, '2026-11-03', monday)
    if authored:
        tuesday = human(tuesday, 'Tuesday note.')
    output = render(source, tuesday)
    assert 'Source not refreshed; using saved capture' in output.plain_text
    assert 'ww45.2(In Progress): No source change' not in output.plain_text
    assert source.source_as_of in output.plain_text
    assert tuesday['current_observations'][0]['source_state'] == 'unchanged'


def test_backfilled_meeting_discloses_capture_date_mismatch_without_changing_status():
    source = source_for('2026-11-07')
    ctx = daily(source, '2026-11-02')
    output = render(source, ctx)
    assert 'Source date differs from meeting date' in output.plain_text
    assert 'ww45.1(In Progress):' in output.plain_text
    assert '2026-11-07T01:00:00Z' in output.plain_text


def test_manual_note_coverage_is_not_ai_summary_or_meeting_confirmation():
    source = source_for()
    ctx = human(daily(source, '2026-11-02'), 'Meeting note.')
    output = render(source, ctx)
    assert 'Source: 1 complete, 0 incomplete, 0 unavailable' in output.plain_text
    assert 'AI summaries: 0/1 available' in output.plain_text
    assert 'Notes: 1/1' in output.plain_text
    assert 'Meeting review: 0/1' in output.plain_text
    assert 'Coverage: Partial' not in output.plain_text


def test_history_is_bounded_by_period_plus_last_observation_for_each_issue():
    monday = daily(source_for(), '2026-11-02')
    tuesday = daily(source_for('2026-11-03', 2), '2026-11-03', monday)
    wednesday = daily(source_for('2026-11-04', 3), '2026-11-04', tuesday)
    new_week = daily(source_for('2026-11-09', 4), '2026-11-09', wednesday)
    assert [item['meeting']['local_date'] for item in new_week['past_observations']] == ['2026-11-04']
    assert [column.local_date for column in report_api.build_meeting_matrix(source_for('2026-11-09', 4), new_week).columns] == ['2026-11-09']


def test_legacy_context_is_read_without_mutation_then_explicitly_prepared_as_v3():
    legacy = daily(source_for(), '2026-11-02')
    for key in ('past_observations', 'meeting_history', 'meeting_reviews', 'meeting_skips'):
        legacy.pop(key, None)
    legacy['schema_version'] = 1
    before = canonical_bytes(legacy)
    assert canonical_bytes(validate_daily_authoring_context(legacy)) == before
    successor = daily(source_for('2026-11-03', 2), '2026-11-03', legacy)
    assert successor['schema_version'] == 3
    assert canonical_bytes(legacy) == before
    assert successor['past_observations'][0] == legacy['current_observations'][0]


@pytest.mark.parametrize('mutation', ['future', 'duplicate', 'current-in-past', 'missing-meeting'])
def test_v3_history_rejects_ambiguous_or_future_observations(mutation):
    base = daily(source_for(), '2026-11-02')
    value = daily(source_for('2026-11-03', 2), '2026-11-03', base)
    value = deepcopy(value)
    assert value['schema_version'] == 3
    if mutation == 'future':
        value['past_observations'][0]['meeting']['local_date'] = '2026-11-04'
    elif mutation == 'duplicate':
        value['past_observations'].append(deepcopy(value['past_observations'][0]))
    elif mutation == 'current-in-past':
        value['past_observations'].append(deepcopy(value['current_observations'][0]))
    else:
        value['meeting_history'] = []
    with pytest.raises(report_api.ReportError):
        validate_daily_authoring_context(value)


def test_weekly_merge_prefers_selected_corrected_day_over_later_inherited_observation():
    from project_management.services.report_period_views import _merge_observations
    monday = daily(source_for(), '2026-11-02')
    tuesday = daily(source_for('2026-11-03', 2), '2026-11-03', monday)
    corrected = deepcopy(monday)
    corrected['current_observations'][0]['source_state'] = 'changed'
    merged = _merge_observations((corrected, tuesday))
    selected = next(item for item in merged if item['meeting']['local_date'] == '2026-11-02')
    assert selected['source_state'] == 'changed'


def test_reprepare_preserves_discussion_only_for_the_same_capture():
    from project_management.app.domain.report_observation_history import preserved_reviews
    from project_management.app.domain.report_continuity_edits import apply_continuity_changes
    source = source_for()
    parent = daily(source, '2026-11-02')
    parent = apply_continuity_changes(parent, ({
        'kind': 'set_meeting_review', 'issue_ref': parent['current_observations'][0]['issue_ref'], 'state': 'discussed',
    },), 'host', '2026-11-02T02:00:00Z')
    same = daily(source, '2026-11-02')
    newer = daily(source_for(index=2), '2026-11-02')
    assert len(preserved_reviews(parent, same)) == 1
    assert preserved_reviews(parent, newer) == ()

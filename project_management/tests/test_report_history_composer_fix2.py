from dataclasses import replace

from project_management.app.api import reports as report_api
from project_management.app.domain.report_continuity import PublicationRef, ReportingCalendar, build_daily_authoring_context, meeting_identity
from project_management.tests.report_draft_fixtures import valid_source_snapshot
from project_management.tests.report_render_fixtures import safe_snapshot
from project_management.tests.test_report_template_compilation import matrix_block


SERIES_ID = 'aaaaaaaa-aaaa-4aaa-8aaa-000000000001'
POLICY_HASH = '1' * 64


def calendar():
    return ReportingCalendar('intel-workweek', 7, 'Asia/Shanghai', 'date_map', {
        '2026-11-02': {'workweek_year': 2026, 'workweek': 45, 'weekday': 1},
        '2026-11-03': {'workweek_year': 2026, 'workweek': 45, 'weekday': 2},
        '2026-11-09': {'workweek_year': 2026, 'workweek': 46, 'weekday': 1},
        '2026-11-10': {'workweek_year': 2026, 'workweek': 46, 'weekday': 2},
    })


def matrix_options(*, full_history=False):
    options = matrix_block()['options']
    if full_history:
        options = dict(options, cross_week_carry='full_history')
    return options


def snapshot(capture_id='80000000-0000-4000-8000-000000000001'):
    return valid_source_snapshot(
        safe_snapshot(days=()),
        project_id='70000000-0000-4000-8000-000000000001',
        stage_id='70000000-0000-4000-8000-000000000002',
        owner_subject='archive-owner',
        rule_hash='b' * 64,
        source_commit='a' * 40,
        capture_id=capture_id,
    )


def context(snapshot, day, baseline=None, *, full_history=False, publication=None):
    return build_daily_authoring_context(
        series_id=SERIES_ID,
        series_policy_revision=1,
        series_policy_hash=POLICY_HASH,
        meeting=meeting_identity(calendar(), day),
        source_snapshot=snapshot,
        matrix_options=matrix_options(full_history=full_history),
        baseline_context=baseline,
        base_daily_publication=publication,
    )


def notes_for(ctx, stable_id):
    return [note for note in ctx['notes'] if note['issue_ref']['stable_id'] == stable_id]


def actions_for(ctx, stable_id):
    return [action for action in ctx['actions'] if action['issue_ref']['stable_id'] == stable_id]


def test_should_keep_resolved_action_catalog_but_not_recreate_or_display_it_cross_week():
    source = snapshot()
    day1 = context(source, '2026-11-02')
    action_id = actions_for(day1, '10001')[0]['action_id']
    resolved_actions = tuple(dict(action, tracking_state='done') if action['action_id'] == action_id else action for action in day1['actions'])
    baseline = dict(day1, actions=resolved_actions)

    new_week = context(source, '2026-11-09', baseline)

    retained = [action for action in actions_for(new_week, '10001') if action['action_id'] == action_id]
    assert len(retained) == 1
    assert retained[0]['tracking_state'] == 'done'
    assert action_id not in new_week['weekly_seed']['unresolved_action_ids']


def test_should_preserve_full_history_when_matrix_requests_full_history():
    source = snapshot()
    day1 = context(source, '2026-11-02', full_history=True)
    changed = replace(source, rows=(replace(source.rows[0], source_hash='f' * 64), source.rows[1]))
    day2 = context(changed, '2026-11-03', day1, full_history=True)
    new_week = context(changed, '2026-11-09', day2, full_history=True)

    assert [note['meeting']['local_date'] for note in notes_for(new_week, '10001')] == ['2026-11-02', '2026-11-03']


def test_should_use_publication_refs_only_for_earlier_period_refs_and_keep_sameweek_seed_stable():
    source = snapshot()
    base_ref = PublicationRef('71000000-0000-4000-8000-000000000001', '1' * 64, '2' * 40)
    day1 = context(source, '2026-11-02')
    day2 = context(source, '2026-11-03', day1)
    new_week = context(source, '2026-11-09', day2, publication=base_ref)

    assert day1['weekly_seed']['note_refs'] == []
    assert day2['weekly_seed']['earlier_period_refs'] == []
    assert day2['weekly_seed']['note_refs'] == day1['weekly_seed']['note_refs']
    assert new_week['weekly_seed']['earlier_period_refs'] == [{
        'publication_id': base_ref.publication_id,
        'manifest_hash': base_ref.manifest_hash,
        'commit': base_ref.commit,
    }]


def test_should_bind_current_observation_to_selected_snapshot_capture_not_summary_target():
    newer_snapshot = snapshot('90000000-0000-4000-8000-000000000900')
    first_row = newer_snapshot.rows[0]
    first_row = replace(first_row, summary_ref=replace(
        first_row.summary_ref,
        target_capture_id='80000000-0000-4000-8000-000000000001',
    ))
    newer_snapshot = replace(newer_snapshot, rows=(first_row, *newer_snapshot.rows[1:]))
    ctx = context(newer_snapshot, '2026-11-02')

    first = ctx['current_observations'][0]
    assert first['capture_id'] == newer_snapshot.capture_id
    assert first['accepted_summary_ref']['target_capture_id'] != newer_snapshot.capture_id
    assert first['source_status']['source_ref']['capture_id'] == newer_snapshot.capture_id
    assert first['source_status']['source_ref']['field_path'] == 'status'

from dataclasses import replace

import pytest

from project_management.app.api import reports as report_api
from project_management.app.domain.report_continuity_context import validate_daily_authoring_context
from project_management.tests.history_persistence_fixtures import (
    continuity_document,
    create_saved_daily,
    git_head,
    history_fixture,
    plain_fragment,
    prepare_daily,
    ref_for,
    source_snapshot,
    weekly_document,
    weekly_view_context,
)
from project_management.tests.report_draft_fixtures import draft_command
from project_management.tests.test_report_template_compilation import data_block, matrix_block


def test_should_validate_weekly_view_context_with_selected_daily_refs_and_null_meeting():
    context = weekly_view_context()

    validated = validate_daily_authoring_context(context)
    missing = dict(context, selected_daily_publications=())
    bad_meeting = dict(context, meeting={'local_date': '2026-11-06'})

    with pytest.raises(report_api.ReportError):
        validate_daily_authoring_context(missing)
    with pytest.raises(report_api.ReportError):
        validate_daily_authoring_context(bad_meeting)

    assert validated['report_role'] == 'weekly_view'
    assert validated['meeting'] is None
    assert validated['selected_daily_publications'][0]['publication_id'] == '74000000-0000-4000-8000-000000000001'


def test_should_project_meeting_matrix_for_b1_b2_contract_with_dates_title_actions_and_missing_days():
    base_snapshot = source_snapshot()
    calendar = report_api.ReportingCalendar(
        'intel-workweek',
        7,
        'Asia/Shanghai',
        'date_map',
        {
            '2026-11-02': {'workweek_year': 2026, 'workweek': 45, 'weekday': 1},
            '2026-11-06': {'workweek_year': 2026, 'workweek': 45, 'weekday': 5},
        },
    )
    day1 = report_api.build_daily_authoring_context(
        series_id='75000000-0000-4000-8000-000000000010',
        series_policy_revision=1,
        series_policy_hash='1' * 64,
        meeting=report_api.meeting_identity(calendar, '2026-11-02'),
        source_snapshot=base_snapshot,
        matrix_options=matrix_block()['options'],
    )
    snapshot = replace(base_snapshot, days=(report_api.ReportDay('2026-11-04', None, 'no_publication', None, {'state': 'missing'}, (), ()),))
    context = report_api.build_daily_authoring_context(
        series_id='75000000-0000-4000-8000-000000000010',
        series_policy_revision=1,
        series_policy_hash='1' * 64,
        meeting=report_api.meeting_identity(calendar, '2026-11-06'),
        source_snapshot=snapshot,
        matrix_options=matrix_block()['options'],
        baseline_context=day1,
    )

    matrix = report_api.build_meeting_matrix(snapshot, context)

    assert [column.local_date for column in matrix.columns] == ['2026-11-02', '2026-11-04', '2026-11-06']
    assert matrix.columns[1].state == 'missing'
    assert matrix.rows[0].title == snapshot.rows[0].title
    assert matrix.rows[0].current_key == snapshot.rows[0].identity.display_key
    assert matrix.rows[0].cells[1].note_ids
    assert matrix.rows[0].cells[1].action_ids
    assert matrix.rows[0].cells[1].state == 'missing'


def test_should_exclude_future_snapshot_days_from_daily_meeting_matrix():
    snapshot = replace(source_snapshot(), days=(report_api.ReportDay('2026-11-04', None, 'no_publication', None, {'state': 'missing'}, (), ()),))
    context = report_api.build_daily_authoring_context(
        series_id='75000000-0000-4000-8000-000000000010',
        series_policy_revision=1,
        series_policy_hash='1' * 64,
        meeting=report_api.meeting_identity(
            report_api.ReportingCalendar(
                'intel-workweek',
                7,
                'Asia/Shanghai',
                'date_map',
                {'2026-11-02': {'workweek_year': 2026, 'workweek': 45, 'weekday': 1}},
            ),
            '2026-11-02',
        ),
        source_snapshot=snapshot,
        matrix_options=matrix_block()['options'],
    )

    matrix = report_api.build_meeting_matrix(snapshot, context)

    assert [column.local_date for column in matrix.columns] == ['2026-11-02']


def test_should_project_current_period_note_columns_without_old_week_seed_columns():
    base_snapshot = replace(source_snapshot(), days=())
    day2_snapshot = replace(base_snapshot, rows=(replace(base_snapshot.rows[0], source_hash='c' * 64), base_snapshot.rows[1]))
    day3_snapshot = replace(base_snapshot, rows=(replace(base_snapshot.rows[0], source_hash='d' * 64), base_snapshot.rows[1]))
    calendar = report_api.ReportingCalendar(
        'intel-workweek',
        7,
        'Asia/Shanghai',
        'date_map',
        {
            '2026-11-02': {'workweek_year': 2026, 'workweek': 45, 'weekday': 1},
            '2026-11-03': {'workweek_year': 2026, 'workweek': 45, 'weekday': 2},
            '2026-11-04': {'workweek_year': 2026, 'workweek': 45, 'weekday': 3},
            '2026-11-09': {'workweek_year': 2026, 'workweek': 46, 'weekday': 1},
        },
    )
    day1 = report_api.build_daily_authoring_context(
        series_id='75000000-0000-4000-8000-000000000010',
        series_policy_revision=1,
        series_policy_hash='1' * 64,
        meeting=report_api.meeting_identity(calendar, '2026-11-02'),
        source_snapshot=base_snapshot,
        matrix_options=matrix_block()['options'],
    )
    day2 = report_api.build_daily_authoring_context(
        series_id='75000000-0000-4000-8000-000000000010',
        series_policy_revision=1,
        series_policy_hash='1' * 64,
        meeting=report_api.meeting_identity(calendar, '2026-11-03'),
        source_snapshot=day2_snapshot,
        matrix_options=matrix_block()['options'],
        baseline_context=day1,
    )
    day3 = report_api.build_daily_authoring_context(
        series_id='75000000-0000-4000-8000-000000000010',
        series_policy_revision=1,
        series_policy_hash='1' * 64,
        meeting=report_api.meeting_identity(calendar, '2026-11-04'),
        source_snapshot=day3_snapshot,
        matrix_options=matrix_block()['options'],
        baseline_context=day2,
    )
    next_week = report_api.build_daily_authoring_context(
        series_id='75000000-0000-4000-8000-000000000010',
        series_policy_revision=1,
        series_policy_hash='1' * 64,
        meeting=report_api.meeting_identity(calendar, '2026-11-09'),
        source_snapshot=day3_snapshot,
        matrix_options=matrix_block()['options'],
        baseline_context=day3,
    )

    same_week = report_api.build_meeting_matrix(day3_snapshot, day3)
    new_week = report_api.build_meeting_matrix(day3_snapshot, next_week)

    assert [column.local_date for column in same_week.columns] == ['2026-11-02', '2026-11-03', '2026-11-04']
    assert [column.local_date for column in new_week.columns] == ['2026-11-09']


def test_should_keep_source_availability_per_cell_not_per_column():
    for rows in (_availability_rows(), tuple(reversed(_availability_rows()))):
        snapshot = replace(source_snapshot(), rows=rows, days=())
        context = report_api.build_daily_authoring_context(
            series_id='75000000-0000-4000-8000-000000000010',
            series_policy_revision=1,
            series_policy_hash='1' * 64,
            meeting=report_api.meeting_identity(
                report_api.ReportingCalendar(
                    'intel-workweek',
                    7,
                    'Asia/Shanghai',
                    'date_map',
                    {'2026-11-02': {'workweek_year': 2026, 'workweek': 45, 'weekday': 1}},
                ),
                '2026-11-02',
            ),
            source_snapshot=snapshot,
            matrix_options=matrix_block()['options'],
        )

        matrix = report_api.build_meeting_matrix(snapshot, context)
        cells = {row.issue_ref['stable_id']: row.cells[0].state for row in matrix.rows}

        assert cells == {'10001': 'content', 'HSD-9002': 'unavailable'}


def test_should_render_missing_label_with_prior_note_in_pinned_report():
    snapshot, context = _missing_context_with_prior_note()
    rendered = _render_pinned_matrix(snapshot, context)

    assert 'Missing report' in rendered.html_fragment
    assert 'Missing report' in rendered.plain_text
    assert 'Scope is isolated to board A0 after overnight capture.' in rendered.html_fragment
    assert 'Scope is isolated to board A0 after overnight capture.' in rendered.plain_text


def test_should_render_action_owner_labels_without_fabricating_missing_owner():
    snapshot = replace(source_snapshot(), days=())
    context = report_api.build_daily_authoring_context(
        series_id='75000000-0000-4000-8000-000000000010',
        series_policy_revision=1,
        series_policy_hash='1' * 64,
        meeting=report_api.meeting_identity(
            report_api.ReportingCalendar(
                'intel-workweek',
                7,
                'Asia/Shanghai',
                'date_map',
                {'2026-11-02': {'workweek_year': 2026, 'workweek': 45, 'weekday': 1}},
            ),
            '2026-11-02',
        ),
        source_snapshot=snapshot,
        matrix_options=matrix_block()['options'],
    )
    first, second = context['actions'][:2]
    actions = (
        {**first, 'owner_ref': {'owner_id': 'qa-b', 'display_name': 'Bob QA'}},
        {**second, 'basis': 'proposed', 'owner_ref': {'owner_id': 'dev-c'}},
        {
            **first,
            'action_id': '76000000-0000-4000-8000-000000000099',
            'basis': 'proposed',
            'owner_ref': None,
            'body_fragment': plain_fragment('Unowned follow up.'),
        },
    )
    context = {**context, 'actions': actions}

    rendered = _render_pinned_matrix(snapshot, context)

    assert 'AR @Bob QA' in rendered.html_fragment
    assert 'AR @Bob QA' in rendered.plain_text
    assert 'AR? @dev-c' in rendered.html_fragment
    assert 'AR? @dev-c' in rendered.plain_text
    assert 'Unowned follow up.' in rendered.plain_text
    assert '@None' not in rendered.html_fragment
    assert '@None' not in rendered.plain_text


def test_should_render_report_and_issue_persistent_notes_once_in_pinned_report():
    snapshot = replace(source_snapshot(), days=())
    context = report_api.build_daily_authoring_context(
        series_id='75000000-0000-4000-8000-000000000010',
        series_policy_revision=1,
        series_policy_hash='1' * 64,
        meeting=report_api.meeting_identity(
            report_api.ReportingCalendar(
                'intel-workweek',
                7,
                'Asia/Shanghai',
                'date_map',
                {'2026-11-02': {'workweek_year': 2026, 'workweek': 45, 'weekday': 1}},
            ),
            '2026-11-02',
        ),
        source_snapshot=snapshot,
        matrix_options=matrix_block()['options'],
    )
    row_issue = context['row_order']['rows'][0]['issue_ref']
    context = {
        **context,
        'persistent_notes': (
            _persistent_note('76000000-0000-4000-8000-000000000011', 'report', None, 'Report persistent blue.', '#0055aa'),
            _persistent_note('76000000-0000-4000-8000-000000000012', 'issue', row_issue, 'Issue persistent green.', '#008800'),
        ),
    }

    rendered = _render_pinned_matrix(snapshot, context)

    assert rendered.html_fragment.count('Report persistent blue.') == 1
    assert rendered.html_fragment.count('Issue persistent green.') == 1
    assert rendered.plain_text.count('Report persistent blue.') == 1
    assert rendered.plain_text.count('Issue persistent green.') == 1
    assert 'color:#0055aa' in rendered.html_fragment
    assert 'color:#008800' in rendered.html_fragment
    matrix_html = rendered.html_fragment.split('Meeting matrix', 1)[1]
    assert matrix_html.index('DEMO-101') < matrix_html.index('Issue persistent green.')
    assert matrix_html.index('Issue persistent green.') < matrix_html.index('DEMO-102')


def test_should_project_seed_notes_inside_current_period_columns_and_use_current_snapshot_key():
    base_snapshot = source_snapshot()
    day1 = report_api.build_daily_authoring_context(
        series_id='75000000-0000-4000-8000-000000000010',
        series_policy_revision=1,
        series_policy_hash='1' * 64,
        meeting=report_api.meeting_identity(report_api.ReportingCalendar('intel-workweek', 7, 'Asia/Shanghai', 'date_map', {'2026-11-03': {'workweek_year': 2026, 'workweek': 45, 'weekday': 2}}), '2026-11-03'),
        source_snapshot=base_snapshot,
        matrix_options=matrix_block()['options'],
    )
    current_row = replace(base_snapshot.rows[0], identity=replace(base_snapshot.rows[0].identity, display_key='DEMO-101-CURRENT'))
    current_snapshot = replace(base_snapshot, rows=(current_row, base_snapshot.rows[1]))
    next_week = report_api.build_daily_authoring_context(
        series_id='75000000-0000-4000-8000-000000000010',
        series_policy_revision=1,
        series_policy_hash='1' * 64,
        meeting=report_api.meeting_identity(report_api.ReportingCalendar('intel-workweek', 7, 'Asia/Shanghai', 'date_map', {'2026-11-09': {'workweek_year': 2026, 'workweek': 46, 'weekday': 1}}), '2026-11-09'),
        source_snapshot=current_snapshot,
        matrix_options=matrix_block()['options'],
        baseline_context=day1,
    )

    matrix = report_api.build_meeting_matrix(current_snapshot, next_week)
    seed_note_id = next(
        note['note_id']
        for note in next_week['notes']
        if note['note_id'] in next_week['weekly_seed']['note_refs']
        and note['issue_ref']['stable_id'] == '10001'
    )
    row_10001 = next(row for row in matrix.rows if row.issue_ref['stable_id'] == '10001')

    assert [column.local_date for column in matrix.columns] == ['2026-11-09']
    assert row_10001.current_key == 'DEMO-101-CURRENT'
    assert seed_note_id in row_10001.cells[0].note_ids


@pytest.mark.django_db(transaction=True)
def test_should_create_and_finalize_weekly_view_from_selected_daily_refs_without_latest_source_read(tmp_path):
    fixture = history_fixture(tmp_path)
    day1 = prepare_daily(fixture, 1, '2026-11-02', None)
    saved1 = create_saved_daily(fixture, day1, 1, 'Day1 baseline.', '#ff0000', draft_command(8510))
    publication1 = fixture.draft_service.finalize_and_commit(fixture.actor, fixture.project.id, fixture.stage.id, saved1.draft_id, command_id=draft_command(8511), expected_revision=saved1.revision)
    fixture.source_reader.source_commit = git_head(fixture.archive_root, fixture.project.id, fixture.stage.id)
    day2 = prepare_daily(fixture, 2, '2026-11-03', ref_for(publication1))
    saved2 = create_saved_daily(fixture, day2, 2, 'Day2 baseline.', '#0000ff', draft_command(8520))
    publication2 = fixture.draft_service.finalize_and_commit(fixture.actor, fixture.project.id, fixture.stage.id, saved2.draft_id, command_id=draft_command(8521), expected_revision=saved2.revision)
    weekly = fixture.template_service.create(fixture.actor, fixture.project.id, command_id=draft_command(8522), name='Weekly matrix', document=weekly_document(), fill_policy={'schema_version': 2, 'instructions': {}, 'daily_note_instructions': None})
    refs = (ref_for(publication1), ref_for(publication2))
    before_calls = fixture.source_reader.calls

    draft = fixture.draft_service.create_period_view(
        fixture.actor, fixture.project.id, fixture.stage.id,
        command_id=draft_command(8523), series_id=fixture.series.series_id,
        period_key='intel-workweek:7:2026:ww45', selected_publication_refs=refs,
        template=report_api.UserTemplateSelection(str(weekly.template_id), weekly.revision, weekly.revision_hash),
    )
    publication = fixture.draft_service.finalize_and_commit(fixture.actor, fixture.project.id, fixture.stage.id, draft.draft_id, command_id=draft_command(8524), expected_revision=draft.revision)

    assert fixture.source_reader.calls == before_calls
    assert draft.authoring_context['report_role'] == 'weekly_view'
    assert draft.snapshot.capture_id == saved2.snapshot.capture_id
    assert publication.manifest.report_role == 'weekly_view'
    assert publication.manifest.period_key == 'intel-workweek:7:2026:ww45'


@pytest.mark.django_db(transaction=True)
def test_should_reject_save_to_weekly_view_draft(tmp_path):
    fixture, draft = weekly_fixture(tmp_path)
    note_id = draft.authoring_context['current_observations'][0]['note_id']

    with pytest.raises(report_api.ReportError) as error:
        fixture.draft_service.save_authored(
            fixture.actor, fixture.project.id, fixture.stage.id, draft.draft_id,
            command_id=draft_command(8530), expected_revision=draft.revision,
            expected_revision_hash=draft.revision_hash,
            edits=(report_api.AuthoredEditRequest('73000000-0000-4000-8000-000000000070', 'note',
                                                  {'scope': 'daily_note', 'note_id': note_id},
                                                  {'schema_version': 2, 'blocks': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': 'illegal weekly edit', 'marks': [], 'foreground': None, 'background': None}]}]},
                                                  None),),
        )

    assert error.value.code == 'REPORT_EDIT_TARGET_INVALID'


@pytest.mark.django_db(transaction=True)
def test_should_replay_period_view_command_before_selected_publication_reads(tmp_path, monkeypatch):
    fixture, draft = weekly_fixture(tmp_path)
    refs = tuple(report_api.PublicationRef(ref['publication_id'], ref['manifest_hash'], ref['commit']) for ref in draft.authoring_context['selected_daily_publications'])

    def fail_read(*args, **kwargs):
        raise AssertionError('period refs were read before command replay')

    monkeypatch.setattr('project_management.services.report_period_view_drafts.read_period_view', fail_read)

    replay = fixture.draft_service.create_period_view(
        fixture.actor, fixture.project.id, fixture.stage.id,
        command_id=draft_command(8523), series_id=fixture.series.series_id,
        period_key='intel-workweek:7:2026:ww45', selected_publication_refs=refs,
        template=report_api.UserTemplateSelection(
            draft.template_snapshot['selection']['template_id'],
            draft.template_snapshot['selection']['revision'],
            draft.template_snapshot['selection']['revision_hash'],
        ),
    )

    assert replay.draft_id == draft.draft_id


@pytest.mark.django_db(transaction=True)
def test_should_reject_daily_template_for_weekly_period_view(tmp_path):
    fixture = history_fixture(tmp_path)
    pub1, pub2 = two_daily_publications(fixture)
    daily_template = fixture.template_service.create(
        fixture.actor, fixture.project.id, command_id=draft_command(8540),
        name='Daily only', document=continuity_document(),
        fill_policy={'schema_version': 2, 'instructions': {}, 'daily_note_instructions': None},
    )

    with pytest.raises(report_api.ReportError) as error:
        fixture.draft_service.create_period_view(
            fixture.actor, fixture.project.id, fixture.stage.id,
            command_id=draft_command(8541), series_id=fixture.series.series_id,
            period_key='intel-workweek:7:2026:ww45', selected_publication_refs=(ref_for(pub1), ref_for(pub2)),
            template=report_api.UserTemplateSelection(str(daily_template.template_id), daily_template.revision, daily_template.revision_hash),
        )

    assert error.value.code in {'REPORT_TEMPLATE_UNSUPPORTED', 'REPORT_CONTEXT_REQUIRED'}


@pytest.mark.django_db(transaction=True)
def test_should_reject_duplicate_or_sameday_period_publication_refs(tmp_path):
    fixture = history_fixture(tmp_path)
    pub1, pub2 = two_daily_publications(fixture)
    weekly = fixture.template_service.create(
        fixture.actor, fixture.project.id, command_id=draft_command(8550),
        name='Weekly matrix', document=weekly_document(),
        fill_policy={'schema_version': 2, 'instructions': {}, 'daily_note_instructions': None},
    )

    with pytest.raises(report_api.ReportError):
        fixture.draft_service.create_period_view(
            fixture.actor, fixture.project.id, fixture.stage.id,
            command_id=draft_command(8551), series_id=fixture.series.series_id,
            period_key='intel-workweek:7:2026:ww45', selected_publication_refs=(ref_for(pub1), ref_for(pub1)),
            template=report_api.UserTemplateSelection(str(weekly.template_id), weekly.revision, weekly.revision_hash),
        )
    with pytest.raises(report_api.ReportError):
        fixture.draft_service.create_period_view(
            fixture.actor, fixture.project.id, fixture.stage.id,
            command_id=draft_command(8552), series_id=fixture.series.series_id,
            period_key='intel-workweek:7:2026:ww45', selected_publication_refs=(ref_for(pub2), ref_for(pub2)),
            template=report_api.UserTemplateSelection(str(weekly.template_id), weekly.revision, weekly.revision_hash),
        )


def weekly_fixture(tmp_path):
    fixture = history_fixture(tmp_path)
    pub1, pub2 = two_daily_publications(fixture)
    weekly = fixture.template_service.create(
        fixture.actor, fixture.project.id, command_id=draft_command(8522),
        name='Weekly matrix', document=weekly_document(),
        fill_policy={'schema_version': 2, 'instructions': {}, 'daily_note_instructions': None},
    )
    draft = fixture.draft_service.create_period_view(
        fixture.actor, fixture.project.id, fixture.stage.id,
        command_id=draft_command(8523), series_id=fixture.series.series_id,
        period_key='intel-workweek:7:2026:ww45', selected_publication_refs=(ref_for(pub1), ref_for(pub2)),
        template=report_api.UserTemplateSelection(str(weekly.template_id), weekly.revision, weekly.revision_hash),
    )
    return fixture, draft


def two_daily_publications(fixture):
    day1 = prepare_daily(fixture, 1, '2026-11-02', None)
    saved1 = create_saved_daily(fixture, day1, 1, 'Day1 baseline.', '#ff0000', draft_command(8560))
    pub1 = fixture.draft_service.finalize_and_commit(fixture.actor, fixture.project.id, fixture.stage.id, saved1.draft_id, command_id=draft_command(8561), expected_revision=saved1.revision)
    fixture.source_reader.source_commit = git_head(fixture.archive_root, fixture.project.id, fixture.stage.id)
    day2 = prepare_daily(fixture, 2, '2026-11-03', ref_for(pub1))
    saved2 = create_saved_daily(fixture, day2, 2, 'Day2 baseline.', '#0000ff', draft_command(8562))
    pub2 = fixture.draft_service.finalize_and_commit(fixture.actor, fixture.project.id, fixture.stage.id, saved2.draft_id, command_id=draft_command(8563), expected_revision=saved2.revision)
    return pub1, pub2


def _availability_rows():
    rows = source_snapshot().rows
    unavailable = replace(rows[1], status=None, source_hash=None, pending_reason='source_incomplete')
    return rows[0], unavailable


def _missing_context_with_prior_note():
    base_snapshot = source_snapshot()
    calendar = report_api.ReportingCalendar(
        'intel-workweek',
        7,
        'Asia/Shanghai',
        'date_map',
        {
            '2026-11-02': {'workweek_year': 2026, 'workweek': 45, 'weekday': 1},
            '2026-11-06': {'workweek_year': 2026, 'workweek': 45, 'weekday': 5},
        },
    )
    day1 = report_api.build_daily_authoring_context(
        series_id='75000000-0000-4000-8000-000000000010',
        series_policy_revision=1,
        series_policy_hash='1' * 64,
        meeting=report_api.meeting_identity(calendar, '2026-11-02'),
        source_snapshot=base_snapshot,
        matrix_options=matrix_block()['options'],
    )
    snapshot = replace(base_snapshot, days=(report_api.ReportDay('2026-11-04', None, 'no_publication', None, {'state': 'missing'}, (), ()),))
    context = report_api.build_daily_authoring_context(
        series_id='75000000-0000-4000-8000-000000000010',
        series_policy_revision=1,
        series_policy_hash='1' * 64,
        meeting=report_api.meeting_identity(calendar, '2026-11-06'),
        source_snapshot=snapshot,
        matrix_options=matrix_block()['options'],
        baseline_context=day1,
    )
    return snapshot, context


def _render_pinned_matrix(snapshot, context):
    return report_api.ReportRenderer().render_pinned(
        snapshot,
        _matrix_template_snapshot(),
        (),
        authoring_context=context,
        draft_id='77000000-0000-4000-8000-000000000001',
        revision=1,
        revision_hash='7' * 64,
        edition_state='draft',
    )


def _matrix_template_snapshot():
    document = {
        'schema_version': 2,
        'report_kind': 'daily',
        'blocks': [
            data_block('key_messages', 1),
            data_block('changes', 2),
            data_block('register', 3),
            data_block('coverage', 4),
            matrix_block(),
        ],
    }
    fill_policy = {'schema_version': 2, 'instructions': {}, 'daily_note_instructions': None}
    revision = report_api.validate_report_template_revision('Daily matrix', document, fill_policy)
    return {
        'selection': {
            'origin': 'user',
            'template_id': '78000000-0000-4000-8000-000000000001',
            'revision': 1,
            'revision_hash': revision.revision_hash,
        },
        'resolved_document': revision.document,
        'presentation_hash': revision.presentation_hash,
        'fill_policy': revision.fill_policy,
        'fill_policy_hash': revision.fill_policy_hash,
        'renderer_version': 'template-document/1',
    }


def _persistent_note(note_id, target, issue_ref, text, color):
    return {
        'note_id': note_id,
        'target': target,
        'issue_ref': issue_ref,
        'fragment': plain_fragment(text, foreground=color),
        'revision': 1,
        'carry_forward': False,
        'provenance': {'origin': 'human', 'edited_by': 'archive-owner', 'edited_at': '2026-11-02T00:00:00+00:00'},
    }

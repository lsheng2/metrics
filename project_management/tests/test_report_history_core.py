from dataclasses import replace
from uuid import UUID, uuid5

import pytest
from django.test import TestCase

from project_management.app.api import reports as report_api
from project_management.app.domain.capture_values import canonical_bytes, decode_json, sha256_bytes
from project_management.app.domain.contracts import ProjectActor
from project_management.app.domain.report_continuity import (
    ReportingCalendar,
    build_daily_authoring_context,
    build_row_order,
    meeting_identity,
)
from project_management.models import Project, ProjectStage
from project_management.models_report_templates import ReportTemplateUse
from project_management.tests.report_draft_fixtures import (
    DraftArchive,
    FixedClock,
    StaticSourceReader,
    draft_command,
    draft_selection,
    valid_source_snapshot,
)
from project_management.tests.report_render_fixtures import safe_snapshot
from project_management.tests.test_report_template_compilation import matrix_block, schema1_document


def schema2_matrix_document():
    document = dict(schema1_document())
    document['schema_version'] = 2
    document['blocks'] = [*document['blocks'], matrix_block()]
    return document


def schema2_policy():
    return {'schema_version': 2, 'instructions': {}, 'daily_note_instructions': None}


def calendar():
    return ReportingCalendar(
        'intel-workweek',
        7,
        'Asia/Shanghai',
        'date_map',
        {
            '2026-11-02': {'workweek_year': 2026, 'workweek': 45, 'weekday': 1},
            '2026-11-03': {'workweek_year': 2026, 'workweek': 45, 'weekday': 2},
            '2027-01-01': {'workweek_year': 2027, 'workweek': 1, 'weekday': 5},
        },
    )


def source_snapshot():
    return valid_source_snapshot(
        safe_snapshot(days=()),
        project_id='70000000-0000-4000-8000-000000000001',
        stage_id='70000000-0000-4000-8000-000000000002',
        owner_subject='archive-owner',
        rule_hash='b' * 64,
        source_commit='a' * 40,
        capture_id='80000000-0000-4000-8000-000000000001',
    )


def test_should_resolve_calendar_identity_from_explicit_map_and_refuse_missing_dates():
    meeting = meeting_identity(calendar(), '2027-01-01')

    assert meeting.local_date == '2027-01-01'
    assert meeting.workweek_year == 2027
    assert meeting.workweek == 1
    assert meeting.weekday == 5
    with pytest.raises(report_api.ReportError) as missing:
        meeting_identity(calendar(), '2026-11-06')
    assert missing.value.code == 'REPORT_CALENDAR_UNAVAILABLE'


def test_should_preserve_existing_rows_append_new_batch_and_reuse_reentered_position():
    rows = tuple(source_snapshot().rows)
    first = build_row_order(None, (rows[1], rows[0]), matrix_block()['options'])
    extra = replace(rows[0], identity=replace(rows[0].identity, stable_id='10003', display_key='DEMO-103'))
    second = build_row_order(first, (rows[1], rows[0], extra), matrix_block()['options'])
    removed = build_row_order(second, (rows[0], extra), matrix_block()['options'])
    reentered = build_row_order(removed, (rows[1], rows[0], extra), matrix_block()['options'])

    assert [row['issue_ref']['stable_id'] for row in first['rows']] == ['10001', 'HSD-9002']
    assert [row['issue_ref']['stable_id'] for row in second['rows']] == ['10001', 'HSD-9002', '10003']
    assert [row['visibility'] for row in removed['rows']] == ['visible', 'removed', 'visible']
    assert reentered['rows'][1]['issue_ref']['stable_id'] == 'HSD-9002'
    assert reentered['rows'][1]['position'] == second['rows'][1]['position']


def test_should_keep_prior_human_note_on_unchanged_day_without_today_copy_then_add_changed_note():
    snapshot = source_snapshot()
    day1 = build_daily_authoring_context(
        series_id='aaaaaaaa-aaaa-4aaa-8aaa-000000000001',
        series_policy_revision=1,
        series_policy_hash='1' * 64,
        meeting=meeting_identity(calendar(), '2026-11-02'),
        source_snapshot=snapshot,
        matrix_options=matrix_block()['options'],
    )
    day2 = build_daily_authoring_context(
        series_id='aaaaaaaa-aaaa-4aaa-8aaa-000000000001',
        series_policy_revision=1,
        series_policy_hash='1' * 64,
        meeting=meeting_identity(calendar(), '2026-11-03'),
        source_snapshot=snapshot,
        matrix_options=matrix_block()['options'],
        baseline_context=day1,
    )
    changed_rows = (replace(snapshot.rows[0], source_hash='f' * 64), snapshot.rows[1])
    changed = build_daily_authoring_context(
        series_id='aaaaaaaa-aaaa-4aaa-8aaa-000000000001',
        series_policy_revision=1,
        series_policy_hash='1' * 64,
        meeting=meeting_identity(calendar(), '2026-11-03'),
        source_snapshot=replace(snapshot, rows=changed_rows),
        matrix_options=matrix_block()['options'],
        baseline_context=day1,
    )

    assert [note['meeting']['local_date'] for note in day2['notes']] == ['2026-11-02', '2026-11-02']
    assert all(observation['source_state'] == 'unchanged' for observation in day2['current_observations'])
    assert day2['notes'][0]['body_hash'] == day1['notes'][0]['body_hash']
    assert any(note['meeting']['local_date'] == '2026-11-03' for note in changed['notes'])
    assert any(observation['source_state'] == 'changed' for observation in changed['current_observations'])


class TestReportHistoryCoreServices(TestCase):
    def setUp(self):
        self.actor = ProjectActor('archive-owner')
        self.template_service = report_api.ReportTemplateService(clock=FixedClock())
        self.project = Project.objects.create(owner_subject=self.actor.subject, key='alpha', name='Alpha')
        self.stage = ProjectStage.objects.create(
            project=self.project,
            key='release-1',
            name='Release 1',
            selection_json={'profile_id': 'alpha-jira', 'revision': 1},
            descriptor_json={'provider_id': 'jira'},
            definition_hash='b' * 64,
        )
        self.continuity = report_api.ReportContinuityService(template_service=self.template_service, clock=FixedClock())

    def matrix_template(self, command):
        return self.template_service.create(
            self.actor,
            self.project.id,
            command_id=draft_command(command),
            name='Daily matrix',
            document=schema2_matrix_document(),
            fill_policy=schema2_policy(),
        )

    def test_should_create_series_policy_with_cas_replay_and_reject_schema1_template(self):
        matrix = self.matrix_template(6000)
        standalone = self.template_service.create(
            self.actor,
            self.project.id,
            command_id=draft_command(6001),
            name='Standalone',
            document=schema1_document(),
            fill_policy={'schema_version': 1, 'instructions': {}},
        )
        selection = report_api.UserTemplateSelection(str(matrix.template_id), matrix.revision, matrix.revision_hash)

        created = self.continuity.create_series(
            self.actor,
            self.project.id,
            self.stage.id,
            command_id=draft_command(6002),
            name='Daily PM',
            calendar=calendar(),
            template_selection=selection,
        )
        replay = self.continuity.create_series(
            self.actor,
            self.project.id,
            self.stage.id,
            command_id=draft_command(6002),
            name='Daily PM',
            calendar=calendar(),
            template_selection=selection,
        )
        saved = self.continuity.save_series_policy(
            self.actor,
            self.project.id,
            self.stage.id,
            command_id=draft_command(6003),
            series_id=created.series_id,
            expected_revision=1,
            expected_revision_hash=created.revision_hash,
            name='Daily PM renamed',
            calendar=calendar(),
            template_selection=selection,
        )

        with pytest.raises(report_api.ReportError) as stale:
            self.continuity.save_series_policy(
                self.actor,
                self.project.id,
                self.stage.id,
                command_id=draft_command(6004),
                series_id=created.series_id,
                expected_revision=1,
                expected_revision_hash=created.revision_hash,
                name='stale',
                calendar=calendar(),
                template_selection=selection,
            )
        with pytest.raises(report_api.ReportError) as schema1:
            self.continuity.create_series(
                self.actor,
                self.project.id,
                self.stage.id,
                command_id=draft_command(6005),
                name='Wrong',
                calendar=calendar(),
                template_selection=report_api.UserTemplateSelection(str(standalone.template_id), 1, standalone.revision_hash),
            )

        assert replay.revision_hash == created.revision_hash
        assert saved.revision == 2
        assert stale.value.code == 'REPORT_REVISION_CONFLICT'
        assert schema1.value.code == 'REPORT_CONTEXT_REQUIRED'

    def test_should_pin_continuity_template_use_and_read_by_payload_hash_without_latest_lookup(self):
        matrix = self.matrix_template(6010)
        selection = report_api.UserTemplateSelection(str(matrix.template_id), matrix.revision, matrix.revision_hash)
        pinned = self.template_service.use(
            self.actor,
            self.project.id,
            command_id=draft_command(6011),
            draft_id='70000000-0000-4000-8000-000000000010',
            request_hash='6' * 64,
            selection=selection,
            use_mode='continuity_prepare',
        )
        use = ReportTemplateUse.objects.get(command=draft_command(6011))
        self.template_service.archive(
            self.actor,
            self.project.id,
            str(matrix.template_id),
            command_id=draft_command(6012),
            expected_revision=matrix.revision,
            expected_revision_hash=matrix.revision_hash,
        )

        read = self.template_service.read_use(
            self.actor,
            self.project.id,
            draft_id='70000000-0000-4000-8000-000000000010',
            template_use_hash=use.snapshot_hash,
        )

        assert read.template_snapshot == pinned.template_snapshot
        assert read.template_definition == pinned.template_definition
        assert read.command_id == draft_command(6011)


@pytest.mark.django_db(transaction=True)
def test_should_prepare_immutable_context_seed_from_source_publication_and_template_use(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    Project.objects.create(id=environment.project.id, owner_subject=environment.actor.subject, key='alpha', name='Alpha')
    ProjectStage.objects.create(
        id=environment.stage.id,
        project_id=environment.project.id,
        key='release-1',
        name='Release 1',
        selection_json={'profile_id': 'alpha-jira', 'revision': 1},
        descriptor_json={'provider_id': 'jira'},
        definition_hash=environment.stage.definition_hash,
    )
    template_service = report_api.ReportTemplateService(clock=FixedClock())
    matrix = template_service.create(
        environment.actor,
        environment.project.id,
        command_id=draft_command(6022),
        name='Daily matrix',
        document=schema2_matrix_document(),
        fill_policy=schema2_policy(),
    )
    continuity = report_api.ReportContinuityService(
        environment,
        StaticSourceReader(source_commit=environment.repository.head(), rule_hash=environment.stage.definition_hash),
        template_service=template_service,
        clock=FixedClock(),
    )
    selection = report_api.UserTemplateSelection(str(matrix.template_id), matrix.revision, matrix.revision_hash)
    series = continuity.create_series(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(6023),
        name='Daily PM',
        calendar=calendar(),
        template_selection=selection,
    )
    create_command_id = draft_command(6024)
    draft_id = str(uuid5(UUID(environment.stage.id), f'draft:{create_command_id}'))
    template_service.use(
        environment.actor,
        environment.project.id,
        command_id=create_command_id,
        draft_id=draft_id,
        request_hash='7' * 64,
        selection=selection,
        use_mode='continuity_prepare',
    )
    template_use_hash = ReportTemplateUse.objects.get(command=create_command_id).snapshot_hash
    selected_source = draft_selection()

    ref = continuity.prepare_context(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        preparation_id='71000000-0000-4000-8000-000000000100',
        create_command_id=create_command_id,
        series_id=series.series_id,
        series_policy_hash=series.revision_hash,
        meeting_date='2026-11-02',
        expected_baseline_ref=None,
        selection=selected_source,
        template_use_hash=template_use_hash,
    )
    seed_path = environment.repository.runtime / 'report-preparations' / ref.preparation_id / 'context.json'
    before = seed_path.read_bytes()
    replay = continuity.prepare_context(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        preparation_id='71000000-0000-4000-8000-000000000100',
        create_command_id=create_command_id,
        series_id=series.series_id,
        series_policy_hash=series.revision_hash,
        meeting_date='2026-11-02',
        expected_baseline_ref=None,
        selection=selected_source,
        template_use_hash=template_use_hash,
    )
    payload = decode_json(before)

    with pytest.raises(report_api.ReportError) as wrong_template:
        continuity.prepare_context(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            preparation_id='71000000-0000-4000-8000-000000000100',
            create_command_id=create_command_id,
            series_id=series.series_id,
            series_policy_hash=series.revision_hash,
            meeting_date='2026-11-02',
            expected_baseline_ref=None,
            selection=selected_source,
            template_use_hash='0' * 64,
        )

    assert replay == ref
    assert seed_path.read_bytes() == before
    assert payload['draft_id'] == draft_id
    assert payload['context_hash'] == sha256_bytes(canonical_bytes(payload['context']))
    assert payload['context']['base_daily_publication'] is None
    assert payload['context']['current_observations'][0]['source_status']['value'] == 'In Progress'
    assert wrong_template.value.code == 'REPORT_REVISION_CONFLICT'

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID, uuid5

import pytest
from django.test import TestCase

from project_management.app.api import reports as report_api
from project_management.app.domain.capture_values import canonical_bytes, decode_json, sha256_bytes
from project_management.app.domain.contracts import ProjectActor
from project_management.app.domain.report_continuity import (
    PublicationRef,
    ReportingCalendar,
    build_daily_authoring_context,
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


SERIES_ID = 'aaaaaaaa-aaaa-4aaa-8aaa-000000000001'
POLICY_HASH = '1' * 64


def schema2_matrix_document():
    document = dict(schema1_document())
    document['schema_version'] = 2
    document['blocks'] = [*document['blocks'], matrix_block()]
    return document


def schema2_policy():
    return {'schema_version': 2, 'instructions': {}, 'daily_note_instructions': None}


def review_calendar():
    return ReportingCalendar(
        'intel-workweek',
        7,
        'Asia/Shanghai',
        'date_map',
        {
            '2026-11-02': {'workweek_year': 2026, 'workweek': 45, 'weekday': 1},
            '2026-11-03': {'workweek_year': 2026, 'workweek': 45, 'weekday': 2},
            '2026-11-06': {'workweek_year': 2026, 'workweek': 45, 'weekday': 5},
            '2026-11-09': {'workweek_year': 2026, 'workweek': 46, 'weekday': 1},
        },
    )


def build_context(snapshot, day, baseline=None, base_daily_publication=None):
    return build_daily_authoring_context(
        series_id=SERIES_ID,
        series_policy_revision=1,
        series_policy_hash=POLICY_HASH,
        meeting=meeting_identity(review_calendar(), day),
        source_snapshot=snapshot,
        matrix_options=matrix_block()['options'],
        baseline_context=baseline,
        base_daily_publication=base_daily_publication,
    )


def valid_snapshot(capture_id='80000000-0000-4000-8000-000000000001'):
    return valid_source_snapshot(
        safe_snapshot(days=()),
        project_id='70000000-0000-4000-8000-000000000001',
        stage_id='70000000-0000-4000-8000-000000000002',
        owner_subject='archive-owner',
        rule_hash='b' * 64,
        source_commit='a' * 40,
        capture_id=capture_id,
    )


def row_by_key(context, stable_id):
    issue_notes = [note for note in context['notes'] if note['issue_ref']['stable_id'] == stable_id]
    return issue_notes


def test_should_reject_bad_or_ambiguous_calendar_maps():
    bad_week = ReportingCalendar('intel-workweek', 7, 'Asia/Shanghai', 'date_map', {
        '2026-11-02': {'workweek_year': 2026, 'workweek': 54, 'weekday': 1},
    })
    ambiguous = ReportingCalendar('intel-workweek', 7, 'Asia/Shanghai', 'date_map', {
        '2026-11-02': {'workweek_year': 2026, 'workweek': 45, 'weekday': 1},
        '2026-11-03': {'workweek_year': 2026, 'workweek': 45, 'weekday': 1},
    })

    with pytest.raises(report_api.ReportError) as bad:
        meeting_identity(bad_week, '2026-11-02')
    with pytest.raises(report_api.ReportError) as dup:
        meeting_identity(ambiguous, '2026-11-02')

    assert bad.value.code == 'REPORT_CALENDAR_UNAVAILABLE'
    assert dup.value.code == 'REPORT_CALENDAR_UNAVAILABLE'


def test_should_treat_same_hash_pending_to_accepted_summary_as_changed():
    snapshot = valid_snapshot()
    pending_row = replace(snapshot.rows[0], summary_ref=None, pending_reason='summary_pending')
    day1 = build_context(replace(snapshot, rows=(pending_row, snapshot.rows[1])), '2026-11-02')
    day2 = build_context(snapshot, '2026-11-03', day1)

    observation = next(item for item in day2['current_observations'] if item['issue_ref']['stable_id'] == '10001')

    assert observation['source_state'] == 'changed'
    assert any(note['meeting']['local_date'] == '2026-11-03' for note in row_by_key(day2, '10001'))


def test_should_keep_colored_deleted_human_note_and_reject_corrupt_context():
    snapshot = valid_snapshot()
    day1 = build_context(snapshot, '2026-11-02')
    fragment = {
        'schema_version': 2,
        'blocks': [{
            'type': 'paragraph',
            'content': [{
                'type': 'text',
                'text': 'human kept red text; deleted AI sentence stays deleted',
                'marks': [],
                'foreground': '#ff0000',
                'background': None,
            }],
        }],
    }
    note = dict(day1['notes'][0], body_fragment=fragment, body_hash=sha256_bytes(canonical_bytes(fragment)))
    human = dict(day1, notes=(note, *day1['notes'][1:]))
    day2 = build_context(snapshot, '2026-11-03', human)
    corrupt = dict(human, notes=(dict(note, body_hash='0' * 64), *human['notes'][1:]))
    unknown = dict(human, unexpected=True)

    assert day2['notes'][0]['body_hash'] == note['body_hash']
    assert day2['notes'][0]['body_fragment'] == fragment
    with pytest.raises(report_api.ReportError):
        build_context(snapshot, '2026-11-03', corrupt)
    with pytest.raises(report_api.ReportError):
        build_context(snapshot, '2026-11-03', unknown)


def test_should_link_notes_to_actions_and_not_recreate_resolved_repeated_actions():
    snapshot = valid_snapshot()
    day1 = build_context(snapshot, '2026-11-02')
    note = row_by_key(day1, '10001')[0]
    action_id = note['action_ids'][0]
    resolved = tuple(dict(action, tracking_state='done') if action['action_id'] == action_id else action for action in day1['actions'])
    day2 = build_context(replace(snapshot, rows=(replace(snapshot.rows[0], source_hash='f' * 64), snapshot.rows[1])), '2026-11-03', dict(day1, actions=resolved))

    assert action_id in {action['action_id'] for action in day1['actions']}
    assert len([action for action in day2['actions'] if action['action_id'] == action_id]) == 1
    assert action_id not in row_by_key(day2, '10001')[-1]['action_ids']


def test_should_roll_new_week_to_last_note_and_unresolved_actions_only():
    snapshot = valid_snapshot()
    day1 = build_context(snapshot, '2026-11-02')
    changed = replace(snapshot, rows=(replace(snapshot.rows[0], source_hash='f' * 64), snapshot.rows[1]))
    day2 = build_context(changed, '2026-11-03', day1)
    publication = PublicationRef('71000000-0000-4000-8000-000000000001', '1' * 64, '2' * 40)
    new_week = build_context(changed, '2026-11-09', day2, base_daily_publication=publication)

    notes_10001 = row_by_key(new_week, '10001')

    assert [note['meeting']['local_date'] for note in notes_10001] == ['2026-11-03']
    assert new_week['weekly_seed']['earlier_period_refs']
    assert set(new_week['weekly_seed']['unresolved_action_ids'])


class TestReportHistoryCoreReviewSeed(TestCase):
    def setUp(self):
        self.actor = ProjectActor('archive-owner')
        self.temporary = TemporaryDirectory(prefix='history-core-review-', dir=Path.cwd() / 'tmp_ui_validation')
        self.addCleanup(self.temporary.cleanup)

    def test_should_prepare_initial_seed_without_baseline_and_refuse_standalone_baseline(self):
        fixture = self._fixture()
        ref = fixture['continuity'].prepare_context(
            self.actor,
            fixture['project_id'],
            fixture['stage_id'],
            preparation_id='71000000-0000-4000-8000-000000000200',
            create_command_id=fixture['command_id'],
            series_id=fixture['series'].series_id,
            series_policy_hash=fixture['series'].revision_hash,
            meeting_date='2026-11-02',
            expected_baseline_ref=None,
            selection=fixture['selection'],
            template_use_hash=fixture['template_use_hash'],
        )
        seed = decode_json((fixture['runtime'] / 'report-preparations' / ref.preparation_id / 'context.json').read_bytes())

        with pytest.raises(report_api.ReportError) as wrong_date:
            fixture['continuity'].prepare_context(
                self.actor,
                fixture['project_id'],
                fixture['stage_id'],
                preparation_id=ref.preparation_id,
                create_command_id=fixture['command_id'],
                series_id=fixture['series'].series_id,
                series_policy_hash=fixture['series'].revision_hash,
                meeting_date='2026-11-03',
                expected_baseline_ref=None,
                selection=fixture['selection'],
                template_use_hash=fixture['template_use_hash'],
            )
        with pytest.raises(report_api.ReportError) as baseline:
            fixture['continuity'].prepare_context(
                self.actor,
                fixture['project_id'],
                fixture['stage_id'],
                preparation_id='71000000-0000-4000-8000-000000000201',
                create_command_id=fixture['command_id_2'],
                series_id=fixture['series'].series_id,
                series_policy_hash=fixture['series'].revision_hash,
                meeting_date='2026-11-02',
                expected_baseline_ref=fixture['standalone_baseline_ref'],
                selection=fixture['selection'],
                template_use_hash=fixture['template_use_hash_2'],
            )

        assert seed['context']['base_daily_publication'] is None
        assert wrong_date.value.code == 'REPORT_REVISION_CONFLICT'
        assert baseline.value.code == 'REPORT_HISTORY_UNAVAILABLE'

    def test_should_prepare_with_old_policy_hash_after_later_policy_save(self):
        fixture = self._fixture()
        old = fixture['series']
        fixture['continuity'].save_series_policy(
            self.actor,
            fixture['project_id'],
            fixture['stage_id'],
            command_id=draft_command(6060),
            series_id=old.series_id,
            expected_revision=old.revision,
            expected_revision_hash=old.revision_hash,
            name='new name',
            calendar=review_calendar(),
            template_selection=fixture['template_selection'],
        )

        ref = fixture['continuity'].prepare_context(
            self.actor,
            fixture['project_id'],
            fixture['stage_id'],
            preparation_id='71000000-0000-4000-8000-000000000202',
            create_command_id=fixture['command_id'],
            series_id=old.series_id,
            series_policy_hash=old.revision_hash,
            meeting_date='2026-11-02',
            expected_baseline_ref=None,
            selection=fixture['selection'],
            template_use_hash=fixture['template_use_hash'],
        )

        assert ref.draft_id

    def _fixture(self):
        environment = DraftArchive(Path(self.temporary.name) / self._testMethodName)
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
            command_id=draft_command(6040),
            name='Daily matrix',
            document=schema2_matrix_document(),
            fill_policy=schema2_policy(),
        )
        selection = report_api.UserTemplateSelection(str(matrix.template_id), matrix.revision, matrix.revision_hash)
        continuity = report_api.ReportContinuityService(
            environment,
            StaticSourceReader(source_commit=environment.repository.head(), rule_hash=environment.stage.definition_hash),
            template_service=template_service,
            clock=FixedClock(),
        )
        series = continuity.create_series(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            command_id=draft_command(6041),
            name='Daily PM',
            calendar=review_calendar(),
            template_selection=selection,
        )
        command_id = draft_command(6042)
        command_id_2 = draft_command(6043)
        template_service.use(
            environment.actor,
            environment.project.id,
            command_id=command_id,
            draft_id=str(uuid5(UUID(environment.stage.id), f'draft:{command_id}')),
            request_hash='8' * 64,
            selection=selection,
            use_mode='continuity_prepare',
        )
        template_service.use(
            environment.actor,
            environment.project.id,
            command_id=command_id_2,
            draft_id=str(uuid5(UUID(environment.stage.id), f'draft:{command_id_2}')),
            request_hash='9' * 64,
            selection=selection,
            use_mode='continuity_prepare',
        )
        baseline = self._standalone_publication(environment)
        return {
            'continuity': continuity,
            'project_id': environment.project.id,
            'stage_id': environment.stage.id,
            'runtime': environment.repository.runtime,
            'series': series,
            'selection': draft_selection(),
            'template_selection': selection,
            'command_id': command_id,
            'command_id_2': command_id_2,
            'template_use_hash': ReportTemplateUse.objects.get(command=command_id).snapshot_hash,
            'template_use_hash_2': ReportTemplateUse.objects.get(command=command_id_2).snapshot_hash,
            'standalone_baseline_ref': baseline,
        }

    def _standalone_publication(self, environment):
        draft_service = report_api.ReportDraftService(
            environment,
            StaticSourceReader(source_commit=environment.repository.head(), rule_hash=environment.stage.definition_hash),
            report_api.ReportRenderer(),
            clock=FixedClock(),
        )
        draft = draft_service.create_authored(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            command_id=draft_command(6050),
            selection=draft_selection(),
            template=report_api.AuthoringTemplateSelection('builtin', 'daily-standup', '2', {}),
        )
        publication = draft_service.finalize_and_commit(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            draft.draft_id,
            command_id=draft_command(6051),
            expected_revision=draft.revision,
        )
        return PublicationRef(publication.manifest.publication_id, publication.manifest_sha256, publication.commit_id)

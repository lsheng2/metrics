from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID, uuid5

import pytest
from django.test import TestCase

from project_management.app.api import reports as report_api
from project_management.app.domain.capture_values import canonical_bytes, decode_json
from project_management.app.domain.contracts import ProjectActor
from project_management.app.domain.report_continuity import ReportingCalendar, build_daily_authoring_context, meeting_identity
from project_management.app.domain.report_continuity_context import validate_daily_authoring_context
from project_management.models import Project, ProjectStage
from project_management.models_report_templates import ReportTemplateUse
from project_management.tests.report_draft_fixtures import DraftArchive, FixedClock, StaticSourceReader, draft_command, draft_selection
from project_management.tests.report_draft_fixtures import valid_source_snapshot
from project_management.tests.report_render_fixtures import safe_snapshot
from project_management.tests.test_report_template_compilation import matrix_block, schema1_document


SERIES_ID = 'aaaaaaaa-aaaa-4aaa-8aaa-000000000001'


def calendar():
    return ReportingCalendar('intel-workweek', 7, 'Asia/Shanghai', 'date_map', {
        '2026-11-02': {'workweek_year': 2026, 'workweek': 45, 'weekday': 1},
    })


def valid_context():
    snapshot = valid_source_snapshot(
        safe_snapshot(days=()),
        project_id='70000000-0000-4000-8000-000000000001',
        stage_id='70000000-0000-4000-8000-000000000002',
        owner_subject='archive-owner',
        rule_hash='b' * 64,
        source_commit='a' * 40,
        capture_id='80000000-0000-4000-8000-000000000001',
    )
    return build_daily_authoring_context(
        series_id=SERIES_ID,
        series_policy_revision=1,
        series_policy_hash='1' * 64,
        meeting=meeting_identity(calendar(), '2026-11-02'),
        source_snapshot=snapshot,
        matrix_options=matrix_block()['options'],
    )


def mutate_context(mutator):
    context = decode_json(canonical_bytes(valid_context()))
    mutator(context)
    return context


@pytest.mark.parametrize('label,mutator', [
    ('row_unknown', lambda c: c['row_order'].update({'extra': True})),
    ('row_bad_visibility', lambda c: c['row_order']['rows'][0].update({'visibility': 'ghost'})),
    ('weekly_dangling_action', lambda c: c['weekly_seed'].update({'unresolved_action_ids': ['10000000-0000-4000-8000-000000000999']})),
    ('weekly_period_dict', lambda c: c['weekly_seed'].update({'earlier_period_refs': [dict(c['period'])]})),
    ('note_dangling_action', lambda c: c['notes'][0].update({'action_ids': ['10000000-0000-4000-8000-000000000999']})),
    ('action_bad_basis', lambda c: c['actions'][0].update({'basis': 'guessed'})),
    ('action_bad_state', lambda c: c['actions'][0].update({'tracking_state': 'fixed'})),
    ('observation_bad_state', lambda c: c['current_observations'][0].update({'source_state': 'same'})),
    ('summary_bad_hash', lambda c: c['current_observations'][0]['accepted_summary_ref'].update({'result_hash': 'not-a-hash'})),
    ('bad_publication_ref', lambda c: c.update({'base_daily_publication': {'publication_id': 'x'}})),
    ('selected_daily_publications', lambda c: c.update({'selected_daily_publications': [{'publication_id': 'x'}]})),
    ('persistent_unknown', lambda c: c.update({'persistent_notes': [{'note_id': '10000000-0000-4000-8000-000000000001'}]})),
    ('bad_meeting_type', lambda c: c['meeting'].update({'weekday': '1'})),
])
def test_should_reject_bad_nested_context_records(label, mutator):
    with pytest.raises(report_api.ReportError):
        validate_daily_authoring_context(mutate_context(mutator), series_id=SERIES_ID, meeting=meeting_identity(calendar(), '2026-11-02'))


class TestPreparedSeedValidationFix2(TestCase):
    def setUp(self):
        self.actor = ProjectActor('archive-owner')
        self.temporary = TemporaryDirectory(prefix='history-core-fix2-', dir=Path.cwd() / 'tmp_ui_validation')
        self.addCleanup(self.temporary.cleanup)

    def test_should_reject_existing_seed_with_context_meeting_mismatch_or_unknown_keys(self):
        fixture = self._fixture()
        ref = fixture['continuity'].prepare_context(
            self.actor, fixture['project_id'], fixture['stage_id'],
            preparation_id='71000000-0000-4000-8000-000000000300',
            create_command_id=fixture['command_id'], series_id=fixture['series'].series_id,
            series_policy_hash=fixture['series'].revision_hash, meeting_date='2026-11-02',
            expected_baseline_ref=None, selection=fixture['selection'],
            template_use_hash=fixture['template_use_hash'],
        )
        path = fixture['runtime'] / 'report-preparations' / ref.preparation_id / 'context.json'
        seed = decode_json(path.read_bytes())
        broken = deepcopy(seed)
        broken['context']['meeting']['local_date'] = '2026-11-03'
        broken['context_hash'] = self._hash(broken['context'])
        path.write_bytes(canonical_bytes(broken))

        with pytest.raises(report_api.ReportError) as mismatch:
            fixture['continuity'].prepare_context(
                self.actor, fixture['project_id'], fixture['stage_id'],
                preparation_id=ref.preparation_id, create_command_id=fixture['command_id'],
                series_id=fixture['series'].series_id, series_policy_hash=fixture['series'].revision_hash,
                meeting_date='2026-11-02', expected_baseline_ref=None, selection=fixture['selection'],
                template_use_hash=fixture['template_use_hash'],
            )

        unknown = deepcopy(seed)
        unknown['context']['weekly_seed']['extra'] = True
        unknown['context_hash'] = self._hash(unknown['context'])
        path.write_bytes(canonical_bytes(unknown))
        with pytest.raises(report_api.ReportError) as extra:
            fixture['continuity'].prepare_context(
                self.actor, fixture['project_id'], fixture['stage_id'],
                preparation_id=ref.preparation_id, create_command_id=fixture['command_id'],
                series_id=fixture['series'].series_id, series_policy_hash=fixture['series'].revision_hash,
                meeting_date='2026-11-02', expected_baseline_ref=None, selection=fixture['selection'],
                template_use_hash=fixture['template_use_hash'],
            )

        assert mismatch.value.code == 'REPORT_ARTIFACT_INVALID'
        assert extra.value.code == 'REPORT_ARTIFACT_INVALID'

    def _fixture(self):
        environment = DraftArchive(Path(self.temporary.name) / self._testMethodName)
        Project.objects.create(id=environment.project.id, owner_subject=environment.actor.subject, key='alpha', name='Alpha')
        ProjectStage.objects.create(id=environment.stage.id, project_id=environment.project.id, key='release-1',
                                    name='Release 1', selection_json={}, descriptor_json={},
                                    definition_hash=environment.stage.definition_hash)
        template_service = report_api.ReportTemplateService(clock=FixedClock())
        document = dict(schema1_document())
        document['schema_version'] = 2
        document['blocks'] = [*document['blocks'], matrix_block()]
        matrix = template_service.create(environment.actor, environment.project.id, command_id=draft_command(6070),
                                         name='Daily matrix', document=document,
                                         fill_policy={'schema_version': 2, 'instructions': {}, 'daily_note_instructions': None})
        template_selection = report_api.UserTemplateSelection(str(matrix.template_id), matrix.revision, matrix.revision_hash)
        continuity = report_api.ReportContinuityService(
            environment, StaticSourceReader(source_commit=environment.repository.head(), rule_hash=environment.stage.definition_hash),
            template_service=template_service, clock=FixedClock(),
        )
        series = continuity.create_series(environment.actor, environment.project.id, environment.stage.id,
                                          command_id=draft_command(6071), name='Daily PM',
                                          calendar=calendar(), template_selection=template_selection)
        command_id = draft_command(6072)
        template_service.use(environment.actor, environment.project.id, command_id=command_id,
                             draft_id=str(uuid5(UUID(environment.stage.id), f'draft:{command_id}')),
                             request_hash='a' * 64, selection=template_selection, use_mode='continuity_prepare')
        return {
            'continuity': continuity, 'project_id': environment.project.id, 'stage_id': environment.stage.id,
            'runtime': environment.repository.runtime, 'series': series, 'selection': draft_selection(),
            'command_id': command_id, 'template_use_hash': ReportTemplateUse.objects.get(command=command_id).snapshot_hash,
        }

    def _hash(self, value):
        from project_management.app.domain.capture_values import sha256_bytes

        return sha256_bytes(canonical_bytes(value))

import pytest

from project_management.app.api import reports as report_api
from project_management.app.domain.capture_values import decode_json
from project_management.app.domain.contracts import ProjectActor
from project_management.app.domain.run_values import draft_command_id as run_draft_command_id
from project_management.app.domain.run_values import operation_id as run_operation_id
import project_management.services.report_preparation as preparation_module
from project_management.models import Project, ProjectStage
from project_management.tests.history_persistence_fixtures import calendar, continuity_document, history_fixture
from project_management.tests.history_persistence_fixtures import daily_note_edit
from project_management.tests.report_draft_fixtures import draft_command


def preparation_service(fixture):
    return report_api.ReportPreparationService(
        fixture.continuity,
        fixture.draft_service,
        fixture.template_service,
    )


def prepare_request(fixture, command, day, capture, gaps=()):
    return {
        'command_id': draft_command(command),
        'series_id': fixture.series.series_id,
        'meeting_date': day,
        'expected_series_policy_hash': fixture.series.revision_hash,
        'expected_baseline_ref': None,
        'template_selection': fixture.template_selection,
        'source_mode': 'saved_capture',
        'capture_id': capture,
        'analysis_mode': 'manual_only',
        'acknowledge_gap_draft_ids': gaps,
    }


@pytest.mark.django_db(transaction=True)
def test_should_create_saved_capture_manual_draft_and_return_existing_slot_without_worker(tmp_path):
    fixture = history_fixture(tmp_path)
    service = preparation_service(fixture)
    request = prepare_request(fixture, 9001, '2026-11-02', '72000000-0000-4000-8000-000000000901')

    preview = fixture.continuity.preview(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        series_id=fixture.series.series_id,
        meeting_date='2026-11-02',
        template_selection=fixture.template_selection,
    )
    result = service.prepare(fixture.actor, fixture.project.id, fixture.stage.id, **request)
    calls_after_create = fixture.source_reader.calls
    second = service.prepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        **prepare_request(fixture, 9002, '2026-11-02', '72000000-0000-4000-8000-000000000902'),
    )
    draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, result.draft_id)

    assert preview.state == 'initial'
    assert preview.baseline_ref is None
    assert result.disposition == 'created'
    assert result.operation_id is None
    assert result.draft_revision == 1
    assert draft.authoring_context['meeting']['local_date'] == '2026-11-02'
    assert second.disposition == 'existing'
    assert second.draft_id == result.draft_id
    assert second.effective_selection == result.effective_selection
    assert second.selection_conflicts == ('source',)
    assert fixture.source_reader.calls == calls_after_create


@pytest.mark.django_db(transaction=True)
def test_should_reject_same_command_changed_payload_without_new_draft(tmp_path):
    fixture = history_fixture(tmp_path)
    service = preparation_service(fixture)
    request = prepare_request(fixture, 9010, '2026-11-02', '72000000-0000-4000-8000-000000000910')
    result = service.prepare(fixture.actor, fixture.project.id, fixture.stage.id, **request)

    with pytest.raises(report_api.ReportError) as changed:
        service.prepare(
            fixture.actor,
            fixture.project.id,
            fixture.stage.id,
            **prepare_request(fixture, 9010, '2026-11-02', '72000000-0000-4000-8000-000000000911'),
        )

    draft_root = fixture.archive_root / 'projects' / fixture.project.id / 'stages' / fixture.stage.id / 'runtime' / 'report-drafts'
    assert changed.value.code == 'REPORT_PREPARATION_COMMAND_CONFLICT'
    assert tuple(draft_root.iterdir()) == (draft_root / result.draft_id,)


@pytest.mark.django_db(transaction=True)
def test_should_resume_original_intent_after_seed_written_without_draft(tmp_path):
    fixture = history_fixture(tmp_path)
    service = preparation_service(fixture)
    original_create = fixture.draft_service.create_authored
    first_request = prepare_request(fixture, 9015, '2026-11-02', '72000000-0000-4000-8000-000000000915')
    failed = {'raised': False}

    def fail_once(*args, **kwargs):
        if not failed['raised']:
            failed['raised'] = True
            raise report_api.ReportError('REPORT_SOURCE_CHANGED')
        return original_create(*args, **kwargs)

    fixture.draft_service.create_authored = fail_once
    with pytest.raises(report_api.ReportError):
        service.prepare(fixture.actor, fixture.project.id, fixture.stage.id, **first_request)

    result = service.prepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        **prepare_request(fixture, 9016, '2026-11-02', '72000000-0000-4000-8000-000000000916'),
    )
    draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, result.draft_id)

    assert result.disposition == 'existing'
    assert result.effective_selection['capture_id'] == first_request['capture_id']
    assert result.selection_conflicts == ('source',)
    assert draft.selection.capture_id == first_request['capture_id']


@pytest.mark.django_db(transaction=True)
def test_should_require_exact_pending_gap_acknowledgment_and_freeze_it_in_context(tmp_path):
    fixture = history_fixture(tmp_path)
    service = preparation_service(fixture)
    day1 = service.prepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        **prepare_request(fixture, 9020, '2026-11-02', '72000000-0000-4000-8000-000000000920'),
    )
    preview = fixture.continuity.preview(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        series_id=fixture.series.series_id,
        meeting_date='2026-11-03',
        template_selection=fixture.template_selection,
    )

    with pytest.raises(report_api.ReportError) as pending:
        service.prepare(
            fixture.actor,
            fixture.project.id,
            fixture.stage.id,
            **prepare_request(fixture, 9021, '2026-11-03', '72000000-0000-4000-8000-000000000921'),
        )
    day2 = service.prepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        **prepare_request(
            fixture,
            9022,
            '2026-11-03',
            '72000000-0000-4000-8000-000000000922',
            gaps=(day1.draft_id,),
        ),
    )
    seed = decode_json(
        (
            fixture.archive_root
            / 'projects'
            / fixture.project.id
            / 'stages'
            / fixture.stage.id
            / 'runtime'
            / 'report-preparations'
            / day2.preparation_id
            / 'context.json'
        ).read_bytes()
    )

    assert preview.state == 'pending'
    assert preview.pending_gap_draft_ids == (day1.draft_id,)
    assert pending.value.code == 'REPORT_BASELINE_PENDING'
    assert seed['context']['acknowledged_gap_draft_ids'] == [day1.draft_id]


@pytest.mark.django_db(transaction=True)
def test_should_keep_saved_draft_out_of_baseline_until_finalize_confirms_publication(tmp_path):
    fixture = history_fixture(tmp_path)
    service = preparation_service(fixture)
    day1 = service.prepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        **prepare_request(fixture, 9030, '2026-11-02', '72000000-0000-4000-8000-000000000930'),
    )
    draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, day1.draft_id)
    note_id = draft.authoring_context['current_observations'][0]['note_id']
    existing = next(note for note in draft.authoring_context['notes'] if note['note_id'] == note_id)
    saved = fixture.draft_service.save_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        draft.draft_id,
        command_id=draft_command(9031),
        expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        edits=(daily_note_edit(9031, note_id, 'Saved but not final.', '#ee0000', existing['body_hash']),),
    )
    saved_preview = fixture.continuity.preview(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        series_id=fixture.series.series_id,
        meeting_date='2026-11-03',
        template_selection=fixture.template_selection,
    )
    publication = fixture.draft_service.finalize_and_commit(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        saved.draft_id,
        command_id=draft_command(9032),
        expected_revision=saved.revision,
    )
    finalized_preview = fixture.continuity.preview(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        series_id=fixture.series.series_id,
        meeting_date='2026-11-03',
        template_selection=fixture.template_selection,
    )

    assert saved_preview.state == 'pending'
    assert saved_preview.baseline_ref is None
    assert finalized_preview.state == 'ready'
    assert finalized_preview.baseline_ref.publication_id == publication.manifest.publication_id


@pytest.mark.django_db(transaction=True)
def test_should_replay_same_command_after_finalize_policy_save_and_template_archive(tmp_path):
    fixture = history_fixture(tmp_path)
    service = preparation_service(fixture)
    request = prepare_request(fixture, 9040, '2026-11-02', '72000000-0000-4000-8000-000000000940')
    result = service.prepare(fixture.actor, fixture.project.id, fixture.stage.id, **request)
    draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, result.draft_id)
    publication = fixture.draft_service.finalize_and_commit(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        draft.draft_id,
        command_id=draft_command(9041),
        expected_revision=draft.revision,
    )
    replacement = fixture.template_service.create(
        fixture.actor,
        fixture.project.id,
        command_id=draft_command(9042),
        name='Replacement matrix',
        document=continuity_document(),
        fill_policy={'schema_version': 2, 'instructions': {}, 'daily_note_instructions': None},
    )
    replacement_selection = report_api.UserTemplateSelection(
        str(replacement.template_id), replacement.revision, replacement.revision_hash,
    )
    saved_policy = fixture.continuity.save_series_policy(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9043),
        series_id=fixture.series.series_id,
        expected_revision=fixture.series.revision,
        expected_revision_hash=fixture.series.revision_hash,
        name='Daily PM v2',
        calendar=calendar(),
        template_selection=replacement_selection,
    )
    fixture.template_service.archive(
        fixture.actor,
        fixture.project.id,
        fixture.template_selection.template_id,
        command_id=draft_command(9044),
        expected_revision=fixture.template_selection.revision,
        expected_revision_hash=fixture.template_selection.revision_hash,
    )

    replay = service.prepare(fixture.actor, fixture.project.id, fixture.stage.id, **request)
    other = prepare_request(fixture, 9045, '2026-11-02', '72000000-0000-4000-8000-000000000945')
    other['expected_series_policy_hash'] = saved_policy.revision_hash
    other['template_selection'] = replacement_selection
    existing = service.prepare(fixture.actor, fixture.project.id, fixture.stage.id, **other)

    assert replay.disposition == 'created'
    assert replay.state == 'finalized'
    assert replay.publication_ref.publication_id == publication.manifest.publication_id
    assert replay.links['draft'] == f"/projects/{fixture.project.id}/stages/{fixture.stage.id}/reports/drafts/{draft.draft_id}/"
    assert replay.links['publication'] == f"/projects/{fixture.project.id}/stages/{fixture.stage.id}/reports/publications/{publication.manifest.publication_id}/"
    assert existing.disposition == 'existing'
    assert existing.state == 'finalized'
    assert existing.publication_ref.publication_id == publication.manifest.publication_id
    assert existing.selection_conflicts == ('template', 'source', 'calendar')


@pytest.mark.django_db(transaction=True)
def test_should_keep_same_local_date_slot_after_calendar_revision_changes(tmp_path):
    fixture = history_fixture(tmp_path)
    service = preparation_service(fixture)
    first = service.prepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        **prepare_request(fixture, 9050, '2026-11-02', '72000000-0000-4000-8000-000000000950'),
    )
    changed_calendar = report_api.ReportingCalendar(
        'intel-workweek',
        8,
        'Asia/Shanghai',
        'date_map',
        {'2026-11-02': {'workweek_year': 2026, 'workweek': 45, 'weekday': 1}},
    )
    saved = fixture.continuity.save_series_policy(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9051),
        series_id=fixture.series.series_id,
        expected_revision=fixture.series.revision,
        expected_revision_hash=fixture.series.revision_hash,
        name='Daily PM calendar rev',
        calendar=changed_calendar,
        template_selection=fixture.template_selection,
    )
    request = prepare_request(fixture, 9052, '2026-11-02', '72000000-0000-4000-8000-000000000952')
    request['expected_series_policy_hash'] = saved.revision_hash

    second = service.prepare(fixture.actor, fixture.project.id, fixture.stage.id, **request)

    assert second.disposition == 'existing'
    assert second.draft_id == first.draft_id
    assert second.selection_conflicts == ('source', 'calendar')


@pytest.mark.django_db(transaction=True)
def test_should_store_worker_compatible_operation_and_draft_command_ids(tmp_path):
    fixture = history_fixture(tmp_path)
    service = preparation_service(fixture)
    result = service.prepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        **prepare_request(fixture, 9060, '2026-11-02', '72000000-0000-4000-8000-000000000960'),
    )
    intent = decode_json(
        (
            fixture.archive_root
            / 'projects'
            / fixture.project.id
            / 'stages'
            / fixture.stage.id
            / 'runtime'
            / 'report-preparations'
            / result.preparation_id
            / 'intent.json'
        ).read_bytes()
    )

    assert intent['derived_operation_id'] == run_operation_id(fixture.stage.id, intent['operation_command_id'])
    assert intent['draft_command_id'] == run_draft_command_id(intent['derived_operation_id'])


@pytest.mark.django_db(transaction=True)
def test_should_recheck_pending_gap_under_writer_before_new_reservation(tmp_path, monkeypatch):
    fixture = history_fixture(tmp_path)
    service = preparation_service(fixture)
    preview = fixture.continuity.preview(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        series_id=fixture.series.series_id,
        meeting_date='2026-11-02',
        template_selection=fixture.template_selection,
    )
    pending_draft_id = '71000000-0000-4000-8000-000000009999'

    def stale_preview(*args, **kwargs):
        return report_api.BaselinePreview(
            'pending',
            preview.series_id,
            preview.series_policy_hash,
            preview.meeting_key,
            preview.period_key,
            preview.baseline_ref,
            (pending_draft_id,),
            preview.template_choices,
            preview.source_choices,
            preview.analysis_choices,
        )

    monkeypatch.setattr(preparation_module, 'build_baseline_preview_from_repository', stale_preview)

    with pytest.raises(report_api.ReportError) as error:
        service.prepare(
            fixture.actor,
            fixture.project.id,
            fixture.stage.id,
            **prepare_request(fixture, 9070, '2026-11-02', '72000000-0000-4000-8000-000000000970'),
        )

    assert error.value.code == 'REPORT_BASELINE_PENDING'
    assert not (fixture.archive_root / 'projects' / fixture.project.id / 'stages' / fixture.stage.id / 'runtime' / 'report-preparations').exists()


@pytest.mark.django_db(transaction=True)
def test_should_reject_unsupported_source_mode_without_marking_existing_slot(tmp_path):
    fixture = history_fixture(tmp_path)
    service = preparation_service(fixture)
    service.prepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        **prepare_request(fixture, 9080, '2026-11-02', '72000000-0000-4000-8000-000000000980'),
    )
    command_root = (
        fixture.archive_root
        / 'projects'
        / fixture.project.id
        / 'stages'
        / fixture.stage.id
        / 'runtime'
        / 'report-preparation-commands'
    )
    before = tuple(sorted(path.name for path in command_root.iterdir()))
    request = prepare_request(fixture, 9081, '2026-11-02', '72000000-0000-4000-8000-000000000981')
    request['source_mode'] = 'refresh'

    with pytest.raises(report_api.ReportError) as error:
        service.prepare(fixture.actor, fixture.project.id, fixture.stage.id, **request)

    assert error.value.code == 'REPORT_INVALID'
    assert tuple(sorted(path.name for path in command_root.iterdir())) == before


@pytest.mark.django_db(transaction=True)
def test_should_validate_saved_capture_source_before_reserving_new_slot(tmp_path):
    fixture = history_fixture(tmp_path)
    service = preparation_service(fixture)
    original_reader = fixture.source_reader
    missing_capture = '72000000-0000-4000-8000-000000000990'

    class CaptureCheckingReader:
        def __init__(self):
            self.calls = []

        def read(self, actor, project_id, stage_id, selection):
            self.calls.append(selection.capture_id)
            if selection.capture_id == missing_capture:
                raise report_api.ReportError('REPORT_NOT_FOUND')
            return original_reader.read(actor, project_id, stage_id, selection)

    reader = CaptureCheckingReader()
    fixture.draft_service.source_reader = reader
    fixture.continuity.source_reader = reader
    bad = prepare_request(fixture, 9085, '2026-11-02', missing_capture)

    with pytest.raises(report_api.ReportError) as error:
        service.prepare(fixture.actor, fixture.project.id, fixture.stage.id, **bad)

    runtime = fixture.archive_root / 'projects' / fixture.project.id / 'stages' / fixture.stage.id / 'runtime'
    good = service.prepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        **prepare_request(fixture, 9086, '2026-11-02', '72000000-0000-4000-8000-000000000986'),
    )

    assert error.value.code == 'REPORT_NOT_FOUND'
    assert not (runtime / 'report-preparation-commands' / f"{bad['command_id']}.json").exists()
    assert good.disposition == 'created'
    assert good.effective_selection['capture_id'] == '72000000-0000-4000-8000-000000000986'


@pytest.mark.django_db(transaction=True)
def test_should_preview_initial_without_archive_runtime_writes(tmp_path):
    actor = ProjectActor('archive-owner')
    project = Project.objects.create(owner_subject=actor.subject, key='alpha', name='Alpha')
    stage = ProjectStage.objects.create(
        project=project,
        key='release-1',
        name='Release 1',
        selection_json={'profile_id': 'alpha-jira', 'revision': 1},
        descriptor_json={'provider_id': 'jira'},
        definition_hash='b' * 64,
    )
    template_service = report_api.ReportTemplateService()
    template = template_service.create(
        actor,
        project.id,
        command_id=draft_command(9090),
        name='Daily matrix',
        document=continuity_document(),
        fill_policy={'schema_version': 2, 'instructions': {}, 'daily_note_instructions': None},
    )
    selection = report_api.UserTemplateSelection(str(template.template_id), template.revision, template.revision_hash)
    continuity = report_api.ReportContinuityService(template_service=template_service)
    series = continuity.create_series(
        actor,
        project.id,
        stage.id,
        command_id=draft_command(9091),
        name='Daily PM',
        calendar=calendar(),
        template_selection=selection,
    )

    preview = continuity.preview(
        actor,
        project.id,
        stage.id,
        series_id=series.series_id,
        meeting_date='2026-11-02',
        template_selection=selection,
    )

    assert preview.state == 'initial'
    assert preview.baseline_ref is None
    assert preview.pending_gap_draft_ids == ()
    assert tuple(tmp_path.iterdir()) == ()

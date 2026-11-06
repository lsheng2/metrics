from dataclasses import replace

import pytest

from project_management.app.api import reports as report_api
from project_management.app.domain.capture_values import decode_json
from project_management.app.api.project_runs import ProjectRunService, ProjectRunWorker
from project_management.out.ai_task_contract import AiTaskContract
from project_management.services.capture import ProjectCaptureService
from project_management.services.report_sources import ReportSourceReader
from project_management.tests.history_persistence_fixtures import daily_note_edit, history_fixture, note_by_id
from project_management.tests.project_run_fixtures import ProviderAccessDouble
from project_management.tests.report_draft_fixtures import draft_command
from project_management.tests.summary_fixtures import PACK_ROOT


def refresh_manual_service(fixture, provider_items):
    source_reader = ReportSourceReader(fixture.archive, AiTaskContract.load(PACK_ROOT))
    fixture.continuity.source_reader = source_reader
    fixture.draft_service.source_reader = source_reader
    provider = ProviderAccessDouble(fixture.stage, tuple(provider_items))
    run_service = ProjectRunService(
        fixture.archive.project_api,
        fixture.archive,
        ProjectCaptureService(
            fixture.archive.project_api,
            provider,
            fixture.archive,
            required_parts=('facts', 'comments', 'history'),
        ),
        object(),
        fixture.draft_service,
        lambda *args: None,
        notifier=lambda *args: None,
    )
    service = report_api.ReportPreparationService(
        fixture.continuity,
        fixture.draft_service,
        fixture.template_service,
        run_service=run_service,
    )
    return service, run_service


def prepare_refresh_manual(fixture, service, command):
    return service.prepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(command),
        series_id=fixture.series.series_id,
        meeting_date='2026-11-02',
        expected_series_policy_hash=fixture.series.revision_hash,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='refresh',
        capture_id=None,
        analysis_mode='manual_only',
        acknowledge_gap_draft_ids=(),
    )


@pytest.mark.django_db(transaction=True)
def test_should_reprepare_terminal_unfinalized_manual_draft_into_saved_capture_candidate_preserving_human_note(tmp_path):
    fixture = history_fixture(tmp_path)
    service, run_service = refresh_manual_service(fixture, ({
        'stable_id': 'ALPHA-1',
        'summary': 'Intermittent validation failure',
        'status': 'Fixed',
        'comments': {'201': {'id': '201', 'body': 'Failure observed.'}},
    },))
    prepared = prepare_refresh_manual(fixture, service, 9200)
    completed = ProjectRunWorker(run_service, daily_preparation_service=service).execute(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        prepared.operation_id,
    )
    draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, completed.draft_id)
    note_id = draft.authoring_context['current_observations'][0]['note_id']
    saved = fixture.draft_service.save_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        draft.draft_id,
        command_id=draft_command(9201),
        expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        edits=(daily_note_edit(9201, note_id, 'Keep the green human note.', '#00aa00', None),),
    )

    replacement = service.reprepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9202),
        preparation_id=prepared.preparation_id,
        expected_operation_revision=completed.revision,
        expected_draft_revision=saved.revision,
        expected_draft_revision_hash=saved.revision_hash,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='saved_capture',
        capture_id=completed.capture_id,
        analysis_mode='manual_only',
    )
    current = service.prepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9203),
        series_id=fixture.series.series_id,
        meeting_date='2026-11-02',
        expected_series_policy_hash=fixture.series.revision_hash,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='saved_capture',
        capture_id='72000000-0000-4000-8000-000000009203',
        analysis_mode='manual_only',
        acknowledge_gap_draft_ids=(),
    )
    old_note = note_by_id(
        fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, saved.draft_id).authoring_context,
        note_id,
    )
    new_draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, replacement.draft_id)
    new_note = note_by_id(new_draft.authoring_context, note_id)

    assert completed.state == 'partial'
    assert replacement.preparation_id != prepared.preparation_id
    assert replacement.operation_id is None
    assert replacement.draft_id != saved.draft_id
    assert replacement.draft_revision == 1
    assert current.draft_id == replacement.draft_id
    assert old_note['body_fragment']['blocks'][0]['content'][0]['text'] == 'Keep the green human note.'
    assert new_note['body_fragment']['blocks'][0]['content'][0]['text'] == 'Keep the green human note.'
    assert new_note['body_fragment']['blocks'][0]['content'][0]['foreground'] == '#00aa00'


@pytest.mark.django_db(transaction=True)
def test_should_keep_original_prepare_replay_readable_after_terminal_reprepare_without_reclaiming_active_slot(tmp_path):
    fixture = history_fixture(tmp_path)
    service, run_service = refresh_manual_service(fixture, ({
        'stable_id': 'ALPHA-1',
        'summary': 'Intermittent validation failure',
        'status': 'Fixed',
        'comments': {'201': {'id': '201', 'body': 'Failure observed.'}},
    },))
    prepared = prepare_refresh_manual(fixture, service, 9210)
    completed = ProjectRunWorker(run_service, daily_preparation_service=service).execute(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        prepared.operation_id,
    )
    draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, completed.draft_id)
    note_id = draft.authoring_context['current_observations'][0]['note_id']
    saved = fixture.draft_service.save_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        draft.draft_id,
        command_id=draft_command(9211),
        expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        edits=(daily_note_edit(9211, note_id, 'Keep replay isolated.', '#00aa00', None),),
    )
    replacement = service.reprepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9212),
        preparation_id=prepared.preparation_id,
        expected_operation_revision=completed.revision,
        expected_draft_revision=saved.revision,
        expected_draft_revision_hash=saved.revision_hash,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='saved_capture',
        capture_id=completed.capture_id,
        analysis_mode='manual_only',
    )

    replay = prepare_refresh_manual(fixture, service, 9210)
    current = service.prepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9213),
        series_id=fixture.series.series_id,
        meeting_date='2026-11-02',
        expected_series_policy_hash=fixture.series.revision_hash,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='saved_capture',
        capture_id=completed.capture_id,
        analysis_mode='manual_only',
        acknowledge_gap_draft_ids=(),
    )

    assert replay.preparation_id == prepared.preparation_id
    assert replay.operation_id == prepared.operation_id
    assert current.preparation_id == replacement.preparation_id
    assert current.draft_id == replacement.draft_id


@pytest.mark.django_db(transaction=True)
def test_should_refuse_stale_terminal_reprepare_before_command_or_slot_transition(tmp_path):
    fixture = history_fixture(tmp_path)
    service, run_service = refresh_manual_service(fixture, ({
        'stable_id': 'ALPHA-1',
        'summary': 'Intermittent validation failure',
        'status': 'Fixed',
        'comments': {'201': {'id': '201', 'body': 'Failure observed.'}},
    },))
    prepared = prepare_refresh_manual(fixture, service, 9220)
    completed = ProjectRunWorker(run_service, daily_preparation_service=service).execute(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        prepared.operation_id,
    )
    draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, completed.draft_id)
    runtime = fixture.archive_root / 'projects' / fixture.project.id / 'stages' / fixture.stage.id / 'runtime'
    slot_id = decode_json((runtime / 'report-preparations' / prepared.preparation_id / 'intent.json').read_bytes())['slot_id']
    original_slot = (runtime / 'report-preparation-slots' / f'{slot_id}.json').read_bytes()
    command_id = draft_command(9222)

    with pytest.raises(report_api.ReportError) as error:
        service.reprepare(
            fixture.actor,
            fixture.project.id,
            fixture.stage.id,
            command_id=command_id,
            preparation_id=prepared.preparation_id,
            expected_operation_revision=completed.revision,
            expected_draft_revision=draft.revision + 1,
            expected_draft_revision_hash=draft.revision_hash,
            expected_baseline_ref=None,
            template_selection=fixture.template_selection,
            source_mode='saved_capture',
            capture_id=completed.capture_id,
            analysis_mode='manual_only',
        )

    assert error.value.code == 'REPORT_REVISION_CONFLICT'
    assert not (runtime / 'report-preparation-commands' / f'{command_id}.json').exists()
    assert (runtime / 'report-preparation-slots' / f'{slot_id}.json').read_bytes() == original_slot


@pytest.mark.django_db(transaction=True)
def test_should_reprepare_failed_original_with_null_draft_expectations_as_new_refresh_operation(tmp_path):
    fixture = history_fixture(tmp_path)
    service, run_service = refresh_manual_service(fixture, ())
    prepared = prepare_refresh_manual(fixture, service, 9230)
    failed = run_service.transition(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        prepared.operation_id,
        lambda current: replace(
            current,
            state='failed',
            revision=current.revision + 1,
            error_code='RUN_STORAGE_INVALID',
        ),
    )

    replacement = service.reprepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9231),
        preparation_id=prepared.preparation_id,
        expected_operation_revision=failed.revision,
        expected_draft_revision=None,
        expected_draft_revision_hash=None,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='refresh',
        capture_id=None,
        analysis_mode='manual_only',
    )
    retry = service.reprepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9231),
        preparation_id=prepared.preparation_id,
        expected_operation_revision=failed.revision,
        expected_draft_revision=None,
        expected_draft_revision_hash=None,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='refresh',
        capture_id=None,
        analysis_mode='manual_only',
    )
    replay = prepare_refresh_manual(fixture, service, 9230)

    assert replacement.preparation_id != prepared.preparation_id
    assert replacement.operation_id is not None
    assert replacement.operation_id != prepared.operation_id
    assert replacement.draft_id is not None
    assert replacement.draft_revision is None
    assert replacement.state == 'queued'
    assert retry.preparation_id == replacement.preparation_id
    assert retry.operation_id == replacement.operation_id
    assert retry.draft_id == replacement.draft_id
    assert replay.preparation_id == prepared.preparation_id
    assert replay.state == 'failed'


@pytest.mark.django_db(transaction=True)
def test_should_reprepare_canceled_original_with_null_draft_expectations_as_new_refresh_operation(tmp_path):
    fixture = history_fixture(tmp_path)
    service, run_service = refresh_manual_service(fixture, ())
    prepared = prepare_refresh_manual(fixture, service, 9240)
    canceled = run_service.cancel(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        prepared.operation_id,
        expected_revision=1,
    )

    replacement = service.reprepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9241),
        preparation_id=prepared.preparation_id,
        expected_operation_revision=canceled.revision,
        expected_draft_revision=None,
        expected_draft_revision_hash=None,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='refresh',
        capture_id=None,
        analysis_mode='manual_only',
    )
    replay = prepare_refresh_manual(fixture, service, 9240)

    assert canceled.state == 'canceled'
    assert replacement.preparation_id != prepared.preparation_id
    assert replacement.operation_id is not None
    assert replacement.operation_id != prepared.operation_id
    assert replacement.draft_revision is None
    assert replacement.state == 'queued'
    assert replay.preparation_id == prepared.preparation_id
    assert replay.state == 'canceled'

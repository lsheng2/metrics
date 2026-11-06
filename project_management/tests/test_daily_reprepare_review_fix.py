from dataclasses import replace
import uuid

import pytest

from project_management.app.api import reports as report_api
from project_management.app.api.project_runs import ProjectRunService, ProjectRunWorker
from project_management.app.domain.capture_values import canonical_bytes, decode_json
from project_management.app.domain.run_contracts import RunRequest
from project_management.out.ai_task_contract import AiTaskContract
from project_management.services.capture import ProjectCaptureService
import project_management.services.report_preparation_worker as worker_module
from project_management.services.report_reprepare_parent_cas import verify_parent_cas
from project_management.services.report_sources import ReportSourceReader
from project_management.storage.report_preparations import ReportPreparationStore
from project_management.tests.history_persistence_fixtures import (
    daily_note_edit,
    history_fixture,
    note_by_id,
    publication_ids,
)
from project_management.tests.project_run_fixtures import ProviderAccessDouble
from project_management.tests.project_run_fixtures import ManualRunEnvironment
from project_management.tests.report_draft_fixtures import draft_command
from project_management.tests.report_render_fixtures import daily_template
from project_management.tests.summary_fixtures import PACK_ROOT


def _refresh_parent_service(fixture, provider_items):
    source_reader = ReportSourceReader(fixture.archive, AiTaskContract.load(PACK_ROOT))
    fixture.continuity.source_reader = source_reader
    fixture.draft_service.source_reader = source_reader
    run_service = ProjectRunService(
        fixture.archive.project_api,
        fixture.archive,
        ProjectCaptureService(
            fixture.archive.project_api,
            ProviderAccessDouble(fixture.stage, tuple(provider_items)),
            fixture.archive,
            required_parts=('facts', 'comments', 'history'),
        ),
        object(),
        fixture.draft_service,
        lambda *args: None,
        notifier=lambda *args: None,
    )
    return report_api.ReportPreparationService(
        fixture.continuity,
        fixture.draft_service,
        fixture.template_service,
        run_service=run_service,
    ), run_service


def _prepare_refresh(fixture, service, command):
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
def test_should_reprepare_saved_capture_parent_without_operation_or_run_service(tmp_path):
    fixture = history_fixture(tmp_path)
    service = report_api.ReportPreparationService(
        fixture.continuity,
        fixture.draft_service,
        fixture.template_service,
    )
    parent = service.prepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9250),
        series_id=fixture.series.series_id,
        meeting_date='2026-11-02',
        expected_series_policy_hash=fixture.series.revision_hash,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='saved_capture',
        capture_id='72000000-0000-4000-8000-000000009250',
        analysis_mode='manual_only',
        acknowledge_gap_draft_ids=(),
    )
    parent_draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, parent.draft_id)

    replacement = service.reprepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9251),
        preparation_id=parent.preparation_id,
        expected_operation_revision=None,
        expected_draft_revision=parent_draft.revision,
        expected_draft_revision_hash=parent_draft.revision_hash,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='saved_capture',
        capture_id='72000000-0000-4000-8000-000000009251',
        analysis_mode='manual_only',
    )
    replacement_intent = decode_json((
        fixture.archive_root / 'projects' / fixture.project.id / 'stages' / fixture.stage.id
        / 'runtime' / 'report-preparations' / replacement.preparation_id / 'intent.json'
    ).read_bytes())

    assert parent.operation_id is None
    assert replacement.operation_id is None
    assert replacement.preparation_id != parent.preparation_id
    assert replacement.draft_id != parent.draft_id
    assert replacement.draft_revision == 1
    assert replacement_intent['stage_hash'] == fixture.stage.definition_hash


@pytest.mark.django_db(transaction=True)
def test_should_replay_reprepare_command_before_parent_draft_drift_checks(tmp_path):
    fixture = history_fixture(tmp_path)
    service = report_api.ReportPreparationService(
        fixture.continuity,
        fixture.draft_service,
        fixture.template_service,
    )
    parent = service.prepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9260),
        series_id=fixture.series.series_id,
        meeting_date='2026-11-02',
        expected_series_policy_hash=fixture.series.revision_hash,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='saved_capture',
        capture_id='72000000-0000-4000-8000-000000009260',
        analysis_mode='manual_only',
        acknowledge_gap_draft_ids=(),
    )
    parent_draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, parent.draft_id)
    replacement = service.reprepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9261),
        preparation_id=parent.preparation_id,
        expected_operation_revision=None,
        expected_draft_revision=parent_draft.revision,
        expected_draft_revision_hash=parent_draft.revision_hash,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='saved_capture',
        capture_id='72000000-0000-4000-8000-000000009261',
        analysis_mode='manual_only',
    )
    note_id = parent_draft.authoring_context['current_observations'][0]['note_id']
    existing = note_by_id(parent_draft.authoring_context, note_id)
    fixture.draft_service.save_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        parent.draft_id,
        command_id=draft_command(9262),
        expected_revision=parent_draft.revision,
        expected_revision_hash=parent_draft.revision_hash,
        edits=(daily_note_edit(9262, note_id, 'Parent drift after replacement.', '#dd3300', existing['body_hash']),),
    )

    replay = service.reprepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9261),
        preparation_id=parent.preparation_id,
        expected_operation_revision=None,
        expected_draft_revision=parent_draft.revision,
        expected_draft_revision_hash=parent_draft.revision_hash,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='saved_capture',
        capture_id='72000000-0000-4000-8000-000000009261',
        analysis_mode='manual_only',
    )
    with pytest.raises(report_api.ReportError) as changed:
        service.reprepare(
            fixture.actor,
            fixture.project.id,
            fixture.stage.id,
            command_id=draft_command(9261),
            preparation_id=parent.preparation_id,
            expected_operation_revision=None,
            expected_draft_revision=parent_draft.revision + 1,
            expected_draft_revision_hash=parent_draft.revision_hash,
            expected_baseline_ref=None,
            template_selection=fixture.template_selection,
            source_mode='saved_capture',
            capture_id='72000000-0000-4000-8000-000000009261',
            analysis_mode='manual_only',
        )

    assert replay.preparation_id == replacement.preparation_id
    assert replay.draft_id == replacement.draft_id
    assert replay.draft_revision == replacement.draft_revision
    assert changed.value.code == 'REPORT_PREPARATION_COMMAND_CONFLICT'


@pytest.mark.django_db(transaction=True)
def test_should_reread_parent_draft_cas_under_writer_before_replacement_command(tmp_path, monkeypatch):
    fixture = history_fixture(tmp_path)
    service = report_api.ReportPreparationService(
        fixture.continuity,
        fixture.draft_service,
        fixture.template_service,
    )
    parent = service.prepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9265),
        series_id=fixture.series.series_id,
        meeting_date='2026-11-02',
        expected_series_policy_hash=fixture.series.revision_hash,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='saved_capture',
        capture_id='72000000-0000-4000-8000-000000009265',
        analysis_mode='manual_only',
        acknowledge_gap_draft_ids=(),
    )
    parent_draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, parent.draft_id)
    command_id = draft_command(9266)
    original_preview = worker_module.build_baseline_preview_from_repository

    def drift_parent(*args, **kwargs):
        preview = original_preview(*args, **kwargs)
        draft_root = (
            fixture.archive_root / 'projects' / fixture.project.id / 'stages' / fixture.stage.id
            / 'runtime' / 'report-drafts' / parent.draft_id
        )
        (draft_root / 'current.json').write_bytes(canonical_bytes({
            'schema_version': 1,
            'revision': parent_draft.revision + 1,
            'revision_hash': parent_draft.revision_hash,
        }))
        return preview

    monkeypatch.setattr(worker_module, 'build_baseline_preview_from_repository', drift_parent)

    with pytest.raises(report_api.ReportError) as error:
        service.reprepare(
            fixture.actor,
            fixture.project.id,
            fixture.stage.id,
            command_id=command_id,
            preparation_id=parent.preparation_id,
            expected_operation_revision=None,
            expected_draft_revision=parent_draft.revision,
            expected_draft_revision_hash=parent_draft.revision_hash,
            expected_baseline_ref=None,
            template_selection=fixture.template_selection,
            source_mode='saved_capture',
            capture_id='72000000-0000-4000-8000-000000009266',
            analysis_mode='manual_only',
        )
    runtime = fixture.archive_root / 'projects' / fixture.project.id / 'stages' / fixture.stage.id / 'runtime'

    assert error.value.code in {'REPORT_ARTIFACT_INVALID', 'REPORT_REVISION_CONFLICT'}
    assert not (runtime / 'report-preparation-commands' / f'{command_id}.json').exists()


@pytest.mark.django_db(transaction=True)
def test_should_reread_parent_operation_cas_under_writer_before_replacement_command(tmp_path, monkeypatch):
    fixture = history_fixture(tmp_path)
    service, run_service = _refresh_parent_service(fixture, ())
    parent = _prepare_refresh(fixture, service, 9267)
    failed = run_service.transition(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        parent.operation_id,
        lambda current: replace(current, state='failed', revision=current.revision + 1, error_code='RUN_STORAGE_INVALID'),
    )
    command_id = draft_command(9268)
    original_preview = worker_module.build_baseline_preview_from_repository

    def drift_operation(*args, **kwargs):
        preview = original_preview(*args, **kwargs)
        run_service.transition(
            fixture.actor,
            fixture.project.id,
            fixture.stage.id,
            parent.operation_id,
            lambda current: replace(current, state='failed', revision=current.revision + 1, error_code='RUN_INVALID'),
        )
        return preview

    monkeypatch.setattr(worker_module, 'build_baseline_preview_from_repository', drift_operation)

    with pytest.raises(report_api.ReportError) as error:
        service.reprepare(
            fixture.actor,
            fixture.project.id,
            fixture.stage.id,
            command_id=command_id,
            preparation_id=parent.preparation_id,
            expected_operation_revision=failed.revision,
            expected_draft_revision=None,
            expected_draft_revision_hash=None,
            expected_baseline_ref=None,
            template_selection=fixture.template_selection,
            source_mode='refresh',
            capture_id=None,
            analysis_mode='manual_only',
        )
    runtime = fixture.archive_root / 'projects' / fixture.project.id / 'stages' / fixture.stage.id / 'runtime'

    assert error.value.code in {'REPORT_ARTIFACT_INVALID', 'REPORT_REVISION_CONFLICT'}
    assert not (runtime / 'report-preparation-commands' / f'{command_id}.json').exists()


@pytest.mark.django_db(transaction=True)
def test_should_refuse_inactive_daily_draft_finalize_before_publication_side_effects(tmp_path):
    fixture = history_fixture(tmp_path)
    service = report_api.ReportPreparationService(
        fixture.continuity,
        fixture.draft_service,
        fixture.template_service,
    )
    parent = service.prepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9280),
        series_id=fixture.series.series_id,
        meeting_date='2026-11-02',
        expected_series_policy_hash=fixture.series.revision_hash,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='saved_capture',
        capture_id='72000000-0000-4000-8000-000000009280',
        analysis_mode='manual_only',
        acknowledge_gap_draft_ids=(),
    )
    parent_draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, parent.draft_id)
    service.reprepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9281),
        preparation_id=parent.preparation_id,
        expected_operation_revision=None,
        expected_draft_revision=parent_draft.revision,
        expected_draft_revision_hash=parent_draft.revision_hash,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='saved_capture',
        capture_id='72000000-0000-4000-8000-000000009281',
        analysis_mode='manual_only',
    )
    before = publication_ids(fixture.archive_root, fixture.project.id, fixture.stage.id)

    with pytest.raises(report_api.ReportError) as error:
        fixture.draft_service.finalize_and_commit(
            fixture.actor,
            fixture.project.id,
            fixture.stage.id,
            parent.draft_id,
            command_id=draft_command(9282),
            expected_revision=parent_draft.revision,
        )

    draft_root = (
        fixture.archive_root / 'projects' / fixture.project.id / 'stages' / fixture.stage.id
        / 'runtime' / 'report-drafts' / parent.draft_id
    )
    assert error.value.code == 'REPORT_REVISION_CONFLICT'
    assert publication_ids(fixture.archive_root, fixture.project.id, fixture.stage.id) == before
    assert not (draft_root / 'finalization.json').exists()


@pytest.mark.django_db(transaction=True)
def test_should_refuse_guarded_daily_finalize_when_preparation_binding_missing(tmp_path):
    fixture = history_fixture(tmp_path)
    service = report_api.ReportPreparationService(
        fixture.continuity,
        fixture.draft_service,
        fixture.template_service,
    )
    prepared = service.prepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9290),
        series_id=fixture.series.series_id,
        meeting_date='2026-11-02',
        expected_series_policy_hash=fixture.series.revision_hash,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='saved_capture',
        capture_id='72000000-0000-4000-8000-000000009290',
        analysis_mode='manual_only',
        acknowledge_gap_draft_ids=(),
    )
    draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, prepared.draft_id)
    draft_root = (
        fixture.archive_root / 'projects' / fixture.project.id / 'stages' / fixture.stage.id
        / 'runtime' / 'report-drafts' / draft.draft_id
    )
    (draft_root / 'preparation-binding.json').unlink()

    with pytest.raises(report_api.ReportError) as error:
        fixture.draft_service.finalize_and_commit(
            fixture.actor,
            fixture.project.id,
            fixture.stage.id,
            draft.draft_id,
            command_id=draft_command(9291),
            expected_revision=draft.revision,
        )

    assert error.value.code in {'REPORT_ARTIFACT_INVALID', 'REPORT_REVISION_CONFLICT'}
    assert not (draft_root / 'finalization.json').exists()


@pytest.mark.django_db(transaction=True)
def test_should_refuse_guarded_daily_finalize_when_binding_is_downgraded_to_internal_kind(tmp_path):
    fixture = history_fixture(tmp_path)
    service = report_api.ReportPreparationService(
        fixture.continuity,
        fixture.draft_service,
        fixture.template_service,
    )
    prepared = service.prepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9300),
        series_id=fixture.series.series_id,
        meeting_date='2026-11-02',
        expected_series_policy_hash=fixture.series.revision_hash,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='saved_capture',
        capture_id='72000000-0000-4000-8000-000000009300',
        analysis_mode='manual_only',
        acknowledge_gap_draft_ids=(),
    )
    draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, prepared.draft_id)
    draft_root = (
        fixture.archive_root / 'projects' / fixture.project.id / 'stages' / fixture.stage.id
        / 'runtime' / 'report-drafts' / draft.draft_id
    )
    binding_path = draft_root / 'preparation-binding.json'
    binding = decode_json(binding_path.read_bytes())
    binding_path.write_bytes(canonical_bytes({
        **binding,
        'schema_version': 1,
        'kind': 'internal_prepared_context',
    }))

    with pytest.raises(report_api.ReportError) as error:
        fixture.draft_service.finalize_and_commit(
            fixture.actor,
            fixture.project.id,
            fixture.stage.id,
            draft.draft_id,
            command_id=draft_command(9301),
            expected_revision=draft.revision,
        )

    assert error.value.code == 'REPORT_ARTIFACT_INVALID'
    assert not (draft_root / 'finalization.json').exists()

from dataclasses import replace
import uuid

import pytest

from project_management.app.api import reports as report_api
from project_management.app.api.project_runs import ProjectRunService, ProjectRunWorker
from project_management.app.domain.capture_values import canonical_bytes
from project_management.app.domain.run_contracts import RunRequest
from project_management.out.ai_task_contract import AiTaskContract
from project_management.services.capture import ProjectCaptureService

import project_management.services.report_preparation_worker as worker_module
from project_management.services.report_reprepare_parent_cas import verify_parent_cas
from project_management.services.report_sources import ReportSourceReader
from project_management.storage.report_preparations import ReportPreparationStore
from project_management.tests.history_persistence_fixtures import history_fixture
from project_management.tests.project_run_fixtures import ManualRunEnvironment, ProviderAccessDouble
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


def test_should_verify_parent_operation_cas_from_event_chain_not_stale_state_cache(tmp_path):
    environment = ManualRunEnvironment(tmp_path / 'archive-root')
    request = RunRequest(str(uuid.uuid4()), environment.stage.definition_hash, daily_template(), 'Asia/Shanghai')
    operation = environment.run_service.submit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        request,
    )
    runtime = tmp_path / 'archive-root' / 'projects' / environment.project.id / 'stages' / environment.stage.id / 'runtime'
    stale_state = (runtime / 'operations' / operation.operation_id / 'state.json').read_bytes()
    environment.run_service.transition(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        operation.operation_id,
        lambda current: replace(current, state='failed', revision=current.revision + 1, error_code='RUN_STORAGE_INVALID'),
    )
    (runtime / 'operations' / operation.operation_id / 'state.json').write_bytes(stale_state)
    intent = {
        'parent_operation_id': operation.operation_id,
        'expected_parent_operation_revision': operation.revision,
        'expected_parent_operation_state': operation.state,
        'parent_draft_id': None,
    }

    with environment.archive._report_repository(
            environment.actor, environment.project.id, environment.stage.id, write=True) as repository:
        with pytest.raises(report_api.ReportError) as error:
            verify_parent_cas(
                repository,
                environment.archive.config.root,
                environment.archive.config.limits,
                environment.draft_service.limits,
                intent,
            )

    assert error.value.code == 'REPORT_REVISION_CONFLICT'


@pytest.mark.django_db(transaction=True)
def test_should_refuse_inactive_replacement_worker_before_capture_or_draft(tmp_path):
    fixture = history_fixture(tmp_path)
    provider = ProviderAccessDouble(fixture.stage, ({
        'stable_id': 'ALPHA-1',
        'summary': 'Intermittent validation failure',
        'status': 'Fixed',
        'comments': {'201': {'id': '201', 'body': 'Failure observed.'}},
    },))
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
    parent = service.prepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9270),
        series_id=fixture.series.series_id,
        meeting_date='2026-11-02',
        expected_series_policy_hash=fixture.series.revision_hash,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='saved_capture',
        capture_id='72000000-0000-4000-8000-000000009270',
        analysis_mode='manual_only',
        acknowledge_gap_draft_ids=(),
    )
    parent_draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, parent.draft_id)
    source_reader = ReportSourceReader(fixture.archive, AiTaskContract.load(PACK_ROOT))
    fixture.continuity.source_reader = source_reader
    fixture.draft_service.source_reader = source_reader
    replacement = service.reprepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9271),
        preparation_id=parent.preparation_id,
        expected_operation_revision=None,
        expected_draft_revision=parent_draft.revision,
        expected_draft_revision_hash=parent_draft.revision_hash,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='refresh',
        capture_id=None,
        analysis_mode='manual_only',
    )
    runtime = fixture.archive_root / 'projects' / fixture.project.id / 'stages' / fixture.stage.id / 'runtime'
    with fixture.archive._report_repository(fixture.actor, fixture.project.id, fixture.stage.id, write=True) as repository:
        store = ReportPreparationStore(repository, fixture.archive.config.root, fixture.archive.config.limits)
        store.replace_slot(store.intent(replacement.preparation_id), store.intent(parent.preparation_id))

    with pytest.raises(report_api.ReportError) as error:
        ProjectRunWorker(run_service, daily_preparation_service=service).execute(
            fixture.actor,
            fixture.project.id,
            fixture.stage.id,
            replacement.operation_id,
        )

    assert error.value.code == 'REPORT_REVISION_CONFLICT'
    assert provider.open_count == 0
    assert not (runtime / 'report-drafts' / replacement.draft_id).exists()


def _replace_active_slot_with_parent(fixture, replacement, parent):
    with fixture.archive._report_repository(fixture.actor, fixture.project.id, fixture.stage.id, write=True) as repository:
        store = ReportPreparationStore(repository, fixture.archive.config.root, fixture.archive.config.limits)
        store.replace_slot(store.intent(replacement.preparation_id), store.intent(parent.preparation_id))


@pytest.mark.django_db(transaction=True)
def test_should_refuse_worker_superseded_after_capture_before_seed_or_draft(tmp_path):
    fixture = history_fixture(tmp_path)
    provider = ProviderAccessDouble(fixture.stage, ({
        'stable_id': 'ALPHA-1',
        'summary': 'Intermittent validation failure',
        'status': 'Fixed',
        'comments': {'201': {'id': '201', 'body': 'Failure observed.'}},
    },))
    run_service = ProjectRunService(
        fixture.archive.project_api,
        fixture.archive,
        ProjectCaptureService(fixture.archive.project_api, provider, fixture.archive,
                              required_parts=('facts', 'comments', 'history')),
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
    parent = service.prepare(
        fixture.actor, fixture.project.id, fixture.stage.id, command_id=draft_command(9310),
        series_id=fixture.series.series_id, meeting_date='2026-11-02',
        expected_series_policy_hash=fixture.series.revision_hash, expected_baseline_ref=None,
        template_selection=fixture.template_selection, source_mode='saved_capture',
        capture_id='72000000-0000-4000-8000-000000009310', analysis_mode='manual_only',
        acknowledge_gap_draft_ids=(),
    )
    parent_draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, parent.draft_id)
    source_reader = ReportSourceReader(fixture.archive, AiTaskContract.load(PACK_ROOT))
    fixture.continuity.source_reader = source_reader
    fixture.draft_service.source_reader = source_reader
    replacement = service.reprepare(
        fixture.actor, fixture.project.id, fixture.stage.id, command_id=draft_command(9311),
        preparation_id=parent.preparation_id, expected_operation_revision=None,
        expected_draft_revision=parent_draft.revision,
        expected_draft_revision_hash=parent_draft.revision_hash, expected_baseline_ref=None,
        template_selection=fixture.template_selection, source_mode='refresh', capture_id=None,
        analysis_mode='manual_only',
    )

    class SupersedeAfterCaptureWorker(ProjectRunWorker):
        def _capture(self, actor, project_id, stage_id, operation):
            receipt = super()._capture(actor, project_id, stage_id, operation)
            _replace_active_slot_with_parent(fixture, replacement, parent)
            return receipt

    completed = SupersedeAfterCaptureWorker(run_service, daily_preparation_service=service).execute(
        fixture.actor, fixture.project.id, fixture.stage.id, replacement.operation_id,
    )
    runtime = fixture.archive_root / 'projects' / fixture.project.id / 'stages' / fixture.stage.id / 'runtime'

    assert provider.open_count == 1
    assert completed.state == 'partial'
    assert completed.draft_id is None
    assert not (runtime / 'operations' / replacement.operation_id / 'draft-selection.json').exists()
    assert not (runtime / 'report-drafts' / replacement.draft_id).exists()


@pytest.mark.django_db(transaction=True)
def test_should_refuse_worker_superseded_after_seed_before_draft_selection_or_draft(tmp_path):
    fixture = history_fixture(tmp_path)
    provider_items = ({
        'stable_id': 'ALPHA-1',
        'summary': 'Intermittent validation failure',
        'status': 'Fixed',
        'comments': {'201': {'id': '201', 'body': 'Failure observed.'}},
    },)
    service = report_api.ReportPreparationService(
        fixture.continuity,
        fixture.draft_service,
        fixture.template_service,
    )
    parent = service.prepare(
        fixture.actor, fixture.project.id, fixture.stage.id, command_id=draft_command(9320),
        series_id=fixture.series.series_id, meeting_date='2026-11-02',
        expected_series_policy_hash=fixture.series.revision_hash, expected_baseline_ref=None,
        template_selection=fixture.template_selection, source_mode='saved_capture',
        capture_id='72000000-0000-4000-8000-000000009320', analysis_mode='manual_only',
        acknowledge_gap_draft_ids=(),
    )
    parent_draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, parent.draft_id)
    source_reader = ReportSourceReader(fixture.archive, AiTaskContract.load(PACK_ROOT))
    fixture.continuity.source_reader = source_reader
    fixture.draft_service.source_reader = source_reader
    service, run_service = _refresh_parent_service(fixture, provider_items)
    replacement = service.reprepare(
        fixture.actor, fixture.project.id, fixture.stage.id, command_id=draft_command(9321),
        preparation_id=parent.preparation_id, expected_operation_revision=None,
        expected_draft_revision=parent_draft.revision,
        expected_draft_revision_hash=parent_draft.revision_hash, expected_baseline_ref=None,
        template_selection=fixture.template_selection, source_mode='refresh', capture_id=None,
        analysis_mode='manual_only',
    )
    original = service.prepare_worker_context

    def supersede_after_seed(*args, **kwargs):
        result = original(*args, **kwargs)
        _replace_active_slot_with_parent(fixture, replacement, parent)
        return result

    service.prepare_worker_context = supersede_after_seed
    completed = ProjectRunWorker(run_service, daily_preparation_service=service).execute(
        fixture.actor, fixture.project.id, fixture.stage.id, replacement.operation_id,
    )
    runtime = fixture.archive_root / 'projects' / fixture.project.id / 'stages' / fixture.stage.id / 'runtime'

    assert completed.state == 'partial'
    assert completed.draft_id is None
    assert (runtime / 'report-preparations' / replacement.preparation_id / 'context.json').exists()
    assert not (runtime / 'operations' / replacement.operation_id / 'draft-selection.json').exists()
    assert not (runtime / 'report-drafts' / replacement.draft_id).exists()

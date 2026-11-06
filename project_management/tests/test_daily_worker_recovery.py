import pytest

from project_management.app.api import reports as report_api
from project_management.app.api.project_runs import ProjectRunService, ProjectRunWorker
from project_management.app.domain.capture_values import decode_json
from project_management.out.ai_task_contract import AiTaskContract
from project_management.services.capture import ProjectCaptureService
from project_management.services.report_sources import ReportSourceReader
from project_management.tests.history_persistence_fixtures import history_fixture
from project_management.tests.project_run_fixtures import ProviderAccessDouble
from project_management.tests.report_draft_fixtures import draft_command
from project_management.tests.summary_fixtures import PACK_ROOT


def refresh_manual_services(fixture, provider_items=None):
    source_reader = ReportSourceReader(fixture.archive, AiTaskContract.load(PACK_ROOT))
    fixture.continuity.source_reader = source_reader
    fixture.draft_service.source_reader = source_reader
    provider = ProviderAccessDouble(fixture.stage, tuple(provider_items or ({
        'stable_id': 'ALPHA-1',
        'summary': 'Intermittent validation failure',
        'status': 'Fixed',
        'comments': {'201': {'id': '201', 'body': 'Failure observed.'}},
    },)))
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
    return report_api.ReportPreparationService(
        fixture.continuity,
        fixture.draft_service,
        fixture.template_service,
        run_service=run_service,
    ), run_service


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
def test_should_repair_daily_request_only_operation_with_original_ids_deadline_and_meeting(tmp_path):
    fixture = history_fixture(tmp_path)
    service, run_service = refresh_manual_services(fixture, provider_items=())
    prepared = prepare_refresh_manual(fixture, service, 9116)
    operation = run_service.get(fixture.actor, fixture.project.id, fixture.stage.id, prepared.operation_id)
    runtime = fixture.archive_root / 'projects' / fixture.project.id / 'stages' / fixture.stage.id / 'runtime'
    operation_root = runtime / 'operations' / operation.operation_id
    for path in (operation_root / 'events').glob('*.json'):
        path.unlink()
    (operation_root / 'state.json').unlink()
    active = runtime / 'operations' / 'active.json'
    if active.exists():
        active.unlink()

    run_service.reconcile_interrupted()
    repaired = run_service.get(fixture.actor, fixture.project.id, fixture.stage.id, operation.operation_id)
    intent = decode_json((runtime / 'report-preparations' / prepared.preparation_id / 'intent.json').read_bytes())

    assert repaired.operation_id == operation.operation_id
    assert repaired.capture_id == operation.capture_id
    assert repaired.deadline_at == operation.deadline_at
    assert repaired.state == 'queued'
    assert intent['meeting_date'] == '2026-11-02'


@pytest.mark.django_db(transaction=True)
def test_should_resume_daily_seed_and_draft_selection_written_without_creating_extra_draft(tmp_path):
    fixture = history_fixture(tmp_path)
    service, run_service = refresh_manual_services(fixture)
    prepared = prepare_refresh_manual(fixture, service, 9117)
    original_create = fixture.draft_service.create_authored
    failed = {'done': False}

    def crash_once(*args, **kwargs):
        if not failed['done']:
            failed['done'] = True
            raise RuntimeError('crash after daily draft selection')
        return original_create(*args, **kwargs)

    fixture.draft_service.create_authored = crash_once
    worker = ProjectRunWorker(run_service, daily_preparation_service=service)
    with pytest.raises(RuntimeError):
        worker.execute(fixture.actor, fixture.project.id, fixture.stage.id, prepared.operation_id)

    run_service.reconcile_interrupted()
    interrupted = run_service.get(fixture.actor, fixture.project.id, fixture.stage.id, prepared.operation_id)
    resumed = run_service.resume(fixture.actor, fixture.project.id, fixture.stage.id, prepared.operation_id, expected_revision=interrupted.revision)
    completed = worker.execute(fixture.actor, fixture.project.id, fixture.stage.id, prepared.operation_id)
    runtime = fixture.archive_root / 'projects' / fixture.project.id / 'stages' / fixture.stage.id / 'runtime'

    assert resumed.operation_id == prepared.operation_id
    assert completed.draft_id == prepared.draft_id
    assert len(tuple((runtime / 'report-drafts').iterdir())) == 1


@pytest.mark.django_db(transaction=True)
def test_should_resume_daily_draft_created_before_terminal_state_without_extra_draft(tmp_path):
    fixture = history_fixture(tmp_path)
    service, run_service = refresh_manual_services(fixture)
    prepared = prepare_refresh_manual(fixture, service, 9118)

    class CrashAfterDraftWorker(ProjectRunWorker):
        def _transition(self, actor, project_id, stage_id, operation_id, updater):
            current = self.run_service.get(actor, project_id, stage_id, operation_id)
            candidate = updater(current)
            if candidate.draft_id is not None and current.draft_id is None:
                raise RuntimeError('crash after daily draft before terminal state')
            return super()._transition(actor, project_id, stage_id, operation_id, updater)

    crashing = CrashAfterDraftWorker(run_service, daily_preparation_service=service)
    with pytest.raises(RuntimeError):
        crashing.execute(fixture.actor, fixture.project.id, fixture.stage.id, prepared.operation_id)

    run_service.reconcile_interrupted()
    interrupted = run_service.get(fixture.actor, fixture.project.id, fixture.stage.id, prepared.operation_id)
    run_service.resume(fixture.actor, fixture.project.id, fixture.stage.id, prepared.operation_id, expected_revision=interrupted.revision)
    completed = ProjectRunWorker(run_service, daily_preparation_service=service).execute(
        fixture.actor, fixture.project.id, fixture.stage.id, prepared.operation_id,
    )
    runtime = fixture.archive_root / 'projects' / fixture.project.id / 'stages' / fixture.stage.id / 'runtime'

    assert completed.draft_id == prepared.draft_id
    assert len(tuple((runtime / 'report-drafts').iterdir())) == 1

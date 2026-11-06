import pytest

from project_management.app.api import reports as report_api
from project_management.app.api.project_runs import ProjectRunWorker
from project_management.app.api.report_factories import build_report_preparation_service
from project_management.app.api.summary_analysis import SummaryAnalysisService
from project_management.app.domain.summary_contracts import AiBackendTarget
from project_management.out.ai_task_contract import AiTaskContract
from project_management.tests.history_persistence_fixtures import daily_note_edit, history_fixture
from project_management.tests.project_run_fixtures import ProjectRunHttp
from project_management.tests.report_draft_fixtures import draft_command
from project_management.tests.summary_fixtures import PACK_ROOT
from project_management.tests.test_daily_reprepare_backend import prepare_refresh_manual, refresh_manual_service


@pytest.mark.django_db(transaction=True)
def test_shouldCreateLinkedCorrectionFromFinalizedManualPreparationAndRefuseNewSource(tmp_path):
    fixture = history_fixture(tmp_path)
    service = report_api.ReportPreparationService(fixture.continuity, fixture.draft_service, fixture.template_service)
    capture_id = draft_command(9950)
    result = service.prepare(
        fixture.actor, fixture.project.id, fixture.stage.id,
        command_id=draft_command(9951), series_id=fixture.series.series_id, meeting_date='2026-11-02',
        expected_series_policy_hash=fixture.series.revision_hash, expected_baseline_ref=None,
        template_selection=fixture.template_selection, source_mode='saved_capture',
        capture_id=capture_id, analysis_mode='manual_only', acknowledge_gap_draft_ids=(),
    )
    draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, result.draft_id)
    published = fixture.draft_service.finalize_and_commit(
        fixture.actor, fixture.project.id, fixture.stage.id, draft.draft_id,
        command_id=draft_command(9952), expected_revision=draft.revision,
    )
    arguments = {
        'preparation_id': result.preparation_id,
        'expected_operation_revision': None,
        'expected_draft_revision': draft.revision,
        'expected_draft_revision_hash': draft.revision_hash,
        'expected_baseline_ref': None,
        'template_selection': fixture.template_selection,
        'source_mode': 'saved_capture',
        'capture_id': capture_id,
        'analysis_mode': 'manual_only',
    }

    correction = service.reprepare(
        fixture.actor, fixture.project.id, fixture.stage.id,
        command_id=draft_command(9953), **arguments,
    )
    linked = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, correction.draft_id)
    assert linked.parent_publication_id == published.manifest.publication_id
    assert correction.operation_id is None
    with pytest.raises(report_api.ReportError) as error:
        service.reprepare(
            fixture.actor, fixture.project.id, fixture.stage.id, command_id=draft_command(9954),
            **{**arguments, 'capture_id': draft_command(9955)},
        )
    assert error.value.code == 'REPORT_FINALIZED'


@pytest.mark.django_db(transaction=True)
def test_shouldReprepareRetainedCaptureWithoutRunningAiOrRefreshRuntime(tmp_path):
    fixture = history_fixture(tmp_path)
    online, run_service = refresh_manual_service(fixture, ({
        'stable_id': 'ALPHA-1', 'summary': 'Retained refresh source', 'status': 'Fixed',
    },))
    result = prepare_refresh_manual(fixture, online, 9960)
    operation = ProjectRunWorker(run_service, daily_preparation_service=online).execute(
        fixture.actor, fixture.project.id, fixture.stage.id, result.operation_id,
    )
    draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, operation.draft_id)
    offline = build_report_preparation_service(
        project_api=fixture.archive.project_api, archive=fixture.archive,
        continuity_service=fixture.continuity, draft_service=fixture.draft_service,
        template_service=fixture.template_service,
    )

    replacement = offline.reprepare(
        fixture.actor, fixture.project.id, fixture.stage.id,
        command_id=draft_command(9961), preparation_id=result.preparation_id,
        expected_operation_revision=operation.revision, expected_draft_revision=draft.revision,
        expected_draft_revision_hash=draft.revision_hash, expected_baseline_ref=None,
        template_selection=fixture.template_selection, source_mode='saved_capture',
        capture_id=operation.capture_id, analysis_mode='manual_only',
    )

    assert replacement.draft_id != draft.draft_id
    assert replacement.operation_id is None


@pytest.mark.django_db(transaction=True)
def test_shouldReprepareChangedItemsWithoutOverwritingHumanNoteOrRedispatchingUnchangedAnalysis(tmp_path):
    fixture = history_fixture(tmp_path)
    service, run_service = refresh_manual_service(fixture, ({
        'stable_id': 'ALPHA-1', 'summary': 'Intermittent validation failure', 'status': 'Fixed',
        'assignee': {'key': 'dev-a', 'displayName': 'Alice'},
        'reporter': {'key': 'qa-b', 'displayName': 'Bob'},
        'comments': {
            '201': {'id': '201', 'body': 'Failure observed.', 'author': {'key': 'dev-a'}},
            '202': {'id': '202', 'body': 'Logs attached. Failure reproduced on build r7.'},
            '203': {'id': '203', 'body': 'Bob (qa-b), please rerun validation on build r8.'},
        },
    },))
    contract = AiTaskContract.load(PACK_ROOT)
    http = ProjectRunHttp(contract)
    run_service.analysis_service = SummaryAnalysisService(fixture.archive, contract, http.client_factory)
    run_service.backend_resolver = lambda actor, project_id, stage_id: AiBackendTarget(
        'http://127.0.0.1:18888', 'metrics-dashboard', 'store-fixture',
        f'projects.{project_id}.stages.{stage_id}', 'dashboard-join-1', 'base-b-cancel-synthetic-1',
    )
    worker = ProjectRunWorker(run_service, daily_preparation_service=service)
    first = service.prepare(
        fixture.actor, fixture.project.id, fixture.stage.id,
        command_id=draft_command(9970), series_id=fixture.series.series_id, meeting_date='2026-11-02',
        expected_series_policy_hash=fixture.series.revision_hash, expected_baseline_ref=None,
        template_selection=fixture.template_selection, source_mode='refresh', capture_id=None,
        analysis_mode='changed_items', acknowledge_gap_draft_ids=(),
    )
    operation = worker.execute(fixture.actor, fixture.project.id, fixture.stage.id, first.operation_id)
    draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, operation.draft_id)
    note = draft.authoring_context['notes'][0]
    saved = fixture.draft_service.save_authored(
        fixture.actor, fixture.project.id, fixture.stage.id, draft.draft_id,
        command_id=draft_command(9971), expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        edits=(daily_note_edit(9971, note['note_id'], 'Human follow-up stays red.', '#aa0000', note['body_hash']),),
    )

    replacement = service.reprepare(
        fixture.actor, fixture.project.id, fixture.stage.id,
        command_id=draft_command(9972), preparation_id=first.preparation_id,
        expected_operation_revision=operation.revision, expected_draft_revision=saved.revision,
        expected_draft_revision_hash=saved.revision_hash, expected_baseline_ref=None,
        template_selection=fixture.template_selection, source_mode='refresh', capture_id=None,
        analysis_mode='changed_items',
    )
    completed = worker.execute(fixture.actor, fixture.project.id, fixture.stage.id, replacement.operation_id)
    retained = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, completed.draft_id)

    assert completed.item_results[0].state == 'no_work'
    assert retained.authoring_context['notes'][0]['body_fragment'] == saved.authoring_context['notes'][0]['body_fragment']
    assert [request for request in http.requests if request == ('POST', '/api/runs')] == [('POST', '/api/runs')]

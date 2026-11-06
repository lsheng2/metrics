from dataclasses import replace

import pytest

from project_management.app.api import reports as report_api
from project_management.app.api.capture_archive import CaptureArchiveService
from project_management.app.api.project_runs import ProjectRunService, ProjectRunWorker, RunError
from project_management.app.api.report_factories import build_report_preparation_for_run, build_report_service
from project_management.out.capture_archive import LocalArchiveRepositoryFactory
from project_management.services.capture import ProjectCaptureService
from project_management.tests.history_persistence_fixtures import history_fixture
from project_management.tests.project_run_fixtures import ProviderAccessDouble
from project_management.tests.report_draft_fixtures import draft_command
from project_management.tests.test_report_preparation_read import runtime_files


def arguments(fixture, command=9980, analysis_mode='manual_only'):
    return {
        'command_id': draft_command(command), 'series_id': fixture.series.series_id,
        'meeting_date': '2026-11-02', 'expected_series_policy_hash': fixture.series.revision_hash,
        'expected_baseline_ref': None, 'template_selection': fixture.template_selection,
        'source_mode': 'refresh', 'capture_id': None, 'analysis_mode': analysis_mode,
        'acknowledge_gap_draft_ids': (),
    }


@pytest.mark.django_db(transaction=True)
def test_shouldPreviewThenPrepareFirstRefreshWithoutPreinitializedArchive(tmp_path):
    fixture = history_fixture(tmp_path)
    root = tmp_path / 'first-use'
    root.mkdir()
    project_api = fixture.archive.project_api
    archive = CaptureArchiveService(
        project_api, LocalArchiveRepositoryFactory(), replace(fixture.archive.config, root=root),
    )
    draft_service = build_report_service(project_api=project_api, archive=archive,
                                         template_service=fixture.template_service)
    provider = ProviderAccessDouble(fixture.stage, ({'stable_id': 'ALPHA-1', 'summary': 'First source', 'status': 'Fixed'},))
    capture = ProjectCaptureService(project_api, provider, archive, required_parts=('facts', 'comments', 'history'))
    run = ProjectRunService(project_api, archive, capture, None, draft_service, None, notifier=lambda *args: None)
    service = build_report_preparation_for_run(run)

    preview = service.continuity.preview(
        fixture.actor, fixture.project.id, fixture.stage.id,
        series_id=fixture.series.series_id, meeting_date='2026-11-02',
        template_selection=fixture.template_selection,
    )
    assert preview.state == 'initial'
    assert not (root / 'projects').exists()
    prepared = service.prepare(fixture.actor, fixture.project.id, fixture.stage.id, **arguments(fixture))
    assert prepared.state == 'queued'
    assert provider.open_count == 0
    operation = ProjectRunWorker(run, daily_preparation_service=service).execute(
        fixture.actor, fixture.project.id, fixture.stage.id, prepared.operation_id,
    )
    draft = draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, operation.draft_id)
    assert draft.authoring_context['meeting']['local_date'] == '2026-11-02'
    assert draft.authoring_context['current_observations'][0]['source_status']['value'] == 'Fixed'


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(('mode', 'expected_code'), (
    ('manual_only', 'RUN_UNAVAILABLE'), ('changed_items', 'REPORT_AI_UNAVAILABLE'),
))
def test_shouldRejectNewUnavailableWorkBeforeReservingPreparation(tmp_path, mode, expected_code):
    fixture = history_fixture(tmp_path)
    run = None if mode == 'manual_only' else ProjectRunService(
        fixture.archive.project_api, fixture.archive, None, None, fixture.draft_service, None,
        notifier=lambda *args: None,
    )
    service = report_api.ReportPreparationService(
        fixture.continuity, fixture.draft_service, fixture.template_service, run_service=run,
    )
    before = runtime_files(fixture)

    with pytest.raises((RunError, report_api.ReportError)) as error:
        service.prepare(fixture.actor, fixture.project.id, fixture.stage.id, **arguments(fixture, analysis_mode=mode))

    assert error.value.code == expected_code
    assert runtime_files(fixture) == before

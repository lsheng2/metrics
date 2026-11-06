from dataclasses import replace

import pytest

from project_management.app.api import reports as report_api
from project_management.app.api.capture_archive import CaptureArchiveService
from project_management.app.api.report_factories import build_report_preparation_service
from project_management.out.capture_archive import LocalArchiveRepositoryFactory
from project_management.tests.history_persistence_fixtures import history_fixture
from project_management.tests.report_draft_fixtures import draft_command
from project_management.tests.test_daily_reprepare_backend import prepare_refresh_manual, refresh_manual_service


def runtime_files(fixture):
    root = fixture.archive_root / 'projects' / fixture.project.id / 'stages' / fixture.stage.id / 'runtime'
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob('*') if path.is_file()}


@pytest.mark.django_db(transaction=True)
def test_shouldReadPreparedDraftAndMeetingWithoutWritingOrRepreparing(tmp_path):
    fixture = history_fixture(tmp_path)
    service = report_api.ReportPreparationService(fixture.continuity, fixture.draft_service, fixture.template_service)
    result = service.prepare(
        fixture.actor, fixture.project.id, fixture.stage.id,
        command_id=draft_command(9900), series_id=fixture.series.series_id, meeting_date='2026-11-02',
        expected_series_policy_hash=fixture.series.revision_hash, expected_baseline_ref=None,
        template_selection=fixture.template_selection, source_mode='saved_capture',
        capture_id=draft_command(9901), analysis_mode='manual_only', acknowledge_gap_draft_ids=(),
    )
    before = runtime_files(fixture)

    details = service.get(fixture.actor, fixture.project.id, fixture.stage.id, result.preparation_id)
    selected = service.for_meeting(
        fixture.actor, fixture.project.id, fixture.stage.id,
        series_id=fixture.series.series_id, meeting_date='2026-11-02',
    )
    missing = service.for_meeting(
        fixture.actor, fixture.project.id, fixture.stage.id,
        series_id=fixture.series.series_id, meeting_date='2026-11-03',
    )

    assert details.result.draft_id == result.draft_id
    assert details.result.state == 'draft'
    assert details.draft_revision_hash
    assert details.operation_revision is None
    assert details.active_preparation_id == result.preparation_id
    assert selected == details
    assert missing is None
    assert runtime_files(fixture) == before


@pytest.mark.django_db(transaction=True)
def test_shouldObserveQueuedRefreshWithoutDispatchOrNewCapture(tmp_path):
    fixture = history_fixture(tmp_path)
    service, _ = refresh_manual_service(fixture, ({'stable_id': 'ALPHA-1', 'status': 'Fixed'},))
    result = prepare_refresh_manual(fixture, service, 9910)
    before = runtime_files(fixture)

    details = service.get(fixture.actor, fixture.project.id, fixture.stage.id, result.preparation_id)

    assert details.result.operation_id == result.operation_id
    assert details.result.state == 'queued'
    assert details.operation_revision == 1
    assert details.draft_revision_hash is None
    assert runtime_files(fixture) == before


@pytest.mark.django_db(transaction=True)
def test_shouldReportNoUnappliedChoiceForRepeatedRefreshWithDerivedCapture(tmp_path):
    fixture = history_fixture(tmp_path)
    service, _ = refresh_manual_service(fixture, ({'stable_id': 'ALPHA-1', 'status': 'Fixed'},))
    first = prepare_refresh_manual(fixture, service, 9920)

    repeated = prepare_refresh_manual(fixture, service, 9921)

    assert repeated.operation_id == first.operation_id
    assert repeated.disposition == 'existing'
    assert repeated.selection_conflicts == ()


@pytest.mark.django_db(transaction=True)
def test_shouldReportNoExistingPreparationBeforeFirstArchiveInitialization(tmp_path):
    fixture = history_fixture(tmp_path)
    fresh_root = tmp_path / 'fresh-archive'
    fresh_root.mkdir()
    archive = CaptureArchiveService(
        fixture.archive.project_api, LocalArchiveRepositoryFactory(),
        replace(fixture.archive.config, root=fresh_root),
    )
    service = build_report_preparation_service(
        project_api=fixture.archive.project_api, archive=archive, template_service=fixture.template_service,
    )

    existing = service.for_meeting(
        fixture.actor, fixture.project.id, fixture.stage.id,
        series_id=fixture.series.series_id, meeting_date='2026-11-02',
    )

    assert existing is None
    assert not (fresh_root / 'projects').exists()

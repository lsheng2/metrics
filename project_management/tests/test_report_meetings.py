from dataclasses import replace
from datetime import date, timedelta

import pytest

from project_management.app.api import reports as report_api
from project_management.app.domain.contracts import ProjectActor, ProjectError
from project_management.services.capture_archive import CaptureArchiveService
from project_management.tests.history_persistence_fixtures import (
    git_head, history_fixture, prepare_daily,
)
from project_management.tests.report_draft_fixtures import draft_command


def calendar_read(fixture, service, start='2026-11-09', end='2026-11-22'):
    return service.read(
        fixture.actor, fixture.project.id, fixture.stage.id,
        series_id=fixture.series.series_id, from_date=start, through_date=end,
    )


def change_request(fixture, view, *, command=15000, action='skip', reason='No standup'):
    return {
        'series_id': fixture.series.series_id,
        'command_id': draft_command(command),
        'expected_revision': view.revision,
        'expected_revision_hash': view.revision_hash,
        'expected_series_policy_hash': fixture.series.revision_hash,
        'action': action,
        'from_date': view.from_date,
        'through_date': view.through_date,
        'reason': reason,
    }


def mutate(fixture, service, request):
    return service.change(fixture.actor, fixture.project.id, fixture.stage.id, **request)


@pytest.mark.django_db(transaction=True)
def test_skip_restore_and_old_command_replay_do_not_create_report_work(tmp_path):
    fixture = history_fixture(tmp_path)
    service = report_api.ReportMeetingService(fixture.continuity)
    before = git_head(fixture.archive_root, fixture.project.id, fixture.stage.id)
    calls = fixture.source_reader.calls
    initial = calendar_read(fixture, service)
    assert initial.revision == 0
    assert {day.state for day in initial.days} == {'unrecorded'}

    request = change_request(fixture, initial)
    saved = mutate(fixture, service, request)
    skipped = calendar_read(fixture, service)
    assert saved.revision == 1
    assert [day.local_date for day in skipped.days] == [
        (date(2026, 11, 9) + timedelta(days=index)).isoformat() for index in range(14)
    ]
    assert {day.state for day in skipped.days} == {'skipped'}
    assert {day.reason for day in skipped.days} == {'No standup'}
    restore_view = calendar_read(fixture, service, '2026-11-16', '2026-11-16')
    mutate(fixture, service, change_request(fixture, restore_view, command=15001, action='restore'))
    from project_management.models import Project

    before_replay_revision = Project.objects.get(id=fixture.project.id).revision
    replay = mutate(fixture, service, request)
    assert replay.replayed is True
    assert replay.revision == 1
    assert Project.objects.get(id=fixture.project.id).revision == before_replay_revision
    current = calendar_read(fixture, service)
    assert current.revision == 2
    assert current.days[7].state == 'unrecorded'
    assert sum(day.state == 'skipped' for day in current.days) == 13
    assert fixture.source_reader.calls == calls
    assert git_head(fixture.archive_root, fixture.project.id, fixture.stage.id) == before
    assert fixture.draft_service.list_drafts(
        fixture.actor, fixture.project.id, fixture.stage.id,
    ).items == ()


@pytest.mark.django_db(transaction=True)
def test_stale_calendar_and_reused_command_fail_without_partial_range_change(tmp_path):
    fixture = history_fixture(tmp_path)
    service = report_api.ReportMeetingService(fixture.continuity)
    initial = calendar_read(fixture, service)
    request = change_request(fixture, initial)
    mutate(fixture, service, request)
    for invalid in (
        {**request, 'reason': 'different payload'},
        {**request, 'command_id': draft_command(15002)},
        {**change_request(fixture, calendar_read(fixture, service), command=15003),
         'expected_series_policy_hash': 'f' * 64},
    ):
        with pytest.raises(report_api.ReportError) as error:
            mutate(fixture, service, invalid)
        assert error.value.code == 'REPORT_MEETING_REVISION_CONFLICT'
    assert calendar_read(fixture, service).revision == 1


@pytest.mark.django_db(transaction=True)
def test_retained_seed_blocks_the_whole_skip_range_before_a_draft_exists(tmp_path):
    fixture = history_fixture(tmp_path)
    service = report_api.ReportMeetingService(fixture.continuity)
    prepare_daily(fixture, 1, '2026-11-02', None)
    view = calendar_read(fixture, service, '2026-11-01', '2026-11-03')
    assert view.days[1].state == 'occupied'
    with pytest.raises(report_api.ReportError) as error:
        mutate(fixture, service, change_request(fixture, view))
    assert error.value.code == 'REPORT_MEETING_OCCUPIED'
    current = calendar_read(fixture, service, '2026-11-01', '2026-11-03')
    assert current.revision == 0
    assert [day.state for day in current.days] == ['unrecorded', 'occupied', 'unrecorded']


@pytest.mark.django_db(transaction=True)
def test_skipped_day_refuses_prepare_and_direct_seed_before_source_read(tmp_path):
    fixture = history_fixture(tmp_path)
    service = report_api.ReportMeetingService(fixture.continuity)
    view = calendar_read(fixture, service, '2026-11-03', '2026-11-03')
    mutate(fixture, service, change_request(fixture, view))
    preparation = report_api.ReportPreparationService(
        fixture.continuity, fixture.draft_service, fixture.template_service,
    )
    calls = fixture.source_reader.calls
    with pytest.raises(report_api.ReportError) as error:
        preparation.prepare(
            fixture.actor, fixture.project.id, fixture.stage.id,
            command_id=draft_command(15004), series_id=fixture.series.series_id,
            meeting_date='2026-11-03', expected_series_policy_hash=fixture.series.revision_hash,
            expected_baseline_ref=None, template_selection=fixture.template_selection,
            source_mode='saved_capture', capture_id=draft_command(15005),
            analysis_mode='manual_only', acknowledge_gap_draft_ids=(),
        )
    assert error.value.code == 'REPORT_MEETING_SKIPPED'
    with pytest.raises(report_api.ReportError) as direct_error:
        prepare_daily(fixture, 2, '2026-11-03', None)
    assert direct_error.value.code == 'REPORT_MEETING_SKIPPED'
    assert fixture.source_reader.calls == calls


@pytest.mark.django_db(transaction=True)
def test_first_skip_does_not_initialize_stage_archive(tmp_path):
    fixture = history_fixture(tmp_path)
    fresh = tmp_path / 'empty-configured-root'
    fresh.mkdir()
    fixture.continuity.archive = CaptureArchiveService(
        fixture.archive.project_api, fixture.repository_factory,
        replace(fixture.archive.config, root=fresh),
    )
    service = report_api.ReportMeetingService(fixture.continuity)
    mutate(fixture, service, change_request(fixture, calendar_read(fixture, service)))
    assert not (fresh / 'projects').exists()
    assert not (fresh / 'archive-root.json').exists()
    assert {day.state for day in calendar_read(fixture, service).days} == {'skipped'}


@pytest.mark.django_db(transaction=True)
def test_foreign_owner_and_corrupt_audit_chain_are_not_empty_calendars(tmp_path):
    fixture = history_fixture(tmp_path)
    service = report_api.ReportMeetingService(fixture.continuity)
    with pytest.raises(ProjectError):
        service.read(
            ProjectActor('another-owner'), fixture.project.id, fixture.stage.id,
            series_id=fixture.series.series_id, from_date='2026-11-09', through_date='2026-11-22',
        )
    mutate(fixture, service, change_request(fixture, calendar_read(fixture, service)))
    from project_management.models_report_series import ReportMeetingChange

    record = ReportMeetingChange.objects.get(series_id=fixture.series.series_id, revision=1)
    record.payload_json['reason'] = 'tampered'
    record.save(update_fields=['payload_json'])
    with pytest.raises(report_api.ReportError) as error:
        calendar_read(fixture, service)
    assert error.value.code == 'REPORT_ARTIFACT_INVALID'


@pytest.mark.django_db(transaction=True)
def test_intent_only_reservation_blocks_skip_and_original_request_can_repair_slot(tmp_path, monkeypatch):
    from project_management.storage.report_preparations import ReportPreparationStore

    fixture = history_fixture(tmp_path)
    service = report_api.ReportMeetingService(fixture.continuity)
    preparation = report_api.ReportPreparationService(
        fixture.continuity, fixture.draft_service, fixture.template_service,
    )
    request = {
        'command_id': draft_command(15006), 'series_id': fixture.series.series_id,
        'meeting_date': '2026-11-02', 'expected_series_policy_hash': fixture.series.revision_hash,
        'expected_baseline_ref': None, 'template_selection': fixture.template_selection,
        'source_mode': 'saved_capture', 'capture_id': draft_command(15007),
        'analysis_mode': 'manual_only', 'acknowledge_gap_draft_ids': (),
    }

    def fail_slot(*args, **kwargs):
        raise OSError('synthetic interruption after intent')

    with monkeypatch.context() as failure:
        failure.setattr(ReportPreparationStore, 'write_slot', fail_slot)
        with pytest.raises(report_api.ReportError) as interrupted:
            preparation.prepare(fixture.actor, fixture.project.id, fixture.stage.id, **request)
        assert interrupted.value.code == 'REPORT_STORAGE_UNAVAILABLE'
    view = calendar_read(fixture, service, '2026-11-02', '2026-11-03')
    assert view.days[0].state == 'occupied'
    with pytest.raises(report_api.ReportError) as error:
        mutate(fixture, service, change_request(fixture, view))
    assert error.value.code == 'REPORT_MEETING_OCCUPIED'
    repaired = preparation.prepare(fixture.actor, fixture.project.id, fixture.stage.id, **request)
    assert repaired.draft_id
    assert calendar_read(fixture, service).revision == 0


@pytest.mark.django_db(transaction=True)
def test_skip_winning_after_preview_is_rechecked_inside_reservation(tmp_path, monkeypatch):
    fixture = history_fixture(tmp_path)
    service = report_api.ReportMeetingService(fixture.continuity)
    preparation = report_api.ReportPreparationService(
        fixture.continuity, fixture.draft_service, fixture.template_service,
    )
    original = preparation._validate_saved_capture

    def intervening_skip(*args, **kwargs):
        original(*args, **kwargs)
        view = calendar_read(fixture, service, '2026-11-03', '2026-11-03')
        mutate(fixture, service, change_request(fixture, view))

    monkeypatch.setattr(preparation, '_validate_saved_capture', intervening_skip)
    with pytest.raises(report_api.ReportError) as error:
        preparation.prepare(
            fixture.actor, fixture.project.id, fixture.stage.id,
            command_id=draft_command(15008), series_id=fixture.series.series_id,
            meeting_date='2026-11-03', expected_series_policy_hash=fixture.series.revision_hash,
            expected_baseline_ref=None, template_selection=fixture.template_selection,
            source_mode='saved_capture', capture_id=draft_command(15009),
            analysis_mode='manual_only', acknowledge_gap_draft_ids=(),
        )
    assert error.value.code == 'REPORT_MEETING_SKIPPED'
    assert fixture.draft_service.list_drafts(
        fixture.actor, fixture.project.id, fixture.stage.id,
    ).items == ()

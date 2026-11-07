from copy import deepcopy

import pytest

from project_management.app.api import reports as report_api
from project_management.app.domain.report_continuity_context import validate_daily_authoring_context
from project_management.tests.history_persistence_fixtures import (
    daily_note_edit, git_head, history_fixture, prepare_daily, publication_file_bytes, ref_for, weekly_document,
)
from project_management.tests.report_draft_fixtures import draft_command
from project_management.tests.test_report_meetings import calendar_read, change_request, mutate


def iso_calendar(fixture):
    previous = fixture.series
    fixture.series = fixture.continuity.save_series_policy(
        fixture.actor, fixture.project.id, fixture.stage.id,
        command_id=draft_command(15100), series_id=previous.series_id,
        expected_revision=previous.revision, expected_revision_hash=previous.revision_hash,
        name=previous.name, calendar=report_api.ReportingCalendar('iso8601', 1, 'Asia/Shanghai', 'iso8601', {}),
        template_selection=fixture.template_selection,
    )


def prepare(fixture, day, command):
    preview = fixture.continuity.preview(
        fixture.actor, fixture.project.id, fixture.stage.id,
        series_id=fixture.series.series_id, meeting_date=day, template_selection=fixture.template_selection,
    )
    service = report_api.ReportPreparationService(
        fixture.continuity, fixture.draft_service, fixture.template_service,
    )
    result = service.prepare(
        fixture.actor, fixture.project.id, fixture.stage.id,
        command_id=draft_command(command), series_id=fixture.series.series_id, meeting_date=day,
        expected_series_policy_hash=preview.series_policy_hash, expected_baseline_ref=preview.baseline_ref,
        template_selection=fixture.template_selection, source_mode='saved_capture',
        capture_id=draft_command(command + 1), analysis_mode='manual_only', acknowledge_gap_draft_ids=(),
    )
    return fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, result.draft_id)


def save_note(fixture, draft, text, color, command):
    note_id = draft.authoring_context['current_observations'][0]['note_id']
    prior = next((note for note in draft.authoring_context['notes'] if note['note_id'] == note_id), None)
    return fixture.draft_service.save_authored(
        fixture.actor, fixture.project.id, fixture.stage.id, draft.draft_id,
        command_id=draft_command(command), expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        edits=(daily_note_edit(command, note_id, text, color, None if prior is None else prior['body_hash']),),
    )


def finalize(fixture, draft, command):
    publication = fixture.draft_service.finalize_and_commit(
        fixture.actor, fixture.project.id, fixture.stage.id, draft.draft_id,
        command_id=draft_command(command), expected_revision=draft.revision,
    )
    fixture.source_reader.source_commit = git_head(fixture.archive_root, fixture.project.id, fixture.stage.id)
    return publication


@pytest.mark.django_db(transaction=True)
def test_two_empty_weeks_preserve_notes_actions_and_frozen_notice_through_publication(tmp_path):
    fixture = history_fixture(tmp_path)
    iso_calendar(fixture)
    meetings = report_api.ReportMeetingService(fixture.continuity)
    friday = save_note(fixture, prepare(fixture, '2026-11-06', 15101),
                       'Human Friday note. AR: confirm validation.', '#aa0000', 15103)
    first = finalize(fixture, friday, 15104)
    original = publication_file_bytes(fixture, first)
    original_note = friday.authoring_context['notes'][0]
    before_skip_calls = fixture.source_reader.calls
    view = calendar_read(fixture, meetings)
    mutate(fixture, meetings, change_request(fixture, view, command=15105, reason='Standup canceled'))
    assert fixture.source_reader.calls == before_skip_calls

    monday = prepare(fixture, '2026-11-23', 15106)
    context = monday.authoring_context
    assert context['schema_version'] == 3
    assert context['base_daily_publication'] == {
        'publication_id': first.manifest.publication_id,
        'manifest_hash': first.manifest_sha256,
        'commit': first.commit_id,
    }
    snapshot = context['meeting_skips']
    assert len(snapshot['days']) == 14
    assert snapshot['days'][0]['local_date'] == '2026-11-09'
    assert snapshot['days'][-1]['local_date'] == '2026-11-22'
    assert snapshot['revision'] == 1
    inherited = next(note for note in context['notes'] if note['note_id'] == original_note['note_id'])
    assert inherited == original_note
    assert context['weekly_seed']['unresolved_action_ids'] == friday.authoring_context['weekly_seed']['unresolved_action_ids']
    assert {note['meeting']['local_date'] for note in context['notes']} == {'2026-11-06'}

    monday = save_note(fixture, monday, 'Resumed Monday note.', '#0055aa', 15108)
    rendered = fixture.draft_service.render(
        fixture.actor, fixture.project.id, fixture.stage.id, monday.draft_id, revision=monday.revision,
    )
    assert 'Standups skipped:' in rendered.html_fragment
    assert '2026-11-09' in rendered.plain_text
    assert '2026-11-22' in rendered.plain_text
    second = finalize(fixture, monday, 15109)
    second_bytes = publication_file_bytes(fixture, second)
    assert b'Standups skipped:' in second_bytes['report.html']

    current = calendar_read(fixture, meetings)
    mutate(fixture, meetings, change_request(fixture, current, command=15110, action='restore'))
    assert publication_file_bytes(fixture, first) == original
    assert publication_file_bytes(fixture, second) == second_bytes
    reopened = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, monday.draft_id)
    assert reopened.authoring_context['meeting_skips'] == snapshot
    assert len(fixture.draft_service.list_drafts(fixture.actor, fixture.project.id, fixture.stage.id).items) == 2
    weekly_template = fixture.template_service.create(
        fixture.actor, fixture.project.id, command_id=draft_command(15112), name='Weekly after gap',
        document=weekly_document(),
        fill_policy={'schema_version': 2, 'instructions': {}, 'daily_note_instructions': None},
    )
    weekly = fixture.draft_service.create_period_view(
        fixture.actor, fixture.project.id, fixture.stage.id, command_id=draft_command(15113),
        series_id=fixture.series.series_id, period_key=second.manifest.period_key,
        selected_publication_refs=(ref_for(second),),
        template=report_api.UserTemplateSelection(
            str(weekly_template.template_id), weekly_template.revision, weekly_template.revision_hash,
        ),
    )
    assert weekly.authoring_context['meeting_skips'] == snapshot
    weekly_rendered = fixture.draft_service.render(
        fixture.actor, fixture.project.id, fixture.stage.id, weekly.draft_id, revision=weekly.revision,
    )
    assert 'Standups skipped:' in weekly_rendered.plain_text
    with pytest.raises(report_api.ReportError) as empty_week:
        fixture.draft_service.create_period_view(
            fixture.actor, fixture.project.id, fixture.stage.id, command_id=draft_command(15114),
            series_id=fixture.series.series_id, period_key='iso8601:1:2026:ww46',
            selected_publication_refs=(),
            template=report_api.UserTemplateSelection(
                str(weekly_template.template_id), weekly_template.revision, weekly_template.revision_hash,
            ),
        )
    assert empty_week.value.code == 'REPORT_HISTORY_UNAVAILABLE'
    preview = fixture.continuity.preview(
        fixture.actor, fixture.project.id, fixture.stage.id, series_id=fixture.series.series_id,
        meeting_date='2026-11-24', template_selection=fixture.template_selection,
    )
    assert preview.baseline_ref == ref_for(second)

    for mutation in ('missing', 'wrong_series', 'future', 'duplicate', 'wrong_schema'):
        broken = deepcopy(context)
        if mutation == 'missing':
            del broken['meeting_skips']
        elif mutation == 'wrong_series':
            broken['meeting_skips']['series_id'] = draft_command(15111)
        elif mutation == 'future':
            broken['meeting_skips']['days'][0]['local_date'] = '2026-11-24'
        elif mutation == 'duplicate':
            broken['meeting_skips']['days'].append(deepcopy(broken['meeting_skips']['days'][0]))
        else:
            broken['schema_version'] = 1
        with pytest.raises(report_api.ReportError):
            validate_daily_authoring_context(broken)


@pytest.mark.django_db(transaction=True)
def test_delayed_preparation_freezes_its_pinned_calendar_not_latest_policy(tmp_path):
    fixture = history_fixture(tmp_path)
    iso_calendar(fixture)
    meetings = report_api.ReportMeetingService(fixture.continuity)
    mutate(fixture, meetings, change_request(fixture, calendar_read(fixture, meetings), command=15200))
    original_policy = fixture.series
    fixture.continuity.save_series_policy(
        fixture.actor, fixture.project.id, fixture.stage.id, command_id=draft_command(15201),
        series_id=original_policy.series_id, expected_revision=original_policy.revision,
        expected_revision_hash=original_policy.revision_hash, name=original_policy.name,
        calendar=report_api.ReportingCalendar('iso8601', 2, 'Asia/Shanghai', 'iso8601', {}),
        template_selection=fixture.template_selection,
    )
    delayed = prepare_daily(fixture, 42, '2026-11-23', None)
    draft = fixture.draft_service.create_authored(
        fixture.actor, fixture.project.id, fixture.stage.id, command_id=delayed.command_id,
        selection=delayed.selection, template=fixture.template_selection,
        preparation_id=delayed.preparation_id,
    )
    assert draft.authoring_context['meeting']['calendar_revision'] == 1
    assert draft.authoring_context['meeting_skips']['calendar']['revision'] == 1
    assert draft.authoring_context['series_policy_hash'] == original_policy.revision_hash

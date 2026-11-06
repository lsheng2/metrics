import pytest

from project_management.app.api import reports as report_api
from project_management.tests.history_persistence_fixtures import (
    create_saved_daily,
    daily_note_edit,
    git_head,
    history_fixture,
    note_by_id,
    prepare_daily,
    publication_ids,
    publication_stub,
    ref_for,
    weekly_document,
)
from project_management.tests.report_draft_fixtures import draft_command


@pytest.mark.django_db(transaction=True)
def test_should_refuse_stale_daily_baseline_before_second_publication_append(tmp_path):
    fixture = history_fixture(tmp_path)
    day1 = prepare_daily(fixture, 1, '2026-11-02', None)
    saved1 = create_saved_daily(fixture, day1, 1, 'Day1 baseline.', '#ff0000', draft_command(8110))
    publication1 = fixture.draft_service.finalize_and_commit(fixture.actor, fixture.project.id, fixture.stage.id, saved1.draft_id, command_id=draft_command(8111), expected_revision=saved1.revision)
    fixture.source_reader.source_commit = git_head(fixture.archive_root, fixture.project.id, fixture.stage.id)
    baseline = report_api.PublicationRef(publication1.manifest.publication_id, publication1.manifest_sha256, publication1.commit_id)
    first = prepare_daily(fixture, 2, '2026-11-03', baseline)
    second = prepare_daily(fixture, 3, '2026-11-03', baseline)
    first_saved = create_saved_daily(fixture, first, 2, 'First day2 note.', '#0000ff', draft_command(8120))
    second_saved = create_saved_daily(fixture, second, 3, 'Second stale day2 note.', '#0000ff', draft_command(8130))
    fixture.draft_service.finalize_and_commit(fixture.actor, fixture.project.id, fixture.stage.id, first_saved.draft_id, command_id=draft_command(8121), expected_revision=first_saved.revision)
    before = publication_ids(fixture.archive_root, fixture.project.id, fixture.stage.id)

    with pytest.raises(report_api.ReportError) as conflict:
        fixture.draft_service.finalize_and_commit(fixture.actor, fixture.project.id, fixture.stage.id, second_saved.draft_id, command_id=draft_command(8131), expected_revision=second_saved.revision)

    assert conflict.value.code == 'REPORT_BASELINE_CONFLICT'
    assert publication_ids(fixture.archive_root, fixture.project.id, fixture.stage.id) == before


@pytest.mark.django_db(transaction=True)
def test_should_refuse_uncommitted_stale_packet_resume_but_return_committed_original(tmp_path):
    fixture = history_fixture(tmp_path)
    day1 = prepare_daily(fixture, 1, '2026-11-02', None)
    saved1 = create_saved_daily(fixture, day1, 1, 'Day1 baseline.', '#ff0000', draft_command(8210))
    publication1 = fixture.draft_service.finalize_and_commit(fixture.actor, fixture.project.id, fixture.stage.id, saved1.draft_id, command_id=draft_command(8211), expected_revision=saved1.revision)
    fixture.source_reader.source_commit = git_head(fixture.archive_root, fixture.project.id, fixture.stage.id)
    baseline = report_api.PublicationRef(publication1.manifest.publication_id, publication1.manifest_sha256, publication1.commit_id)
    stale = prepare_daily(fixture, 2, '2026-11-03', baseline)
    winner = prepare_daily(fixture, 3, '2026-11-03', baseline)
    stale_saved = create_saved_daily(fixture, stale, 2, 'Stale day2 packet.', '#0000ff', draft_command(8220))
    winner_saved = create_saved_daily(fixture, winner, 3, 'Winning day2 packet.', '#0000ff', draft_command(8230))
    fixture.repository_factory.fail_append_once = True
    with pytest.raises(report_api.ReportError):
        fixture.draft_service.finalize_and_commit(fixture.actor, fixture.project.id, fixture.stage.id, stale_saved.draft_id, command_id=draft_command(8221), expected_revision=stale_saved.revision)
    winning_publication = fixture.draft_service.finalize_and_commit(fixture.actor, fixture.project.id, fixture.stage.id, winner_saved.draft_id, command_id=draft_command(8231), expected_revision=winner_saved.revision)
    before = publication_ids(fixture.archive_root, fixture.project.id, fixture.stage.id)

    with pytest.raises(report_api.ReportError) as conflict:
        fixture.draft_service.resume_finalization(fixture.actor, fixture.project.id, fixture.stage.id, stale_saved.draft_id, command_id=draft_command(8221))
    returned = fixture.draft_service.resume_finalization(fixture.actor, fixture.project.id, fixture.stage.id, winner_saved.draft_id, command_id=draft_command(8231))

    assert conflict.value.code == 'REPORT_BASELINE_CONFLICT'
    assert returned.manifest.publication_id == winning_publication.manifest.publication_id
    assert publication_ids(fixture.archive_root, fixture.project.id, fixture.stage.id) == before


def test_should_select_daily_head_by_meeting_date_not_finalized_time():
    from project_management.services.report_daily_baseline import select_daily_head

    day2 = publication_stub('day2', 'intel-workweek:7:2026-11-03', '2026-11-03T09:00:00Z')
    old_correction = publication_stub('old-correction', 'intel-workweek:7:2026-11-02', '2026-11-04T09:00:00Z')

    assert select_daily_head((day2, old_correction)).manifest.publication_id == 'day2'


@pytest.mark.django_db(transaction=True)
def test_should_archive_older_linked_correction_without_stealing_daily_head(tmp_path):
    fixture = history_fixture(tmp_path)
    day1 = prepare_daily(fixture, 1, '2026-11-02', None)
    saved1 = create_saved_daily(fixture, day1, 1, 'Day1 baseline.', '#ff0000', draft_command(8710))
    pub1 = fixture.draft_service.finalize_and_commit(
        fixture.actor, fixture.project.id, fixture.stage.id, saved1.draft_id,
        command_id=draft_command(8711), expected_revision=saved1.revision,
    )
    fixture.source_reader.source_commit = git_head(fixture.archive_root, fixture.project.id, fixture.stage.id)
    day2 = prepare_daily(fixture, 2, '2026-11-03', ref_for(pub1))
    saved2 = create_saved_daily(fixture, day2, 2, 'Day2 head.', '#0000ff', draft_command(8720))
    pub2 = fixture.draft_service.finalize_and_commit(
        fixture.actor, fixture.project.id, fixture.stage.id, saved2.draft_id,
        command_id=draft_command(8721), expected_revision=saved2.revision,
    )
    linked = fixture.draft_service.create_linked_revision(
        fixture.actor, fixture.project.id, fixture.stage.id,
        command_id=draft_command(8730), publication_ref=ref_for(pub1),
    )
    note_id = linked.authoring_context['current_observations'][0]['note_id']
    original = note_by_id(linked.authoring_context, note_id)
    corrected = fixture.draft_service.save_authored(
        fixture.actor, fixture.project.id, fixture.stage.id, linked.draft_id,
        command_id=draft_command(8732), expected_revision=linked.revision,
        expected_revision_hash=linked.revision_hash,
        edits=(daily_note_edit(31, note_id, 'Day1 corrected red note.', '#ff0000', original['body_hash']),),
    )
    correction = fixture.draft_service.finalize_and_commit(
        fixture.actor, fixture.project.id, fixture.stage.id, corrected.draft_id,
        command_id=draft_command(8731), expected_revision=corrected.revision,
    )
    fixture.source_reader.source_commit = git_head(fixture.archive_root, fixture.project.id, fixture.stage.id)
    day3 = prepare_daily(fixture, 3, '2026-11-04', ref_for(pub2))
    draft3 = fixture.draft_service.create_authored(
        fixture.actor, fixture.project.id, fixture.stage.id,
        command_id=day3.command_id, selection=day3.selection,
        template=fixture.template_selection, preparation_id=day3.preparation_id,
    )

    assert correction.manifest.purpose == 'standup'
    assert correction.manifest.report_role == 'daily'
    assert draft3.authoring_context['base_daily_publication']['publication_id'] == pub2.manifest.publication_id
    weekly = fixture.template_service.create(
        fixture.actor, fixture.project.id, command_id=draft_command(8733),
        name='Weekly matrix', document=weekly_document(),
        fill_policy={'schema_version': 2, 'instructions': {}, 'daily_note_instructions': None},
    )
    forward = fixture.draft_service.create_period_view(
        fixture.actor, fixture.project.id, fixture.stage.id,
        command_id=draft_command(8734), series_id=fixture.series.series_id,
        period_key='intel-workweek:7:2026:ww45', selected_publication_refs=(ref_for(correction), ref_for(pub2)),
        template=report_api.UserTemplateSelection(str(weekly.template_id), weekly.revision, weekly.revision_hash),
    )
    reverse = fixture.draft_service.create_period_view(
        fixture.actor, fixture.project.id, fixture.stage.id,
        command_id=draft_command(8735), series_id=fixture.series.series_id,
        period_key='intel-workweek:7:2026:ww45', selected_publication_refs=(ref_for(pub2), ref_for(correction)),
        template=report_api.UserTemplateSelection(str(weekly.template_id), weekly.revision, weekly.revision_hash),
    )
    forward_notes = [note for note in forward.authoring_context['notes'] if note['meeting']['local_date'] == '2026-11-02']
    reverse_notes = [note for note in reverse.authoring_context['notes'] if note['meeting']['local_date'] == '2026-11-02']
    assert any(note['body_fragment']['blocks'][0]['content'][0]['text'] == 'Day1 corrected red note.' for note in forward_notes)
    assert forward_notes == reverse_notes


@pytest.mark.django_db(transaction=True)
def test_should_reject_sameday_linked_correction_when_parent_is_not_current_head(tmp_path):
    fixture = history_fixture(tmp_path)
    day1 = prepare_daily(fixture, 1, '2026-11-02', None)
    saved1 = create_saved_daily(fixture, day1, 1, 'Day1 baseline.', '#ff0000', draft_command(8740))
    pub1 = fixture.draft_service.finalize_and_commit(
        fixture.actor, fixture.project.id, fixture.stage.id, saved1.draft_id,
        command_id=draft_command(8741), expected_revision=saved1.revision,
    )
    stale = fixture.draft_service.create_linked_revision(
        fixture.actor, fixture.project.id, fixture.stage.id,
        command_id=draft_command(8742), publication_ref=ref_for(pub1),
    )
    winner = fixture.draft_service.create_linked_revision(
        fixture.actor, fixture.project.id, fixture.stage.id,
        command_id=draft_command(8743), publication_ref=ref_for(pub1),
    )
    fixture.draft_service.finalize_and_commit(
        fixture.actor, fixture.project.id, fixture.stage.id, winner.draft_id,
        command_id=draft_command(8744), expected_revision=winner.revision,
    )

    with pytest.raises(report_api.ReportError) as error:
        fixture.draft_service.finalize_and_commit(
            fixture.actor, fixture.project.id, fixture.stage.id, stale.draft_id,
            command_id=draft_command(8745), expected_revision=stale.revision,
        )

    assert error.value.code == 'REPORT_BASELINE_CONFLICT'


@pytest.mark.django_db(transaction=True)
def test_should_reject_corrupt_parent_ref_before_linked_correction_commit(tmp_path):
    fixture = history_fixture(tmp_path)
    day1 = prepare_daily(fixture, 1, '2026-11-02', None)
    saved1 = create_saved_daily(fixture, day1, 1, 'Day1 baseline.', '#ff0000', draft_command(8750))
    pub1 = fixture.draft_service.finalize_and_commit(
        fixture.actor, fixture.project.id, fixture.stage.id, saved1.draft_id,
        command_id=draft_command(8751), expected_revision=saved1.revision,
    )
    corrupt = report_api.PublicationRef(pub1.manifest.publication_id, '0' * 64, pub1.commit_id)

    with pytest.raises(report_api.ReportError) as error:
        fixture.draft_service.create_linked_revision(
            fixture.actor, fixture.project.id, fixture.stage.id,
            command_id=draft_command(8752), publication_ref=corrupt,
        )

    assert error.value.code in {'REPORT_HISTORY_UNAVAILABLE', 'REPORT_ARTIFACT_INVALID'}

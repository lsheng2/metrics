import pytest

from project_management.app.api import reports as report_api
from project_management.app.domain.capture_values import canonical_bytes, sha256_bytes
from project_management.tests.history_persistence_fixtures import (
    create_saved_daily,
    daily_note_edit,
    git_head,
    history_fixture,
    note_by_id,
    prepare_daily,
    publication_file_bytes,
    ref_for,
)
from project_management.tests.report_draft_fixtures import draft_command


@pytest.mark.django_db(transaction=True)
def test_should_persist_prepared_daily_context_through_finalize_and_seed_next_day_with_real_git(tmp_path):
    fixture = history_fixture(tmp_path)
    day1 = prepare_daily(fixture, 1, '2026-11-02', None)
    draft1 = fixture.draft_service.create_authored(
        fixture.actor, fixture.project.id, fixture.stage.id,
        command_id=day1.command_id, selection=day1.selection,
        template=fixture.template_selection, preparation_id=day1.preparation_id,
    )
    day1_note_id = draft1.authoring_context['current_observations'][0]['note_id']
    original_day1 = note_by_id(draft1.authoring_context, day1_note_id)
    saved1 = fixture.draft_service.save_authored(
        fixture.actor, fixture.project.id, fixture.stage.id, draft1.draft_id,
        command_id=draft_command(8010), expected_revision=draft1.revision,
        expected_revision_hash=draft1.revision_hash,
        edits=(daily_note_edit(1, day1_note_id, 'Day1 human red note. Deleted AI sentence stays gone.', '#ff0000', original_day1['body_hash']),),
    )
    publication1 = fixture.draft_service.finalize_and_commit(
        fixture.actor, fixture.project.id, fixture.stage.id, saved1.draft_id,
        command_id=draft_command(8011), expected_revision=saved1.revision,
    )
    fixture.source_reader.source_commit = git_head(fixture.archive_root, fixture.project.id, fixture.stage.id)
    baseline = report_api.PublicationRef(publication1.manifest.publication_id, publication1.manifest_sha256, publication1.commit_id)
    day2 = prepare_daily(fixture, 2, '2026-11-03', baseline)
    draft2 = fixture.draft_service.create_authored(
        fixture.actor, fixture.project.id, fixture.stage.id,
        command_id=day2.command_id, selection=day2.selection,
        template=fixture.template_selection, preparation_id=day2.preparation_id,
    )
    day2_note_id = draft2.authoring_context['current_observations'][0]['note_id']
    saved2 = fixture.draft_service.save_authored(
        fixture.actor, fixture.project.id, fixture.stage.id, draft2.draft_id,
        command_id=draft_command(8020), expected_revision=draft2.revision,
        expected_revision_hash=draft2.revision_hash,
        edits=(daily_note_edit(2, day2_note_id, 'Day2 human blue note on unchanged source.', '#0000ff', None),),
    )
    publication2 = fixture.draft_service.finalize_and_commit(
        fixture.actor, fixture.project.id, fixture.stage.id, saved2.draft_id,
        command_id=draft_command(8021), expected_revision=saved2.revision,
    )
    rendered = fixture.draft_service.render(fixture.actor, fixture.project.id, fixture.stage.id, saved2.draft_id, revision=saved2.revision)
    retained_day1 = note_by_id(draft2.authoring_context, day1_note_id)
    materialized_day2 = note_by_id(saved2.authoring_context, day2_note_id)

    assert day1.template_use_hash != day1.template_request_hash
    assert day1.final_create_request_hash != day1.template_request_hash
    assert draft1.draft_id == day1.context_ref.draft_id
    assert retained_day1['body_hash'] == note_by_id(saved1.authoring_context, day1_note_id)['body_hash']
    assert retained_day1['body_hash'] != original_day1['body_hash']
    assert materialized_day2['meeting']['local_date'] == '2026-11-03'
    assert materialized_day2['body_fragment']['blocks'][0]['content'][0]['foreground'] == '#0000ff'
    assert publication1.manifest.report_role == 'daily'
    assert publication1.manifest.series_id == fixture.series.series_id
    assert publication1.manifest.continuity_hash == sha256_bytes(canonical_bytes(saved1.authoring_context))
    assert publication2.manifest.period_key == 'intel-workweek:7:2026:ww45'
    assert git_head(fixture.archive_root, fixture.project.id, fixture.stage.id) == publication2.commit_id
    assert 'ww45.1(In Progress):' in rendered.html_document.decode('utf-8')
    assert 'Day1 human red note' in rendered.html_document.decode('utf-8')
    assert 'Day2 human blue note' in rendered.html_document.decode('utf-8')


@pytest.mark.django_db(transaction=True)
def test_should_preserve_three_day_and_nextweek_semantics_and_original_six_files(tmp_path):
    fixture = history_fixture(tmp_path)
    day1 = prepare_daily(fixture, 1, '2026-11-02', None)
    draft1 = fixture.draft_service.create_authored(
        fixture.actor, fixture.project.id, fixture.stage.id,
        command_id=day1.command_id, selection=day1.selection,
        template=fixture.template_selection, preparation_id=day1.preparation_id,
    )
    note1_id = draft1.authoring_context['current_observations'][0]['note_id']
    original1 = note_by_id(draft1.authoring_context, note1_id)
    saved1 = fixture.draft_service.save_authored(
        fixture.actor, fixture.project.id, fixture.stage.id, draft1.draft_id,
        command_id=draft_command(8610), expected_revision=draft1.revision,
        expected_revision_hash=draft1.revision_hash,
        edits=(daily_note_edit(21, note1_id, 'Day1 red retained source note.', '#ff0000', original1['body_hash']),),
        continuity_changes=(
            {'kind': 'add_persistent_note', 'note_id': '76000000-0000-4000-8000-000000000101', 'target': 'report', 'issue_ref': None, 'fragment': {'schema_version': 2, 'blocks': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': 'Carry this weekly context.', 'marks': [], 'foreground': None, 'background': None}]}]}, 'carry_forward': True},
            {'kind': 'add_persistent_note', 'note_id': '76000000-0000-4000-8000-000000000102', 'target': 'report', 'issue_ref': None, 'fragment': {'schema_version': 2, 'blocks': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': 'Do not carry this context.', 'marks': [], 'foreground': None, 'background': None}]}]}, 'carry_forward': False},
        ),
    )
    pub1 = fixture.draft_service.finalize_and_commit(fixture.actor, fixture.project.id, fixture.stage.id, saved1.draft_id, command_id=draft_command(8611), expected_revision=saved1.revision)
    pub1_files = publication_file_bytes(fixture, pub1)
    fixture.source_reader.source_commit = git_head(fixture.archive_root, fixture.project.id, fixture.stage.id)
    day2 = prepare_daily(fixture, 2, '2026-11-03', ref_for(pub1))
    saved2 = create_saved_daily(fixture, day2, 22, 'Day2 blue unchanged-source note.', '#0000ff', draft_command(8620))
    pub2 = fixture.draft_service.finalize_and_commit(fixture.actor, fixture.project.id, fixture.stage.id, saved2.draft_id, command_id=draft_command(8621), expected_revision=saved2.revision)
    fixture.source_reader.source_commit = git_head(fixture.archive_root, fixture.project.id, fixture.stage.id)
    day3 = prepare_daily(fixture, 3, '2026-11-04', ref_for(pub2))
    draft3 = fixture.draft_service.create_authored(fixture.actor, fixture.project.id, fixture.stage.id, command_id=day3.command_id, selection=day3.selection, template=fixture.template_selection, preparation_id=day3.preparation_id)
    render3 = fixture.draft_service.render(fixture.actor, fixture.project.id, fixture.stage.id, draft3.draft_id, revision=draft3.revision)
    pub3 = fixture.draft_service.finalize_and_commit(fixture.actor, fixture.project.id, fixture.stage.id, draft3.draft_id, command_id=draft_command(8631), expected_revision=draft3.revision)
    fixture.source_reader.source_commit = git_head(fixture.archive_root, fixture.project.id, fixture.stage.id)
    nextweek = prepare_daily(fixture, 4, '2026-11-09', ref_for(pub3))
    draft_next = fixture.draft_service.create_authored(fixture.actor, fixture.project.id, fixture.stage.id, command_id=nextweek.command_id, selection=nextweek.selection, template=fixture.template_selection, preparation_id=nextweek.preparation_id)

    day3_text = render3.html_document.decode('utf-8')
    assert 'Day1 red retained source note.' in day3_text
    assert 'Day2 blue unchanged-source note.' in day3_text
    assert 'ww45.1(In Progress):' in day3_text
    assert 'ww45.2(In Progress):' in day3_text
    assert draft_next.authoring_context['weekly_seed']['unresolved_action_ids']
    assert [note['note_id'] for note in draft_next.authoring_context['persistent_notes']] == ['76000000-0000-4000-8000-000000000101']
    assert publication_file_bytes(fixture, pub1) == pub1_files

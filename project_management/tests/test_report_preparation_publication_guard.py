import pytest

from project_management.app.api import reports as report_api
from project_management.app.api.project_runs import ProjectRunWorker
from project_management.app.domain.capture_values import decode_json
from project_management.tests.history_persistence_fixtures import (
    daily_note_edit, git_head, history_fixture, note_by_id,
)
from project_management.tests.report_draft_fixtures import draft_command
from project_management.tests.test_daily_worker_recovery import (
    prepare_refresh_manual, refresh_manual_services,
)


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize('replacement_mode', [None, 'saved_capture', 'refresh'],
                         ids=['refresh', 'reprepare-saved', 'reprepare-refresh'])
def test_should_finalize_active_prepared_draft_after_human_save(tmp_path, replacement_mode):
    fixture = history_fixture(tmp_path)
    preparation, runs = refresh_manual_services(fixture)
    actor, project, stage = fixture.actor, fixture.project.id, fixture.stage.id
    drafts = fixture.draft_service
    prepared = prepare_refresh_manual(fixture, preparation, 9900)
    worker = ProjectRunWorker(runs, daily_preparation_service=preparation)
    operation = worker.execute(actor, project, stage, prepared.operation_id)
    original = drafts.get(actor, project, stage, operation.draft_id)
    current = original

    if replacement_mode is not None:
        replacement = preparation.reprepare(
            actor, project, stage, command_id=draft_command(9901),
            preparation_id=prepared.preparation_id,
            expected_operation_revision=operation.revision,
            expected_draft_revision=original.revision,
            expected_draft_revision_hash=original.revision_hash,
            expected_baseline_ref=None,
            template_selection=fixture.template_selection,
            source_mode=replacement_mode,
            capture_id=operation.capture_id if replacement_mode == 'saved_capture' else None,
            analysis_mode='manual_only',
        )
        if replacement.operation_id is not None:
            worker.execute(actor, project, stage, replacement.operation_id)
        current = drafts.get(actor, project, stage, replacement.draft_id)
        head = git_head(fixture.archive_root, project, stage)
        with pytest.raises(report_api.ReportError) as error:
            drafts.finalize_and_commit(
                actor, project, stage, original.draft_id,
                command_id=draft_command(9902), expected_revision=original.revision,
            )
        assert error.value.code == 'REPORT_REVISION_CONFLICT'
        assert git_head(fixture.archive_root, project, stage) == head
        assert drafts.finalization_status(actor, project, stage, original.draft_id) is None

    note_id = current.authoring_context['current_observations'][0]['note_id']
    note = next((item for item in current.authoring_context['notes'] if item['note_id'] == note_id), None)
    saved = drafts.save_authored(
        actor, project, stage, current.draft_id,
        command_id=draft_command(9903), expected_revision=current.revision,
        expected_revision_hash=current.revision_hash,
        edits=(daily_note_edit(9903, note_id, 'Keep this human note.', '#0055aa',
                              None if note is None else note['body_hash']),),
    )
    reopened = drafts.get(actor, project, stage, saved.draft_id)
    publication = drafts.finalize_and_commit(
        actor, project, stage, reopened.draft_id,
        command_id=draft_command(9904), expected_revision=reopened.revision,
    )
    archived = decode_json(drafts.read_artifact(
        actor, project, stage, publication.manifest.publication_id, 'edits.json',
    ))
    archived_note = note_by_id(archived['authoring_context'], note_id)
    next_day = fixture.continuity.preview(
        actor, project, stage, series_id=fixture.series.series_id,
        meeting_date='2026-11-03', template_selection=fixture.template_selection,
    )

    assert publication.manifest.draft_revision == saved.revision == 2
    assert archived_note['body_hash'] == note_by_id(saved.authoring_context, note_id)['body_hash']
    assert archived_note['body_fragment']['blocks'][0]['content'][0]['text'] == 'Keep this human note.'
    assert archived_note['body_fragment']['blocks'][0]['content'][0]['foreground'] == '#0055aa'
    assert next_day.baseline_ref.publication_id == publication.manifest.publication_id

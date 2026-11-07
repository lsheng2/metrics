from dataclasses import replace

import pytest

from project_management.app.api import reports as report_api
from project_management.tests.history_persistence_fixtures import (
    daily_note_edit, git_head, history_fixture, prepare_daily, publication_file_bytes, ref_for,
)
from project_management.tests.report_draft_fixtures import draft_command
from project_management.tests.report_user_workflow_fixtures import new_action, source_for
from project_management.tests.test_report_standup import standup_document


@pytest.mark.django_db(transaction=True)
def test_native_publications_carry_human_ar_through_empty_week_reentry_and_no_note_day(tmp_path):
    fixture = history_fixture(tmp_path, document=standup_document())
    args = fixture.actor, fixture.project.id, fixture.stage.id
    fixture.series = fixture.continuity.save_series_policy(
        *args, command_id=draft_command(24000), series_id=fixture.series.series_id,
        expected_revision=fixture.series.revision, expected_revision_hash=fixture.series.revision_hash,
        name=fixture.series.name, calendar=report_api.ReportingCalendar('iso8601', 1, 'Asia/Shanghai', 'iso8601', {}),
        template_selection=fixture.template_selection,
    )
    drafts, baseline, originals = fixture.draft_service, None, []
    for index, day in enumerate(('2026-11-06', '2026-11-09', '2026-11-10', '2026-11-11'), 1):
        fixture.source_reader.source_commit = git_head(fixture.archive_root, fixture.project.id, fixture.stage.id)
        source = source_for(day, index)
        fixture.source_reader.snapshot = replace(source, rows=()) if index == 2 else source
        preparation = prepare_daily(fixture, index, day, baseline)
        draft = drafts.create_authored(
            *args, command_id=preparation.command_id, selection=preparation.selection,
            template=fixture.template_selection, preparation_id=preparation.preparation_id,
        )
        if index == 1:
            ctx = draft.authoring_context
            action = new_action(ctx, index=24001, owner={'owner_id': 'bob', 'display_name': 'Bob'})
            draft = drafts.save_authored(
                *args, draft.draft_id, command_id=draft_command(24001),
                expected_revision=draft.revision, expected_revision_hash=draft.revision_hash,
                edits=(daily_note_edit(24001, ctx['current_observations'][0]['note_id'], 'Friday human note.', '#aa0000', None),),
                continuity_changes=(action, {'kind': 'set_meeting_review',
                                             'issue_ref': ctx['current_observations'][0]['issue_ref'], 'state': 'discussed'}),
            )
        output = drafts.render(*args, draft.draft_id, revision=draft.revision)
        assert 'AR @Bob' in output.plain_text
        assert 'Friday human note.' in output.plain_text
        if index == 2:
            assert 'No current tickets' in output.plain_text
            assert 'Outside current scope' in output.plain_text
        if index == 3:
            assert 'Returned to scope' in output.plain_text
            assert len(draft.authoring_context['notes']) == 1
        if index == 4:
            assert 'ww46.2(In Progress): Returned to scope' in output.plain_text
            assert 'ww46.3(In Progress): No source change' in output.plain_text
        publication = drafts.finalize_and_commit(
            *args, draft.draft_id, command_id=draft_command(24100 + index), expected_revision=draft.revision,
        )
        originals.append((publication, publication_file_bytes(fixture, publication)))
        baseline = ref_for(publication)
    for publication, files in originals:
        assert publication_file_bytes(fixture, publication) == files

from io import BytesIO

from openpyxl import load_workbook
import pytest

from project_management.app.api import reports as report_api
from project_management.app.api.project_runs import ProjectRunWorker
from project_management.tests.history_persistence_fixtures import (
    daily_note_edit, history_fixture, publication_file_bytes, ref_for,
)
from project_management.tests.report_draft_fixtures import draft_command
from project_management.tests.test_daily_reprepare_backend import refresh_manual_service
from project_management.tests.test_report_standup import standup_document


@pytest.mark.django_db(transaction=True)
def test_manual_recapture_keeps_source_equality_and_discloses_backfilled_meeting_time(tmp_path):
    fixture = history_fixture(tmp_path, document=standup_document())
    args = fixture.actor, fixture.project.id, fixture.stage.id
    preparation, runs = refresh_manual_service(fixture, ({
        'stable_id': 'ALPHA-1', 'summary': 'Validation follow-up', 'status': 'In Analysis',
        'comments': {'201': {'id': '201', 'body': 'Waiting for lab validation.'}},
    },))
    worker = ProjectRunWorker(runs, daily_preparation_service=preparation)
    drafts = fixture.draft_service

    def prepare(index, day, baseline):
        admitted = preparation.prepare(
            *args, command_id=draft_command(index), series_id=fixture.series.series_id,
            meeting_date=day, expected_series_policy_hash=fixture.series.revision_hash,
            expected_baseline_ref=baseline, template_selection=fixture.template_selection,
            source_mode='refresh', capture_id=None, analysis_mode='manual_only',
            acknowledge_gap_draft_ids=(),
        )
        result = worker.execute(*args, admitted.operation_id)
        assert result.state == 'partial'
        return drafts.get(*args, result.draft_id)

    monday = prepare(14001, '2026-11-02', None)
    monday_observation = monday.authoring_context['current_observations'][0]
    assert monday_observation['source_state'] == 'initial'
    assert monday.snapshot.rows[0].pending_reason == 'summary_pending'
    assert not monday.authoring_context['notes']
    saved = drafts.save_authored(
        *args, monday.draft_id, command_id=draft_command(14002),
        expected_revision=monday.revision, expected_revision_hash=monday.revision_hash,
        edits=(daily_note_edit(14002, monday_observation['note_id'], 'Human: keep the lab follow-up.', '#aa0000', None),),
    )
    first = drafts.finalize_and_commit(
        *args, monday.draft_id, command_id=draft_command(14003), expected_revision=saved.revision,
    )
    original = publication_file_bytes(fixture, first)
    tuesday = prepare(14004, '2026-11-03', ref_for(first))
    observation = tuesday.authoring_context['current_observations'][0]

    assert monday.snapshot.capture_id != tuesday.snapshot.capture_id
    assert monday_observation['source_hash'] == observation['source_hash']
    assert observation['source_state'] == 'unchanged'
    assert observation['accepted_summary_ref'] is None
    assert tuesday.authoring_context['notes'] == saved.authoring_context['notes']
    assert all(note['note_id'] != observation['note_id'] for note in tuesday.authoring_context['notes'])
    second = drafts.finalize_and_commit(
        *args, tuesday.draft_id, command_id=draft_command(14005), expected_revision=tuesday.revision,
    )
    files = publication_file_bytes(fixture, second)
    text = files['report.txt'].decode('utf-8')
    assert 'ww45.1(In Analysis): Human: keep the lab follow-up.' in text
    assert 'ww45.2(In Analysis): Source date differs from meeting date' in text
    assert 'ww45.2(In Analysis): No source change' not in text
    assert text.count('Human: keep the lab follow-up.') == 1
    assert b'#aa0000' in files['report.html']
    assert publication_file_bytes(fixture, first) == original
    exports = report_api.ReportExportService(drafts)
    markdown = exports.publication(*args, second.manifest.publication_id, format_name='markdown')
    spreadsheet = exports.publication(*args, second.manifest.publication_id, format_name='xlsx')
    assert 'Source date differs from meeting date' in markdown.content.decode('utf-8')
    workbook = load_workbook(BytesIO(spreadsheet.content), read_only=True)
    try:
        assert any('Source date differs from meeting date' in str(value) for sheet in workbook for row in sheet.values for value in row)
    finally:
        workbook.close()
    assert publication_file_bytes(fixture, first) == original
    assert publication_file_bytes(fixture, second) == files

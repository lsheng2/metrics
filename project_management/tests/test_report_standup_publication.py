from io import BytesIO
from zipfile import ZipFile
import pytest

from project_management.app.api import ProjectActor, reports as report_api
from project_management.tests.history_persistence_fixtures import (
    create_saved_daily, git_head, history_fixture, prepare_daily, publication_file_bytes, ref_for,
)
from project_management.tests.report_draft_fixtures import draft_command
from project_management.tests.test_report_standup import POLICY, standup_document


@pytest.mark.django_db(transaction=True)
def test_shouldPublishConciseSuccessorAndExportOriginalAuditWithoutChangingLegacy(tmp_path, monkeypatch):
    fixture = history_fixture(tmp_path)
    args = fixture.actor, fixture.project.id, fixture.stage.id
    drafts = fixture.draft_service
    day1 = prepare_daily(fixture, 1, '2026-11-02', None)
    saved1 = create_saved_daily(fixture, day1, 1, 'Monday human correction.', '#aa0000', draft_command(11001))
    first = drafts.finalize_and_commit(*args, saved1.draft_id,
                                      command_id=draft_command(11002), expected_revision=saved1.revision)
    original = publication_file_bytes(fixture, first)
    template = fixture.template_service.create(
        fixture.actor, fixture.project.id, command_id=draft_command(11003), name='Concise daily',
        document=standup_document(), fill_policy=POLICY,
    )
    fixture.template_selection = report_api.UserTemplateSelection(
        str(template.template_id), template.revision, template.revision_hash,
    )
    fixture.series = fixture.continuity.save_series_policy(
        *args, command_id=draft_command(11006), series_id=fixture.series.series_id,
        expected_revision=fixture.series.revision, expected_revision_hash=fixture.series.revision_hash,
        name=fixture.series.name, calendar=fixture.series.calendar,
        template_selection=fixture.template_selection,
    )
    fixture.source_reader.source_commit = git_head(fixture.archive_root, fixture.project.id, fixture.stage.id)
    day2 = prepare_daily(fixture, 2, '2026-11-03', ref_for(first))
    saved2 = create_saved_daily(fixture, day2, 2, 'Tuesday human follow-up.', '#0055aa', draft_command(11004))
    reopened = drafts.get(*args, saved2.draft_id)
    rendered = drafts.render(*args, reopened.draft_id, revision=reopened.revision)
    assert 'Monday human correction.' in rendered.plain_text
    assert 'Tuesday human follow-up.' in rendered.plain_text
    assert fixture.source_reader.snapshot.rows[0].what not in rendered.plain_text
    assert 'Evidence refs:' not in rendered.plain_text
    assert '#aa0000' in rendered.html_fragment and '#0055aa' in rendered.html_fragment
    second = drafts.finalize_and_commit(*args, saved2.draft_id,
                                       command_id=draft_command(11005), expected_revision=reopened.revision)
    files = publication_file_bytes(fixture, second)
    before = git_head(fixture.archive_root, fixture.project.id, fixture.stage.id)

    def forbidden(*args, **kwargs):
        raise AssertionError('Audit export must not render, refresh or finalize')

    monkeypatch.setattr(drafts.renderer, 'render', forbidden)
    monkeypatch.setattr(drafts.renderer, 'render_pinned', forbidden)
    monkeypatch.setattr(fixture.source_reader, 'read', forbidden)
    monkeypatch.setattr(drafts, 'finalize_and_commit', forbidden)
    export = report_api.ReportExportService(drafts).publication(
        *args, second.manifest.publication_id, format_name='audit_zip',
    )
    with ZipFile(BytesIO(export.content)) as audit:
        for name, value in files.items():
            assert audit.read(name) == value
        assert 'Monday human correction.' in audit.read('edits.json').decode()
        assert 'Source snapshot' in audit.read('audit.html').decode()
    assert publication_file_bytes(fixture, first) == original
    assert publication_file_bytes(fixture, second) == files
    assert git_head(fixture.archive_root, fixture.project.id, fixture.stage.id) == before
    with pytest.raises(report_api.ReportError):
        drafts.read_publication_artifacts(ProjectActor('other'), fixture.project.id, fixture.stage.id,
                                          second.manifest.publication_id)

from dataclasses import replace
from hashlib import sha256
import importlib
from io import BytesIO
from uuid import uuid4

from openpyxl import load_workbook
import pytest

from project_management.app.api import ProjectActor
from project_management.app.domain.report_contracts import ReportError
from project_management.tests.history_persistence_fixtures import (
    create_saved_daily, git_head, history_fixture, prepare_daily, publication_file_bytes, ref_for,
)
from project_management.tests.report_draft_fixtures import draft_command


@pytest.mark.django_db(transaction=True)
def test_shouldExportVerifiedPublicationWithoutRendererOrAnyMutation(tmp_path, monkeypatch):
    cls = importlib.import_module('project_management.services.report_exports').ReportExportService
    fixture = history_fixture(tmp_path)
    source = fixture.source_reader.snapshot
    first = source.rows[0]
    third = replace(first, identity=replace(first.identity, stable_id='DEMO-103', display_key='DEMO-103'),
                    source_key=replace(first.source_key, stable_id='DEMO-103'),
                    title='Third independent ticket', status='In Analysis',
                    summary_ref=replace(first.summary_ref, summary_id='summary-103'))
    fixture.source_reader.snapshot = replace(source, rows=source.rows + (third,))
    args = (fixture.actor, fixture.project.id, fixture.stage.id)
    first_day = prepare_daily(fixture, 1, '2026-11-02', None)
    saved1 = create_saved_daily(fixture, first_day, 1, 'Day one red human note.', '#aa0000', draft_command(9010))
    publication1 = fixture.draft_service.finalize_and_commit(
        *args, saved1.draft_id, command_id=draft_command(9011), expected_revision=saved1.revision,
    )
    fixture.source_reader.source_commit = git_head(fixture.archive_root, fixture.project.id, fixture.stage.id)
    second_day = prepare_daily(fixture, 2, '2026-11-03', ref_for(publication1))
    saved2 = create_saved_daily(fixture, second_day, 2, 'Day two blue human note.', '#0055aa', draft_command(9020))
    exporter = cls(fixture.draft_service)
    draft_export = exporter.draft(*args, saved2.draft_id, revision=saved2.revision, format_name='markdown')
    assert 'Day two blue human note.' in draft_export.content.decode()
    publication2 = fixture.draft_service.finalize_and_commit(
        *args, saved2.draft_id, command_id=draft_command(9021), expected_revision=saved2.revision,
    )
    original = publication_file_bytes(fixture, publication2)
    original_first = publication_file_bytes(fixture, publication1)
    before_head = git_head(fixture.archive_root, fixture.project.id, fixture.stage.id)

    def forbidden(*args, **kwargs):
        raise AssertionError('Published export must not rebuild source, render or publish')

    monkeypatch.setattr(fixture.draft_service.renderer, 'render', forbidden)
    monkeypatch.setattr(fixture.draft_service.renderer, 'render_pinned', forbidden)
    monkeypatch.setattr(fixture.source_reader, 'read', forbidden)
    monkeypatch.setattr(fixture.draft_service, 'finalize_and_commit', forbidden)
    markdown = exporter.publication(*args, publication2.manifest.publication_id, format_name='markdown')
    excel = exporter.publication(*args, publication2.manifest.publication_id, format_name='xlsx')
    assert markdown.source_sha256 == excel.source_sha256 == sha256(original['report.html']).hexdigest()
    text = markdown.content.decode()
    for marker in ('DEMO-101', 'DEMO-102', 'DEMO-103', 'Day one red human note.',
                   'Day two blue human note.', 'ww45.1(In Progress):', 'ww45.2(In Progress):'):
        assert marker in text
    workbook = load_workbook(BytesIO(excel.content))
    values = '\n'.join(str(cell.value) for sheet in workbook for row in sheet for cell in row if cell.value)
    assert 'Day one red human note.' in values and 'Day two blue human note.' in values
    assert 'In Analysis' in values
    assert publication_file_bytes(fixture, publication2) == original
    assert publication_file_bytes(fixture, publication1) == original_first
    assert git_head(fixture.archive_root, fixture.project.id, fixture.stage.id) == before_head
    with pytest.raises(ReportError) as hidden:
        exporter.publication(ProjectActor('other-owner'), fixture.project.id, fixture.stage.id,
                             publication2.manifest.publication_id, format_name='markdown')
    assert hidden.value.code == 'REPORT_NOT_FOUND'

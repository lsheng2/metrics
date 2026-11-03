from dataclasses import replace

import pytest

from project_management.app.api import reports as report_api
from project_management.app.domain.contracts import ProjectActor
from project_management.app.domain.captures import ArchiveError
from project_management.tests.report_draft_fixtures import (
    DraftArchive,
    FixedClock,
    StaticSourceReader,
    draft_command,
    draft_selection,
)
from project_management.tests.report_render_fixtures import daily_template


def build_service(environment):
    return report_api.ReportDraftService(
        environment,
        StaticSourceReader(source_commit=environment.repository.head(), rule_hash=environment.stage.definition_hash),
        report_api.ReportRenderer(),
        clock=FixedClock(),
    )


def test_wrong_owner_archived_write_and_authorized_download_boundaries(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    service = build_service(environment)
    draft = service.create(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(200),
        selection=draft_selection(),
        template=daily_template(),
    )
    publication = service.finalize_and_commit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(201),
        expected_revision=1,
    )
    wrong_owner = ProjectActor('other-owner')

    with pytest.raises(report_api.ReportError) as wrong_get:
        service.get_publication(wrong_owner, environment.project.id, environment.stage.id, publication.manifest.publication_id)
    with pytest.raises(report_api.ReportError) as wrong_artifact:
        service.read_artifact(wrong_owner, environment.project.id, environment.stage.id, publication.manifest.publication_id, 'report.html')

    environment.project = replace(environment.project, archived=True)
    assert service.read_artifact(
        environment.actor, environment.project.id, environment.stage.id, publication.manifest.publication_id, 'html'
    ).startswith(b'<!doctype html>')
    with pytest.raises(report_api.ReportError) as archived_write:
        service.finalize_and_commit(
            environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
            command_id=draft_command(202), expected_revision=1,
        )

    assert wrong_get.value.code == 'REPORT_NOT_FOUND'
    assert wrong_artifact.value.code == 'REPORT_NOT_FOUND'
    assert archived_write.value.code == 'REPORT_SOURCE_CHANGED'


def test_publication_namespace_rejects_wrong_paths_and_unknown_names(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    service = build_service(environment)
    draft = service.create(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(210),
        selection=draft_selection(),
        template=daily_template(),
    )

    with pytest.raises(report_api.ReportError):
        service.read_artifact(environment.actor, environment.project.id, environment.stage.id, draft.draft_id, '../manifest.json')
    with pytest.raises(ArchiveError):
        environment.repository.append_record(
            draft.draft_id,
            'captures',
            {f'report_publications/{draft.draft_id}/manifest.json': b'{}'},
            expected_head=environment.repository.head(),
            record_fingerprint='0' * 64,
        )

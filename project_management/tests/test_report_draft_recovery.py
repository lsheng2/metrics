from dataclasses import replace

import pytest

from project_management.app.api import reports as report_api
from project_management.app.domain.captures import ArchiveError
from project_management.tests.report_draft_fixtures import (
    DraftArchive,
    FixedClock,
    StaticSourceReader,
    draft_command,
    draft_root,
    draft_selection,
)
from project_management.tests.report_render_fixtures import daily_template


def build_service(environment, *, source=None, renderer=None):
    return report_api.ReportDraftService(
        environment,
        source or StaticSourceReader(source_commit=environment.repository.head(), rule_hash=environment.stage.definition_hash),
        renderer or report_api.ReportRenderer(),
        clock=FixedClock(),
    )


def test_create_replay_repairs_missing_current_after_completed_revision_without_source_reread(tmp_path, monkeypatch):
    environment = DraftArchive(tmp_path / 'archive-root')
    source = StaticSourceReader(source_commit=environment.repository.head(), rule_hash=environment.stage.definition_hash)
    service = build_service(environment, source=source)
    from project_management.storage import report_drafts as draft_storage

    original_write = draft_storage.write_bytes
    failure = {'armed': True}

    def fail_current_once(root, relative, data, *, immutable=False, conflict_code='ARCHIVE_CAPTURE_CONFLICT'):
        if failure['armed'] and relative == 'current.json':
            failure['armed'] = False
            raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE')
        return original_write(root, relative, data, immutable=immutable, conflict_code=conflict_code)

    monkeypatch.setattr(draft_storage, 'write_bytes', fail_current_once)
    selection = draft_selection()
    with pytest.raises(report_api.ReportError):
        service.create(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            command_id=draft_command(80),
            selection=selection,
            template=daily_template(),
        )

    draft_id = next((environment.repository.runtime / 'report-drafts').iterdir()).name
    assert not (draft_root(environment, draft_id) / 'current.json').exists()

    replay = service.create(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(80),
        selection=selection,
        template=daily_template(),
    )

    assert (replay.revision, replay.created_at, source.calls) == (1, '2026-11-02T03:00:00+00:00', 1)
    assert (draft_root(environment, replay.draft_id) / 'current.json').exists()


def test_draft_render_binds_saved_revision_hash_in_dto_html_and_plain_text(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    service = build_service(environment)
    draft = service.create(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(81),
        selection=draft_selection(),
        template=daily_template(),
    )

    rendered = service.render(environment.actor, environment.project.id, environment.stage.id, draft.draft_id, revision=1)

    assert rendered.revision_hash == draft.revision_hash
    assert draft.revision_hash in rendered.html_fragment
    assert f"Revision hash: {draft.revision_hash}" in rendered.plain_text

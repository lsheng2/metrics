from concurrent.futures import ThreadPoolExecutor
from threading import Event, get_ident

import pytest

from project_management.app.api import ProjectActor
from project_management.app.api import reports as report_api
from project_management.app.domain.captures import ArchiveError
from project_management.tests.history_persistence_fixtures import history_fixture, git_head
from project_management.tests.report_draft_fixtures import draft_command


@pytest.mark.django_db(transaction=True)
def test_borrowed_snapshot_never_grants_foreign_or_write_access(tmp_path):
    fixture = history_fixture(tmp_path)
    with fixture.archive._report_read_view(fixture.actor, fixture.project.id, fixture.stage.id) as view:
        with pytest.raises(report_api.ReportError) as denied:
            fixture.draft_service.get(ProjectActor('another-owner'), fixture.project.id, fixture.stage.id,
                                      draft_command(18100), _read_view=view)
        assert denied.value.code == 'REPORT_NOT_FOUND'
        with pytest.raises(ArchiveError) as writer:
            with fixture.archive._report_repository(fixture.actor, fixture.project.id, fixture.stage.id,
                                                    write=True, _read_view=view):
                pytest.fail('Borrowed read scope exposed a writer')
        assert writer.value.code == 'ARCHIVE_MANIFEST_INVALID'
    with pytest.raises(report_api.ReportError) as expired:
        fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id,
                                  draft_command(18100), _read_view=view)
    assert expired.value.code == 'REPORT_STORAGE_UNAVAILABLE'


@pytest.mark.django_db(transaction=True)
def test_two_readers_observe_writer_without_mixing_runtime_revisions(tmp_path, monkeypatch):
    from project_management.storage.report_drafts import ReportDraftStore

    fixture = history_fixture(tmp_path)
    service = fixture.draft_service
    draft = service.create_authored(
        fixture.actor, fixture.project.id, fixture.stage.id,
        command_id=draft_command(18110),
        selection=report_api.ReportSelection(capture_id=draft_command(18111)),
        template=report_api.AuthoringTemplateSelection('builtin', 'daily-standup', '2', {}),
    )
    head = git_head(fixture.archive_root, fixture.project.id, fixture.stage.id)
    entered, resume = Event(), Event()
    old_reader = [None]
    original = ReportDraftStore._state

    def intercepted(store, root):
        if get_ident() == old_reader[0]:
            entered.set()
            if not resume.wait(timeout=8):
                raise AssertionError('Reader handoff did not complete')
        return original(store, root)

    def read_old():
        old_reader[0] = get_ident()
        return service.get(fixture.actor, fixture.project.id, fixture.stage.id, draft.draft_id)

    monkeypatch.setattr(ReportDraftStore, '_state', intercepted)
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix='report-read-race') as pool:
        pending = pool.submit(read_old)
        try:
            assert entered.wait(timeout=5)
            saved = service.save_authored(
                fixture.actor, fixture.project.id, fixture.stage.id, draft.draft_id,
                command_id=draft_command(18112), expected_revision=draft.revision,
                expected_revision_hash=draft.revision_hash, edits=(),
            )
            current = pool.submit(service.get, fixture.actor, fixture.project.id, fixture.stage.id, draft.draft_id).result(timeout=5)
            assert current.revision == saved.revision == 2
        finally:
            resume.set()
        with pytest.raises(report_api.ReportError) as moved:
            pending.result(timeout=5)
        assert moved.value.code == 'REPORT_REVISION_CONFLICT'
    with pytest.raises(report_api.ReportError) as stale:
        service.save_authored(
            fixture.actor, fixture.project.id, fixture.stage.id, draft.draft_id,
            command_id=draft_command(18113), expected_revision=draft.revision,
            expected_revision_hash=draft.revision_hash, edits=(),
        )
    assert stale.value.code == 'REPORT_REVISION_CONFLICT'
    assert git_head(fixture.archive_root, fixture.project.id, fixture.stage.id) == head

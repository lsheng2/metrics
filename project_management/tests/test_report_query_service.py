from unittest.mock import patch

import pytest

from project_management.app.api import reports as report_api
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.report_publication_contracts import PUBLICATION_FILES
from project_management.storage.git import GitRunner
from project_management.tests.history_persistence_fixtures import git_head, history_fixture, publication_file_bytes
from project_management.tests.report_draft_fixtures import draft_command


@pytest.mark.django_db(transaction=True)
def test_workspace_reads_original_packets_once_with_bounded_git(tmp_path):
    from project_management.app.api.report_queries import ReportQueryService, ReportWorkspaceQuery

    fixture = history_fixture(tmp_path)
    publications = []
    for index in range(3):
        fixture.source_reader.source_commit = git_head(fixture.archive_root, fixture.project.id, fixture.stage.id)
        draft = fixture.draft_service.create_authored(
            fixture.actor, fixture.project.id, fixture.stage.id, command_id=draft_command(17000 + index * 2),
            selection=report_api.ReportSelection(capture_id=draft_command(17100 + index)),
            template=report_api.AuthoringTemplateSelection('builtin', 'daily-standup', '2', {}),
        )
        publication = fixture.draft_service.finalize_and_commit(
            fixture.actor, fixture.project.id, fixture.stage.id, draft.draft_id,
            command_id=draft_command(17001 + index * 2), expected_revision=draft.revision,
        )
        publications.append(publication)
    originals = {item.manifest.publication_id: publication_file_bytes(fixture, item) for item in publications}
    calls = []
    original = GitRunner.run

    def counted(self, arguments, **kwargs):
        calls.append(tuple(arguments))
        return original(self, arguments, **kwargs)

    service = ReportQueryService(fixture.archive, fixture.draft_service)
    from project_management.storage.archive_read_view import GitArchiveReadView
    from project_management.storage import publication_validation

    validator = publication_validation.validate_publication_files
    validated = []

    def verified(publication_id, *args, **kwargs):
        validated.append(publication_id)
        return validator(publication_id, *args, **kwargs)

    with patch.object(GitRunner, 'run', counted), \
            patch.object(GitArchiveReadView, 'checkout_state', side_effect=AssertionError('Unrendered checkout diagnostic')), \
            patch.object(publication_validation, 'validate_publication_files', verified):
        page = service.workspace(fixture.actor, fixture.project.id, fixture.stage.id, query=ReportWorkspaceQuery())
    assert len(page.publications.items) == 3
    assert len(page.drafts.items) == 3
    assert {item.state for item in page.drafts.items} == {'finalized'}
    assert len(calls) <= 5, calls
    assert sum(arguments[0] == 'show' for arguments in calls) == 1
    assert sorted(item.manifest.publication_id for item in page.publications.items) == sorted(originals)
    assert sorted(validated) == sorted(originals)
    for item in publications:
        assert publication_file_bytes(fixture, item) == originals[item.manifest.publication_id]
    from project_management.services.report_daily_baseline import verified_daily_head

    calls.clear()
    with patch.object(GitRunner, 'run', counted):
        with fixture.archive._report_repository(fixture.actor, fixture.project.id, fixture.stage.id) as view:
            assert verified_daily_head(view, fixture.series.series_id) is None
    assert len(calls) <= 5, calls


@pytest.mark.django_db(transaction=True)
def test_query_does_not_turn_corrupt_runtime_into_an_empty_page(tmp_path):
    from project_management.app.api.report_queries import ReportQueryService, ReportWorkspaceQuery

    fixture = history_fixture(tmp_path)
    draft = fixture.draft_service.create_authored(
        fixture.actor, fixture.project.id, fixture.stage.id, command_id=draft_command(17200),
        selection=report_api.ReportSelection(capture_id=draft_command(17201)),
        template=report_api.AuthoringTemplateSelection('builtin', 'daily-standup', '2', {}),
    )
    path = fixture.archive_root / 'projects' / fixture.project.id / 'stages' / fixture.stage.id / 'runtime'
    (path / 'report-drafts' / draft.draft_id / 'current.json').write_text('{}', encoding='utf-8')
    service = ReportQueryService(fixture.archive, fixture.draft_service)
    with pytest.raises(report_api.ReportError) as error:
        service.workspace(fixture.actor, fixture.project.id, fixture.stage.id, query=ReportWorkspaceQuery())
    assert error.value.code == 'REPORT_ARTIFACT_INVALID'


@pytest.mark.django_db(transaction=True)
def test_read_rejects_runtime_head_moving_during_packet_validation(tmp_path, monkeypatch):
    from project_management.storage.report_drafts import ReportDraftStore
    from project_management.app.domain.capture_values import canonical_bytes

    fixture = history_fixture(tmp_path)
    draft = fixture.draft_service.create_authored(
        fixture.actor, fixture.project.id, fixture.stage.id, command_id=draft_command(17210),
        selection=report_api.ReportSelection(capture_id=draft_command(17211)),
        template=report_api.AuthoringTemplateSelection('builtin', 'daily-standup', '2', {}),
    )
    original = ReportDraftStore._state

    def moving(store, root):
        state = original(store, root)
        (root / 'current.json').write_bytes(canonical_bytes({
            'schema_version': 1, 'revision': draft.revision + 1, 'revision_hash': 'f' * 64,
        }))
        return state

    monkeypatch.setattr(ReportDraftStore, '_state', moving)
    with pytest.raises(report_api.ReportError) as error:
        fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, draft.draft_id)
    assert error.value.code == 'REPORT_REVISION_CONFLICT'

import stat
import unittest

import pytest

from project_management.tests.capture_archive_fixtures import CaptureArchiveScenario
from project_management.app.api import reports as report_api
from project_management.app.domain.captures import ArchiveError
from project_management.storage.git import GitResult
from project_management.tests.report_draft_fixtures import (
    DraftArchive,
    FixedClock,
    StaticSourceReader,
    draft_command,
    draft_note,
    draft_selection,
    draft_root,
)
from project_management.tests.report_render_fixtures import daily_template


def build_service(environment):
    return report_api.ReportDraftService(
        environment,
        StaticSourceReader(source_commit=environment.repository.head(), rule_hash=environment.stage.definition_hash),
        report_api.ReportRenderer(),
        clock=FixedClock(),
    )


def test_shouldListDraftsWithBoundedQueryAndPropagateCorruption(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    service = build_service(environment)
    first = service.create(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(300),
        selection=draft_selection(),
        template=daily_template(),
    )
    second = service.create(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(301),
        selection=draft_selection(),
        template=daily_template(),
    )
    saved = service.save(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        second.draft_id,
        command_id=draft_command(302),
        expected_revision=1,
        edits=(draft_note(30),),
        template=daily_template(),
    )

    page = service.list_drafts(environment.actor, environment.project.id, environment.stage.id, limit=1)
    next_page = service.list_drafts(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        limit=1,
        offset=page.next_offset,
    )

    actual = tuple((item.draft_id, item.revision) for item in page.items + next_page.items)
    expected = tuple(sorted(((first.draft_id, 1), (second.draft_id, saved.revision))))
    listed_saved = next(item for item in page.items + next_page.items if item.draft_id == second.draft_id)

    assert actual == expected
    assert (page.next_offset, next_page.next_offset) == (1, None)
    assert listed_saved.revision_hash == saved.revision_hash
    assert listed_saved.template_id == 'daily-standup'
    assert listed_saved.source_as_of == saved.snapshot.source_as_of

    with pytest.raises(report_api.ReportError) as bad_limit:
        service.list_drafts(environment.actor, environment.project.id, environment.stage.id, limit=0)
    with pytest.raises(report_api.ReportError) as bad_offset:
        service.list_drafts(environment.actor, environment.project.id, environment.stage.id, offset=-1)

    assert bad_limit.value.code == 'REPORT_INVALID'
    assert bad_offset.value.code == 'REPORT_INVALID'

    (draft_root(environment, first.draft_id) / 'current.json').write_text('{}', encoding='utf-8')
    with pytest.raises(report_api.ReportError) as corrupt:
        service.list_drafts(environment.actor, environment.project.id, environment.stage.id)
    assert corrupt.value.code == 'REPORT_ARTIFACT_INVALID'


def test_shouldListPublicationsByLexicographicIdentityWithPagination(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    service = build_service(environment)
    first = service.create(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(310),
        selection=draft_selection(),
        template=daily_template(),
    )
    second = service.create(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(311),
        selection=report_api.ReportSelection(
            capture_id=draft_selection().capture_id,
            purpose='historical_export',
            timezone='Asia/Shanghai',
        ),
        template=daily_template(),
    )
    first_publication = service.finalize_and_commit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        first.draft_id,
        command_id=draft_command(312),
        expected_revision=1,
    )
    second_publication = service.finalize_and_commit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        second.draft_id,
        command_id=draft_command(313),
        expected_revision=1,
    )

    expected_ids = tuple(sorted([
        first_publication.manifest.publication_id,
        second_publication.manifest.publication_id,
    ]))
    first_page = service.list_publications(environment.actor, environment.project.id, environment.stage.id, limit=1)
    second_page = service.list_publications(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        limit=1,
        offset=first_page.next_offset,
    )

    assert tuple(item.manifest.publication_id for item in first_page.items + second_page.items) == expected_ids
    assert first_page.next_offset == 1
    assert second_page.next_offset is None


class FakeDirectoryInfo:
    st_mode = stat.S_IFDIR


class FakeDraftEntry:
    def __init__(self, name):
        self.name = name

    def lstat(self):
        return FakeDirectoryInfo()

    def is_symlink(self):
        return False


class FakeDraftRoot:
    def exists(self):
        return True

    def resolve(self):
        return self

    def lstat(self):
        return FakeDirectoryInfo()

    def is_symlink(self):
        return False

    @property
    def parent(self):
        return self

    def is_relative_to(self, other):
        return True

    def iterdir(self):
        for index in range(1001):
            yield FakeDraftEntry(f'aaaaaaaa-aaaa-4aaa-8aaa-{index:012d}')
        raise AssertionError('draft listing consumed past bounded lookahead')


class FakeRuntime:
    def __truediv__(self, name):
        assert name == 'report-drafts'
        return FakeDraftRoot()


def test_shouldStopDraftEnumerationAtConfiguredLookahead(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    environment.repository.runtime = FakeRuntime()
    service = build_service(environment)

    with pytest.raises(report_api.ReportError) as error:
        service.list_drafts(environment.actor, environment.project.id, environment.stage.id)

    assert error.value.code == 'REPORT_LIMIT'


def test_shouldStopPublicationEnumerationAtConfiguredLookahead(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')

    def bounded_publication_ids(*, limit):
        assert limit == 1001
        for index in range(1001):
            yield f'bbbbbbbb-bbbb-4bbb-8bbb-{index:012d}'
        raise AssertionError('publication listing consumed past bounded lookahead')

    environment.repository.list_report_publication_ids = bounded_publication_ids
    service = build_service(environment)

    with pytest.raises(report_api.ReportError) as error:
        service.list_publications(environment.actor, environment.project.id, environment.stage.id)

    assert error.value.code == 'REPORT_LIMIT'


class TestReportListingGitBoundary(CaptureArchiveScenario, unittest.TestCase):
    def repository(self, root, archive):
        return archive.repository_factory.open(archive.config, self.project, self.stage, self.actor.subject)

    def test_shouldListCommittedPublicationIdsThroughBoundedGitDirectoryRead(self):
        with self.archive_service() as (root, archive):
            archive.initialize_stage(self.actor, self.project.id, self.stage.id)
            head = self.git_text(self.archive_path(root), 'rev-parse', 'main')
            service = report_api.ReportDraftService(
                archive,
                StaticSourceReader(source_commit=head, rule_hash=self.stage.definition_hash),
                report_api.ReportRenderer(),
                clock=FixedClock(),
            )
            draft = service.create(
                self.actor,
                self.project.id,
                self.stage.id,
                command_id=draft_command(900),
                selection=report_api.ReportSelection(
                    capture_id=draft_selection().capture_id,
                    purpose='historical_export',
                    timezone='Asia/Shanghai',
                ),
                template=daily_template(),
            )
            publication = service.finalize_and_commit(
                self.actor,
                self.project.id,
                self.stage.id,
                draft.draft_id,
                command_id=draft_command(901),
                expected_revision=1,
            )

            page = service.list_publications(self.actor, self.project.id, self.stage.id)

            self.assertEqual((publication.manifest.publication_id,), tuple(
                item.manifest.publication_id for item in page.items
            ))
            self.assertIsNone(page.next_offset)

    def test_shouldDistinguishAbsentPublicationTreeFromGitFailuresAndOverflow(self):
        with self.archive_service() as (root, archive):
            archive.initialize_stage(self.actor, self.project.id, self.stage.id)
            repository = self.repository(root, archive)
            self.assertEqual((), repository.list_report_publication_ids(limit=1001))

            repository.git = FakePublicationGit(parent_returncode=1)
            with self.assertRaises(ArchiveError) as git_error:
                repository.list_report_publication_ids(limit=1001)
            self.assertEqual('ARCHIVE_MANIFEST_INVALID', git_error.exception.code)

            repository.git = FakePublicationGit(children=[
                f'bbbbbbbb-bbbb-4bbb-8bbb-{index:012d}' for index in range(1002)
            ])
            with self.assertRaises(ArchiveError) as overflow:
                repository.list_report_publication_ids(limit=1001)
            self.assertEqual('ARCHIVE_QUOTA_EXCEEDED', overflow.exception.code)

            repository.git = FakePublicationGit(children=['not-a-uuid'])
            with self.assertRaises(ArchiveError) as malformed:
                repository.list_report_publication_ids(limit=1001)
            self.assertEqual('ARCHIVE_MANIFEST_INVALID', malformed.exception.code)


class FakePublicationGit:
    def __init__(self, *, parent_returncode=0, children=()):
        self.parent_returncode = parent_returncode
        self.children = tuple(children)
        self.calls = []

    def run(self, arguments, *, check=True, input_data=None, extra_env=None, output_limit=None, output_limit_code='ARCHIVE_STORAGE_UNAVAILABLE'):
        self.calls.append((tuple(arguments), output_limit, output_limit_code))
        if arguments == ['ls-tree', '-z', '--name-only', 'main', 'report_publications']:
            return GitResult(self.parent_returncode, b'' if self.parent_returncode else b'report_publications\x00')
        if arguments == ['ls-tree', '-z', '--name-only', 'main:report_publications']:
            data = b''.join(item.encode('utf-8') + b'\0' for item in self.children)
            if output_limit is not None and len(data) > output_limit:
                raise ArchiveError(output_limit_code)
            return GitResult(0, data)
        raise AssertionError(arguments)

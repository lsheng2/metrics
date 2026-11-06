from contextlib import contextmanager, nullcontext
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import uuid

from project_management.app.domain.capture_values import canonical_bytes
from project_management.app.domain.captures import (
    ArchiveError, ArchiveLimits, ArchiveStorageConfig, CaptureMetadata, CaptureMetadataPage,
)
from project_management.app.domain.contracts import (
    ProjectActor,
    ProjectError,
    ProjectSummary,
    ScopeDescriptor,
    ScopeSelection,
    StageSummary,
)
from project_management.app.domain.report_contracts import ReportSelection
from project_management.app.spi.archive import CommitReceipt
from project_management.storage.locks import CombinedLocks
from project_management.storage.paths import read_bytes, safe_relative_path, write_bytes
from project_management.storage.staging import active_capture_path
from project_management.tests.report_render_fixtures import safe_snapshot


class FixedClock:
    def __init__(self):
        self._start = datetime(2026, 11, 2, 3, 0, 0, tzinfo=UTC)
        self._index = 0

    def __call__(self):
        value = self._start + timedelta(minutes=self._index)
        self._index += 1
        return value


class StaticSourceReader:
    def __init__(self, snapshot=None, *, source_commit='a' * 40, rule_hash='b' * 64):
        self.snapshot = snapshot or safe_snapshot(days=())
        self.source_commit = source_commit
        self.rule_hash = rule_hash
        self.calls = 0
        self.selections = []

    def read(self, actor, project_id, stage_id, selection: ReportSelection):
        self.calls += 1
        self.selections.append(selection)
        return self._snapshot(actor.subject, project_id, stage_id, selection, self.source_commit)

    def read_from_repository(self, actor, project, stage, repository, selection, head):
        self.calls += 1
        self.selections.append(selection)
        return self._snapshot(actor.subject, project.id, stage.id, selection, head)

    def membership(self, actor, project_id, stage_id, snapshot):
        from project_management.services.report_sources import ScopeMember, ScopeMembershipSnapshot

        return ScopeMembershipSnapshot(
            1,
            snapshot.capture_id,
            snapshot.source_commit,
            'a' * 64,
            snapshot.source_as_of,
            snapshot.rule_hash,
            'principal:archive-owner',
            'complete',
            len(snapshot.rows),
            len(snapshot.rows),
            tuple(ScopeMember(row.identity, row.source_key) for row in snapshot.rows),
            'b' * 64,
        )

    def _snapshot(self, owner_subject, project_id, stage_id, selection, source_commit):
        return valid_source_snapshot(
            replace(
                self.snapshot,
                project_id=project_id,
                stage_id=stage_id,
                owner_subject=owner_subject,
                rule_hash=self.rule_hash,
                source_commit=source_commit,
                capture_id=selection.capture_id,
                timezone=selection.timezone,
                baseline_publication_id=selection.baseline_publication_id,
            ),
            project_id=project_id,
            stage_id=stage_id,
            owner_subject=owner_subject,
            rule_hash=self.rule_hash,
            source_commit=source_commit,
            capture_id=selection.capture_id,
        )


class StageDraftRepository:
    def open_read_view(self):
        return nullcontext(self)

    def map_reads(self, function, items):
        return tuple(map(function, items))

    def read_files(self, requests):
        result = tuple(self.read_file(item.path, item.commit_id) for item in requests)
        if any(len(data) > item.max_bytes for data, item in zip(result, requests)):
            raise ArchiveError('ARCHIVE_QUOTA_EXCEEDED')
        return result

    def validated(self, key, load):
        return load()

    def __init__(self, root: Path, project, stage, owner_subject: str):
        self.root = root
        self.project = project
        self.stage = stage
        self.owner_subject = owner_subject
        self.stage_root = root / 'projects' / project.id / 'stages' / stage.id
        self.runtime = self.stage_root / 'runtime'
        self.archive = self.stage_root / 'archive'
        self.objects = self.stage_root / 'objects'
        self._head = 'a' * 40
        self._path_commits = {}
        self.fail_append_once = False
        self.fail_find_commit_once = False

    def verify_identity(self):
        return None

    def head(self):
        return self._head

    def initialize(self):
        self.stage_root.mkdir(parents=True, exist_ok=True)
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.archive.mkdir(parents=True, exist_ok=True)
        return self._head

    def append_record(self, record_id, namespace, files, *, expected_head, record_fingerprint):
        if self.fail_append_once:
            self.fail_append_once = False
            raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE')
        if namespace != 'report_publications':
            raise ArchiveError('UNSAFE_PATH')
        if self._head != expected_head:
            raise ArchiveError('ARCHIVE_CHAIN_CONFLICT')
        safe_relative_path(f'{namespace}/{record_id}/manifest.json')
        commit = f'{len(set(self._path_commits.values())) + 1:040x}'
        for path, data in files.items():
            write_bytes(self.archive, path, bytes(data), immutable=True)
            self._path_commits[path] = commit
        parent = self._head
        self._head = commit
        return CommitReceipt(commit, parent, 'f' * 40, record_fingerprint, 'current')

    def read_file(self, git_path: str, commit: str = 'main') -> bytes:
        if commit != 'main' and self._path_commits.get(git_path) != commit:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        return read_bytes(self.archive, git_path)

    def list_files(self, prefix: str, commit: str = 'main') -> tuple[str, ...]:
        safe_relative_path(prefix)
        return tuple(sorted(path for path in self._path_commits if path.startswith(prefix)))

    def list_report_publication_ids(self, *, limit: int) -> tuple[str, ...]:
        ids = []
        for path in sorted(self._path_commits):
            parts = path.split('/')
            if len(parts) == 3 and parts[0] == 'report_publications' and parts[2] == 'manifest.json':
                ids.append(parts[1])
                if len(ids) > limit:
                    break
        return tuple(ids)

    def commit_for_path(self, git_path: str) -> str:
        commit = self.find_commit_for_path(git_path)
        if commit is None:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        return commit

    def find_commit_for_path(self, git_path: str, commit: str = 'main') -> str | None:
        if self.fail_find_commit_once:
            self.fail_find_commit_once = False
            raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE')
        try:
            return self._path_commits[git_path]
        except KeyError:
            return None

    def checkout_state(self, commit_id: str) -> str:
        return 'current' if commit_id == self._head else 'stale'

    def publication_source_chain(self, source_key):
        return self._publication_source_chain(source_key)


class DraftArchive:
    def _capture_read_requests(self, view, after):
        return ()

    @contextmanager
    def _report_read_view(self, actor, project_id, stage_id, *, allow_absent=False):
        with self._report_repository(actor, project_id, stage_id) as repository:
            yield repository

    def __init__(self, root: Path, *, limits=None, archived=False, source_status='current'):
        self.actor = ProjectActor('archive-owner')
        self.project = ProjectSummary(str(uuid.uuid4()), 'alpha', 'Alpha', archived, datetime.now(UTC))
        descriptor = ScopeDescriptor(
            provider_id='jira',
            profile_id='alpha-jira',
            endpoint='https://tracker.example.test/jira',
            source_ref='scope:1',
            query_kind='jql',
            query='project = ALPHA',
            source_version='query-version-1',
        )
        self.stage = StageSummary(
            id=str(uuid.uuid4()),
            key='release-1',
            name='Release 1',
            selection=ScopeSelection('alpha-jira', 1),
            descriptor=descriptor,
            definition_hash=descriptor.definition_hash(),
            created_at=datetime.now(UTC),
            source_status=source_status,
        )
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.config = ArchiveStorageConfig(
            root,
            'Archive Test',
            'archive@example.test',
            limits or self.limits(),
        )
        self.repository = StageDraftRepository(root, self.project, self.stage, self.actor.subject)
        self.repository.config = self.config
        self.repository.initialize()
        self.root_id = str(uuid.uuid4())

    def limits(self, **overrides):
        values = {
            'max_root_bytes': 64 * 1024 * 1024,
            'max_root_files': 10000,
            'max_stage_bytes': 32 * 1024 * 1024,
            'max_stage_files': 5000,
            'max_capture_bytes': 8 * 1024 * 1024,
            'max_capture_files': 1000,
            'max_raw_page_bytes': 1024 * 1024,
            'max_object_bytes': 2 * 1024 * 1024,
        }
        values.update(overrides)
        return ArchiveLimits(**values)

    @contextmanager
    def _report_repository(self, actor, project_id, stage_id, *, write=False, _read_view=None):
        project, stage = self._stage_for_write(actor, project_id, stage_id) if write else self._stage_for_read(actor, project_id, stage_id)
        if _read_view is not None:
            if write or _read_view.root != self.root or _read_view.owner_subject != actor.subject:
                raise ArchiveError('ARCHIVE_IDENTITY_MISMATCH')
            yield _read_view
            return
        if write:
            with self._locks(project, stage):
                self._stage_for_write(actor, project_id, stage_id)
                if (self.repository.runtime / active_capture_path(self.repository.runtime)).exists():
                    raise ArchiveError('ARCHIVE_BUSY')
                yield self.repository
        else:
            yield self.repository

    def stage_archive_status(self, actor, project_id, stage_id):
        self._stage_for_read(actor, project_id, stage_id)
        return 'ready' if self.repository.stage_root.exists() else 'absent'

    def list_capture_metadata(self, actor, project_id, stage_id, *, limit=100, after=None, _read_view=None, allow_absent=False):
        page = self.list_captures(actor, project_id, stage_id, limit=limit, after=after)
        return CaptureMetadataPage(
            tuple(CaptureMetadata(item, safe_snapshot().source_as_of) for item in page.items), page.next_cursor,
        )

    def _stage_for_read(self, actor, project_id, stage_id):
        if actor.subject != self.actor.subject or project_id != self.project.id or stage_id != self.stage.id:
            raise ProjectError('PROJECT_NOT_FOUND')
        return self.project, self.stage

    def _stage_for_write(self, actor, project_id, stage_id):
        project, stage = self._stage_for_read(actor, project_id, stage_id)
        if project.archived:
            raise ProjectError('PROJECT_ARCHIVED')
        if stage.source_status != 'current':
            raise ProjectError('SOURCE_CHANGED')
        return project, stage

    def _locks(self, project, stage):
        return CombinedLocks(self.config.root / 'budget.lock', self.repository.runtime / 'archive.lock')

    def _root_id(self):
        return self.root_id


def draft_selection() -> ReportSelection:
    return ReportSelection(capture_id=str(uuid.uuid4()), timezone='Asia/Shanghai')


def draft_command(value: int) -> str:
    return f'bbbbbbbb-bbbb-4bbb-8bbb-{value:012d}'


def draft_note(value: int, text='Meeting note from review.'):
    from project_management.app.api import reports as report_api

    return report_api.ReportEdit(
        f'cccccccc-cccc-4ccc-8ccc-{value:012d}',
        'note',
        {'scope': 'report'},
        text,
        author='browser supplied author',
        edited_at='1999-01-01T00:00:00Z',
    )


def current_payload(revision, revision_hash):
    return canonical_bytes({'revision': revision, 'revision_hash': revision_hash, 'schema_version': 1})


def draft_root(environment: DraftArchive, draft_id: str) -> Path:
    return environment.repository.runtime / 'report-drafts' / draft_id


def valid_source_snapshot(snapshot, *, project_id, stage_id, owner_subject, rule_hash, source_commit, capture_id):
    rows = tuple(_valid_row(row, rule_hash, capture_id, index) for index, row in enumerate(snapshot.rows, 1))
    row_by_source = {row.identity.stable_id: row for row in rows}
    events = tuple(_valid_event(event, row_by_source, rule_hash, index) for index, event in enumerate(snapshot.events, 1))
    days = tuple(_valid_day(day, row_by_source, rule_hash, capture_id, index) for index, day in enumerate(snapshot.days, 1))
    return replace(
        snapshot,
        project_id=project_id,
        stage_id=stage_id,
        owner_subject=owner_subject,
        rule_hash=rule_hash,
        source_commit=source_commit,
        capture_id=capture_id,
        comparison_policy_hash='c' * 64,
        rows=rows,
        events=events,
        days=days,
    )


def _valid_row(row, rule_hash, capture_id, index):
    source_key = replace(row.source_key, rule_hash=rule_hash)
    summary_ref = None
    if row.summary_ref is not None:
        summary_ref = replace(
            row.summary_ref,
            target_capture_id=capture_id,
            source_hash=f'{index:064x}',
            input_hash=f'{index + 10:064x}',
            result_hash=f'{index + 20:064x}',
            owning_commit=f'{index:040x}',
        )
    return replace(
        row,
        source_key=source_key,
        source_hash=f'{index + 30:064x}',
        summary_ref=summary_ref,
    )


def _valid_event(event, row_by_source, rule_hash, index):
    source_key = replace(event.source_key, rule_hash=rule_hash)
    return replace(event, event_id=f'event-{index}', source_key=source_key)


def _valid_day(day, row_by_source, rule_hash, capture_id, index):
    rows = tuple(_valid_row(row, rule_hash, capture_id, index + offset)
                 for offset, row in enumerate(day.rows, 1))
    events = tuple(_valid_event(event, row_by_source, rule_hash, index + offset) for offset, event in enumerate(day.events, 1))
    return replace(day, rows=rows, events=events)

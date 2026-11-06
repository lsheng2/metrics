from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from project_management.services.capture_archive import CaptureArchiveService
from project_management.tests.capture_archive_fixtures import ProjectApiStub


class MemoryGit:
    def __init__(self, repository):
        self.repository = repository

    def run(self, arguments, *, check=True, input_data=None, extra_env=None):
        if arguments[:4] == ['log', '-n', '1', '--format=%H']:
            path = arguments[-1]
            commit = self.repository.commits.get(path, self.repository.commit)
            return SimpleNamespace(returncode=0, stdout=f'{commit}\n'.encode('ascii'))
        return SimpleNamespace(returncode=1, stdout=b'')


class MemoryRepository:
    def __init__(self, project, stage, files, *, head='c' * 40):
        self.project = project
        self.stage = stage
        self.owner_subject = None
        self.files = dict(files)
        self.commit = head
        self.commits = {path: head for path in self.files}
        self.stage_root = Path('memory-stage')
        self.archive = Path('memory-archive')
        self.objects = Path('memory-objects')
        self.runtime = Path('memory-runtime')
        self.git = MemoryGit(self)
        self.reads = []
        self.on_read = None
        self.on_list = None

    def verify_identity(self):
        return None

    def head(self):
        return self.commit

    def read_file(self, git_path, commit='main'):
        self.reads.append(git_path)
        if self.on_read is not None:
            self.on_read(self, git_path)
        try:
            self._check_commit(git_path, commit)
            return self.files[git_path]
        except KeyError:
            from project_management.app.domain.captures import ArchiveError

            raise ArchiveError('ARCHIVE_MANIFEST_INVALID') from None

    def list_files(self, prefix, commit='main'):
        if self.on_list is not None:
            self.on_list(self, prefix)
        return tuple(sorted(path for path in self.files if path == prefix or path.startswith(prefix.rstrip('/') + '/')))

    def commit_for_path(self, git_path):
        commit = self.find_commit_for_path(git_path)
        if commit is None:
            from project_management.app.domain.captures import ArchiveError

            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        return commit

    def find_commit_for_path(self, git_path, commit='main'):
        try:
            self._check_commit(git_path, commit)
            return self.commits[git_path]
        except KeyError:
            return None

    def parent_for_commit(self, commit_id):
        return None

    def checkout_state(self, commit_id):
        return 'current'

    def _check_commit(self, git_path, commit):
        requested = self.commit if commit == 'main' else commit
        if self.commits[git_path] != requested:
            from project_management.app.domain.captures import ArchiveError

            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')


class MemoryRepositoryFactory:
    def __init__(self, repository):
        self.repository = repository
        self.opens = 0

    def open(self, config, project, stage, owner_subject):
        self.opens += 1
        self.repository.owner_subject = owner_subject
        return self.repository


class DriftingProjectApi(ProjectApiStub):
    def __init__(self, project, first_stage, second_stage):
        super().__init__(project, first_stage)
        self.second_stage = second_stage

    def get_project(self, actor, project_id):
        detail = super().get_project(actor, project_id)
        if self.calls > 1:
            return replace(detail, stages=(self.second_stage,))
        return detail


class NoRootArchive:
    def _validate_root_before_lock(self):
        return None


class CountingArchive(NoRootArchive):
    def __init__(self, archive, fail_after):
        self.archive = archive
        self.fail_after = fail_after
        self.calls = 0

    def __getattr__(self, name):
        return getattr(self.archive, name)

    def _source_key(self, intent, identity):
        self.calls += 1
        if self.calls > self.fail_after:
            raise AssertionError('reader continued after aggregate row limit')
        return self.archive._source_key(intent, identity)


class MemoryCaptureArchiveService(NoRootArchive, CaptureArchiveService):
    pass

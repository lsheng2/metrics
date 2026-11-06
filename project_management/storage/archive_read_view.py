from copy import deepcopy
from contextlib import nullcontext
from functools import wraps
import hashlib
from threading import RLock
import time

from project_management.app.domain.captures import ArchiveError
from project_management.app.spi.archive_reads import ArchiveBlobRequest
from project_management.storage.archive_read_history import head_tree, read_history, read_tree
from project_management.storage.git_read_batch import expression, fetch_blobs, inspect_blobs, object_id
from project_management.storage.paths import read_bytes
from project_management.storage.read_workers import ordered_read_map


def _serialized(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return call


class GitArchiveReadView:
    def __init__(self, repository, *, max_bytes=64 * 1024 * 1024, max_objects=4096,
                 timeout=10, clock=time.monotonic):
        self.repository = repository
        for field in ('project', 'stage', 'owner_subject', 'root', 'stage_root', 'runtime',
                      'archive', 'objects', 'config', 'git'):
            setattr(self, field, getattr(repository, field))
        self.clock = clock
        self.deadline = clock() + timeout
        self.max_bytes, self.max_objects = max_bytes, max_objects
        self._lock = RLock()
        self._closed = False
        self._history = read_history(self._run)
        self.head_commit = self._history[0][0].commit_id
        self._trees = {self.head_commit: head_tree(self._history)}
        self._files, self._blobs, self._validated = {}, {}, {}
        self._checkout, self._index_at_head = {}, None
        self.bytes_read = 0

    def __enter__(self):
        return self

    def open_read_view(self):
        self._active()
        return nullcontext(self)

    def __exit__(self, *args):
        self._closed = True
        self._blobs.clear()
        self._files.clear()
        self._validated.clear()

    @_serialized
    def _run(self, arguments, **kwargs):
        remaining = self.deadline - self.clock()
        if remaining <= 0:
            raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE')
        return self.git.run(arguments, timeout=remaining, **kwargs)

    def _active(self):
        if self._closed or self.clock() >= self.deadline:
            raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE')

    def head(self):
        self._active()
        return self.head_commit

    @_serialized
    def _records(self):
        self._active()
        return self._history

    def _commit(self, commit):
        self._active()
        commit = self.head_commit if commit in {None, 'main'} else object_id(commit)
        if commit != self.head_commit and not any(item.commit_id == commit for item, _ in self._records()):
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        return commit

    @_serialized
    def read_files(self, requests):
        self._active()
        requests = tuple(ArchiveBlobRequest(self._commit(item.commit_id), item.path, item.max_bytes) for item in requests)
        for item in requests:
            expression(item.commit_id, item.path)
            if type(item.max_bytes) is not int or not 0 <= item.max_bytes <= 64 * 1024 * 1024:
                raise ArchiveError('ARCHIVE_QUOTA_EXCEEDED')
        missing = {}
        for item in requests:
            key = (item.commit_id, item.path)
            if key not in self._files:
                prior = missing.get(key)
                missing[key] = item if prior is None or item.max_bytes < prior.max_bytes else prior
        if len(missing) + len(self._files) > self.max_objects:
            raise ArchiveError('ARCHIVE_QUOTA_EXCEEDED')
        needed = tuple(missing.values())
        infos = inspect_blobs(self._run, needed)
        new_objects = {info.oid: info for info in infos if info.oid not in self._blobs}
        size = sum(item.size for item in new_objects.values())
        if self.bytes_read + size > self.max_bytes or len(new_objects) + len(self._blobs) > self.max_objects:
            raise ArchiveError('ARCHIVE_QUOTA_EXCEEDED')
        contents = fetch_blobs(self._run, tuple(new_objects.values()))
        self._active()
        self._blobs.update(contents)
        self.bytes_read += size
        self._files.update({(item.commit_id, item.path): info for item, info in zip(needed, infos)})
        result = []
        for item in requests:
            info = self._files[item.commit_id, item.path]
            if info.size > item.max_bytes:
                raise ArchiveError('ARCHIVE_QUOTA_EXCEEDED')
            result.append(self._blobs[info.oid])
        return tuple(result)

    def read_file(self, path, commit='main'):
        return self.read_files((ArchiveBlobRequest(self._commit(commit), path),))[0]

    def prefetch(self, paths, commit='main'):
        self.read_files(tuple(ArchiveBlobRequest(self._commit(commit), path) for path in paths))

    @_serialized
    def _tree(self, commit):
        commit = self._commit(commit)
        if commit not in self._trees:
            self._trees[commit] = read_tree(self._run, commit)
        return self._trees[commit]

    def list_paths(self, prefix, *, commit_id=None):
        expression(self.head_commit, prefix)
        return tuple(sorted(path for path in self._tree(commit_id) if path == prefix or path.startswith(prefix + '/')))

    def list_files(self, prefix, commit='main'):
        return self.list_paths(prefix, commit_id=commit)

    def list_report_publication_ids(self, *, limit):
        ids = sorted({path.split('/')[1] for path in self.list_files('report_publications')
                      if path.endswith('/manifest.json')})
        if len(ids) > limit:
            raise ArchiveError('ARCHIVE_QUOTA_EXCEEDED')
        return tuple(ids)

    def locate_records(self, paths):
        return {path: self._location(path, self.head_commit) for path in paths}

    def _location(self, path, at):
        expression(self.head_commit, path)
        started = False
        for location, changed in self._records():
            started = started or location.commit_id == at
            if started and path in changed:
                return location
        return None

    def find_commit_for_path(self, path, commit='main'):
        found = self._location(path, self._commit(commit))
        return None if found is None else found.commit_id

    def commit_for_path(self, path):
        commit = self.find_commit_for_path(path)
        if commit is None:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        return commit

    def parent_for_commit(self, commit):
        commit = self._commit(commit)
        return next(item.parent_commit for item, _ in self._records() if item.commit_id == commit)

    def checkout_states(self, commit_ids):
        return {commit: self.checkout_state(commit) for commit in commit_ids}

    @_serialized
    def checkout_state(self, commit):
        commit = self._commit(commit)
        if self._index_at_head is None:
            self._index_at_head = self._run(
                ['diff-index', '--cached', '--quiet', self.head_commit, '--'], check=False,
            ).returncode == 0
        if self._index_at_head:
            locations = {item.commit_id: item for item, _ in self._records()}
            if locations[commit].tree_id != locations[self.head_commit].tree_id:
                return 'stale'
            commit = self.head_commit
        if commit not in self._checkout:
            if not self._index_at_head and self._run(['diff-index', '--cached', '--quiet', commit, '--'], check=False).returncode:
                self._checkout[commit] = 'stale'
            else:
                self._checkout[commit] = 'current' if self._worktree_matches(commit) else 'stale'
        return self._checkout[commit]

    def _worktree_matches(self, commit):
        def matches(item):
            path, oid = item
            try:
                data = read_bytes(self.archive, path)
            except ArchiveError as error:
                if error.code == 'ARCHIVE_RAW_PAGE_MISSING':
                    return False
                raise
            if hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() != oid:
                return False
            return True

        with ordered_read_map(matches, tuple(self._tree(commit).items()), self._active) as results:
            return all(results)

    def map_reads(self, function, items):
        with ordered_read_map(function, items, self._active) as results:
            return tuple(results)

    @_serialized
    def validated(self, key, load):
        self._active()
        if key not in self._validated:
            value = load()
            self._active()
            self._validated[key] = value
        return deepcopy(self._validated[key])

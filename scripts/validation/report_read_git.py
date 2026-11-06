from __future__ import annotations

from contextlib import contextmanager
from time import time

from project_management.app.domain.captures import ArchiveError
from project_management.app.spi.archive_reads import ArchiveBlobRequest
from project_management.app.spi.archive import CommitReceipt


class PublicationBuffer:
    def __init__(self, source_head: str):
        self.source_head = source_head
        self.records = []
        self.by_commit = {}
        self.path_to_commit = {}

    def append(self, record_id: str, files, fingerprint: str) -> CommitReceipt:
        commit_id = f'{len(self.records) + 1:040x}'
        stored = {path: bytes(data) for path, data in files.items()}
        self.records.append((record_id, stored, fingerprint, commit_id))
        self.by_commit[commit_id] = stored
        for path in stored:
            self.path_to_commit[path] = commit_id
        return CommitReceipt(commit_id, self.source_head, '0' * 40, fingerprint, 'current')


class BufferedPublicationRepository:
    def __init__(self, inner, buffer: PublicationBuffer):
        self._inner = inner
        self._buffer = buffer

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def head(self):
        return self._buffer.source_head

    def append_record(self, record_id, namespace, files, *, expected_head, record_fingerprint):
        if namespace == 'report_publications':
            if expected_head != self._buffer.source_head:
                raise AssertionError('Buffered report fixture must keep source head fixed.')
            return self._buffer.append(record_id, files, record_fingerprint)
        return self._inner.append_record(
            record_id, namespace, files, expected_head=expected_head, record_fingerprint=record_fingerprint,
        )

    def find_commit_for_path(self, git_path: str, commit='main'):
        if git_path in self._buffer.path_to_commit:
            return self._buffer.path_to_commit[git_path]
        return self._inner.find_commit_for_path(git_path, self._buffer.source_head if commit == 'main' else commit)

    def commit_for_path(self, git_path: str):
        commit = self.find_commit_for_path(git_path)
        if commit is None:
            from project_management.app.domain.captures import ArchiveError

            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        return commit

    def read_file(self, git_path: str, commit='main') -> bytes:
        commit_id = self.find_commit_for_path(git_path) if commit == 'main' else commit
        if commit_id in self._buffer.by_commit and git_path in self._buffer.by_commit[commit_id]:
            return self._buffer.by_commit[commit_id][git_path]
        return self._inner.read_file(git_path, self._buffer.source_head if commit == 'main' else commit)

    def read_files(self, requests):
        requests = tuple(requests)
        result = tuple(self.read_file(item.path, item.commit_id) for item in requests)
        if any(len(data) > request.max_bytes for request, data in zip(requests, result)):
            raise ArchiveError('ARCHIVE_QUOTA_EXCEEDED')
        return result

    def list_files(self, prefix: str, commit='main') -> tuple[str, ...]:
        existing = set(self._inner.list_files(prefix, self._buffer.source_head if commit == 'main' else commit))
        existing.update(path for path in self._buffer.path_to_commit if path == prefix or path.startswith(prefix + '/'))
        return tuple(sorted(existing))

    def parent_for_commit(self, commit_id: str):
        if commit_id in self._buffer.by_commit:
            return self._buffer.source_head
        return self._inner.parent_for_commit(commit_id)

    def checkout_state(self, commit_id: str):
        if commit_id in self._buffer.by_commit:
            return 'current'
        return self._inner.checkout_state(commit_id)


def buffered_report_repository(original, buffer: PublicationBuffer):
    @contextmanager
    def open_buffered(*args, **kwargs):
        with original(*args, **kwargs) as repository:
            yield BufferedPublicationRepository(repository, buffer)

    return open_buffered


def fast_import_records(repository, records) -> None:
    if not records:
        return
    payload = bytearray()
    initial_head = repository.head()
    for index, (record_id, files, fingerprint, _pseudo) in enumerate(records, 1):
        message = f'archive {record_id}\n\nfingerprint {fingerprint}\n'.encode('utf-8')
        payload.extend(b'commit refs/heads/main\n')
        payload.extend(f'mark :{index}\n'.encode('ascii'))
        payload.extend(f'committer Synthetic Validation <validation@example.test> {int(time())} +0000\n'.encode('ascii'))
        payload.extend(f'data {len(message)}\n'.encode('ascii'))
        payload.extend(message + b'\n')
        if index == 1:
            payload.extend(f'from {initial_head}\n'.encode('ascii'))
        for path, data in sorted(files.items()):
            payload.extend(f'M 100644 inline {path}\n'.encode('utf-8'))
            payload.extend(f'data {len(data)}\n'.encode('ascii'))
            payload.extend(data + b'\n')
    repository.git.run(['fast-import'], input_data=bytes(payload), timeout=120, output_limit=1024 * 1024)
    with repository.open_read_view() as view:
        head = view.head()
        paths = tuple(view._tree(head))
        contents = view.read_files(tuple(ArchiveBlobRequest(head, path) for path in paths))
    if repository._materialize(head, None, dict(zip(paths, contents))) != 'current':
        raise ValueError('Native fixture checkout was not materialized.')

from dataclasses import dataclass
import hashlib
import re

from project_management.app.domain.captures import ArchiveError
from project_management.storage.paths import safe_relative_path


OID = re.compile(r'[0-9a-f]{40}')
MAX_BATCH_OBJECTS = 256
MAX_BATCH_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class BlobInfo:
    oid: str
    size: int


def object_id(value):
    if type(value) is not str or OID.fullmatch(value) is None:
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    return value


def expression(commit, path):
    object_id(commit)
    safe_relative_path(path)
    if any(ord(char) < 32 or ord(char) == 127 for char in path):
        raise ArchiveError('UNSAFE_PATH')
    return f'{commit}:{path}'


def parse_batch_check(data, limits):
    lines = data.splitlines()
    if len(lines) != len(limits):
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    values = []
    for line, limit in zip(lines, limits):
        try:
            oid, kind, size, mode = line.decode('ascii').split(' ')
            object_id(oid)
            if kind != 'blob' or mode != '100644' or not re.fullmatch(r'0|[1-9][0-9]*', size):
                raise ValueError
            size = int(size)
        except (UnicodeError, ValueError):
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID') from None
        if type(limit) is not int or limit < 0 or size > limit:
            raise ArchiveError('ARCHIVE_QUOTA_EXCEEDED')
        values.append(BlobInfo(oid, size))
    return tuple(values)


def parse_batch(data, expected):
    position, values = 0, []
    for info in expected:
        end = data.find(b'\n', position)
        if end == -1 or end - position > 128:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        if data[position:end] != f'{info.oid} blob {info.size}'.encode('ascii'):
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        position = end + 1
        content = data[position:position + info.size]
        if len(content) != info.size or data[position + info.size:position + info.size + 1] != b'\n':
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        digest = hashlib.sha1(b'blob ' + str(info.size).encode('ascii') + b'\0' + content).hexdigest()
        if digest != info.oid:
            raise ArchiveError('ARCHIVE_RAW_PAGE_INTEGRITY_FAILED')
        values.append(content)
        position += info.size + 1
    if position != len(data):
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    return tuple(values)


def inspect_blobs(run, requests):
    values = []
    for index in range(0, len(requests), MAX_BATCH_OBJECTS):
        batch = requests[index:index + MAX_BATCH_OBJECTS]
        data = ''.join(expression(item.commit_id, item.path) + '\n' for item in batch).encode('utf-8')
        result = run(
            ['cat-file', '--batch-check=%(objectname) %(objecttype) %(objectsize) %(objectmode)'],
            input_data=data, output_limit=max(1024, len(batch) * 256), check=False,
        )
        if (b'%(objectmode)' in result.stdout
                or (result.returncode and b'unknown format element' in result.stderr and b'objectmode' in result.stderr)):
            raise ArchiveError('ARCHIVE_READ_UNSUPPORTED')
        if result.returncode:
            raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE')
        values.extend(parse_batch_check(result.stdout, tuple(item.max_bytes for item in batch)))
    return tuple(values)


def fetch_blobs(run, objects):
    pending, size = [], 0
    output = {}
    for info in objects:
        if pending and (len(pending) == MAX_BATCH_OBJECTS or size + info.size > MAX_BATCH_BYTES):
            output.update(_fetch(run, pending))
            pending, size = [], 0
        pending.append(info)
        size += info.size
    if pending:
        output.update(_fetch(run, pending))
    return output


def _fetch(run, batch):
    data = ''.join(item.oid + '\n' for item in batch).encode('ascii')
    result = run(['cat-file', '--batch'], input_data=data,
                 output_limit=sum(item.size for item in batch) + len(batch) * 128)
    return dict(zip((item.oid for item in batch), parse_batch(result.stdout, batch)))

import hashlib
from types import SimpleNamespace

import pytest

from project_management.app.domain.captures import ArchiveError


def batch_api():
    from project_management.storage.git_read_batch import parse_batch, parse_batch_check
    return parse_batch, parse_batch_check


def oid(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode('ascii') + b'\0' + data).hexdigest()


def test_batch_parser_preserves_binary_empty_and_order():
    parse, metadata = batch_api()
    binary = b'line one\n\x00line two\xff'
    first, second = oid(binary), oid(b'')
    meta = metadata(
        f'{first} blob {len(binary)} 100644\n{second} blob 0 100644\n'.encode(),
        (100, 0),
    )
    result = parse(
        f'{first} blob {len(binary)}\n'.encode() + binary + b'\n' + f'{second} blob 0\n\n'.encode(),
        meta,
    )
    assert result == (binary, b'')


@pytest.mark.parametrize('value', [
    b'bad missing\n', b'bad ambiguous\n', b'bad\n',
    b'a' * 40 + b' tree 3 040000\n',
    b'a' * 40 + b' blob 3 120000\n',
    b'a' * 40 + b' blob -1 100644\n',
    b'a' * 40 + b' blob x 100644\n',
    b'a' * 40 + b' blob 4 100644\n',
    b'a' * 40 + b' blob 3 100644\nextra\n',
])
def test_metadata_failure_does_not_return_partial_batch(value):
    _, metadata = batch_api()
    with pytest.raises(ArchiveError):
        metadata(value, (3,))


@pytest.mark.parametrize('tail', [b'wrong\n', b'ok', b'ok\nextra', b'o\n'])
def test_batch_rejects_wrong_length_hash_or_trailing_bytes(tail):
    parse, metadata = batch_api()
    digest = oid(b'ok')
    meta = metadata(f'{digest} blob 2 100644\n'.encode(), (3,))
    with pytest.raises(ArchiveError):
        parse(f'{digest} blob 2\n'.encode() + tail, meta)


def test_batch_requires_matching_object_identity():
    parse, metadata = batch_api()
    meta = metadata(f'{oid(b"ok")} blob 2 100644\n'.encode(), (3,))
    with pytest.raises(ArchiveError):
        parse(f'{"a" * 40} blob 2\nok\n'.encode(), meta)


@pytest.mark.parametrize(('stderr', 'expected'), [
    (b'fatal: unknown format element: objectmode\n', 'ARCHIVE_READ_UNSUPPORTED'),
    (b'fatal: unable to read object\n', 'ARCHIVE_STORAGE_UNAVAILABLE'),
])
def test_batch_capability_failure_is_distinct_from_storage_failure(stderr, expected):
    from project_management.app.spi.archive_reads import ArchiveBlobRequest
    from project_management.storage.git_read_batch import inspect_blobs

    def failed_run(arguments, *, check=True, **kwargs):
        if check:
            raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE')
        return SimpleNamespace(returncode=128, stdout=b'', stderr=stderr)

    with pytest.raises(ArchiveError) as error:
        inspect_blobs(failed_run, (ArchiveBlobRequest('a' * 40, 'captures/item.json'),))
    assert error.value.code == expected

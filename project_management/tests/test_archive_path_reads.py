from pathlib import Path
from types import SimpleNamespace
import stat

import pytest

from project_management.app.domain.captures import ArchiveError
from project_management.storage.paths import controlled_path, read_bytes


def test_controlled_path_checks_each_ancestor_once_without_resolving_links(tmp_path, monkeypatch):
    root = tmp_path / 'archive'
    parent = root / 'a' / 'b'
    parent.mkdir(parents=True)
    target = parent / 'item.json'
    target.write_bytes(b'unchanged')
    calls = {}
    original = Path.lstat

    def measured(path):
        key = str(path)
        calls[key] = calls.get(key, 0) + 1
        return original(path)

    monkeypatch.setattr(Path, 'lstat', measured)
    assert controlled_path(root, 'a/b/item.json') == target
    assert max(calls.values()) == 1, calls


@pytest.mark.parametrize('kind', ['symlink', 'reparse', 'not_directory'])
def test_single_pass_still_rejects_bad_ancestor(tmp_path, monkeypatch, kind):
    root = tmp_path / 'archive'
    root.mkdir()
    path = root / 'nested'
    path.mkdir()
    original = Path.lstat

    def unsafe(candidate):
        info = original(candidate)
        if candidate == path:
            return SimpleNamespace(
                st_mode=stat.S_IFLNK if kind == 'symlink' else stat.S_IFREG if kind == 'not_directory' else stat.S_IFDIR,
                st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT if kind == 'reparse' else 0,
                st_nlink=1,
            )
        return info

    monkeypatch.setattr(Path, 'lstat', unsafe)
    with pytest.raises(ArchiveError) as error:
        controlled_path(root, 'nested/file.json')
    assert error.value.code == 'UNSAFE_PATH'


def test_opened_file_identity_and_hardlink_refusals_remain(tmp_path, monkeypatch):
    import os

    (tmp_path / 'item.json').write_bytes(b'abc')
    original = os.fstat

    def replaced(fd):
        info = original(fd)
        return SimpleNamespace(st_dev=info.st_dev, st_ino=info.st_ino + 1)

    monkeypatch.setattr(os, 'fstat', replaced)
    with pytest.raises(ArchiveError) as error:
        read_bytes(tmp_path, 'item.json')
    assert error.value.code == 'ARCHIVE_STORAGE_UNAVAILABLE'

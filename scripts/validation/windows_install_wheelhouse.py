"""Immutable wheelhouse lock validation for Windows runtime installation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from scripts.validation.project_full_stack_support import (
    digest_file, is_reparse_or_symlink, read_json, reject_reparse_components,
)


LOCK_KIND = 'windows-wheelhouse-lock'
SHA256_TEXT = re.compile(r'^[0-9a-f]{64}$')
SAFE_WHEEL_NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.+-]*\.whl$')


@dataclass(frozen=True, slots=True)
class WheelhouseLock:
    root: Path
    wheelhouse: Path
    manifest: Path
    sha256: str
    files: dict[str, str]

    def receipt(self):
        return {
            'path': str(self.wheelhouse),
            'manifest': {'path': str(self.manifest), 'sha256': self.sha256},
            'files': dict(sorted(self.files.items())),
        }


def load_wheelhouse_lock(wheelhouse, manifest, manifest_sha256, root):
    root = _canonical(root)
    if not root.is_dir() or is_reparse_or_symlink(root):
        raise ValueError('Wheelhouse owner root is invalid')
    wheelhouse = _owned_directory(wheelhouse, root)
    manifest = _owned_file(manifest, root)
    if not _valid_sha256(manifest_sha256) or digest_file(manifest) != manifest_sha256:
        raise ValueError('Wheelhouse lock identity mismatch')
    data = read_json(manifest)
    files = data.get('files')
    if (data.get('schema_version') != 1 or data.get('kind') != LOCK_KIND
            or not isinstance(files, dict) or not files):
        raise ValueError('Invalid wheelhouse lock schema')
    expected = {_safe_wheel_name(name): _safe_sha256(value) for name, value in files.items()}
    actual = _wheelhouse_hashes(wheelhouse)
    if set(actual) != set(expected):
        raise ValueError('Wheelhouse file set mismatch')
    if any(actual[name] != digest for name, digest in expected.items()):
        raise ValueError('Wheelhouse file hash mismatch')
    return WheelhouseLock(root=root, wheelhouse=wheelhouse, manifest=manifest,
                          sha256=manifest_sha256, files=expected)


def verify_wheelhouse_lock(lock):
    return load_wheelhouse_lock(lock.wheelhouse, lock.manifest, lock.sha256, lock.root)


def _canonical(value):
    path = Path(value)
    if not path.is_absolute():
        raise ValueError('Wheelhouse paths must be absolute')
    reject_reparse_components(path)
    resolved = path.resolve()
    if resolved != path.absolute():
        raise ValueError('Wheelhouse paths must be canonical')
    return resolved


def _owned_directory(value, root):
    path = _canonical(value)
    if path == root or not path.is_relative_to(root) or not path.is_dir() or is_reparse_or_symlink(path):
        raise ValueError('Wheelhouse path is outside its owned root')
    return path


def _owned_file(value, root):
    path = _canonical(value)
    if path == root or not path.is_relative_to(root) or not path.is_file() or is_reparse_or_symlink(path):
        raise ValueError('Wheelhouse lock path is outside its owned root')
    return path


def _safe_wheel_name(value):
    if not isinstance(value, str) or Path(value).name != value or SAFE_WHEEL_NAME.fullmatch(value) is None:
        raise ValueError('Unsafe wheel filename in lock')
    return value


def _safe_sha256(value):
    if not _valid_sha256(value):
        raise ValueError('Invalid wheel hash in lock')
    return value


def _valid_sha256(value):
    return isinstance(value, str) and SHA256_TEXT.fullmatch(value) is not None


def _wheelhouse_hashes(wheelhouse):
    hashes = {}
    for path in wheelhouse.iterdir():
        if path.suffix.lower() != '.whl':
            continue
        if is_reparse_or_symlink(path) or not path.is_file():
            raise ValueError('Wheelhouse entries must be regular files')
        resolved = path.resolve()
        if resolved.parent != wheelhouse or not resolved.is_relative_to(wheelhouse):
            raise ValueError('Wheelhouse entry escapes its owner')
        hashes[path.name] = digest_file(path)
    if not hashes:
        raise ValueError('Wheelhouse is empty')
    return hashes

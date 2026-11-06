import hashlib
import ntpath
import os
from pathlib import Path
import re
import stat
import uuid

from project_management.app.domain.captures import ArchiveError


JSON_READ_LIMIT = 16 * 1024 * 1024


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_uuid(value: str) -> str:
    if type(value) is not str or re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', value) is None:
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    return str(uuid.UUID(value))


def validate_hash(value: str) -> str:
    if type(value) is not str or re.fullmatch(r'[0-9a-f]{64}', value) is None:
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    return value


def safe_relative_path(relative: str) -> tuple[str, ...]:
    if type(relative) is not str or not relative or len(relative) > 512 or '\\' in relative or ':' in relative:
        raise ArchiveError('UNSAFE_PATH')
    parts = tuple(relative.split('/'))
    if any(part in {'', '.', '..'} or _reserved(part) for part in parts):
        raise ArchiveError('UNSAFE_PATH')
    return parts


def controlled_path(root: Path, relative: str) -> Path:
    root = Path(root).absolute()
    if root.drive.startswith('\\\\') or '..' in root.parts:
        raise ArchiveError('UNSAFE_PATH')
    target = root.joinpath(*safe_relative_path(relative))
    # Literal child components plus non-following ancestor checks establish containment.
    for ancestor in reversed(target.parents):
        try:
            info = ancestor.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE') from None
        if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
                or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise ArchiveError('UNSAFE_PATH')
    try:
        info = target.lstat()
    except FileNotFoundError:
        return target
    if (not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_nlink > 1
            or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
        raise ArchiveError('UNSAFE_PATH')
    return target


def read_bytes(root: Path, relative: str, *, limit: int = JSON_READ_LIMIT) -> bytes:
    path = controlled_path(root, relative)
    try:
        before = path.stat(follow_symlinks=False)
        if before.st_size > limit:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        with path.open('rb') as stream:
            opened = os.fstat(stream.fileno())
            if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
                raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE')
            data = stream.read(limit + 1)
    except FileNotFoundError:
        raise ArchiveError('ARCHIVE_RAW_PAGE_MISSING') from None
    except OSError:
        raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE') from None
    if len(data) > limit or len(data) != before.st_size:
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    return data


def write_bytes(root: Path, relative: str, data: bytes, *, immutable: bool = False, conflict_code: str = 'ARCHIVE_CAPTURE_CONFLICT') -> None:
    if type(data) is not bytes:
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    root = root.absolute()
    path = controlled_path(root, relative)
    if immutable and path.exists():
        if read_bytes(root, relative, limit=max(len(data), JSON_READ_LIMIT)) != data:
            raise ArchiveError(conflict_code)
        return
    _make_parents(root, path.parent)
    temporary = path.with_name(f'.{path.name}.{uuid.uuid4().hex}.tmp')
    try:
        with temporary.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        controlled_path(root, temporary.relative_to(root).as_posix())
        if immutable:
            try:
                os.link(temporary, path)
            except FileExistsError:
                if read_bytes(root, relative, limit=max(len(data), JSON_READ_LIMIT)) != data:
                    raise ArchiveError(conflict_code) from None
        else:
            os.replace(temporary, path)
    except ArchiveError:
        raise
    except OSError:
        raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE') from None
    finally:
        try:
            if temporary.exists():
                temporary.unlink()
        except OSError:
            pass


def tree_usage(root: Path) -> tuple[int, int]:
    root = root.absolute()
    inspect_components(root)
    if not root.exists():
        return 0, 0
    total_bytes = 0
    total_files = 0
    try:
        for path in root.rglob('*'):
            info = path.lstat()
            if path.is_symlink() or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0):
                raise ArchiveError('UNSAFE_PATH')
            if stat.S_ISREG(info.st_mode):
                if info.st_nlink > 1:
                    raise ArchiveError('UNSAFE_PATH')
                total_files += 1
                if total_files > 1000000:
                    raise ArchiveError('ARCHIVE_QUOTA_EXCEEDED')
                total_bytes += info.st_size
            elif not stat.S_ISDIR(info.st_mode):
                raise ArchiveError('UNSAFE_PATH')
    except OSError:
        raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE') from None
    return total_bytes, total_files


def ensure_empty_or_identity_root(root: Path) -> None:
    ensure_configured_archive_root(root)
    resolved = root.resolve()
    entries = [entry for entry in resolved.iterdir() if entry.name not in {'archive-root.json', 'budget.lock', 'projects'}]
    if entries:
        raise ArchiveError('ARCHIVE_IDENTITY_MISMATCH')
    if not (root / 'archive-root.json').exists() and (root / 'projects').exists():
        # Lock directories are created only after the unowned-root preflight.
        if any(path.is_file() and path.name != 'archive.lock' for path in (root / 'projects').rglob('*')):
            raise ArchiveError('ARCHIVE_IDENTITY_MISMATCH')


def ensure_configured_archive_root(root: Path) -> None:
    root = Path(root)
    if not root.is_absolute():
        raise ArchiveError('ARCHIVE_CONFIG_INVALID')
    inspect_components(root)
    checkout = Path(__file__).resolve().parents[2]
    try:
        root_info = root.lstat()
    except FileNotFoundError:
        raise ArchiveError('ARCHIVE_ROOT_UNCONFIGURED') from None
    except OSError:
        raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE') from None
    if root.is_symlink() or not stat.S_ISDIR(root_info.st_mode):
        raise ArchiveError('ARCHIVE_CONFIG_INVALID')
    resolved = root.resolve()
    if resolved == checkout or resolved.is_relative_to(checkout):
        raise ArchiveError('ARCHIVE_CONFIG_INVALID')
    if (resolved / '.git').exists():
        raise ArchiveError('ARCHIVE_CONFIG_INVALID')
    if any((parent / '.git').exists() for parent in resolved.parents):
        raise ArchiveError('ARCHIVE_CONFIG_INVALID')


def _make_parents(root: Path, parent: Path) -> None:
    inspect_components(parent)
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE') from None
    _check_existing_ancestors(root, parent)


def _check_existing_ancestors(root: Path, path: Path) -> None:
    root = root.resolve()
    current = path
    while current != root and current.is_relative_to(root):
        if current.exists():
            info = current.lstat()
            if (current.is_symlink() or not stat.S_ISDIR(info.st_mode)
                    or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
                raise ArchiveError('UNSAFE_PATH')
        current = current.parent


def _reserved(part: str) -> bool:
    checker = getattr(ntpath, 'isreserved', None)
    return bool(checker(part)) if checker is not None else False


def inspect_components(path):
    path = Path(path)
    if not path.is_absolute() or path.drive.startswith('\\\\') or '..' in path.parts:
        raise ArchiveError('UNSAFE_PATH')
    for current in reversed((path, *path.parents)):
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if current.is_symlink() or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ArchiveError('UNSAFE_PATH')


def validate_directory(path):
    inspect_components(path)
    if not Path(path).is_dir():
        raise ArchiveError('UNSAFE_PATH')

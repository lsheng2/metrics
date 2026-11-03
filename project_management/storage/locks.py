from contextlib import contextmanager
from pathlib import Path

import portalocker

from project_management.app.domain.captures import ArchiveError


@contextmanager
def exclusive_lock(path: Path, *, create_parent: bool = False):
    try:
        if create_parent:
            path.parent.mkdir(parents=True, exist_ok=True)
        elif not path.parent.exists():
            raise ArchiveError('ARCHIVE_ROOT_UNCONFIGURED')
        with portalocker.Lock(path, timeout=0, flags=portalocker.LOCK_EX | portalocker.LOCK_NB):
            yield
    except portalocker.exceptions.LockException:
        raise ArchiveError('ARCHIVE_BUSY') from None
    except OSError:
        raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE') from None


class CombinedLocks:
    def __init__(self, root_lock, stage_lock):
        self.root_lock = root_lock
        self.stage_lock = stage_lock
        self.root_context = None
        self.stage_context = None

    def __enter__(self):
        self.root_context = exclusive_lock(self.root_lock)
        self.root_context.__enter__()
        try:
            self.stage_context = exclusive_lock(self.stage_lock, create_parent=True)
            self.stage_context.__enter__()
        except Exception:
            self.root_context.__exit__(None, None, None)
            self.root_context = None
            raise
        return self

    def __exit__(self, exc_type, exc, traceback):
        try:
            if self.stage_context is not None:
                self.stage_context.__exit__(exc_type, exc, traceback)
        finally:
            if self.root_context is not None:
                self.root_context.__exit__(exc_type, exc, traceback)

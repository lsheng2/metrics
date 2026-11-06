from dataclasses import dataclass
from typing import Callable, ContextManager, Hashable, Mapping, Protocol, TypeVar


T = TypeVar('T')
V = TypeVar('V')


@dataclass(frozen=True, slots=True)
class ArchiveBlobRequest:
    commit_id: str
    path: str
    max_bytes: int = 16 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ArchiveRecordLocation:
    commit_id: str
    parent_commit: str | None
    tree_id: str


class ArchiveReadView(Protocol):
    head_commit: str

    def open_read_view(self) -> ContextManager['ArchiveReadView']: ...
    def read_files(self, requests: tuple[ArchiveBlobRequest, ...]) -> tuple[bytes, ...]: ...
    def locate_records(self, paths: tuple[str, ...]) -> Mapping[str, ArchiveRecordLocation | None]: ...
    def list_paths(self, prefix: str, *, commit_id: str | None = None) -> tuple[str, ...]: ...
    def checkout_states(self, commit_ids: tuple[str, ...]) -> Mapping[str, str]: ...
    def validated(self, key: Hashable, load: Callable[[], T]) -> T: ...
    def map_reads(self, function: Callable[[V], T], items: tuple[V, ...]) -> tuple[T, ...]: ...

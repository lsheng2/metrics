from dataclasses import dataclass
from typing import Mapping, Protocol


@dataclass(frozen=True, slots=True)
class CommitReceipt:
    commit_id: str
    parent_commit: str | None
    tree_id: str
    record_fingerprint: str
    checkout_state: str


class StageRepository(Protocol):
    def append_record(
        self,
        record_id: str,
        namespace: str,
        files: Mapping[str, bytes],
        *,
        expected_head: str | None,
        record_fingerprint: str,
    ) -> CommitReceipt: ...

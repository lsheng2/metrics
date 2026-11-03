from pathlib import Path

from project_management.app.domain.captures import ArchiveError, RawPageRef
from project_management.storage.paths import read_bytes, sha256_bytes, validate_hash, write_bytes


class ObjectStore:
    def __init__(self, root: Path, max_bytes: int):
        self.root = root
        self.max_bytes = max_bytes

    def put(self, payload: bytes, content_type: str, request_fingerprint: str, page_id: str) -> RawPageRef:
        if type(payload) is not bytes or len(payload) > self.max_bytes:
            raise ArchiveError('ARCHIVE_QUOTA_EXCEEDED')
        digest = sha256_bytes(payload)
        write_bytes(self.root, self._relative(digest), payload, immutable=True)
        return RawPageRef(page_id, digest, len(payload), content_type, request_fingerprint)

    def read(self, reference: RawPageRef) -> bytes:
        validate_hash(reference.sha256)
        data = read_bytes(self.root, self._relative(reference.sha256), limit=self.max_bytes)
        if len(data) != reference.size_bytes or sha256_bytes(data) != reference.sha256:
            raise ArchiveError('ARCHIVE_RAW_PAGE_INTEGRITY_FAILED')
        return data

    def _relative(self, digest: str) -> str:
        return f'sha256/{validate_hash(digest)}/payload'

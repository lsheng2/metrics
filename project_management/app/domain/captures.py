from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, Mapping


ARCHIVE_ERROR_MESSAGES = {
    'ARCHIVE_ROOT_UNCONFIGURED': 'Archive storage is not configured.',
    'ARCHIVE_CONFIG_INVALID': 'Archive storage configuration is invalid.',
    'ARCHIVE_BUSY': 'Archive storage is busy. Retry the same request later.',
    'ARCHIVE_DEADLINE_EXPIRED': 'Capture deadline has expired.',
    'ARCHIVE_QUOTA_EXCEEDED': 'Archive quota would be exceeded.',
    'ARCHIVE_CAPTURE_CONFLICT': 'Capture data conflicts with an existing intent.',
    'ARCHIVE_COVERAGE_INCOMPLETE': 'Capture coverage is incomplete.',
    'ARCHIVE_IDENTITY_MISMATCH': 'Archive identity does not match this configuration.',
    'ARCHIVE_CHAIN_CONFLICT': 'Archive history changed during publication.',
    'ARCHIVE_RAW_PAGE_MISSING': 'A required raw page is missing.',
    'ARCHIVE_RAW_PAGE_INTEGRITY_FAILED': 'A retained raw page failed integrity validation.',
    'ARCHIVE_MANIFEST_INVALID': 'The archive manifest is invalid.',
    'ARCHIVE_GIT_DIRTY': 'Archive checkout contains unexpected local edits.',
    'ARCHIVE_STORAGE_UNAVAILABLE': 'Archive storage is unavailable.',
    'ARCHIVE_READ_UNSUPPORTED': 'The installed Git does not support bounded archive reads.',
    'UNSAFE_PATH': 'Archive storage path is unsafe.',
}


class ArchiveError(Exception):
    def __init__(self, code):
        self.code = code
        self.message = ARCHIVE_ERROR_MESSAGES[code]
        super().__init__(self.message)


@dataclass(frozen=True, slots=True)
class ArchiveLimits:
    max_root_bytes: int
    max_root_files: int
    max_stage_bytes: int
    max_stage_files: int
    max_capture_bytes: int
    max_capture_files: int
    max_raw_page_bytes: int
    max_object_bytes: int


@dataclass(frozen=True, slots=True)
class ArchiveStorageConfig:
    root: Path
    author_name: str
    author_email: str
    limits: ArchiveLimits


@dataclass(frozen=True, slots=True)
class CaptureSourceIdentity:
    provider_id: str
    endpoint_id: str
    endpoint_url: str
    principal_id: str
    credential_revision: str
    rule_hash: str


@dataclass(frozen=True, slots=True)
class WorkItemIdentity:
    provider_id: str
    endpoint_id: str
    stable_id: str
    display_key: str


@dataclass(frozen=True, slots=True)
class SourceChainKey:
    provider_id: str
    endpoint_id: str
    stable_id: str
    principal_id: str
    rule_hash: str


@dataclass(frozen=True, slots=True)
class PartCoverage:
    state: str
    source_version: str | None
    observed_count: int | None
    total_count: int | None
    reason_code: str | None


@dataclass(frozen=True, slots=True)
class CaptureCoverage:
    facts: PartCoverage
    comments: PartCoverage
    history: PartCoverage
    attachments: PartCoverage
    dependencies: PartCoverage


@dataclass(frozen=True, slots=True)
class CaptureIntent:
    project_id: str
    stage_id: str
    capture_id: str
    request_id: str
    source: CaptureSourceIdentity
    original_input_hash: str
    required_parts: tuple[str, ...]
    deadline_at: datetime


@dataclass(frozen=True, slots=True)
class RawPageInput:
    page_key: str
    item: WorkItemIdentity | None
    content_type: str
    payload: bytes
    request_fingerprint: str
    partial: bool = False
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class RawPageRef:
    page_id: str
    sha256: str
    size_bytes: int
    content_type: str
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class SnapshotInput:
    identity: WorkItemIdentity
    facts: Mapping
    comments_by_id: Mapping
    history_by_id: Mapping
    attachments_by_id: Mapping
    dependencies_by_id: Mapping
    coverage: CaptureCoverage
    raw_page_ids: tuple[str, ...]
    consistent: bool


@dataclass(frozen=True, slots=True)
class StoredSnapshotRef:
    identity: WorkItemIdentity
    capture_id: str
    sequence: int
    previous_capture_id: str | None
    source_hash: str
    git_path: str


@dataclass(frozen=True, slots=True)
class MembershipInput:
    items: tuple[WorkItemIdentity, ...]
    coverage: PartCoverage
    raw_page_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CaptureReceipt:
    capture_id: str
    commit_id: str
    manifest_sha256: str
    parent_commit: str | None
    membership_complete: bool
    complete: bool
    failure_code: str | None
    snapshots: tuple[StoredSnapshotRef, ...]
    checkout_state: str


@dataclass(frozen=True, slots=True)
class ArchiveIdentity:
    root_id: str
    project_id: str
    stage_id: str
    owner_subject: str
    descriptor_hash: str
    head_commit: str | None


@dataclass(frozen=True, slots=True)
class PreparedCapture:
    capture_id: str
    intent_hash: str
    state: Literal['prepared', 'replayed']


@dataclass(frozen=True, slots=True)
class CaptureManifest:
    schema_version: Literal[1]
    intent: CaptureIntent
    membership: MembershipInput
    snapshots: tuple[StoredSnapshotRef, ...]
    pages: tuple[RawPageRef, ...]
    complete: bool
    failure_code: str | None
    prepared_at: str
    finalized_at: str


@dataclass(frozen=True, slots=True)
class CapturePage:
    items: tuple[CaptureReceipt, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class CaptureMetadata:
    receipt: CaptureReceipt
    source_as_of: str


@dataclass(frozen=True, slots=True)
class CaptureMetadataPage:
    items: tuple[CaptureMetadata, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class SourceChainPage:
    items: tuple[StoredSnapshotRef, ...]
    next_cursor: str | None

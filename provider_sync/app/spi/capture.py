from dataclasses import dataclass
from typing import Callable, Mapping, Protocol

from project_management.app.api.capture_archive import CaptureIntent, RawPageInput, RawPageRef, WorkItemIdentity


@dataclass(frozen=True, slots=True)
class RawResponse:
    status_code: int
    content_type: str
    body: bytes
    partial: bool
    error_code: str | None
    retry_after: str | None = None


@dataclass(frozen=True, slots=True)
class HeldRawPage:
    page_key: str
    item: WorkItemIdentity | None
    content_type: str
    body: bytes
    request_fingerprint: str
    partial: bool
    error_code: str | None


@dataclass(frozen=True, slots=True)
class CapturedJson:
    value: Mapping
    raw_page_id: str | None
    page_key: str
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class ArchivePageSink:
    intent: CaptureIntent
    append_page: Callable[[RawPageInput], RawPageRef]


class ProviderCaptureAdapter(Protocol):
    def verify(self, connection, session): ...
    def resolve(self, descriptor, principal, session): ...
    def enumerate(self, descriptor, principal, session): ...
    def capture(self, marker, descriptor, principal, session): ...

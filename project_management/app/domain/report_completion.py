from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ReferenceObservation:
    identity: Mapping
    requested_key: str
    current_key: str
    canonical_url: str
    title: str | None
    assignee: Mapping | None
    assignee_state: str
    observed_at: str
    source_updated_at: str | None
    lookup_kind: str
    scope_snapshot_hash: str


@dataclass(frozen=True, slots=True)
class CompletionRequest:
    request_id: str
    token: str
    expected_revision: int
    expected_revision_hash: str
    snapshot_hash: str
    region_target: Mapping
    editor_epoch: str
    local_version: int


@dataclass(frozen=True, slots=True)
class CompletionError:
    code: str
    message: str
    retry_after_seconds: int | None = None


@dataclass(frozen=True, slots=True)
class CompletionOption:
    option_id: str
    enabled: bool
    disabled_reason: str | None
    fragment: Mapping | None
    receipt: str | None


@dataclass(frozen=True, slots=True)
class CompletionResult:
    request_id: str
    editor_epoch: str
    local_version: int
    status: str
    snapshot_hash: str
    observed_at: str | None
    options: tuple[CompletionOption, ...]
    error: CompletionError | None = None

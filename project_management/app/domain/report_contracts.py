from dataclasses import dataclass
from typing import Literal, Mapping

from project_management.app.domain.captures import SourceChainKey, WorkItemIdentity


REPORT_ERROR_MESSAGES = {
    'REPORT_INVALID': 'Report request is invalid.',
    'REPORT_NOT_FOUND': 'Report source material was not found.',
    'REPORT_REVISION_CONFLICT': 'Report revision has changed.',
    'REPORT_SOURCE_CHANGED': 'Report source material changed during the read.',
    'REPORT_COMPARISON_UNAVAILABLE': 'The requested report comparison is not available.',
    'REPORT_TEMPLATE_UNSUPPORTED': 'The requested report template is not supported.',
    'REPORT_EDIT_TARGET_INVALID': 'The requested report edit target is invalid.',
    'REPORT_FINALIZING': 'The report is currently finalizing.',
    'REPORT_FINALIZED': 'The report is already finalized.',
    'REPORT_LIMIT': 'Report source material exceeds the configured read limit.',
    'REPORT_FINALIZATION_PENDING': 'Report finalization is pending.',
    'REPORT_ARTIFACT_INVALID': 'The report artifact is invalid.',
}


class ReportError(Exception):
    def __init__(self, code):
        if code not in REPORT_ERROR_MESSAGES:
            code = 'REPORT_INVALID'
        self.code = code
        self.message = REPORT_ERROR_MESSAGES[code]
        super().__init__(self.message)


ReportSourceError = ReportError


@dataclass(frozen=True, slots=True)
class ReportLimits:
    max_snapshot_bytes: int = 8_388_608
    max_members: int = 500
    max_captures: int = 100


@dataclass(frozen=True, slots=True)
class ReportSelection:
    capture_id: str
    baseline_publication_id: str | None = None
    parent_publication_id: str | None = None
    purpose: Literal['standup', 'historical_export'] = 'standup'
    timezone: str = 'UTC'


@dataclass(frozen=True, slots=True)
class SummaryReference:
    summary_id: str
    revision: int
    target_capture_id: str
    source_hash: str
    input_hash: str
    result_hash: str
    owning_commit: str


@dataclass(frozen=True, slots=True)
class ReportMessage:
    message_id: str
    text: str
    source_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReportEvent:
    event_id: str
    source_key: SourceChainKey
    kind: str
    before: Mapping | None
    after: Mapping | None
    occurred_at: str | None
    observed_at: str
    source_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReportDay:
    report_date: str
    publication_id: str | None
    state: Literal['published', 'no_publication']
    source_as_of: str | None
    coverage: Mapping
    rows: tuple['ReportRow', ...]
    events: tuple[ReportEvent, ...]


@dataclass(frozen=True, slots=True)
class ReportRow:
    source_key: SourceChainKey
    identity: WorkItemIdentity
    title: str | None
    status: str | None
    assignee: object | None
    source_url: str | None
    source_hash: str | None
    coverage: Mapping
    summary_ref: SummaryReference | None
    what: str | None
    current_position: str | None
    verification: str | None
    next_actions: tuple[Mapping, ...]
    blocker_refs: tuple[str, ...]
    limitation_refs: tuple[str, ...]
    evidence: tuple[Mapping, ...]
    summary_as_of: str | None
    pending_reason: str | None


@dataclass(frozen=True, slots=True)
class ReportSourceSnapshot:
    schema_version: Literal[1]
    project_id: str
    stage_id: str
    project_name: str
    stage_name: str
    owner_subject: str
    rule_hash: str
    source_commit: str
    capture_id: str
    source_as_of: str
    report_date: str
    timezone: str
    baseline_publication_id: str | None
    comparison_policy_hash: str
    coverage: Mapping
    key_messages: tuple[ReportMessage, ...]
    rows: tuple[ReportRow, ...]
    events: tuple[ReportEvent, ...]
    days: tuple[ReportDay, ...]

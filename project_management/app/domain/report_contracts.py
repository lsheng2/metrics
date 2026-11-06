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
    'REPORT_CONTEXT_REQUIRED': 'Report preparation context is required.',
    'REPORT_DOCUMENT_UNSUPPORTED': 'The report document is not supported.',
    'REPORT_HISTORY_UNAVAILABLE': 'Report history is unavailable.',
    'REPORT_BASELINE_CONFLICT': 'Report baseline has changed.',
    'REPORT_BASELINE_PENDING': 'A previous report draft must be acknowledged before preparing this report.',
    'REPORT_CALENDAR_UNAVAILABLE': 'Report calendar mapping is unavailable.',
    'REPORT_PREPARATION_COMMAND_CONFLICT': 'Report preparation command conflicts with an existing command.',
    'REPORT_REQUIRED_SLOT_EMPTY': 'A required report slot is empty.',
    'REPORT_AI_UNAVAILABLE': 'Report AI analysis is unavailable.',
    'REPORT_AI_RESULT_INVALID': 'The AI authoring candidate failed validation.',
    'REPORT_AI_BUSY': 'An AI authoring request for this draft is still active.',
    'REPORT_AI_CANCELED': 'The AI authoring request was canceled.',
    'REPORT_AI_EXPIRED': 'The original AI authoring deadline expired.',
    'REPORT_AI_LIMIT': 'The original AI authoring observation limit was reached.',
    'REPORT_EXPORT_UNAVAILABLE': 'The selected report export is unavailable.',
    'REPORT_EXPORT_UNSUPPORTED': 'The selected format cannot represent this report content.',
    'REPORT_STORAGE_UNAVAILABLE': 'Report storage is unavailable.',
    'REFERENCE_RECEIPT_EXPIRED': 'Reference receipt has expired.',
    'REFERENCE_CONTENT_CHANGED': 'Reference link content changed.',
    'REFERENCE_INVALID': 'Reference information is invalid.',
    'COMPLETION_INVALID_ID': 'Completion ID is invalid.',
    'COMPLETION_ID_TOO_LONG': 'Completion ID is too long.',
    'COMPLETION_PROVIDER_MISMATCH': 'Completion ID does not match this provider.',
    'COMPLETION_SCOPE_UNAVAILABLE': 'Completion scope is unavailable.',
    'COMPLETION_SOURCE_CHANGED': 'Completion source changed.',
    'COMPLETION_SCOPE_UNVERIFIED': 'Completion scope is unverified.',
    'COMPLETION_OUTSIDE_REPORT_SCOPE': 'Completion ID is outside this report scope.',
    'COMPLETION_ITEM_UNAVAILABLE': 'Completion item is unavailable.',
    'COMPLETION_AUTH_REQUIRED': 'Completion provider authentication is unavailable.',
    'COMPLETION_PRINCIPAL_CHANGED': 'Completion principal changed.',
    'COMPLETION_PROVIDER_UNQUALIFIED': 'Completion provider is not qualified.',
    'COMPLETION_RATE_LIMITED': 'Completion lookup is rate limited.',
    'COMPLETION_TIMEOUT': 'Completion lookup timed out.',
    'COMPLETION_NETWORK_ERROR': 'Completion provider network failed.',
    'COMPLETION_RESPONSE_INVALID': 'Completion provider response is invalid.',
    'COMPLETION_REQUEST_REPLAY': 'Completion request was already used.',
    'COMPLETION_INVALID_REQUEST': 'Completion request is invalid.',
    'COMPLETION_REQUEST_TOO_LARGE': 'Completion request is too large.',
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

from dataclasses import dataclass
from typing import Literal

from project_management.app.domain.report_presentation import TemplateSelection


RUN_ERROR_MESSAGES = {
    'RUN_INVALID': 'Run request is invalid.',
    'RUN_NOT_FOUND': 'Run operation was not found.',
    'RUN_UNAVAILABLE': 'Run service is unavailable.',
    'RUN_BUSY': 'Run operation is busy.',
    'RUN_COMMAND_CONFLICT': 'Run command conflicts with the stored request.',
    'RUN_REVISION_CONFLICT': 'Run operation revision has changed.',
    'RUN_SOURCE_CHANGED': 'Run source changed.',
    'RUN_LIMIT': 'Run limit has been reached.',
    'RUN_DEADLINE_EXPIRED': 'Run deadline has expired.',
    'RUN_INTERRUPTED': 'Run operation was interrupted.',
    'RUN_CAPTURE_UNCERTAIN': 'Run capture outcome is uncertain.',
    'RUN_STORAGE_INVALID': 'Run storage is invalid.',
    'RUN_STORAGE_UNAVAILABLE': 'Run storage is unavailable.',
}


class RunError(Exception):
    def __init__(self, code):
        self.code = code if code in RUN_ERROR_MESSAGES else 'RUN_INVALID'
        self.message = RUN_ERROR_MESSAGES[self.code]
        super().__init__(self.message)


@dataclass(frozen=True, slots=True)
class RunPolicy:
    timeout_seconds: int = 600
    max_analysis_items: int = 10
    max_observations_per_attempt: int = 16
    max_queued_operations: int = 16


@dataclass(frozen=True, slots=True)
class RunRequest:
    command_id: str
    expected_stage_hash: str
    template: TemplateSelection
    timezone: str


@dataclass(frozen=True, slots=True)
class DailyRunTarget:
    preparation_id: str
    preparation_intent_hash: str
    draft_id: str
    effective_selection_hash: str
    source_mode: Literal['refresh']
    analysis_mode: Literal['manual_only', 'changed_items']


@dataclass(frozen=True, slots=True)
class DailyRunRequest:
    command_id: str
    expected_stage_hash: str
    template: TemplateSelection
    timezone: str
    target: DailyRunTarget


@dataclass(frozen=True, slots=True)
class ItemRunResult:
    source_key_hash: str
    state: str
    attempt_id: str | None = None
    accepted_summary_id: str | None = None
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class RunOperation:
    operation_id: str
    command_id: str
    project_id: str
    stage_id: str
    actor_subject: str
    stage_hash: str
    policy_hash: str
    created_at: str
    deadline_at: str
    capture_id: str
    state: Literal[
        'queued',
        'capturing',
        'analyzing',
        'draft_ready',
        'partial',
        'cancel_requested',
        'canceled',
        'failed',
        'interrupted',
    ]
    revision: int
    cancel_requested: bool
    item_results: tuple[ItemRunResult, ...]
    draft_id: str | None
    draft_revision: int | None
    draft_revision_hash: str | None
    snapshot_hash: str | None
    template_hash: str | None
    error_code: str | None
    execution_mode: Literal['synthetic']


@dataclass(frozen=True, slots=True)
class RuntimeStopResult:
    stopped: bool
    active_operation_id: str | None
    unresolved: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OperationLocation:
    project_id: str
    stage_id: str
    operation_id: str


@dataclass(frozen=True, slots=True)
class OperationRecoveryCandidate:
    location: OperationLocation
    actor_subject: str
    admission_hash: str
    has_initial_event: bool

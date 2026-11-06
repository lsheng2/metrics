from dataclasses import dataclass
from dataclasses import field
from typing import Literal, Mapping

from project_management.app.domain.report_continuity import PublicationRef


@dataclass(frozen=True, slots=True)
class BaselinePreview:
    state: Literal['initial', 'ready', 'pending', 'unavailable']
    series_id: str
    series_policy_hash: str
    meeting_key: str
    period_key: str
    baseline_ref: PublicationRef | None
    pending_gap_draft_ids: tuple[str, ...]
    template_choices: tuple[Mapping, ...]
    source_choices: tuple[str, ...]
    analysis_choices: tuple[str, ...]
    meeting_skipped: bool = False


@dataclass(frozen=True, slots=True)
class PreparationResult:
    disposition: Literal['created', 'existing']
    preparation_id: str
    operation_id: str | None
    draft_id: str | None
    draft_revision: int | None
    publication_ref: PublicationRef | None
    effective_selection: Mapping
    selection_conflicts: tuple[str, ...]
    state: str
    links: Mapping
    preservation_review_issues: tuple[Mapping, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class PreparationDetails:
    result: PreparationResult
    operation_revision: int | None
    draft_revision_hash: str | None
    active_preparation_id: str | None
    parent_preparation_id: str | None

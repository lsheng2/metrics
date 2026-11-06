from dataclasses import dataclass

from project_management.app.domain.captures import CaptureMetadataPage
from project_management.app.domain.report_draft_values import ReportDraftPage
from project_management.app.domain.report_publication_contracts import PublicationManifest
from project_management.app.domain.run_contracts import RunOperation
from project_management.app.domain.report_preparation import BaselinePreview, PreparationDetails


@dataclass(frozen=True, slots=True)
class ReportWorkspaceQuery:
    capture_after: str | None = None
    draft_offset: int = 0
    publication_offset: int = 0
    page_size: int = 20
    include_operations: bool = False


@dataclass(frozen=True, slots=True)
class ReportOperationsRead:
    project_id: str
    stage_id: str
    actor_subject: str
    stage_hash: str
    items: tuple[RunOperation, ...]
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class ReportPublicationListItem:
    manifest: PublicationManifest
    manifest_sha256: str
    commit_id: str


@dataclass(frozen=True, slots=True)
class ReportPublicationListPage:
    items: tuple[ReportPublicationListItem, ...]
    next_offset: int | None


@dataclass(frozen=True, slots=True)
class ReportWorkspaceRead:
    archive_state: str
    archive_head: str | None
    observed_at: str
    captures: CaptureMetadataPage
    drafts: ReportDraftPage
    publications: ReportPublicationListPage
    operations: ReportOperationsRead | None = None


@dataclass(frozen=True, slots=True)
class ReportDailyPreviewRead:
    preview: BaselinePreview
    existing: PreparationDetails | None
    captures: CaptureMetadataPage | None

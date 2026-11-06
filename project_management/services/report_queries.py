from datetime import UTC, datetime

from project_management.app.domain.captures import ArchiveError, CaptureMetadataPage
from project_management.app.domain.contracts import ProjectError
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_draft_values import ReportDraftPage
from project_management.app.domain.report_queries import (
    ReportDailyPreviewRead, ReportOperationsRead, ReportPublicationListPage, ReportWorkspaceQuery, ReportWorkspaceRead,
)
from project_management.app.domain.run_contracts import RunError
from project_management.services.report_draft_listing import draft_publication_ids
from project_management.services.report_publication_reads import ReportPublicationReader, prefetch_publications


class ReportQueryService:
    def __init__(self, archive, draft_service, preparation_service=None):
        self.archive, self.drafts = archive, draft_service
        self.preparations = preparation_service

    def daily_preview(self, actor, project_id, stage_id, *, series_id, meeting_date,
                      template_selection, capture_after=None, include_captures=False):
        if self.preparations is None:
            raise ReportError('REPORT_NOT_FOUND')
        if type(include_captures) is not bool:
            raise ReportError('REPORT_INVALID')
        try:
            with self.archive._report_read_view(actor, project_id, stage_id, allow_absent=True) as view:
                if view is not None and include_captures:
                    prefetch_publications(
                        view, view.list_report_publication_ids(limit=500),
                        extra_requests=self.archive._capture_read_requests(view, capture_after),
                    )
                preview = self.preparations.continuity.preview(
                    actor, project_id, stage_id, series_id=series_id, meeting_date=meeting_date,
                    template_selection=template_selection, _read_view=view,
                )
                existing = self.preparations.for_meeting(
                    actor, project_id, stage_id, series_id=series_id, meeting_date=meeting_date, _read_view=view,
                )
                captures = None
                if include_captures:
                    captures = (CaptureMetadataPage((), None) if view is None else self.archive.list_capture_metadata(
                        actor, project_id, stage_id, limit=20, after=capture_after, _read_view=view,
                    ))
                return ReportDailyPreviewRead(preview, existing, captures)
        except (ArchiveError, ProjectError) as error:
            raise self.drafts._report_error(error, missing_as_not_found=True) from None

    def workspace(self, actor, project_id, stage_id, *, query: ReportWorkspaceQuery):
        if not isinstance(query, ReportWorkspaceQuery) or type(query.include_operations) is not bool:
            raise ReportError('REPORT_INVALID')
        self.drafts._validate_page(query.page_size, query.draft_offset)
        self.drafts._validate_page(query.page_size, query.publication_offset)
        try:
            with self.archive._report_read_view(actor, project_id, stage_id, allow_absent=True) as view:
                if view is None:
                    return ReportWorkspaceRead('absent', None, datetime.now(UTC).isoformat(),
                                               CaptureMetadataPage((), None), ReportDraftPage((), None),
                                               ReportPublicationListPage((), None))
                selected_drafts = self.drafts._draft_ids(view.runtime / 'report-drafts')[
                    query.draft_offset:query.draft_offset + query.page_size]
                publication_ids = self.drafts._publication_ids(view)
                selected_publications = publication_ids[query.publication_offset:query.publication_offset + query.page_size]
                prefetch_publications(view, selected_publications + draft_publication_ids(
                    self.drafts._store(view), selected_drafts,
                ), extra_requests=self.archive._capture_read_requests(view, query.capture_after))
                captures = self.archive.list_capture_metadata(
                    actor, project_id, stage_id, limit=query.page_size, after=query.capture_after, _read_view=view,
                )
                drafts = self.drafts.list_drafts(
                    actor, project_id, stage_id, limit=query.page_size, offset=query.draft_offset, _read_view=view,
                )
                reader = ReportPublicationReader(view)
                publications = ReportPublicationListPage(
                    tuple(reader.list_item(item, actor.subject) for item in selected_publications),
                    self.drafts._next_offset(len(publication_ids), query.page_size, query.publication_offset),
                )
                operations = self._operations(view, actor) if query.include_operations else None
                return ReportWorkspaceRead('ready', view.head(), datetime.now(UTC).isoformat(),
                                           captures, drafts, publications, operations)
        except (ArchiveError, ProjectError) as error:
            if getattr(error, 'code', '') in {'ARCHIVE_STORAGE_UNAVAILABLE', 'ARCHIVE_READ_UNSUPPORTED'}:
                raise ReportError('REPORT_STORAGE_UNAVAILABLE') from None
            raise self.drafts._report_error(error, missing_as_not_found=True) from None

    def _operations(self, view, actor):
        items, error_code = (), None
        try:
            items = tuple(row for row in self.archive._project_operation_store(view).list(limit=10, _read_map=view.map_reads)
                          if row.actor_subject == actor.subject)
        except RunError as error:
            error_code = error.code
        return ReportOperationsRead(view.project.id, view.stage.id, actor.subject,
                                    view.stage.definition_hash, items, error_code)

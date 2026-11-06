from dataclasses import dataclass

from project_management.app.api.capture_archive import ArchiveError
from project_management.app.api.reports import ReportError
from ui_web.facades.report_templates import ready_continuity_template_choices
from ui_web.report_authoring_forms import ReportAuthoredSaveForm


@dataclass(frozen=True, slots=True)
class SubmittedCapture:
    capture_id: str
    label: str


class ProjectReportControlsMixin:
    def authored_command_form(self, actor, project_id, stage_id, data):
        self._project_stage(actor, project_id, stage_id)
        return ReportAuthoredSaveForm(data)

    def control_context(self, actor, project_id, stage_id, *, data=None, load_captures=False, capture_page=None):
        detail, stage = self._project_stage(actor, project_id, stage_id)
        series = self._series_page(actor, project_id, stage_id)
        templates = ready_continuity_template_choices(self.template_service, actor, project_id)
        captures = ()
        if capture_page is not None:
            captures = self._capture_choices(capture_page)['captures']
        elif load_captures and self.archive is not None:
            try:
                page = self.archive.list_capture_metadata(
                    actor, project_id, stage_id, limit=20,
                    after=(data or {}).get('capture_after') or None, allow_absent=True,
                )
            except ArchiveError as error:
                code = 'REPORT_STORAGE_UNAVAILABLE' if error.code in {
                    'ARCHIVE_STORAGE_UNAVAILABLE', 'ARCHIVE_READ_UNSUPPORTED',
                } else 'REPORT_LIMIT' if error.code == 'ARCHIVE_QUOTA_EXCEEDED' else 'REPORT_ARTIFACT_INVALID'
                raise ReportError(code) from None
            captures = self._capture_choices(page)['captures']
        elif data and data.get('capture_id'):
            value = data['capture_id']
            captures = (SubmittedCapture(value, value),)
        return {
            'detail': detail, 'stage': stage, 'captures': captures,
            'series_page': series, 'series_template_choices': templates,
        }

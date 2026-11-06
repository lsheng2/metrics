from project_management.app.api import reports as report_api


class ProjectReportExportFacadeMixin:
    def export_draft(self, actor, project_id, stage_id, draft_id, *, revision, format_name):
        return report_api.ReportExportService(self._service()).draft(
            actor, project_id, stage_id, draft_id, revision=revision, format_name=format_name,
        )

    def export_publication(self, actor, project_id, stage_id, publication_id, *, format_name):
        return report_api.ReportExportService(self._service()).publication(
            actor, project_id, stage_id, publication_id, format_name=format_name,
        )

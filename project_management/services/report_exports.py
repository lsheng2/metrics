from project_management.app.domain.capture_values import sha256_bytes
from project_management.reporting.report_exports import compile_export


class ReportExportService:
    def __init__(self, draft_service):
        self.drafts = draft_service

    def draft(self, actor, project_id, stage_id, draft_id, *, revision, format_name):
        rendered = self.drafts.render(actor, project_id, stage_id, draft_id, revision=revision)
        return compile_export(
            rendered.html_document, source_sha256=rendered.html_document_sha256,
            format_name=format_name, filename_stem=f'draft-{rendered.draft_id}-r{rendered.revision}',
        )

    def publication(self, actor, project_id, stage_id, publication_id, *, format_name):
        html = self.drafts.read_artifact(actor, project_id, stage_id, publication_id, 'html')
        return compile_export(html, source_sha256=sha256_bytes(html), format_name=format_name,
                              filename_stem=f'publication-{publication_id}')

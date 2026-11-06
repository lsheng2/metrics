from django.http import HttpResponse
from django.utils.translation import gettext as _
from django.views import View

from project_management.app.api import ProjectError
from project_management.app.api.reports import ReportError
from ui_web.project_access import ProjectAccessError
from ui_web.views.project_reports import ReportAccessMixin, artifact_headers, clean_revision


class ReportExportView(ReportAccessMixin, View):
    http_method_names = ['get']
    publication = False

    def get(self, request, project_id, stage_id, draft_id=None, publication_id=None):
        try:
            actor = self.actor(request)
            format_name, revision = export_query(request.GET, publication=self.publication)
            facade = self.facade_factory()
            args = (actor, str(project_id), str(stage_id))
            if self.publication:
                artifact = facade.export_publication(*args, str(publication_id), format_name=format_name)
            else:
                artifact = facade.export_draft(*args, str(draft_id), revision=revision, format_name=format_name)
            response = HttpResponse(artifact.content, content_type=artifact.media_type)
            response['Content-Disposition'] = f'attachment; filename="{artifact.filename}"'
            response['X-Report-Source-SHA256'] = artifact.source_sha256
            response['X-Report-Export-SHA256'] = artifact.sha256
            response['X-Report-Export-Revision'] = artifact.generator_revision
            response['X-Report-Export-Warnings'] = ','.join(artifact.warnings)
            return artifact_headers(response, inline=False)
        except (ProjectAccessError, ProjectError, ReportError) as error:
            if isinstance(error, ReportError) and error.code == 'REPORT_EXPORT_UNAVAILABLE':
                return self.ui_error_response(request, _('This export is unavailable. Download HTML instead.'), 503)
            if isinstance(error, ReportError) and error.code == 'REPORT_EXPORT_UNSUPPORTED':
                return self.ui_error_response(request, _('This content cannot be exported in the selected format. Download HTML instead.'), 422)
            return self.error_response(request, error)


class ReportDraftExportView(ReportExportView):
    pass


class ReportPublicationExportView(ReportExportView):
    publication = True


def export_query(query, *, publication):
    expected = {'format'} if publication else {'format', 'revision'}
    if set(query) != expected or any(len(query.getlist(key)) != 1 for key in expected):
        raise ReportError('REPORT_INVALID')
    format_name = query['format']
    if format_name not in {'markdown', 'xlsx'}:
        raise ReportError('REPORT_INVALID')
    return format_name, None if publication else clean_revision(query, allow={'format'})

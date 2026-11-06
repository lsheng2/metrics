from pathlib import PurePath

from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views import View

from project_management.app.api import ProjectError
from project_management.app.api import reports as report_api
from ui_web.facades.project_reports import default_report_facade
from ui_web.project_access import ProjectAccessError, private_no_store
from ui_web.report_authoring_forms import ReportAuthoredSaveForm
from ui_web.report_authoring_responses import authored_json_error, report_status, wants_json
from ui_web.report_forms import (
    ReportCreateForm,
    ReportDownloadQueryForm,
    ReportFinalizeForm,
    ReportRenderQueryForm,
    ReportResumeForm,
    ReportRevisionCreateForm,
    ReportStageQueryForm,
    ReportSaveForm,
    target_choices_for_snapshot,
)
from ui_web.views.project_management_views import ProjectAccessMixin, project_error_ui_message
from ui_web.views.project_run_views import ProjectRunSubmitView


SAFE_CSP = "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; sandbox"
STRICT_POST_EXEMPT = {'csrfmiddlewaretoken'}


class ReportAccessMixin(ProjectAccessMixin):
    facade_factory = staticmethod(default_report_facade)

    def error_response(self, request, error):
        if isinstance(error, report_api.ReportError):
            return self.ui_error_response(request, report_error_ui_message(error), report_status(error))
        return super().error_response(request, error)

    def report_context(self, request, actor, project_id, stage_id, **kwargs):
        context = self.facade_factory().stage_context(actor, str(project_id), str(stage_id), **kwargs)
        context['run'] = ProjectRunSubmitView.facade_factory().stage_context(
            actor,
            str(project_id),
            str(stage_id),
        )
        context['project_language_return_url'] = reverse('ui_web:project_stage_reports', kwargs={
            'project_id': project_id,
            'stage_id': stage_id,
        })
        return context

    def draft_context(self, request, actor, project_id, stage_id, draft_id, **kwargs):
        context = self.facade_factory().draft_context(actor, str(project_id), str(stage_id), str(draft_id), **kwargs)
        context['project_language_return_url'] = reverse('ui_web:report_draft_edit', kwargs={
            'project_id': project_id,
            'stage_id': stage_id,
            'draft_id': draft_id,
        })
        context['render_url'] = reverse('ui_web:report_draft_render', kwargs={
            'project_id': project_id,
            'stage_id': stage_id,
            'draft_id': draft_id,
        }) + f"?revision={context['draft'].revision}"
        context['download_url'] = reverse('ui_web:report_draft_download', kwargs={
            'project_id': project_id,
            'stage_id': stage_id,
            'draft_id': draft_id,
        }) + f"?revision={context['draft'].revision}&format=html"
        context['clipboard_url'] = reverse('ui_web:report_draft_clipboard', kwargs={
            'project_id': project_id,
            'stage_id': stage_id,
            'draft_id': draft_id,
        }) + f"?revision={context['draft'].revision}"
        context['completion_url'] = reverse('ui_web:report_draft_completion', kwargs={
            'project_id': project_id,
            'stage_id': stage_id,
            'draft_id': draft_id,
        })
        return context


class ProjectStageReportView(ReportAccessMixin, View):
    def get(self, request, project_id, stage_id):
        try:
            actor = self.actor(request)
            query = ReportStageQueryForm(request.GET)
            if not query.is_valid():
                raise report_api.ReportError('REPORT_INVALID')
            context = self.report_context(
                request,
                actor,
                project_id,
                stage_id,
                capture_after=query.cleaned_data.get('capture_after') or None,
                draft_offset=query.cleaned_data['draft_offset'],
                publication_offset=query.cleaned_data['publication_offset'],
            )
            return self.render_private(request, 'projects/reports/stage.html', context)
        except (ProjectAccessError, ProjectError, report_api.ReportError) as error:
            return self.error_response(request, error)


class ReportDraftCreateView(ReportAccessMixin, View):
    def post(self, request, project_id, stage_id):
        try:
            actor = self.actor(request)
            facade = self.facade_factory()
            capture_after = request.POST.get('capture_after') or None
            context = self.report_context(request, actor, project_id, stage_id, capture_after=capture_after)
            self._reject_unknown_post(request, ReportCreateForm.base_fields)
            form = facade.create_form(context['captures'], context['publication_choices'], request.POST,
                                      user_template_choices=context.get('user_template_choices', ()),
                                      require_capture_selection=bool(context.get('capture_next_cursor')))
            if not form.is_valid():
                context['create_form'] = form
                return self.render_private(request, 'projects/reports/stage.html', context, status=400)
            draft = facade.create_draft(actor, str(project_id), str(stage_id), form)
            return redirect('ui_web:report_draft_edit', project_id=project_id, stage_id=stage_id, draft_id=draft.draft_id)
        except (ProjectAccessError, ProjectError, report_api.ReportError) as error:
            return self.error_response(request, error)

    def _reject_unknown_post(self, request, fields):
        reject_unexpected_keys(request.POST, set(fields), allow=STRICT_POST_EXEMPT)


class ReportDraftEditView(ReportAccessMixin, View):
    def get(self, request, project_id, stage_id, draft_id):
        try:
            actor = self.actor(request)
            context = self.draft_context(request, actor, project_id, stage_id, draft_id)
            return self.render_private(request, 'projects/reports/editor.html', context)
        except (ProjectAccessError, ProjectError, report_api.ReportError) as error:
            return self.error_response(request, error)


class ReportDraftSaveView(ReportAccessMixin, View):
    def post(self, request, project_id, stage_id, draft_id):
        form = None
        try:
            actor = self.actor(request)
            facade = self.facade_factory()
            draft = facade.get_draft(actor, str(project_id), str(stage_id), str(draft_id))
            target_choices = target_choices_for_snapshot(draft.snapshot)
            self._reject_unknown_post(request, authored=request.POST.get('payload_version') == '2')
            form = facade.save_form(draft, target_choices, request.POST)
            if not form.is_valid():
                if wants_json(request):
                    return authored_json_error(
                        report_api.ReportError('REPORT_INVALID'),
                        form=form,
                        draft=draft,
                    )
                context = self.draft_context(request, actor, project_id, stage_id, draft_id, save_form=form)
                return self.render_private(request, 'projects/reports/editor.html', context, status=400)
            saved = facade.save_draft(actor, str(project_id), str(stage_id), str(draft_id), form)
            if isinstance(form, ReportAuthoredSaveForm) or wants_json(request):
                return private_no_store(JsonResponse({
                    'state': 'saved',
                    'draft_id': saved.draft_id,
                    'revision': saved.revision,
                    'revision_hash': saved.revision_hash,
                    'snapshot_hash': saved.snapshot_hash,
                    'template_hash': saved.template_definition.template_hash,
                    'clipboard_url': reverse('ui_web:report_draft_clipboard', kwargs={
                        'project_id': project_id,
                        'stage_id': stage_id,
                        'draft_id': saved.draft_id,
                    }) + f"?revision={saved.revision}",
                    'redirect_url': reverse('ui_web:report_draft_edit', kwargs={
                        'project_id': project_id,
                        'stage_id': stage_id,
                        'draft_id': saved.draft_id,
                    }),
                }))
            return redirect('ui_web:report_draft_edit', project_id=project_id, stage_id=stage_id, draft_id=saved.draft_id)
        except (ProjectAccessError, ProjectError, report_api.ReportError) as error:
            if request.POST.get('payload_version') == '2' or wants_json(request):
                return authored_json_error(error, form=form)
            return self.error_response(request, error)

    def _reject_unknown_post(self, request, *, authored):
        if authored:
            reject_unexpected_keys(request.POST, {
                'payload_version', 'command_id', 'expected_revision', 'expected_revision_hash',
                'authored_edits', 'continuity_changes',
            }, allow=STRICT_POST_EXEMPT)
        else:
            reject_unexpected_keys(
                request.POST,
                set(ReportSaveForm.base_fields),
                allow=STRICT_POST_EXEMPT,
                multi_keys={'edit_id', 'edit_kind', 'edit_target', 'edit_text', 'edit_operation'},
            )


class ReportDraftRenderView(ReportAccessMixin, View):
    def get(self, request, project_id, stage_id, draft_id):
        try:
            actor = self.actor(request)
            revision = clean_revision(request.GET)
            rendered = self.facade_factory().render(actor, str(project_id), str(stage_id), str(draft_id), revision)
            response = HttpResponse(rendered.html_document, content_type='text/html; charset=utf-8')
            response = artifact_headers(response, inline=False)
            response['X-Frame-Options'] = 'SAMEORIGIN'
            return response
        except (ProjectAccessError, ProjectError, report_api.ReportError) as error:
            return self.error_response(request, error)


class ReportDraftDownloadView(ReportAccessMixin, View):
    def get(self, request, project_id, stage_id, draft_id):
        try:
            actor = self.actor(request)
            revision = clean_revision(request.GET, allow={'format'})
            format_name = clean_download_format(request.GET, allow={'revision'})
            rendered = self.facade_factory().render(actor, str(project_id), str(stage_id), str(draft_id), revision)
            data = rendered.html_document if format_name == 'html' else rendered.plain_text.encode('utf-8')
            filename = safe_report_filename('draft', draft_id, revision, format_name)
            content_type = 'text/html; charset=utf-8' if format_name == 'html' else 'text/plain; charset=utf-8'
            response = HttpResponse(data, content_type=content_type)
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return artifact_headers(response, inline=False)
        except (ProjectAccessError, ProjectError, report_api.ReportError) as error:
            return self.error_response(request, error)


class ReportDraftClipboardView(ReportAccessMixin, View):
    def get(self, request, project_id, stage_id, draft_id):
        try:
            actor = self.actor(request)
            revision = clean_revision(request.GET)
            rendered = self.facade_factory().render(actor, str(project_id), str(stage_id), str(draft_id), revision)
            if not rendered.clipboard_available:
                raise report_api.ReportError('REPORT_LIMIT')
            payload = {
                'schema_version': 1,
                'draft_id': rendered.draft_id,
                'revision': rendered.revision,
                'revision_hash': rendered.revision_hash,
                'snapshot_hash': rendered.snapshot_hash,
                'template_hash': rendered.template_hash,
                'html_fragment': rendered.html_fragment,
                'html_sha256': rendered.html_fragment_sha256,
                'plain_text': rendered.plain_text,
                'plain_sha256': rendered.plain_text_sha256,
                'clipboard_available': rendered.clipboard_available,
            }
            return private_no_store(JsonResponse(payload))
        except (ProjectAccessError, ProjectError, report_api.ReportError) as error:
            return self.error_response(request, error)


class ReportDraftFinalizeView(ReportAccessMixin, View):
    def post(self, request, project_id, stage_id, draft_id):
        try:
            actor = self.actor(request)
            reject_unexpected_keys(request.POST, set(ReportFinalizeForm.base_fields), allow=STRICT_POST_EXEMPT)
            form = ReportFinalizeForm(request.POST)
            if not form.is_valid():
                context = self.draft_context(request, actor, project_id, stage_id, draft_id, finalize_form=form)
                return self.render_private(request, 'projects/reports/editor.html', context, status=400)
            publication = self.facade_factory().finalize(actor, str(project_id), str(stage_id), str(draft_id), form)
            return redirect('ui_web:report_publication', project_id=project_id, stage_id=stage_id,
                            publication_id=publication.manifest.publication_id)
        except (ProjectAccessError, ProjectError, report_api.ReportError) as error:
            if getattr(error, 'code', '') == 'REPORT_REQUIRED_SLOT_EMPTY':
                context = self.draft_context(request, actor, project_id, stage_id, draft_id)
                context['required_slot_error'] = report_error_ui_message(error)
                return self.render_private(request, 'projects/reports/editor.html', context, status=422)
            return self.error_response(request, error)


class ReportDraftResumeView(ReportAccessMixin, View):
    def post(self, request, project_id, stage_id, draft_id):
        try:
            actor = self.actor(request)
            reject_unexpected_keys(request.POST, set(ReportResumeForm.base_fields), allow=STRICT_POST_EXEMPT)
            form = ReportResumeForm(request.POST)
            if not form.is_valid():
                raise report_api.ReportError('REPORT_INVALID')
            publication = self.facade_factory().resume(actor, str(project_id), str(stage_id), str(draft_id), form)
            return redirect('ui_web:report_publication', project_id=project_id, stage_id=stage_id,
                            publication_id=publication.manifest.publication_id)
        except (ProjectAccessError, ProjectError, report_api.ReportError) as error:
            return self.error_response(request, error)


class ReportPublicationView(ReportAccessMixin, View):
    def get(self, request, project_id, stage_id, publication_id):
        try:
            actor = self.actor(request)
            context = self.facade_factory().publication_context(actor, str(project_id), str(stage_id), str(publication_id))
            context['project_language_return_url'] = reverse('ui_web:report_publication', kwargs={
                'project_id': project_id,
                'stage_id': stage_id,
                'publication_id': publication_id,
            })
            return self.render_private(request, 'projects/reports/publication.html', context)
        except (ProjectAccessError, ProjectError, report_api.ReportError) as error:
            return self.error_response(request, error)


class ReportPublicationRevisionView(ReportAccessMixin, View):
    def post(self, request, project_id, stage_id, publication_id):
        try:
            actor = self.actor(request)
            reject_unexpected_keys(request.POST, set(ReportRevisionCreateForm.base_fields), allow=STRICT_POST_EXEMPT)
            form = ReportRevisionCreateForm(request.POST)
            if not form.is_valid():
                raise report_api.ReportError('REPORT_INVALID')
            draft = self.facade_factory().create_revision(
                actor, str(project_id), str(stage_id), str(publication_id), form,
            )
            return redirect('ui_web:report_draft_edit', project_id=project_id, stage_id=stage_id, draft_id=draft.draft_id)
        except (ProjectAccessError, ProjectError, report_api.ReportError) as error:
            return self.error_response(request, error)


class ReportPublicationDownloadView(ReportAccessMixin, View):
    def get(self, request, project_id, stage_id, publication_id):
        try:
            actor = self.actor(request)
            format_name = clean_download_format(request.GET)
            data = self.facade_factory().read_publication_artifact(
                actor, str(project_id), str(stage_id), str(publication_id), format_name,
            )
            filename = safe_report_filename('publication', publication_id, None, format_name)
            content_type = 'text/html; charset=utf-8' if format_name == 'html' else 'text/plain; charset=utf-8'
            response = HttpResponse(data, content_type=content_type)
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return artifact_headers(response, inline=False)
        except (ProjectAccessError, ProjectError, report_api.ReportError) as error:
            return self.error_response(request, error)


def reject_unexpected_keys(data, expected, *, allow, multi_keys=frozenset()):
    allowed = set(expected) | set(allow)
    if set(data.keys()) - allowed:
        raise report_api.ReportError('REPORT_INVALID')
    for key, values in data.lists():
        if key in expected and key not in multi_keys and len(values) != 1:
            raise report_api.ReportError('REPORT_INVALID')


def clean_revision(query, *, allow=()):
    reject_unexpected_keys(query, {'revision'}, allow=set(allow))
    form = ReportRenderQueryForm(query)
    if not form.is_valid():
        raise report_api.ReportError('REPORT_INVALID')
    return form.cleaned_data['revision']


def clean_download_format(query, *, allow=()):
    reject_unexpected_keys(query, {'format'}, allow=set(allow))
    form = ReportDownloadQueryForm(query)
    if not form.is_valid():
        raise report_api.ReportError('REPORT_INVALID')
    return form.cleaned_data['format']


def artifact_headers(response, *, inline):
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    response['Content-Security-Policy'] = SAFE_CSP
    return response


def safe_report_filename(prefix, identifier, revision, format_name):
    suffix = 'html' if format_name == 'html' else 'txt'
    parts = [prefix, str(identifier)]
    if revision is not None:
        parts.append(f'r{revision}')
    name = '-'.join(parts) + f'.{suffix}'
    return PurePath(name).name.replace('"', '')


def report_error_ui_message(error):
    return {
        'REPORT_INVALID': _('Report request is invalid.'),
        'REPORT_NOT_FOUND': _('Report is not available.'),
        'REPORT_REVISION_CONFLICT': _('Report revision has changed. Save or reload before continuing.'),
        'REPORT_SOURCE_CHANGED': _('Report source material has changed. Create a new draft.'),
        'REPORT_TEMPLATE_UNSUPPORTED': _('Report template is not supported.'),
        'REPORT_EDIT_TARGET_INVALID': _('Report edit target is not valid.'),
        'REPORT_FINALIZING': _('Report finalization is still pending.'),
        'REPORT_FINALIZED': _('Report is already finalized.'),
        'REPORT_LIMIT': _('Report is over the configured limit.'),
        'REPORT_ARTIFACT_INVALID': _('Report artifact is invalid.'),
        'REPORT_REQUIRED_SLOT_EMPTY': _('Fill all required template slots before finalizing.'),
    }.get(error.code, _('Report request failed.'))

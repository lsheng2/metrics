from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views import View

from project_management.app.api import ProjectError
from project_management.app.api import reports as report_api
from ui_web.facades.report_templates import default_template_facade
from ui_web.project_access import ProjectAccessError, private_no_store
from ui_web.report_authoring_responses import wants_json
from ui_web.report_template_forms import (
    TemplateArchiveForm,
    TemplateCopyForm,
    TemplateLibraryActionForm,
    TemplateSaveForm,
)
from ui_web.views.project_management_views import ProjectAccessMixin
from ui_web.views.project_reports import reject_unexpected_keys, report_error_ui_message


class TemplateAccessMixin(ProjectAccessMixin):
    facade_factory = staticmethod(default_template_facade)

    def error_response(self, request, error):
        if isinstance(error, report_api.ReportError):
            return self.ui_error_response(request, report_error_ui_message(error), report_status(error))
        return super().error_response(request, error)

    def library_context(self, request, actor, project_id, **kwargs):
        context = self.facade_factory().library_context(actor, str(project_id), **kwargs)
        context['project_language_return_url'] = reverse('ui_web:report_templates', kwargs={'project_id': project_id})
        return context

    def editor_context(self, request, actor, project_id, template_id, **kwargs):
        context = self.facade_factory().editor_context(actor, str(project_id), str(template_id), **kwargs)
        context['project_language_return_url'] = reverse('ui_web:report_template_editor', kwargs={
            'project_id': project_id,
            'template_id': template_id,
        })
        return context


class ReportTemplateLibraryView(TemplateAccessMixin, View):
    def get(self, request, project_id):
        try:
            actor = self.actor(request)
            context = self.library_context(request, actor, project_id, offset=clean_offset(request.GET))
            return self.render_private(request, 'projects/report_templates/list.html', context)
        except (ProjectAccessError, ProjectError, report_api.ReportError) as error:
            return self.error_response(request, error)

    def post(self, request, project_id):
        try:
            actor = self.actor(request)
            reject_unexpected_keys(request.POST, set(TemplateLibraryActionForm.base_fields), allow={'csrfmiddlewaretoken'})
            form = TemplateLibraryActionForm(request.POST)
            if not form.is_valid():
                context = self.library_context(request, actor, project_id, action_form=form)
                return self.render_private(request, 'projects/report_templates/list.html', context, status=400)
            revision = self.facade_factory().create(actor, str(project_id), form)
            return redirect('ui_web:report_template_editor', project_id=project_id, template_id=revision.template_id)
        except (ProjectAccessError, ProjectError, report_api.ReportError) as error:
            return self.error_response(request, error)


class ReportTemplateEditorView(TemplateAccessMixin, View):
    def get(self, request, project_id, template_id):
        try:
            actor = self.actor(request)
            context = self.editor_context(request, actor, project_id, template_id, revision=clean_revision(request.GET))
            return self.render_private(request, 'projects/report_templates/editor.html', context)
        except (ProjectAccessError, ProjectError, report_api.ReportError) as error:
            return self.error_response(request, error)


class ReportTemplateSaveView(TemplateAccessMixin, View):
    def post(self, request, project_id, template_id):
        form = None
        try:
            actor = self.actor(request)
            reject_unexpected_keys(request.POST, set(TemplateSaveForm.base_fields), allow={'csrfmiddlewaretoken'})
            form = TemplateSaveForm(request.POST)
            current_revision = current_from_post(request.POST)
            if not form.is_valid():
                if wants_json(request):
                    return template_json_error(form=form)
                context = self.editor_context(request, actor, project_id, template_id, revision=current_revision, form=form)
                return self.render_private(request, 'projects/report_templates/editor.html', context, status=400)
            revision = self.facade_factory().save(actor, str(project_id), str(template_id), form)
            if wants_json(request):
                return private_no_store(JsonResponse({
                    'state': 'saved',
                    'revision': revision.revision,
                    'revision_hash': revision.revision_hash,
                    'redirect_url': reverse('ui_web:report_template_editor', kwargs={
                        'project_id': project_id,
                        'template_id': template_id,
                    }),
                }))
            return redirect('ui_web:report_template_editor', project_id=project_id, template_id=template_id)
        except (ProjectAccessError, ProjectError, report_api.ReportError) as error:
            if form and form.is_valid() and getattr(error, 'code', '') == 'REPORT_REVISION_CONFLICT':
                if wants_json(request):
                    return template_json_error(error, form=form, status=409)
                context = self.editor_context(
                    request, actor, project_id, template_id,
                    revision=form.cleaned_data['expected_revision'], form=form,
                    error=_('Template revision has changed. Your posted content is still shown below.'),
                )
                return self.render_private(request, 'projects/report_templates/editor.html', context, status=409)
            if wants_json(request):
                return template_json_error(error, form=form, status=report_status(error))
            return self.error_response(request, error)


class ReportTemplateArchiveView(TemplateAccessMixin, View):
    def post(self, request, project_id, template_id):
        try:
            actor = self.actor(request)
            reject_unexpected_keys(request.POST, set(TemplateArchiveForm.base_fields), allow={'csrfmiddlewaretoken'})
            form = TemplateArchiveForm(request.POST)
            if not form.is_valid():
                raise report_api.ReportError('REPORT_INVALID')
            self.facade_factory().archive(actor, str(project_id), str(template_id), form)
            return redirect('ui_web:report_templates', project_id=project_id)
        except (ProjectAccessError, ProjectError, report_api.ReportError) as error:
            return self.error_response(request, error)


class ReportTemplateCopyView(TemplateAccessMixin, View):
    def post(self, request, project_id, template_id):
        try:
            actor = self.actor(request)
            reject_unexpected_keys(request.POST, set(TemplateCopyForm.base_fields), allow={'csrfmiddlewaretoken'})
            form = TemplateCopyForm(request.POST)
            if not form.is_valid():
                raise report_api.ReportError('REPORT_INVALID')
            revision = self.facade_factory().copy(actor, str(project_id), str(template_id), form)
            return redirect('ui_web:report_template_editor', project_id=project_id, template_id=revision.template_id)
        except (ProjectAccessError, ProjectError, report_api.ReportError) as error:
            return self.error_response(request, error)


def clean_offset(query):
    if not query:
        return 0
    reject_unexpected_keys(query, {'offset'}, allow=set())
    try:
        value = int(query.get('offset') or '0')
    except ValueError:
        raise report_api.ReportError('REPORT_INVALID') from None
    if value < 0 or value > 1000:
        raise report_api.ReportError('REPORT_INVALID')
    return value


def clean_revision(query):
    if not query:
        return None
    reject_unexpected_keys(query, {'revision'}, allow=set())
    try:
        value = int(query.get('revision') or '0')
    except ValueError:
        raise report_api.ReportError('REPORT_INVALID') from None
    if value < 1 or value > 1_000_000:
        raise report_api.ReportError('REPORT_INVALID')
    return value


def current_from_post(data):
    try:
        return int(data.get('expected_revision') or '1')
    except ValueError:
        return 1


def report_status(error):
    if error.code == 'REPORT_NOT_FOUND':
        return 404
    if error.code == 'REPORT_REVISION_CONFLICT':
        return 409
    if error.code == 'REPORT_LIMIT':
        return 413
    return 400
def template_json_error(error=None, *, form=None, status=400):
    code = getattr(error, 'code', 'REPORT_INVALID')
    message = str(error) if error is not None else _('Template request is invalid.')
    return private_no_store(JsonResponse({
        'state': 'failed',
        'error_code': code,
        'message': message,
        'form_errors': {} if form is None else form.errors.get_json_data(),
    }, status=status))

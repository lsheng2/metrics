import re
import secrets
from datetime import datetime, timezone

from django.conf import settings
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext as _
from django.views import View

from project_management.app.api import ProjectError
from project_management.container import build_project_api
from ui_web.facades.project_management import ProjectManagementFacade
from ui_web.project_access import ProjectAccessError, private_no_store, project_access_response, project_actor
from ui_web.project_language_returns import same_origin_next
from ui_web.project_forms import (
    ProjectArchiveForm,
    ProjectCreateForm,
    ProjectListQueryForm,
    StageConfirmForm,
    StagePreviewForm,
)
from ui_web.project_sources import ProjectSourceChoices


PREVIEW_SESSION_KEY = 'project_stage_preview'
STAGE_DRAFT_SESSION_KEY = 'project_stage_draft'
PREVIEW_MAX_AGE_SECONDS = 600


def project_facade():
    return ProjectManagementFacade(build_project_api(), ProjectSourceChoices())


class ProjectAccessMixin:
    facade_factory = staticmethod(project_facade)

    def actor(self, request):
        return project_actor(request)

    def error_response(self, request, error):
        if isinstance(error, ProjectAccessError):
            return project_access_response(error)
        if isinstance(error, ProjectError):
            return self.ui_error_response(request, project_error_ui_message(error), self.status_for_project_error(error))
        raise error

    def ui_error_response(self, request, message, status):
        return self.render_private(request, 'projects/error.html', {
            'message': message,
            'project_language_return_url': reverse('ui_web:projects'),
        }, status=status)

    def status_for_project_error(self, error):
        if error.code == 'PROJECT_NOT_FOUND':
            return 404
        if error.code in {'INVALID_PROJECT', 'INVALID_SELECTION'}:
            return 400
        return 409

    def render_private(self, request, template, context, status=200):
        return private_no_store(render(request, template, context, status=status))


class ProjectListView(ProjectAccessMixin, View):
    def get(self, request):
        try:
            actor = self.actor(request)
            offset = self.offset(request)
            context = self.facade_factory().list_projects(actor, offset=offset)
            context['create_form'] = ProjectCreateForm()
            context['project_language_return_url'] = reverse('ui_web:projects')
            return self.render_private(request, 'projects/list.html', context)
        except (ProjectAccessError, ProjectError) as error:
            return self.error_response(request, error)

    def post(self, request):
        try:
            actor = self.actor(request)
            form = ProjectCreateForm(request.POST)
            offset = self.offset(request)
            facade = self.facade_factory()
            if not form.is_valid():
                context = facade.list_projects(actor, offset=offset)
                context['create_form'] = form
                context['project_language_return_url'] = reverse('ui_web:projects')
                return self.render_private(request, 'projects/list.html', context, status=400)
            try:
                project = facade.create_project(actor, **form.cleaned_data)
            except ProjectError as error:
                if error.code != 'PROJECT_KEY_CONFLICT':
                    raise
                form.add_error(None, project_error_ui_message(error))
                context = facade.list_projects(actor, offset=offset)
                context['create_form'] = form
                context['project_language_return_url'] = reverse('ui_web:projects')
                return self.render_private(request, 'projects/list.html', context, status=409)
            return redirect('ui_web:project_detail', project_id=project.id)
        except (ProjectAccessError, ProjectError) as error:
            return self.error_response(request, error)

    def offset(self, request):
        form = ProjectListQueryForm(request.GET if 'offset' in request.GET else {'offset': '0'})
        if not form.is_valid():
            raise ProjectError('INVALID_PROJECT')
        return form.cleaned_data['offset']


class ProjectDetailView(ProjectAccessMixin, View):
    def get(self, request, project_id):
        try:
            actor = self.actor(request)
            facade = self.facade_factory()
            context = facade.get_project(actor, str(project_id))
            context['stage_form'] = stage_form_for_detail(
                request,
                actor.subject,
                str(project_id),
                context['source_choices'],
            )
            context['archive_form'] = ProjectArchiveForm()
            context['project_language_return_url'] = reverse('ui_web:project_detail', kwargs={'project_id': project_id})
            return self.render_private(request, 'projects/detail.html', context)
        except (ProjectAccessError, ProjectError) as error:
            return self.error_response(request, error)


class ProjectStagePreviewView(ProjectAccessMixin, View):
    def post(self, request, project_id):
        try:
            actor = self.actor(request)
            backend_response = require_database_session_backend(request)
            if backend_response:
                return backend_response
            facade = self.facade_factory()
            detail_context = facade.get_project(actor, str(project_id))
            form = StagePreviewForm(request.POST, source_choices=detail_context['source_choices'])
            if not form.is_valid():
                store_stage_draft(request, actor.subject, str(project_id), request.POST)
                detail_context['stage_form'] = form
                detail_context['archive_form'] = ProjectArchiveForm()
                detail_context['project_language_return_url'] = reverse('ui_web:project_detail', kwargs={'project_id': project_id})
                return self.render_private(request, 'projects/detail.html', detail_context, status=400)
            source_choice = form.cleaned_data['source']
            try:
                preview = facade.preview_stage(
                    actor,
                    str(project_id),
                    key=form.cleaned_data['key'],
                    name=form.cleaned_data['name'],
                    selection=source_choice.selection,
                )
            except ProjectError as error:
                form.add_error(None, project_error_ui_message(error))
                store_stage_draft(request, actor.subject, str(project_id), request.POST)
                detail_context['stage_form'] = form
                detail_context['archive_form'] = ProjectArchiveForm()
                detail_context['project_language_return_url'] = reverse('ui_web:project_detail', kwargs={'project_id': project_id})
                return self.render_private(request, 'projects/detail.html', detail_context, status=self.status_for_project_error(error))
            preview_id = secrets.token_urlsafe(32)
            request.session[PREVIEW_SESSION_KEY] = preview_payload(preview_id, actor.subject, preview)
            request.session.modified = True
            return self.render_private(request, 'projects/preview.html', {
                'detail': detail_context['detail'],
                'preview': preview,
                'preview_id': preview_id,
                'source_label': source_choice.label,
                'confirm_form': StageConfirmForm({'preview_id': preview_id}),
                'project_language_return_url': reverse('ui_web:project_detail', kwargs={'project_id': project_id}),
            })
        except (ProjectAccessError, ProjectError) as error:
            return self.error_response(request, error)


class ProjectStageConfirmView(ProjectAccessMixin, View):
    def post(self, request, project_id):
        try:
            actor = self.actor(request)
            backend_response = require_database_session_backend(request)
            if backend_response:
                return backend_response
            form = StageConfirmForm(request.POST)
            if not form.is_valid():
                return self.ui_error_response(request, _('Preview is not valid.'), status=409)
            preview_data = request.session.get(PREVIEW_SESSION_KEY)
            if not valid_preview(preview_data, form.cleaned_data['preview_id'], actor.subject, str(project_id)):
                return self.ui_error_response(request, _('Preview is not valid.'), status=409)
            try:
                self.facade_factory().confirm_stage(actor, str(project_id), preview_data)
            except ProjectError as error:
                if error.code == 'SOURCE_CHANGED':
                    request.session.pop(PREVIEW_SESSION_KEY, None)
                    request.session.modified = True
                return self.error_response(request, error)
            request.session.pop(PREVIEW_SESSION_KEY, None)
            request.session.modified = True
            return redirect('ui_web:project_detail', project_id=project_id)
        except (ProjectAccessError, ProjectError) as error:
            return self.error_response(request, error)


class ProjectArchiveView(ProjectAccessMixin, View):
    def post(self, request, project_id):
        try:
            actor = self.actor(request)
            form = ProjectArchiveForm(request.POST)
            if not form.is_valid():
                context = self.facade_factory().get_project(actor, str(project_id))
                context['stage_form'] = StagePreviewForm(source_choices=context['source_choices'])
                context['archive_form'] = form
                context['project_language_return_url'] = reverse('ui_web:project_detail', kwargs={'project_id': project_id})
                return self.render_private(request, 'projects/detail.html', context, status=400)
            self.facade_factory().archive_project(actor, str(project_id))
            return redirect('ui_web:project_detail', project_id=project_id)
        except (ProjectAccessError, ProjectError) as error:
            return self.error_response(request, error)


class ProjectLanguageView(ProjectAccessMixin, View):
    def post(self, request):
        try:
            self.actor(request)
        except ProjectAccessError as error:
            return project_access_response(error)
        language = request.POST.get('language', 'en')
        if language not in {'en', 'zh-hans'}:
            language = 'en'
        translation.activate(language)
        response = HttpResponseRedirect(same_origin_next(request))
        response.set_cookie(
            settings.LANGUAGE_COOKIE_NAME,
            language,
            max_age=settings.LANGUAGE_COOKIE_AGE,
            path=settings.LANGUAGE_COOKIE_PATH,
            domain=settings.LANGUAGE_COOKIE_DOMAIN,
            secure=settings.LANGUAGE_COOKIE_SECURE,
            httponly=settings.LANGUAGE_COOKIE_HTTPONLY,
            samesite=settings.LANGUAGE_COOKIE_SAMESITE,
        )
        return response


def require_database_session_backend(request):
    if settings.SESSION_ENGINE != 'django.contrib.sessions.backends.db':
        return private_no_store(render(
            request,
            'projects/error.html',
            {'message': _('Project preview requires server-side sessions.')},
            status=503,
        ))
    return None


def preview_payload(preview_id, actor_subject, preview):
    return {
        'preview_id': preview_id,
        'actor_subject': actor_subject,
        'project_id': preview.project_id,
        'key': preview.key,
        'name': preview.name,
        'selection': {
            'profile_id': preview.selection.profile_id,
            'scope_id': preview.selection.scope_id,
        },
        'definition_hash': preview.definition_hash,
        'issued_at': int(datetime.now(tz=timezone.utc).timestamp()),
    }


def store_stage_draft(request, actor_subject, project_id, data):
    request.session[STAGE_DRAFT_SESSION_KEY] = {
        'actor_subject': actor_subject,
        'project_id': project_id,
        'key': str(data.get('key', ''))[:64],
        'name': str(data.get('name', ''))[:160],
        'source': str(data.get('source', ''))[:240],
        'issued_at': int(datetime.now(tz=timezone.utc).timestamp()),
    }
    request.session.modified = True


def stage_form_for_detail(request, actor_subject, project_id, source_choices):
    initial = stage_initial_from_preview(request, actor_subject, project_id)
    if not initial:
        initial = stage_initial_from_draft(request, actor_subject, project_id)
    return StagePreviewForm(initial=initial, source_choices=source_choices)


def stage_initial_from_preview(request, actor_subject, project_id):
    preview_data = request.session.get(PREVIEW_SESSION_KEY)
    if not valid_preview_context(preview_data, actor_subject, project_id):
        return {}
    selection = preview_data.get('selection') or {}
    profile_id = selection.get('profile_id', '')
    scope_id = selection.get('scope_id')
    source = f'jira/{profile_id}/{scope_id}' if scope_id is not None else f'hsdes/{profile_id}'
    return {
        'key': preview_data.get('key', ''),
        'name': preview_data.get('name', ''),
        'source': source,
    }


def stage_initial_from_draft(request, actor_subject, project_id):
    draft = request.session.get(STAGE_DRAFT_SESSION_KEY)
    if not valid_stage_draft(draft, actor_subject, project_id):
        return {}
    return {
        'key': draft.get('key', ''),
        'name': draft.get('name', ''),
        'source': draft.get('source', ''),
    }


def valid_preview_context(preview_data, actor_subject, project_id):
    if not isinstance(preview_data, dict) or not safe_preview_token(preview_data.get('preview_id', '')):
        return False
    return valid_session_entry(preview_data, actor_subject, project_id)


def valid_stage_draft(draft, actor_subject, project_id):
    if not isinstance(draft, dict):
        return False
    return valid_session_entry(draft, actor_subject, project_id)


def valid_preview(preview_data, preview_id, actor_subject, project_id):
    if not isinstance(preview_data, dict):
        return False
    stored_preview_id = preview_data.get('preview_id', '')
    if not safe_preview_token(stored_preview_id) or not safe_preview_token(preview_id):
        return False
    if not secrets.compare_digest(stored_preview_id, preview_id):
        return False
    return valid_session_entry(preview_data, actor_subject, project_id)


def valid_session_entry(entry, actor_subject, project_id):
    if entry.get('actor_subject') != actor_subject or entry.get('project_id') != project_id:
        return False
    issued_at = entry.get('issued_at')
    if type(issued_at) is not int:
        return False
    elapsed = int(datetime.now(tz=timezone.utc).timestamp()) - issued_at
    return 0 <= elapsed <= PREVIEW_MAX_AGE_SECONDS


def safe_preview_token(value):
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]{32,120}', value) is not None


def project_error_ui_message(error):
    return {
        'PROJECT_NOT_FOUND': _('Project is not available.'),
        'PROJECT_ARCHIVED': _('Archived projects cannot accept new stages.'),
        'PROJECT_KEY_CONFLICT': _('Project key is already used with different details.'),
        'INVALID_PROJECT': _('Project request is invalid.'),
        'INVALID_SELECTION': _('Source selection is invalid.'),
        'SOURCE_UNAVAILABLE': _('The selected source is not available.'),
        'SOURCE_CHANGED': _('Source changed. Preview the stage again.'),
        'PROJECT_LIMIT': _('Project stage limit has been reached.'),
        'PROJECT_BUSY': _('Project storage is busy. Retry the same request later.'),
        'STAGE_RULE_IMMUTABLE': _('Stage key is already bound to a different definition.'),
    }.get(error.code, _('Project request is invalid.'))

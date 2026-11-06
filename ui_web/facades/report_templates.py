from dataclasses import dataclass

from django.utils.translation import gettext as _

from project_management.app.api import ProjectError
from project_management.app.api.report_factories import build_report_template_service
from project_management.app.api.factories import build_project_api
from ui_web.report_template_forms import (
    initial_archive_form,
    initial_copy_form,
    initial_library_form,
    initial_save_form,
)
from ui_web.report_template_view_model import editor_payload, ready_template_choices, template_choice_value


@dataclass(frozen=True, slots=True)
class TemplateLibraryForms:
    blank: object
    daily: object
    weekly: object
    continuity_daily: object
    continuity_weekly: object


def default_template_facade():
    return ProjectReportTemplateFacade(build_project_api(), build_report_template_service())


def ready_user_template_choices(service, actor, project_id):
    try:
        return ready_template_choices(service.list(actor, project_id, limit=100, offset=0))
    except ProjectError as error:
        if error.code == 'PROJECT_NOT_FOUND':
            return ()
        raise


def ready_continuity_template_choices(service, actor, project_id):
    return ready_schema2_template_choices(service, actor, project_id)


def ready_weekly_template_choices(service, actor, project_id):
    return ready_schema2_template_choices(service, actor, project_id, report_kind='weekly')


def ready_schema2_template_choices(service, actor, project_id, report_kind=None):
    try:
        page = service.list(actor, project_id, limit=100, offset=0)
        choices = []
        for item in page.items:
            if item.readiness != 'ready' or item.archived:
                continue
            revision = service.get(actor, project_id, item.template_id, revision=item.current_revision)
            if revision.document['schema_version'] != 2:
                continue
            if report_kind is not None and revision.document['report_kind'] != report_kind:
                continue
            if not any(block['kind'] == 'data' and block['source'] == 'meeting_matrix'
                       for block in revision.document['blocks']):
                continue
            choices.append((template_choice_value(item), _('%(name)s r%(revision)s (%(hash)s)') % {
                'name': item.name,
                'revision': item.current_revision,
                'hash': item.revision_hash[:12],
            }))
        return tuple(choices)
    except ProjectError as error:
        if error.code == 'PROJECT_NOT_FOUND':
            return ()
        raise


class ProjectReportTemplateFacade:
    def __init__(self, project_api, template_service):
        self.project_api = project_api
        self.template_service = template_service

    def library_context(self, actor, project_id, *, offset=0, action_form=None):
        detail = self.project_api.get_project(actor, project_id)
        page = self.template_service.list(actor, project_id, limit=20, offset=offset)
        blank = action_form if action_form is not None else initial_library_form('blank', _('Untitled template'))
        daily = initial_library_form('builtin_daily', _('Daily starter'))
        weekly = initial_library_form('builtin_weekly', _('Weekly starter'))
        continuity_daily = initial_library_form('continuity_daily', _('Continuity daily starter'))
        continuity_weekly = initial_library_form('continuity_weekly', _('Continuity weekly starter'))
        return {
            'detail': detail,
            'templates': page,
            'template_rows': tuple({'item': item, 'copy_form': initial_copy_form(item)} for item in page.items),
            'offset': offset,
            'previous_offset': max(offset - 20, 0) if offset else None,
            'forms': TemplateLibraryForms(blank, daily, weekly, continuity_daily, continuity_weekly),
            'create_forms': (
                {'form': initial_library_form('standup_daily', _('Concise daily standup')),
                 'label': _('Concise daily standup')},
                {'form': initial_library_form('standup_weekly', _('Concise weekly standup')),
                 'label': _('Concise weekly standup')},
                {'form': blank, 'label': _('Blank template')},
                {'form': daily, 'label': _('Copy daily starter')},
                {'form': weekly, 'label': _('Copy weekly starter')},
                {'form': continuity_daily, 'label': _('Copy continuity daily starter')},
                {'form': continuity_weekly, 'label': _('Copy continuity weekly starter')},
            ),
        }

    def editor_context(self, actor, project_id, template_id, *, revision=None, form=None, error=None):
        detail = self.project_api.get_project(actor, project_id)
        summary = self._summary(actor, project_id, template_id)
        current = self.template_service.get(actor, project_id, template_id, revision=revision or summary.current_revision)
        payload = editor_payload(current, form=form)
        return {
            'detail': detail,
            'template': current,
            'template_archived': summary.archived,
            'editor': payload,
            'save_form': form or initial_save_form(current),
            'archive_form': initial_archive_form(current),
            'copy_form': initial_copy_form(current),
            'error_message': error,
        }

    def create(self, actor, project_id, form):
        document, policy = form.template_payload()
        return self.template_service.create(
            actor,
            project_id,
            command_id=str(form.cleaned_data['command_id']),
            name=form.cleaned_data['name'],
            document=document,
            fill_policy=policy,
        )

    def save(self, actor, project_id, template_id, form):
        return self.template_service.save(
            actor,
            project_id,
            template_id,
            command_id=str(form.cleaned_data['command_id']),
            expected_revision=form.cleaned_data['expected_revision'],
            expected_revision_hash=form.cleaned_data['expected_revision_hash'],
            name=form.cleaned_data['name'],
            document=form.document_value(),
            fill_policy=form.fill_policy_value(),
        )

    def archive(self, actor, project_id, template_id, form):
        return self.template_service.archive(
            actor,
            project_id,
            template_id,
            command_id=str(form.cleaned_data['command_id']),
            expected_revision=form.cleaned_data['expected_revision'],
            expected_revision_hash=form.cleaned_data['expected_revision_hash'],
        )

    def copy(self, actor, project_id, template_id, form):
        return self.template_service.copy(
            actor,
            project_id,
            template_id,
            revision=form.cleaned_data['revision'],
            target_project_id=project_id,
            command_id=str(form.cleaned_data['command_id']),
            name=form.cleaned_data['name'],
        )

    def _summary(self, actor, project_id, template_id):
        page = self.template_service.list(actor, project_id, limit=100, offset=0)
        for item in page.items:
            if item.template_id == template_id:
                return item
        raise ProjectError('PROJECT_NOT_FOUND')

import json
from urllib.parse import urlencode

from django.http import JsonResponse
from django.shortcuts import redirect

from ..container import ui_web_container
from .graceful_template_view import GracefulTemplateView


class BugTrendScopeLibraryView(GracefulTemplateView):
    template_name = 'bug_trend_scope_library.html'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def get(self, request, *args, **kwargs):
        export_scope_id = request.GET.get('export_scope_id')
        if export_scope_id and export_scope_id.isdecimal():
            package = self.bug_trend_facade.export_scope_config_package(int(export_scope_id))
            response = JsonResponse(package, json_dumps_params={'indent': 2})
            response['Content-Disposition'] = f'attachment; filename="scope-{export_scope_id}.json"'
            return response
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        scope_id = request.POST.get('scope_id')
        if action == 'disable' and scope_id and scope_id.isdecimal():
            self.bug_trend_facade.disable_scope_config(int(scope_id))
            return self._library_redirect({'archived': 1})
        if action == 'delete_archived' and scope_id and scope_id.isdecimal():
            return self._delete_archived_scope_response(request, int(scope_id))
        if action == 'import_scope':
            return self._import_scope_response(request)
        if action == 'confirm_binding' and scope_id and scope_id.isdecimal():
            self.bug_trend_facade.confirm_scope_provider_binding(int(scope_id))
        if action == 'bulk_confirm_bindings':
            return self._bulk_confirm_response()
        if action == 'save_binding' and scope_id and scope_id.isdecimal():
            try:
                self.bug_trend_facade.set_scope_provider_binding(int(scope_id), request.POST.get('profile_id', ''))
            except ValueError:
                pass
        return redirect('ui_web:bug_trend_scope_library')

    def _delete_archived_scope_response(self, request, scope_id: int):
        try:
            self.bug_trend_facade.delete_archived_scope_config(scope_id, request.POST.get('delete_confirmation', ''))
            return self._library_redirect({'deleted': 1})
        except ValueError as error:
            return self._library_redirect({'delete_error': self._error_message(error)})

    def _import_scope_response(self, request):
        try:
            package = self._scope_import_package(request)
            imported = self.bug_trend_facade.import_scope_config_package(package)
            return self._library_redirect({'imported_scope': imported.name})
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
            return self._library_redirect({'import_error': self._error_message(error)})

    def _bulk_confirm_response(self):
        result = self.bug_trend_facade.bulk_confirm_scope_provider_bindings()
        response = redirect('ui_web:bug_trend_scope_library')
        response['Location'] = (
            f'{response["Location"]}?bulk_changed={result.get("changed_count", 0)}'
            f'&bulk_skipped={result.get("skipped_count", 0)}'
        )
        return response

    def _library_redirect(self, params: dict):
        response = redirect('ui_web:bug_trend_scope_library')
        response['Location'] = f'{response["Location"]}?{urlencode(params)}'
        return response

    def _scope_import_package(self, request):
        uploaded_file = request.FILES.get('scope_package')
        if uploaded_file is None:
            raise ValueError({'scope_import': 'Choose a scope JSON package to import.'})
        return json.loads(uploaded_file.read().decode('utf-8'))

    def _error_message(self, error):
        if error.args and isinstance(error.args[0], dict):
            return '; '.join(str(value) for value in error.args[0].values())
        return str(error)

    def populate_context(self, context, **kwargs):
        scope_rows = self.bug_trend_facade.get_scope_library_rows()
        context['scope_rows'] = scope_rows
        context['scope_library_summary'] = self.bug_trend_facade.get_scope_library_summary(scope_rows)
        context['bulk_changed'] = self.request.GET.get('bulk_changed')
        context['bulk_skipped'] = self.request.GET.get('bulk_skipped')
        context['archived'] = self.request.GET.get('archived')
        context['deleted'] = self.request.GET.get('deleted')
        context['imported_scope'] = self.request.GET.get('imported_scope')
        context['import_error'] = self.request.GET.get('import_error')
        context['delete_error'] = self.request.GET.get('delete_error')
        context['scope_binding_policy'] = self.bug_trend_facade.get_scope_binding_policy()
        context['scope_binding_audit_events'] = self.bug_trend_facade.get_scope_binding_audit_events()
        context['provider_profile_choices'] = self.bug_trend_facade.get_scope_provider_profile_choices()
        context['build_page_title'] = 'Bug Trend Scope Library'


class BugTrendScopeConfigView(GracefulTemplateView):
    template_name = 'bug_trend_scope_config.html'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def post(self, request, *args, **kwargs):
        if request.POST.get('action') == 'discard':
            scope_id = request.POST.get('id')
            if scope_id and scope_id.isdecimal():
                return redirect(f'{request.path}?scope_id={scope_id}')
            return redirect(f'{request.path}?mode=new')
        if request.POST.get('action') == 'save_binding':
            return self._save_binding_response(request, kwargs)
        try:
            saved, hash_changed = self.bug_trend_facade.save_scope_config(request.POST)
        except ValueError as error:
            context = self.get_context_data(**kwargs)
            context['config'] = self.bug_trend_facade.scope_config_from_post(request.POST)
            self._populate_scope_editor_context(context, context['config'], request.POST)
            context['scope_config_errors'] = error.args[0] if error.args else {'config': 'Invalid scope config.'}
            return self.render_to_response(context, status=400)
        binding_saved = self._save_provider_binding_if_selected(request.POST, saved.id)
        response = redirect('ui_web:bug_trend_scope_config')
        response['Location'] = f'{response["Location"]}?scope_id={saved.id}&saved=1&hash_changed={int(hash_changed)}&binding_saved={int(binding_saved)}'
        return response

    def _save_binding_response(self, request, kwargs):
        scope_id = request.POST.get('id')
        if not scope_id or not scope_id.isdecimal():
            return redirect('ui_web:bug_trend_scope_config')
        try:
            profile_id = self.bug_trend_facade.selected_scope_provider_profile_id(request.POST)
            self.bug_trend_facade.set_scope_provider_binding(int(scope_id), profile_id or request.POST.get('profile_id', ''))
            response = redirect('ui_web:bug_trend_scope_config')
            response['Location'] = f'{response["Location"]}?scope_id={scope_id}&binding_saved=1'
            return response
        except ValueError as error:
            context = self.get_context_data(**kwargs)
            context['config'] = self.bug_trend_facade.scope_config_from_post(request.POST)
            self._populate_scope_editor_context(context, context['config'], request.POST)
            context['scope_config_errors'] = {'provider_binding': str(error)}
            return self.render_to_response(context, status=400)

    def populate_context(self, context, **kwargs):
        mode = self.request.GET.get('mode')
        duplicate_id = self.request.GET.get('duplicate_scope_id')
        if mode == 'new':
            config = self.bug_trend_facade.new_scope_config(
                self.request.GET.get('provider_id', ''),
                self.request.GET.get('profile_id', ''),
            )
            context['config'] = config
            context['editor_mode'] = 'new'
            self._populate_scope_editor_context(context, config, self.request.GET)
            context['build_page_title'] = 'New Bug Trend Scope'
            return
        if duplicate_id and duplicate_id.isdecimal():
            config = self.bug_trend_facade.duplicate_scope_config(int(duplicate_id))
            context['config'] = config
            context['editor_mode'] = 'duplicate'
            context['source_scope_id'] = duplicate_id
            self._populate_scope_editor_context(context, config, self.request.GET)
            context['build_page_title'] = 'Duplicate Bug Trend Scope'
            return
        scope_id = self.request.GET.get('scope_id')
        if not scope_id or not scope_id.isdecimal():
            context['config'] = None
            context['scope_config_errors'] = {'scope_id': 'A valid scope id is required.'}
            context['build_page_title'] = 'Bug Trend Saved Scope Config'
            return
        config = self.bug_trend_facade.get_scope_config(
            int(scope_id),
            self.request.GET.get('add_field', ''),
            self.request.GET.get('add_value', ''),
        )
        context['config'] = config
        context['editor_mode'] = 'edit'
        context['saved'] = self.request.GET.get('saved') == '1'
        context['binding_saved'] = self.request.GET.get('binding_saved') == '1'
        context['hash_changed'] = self.request.GET.get('hash_changed') == '1'
        self._populate_scope_editor_context(context, config, self.request.GET)
        context['build_page_title'] = 'Bug Trend Saved Scope Config'

    def _populate_scope_editor_context(self, context, config, query_data=None):
        query_data = query_data or self.request.GET
        context['scope_metadata'] = self._metadata_options(config)
        context['scope_provider_context'] = self.bug_trend_facade.get_scope_config_provider_context(
            config,
            query_data.get('provider_id', ''),
            query_data.get('profile_id', ''),
        )
        context['metadata_scope_id'] = str(config.id or '')

    def _metadata_options(self, config):
        if self.request.GET.get('refresh_metadata') != '1':
            return None
        if self.request.GET.get('provider_id') and self.request.GET.get('provider_id') != 'jira':
            return {'warnings': ['Metadata refresh is currently available for Jira provider only. Use provider profile workflow/readiness for this provider.'], 'options': None}
        return self.bug_trend_facade.get_scope_metadata_options(config, selected_projects_from_query(self.request.GET))

    def _save_provider_binding_if_selected(self, post_data, scope_id: int) -> bool:
        profile_id = self.bug_trend_facade.selected_scope_provider_profile_id(post_data)
        if not profile_id:
            return False
        self.bug_trend_facade.set_scope_provider_binding(scope_id, profile_id)
        return True

    def render_to_response(self, context, **response_kwargs):
        if context.get('scope_config_errors') and context.get('config') is None:
            response_kwargs.setdefault('status', 400)
        return super().render_to_response(context, **response_kwargs)


class BugTrendScopeMetadataView(GracefulTemplateView):
    template_name = 'partials/bug_trend_scope_metadata.html'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def populate_context(self, context, **kwargs):
        scope_id = self.request.GET.get('id') or self.request.GET.get('scope_id')
        has_draft_payload = any(self.request.GET.get(field_name) for field_name in ['name', 'jql', 'bug_type_values'])
        if scope_id and scope_id.isdecimal() and not has_draft_payload:
            config = self.bug_trend_facade.get_scope_config(int(scope_id))
        else:
            config = self.bug_trend_facade.scope_config_from_post(self.request.GET)
        selected_projects = selected_projects_from_query(self.request.GET)
        if self.request.GET.get('provider_id') and self.request.GET.get('provider_id') != 'jira':
            context['scope_metadata'] = {'warnings': ['Metadata refresh is currently available for Jira provider only. Use provider profile workflow/readiness for this provider.'], 'options': None}
        else:
            context['scope_metadata'] = self.bug_trend_facade.get_scope_metadata_options(config, selected_projects)
        context['metadata_scope_id'] = scope_id if scope_id and scope_id.isdecimal() else ''


def selected_projects_from_query(query_data):
    selected_projects = []
    for raw_value in query_data.getlist('selected_project') + query_data.getlist('selected_projects'):
        for value in str(raw_value).replace(',', '\n').split('\n'):
            project = value.strip()
            if project and project not in selected_projects:
                selected_projects.append(project)
    return selected_projects

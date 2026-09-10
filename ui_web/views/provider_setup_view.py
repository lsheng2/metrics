import json
from urllib.parse import urlencode

from django.http import JsonResponse
from django.shortcuts import redirect

from ..container import ui_web_container
from .graceful_template_view import GracefulTemplateView


class ProviderSetupView(GracefulTemplateView):
    template_name = 'provider_setup.html'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def get_template_names(self):
        if self._is_editor_request():
            return ['provider_profile_config.html']
        return [self.template_name]

    def get(self, request, *args, **kwargs):
        export_profile_id = request.GET.get('export_profile_id')
        if export_profile_id:
            package = self.bug_trend_facade.export_provider_profile_package(export_profile_id)
            response = JsonResponse(package, json_dumps_params={'indent': 2})
            response['Content-Disposition'] = f'attachment; filename="provider-profile-{export_profile_id}.json"'
            return response
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        profile_id = request.POST.get('profile_id', '')
        if action in {'save_draft', 'enable_profile'}:
            return self._save_profile_response(request, kwargs, action)
        if action == 'test_connection':
            return self._connection_test_response(request, kwargs)
        if action == 'archive_profile' and profile_id:
            self.bug_trend_facade.archive_provider_profile_config(profile_id)
            return self._setup_redirect({'archived_profile': profile_id})
        if action == 'restore_profile' and profile_id:
            self.bug_trend_facade.restore_provider_profile_config(profile_id)
            return self._setup_redirect({'restored_profile': profile_id})
        if action == 'delete_archived_profile' and profile_id:
            return self._delete_archived_profile_response(request, profile_id)
        if action == 'duplicate_profile' and profile_id:
            duplicate = self.bug_trend_facade.duplicate_provider_profile_config(profile_id)
            return self._setup_redirect({'profile_id': duplicate.profile_id, 'duplicated_profile': duplicate.profile_id})
        if action == 'import_profile':
            return self._import_profile_response(request)
        if action == 'bind_scope' and profile_id and request.POST.get('scope_id', '').isdecimal():
            return self._bind_scope_response(request, profile_id)
        return redirect('ui_web:provider_setup')

    def _save_profile_response(self, request, kwargs, action):
        try:
            post_data = request.POST.copy()
            post_data['lifecycle_state'] = 'enabled' if action == 'enable_profile' else request.POST.get('lifecycle_state', 'draft')
            saved = self.bug_trend_facade.save_provider_profile_config(post_data)
            return self._setup_redirect({'profile_id': saved.profile_id, 'saved': 1})
        except (ValueError, json.JSONDecodeError) as error:
            context = self.get_context_data(**kwargs)
            context['provider_setup_editor'] = self.bug_trend_facade.get_provider_setup_editor(post_data=request.POST)
            context['provider_profile_editor_mode'] = 'edit' if request.POST.get('id') else 'new'
            context['provider_profile_errors'] = self._error_dict(error)
            return self.render_to_response(context, status=400)

    def _connection_test_response(self, request, kwargs):
        try:
            connection_test = self.bug_trend_facade.test_provider_profile_connection(request.POST)
        except (ValueError, json.JSONDecodeError) as error:
            connection_test = {
                'status': 'failed',
                'summary': self._error_message(error),
                'details': {},
            }
        context = self.get_context_data(**kwargs)
        context['provider_setup_editor'] = self.bug_trend_facade.get_provider_setup_editor(post_data=request.POST)
        context['provider_profile_editor_mode'] = 'edit' if request.POST.get('id') else 'new'
        context['provider_connection_test'] = connection_test
        return self.render_to_response(context)

    def _delete_archived_profile_response(self, request, profile_id: str):
        try:
            self.bug_trend_facade.delete_archived_provider_profile_config(
                profile_id,
                request.POST.get('delete_confirmation', ''),
            )
            return self._setup_redirect({'deleted_profile': profile_id})
        except ValueError as error:
            return self._setup_redirect({'delete_error': self._error_message(error)})

    def _import_profile_response(self, request):
        try:
            package = self._profile_import_package(request)
            imported = self.bug_trend_facade.import_provider_profile_package(package)
            return self._setup_redirect({'profile_id': imported.profile_id, 'imported_profile': imported.profile_id})
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
            return self._setup_redirect({'import_error': self._error_message(error)})

    def _bind_scope_response(self, request, profile_id: str):
        try:
            self.bug_trend_facade.set_scope_provider_binding(int(request.POST.get('scope_id')), profile_id)
            return self._setup_redirect({'profile_id': profile_id, 'binding_saved': 1})
        except ValueError as error:
            return self._setup_redirect({'profile_id': profile_id, 'binding_error': self._error_message(error)})

    def populate_context(self, context, **kwargs):
        rows = self.bug_trend_facade.list_provider_profile_rows()
        context['provider_profile_rows'] = rows
        context['provider_setup_summary'] = self.bug_trend_facade.get_provider_setup_summary(rows)
        context['provider_setup_editor'] = self._editor_context()
        context['scope_candidates'] = self.bug_trend_facade.get_scope_library()
        context['saved'] = self.request.GET.get('saved') == '1'
        context['binding_saved'] = self.request.GET.get('binding_saved') == '1'
        context['archived_profile'] = self.request.GET.get('archived_profile')
        context['restored_profile'] = self.request.GET.get('restored_profile')
        context['deleted_profile'] = self.request.GET.get('deleted_profile')
        context['duplicated_profile'] = self.request.GET.get('duplicated_profile')
        context['imported_profile'] = self.request.GET.get('imported_profile')
        context['import_error'] = self.request.GET.get('import_error')
        context['delete_error'] = self.request.GET.get('delete_error')
        context['binding_error'] = self.request.GET.get('binding_error')
        context['provider_profile_editor_mode'] = self._provider_profile_editor_mode()
        context['build_page_title'] = 'Provider Profile Config' if self._is_editor_request() else 'Provider Setup'

    def _is_editor_request(self):
        if self.request.method == 'POST':
            return self.request.POST.get('action') in {'save_draft', 'enable_profile', 'test_connection'}
        return self.request.GET.get('mode') == 'new' or bool(self.request.GET.get('profile_id', ''))

    def _provider_profile_editor_mode(self):
        if self.request.GET.get('mode') == 'new':
            return 'new'
        if self.request.method == 'POST' and not self.request.POST.get('id'):
            return 'new'
        return 'edit'

    def _editor_context(self):
        mode = self.request.GET.get('mode')
        profile_id = self.request.GET.get('profile_id', '')
        provider_id = self.request.GET.get('provider_id', '')
        if mode == 'new' or profile_id:
            return self.bug_trend_facade.get_provider_setup_editor(profile_id, provider_id)
        return None

    def _setup_redirect(self, params: dict):
        response = redirect('ui_web:provider_setup')
        response['Location'] = f'{response["Location"]}?{urlencode(params)}'
        return response

    def _profile_import_package(self, request):
        uploaded_file = request.FILES.get('profile_package')
        if uploaded_file is None:
            raise ValueError({'profile_import': 'Choose a provider profile JSON package to import.'})
        return json.loads(uploaded_file.read().decode('utf-8'))

    def _error_dict(self, error):
        if error.args and isinstance(error.args[0], dict):
            return error.args[0]
        return {'profile': str(error)}

    def _error_message(self, error):
        if error.args and isinstance(error.args[0], dict):
            return '; '.join(str(value) for value in error.args[0].values())
        return str(error)

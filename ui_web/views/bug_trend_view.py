import json
from datetime import date, timedelta
from urllib.parse import urlencode

from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect

from ..container import ui_web_container
from .graceful_template_view import GracefulTemplateView


CHART_DATA_REQUIRED_PARAMS = frozenset({'scope_id', 'begin', 'end', 'chart_id'})
CHART_DATA_OPTIONAL_PARAMS = frozenset()
EVIDENCE_REQUIRED_PARAMS = frozenset({'scope_id', 'begin', 'end', 'run', 'chart_id'})
EVIDENCE_OPTIONAL_PARAMS = frozenset({'bucket', 'series', 'owner', 'status', 'severity', 'component', 'text'})


def validate_query_contract(request, required_params, optional_params):
    provided_params = set(request.GET.keys())
    missing_params = sorted(param for param in required_params if not request.GET.get(param))
    unknown_params = sorted(provided_params - required_params - optional_params)
    if missing_params or unknown_params:
        return JsonResponse({
            'error': 'Invalid Bug Trend API query parameters.',
            'missing_params': missing_params,
            'unknown_params': unknown_params,
        }, status=400)
    return None


def chart_id_error_response(error):
    if isinstance(error, ObjectDoesNotExist):
        return JsonResponse({'error': 'Unknown or unpublished Bug Trend chart.', 'chart_id': ''}, status=400)
    if isinstance(error, ValueError):
        return JsonResponse({'error': str(error)}, status=400)
    return None


def parse_date_query(value: str, field_name: str):
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(f'{field_name} must be an ISO date.')


class BugTrendView(GracefulTemplateView):
    template_name = 'bug_trend.html'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['partials/bug_trend_content.html']
        return [self.template_name]

    def populate_context(self, context, **kwargs):
        self._populate_common_context(context)
        scope_options = context['scope_options']
        if not scope_options:
            context['chart_json'] = '{}'
            context['selected_scope_id'] = ''
            context['unavailable_reason'] = 'Create a scope before opening the bug trend dashboard.'
            return

        selected_scope_id = int(self.request.GET.get('scope_id') or scope_options[0].id)
        active_chart_id = self.request.GET.get('chart_id') or 'default_bug_trend'
        active_chart = self._active_chart_option(context['chart_options'], active_chart_id)
        begin, end = self._date_range()
        try:
            chart_data = self.bug_trend_facade.get_chart_data(selected_scope_id, begin, end, active_chart_id)
        except ObjectDoesNotExist:
            active_chart_id = 'default_bug_trend'
            active_chart = self._active_chart_option(context['chart_options'], active_chart_id)
            chart_data = self.bug_trend_facade.get_chart_data(selected_scope_id, begin, end, active_chart_id)
        evidence = None
        evidence_unavailable_reason = ''
        if active_chart and active_chart.capability == 'summary_only':
            evidence_unavailable_reason = active_chart.unsupported_reason or 'Selected chart does not support ticket evidence.'
        elif chart_data.current_evidence_available:
            evidence = self.bug_trend_facade.get_evidence_data(selected_scope_id, begin, end, calculation_run_id=chart_data.calculation_run_id, active_chart_id=active_chart_id)
        context['selected_scope_id'] = selected_scope_id
        context['active_chart_id'] = active_chart_id
        context['begin'] = begin.isoformat()
        context['end'] = end.isoformat()
        context['chart_json'] = self.bug_trend_facade.get_chart_json(chart_data)
        context['unavailable_reason'] = chart_data.unavailable_reason
        context['run_metadata'] = chart_data.run_metadata or {}
        context['evidence'] = evidence
        context['evidence_unavailable_reason'] = evidence_unavailable_reason

    def _populate_common_context(self, context):
        context['scope_options'] = self.bug_trend_facade.get_scope_options()
        context['chart_options'] = self.bug_trend_facade.get_chart_options()
        context['build_page_title'] = 'Bug Trend Indicator'

    def _date_range(self):
        today = date.today()
        default_begin = today - timedelta(days=27)
        begin = parse_date_query(self.request.GET.get('begin') or default_begin.isoformat(), 'begin')
        end = parse_date_query(self.request.GET.get('end') or today.isoformat(), 'end')
        return begin, end

    def _active_chart_option(self, chart_options, chart_id):
        return next((chart for chart in chart_options if chart.chart_id == chart_id), None)


class BugTrendEvidenceView(GracefulTemplateView):
    template_name = 'partials/bug_trend_evidence.html'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def get(self, request, *args, **kwargs):
        invalid_response = validate_query_contract(request, EVIDENCE_REQUIRED_PARAMS, EVIDENCE_OPTIONAL_PARAMS)
        if invalid_response:
            return invalid_response
        return super().get(request, *args, **kwargs)

    def populate_context(self, context, **kwargs):
        begin, end = self._date_range()
        evidence = self.bug_trend_facade.get_evidence_data(
            scope_id=int(self.request.GET.get('scope_id')),
            begin=begin,
            end=end,
            calculation_run_id=self.request.GET.get('run', ''),
            bucket_id=self.request.GET.get('bucket', ''),
            series_name=self.request.GET.get('series', ''),
            owner=self.request.GET.get('owner', ''),
            status=self.request.GET.get('status', ''),
            severity=self.request.GET.get('severity', ''),
            component=self.request.GET.get('component', ''),
            text=self.request.GET.get('text', ''),
            active_chart_id=self.request.GET.get('chart_id'),
        )
        context['evidence'] = evidence

    def _date_range(self):
        begin = parse_date_query(self.request.GET.get('begin'), 'begin')
        end = parse_date_query(self.request.GET.get('end'), 'end')
        return begin, end


class BugTrendEvidenceExportView(GracefulTemplateView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def get(self, request, *args, **kwargs):
        invalid_response = validate_query_contract(request, EVIDENCE_REQUIRED_PARAMS, EVIDENCE_OPTIONAL_PARAMS)
        if invalid_response:
            return invalid_response
        try:
            begin, end = self._date_range()
            export = self.bug_trend_facade.export_evidence_data(
                scope_id=int(request.GET.get('scope_id')),
                begin=begin,
                end=end,
                calculation_run_id=request.GET.get('run', ''),
                bucket_id=request.GET.get('bucket', ''),
                series_name=request.GET.get('series', ''),
                owner=request.GET.get('owner', ''),
                status=request.GET.get('status', ''),
                severity=request.GET.get('severity', ''),
                component=request.GET.get('component', ''),
                text=request.GET.get('text', ''),
                active_chart_id=request.GET.get('chart_id'),
            )
        except (ObjectDoesNotExist, ValueError) as error:
            return chart_id_error_response(error)
        response = HttpResponse(export.content, content_type=export.content_type)
        response['Content-Disposition'] = f'attachment; filename="{export.filename}"'
        return response

    def _date_range(self):
        begin = parse_date_query(self.request.GET.get('begin'), 'begin')
        end = parse_date_query(self.request.GET.get('end'), 'end')
        return begin, end


class BugTrendScopeAuditView(GracefulTemplateView):
    template_name = 'bug_trend_scope_audit.html'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def populate_context(self, context, **kwargs):
        audit = self.bug_trend_facade.get_scope_audit_data(int(self.request.GET.get('scope_id')))
        context['audit'] = audit
        context['build_page_title'] = 'Bug Trend Scope Audit'


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
            try:
                self.bug_trend_facade.delete_archived_scope_config(int(scope_id), request.POST.get('delete_confirmation', ''))
                return self._library_redirect({'deleted': 1})
            except ValueError as error:
                return self._library_redirect({'delete_error': self._error_message(error)})
        if action == 'import_scope':
            try:
                package = self._scope_import_package(request)
                imported = self.bug_trend_facade.import_scope_config_package(package)
                return self._library_redirect({'imported_scope': imported.name})
            except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
                return self._library_redirect({'import_error': self._error_message(error)})
        if action == 'confirm_binding' and scope_id and scope_id.isdecimal():
            self.bug_trend_facade.confirm_scope_provider_binding(int(scope_id))
        if action == 'bulk_confirm_bindings':
            result = self.bug_trend_facade.bulk_confirm_scope_provider_bindings()
            response = redirect('ui_web:bug_trend_scope_library')
            response['Location'] = (
                f'{response["Location"]}?bulk_changed={result.get("changed_count", 0)}'
                f'&bulk_skipped={result.get("skipped_count", 0)}'
            )
            return response
        if action == 'save_binding' and scope_id and scope_id.isdecimal():
            try:
                self.bug_trend_facade.set_scope_provider_binding(int(scope_id), request.POST.get('profile_id', ''))
            except ValueError:
                pass
        return redirect('ui_web:bug_trend_scope_library')

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
        if action == 'test_connection':
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
        if action == 'archive_profile' and profile_id:
            self.bug_trend_facade.archive_provider_profile_config(profile_id)
            return self._setup_redirect({'archived_profile': profile_id})
        if action == 'restore_profile' and profile_id:
            self.bug_trend_facade.restore_provider_profile_config(profile_id)
            return self._setup_redirect({'restored_profile': profile_id})
        if action == 'delete_archived_profile' and profile_id:
            try:
                self.bug_trend_facade.delete_archived_provider_profile_config(profile_id, request.POST.get('delete_confirmation', ''))
                return self._setup_redirect({'deleted_profile': profile_id})
            except ValueError as error:
                return self._setup_redirect({'delete_error': self._error_message(error)})
        if action == 'duplicate_profile' and profile_id:
            duplicate = self.bug_trend_facade.duplicate_provider_profile_config(profile_id)
            return self._setup_redirect({'profile_id': duplicate.profile_id, 'duplicated_profile': duplicate.profile_id})
        if action == 'import_profile':
            try:
                package = self._profile_import_package(request)
                imported = self.bug_trend_facade.import_provider_profile_package(package)
                return self._setup_redirect({'profile_id': imported.profile_id, 'imported_profile': imported.profile_id})
            except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
                return self._setup_redirect({'import_error': self._error_message(error)})
        if action == 'bind_scope' and profile_id and request.POST.get('scope_id', '').isdecimal():
            try:
                self.bug_trend_facade.set_scope_provider_binding(int(request.POST.get('scope_id')), profile_id)
                return self._setup_redirect({'profile_id': profile_id, 'binding_saved': 1})
            except ValueError as error:
                return self._setup_redirect({'profile_id': profile_id, 'binding_error': self._error_message(error)})
        return redirect('ui_web:provider_setup')

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
            scope_id = request.POST.get('id')
            if scope_id and scope_id.isdecimal():
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
        selected_projects = self._selected_projects()
        return self.bug_trend_facade.get_scope_metadata_options(config, selected_projects)

    def _save_provider_binding_if_selected(self, post_data, scope_id: int) -> bool:
        profile_id = self.bug_trend_facade.selected_scope_provider_profile_id(post_data)
        if not profile_id:
            return False
        self.bug_trend_facade.set_scope_provider_binding(scope_id, profile_id)
        return True

    def _selected_projects(self):
        return selected_projects_from_query(self.request.GET)

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

class BugTrendChartDataApiView(GracefulTemplateView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def get(self, request, *args, **kwargs):
        invalid_response = validate_query_contract(request, CHART_DATA_REQUIRED_PARAMS, CHART_DATA_OPTIONAL_PARAMS)
        if invalid_response:
            return invalid_response
        try:
            begin, end = self._date_range()
            chart_data = self.bug_trend_facade.get_chart_data(int(request.GET.get('scope_id')), begin, end, request.GET.get('chart_id'))
        except (ObjectDoesNotExist, ValueError) as error:
            return chart_id_error_response(error)
        return JsonResponse(self.bug_trend_facade.get_chart_payload(chart_data))

    def _date_range(self):
        begin = parse_date_query(self.request.GET.get('begin'), 'begin')
        end = parse_date_query(self.request.GET.get('end'), 'end')
        return begin, end


class BugTrendEvidenceApiView(GracefulTemplateView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def get(self, request, *args, **kwargs):
        invalid_response = validate_query_contract(request, EVIDENCE_REQUIRED_PARAMS, EVIDENCE_OPTIONAL_PARAMS)
        if invalid_response:
            return invalid_response
        try:
            begin, end = self._date_range()
            evidence = self.bug_trend_facade.get_evidence_data(
                scope_id=int(request.GET.get('scope_id')),
                begin=begin,
                end=end,
                calculation_run_id=request.GET.get('run', ''),
                bucket_id=request.GET.get('bucket', ''),
                series_name=request.GET.get('series', ''),
                owner=request.GET.get('owner', ''),
                status=request.GET.get('status', ''),
                severity=request.GET.get('severity', ''),
                component=request.GET.get('component', ''),
                text=request.GET.get('text', ''),
                active_chart_id=request.GET.get('chart_id'),
            )
        except (ObjectDoesNotExist, ValueError) as error:
            return chart_id_error_response(error)
        return JsonResponse(self.bug_trend_facade.get_evidence_payload(evidence))

    def _date_range(self):
        begin = parse_date_query(self.request.GET.get('begin'), 'begin')
        end = parse_date_query(self.request.GET.get('end'), 'end')
        return begin, end

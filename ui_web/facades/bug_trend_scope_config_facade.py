from bug_metrics.app.api.scope_config import SEMANTIC_LIST_FIELDS, SavedScopeConfig, normalize_scope_list_values, saved_scope_config_from_dict
from bug_metrics.models import JiraScopeConfig
from jira_sync.app.api.jira_query_builder import JiraScopeQueryBuilder

from ..data.bug_trend_data import BugTrendProviderProfileChoice, BugTrendScopeBindingData, BugTrendScopeConfigProviderContext, BugTrendScopeLibraryRow, BugTrendScopeLibraryScopeData, BugTrendScopeOption
from .bug_trend_scope_profile import resolve_scope_provider_binding
from .provider_scope_setup import default_provider_id, provider_detail_rows, provider_id_for_profile, provider_profile_choices_for, provider_setup_options, provider_setup_template, selected_profile_for, selected_profile_id_for


SEMANTIC_MAPPING_TEXT_FIELDS = {
    'severity_field',
    'component_field',
    'owner_field',
    'milestone_field',
    'fix_version_field',
    'package_version_field',
}

QUERY_BUILDER_LIST_FIELDS = {
    'query_builder_issue_types': 'issue_types',
    'query_builder_components': 'components',
    'query_builder_affected_versions': 'affected_versions',
    'query_builder_fix_versions': 'fix_versions',
    'query_builder_priorities': 'priorities',
    'query_builder_resolutions': 'resolutions',
    'query_builder_security_levels': 'security_levels',
    'query_builder_labels': 'labels',
}

QUERY_BUILDER_CUSTOM_FIELD_ROWS = range(1, 7)


class BugTrendScopeConfigFacadeMixin:
    def get_scope_options(self):
        options = []
        for scope in self._bug_trend_api.list_enabled_scopes():
            binding = resolve_scope_provider_binding(self._bug_trend_api, scope)
            options.append(BugTrendScopeOption(
                scope.id,
                scope.name,
                self._scope_label(scope),
                binding.profile_id,
                binding.provider_id,
                binding.status,
                binding.blockers,
            ))
        return options

    def get_scope_library(self):
        return self._bug_trend_api.list_scope_configs()

    def get_scope_library_rows(self):
        if not hasattr(self._bug_trend_api, 'list_scope_provider_bindings'):
            return [
                BugTrendScopeLibraryRow(self._saved_scope_data(scope), BugTrendScopeBindingData('', '', 'configuration_required', '-', [], False, True))
                for scope in self.get_scope_library()
            ]
        configs_by_id = {config.id: config for config in self.get_scope_library()}
        rows = []
        for scope, binding in self._bug_trend_api.list_scope_provider_bindings():
            config = configs_by_id.get(scope.id)
            if not config:
                continue
            rows.append(self._scope_library_row(config, binding))
        return rows

    def get_scope_library_summary(self, rows=None) -> dict:
        rows = rows if rows is not None else self.get_scope_library_rows()
        return {
            'total': len(rows),
            'saved_scope_count': len(rows),
            'compatibility_ready_count': sum(1 for row in rows if row.binding.can_confirm),
            'needs_attention_count': sum(1 for row in rows if row.binding.can_edit),
        }

    def get_scope_binding_policy(self) -> str:
        if not hasattr(self._bug_trend_api, 'get_scope_binding_policy'):
            return 'compatibility_allowed'
        return self._bug_trend_api.get_scope_binding_policy()

    def get_scope_binding_audit_events(self, limit: int = 12) -> list[dict]:
        if not hasattr(self._bug_trend_api, 'list_scope_binding_audit_events'):
            return []
        return self._bug_trend_api.list_scope_binding_audit_events(limit)

    def confirm_scope_provider_binding(self, scope_id: int):
        return self._bug_trend_api.confirm_scope_provider_binding(scope_id)

    def bulk_confirm_scope_provider_bindings(self):
        if not hasattr(self._bug_trend_api, 'bulk_confirm_scope_provider_bindings'):
            return {'changed_count': 0, 'skipped_count': 0, 'changed': [], 'skipped': []}
        result = self._bug_trend_api.bulk_confirm_scope_provider_bindings()
        return result.to_dict() if hasattr(result, 'to_dict') else result

    def set_scope_provider_binding(self, scope_id: int, profile_id: str):
        return self._bug_trend_api.set_scope_provider_binding(scope_id, profile_id)

    def get_scope_delete_impact(self, scope_id: int) -> dict:
        if not hasattr(self._bug_trend_api, 'get_scope_delete_impact'):
            return {}
        return self._bug_trend_api.get_scope_delete_impact(scope_id)

    def export_scope_config_package(self, scope_id: int) -> dict:
        return self._bug_trend_api.export_scope_config_package(scope_id)

    def import_scope_config_package(self, package: dict):
        return self._bug_trend_api.import_scope_config_package(package)

    def delete_archived_scope_config(self, scope_id: int, confirmation: str) -> dict:
        return self._bug_trend_api.delete_archived_scope_config(scope_id, confirmation)

    def get_scope_provider_profile_choices(self):
        if not hasattr(self._bug_trend_api, 'list_scope_provider_profile_choices'):
            return []
        return [
            BugTrendProviderProfileChoice(
                choice.get('profile_id', ''),
                choice.get('provider_id', ''),
                choice.get('display_name', ''),
                dict(choice.get('connection_settings', {}) or {}),
                dict(choice.get('scope_labels', {}) or {}),
                dict(choice.get('source_population', {}) or {}),
                choice.get('mapping_version_hash', ''),
            )
            for choice in self._bug_trend_api.list_scope_provider_profile_choices()
        ]

    def get_scope_provider_binding_health(self) -> dict:
        if not hasattr(self._bug_trend_api, 'get_scope_provider_binding_health'):
            return {'total': 0, 'counts': {}, 'rows': []}
        return self._bug_trend_api.get_scope_provider_binding_health()

    def get_scope_config_provider_context(
        self,
        config: SavedScopeConfig,
        selected_provider_id: str = '',
        selected_profile_id: str = '',
    ) -> BugTrendScopeConfigProviderContext:
        profile_choices = self.get_scope_provider_profile_choices()
        requested_provider_id = selected_provider_id
        requested_profile_id = selected_profile_id
        selected_provider_id = self._selected_provider_id(profile_choices, requested_provider_id, requested_profile_id, '')
        selected_profile_id = selected_profile_id_for(profile_choices, selected_provider_id, requested_profile_id, '')
        selected_profile = selected_profile_for(profile_choices, selected_profile_id)
        selected_template = provider_setup_template(selected_provider_id)
        if config.id is None:
            return BugTrendScopeConfigProviderContext(
                selected_profile_id,
                selected_provider_id,
                'draft',
                'Save draft with a provider profile to create an explicit binding, or repair it later from Scope Library.',
                [],
                profile_choices,
                False,
                selected_provider_id,
                selected_template.metadata_supported,
                selected_template.metadata_summary,
                selected_provider_id,
                selected_profile_id,
                provider_profile_choices_for(profile_choices, selected_provider_id),
                provider_setup_options(profile_choices, selected_provider_id),
                selected_template.label,
                selected_template.color,
                selected_template.summary,
                selected_template.source_query_label,
                selected_template.source_query_help,
                provider_detail_rows(selected_template, selected_profile),
            )
        binding = self._scope_config_binding_data(config)
        selected_provider_id = self._selected_provider_id(profile_choices, requested_provider_id, requested_profile_id, binding.provider_id)
        selected_profile_id = selected_profile_id_for(profile_choices, selected_provider_id, requested_profile_id, binding.profile_id)
        selected_profile = selected_profile_for(profile_choices, selected_profile_id)
        selected_template = provider_setup_template(selected_provider_id)
        return BugTrendScopeConfigProviderContext(
            binding.profile_id,
            binding.provider_id,
            binding.status,
            binding.provenance_summary,
            binding.blockers,
            profile_choices,
            True,
            selected_provider_id,
            selected_template.metadata_supported,
            selected_template.metadata_summary,
            selected_provider_id,
            selected_profile_id,
            provider_profile_choices_for(profile_choices, selected_provider_id),
            provider_setup_options(profile_choices, selected_provider_id),
            selected_template.label,
            selected_template.color,
            selected_template.summary,
            selected_template.source_query_label,
            selected_template.source_query_help,
            provider_detail_rows(selected_template, selected_profile),
        )

    def _binding_data(self, binding) -> BugTrendScopeBindingData:
        provenance = dict(getattr(binding, 'provenance', {}) or {})
        provenance_summary = provenance.get('matched_by') or provenance.get('source') or '-'
        return BugTrendScopeBindingData(
            binding.profile_id,
            binding.provider_id,
            binding.status,
            provenance_summary,
            list(binding.blockers or []),
            binding.status == 'compatibility' and bool(binding.profile_id and binding.provider_id),
            binding.status not in {'explicit', 'disabled'},
        )

    def _scope_config_binding_data(self, config: SavedScopeConfig) -> BugTrendScopeBindingData:
        if hasattr(self._bug_trend_api, 'list_scope_provider_bindings'):
            for scope, binding in self._bug_trend_api.list_scope_provider_bindings():
                if str(scope.id) == str(config.id):
                    return self._binding_data(binding)
        return self._binding_data(resolve_scope_provider_binding(self._bug_trend_api, config))

    def selected_scope_provider_profile_id(self, post_data) -> str:
        provider_id = str(post_data.get('provider_id', '') or '').strip()
        profile_id = str(post_data.get('profile_id', '') or '').strip()
        if not provider_id or not profile_id:
            return ''
        profile_choices = self.get_scope_provider_profile_choices()
        return profile_id if provider_id_for_profile(profile_choices, profile_id) == provider_id else ''

    def _selected_provider_id(
        self,
        profile_choices: list[BugTrendProviderProfileChoice],
        requested_provider_id: str,
        requested_profile_id: str,
        current_provider_id: str,
    ) -> str:
        requested_provider_id = str(requested_provider_id or '').strip().lower()
        if requested_provider_id:
            return requested_provider_id
        profile_provider_id = provider_id_for_profile(profile_choices, requested_profile_id)
        if profile_provider_id:
            return profile_provider_id
        if current_provider_id:
            return current_provider_id
        return default_provider_id(profile_choices)

    def _scope_library_row(self, scope, binding) -> BugTrendScopeLibraryRow:
        return BugTrendScopeLibraryRow(
            self._saved_scope_data(scope),
            self._binding_data(binding),
            delete_impact=self.get_scope_delete_impact(scope.id),
            delete_confirmation=f'DELETE {scope.name}',
        )

    def _saved_scope_data(self, scope) -> BugTrendScopeLibraryScopeData:
        return BugTrendScopeLibraryScopeData(
            str(scope.id),
            scope.name,
            scope.ip,
            scope.project_label,
            scope.enabled,
            scope.config_version_hash,
        )

    def _scope_label(self, scope):
        parts = [part for part in [scope.ip, scope.project_label, scope.name] if part]
        return ' / '.join(parts) if parts else scope.name

    def get_scope_config(self, scope_id: int, add_field: str = '', add_value: str = '') -> SavedScopeConfig:
        config = self._bug_trend_api.get_scope_config(scope_id)
        if add_field in SEMANTIC_LIST_FIELDS and add_value:
            values = list(getattr(config, add_field))
            if add_value not in values:
                values.append(add_value)
                setattr(config, add_field, values)
        if add_field in SEMANTIC_MAPPING_TEXT_FIELDS and add_value:
            setattr(config, add_field, add_value)
        return config

    def new_scope_config(self, provider_id: str = '', profile_id: str = '') -> SavedScopeConfig:
        payload = {
            'id': None,
            'name': '',
            'ip': '',
            'project_label': '',
            'jql': '',
            'owner_field': 'assignee',
            'timezone': 'UTC',
            'bucket_granularity': JiraScopeConfig.GRANULARITY_WEEKLY,
            'enabled': False,
        }
        if profile_id:
            payload.update(self._scope_defaults_from_profile(profile_id))
        return saved_scope_config_from_dict(payload)

    def duplicate_scope_config(self, scope_id: int) -> SavedScopeConfig:
        source = self._bug_trend_api.get_scope_config(scope_id)
        return SavedScopeConfig(
            id=None,
            name=f'{source.name} copy',
            ip=source.ip,
            project_label=source.project_label,
            jql=source.jql,
            bug_type_values=list(source.bug_type_values),
            open_status_values=list(source.open_status_values),
            fixed_status_values=list(source.fixed_status_values),
            closed_status_values=list(source.closed_status_values),
            terminal_excluded_status_values=list(source.terminal_excluded_status_values),
            fixed_resolution_values=list(source.fixed_resolution_values),
            closed_resolution_values=list(source.closed_resolution_values),
            reopen_status_values=list(source.reopen_status_values),
            severity_field=source.severity_field,
            critical_high_values=list(source.critical_high_values),
            medium_low_values=list(source.medium_low_values),
            component_field=source.component_field,
            owner_field=source.owner_field,
            team_field=source.team_field,
            milestone_field=source.milestone_field,
            fix_version_field=source.fix_version_field,
            package_version_field=source.package_version_field,
            display_fields=list(source.display_fields),
            timezone=source.timezone,
            bucket_granularity=source.bucket_granularity,
            enabled=False,
            source_mode=source.source_mode,
            query_builder_state=dict(source.query_builder_state or {}),
            config_version_hash='',
        )

    def disable_scope_config(self, scope_id: int):
        return self._bug_trend_api.disable_scope_config(scope_id)

    def get_scope_metadata_options(self, config: SavedScopeConfig, selected_projects: list[str] = None):
        if self._scope_metadata_api is None:
            return None
        try:
            return self._scope_metadata_api.discover_scope_options('jira', config.jql, selected_projects or [], config.bug_type_values, refresh=True)
        except Exception as error:
            return {'warnings': [f'Metadata refresh failed: {error}']}

    def save_scope_config(self, post_data) -> tuple[SavedScopeConfig, bool]:
        config = self.scope_config_from_post(post_data)
        if post_data.get('id') and config.id is None:
            raise ValueError({'id': 'Scope id must be numeric.'})
        persisted = self._bug_trend_api.get_scope_config(config.id) if config.id else None
        original_hash = persisted.config_version_hash if persisted else ''
        action = post_data.get('action')
        if action == 'save_enable':
            config.enabled = True
        elif config.id is not None and persisted is not None:
            config.enabled = persisted.enabled
        elif action == 'save_draft' and config.id is None:
            config.enabled = False
        saved = self._bug_trend_api.save_scope_config(config)
        return saved, saved.config_version_hash != original_hash

    def scope_config_from_post(self, post_data) -> SavedScopeConfig:
        source_mode = self._source_mode(post_data.get('source_mode', ''))
        query_builder_state = {}
        jql = post_data.get('jql', '')
        if source_mode == JiraScopeConfig.SOURCE_MODE_QUERY_BUILDER:
            query_builder_state = self._query_builder_state_from_post(post_data)
            jql = JiraScopeQueryBuilder().build(query_builder_state)
        payload = {field_name: post_data.get(field_name, '') for field_name in [
            'id', 'name', 'ip', 'project_label', 'severity_field', 'component_field',
            'owner_field', 'team_field', 'milestone_field', 'fix_version_field',
            'package_version_field', 'timezone', 'bucket_granularity',
        ]}
        payload['source_mode'] = source_mode
        payload['jql'] = jql
        payload['query_builder_state'] = query_builder_state
        try:
            payload['id'] = int(payload['id']) if payload['id'] else None
        except ValueError:
            payload['id'] = None
        payload['enabled'] = post_data.get('enabled') == 'on'
        for field_name in SEMANTIC_LIST_FIELDS:
            payload[field_name] = self._parse_list_field(post_data.get(field_name, ''))
        return saved_scope_config_from_dict(payload)

    def _parse_list_field(self, value: str) -> list[str]:
        return normalize_scope_list_values(value)

    def source_mode_context(self, config: SavedScopeConfig, query_data=None) -> dict:
        preview_config = self._preview_source_config(config, query_data)
        builder_state = dict(preview_config.query_builder_state or {})
        source_mode = self._source_mode(preview_config.source_mode)
        return {
            'mode': source_mode,
            'custom_jql_active': source_mode == JiraScopeConfig.SOURCE_MODE_CUSTOM_JQL,
            'query_builder_active': source_mode == JiraScopeConfig.SOURCE_MODE_QUERY_BUILDER,
            'custom_jql_value': preview_config.jql if source_mode == JiraScopeConfig.SOURCE_MODE_CUSTOM_JQL else config.jql,
            'query_builder_state': builder_state,
            'query_builder_jql': JiraScopeQueryBuilder().build(builder_state),
            'custom_jql_mode': JiraScopeConfig.SOURCE_MODE_CUSTOM_JQL,
            'query_builder_mode': JiraScopeConfig.SOURCE_MODE_QUERY_BUILDER,
        }

    def _preview_source_config(self, config: SavedScopeConfig, query_data) -> SavedScopeConfig:
        if query_data is None or not self._has_query_builder_request(query_data):
            return config
        preview = self.scope_config_from_post(query_data)
        for field_name in [
            'id',
            'name',
            'ip',
            'project_label',
            'bug_type_values',
            'open_status_values',
            'fixed_status_values',
            'closed_status_values',
            'terminal_excluded_status_values',
            'fixed_resolution_values',
            'closed_resolution_values',
            'reopen_status_values',
            'severity_field',
            'critical_high_values',
            'medium_low_values',
            'component_field',
            'owner_field',
            'team_field',
            'milestone_field',
            'fix_version_field',
            'package_version_field',
            'display_fields',
            'timezone',
            'bucket_granularity',
            'enabled',
            'config_version_hash',
        ]:
            if not getattr(preview, field_name):
                setattr(preview, field_name, getattr(config, field_name))
        return preview

    def _has_query_builder_request(self, post_data) -> bool:
        if post_data.get('source_mode'):
            return True
        if post_data.get('query_builder_project'):
            return True
        return any(post_data.get(field_name) for field_name in QUERY_BUILDER_LIST_FIELDS)

    def _source_mode(self, raw_source_mode: str) -> str:
        source_mode = str(raw_source_mode or '').strip()
        if source_mode == JiraScopeConfig.SOURCE_MODE_QUERY_BUILDER:
            return JiraScopeConfig.SOURCE_MODE_QUERY_BUILDER
        return JiraScopeConfig.SOURCE_MODE_CUSTOM_JQL

    def _query_builder_state_from_post(self, post_data) -> dict:
        state = {}
        project = str(post_data.get('query_builder_project', '') or '').strip()
        if project:
            state['project'] = project
        for post_field_name, state_field_name in QUERY_BUILDER_LIST_FIELDS.items():
            values = self._parse_post_values(post_data, post_field_name)
            if values:
                state[state_field_name] = values
        custom_fields = self._query_builder_custom_fields_from_post(post_data)
        if custom_fields:
            state['custom_fields'] = custom_fields
        return state

    def _query_builder_custom_fields_from_post(self, post_data) -> list[dict]:
        custom_fields = []
        for field_name, values in self._repeated_custom_field_filters(post_data):
            if field_name and values:
                custom_fields.append({'field': field_name, 'values': values})
        for index in QUERY_BUILDER_CUSTOM_FIELD_ROWS:
            field_name = str(post_data.get(f'query_builder_custom_field_{index}', '') or '').strip()
            values = self._parse_post_values(post_data, f'query_builder_custom_values_{index}')
            if field_name and values:
                custom_fields.append({'field': field_name, 'values': values})
        return custom_fields

    def _repeated_custom_field_filters(self, post_data):
        field_names = self._raw_post_values(post_data, 'query_builder_custom_field')
        values_list = self._raw_post_values(post_data, 'query_builder_custom_values')
        for index, field_name in enumerate(field_names):
            values = values_list[index] if index < len(values_list) else ''
            yield str(field_name or '').strip(), self._parse_list_field(values)

    def _parse_post_values(self, post_data, field_name: str) -> list[str]:
        return normalize_scope_list_values(self._raw_post_values(post_data, field_name))

    def _raw_post_values(self, post_data, field_name: str):
        if hasattr(post_data, 'getlist'):
            return post_data.getlist(field_name)
        value = post_data.get(field_name, '')
        return value if isinstance(value, list) else [value]

    def _scope_defaults_from_profile(self, profile_id: str) -> dict:
        profile = self._bug_trend_api.get_provider_profile_config(profile_id)
        value_mappings = dict(profile.value_mappings or {})
        field_bindings = dict(profile.field_bindings or {})
        source_population = dict(profile.source_population or {})
        return {
            'name': profile.profile_id,
            'ip': dict(profile.scope_labels or {}).get('ip', ''),
            'project_label': dict(profile.scope_labels or {}).get('project_or_product', ''),
            'jql': source_population.get('native_query_text') or source_population.get('source_query_ref') or '',
            'bug_type_values': value_mappings.get('bug_type_values', []),
            'open_status_values': value_mappings.get('open_status_values', []),
            'fixed_status_values': value_mappings.get('fixed_status_values', []),
            'closed_status_values': value_mappings.get('closed_status_values', []),
            'critical_high_values': value_mappings.get('critical_high_values', []),
            'medium_low_values': value_mappings.get('medium_low_values', []),
            'severity_field': self._native_field(field_bindings, 'severity'),
            'component_field': self._native_field(field_bindings, 'component'),
            'owner_field': self._native_field(field_bindings, 'owner') or 'assignee',
            'milestone_field': self._native_field(field_bindings, 'milestone'),
            'fix_version_field': self._native_field(field_bindings, 'release'),
        }

    def _native_field(self, field_bindings: dict, canonical_field: str) -> str:
        binding = field_bindings.get(canonical_field, {})
        return binding.get('native_field', '') if isinstance(binding, dict) else ''

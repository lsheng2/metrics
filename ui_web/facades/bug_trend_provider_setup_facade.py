import json
from dataclasses import replace

from django.conf import settings

from bug_metrics.app.api.provider_profile_config import PROFILE_JSON_FIELDS, provider_profile_config_from_post
from bug_metrics.provider_profile_security import without_profile_secret_values

from ..data.bug_trend_data import BugTrendProviderProfileChoice, BugTrendProviderProfileRow, BugTrendProviderSetupEditor
from .provider_scope_setup import provider_detail_rows, provider_setup_options, provider_setup_template


class BugTrendProviderSetupFacadeMixin:
    def list_provider_profile_rows(self) -> list[BugTrendProviderProfileRow]:
        return [
            self._provider_profile_config_row(profile)
            for profile in self._bug_trend_api.list_provider_profile_configs()
        ]

    def get_provider_setup_summary(self, rows=None) -> dict:
        rows = rows if rows is not None else self.list_provider_profile_rows()
        return {
            'total': len(rows),
            'enabled': sum(1 for row in rows if row.lifecycle_state == 'enabled'),
            'draft': sum(1 for row in rows if row.lifecycle_state == 'draft'),
            'archived': sum(1 for row in rows if row.lifecycle_state == 'archived'),
            'jira': sum(1 for row in rows if row.provider_id == 'jira'),
            'hsdes': sum(1 for row in rows if row.provider_id == 'hsdes'),
        }

    def get_provider_setup_editor(self, profile_id: str = '', provider_id: str = '', post_data=None) -> BugTrendProviderSetupEditor:
        if post_data is not None:
            profile = provider_profile_config_from_post(post_data)
        elif profile_id:
            profile = self._bug_trend_api.get_provider_profile_config(profile_id)
        else:
            profile = self._bug_trend_api.new_provider_profile_config(provider_id or 'jira')
        display_profile = self._display_profile_config(profile)
        selected_provider_id = profile.provider_id if profile_id and post_data is None else provider_id or profile.provider_id
        profile_choices = self.get_scope_provider_profile_choices()
        template = provider_setup_template(selected_provider_id)
        return BugTrendProviderSetupEditor(
            display_profile,
            provider_setup_options(profile_choices, selected_provider_id, allow_template_creation=True),
            selected_provider_id,
            template.label,
            template.color,
            template.summary,
            template.source_query_label,
            template.source_query_help,
            template.metadata_supported,
            template.metadata_summary,
            provider_detail_rows(template, self._profile_choice_from_config(display_profile)),
            self._provider_profile_json_fields(display_profile),
            json.dumps(without_profile_secret_values(display_profile.connection_settings or {}), sort_keys=True),
            display_profile.connection_settings.get('connection_status_label', 'Configuration required'),
        )

    def save_provider_profile_config(self, post_data):
        return self._bug_trend_api.save_provider_profile_config(provider_profile_config_from_post(post_data))

    def test_provider_profile_connection(self, post_data):
        return self._bug_trend_api.test_provider_profile_connection(provider_profile_config_from_post(post_data))

    def duplicate_provider_profile_config(self, profile_id: str):
        return self._bug_trend_api.duplicate_provider_profile_config(profile_id)

    def archive_provider_profile_config(self, profile_id: str):
        return self._bug_trend_api.archive_provider_profile_config(profile_id)

    def restore_provider_profile_config(self, profile_id: str):
        return self._bug_trend_api.restore_provider_profile_config(profile_id)

    def delete_archived_provider_profile_config(self, profile_id: str, confirmation: str) -> dict:
        return self._bug_trend_api.delete_archived_provider_profile_config(profile_id, confirmation)

    def export_provider_profile_package(self, profile_id: str) -> dict:
        return self._bug_trend_api.export_provider_profile_package(profile_id)

    def import_provider_profile_package(self, package: dict):
        return self._bug_trend_api.import_provider_profile_package(package)

    def _provider_profile_config_row(self, profile) -> BugTrendProviderProfileRow:
        template = provider_setup_template(profile.provider_id)
        return BugTrendProviderProfileRow(
            profile.profile_id,
            profile.provider_id,
            template.label,
            template.color,
            profile.display_name,
            profile.lifecycle_state,
            profile.source_kind,
            self._provider_source_summary(profile),
            profile.mapping_version_hash,
            profile.source_version_hash,
            self._bug_trend_api.get_provider_profile_delete_impact(profile.profile_id),
            f'DELETE {profile.profile_id}',
        )

    def _display_profile_config(self, profile):
        return replace(profile, connection_settings=self._display_connection_settings(profile.provider_id, profile.connection_settings))

    def _display_connection_settings(self, provider_id: str, connection_settings: dict) -> dict:
        display_settings = dict(connection_settings or {})
        display_settings['base_url'] = self._settings_reference_value(display_settings.get('base_url'))
        display_settings['auth_mode'] = self._settings_reference_value(display_settings.get('auth_mode'))
        display_settings['auth_mode_label'] = self._auth_mode_label(provider_id, display_settings.get('auth_mode'))
        credentials = dict(display_settings.get('credentials') or {})
        settings_credentials = self._settings_credentials_for_provider(provider_id)
        for key in ['email', 'username', 'password']:
            if not credentials.get(key) and settings_credentials.get(key):
                credentials[key] = settings_credentials[key]
        for key in ['api_token', 'password', 'token']:
            if credentials.get(key) or settings_credentials.get(key):
                credentials[key] = '********'
        if credentials:
            display_settings['credentials'] = credentials
        display_settings['connection_status_label'] = self._connection_status_label(provider_id, display_settings, credentials)
        return display_settings

    def _auth_mode_label(self, provider_id: str, auth_mode: str) -> str:
        auth_mode = str(auth_mode or '').strip()
        labels = {
            'jira': {
                'server_pat': 'API token / PAT',
                'cloud_basic': 'Email + API token',
            },
            'hsdes': {
                'kerberos': 'Windows Integrated Auth',
                'windows_integrated': 'Windows Integrated Auth',
                'basic': 'Username + password',
                'token': 'Bearer token',
            },
            'github': {
                'token': 'Personal access token',
            },
        }
        return labels.get(str(provider_id or '').strip().lower(), {}).get(auth_mode, auth_mode or 'Not selected')

    def _connection_status_label(self, provider_id: str, connection_settings: dict, credentials: dict) -> str:
        provider_id = str(provider_id or '').strip().lower()
        auth_mode = str(connection_settings.get('auth_mode', '') or '').strip()
        if not str(connection_settings.get('base_url', '') or '').strip():
            return 'Base URL required'
        if not auth_mode:
            return 'Authentication method required'
        if provider_id == 'jira':
            if auth_mode == 'cloud_basic':
                return 'Ready to test' if credentials.get('email') and credentials.get('api_token') else 'Email and API token required'
            return 'Ready to test' if credentials.get('api_token') else 'API token required'
        if provider_id == 'hsdes':
            if auth_mode in {'kerberos', 'windows_integrated'}:
                return 'Ready to test with Windows Integrated Auth'
            if auth_mode == 'basic':
                return 'Ready to test' if credentials.get('username') and credentials.get('password') else 'Username and password required'
            if auth_mode == 'token':
                return 'Ready to test' if credentials.get('token') else 'Bearer token required'
            return 'Authentication method required'
        if provider_id == 'github':
            return 'Ready to test' if credentials.get('token') else 'Token required'
        return 'Configuration required'

    def _settings_reference_value(self, value):
        raw_value = str(value or '')
        if not raw_value.startswith('settings:'):
            return value
        setting_name = raw_value.removeprefix('settings:').strip()
        if not setting_name.replace('_', '').isalnum():
            return value
        setting_value = getattr(settings, setting_name, None)
        return setting_value if setting_value not in {None, ''} else value

    def _settings_credentials_for_provider(self, provider_id: str) -> dict:
        provider_id = str(provider_id or '').strip().lower()
        if provider_id == 'jira':
            return {
                'email': getattr(settings, 'METRICS_JIRA_EMAIL', '') or '',
                'api_token': getattr(settings, 'METRICS_JIRA_API_TOKEN', '') or '',
            }
        if provider_id == 'hsdes':
            return {
                'username': getattr(settings, 'METRICS_HSDES_USERNAME', '') or '',
                'password': getattr(settings, 'METRICS_HSDES_PASSWORD', '') or '',
                'token': getattr(settings, 'METRICS_HSDES_TOKEN', '') or '',
            }
        if provider_id == 'github':
            return {
                'token': getattr(settings, 'METRICS_GITHUB_TOKEN', '') or '',
            }
        return {}

    def _provider_profile_json_fields(self, profile) -> list[dict]:
        return [
            {
                'name': field_name,
                'label': field_name.replace('_', ' ').title(),
                'value': json.dumps(getattr(profile, field_name), indent=2, sort_keys=True),
            }
            for field_name in PROFILE_JSON_FIELDS
            if field_name != 'connection_settings'
        ]

    def _profile_choice_from_config(self, profile):
        return BugTrendProviderProfileChoice(
            profile.profile_id,
            profile.provider_id,
            profile.display_name,
            dict(getattr(profile, 'connection_settings', {}) or {}),
            dict(profile.scope_labels or {}),
            dict(profile.source_population or {}),
            profile.mapping_version_hash,
        )

    def _provider_source_summary(self, profile) -> str:
        connection_settings = dict(getattr(profile, 'connection_settings', {}) or {})
        connection_summary = (
            connection_settings.get('base_url')
            or connection_settings.get('credential_ref')
            or connection_settings.get('auth_mode')
        )
        if connection_summary:
            return connection_summary
        source_population = dict(profile.source_population or {})
        return (
            source_population.get('source_query_name')
            or source_population.get('source_query_ref')
            or source_population.get('native_query_text')
            or source_population.get('tenant_or_site')
            or '-'
        )

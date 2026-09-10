from dataclasses import dataclass, field
import json
from typing import Any, Dict

from bug_metrics.models import ProviderProfileConfig


PROFILE_JSON_FIELDS = (
    'connection_settings',
    'source_population',
    'scope_labels',
    'field_bindings',
    'value_mappings',
    'chart_bindings',
    'sync_policy',
    'readiness_policy',
)


@dataclass(slots=True)
class SavedProviderProfileConfig:
    id: int | None
    profile_id: str
    provider_id: str
    display_name: str
    lifecycle_state: str
    connection_settings: Dict[str, Any] = field(default_factory=dict)
    source_population: Dict[str, Any] = field(default_factory=dict)
    scope_labels: Dict[str, Any] = field(default_factory=dict)
    field_bindings: Dict[str, Any] = field(default_factory=dict)
    value_mappings: Dict[str, Any] = field(default_factory=dict)
    chart_bindings: Dict[str, Any] = field(default_factory=dict)
    sync_policy: Dict[str, Any] = field(default_factory=dict)
    readiness_policy: Dict[str, Any] = field(default_factory=dict)
    mapping_version: int = 1
    mapping_version_hash: str = ''
    source_version_hash: str = ''
    source_kind: str = 'managed'


def default_connection_settings_for_provider(provider_id: str) -> Dict[str, Any]:
    provider_id = str(provider_id or '').strip().lower()
    if provider_id == 'jira':
        return {
            'base_url': 'settings:METRICS_JIRA_SERVER_URL',
            'auth_mode': 'settings:METRICS_JIRA_AUTH_MODE',
            'credential_ref': 'settings:METRICS_JIRA_EMAIL/METRICS_JIRA_API_TOKEN',
            'credential_storage': 'settings_or_profile',
            'onboarding_status': 'deployment_configured',
        }
    if provider_id == 'hsdes':
        return {
            'base_url': 'settings:METRICS_HSDES_API_BASE_URL',
            'auth_mode': 'settings:METRICS_HSDES_AUTH_MODE',
            'credential_ref': 'settings:METRICS_HSDES_* or Windows Integrated Auth',
            'credential_storage': 'settings_or_profile',
            'onboarding_status': 'configuration_required',
        }
    if provider_id == 'github':
        return {
            'base_url': 'settings:METRICS_GITHUB_BASE_URL',
            'auth_mode': 'token',
            'credential_ref': 'settings:METRICS_GITHUB_TOKEN',
            'credential_storage': 'settings_or_profile',
            'onboarding_status': 'template_only',
        }
    return {
        'base_url': '',
        'auth_mode': '',
        'credential_ref': '',
        'credential_storage': 'settings_or_profile',
        'onboarding_status': 'configuration_required',
    }


def blank_connection_settings_for_provider(provider_id: str) -> Dict[str, Any]:
    provider_id = str(provider_id or '').strip().lower()
    return {
        'base_url': '',
        'auth_mode': '',
        'credential_ref': '',
        'credential_storage': 'settings_or_profile',
        'onboarding_status': 'template_only' if provider_id == 'github' else 'configuration_required',
    }


def provider_profile_config_from_dict(payload: Dict[str, Any]) -> SavedProviderProfileConfig:
    provider_id = str(payload.get('provider_id', '') or '').strip()
    connection_settings = {
        **default_connection_settings_for_provider(provider_id),
        **_dict_value(payload.get('connection_settings')),
    }
    return SavedProviderProfileConfig(
        id=int(payload['id']) if str(payload.get('id', '') or '').isdecimal() else None,
        profile_id=str(payload.get('profile_id', '') or '').strip(),
        provider_id=provider_id,
        display_name=str(payload.get('display_name', '') or '').strip(),
        lifecycle_state=str(payload.get('lifecycle_state', '') or ProviderProfileConfig.LIFECYCLE_DRAFT).strip(),
        connection_settings=connection_settings,
        source_population=_dict_value(payload.get('source_population')),
        scope_labels=_dict_value(payload.get('scope_labels')),
        field_bindings=_dict_value(payload.get('field_bindings')),
        value_mappings=_dict_value(payload.get('value_mappings')),
        chart_bindings=_dict_value(payload.get('chart_bindings')),
        sync_policy=_dict_value(payload.get('sync_policy')),
        readiness_policy=_dict_value(payload.get('readiness_policy')),
        mapping_version=int(payload.get('mapping_version') or 1),
        mapping_version_hash=str(payload.get('mapping_version_hash', '') or ''),
        source_version_hash=str(payload.get('source_version_hash', '') or ''),
        source_kind=str(payload.get('source_kind', 'managed') or 'managed'),
    )


def provider_profile_config_from_post(post_data) -> SavedProviderProfileConfig:
    payload = {
        'id': post_data.get('id', ''),
        'profile_id': post_data.get('profile_id', ''),
        'provider_id': post_data.get('provider_id', ''),
        'display_name': post_data.get('display_name', ''),
        'lifecycle_state': post_data.get('lifecycle_state', ProviderProfileConfig.LIFECYCLE_DRAFT),
        'mapping_version': post_data.get('mapping_version', '1'),
    }
    for field_name in PROFILE_JSON_FIELDS:
        payload[field_name] = post_data.get(field_name, '{}')
    source_population = _dict_value(payload.get('source_population'))
    if str(payload['provider_id'] or '').strip().lower() == 'hsdes':
        for post_name, source_name in {
            'hsdes_saved_query_id': 'source_query_ref',
            'hsdes_tenant': 'tenant_or_site',
            'hsdes_subject': 'subject_or_issue_type',
        }.items():
            if post_name in post_data:
                source_population[source_name] = str(post_data.get(post_name, '') or '').strip()
        source_population['provider_id'] = 'hsdes'
        if not source_population.get('ownership_type'):
            source_population['ownership_type'] = 'provider_owned_saved_query'
        payload['source_population'] = source_population
    connection_settings = _dict_value(payload.get('connection_settings'))
    connection_settings.pop('onboarding_status', None)
    for post_name, setting_name in {
        'connection_base_url': 'base_url',
        'connection_auth_mode': 'auth_mode',
        'credential_ref': 'credential_ref',
    }.items():
        if post_name in post_data:
            connection_settings[setting_name] = str(post_data.get(post_name, '') or '').strip()
    credentials = dict(connection_settings.get('credentials') or {})
    active_credential_keys = _active_auth_credential_keys(payload['provider_id'], connection_settings.get('auth_mode'))
    if post_data.get('clear_connection_credentials') == 'on':
        credentials = {}
        connection_settings['_clear_credentials'] = True
    else:
        for post_name, credential_name in {
            'connection_username': 'username',
            'connection_email': 'email',
            'connection_api_token': 'api_token',
            'connection_password': 'password',
            'connection_token': 'token',
        }.items():
            raw_value = str(post_data.get(post_name, '') or '').strip()
            if credential_name in {'api_token', 'token'} and _masked_secret_value(raw_value):
                continue
            if post_name in post_data and raw_value and credential_name in active_credential_keys:
                credentials[credential_name] = raw_value
        if credentials:
            connection_settings['credentials'] = credentials
            connection_settings['credential_storage'] = 'profile_local'
    payload['connection_settings'] = connection_settings
    return provider_profile_config_from_dict(payload)


def _dict_value(value) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value in {None, ''}:
        return {}
    if isinstance(value, str):
        return json.loads(value)
    return dict(value)


def _masked_secret_value(value: str) -> bool:
    stripped = str(value or '').strip()
    return bool(stripped) and set(stripped) <= {'*'} and len(stripped) >= 6


def _active_auth_credential_keys(provider_id: str, auth_mode: str) -> set[str]:
    provider_id = str(provider_id or '').strip().lower()
    auth_mode = str(auth_mode or '').strip().lower()
    if provider_id == 'jira':
        if not auth_mode:
            return set()
        if auth_mode == 'cloud_basic':
            return {'email', 'api_token'}
        return {'api_token'}
    if provider_id == 'hsdes':
        if auth_mode == 'basic':
            return {'username', 'password'}
        if auth_mode == 'token':
            return {'token'}
        return set()
    if provider_id == 'github':
        return {'token'}
    return {'username', 'email', 'api_token', 'password', 'token'}

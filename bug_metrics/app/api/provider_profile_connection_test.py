from dataclasses import asdict, dataclass
from typing import Any

from django.conf import settings

from bug_metrics.provider_profile_connection import first_profile_credential_value, profile_connection_value, profile_credential_value
from jira_sync.out.jira_scope_issue_adapter import create_jira_client
from provider_sync.app.api.hsdes import HsdesHttpClient, HsdesProviderError

from .provider_profile_config import ProviderProfileConfigService, SavedProviderProfileConfig


@dataclass(slots=True)
class ProviderProfileConnectionTestResult:
    status: str
    provider_id: str
    profile_id: str
    summary: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProviderProfileConnectionTestService:
    def __init__(self, profile_config_service=None, jira_client_factory=None, hsdes_client_factory=None):
        self._profile_config_service = profile_config_service or ProviderProfileConfigService()
        self._jira_client_factory = jira_client_factory
        self._hsdes_client_factory = hsdes_client_factory

    def test_connection(self, config: SavedProviderProfileConfig) -> ProviderProfileConnectionTestResult:
        config = self._with_saved_credentials(config)
        if config.provider_id == 'jira':
            return self._test_jira_connection(config)
        if config.provider_id == 'hsdes':
            return self._test_hsdes_connection(config)
        return ProviderProfileConnectionTestResult(
            'unsupported',
            config.provider_id,
            config.profile_id,
            f'Provider {config.provider_id} does not have a connection test yet.',
            {'provider_id': config.provider_id},
        )

    def _test_jira_connection(self, config: SavedProviderProfileConfig) -> ProviderProfileConnectionTestResult:
        try:
            server_info = (self._jira_client_factory or create_jira_client)(settings, config.connection_settings).get_server_info()
            return ProviderProfileConnectionTestResult(
                'success',
                config.provider_id,
                config.profile_id,
                'Jira connection succeeded.',
                {
                    'base_url': profile_connection_value(config.connection_settings, 'base_url', settings.METRICS_JIRA_SERVER_URL),
                    'server_title': self._server_info_value(server_info, 'serverTitle'),
                    'version': self._server_info_value(server_info, 'version'),
                },
            )
        except Exception as error:
            return self._failed_result(config, 'Jira connection failed.', error)

    def _test_hsdes_connection(self, config: SavedProviderProfileConfig) -> ProviderProfileConnectionTestResult:
        source_population = dict(config.source_population or {})
        query_id = self._source_value(source_population, ['source_query_ref', 'saved_query_id', 'query_id'])
        tenant = self._source_value(source_population, ['tenant_or_site', 'tenant'])
        subject = self._source_value(source_population, ['subject_or_issue_type', 'subject'])
        if not query_id or not tenant or not subject:
            missing_fields = [
                label
                for label, value in {
                    'HSD-ES saved query id': query_id,
                    'Tenant': tenant,
                    'Subject': subject,
                }.items()
                if not value
            ]
            return ProviderProfileConnectionTestResult(
                'configuration_required',
                config.provider_id,
                config.profile_id,
                'HSD-ES connection test needs a saved query id, tenant and subject in the HSD-ES Connection Probe fields.',
                {'missing_fields': ', '.join(missing_fields)},
            )
        try:
            client = (self._hsdes_client_factory or HsdesHttpClient)(
                base_url=profile_connection_value(config.connection_settings, 'base_url', settings.METRICS_HSDES_API_BASE_URL),
                auth_mode=profile_connection_value(config.connection_settings, 'auth_mode', settings.METRICS_HSDES_AUTH_MODE),
                username=profile_credential_value(config.connection_settings, 'username', settings.METRICS_HSDES_USERNAME),
                password=profile_credential_value(config.connection_settings, 'password', settings.METRICS_HSDES_PASSWORD),
                token=first_profile_credential_value(config.connection_settings, ['token', 'api_token'], settings.METRICS_HSDES_TOKEN),
                timeout_seconds=int(profile_connection_value(config.connection_settings, 'timeout_seconds', settings.METRICS_HSDES_TIMEOUT_SECONDS)),
                transport=profile_connection_value(config.connection_settings, 'transport', settings.METRICS_HSDES_HTTP_TRANSPORT),
            )
            payload = client.execute_saved_query(query_id, tenant, subject, ['id'], 0, 1)
            return ProviderProfileConnectionTestResult(
                'success',
                config.provider_id,
                config.profile_id,
                'HSD-ES saved-query probe succeeded.',
                {
                    'query_id': query_id,
                    'tenant': tenant,
                    'subject': subject,
                    'result_count': self._result_count(payload),
                },
            )
        except HsdesProviderError as error:
            return ProviderProfileConnectionTestResult(
                'failed',
                config.provider_id,
                config.profile_id,
                'HSD-ES connection failed.',
                {'category': error.category, 'error': self._redacted_message(str(error), config.connection_settings)},
            )
        except Exception as error:
            return self._failed_result(config, 'HSD-ES connection failed.', error)

    def _with_saved_credentials(self, config: SavedProviderProfileConfig) -> SavedProviderProfileConfig:
        try:
            saved = self._profile_config_service.get_provider_profile_config(config.profile_id)
        except (KeyError, ValueError):
            return config
        merged_connection_settings = dict(saved.connection_settings or {})
        incoming_connection_settings = dict(config.connection_settings or {})
        merged_credentials = {
            **dict(merged_connection_settings.get('credentials') or {}),
            **dict(incoming_connection_settings.get('credentials') or {}),
        }
        merged_connection_settings.update(incoming_connection_settings)
        if merged_credentials:
            merged_connection_settings['credentials'] = merged_credentials
        config.connection_settings = merged_connection_settings
        return config

    def _failed_result(self, config: SavedProviderProfileConfig, summary: str, error: Exception) -> ProviderProfileConnectionTestResult:
        return ProviderProfileConnectionTestResult(
            'failed',
            config.provider_id,
            config.profile_id,
            summary,
            {'error': self._redacted_message(str(error), config.connection_settings)},
        )

    def _redacted_message(self, message: str, connection_settings: dict[str, Any]) -> str:
        redacted = str(message)
        for value in dict(connection_settings.get('credentials') or {}).values():
            if value:
                redacted = redacted.replace(str(value), '[redacted]')
        return redacted

    def _server_info_value(self, server_info, key: str) -> str:
        return str(server_info.get(key, '') if isinstance(server_info, dict) else '')

    def _source_value(self, source_population: dict[str, Any], keys: list[str]) -> str:
        for key in keys:
            value = str(source_population.get(key, '') or '').strip()
            if value:
                return value
        return ''

    def _result_count(self, payload) -> int:
        if not isinstance(payload, dict):
            return 0
        if 'total' in payload:
            return int(payload.get('total') or 0)
        for key in ['data', 'articles', 'results']:
            if isinstance(payload.get(key), list):
                return len(payload[key])
        return 0

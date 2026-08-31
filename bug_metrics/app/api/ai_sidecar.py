from urllib.parse import urljoin
from urllib.request import Request, urlopen
import json

from django.conf import settings


AI_SIDECAR_CONTRACT_VERSION = '0.1'


class AiSidecarProbeService:
    def __init__(self, json_getter=None):
        self._json_getter = json_getter or self._default_json_getter

    def get_status(self) -> dict:
        config = self._config()
        if not config['enabled']:
            return self._status(config, 'disabled', 'AI sidecar is disabled by configuration.')
        try:
            handshake = self._json_getter(self._url(config['base_url'], config['handshake_path']), config['timeout_seconds'])
            mismatch = self._handshake_mismatch(config, handshake)
            if mismatch:
                return self._status(config, 'unavailable', mismatch)
            runtime_info = self._json_getter(self._url(config['base_url'], '/api/runtime/info'), config['timeout_seconds'])
            runtime_mismatch = self._runtime_mismatch(config, runtime_info)
            if runtime_mismatch:
                return self._status(config, 'degraded', runtime_mismatch, runtime_info)
            return self._status(config, 'ready', '', runtime_info)
        except Exception as error:
            return self._status(config, 'unavailable', self._safe_error(error))

    def _config(self) -> dict:
        return {
            'enabled': bool(getattr(settings, 'METRICS_AI_SIDECAR_ENABLED', False)),
            'base_url': str(getattr(settings, 'METRICS_AI_BASE_URL', 'http://127.0.0.1:48300')).rstrip('/'),
            'service_id': str(getattr(settings, 'METRICS_AI_BASE_SERVICE_ID', 'dashboard-query-agent-app-service')),
            'instance_token': str(getattr(settings, 'METRICS_AI_BASE_INSTANCE_TOKEN', '') or ''),
            'profile_id': str(getattr(settings, 'METRICS_AI_BASE_PROFILE_ID', 'dashboard_query_agent')),
            'handshake_path': str(getattr(settings, 'METRICS_AI_BASE_HANDSHAKE_PATH', '/health/handshake')),
            'timeout_seconds': float(getattr(settings, 'METRICS_AI_BASE_TIMEOUT_SECONDS', 3.0)),
        }

    def _status(self, config: dict, status: str, reason: str, runtime_info: dict | None = None) -> dict:
        runtime_app = (runtime_info or {}).get('app', {}) if isinstance(runtime_info, dict) else {}
        return {
            'contract_version': AI_SIDECAR_CONTRACT_VERSION,
            'enabled': config['enabled'],
            'status': status,
            'reason': reason,
            'base_url': config['base_url'],
            'service_id': config['service_id'],
            'profile_id': runtime_app.get('profileId') or config['profile_id'],
            'expected_profile_id': config['profile_id'],
            'handshake_path': config['handshake_path'],
            'capabilities': self._safe_capabilities(runtime_app.get('capabilities', {})),
        }

    def _handshake_mismatch(self, config: dict, handshake: dict) -> str:
        if handshake.get('serviceId') != config['service_id']:
            return 'AI Base service identity mismatch.'
        expected_token = config['instance_token']
        if expected_token and handshake.get('instanceToken') != expected_token:
            return 'AI Base instance token mismatch.'
        return ''

    def _runtime_mismatch(self, config: dict, runtime_info: dict) -> str:
        app = runtime_info.get('app', {}) if isinstance(runtime_info, dict) else {}
        if app.get('profileId') != config['profile_id']:
            return 'AI Base profile mismatch.'
        capabilities = self._dashboard_capabilities(app.get('capabilities', {}))
        if not capabilities.get('dashboardQuery'):
            return 'AI Base dashboardQuery capability is not enabled.'
        if not capabilities.get('metricsConnector'):
            return 'AI Base metricsConnector capability is not enabled.'
        return ''

    def _safe_capabilities(self, capabilities: dict) -> dict:
        capabilities = self._dashboard_capabilities(capabilities)
        allowed = {'dashboardQuery', 'grafanaOperations', 'metricsConnector'}
        return {key: bool(value) for key, value in capabilities.items() if key in allowed}

    def _dashboard_capabilities(self, capabilities: dict) -> dict:
        if not isinstance(capabilities, dict):
            return {}
        feature_capabilities = capabilities.get('featureCapabilities', {})
        if isinstance(feature_capabilities, dict):
            return {**capabilities, **feature_capabilities}
        return capabilities

    def _url(self, base_url: str, path: str) -> str:
        return urljoin(f'{base_url}/', path.lstrip('/'))

    def _safe_error(self, error: Exception) -> str:
        return f'AI Base sidecar probe failed: {type(error).__name__}.'

    def _default_json_getter(self, url: str, timeout_seconds: float) -> dict:
        request = Request(url, headers={'Accept': 'application/json'})
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = response.read().decode('utf-8')
        return json.loads(payload)

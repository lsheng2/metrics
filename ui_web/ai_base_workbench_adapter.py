from urllib.parse import urlencode, urlparse, urlunparse

from django.conf import settings

from .workbench_state import WorkbenchPageQueryState


class AiBaseWorkbenchAdapter:
    source_app_id = 'metrics-dashboard'
    default_agent_key = 'metrics.dashboardQuery'
    default_binding_key = 'metrics.workbench.overview'
    default_redaction_policy = 'metrics-dashboard-default'

    def __init__(self, launcher_command: str):
        self._launcher_command = launcher_command

    def frontend_base_url(self, sidecar_status: dict) -> str:
        configured_frontend = str(getattr(settings, 'METRICS_AI_BASE_FRONTEND_URL', '') or '').rstrip('/')
        if configured_frontend:
            return configured_frontend
        backend_base_url = str(sidecar_status.get('base_url') or settings.METRICS_AI_BASE_URL).rstrip('/')
        parsed_url = urlparse(backend_base_url)
        if not parsed_url.scheme or not parsed_url.hostname:
            return backend_base_url
        frontend_port = (parsed_url.port + 10) if parsed_url.port else None
        netloc = parsed_url.hostname
        if frontend_port:
            netloc = f'{netloc}:{frontend_port}'
        return urlunparse((parsed_url.scheme, netloc, '', '', '', ''))

    def workspace_key_for_state(self, state: WorkbenchPageQueryState) -> str:
        if not state.provider_id or not state.profile_id:
            return ''
        return f'metrics.{state.provider_id}.{state.profile_id}'

    def context(self, state: WorkbenchPageQueryState, sidecar_status: dict) -> dict:
        return {
            'profile_id': state.profile_id,
            'provider_id': state.provider_id,
            'range_mode': state.range_mode,
            'begin': state.begin,
            'end': state.end,
            'chart_id': state.chart_id,
            'chart_version': state.chart_version,
            'selection': {
                'run': state.calculation_run_id,
                'snapshot': state.fact_snapshot_id,
                'bucket': state.selected_bucket_id,
                'series': state.selected_series_name,
            },
            'ai_base': self.ai_base_payload(state, sidecar_status),
        }

    def ai_base_payload(self, state: WorkbenchPageQueryState, sidecar_status: dict) -> dict:
        return {
            'enabled': bool(sidecar_status.get('enabled', False)),
            'status': sidecar_status.get('status', 'disabled'),
            'reason': sidecar_status.get('reason', ''),
            'base_url': sidecar_status.get('base_url', ''),
            'frontend_url': self.frontend_base_url(sidecar_status),
            'profile_id': sidecar_status.get('profile_id', ''),
            'service_id': sidecar_status.get('service_id', ''),
            'capabilities': sidecar_status.get('capabilities', {}),
            'chat_url': self.chat_url(state, sidecar_status),
            'workspace_key': self.workspace_key_for_state(state),
            'agent_id': sidecar_status.get('profile_id') or 'dashboard_query_agent',
            'binding_request': self.binding_request(state, sidecar_status),
            'launcher_command': self._launcher_command,
        }

    def chat_url(self, state: WorkbenchPageQueryState, sidecar_status: dict) -> str:
        mode = self._embed_mode()
        base_url = self.frontend_base_url(sidecar_status)
        if mode == 'app-chat':
            return f'{base_url}/?embed=app-chat#/chat?{urlencode(self._app_chat_query(state))}'
        return f'{base_url}/?embed=workbench#/chat?{urlencode(self._legacy_workbench_query(state, sidecar_status))}'

    def binding_request(self, state: WorkbenchPageQueryState, sidecar_status: dict) -> dict:
        workspace_key = self.workspace_key_for_state(state)
        session_key = self._session_key(state)
        return {
            'sourceAppId': self.source_app_id,
            'auth': {
                'authMode': 'local_sidecar_signed_token',
                'credentialRef': 'metrics-dashboard-local',
            },
            'bindingKey': self.default_binding_key,
            'agentKey': self.default_agent_key,
            'workspaceKey': workspace_key,
            'sessionKey': session_key,
            'sessionTitle': f'{state.profile_id or "Metrics"} Workbench',
            'sessionMode': 'reuse_or_create',
            'context': {
                'contextKind': 'metrics.dashboard.workbench',
                'visibility': 'model_context',
                'version': 'dashboard-workbench-v1',
                'redactionPolicy': self.default_redaction_policy,
                'data': {
                    'profileId': state.profile_id,
                    'providerId': state.provider_id,
                    'rangeMode': state.range_mode,
                    'begin': state.begin,
                    'end': state.end,
                    'chartId': state.chart_id,
                    'chartVersion': state.chart_version,
                    'selection': {
                        'run': state.calculation_run_id,
                        'snapshot': state.fact_snapshot_id,
                        'bucket': state.selected_bucket_id,
                        'series': state.selected_series_name,
                    },
                },
            },
            'correlationId': f'metrics-workbench:{state.profile_id}:{state.chart_id}',
        }

    def next_action(self, status: str) -> str:
        if status in {'ready', 'connected', 'available'}:
            return 'Use the AI pane with the bounded workbench context.'
        if status == 'disabled':
            return f'Restart the unified stack with: {self._launcher_command}'
        return f'Start or restart AI Base with: {self._launcher_command}'

    def _legacy_workbench_query(self, state: WorkbenchPageQueryState, sidecar_status: dict) -> dict:
        return {
            'source': 'metrics-workbench',
            'profile_id': state.profile_id,
            'provider_id': state.provider_id,
            'workspace_key': self.workspace_key_for_state(state),
            'agent_id': sidecar_status.get('profile_id') or 'dashboard_query_agent',
            'range_mode': state.range_mode,
            'begin': state.begin,
            'end': state.end,
            'chart_id': state.chart_id,
            'bucket': state.selected_bucket_id,
            'series': state.selected_series_name,
        }

    def _app_chat_query(self, state: WorkbenchPageQueryState) -> dict:
        request = self.binding_request(state, {})
        return {
            'sourceAppId': request['sourceAppId'],
            'bindingKey': request['bindingKey'],
            'workspaceKey': request['workspaceKey'],
            'agentKey': request['agentKey'],
            'sessionKey': request['sessionKey'],
            'sessionTitle': request['sessionTitle'],
            'contextKind': request['context']['contextKind'],
            'contextVersion': request['context']['version'],
            'redactionPolicy': request['context']['redactionPolicy'],
            'profileId': state.profile_id,
            'providerId': state.provider_id,
            'correlationId': request['correlationId'],
            'credentialRef': request['auth']['credentialRef'],
        }

    @staticmethod
    def _session_key(state: WorkbenchPageQueryState) -> str:
        profile_id = state.profile_id or 'default'
        return f'metrics.workbench.{profile_id}.overview'

    @staticmethod
    def _embed_mode() -> str:
        mode = str(getattr(settings, 'METRICS_AI_BASE_EMBED_MODE', 'workbench') or 'workbench').strip().lower()
        return 'app-chat' if mode == 'app-chat' else 'workbench'

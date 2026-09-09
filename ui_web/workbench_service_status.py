from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings

from scripts.service_lifecycle_engine import (
    FilesystemLifecycleStateStore,
    HealthProbeRequirement,
    LifecycleState,
    LifecycleStateStoreError,
    ServiceHealthStatus,
    ServiceLaunchMetadata,
    ServiceLiveSnapshot,
    ServiceOperatorLink,
    build_service_health_snapshot,
    resolve_lifecycle_service_launch_metadata,
)

from .ai_base_workbench_adapter import AiBaseWorkbenchAdapter
from .workbench_registry import WorkbenchServiceStatus


@dataclass(slots=True)
class WorkbenchServiceStatusBuilder:
    ai_adapter: AiBaseWorkbenchAdapter
    dashboard_home_url: str

    def build(self, sidecar_status: dict) -> list[WorkbenchServiceStatus]:
        ai_status = sidecar_status.get('status') or 'disabled'
        grafana_base_url = str(settings.METRICS_AI_GRAFANA_BASE_URL or '').rstrip('/')
        ai_frontend_url = self.ai_adapter.frontend_base_url(sidecar_status)
        checked_at = self._status_checked_at()
        lifecycle_services = self._dashboard_lifecycle_services()
        return [
            self._status_from_snapshot(
                'dashboard',
                'Dashboard UI',
                self._live_snapshot(
                    service_id='dashboard',
                    status=self._health_status_for_observed_dashboard_service(lifecycle_services, 'django'),
                    display_status=self._display_status_for_observed_dashboard_service(lifecycle_services, 'django'),
                    checked_at=checked_at,
                    target_url=self.dashboard_home_url,
                    lifecycle_state=self._lifecycle_state_for(lifecycle_services, 'django') or LifecycleState.READY.value,
                    launch_metadata=self._launch_metadata_for(lifecycle_services, 'django'),
                    provenance=self._provenance_for(lifecycle_services, 'django'),
                ),
                self.dashboard_home_url,
                next_action='If this shell stops responding, restart python manage.py runserver on the Dashboard port.',
            ),
            self._status_from_snapshot(
                'grafana',
                'Grafana',
                self._live_snapshot(
                    service_id='grafana',
                    status=self._health_status_for_lifecycle_service(lifecycle_services, 'grafana', bool(grafana_base_url)),
                    display_status=self._display_status_for_lifecycle_service(lifecycle_services, 'grafana', bool(grafana_base_url)),
                    checked_at=checked_at,
                    target_url=self._base_url_for(lifecycle_services, 'grafana', grafana_base_url),
                    lifecycle_state=self._lifecycle_state_for(lifecycle_services, 'grafana'),
                    reason='' if grafana_base_url else 'METRICS_AI_GRAFANA_BASE_URL is empty.',
                    launch_metadata=self._launch_metadata_for(lifecycle_services, 'grafana'),
                    provenance=self._provenance_for(lifecycle_services, 'grafana'),
                ),
                self._base_url_for(lifecycle_services, 'grafana', grafana_base_url),
                '' if grafana_base_url else 'METRICS_AI_GRAFANA_BASE_URL is empty.',
                self._grafana_next_action(grafana_base_url),
            ),
            self._status_from_snapshot(
                'ai-base',
                'AI Base',
                self._live_snapshot(
                    service_id='ai-base',
                    status=self._health_status_for_ai_base(ai_status),
                    display_status=self._display_status_for_ai_base(ai_status),
                    checked_at=checked_at,
                    target_url=ai_frontend_url,
                    reason=str(sidecar_status.get('reason') or ''),
                    special_state='' if ai_status in {'ready', 'connected', 'available'} else ai_status,
                    launch_metadata=ServiceLaunchMetadata(source='ai-sidecar-status'),
                ),
                ai_frontend_url,
                str(sidecar_status.get('reason') or ''),
                self.ai_adapter.next_action(ai_status),
            ),
        ]

    def _status_checked_at(self) -> str:
        return datetime.now().strftime('%I:%M:%S %p').lstrip('0')

    def _live_snapshot(
        self,
        *,
        service_id: str,
        status: ServiceHealthStatus,
        display_status: str,
        checked_at: str,
        target_url: str = '',
        lifecycle_state: str = '',
        reason: str = '',
        special_state: str = '',
        launch_metadata: ServiceLaunchMetadata | None = None,
        provenance: dict | None = None,
    ) -> ServiceLiveSnapshot:
        resolved_special_state = special_state
        if not resolved_special_state and display_status not in {'connected', 'available', 'ready'}:
            resolved_special_state = display_status
        return ServiceLiveSnapshot(
            service_name=service_id,
            configured=status != ServiceHealthStatus.UNREACHABLE or bool(target_url),
            lifecycle_state=lifecycle_state or ('ready' if status == ServiceHealthStatus.READY else 'unknown'),
            health=build_service_health_snapshot(
                service_name=service_id,
                checked_at=checked_at,
                explicit_status=status,
                probe_name='workbench',
                requirement=HealthProbeRequirement.REQUIRED_FOR_LIVE_STATUS,
                reason=reason,
                special_state=resolved_special_state,
            ),
            launch_metadata=launch_metadata or ServiceLaunchMetadata(source='workbench'),
            provenance=provenance,
            base_url=target_url,
            links=(ServiceOperatorLink(rel='open', href=target_url),) if target_url else (),
        )

    def _status_from_snapshot(
        self,
        service_id: str,
        label: str,
        snapshot: ServiceLiveSnapshot,
        target_url: str,
        reason: str = '',
        next_action: str = '',
    ) -> WorkbenchServiceStatus:
        payload = snapshot.as_dict()
        health = payload.get('health', {})
        status = str(health.get('status') or 'unknown') if isinstance(health, dict) else 'unknown'
        display_status = self._display_status_from_snapshot(status, payload)
        resolved_reason = reason
        if isinstance(health, dict) and not resolved_reason:
            resolved_reason = str(health.get('reason') or '')
        return WorkbenchServiceStatus(
            service_id=service_id,
            label=label,
            status=status,
            target_url=target_url,
            reason=resolved_reason,
            next_action=next_action,
            checked_at=str(health.get('checked_at') or '') if isinstance(health, dict) else '',
            display_status=display_status,
            detail=self._status_detail(payload),
            tone=self._status_tone(display_status),
            live_snapshot=payload,
        )

    def _display_status_from_snapshot(self, status: str, payload: dict) -> str:
        health = payload.get('health', {})
        if isinstance(health, dict):
            special_state = str(health.get('special_state') or '')
            if special_state and special_state != 'ready':
                return special_state.replace('_', ' ')
        if status == ServiceHealthStatus.READY.value:
            return 'connected'
        if status == ServiceHealthStatus.AUTH_REQUIRED.value:
            return 'auth required'
        if status == ServiceHealthStatus.UNREACHABLE.value:
            return 'unavailable'
        if status == ServiceHealthStatus.STOPPED.value:
            return 'disabled'
        return status.replace('_', ' ')

    def _status_detail(self, payload: dict) -> str:
        health = payload.get('health', {})
        if not isinstance(health, dict):
            return ''
        reason = str(health.get('reason') or '')
        if reason and len(reason) <= 18 and reason not in {'configured'}:
            return reason.replace('_', ' ')
        return ''

    def _status_tone(self, display_status: str) -> str:
        if display_status in {'connected', 'available', 'ready'}:
            return 'success'
        if display_status in {'configured', 'starting'}:
            return 'info'
        if 'auth' in display_status or display_status in {'degraded'}:
            return 'warning'
        if display_status in {'disabled', 'unavailable', 'unreachable', 'stopped'}:
            return 'neutral'
        return 'warning'

    def _health_status_for_ai_base(self, ai_status: str) -> ServiceHealthStatus:
        if ai_status in {'ready', 'connected', 'available'}:
            return ServiceHealthStatus.READY
        if ai_status in {'disabled', 'stopped'}:
            return ServiceHealthStatus.STOPPED
        if ai_status in {'unavailable', 'disconnected'}:
            return ServiceHealthStatus.UNREACHABLE
        return ServiceHealthStatus.DEGRADED

    def _display_status_for_ai_base(self, ai_status: str) -> str:
        if ai_status in {'ready', 'available'}:
            return 'connected'
        return ai_status.replace('_', ' ')

    def _health_status_for_observed_dashboard_service(
        self,
        services: dict[str, dict[str, object]],
        service_name: str,
    ) -> ServiceHealthStatus:
        lifecycle_state = self._lifecycle_state_for(services, service_name)
        if not lifecycle_state:
            return ServiceHealthStatus.READY
        return self._health_status_for_lifecycle_state(lifecycle_state)

    def _display_status_for_observed_dashboard_service(
        self,
        services: dict[str, dict[str, object]],
        service_name: str,
    ) -> str:
        lifecycle_state = self._lifecycle_state_for(services, service_name)
        if not lifecycle_state:
            return 'connected'
        return self._display_status_for_lifecycle_state(lifecycle_state)

    def _dashboard_lifecycle_services(self) -> dict[str, dict[str, object]]:
        state_path = self._dashboard_lifecycle_state_path()
        store = FilesystemLifecycleStateStore(state_path.parent)
        if not store.exists(state_path):
            return {}
        try:
            payload = store.read_json(state_path)
        except LifecycleStateStoreError:
            return {}
        services = payload.get('services', {})
        if not isinstance(services, dict):
            return {}
        return {
            str(service_name): dict(service)
            for service_name, service in services.items()
            if isinstance(service, dict)
        }

    def _dashboard_lifecycle_state_path(self) -> Path:
        return Path(settings.METRICS_STATE_DIR) / 'e2e' / 'service-lifecycle-engine' / 'metrics-bug-trend-default.json'

    def _launch_metadata_for(self, services: dict[str, dict[str, object]], service_name: str) -> ServiceLaunchMetadata:
        return resolve_lifecycle_service_launch_metadata(
            services,
            service_name,
            source='service-lifecycle-state',
        )

    def _provenance_for(self, services: dict[str, dict[str, object]], service_name: str) -> dict | None:
        service = services.get(service_name, {})
        provenance = service.get('provenance') if isinstance(service, dict) else None
        return dict(provenance) if isinstance(provenance, dict) else None

    def _base_url_for(self, services: dict[str, dict[str, object]], service_name: str, fallback_url: str) -> str:
        service = services.get(service_name, {})
        host = service.get('host') if isinstance(service, dict) else ''
        port = service.get('port') if isinstance(service, dict) else ''
        if host and port:
            return f'http://{host}:{port}'
        return fallback_url

    def _health_status_for_lifecycle_service(
        self,
        services: dict[str, dict[str, object]],
        service_name: str,
        configured: bool,
    ) -> ServiceHealthStatus:
        if not configured:
            return ServiceHealthStatus.UNREACHABLE
        lifecycle_state = self._lifecycle_state_for(services, service_name)
        return self._health_status_for_lifecycle_state(lifecycle_state)

    def _display_status_for_lifecycle_service(
        self,
        services: dict[str, dict[str, object]],
        service_name: str,
        configured: bool,
    ) -> str:
        if not configured:
            return 'unavailable'
        lifecycle_state = self._lifecycle_state_for(services, service_name)
        return self._display_status_for_lifecycle_state(lifecycle_state)

    def _health_status_for_lifecycle_state(self, lifecycle_state: str) -> ServiceHealthStatus:
        if lifecycle_state == LifecycleState.READY.value:
            return ServiceHealthStatus.READY
        if lifecycle_state == LifecycleState.PREPARED.value:
            return ServiceHealthStatus.STARTING
        if lifecycle_state == LifecycleState.STOPPED.value:
            return ServiceHealthStatus.STOPPED
        if lifecycle_state == LifecycleState.ABORTED.value:
            return ServiceHealthStatus.DEGRADED
        return ServiceHealthStatus.UNKNOWN

    def _display_status_for_lifecycle_state(self, lifecycle_state: str) -> str:
        if lifecycle_state == LifecycleState.READY.value:
            return 'connected'
        if lifecycle_state == LifecycleState.PREPARED.value:
            return 'starting'
        if lifecycle_state == LifecycleState.STOPPED.value:
            return 'stopped'
        if lifecycle_state == LifecycleState.ABORTED.value:
            return 'aborted'
        return 'configured'

    def _lifecycle_state_for(self, services: dict[str, dict[str, object]], service_name: str) -> str:
        service = services.get(service_name, {})
        if not isinstance(service, dict):
            return ''
        return str(service.get('lifecycle_state') or '').strip().lower()

    def _grafana_next_action(self, grafana_base_url: str) -> str:
        if not grafana_base_url:
            return 'Set METRICS_AI_GRAFANA_BASE_URL and start the Grafana service before using the panel preview.'
        port = urlparse(grafana_base_url).port
        if port:
            return f'If the panel is blank, check that Grafana is listening on port {port}.'
        return 'If the panel is blank, check the configured Grafana URL and service health.'

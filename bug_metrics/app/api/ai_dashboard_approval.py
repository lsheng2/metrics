import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from django.utils import timezone

from bug_metrics.models import BugTrendAuditEvent

from .ai_dashboard_composition_contracts import DashboardAiPublishApprovalRequest, DashboardAiPublishRequest
from .provider_profiles import ProviderProfileReadinessService


APPROVAL_PENDING = 'pending_approval'
APPROVAL_APPROVED = 'approved'
APPROVAL_REJECTED = 'rejected'
APPROVAL_PUBLISHED = 'published'
APPROVAL_EXPIRED = 'expired'
APPROVAL_TTL = timedelta(hours=24)


@dataclass(frozen=True, slots=True)
class AiGrafanaPublishApprovalState:
    approval_id: str
    status: str
    actor: str
    request_summary: dict

    def to_dict(self) -> dict:
        return {
            'approval_id': self.approval_id,
            'status': self.status,
            'actor': self.actor,
            'request_summary': dict(self.request_summary),
        }


class AiGrafanaPublishApprovalService:
    def __init__(self, readiness_service: ProviderProfileReadinessService | None = None):
        self._readiness_service = readiness_service or ProviderProfileReadinessService()

    def request_approval(self, request: DashboardAiPublishApprovalRequest) -> dict:
        self._validate_artifact_binding(request.artifact_ref, request.artifact_version, request.artifact_hash)
        approval_id = self._approval_id(request)
        summary = self._summary_from_approval_request(request, approval_id)
        BugTrendAuditEvent.objects.create(
            event_type='ai_grafana_publish_approval_requested',
            actor=request.actor,
            chart_id=request.chart_id,
            request_summary=summary,
            result=APPROVAL_PENDING,
        )
        return AiGrafanaPublishApprovalState(approval_id, APPROVAL_PENDING, request.actor, summary).to_dict()

    def decide_approval(self, approval_id: str, decision: str, actor: str) -> dict:
        if decision not in {APPROVAL_APPROVED, APPROVAL_REJECTED}:
            raise ValueError('approval decision must be approved or rejected.')
        current = self.get_approval_state(approval_id)
        if current['status'] == 'missing':
            raise ValueError('approval_id is not known.')
        summary = dict(current['request_summary'])
        summary['approval_id'] = approval_id
        BugTrendAuditEvent.objects.create(
            event_type=f'ai_grafana_publish_approval_{decision}',
            actor=actor,
            chart_id=str(summary.get('chart_id', '')),
            request_summary=summary,
            result=decision,
        )
        return AiGrafanaPublishApprovalState(approval_id, decision, actor, summary).to_dict()

    def validate_publish_authorization(self, request: DashboardAiPublishRequest) -> dict:
        current = self.get_approval_state(request.approval_id)
        if current['status'] != APPROVAL_APPROVED:
            return current
        if self._is_expired(current['request_summary']):
            result = dict(current)
            result['status'] = APPROVAL_EXPIRED
            return result
        mismatches = self._publish_scope_mismatches(current['request_summary'], request)
        if mismatches:
            result = dict(current)
            result['status'] = 'scope_mismatch'
            result['mismatches'] = mismatches
            return result
        return current

    def ensure_local_demo_approval(self, request: DashboardAiPublishRequest) -> dict:
        return self.validate_publish_authorization(request)

    def mark_published(self, request: DashboardAiPublishRequest, dashboard_url: str, correlation_id: str, provider_id: str = '') -> dict:
        summary = self._summary_from_publish_request(request)
        current = self.get_approval_state(request.approval_id)
        summary['provider_id'] = provider_id
        summary['created_at'] = current.get('request_summary', {}).get('created_at', '')
        summary['expires_at'] = current.get('request_summary', {}).get('expires_at', '')
        summary['dashboard_url'] = dashboard_url
        summary['correlation_id'] = correlation_id
        BugTrendAuditEvent.objects.create(
            event_type='ai_grafana_publish_approval_published',
            actor=request.actor,
            chart_id=request.chart_id,
            request_summary=summary,
            result=APPROVAL_PUBLISHED,
        )
        return AiGrafanaPublishApprovalState(request.approval_id, APPROVAL_PUBLISHED, request.actor, summary).to_dict()

    def get_approval_state(self, approval_id: str) -> dict:
        events = [
            event
            for event in BugTrendAuditEvent.objects.filter(
                event_type__in=[
                    'ai_grafana_publish_approval_requested',
                    'ai_grafana_publish_approval_approved',
                    'ai_grafana_publish_approval_rejected',
                    'ai_grafana_publish_approval_published',
                ],
            ).order_by('created_at', 'id')
            if event.request_summary.get('approval_id') == approval_id
        ]
        if not events:
            return {'approval_id': approval_id, 'status': 'missing', 'actor': '', 'request_summary': {}}
        event = events[-1]
        return AiGrafanaPublishApprovalState(approval_id, event.result, event.actor, event.request_summary).to_dict()

    def list_publish_history(self, limit: int = 25) -> dict:
        events = list(
            BugTrendAuditEvent.objects.filter(
                event_type='ai_grafana_publish_approval_published',
            ).order_by('-created_at', '-id')[:limit]
        )
        latest_by_dashboard = {}
        for event in events:
            dashboard_uid = event.request_summary.get('dashboard_uid', '')
            if dashboard_uid and dashboard_uid not in latest_by_dashboard:
                latest_by_dashboard[dashboard_uid] = event.request_summary.get('approval_id', '')
        return {
            'contract_version': '0.2',
            'items': [
                self._history_item(event, latest_by_dashboard)
                for event in events
            ],
        }

    def _history_item(self, event: BugTrendAuditEvent, latest_by_dashboard: dict) -> dict:
        summary = event.request_summary
        dashboard_uid = summary.get('dashboard_uid', '')
        approval_id = summary.get('approval_id', '')
        return {
            'approval_id': approval_id,
            'status': event.result,
            'latest': bool(dashboard_uid and latest_by_dashboard.get(dashboard_uid) == approval_id),
            'actor': event.actor,
            'provider_id': summary.get('provider_id', ''),
            'profile_id': summary.get('profile_id', ''),
            'dashboard_uid': dashboard_uid,
            'dashboard_url': summary.get('dashboard_url', ''),
            'chart_id': summary.get('chart_id', ''),
            'requested_series': list(summary.get('requested_series', [])),
            'range_mode': summary.get('range_mode', ''),
            'range_start': summary.get('range_start', ''),
            'range_end': summary.get('range_end', ''),
            'dry_run_proof_id': summary.get('dry_run_proof_id', ''),
            'artifact_ref': summary.get('artifact_ref', ''),
            'artifact_version': summary.get('artifact_version', 0),
            'artifact_hash': summary.get('artifact_hash', ''),
            'operation': summary.get('operation', ''),
            'workspace_key': summary.get('workspace_key', ''),
            'correlation_id': summary.get('correlation_id', ''),
            'expires_at': summary.get('expires_at', ''),
            'created_at': event.created_at.isoformat(),
        }

    def _approval_id(self, request: DashboardAiPublishApprovalRequest) -> str:
        payload = self._summary_from_approval_request(request, '')
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
        return f'approval_{digest[:24]}'

    def _summary_from_approval_request(self, request: DashboardAiPublishApprovalRequest, approval_id: str) -> dict:
        created_at = timezone.now()
        return {
            'approval_id': approval_id,
            'actor': request.actor,
            'provider_id': self._provider_id(request.provider_id, request.profile_id),
            'workspace_key': self._workspace_key(request.workspace_key, request.provider_id, request.profile_id),
            'profile_id': request.profile_id,
            'dashboard_uid': request.dashboard_uid,
            'chart_id': request.chart_id,
            'requested_series': list(request.requested_series),
            'range_mode': request.range_mode,
            'range_start': request.range_start,
            'range_end': request.range_end,
            'dry_run_proof_id': request.dry_run_proof_id,
            'artifact_ref': request.artifact_ref,
            'artifact_version': request.artifact_version,
            'artifact_hash': request.artifact_hash,
            'operation': request.operation,
            'created_at': created_at.isoformat(),
            'expires_at': (created_at + APPROVAL_TTL).isoformat(),
        }

    def _summary_from_publish_request(self, request: DashboardAiPublishRequest) -> dict:
        return {
            'approval_id': request.approval_id,
            'actor': request.actor,
            'provider_id': self._provider_id(request.provider_id, request.profile_id),
            'workspace_key': self._workspace_key(request.workspace_key, request.provider_id, request.profile_id),
            'profile_id': request.profile_id,
            'dashboard_uid': request.dashboard_uid,
            'chart_id': request.chart_id,
            'requested_series': list(request.requested_series),
            'range_mode': request.range_mode,
            'range_start': request.range_start,
            'range_end': request.range_end,
            'dry_run_proof_id': request.dry_run_proof_id,
            'artifact_ref': request.artifact_ref,
            'artifact_version': request.artifact_version,
            'artifact_hash': request.artifact_hash,
            'operation': request.operation,
        }

    def _publish_scope_mismatches(self, summary: dict, request: DashboardAiPublishRequest) -> list[str]:
        expected = self._summary_from_publish_request(request)
        ignored_keys = {'approval_id', 'created_at', 'expires_at'}
        mismatches = []
        for key, expected_value in expected.items():
            if key in ignored_keys:
                continue
            if summary.get(key) != expected_value:
                mismatches.append(key)
        return mismatches

    def _provider_id(self, requested_provider_id: str, profile_id: str) -> str:
        if requested_provider_id:
            return requested_provider_id
        return self._readiness_service.get_readiness('', profile_id).get('provider_id', '')

    def _workspace_key(self, requested_workspace_key: str, provider_id: str, profile_id: str) -> str:
        if requested_workspace_key:
            return requested_workspace_key
        resolved_provider_id = self._provider_id(provider_id, profile_id)
        return f'metrics.{resolved_provider_id}.{profile_id}' if resolved_provider_id and profile_id else ''

    def _validate_artifact_binding(self, artifact_ref: str, artifact_version: int, artifact_hash: str) -> None:
        if not artifact_ref:
            raise ValueError('artifact_ref is required.')
        if artifact_version < 1:
            raise ValueError('artifact_version must be positive.')
        if not artifact_hash.startswith('sha256:'):
            raise ValueError('artifact_hash must be a sha256 content hash.')

    def _is_expired(self, summary: dict) -> bool:
        expires_at = summary.get('expires_at', '')
        if not expires_at:
            return True
        parsed_expires_at = datetime.fromisoformat(str(expires_at))
        if timezone.is_naive(parsed_expires_at):
            parsed_expires_at = timezone.make_aware(parsed_expires_at, UTC)
        return timezone.now() >= parsed_expires_at

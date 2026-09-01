import hashlib
import json
from dataclasses import dataclass

from bug_metrics.models import BugTrendAuditEvent

from .ai_dashboard_composition_contracts import DashboardAiPublishApprovalRequest, DashboardAiPublishRequest


APPROVAL_PENDING = 'pending_approval'
APPROVAL_APPROVED = 'approved'
APPROVAL_REJECTED = 'rejected'
APPROVAL_PUBLISHED = 'published'


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
    def request_approval(self, request: DashboardAiPublishApprovalRequest) -> dict:
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

    def ensure_local_demo_approval(self, request: DashboardAiPublishRequest) -> dict:
        current = self.get_approval_state(request.approval_id)
        if current['status'] == APPROVAL_REJECTED:
            return current
        if current['status'] in {APPROVAL_APPROVED, APPROVAL_PUBLISHED}:
            return current
        if not request.approval_id.startswith('approval_chat_demo_'):
            return current
        summary = self._summary_from_publish_request(request)
        BugTrendAuditEvent.objects.create(
            event_type='ai_grafana_publish_approval_approved',
            actor=request.actor,
            chart_id=request.chart_id,
            request_summary=summary,
            result=APPROVAL_APPROVED,
        )
        return AiGrafanaPublishApprovalState(request.approval_id, APPROVAL_APPROVED, request.actor, summary).to_dict()

    def mark_published(self, request: DashboardAiPublishRequest, dashboard_url: str, correlation_id: str, provider_id: str = '') -> dict:
        summary = self._summary_from_publish_request(request)
        summary['provider_id'] = provider_id
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
            'correlation_id': summary.get('correlation_id', ''),
            'created_at': event.created_at.isoformat(),
        }

    def _approval_id(self, request: DashboardAiPublishApprovalRequest) -> str:
        payload = self._summary_from_approval_request(request, '')
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
        return f'approval_{digest[:24]}'

    def _summary_from_approval_request(self, request: DashboardAiPublishApprovalRequest, approval_id: str) -> dict:
        return {
            'approval_id': approval_id,
            'provider_id': '',
            'profile_id': request.profile_id,
            'dashboard_uid': request.dashboard_uid,
            'chart_id': request.chart_id,
            'requested_series': list(request.requested_series),
            'range_mode': request.range_mode,
            'range_start': request.range_start,
            'range_end': request.range_end,
            'dry_run_proof_id': request.dry_run_proof_id,
        }

    def _summary_from_publish_request(self, request: DashboardAiPublishRequest) -> dict:
        return {
            'approval_id': request.approval_id,
            'provider_id': '',
            'profile_id': request.profile_id,
            'dashboard_uid': request.dashboard_uid,
            'chart_id': request.chart_id,
            'requested_series': list(request.requested_series),
            'range_mode': request.range_mode,
            'range_start': request.range_start,
            'range_end': request.range_end,
            'dry_run_proof_id': request.dry_run_proof_id,
        }

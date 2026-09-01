from dataclasses import dataclass, field
from typing import List

from bug_metrics.models import BugTrendAuditEvent

from .ai_chart_definitions import AI_CHART_DEFINITIONS
from .ai_dashboard_composition import AiDashboardCompositionService
from .ai_dashboard_composition_contracts import (
    AI_DASHBOARD_COMPOSITION_CONTRACT_VERSION,
    DashboardAiPublishApprovalRequest,
    DashboardAiPublishRequest,
    DashboardAiWorkflowRequest,
    DashboardCompositionIntent,
    GcxPublicationCallbackRequest,
    GcxPublicationPreconditionRequest,
)
from .ai_dashboard_workflow import AiDashboardWorkflowService
from .ai_dashboard_approval import AiGrafanaPublishApprovalService
from .provider_aggregate_contracts import (
    DEFERRED_CHART_REASONS,
    PROVIDER_CHART_CONTRACT_VERSION,
    PROVIDER_CHART_EVIDENCE_CAPABILITIES,
    ProviderChartAggregateQuery,
    evidence_capability_for_result,
)
from .provider_aggregates import ProviderChartAggregateService
from .provider_profiles import ProviderProfileReadinessService


AI_DASHBOARD_CONTEXT_CONTRACT_VERSION = '0.1'


@dataclass(frozen=True, slots=True)
class ProviderAiDashboardContextQuery:
    provider_id: str
    profile_id: str
    begin_ww: str
    end_ww: str
    chart_ids: List[str] = field(default_factory=list)
    chart_version: int = 1


@dataclass(frozen=True, slots=True)
class ProviderAiChartExplanationRequest:
    provider_id: str
    profile_id: str
    begin_ww: str
    end_ww: str
    chart_id: str
    chart_version: int = 1


@dataclass(frozen=True, slots=True)
class ProviderAiChartDraftRequest:
    chart_id: str
    title: str
    provider_neutral_intent: str
    series: List[str]
    data_surface: str
    evidence_capability: str
    visualization: str
    actor: str = 'local_operator'


@dataclass(frozen=True, slots=True)
class ProviderActionPlanRequest:
    provider_id: str
    profile_id: str
    source_item_id: str
    action_type: str
    proposed_changes: dict[str, str]
    reason: str
    actor: str = 'local_operator'
    before_values: dict[str, str] = field(default_factory=dict)


class ProviderAiDashboardContextService:
    def __init__(self, aggregate_service: ProviderChartAggregateService, readiness_service: ProviderProfileReadinessService | None = None):
        self._aggregate_service = aggregate_service
        self._readiness_service = readiness_service or ProviderProfileReadinessService()
        self._composition_service = AiDashboardCompositionService(self._readiness_service)
        self._workflow_service = AiDashboardWorkflowService(self._composition_service, self._readiness_service)
        self._approval_service = AiGrafanaPublishApprovalService()

    def get_context(self, query: ProviderAiDashboardContextQuery) -> dict:
        chart_ids = self._selected_chart_ids(query.chart_ids)
        chart_contexts = [self._chart_context(query, chart_id) for chart_id in chart_ids]
        return {
            'contract_version': AI_DASHBOARD_CONTEXT_CONTRACT_VERSION,
            'query_state': {
                'provider_id': query.provider_id,
                'profile_id': query.profile_id,
                'begin_ww': query.begin_ww,
                'end_ww': query.end_ww,
            },
            'provider_facts_context': {
                'provider_id': query.provider_id,
                'profile_id': query.profile_id,
                'source_populations': self._unique_source_populations(chart_contexts),
                'freshness_status': self._freshness_status(chart_contexts),
                'latest_snapshot_id': self._latest_snapshot_id(chart_contexts),
                'chart_statuses': [
                    {
                        'chart_id': item['chart_id'],
                        'provider_support_status': item['provider_support_status'],
                        'reason': item['deferred_reason'] or item['provider_reason'],
                    }
                    for item in chart_contexts
                ],
            },
            'charts': chart_contexts,
        }

    def explain_chart(self, request: ProviderAiChartExplanationRequest) -> dict:
        context = self.get_context(
            ProviderAiDashboardContextQuery(
                provider_id=request.provider_id,
                profile_id=request.profile_id,
                begin_ww=request.begin_ww,
                end_ww=request.end_ww,
                chart_ids=[request.chart_id],
                chart_version=request.chart_version,
            )
        )
        chart = context['charts'][0]
        aggregate = self._aggregate_service.get_aggregates(
            ProviderChartAggregateQuery(
                provider_id=request.provider_id,
                profile_id=request.profile_id,
                begin_ww=request.begin_ww,
                end_ww=request.end_ww,
                chart_id=request.chart_id,
                chart_version=request.chart_version,
            )
        )
        if chart['provider_support_status'] == 'deferred':
            return {
                'chart_id': request.chart_id,
                'status': 'deferred',
                'answer': chart['deferred_reason'],
                'citations': [
                    {'source_type': 'chart_definition', 'chart_id': request.chart_id, 'chart_version': request.chart_version},
                    {'source_type': 'deferred_reason', 'reason': chart['deferred_reason']},
                    {'source_type': 'provider_facts', 'provider_provenance': chart['provider_provenance']},
                ],
            }
        return {
            'chart_id': request.chart_id,
            'status': chart['provider_support_status'],
            'answer': f"{chart['title']} uses Metrics-owned chart data for {request.provider_id}/{request.profile_id} with {len(aggregate.rows)} aggregate rows.",
            'citations': [
                {'source_type': 'chart_definition', 'chart_id': request.chart_id, 'chart_version': request.chart_version},
                {'source_type': 'chart_data', 'row_count': len(aggregate.grafana_rows), 'status': aggregate.status},
                {'source_type': 'provider_facts', 'provider_provenance': chart['provider_provenance']},
                {'source_type': 'aggregate_artifact', 'fact_snapshot_id': aggregate.fact_snapshot_id, 'run_metadata': aggregate.run_metadata},
            ],
        }

    def create_chart_draft(self, request: ProviderAiChartDraftRequest) -> dict:
        self._validate_provider_chart_draft(request)
        BugTrendAuditEvent.objects.create(
            event_type='ai_provider_chart_draft_validated',
            actor=request.actor,
            chart_id=request.chart_id,
            request_summary={
                'data_surface': request.data_surface,
                'evidence_capability': request.evidence_capability,
                'series': list(request.series),
            },
        )
        return {
            'status': 'draft_validated',
            'chart_id': request.chart_id,
            'title': request.title,
            'semantic_owner': 'metrics',
            'provider_neutral_intent': request.provider_neutral_intent,
            'series': list(request.series),
            'data_surface': request.data_surface,
            'evidence_capability': request.evidence_capability,
            'visualization': request.visualization,
            'publication_policy': 'metrics_validator_required',
        }

    def list_composition_catalog(self, profile_id: str = '') -> dict:
        return self._composition_service.list_composition_catalog(profile_id)

    def validate_composition_intent(self, intent: DashboardCompositionIntent) -> dict:
        return self._composition_service.validate_composition_intent(intent)

    def run_composition_workflow(self, request: DashboardAiWorkflowRequest) -> dict:
        return self._workflow_service.run_composition_workflow(request)

    def validate_render_config_draft(self, draft_render_config: dict) -> dict:
        return self._composition_service.validate_render_config_draft(draft_render_config)

    def validate_gcx_publication_precondition(self, request: GcxPublicationPreconditionRequest) -> dict:
        return self._composition_service.validate_gcx_publication_precondition(request)

    def record_gcx_publication_callback(self, request: GcxPublicationCallbackRequest) -> dict:
        return self._composition_service.record_gcx_publication_callback(request)

    def request_grafana_publish_approval(self, request: DashboardAiPublishApprovalRequest) -> dict:
        return self._approval_service.request_approval(request)

    def decide_grafana_publish_approval(self, approval_id: str, decision: str, actor: str) -> dict:
        return self._approval_service.decide_approval(approval_id, decision, actor)

    def get_grafana_publish_approval(self, approval_id: str) -> dict:
        return self._approval_service.get_approval_state(approval_id)

    def list_grafana_publish_history(self, limit: int = 25) -> dict:
        return self._approval_service.list_publish_history(limit)

    def publish_grafana_dashboard_demo(self, request: DashboardAiPublishRequest, correlation_id: str) -> dict:
        if not request.approval_id or not request.dry_run_proof_id:
            return self._composition_service.publish_grafana_dashboard_demo(request, correlation_id)
        approval = self._approval_service.ensure_local_demo_approval(request)
        if approval['status'] != 'approved':
            return {
                'contract_version': AI_DASHBOARD_COMPOSITION_CONTRACT_VERSION,
                'status': 'blocked',
                'reason': 'approval_not_granted',
                'operation': request.operation,
                'dashboard_uid': request.dashboard_uid,
                'correlation_id': correlation_id,
                'dry_run_proof_id': request.dry_run_proof_id,
                'approval_id': request.approval_id,
                'approval': approval,
            }
        readiness = self._aggregate_service.get_aggregates(
            ProviderChartAggregateQuery(
                provider_id='',
                profile_id=request.profile_id,
                begin_ww=request.range_start if request.range_mode == 'ww' else '',
                end_ww=request.range_end if request.range_mode == 'ww' else '',
                chart_id=request.chart_id,
                chart_version=1,
                range_mode=request.range_mode,
                begin_date=request.range_start if request.range_mode == 'date' else '',
                end_date=request.range_end if request.range_mode == 'date' else '',
            )
        )
        if readiness.status != 'supported' or not readiness.grafana_rows:
            return {
                'contract_version': AI_DASHBOARD_COMPOSITION_CONTRACT_VERSION,
                'status': 'blocked',
                'reason': 'data_not_ready',
                'operation': request.operation,
                'dashboard_uid': request.dashboard_uid,
                'correlation_id': correlation_id,
                'dry_run_proof_id': request.dry_run_proof_id,
                'approval_id': request.approval_id,
                'readiness': {
                    'provider_id': readiness.provider_id,
                    'profile_id': readiness.profile_id,
                    'chart_id': readiness.chart_id,
                    'chart_version': readiness.chart_version,
                    'status': readiness.status,
                    'reason': readiness.reason,
                    'fact_snapshot_id': readiness.fact_snapshot_id,
                    'run_metadata': readiness.run_metadata,
                },
            }
        result = self._composition_service.publish_grafana_dashboard_demo(request, correlation_id)
        if result.get('status') == 'published':
            result['approval'] = self._approval_service.mark_published(
                request,
                result.get('dashboard_url', ''),
                correlation_id,
                readiness.provider_id,
            )
        return result

    def list_entry_placements(self) -> List[dict]:
        backend_contracts = ['ai_dashboard_context', 'ai_chart_explanation', 'ai_chart_draft', 'provider_action_plan']
        return [
            {
                'placement_id': 'grafana_app_scenes',
                'status': 'preferred',
                'backend_contracts': backend_contracts,
            },
            {
                'placement_id': 'metrics_ui_sidebar',
                'status': 'preferred',
                'backend_contracts': backend_contracts,
            },
            {
                'placement_id': 'separate_ai_dashboard',
                'status': 'fallback',
                'backend_contracts': backend_contracts,
            },
        ]

    def create_action_plan(self, request: ProviderActionPlanRequest) -> dict:
        if request.provider_id == 'hsdes':
            return self._create_non_executable_hsdes_action_suggestion(request)
        if request.provider_id != 'jira':
            raise ValueError('Only Jira ProviderActionPlan proposals are in scope for this phase.')
        preview = [
            {
                'field': field_name,
                'before': request.before_values.get(field_name, ''),
                'after': after_value,
            }
            for field_name, after_value in sorted(request.proposed_changes.items())
        ]
        plan = {
            'provider_id': request.provider_id,
            'profile_id': request.profile_id,
            'source_item_id': request.source_item_id,
            'action_type': request.action_type,
            'reason': request.reason,
            'approval_state': 'approval_required',
            'execution_mode': 'preview_only',
            'direct_write_performed': False,
            'before_after_preview': preview,
        }
        BugTrendAuditEvent.objects.create(
            event_type='provider_action_plan_proposed',
            actor=request.actor,
            request_summary=plan,
        )
        return plan

    def _create_non_executable_hsdes_action_suggestion(self, request: ProviderActionPlanRequest) -> dict:
        preview = [
            {
                'field': field_name,
                'before': request.before_values.get(field_name, ''),
                'after': after_value,
            }
            for field_name, after_value in sorted(request.proposed_changes.items())
        ]
        plan = {
            'provider_id': request.provider_id,
            'profile_id': request.profile_id,
            'source_item_id': request.source_item_id,
            'action_type': request.action_type,
            'reason': request.reason,
            'approval_state': 'unsupported',
            'execution_mode': 'disabled',
            'direct_write_performed': False,
            'before_after_preview': preview,
            'unsupported_reason': 'HSD-ES writes remain disabled until tenant/subject required fields, permission model, send_mail behavior and approval policy are reviewed.',
        }
        BugTrendAuditEvent.objects.create(
            event_type='provider_action_plan_unsupported',
            actor=request.actor,
            request_summary=plan,
            result='unsupported',
        )
        return plan

    def _chart_context(self, query: ProviderAiDashboardContextQuery, chart_id: str) -> dict:
        aggregate = self._aggregate_service.get_aggregates(
            ProviderChartAggregateQuery(
                provider_id=query.provider_id,
                profile_id=query.profile_id,
                begin_ww=query.begin_ww,
                end_ww=query.end_ww,
                chart_id=chart_id,
                chart_version=query.chart_version,
            )
        )
        support_status = self._support_status(chart_id, aggregate.status)
        provider_reason = DEFERRED_CHART_REASONS.get(chart_id, aggregate.reason)
        return {
            'chart_id': chart_id,
            'chart_version': query.chart_version,
            'title': AI_CHART_DEFINITIONS[chart_id]['title'],
            'semantic_owner': 'metrics',
            'data_surface': '/api/provider-charts/data/',
            'aggregate_contract_version': PROVIDER_CHART_CONTRACT_VERSION,
            'series': list(AI_CHART_DEFINITIONS[chart_id]['series']),
            'evidence_capability': PROVIDER_CHART_EVIDENCE_CAPABILITIES.get(chart_id, 'summary_only'),
            'effective_evidence_capability': evidence_capability_for_result(chart_id, support_status),
            'provider_binding': self._provider_binding(query.provider_id, chart_id),
            'provider_support_status': support_status,
            'provider_reason': provider_reason,
            'deferred_reason': DEFERRED_CHART_REASONS.get(chart_id, ''),
            'provider_provenance': aggregate.source_population,
            'fact_snapshot_id': aggregate.fact_snapshot_id,
            'run_metadata': aggregate.run_metadata,
            'allowed_ai_sources': ['chart_definition', 'provider_facts', 'chart_data', 'evidence_rows', 'aggregate_artifacts', 'deferred_reasons'],
        }

    def _selected_chart_ids(self, chart_ids: List[str]) -> List[str]:
        selected = chart_ids or list(AI_CHART_DEFINITIONS.keys())
        unknown = sorted(set(selected) - set(AI_CHART_DEFINITIONS.keys()))
        if unknown:
            raise ValueError(f'Unknown approved chart definitions: {", ".join(unknown)}.')
        return selected

    def _support_status(self, chart_id: str, aggregate_status: str) -> str:
        if chart_id in DEFERRED_CHART_REASONS:
            return 'deferred'
        return aggregate_status

    def _provider_binding(self, provider_id: str, chart_id: str) -> str:
        if chart_id in DEFERRED_CHART_REASONS:
            return 'first_wave_deferred'
        if provider_id == 'hsdes':
            return 'hsdes_quality_configuration_required'
        if provider_id == 'jira':
            return 'jira_first_quality'
        return 'unsupported_provider'

    def _unique_source_populations(self, chart_contexts: List[dict]) -> List[dict]:
        populations = []
        seen = set()
        for item in chart_contexts:
            provenance = item['provider_provenance']
            key = tuple(sorted(provenance.items()))
            if key not in seen:
                seen.add(key)
                populations.append(provenance)
        return populations

    def _freshness_status(self, chart_contexts: List[dict]) -> str:
        for item in chart_contexts:
            freshness_status = item.get('run_metadata', {}).get('freshness_status', '')
            if freshness_status:
                return freshness_status
        return ''

    def _latest_snapshot_id(self, chart_contexts: List[dict]) -> str:
        for item in chart_contexts:
            snapshot_id = item.get('fact_snapshot_id', '')
            if snapshot_id:
                return snapshot_id
        return ''

    def _validate_provider_chart_draft(self, request: ProviderAiChartDraftRequest) -> None:
        unknown = set([request.chart_id]) - set(AI_CHART_DEFINITIONS.keys())
        if unknown:
            raise ValueError(f'Unknown approved chart definitions: {", ".join(sorted(unknown))}.')
        errors = []
        if request.data_surface != '/api/provider-charts/data/':
            errors.append('AI chart drafts must use an approved Metrics provider chart data surface.')
        if request.evidence_capability != PROVIDER_CHART_EVIDENCE_CAPABILITIES.get(request.chart_id, 'summary_only'):
            errors.append('AI chart drafts must declare the approved evidence capability.')
        approved_series = set(AI_CHART_DEFINITIONS[request.chart_id]['series'])
        unknown_series = sorted(set(request.series) - approved_series)
        if unknown_series:
            errors.append(f'AI chart drafts reference unknown approved series: {", ".join(unknown_series)}.')
        intent_text = request.provider_neutral_intent.lower()
        forbidden_fragments = ['jql', 'eql', 'select ', ' from ', 'project =', 'component =', 'customfield_', 'ip_fw_sw_sensing', 'queryid', 'db.']
        if any(fragment in intent_text for fragment in forbidden_fragments):
            errors.append('AI chart drafts must use provider-neutral intent rather than native query semantics.')
        if errors:
            raise ValueError(errors)

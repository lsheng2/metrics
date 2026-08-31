from uuid import uuid4

from .ai_dashboard_composition import AiDashboardCompositionService
from .ai_dashboard_composition_contracts import (
    AI_DASHBOARD_COMPOSITION_CONTRACT_VERSION,
    DashboardAiWorkflowRequest,
    DashboardCompositionIntent,
    GcxPublicationPreconditionRequest,
    PublicationAuditMetadata,
)
from .provider_profiles import ProviderProfileReadinessService


class AiDashboardWorkflowService:
    def __init__(self, composition_service: AiDashboardCompositionService,
                 readiness_service: ProviderProfileReadinessService):
        self._composition_service = composition_service
        self._readiness_service = readiness_service

    def run_composition_workflow(self, request: DashboardAiWorkflowRequest) -> dict:
        intent = DashboardCompositionIntent(
            profile_id=request.profile_id,
            dashboard_uid=request.dashboard_uid,
            chart_id=request.chart_id,
            requested_series=list(request.requested_series),
            range_mode=request.range_mode,
            range_start=request.range_start,
            range_end=request.range_end,
            output_type=request.output_type,
            actor=request.actor,
            panel_title=request.panel_title,
            visualization=request.visualization,
        )
        catalog = self._composition_service.list_composition_catalog(request.profile_id)
        intent_validation = self._composition_service.validate_composition_intent(intent)
        draft_render_config = intent_validation.get('draft_render_config')
        render_validation = self._render_not_checked('Intent validation did not produce a render config draft.')
        gcx_precondition = self._precondition_not_checked(request, 'No validated render config draft is available.')
        if draft_render_config:
            render_validation = self._composition_service.validate_render_config_draft(draft_render_config)
            if render_validation.get('valid'):
                gcx_precondition = self._composition_service.validate_gcx_publication_precondition(
                    GcxPublicationPreconditionRequest(
                        operation=request.operation,
                        actor=request.actor,
                        draft_render_config=draft_render_config,
                    )
                )
        return {
            'contract_version': AI_DASHBOARD_COMPOSITION_CONTRACT_VERSION,
            'workflow_type': 'metrics_ai_dashboard_composition',
            'correlation_id': f'metrics-ai-{uuid4()}',
            'request': self._workflow_request_payload(request),
            'catalog_summary': self._workflow_catalog_summary(catalog),
            'intent_validation': intent_validation,
            'render_validation': render_validation,
            'gcx_precondition': gcx_precondition,
            'guidance': self._workflow_guidance(intent_validation, render_validation, gcx_precondition),
        }

    def _workflow_request_payload(self, request: DashboardAiWorkflowRequest) -> dict:
        return {
            'provider_id': self._provider_id_for_profile(request.profile_id),
            'profile_id': request.profile_id,
            'dashboard_uid': request.dashboard_uid,
            'chart_id': request.chart_id,
            'requested_series': list(request.requested_series),
            'range_mode': request.range_mode,
            'range_start': request.range_start,
            'range_end': request.range_end,
            'operation': request.operation,
            'output_type': request.output_type,
            'actor': request.actor,
            'panel_title': request.panel_title,
            'visualization': request.visualization,
        }

    def _workflow_catalog_summary(self, catalog: dict) -> dict:
        profiles = catalog.get('profiles', [])
        chart_recipes = catalog.get('chart_recipes', {})
        return {
            'profile_count': len(profiles),
            'profiles': [
                {
                    'profile_id': profile.get('profile_id', ''),
                    'provider_id': profile.get('provider_id', ''),
                    'status': profile.get('status', ''),
                    'freshness_status': profile.get('freshness_status', ''),
                }
                for profile in profiles
            ],
            'chart_ids': sorted(chart_recipes.keys()),
            'range_modes': list(catalog.get('range_modes', [])),
            'limits': dict(catalog.get('limits', {})),
        }

    def _render_not_checked(self, reason: str) -> dict:
        return {
            'contract_version': AI_DASHBOARD_COMPOSITION_CONTRACT_VERSION,
            'valid': False,
            'status': 'not_checked',
            'reason': reason,
            'findings': [],
        }

    def _precondition_not_checked(self, request: DashboardAiWorkflowRequest, reason: str) -> dict:
        return {
            'contract_version': AI_DASHBOARD_COMPOSITION_CONTRACT_VERSION,
            'status': 'not_checked',
            'mutation_allowed': False,
            'reason': reason,
            'findings': [],
            'publication_audit': PublicationAuditMetadata(
                actor=request.actor,
                operation=request.operation,
                validation_status='not_checked',
                approval_state='blocked',
                mutation_allowed=False,
            ).to_dict(),
        }

    def _workflow_guidance(self, intent_validation: dict, render_validation: dict, gcx_precondition: dict) -> dict:
        if intent_validation.get('status') == 'needs_metric_recipe':
            return {
                'status': 'needs_metric_recipe',
                'message': 'Metrics must add or approve the requested series before AI can create this chart.',
                'next_action': 'update_metrics_chart_recipe',
            }
        if not intent_validation.get('valid'):
            return {
                'status': 'blocked',
                'message': 'Fix the intent validation findings before generating a chart draft.',
                'next_action': 'revise_ai_request',
            }
        if not render_validation.get('valid'):
            return {
                'status': 'blocked',
                'message': 'Fix render config validation findings before any gcx dry-run or import.',
                'next_action': 'revise_render_config',
            }
        if gcx_precondition.get('mutation_allowed'):
            return {
                'status': 'ready_for_dry_run',
                'message': 'The draft passed Metrics validation and gcx precondition; run gcx dry-run before any approved import.',
                'next_action': 'gcx_dry_run',
            }
        return {
            'status': 'blocked',
            'message': 'Metrics did not allow the requested gcx operation.',
            'next_action': 'review_precondition_findings',
        }

    def _provider_id_for_profile(self, profile_id: str) -> str:
        return self._readiness_service.get_readiness('', profile_id).get('provider_id', '')

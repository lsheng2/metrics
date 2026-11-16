from typing import List

from django.core.exceptions import ObjectDoesNotExist

from .ai_context import (
    DashboardAiArtifactValidationRequest,
    DashboardAiPublishApprovalRequest,
    DashboardAiPublishRequest,
    DashboardAiWorkflowRequest,
    DashboardCompositionIntent,
    GcxPublicationCallbackRequest,
    GcxPublicationPreconditionRequest,
    ProviderActionPlanRequest,
    ProviderAiChartDraftRequest,
    ProviderAiChartExplanationRequest,
    ProviderAiDashboardContextQuery,
)
from .chart_catalog import AiChartDraftRequest, ChartDefinition


class BugTrendAiDashboardApiMixin:
    def create_ai_chart_draft(self, request: AiChartDraftRequest) -> ChartDefinition:
        return self._chart_catalog_service.create_ai_chart_draft(request)

    def get_ai_dashboard_context(self, query: ProviderAiDashboardContextQuery) -> dict:
        return self._provider_ai_context_service.get_context(query)

    def get_ai_workbench_context(self, values: dict) -> dict:
        try:
            scope_id = int(values['binding_key'].removeprefix('metrics.scope.'))
            scope = self.get_scope(scope_id)
        except (KeyError, TypeError, ValueError, ObjectDoesNotExist):
            return {'status': 'binding_unresolved'}
        binding = self.resolve_scope_provider_binding(scope)
        if (not binding.is_resolved or binding.profile_id != values.get('profile_id')
                or binding.provider_id != values.get('provider_id')):
            return {'status': 'binding_unresolved'}
        return self._provider_ai_context_service.get_workbench_context(values)

    def explain_ai_dashboard_chart(self, request: ProviderAiChartExplanationRequest) -> dict:
        return self._provider_ai_context_service.explain_chart(request)

    def create_ai_provider_chart_draft(self, request: ProviderAiChartDraftRequest) -> dict:
        return self._provider_ai_context_service.create_chart_draft(request)

    def get_ai_sidecar_status(self) -> dict:
        return self._ai_sidecar_probe_service.get_status()

    def list_ai_dashboard_composition_catalog(self, profile_id: str = '') -> dict:
        return self._provider_ai_context_service.list_composition_catalog(profile_id)

    def validate_ai_dashboard_composition_intent(self, request: DashboardCompositionIntent) -> dict:
        return self._provider_ai_context_service.validate_composition_intent(request)

    def run_ai_dashboard_workflow(self, request: DashboardAiWorkflowRequest) -> dict:
        workflow = self._provider_ai_context_service.run_composition_workflow(request)
        workflow['sidecar_readiness'] = self.get_ai_sidecar_status()
        return workflow

    def validate_ai_dashboard_render_config_draft(self, draft_render_config: dict) -> dict:
        return self._provider_ai_context_service.validate_render_config_draft(draft_render_config)

    def validate_ai_dashboard_workspace_artifact(self, request: DashboardAiArtifactValidationRequest) -> dict:
        return self._provider_ai_context_service.validate_workspace_artifact(request)

    def validate_ai_gcx_publication_precondition(self, request: GcxPublicationPreconditionRequest) -> dict:
        return self._provider_ai_context_service.validate_gcx_publication_precondition(request)

    def record_ai_gcx_publication_callback(self, request: GcxPublicationCallbackRequest) -> dict:
        return self._provider_ai_context_service.record_gcx_publication_callback(request)

    def publish_ai_grafana_dashboard_demo(self, request: DashboardAiPublishRequest, correlation_id: str) -> dict:
        return self._provider_ai_context_service.publish_grafana_dashboard_demo(request, correlation_id)

    def request_ai_grafana_publish_approval(self, request: DashboardAiPublishApprovalRequest) -> dict:
        return self._provider_ai_context_service.request_grafana_publish_approval(request)

    def decide_ai_grafana_publish_approval(self, approval_id: str, decision: str, actor: str = 'local_operator') -> dict:
        return self._provider_ai_context_service.decide_grafana_publish_approval(approval_id, decision, actor)

    def get_ai_grafana_publish_approval(self, approval_id: str) -> dict:
        return self._provider_ai_context_service.get_grafana_publish_approval(approval_id)

    def list_ai_grafana_publish_history(self, limit: int = 25) -> dict:
        return self._provider_ai_context_service.list_grafana_publish_history(limit)

    def list_ai_entry_placements(self) -> List[dict]:
        return self._provider_ai_context_service.list_entry_placements()

    def create_provider_action_plan(self, request: ProviderActionPlanRequest) -> dict:
        return self._provider_ai_context_service.create_action_plan(request)

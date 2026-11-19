from django.core.exceptions import ObjectDoesNotExist

from .chart_catalog import AiChartDraftRequest, ChartDefinition


class BugTrendAiDashboardApiMixin:
    def evaluate_ai_chart_workflow(self, request):
        from .ai_chart_workflow import AiChartWorkflowService
        return AiChartWorkflowService().run(request)

    def preview_ai_chart_publication(self, request):
        from .ai_chart_workflow import AiChartWorkflowService
        return AiChartWorkflowService().preview(request)

    def publish_approved_ai_chart(self, approval):
        from .ai_chart_publication import publish_approved_chart
        return publish_approved_chart(approval)

    def list_ai_chart_publications(self, limit=25):
        from .ai_chart_publication import list_chart_publications
        return list_chart_publications(limit)

    def create_ai_chart_draft(self, request: AiChartDraftRequest) -> ChartDefinition:
        return self._chart_catalog_service.create_ai_chart_draft(request)

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

    def list_ai_dashboard_composition_catalog(self, profile_id: str = '') -> dict:
        return self._provider_ai_context_service.list_composition_catalog(profile_id)

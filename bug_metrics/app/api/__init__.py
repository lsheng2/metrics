from datetime import date
from typing import List, Optional

from bug_metrics.models import BugTrendBucket, BugTrendCalculationRun, BugTrendChartDefinition, JiraScopeConfig
from jira_history.container import jira_history_container

from .ai_context import (
    DashboardAiPublishApprovalRequest,
    DashboardAiPublishRequest,
    DashboardAiWorkflowRequest,
    DashboardCompositionIntent,
    GcxPublicationPreconditionRequest,
    ProviderActionPlanRequest,
    ProviderAiChartDraftRequest,
    ProviderAiChartExplanationRequest,
    ProviderAiDashboardContextQuery,
    ProviderAiDashboardContextService,
    GcxPublicationCallbackRequest,
)
from .ai_sidecar import AiSidecarProbeService
from .calculation import BugTrendCalculationService
from .chart_catalog import AiChartDraftRequest, ChartCatalogService, ChartDefinition, ChartPublishResult, ChartValidationResult, RendererRouteDecisionResult
from .chart_data import BUG_TREND_CONTRACT_VERSION, BugTrendChart, BugTrendDataset, BugTrendRunMetadata
from .data_health import BugTrendCalculationHealth, BugTrendCalculationHealthService
from .evidence_export import BugTrendEvidenceExport, BugTrendEvidenceExportService
from .hsdes_projection import HsdesProviderProjectionService
from .page_query import (
    BugTrendChartListSyncResult,
    BugTrendEvidenceTicketResult,
    BugTrendPageQueryService,
    BugTrendPageQueryState,
    BugTrendTicketListFilters,
)
from .provider_aggregate_contracts import (
    ProviderChartAggregateQuery,
    ProviderChartAggregateResult,
    ProviderChartEvidenceQuery,
)
from .provider_aggregates import ProviderChartAggregateService
from .provider_correlation import ProviderCorrelationService
from .provider_evidence import ProviderChartEvidenceService
from .provider_profiles import ProviderProfileReadinessService
from .scope_audit import ScopeAudit, ScopeAuditService
from .scope_config import SavedScopeConfig, ScopeConfigService, ScopeConfigValidationResult
from .series import active_bug_trend_series
from provider_sync.app.api import ProviderSyncCacheService


class ApiForBugTrend:
    def __init__(self):
        self._page_query_service = BugTrendPageQueryService(
            self.get_scope,
            self._format_bucket_label,
        )
        self._scope_audit_service = ScopeAuditService()
        self._scope_config_service = ScopeConfigService()
        self._chart_catalog_service = ChartCatalogService()
        self._calculation_health_service = BugTrendCalculationHealthService()
        self._evidence_export_service = BugTrendEvidenceExportService()
        self._calculation_service = BugTrendCalculationService(self.get_scope)
        self._provider_chart_aggregate_service = ProviderChartAggregateService()
        self._provider_chart_evidence_service = ProviderChartEvidenceService(self._provider_chart_aggregate_service, self.get_evidence_tickets)
        self._provider_ai_context_service = ProviderAiDashboardContextService(self._provider_chart_aggregate_service)
        self._ai_sidecar_probe_service = AiSidecarProbeService()
        self._provider_profile_readiness_service = ProviderProfileReadinessService()
        self._hsdes_projection_service = HsdesProviderProjectionService()
        self._provider_correlation_service = ProviderCorrelationService()
        self._provider_sync_cache_service = ProviderSyncCacheService()

    def list_enabled_scopes(self) -> List[JiraScopeConfig]:
        return list(JiraScopeConfig.objects.filter(enabled=True).order_by('ip', 'project_label', 'name'))

    def list_scope_configs(self) -> List[SavedScopeConfig]:
        return self._scope_config_service.list_scope_configs()

    def get_scope(self, scope_id: int) -> JiraScopeConfig:
        return JiraScopeConfig.objects.get(id=scope_id, enabled=True)

    def get_scope_config(self, scope_id: int) -> SavedScopeConfig:
        return self._scope_config_service.get_scope_config(scope_id)

    def validate_scope_config(self, config: SavedScopeConfig) -> ScopeConfigValidationResult:
        return self._scope_config_service.validate_scope_config(config)

    def save_scope_config(self, config: SavedScopeConfig) -> SavedScopeConfig:
        return self._scope_config_service.save_scope_config(config)

    def activate_scope_config(self, scope_id: int) -> SavedScopeConfig:
        return self._scope_config_service.activate_scope_config(scope_id)

    def disable_scope_config(self, scope_id: int) -> SavedScopeConfig:
        return self._scope_config_service.disable_scope_config(scope_id)

    def list_calculation_health(self) -> List[BugTrendCalculationHealth]:
        return self._calculation_health_service.list_calculation_health()

    def list_provider_sync_health(self) -> list[dict]:
        return self._provider_profile_readiness_service.list_profile_health()

    def list_enabled_charts(self) -> List[ChartDefinition]:
        return self._chart_catalog_service.list_enabled_charts()

    def get_chart_definition(self, chart_id: str) -> ChartDefinition:
        return self._chart_catalog_service.get_chart(chart_id)

    def validate_chart_for_publish(self, chart) -> ChartValidationResult:
        return self._chart_catalog_service.validate_chart_for_publish(chart)

    def record_renderer_route_decision(self, chart_id: str, same_page_evidence_required: bool,
                                       c_stock_same_page_capable: bool, supported_c_stock_capabilities: List[str],
                                       decision_summary: str,
                                       renderer_route: str = BugTrendChartDefinition.ROUTE_C_STOCK) -> RendererRouteDecisionResult:
        return self._chart_catalog_service.record_renderer_route_decision(chart_id, same_page_evidence_required, c_stock_same_page_capable, supported_c_stock_capabilities, decision_summary, renderer_route)

    def latest_renderer_route_decision(self, chart_id: str) -> RendererRouteDecisionResult | None:
        return self._chart_catalog_service.latest_renderer_route_decision(chart_id)

    def create_ai_chart_draft(self, request: AiChartDraftRequest) -> ChartDefinition:
        return self._chart_catalog_service.create_ai_chart_draft(request)

    def get_ai_dashboard_context(self, query: ProviderAiDashboardContextQuery) -> dict:
        return self._provider_ai_context_service.get_context(query)

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

    def publish_chart(self, chart_id: str, actor: str = 'local_operator', governance_mode: str = 'personal') -> ChartPublishResult:
        return self._chart_catalog_service.publish_chart(chart_id, actor, governance_mode)

    def record_failed_calculation(self, scope_id: int, coverage_start: date, coverage_end: date) -> BugTrendCalculationRun:
        return self._calculation_service.record_failed_calculation(scope_id, coverage_start, coverage_end)

    def get_chart(self, scope_id: int, begin: date, end: date, chart_id: str = 'default_bug_trend') -> BugTrendChart:
        scope = self.get_scope(scope_id)
        chart_definition = self._enabled_chart_definition(chart_id)
        run = self._latest_authoritative_run(scope, begin, end)
        if run is None:
            stale_run = self._latest_stale_run(scope, begin, end)
            if stale_run:
                return BugTrendChart(
                    scope.id,
                    BUG_TREND_CONTRACT_VERSION,
                    str(stale_run.id),
                    [],
                    [],
                    [],
                    'Calculation run does not match the current scope configuration. Recalculate this scope to refresh the Bug Trend chart.',
                    self._run_metadata(scope, stale_run, 'stale_config'),
                    current_evidence_available=False,
                )
            return BugTrendChart(scope.id, BUG_TREND_CONTRACT_VERSION, None, [], [], [], 'No completed calculation covers the selected range for the current scope configuration.', current_evidence_available=False)

        return self._chart_from_run(scope, run, begin, end, chart_definition)

    def get_chart_for_run(self, calculation_run_id: str, begin: date | None = None, end: date | None = None, chart_id: str = 'default_bug_trend') -> BugTrendChart:
        run = BugTrendCalculationRun.objects.select_related('scope').get(
            id=calculation_run_id,
            status=BugTrendCalculationRun.STATUS_COMPLETED,
        )
        scope = self.get_scope(run.scope_id)
        chart_definition = self._enabled_chart_definition(chart_id)
        chart_begin = begin or run.source_coverage_start
        chart_end = end or run.source_coverage_end
        if run.config_version_hash != scope.config_version_hash:
            return BugTrendChart(scope.id, BUG_TREND_CONTRACT_VERSION, str(run.id), [], [], [], 'Calculation run does not match the current scope configuration.', self._run_metadata(scope, run, 'stale_config'), current_evidence_available=False)
        return self._chart_from_run(scope, run, chart_begin, chart_end, chart_definition)

    def _chart_from_run(self, scope: JiraScopeConfig, run: BugTrendCalculationRun, begin: date, end: date, chart_definition: BugTrendChartDefinition) -> BugTrendChart:
        if run.source_coverage_start > begin or run.source_coverage_end < end:
            return BugTrendChart(scope.id, BUG_TREND_CONTRACT_VERSION, str(run.id), [], [], [], 'Calculation run does not cover the selected range.', current_evidence_available=False)

        buckets = list(run.buckets.filter(bucket_start__gte=begin, bucket_end__lte=end).order_by('bucket_start'))
        return BugTrendChart(
            scope_id=scope.id,
            contract_version=BUG_TREND_CONTRACT_VERSION,
            calculation_run_id=str(run.id),
            labels=[self._format_bucket_label(bucket) for bucket in buckets],
            bucket_ids=[str(bucket.id) for bucket in buckets],
            datasets=self._build_datasets(scope, buckets, chart_definition),
            run_metadata=self._run_metadata(scope, run, 'fresh'),
            current_evidence_available=True,
            bucket_starts=[bucket.bucket_start.isoformat() for bucket in buckets],
            bucket_ends=[bucket.bucket_end.isoformat() for bucket in buckets],
            bucket_granularity=run.bucket_granularity,
        )

    def get_evidence_tickets(self, state: BugTrendPageQueryState) -> BugTrendEvidenceTicketResult:
        chart_definition = self._enabled_evidence_chart_definition(state.active_chart_id)
        state.allowed_series_names = list(chart_definition.chart_spec.get('series', []))
        return self._page_query_service.get_evidence_tickets(state)

    def export_evidence_tickets(self, state: BugTrendPageQueryState, actor: str = 'local_operator') -> BugTrendEvidenceExport:
        result = self.get_evidence_tickets(state)
        return self._evidence_export_service.export_evidence_tickets(state, result, actor)

    def validate_chart_list_sync(self, state: BugTrendPageQueryState) -> BugTrendChartListSyncResult:
        chart_definition = self._enabled_evidence_chart_definition(state.active_chart_id)
        state.allowed_series_names = list(chart_definition.chart_spec.get('series', []))
        return self._page_query_service.validate_chart_list_sync(state)

    def get_scope_audit(self, scope_id: int) -> ScopeAudit:
        scope = self.get_scope(scope_id)
        facts = jira_history_container.jira_history_api.get_scope_audit_facts(scope)
        return self._scope_audit_service.build_scope_audit(scope, facts)

    def recalculate_scope(self, scope_id: int, coverage_start: date, coverage_end: date) -> BugTrendCalculationRun:
        return self._calculation_service.recalculate_scope(scope_id, coverage_start, coverage_end)

    def get_provider_chart_aggregates(self, query: ProviderChartAggregateQuery) -> ProviderChartAggregateResult:
        return self._provider_chart_aggregate_service.get_aggregates(query)

    def build_hsdes_quality_aggregate_artifact(self, query: ProviderChartAggregateQuery, facts: list[dict]) -> ProviderChartAggregateResult:
        return self._provider_chart_aggregate_service.build_hsdes_quality_aggregate_artifact(query, facts)

    def get_provider_profile_readiness(self, provider_id: str, profile_id: str) -> dict:
        return self._provider_profile_readiness_service.get_readiness(provider_id, profile_id)

    def validate_provider_profile_drift(self, provider_id: str, profile_id: str, observed_profile: dict) -> dict:
        return self._provider_profile_readiness_service.validate_drift(provider_id, profile_id, observed_profile)

    def get_provider_capability_manifest(self, provider_id: str, profile_id: str) -> dict:
        return self._provider_profile_readiness_service.get_capability_manifest(provider_id, profile_id)

    def normalize_hsdes_search_page(self, profile_id: str, payload: dict) -> dict:
        return self._hsdes_projection_service.normalize_search_page(profile_id, payload)

    def normalize_hsdes_article_detail(self, profile_id: str, payload: dict) -> dict:
        return self._hsdes_projection_service.normalize_article_detail(profile_id, payload)

    def generate_provider_correlation_candidates(self, source_facts: list[dict], target_facts: list[dict]) -> list[dict]:
        return self._provider_correlation_service.generate_candidates(source_facts, target_facts)

    def review_provider_correlation(self, candidate: dict, state: str, reviewer: str) -> dict:
        return self._provider_correlation_service.review_correlation(candidate, state, reviewer)

    def get_provider_correlation_evidence_view(self, correlations: list[dict]) -> dict:
        return self._provider_correlation_service.evidence_view(correlations)

    def explain_cross_provider_correlation_risk(self, correlations: list[dict]) -> dict:
        return self._provider_correlation_service.explain_risk(correlations)

    def get_provider_chart_evidence(self, query: ProviderChartEvidenceQuery) -> dict:
        return self._provider_chart_evidence_service.get_provider_chart_evidence(query)

    def _latest_authoritative_run(self, scope: JiraScopeConfig, begin: date, end: date) -> Optional[BugTrendCalculationRun]:
        return BugTrendCalculationRun.objects.filter(
            scope=scope,
            status=BugTrendCalculationRun.STATUS_COMPLETED,
            config_version_hash=scope.config_version_hash,
            source_coverage_start__lte=begin,
            source_coverage_end__gte=end,
        ).order_by('-completed_at').first()

    def _latest_stale_run(self, scope: JiraScopeConfig, begin: date, end: date) -> Optional[BugTrendCalculationRun]:
        return BugTrendCalculationRun.objects.filter(
            scope=scope,
            status=BugTrendCalculationRun.STATUS_COMPLETED,
            source_coverage_start__lte=begin,
            source_coverage_end__gte=end,
        ).exclude(config_version_hash=scope.config_version_hash).order_by('-completed_at').first()

    def _run_metadata(self, scope: JiraScopeConfig, run: BugTrendCalculationRun, freshness_status: str) -> BugTrendRunMetadata:
        return BugTrendRunMetadata(
            calculation_run_id=str(run.id),
            run_config_version_hash=run.config_version_hash,
            current_config_version_hash=scope.config_version_hash,
            freshness_status=freshness_status,
            source_coverage_start=run.source_coverage_start.isoformat(),
            source_coverage_end=run.source_coverage_end.isoformat(),
            completed_at=run.completed_at.isoformat() if run.completed_at else '',
        )

    def _enabled_chart_definition(self, chart_id: str) -> BugTrendChartDefinition:
        return BugTrendChartDefinition.objects.select_related('evidence_contract').get(chart_id=chart_id, enabled=True, status=BugTrendChartDefinition.STATUS_PUBLISHED)

    def _enabled_evidence_chart_definition(self, chart_id: str) -> BugTrendChartDefinition:
        chart_definition = self._enabled_chart_definition(chart_id)
        if chart_definition.evidence_contract.capability == chart_definition.evidence_contract.CAPABILITY_SUMMARY_ONLY:
            raise ValueError(chart_definition.evidence_contract.unsupported_reason or 'Chart does not support ticket evidence.')
        return chart_definition

    def _build_datasets(self, scope: JiraScopeConfig, buckets: List[BugTrendBucket], chart_definition: BugTrendChartDefinition) -> List[BugTrendDataset]:
        series_names = chart_definition.chart_spec.get('series', [])
        series_definitions = active_bug_trend_series(scope)
        allowed_names = set(series_names)
        series_definitions = [series for series in series_definitions if series.series_name in allowed_names]
        return [
            BugTrendDataset(series.series_name, series.chart_type, series.chart_values(buckets), series.color)
            for series in series_definitions
        ]

    def _format_bucket_label(self, bucket: BugTrendBucket) -> str:
        if bucket.granularity == JiraScopeConfig.GRANULARITY_WEEKLY:
            year, week, _ = bucket.bucket_start.isocalendar()
            return f'{str(year)[2:]}WW{week:02d}'
        return bucket.bucket_start.isoformat()

bug_trend_api = ApiForBugTrend()

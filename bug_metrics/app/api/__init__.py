from datetime import date
from typing import List, Optional

from bug_metrics.models import BugTrendBucket, BugTrendCalculationRun, BugTrendChartDefinition, JiraScopeConfig
from jira_history.container import jira_history_container

from .calculation import BugTrendCalculationService
from .chart_catalog import AiChartDraftRequest, ChartCatalogService, ChartDefinition, ChartPublishResult, ChartValidationResult, RendererRouteDecisionResult
from .chart_data import BUG_TREND_CONTRACT_VERSION, BugTrendChart, BugTrendDataset, BugTrendRunMetadata
from .data_health import BugTrendCalculationHealth, BugTrendCalculationHealthService
from .evidence_export import BugTrendEvidenceExport, BugTrendEvidenceExportService
from .page_query import (
    BugTrendChartListSyncResult,
    BugTrendEvidenceTicketResult,
    BugTrendPageQueryService,
    BugTrendPageQueryState,
    BugTrendTicketListFilters,
)
from .scope_audit import ScopeAudit, ScopeAuditService
from .scope_config import SavedScopeConfig, ScopeConfigService, ScopeConfigValidationResult
from .series import active_bug_trend_series


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

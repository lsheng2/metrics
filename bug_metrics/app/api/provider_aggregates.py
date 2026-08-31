from dataclasses import replace

from .hsdes_seed_facts import HsdesSeedFactRepository
from .provider_aggregate_common import (
    iso_date_value,
    provider_query_range_mode,
    provider_query_range_to_dates,
    ww_range_to_dates,
    ww_to_monday,
)
from .provider_aggregate_contracts import (
    DEFERRED_CHART_REASONS,
    PROVIDER_CHART_CONTRACT_VERSION,
    ProviderChartAggregateQuery,
    ProviderChartAggregateResult,
)
from .provider_aggregate_hsdes import HsdesAggregateRowsMixin
from .provider_aggregate_jira import JiraAggregateRowsMixin
from .provider_aggregate_results import ProviderAggregateResultsMixin
from .provider_aggregate_sources import ProviderAggregateSourceMixin
from .provider_facts import HsdesCanonicalFactAdapter, JiraCalculationRunFactAdapter
from .provider_profile_registry import ChartRecipeRequirement, ProjectProviderProfileRegistry
from provider_sync.app.api import ProviderSyncCacheService


class ProviderChartAggregateService(
    ProviderAggregateResultsMixin,
    ProviderAggregateSourceMixin,
    JiraAggregateRowsMixin,
    HsdesAggregateRowsMixin,
):
    def __init__(self, hsdes_seed_fact_repository=None, provider_sync_cache_service=None, profile_registry=None,
                 jira_fact_adapter=None, hsdes_fact_adapter=None):
        self._hsdes_seed_fact_repository = hsdes_seed_fact_repository or HsdesSeedFactRepository()
        self._provider_sync_cache_service = provider_sync_cache_service or ProviderSyncCacheService()
        self._profile_registry = profile_registry or ProjectProviderProfileRegistry.load_default()
        self._jira_fact_adapter = jira_fact_adapter or JiraCalculationRunFactAdapter()
        self._hsdes_fact_adapter = hsdes_fact_adapter or HsdesCanonicalFactAdapter()

    def get_aggregates(self, query: ProviderChartAggregateQuery) -> ProviderChartAggregateResult:
        query, profile_error = self._resolve_query_profile(query)
        if profile_error:
            return self._state_result(query, profile_error['status'], profile_error['reason'], self._empty_source_population(query))
        chart_support = self._resolve_chart_support(query)
        if chart_support.status != 'supported':
            return self._state_result(query, chart_support.status, self._chart_support_reason(query, chart_support), self._source_population_from_profile(query))
        begin, end = provider_query_range_to_dates(query)
        if query.provider_id == 'hsdes':
            return self._hsdes_aggregates(query, begin, end)
        if query.provider_id != 'jira':
            return self._state_result(query, 'unsupported', f'Provider {query.provider_id} is not supported by this aggregate service.', self._empty_source_population(query))
        return self._jira_aggregates(query, begin, end)

    def build_hsdes_quality_aggregate_artifact(self, query: ProviderChartAggregateQuery, facts: list[dict], freshness_status: str = 'materialized_from_normalized_hsdes_facts') -> ProviderChartAggregateResult:
        query, profile_error = self._resolve_query_profile(query)
        if profile_error:
            return self._state_result(query, profile_error['status'], profile_error['reason'], self._empty_source_population(query))
        begin, end = provider_query_range_to_dates(query)
        if query.provider_id != 'hsdes':
            return self._state_result(query, 'unsupported', 'Only HSD-ES quality aggregate artifact generation is supported by this path.', self._empty_source_population(query))
        chart_support = self._resolve_chart_support(query)
        if chart_support.status != 'supported':
            return self._state_result(query, chart_support.status, self._chart_support_reason(query, chart_support), self._hsdes_source_population(query))

        fact_snapshot_id = self._hsdes_fact_snapshot_id(query, facts)
        source_population = self._hsdes_source_population(query)
        source_population['fact_snapshot_id'] = fact_snapshot_id
        run_id = f'hsdes-{query.chart_id}-{self._range_identity(query, begin, end)}-{source_population["source_query_hash"][:12]}'
        rows = self._build_hsdes_rows(query, facts, begin, end, source_population, fact_snapshot_id, run_id)
        return ProviderChartAggregateResult(
            contract_version=PROVIDER_CHART_CONTRACT_VERSION,
            provider_id=query.provider_id,
            profile_id=query.profile_id,
            chart_id=query.chart_id,
            chart_version=query.chart_version,
            begin_ww=query.begin_ww,
            end_ww=query.end_ww,
            status='supported',
            reason='',
            fact_snapshot_id=fact_snapshot_id,
            source_population=source_population,
            scope_labels=self._scope_labels(query.profile_id),
            run_metadata={
                'calculation_run_id': run_id,
                'freshness_status': freshness_status,
                'source_coverage_start': begin.isoformat(),
                'source_coverage_end': end.isoformat(),
            },
            rows=rows,
            grafana_rows=self._grafana_rows(rows),
            range_mode=provider_query_range_mode(query),
            begin_date=begin.isoformat(),
            end_date=end.isoformat(),
        )

    def _hsdes_aggregates(self, query, begin, end):
        range_mode = provider_query_range_mode(query)
        cached_artifact = self._provider_sync_cache_service.cached_aggregate_artifact(
            query.provider_id,
            query.profile_id,
            query.chart_id,
            query.chart_version,
            query.begin_ww,
            query.end_ww,
            range_mode=range_mode,
            range_start=begin.isoformat() if range_mode == 'date' else '',
            range_end=end.isoformat() if range_mode == 'date' else '',
        )
        if cached_artifact.artifact:
            return self._aggregate_result_from_artifact(query, cached_artifact)
        live_snapshot = self._provider_sync_cache_service.latest_successful_snapshot(query.provider_id, query.profile_id)
        if live_snapshot:
            live_facts = self._provider_sync_cache_service.facts_for_snapshot(live_snapshot)
            return self.build_hsdes_quality_aggregate_artifact(query, live_facts, live_snapshot.freshness_status)
        seed_facts = self._hsdes_seed_fact_repository.facts_for_profile(query.profile_id)
        if seed_facts:
            return self.build_hsdes_quality_aggregate_artifact(query, seed_facts, 'materialized_from_seed_hsdes_facts')
        return self._state_result(query, 'configuration_required', 'HSD-ES quality facts require confirmed field bindings before aggregate generation.', self._hsdes_source_population(query))

    def _jira_aggregates(self, query, begin, end):
        scope = self._jira_scope_for_profile(query.profile_id)
        if scope is None:
            return self._state_result(query, 'unavailable', 'No enabled Jira scope is mapped to the requested provider profile.', self._jira_source_population_without_scope(query))
        run = self._latest_authoritative_run(scope, begin, end)
        if run is None:
            return self._jira_missing_run_result(query, scope, begin, end)
        expected_snapshot_id = self._fact_snapshot_id(scope, run)
        source_population = self._jira_source_population(query, scope, run)
        if query.fact_snapshot_id and query.fact_snapshot_id != expected_snapshot_id:
            return self._state_result(query, 'stale', 'Requested fact snapshot does not match the selected aggregate artifact.', source_population, self._run_metadata(scope, run, 'snapshot_mismatch'))
        rows = self._build_rows(query, scope, run, begin, end, expected_snapshot_id, source_population)
        return ProviderChartAggregateResult(
            contract_version=PROVIDER_CHART_CONTRACT_VERSION,
            provider_id=query.provider_id,
            profile_id=query.profile_id,
            chart_id=query.chart_id,
            chart_version=query.chart_version,
            begin_ww=query.begin_ww,
            end_ww=query.end_ww,
            status='supported',
            reason='',
            fact_snapshot_id=expected_snapshot_id,
            source_population=source_population,
            scope_labels=self._scope_labels(query.profile_id, scope),
            run_metadata=self._run_metadata(scope, run, 'fresh'),
            rows=rows,
            grafana_rows=self._grafana_rows(rows),
            range_mode=provider_query_range_mode(query),
            begin_date=begin.isoformat(),
            end_date=end.isoformat(),
        )

    def _jira_missing_run_result(self, query, scope, begin, end):
        stale_run = self._latest_stale_run(scope, begin, end)
        source_population = self._jira_source_population(query, scope, stale_run)
        if stale_run:
            return self._state_result(query, 'stale', 'Aggregate artifact does not match the current profile mapping or source query version.', source_population, self._run_metadata(scope, stale_run, 'stale_config'))
        return self._state_result(query, 'unavailable', 'No completed aggregate artifact covers the requested WW range for the current profile.', source_population)

    def _resolve_query_profile(self, query):
        resolution = self._profile_registry.resolve_profile(query.profile_id)
        if resolution.profile is None:
            reason = resolution.blockers[0]['message'] if resolution.blockers else f'Provider profile {query.profile_id} is not available.'
            return query, {'status': resolution.status, 'reason': reason}
        profile = resolution.profile
        if query.provider_id and query.provider_id != profile.provider_id:
            return query, {
                'status': 'unsupported',
                'reason': f'Provider {query.provider_id} does not match selected profile {query.profile_id}.',
            }
        if query.provider_id == profile.provider_id:
            return query, None
        return replace(query, provider_id=profile.provider_id), None

    def _resolve_chart_support(self, query):
        profile = self._profile_registry.get_profile(query.profile_id)
        binding = profile.chart_bindings.get(query.chart_id, {})
        recipe = ChartRecipeRequirement(
            chart_id=query.chart_id,
            chart_version=query.chart_version,
            required_canonical_fields=list(binding.get('required_canonical_fields', [])),
            provider_capability='quality_facts',
            evidence_capability='summary_only',
        )
        return self._profile_registry.resolve_chart_support(
            query.profile_id,
            recipe,
            self._provider_capabilities(query.provider_id),
        )

    def _provider_capabilities(self, provider_id):
        if provider_id == 'jira':
            return {'quality_facts': 'supported'}
        if provider_id == 'hsdes':
            return {'quality_facts': 'seeded_preview'}
        return {}

    def _chart_support_reason(self, query, chart_support):
        if chart_support.status == 'deferred' and query.chart_id in DEFERRED_CHART_REASONS:
            return DEFERRED_CHART_REASONS[query.chart_id]
        if chart_support.missing_canonical_fields:
            return f'Chart {query.chart_id} requires missing canonical field bindings: {", ".join(chart_support.missing_canonical_fields)}.'
        if chart_support.blockers:
            return chart_support.blockers[0]['message']
        return f'Chart {query.chart_id} is {chart_support.status} for provider profile {query.profile_id}.'

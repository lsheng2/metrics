import hashlib
from copy import deepcopy
from datetime import date, timedelta

from django.db.models import QuerySet

from bug_metrics.models import BugTrendBucket, BugTrendBucketIssue, BugTrendCalculationRun, JiraScopeConfig
from jira_history.models import JiraIssue

from .provider_aggregate_contracts import (
    DEFERRED_CHART_REASONS,
    FIRST_HSDES_CRITERIA_OPERATOR,
    FIRST_HSDES_CRITERIA_SNAPSHOT,
    FIRST_HSDES_EXCLUSION_SNAPSHOT,
    FIRST_HSDES_OBSERVED_RESULT_CONTRACT,
    FIRST_HSDES_PERMISSION_ASSUMPTIONS,
    FIRST_HSDES_PROFILE_ID,
    FIRST_HSDES_QUERY_ID,
    FIRST_HSDES_SOURCE_QUERY_NAME,
    FIRST_HSDES_SUBJECT,
    FIRST_HSDES_TENANT,
    FIRST_JIRA_PROFILE_ID,
    MAPPING_VERSION,
    PROVIDER_CHART_CONTRACT_VERSION,
    SOURCE_POPULATION_FIELDS,
    SUPPORTED_HSDES_SEED_CHARTS,
    SUPPORTED_JIRA_CHARTS,
    ProviderAggregateRow,
    ProviderChartAggregateQuery,
    ProviderChartAggregateResult,
    scope_label_dimensions,
    static_scope_labels_for_profile,
)
from .hsdes_seed_facts import HsdesSeedFactRepository
from .series import active_bug_trend_series
from provider_sync.app.api import ProviderSyncCacheService


AGING_BUCKET_LABELS = {
    'aging_0_7_days': '0-7 Days',
    'aging_8_14_days': '8-14 Days',
    'aging_15_30_days': '15-30 Days',
    'aging_31_plus_days': '31+ Days',
}


class ProviderChartAggregateService:
    def __init__(self, hsdes_seed_fact_repository=None, provider_sync_cache_service=None):
        self._hsdes_seed_fact_repository = hsdes_seed_fact_repository or HsdesSeedFactRepository()
        self._provider_sync_cache_service = provider_sync_cache_service or ProviderSyncCacheService()

    def get_aggregates(self, query: ProviderChartAggregateQuery) -> ProviderChartAggregateResult:
        begin, end = provider_query_range_to_dates(query)
        range_mode = provider_query_range_mode(query)
        if query.chart_id in DEFERRED_CHART_REASONS:
            source_population = self._hsdes_source_population(query) if query.provider_id == 'hsdes' else self._jira_source_population_without_scope(query)
            return self._state_result(query, 'deferred', DEFERRED_CHART_REASONS[query.chart_id], source_population)
        if query.provider_id == 'hsdes':
            if range_mode == 'ww':
                cached_artifact = self._provider_sync_cache_service.cached_aggregate_artifact(
                    query.provider_id,
                    query.profile_id,
                    query.chart_id,
                    query.chart_version,
                    query.begin_ww,
                    query.end_ww,
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
        if query.provider_id != 'jira':
            return self._state_result(query, 'unsupported', f'Provider {query.provider_id} is not supported by this aggregate service.', self._empty_source_population(query))
        if query.chart_id not in SUPPORTED_JIRA_CHARTS:
            return self._state_result(query, 'unsupported', f'Chart {query.chart_id} is not supported for Jira provider aggregates.', self._jira_source_population_without_scope(query))

        scope = self._jira_scope_for_profile(query.profile_id)
        if scope is None:
            return self._state_result(query, 'unavailable', 'No enabled Jira scope is mapped to the requested provider profile.', self._jira_source_population_without_scope(query))

        run = self._latest_authoritative_run(scope, begin, end)
        if run is None:
            stale_run = self._latest_stale_run(scope, begin, end)
            source_population = self._jira_source_population(query, scope, stale_run)
            if stale_run:
                return self._state_result(query, 'stale', 'Aggregate artifact does not match the current profile mapping or source query version.', source_population, self._run_metadata(scope, stale_run, 'stale_config'))
            return self._state_result(query, 'unavailable', 'No completed aggregate artifact covers the requested WW range for the current profile.', source_population)

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
            range_mode=range_mode,
            begin_date=begin.isoformat(),
            end_date=end.isoformat(),
        )

    def build_hsdes_quality_aggregate_artifact(self, query: ProviderChartAggregateQuery, facts: list[dict], freshness_status: str = 'materialized_from_normalized_hsdes_facts') -> ProviderChartAggregateResult:
        begin, end = provider_query_range_to_dates(query)
        if query.provider_id != 'hsdes':
            return self._state_result(query, 'unsupported', 'Only HSD-ES quality aggregate artifact generation is supported by this path.', self._empty_source_population(query))
        if query.chart_id in DEFERRED_CHART_REASONS:
            return self._state_result(query, 'deferred', DEFERRED_CHART_REASONS[query.chart_id], self._hsdes_source_population(query))
        if query.chart_id not in SUPPORTED_HSDES_SEED_CHARTS:
            return self._state_result(query, 'configuration_required', f'HSD-ES chart {query.chart_id} requires confirmed field bindings before aggregate artifact generation.', self._hsdes_source_population(query))

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

    def _build_hsdes_rows(self, query, facts, begin, end, source_population, fact_snapshot_id, calculation_run_id):
        if query.chart_id == 'component_bug':
            return self._hsdes_component_bug_rows(query, facts, begin, end, source_population, fact_snapshot_id, calculation_run_id)
        if query.chart_id == 'rolling_valid_bug':
            return self._hsdes_rolling_valid_bug_rows(query, facts, begin, end, source_population, fact_snapshot_id, calculation_run_id)
        if query.chart_id == 'open_bug_trend':
            return self._hsdes_open_bug_trend_rows(query, facts, begin, end, source_population, fact_snapshot_id, calculation_run_id)
        if query.chart_id == 'total_bug_trend':
            return self._hsdes_total_bug_trend_rows(query, facts, begin, end, source_population, fact_snapshot_id, calculation_run_id)
        if query.chart_id == 'open_bug_aging':
            return self._hsdes_open_bug_aging_rows(query, facts, begin, end, source_population, fact_snapshot_id, calculation_run_id)
        return self._hsdes_daily_new_standard_bug_rows(query, facts, begin, end, source_population, fact_snapshot_id, calculation_run_id)

    def _build_rows(self, query, scope, run, begin, end, fact_snapshot_id, source_population):
        if query.chart_id == 'component_bug':
            return self._component_bug_rows(query, scope, run, begin, end, fact_snapshot_id, source_population)
        if query.chart_id == 'rolling_valid_bug':
            return self._rolling_valid_bug_rows(query, scope, run, begin, end, fact_snapshot_id, source_population)
        if query.chart_id == 'open_bug_trend':
            return self._open_bug_trend_rows(query, scope, run, begin, end, fact_snapshot_id, source_population)
        if query.chart_id == 'total_bug_trend':
            return self._total_bug_trend_rows(query, scope, run, begin, end, fact_snapshot_id, source_population)
        if query.chart_id == 'open_bug_aging':
            return self._open_bug_aging_rows(query, scope, run, begin, end, fact_snapshot_id, source_population)
        return self._daily_new_standard_bug_rows(query, scope, run, begin, end, fact_snapshot_id, source_population)

    def _component_bug_rows(self, query, scope, run, begin, end, fact_snapshot_id, source_population):
        component_issue_keys = {}
        memberships = self._bucket_memberships(run, begin, end)
        for membership in memberships:
            component = membership.component_value or 'Unassigned'
            component_issue_keys.setdefault(component, set()).add(membership.issue_key)
        rows = []
        for component, issue_keys in sorted(component_issue_keys.items()):
            rows.append(self._row(query, scope, run, fact_snapshot_id, source_population, 'component_bug_count', 'range', begin, end, query.begin_ww, '', {'component': component}, 'component_bug_count', len(issue_keys)))
        return rows

    def _rolling_valid_bug_rows(self, query, scope, run, begin, end, fact_snapshot_id, source_population):
        rows = []
        buckets = list(self._buckets(run, begin, end))
        valid_counts = [bucket.new_critical_high_count + bucket.new_medium_low_count for bucket in buckets]
        for index, bucket in enumerate(buckets):
            window = valid_counts[max(0, index - 3):index + 1]
            rows.append(self._row(query, scope, run, fact_snapshot_id, source_population, 'rolling_valid_bug_count', bucket.granularity, bucket.bucket_start, bucket.bucket_end, self._ww_label(bucket.bucket_start), '', {}, 'rolling_valid_bug_count', sum(window) / len(window), str(bucket.id)))
        return rows

    def _open_bug_trend_rows(self, query, scope, run, begin, end, fact_snapshot_id, source_population):
        rows = []
        for bucket in self._buckets(run, begin, end):
            for series in active_bug_trend_series(scope):
                rows.append(self._row(query, scope, run, fact_snapshot_id, source_population, series.series_name, bucket.granularity, bucket.bucket_start, bucket.bucket_end, self._ww_label(bucket.bucket_start), '', {}, series.series_name, series.count_value(bucket) * series.chart_sign, str(bucket.id)))
        return rows

    def _total_bug_trend_rows(self, query, scope, run, begin, end, fact_snapshot_id, source_population):
        rows = []
        metric_fields = [
            ('total_new_bugs', lambda bucket: bucket.new_critical_high_count + bucket.new_medium_low_count),
            ('total_open_bugs', lambda bucket: bucket.open_count),
            ('total_fixed_or_closed_bugs', lambda bucket: bucket.fixed_or_closed_count),
        ]
        for bucket in self._buckets(run, begin, end):
            for metric_id, value_for_bucket in metric_fields:
                rows.append(self._row(query, scope, run, fact_snapshot_id, source_population, metric_id, bucket.granularity, bucket.bucket_start, bucket.bucket_end, self._ww_label(bucket.bucket_start), '', {}, metric_id, value_for_bucket(bucket), str(bucket.id)))
        return rows

    def _open_bug_aging_rows(self, query, scope, run, begin, end, fact_snapshot_id, source_population):
        buckets = list(self._buckets(run, begin, end))
        if not buckets:
            return []
        bucket = buckets[-1]
        aging_counts = {
            'aging_0_7_days': 0,
            'aging_8_14_days': 0,
            'aging_15_30_days': 0,
            'aging_31_plus_days': 0,
        }
        for membership in BugTrendBucketIssue.objects.filter(bucket=bucket, series_name='all_open_bugs'):
            if not membership.created_at:
                continue
            age_days = (bucket.bucket_end - membership.created_at.date()).days
            if age_days <= 7:
                aging_counts['aging_0_7_days'] += 1
            elif age_days <= 14:
                aging_counts['aging_8_14_days'] += 1
            elif age_days <= 30:
                aging_counts['aging_15_30_days'] += 1
            else:
                aging_counts['aging_31_plus_days'] += 1
        return [
            self._row(query, scope, run, fact_snapshot_id, source_population, metric_id, 'range', begin, end, query.begin_ww, '', {}, metric_id, value)
            for metric_id, value in aging_counts.items()
        ]

    def _daily_new_standard_bug_rows(self, query, scope, run, begin, end, fact_snapshot_id, source_population):
        rows = []
        issues = list(JiraIssue.objects.filter(scope=scope, is_in_current_scope=True))
        cursor = begin
        while cursor <= end:
            value = len([
                issue for issue in issues
                if self._is_bug(scope, issue) and issue.created_at and issue.created_at.date() == cursor
            ])
            rows.append(self._row(query, scope, run, fact_snapshot_id, source_population, 'daily_new_standard_bug_count', 'day', cursor, cursor, self._ww_label(cursor), cursor.isoformat(), {}, 'new_standard_bugs', value))
            cursor += timedelta(days=1)
        return rows

    def _hsdes_component_bug_rows(self, query, facts, begin, end, source_population, fact_snapshot_id, calculation_run_id):
        component_issue_ids = {}
        for fact in self._hsdes_bug_facts(facts):
            canonical_fields = fact.get('canonical_fields', {})
            created_at = self._date_from_iso(canonical_fields.get('created_at', ''))
            if created_at and not begin <= created_at <= end:
                continue
            component = canonical_fields.get('component_or_area') or 'Unassigned'
            component_issue_ids.setdefault(component, set()).add(fact.get('source_item_id', ''))
        return [
            self._hsdes_row(query, source_population, fact_snapshot_id, calculation_run_id, 'component_bug_count', 'range', begin, end, query.begin_ww, '', {'component': component}, 'component_bug_count', len(issue_ids))
            for component, issue_ids in sorted(component_issue_ids.items())
        ]

    def _hsdes_rolling_valid_bug_rows(self, query, facts, begin, end, source_population, fact_snapshot_id, calculation_run_id):
        rows = []
        previous_counts = []
        for bucket_start, bucket_end in self._week_ranges(begin, end):
            valid_count = self._hsdes_new_bug_count(facts, bucket_start, bucket_end)
            previous_counts.append(valid_count)
            rolling_window = previous_counts[max(0, len(previous_counts) - 4):]
            rows.append(self._hsdes_row(query, source_population, fact_snapshot_id, calculation_run_id, 'rolling_valid_bug_count', 'week', bucket_start, bucket_end, self._ww_label(bucket_start), '', {}, 'rolling_valid_bug_count', sum(rolling_window) / len(rolling_window), self._hsdes_bucket_id(query, 'rolling_valid_bug_count', bucket_start)))
        return rows

    def _hsdes_open_bug_trend_rows(self, query, facts, begin, end, source_population, fact_snapshot_id, calculation_run_id):
        rows = []
        for bucket_start, bucket_end in self._week_ranges(begin, end):
            rows.extend([
                self._hsdes_row(query, source_population, fact_snapshot_id, calculation_run_id, 'all_open_bugs', 'week', bucket_start, bucket_end, self._ww_label(bucket_start), '', {}, 'all_open_bugs', self._hsdes_open_bug_count(facts, bucket_end), self._hsdes_bucket_id(query, 'all_open_bugs', bucket_start)),
                self._hsdes_row(query, source_population, fact_snapshot_id, calculation_run_id, 'all_open_critical_high', 'week', bucket_start, bucket_end, self._ww_label(bucket_start), '', {}, 'all_open_critical_high', self._hsdes_open_bug_count(facts, bucket_end, critical_high=True), self._hsdes_bucket_id(query, 'all_open_critical_high', bucket_start)),
                self._hsdes_row(query, source_population, fact_snapshot_id, calculation_run_id, 'new_critical_high', 'week', bucket_start, bucket_end, self._ww_label(bucket_start), '', {}, 'new_critical_high', self._hsdes_new_bug_count(facts, bucket_start, bucket_end, critical_high=True), self._hsdes_bucket_id(query, 'new_critical_high', bucket_start)),
                self._hsdes_row(query, source_population, fact_snapshot_id, calculation_run_id, 'new_medium_low', 'week', bucket_start, bucket_end, self._ww_label(bucket_start), '', {}, 'new_medium_low', self._hsdes_new_bug_count(facts, bucket_start, bucket_end, medium_low=True), self._hsdes_bucket_id(query, 'new_medium_low', bucket_start)),
                self._hsdes_row(query, source_population, fact_snapshot_id, calculation_run_id, 'fixed_or_closed_bugs', 'week', bucket_start, bucket_end, self._ww_label(bucket_start), '', {}, 'fixed_or_closed_bugs', -self._hsdes_closed_bug_count(facts, bucket_start, bucket_end), self._hsdes_bucket_id(query, 'fixed_or_closed_bugs', bucket_start)),
            ])
        return rows

    def _hsdes_total_bug_trend_rows(self, query, facts, begin, end, source_population, fact_snapshot_id, calculation_run_id):
        rows = []
        for bucket_start, bucket_end in self._week_ranges(begin, end):
            rows.extend([
                self._hsdes_row(query, source_population, fact_snapshot_id, calculation_run_id, 'total_new_bugs', 'week', bucket_start, bucket_end, self._ww_label(bucket_start), '', {}, 'total_new_bugs', self._hsdes_new_bug_count(facts, bucket_start, bucket_end), self._hsdes_bucket_id(query, 'total_new_bugs', bucket_start)),
                self._hsdes_row(query, source_population, fact_snapshot_id, calculation_run_id, 'total_open_bugs', 'week', bucket_start, bucket_end, self._ww_label(bucket_start), '', {}, 'total_open_bugs', self._hsdes_open_bug_count(facts, bucket_end), self._hsdes_bucket_id(query, 'total_open_bugs', bucket_start)),
                self._hsdes_row(query, source_population, fact_snapshot_id, calculation_run_id, 'total_fixed_or_closed_bugs', 'week', bucket_start, bucket_end, self._ww_label(bucket_start), '', {}, 'total_fixed_or_closed_bugs', self._hsdes_closed_bug_count(facts, bucket_start, bucket_end), self._hsdes_bucket_id(query, 'total_fixed_or_closed_bugs', bucket_start)),
            ])
        return rows

    def _hsdes_open_bug_aging_rows(self, query, facts, begin, end, source_population, fact_snapshot_id, calculation_run_id):
        aging_counts = {
            'aging_0_7_days': 0,
            'aging_8_14_days': 0,
            'aging_15_30_days': 0,
            'aging_31_plus_days': 0,
        }
        for fact in self._hsdes_bug_facts(facts):
            canonical_fields = fact.get('canonical_fields', {})
            created_at = self._date_from_iso(canonical_fields.get('created_at', ''))
            if not created_at or not self._hsdes_is_open_at(fact, end):
                continue
            age_days = (end - created_at).days
            if age_days <= 7:
                aging_counts['aging_0_7_days'] += 1
            elif age_days <= 14:
                aging_counts['aging_8_14_days'] += 1
            elif age_days <= 30:
                aging_counts['aging_15_30_days'] += 1
            else:
                aging_counts['aging_31_plus_days'] += 1
        return [
            self._hsdes_row(query, source_population, fact_snapshot_id, calculation_run_id, metric_id, 'range', begin, end, query.begin_ww, '', {}, metric_id, value)
            for metric_id, value in aging_counts.items()
        ]

    def _hsdes_daily_new_standard_bug_rows(self, query, facts, begin, end, source_population, fact_snapshot_id, calculation_run_id):
        rows = []
        cursor = begin
        while cursor <= end:
            rows.append(self._hsdes_row(query, source_population, fact_snapshot_id, calculation_run_id, 'daily_new_standard_bug_count', 'day', cursor, cursor, self._ww_label(cursor), cursor.isoformat(), {}, 'new_standard_bugs', self._hsdes_new_bug_count(facts, cursor, cursor), self._hsdes_bucket_id(query, 'new_standard_bugs', cursor)))
            cursor += timedelta(days=1)
        return rows

    def _week_ranges(self, begin, end):
        bucket_start = begin
        while bucket_start <= end:
            bucket_end = min(bucket_start + timedelta(days=6), end)
            yield bucket_start, bucket_end
            bucket_start += timedelta(days=7)

    def _hsdes_bug_facts(self, facts):
        return [
            fact for fact in facts
            if fact.get('canonical_fields', {}).get('source_item_type') == 'bug'
        ]

    def _hsdes_new_bug_count(self, facts, begin, end, critical_high=False, medium_low=False):
        return len([
            fact for fact in self._hsdes_bug_facts(facts)
            if self._hsdes_created_between(fact, begin, end)
            and self._hsdes_matches_severity(fact, critical_high, medium_low)
        ])

    def _hsdes_open_bug_count(self, facts, bucket_end, critical_high=False):
        return len([
            fact for fact in self._hsdes_bug_facts(facts)
            if self._hsdes_is_open_at(fact, bucket_end)
            and self._hsdes_matches_severity(fact, critical_high, False)
        ])

    def _hsdes_closed_bug_count(self, facts, begin, end):
        return len([
            fact for fact in self._hsdes_bug_facts(facts)
            if self._hsdes_closed_between(fact, begin, end)
        ])

    def _hsdes_created_between(self, fact, begin, end):
        created_at = self._date_from_iso(fact.get('canonical_fields', {}).get('created_at', ''))
        return bool(created_at and begin <= created_at <= end)

    def _hsdes_closed_between(self, fact, begin, end):
        closed_at = self._hsdes_closed_at(fact)
        return bool(closed_at and begin <= closed_at <= end)

    def _hsdes_is_open_at(self, fact, bucket_end):
        created_at = self._date_from_iso(fact.get('canonical_fields', {}).get('created_at', ''))
        closed_at = self._hsdes_closed_at(fact)
        return bool(created_at and created_at <= bucket_end and (not closed_at or closed_at > bucket_end))

    def _hsdes_closed_at(self, fact):
        canonical_fields = fact.get('canonical_fields', {})
        return self._date_from_iso(canonical_fields.get('closed_at', '')) or self._date_from_iso(canonical_fields.get('resolved_at', ''))

    def _hsdes_matches_severity(self, fact, critical_high, medium_low):
        if not critical_high and not medium_low:
            return True
        severity = fact.get('canonical_fields', {}).get('severity_or_priority', '').lower()
        is_critical_high = any(token in severity for token in ['critical', 'high', 'p1', 'p2'])
        return is_critical_high if critical_high else not is_critical_high

    def _hsdes_bucket_id(self, query, metric_id, bucket_start):
        return f'{query.profile_id}:{query.chart_id}:{metric_id}:{bucket_start.isoformat()}'

    def _range_identity(self, query, begin, end):
        if provider_query_range_mode(query) == 'date':
            return f'{begin.isoformat()}-{end.isoformat()}'
        return f'{query.begin_ww}-{query.end_ww}'

    def _row(self, query, scope, run, fact_snapshot_id, source_population, metric_id, bucket_grain, bucket_start, bucket_end, bucket_ww, bucket_date, dimensions, series, value, bucket_id=''):
        merged_dimensions = scope_label_dimensions(self._scope_labels(query.profile_id, scope))
        merged_dimensions.update(dimensions)
        return ProviderAggregateRow(
            metric_id=metric_id,
            chart_id=query.chart_id,
            chart_version=query.chart_version,
            provider_id=query.provider_id,
            profile_id=query.profile_id,
            source_scope_ref=f'jira_scope:{scope.id}',
            begin_ww=query.begin_ww,
            end_ww=query.end_ww,
            bucket_grain=bucket_grain,
            bucket_start=bucket_start.isoformat(),
            bucket_end=bucket_end.isoformat(),
            bucket_ww=bucket_ww,
            bucket_date=bucket_date,
            dimensions=merged_dimensions,
            series=series,
            value=value,
            fact_snapshot_id=fact_snapshot_id,
            calculation_run_id=str(run.id),
            mapping_version=MAPPING_VERSION,
            mapping_version_hash=run.config_version_hash,
            source_query=source_population,
            bucket_id=bucket_id,
        )

    def _hsdes_row(self, query, source_population, fact_snapshot_id, calculation_run_id, metric_id, bucket_grain, bucket_start, bucket_end, bucket_ww, bucket_date, dimensions, series, value, bucket_id=''):
        merged_dimensions = scope_label_dimensions(self._scope_labels(query.profile_id))
        merged_dimensions.update(dimensions)
        return ProviderAggregateRow(
            metric_id=metric_id,
            chart_id=query.chart_id,
            chart_version=query.chart_version,
            provider_id=query.provider_id,
            profile_id=query.profile_id,
            source_scope_ref=f'hsdes_query:{source_population["source_query_ref"]}',
            begin_ww=query.begin_ww,
            end_ww=query.end_ww,
            bucket_grain=bucket_grain,
            bucket_start=bucket_start.isoformat(),
            bucket_end=bucket_end.isoformat(),
            bucket_ww=bucket_ww,
            bucket_date=bucket_date,
            dimensions=merged_dimensions,
            series=series,
            value=value,
            fact_snapshot_id=fact_snapshot_id,
            calculation_run_id=calculation_run_id,
            mapping_version=MAPPING_VERSION,
            mapping_version_hash=source_population['source_query_hash'],
            source_query=source_population,
            bucket_id=bucket_id,
        )

    def _grafana_rows(self, rows):
        grafana_rows = {}
        for aggregate_row in rows:
            if aggregate_row.chart_id == 'open_bug_aging':
                grafana_row = self._base_grafana_row(aggregate_row)
                grafana_row['age_bucket_label'] = AGING_BUCKET_LABELS.get(aggregate_row.series, aggregate_row.series)
                grafana_row['open_bug_count'] = aggregate_row.value
                grafana_rows[(
                    aggregate_row.calculation_run_id,
                    aggregate_row.bucket_start,
                    aggregate_row.bucket_end,
                    aggregate_row.bucket_grain,
                    aggregate_row.bucket_ww,
                    aggregate_row.bucket_date,
                    aggregate_row.series,
                    tuple(sorted(aggregate_row.dimensions.items())),
                )] = grafana_row
                continue
            row_key = (
                aggregate_row.calculation_run_id,
                aggregate_row.bucket_start,
                aggregate_row.bucket_end,
                aggregate_row.bucket_grain,
                aggregate_row.bucket_ww,
                aggregate_row.bucket_date,
                tuple(sorted(aggregate_row.dimensions.items())),
            )
            if row_key not in grafana_rows:
                grafana_rows[row_key] = self._base_grafana_row(aggregate_row)
            grafana_rows[row_key][aggregate_row.series] = aggregate_row.value
        return [deepcopy(row) for row in grafana_rows.values()]

    def _base_grafana_row(self, aggregate_row):
        grafana_row = {
            'provider_id': aggregate_row.provider_id,
            'profile_id': aggregate_row.profile_id,
            'source_scope_ref': aggregate_row.source_scope_ref,
            'chart_id': aggregate_row.chart_id,
            'chart_version': aggregate_row.chart_version,
            'calculation_run_id': aggregate_row.calculation_run_id,
            'fact_snapshot_id': aggregate_row.fact_snapshot_id,
            'bucket_id': aggregate_row.bucket_id,
            'bucket_label': aggregate_row.bucket_ww or aggregate_row.bucket_date,
            'bucket_start': aggregate_row.bucket_start,
            'bucket_end': aggregate_row.bucket_end,
            'bucket_granularity': aggregate_row.bucket_grain,
            'bucket_ww': aggregate_row.bucket_ww,
            'bucket_date': aggregate_row.bucket_date,
            'dimensions': aggregate_row.dimensions,
            'mapping_version': aggregate_row.mapping_version,
            'mapping_version_hash': aggregate_row.mapping_version_hash,
        }
        grafana_row.update(self._grafana_render_fields(aggregate_row.chart_id, aggregate_row.dimensions))
        return grafana_row

    def _grafana_render_fields(self, chart_id, dimensions):
        if chart_id == 'component_bug':
            return {'component_label': dimensions.get('component') or 'Unassigned'}
        return {}

    def _normalize_cached_grafana_rows(self, chart_id, rows):
        if chart_id == 'open_bug_aging':
            return self._normalize_cached_open_bug_aging_rows(rows)
        normalized_rows = []
        for row in rows:
            normalized_row = deepcopy(row)
            dimensions = normalized_row.get('dimensions', {})
            if isinstance(dimensions, dict):
                normalized_row.update(self._grafana_render_fields(chart_id, dimensions))
            normalized_rows.append(normalized_row)
        return normalized_rows

    def _normalize_cached_open_bug_aging_rows(self, rows):
        normalized_rows = []
        for row in rows:
            if 'age_bucket_label' in row and 'open_bug_count' in row:
                normalized_rows.append(deepcopy(row))
                continue
            for series, label in AGING_BUCKET_LABELS.items():
                normalized_row = deepcopy(row)
                for stale_series in AGING_BUCKET_LABELS:
                    normalized_row.pop(stale_series, None)
                normalized_row['age_bucket_label'] = label
                normalized_row['open_bug_count'] = row.get(series, 0)
                normalized_rows.append(normalized_row)
        return normalized_rows

    def _state_result(self, query, status, reason, source_population, run_metadata=None):
        begin, end = provider_query_range_to_dates(query)
        return ProviderChartAggregateResult(
            contract_version=PROVIDER_CHART_CONTRACT_VERSION,
            provider_id=query.provider_id,
            profile_id=query.profile_id,
            chart_id=query.chart_id,
            chart_version=query.chart_version,
            begin_ww=query.begin_ww,
            end_ww=query.end_ww,
            status=status,
            reason=reason,
            fact_snapshot_id='',
            source_population=source_population,
            scope_labels=self._scope_labels(query.profile_id),
            run_metadata=run_metadata or {},
            rows=[],
            grafana_rows=[],
            range_mode=provider_query_range_mode(query),
            begin_date=begin.isoformat(),
            end_date=end.isoformat(),
        )

    def _aggregate_result_from_artifact(self, query, cached_artifact):
        begin, end = ww_range_to_dates(query.begin_ww, query.end_ww)
        artifact = cached_artifact.artifact
        run_metadata = dict(artifact.run_metadata_json)
        run_metadata['freshness_status'] = cached_artifact.freshness_status
        run_metadata['cache_age_seconds'] = cached_artifact.cache_age_seconds
        run_metadata['cache_stale_reason'] = cached_artifact.reason
        return ProviderChartAggregateResult(
            contract_version=PROVIDER_CHART_CONTRACT_VERSION,
            provider_id=query.provider_id,
            profile_id=query.profile_id,
            chart_id=query.chart_id,
            chart_version=query.chart_version,
            begin_ww=query.begin_ww,
            end_ww=query.end_ww,
            status=artifact.status,
            reason=artifact.reason,
            fact_snapshot_id=str(artifact.snapshot_id),
            source_population=artifact.source_population_json,
            scope_labels=self._scope_labels(query.profile_id),
            run_metadata=run_metadata,
            rows=[],
            grafana_rows=self._normalize_cached_grafana_rows(query.chart_id, artifact.grafana_rows_json),
            range_mode='ww',
            begin_date=begin.isoformat(),
            end_date=end.isoformat(),
        )

    def _jira_scope_for_profile(self, profile_id):
        query = JiraScopeConfig.objects.filter(enabled=True)
        scope = query.filter(name=profile_id).first()
        if scope:
            return scope
        if profile_id == FIRST_JIRA_PROFILE_ID:
            return query.filter(jql='project = "131600" AND component = "team_int_qemu"').first()
        return query.filter(name__iexact=profile_id).first()

    def jira_scope_for_profile(self, profile_id):
        return self._jira_scope_for_profile(profile_id)

    def _latest_authoritative_run(self, scope, begin, end):
        return BugTrendCalculationRun.objects.filter(
            scope=scope,
            status=BugTrendCalculationRun.STATUS_COMPLETED,
            config_version_hash=scope.config_version_hash,
            source_coverage_start__lte=begin,
            source_coverage_end__gte=end,
        ).order_by('-completed_at').first()

    def _latest_stale_run(self, scope, begin, end):
        return BugTrendCalculationRun.objects.filter(
            scope=scope,
            status=BugTrendCalculationRun.STATUS_COMPLETED,
            source_coverage_start__lte=begin,
            source_coverage_end__gte=end,
        ).exclude(config_version_hash=scope.config_version_hash).order_by('-completed_at').first()

    def _buckets(self, run, begin, end) -> QuerySet[BugTrendBucket]:
        return run.buckets.filter(bucket_start__gte=begin, bucket_end__lte=end).order_by('bucket_start')

    def _bucket_memberships(self, run, begin, end):
        return BugTrendBucketIssue.objects.filter(
            calculation_run=run,
            bucket__bucket_start__gte=begin,
            bucket__bucket_end__lte=end,
        )

    def _is_bug(self, scope, issue):
        return not scope.bug_type_values or issue.issue_type in scope.bug_type_values

    def _scope_labels(self, profile_id, scope=None):
        fallback_dimensions = {}
        if scope:
            fallback_dimensions = {
                'ip': scope.ip,
                'project_or_product': scope.project_label or scope.name,
                'milestone': scope.milestone_field,
            }
        return static_scope_labels_for_profile(profile_id, fallback_dimensions)

    def _jira_source_population_without_scope(self, query):
        return self._source_population({
            'profile_id': query.profile_id,
            'provider_id': query.provider_id,
            'ownership_type': 'metrics_managed_native_query',
            'source_query_ref': '',
            'source_query_hash': '',
            'source_query_name': '',
            'native_query_text': '',
            'tenant_or_site': '',
            'subject_or_issue_type': 'jira_issue',
            'criteria_operator': 'JQL',
            'criteria_snapshot': '',
            'exclusion_snapshot': '',
            'permission_assumptions': 'configured Jira credentials can search the Metrics-managed JQL',
            'observed_result_contract': 'Jira issue search returns issue rows with stable key and updated fields.',
            'mapping_version': str(MAPPING_VERSION),
            'mapping_version_hash': '',
            'fact_snapshot_id': '',
        })

    def _jira_source_population(self, query, scope, run):
        source_query_hash = hashlib.sha256(scope.jql.encode('utf-8')).hexdigest()
        fact_snapshot_id = self._fact_snapshot_id(scope, run) if run else ''
        return self._source_population({
            'profile_id': query.profile_id,
            'provider_id': query.provider_id,
            'ownership_type': 'metrics_managed_native_query',
            'source_query_ref': f'jira_scope:{scope.id}',
            'source_query_hash': source_query_hash,
            'source_query_name': scope.name,
            'native_query_text': scope.jql,
            'tenant_or_site': '',
            'subject_or_issue_type': 'jira_issue',
            'criteria_operator': 'JQL',
            'criteria_snapshot': scope.jql,
            'exclusion_snapshot': '',
            'permission_assumptions': 'configured Jira credentials can search the Metrics-managed JQL',
            'observed_result_contract': 'Jira issue search returns issue rows with stable key and updated fields.',
            'mapping_version': str(MAPPING_VERSION),
            'mapping_version_hash': run.config_version_hash if run else scope.config_version_hash,
            'fact_snapshot_id': fact_snapshot_id,
        })

    def _hsdes_source_population(self, query):
        is_first_profile = query.profile_id == FIRST_HSDES_PROFILE_ID
        criteria_text = FIRST_HSDES_CRITERIA_SNAPSHOT if is_first_profile else ''
        exclusion_text = FIRST_HSDES_EXCLUSION_SNAPSHOT if is_first_profile else ''
        query_fingerprint = f'{criteria_text}|{exclusion_text}'
        return self._source_population({
            'profile_id': query.profile_id,
            'provider_id': query.provider_id,
            'ownership_type': 'provider_owned_saved_query',
            'source_query_ref': FIRST_HSDES_QUERY_ID if is_first_profile else '',
            'source_query_hash': hashlib.sha256(query_fingerprint.encode('utf-8')).hexdigest() if is_first_profile else '',
            'source_query_name': FIRST_HSDES_SOURCE_QUERY_NAME if is_first_profile else '',
            'native_query_text': '',
            'tenant_or_site': FIRST_HSDES_TENANT if is_first_profile else '',
            'subject_or_issue_type': FIRST_HSDES_SUBJECT if is_first_profile else '',
            'criteria_operator': FIRST_HSDES_CRITERIA_OPERATOR if is_first_profile else '',
            'criteria_snapshot': criteria_text,
            'exclusion_snapshot': exclusion_text,
            'permission_assumptions': FIRST_HSDES_PERMISSION_ASSUMPTIONS if is_first_profile else '',
            'observed_result_contract': FIRST_HSDES_OBSERVED_RESULT_CONTRACT if is_first_profile else '',
            'mapping_version': str(MAPPING_VERSION),
            'mapping_version_hash': '',
            'fact_snapshot_id': '',
        })

    def _empty_source_population(self, query):
        return self._source_population({
            'profile_id': query.profile_id,
            'provider_id': query.provider_id,
            'ownership_type': '',
            'source_query_ref': '',
            'source_query_hash': '',
            'source_query_name': '',
            'native_query_text': '',
            'tenant_or_site': '',
            'subject_or_issue_type': '',
            'criteria_operator': '',
            'criteria_snapshot': '',
            'exclusion_snapshot': '',
            'permission_assumptions': '',
            'observed_result_contract': '',
            'mapping_version': '',
            'mapping_version_hash': '',
            'fact_snapshot_id': '',
        })

    def _source_population(self, values):
        return {
            field_name: values.get(field_name, '')
            for field_name in SOURCE_POPULATION_FIELDS
        }

    def _fact_snapshot_id(self, scope, run):
        return f'jira-scope-{scope.id}-{run.config_version_hash[:12]}-{run.id}'

    def _hsdes_fact_snapshot_id(self, query, facts):
        payload = '|'.join(sorted(f'{fact.get("source_item_id", "")}:{fact.get("source_item_revision", "")}' for fact in facts))
        digest = hashlib.sha256(payload.encode('utf-8')).hexdigest()[:12]
        return f'hsdes-profile-{query.profile_id}-{digest}'

    def _date_from_iso(self, value):
        if not value:
            return None
        return date.fromisoformat(value[:10])

    def _run_metadata(self, scope, run, freshness_status):
        return {
            'calculation_run_id': str(run.id),
            'run_config_version_hash': run.config_version_hash,
            'current_config_version_hash': scope.config_version_hash,
            'freshness_status': freshness_status,
            'source_coverage_start': run.source_coverage_start.isoformat(),
            'source_coverage_end': run.source_coverage_end.isoformat(),
            'completed_at': run.completed_at.isoformat() if run.completed_at else '',
        }

    def _ww_label(self, bucket_start):
        year, week, _ = bucket_start.isocalendar()
        return f'{str(year)[2:]}WW{week:02d}'


def ww_range_to_dates(begin_ww: str, end_ww: str) -> tuple[date, date]:
    begin = ww_to_monday(begin_ww)
    end = ww_to_monday(end_ww) + timedelta(days=6)
    return begin, end


def provider_query_range_to_dates(query) -> tuple[date, date]:
    range_mode = provider_query_range_mode(query)
    if range_mode == 'date':
        begin = iso_date_value(query.begin_date, 'begin_date')
        end = iso_date_value(query.end_date, 'end_date')
        if begin > end:
            raise ValueError('begin_date must be earlier than or equal to end_date.')
        return begin, end
    if range_mode == 'ww':
        return ww_range_to_dates(query.begin_ww, query.end_ww)
    raise ValueError('range_mode must be ww or date.')


def provider_query_range_mode(query) -> str:
    return (query.range_mode or 'ww').strip().lower()


def iso_date_value(value: str, field_name: str) -> date:
    if not value:
        raise ValueError(f'{field_name} is required when range_mode=date.')
    return date.fromisoformat(value[:10])


def ww_to_monday(value: str) -> date:
    normalized = value.strip()
    if len(normalized) != 6 or normalized[2:4].upper() != 'WW':
        raise ValueError('WW values must use YYWWNN format.')
    year = 2000 + int(normalized[:2])
    week = int(normalized[4:])
    return date.fromisocalendar(year, week, 1)

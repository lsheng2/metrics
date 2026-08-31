from copy import deepcopy
from datetime import date

from .provider_aggregate_common import AGING_BUCKET_LABELS, provider_query_range_mode, provider_query_range_to_dates, ww_range_to_dates
from .provider_aggregate_contracts import (
    MAPPING_VERSION,
    PROVIDER_CHART_CONTRACT_VERSION,
    ProviderAggregateRow,
    ProviderChartAggregateResult,
    scope_label_dimensions,
    static_scope_labels_for_profile,
)


class ProviderAggregateResultsMixin:
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
                self._add_aging_row(grafana_rows, aggregate_row)
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

    def _add_aging_row(self, grafana_rows, aggregate_row):
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
        artifact = cached_artifact.artifact
        range_mode = artifact.range_mode or provider_query_range_mode(query)
        if range_mode == 'date':
            begin_date = artifact.range_start or query.begin_date
            end_date = artifact.range_end or query.end_date
        else:
            begin, end = ww_range_to_dates(artifact.begin_ww, artifact.end_ww)
            begin_date = artifact.range_start or begin.isoformat()
            end_date = artifact.range_end or end.isoformat()
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
            begin_ww=artifact.begin_ww,
            end_ww=artifact.end_ww,
            status=artifact.status,
            reason=artifact.reason,
            fact_snapshot_id=str(artifact.snapshot_id),
            source_population=artifact.source_population_json,
            scope_labels=self._scope_labels(query.profile_id),
            run_metadata=run_metadata,
            rows=[],
            grafana_rows=self._normalize_cached_grafana_rows(query.chart_id, artifact.grafana_rows_json),
            range_mode=range_mode,
            begin_date=begin_date,
            end_date=end_date,
        )

    def _scope_labels(self, profile_id, scope=None):
        fallback_dimensions = {}
        if scope:
            fallback_dimensions = {
                'ip': scope.ip,
                'project_or_product': scope.project_label or scope.name,
                'milestone': scope.milestone_field,
            }
        return static_scope_labels_for_profile(profile_id, fallback_dimensions)

    def _date_from_iso(self, value):
        if not value:
            return None
        return date.fromisoformat(value[:10])

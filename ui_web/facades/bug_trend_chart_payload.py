from ..data.bug_trend_data import BugTrendChartData


def chart_payload(chart_data: BugTrendChartData) -> dict:
    points = []
    for dataset in chart_data.datasets:
        for index, value in enumerate(dataset['values']):
            points.append({
                'calculation_run_id': chart_data.calculation_run_id,
                'bucket_id': bucket_value(chart_data.bucket_ids, index),
                'bucket_label': bucket_value(chart_data.labels, index),
                'bucket_start': bucket_value(chart_data.bucket_starts, index),
                'bucket_end': bucket_value(chart_data.bucket_ends, index),
                'bucket_granularity': chart_data.bucket_granularity,
                'series_name': dataset['series_name'],
                'series_label': series_label(dataset['series_name']),
                'label': bucket_value(chart_data.labels, index),
                'value': value,
                'type': dataset['type'],
                'color': dataset['color'],
            })
    return {
        'scope_id': chart_data.scope_id,
        'chart_id': chart_data.chart_id,
        'contract_version': chart_data.contract_version,
        'calculation_run_id': chart_data.calculation_run_id,
        'labels': chart_data.labels,
        'bucket_ids': chart_data.bucket_ids,
        'bucket_starts': chart_data.bucket_starts,
        'bucket_ends': chart_data.bucket_ends,
        'bucket_granularity': chart_data.bucket_granularity,
        'datasets': chart_data.datasets,
        'points': points,
        'grafana_rows': grafana_rows(chart_data),
        'unavailable_reason': chart_data.unavailable_reason,
        'run_metadata': chart_data.run_metadata or {},
        'current_evidence_available': chart_data.current_evidence_available,
    }


def grafana_rows(chart_data: BugTrendChartData) -> list[dict]:
    rows = []
    for index, bucket_id in enumerate(chart_data.bucket_ids):
        row = {
            'calculation_run_id': chart_data.calculation_run_id,
            'bucket_id': bucket_id,
            'bucket_label': bucket_value(chart_data.labels, index),
            'bucket_start': bucket_value(chart_data.bucket_starts, index),
            'bucket_end': bucket_value(chart_data.bucket_ends, index),
            'bucket_granularity': chart_data.bucket_granularity,
        }
        for dataset in chart_data.datasets:
            row[dataset['series_name']] = dataset['values'][index]
        rows.append(row)
    return rows


def bucket_value(values: list, index: int) -> str:
    return values[index] if values and index < len(values) else ''


def series_label(series_name: str) -> str:
    return series_name.replace('_', ' ').title()


def run_metadata_payload(run_metadata) -> dict:
    if not run_metadata:
        return {}
    return {
        'calculation_run_id': run_metadata.calculation_run_id,
        'run_config_version_hash': run_metadata.run_config_version_hash,
        'current_config_version_hash': run_metadata.current_config_version_hash,
        'freshness_status': run_metadata.freshness_status,
        'source_coverage_start': run_metadata.source_coverage_start,
        'source_coverage_end': run_metadata.source_coverage_end,
        'completed_at': run_metadata.completed_at,
    }

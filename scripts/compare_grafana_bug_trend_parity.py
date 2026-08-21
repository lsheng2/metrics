#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import parse_qsl, urlparse


def main() -> None:
    parser = argparse.ArgumentParser(description='Compare Bug Trend JSON API output with run-pinned Metrics chart data.')
    parser.add_argument('--calculation-run-id', required=True)
    parser.add_argument('--artifact', default='ops/grafana/bug_trend_dashboard.json')
    parser.add_argument('--begin', default='')
    parser.add_argument('--end', default='')
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'metrics.settings.production')

    import django
    django.setup()

    from django.test import Client
    from django.urls import reverse

    from bug_metrics.container import bug_metrics_container
    from bug_metrics.models import BugTrendCalculationRun

    artifact = json.loads((repo_root / args.artifact).read_text(encoding='utf-8'))
    chart_target = chart_target_from(artifact)
    chart_id = chart_id_from(chart_target)
    chart_definition = bug_metrics_container.bug_trend_api.get_chart_definition(chart_id)
    if chart_definition.evidence_contract.capability != 'bucket_series':
        print(f'FAIL {chart_id} must keep bucket_series evidence capability for Grafana parity')
        raise SystemExit(1)

    run = BugTrendCalculationRun.objects.select_related('scope').get(id=args.calculation_run_id)
    begin = date.fromisoformat(args.begin) if args.begin else run.source_coverage_start
    end = date.fromisoformat(args.end) if args.end else run.source_coverage_end
    expected_chart = bug_metrics_container.bug_trend_api.get_chart_for_run(str(run.id), begin, end, chart_id)
    expected_payload = {
        'scope_id': expected_chart.scope_id,
        'calculation_run_id': expected_chart.calculation_run_id,
        'labels': expected_chart.labels,
        'bucket_ids': expected_chart.bucket_ids,
        'datasets': [
            {
                'series_name': dataset.series_name,
                'type': dataset.chart_type,
                'values': dataset.values,
                'color': dataset.color,
            }
            for dataset in expected_chart.datasets
        ],
        'unavailable_reason': expected_chart.unavailable_reason,
    }
    response = Client().get(reverse('ui_web:bug_trend_chart_data_api'), {
        'scope_id': run.scope_id,
        'begin': begin.isoformat(),
        'end': end.isoformat(),
        'chart_id': chart_id,
    })
    if response.status_code != 200:
        print(f'FAIL chart API returned HTTP {response.status_code}')
        raise SystemExit(1)
    actual_payload = response.json()
    mismatches = compare_payloads(expected_payload, actual_payload)
    mismatches.extend(compare_artifact_contract(chart_target, artifact, actual_payload))
    for mismatch in mismatches:
        print(f'FAIL {mismatch}')
    if mismatches:
        raise SystemExit(1)
    print(f'PASS grafana bug trend parity run={run.id}')


def compare_payloads(expected, actual):
    mismatches = []
    for key in ('scope_id', 'calculation_run_id', 'labels', 'bucket_ids', 'datasets', 'unavailable_reason'):
        if actual.get(key) != expected.get(key):
            mismatches.append(f'{key}: expected {expected.get(key)!r}, found {actual.get(key)!r}')
    return mismatches


def chart_target_from(artifact):
    for panel in artifact.get('panels', []):
        for target in panel.get('targets', []):
            path = target.get('path') or target.get('url', '')
            if path.startswith('/api/bug-trend/chart-data/'):
                return target
    raise SystemExit('FAIL no approved chart-data target found in Grafana artifact')


def chart_id_from(chart_target):
    target_path = chart_target.get('path') or chart_target.get('url', '')
    params = dict(parse_qsl(urlparse(target_path).query, keep_blank_values=True))
    return params.get('chart_id') or 'default_bug_trend'


def compare_artifact_contract(chart_target, artifact, payload):
    mismatches = []
    target_path = chart_target.get('path') or chart_target.get('url', '')
    if urlparse(target_path).path != '/api/bug-trend/chart-data/':
        mismatches.append(f'artifact target path is not chart-data: {target_path}')
    target_params = {name for name, _ in parse_qsl(urlparse(target_path).query, keep_blank_values=True)}
    required_params = {'scope_id', 'begin', 'end'}
    allowed_params = required_params | {'chart_id'}
    if not required_params.issubset(target_params) or target_params - allowed_params:
        mismatches.append(f'artifact chart target params must include scope_id/begin/end and only approved optionals, found {sorted(target_params)}')

    points = payload.get('points', [])
    if not points:
        mismatches.append('chart payload has no Grafana point rows')
        return mismatches

    point_fields = set(points[0])
    contract = chart_target.get('metricsContract', {})
    contract_root = contract.get('root')
    if contract_root != 'points':
        mismatches.append(f'artifact metricsContract root must be points, found {contract_root!r}')
    column_fields = {column.get('selector') for column in chart_target.get('columns', []) if column.get('selector')}
    missing_column_fields = set(contract.get('requiredFields', [])) - column_fields
    if missing_column_fields:
        mismatches.append(f'artifact columns do not expose required fields: {sorted(missing_column_fields)}')
    link_field_refs = data_link_field_refs(artifact)
    missing_link_fields = link_field_refs - point_fields
    if missing_link_fields:
        mismatches.append(f'artifact data links reference fields missing from chart points: {sorted(missing_link_fields)}')
    contract_link_fields = set(contract.get('evidenceLinkFields', []))
    if link_field_refs != contract_link_fields:
        mismatches.append(f'artifact evidence link fields {sorted(link_field_refs)} do not match metricsContract {sorted(contract_link_fields)}')
    required_point_fields = set(contract.get('requiredFields', [])) or {'calculation_run_id', 'bucket_id', 'series_name', 'label', 'value'}
    missing_required_fields = required_point_fields - point_fields
    if missing_required_fields:
        mismatches.append(f'chart points missing required fields: {sorted(missing_required_fields)}')
    inconsistent_points = [point for point in points if set(point) != point_fields]
    if inconsistent_points:
        mismatches.append('chart point rows do not share a stable field shape')
    return mismatches


def data_link_field_refs(artifact):
    refs = set()
    for panel in artifact.get('panels', []):
        field_config = panel.get('fieldConfig', {})
        defaults = field_config.get('defaults', {})
        for link in defaults.get('links', []):
            refs.update(re.findall(r'\$\{__data\.fields\.([A-Za-z_][A-Za-z0-9_]*)\}', link.get('url', '')))
    return refs


if __name__ == '__main__':
    main()
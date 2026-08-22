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
    parser = argparse.ArgumentParser(description='Compare Bug Trend JSON API output with run-selected reference Metrics chart data.')
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
        'contract_version': expected_chart.contract_version,
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
    response = Client().get(reverse('ui_web:chart_data_api'), {
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
    for key in ('scope_id', 'contract_version', 'calculation_run_id', 'labels', 'bucket_ids', 'datasets', 'unavailable_reason'):
        if actual.get(key) != expected.get(key):
            mismatches.append(f'{key}: expected {expected.get(key)!r}, found {actual.get(key)!r}')
    return mismatches


def chart_target_from(artifact):
    for panel in artifact.get('panels', []):
        for target in panel.get('targets', []):
            path = target.get('path') or target.get('url', '')
            if path.startswith('/api/charts/data/'):
                return target
    raise SystemExit('FAIL no approved chart-data target found in Grafana artifact')


def chart_id_from(chart_target):
    target_path = chart_target.get('path') or chart_target.get('url', '')
    params = dict(parse_qsl(urlparse(target_path).query, keep_blank_values=True))
    chart_id = params.get('chart_id')
    if not chart_id:
        raise SystemExit('FAIL chart-data target must declare chart_id')
    return chart_id


def compare_artifact_contract(chart_target, artifact, payload):
    mismatches = []
    target_path = chart_target.get('path') or chart_target.get('url', '')
    if urlparse(target_path).path != '/api/charts/data/':
        mismatches.append(f'artifact target path is not chart-data: {target_path}')
    target_params = {name for name, _ in parse_qsl(urlparse(target_path).query, keep_blank_values=True)}
    required_params = {'scope_id', 'begin', 'end', 'chart_id'}
    allowed_params = required_params
    if not required_params.issubset(target_params) or target_params - allowed_params:
        mismatches.append(f'artifact chart target params must include scope_id/begin/end/chart_id and no extra params, found {sorted(target_params)}')

    grafana_rows = payload.get('grafana_rows', [])
    if not grafana_rows:
        mismatches.append('chart payload has no Grafana render rows')
        return mismatches

    row_fields = set(grafana_rows[0])
    contract = chart_target.get('metricsContract', {})
    if contract.get('chartId') != chart_id_from(chart_target):
        mismatches.append(f'artifact metricsContract chartId must match target chart_id, found {contract.get("chartId")!r}')
    if contract.get('contractVersion') != payload.get('contract_version'):
        mismatches.append(f'artifact contractVersion {contract.get("contractVersion")!r} does not match API contract_version {payload.get("contract_version")!r}')
    contract_root = contract.get('root')
    if contract_root != 'grafana_rows':
        mismatches.append(f'artifact metricsContract root must be grafana_rows, found {contract_root!r}')
    if contract.get('shape') != 'wide_bucket_series':
        mismatches.append(f'artifact metricsContract shape must be wide_bucket_series, found {contract.get("shape")!r}')
    expected_series = {dataset['series_name'] for dataset in payload.get('datasets', [])}
    contract_value_fields = set(contract.get('valueFields', []))
    if not contract_value_fields:
        mismatches.append('artifact metricsContract valueFields must not be empty')
    if contract_value_fields != expected_series:
        mismatches.append(f'artifact valueFields {sorted(contract_value_fields)} do not match chart datasets {sorted(expected_series)}')
    column_fields = {column.get('selector') for column in chart_target.get('columns', []) if column.get('selector')}
    required_fields = set(contract.get('requiredFields', [])) | contract_value_fields
    missing_column_fields = required_fields - column_fields
    if missing_column_fields:
        mismatches.append(f'artifact columns do not expose required fields: {sorted(missing_column_fields)}')
    link_field_refs = data_link_field_refs(artifact)
    missing_link_fields = link_field_refs - row_fields
    if missing_link_fields:
        mismatches.append(f'artifact data links reference fields missing from chart render rows: {sorted(missing_link_fields)}')
    contract_link_fields = set(contract.get('evidenceLinkFields', []))
    if not contract_link_fields.issubset(link_field_refs):
        mismatches.append(f'artifact evidence link fields {sorted(link_field_refs)} do not match metricsContract {sorted(contract_link_fields)}')
    if 'series=${__field.name}' not in ''.join(panel_link_urls(artifact)):
        mismatches.append('artifact data link must map wide series through series=${__field.name}')
    missing_required_fields = required_fields - row_fields
    if missing_required_fields:
        mismatches.append(f'chart render rows missing required fields: {sorted(missing_required_fields)}')
    inconsistent_rows = [row for row in grafana_rows if set(row) != row_fields]
    if inconsistent_rows:
        mismatches.append('chart render rows do not share a stable field shape')
    return mismatches


def panel_link_urls(artifact):
    urls = []
    for panel in artifact.get('panels', []):
        field_config = panel.get('fieldConfig', {})
        defaults = field_config.get('defaults', {})
        urls.extend(link.get('url', '') for link in defaults.get('links', []))
    return urls


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
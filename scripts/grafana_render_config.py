from __future__ import annotations

import json
import sys
import argparse
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from grafana_artifact_contract import Finding, GrafanaAllowlist, load_allowlist, validate_artifact
from grafana_render_config_contracts import REQUIRED_CHART_TARGET_FIELDS, REQUIRED_PANEL_FIELDS, REQUIRED_READINESS_TARGET_FIELDS, REQUIRED_ROOT_FIELDS


def load_render_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def write_generated_dashboard(render_config_path: Path, allowlist_path: Path, output_path: Path) -> dict[str, Any]:
    allowlist = load_allowlist(allowlist_path)
    dashboard = generate_dashboard(load_render_config(render_config_path), allowlist)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(dashboard, indent=2) + '\n', encoding='utf-8')
    return dashboard


def validate_generated_dashboard(output_path: Path, allowlist_path: Path) -> list[Finding]:
    return validate_artifact(output_path, load_allowlist(allowlist_path))


def validate_render_config(render_config: dict[str, Any], allowlist: GrafanaAllowlist, path: Path) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(validate_required_mapping_fields(path, 'root', render_config, REQUIRED_ROOT_FIELDS))
    variables = render_config.get('variables', [])
    range_controls = render_config.get('range_controls', {})
    sections = render_config.get('sections', [])
    if not isinstance(variables, list):
        findings.append(Finding(path, 'root variables must be a list'))
    if not isinstance(range_controls, dict):
        findings.append(Finding(path, 'root range_controls must be an object'))
    if not isinstance(sections, list):
        findings.append(Finding(path, 'root sections must be a list'))
        return findings
    for section_index, section in enumerate(sections):
        if not isinstance(section, dict):
            findings.append(Finding(path, f'sections[{section_index}] must be an object'))
            continue
        panels = section.get('panels', [])
        if not isinstance(panels, list):
            findings.append(Finding(path, f'sections[{section_index}].panels must be a list'))
            continue
        for panel_index, panel in enumerate(panels):
            if not isinstance(panel, dict):
                findings.append(Finding(path, f'sections[{section_index}].panels[{panel_index}] must be an object'))
                continue
            findings.extend(validate_render_panel(path, f'sections[{section_index}].panels[{panel_index}]', panel, allowlist))
    return findings


def generate_dashboard(render_config: dict[str, Any], allowlist: GrafanaAllowlist) -> dict[str, Any]:
    findings = validate_render_config(render_config, allowlist, Path(str(render_config.get('dashboard_uid', 'render_config'))))
    if findings:
        messages = '; '.join(finding.message for finding in findings)
        raise ValueError(messages)
    panels = []
    panels.extend(generate_top_panels(render_config))
    for section in render_config.get('sections', []):
        panels.append({
            'id': int(section.get('panel_id', len(panels) + 1)),
            'title': section['title'],
            'type': 'row',
            'gridPos': dict(section['layout']),
        })
        for panel in section.get('panels', []):
            panels.append(generate_panel(panel, allowlist))
    return {
        'uid': render_config['dashboard_uid'],
        'title': render_config['title'],
        'schemaVersion': int(render_config.get('schema_version', 39)),
        'version': int(render_config.get('version', 1)),
        'tags': list(render_config.get('tags', [])),
        'templating': {'list': [generate_variable(variable) for variable in render_config.get('variables', [])]},
        'panels': panels,
        'time': dict(render_config.get('time', {})),
        'timezone': render_config.get('timezone', 'browser'),
    }


def generate_top_panels(render_config: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        generate_panel(panel, None)
        for panel in render_config.get('top_panels', [])
    ]


def generate_variable(variable: dict[str, Any]) -> dict[str, Any]:
    values = list(variable.get('values', []))
    current_value = variable.get('current', values[0] if values else variable.get('query', ''))
    if variable.get('type') == 'textbox':
        return {
            'name': variable['name'],
            'type': 'textbox',
            'query': current_value,
            'current': {'text': current_value, 'value': current_value},
            'label': variable.get('label', variable['name']),
            'description': variable.get('description', ''),
        }
    options = [
        {'selected': value == current_value, 'text': variable.get('labels', {}).get(value, value), 'value': value}
        for value in values
    ]
    return {
        'name': variable['name'],
        'type': 'custom',
        'query': variable.get('query') or ','.join(values),
        'current': {'text': variable.get('labels', {}).get(current_value, current_value), 'value': current_value},
        'options': options,
        'label': variable.get('label', variable['name']),
        'description': variable.get('description', ''),
    }


def generate_panel(panel: dict[str, Any], allowlist: GrafanaAllowlist | None) -> dict[str, Any]:
    if panel.get('type') == 'text':
        return {
            'id': int(panel['panel_id']),
            'title': panel['title'],
            'type': 'text',
            'description': panel.get('description', ''),
            'gridPos': dict(panel['layout']),
            'options': {'content': panel.get('content', ''), 'mode': panel.get('mode', 'markdown')},
        }
    targets = panel.get('targets')
    if targets is None:
        targets = [panel]
    generated = {
        'id': int(panel['panel_id']),
        'title': panel['title'],
        'type': panel['type'],
        'description': panel.get('description', ''),
        'gridPos': dict(panel['layout']),
        'datasource': datasource(),
        'targets': [
            generate_target(index, target, allowlist)
            for index, target in enumerate(targets)
        ],
    }
    if panel.get('options'):
        generated['options'] = dict(panel['options'])
    if panel.get('field_config'):
        generated['fieldConfig'] = dict(panel['field_config'])
    elif any(target.get('evidence_link', {}).get('enabled') for target in targets):
        generated['fieldConfig'] = {
            'defaults': {
                'links': [{
                    'title': 'Open evidence',
                    'url': '/api/provider-charts/evidence/?profile_id=$profile_id&begin_ww=$begin_ww&end_ww=$end_ww&chart_id='
                           f'{targets[0]["chart_recipe_ref"]["chart_id"]}&run=${{__data.fields.calculation_run_id}}'
                           '&bucket=${__data.fields.bucket_id}&series=${__field.name}&range_mode=$range_mode'
                           '&begin_date=${__from:date:YYYY-MM-DD}&end_date=${__to:date:YYYY-MM-DD}',
                    'targetBlank': False,
                }]
            }
        }
    return generated


def generate_target(index: int, target: dict[str, Any], allowlist: GrafanaAllowlist | None) -> dict[str, Any]:
    if target.get('api_surface') == 'provider_profile_readiness':
        return generate_readiness_target(index, target)
    recipe_ref = target['chart_recipe_ref']
    chart_id = recipe_ref['chart_id']
    chart_version = int(recipe_ref.get('chart_version', 1))
    root = target['render_root']
    shape = target['render_shape']
    contract = {
        'chartId': chart_id,
        'contractVersion': '0.2',
        'root': root,
        'shape': shape,
        'requiredFields': list(target.get('required_fields', required_fields_for_shape(shape))),
        'semanticOwner': 'metrics',
        'chartRecipeId': chart_id,
        'chartRecipeVersion': chart_version,
        'providerBinding': target['provider_binding'],
        'evidenceCapability': target['evidence_capability'],
        'evidenceLinkFields': list(target.get('evidence_link', {}).get('fields', [])),
    }
    if root == 'grafana_rows':
        contract.update({
            'categoryField': target['category_field'],
            'valueFields': list(target['value_fields']),
            'seriesFieldSource': '__field.name',
            'calculationOwner': 'metrics',
            'aggregationOwner': 'materialized_aggregate',
        })
    if chart_id.startswith('daily_'):
        recipe = allowlist.provider_chart_recipes[chart_id]
        contract['calculationOwner'] = 'metrics'
        contract['aggregationOwner'] = 'materialized_aggregate'
        contract['bucketGrain'] = target.get('bucket_grain') or sorted(recipe.bucket_grains)[0]
    elif target.get('bucket_grain'):
        contract['bucketGrain'] = target['bucket_grain']
    return {
        'refId': chr(ord('A') + index),
        'datasource': datasource(),
        'type': 'json',
        'source': 'url',
        'parser': 'backend',
        'format': 'table',
        'url_options': {'method': 'GET'},
        'url': provider_chart_url(chart_id, chart_version),
        'root_selector': f'$.{root}',
        'columns': columns_for_target(target, contract),
        'metricsContract': contract,
    }


def generate_readiness_target(index: int, target: dict[str, Any]) -> dict[str, Any]:
    root = target['render_root']
    return {
        'refId': chr(ord('A') + index),
        'datasource': datasource(),
        'type': 'json',
        'source': 'url',
        'parser': 'backend',
        'format': 'table',
        'url_options': {'method': 'GET'},
        'url': '/api/provider-profiles/readiness/?profile_id=$profile_id&range_mode=$range_mode&begin_ww=$begin_ww&end_ww=$end_ww&begin_date=${__from:date:YYYY-MM-DD}&end_date=${__to:date:YYYY-MM-DD}',
        'root_selector': f'$.{root}',
        'columns': list(target.get('columns', [])),
        'metricsContract': {
            'contractVersion': '0.2',
            'root': root,
            'shape': target['render_shape'],
            'requiredFields': list(target.get('required_fields', [])),
            'evidenceCapability': target['evidence_capability'],
            'evidenceLinkFields': [],
            'semanticOwner': 'metrics',
        },
    }


def datasource() -> dict[str, str]:
    return {'type': 'yesoreyeram-infinity-datasource', 'uid': 'metrics-bug-trend-api'}


def provider_chart_url(chart_id: str, chart_version: int) -> str:
    return (
        f'/api/provider-charts/data/?profile_id=$profile_id&begin_ww=$begin_ww&end_ww=$end_ww'
        f'&chart_id={chart_id}&chart_version={chart_version}&range_mode=$range_mode'
        '&begin_date=${__from:date:YYYY-MM-DD}&end_date=${__to:date:YYYY-MM-DD}'
    )


def required_fields_for_shape(shape: str) -> list[str]:
    if shape == 'provider_series_state':
        return ['provider_id', 'profile_id', 'chart_id', 'status', 'reason', 'fact_snapshot_id']
    return ['provider_id', 'profile_id', 'calculation_run_id', 'fact_snapshot_id', 'bucket_id', 'bucket_label', 'bucket_start', 'bucket_end', 'bucket_granularity', 'mapping_version']


def columns_for_target(target: dict[str, Any], contract: dict[str, Any]) -> list[dict[str, str]]:
    if target.get('columns'):
        return list(target['columns'])
    if contract['shape'] == 'provider_series_state':
        return [
            {'selector': 'provider_id', 'text': 'Provider', 'type': 'string'},
            {'selector': 'profile_id', 'text': 'Profile', 'type': 'string'},
            {'selector': 'chart_id', 'text': 'Chart', 'type': 'string'},
            {'selector': 'status', 'text': 'Status', 'type': 'string'},
            {'selector': 'reason', 'text': 'Reason', 'type': 'string'},
            {'selector': 'fact_snapshot_id', 'text': 'Snapshot', 'type': 'string'},
        ]
    fields = list(contract['requiredFields']) + list(contract.get('valueFields', []))
    if contract.get('categoryField') and contract['categoryField'] not in fields:
        fields.append(contract['categoryField'])
    return [
        {'selector': field, 'text': field, 'type': 'number' if field in contract.get('valueFields', []) else 'string'}
        for field in fields
    ]


def validate_required_mapping_fields(path: Path, value_path: str, value: dict[str, Any], required_fields: frozenset[str]) -> list[Finding]:
    missing_fields = sorted(field for field in required_fields if field not in value)
    return [
        Finding(path, f'{value_path} {field} is required')
        for field in missing_fields
    ]


def validate_render_panel(path: Path, panel_path: str, panel: dict[str, Any], allowlist: GrafanaAllowlist) -> list[Finding]:
    if panel.get('type') == 'text':
        return validate_required_mapping_fields(path, panel_path, panel, frozenset({'panel_id', 'title', 'type', 'layout', 'content'}))
    if 'targets' in panel:
        findings = validate_required_mapping_fields(path, panel_path, panel, frozenset({'panel_id', 'title', 'type', 'layout', 'targets'}))
        targets = panel.get('targets', [])
        if not isinstance(targets, list):
            return findings + [Finding(path, f'{panel_path}.targets must be a list')]
        for target_index, target in enumerate(targets):
            if not isinstance(target, dict):
                findings.append(Finding(path, f'{panel_path}.targets[{target_index}] must be an object'))
                continue
            findings.extend(validate_render_panel_target(path, f'{panel_path}.targets[{target_index}]', target, allowlist))
        return findings
    return validate_render_panel_target(path, panel_path, panel, allowlist)


def validate_render_panel_target(path: Path, panel_path: str, panel: dict[str, Any], allowlist: GrafanaAllowlist) -> list[Finding]:
    if panel.get('api_surface') == 'provider_profile_readiness':
        return validate_readiness_target(path, panel_path, panel, allowlist)
    required_fields = REQUIRED_CHART_TARGET_FIELDS if 'panel_id' not in panel else REQUIRED_PANEL_FIELDS
    findings = validate_required_mapping_fields(path, panel_path, panel, required_fields)
    recipe_ref = panel.get('chart_recipe_ref')
    if not isinstance(recipe_ref, dict):
        findings.append(Finding(path, f'{panel_path} chart_recipe_ref is required'))
        return findings
    chart_id = str(recipe_ref.get('chart_id', ''))
    recipe = allowlist.provider_chart_recipes.get(chart_id)
    if recipe is None:
        findings.append(Finding(path, f'{panel_path} chart_recipe_ref {chart_id!r} is not an approved Metrics chart recipe'))
        return findings
    if int(recipe_ref.get('chart_version', 0) or 0) != recipe.version:
        findings.append(Finding(path, f'{panel_path} chart_recipe_ref version must be {recipe.version}'))
    if panel.get('provider_binding') not in recipe.approved_provider_bindings:
        findings.append(Finding(path, f'{panel_path} provider_binding {panel.get("provider_binding")!r} is not approved for chart recipe {chart_id}'))
    if panel.get('render_root') not in recipe.approved_render_roots:
        findings.append(Finding(path, f'{panel_path} render_root {panel.get("render_root")!r} is not approved for chart recipe {chart_id}'))
    if panel.get('render_shape') not in recipe.approved_render_shapes:
        findings.append(Finding(path, f'{panel_path} render_shape {panel.get("render_shape")!r} is not approved for chart recipe {chart_id}'))
    category_field = panel.get('category_field')
    if recipe.approved_category_fields and category_field not in recipe.approved_category_fields:
        findings.append(Finding(path, f'{panel_path} category_field {category_field!r} is not approved for chart recipe {chart_id}'))
    value_fields = set(panel.get('value_fields', []))
    extra_value_fields = value_fields - recipe.approved_value_fields
    if extra_value_fields:
        findings.append(Finding(path, f'{panel_path} value_fields outside approved chart recipe {chart_id}: {", ".join(sorted(extra_value_fields))}'))
    evidence_capability = panel.get('evidence_capability')
    if evidence_capability not in recipe.approved_evidence_capabilities:
        findings.append(Finding(path, f'{panel_path} evidence_capability {evidence_capability!r} is not approved for chart recipe {chart_id}'))
    return findings


def validate_readiness_target(path: Path, target_path: str, target: dict[str, Any], allowlist: GrafanaAllowlist) -> list[Finding]:
    findings = validate_required_mapping_fields(path, target_path, target, REQUIRED_READINESS_TARGET_FIELDS)
    surface = allowlist.api_surfaces.get('/api/provider-profiles/readiness/')
    if surface is None:
        return findings + [Finding(path, f'{target_path} readiness surface is not approved')]
    if target.get('render_root') not in surface.approved_render_roots:
        findings.append(Finding(path, f'{target_path} render_root {target.get("render_root")!r} is not approved for readiness surface'))
    if target.get('render_shape') not in surface.approved_render_shapes:
        findings.append(Finding(path, f'{target_path} render_shape {target.get("render_shape")!r} is not approved for readiness surface'))
    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description='Generate a Grafana dashboard from a Metrics render config.')
    parser.add_argument('--render-config', required=True)
    parser.add_argument('--allowlist', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output_path = Path(args.output)
    write_generated_dashboard(Path(args.render_config), Path(args.allowlist), output_path)
    findings = validate_generated_dashboard(output_path, Path(args.allowlist))
    for finding in findings:
        print(f'FAIL {finding.path}: {finding.message}')
    if findings:
        raise SystemExit(1)
    print(f'PASS generated Grafana dashboard: {output_path}')


if __name__ == '__main__':
    main()

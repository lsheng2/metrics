from __future__ import annotations

from typing import Any


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
        column_for_field(field, contract)
        for field in fields
    ]


def column_for_field(field: str, contract: dict[str, Any]) -> dict[str, str]:
    if field in contract.get('valueFields', []):
        return {'selector': field, 'text': field, 'type': 'number'}
    if contract.get('shape') == 'wide_bucket_series' and field == 'bucket_start':
        return {'selector': field, 'text': field, 'type': 'timestamp', 'timestampFormat': '2006-01-02'}
    return {'selector': field, 'text': field, 'type': 'string'}

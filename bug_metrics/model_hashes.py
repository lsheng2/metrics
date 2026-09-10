import hashlib
import json

from bug_metrics.provider_profile_security import without_profile_secret_values


SCOPE_SEMANTIC_LIST_FIELD_NAMES = (
    'bug_type_values',
    'open_status_values',
    'fixed_status_values',
    'closed_status_values',
    'terminal_excluded_status_values',
    'fixed_resolution_values',
    'closed_resolution_values',
    'reopen_status_values',
    'critical_high_values',
    'medium_low_values',
    'display_fields',
)


def normalize_scope_list_values(value):
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = [value]
    else:
        raw_items = list(value)
    normalized = []
    for raw_item in raw_items:
        if raw_item is None:
            continue
        raw_text = str(raw_item).replace('\\r\\n', '\n').replace('\\n', '\n').replace('\\r', '\n')
        for item in raw_text.replace('\r\n', '\n').replace('\r', '\n').replace(',', '\n').split('\n'):
            text = item.strip()
            if text and text not in normalized:
                normalized.append(text)
    return normalized


def scope_config_version_hash(scope) -> str:
    payload = {
        'jql': scope.jql,
        'bug_type_values': normalize_scope_list_values(scope.bug_type_values),
        'open_status_values': normalize_scope_list_values(scope.open_status_values),
        'fixed_status_values': normalize_scope_list_values(scope.fixed_status_values),
        'closed_status_values': normalize_scope_list_values(scope.closed_status_values),
        'terminal_excluded_status_values': normalize_scope_list_values(scope.terminal_excluded_status_values),
        'fixed_resolution_values': normalize_scope_list_values(scope.fixed_resolution_values),
        'closed_resolution_values': normalize_scope_list_values(scope.closed_resolution_values),
        'reopen_status_values': normalize_scope_list_values(scope.reopen_status_values),
        'severity_field': scope.severity_field,
        'critical_high_values': normalize_scope_list_values(scope.critical_high_values),
        'medium_low_values': normalize_scope_list_values(scope.medium_low_values),
        'component_field': scope.component_field,
        'owner_field': scope.owner_field,
        'team_field': scope.team_field,
        'milestone_field': scope.milestone_field,
        'fix_version_field': scope.fix_version_field,
        'package_version_field': scope.package_version_field,
        'display_fields': normalize_scope_list_values(scope.display_fields),
        'timezone': scope.timezone,
        'bucket_granularity': scope.bucket_granularity,
    }
    return stable_json_hash(payload)


def provider_mapping_version_hash(profile) -> str:
    payload = {
        'profile_id': profile.profile_id,
        'provider_id': profile.provider_id,
        'display_name': profile.display_name,
        'source_population': profile.source_population,
        'connection_settings': without_profile_secret_values(profile.connection_settings),
        'scope_labels': profile.scope_labels,
        'field_bindings': profile.field_bindings,
        'value_mappings': profile.value_mappings,
        'chart_bindings': profile.chart_bindings,
        'sync_policy': profile.sync_policy,
        'readiness_policy': profile.readiness_policy,
        'mapping_version': profile.mapping_version,
    }
    return stable_json_hash(payload)


def provider_source_version_hash(profile) -> str:
    payload = {
        'provider_id': profile.provider_id,
        'connection_settings': without_profile_secret_values(profile.connection_settings),
        'source_population': profile.source_population,
    }
    return stable_json_hash(payload)


def stable_json_hash(payload: dict) -> str:
    encoded_payload = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(encoded_payload.encode('utf-8')).hexdigest()

import hashlib
import json

from django.db import migrations


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


def normalize_existing_scope_semantic_lists(apps, schema_editor):
    scope_model = apps.get_model('bug_metrics', 'JiraScopeConfig')
    for scope in scope_model.objects.all():
        changed_fields = []
        for field_name in SCOPE_SEMANTIC_LIST_FIELD_NAMES:
            current_value = getattr(scope, field_name)
            normalized_value = normalize_scope_list_values(current_value)
            if current_value != normalized_value:
                setattr(scope, field_name, normalized_value)
                changed_fields.append(field_name)
        if changed_fields:
            scope.config_version_hash = calculate_config_version_hash(scope)
            scope.save(update_fields=changed_fields + ['config_version_hash', 'updated_at'])


def calculate_config_version_hash(scope) -> str:
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
    encoded_payload = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(encoded_payload.encode('utf-8')).hexdigest()


class Migration(migrations.Migration):

    dependencies = [
        ('bug_metrics', '0010_normalize_scope_semantic_lists'),
    ]

    operations = [
        migrations.RunPython(normalize_existing_scope_semantic_lists, migrations.RunPython.noop),
    ]
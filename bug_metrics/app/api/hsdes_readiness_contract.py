from .provider_aggregate_contracts import FIRST_HSDES_SUBJECT, FIRST_HSDES_TENANT


FIRST_HSDES_EXPECTED_FIELD_SET = frozenset({
    'id',
    'rev',
    'fieldValues',
    'HSD_type',
    'status',
    'reason',
    'priority',
    'exposure',
    'component',
    'release',
    'release_affected',
    'target_MS',
    'owner',
    'submitted_by',
    'submitted_date',
    'updated_date',
    'implemented_date',
    'closed_date',
    'team_found',
    'pss_escape',
    'days_open',
})


def hsdes_api_contract() -> dict:
    return {
        'identity_fields': {
            'article_id': 'id',
            'revision': 'rev',
            'tenant': FIRST_HSDES_TENANT,
            'subject': FIRST_HSDES_SUBJECT,
        },
        'detail': {
            'endpoint': '/rest/article/{id}',
            'status': 'docs_confirmed_pending_runtime_validation',
        },
        'search': {
            'endpoint': '/rest/query/execution/eql',
            'query_language': 'EQL',
            'status': 'docs_confirmed_pending_runtime_validation',
        },
        'pagination': {
            'offset_parameter': 'start_at',
            'limit_parameter': 'max_results',
            'status': 'docs_confirmed_pending_runtime_validation',
        },
        'payload': {
            'field_values': 'fieldValues',
            'expected_field_set': sorted(FIRST_HSDES_EXPECTED_FIELD_SET),
            'status': 'docs_confirmed_pending_runtime_validation',
        },
        'lookups': {
            'static_lookup_hint': 'schema/lookupvalue?lookup_group=...',
            'status': 'requires_runtime_validation',
        },
        'relations': {
            'links': '/rest/article/{id}/links',
            'children': '/rest/article/{id}/children',
            'comments': 'comments-as-articles',
            'status': 'requires_runtime_validation',
        },
        'permissions': {
            'status': 'requires_runtime_validation',
        },
    }

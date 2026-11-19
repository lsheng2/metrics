ID_SCHEMA = {'type': 'string', 'pattern': '^[A-Za-z0-9._:-]{1,160}$'}
CATALOG_SCHEMA = {
    'type': 'object', 'properties': {'profile_id': ID_SCHEMA}, 'additionalProperties': False,
}
WORKFLOW_SCHEMA = {
    'type': 'object',
    'properties': {
        'profile_id': ID_SCHEMA,
        'chart_id': ID_SCHEMA,
        'requested_series': {'type': 'array', 'items': ID_SCHEMA, 'minItems': 1, 'maxItems': 32, 'uniqueItems': True},
        'range_mode': {'type': 'string', 'enum': ['date', 'ww']},
        'range_start': {'type': 'string', 'minLength': 1, 'maxLength': 32},
        'range_end': {'type': 'string', 'minLength': 1, 'maxLength': 32},
        'visualization': {'type': 'string', 'enum': ['timeseries', 'barchart', 'table', 'stat']},
        'panel_title': {'type': 'string', 'maxLength': 200},
        'render_config': {'type': 'object'},
    },
    'required': ['profile_id', 'chart_id', 'requested_series', 'range_mode', 'range_start', 'range_end'],
    'additionalProperties': False,
}
RESULT_SCHEMA = {
    'type': 'object',
    'properties': {
        'status': {'type': 'string', 'enum': [
            'catalog', 'scope_required', 'binding_unresolved', 'validation_failed',
            'needs_metric_recipe', 'draft_validated', 'published', 'failed',
        ]},
    },
    'required': ['status'],
    'additionalProperties': True,
}

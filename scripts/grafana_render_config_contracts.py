REQUIRED_ROOT_FIELDS = frozenset({
    'dashboard_uid',
    'title',
    'profile_variable',
    'variables',
    'range_controls',
    'sections',
})

REQUIRED_PANEL_FIELDS = frozenset({
    'panel_id',
    'title',
    'type',
    'layout',
    'chart_recipe_ref',
    'provider_binding',
    'render_root',
    'render_shape',
    'category_field',
    'value_fields',
    'evidence_capability',
})

REQUIRED_CHART_TARGET_FIELDS = frozenset({
    'chart_recipe_ref',
    'provider_binding',
    'render_root',
    'render_shape',
    'category_field',
    'value_fields',
    'evidence_capability',
})

REQUIRED_READINESS_TARGET_FIELDS = frozenset({
    'api_surface',
    'render_root',
    'render_shape',
    'evidence_capability',
})

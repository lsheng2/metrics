SCENARIOS = {
    'single': ('scripts.validation.project_full_stack_settings', 'scripts.validation.project_full_stack_fixture'),
    'full-week': ('scripts.validation.project_week_settings', 'scripts.validation.project_week_fixture'),
}


def settings_for(name):
    return definition(name)[0]


def fixture_for(name):
    return definition(name)[1]


def definition(name):
    if type(name) is not str or name not in SCENARIOS:
        raise ValueError('Unrecognized qualification scenario.')
    return SCENARIOS[name]


def validate_scenario(manifest, vector):
    name = manifest.get('scenario', 'single')
    definition(name)
    if name == 'single':
        if vector.get('schema_version') != 1 or 'cases' in vector:
            raise ValueError('Legacy scenario cannot select a week vector.')
        return name
    try:
        cases = vector['cases']
        if (vector['schema_version'] != 2 or not isinstance(cases, list) or len(cases) != 3
                or [case['input_template']['binding']['stable_id'] for case in cases] != ['101', '102', '103']):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise ValueError('Full-week scenario requires its exact three-vector fixture.') from None
    return name

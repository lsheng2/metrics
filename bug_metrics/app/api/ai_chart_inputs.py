import re
from urllib.parse import parse_qs, urlsplit


IDENTIFIER = re.compile(r'[A-Za-z0-9._:-]{1,160}')
_FORBIDDEN_KEYS = frozenset({
    'actor', 'approvalid', 'approval', 'proofid', 'dryrunproofid', 'workspacekey',
    'toolcallid', 'authorization', 'sql',
})
_SENSITIVE_FRAGMENTS = (
    'password', 'token', 'secret', 'apikey', 'privatepath', 'nativequery', 'rawquery',
)


def unsafe_draft_findings(value, path='render_config'):
    findings = []
    if isinstance(value, dict):
        for key, item in value.items():
            compact = ''.join(char for char in str(key).lower() if char.isalnum())
            field = f'{path}.{key}'
            if compact in _FORBIDDEN_KEYS or any(part in compact for part in _SENSITIVE_FRAGMENTS):
                findings.append(finding('unsafe_draft', field, 'Draft contains a reserved or sensitive field.'))
            else:
                findings.extend(unsafe_draft_findings(item, field))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            findings.extend(unsafe_draft_findings(item, f'{path}[{index}]'))
    return findings


def request_findings(request):
    findings = []
    for field in ('profile_id', 'chart_id'):
        value = getattr(request, field)
        if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
            findings.append(finding('invalid_input', field, 'A valid identifier is required.'))
    if (not isinstance(request.requested_series, (list, tuple)) or not request.requested_series
            or any(not isinstance(item, str) or not IDENTIFIER.fullmatch(item) for item in request.requested_series)):
        findings.append(finding('invalid_input', 'requested_series', 'Select valid series identifiers.'))
    if request.range_mode not in ('date', 'ww'):
        findings.append(finding('invalid_input', 'range_mode', 'Select date or work-week bounds.'))
    for field in ('range_start', 'range_end'):
        value = getattr(request, field)
        if not isinstance(value, str) or len(value) > 32:
            findings.append(finding('invalid_input', field, 'A bounded date or work-week value is required.'))
    if request.render_config is not None and not isinstance(request.render_config, dict):
        findings.append(finding('invalid_input', 'render_config', 'Render config must be an object.'))
    findings.extend(unsafe_draft_findings(request.render_config))
    return findings


def finding(code, field, message):
    return {'code': code, 'field': field, 'message': message, 'severity': 'error'}


def draft_crosses_boundary(draft, *, profile_id, provider_id, scope_id=None):
    if not isinstance(draft, dict):
        return False
    expected = {'profileid': profile_id, 'providerid': provider_id, 'scopeid': scope_id}
    variables = {key: set() for key in expected}
    draft_variables = draft.get('variables', [])
    if draft_variables is None:
        return True
    if not isinstance(draft_variables, (list, tuple)):
        return True
    for variable in draft_variables:
        if not isinstance(variable, dict):
            return True
        name = variable.get('name')
        key = ''.join(char for char in str(name).lower() if char.isalnum())
        if variable.get('kind') == 'profile' or name == draft.get('profile_variable'):
            key = 'profileid'
        if key not in expected:
            continue
        values, current = variable.get('values'), variable.get('current')
        if values != [expected[key]] or current != expected[key]:
            return True
        variables[key].update((f'${name}', f'${{{name}}}'))

    def matches(key, value):
        if isinstance(value, (list, tuple)):
            return bool(value) and all(matches(key, item) for item in value)
        if not isinstance(value, str):
            return False
        return (expected[key] is not None and str(value) == str(expected[key])) or value in variables[key]

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                normalized = ''.join(char for char in str(key).lower() if char.isalnum())
                if normalized in expected and not matches(normalized, item):
                    return True
                if normalized in {'url', 'href'} and isinstance(item, str):
                    try:
                        query = urlsplit(item).query
                    except ValueError:
                        return True
                    for parameter, entries in parse_qs(query).items():
                        parameter = parameter.replace('_', '').lower()
                        if parameter in expected and not matches(parameter, entries):
                            return True
                if walk(item):
                    return True
        elif isinstance(value, (list, tuple)):
            return any(walk(item) for item in value)
        return False

    return walk(draft)

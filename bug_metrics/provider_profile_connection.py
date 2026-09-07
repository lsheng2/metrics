from typing import Any


def profile_connection_value(connection_settings: dict[str, Any], key: str, default):
    value = dict(connection_settings or {}).get(key)
    return _runtime_value(value, default)


def profile_credential_value(connection_settings: dict[str, Any], key: str, default):
    settings = dict(connection_settings or {})
    credentials = dict(settings.get('credentials') or {})
    value = credentials.get(key)
    if value in {None, ''}:
        value = settings.get(key)
    return _runtime_value(value, default)


def first_profile_credential_value(connection_settings: dict[str, Any], keys: list[str], default):
    for key in keys:
        value = profile_credential_value(connection_settings, key, '')
        if value not in {None, ''}:
            return value
    return default


def _runtime_value(value, default):
    if isinstance(value, str) and value.startswith('settings:'):
        return default
    return value if value not in {None, ''} else default

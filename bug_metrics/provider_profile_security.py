from typing import Any


PROFILE_SECRET_REDACTION = '[redacted]'


def is_profile_secret_key(key: str) -> bool:
    normalized = str(key or '').lower()
    if normalized in {'credential_ref', 'credential_reference'}:
        return False
    if normalized in {'credentials', 'credential_values'}:
        return True
    return any(fragment in normalized for fragment in ('token', 'password', 'secret'))


def without_profile_secret_values(value: Any):
    if isinstance(value, dict):
        return {
            key: without_profile_secret_values(item)
            for key, item in value.items()
            if not is_profile_secret_key(key)
        }
    if isinstance(value, list):
        return [without_profile_secret_values(item) for item in value]
    return value


def redacted_profile_secret_values(value: Any):
    if isinstance(value, dict):
        return {
            key: PROFILE_SECRET_REDACTION if is_profile_secret_key(key) else redacted_profile_secret_values(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redacted_profile_secret_values(item) for item in value]
    return value

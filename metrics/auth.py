import base64
from dataclasses import dataclass
import hmac
import json

from django.core.exceptions import ImproperlyConfigured


BASIC_AUTH_CHALLENGE = 'Basic realm="Restricted"'
BASIC_AUTH_SETTING = 'METRICS_BASIC_AUTH_USERS'


@dataclass(frozen=True, slots=True)
class BasicAuthIdentity:
    username: str
    anonymous: bool = False


def load_basic_auth_users(raw_value):
    if raw_value in (None, ''):
        return None
    if isinstance(raw_value, str):
        try:
            raw_value = json.loads(raw_value)
        except json.JSONDecodeError as error:
            raise ImproperlyConfigured(BASIC_AUTH_SETTING) from error
    if not isinstance(raw_value, dict) or not raw_value:
        raise ImproperlyConfigured(BASIC_AUTH_SETTING)
    for username, password in raw_value.items():
        if not isinstance(username, str) or not username:
            raise ImproperlyConfigured(BASIC_AUTH_SETTING)
        if not isinstance(password, str) or not password:
            raise ImproperlyConfigured(BASIC_AUTH_SETTING)
    return dict(raw_value)


def check_basic_authorization(users, authorization_header):
    if users is None:
        return BasicAuthIdentity('local_operator', anonymous=True)
    if not isinstance(users, dict) or not users:
        raise ImproperlyConfigured(BASIC_AUTH_SETTING)
    for username, password in users.items():
        if not isinstance(username, str) or not username:
            raise ImproperlyConfigured(BASIC_AUTH_SETTING)
        if not isinstance(password, str) or not password:
            raise ImproperlyConfigured(BASIC_AUTH_SETTING)

    if not authorization_header or not authorization_header.lower().startswith('basic '):
        return None
    try:
        token = authorization_header.split(' ', 1)[1]
        decoded = base64.b64decode(token, validate=True).decode('utf-8')
    except Exception:
        return None
    if ':' not in decoded:
        return None
    username, password = decoded.split(':', 1)
    expected = users.get(username)
    if expected is not None and hmac.compare_digest(
        expected.encode('utf-8'),
        password.encode('utf-8'),
    ):
        return BasicAuthIdentity(username)
    return None

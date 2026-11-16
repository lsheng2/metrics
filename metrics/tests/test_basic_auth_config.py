import base64

import pytest
from django.core.exceptions import ImproperlyConfigured

from metrics.auth import (
    BASIC_AUTH_CHALLENGE,
    check_basic_authorization,
    load_basic_auth_users,
)


def basic_header(username, password):
    token = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('ascii')
    return f'Basic {token}'


def test_shouldAcceptOnlyWellFormedBasicAuthUserSettings():
    assert load_basic_auth_users(None) is None
    assert load_basic_auth_users('') is None
    assert load_basic_auth_users('{"alice":"wonder"}') == {'alice': 'wonder'}
    assert load_basic_auth_users({'alice': 'wonder'}) == {'alice': 'wonder'}


@pytest.mark.parametrize('raw_value', [
    '[]',
    '{}',
    '{"":"wonder"}',
    '{"alice":""}',
    '{"alice":5}',
    ['alice'],
    {},
])
def test_shouldFailClosedForMalformedBasicAuthUsers(raw_value):
    with pytest.raises(ImproperlyConfigured) as raised:
        load_basic_auth_users(raw_value)

    assert str(raised.value) == 'METRICS_BASIC_AUTH_USERS'
    assert 'alice' not in str(raised.value)
    assert 'wonder' not in str(raised.value)


def test_shouldShareAuthorizationDecisionForDjangoAndRuntime():
    identity = check_basic_authorization(
        {'alice': 'wonder'},
        basic_header('alice', 'wonder'),
    )

    assert identity is not None
    assert identity.username == 'alice'
    assert identity.anonymous is False
    assert BASIC_AUTH_CHALLENGE == 'Basic realm="Restricted"'

    assert check_basic_authorization({'alice': 'wonder'}, basic_header('alice', 'wrong')) is None
    assert check_basic_authorization({'alice': 'wonder'}, None) is None


def test_shouldAcceptUtf8BasicCredentialsWithoutNormalizingIdentity():
    identity = check_basic_authorization(
        {'Ålice': 'päss'},
        basic_header('Ålice', 'päss'),
    )

    assert identity is not None
    assert identity.username == 'Ålice'
    assert identity.anonymous is False


def test_shouldReturnAnonymousLocalOperatorWhenBasicAuthIsNotConfigured():
    identity = check_basic_authorization(None, None)

    assert identity is not None
    assert identity.username == 'local_operator'
    assert identity.anonymous is True

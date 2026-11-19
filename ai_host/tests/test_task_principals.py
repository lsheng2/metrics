import pytest
from django.test import override_settings

from project_management.app.api import ProjectActor
from project_management.app.domain.run_contracts import RunError


def resolve(subject):
    from ai_host.principals import task_principal
    return task_principal(ProjectActor(subject))


@override_settings(METRICS_BASIC_AUTH_USERS={'alice': 'synthetic-password'})
def test_task_identity_uses_the_same_basic_subject_without_rewriting_archive_owner():
    value = resolve('basic:alice')
    assert (value.subject, value.runtime_subject, value.anonymous) == ('basic:alice', 'alice', False)
    with pytest.raises(RunError):
        resolve('basic:ali')
    with pytest.raises(RunError):
        resolve('alice')


@override_settings(METRICS_BASIC_AUTH_USERS=None)
def test_anonymous_host_accepts_only_the_local_operator_identity():
    value = resolve('local_operator')
    assert value.runtime_subject == 'local_operator' and value.anonymous
    with pytest.raises(RunError):
        resolve('basic:alice')


@override_settings(
    METRICS_BASIC_AUTH_USERS={'alice': 'synthetic-password'},
    METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='alice',
)
def test_local_cli_identity_requires_an_explicit_configured_basic_user():
    value = resolve('local_operator')
    assert (value.subject, value.runtime_subject, value.anonymous) == ('local_operator', 'alice', False)
    with override_settings(METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='bob'):
        with pytest.raises(RunError):
            resolve('local_operator')

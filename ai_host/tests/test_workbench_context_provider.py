from dataclasses import replace

import pytest
from django.test import override_settings
from django.urls import reverse

from ai_base_runtime.apps import ContextRef, ToolError
from ai_base_runtime.spi import Principal
from ai_host.tests.test_workbench_context_ref import page_state
from ai_host.workbench_context import build_context_ref
from bug_metrics.models import BugTrendScopeProviderBinding
from ui_web.tests.workbench_view_test_support import WorkbenchViewTestSupport


@pytest.fixture
def bound_state():
    scope = WorkbenchViewTestSupport()._bound_scope('chiplet-2a-jira', 'jira')
    return page_state(scope_id=str(scope.id), profile_id='chiplet-2a-jira')


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
@override_settings(METRICS_BASIC_AUTH_USERS=None)
async def test_resolves_registered_binding_to_safe_current_context(bound_state):
    from ai_host.context_provider import WORKBENCH_CONTEXT_PROVIDER

    principal = Principal(id='local_operator', display_name='Local operator', anonymous=True)
    ref = build_context_ref(bound_state)
    await WORKBENCH_CONTEXT_PROVIDER.validate(principal, ref)
    bundle = await WORKBENCH_CONTEXT_PROVIDER.resolve(principal, ref)

    assert bundle['status'] == 'ready'
    assert bundle['context_ref']['values']['binding_key'] == f'metrics.scope.{bound_state.scope_id}'
    assert bundle['boundary']['allowed_profile_ids'] == ['chiplet-2a-jira']
    assert bundle['boundary']['allowed_provider_ids'] == ['jira']
    assert bundle['bundle_version'].startswith('chiplet-2a-jira:')
    assert {item['role'] for item in bundle['files']} >= {'canonical_field_map', 'data_block_catalog'}
    assert not {'workspace_key', 'workspace_name', 'generated_at'} & set(bundle)


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
@override_settings(METRICS_BASIC_AUTH_USERS=None)
async def test_mismatched_profile_cannot_obtain_another_profile_bundle(bound_state):
    from ai_host.context_provider import WORKBENCH_CONTEXT_PROVIDER

    ref = build_context_ref(replace(bound_state, profile_id='nvu-ttl-hsdes', provider_id='hsdes'))
    principal = Principal(id='local_operator', display_name='Local operator', anonymous=True)
    with pytest.raises(ToolError) as error:
        await WORKBENCH_CONTEXT_PROVIDER.validate(principal, ref)
    assert error.value.code == 'context_boundary_violation'
    bundle = await WORKBENCH_CONTEXT_PROVIDER.resolve(principal, ref)
    assert bundle == {'status': 'binding_unresolved', 'repair_url': reverse('ui_web:bug_trend_scope_library')}


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
@override_settings(METRICS_BASIC_AUTH_USERS={'alice': 'synthetic-password'})
async def test_principal_must_match_host_identity_before_context_read(bound_state):
    from ai_host.context_provider import WORKBENCH_CONTEXT_PROVIDER

    ref = build_context_ref(bound_state)
    for principal in (Principal(id='mallory', display_name='Mallory'),
                      Principal(id='alice', display_name='Alice', anonymous=True)):
        with pytest.raises(ToolError) as error:
            await WORKBENCH_CONTEXT_PROVIDER.resolve(principal, ref)
        assert error.value.code == 'context_boundary_violation'


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
@override_settings(METRICS_BASIC_AUTH_USERS=None)
async def test_unknown_context_fields_are_not_forwarded_to_business_api(bound_state):
    from ai_host.context_provider import WORKBENCH_CONTEXT_PROVIDER

    ref = build_context_ref(bound_state)
    injected = ContextRef(kind=ref.kind, values={**ref.values, 'query': 'private query text'})
    with pytest.raises(ToolError) as error:
        await WORKBENCH_CONTEXT_PROVIDER.resolve(
            Principal(id='local_operator', display_name='Local operator', anonymous=True), injected,
        )
    assert error.value.code == 'context_boundary_violation'


@pytest.mark.django_db(transaction=True)
@override_settings(METRICS_BASIC_AUTH_USERS=None)
def test_changed_binding_is_resolved_again_instead_of_using_cached_context(bound_state):
    import asyncio
    from ai_host.context_provider import WORKBENCH_CONTEXT_PROVIDER

    principal = Principal(id='local_operator', display_name='Local operator', anonymous=True)
    ref = build_context_ref(bound_state)
    assert asyncio.run(WORKBENCH_CONTEXT_PROVIDER.resolve(principal, ref))['status'] == 'ready'
    BugTrendScopeProviderBinding.objects.filter(scope_id=int(bound_state.scope_id)).update(
        profile_id='nvu-ttl-hsdes', provider_id='hsdes',
    )
    bundle = asyncio.run(WORKBENCH_CONTEXT_PROVIDER.resolve(principal, ref))
    assert bundle['status'] == 'binding_unresolved'
    assert 'files' not in bundle


@pytest.mark.django_db(transaction=True)
@override_settings(METRICS_BASIC_AUTH_USERS=None)
def test_hsdes_bundle_uses_the_bound_provider_without_jira_defaults():
    import asyncio
    from ai_host.context_provider import WORKBENCH_CONTEXT_PROVIDER

    scope = WorkbenchViewTestSupport()._bound_scope('nvu-ttl-hsdes', 'hsdes')
    ref = build_context_ref(page_state(
        scope_id=str(scope.id), profile_id='nvu-ttl-hsdes', provider_id='hsdes',
    ))
    principal = Principal(id='local_operator', display_name='Local operator', anonymous=True)
    bundle = asyncio.run(WORKBENCH_CONTEXT_PROVIDER.resolve(principal, ref))
    assert bundle['status'] == 'ready'
    assert bundle['boundary']['allowed_provider_ids'] == ['hsdes']
    assert bundle['boundary']['allowed_profile_ids'] == ['nvu-ttl-hsdes']
    files = {item['role']: item for item in bundle['files']}
    assert files['provider_profile']['content_json']['provider_id'] == 'hsdes'
    assert files['canonical_field_map']['content_json']['provider_field_examples']['work_item_id'] == 'id'

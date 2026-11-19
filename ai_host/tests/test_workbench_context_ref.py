from dataclasses import replace
import json

import pytest

from ui_web.workbench_state import WorkbenchPageQueryState


def page_state(**overrides):
    return replace(WorkbenchPageQueryState(
        scope_id='42', profile_id='sample-jira', provider_id='jira',
        range_mode='date', begin='2026-11-01', end='2026-11-16',
        chart_id='open_bug_trend',
    ), **overrides)


def wire(ref):
    return {'kind': ref.kind, 'values': dict(ref.values)}


def test_context_ref_contains_only_server_resolved_identifiers():
    from ai_host.workbench_context import build_context_ref

    ref = build_context_ref(page_state())

    assert wire(ref) == {
        'kind': 'metrics.workbench',
        'values': {
            'binding_key': 'metrics.scope.42',
            'profile_id': 'sample-jira', 'provider_id': 'jira',
            'range_mode': 'date', 'begin': '2026-11-01', 'end': '2026-11-16',
            'chart_id': 'open_bug_trend', 'bucket': '', 'series': '',
            'ticket_ids': (), 'ticket_ids_total': 0, 'ticket_ids_truncated': False,
        },
    }


def test_selected_ticket_limit_keeps_selection_order():
    from ai_host.workbench_context import build_context_ref

    tickets = [f'SAMPLE-{index}' for index in range(51)]
    ref = build_context_ref(page_state(), ticket_ids=tickets)

    assert ref.values['ticket_ids'] == tuple(tickets[:50])
    assert ref.values['ticket_ids_total'] == 51
    assert ref.values['ticket_ids_truncated'] is True


def test_selected_ticket_byte_limit_keeps_longest_prefix():
    from ai_host.workbench_context import build_context_ref

    tickets = [f'{index:02d}' + 'x' * 78 for index in range(50)]
    ref = build_context_ref(page_state(
        scope_id='9' * 19, profile_id='p' * 160, provider_id='hsdes',
        chart_id='c' * 160, selected_bucket_id='b' * 160, selected_series_name='s' * 160,
    ), ticket_ids=tickets)
    payload = wire(ref)
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()

    assert len(encoded) <= 4096
    selected = payload['values']['ticket_ids']
    assert 0 < len(selected) < 50
    assert selected == tuple(tickets[:len(selected)])
    assert payload['values']['ticket_ids_total'] == 50
    assert payload['values']['ticket_ids_truncated'] is True
    payload['values']['ticket_ids'] = tickets[:len(selected) + 1]
    assert len(json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()) > 4096


@pytest.mark.parametrize('changes', [
    {'scope_id': ''}, {'scope_id': '../42'}, {'profile_id': ''},
    {'provider_id': ''}, {'profile_id': 'SELECT * FROM users'},
    {'begin': 'secret query text'}, {'chart_id': '../private/file'},
])
def test_invalid_or_unresolved_identifiers_do_not_produce_a_context(changes):
    from ai_host.workbench_context import build_context_ref

    assert build_context_ref(page_state(**changes)) is None


def test_browser_cannot_supply_resolved_profile_or_selected_ticket_bodies():
    from ai_host.workbench_context import build_context_ref

    state = WorkbenchPageQueryState.from_query({
        'scope_id': '42', 'profile_id': 'attacker', 'provider_id': 'jira',
        'begin': '2026-11-01', 'end': '2026-11-16',
    })
    assert build_context_ref(state) is None
    assert build_context_ref(page_state(), ticket_ids=['SAMPLE-1', 'private body\nsecret']) is None

from copy import deepcopy

import pytest

from project_management.app.api import reports as report_api
from project_management.app.domain.capture_values import canonical_bytes
from project_management.app.domain.report_authoring_fragments import plain_text_fragment
from project_management.app.domain.report_continuity_edits import apply_continuity_changes, apply_continuity_edit_requests
from project_management.tests.report_user_workflow_fixtures import daily, human, new_action, source_for
from project_management.tests.test_report_standup import render


def apply(ctx, *changes):
    return apply_continuity_changes(ctx, changes, 'meeting-host', '2026-11-02T02:00:00Z')


def test_human_ar_survives_newer_notes_and_week_rollover_without_inferred_prose_tasks():
    source = source_for()
    monday = human(daily(source, '2026-11-02'), 'AR: @Someone is plain text.')
    action = new_action(monday, owner={'owner_id': 'bob', 'display_name': 'Bob'})
    monday = apply(monday, action)
    tuesday = human(daily(source_for('2026-11-03', 2), '2026-11-03', monday), 'Newer note.')
    next_source = source_for('2026-11-09', 3)
    next_week = daily(next_source, '2026-11-09', tuesday)
    assert len(next_week['actions']) == 1
    assert next_week['actions'][0]['provenance']['created_by'] == 'meeting-host'
    assert next_week['actions'][0]['issued_meeting']['local_date'] == '2026-11-02'
    assert 'AR @Bob' in render(next_source, next_week).plain_text
    assert '@Someone' not in render(next_source, next_week).plain_text


def test_human_action_can_be_closed_and_reopened_with_resolution_without_fake_source_evidence():
    ctx = daily(source_for(), '2026-11-02')
    added = new_action(ctx)
    ctx = apply(ctx, added)
    command = {
        'kind': 'set_action_tracking', 'action_id': added['action_id'],
        'expected_state': 'open', 'state': 'done', 'resolution': plain_text_fragment('Verified in meeting.'),
        'evidence_refs': [],
    }
    done = apply(ctx, command)
    assert done['actions'][0]['tracking_state'] == 'done'
    assert done['actions'][0]['resolution']['resolved_by'] == 'meeting-host'
    reopened = apply(done, {**command, 'expected_state': 'done', 'state': 'open'})
    assert reopened['actions'][0]['tracking_state'] == 'open'
    with pytest.raises(report_api.ReportError):
        apply(ctx, {**command, 'resolution': plain_text_fragment('')})


def test_action_owner_change_is_explicit_cas_and_preserves_the_action_identity():
    ctx = daily(source_for(), '2026-11-02')
    added = new_action(ctx)
    ctx = apply(ctx, added)
    command = {'kind': 'set_action_owner', 'action_id': added['action_id'], 'expected_owner_ref': None,
               'owner_ref': {'owner_id': 'bob', 'display_name': 'Bob'}}
    changed = apply(ctx, command)
    assert changed['actions'][0]['action_id'] == ctx['actions'][0]['action_id']
    assert changed['actions'][0]['owner_ref']['display_name'] == 'Bob'
    with pytest.raises(report_api.ReportError):
        apply(changed, command)


@pytest.mark.parametrize('kind', ['duplicate', 'foreign-issue', 'blank-owner', 'blank-body'])
def test_human_action_rejects_ambiguous_or_empty_input(kind):
    ctx = daily(source_for(), '2026-11-02')
    command = new_action(ctx)
    if kind == 'duplicate':
        ctx = apply(ctx, command)
    elif kind == 'foreign-issue':
        command['issue_ref'] = {**command['issue_ref'], 'stable_id': 'other'}
    elif kind == 'blank-owner':
        command['owner_ref'] = {'owner_id': ' ', 'display_name': 'Bob'}
    else:
        command['fragment'] = plain_text_fragment('')
    before = canonical_bytes(ctx)
    with pytest.raises(report_api.ReportError):
        apply(ctx, command)
    assert canonical_bytes(ctx) == before


def test_discussion_is_explicit_and_does_not_turn_no_change_into_authored_text():
    source = source_for()
    ctx = daily(source, '2026-11-02')
    issue = ctx['row_order']['rows'][0]['issue_ref']
    for state in ('discussed', 'not_discussed', 'no_additional_update'):
        changed = apply(ctx, {'kind': 'set_meeting_review', 'issue_ref': issue, 'state': state})
        assert changed['meeting_reviews'][0]['state'] == state
        assert changed['meeting_reviews'][0]['recorded_by'] == 'meeting-host'
        assert not changed['notes']
        assert 'Meeting review: 1/1' in render(source, changed).plain_text
        cleared = apply(changed, {'kind': 'set_meeting_review', 'issue_ref': issue, 'state': 'unreviewed'})
        assert not cleared['meeting_reviews']
        next_day = daily(source_for('2026-11-03', 2), '2026-11-03', changed)
        assert not any(item['meeting']['local_date'] == '2026-11-03' for item in next_day['meeting_reviews'])


def test_source_action_closure_still_requires_its_original_evidence():
    ctx = daily(source_for(summary=True), '2026-11-02')
    action = ctx['actions'][0]
    with pytest.raises(report_api.ReportError):
        apply(ctx, {
            'kind': 'set_action_tracking', 'action_id': action['action_id'],
            'expected_state': action['tracking_state'], 'state': 'done',
            'resolution': plain_text_fragment('Claimed resolved.'), 'evidence_refs': [],
        })


def test_human_action_body_edit_updates_attribution_without_changing_creation():
    ctx = daily(source_for(), '2026-11-02')
    command = new_action(ctx)
    ctx = apply(ctx, command)
    edited, _ = apply_continuity_edit_requests(ctx, (), (report_api.AuthoredEditRequest(
        '93000000-0000-4000-8000-000000000001', 'note',
        {'scope': 'report_action', 'action_id': command['action_id']},
        plain_text_fragment('Updated follow-up.'),
    ),), 'second-host', '2026-11-02T03:00:00Z')
    assert edited['actions'][0]['provenance']['created_by'] == 'meeting-host'
    assert edited['actions'][0]['provenance']['updated_by'] == 'second-host'

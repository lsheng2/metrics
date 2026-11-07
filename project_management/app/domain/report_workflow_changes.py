from typing import Mapping

from project_management.app.domain.report_authoring_fragments import rich_text_fragment_plain_text, validate_rich_text_fragment
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_draft_values import validate_time_text, validate_uuid_text
from project_management.app.domain.report_observation_history import REVIEW_STATES, issue_key, upgrade_context


COMMAND_FIELDS = {
    'add_report_action': {'kind', 'action_id', 'issue_ref', 'owner_ref', 'fragment'},
    'set_action_owner': {'kind', 'action_id', 'expected_owner_ref', 'owner_ref'},
    'set_meeting_review': {'kind', 'issue_ref', 'state'},
}


def apply_workflow_change(context, change, actor, timestamp):
    if context['report_role'] != 'daily':
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    context = upgrade_context(context)
    if change['kind'] == 'add_report_action':
        action_id = validate_uuid_text(change['action_id'])
        if any(item['action_id'] == action_id for item in context['actions']):
            raise ReportError('REPORT_REVISION_CONFLICT')
        ref = _row_ref(context, change['issue_ref'])
        fragment = validate_rich_text_fragment(change['fragment'])
        if not rich_text_fragment_plain_text(fragment).strip():
            raise ReportError('REPORT_EDIT_TARGET_INVALID')
        action = {
            'action_id': action_id, 'issue_ref': ref, 'issued_meeting': context['meeting'],
            'owner_ref': owner_ref(change['owner_ref']), 'body_fragment': fragment,
            'basis': 'recorded', 'tracking_state': 'open', 'evidence_refs': (), 'resolution': None,
            'provenance': {'origin': 'human', 'created_by': actor, 'created_at': timestamp,
                           'updated_by': actor, 'updated_at': timestamp},
        }
        return _with_actions(context, (*context['actions'], action))
    if change['kind'] == 'set_action_owner':
        identity = validate_uuid_text(change['action_id'])
        owner = owner_ref(change['owner_ref'])
        actions, found = [], False
        for action in context['actions']:
            if action['action_id'] != identity:
                actions.append(action)
                continue
            found = True
            if action['owner_ref'] != change['expected_owner_ref']:
                raise ReportError('REPORT_REVISION_CONFLICT')
            # Provider-derived owners remain source evidence; create a human AR to assign different work.
            if not is_human_action(action):
                raise ReportError('REPORT_EDIT_TARGET_INVALID')
            actions.append(touch_action({**action, 'owner_ref': owner}, actor, timestamp))
        if not found:
            raise ReportError('REPORT_EDIT_TARGET_INVALID')
        return _with_actions(context, tuple(actions))
    ref = _row_ref(context, change['issue_ref'])
    if not any(issue_key(item['issue_ref']) == issue_key(ref) for item in context['current_observations']):
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    state = change['state']
    if state not in REVIEW_STATES | {'unreviewed'}:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    reviews = tuple(item for item in context['meeting_reviews']
                    if not (issue_key(item['issue_ref']) == issue_key(ref) and item['meeting'] == context['meeting']))
    if state != 'unreviewed':
        reviews += ({'issue_ref': ref, 'meeting': context['meeting'], 'state': state,
                     'recorded_by': actor, 'recorded_at': timestamp},)
    return {**context, 'meeting_reviews': reviews}


def is_human_action(action):
    return action.get('provenance', {}).get('origin') == 'human'


def touch_action(action, actor, timestamp):
    if not is_human_action(action):
        return action
    return {**action, 'provenance': {**action['provenance'], 'updated_by': actor, 'updated_at': timestamp}}


def owner_ref(value):
    if value is None:
        return None
    if not isinstance(value, Mapping) or set(value) != {'owner_id', 'display_name'}:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    return {key: _text(item, 160) for key, item in value.items()}


def validate_human_action(action):
    provenance = action['provenance']
    if not isinstance(provenance, Mapping) or set(provenance) != {
            'origin', 'created_by', 'created_at', 'updated_by', 'updated_at'}:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if provenance['origin'] != 'human' or action['basis'] != 'recorded' or action['evidence_refs']:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    try:
        owner_ref(action['owner_ref'])
        _text(provenance['created_by'], 512)
        _text(provenance['updated_by'], 512)
        validate_time_text(provenance['created_at'])
        validate_time_text(provenance['updated_at'])
        if not rich_text_fragment_plain_text(action['body_fragment']).strip():
            raise ReportError('REPORT_ARTIFACT_INVALID')
    except (TypeError, ValueError, ReportError):
        raise ReportError('REPORT_ARTIFACT_INVALID') from None


def _row_ref(context, value):
    if not isinstance(value, Mapping) or set(value) != {'provider_id', 'endpoint_fingerprint', 'stable_id', 'key_at_capture'}:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    for row in context['row_order']['rows']:
        if issue_key(row['issue_ref']) == issue_key(value):
            return row['issue_ref']
    raise ReportError('REPORT_EDIT_TARGET_INVALID')


def _text(value, limit):
    if type(value) is not str or not value.strip() or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    return value.strip()


def _with_actions(context, actions):
    return {**context, 'actions': actions, 'weekly_seed': {
        **context['weekly_seed'], 'unresolved_action_ids': tuple(
            item['action_id'] for item in actions if item['tracking_state'] not in {'done', 'canceled'}
        ),
    }}

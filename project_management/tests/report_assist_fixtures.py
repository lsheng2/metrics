from dataclasses import replace
from types import SimpleNamespace

from project_management.app.domain.report_authoring_fragments import plain_text_fragment
from project_management.tests.report_render_fixtures import safe_snapshot


def assist_draft(*, daily=False):
    snapshot = safe_snapshot(days=())
    snapshot = replace(snapshot, project_id='70000000-0000-4000-8000-000000000001',
                       stage_id='70000000-0000-4000-8000-000000000002', owner_subject='owner')
    context = None
    if daily:
        row = snapshot.rows[0]
        issue = {'provider_id': row.identity.provider_id, 'stable_id': row.identity.stable_id}
        context = {
            'report_role': 'daily',
            'current_observations': [{'note_id': '73000000-0000-4000-8000-000000000001', 'issue_ref': issue}],
            'notes': [{
                'note_id': '73000000-0000-4000-8000-000000000002', 'body_fragment': plain_text_fragment('Historical note.'),
            }],
            'persistent_notes': [], 'actions': [],
        }
    return SimpleNamespace(
        draft_id='72000000-0000-4000-8000-000000000001', revision=1, revision_hash='a' * 64,
        snapshot_hash='b' * 64, snapshot=snapshot, state='draft', authoring_schema='report-authoring/2',
        authoring_context=context, authored_edits=(),
        template_snapshot={
            'resolved_document': {'blocks': [
                {'kind': 'slot', 'slot_id': '74000000-0000-4000-8000-000000000001',
                 'fill_mode': 'ai_optional', 'initial': plain_text_fragment('')},
                {'kind': 'slot', 'slot_id': '74000000-0000-4000-8000-000000000002',
                 'fill_mode': 'manual', 'initial': plain_text_fragment('')},
            ]},
            'fill_policy': {'instructions': {}, 'daily_note_instructions': 'Keep status and next action concise.'},
            'fill_policy_hash': 'c' * 64,
        },
    )

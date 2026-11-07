from dataclasses import replace

from project_management.app.api import reports as report_api
from project_management.app.domain.report_authoring_fragments import plain_text_fragment
from project_management.app.domain.report_continuity_edits import apply_continuity_edit_requests
from project_management.tests.test_report_history_composer_fix2 import snapshot
from project_management.tests.test_report_template_compilation import matrix_block


def source_for(day='2026-11-02', index=1, *, summary=False):
    source = snapshot()
    row = source.rows[0]
    if not summary:
        row = replace(row, summary_ref=None, what=None, current_position=None,
                      verification=None, next_actions=(), evidence=(), blocker_refs=(),
                      limitation_refs=(), summary_as_of=None)
    row = replace(row, pending_reason=None if summary else 'summary_pending', title='Validation follow-up')
    return replace(
        source, rows=(row,), events=(), days=(), report_date=day,
        capture_id=f'80000000-0000-4000-8000-{index:012d}', source_as_of=f'{day}T01:00:00Z',
        coverage={'complete': summary, 'membership': {'state': 'complete'},
                  'accepted_count': int(summary), 'pending_count': int(not summary)},
    )


def daily(source, day, base=None):
    return report_api.build_daily_authoring_context(
        series_id='aaaaaaaa-aaaa-4aaa-8aaa-000000000001', series_policy_revision=1,
        series_policy_hash='1' * 64,
        meeting=report_api.meeting_identity(
            report_api.ReportingCalendar('iso8601', 1, 'Asia/Shanghai', 'iso8601', {}), day,
        ),
        source_snapshot=source, matrix_options=matrix_block()['options'], baseline_context=base,
    )


def human(ctx, text, index=1):
    observation = ctx['current_observations'][0]
    previous = next((note for note in ctx['notes'] if note['note_id'] == observation['note_id']), None)
    request = report_api.AuthoredEditRequest(
        f'73000000-0000-4000-8000-{index:012d}', 'note',
        {'scope': 'daily_note', 'note_id': observation['note_id']},
        plain_text_fragment(text), None if previous is None else previous['body_hash'],
    )
    return apply_continuity_edit_requests(ctx, (), (request,), 'host', '2026-11-03T01:00:00Z')[0]


def new_action(ctx, *, index=1, owner=None):
    return {
        'kind': 'add_report_action', 'action_id': f'74000000-0000-4000-8000-{index:012d}',
        'issue_ref': ctx['row_order']['rows'][0]['issue_ref'], 'owner_ref': owner,
        'fragment': plain_text_fragment('Rerun validation.'),
    }

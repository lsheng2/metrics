from dataclasses import replace
import hashlib

from project_management.app.api import reports as report_api
from project_management.app.domain.capture_values import canonical_bytes, content_hash
from project_management.app.domain.captures import SourceChainKey, WorkItemIdentity
from project_management.app.domain.report_contracts import (
    ReportDay,
    ReportEvent,
    ReportMessage,
    ReportRow,
    ReportSourceSnapshot,
    SummaryReference,
)


LONG_UNICODE_EVIDENCE = (
    'Long retained evidence segment with Unicode: 会议记录 Ω≈ç√ ∑ '
    + 'wrapped-value ' * 160
)
HOSTILE_TITLE = 'Escalation <script>alert("x")</script> & quoted'
HOSTILE_NOTE = '<img src=x onerror=alert(1)> =SUM(A1:A2) 会议备注 & "literal"'
MULTILINE_NOTE = 'First human note line\nSecond human note line with <b>literal</b>'


def draft_id(value: int) -> str:
    return f'aaaaaaaa-aaaa-4aaa-8aaa-{value:012d}'


def text_hash(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def source_key_hash(source_key: SourceChainKey) -> str:
    return hashlib.sha256(canonical_bytes(source_key)).hexdigest()


def daily_template(**options):
    return report_api.TemplateSelection('daily-standup', '1', options)


def weekly_template(**options):
    return report_api.TemplateSelection('weekly-timeline', '1', options)


def safe_snapshot(days=None) -> ReportSourceSnapshot:
    row_101 = _row_101()
    row_102 = _row_102()
    events = (
        ReportEvent(
            event_id='evt-status-101',
            source_key=row_101.source_key,
            kind='status_changed',
            before={'status': 'Triaged'},
            after={'status': 'In Progress'},
            occurred_at='2026-11-01T07:00:00Z',
            observed_at='2026-11-02T01:20:00Z',
            source_refs=('EV-101-A',),
        ),
        ReportEvent(
            event_id='evt-reopened-102',
            source_key=row_102.source_key,
            kind='reopened',
            before={'status': 'Closed'},
            after={'status': 'Fixed'},
            occurred_at=None,
            observed_at='2026-11-02T02:05:00Z',
            source_refs=('EV-102-A',),
        ),
    )
    return ReportSourceSnapshot(
        schema_version=1,
        project_id='demo-project',
        stage_id='bringup',
        project_name='Demo Project',
        stage_name='Silicon Bring-up',
        owner_subject='owner@example.com',
        rule_hash='rule-hash-render',
        source_commit='source-commit-render',
        capture_id='capture-render',
        source_as_of='2026-11-02T02:30:00Z',
        report_date='2026-11-02',
        timezone='Asia/Shanghai',
        baseline_publication_id=None,
        comparison_policy_hash='comparison-policy-render',
        coverage={
            'membership': {'state': 'complete', 'observed_count': 2, 'total_count': 2},
            'facts': {'state': 'complete', 'observed_count': 2, 'total_count': 2},
            'summaries': {'state': 'partial', 'observed_count': 1, 'total_count': 2},
            'limitations': ['HSD comments unavailable for DEMO-102'],
        },
        key_messages=(
            ReportMessage('msg-1', 'Two issues need review & owner follow-up.', ('EV-101-A',)),
            ReportMessage('msg-2', 'Formula-like value =1+1 stays text.', ('EV-102-A',)),
        ),
        rows=(row_101, row_102),
        events=events,
        days=_default_days(row_101, row_102, events) if days is None else days,
    )


def no_day_snapshot() -> ReportSourceSnapshot:
    return safe_snapshot(days=())


def too_many_day_snapshot() -> ReportSourceSnapshot:
    row = _row_101()
    return safe_snapshot(
        days=tuple(
            ReportDay(
                report_date=f'2026-10-{day:02d}',
                publication_id=f'pub-{day}',
                state='published',
                source_as_of=f'2026-10-{day:02d}T01:00:00Z',
                coverage={'membership': {'state': 'complete'}},
                rows=(row,),
                events=(),
            )
            for day in range(20, 28)
        )
    )


def hostile_edits(snapshot=None):
    snapshot = snapshot or safe_snapshot()
    row_101, row_102 = snapshot.rows
    return (
        report_api.ReportEdit(
            '11111111-1111-4111-8111-111111111111',
            'note',
            {'scope': 'report'},
            HOSTILE_NOTE,
            author='Meeting Chair',
            edited_at='2026-11-02T03:00:00Z',
        ),
        report_api.ReportEdit(
            '22222222-2222-4222-8222-222222222222',
            'note',
            {'scope': 'issue', 'source_key_hash': source_key_hash(row_101.source_key)},
            MULTILINE_NOTE,
            author='Meeting Chair',
            edited_at='2026-11-02T03:01:00Z',
        ),
        report_api.ReportEdit(
            '33333333-3333-4333-8333-333333333333',
            'note',
            {
                'scope': 'action',
                'source_key_hash': source_key_hash(row_102.source_key),
                'summary_id': row_102.summary_ref.summary_id,
                'action_index': 0,
            },
            'Action note: retest window stays Friday.',
            author='Meeting Chair',
            edited_at='2026-11-02T03:02:00Z',
        ),
        report_api.ReportEdit(
            '44444444-4444-4444-8444-444444444444',
            'narrative_override',
            {
                'scope': 'issue',
                'source_key_hash': source_key_hash(row_101.source_key),
                'field': 'what',
            },
            'Edited narrative: management asks for same-day triage.',
            expected_original_hash=text_hash(row_101.what),
            author='Meeting Chair',
            edited_at='2026-11-02T03:03:00Z',
        ),
        report_api.ReportEdit(
            '55555555-5555-4555-8555-555555555555',
            'narrative_override',
            {
                'scope': 'action',
                'source_key_hash': source_key_hash(row_102.source_key),
                'summary_id': row_102.summary_ref.summary_id,
                'action_index': 0,
                'field': 'owner_display',
            },
            'Dana Human Proposal',
            expected_original_hash=text_hash(row_102.next_actions[0]['owner_id']),
            author='Meeting Chair',
            edited_at='2026-11-02T03:04:00Z',
        ),
        report_api.ReportEdit(
            '66666666-6666-4666-8666-666666666666',
            'narrative_override',
            {'scope': 'message', 'message_id': 'msg-2', 'field': 'text'},
            'Edited key message keeps =1+1 literal.',
            expected_original_hash=text_hash(snapshot.key_messages[1].text),
            author='Meeting Chair',
            edited_at='2026-11-02T03:05:00Z',
        ),
    )


def _row_101() -> ReportRow:
    key = SourceChainKey('jira', 'team-jira', '10001', 'owner@example.com', 'rule-hash-render')
    summary = SummaryReference(
        summary_id='summary-101',
        revision=3,
        target_capture_id='capture-render',
        source_hash='summary-source-101',
        input_hash='summary-input-101',
        result_hash='summary-result-101',
        owning_commit='summary-commit-101',
    )
    return ReportRow(
        source_key=key,
        identity=WorkItemIdentity('jira', 'team-jira', '10001', 'DEMO-101'),
        title=HOSTILE_TITLE,
        status='In Progress',
        assignee={'key': 'dev-a', 'displayName': 'Alice'},
        source_url='https://jira.example.intel.com/browse/DEMO-101',
        source_hash='row-source-101',
        coverage={'facts': 'complete', 'comments': 'complete', 'summary': 'accepted'},
        summary_ref=summary,
        what='Power rail bring-up blocks boot after cold reset.',
        current_position='Scope is isolated to board A0 after overnight capture.',
        verification='Lab capture EV-101-A matches the accepted summary.',
        next_actions=(
            {
                'action': 'Retest fixed patch on board A0',
                'owner_id': 'qa-b',
                'owner_basis': 'explicit',
                'owner_quote': 'Bob (qa-b), please rerun validation on build r8.',
                'owner_confirmed': False,
                'state': 'open',
                'evidence': ('EV-101-A',),
            },
        ),
        blocker_refs=('EV-101-A',),
        limitation_refs=(),
        evidence=(
            {
                'ref_id': 'EV-101-A',
                'kind': 'history',
                'source_id': '12',
                'capture_id': 'capture-render',
                'json_pointer': '/history/12',
                'source_hash': content_hash({'text': LONG_UNICODE_EVIDENCE, 'sequence': 12}),
                'value': {'text': LONG_UNICODE_EVIDENCE, 'sequence': 12},
            },
        ),
        summary_as_of='2026-11-02T01:45:00Z',
        pending_reason='Waiting for owner confirmation from lab.',
    )


def _row_102() -> ReportRow:
    key = SourceChainKey('hsd', 'team-hsd', 'HSD-9002', 'owner@example.com', 'rule-hash-render')
    summary = SummaryReference(
        summary_id='summary-102',
        revision=2,
        target_capture_id='capture-render',
        source_hash='summary-source-102',
        input_hash='summary-input-102',
        result_hash='summary-result-102',
        owning_commit='summary-commit-102',
    )
    return ReportRow(
        source_key=key,
        identity=WorkItemIdentity('hsd', 'team-hsd', 'HSD-9002', 'DEMO-102'),
        title='Fixed watchdog issue still has open retest action',
        status='Fixed',
        assignee=None,
        source_url=None,
        source_hash='row-source-102',
        coverage={'facts': 'complete', 'comments': 'pending', 'summary': 'accepted'},
        summary_ref=summary,
        what='Watchdog timeout was fixed, but retest remains open.',
        current_position='Patch is merged in firmware branch rc-7.',
        verification='Retest is not complete until validation signs off.',
        next_actions=(
            {
                'action': 'Run open retest on firmware rc-7',
                'owner_id': 'dev-c',
                'owner_basis': 'explicit',
                'owner_quote': 'Chen will run the rc-7 retest.',
                'owner_confirmed': False,
                'state': 'open',
                'evidence': ('EV-102-A',),
            },
        ),
        blocker_refs=(),
        limitation_refs=('EV-102-A',),
        evidence=(
            {
                'ref_id': 'EV-102-A',
                'kind': 'comment',
                'source_id': '7',
                'capture_id': 'capture-render',
                'json_pointer': '/comments/7',
                'source_hash': content_hash({'body': 'Pending validation note with ampersand & less-than < markers.'}),
                'value': {'body': 'Pending validation note with ampersand & less-than < markers.'},
            },
        ),
        summary_as_of='2026-11-02T02:00:00Z',
        pending_reason=None,
    )


def _default_days(row_101, row_102, events):
    return (
        ReportDay(
            report_date='2026-11-01',
            publication_id='pub-2026-11-01',
            state='published',
            source_as_of='2026-11-01T02:30:00Z',
            coverage={'membership': {'state': 'complete', 'observed_count': 2, 'total_count': 2}, 'summary': 'accepted'},
            rows=(row_101, row_102),
            events=(events[0],),
        ),
        ReportDay(
            report_date='2026-11-02',
            publication_id=None,
            state='no_publication',
            source_as_of=None,
            coverage={'membership': {'state': 'no_publication'}},
            rows=(),
            events=(),
        ),
    )


def exact_three_comment_snapshot() -> ReportSourceSnapshot:
    row = _row_101()
    comments = (
        _comment_evidence('201', {'id': 201, 'body': 'Failure observed.', 'author': {'key': 'dev-a'}}),
        _comment_evidence('202', {'id': 202, 'body': 'Logs attached. Failure reproduced on build r7.'}),
        _comment_evidence(
            '203',
            {
                'id': 203,
                'body': 'Bob (qa-b), please rerun validation on build r8.',
                'author': {'key': 'qa-b', 'displayName': 'Bob'},
                'unicode': LONG_UNICODE_EVIDENCE,
                'retries': 2,
            },
        ),
    )
    row = replace(
        row,
        evidence=comments,
        next_actions=(dict(row.next_actions[0], evidence=('comment:203',)),),
    )
    return replace(safe_snapshot(days=()), rows=(row,), events=())


def weekly_union_snapshot() -> ReportSourceSnapshot:
    current = _row_101()
    departed = _row_102()
    closed = ReportEvent(
        'evt-closed-102',
        departed.source_key,
        'closed',
        {'status': 'In Progress'},
        {'status': 'Closed'},
        '2026-11-01T08:00:00Z',
        '2026-11-01T09:00:00Z',
        ('EV-102-A',),
    )
    reopened = ReportEvent(
        'evt-reopened-102',
        departed.source_key,
        'reopened',
        {'status': 'Closed'},
        {'status': 'Fixed'},
        '2026-11-01T10:00:00Z',
        '2026-11-01T10:30:00Z',
        ('EV-102-A',),
    )
    day = ReportDay(
        '2026-11-01',
        'pub-yesterday',
        'published',
        '2026-11-01T02:30:00Z',
        {'membership': {'state': 'complete'}, 'summary': 'partial'},
        (departed,),
        (closed, reopened),
    )
    return replace(safe_snapshot(days=(day,)), rows=(current,), events=())


def snapshot_with_source_url(source_url: str) -> ReportSourceSnapshot:
    snapshot = safe_snapshot(days=())
    return replace(snapshot, rows=(replace(snapshot.rows[0], source_url=source_url),))


def _comment_evidence(source_id: str, value: dict) -> dict:
    return {
        'ref_id': f'comment:{source_id}',
        'kind': 'comment',
        'source_id': source_id,
        'json_pointer': f'/comments/{source_id}',
        'value': value,
        'source_hash': content_hash(value),
        'capture_id': 'capture-render',
    }

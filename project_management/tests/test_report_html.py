from dataclasses import replace
import re
from html.parser import HTMLParser

import pytest

from project_management.app.api import reports as report_api
from project_management.reporting.validation import validate_rendered_html
from project_management.tests.report_render_fixtures import (
    HOSTILE_NOTE,
    HOSTILE_TITLE,
    LONG_UNICODE_EVIDENCE,
    MULTILINE_NOTE,
    daily_template,
    draft_id,
    exact_three_comment_snapshot,
    hostile_edits,
    safe_snapshot,
    snapshot_with_source_url,
    weekly_union_snapshot,
    weekly_template,
)


class ReportParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.attrs = []
        self.rows = []
        self.text_parts = []
        self._row = None
        self._cell = None

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs.extend((tag, key, value or '') for key, value in attrs)
        if tag == 'tr':
            self._row = []
        if tag in {'td', 'th'} and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag in {'td', 'th'} and self._row is not None and self._cell is not None:
            self._row.append(''.join(self._cell).strip())
            self._cell = None
        if tag == 'tr' and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        self.text_parts.append(data)
        if self._cell is not None:
            self._cell.append(data)

    @property
    def text(self):
        return ' '.join(part.strip() for part in self.text_parts if part.strip())


def test_literal_content_cannot_create_active_markup():
    snapshot = safe_snapshot()
    rendered = report_api.ReportRenderer().render(
        snapshot,
        daily_template(),
        hostile_edits(snapshot),
        draft_id=draft_id(10),
        revision=1,
    )
    parser = _parse(rendered.html_document)

    assert HOSTILE_TITLE in parser.text
    assert HOSTILE_NOTE in parser.text
    assert '=SUM(A1:A2)' in parser.text
    assert '会议备注' in parser.text
    assert snapshot.rows[0].title == HOSTILE_TITLE
    assert rendered.html_document.count(b'&lt;script&gt;') == 1
    assert rendered.html_document.count(b'&lt;img') == 1
    assert not ({'script', 'style', 'img', 'iframe', 'form'} & set(parser.tags))
    assert all(not name.lower().startswith('on') for _, name, _ in parser.attrs)
    assert all('javascript:' not in value.lower() for _, _, value in parser.attrs)


def test_email_fragment_is_self_contained():
    snapshot = safe_snapshot()
    rendered = report_api.ReportRenderer().render(
        snapshot,
        daily_template(group_by='status', optional_columns=['summary_time', 'source_hash']),
        hostile_edits(snapshot),
        draft_id=draft_id(11),
        revision=2,
        edition_state='final',
    )

    fragment = rendered.html_fragment
    assert fragment.startswith('<main')
    assert '<table' in fragment
    assert 'style="' in fragment
    assert 'Key messages' in fragment
    assert 'Changes' in fragment
    assert 'Issue register' in fragment
    assert 'Evidence and coverage' in fragment
    assert 'https://jira.example.intel.com/browse/DEMO-101' in fragment
    assert 'Meeting note' in fragment
    assert 'contenteditable' not in fragment
    assert 'localhost' not in fragment
    assert 'hx-' not in fragment
    assert '<script' not in fragment.lower()
    assert '<form' not in fragment.lower()
    assert '<button' not in fragment.lower()
    assert rendered.plain_text.count('DEMO-101') >= 1
    assert rendered.clipboard_available is True


def test_output_matches_independent_expected_fields():
    snapshot = safe_snapshot()
    edits = hostile_edits(snapshot)
    rendered = report_api.ReportRenderer().render(
        snapshot,
        daily_template(section_order=['register', 'key_messages', 'changes', 'coverage']),
        edits,
        draft_id=draft_id(12),
        revision=4,
    )

    parser = _parse(rendered.html_document)
    _assert_row_contains(parser.rows, 'DEMO-101', ('Alice', 'qa-b', 'open', 'EV-101-A'))
    _assert_row_contains(parser.rows, 'DEMO-102', ('Fixed', 'Dana Human Proposal', 'EV-102-A'))
    assert 'Edited narrative: management asks for same-day triage.' in parser.text
    assert 'Original: Power rail bring-up blocks boot after cold reset.' in parser.text
    assert 'Edited by Meeting Chair at 2026-11-02T03:04:00Z' in parser.text
    assert 'source confirmed: false' in parser.text
    assert 'summary-101' in parser.text
    assert 'summary-102' in parser.text
    assert 'row-source-101' in parser.text
    assert 'Action state: open' in parser.text
    assert 'Observed: 2026-11-02T01:20:00Z' in parser.text
    assert 'Occurred: unknown' in parser.text
    assert LONG_UNICODE_EVIDENCE in parser.text
    assert MULTILINE_NOTE in parser.text
    assert 'white-space:pre-wrap' in rendered.html_fragment


def test_actual_source_evidence_shape_preserves_pointer_and_nested_literal_json():
    rendered = report_api.ReportRenderer().render(
        exact_three_comment_snapshot(),
        daily_template(),
        draft_id=draft_id(13),
        revision=1,
    )
    parser = _parse(rendered.html_document)

    assert '/comments/203' in parser.text
    assert 'comment:201' in parser.text
    assert 'comment:202' in parser.text
    assert 'comment:203' in parser.text
    assert '"author":{"displayName":"Bob","key":"qa-b"}' in parser.text
    assert '"id":203' in parser.text
    assert '"retries":2' in parser.text
    assert LONG_UNICODE_EVIDENCE in parser.text


def test_evidence_rows_preserve_exact_issue_ref_pointer_hash_and_value_cells():
    snapshot = exact_three_comment_snapshot()
    rendered = report_api.ReportRenderer().render(
        snapshot,
        daily_template(),
        draft_id=draft_id(19),
        revision=1,
    )
    parser = _parse(rendered.html_document)
    rows = _evidence_rows(parser.rows)
    expected = {
        'comment:201': ('DEMO-101', 'capture-render / /comments/201', snapshot.rows[0].evidence[0]['source_hash'],
                        '{"author":{"key":"dev-a"},"body":"Failure observed.","id":201}'),
        'comment:202': ('DEMO-101', 'capture-render / /comments/202', snapshot.rows[0].evidence[1]['source_hash'],
                        '{"body":"Logs attached. Failure reproduced on build r7.","id":202}'),
        'comment:203': ('DEMO-101', 'capture-render / /comments/203', snapshot.rows[0].evidence[2]['source_hash'],
                        '{"author":{"displayName":"Bob","key":"qa-b"},"body":"Bob (qa-b), please rerun validation on build r8.","id":203,"retries":2,"unicode":"' + LONG_UNICODE_EVIDENCE + '"}'),
    }

    assert set(rows) == set(expected)
    for ref_id, (issue, pointer, source_hash, value) in expected.items():
        assert rows[ref_id] == (issue, pointer, f'Issue: row-source-101Evidence: {source_hash}', value)


def test_weekly_output_retains_mandatory_sections_notes_events_and_order():
    snapshot = safe_snapshot()
    rendered = report_api.ReportRenderer().render(
        snapshot,
        weekly_template(section_order=['changes', 'key_messages', 'register', 'coverage']),
        hostile_edits(snapshot),
        draft_id=draft_id(14),
        revision=1,
    )

    parser = _parse(rendered.html_document)
    assert 'Weekly timeline' in parser.text
    assert 'No published report' in parser.text
    assert parser.text.index('Changes') < parser.text.index('Key messages') < parser.text.index('Issue register')
    assert HOSTILE_NOTE in parser.text
    assert 'evt-status-101' in parser.text
    assert 'Edited key message keeps =1+1 literal.' in parser.text
    assert 'DEMO-101' in parser.text
    assert 'DEMO-102' in parser.text
    assert 'EV-101-A' in parser.text
    assert LONG_UNICODE_EVIDENCE in parser.text


def test_weekly_history_unions_day_only_rows_and_renders_day_events():
    rendered = report_api.ReportRenderer().render(
        weekly_union_snapshot(),
        weekly_template(),
        (),
        draft_id=draft_id(15),
        revision=1,
    )
    parser = _parse(rendered.html_document)

    _assert_row_contains(parser.rows, 'DEMO-102', ('Fixed', 'dev-c', 'open', 'partial'))
    assert 'Patch is merged in firmware branch rc-7.' in parser.text
    assert 'Run open retest on firmware rc-7' in parser.text
    assert 'evt-closed-102' in parser.text
    assert 'evt-reopened-102' in parser.text
    assert 'Not present in published report' in parser.text
    assert '| Published |' not in rendered.plain_text


def test_weekly_no_publication_day_preserves_coverage_and_known_events():
    snapshot = weekly_union_snapshot()
    no_publication_day = report_api.ReportDay(
        '2026-11-02',
        None,
        'no_publication',
        None,
        {'membership': {'state': 'partial', 'reason_code': 'capture_missing'}, 'summary': 'pending'},
        (),
        snapshot.days[0].events,
    )
    snapshot = replace(snapshot, days=(no_publication_day,))

    rendered = report_api.ReportRenderer().render(
        snapshot,
        weekly_template(),
        (),
        draft_id=draft_id(20),
        revision=1,
    )
    parser = _parse(rendered.html_document)
    demo_101_row = _single_timeline_row(parser.rows, 'DEMO-101')

    assert 'No published report' in ' | '.join(demo_101_row)
    assert 'membership.reason_code=capture_missing' in ' | '.join(demo_101_row)
    assert 'summary=pending' in ' | '.join(demo_101_row)
    assert 'evt-closed-102' not in ' | '.join(demo_101_row)
    assert 'evt-reopened-102' not in ' | '.join(demo_101_row)
    assert 'evt-closed-102' in parser.text
    assert 'evt-reopened-102' in parser.text
    assert 'hsd/team-hsd/HSD-9002' in parser.text


def test_limits_refuse_without_truncation():
    snapshot = safe_snapshot()
    renderer = report_api.ReportRenderer()
    rendered = renderer.render(snapshot, daily_template(), draft_id=draft_id(16), revision=1)

    exact_html = report_api.ReportRenderer(max_html_bytes=len(rendered.html_document)).render(
        snapshot,
        daily_template(),
        draft_id=draft_id(16),
        revision=1,
    )
    assert exact_html.html_document == rendered.html_document

    with pytest.raises(report_api.ReportError) as error:
        report_api.ReportRenderer(max_html_bytes=len(rendered.html_document) - 1).render(
            snapshot,
            daily_template(),
            draft_id=draft_id(16),
            revision=1,
        )
    assert error.value.code == 'REPORT_LIMIT'

    exact_clipboard = report_api.ReportRenderer(
        max_clipboard_bytes=len(rendered.html_fragment.encode('utf-8'))
    ).render(snapshot, daily_template(), draft_id=draft_id(16), revision=1)
    over_clipboard = report_api.ReportRenderer(
        max_clipboard_bytes=len(rendered.html_fragment.encode('utf-8')) - 1
    ).render(snapshot, daily_template(), draft_id=draft_id(16), revision=1)

    assert exact_clipboard.clipboard_available is True
    assert over_clipboard.clipboard_available is False
    assert over_clipboard.html_document == rendered.html_document
    assert LONG_UNICODE_EVIDENCE in over_clipboard.plain_text


def test_independent_parser_detects_mutated_output():
    snapshot = safe_snapshot()
    rendered = report_api.ReportRenderer().render(
        snapshot,
        daily_template(),
        hostile_edits(snapshot),
        draft_id=draft_id(17),
        revision=1,
    )
    document = rendered.html_document.decode('utf-8')

    _assert_semantic_document(document)

    with pytest.raises(AssertionError):
        _assert_semantic_document(_delete_row_containing(document, 'DEMO-102'))
    with pytest.raises(AssertionError):
        _assert_semantic_document(
            document.replace('<strong>Next owner:</strong> qa-b', '<strong>Next owner:</strong> dev-c', 1)
        )
    with pytest.raises(AssertionError):
        _assert_semantic_document(document.replace('会议备注', 'altered meeting note', 1))
    with pytest.raises(AssertionError):
        _assert_semantic_document(
            document.replace('https://jira.example.intel.com/browse/DEMO-101', 'http://localhost/bad', 1)
        )


def test_unsafe_source_urls_are_rejected_as_report_errors():
    bad_urls = (
        'https://tracker.example.test/jira bad/browse/DEMO-101',
        'https://tracker.example.test\\jira/browse/DEMO-101',
        'https://user:pass@tracker.example.test/jira/browse/DEMO-101',
        'https://tracker.example.test:bad/jira/browse/DEMO-101',
        'https://localhost/jira/browse/DEMO-101',
        'https://:443/jira/browse/DEMO-101',
    )

    for url in bad_urls:
        with pytest.raises(report_api.ReportError):
            report_api.ReportRenderer().render(
                snapshot_with_source_url(url),
                daily_template(),
                draft_id=draft_id(18),
                revision=1,
            )


def test_renderer_constructor_and_draft_id_validation():
    for kwargs in (
        {'max_html_bytes': 0},
        {'max_html_bytes': True},
        {'max_clipboard_bytes': -1},
        {'max_clipboard_bytes': 1.2},
    ):
        with pytest.raises(report_api.ReportError) as error:
            report_api.ReportRenderer(**kwargs)
        assert error.value.code == 'REPORT_INVALID'

    with pytest.raises(report_api.ReportError) as error:
        report_api.ReportRenderer().render(safe_snapshot(), daily_template(), draft_id='draft-not-uuid', revision=1)
    assert error.value.code == 'REPORT_INVALID'


def test_plain_text_includes_full_provenance_metadata():
    snapshot = safe_snapshot()
    rendered = report_api.ReportRenderer().render(
        snapshot,
        daily_template(),
        draft_id=draft_id(21),
        revision=1,
    )
    definition = report_api.ReportRenderer().template_definition(daily_template())

    for expected in (
        f"Capture id: {snapshot.capture_id}",
        f"Source commit: {snapshot.source_commit}",
        f"Rule hash: {snapshot.rule_hash}",
        f"Comparison policy: {snapshot.comparison_policy_hash}",
        f"Template hash: {definition.template_hash}",
        f"Renderer version: {definition.renderer_version}",
    ):
        assert expected in rendered.plain_text


def test_runtime_validator_rejects_injected_event_attributes():
    rendered = report_api.ReportRenderer().render(
        safe_snapshot(),
        daily_template(),
        draft_id=draft_id(22),
        revision=1,
    )
    document = rendered.html_document.decode('utf-8')

    with pytest.raises(report_api.ReportError):
        validate_rendered_html(document.replace('<td ', '<td onmouseover="alert(1)" ', 1))
    with pytest.raises(report_api.ReportError):
        validate_rendered_html(document.replace('<main ', '<main onerror="alert(1)" ', 1))


def test_renderer_revision_hash_is_optional_but_rendered_when_bound():
    unbound = report_api.ReportRenderer().render(
        safe_snapshot(),
        daily_template(),
        draft_id=draft_id(23),
        revision=1,
    )
    revision_hash = '1' * 64

    bound = report_api.ReportRenderer().render(
        safe_snapshot(),
        daily_template(),
        draft_id=draft_id(23),
        revision=1,
        revision_hash=revision_hash,
    )

    assert unbound.revision_hash is None
    assert bound.revision_hash == revision_hash
    assert revision_hash in bound.html_fragment
    assert f'Revision hash: {revision_hash}' in bound.plain_text


def test_renderer_rejects_malformed_revision_hash():
    with pytest.raises(report_api.ReportError) as error:
        report_api.ReportRenderer().render(
            safe_snapshot(),
            daily_template(),
            draft_id=draft_id(24),
            revision=1,
            revision_hash='not-a-hash',
        )

    assert error.value.code == 'REPORT_INVALID'


def _parse(document):
    parser = ReportParser()
    parser.feed(document.decode('utf-8') if isinstance(document, bytes) else document)
    return parser


def _assert_row_contains(rows, key, values):
    matching = [
        ' | '.join(row)
        for row in rows
        if any(key in cell for cell in row) and all(value in ' | '.join(row) for value in values)
    ]
    assert len(matching) == 1


def _single_row_containing(rows, key):
    matching = [row for row in rows if any(key in cell for cell in row)]
    assert len(matching) == 1
    return matching[0]


def _single_timeline_row(rows, key):
    matching = [row for row in rows if len(row) == 3 and row[0] == key]
    assert len(matching) == 1
    return matching[0]


def _evidence_rows(rows):
    result = {}
    for row in rows:
        if len(row) == 5 and row[1].startswith('comment:'):
            result[row[1]] = (row[0], row[2], row[3], row[4])
    return result


def _assert_semantic_document(document):
    parser = _parse(document)
    text = parser.text
    _assert_row_contains(parser.rows, 'DEMO-101', ('Alice', 'qa-b', 'EV-101-A'))
    _assert_row_contains(parser.rows, 'DEMO-102', ('Fixed', 'Dana Human Proposal', 'EV-102-A'))
    assert '<strong>Next owner:</strong> qa-b' in document
    assert '<strong>Next owner:</strong> Dana Human Proposal' in document
    assert HOSTILE_NOTE in text
    assert 'https://jira.example.intel.com/browse/DEMO-101' in document
    assert 'http://localhost/bad' not in document


def _delete_row_containing(document, text):
    return re.sub(r'<tr>[^<]*(?:(?!</tr>).)*?' + re.escape(text) + r'(?:(?!</tr>).)*?</tr>', '', document, count=1, flags=re.S)

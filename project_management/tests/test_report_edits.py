import pytest

from project_management.app.api import reports as report_api
from project_management.app.domain.report_edits import original_target_text, validate_edit_targets
from project_management.tests.report_render_fixtures import (
    daily_template,
    draft_id,
    hostile_edits,
    safe_snapshot,
    source_key_hash,
    text_hash,
)


def test_validate_edit_targets_accepts_notes_and_overrides_without_mutating_snapshot():
    snapshot = safe_snapshot()
    original_what = snapshot.rows[0].what
    original_owner = snapshot.rows[1].next_actions[0]['owner_id']

    edits = validate_edit_targets(snapshot, hostile_edits(snapshot))
    rendered = report_api.ReportRenderer().render(
        snapshot,
        daily_template(),
        edits,
        draft_id=draft_id(30),
        revision=1,
    )

    assert len(edits) == 6
    assert snapshot.rows[0].what == original_what
    assert snapshot.rows[1].next_actions[0]['owner_id'] == original_owner
    assert snapshot.rows[1].next_actions[0]['owner_confirmed'] is False
    assert 'Edited by Meeting Chair at 2026-11-02T03:04:00Z' in rendered.plain_text
    assert 'Original: dev-c' in rendered.plain_text
    assert 'Human proposal; source confirmed: false' in rendered.plain_text


def test_original_target_text_returns_each_editable_source_text():
    snapshot = safe_snapshot()
    row_101, row_102 = snapshot.rows

    assert original_target_text(
        snapshot,
        {'scope': 'issue', 'source_key_hash': source_key_hash(row_101.source_key), 'field': 'what'},
    ) == row_101.what
    assert original_target_text(
        snapshot,
        {
            'scope': 'action',
            'source_key_hash': source_key_hash(row_102.source_key),
            'summary_id': 'summary-102',
            'action_index': 0,
            'field': 'action',
        },
    ) == row_102.next_actions[0]['action']
    assert original_target_text(
        snapshot,
        {
            'scope': 'action',
            'source_key_hash': source_key_hash(row_102.source_key),
            'summary_id': 'summary-102',
            'action_index': 0,
            'field': 'owner_display',
        },
    ) == 'dev-c'
    assert original_target_text(
        snapshot,
        {'scope': 'message', 'message_id': 'msg-1', 'field': 'text'},
    ) == snapshot.key_messages[0].text
    assert original_target_text(snapshot, {'scope': 'report'}) is None


@pytest.mark.parametrize(
    'edit',
    [
        lambda snapshot: report_api.ReportEdit(
            'not-a-uuid',
            'note',
            {'scope': 'report'},
            'valid text',
        ),
        lambda snapshot: report_api.ReportEdit(
            '77777777-7777-4777-8777-777777777777',
            'note',
            {'scope': 'unknown'},
            'valid text',
        ),
        lambda snapshot: report_api.ReportEdit(
            '77777777-7777-4777-8777-777777777777',
            'note',
            {'scope': 'report', 'extra': 'bad'},
            'valid text',
        ),
        lambda snapshot: report_api.ReportEdit(
            '77777777-7777-4777-8777-777777777777',
            'note',
            {'scope': 'issue', 'source_key_hash': 'missing'},
            'valid text',
        ),
        lambda snapshot: report_api.ReportEdit(
            '77777777-7777-4777-8777-777777777777',
            'narrative_override',
            {
                'scope': 'issue',
                'source_key_hash': source_key_hash(snapshot.rows[0].source_key),
                'field': 'status',
            },
            'valid text',
        ),
        lambda snapshot: report_api.ReportEdit(
            '77777777-7777-4777-8777-777777777777',
            'note',
            {
                'scope': 'action',
                'source_key_hash': source_key_hash(snapshot.rows[0].source_key),
                'summary_id': 'summary-101',
                'action_index': 9,
            },
            'valid text',
        ),
        lambda snapshot: report_api.ReportEdit(
            '77777777-7777-4777-8777-777777777777',
            'narrative_override',
            {'scope': 'message', 'message_id': 'missing', 'field': 'text'},
            'valid text',
        ),
        lambda snapshot: report_api.ReportEdit(
            '77777777-7777-4777-8777-777777777777',
            'narrative_override',
            {
                'scope': 'issue',
                'source_key_hash': source_key_hash(snapshot.rows[0].source_key),
                'field': 'what',
            },
            'valid text',
            expected_original_hash=text_hash('stale original'),
        ),
        lambda snapshot: report_api.ReportEdit(
            '77777777-7777-4777-8777-777777777777',
            'narrative_override',
            {
                'scope': 'issue',
                'source_key_hash': source_key_hash(snapshot.rows[0].source_key),
                'field': 'what',
            },
            '',
            expected_original_hash=text_hash(snapshot.rows[0].what),
        ),
        lambda snapshot: report_api.ReportEdit(
            '77777777-7777-4777-8777-777777777777',
            'note',
            {'scope': 'report'},
            'bad\x00text',
        ),
    ],
)
def test_edit_target_validation_rejects_invalid_edit(edit):
    with pytest.raises(report_api.ReportError) as error:
        validate_edit_targets(safe_snapshot(), (edit(safe_snapshot()),))

    assert error.value.code == 'REPORT_EDIT_TARGET_INVALID'


def test_edit_target_validation_rejects_duplicate_overrides():
    snapshot = safe_snapshot()
    row = snapshot.rows[0]
    first = report_api.ReportEdit(
        '88888888-8888-4888-8888-888888888888',
        'narrative_override',
        {'scope': 'issue', 'source_key_hash': source_key_hash(row.source_key), 'field': 'what'},
        'first replacement',
        expected_original_hash=text_hash(row.what),
    )
    second = report_api.ReportEdit(
        '99999999-9999-4999-8999-999999999999',
        'narrative_override',
        {'scope': 'issue', 'source_key_hash': source_key_hash(row.source_key), 'field': 'what'},
        'second replacement',
        expected_original_hash=text_hash(row.what),
    )

    with pytest.raises(report_api.ReportError) as error:
        validate_edit_targets(snapshot, (first, second))

    assert error.value.code == 'REPORT_EDIT_TARGET_INVALID'


def test_edit_text_length_boundaries_are_enforced():
    snapshot = safe_snapshot()
    exact_text = 'x' * 16_384
    too_long_text = exact_text + 'x'

    validate_edit_targets(
        snapshot,
        (
            report_api.ReportEdit(
                'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
                'note',
                {'scope': 'report'},
                exact_text,
            ),
        ),
    )
    with pytest.raises(report_api.ReportError) as error:
        validate_edit_targets(
            snapshot,
            (
                report_api.ReportEdit(
                    'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
                    'note',
                    {'scope': 'report'},
                    too_long_text,
                ),
            ),
        )

    assert error.value.code == 'REPORT_EDIT_TARGET_INVALID'


def test_edit_boundary_rejects_malformed_target_without_raw_archive_error():
    edit = report_api.ReportEdit(
        'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
        'note',
        {1: 'bad-key'},
        'valid text',
    )

    with pytest.raises(report_api.ReportError) as error:
        validate_edit_targets(safe_snapshot(), (edit,))

    assert error.value.code == 'REPORT_EDIT_TARGET_INVALID'


def test_edit_boundary_rejects_unencodable_text_without_raw_unicode_error():
    edit = report_api.ReportEdit(
        'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
        'note',
        {'scope': 'report'},
        'bad\ud800text',
    )

    with pytest.raises(report_api.ReportError) as error:
        validate_edit_targets(safe_snapshot(), (edit,))

    assert error.value.code == 'REPORT_EDIT_TARGET_INVALID'
